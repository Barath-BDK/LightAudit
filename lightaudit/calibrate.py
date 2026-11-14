"""Calibration on the calibration split only (BUILD_SPEC 9): posterior shape (h, T) and the conformal alarm level."""
from __future__ import annotations

import json
import math
import multiprocessing as mp
import os
from dataclasses import replace
from datetime import date
from pathlib import Path

import numpy as np

from .config import CALIB_DEFAULT, ROOT, SPLIT_SEEDS, Config
from .grid import dir_to_index, hpd
from .posterior import kde_posterior

RESULTS = ROOT / "data" / "results"


def conformal_quantile(scores, alpha: float) -> float:
    """Split-conformal threshold: the ceil((n+1)(1-alpha))-th smallest score (inf if that exceeds n)."""
    s = np.sort(np.asarray(scores, np.float64))
    n = len(s)
    k = math.ceil((n + 1) * (1 - alpha))
    return float(s[k - 1]) if 1 <= k <= n else float("inf")


def n_procs() -> int:
    return max(1, (os.cpu_count() or 2) - 1)


def _shape_job(seed):
    """Bootstrap light samples of every reliable-candidate region of one pristine `normal` scene."""
    from .pipeline import audit_sample
    from .synth import get_sample
    cfg = Config()
    s = get_sample(seed, "normal")
    res = audit_sample(s, cfg=cfg, residual=False)
    return [(r["samples"], r["weight"], s.light_cam) for r in res["regions"]
            if not r["excluded"] and r["samples"] is not None]


def _score_job(args):
    from .pipeline import audit_sample
    from .synth import get_sample
    seed, kind, cfg = args
    res = audit_sample(get_sample(seed, kind), cfg=cfg, panel=(kind == "damage"), residual=False)
    return seed, kind, res["fusion"]["verdict"], res["fusion"]["S_img"]


def coverage(samples_list, gt_list, h: float, T: float, levels=(0.68, 0.95)) -> list[float]:
    hit = np.zeros(len(levels))
    for samples, gt in zip(samples_list, gt_list):
        _, masks = hpd(kde_posterior(samples, h, T), levels)
        k = dir_to_index(gt)
        hit += [m[k] for m in masks]
    return list(hit / max(len(samples_list), 1))


def cal_kind(i: int) -> str:
    return "normal" if i % 10 < 7 else "damage"


def run_calibration(n_cal: int | None = None, n_shape: int | None = None, out: Path = CALIB_DEFAULT,
                    cfg: Config = Config(), procs: int | None = None) -> dict:
    n_cal, n_shape = n_cal or cfg.n_cal, n_shape or cfg.n_cal_shape
    n_shape = min(n_shape, n_cal)
    seed0 = SPLIT_SEEDS["cal"]
    with mp.Pool(procs or n_procs()) as pool:
        # 1. posterior shape on pristine `normal` scenes, reliable regions only
        rows = [r for rs in pool.imap(_shape_job, range(seed0, seed0 + n_shape)) for r in rs]
        rel = [(s, g) for s, w, g in rows if w >= cfg.w_min]
        S, G = [s for s, _ in rel], [g for _, g in rel]
        grid = []
        for h in cfg.h_grid:
            for T in cfg.T_grid:
                c68, c95 = coverage(S, G, h, T)
                grid.append(dict(h=h, T=T, cov68=c68, cov95=c95, loss=abs(c68 - 0.68) + abs(c95 - 0.95)))
        best = min(grid, key=lambda g: g["loss"])
        cfg2 = replace(cfg, kde_h=float(best["h"]), T=float(best["T"]))
        # 2. conformal alarm threshold on pristine scenes (70% normal, 30% unedited damage scenes in panel mode)
        jobs = [(seed0 + i, cal_kind(i), cfg2) for i in range(n_cal)]
        scored = list(pool.imap(_score_job, jobs))
    scores = [s for _, _, v, s in scored if v != "INSUFFICIENT"]
    calib = dict(
        h=best["h"], T=best["T"], cov68=best["cov68"], cov95=best["cov95"],
        tau_img_05=conformal_quantile(scores, 0.05), tau_img_10=conformal_quantile(scores, 0.10),
        tau_ref_factor=1.0, w_min=cfg.w_min, n_cal=n_cal, n_shape_scenes=n_shape, n_shape_regions=len(rel),
        n_scored=len(scores), insufficient_rate=1 - len(scores) / max(len(scored), 1),
        seeds=[seed0, seed0 + n_cal - 1], date=date.today().isoformat(), normals="noisy_gt(8)")
    for k in ("tau_img_05", "tau_img_10"):  # too few scores for the conformal rank: fall back to the max (logged)
        if not math.isfinite(calib[k]):
            calib[k] = float(max(scores)) if scores else cfg.tau_img
            calib[k + "_note"] = "n too small for the conformal quantile; used the maximum pristine score"
    Path(out).write_text(json.dumps(calib, indent=1))
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "calibration.json").write_text(json.dumps(dict(
        calib=calib, grid=grid, scores=scores,
        verdicts=[dict(seed=s, kind=k, verdict=v, S_img=x) for s, k, v, x in scored]), indent=1))
    return calib
