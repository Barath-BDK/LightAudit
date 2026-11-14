"""Shared machinery of the evaluation suite: splits, result caching, re-fusion and per-image summaries.

Caching (BUILD_SPEC 14.1). Every audit is stored in `data/results/cache/` as a *slim* per-region record
(bootstrap light samples, glint blobs, contour map, reliability factors, ...). Everything that depends on the
calibration (KDE posterior P with h/T, cones, fusion, verdict) is recomputed from it on load, so the cache stays
valid when the calibration changes and ablations (cue subsets, KDE on/off, w_min, leave-one-out) need no
re-computation.

Composites only recompute the pasted region(s): `audit_sample(..., reuse=<pristine result of the same scene>,
changed=<edited region ids>)`. This is exact for the rank cue up to one detail of the synthetic camera: the
auto-exposure is computed on the whole image, so re-lighting the pasted object can change the global exposure
by a few percent; the reused regions' rank landscapes are invariant to that (monotone), only their validity masks
(saturation / dark limits) could shift by a handful of pixels.
"""
from __future__ import annotations

import json
import math
import multiprocessing as mp
import os
import pickle
import platform
import sys
import time
from dataclasses import asdict, replace
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from lightaudit.config import CALIB_DEFAULT, ROOT, SPLIT_SEEDS, Config, calibrated, load_calib

RESULTS = ROOT / "data" / "results"
CACHE = RESULTS / "cache"
TABLES = RESULTS / "tables"
FIGS = ROOT / "docs" / "figures"
CACHE_VERSION = "v2"
CAVEAT = "synthetic scenes with simulated normal predictors unless stated"

CUE_SETS = {"C1": ("shading",), "C1+C2": ("shading", "glint"), "C1+C2+C3": ("shading", "glint", "contour")}
FUSED_NOTE = ("'fused' = C1+C2+C3: the shadow-pair cue C4 is manual-only (clicked in the viewer), so no automatic "
              "experiment can include it; 'fused' is therefore identical to C1+C2+C3.")
SCORE_NOTE = ("image score = S_img (max leave-one-out shortfall over reliable regions); images on which the audit "
              "abstains (INSUFFICIENT) get score -inf, i.e. abstention counts as not flagged at every threshold. "
              "'at tau' = the rule verdict is SUSPICIOUS at the calibrated tau_img (alpha = 0.05).")


# ----------------------------------------------------------------------------------------------- splits / suite
def suite_n(suite: str, full: int) -> int:
    """quick = 10% of the full count (at least 2)."""
    return full if suite == "full" else max(2, int(round(full * 0.1)))


def test_seeds(part: str, n: int) -> list[int]:
    """test split 3000-3299: 'comp' = 3000-3149 (composite experiments), 'prist' = 3150-3299 (pristine/robustness)."""
    base = SPLIT_SEEDS["test"] + (0 if part == "comp" else 150)
    assert n <= 150
    return list(range(base, base + n))


def require_calibration() -> dict:
    if not CALIB_DEFAULT.exists():
        raise SystemExit("lightaudit/calib_default.json does not exist yet: run `python -m lightaudit.cli calibrate` "
                         "first (results for the report must use the calibrated thresholds).")
    return load_calib()


def calib_info() -> dict:
    c = load_calib()
    keep = ("h", "T", "cov68", "cov95", "tau_img_05", "tau_img_10", "w_min", "n_cal", "seeds", "date", "source")
    return {k: c.get(k) for k in keep}


def header(exp: str, suite: str, **kw) -> dict:
    return dict(experiment=exp, suite=suite, caveat=CAVEAT, calibration=calib_info(),
                timestamp=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                python=sys.version.split()[0], platform=platform.platform(), **kw)


def _py(o):
    if isinstance(o, dict):
        return {str(k): _py(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_py(v) for v in o]
    if isinstance(o, np.ndarray):
        return _py(o.tolist())
    if isinstance(o, (np.bool_,)):
        return bool(o)
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (float, np.floating)):
        f = float(o)
        return None if not math.isfinite(f) else f
    return o


def write_json(name: str, obj: dict) -> Path:
    RESULTS.mkdir(parents=True, exist_ok=True)
    p = RESULTS / name
    p.write_text(json.dumps(_py(obj), indent=1))
    return p


def write_csv(name: str, rows: list[dict]) -> Path | None:
    if not rows:
        return None
    import csv
    RESULTS.mkdir(parents=True, exist_ok=True)
    p = RESULTS / name
    keys = list(dict.fromkeys(k for r in rows for k in r))
    with open(p, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, keys)
        w.writeheader()
        for r in rows:
            w.writerow({k: _py(r.get(k)) for k in keys})
    return p


def load_json(name: str) -> dict | None:
    p = RESULTS / name
    return json.loads(p.read_text()) if p.exists() else None


# ------------------------------------------------------------------------------------------------- parallel map
def n_procs() -> int:
    from lightaudit.calibrate import n_procs as _n
    return int(os.environ.get("LIGHTAUDIT_PROCS", _n()))


