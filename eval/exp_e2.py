"""E2 - effect of normal quality (H2).

Pristine test `normal` scenes audited with simulated normals noisy_gt(sigma), sigma in {0, 4, 8, 12, 16, 20}.
Per region (non-excluded, with a bootstrap posterior): angular error of the posterior centre vs the GT sun, r68
(from the calibrated KDE), region size and spread. Reported for all regions with a posterior and for the
reliable ones (weight >= w_min).
"""
from __future__ import annotations

import numpy as np
from scipy.stats import spearmanr

from . import common as C
from . import metrics as M

SIGMAS = (0, 4, 8, 12, 16, 20)


def _job(seed: int) -> list[dict]:
    from lightaudit.config import calibrated
    from lightaudit.grid import angle_deg
    cfg = calibrated()
    rows = []
    for sg in SIGMAS:
        rec = C.pristine(seed, "normal", float(sg))
        for d in rec["regions"]:
            if d["excluded"] or d["samples"] is None:
                continue
            r = C.unslim_region(d, cfg)
            rows.append(dict(seed=seed, sigma=sg, region=d["name"], n_valid=d["n_valid"], spread_deg=d["spread_deg"],
                             mean_unc=d["mean_unc"], weight=d["weight"], reliable=bool(d["weight"] >= cfg.w_min),
                             err_deg=float(angle_deg(d["center"], rec["light_cam"])), r68_deg=r["r68_deg"],
                             r95_deg=r["r95_deg"]))
    return rows


def _binned(x, y, edges):
    out = []
    for a, b in zip(edges[:-1], edges[1:]):
        m = (x >= a) & (x < b)
        out.append(dict(lo=float(a), hi=float(b), n=int(m.sum()), median=float(np.median(y[m])) if m.any() else None))
    return out


def run(suite: str) -> dict:
    C.require_calibration()
    seeds = C.test_seeds("prist", C.suite_n(suite, 150))
    per_scene = C.pmap(_job, seeds, "E2")
    rows = [r for rs in per_scene for r in rs]
    by_sigma = {}
    for sg in SIGMAS:
        entry = {}
        for subset in ("all", "reliable"):
            g = [[r for r in rs if r["sigma"] == sg and (subset == "all" or r["reliable"])] for rs in per_scene]
            flat = [r for x in g for r in x]
            e = M.bootstrap_ci(lambda gs: float(np.median([r["err_deg"] for x in gs for r in x])) if any(gs) else np.nan,
                               g, n_boot=1000, seed=sg)
            entry[subset] = dict(n_regions=len(flat), median_err=e[0], median_err_ci=[e[1], e[2]],
                                 mean_err=float(np.mean([r["err_deg"] for r in flat])) if flat else None,
                                 median_r68=float(np.median([r["r68_deg"] for r in flat])) if flat else None,
                                 mean_r68=float(np.mean([r["r68_deg"] for r in flat])) if flat else None,
                                 frac_reliable=float(np.mean([r["reliable"] for r in flat])) if flat else None)
        by_sigma[str(sg)] = entry
    r8 = [r for r in rows if r["sigma"] == 8]
    x_n, x_s = np.array([r["n_valid"] for r in r8], float), np.array([r["spread_deg"] for r in r8], float)
    err8 = np.array([r["err_deg"] for r in r8], float)
    unc_all = np.array([r["mean_unc"] for r in rows], float)
    err_all = np.array([r["err_deg"] for r in rows], float)
    rho_all = spearmanr(unc_all, err_all) if len(rows) > 2 else None
    rho_8 = spearmanr([r["mean_unc"] for r in r8], err8) if len(r8) > 2 else None
    out = C.header("E2", suite, n_scenes=len(seeds), seeds=[seeds[0], seeds[-1]], sigmas=list(SIGMAS),
                   by_sigma=by_sigma,
                   size_bins_sigma8=_binned(x_n, err8, [150, 400, 800, 1600, 3200, 1e9]) if len(r8) else [],
                   spread_bins_sigma8=_binned(x_s, err8, [0, 10, 20, 30, 45, 60, 180]) if len(r8) else [],
                   spearman_unc_err_pooled=None if rho_all is None else dict(rho=float(rho_all[0]), p=float(rho_all[1]),
                                                                              n=len(rows)),
                   spearman_unc_err_sigma8=None if rho_8 is None else dict(rho=float(rho_8[0]), p=float(rho_8[1]),
                                                                            n=len(r8)))
    C.write_json("e02_normal_noise.json", out)
    C.write_csv("e02_rows.csv", rows)
    return out
