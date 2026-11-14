"""E10 - a real normal predictor in the loop (P1). Synthetic renders, but the normals come from
lightaudit.normals.predict_normals on the rendered IMAGE (sim-to-real measurement) instead of noisy_gt.
Per scene: pristine image and the car pasted at delta = 90 deg. Reports normal error vs GT, region light error,
verdicts, and the T3a attack (exact light, attacker uses the defender's predicted normals) with the normals
RE-PREDICTED from the attacked image (circularity check). Small N (CPU): 10 scenes full, 2 quick (spec: 30).
If no backend runs, writes {"status": "not run: no backend"}."""
from __future__ import annotations

import numpy as np

from . import common as C

BACKENDS = ("dsine", "depth_anything")  # dsine first; depth_anything is used if the dsine hub download fails


def _audit(s, rgb, n, u, cfg):
    from lightaudit.pipeline import audit
    from lightaudit.regions import auto_exclude
    from lightaudit.synth import region_meta
    lab = s.labels.astype(np.int32)
    meta = auto_exclude(rgb, lab, [dict(m) for m in region_meta(s)], cfg)
    return audit(rgb, n, u, lab, meta, cfg, s.scene.fov_deg, seed=s.scene.seed, scale=s.scene.scale, residual=False)


def _job(seed):
    key = C._key("e10", seed, *BACKENDS)
    got = C._load(key) if key.exists() else None
    if got is not None:
        return got
    from lightaudit.attacks import run_attack
    from lightaudit.config import calibrated
    from lightaudit.grid import angle_deg
    from lightaudit.normals import predict_normals
    cfg = calibrated()
    s = C.sample(seed, "normal")
    comp = C.make_composite(s, "car", 90, seed)
    hit = s.labels > 0
    out = dict(seed=seed)
    for tag, rgb in (("pristine", s.rgb), ("spliced", comp["rgb"])):
        n, u, info = predict_normals(rgb, BACKENDS, s.scene.fov_deg)
        if not set(info.get("backends", [])) & set(BACKENDS):
            return dict(seed=seed, failed=info.get("log"))
        err = np.degrees(np.arccos(np.clip((n * s.normals_gt).sum(-1), -1, 1)))[hit]
        res = _audit(s, rgb, n, u, cfg)
        f = res["fusion"]
        rel = [r for r in res["regions"] if r["reliable"]]
        top = res["regions"][f["top_region"]]["id"] if f["top_region"] is not None else None
        out[tag] = dict(normal_err_median=float(np.median(err)), normal_err_mean=float(err.mean()),
                        verdict=f["verdict"], S_img=f["S_img"], top_id=top, n_reliable=len(rel),
                        light_err=[float(angle_deg(r["center"], s.light_cam)) for r in rel], mode=info.get("mode"))
        if tag == "spliced":
            out["spliced"]["top_is_car"] = top == 2
            if any(r["id"] == 2 and not r["excluded"] for r in res["regions"]):
                a = run_attack("T3a", res, 2, lambda img: _audit(s, img, n, u, cfg), sigma_att=0.0, seed=seed, cfg=cfg)
                n2, u2, _ = predict_normals(a["rgb"], BACKENDS, s.scene.fov_deg)
                m = s.labels == 2
                shift = np.degrees(np.arccos(np.clip((n2 * n).sum(-1), -1, 1)))[m]
                r2 = _audit(s, a["rgb"], n2, u2, cfg)
                out["attack_T3a"] = dict(verdict_fixed_normals=a["result"]["fusion"]["verdict"],
                                         verdict_repredicted=r2["fusion"]["verdict"],
                                         S_img_fixed=a["result"]["fusion"]["S_img"], S_img_repredicted=r2["fusion"]["S_img"],
                                         normal_shift_in_car_median=float(np.median(shift)), fidelity=a["fidelity"])
    C._save(key, out)
    return out


def run(suite: str) -> dict:
    C.require_calibration()
    n = 10 if suite == "full" else 2
    seeds = C.test_seeds("comp", n)
    try:
        from lightaudit import backends_available
        av = backends_available()
        if not any(av.get(b) for b in BACKENDS):
            raise RuntimeError(f"backends {BACKENDS} not available: {av}")
        rows = C.pmap(_job, seeds, "E10", procs=1)
    except Exception as e:
        out = C.header("E10", suite, status="not run: no backend", error=f"{type(e).__name__}: {e}")
        C.write_json("e10_real_normals.json", out)
        return out
    ok = [r for r in rows if "pristine" in r]
    if not ok:
        out = C.header("E10", suite, status="not run: no backend", error=str(rows[0].get("failed") if rows else ""))
        C.write_json("e10_real_normals.json", out)
        return out
    agg = {}
    for tag in ("pristine", "spliced"):
        rs = [r[tag] for r in ok]
        le = [x for r in rs for x in r["light_err"]]
        agg[tag] = dict(n=len(rs), normal_err_median=float(np.median([r["normal_err_median"] for r in rs])),
                        region_light_err_median=float(np.median(le)) if le else None, n_reliable_regions=len(le),
                        verdicts={v: sum(r["verdict"] == v for r in rs) for v in ("CONSISTENT", "SUSPICIOUS", "INSUFFICIENT", "CONFLICT")})
    at = [r["attack_T3a"] for r in ok if "attack_T3a" in r]
    out = C.header("E10", suite, status="ran", backends=list(BACKENDS), n_scenes=len(ok), seeds=[seeds[0], seeds[-1]],
                   summary=agg, attack=dict(n=len(at),
                                            suspicious_fixed_normals=sum(a["verdict_fixed_normals"] == "SUSPICIOUS" for a in at),
                                            suspicious_repredicted=sum(a["verdict_repredicted"] == "SUSPICIOUS" for a in at),
                                            median_normal_shift_deg=float(np.median([a["normal_shift_in_car_median"] for a in at])) if at else None),
                   rows=rows, e10_caveat="real normal predictor on synthetic renders; small N; T3a uses the exact light")
    C.write_json("e10_real_normals.json", out)
    return out