def pmap(fn, jobs: list, label: str = "", procs: int | None = None) -> list:
    """Order-preserving parallel map over scene-level jobs with a progress line."""
    procs = procs or n_procs()
    out = [None] * len(jobs)
    t0 = time.time()
    if procs <= 1 or len(jobs) <= 1:
        for i, j in enumerate(jobs):
            out[i] = fn(j)
            _progress(label, i + 1, len(jobs), t0)
        return out
    with mp.Pool(procs) as pool:
        for k, (i, r) in enumerate(pool.imap_unordered(_indexed, [(fn, i, j) for i, j in enumerate(jobs)])):
            out[i] = r
            _progress(label, k + 1, len(jobs), t0)
    return out


def _indexed(a):
    fn, i, j = a
    return i, fn(j)


def _progress(label, k, n, t0):
    if k == n or k % max(1, n // 20) == 0:
        print(f"  [{label}] {k}/{n}  {time.time() - t0:.0f}s", flush=True)


# ---------------------------------------------------------------------------------------------- slim regions
SLIM_KEYS = ("id", "name", "kind", "source", "excluded", "exclude_reason", "area_px", "n_valid", "spread_deg",
             "rho_max", "sharp_area", "mean_unc", "factors", "weight", "reason", "center", "samples", "glint_blobs",
             "contour")


def slim_region(r: dict) -> dict:
    d = {k: r.get(k) for k in SLIM_KEYS}
    d["center"] = np.asarray(r["center"], np.float64)
    if d["contour"] is not None:
        d["contour"] = np.asarray(d["contour"], np.float16)
    d["glint_blobs"] = [dict(l=np.asarray(b["l"], np.float64), sigma_deg=float(b["sigma_deg"]),
                             centroid=b["centroid"], area=b["area"]) for b in (r.get("glint_blobs") or [])]
    return d


def unslim_region(d: dict, cfg: Config, h: float | None = None, T: float | None = None) -> dict:
    """Full region dict for fuse_regions: P rebuilt from the bootstrap samples with (h, T) (default: cfg's)."""
    from lightaudit.cues import glint_landscape
    from lightaudit.grid import eq_dirs
    from lightaudit.posterior import credible, kde_posterior
    r = dict(d)
    if d["samples"] is not None:
        r["P"] = kde_posterior(d["samples"], cfg.kde_h if h is None else h, cfg.T if T is None else T)
        r["r68_deg"], r["r95_deg"], *_ = credible(r["P"])
    else:
        r["P"] = np.ones(len(eq_dirs()), np.float32)
        r["r68_deg"], r["r95_deg"] = 180.0, 180.0
    r["glint"] = glint_landscape(d["glint_blobs"]) if d["glint_blobs"] else None
    r["contour"] = None if d["contour"] is None else np.asarray(d["contour"], np.float32)
    return r


def _save(p: Path, obj) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(f".tmp{os.getpid()}")
    with open(tmp, "wb") as f:
        pickle.dump(obj, f, protocol=pickle.HIGHEST_PROTOCOL)
    os.replace(tmp, p)


def _load(p: Path):
    try:
        with open(p, "rb") as f:
            return pickle.load(f)
    except Exception:  # truncated / stale file: recompute
        return None


def _key(*parts) -> Path:
    return CACHE / CACHE_VERSION / ("_".join(str(p) for p in parts) + ".pkl")


# --------------------------------------------------------------------------------------------- cached audits
_SAMPLES: dict = {}


def sample(seed: int, kind: str):
    from lightaudit.synth import get_sample
    k = (seed, kind)
    if k not in _SAMPLES:
        _SAMPLES.clear()  # one scene at a time per worker
        _SAMPLES[k] = get_sample(seed, kind)
    return _SAMPLES[k]


def pristine(seed: int, kind: str, sigma: float = 8.0, cue: str = "rank", panel: bool | None = None) -> dict:
    """Slim pristine audit {seed, kind, sigma, cue, panel, light_cam, regions}; cached."""
    panel = (kind == "damage") if panel is None else panel
    p = _key("pr", kind, seed, f"s{sigma:g}", cue, "panel" if panel else "full")
    d = _load(p) if p.exists() else None
    if d is None:
        from lightaudit.pipeline import audit_sample
        s = sample(seed, kind)
        res = audit_sample(s, sigma, cfg=calibrated(), panel=panel, cue=cue, residual=False)
        d = dict(seed=seed, kind=kind, sigma=sigma, cue=cue, panel=panel, light_cam=np.asarray(s.light_cam, np.float64),
                 regions=[slim_region(r) for r in res["regions"]], edited=[], delta=0.0, target=None)
        _save(p, d)
    return d


def edited_ids(s, comp: dict, panel: bool, cfg: Config) -> list[int]:
    """Region ids >50% covered by the composite mask (same rule as audit_sample's ground truth)."""
    from lightaudit.regions import apply_roi
    from lightaudit.synth import region_meta
    labels, meta = s.labels.astype(np.int32), region_meta(s)
    if panel and s.dent_mask.any():
        labels, meta = apply_roi(labels, meta, s.dent_mask, cfg)
    m = comp["mask"]
    out = []
    for r in meta:
        a = int((labels == r["id"]).sum())
        if a and (m & (labels == r["id"])).sum() > 0.5 * a:
            out.append(r["id"])
    return out


def make_composite(s, target: str, delta: float, seed: int):
    """The E4 direction rule: l_B at `delta` from l_A, random azimuth around l_A drawn from the scene seed (so a
    scene uses the same azimuth for every delta). Returns None if the target does not exist (no distractor)."""
    from lightaudit.synth import light_at_angle, paste
    try:
        return paste(s, target, light_at_angle(s.scene.l_world, delta, seed))
    except ValueError:
        return None


def composite(seed: int, kind: str, target: str, delta: float, sigma: float = 8.0, cue: str = "rank") -> dict | None:
    """Slim composite audit (only the edited regions stored; the rest refer to the pristine record)."""
    panel = target == "dent"
    p = _key("co", kind, seed, target, f"d{delta:g}", f"s{sigma:g}", cue)
    d = _load(p) if p.exists() else None
    if d is None:
        from lightaudit.pipeline import audit_sample
        cfg = calibrated()
        s = sample(seed, kind)
        comp = make_composite(s, target, delta, seed)
        if comp is None:
            d = dict(missing=True)
        else:
            base = pristine(seed, kind, sigma, cue, panel)
            ed = edited_ids(s, comp, panel, cfg)
            reuse = dict(regions=[unslim_region(r, cfg) for r in base["regions"]])
            res = audit_sample(s, sigma, cfg=cfg, composite=comp, panel=panel, cue=cue, residual=False,
                               reuse=reuse, changed=ed)
            regs = [slim_region(r) if r["id"] in ed else ("ref", r["id"], r["excluded"], r.get("exclude_reason"))
                    for r in res["regions"]]
            d = dict(seed=seed, kind=kind, sigma=sigma, cue=cue, panel=panel, target=target, delta=float(comp["delta_deg"]),
                     delta_nominal=delta, light_cam=np.asarray(s.light_cam, np.float64), regions=regs,
                     edited=res["ground_truth"]["edited_region_ids"], changed=ed)
        _save(p, d)
    if d.get("missing"):
        return None
    if any(isinstance(r, tuple) for r in d["regions"]):
        base = {r["id"]: r for r in pristine(seed, kind, sigma, cue, panel)["regions"]}
        regs = []
        for r in d["regions"]:
            if isinstance(r, tuple):
                b = dict(base[r[1]])
                b.update(excluded=r[2], exclude_reason=r[3])
                regs.append(b)
            else:
                regs.append(r)
        d = dict(d, regions=regs)
    return d


# -------------------------------------------------------------------------------------------- re-fusion
def refuse(rec: dict, cfg: Config, cues=CUE_SETS["C1+C2+C3"], loo: bool = True, h=None, T=None):
    """(fusion, regions) for a slim record under the given config / cue set / KDE parameters."""
    from lightaudit.pipeline import fuse_regions
    regs = [unslim_region(r, cfg, h, T) for r in rec["regions"]]
    f = fuse_regions(regs, cfg, cues=cues, loo=loo)
    return f, regs


def summarize(f: dict, regs: list[dict], edited=()) -> dict:
    """Per-image outcome used by every experiment."""
    v = f["verdict"]
    top = f["top_region"]
    top_id = regs[top]["id"] if top is not None else None
    flagged_ids = [regs[k]["id"] for k in f["flagged"]]
    return dict(verdict=v, S_img=float(f["S_img"]), score=float(f["S_img"]) if v != "INSUFFICIENT" else float("-inf"),
                top_id=top_id, top_correct=bool(top_id in edited) if edited else None,
                flagged_ids=flagged_ids, flag_correct=bool(set(flagged_ids) & set(edited)) if edited else None,
                n_reliable=int(f["n_reliable"]))


def evaluate(rec: dict, cfg: Config, variants: dict) -> dict:
    """{variant name: summary}. variants = {name: dict(cues=..., loo=..., h=..., T=..., cfg=Config)}."""
    out = {}
    for name, v in variants.items():
        c = v.get("cfg", cfg)
        f, regs = refuse(rec, c, v.get("cues", CUE_SETS["C1+C2+C3"]), v.get("loo", True), v.get("h"), v.get("T"))
        s = summarize(f, regs, rec.get("edited") or ())
        if v.get("arbiter"):
            from lightaudit import arbiter
            s["arb_score"] = arbiter.score(dict(regions=regs, fusion=f)) if f["verdict"] != "INSUFFICIENT" else float("-inf")
        out[name] = s
    return out


def std_variants(cfg: Config, arbiter: bool = False) -> dict:
    v = {k: dict(cues=c) for k, c in CUE_SETS.items()}
    if arbiter:
        v["C1+C2+C3"]["arbiter"] = True
    return v


def cfg_dict(cfg: Config) -> dict:
    return {k: v for k, v in asdict(cfg).items() if k in ("kde_h", "T", "tau_img", "tau_ref_factor", "w_min", "alpha",
                                                          "w_glint", "w_contour", "B", "N_exact")}


def replace_cfg(cfg: Config, **kw) -> Config:
    return replace(cfg, **kw)
