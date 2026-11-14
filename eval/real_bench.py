"""Real-image benchmark on the MIT Multi-Illumination dataset (Murmann et al., ICCV 2019).

Each scene is one real, static scene photographed under 25 flash/bounce light directions, with a diffuse gray ball
and a chrome ball in view. Geometry is identical across the 25 images, so:
  * regions and normals are computed once per scene (on the mean image, which is evenly lit);
  * the true dominant light of every image is read from the gray-ball crop (analytic sphere normals);
  * a lighting-only splice "region k from lighting j pasted into the image under lighting i" is just region k's
    pixels from image j with everything else from image i: the geometry lines up exactly.

    python eval/real_bench.py prepare [scene ...]     # SAM regions + normal ensemble + GT lights -> prep.npz
    python eval/real_bench.py fetch N                 # download N more scenes (mip3 jpg + probes)
"""
from __future__ import annotations

import io
import json
import sys
import urllib.request
import zipfile
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "multilum"
BASE = "https://data.csail.mit.edu/multilum"
NDIR = 25


def scenes() -> list[str]:
    return sorted(p.name for p in DATA.iterdir() if (p / "dir_24_mip3.jpg").exists())


def fetch(n: int) -> None:
    """Download n more scenes (about 2.5 MB each)."""
    names = [x["name"] for x in json.loads((DATA / "scenes.json").read_text())]
    have, got = set(scenes()), 0
    for sc in names[:: max(1, len(names) // (n * 3))]:  # spread over buildings / rooms
        if got >= n:
            break
        if sc in have:
            continue
        try:
            for url, sub in ((f"{BASE}/{sc}/{sc}_mip3_jpg.zip", ""), (f"{BASE}/{sc}/{sc}_probes_256px_jpg.zip", "probes")):
                req = urllib.request.Request(url, headers={"User-Agent": "research-client/1.0"})
                z = zipfile.ZipFile(io.BytesIO(urllib.request.urlopen(req, timeout=180).read()))
                d = DATA / sc / sub
                d.mkdir(parents=True, exist_ok=True)
                for m in z.namelist():
                    if m.lower().endswith(".jpg") and ".." not in m:
                        (d / Path(m).name).write_bytes(z.read(m))
            got += 1
            print("fetched", sc, flush=True)
        except Exception as e:
            print("failed", sc, type(e).__name__, flush=True)


def load(scene: str, d: int) -> np.ndarray:
    return np.asarray(Image.open(DATA / scene / f"dir_{d}_mip3.jpg").convert("RGB"))


def sphere_normals(size: int):
    """Analytic normals of a centred sphere crop (camera space: +x right, +y up, +z to the viewer) + mask."""
    c = (np.arange(size) + 0.5) / size * 2 - 1
    x, y = np.meshgrid(c, -c)
    r2 = x * x + y * y
    m = r2 < 0.92 ** 2
    z = np.sqrt(np.clip(1 - r2, 0, 1))
    return np.stack([x, y, z], -1).astype(np.float32), m


def gt_lights(scene: str) -> np.ndarray:
    """(25, 3) dominant light per image: the best single directional light for the gray ball (least squares on
    analytic normals). This is the same quantity a region estimate is trying to recover."""
    from lightaudit.cues import ls_landscape
    from lightaudit.grid import eq_dirs
    from lightaudit.imageio import luminance
    out = np.zeros((NDIR, 3), np.float32)
    for d in range(NDIR):
        g = np.asarray(Image.open(DATA / scene / "probes" / f"dir_{d}_gray256.jpg").convert("RGB"))
        n, m = sphere_normals(g.shape[0])
        Y = luminance(g)
        m = m & (Y > 0.03) & (Y < 0.97)
        idx = np.flatnonzero(m.ravel())[:: max(1, int(m.sum()) // 3000)]
        S = ls_landscape(n.reshape(-1, 3)[idx], Y.ravel()[idx], eq_dirs())
        out[d] = eq_dirs()[int(np.argmax(S))]
    return out


def prepare(scene: str) -> Path:
    """Regions (SAM on the mean image), normal ensemble (DSINE + Depth Anything on the mean image), GT lights."""
    from lightaudit.config import Config
    from lightaudit.normals import predict_normals, sam_regions
    out = DATA / scene / "prep.npz"
    if out.exists():
        return out
    cfg = Config()
    mean = np.mean([load(scene, d).astype(np.float32) for d in range(NDIR)], 0)
    mean = np.clip(mean * (140 / max(mean.mean(), 1)), 0, 255).astype(np.uint8)  # evenly lit, normal exposure
    normals, unc, info = predict_normals(mean, ("dsine", "depth_anything"))
    try:
        labels, meta = sam_regions(mean, cfg)
        src = "sam"
    except Exception as e:
        from lightaudit.regions import slic_regions
        labels, meta = slic_regions(mean, normals, cfg)
        src = f"slic ({type(e).__name__})"
    np.savez_compressed(out, normals=normals.astype(np.float16), unc=unc.astype(np.float16), labels=labels.astype(np.int16),
                        gt=gt_lights(scene), backends=np.array("+".join(info.get("backends", []))), regions=np.array(src))
    Image.fromarray(mean).save(DATA / scene / "mean.jpg", quality=92)
    print(f"{scene}: {int(labels.max())} regions ({src}), normals {info.get('backends')}", flush=True)
    return out


def renormal(scene: str) -> None:
    """Recompute the normals of a prepared scene (keeps the regions): each backend separately + the ensemble."""
    from lightaudit import normals as NM
    f = DATA / scene / "prep.npz"
    z = dict(np.load(f))
    mean = np.asarray(Image.open(DATA / scene / "mean.jpg").convert("RGB"))
    log: list = []
    for be in ("dsine", "depth_anything"):
        z["normals_" + be] = NM._cached_backend(be, mean, 60.0, log).astype(np.float16)
    n, unc, info = NM.predict_normals(mean, ("dsine", "depth_anything"))
    z.update(normals=n.astype(np.float16), unc=unc.astype(np.float16), backends=np.array("+".join(info.get("backends", []))))
    for old in f.parent.glob("land_*.npz"):
        old.unlink()
    np.savez_compressed(f, **z)
    print(f"{scene}: normals recomputed ({info.get('backends')})", flush=True)


def find_ball(scene: str, kind: str = "gray"):
    """Locate the calibration ball in the full image by masked template matching: (x0, y0, size)."""
    import cv2
    img = cv2.cvtColor(load(scene, 0), cv2.COLOR_RGB2GRAY).astype(np.float32)
    probe = np.asarray(Image.open(DATA / scene / "probes" / f"dir_0_{kind}256.jpg").convert("L")).astype(np.float32)
    best = (-1.0, None)
    for size in range(24, 150, 4):
        t = cv2.resize(probe, (size, size), interpolation=cv2.INTER_AREA)
        m = np.zeros((size, size), np.uint8)
        cv2.circle(m, (size // 2, size // 2), int(size * 0.46), 255, -1)
        r = cv2.matchTemplate(img, t, cv2.TM_CCORR_NORMED, mask=m)
        r[~np.isfinite(r)] = -1
        _, v, _, loc = cv2.minMaxLoc(r)
        if v > best[0]:
            best = (v, (loc[0], loc[1], size))
    return best[1]


def ball_check(scene: str) -> dict:
    """Normal error of every normal source on the gray ball (true shape known), and the light error it causes."""
    from lightaudit.cues import ls_landscape
    from lightaudit.grid import eq_dirs
    from lightaudit.imageio import luminance
    prep = np.load(DATA / scene / "prep.npz")
    x0, y0, size = find_ball(scene)
    na, m = sphere_normals(size)
    out = {}
    for key in ["analytic"] + [k for k in ("normals_dsine", "normals_depth_anything", "normals") if k in prep]:
        nn = na if key == "analytic" else prep[key].astype(np.float32)[y0:y0 + size, x0:x0 + size]
        le = []
        for d in range(NDIR):
            Y = luminance(load(scene, d))[y0:y0 + size, x0:x0 + size]
            ok = m & (Y > 0.03) & (Y < 0.97)
            le.append(float(ang(eq_dirs()[int(np.argmax(ls_landscape(nn[ok], Y[ok], eq_dirs())))], prep["gt"][d])))
        out[key] = (float(np.median(ang(nn[m], na[m]))), float(np.median(le)))
    print(scene, " | ".join(f"{k}: normal err {a:.0f}, light err {b:.0f}" for k, (a, b) in out.items()), flush=True)
    return out


# ------------------------------------------------------------------------------------------- estimators
def _corr(S, y):
    """Pearson correlation of each row of S (D, N) with y (N,)."""
    S = S - S.mean(1, keepdims=True)
    y = y - y.mean()
    den = np.linalg.norm(S, axis=1) * max(float(np.linalg.norm(y)), 1e-9)
    return np.where(den > 1e-9, (S @ y) / np.maximum(den, 1e-9), 0.0).astype(np.float32)


def _clusters(rgb, k=4):
    """Albedo proxy: k-means on chromaticity (shading-invariant for white light). Returns a one-hot matrix (N, k)."""
    import cv2
    x = rgb.astype(np.float32) + 1.0
    ch = (x[:, :2] / x.sum(1, keepdims=True)).astype(np.float32)
    _, lab, _ = cv2.kmeans(ch, k, None, (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 1e-4), 2, cv2.KMEANS_PP_CENTERS)
    return np.eye(k, dtype=np.float32)[lab.ravel()]


def _resid(X, C):
    """Rows of X (D, N) with the cluster means (columns of the one-hot C) removed."""
    cnt = np.maximum(C.sum(0), 1)
    return X - ((X @ C) / cnt) @ C.T


def est_ls(n, Y, rgb, dirs):  # clamped Lambert, gamma 2.2 (the pipeline's default cue)
    return _corr(np.maximum(dirs @ n.T, 0), Y ** 2.2)


def est_sh1(n, Y, rgb, dirs):  # first-order spherical harmonics: no clamp (soft / area light)
    return _corr(dirs @ n.T, Y ** 2.2)


def est_ls_alb(n, Y, rgb, dirs):  # clamped Lambert, albedo clusters projected out
    C = _clusters(rgb)
    return _corr(_resid(np.maximum(dirs @ n.T, 0), C), _resid((Y ** 2.2)[None], C)[0])


def est_sh1_alb(n, Y, rgb, dirs):
    C = _clusters(rgb)
    return _corr(_resid(dirs @ n.T, C), _resid((Y ** 2.2)[None], C)[0])


def est_ls_log(n, Y, rgb, dirs):  # log domain: albedo becomes an additive offset per cluster
    C = _clusters(rgb)
    return _corr(_resid(np.log(0.15 + np.maximum(dirs @ n.T, 0)), C), _resid(np.log(1e-3 + Y ** 2.2)[None], C)[0])


ESTIMATORS = {"ls": est_ls, "sh1": est_sh1, "ls_alb": est_ls_alb, "sh1_alb": est_sh1_alb, "ls_log": est_ls_log}


# ------------------------------------------------------------------------------------------- benchmark
def region_pixels(prep, max_px=1200, seed=0, nkey="normals"):
    """Per region: sampled pixel coordinates with usable geometry, normal spread, area."""
    from lightaudit.config import Config
    from lightaudit.validity import erode, erode_px
    cfg = Config()
    normals, labels = prep[nkey].astype(np.float32), prep["labels"]
    unc = prep["unc"].astype(np.float32) if nkey == "normals" else np.full(labels.shape, 12.0, np.float32)
    rng = np.random.default_rng(seed)
    out = []
    for k in range(1, int(labels.max()) + 1):
        m = erode(labels == k, erode_px(*labels.shape, cfg)) & (normals[..., 2] >= cfg.nz_min) & (unc <= cfg.unc_max)
        ys, xs = np.nonzero(m)
        if len(ys) < 300:
            continue
        if len(ys) > max_px:
            pick = rng.choice(len(ys), max_px, replace=False)
            ys, xs = ys[pick], xs[pick]
        n = normals[ys, xs]
        mn = n.mean(0) / max(np.linalg.norm(n.mean(0)), 1e-6)
        spread = float(np.percentile(np.degrees(np.arccos(np.clip(n @ mn, -1, 1))), 90))
        eig = float(np.linalg.eigvalsh(np.cov(n.T))[0])  # smallest eigenvalue: 0 for a plane or a cylinder
        out.append(dict(id=k, ys=ys, xs=xs, n=n, spread=spread, eig=eig, area=int((labels == k).sum())))
    return out


def landscapes(scene: str, est: str, nkey: str = "normals") -> dict:
    """S[d, r, D] for every lighting d and region r, cached. NaN rows where a region has too few usable pixels."""
    from lightaudit.grid import coarse_index, eq_dirs
    from lightaudit.imageio import luminance
    f = DATA / scene / f"land_{est}_{nkey}.npz"
    prep = np.load(DATA / scene / "prep.npz")
    regs = region_pixels(prep, nkey=nkey)
    if f.exists():
        z = np.load(f)
        return dict(S=z["S"].astype(np.float32), regs=regs, gt=prep["gt"], dirs=z["dirs"])
    dirs = eq_dirs()[coarse_index(4)]
    fn = ESTIMATORS[est]
    S = np.full((NDIR, len(regs), len(dirs)), np.nan, np.float32)
    for d in range(NDIR):
        rgb = load(scene, d)
        Y = luminance(rgb)
        for i, r in enumerate(regs):
            y = Y[r["ys"], r["xs"]]
            ok = (y > 0.03) & (y < 0.97)
            if ok.sum() >= 200:
                S[d, i] = fn(r["n"][ok], y[ok], rgb[r["ys"], r["xs"]][ok], dirs)
    np.savez_compressed(f, S=S.astype(np.float16), dirs=dirs)
    return dict(S=S, regs=regs, gt=prep["gt"], dirs=dirs)


def auc(neg, pos):
    neg, pos = np.asarray(neg, float), np.asarray(pos, float)
    if not len(neg) or not len(pos):
        return float("nan")
    return float((pos[:, None] > neg[None]).mean() + 0.5 * (pos[:, None] == neg[None]).mean())


def ang(a, b):
    return np.degrees(np.arccos(np.clip((a * b).sum(-1), -1, 1)))


def analyse(scene_list, est, min_spread=15.0, min_rho=0.3, min_delta=40.0, seed=0, verbose=True, nkey="normals"):
    """Accuracy, tracking and simulated-splice detection for one estimator. Returns a dict of pooled numbers.

    Simulated splice: region k's landscape from lighting j replaces its landscape in image i (same geometry, so
    this equals pasting those pixels). Score of an image = max over reliable regions of the correlation drop
    S_k(own best light) - S_k(consensus of the other regions)."""
    rng = np.random.default_rng(seed)
    err, track_e, track_g, neg, pos, loc = [], [], [], [], [], []
    for sc in scene_list:
        L = landscapes(sc, est, nkey)
        S, gt, dirs = L["S"], L["gt"], L["dirs"]
        rho = np.nanmax(S, 2)  # (25, R)
        best = dirs[np.nanargmax(np.where(np.isnan(S), -9, S), 2)]  # (25, R, 3)
        geom = np.array([r["spread"] >= min_spread for r in L["regs"]])
        rel = geom[None] & (rho >= min_rho) & ~np.isnan(rho)  # (25, R)
        for d in range(NDIR):
            err += list(ang(best[d, rel[d]], gt[d]))
        for r in np.flatnonzero(geom):
            ok = np.flatnonzero(rel[:, r])
            for a in range(len(ok)):
                for b in range(a + 1, len(ok)):
                    track_e.append(float(ang(best[ok[a], r], best[ok[b], r])))
                    track_g.append(float(ang(gt[ok[a]], gt[ok[b]])))
        gtang = ang(gt[:, None, :], gt[None, :, :])
        for i in range(NDIR):
            idx = np.flatnonzero(rel[i])
            if len(idx) < 3:
                continue
            Si = S[i, idx]

            def score(M):
                F = M.sum(0)
                s = [M[k].max() - M[k, int(np.argmax(F - M[k]))] for k in range(len(M))]
                return float(np.max(s)), int(np.argmax(s))

            neg.append(score(Si)[0])
            for kk, k in enumerate(idx):
                cand = [j for j in range(NDIR) if gtang[i, j] >= min_delta and rel[j, k]]
                if not cand:
                    continue
                M = Si.copy()
                M[kk] = S[int(rng.choice(cand)), k]
                sc_, top = score(M)
                pos.append(sc_)
                loc.append(top == kk)
    track = float(np.corrcoef(track_e, track_g)[0, 1]) if len(track_e) > 10 else float("nan")
    out = dict(est=est, n_regions=len(err), err_med=float(np.median(err)) if err else float("nan"), track_corr=track,
               auc=auc(neg, pos), n_neg=len(neg), n_pos=len(pos), loc=float(np.mean(loc)) if loc else float("nan"),
               tpr5=float(np.mean(np.array(pos) > np.quantile(neg, 0.95))) if neg and pos else float("nan"))
    if verbose:
        print(f"{est:8s} {nkey:15s} regions {out['n_regions']:5d}  median err {out['err_med']:5.1f} deg  tracking r {track:5.2f}  "
              f"splice AUC {out['auc']:.3f}  TPR@5%FPR {out['tpr5']:.2f}  top-1 {out['loc']:.2f}  "
              f"(neg {len(neg)}, pos {len(pos)})", flush=True)
    return out


def lr_scores(M, n_eff=40.0):
    """Likelihood-ratio test per region: "shares the light of the others" against "has its own light".

    M: (R, D) correlation landscapes. With a free gain and offset per region, the residual sum of squares of the
    best fit under light l is SS_tot * (1 - rho(l)^2), so the profile log-likelihood is -n/2 * log(1 - rho^2).
    Shared light for region k = the maximiser of the summed log-likelihood of the other regions. The statistic
    n_eff * log(RSS_shared / RSS_own) is referred to chi-square(2) (two extra parameters: a direction); n_eff
    stands in for the effective number of independent pixels and is calibrated empirically. Holm correction over
    the regions gives the image-level p-value. Returns (-log10 of the Holm-adjusted minimum p, argmax region, T)."""
    from scipy.stats import chi2
    Lg = -np.log(1 - np.clip(M, 0, 0.999) ** 2)
    F = Lg.sum(0)
    T = np.array([Lg[k].max() - Lg[k, int(np.argmax(F - Lg[k]))] for k in range(len(M))])
    p = chi2.sf(n_eff * T, 2)
    order = np.argsort(p)
    adj = np.maximum.accumulate(p[order] * (len(p) - np.arange(len(p))))  # Holm step-down
    return float(-np.log10(max(min(adj[0], 1.0), 1e-300))), int(order[0]), T


def analyse2(scene_list, est="ls", nkey="normals", score="lr", gate="eig", gate_thr=0.02, min_rho=0.3, top_k=None,
             min_delta=40.0, max_delta=180.0, n_eff=40.0, seed=0, verbose=True, split=None):
    """Simulated-splice benchmark with a choice of test statistic ("drop" = correlation drop, "lr" = likelihood
    ratio + Holm), region gate ("spread" or "eig" = smallest eigenvalue of the normal covariance) and top-k regions
    by pixel count. split = (calibration lightings, test lightings) for an honest threshold."""
    rng = np.random.default_rng(seed)
    neg, pos, loc, nreg = {}, [], [], []
    for sc in scene_list:
        L = landscapes(sc, est, nkey)
        S = L["S"]
        gt = L["gt"]
        rho = np.nanmax(np.where(np.isnan(S), -9, S), 2)
        g = np.array([(r["eig"] >= gate_thr) if gate == "eig" else (r["spread"] >= gate_thr) for r in L["regs"]])
        size = np.array([len(r["ys"]) * 1.0 + r["area"] * 1e-6 for r in L["regs"]])
        rel = g[None] & (rho >= min_rho)
        gtang = ang(gt[:, None, :], gt[None, :, :])
        for i in range(NDIR):
            idx = np.flatnonzero(rel[i])
            if top_k:
                idx = idx[np.argsort(-size[idx])[:top_k]]
            if len(idx) < 3:
                continue
            Si = S[i, idx]

            def sc_fn(M):
                if score == "lr":
                    a, b, _ = lr_scores(M, n_eff)
                    return a, b
                F = M.sum(0)
                s = [M[k].max() - M[k, int(np.argmax(F - M[k]))] for k in range(len(M))]
                return float(np.max(s)), int(np.argmax(s))

            neg[(sc, i)] = sc_fn(Si)[0]
            nreg.append(len(idx))
            for kk, k in enumerate(idx):
                cand = [j for j in range(NDIR) if min_delta <= gtang[i, j] <= max_delta and rel[j, k]]
                if not cand:
                    continue
                M = Si.copy()
                M[kk] = S[int(rng.choice(cand)), k]
                a, top = sc_fn(M)
                pos.append((sc, i, a))
                loc.append(top == kk)
    nv = np.array(list(neg.values()))
    pv = np.array([a for _, _, a in pos])
    out = dict(auc=auc(nv, pv), n_neg=len(nv), n_pos=len(pv), loc=float(np.mean(loc)) if loc else float("nan"),
               tpr5=float(np.mean(pv > np.quantile(nv, 0.95))) if len(nv) and len(pv) else float("nan"),
               tpr10=float(np.mean(pv > np.quantile(nv, 0.90))) if len(nv) and len(pv) else float("nan"),
               regions=float(np.mean(nreg)) if nreg else 0.0,
               corr_nreg=float(np.corrcoef(nreg, nv)[0, 1]) if len(nv) > 5 and np.std(nreg) > 0 else float("nan"))
    if split:  # threshold from calibration lightings only, rates on the held-out lightings
        cal = np.array([v for (sc, i), v in neg.items() if i in split[0]])
        tneg = np.array([v for (sc, i), v in neg.items() if i in split[1]])
        tpos = np.array([a for sc, i, a in pos if i in split[1]])
        thr = np.quantile(cal, 0.90)
        out.update(test_fpr=float(np.mean(tneg > thr)), test_tpr=float(np.mean(tpos > thr)), n_test_neg=len(tneg),
                   n_test_pos=len(tpos), test_auc=auc(tneg, tpos))
    if verbose:
        tag = f"{est}/{nkey.replace('normals_', '').replace('normals', 'ens')}/{score}/{gate}{gate_thr}/k{top_k}"
        extra = f"  held-out: FPR {out['test_fpr']:.2f} TPR {out['test_tpr']:.2f} AUC {out['test_auc']:.2f}" if split else ""
        print(f"{tag:38s} AUC {out['auc']:.3f} TPR@5% {out['tpr5']:.2f} TPR@10% {out['tpr10']:.2f} top-1 {out['loc']:.2f} "
              f"regions/img {out['regions']:.1f} corr(score,#regions) {out['corr_nreg']:.2f} n {out['n_neg']}/{out['n_pos']}{extra}",
              flush=True)
    return out


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "prepare"
    if cmd == "fetch":
        fetch(int(sys.argv[2]))
    elif cmd == "prepare":
        for sc in (sys.argv[2:] or scenes()):
            prepare(sc)
    elif cmd == "bench":
        ready = [sc for sc in scenes() if (DATA / sc / "prep.npz").exists()]
        print("scenes:", ready)
        import os
        for nkey in os.environ.get("REAL_NKEY", "normals").split(","):
            for est in (sys.argv[2:] or list(ESTIMATORS)):
                analyse(ready, est, nkey=nkey)
    elif cmd == "renormal":
        for sc in (sys.argv[2:] or scenes()):
            renormal(sc)
    elif cmd == "ball":
        for sc in scenes():
            if (DATA / sc / "prep.npz").exists():
                ball_check(sc)
