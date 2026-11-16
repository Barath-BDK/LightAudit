"""Stress tests for the seam statistic S (docs/designs/seam_test.md, review findings 1-3), on the held-out objects of
eval/mit_panel.py with the thresholds it wrote (10% level, lightaudit/calib_real_panel.json):

  * wider feathering of the pasted area (Gaussian sigma 1.5 / 4 / 8 px before the 2x upscale);
  * Poisson blending (cv2.seamlessClone), the standard tool for hiding a paste edge;
  * a marked area that does not follow the paste edge: analysis ROI eroded by 4 px or dilated by 4 / 10 px
    (clean images too, so false alarms are measured for the same mismatch). Dilating is also the proposed
    mitigation for a dent rim: measure the seam outside the crease.

    python eval/seam_robust.py        # writes data/results/seam_robust.json
"""
from __future__ import annotations

import json
import multiprocessing as mp
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
KEYS = ("T", "Tr", "S")
VARIANTS = ("base", "feather4", "feather8", "poisson", "roi-4", "roi+4", "roi+10")


def _one(obj):
    from eval import mit_bench as mb
    from lightaudit.config import Config
    from lightaudit.regions import apply_roi
    from lightaudit.residual import panel_shared, seam_S
    cfg = Config()
    d = mb.load(obj)
    N = np.load(mb.DATA / obj / "prep.npz")["normals_depth_anything"].astype(np.float32)
    up = 2
    big = lambda x, it: cv2.resize(x, (x.shape[1] * up, x.shape[0] * up), interpolation=it)  # noqa: E731
    n_b = big(N, cv2.INTER_LINEAR)
    n_b /= np.maximum(np.linalg.norm(n_b, axis=-1, keepdims=True), 1e-6)
    lab = mb.parts(d["mask"], 4)
    mask_b = big(d["mask"].astype(np.uint8), cv2.INTER_NEAREST).astype(np.int32)
    unc = np.full(mask_b.shape, cfg.single_backend_unc, np.float32)
    to8 = lambda lin: np.round(np.clip(big((np.clip(lin, 0, 1) ** (1 / 2.2)).astype(np.float32), cv2.INTER_CUBIC), 0, 1) * 255) / 255  # noqa: E731
    rng = np.random.default_rng(__import__("zlib").crc32(obj.encode()))
    k3 = np.ones((3, 3), np.uint8)
    rows = []
    for part in range(1, 5):
        roi = lab == part
        if roi.sum() < 400:
            continue
        roi_b = big(roi.astype(np.uint8), cv2.INTER_NEAREST)
        rois = {"base": roi_b, "roi-4": cv2.erode(roi_b, k3, iterations=4), "roi+4": cv2.dilate(roi_b, k3, iterations=4),
                "roi+10": cv2.dilate(roi_b, k3, iterations=10)}
        setups = {}
        for name, r in rois.items():
            r = r.astype(bool) & (mask_b > 0)
            labels, meta = apply_roi(mask_b, [dict(id=1, name=obj, source="mask", excluded=False)], r, cfg)
            setups[name] = (labels, [dict(id=m["id"], name=m["name"]) for m in meta])
        alpha = {s: np.clip(cv2.GaussianBlur(roi.astype(np.float32), (0, 0), s), 0, 1) for s in (1.5, 4.0, 8.0)}
        ys, xs = np.nonzero(roi_b)
        centre = (int((xs.min() + xs.max() + 1) // 2), int((ys.min() + ys.max() + 1) // 2))
        for i in range(mb.NL):
            j = int(rng.choice([x for x in range(mb.NL) if x != i]))
            li, lj = d["lin"][i], d["lin"][j]
            Yi = to8(li)
            imgs = {"clean": Yi, "base": to8(li * (1 - alpha[1.5]) + lj * alpha[1.5]),
                    "feather4": to8(li * (1 - alpha[4.0]) + lj * alpha[4.0]), "feather8": to8(li * (1 - alpha[8.0]) + lj * alpha[8.0])}
            g3 = lambda Y: np.repeat((Y * 255).astype(np.uint8)[..., None], 3, 2)  # noqa: E731
            try:
                pc = cv2.seamlessClone(g3(to8(lj)), g3(Yi), (roi_b * 255).astype(np.uint8), centre, cv2.NORMAL_CLONE)
                imgs["poisson"] = pc[..., 0].astype(np.float32) / 255
            except cv2.error:
                pass
            jobs = [("clean", "base", "clean"), ("base", "base", "splice"), ("feather4", "base", "splice"),
                    ("feather8", "base", "splice"), ("poisson", "base", "splice")]
            jobs += [(img, v, kind) for v in ("roi-4", "roi+4", "roi+10") for img, kind in (("clean", "clean"), ("base", "splice"))]
            for img, setup, kind in jobs:
                if img not in imgs:
                    continue
                Y = imgs[img].astype(np.float32)
                labels, regs = setups[setup]
                kw = dict(retinex=True, thr=cfg.retinex_thr, band=cfg.panel_band)
                st = dict(T=panel_shared(Y, n_b, unc, labels, regs, cfg, shape_only=True, **kw),
                          Tr=panel_shared(Y, n_b, unc, labels, regs, cfg, **kw), S=seam_S(Y, labels, regs, cfg))
                variant = setup if setup != "base" else (img if kind == "splice" else "base")
                rows.append(dict(obj=obj, part=part, lamp=i, variant=variant, kind=kind, **st))
    return rows


def main():
    from eval import mit_bench as mb
    objs = mb.objects()
    test = objs[1::2]
    tau = json.loads((ROOT / "lightaudit" / "calib_real_panel.json").read_text())
    tau = {k: tau[f"tau_panel_{k}_10"] for k in KEYS}
    with mp.Pool(5) as p:
        rows = [r for rs in p.map(_one, test) for r in rs]
    over = lambda r, keys: any(r[k] is not None and r[k] > tau[k] for k in keys)  # noqa: E731
    out = {}
    for v in VARIANTS:
        res = {}
        for name, keys in (("T+Tr", ("T", "Tr")), ("S", ("S",)), ("T+Tr+S", KEYS)):
            c = [over(r, keys) for r in rows if r["variant"] == v and r["kind"] == "clean"]
            s = [over(r, keys) for r in rows if r["variant"] == v and r["kind"] == "splice"]
            res[name] = dict(false_alarms=float(np.mean(c)) if c else None, detected=float(np.mean(s)) if s else None, n=len(s))
        none_S = float(np.mean([r["S"] is None for r in rows if r["variant"] == v]))
        out[v] = dict(res, S_none=none_S)
        print(f"{v:9s} " + "  ".join(f"{n}: FA {x['false_alarms'] if x['false_alarms'] is not None else float('nan'):.3f} det {x['detected']:.3f}"
                                     for n, x in res.items()) + f"  (S undefined {none_S:.2f}, n {res['S']['n']})", flush=True)
    (ROOT / "data" / "results" / "seam_robust.json").write_text(json.dumps(dict(tau=tau, variants=out), indent=1))


if __name__ == "__main__":
    main()
