"""E3 - calibration of the region posteriors (H3), measured on the TEST split.

Reliable regions (weight >= w_min, not excluded) of pristine test `normal` scenes, noisy_gt(8). For each region
the KDE posterior is rebuilt from its bootstrap light samples with (a) the uncalibrated defaults h = 10 deg,
T = 1 and (b) the calibrated (h, T) from lightaudit/calib_default.json (chosen on the calibration split only).
Coverage at level q = fraction of regions whose q-HPD set contains the GT sun cell.
"""
from __future__ import annotations

import numpy as np

from . import common as C
from . import metrics as M

LEVELS = (0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.68, 0.7, 0.8, 0.9, 0.95)


def _job(seed: int) -> list[dict]:
    from lightaudit.config import Config, calibrated
    from lightaudit.grid import dir_to_index, hpd
    from lightaudit.posterior import credible, kde_posterior
    cal, unc = calibrated(), Config()
    rec = C.pristine(seed, "normal")
    k = dir_to_index(rec["light_cam"])
    rows = []
    for d in rec["regions"]:
        if d["excluded"] or d["samples"] is None or d["weight"] < cal.w_min:
            continue
        row = dict(seed=seed, region=d["name"])
        for tag, c in (("before", unc), ("after", cal)):
            P = kde_posterior(d["samples"], c.kde_h, c.T)
            _, masks = hpd(P, LEVELS)
            row[tag] = [bool(m[k]) for m in masks]
            row[f"r68_{tag}"], row[f"r95_{tag}"], *_ = credible(P)
        rows.append(row)
    return rows


def run(suite: str) -> dict:
    from lightaudit.config import Config, calibrated
    C.require_calibration()
    seeds = C.test_seeds("prist", C.suite_n(suite, 150))
    per_scene = C.pmap(_job, seeds, "E3")
    flat = [r for rs in per_scene for r in rs]
    res = {}
    for tag in ("before", "after"):
        cov = {}
        for i, q in enumerate(LEVELS):
            p, lo, hi = M.bootstrap_ci(lambda gs: float(np.mean([r[tag][i] for g in gs for r in g])) if any(gs) else np.nan,
                                       per_scene, n_boot=1000, seed=i)
            cov[str(q)] = dict(coverage=p, ci=[lo, hi])
        r68 = [r[f"r68_{tag}"] for r in flat]
        res[tag] = dict(coverage=cov, mean_r68=float(np.mean(r68)) if r68 else None,
                        median_r68=float(np.median(r68)) if r68 else None,
                        mean_r95=float(np.mean([r[f"r95_{tag}"] for r in flat])) if flat else None)
    cal, d = calibrated(), Config()
    out = C.header("E3", suite, n_scenes=len(seeds), seeds=[seeds[0], seeds[-1]], n_regions=len(flat),
                   levels=list(LEVELS), before=dict(h=d.kde_h, T=d.T, **res["before"]),
                   after=dict(h=cal.kde_h, T=cal.T, **res["after"]),
                   note="coverage measured on the test split; (h, T) were chosen on the calibration split only")
    C.write_json("e03_calibration.json", out)
    return out
