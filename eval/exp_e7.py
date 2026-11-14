"""E7 - robustness to image processing.

Pristine test `normal` scenes (3150+) and car composites at delta = 90 deg (3000+), n = 50 each in the full suite
(a deviation from the 150 of 14.1, for CPU time; recorded in the JSON). Each perturbation is applied to the final
8-bit image and the full pipeline re-runs (noisy_gt(8) normals, resized with the image for the resize case). The
calibrated tau is NOT re-fit per perturbation. Metrics: TPR (composites flagged SUSPICIOUS) and FPR (pristine
flagged SUSPICIOUS) at the calibrated tau, for C1 only and all cues.
"""
from __future__ import annotations

import cv2
import numpy as np

from . import common as C
from . import metrics as M

PERTS = [("none", None), ("jpeg", 95), ("jpeg", 75), ("jpeg", 50), ("jpeg", 30), ("resize", 0.75), ("resize", 0.5),
         ("resize", 0.35), ("noise", 0.01), ("noise", 0.03), ("noise", 0.06), ("tone", "gamma1.5"),
         ("tone", "gamma2.8"), ("tone", "contrast1.5")]


def perturb(rgb, normals, unc, labels, kind, p, seed):
    if kind == "jpeg":
        from lightaudit.imageio import jpeg_roundtrip
        return jpeg_roundtrip(rgb, p), normals, unc, labels, 1.0
    if kind == "resize":
        H, W = labels.shape
        w, h = round(W * p), round(H * p)
        n = cv2.resize(normals, (w, h), interpolation=cv2.INTER_LINEAR)
        n /= np.maximum(np.linalg.norm(n, axis=-1, keepdims=True), 1e-6)
        return (cv2.resize(rgb, (w, h), interpolation=cv2.INTER_AREA), n.astype(np.float32),
                cv2.resize(unc, (w, h), interpolation=cv2.INTER_LINEAR),
                cv2.resize(labels.astype(np.int32), (w, h), interpolation=cv2.INTER_NEAREST), p)
    x = rgb.astype(np.float32) / 255
    if kind == "noise":
        x = x + np.random.default_rng(seed).normal(0, p, x.shape)
    elif p.startswith("gamma"):  # re-encode from an assumed display gamma 2.2 to gamma g
        x = x ** (float(p[5:]) / 2.2)
    else:
        x = 0.5 + 1.5 * (x - 0.5)
    return np.clip(np.round(x * 255), 0, 255).astype(np.uint8), normals, unc, labels, 1.0


def _job(args):
    seed, spliced = args
    from lightaudit.config import calibrated
    from lightaudit.pipeline import audit
    from lightaudit.regions import auto_exclude
    from lightaudit.synth import region_meta, simulate_normals
    cfg = calibrated()
    out = dict(seed=seed, spliced=spliced, res={})
    s = None
    for kind, p in PERTS:
        if kind == "none":
            rec = C.composite(seed, "normal", "car", 90) if spliced else C.pristine(seed, "normal")
        else:
            key = C._key("e7", seed, int(spliced), kind, p)
            rec = C._load(key) if key.exists() else None
            if rec is None:
                s = s or C.sample(seed, "normal")
                comp = C.make_composite(s, "car", 90, seed) if spliced else None
                rgb0 = comp["rgb"] if comp else s.rgb
                n0, u0 = simulate_normals(s.normals_gt, s.labels, 8.0, s.scene.seed, cfg)
                rgb, n, u, lab, f = perturb(rgb0, n0, u0, s.labels.astype(np.int32), kind, p, seed)
                meta = auto_exclude(rgb, lab, [dict(m) for m in region_meta(s) if (lab == m["id"]).any()], cfg)
                res = audit(rgb, n, u, lab, meta, cfg, s.scene.fov_deg, seed=s.scene.seed, scale=s.scene.scale * f,
                            residual=False)
                edited = []
                if comp:
                    m = comp["mask"] if f == 1.0 else cv2.resize(comp["mask"].astype(np.uint8), lab.shape[::-1],
                                                                  interpolation=cv2.INTER_NEAREST).astype(bool)
                    edited = [r["id"] for r in res["regions"] if r["area_px"] and (m & (lab == r["id"])).sum() > 0.5 * r["area_px"]]
                rec = dict(seed=seed, kind="normal", regions=[C.slim_region(r) for r in res["regions"]], edited=edited,
                           light_cam=np.asarray(s.light_cam, np.float64))
                C._save(key, rec)
        out["res"][f"{kind}:{p}"] = C.evaluate(rec, cfg, {"C1": dict(cues=C.CUE_SETS["C1"]),
                                                         "fused": dict(cues=C.CUE_SETS["C1+C2+C3"])})
    return out


def run(suite: str) -> dict:
    C.require_calibration()
    n = C.suite_n(suite, 50)
    jobs = [(s, False) for s in C.test_seeds("prist", n)] + [(s, True) for s in C.test_seeds("comp", n)]
    rows = C.pmap(_job, jobs, "E7")
    res = {}
    for kind, p in PERTS:
        k = f"{kind}:{p}"
        res[k] = dict(kind=kind, param=p)
        for v in ("C1", "fused"):
            for sp, name in ((True, "tpr"), (False, "fpr")):
                fl = [float(r["res"][k][v]["verdict"] == "SUSPICIOUS") for r in rows if r["spliced"] == sp]
                a = M.bootstrap_ci(lambda g: float(np.mean(g)), fl, n_boot=1000, seed=7)
                res[k][f"{name}_{v}"] = a[0]
                res[k][f"{name}_{v}_ci"] = [a[1], a[2]]
                res[k][f"abstain_{'spliced' if sp else 'pristine'}_{v}"] = float(np.mean(
                    [r["res"][k][v]["verdict"] == "INSUFFICIENT" for r in rows if r["spliced"] == sp]))
    out = C.header("E7", suite, n_pristine=n, n_spliced=n, splice="car at delta = 90 deg",
                   deviation="n = 50 + 50 in the full suite instead of 150 (CPU budget)",
                   tau_note="calibrated tau_img, not re-fit per perturbation", perturbations=res)
    C.write_json("e07_robustness.json", out)
    C.write_csv("e07_robustness.csv", [dict(pert=k, **{a: b for a, b in v.items() if not isinstance(b, list)})
                                       for k, v in res.items()])
    return out
