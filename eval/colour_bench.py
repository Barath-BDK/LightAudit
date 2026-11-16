"""Light-colour consistency on real indoor scenes (MIT Multi-Illumination), whole-object check.

Idea (Riess & Angelopoulou 2010; de Carvalho et al. 2013): estimate the colour of the light falling on each region
and flag the region whose light colour disagrees with the rest. Needs no normals. Estimators per region (linear RGB,
region eroded by 2 px): grey-world (mean), grey-edge (Minkowski p-norm of gradients, van de Weijer 2007) and
white-patch (99th percentile). Score of an image = the largest leave-one-out angular distance between a region's
illuminant chromaticity and the median of the others, divided by a per-region noise level (bootstrap spread).

Splices are made at the level of region statistics: region k's statistics replaced by
  * relit: the same region under another flash direction of the same scene (>= 40 deg apart);
  * foreign: a region of another scene (any of its lightings): a paste from another photo.
Thresholds come from clean images of the OTHER scenes (leave-one-scene-out), so false-alarm rates are honest.
The current whole-object score on the same scenes is AUC 0.49-0.59 (HANDOVER.md 5).

    python eval/colour_bench.py         # writes data/results/colour_bench.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from scipy import ndimage as ndi

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "eval"))
from real_bench import DATA, NDIR, ang, auc, load, scenes  # noqa: E402

EST = ("grey_world", "grey_edge", "white_patch")
MIN_AREA = 2000


def chroma(v):
    v = np.maximum(np.asarray(v, float), 1e-9)
    return v / np.linalg.norm(v, axis=-1, keepdims=True)


def region_illum(lin: np.ndarray, m: np.ndarray, rng, n_boot: int = 20) -> dict:
    """Unit illuminant RGB per estimator, plus its bootstrap angular spread (deg) over pixel blocks."""
    ys, xs = np.nonzero(m)
    px = lin[ys, xs]
    gy, gx = np.gradient(lin, axis=(0, 1))
    g = np.sqrt(gx ** 2 + gy ** 2)[ys, xs]
    ok = px.max(1) < 0.95  # clipped pixels say nothing about the light colour
    if ok.sum() < 200:
        return None
    px, g = px[ok], g[ok]
    blocks = ((ys[ok] // 16) * 4096 + xs[ok] // 16)
    ub, inv = np.unique(blocks, return_inverse=True)

    def est(sel):
        p, q = px[sel], g[sel]
        return {"grey_world": p.mean(0), "grey_edge": (q ** 6).mean(0) ** (1 / 6), "white_patch": np.percentile(p, 99, axis=0)}

    full = {k: chroma(v) for k, v in est(np.ones(len(px), bool)).items()}
    boots = {k: [] for k in EST}
    for _ in range(n_boot):
        pick = rng.choice(len(ub), len(ub))
        sel = np.isin(inv, pick)
        for k, v in est(sel).items():
            boots[k].append(ang(chroma(v), full[k]))
    return {k: (full[k], max(float(np.percentile(boots[k], 68)), 0.3)) for k in EST}


def scene_stats(scene: str) -> dict:
    f = DATA / scene / "colour_v1.npz"
    prep = np.load(DATA / scene / "prep.npz")
    labels = prep["labels"]
    ids = [k for k in range(1, int(labels.max()) + 1) if (labels == k).sum() >= MIN_AREA]
    masks = [ndi.binary_erosion(labels == k, iterations=2) for k in ids]
    if f.exists():
        z = np.load(f, allow_pickle=True)
        return dict(st=z["st"].tolist(), gt=prep["gt"], ids=ids)
    rng = np.random.default_rng(0)
    st = []
    for d in range(NDIR):
        lin = (load(scene, d).astype(np.float64) / 255) ** 2.2
        st.append([region_illum(lin, m, rng) for m in masks])
    np.savez_compressed(f, st=np.array(st, dtype=object))
    return dict(st=st, gt=prep["gt"], ids=ids)


def image_score(regs: list[dict], key: str) -> tuple[float, int]:
    """Largest leave-one-out deviation (in units of each region's own noise) and its region index (None skipped)."""
    idx = [k for k, r in enumerate(regs) if r is not None]
    C = np.array([regs[k][key][0] for k in idx])
    s = np.array([regs[k][key][1] for k in idx])
    out = [ang(C[n], chroma(np.median(np.delete(C, n, 0), 0))) / s[n] for n in range(len(C))]
    n = int(np.argmax(out))
    return float(out[n]), idx[n]


def run(min_delta: float = 40.0, seed: int = 0, alpha: float = 0.10):
    rng = np.random.default_rng(seed)
    sc = [s for s in scenes() if (DATA / s / "prep.npz").exists()]
    S = {s: scene_stats(s) for s in sc}
    rows = []
    for s in sc:
        st, gt = S[s]["st"], S[s]["gt"]
        ga = ang(gt[:, None], gt[None])
        others = [o for o in sc if o != s]
        for i in range(NDIR):
            base = st[i]
            if sum(r is not None for r in base) < 4:
                continue
            rows.append(dict(scene=s, kind="clean", **{k: image_score(base, k)[0] for k in EST}))
            for k in range(len(base)):
                if base[k] is None:
                    continue
                cand = [j for j in range(NDIR) if ga[i, j] >= min_delta and st[j][k] is not None]
                if not cand:
                    continue
                j = int(rng.choice(cand))
                sp = list(base)
                sp[k] = st[j][k]
                r = dict(scene=s, kind="relit", delta=float(ga[i, j]))
                for e in EST:
                    v, top = image_score(sp, e)
                    r[e], r[e + "_top"] = v, top == k
                rows.append(r)
                o = others[int(rng.integers(len(others)))]
                so = S[o]["st"][int(rng.integers(NDIR))]
                sp = list(base)
                sp[k] = [q for q in so if q is not None][int(rng.integers(sum(q is not None for q in so)))]
                r = dict(scene=s, kind="foreign")
                for e in EST:
                    v, top = image_score(sp, e)
                    r[e], r[e + "_top"] = v, top == k
                rows.append(r)
    out = {}
    kind = np.array([r["kind"] for r in rows])
    scn = np.array([r["scene"] for r in rows])
    for e in EST:
        x = np.array([r[e] for r in rows])
        res = {f"auc_{kd}": auc(x[kind == "clean"], x[kind == kd]) for kd in ("relit", "foreign")}
        res.update({f"top1_{kd}": float(np.mean([r[e + "_top"] for r in rows if r["kind"] == kd])) for kd in ("relit", "foreign")})
        fa, det = [], {"relit": [], "foreign": []}
        for s in sc:
            thr = np.quantile(x[(kind == "clean") & (scn != s)], 1 - alpha)
            t = scn == s
            fa += list(x[t & (kind == "clean")] > thr)
            for kd in det:
                det[kd] += list(x[t & (kind == kd)] > thr)
        res.update(false_alarms=float(np.mean(fa)), det_relit=float(np.mean(det["relit"])), det_foreign=float(np.mean(det["foreign"])))
        out[e] = res
        print(f"{e:11s} AUC relit {res['auc_relit']:.3f} foreign {res['auc_foreign']:.3f} | top-1 relit {res['top1_relit']:.2f} "
              f"foreign {res['top1_foreign']:.2f} | held-out scene @{alpha}: FA {res['false_alarms']:.3f} relit {res['det_relit']:.3f} "
              f"foreign {res['det_foreign']:.3f}", flush=True)
    out["n"] = {kd: int((kind == kd).sum()) for kd in ("clean", "relit", "foreign")}
    (ROOT / "data" / "results" / "colour_bench.json").write_text(json.dumps(out, indent=1))
    return out


if __name__ == "__main__":
    run()
