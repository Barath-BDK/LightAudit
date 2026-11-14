"""E1 - cue accuracy under camera non-linearity (H1).

Single-region light estimation on pristine test `normal` scenes with EXACT normals, each scene re-developed with
each of the five tone curves (the scene's own exposure, noise and JPEG settings are kept). For every eligible
region (non-excluded GT object, >= Nmin valid pixels, 90th-percentile normal spread >= 10 deg, i.e. not flat) the
light is estimated as the argmax over the full EQ grid of
  - C1 rank landscape (7.5),
  - the LS-baseline landscape S(l) = Pearson(Y^2.2, max(0, n.l)) (7.13), and
  - the closed-form linear least squares Y^2.2 ~ a + L.n (reported for reference),
on the same valid pixels (up to N_exact = 1200, the pipeline's subsample). Error = angle to the GT sun direction.
Known model violations that remain in the data: cast shadows, specular highlights on paint, sky ambient.
"""
from __future__ import annotations

import numpy as np

from . import common as C
from . import metrics as M

TONES = ("srgb", "gamma1.8", "gamma2.6", "scurve", "filmic")
METHODS = ("rank", "ls", "ls_lstsq")
MIN_SPREAD = 10.0


def _job(seed: int) -> list[dict]:
    from lightaudit.config import Config
    from lightaudit.cues import ls_landscape, rank_landscape
    from lightaudit.cues.ls_baseline import ls_direction
    from lightaudit.grid import angle_deg, eq_dirs
    from lightaudit.imageio import luminance
    from lightaudit.regions import auto_exclude
    from lightaudit.synth import region_meta
    from lightaudit.validity import valid_pixels
    p = C._key("e1", seed)
    got = C._load(p) if p.exists() else None
    if got is not None:
        return got
    cfg = Config()
    s = C.sample(seed, "normal")
    cam0 = dict(s.scene.cam)
    n = s.normals_gt.astype(np.float32)
    unc = np.full(s.labels.shape, cfg.unc_floor, np.float32)
    labels = s.labels.astype(np.int32)
    dirs = eq_dirs()
    gt = np.asarray(s.light_cam, np.float64)
    rows = []
    try:
        for tone in TONES:
            s.scene.cam = dict(cam0, tone=tone)
            rgb = s.finish(s.rgb_lin)
            Y = luminance(rgb)
            for m in auto_exclude(rgb, labels, [dict(x) for x in region_meta(s)], cfg):
                if m["excluded"]:
                    continue
                mask = labels == m["id"]
                ys, xs, nv = valid_pixels(Y, n, unc, mask, cfg, seed * 1000 + m["id"])
                row = dict(seed=seed, tone=tone, region=m["name"], region_id=m["id"], n_valid=int(nv),
                           scene_tone=cam0["tone"])
                if nv >= cfg.Nmin:
                    nv_, Yv = n[ys, xs], Y[ys, xs]
                    mn = nv_.mean(0)
                    mn /= np.linalg.norm(mn)
                    row["spread_deg"] = float(np.percentile(np.degrees(np.arccos(np.clip(nv_ @ mn, -1, 1))), 90))
                    rng = np.random.default_rng(seed * 1000 + m["id"] + 1)
                    sub = rng.choice(len(Yv), cfg.N_exact, replace=False) if len(Yv) > cfg.N_exact else slice(None)
                    for name, fn in (("rank", rank_landscape), ("ls", ls_landscape)):
                        S = fn(nv_[sub], Yv[sub], dirs)
                        row[f"err_{name}"] = float(angle_deg(dirs[int(np.argmax(S))], gt))
                    row["err_ls_lstsq"] = float(angle_deg(ls_direction(nv_[sub], Yv[sub]), gt))
                rows.append(row)
    finally:
        s.scene.cam = cam0
    C._save(p, rows)
    return rows


def eligible(r: dict) -> bool:
    return r.get("err_rank") is not None and r["n_valid"] >= 150 and r.get("spread_deg", 0) >= MIN_SPREAD


def run(suite: str) -> dict:
    C.require_calibration()
    seeds = C.test_seeds("prist", C.suite_n(suite, 150))
    per_scene = C.pmap(_job, seeds, "E1")
    rows = [r for rs in per_scene for r in rs]
    summary = {}
    for tone in TONES:
        summary[tone] = {}
        groups = [[r for r in rs if r["tone"] == tone and eligible(r)] for rs in per_scene]
        for meth in METHODS:
            key = f"err_{meth}"
            vals = np.array([r[key] for g in groups for r in g])
            med = M.bootstrap_ci(lambda gs: float(np.median([r[key] for g in gs for r in g])) if any(gs) else np.nan,
                                 groups, n_boot=1000, seed=1)
            summary[tone][meth] = dict(n_regions=int(len(vals)), n_scenes=int(sum(1 for g in groups if g)),
                                       median=med[0], median_ci=[med[1], med[2]],
                                       mean=float(vals.mean()) if len(vals) else None,
                                       p90=float(np.percentile(vals, 90)) if len(vals) else None,
                                       frac_below_10=float((vals < 10).mean()) if len(vals) else None)
        # paired difference LS - rank on the same regions
        diff = [[r["err_ls"] - r["err_rank"] for r in g] for g in groups]
        d = M.bootstrap_ci(lambda gs: float(np.median([x for g in gs for x in g])) if any(gs) else np.nan, diff,
                           n_boot=1000, seed=2)
        summary[tone]["median_paired_diff_ls_minus_rank"] = dict(value=d[0], ci=[d[1], d[2]])
    out = C.header("E1", suite, n_scenes=len(seeds), seeds=[seeds[0], seeds[-1]], normals="exact (GT)",
                   eligibility=f"non-excluded GT region, n_valid >= 150, normal spread >= {MIN_SPREAD} deg",
                   estimator="argmax of the landscape over the full 8192-cell EQ grid on <= 1200 valid pixels",
                   tones=list(TONES), methods=list(METHODS), summary=summary,
                   n_rows=len(rows), n_eligible=int(sum(eligible(r) for r in rows)))
    C.write_json("e01_tone_curves.json", out)
    C.write_csv("e01_rows.csv", rows)
    return out
