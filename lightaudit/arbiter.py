"""Gradient-boosted arbiter (BUILD_SPEC 9.1, P1). The default decision mode stays the explainable rule; the arbiter
is evaluated as an ablation (E8(e)).

Training data: region-level rows from the *arbiter* split (seeds 2000+): for each scene the pristine audit (all
rows label 0) and one composite (a car or distractor re-lit at a random angle in [20, 180] deg on `normal` scenes,
a re-lit dent in panel mode on `damage` scenes; rows of the pasted region label 1). Only reliable regions give
rows (the image score is a max over reliable regions). The alarm threshold is the split-conformal quantile of the
image-level arbiter score on pristine *calibration*-split scenes (same 70% normal / 30% damage mix as
calibrate.py). Nothing from the test split is used.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone

import numpy as np

from .config import ROOT, SPLIT_SEEDS, Config, calibrated

MODEL = ROOT / "lightaudit" / "arbiter.joblib"
SUMMARY = ROOT / "data" / "results" / "arbiter.json"
FEATURES = ["s_k", "angle_k", "w", "f_size", "f_spread", "f_sharp", "f_dir", "f_norm", "rho_max", "sharp_area",
            "mean_unc", "has_glint", "n_valid", "spread_deg", "is_largest_region"]
_MODEL_CACHE: dict = {}


def features(region: dict, is_largest: bool) -> list:
    """Feature vector of one fused region (after fuse_regions wrote shortfall / angle_deg into it)."""
    f = region.get("factors") or {}
    s = region.get("shortfall")
    a = region.get("angle_deg")
    return [float(s) if s is not None else np.nan, float(a) if a is not None else np.nan, float(region["weight"]),
            f.get("f_size", np.nan), f.get("f_spread", np.nan), f.get("f_sharp", np.nan), f.get("f_dir", np.nan),
            f.get("f_norm", np.nan), float(region["rho_max"]), float(region["sharp_area"]), float(region["mean_unc"]),
            float(region.get("glint") is not None or bool(region.get("glint_blobs"))), float(region["n_valid"]),
            float(region["spread_deg"]), float(is_largest)]


def _rows(result: dict) -> list[tuple[int, list]]:
    """(region index, features) for every reliable region of a fused result."""
    regs = result["regions"]
    cand = [r for r in regs if not r.get("excluded") and r.get("kind", "region") == "region"]
    largest = max(cand, key=lambda r: r["area_px"])["id"] if cand else None
    return [(i, features(r, r["id"] == largest)) for i, r in enumerate(regs) if r.get("reliable")]


def load(path=MODEL) -> dict:
    key = str(path)
    if key not in _MODEL_CACHE:
        import joblib
        _MODEL_CACHE[key] = joblib.load(path)
    return _MODEL_CACHE[key]


def region_probs(result: dict, model: dict | None = None) -> dict:
    """{region index: P(region is pasted)} for the reliable regions."""
    m = model or load()
    rows = _rows(result)
    if not rows:
        return {}
    p = m["model"].predict_proba(np.array([x for _, x in rows], np.float64))[:, 1]
    return {i: float(v) for (i, _), v in zip(rows, p)}


def score(result: dict, model: dict | None = None) -> float:
    """Image-level arbiter score = max predicted probability over reliable regions (0 if there are none)."""
    p = region_probs(result, model)
    return max(p.values()) if p else 0.0


def verdict(result: dict, threshold: float | None = None, model: dict | None = None) -> str:
    """Arbiter decision mode: abstentions of the rule (INSUFFICIENT) are kept; otherwise SUSPICIOUS iff the arbiter
    score exceeds the conformal threshold, else CONSISTENT."""
    if result["fusion"]["verdict"] == "INSUFFICIENT":
        return "INSUFFICIENT"
    m = model or load()
    t = m["threshold"] if threshold is None else threshold
    return "SUSPICIOUS" if score(result, m) > t else "CONSISTENT"


# ------------------------------------------------------------------------------------------------- training
def _arb_job(args):
    """Rows of one arbiter-split scene: pristine + one composite."""
    i, seed = args
    sys.path.insert(0, str(ROOT))
    from eval import common as C
    cfg = calibrated()
    rng = np.random.default_rng([seed, 99])
    kind = "damage" if i % 10 >= 7 else "normal"
    target = "dent" if kind == "damage" else ("car" if i % 2 == 0 else "distractor")
    delta = float(rng.uniform(20, 180))
    out = []
    recs = [C.pristine(seed, kind)]
    co = C.composite(seed, kind, target, round(delta, 1))
    if co is not None:
        recs.append(co)
    for rec in recs:
        f, regs = C.refuse(rec, cfg)
        for k, x in _rows(dict(regions=regs, fusion=f)):
            out.append(dict(seed=seed, kind=kind, target=rec.get("target"), delta=rec.get("delta", 0.0), x=x,
                            y=int(regs[k]["id"] in (rec.get("edited") or []))))
    return out


def _cal_job(args):
    i, seed = args
    sys.path.insert(0, str(ROOT))
    from eval import common as C
    from .calibrate import cal_kind
    cfg = calibrated()
    rec = C.pristine(seed, cal_kind(i))
    f, regs = C.refuse(rec, cfg)
    return dict(seed=seed, kind=cal_kind(i), verdict=f["verdict"], rows=[x for _, x in _rows(dict(regions=regs, fusion=f))])


def train(n: int = 200, n_cal: int | None = None, procs: int | None = None) -> dict:
    """Builds the rows, fits the classifier, sets the conformal threshold, saves the model and a summary."""
    import joblib
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.inspection import permutation_importance
    from sklearn.metrics import roc_auc_score
    sys.path.insert(0, str(ROOT))
    from eval import common as C
    from .calibrate import conformal_quantile
    from .config import CALIB_DEFAULT
    cfg = Config()
    n_cal = n_cal or cfg.n_cal
    s0, c0 = SPLIT_SEEDS["arb"], SPLIT_SEEDS["cal"]
    n = min(n, 200)
    rows = [r for rs in C.pmap(_arb_job, [(i, s0 + i) for i in range(n)], "arbiter rows", procs) for r in rs]
    X = np.array([r["x"] for r in rows], np.float64)
    y = np.array([r["y"] for r in rows], int)
    scene = np.array([r["seed"] for r in rows])
    # held-out scenes (20%) for the importance / AUC report; the final model is refit on all scenes
    seeds = np.unique(scene)
    held = set(np.random.default_rng(0).choice(seeds, max(1, len(seeds) // 5), replace=False).tolist())
    te = np.array([s in held for s in scene])

    def fit(Xa, ya):
        return HistGradientBoostingClassifier(max_iter=200, learning_rate=0.05, max_leaf_nodes=15,
                                              l2_regularization=1.0, random_state=0).fit(Xa, ya)

    m_tr = fit(X[~te], y[~te])
    held_auc = float(roc_auc_score(y[te], m_tr.predict_proba(X[te])[:, 1])) if len(set(y[te])) == 2 else None
    imp = permutation_importance(m_tr, X[te], y[te], scoring="roc_auc", n_repeats=20, random_state=0) \
        if held_auc is not None else None
    model = fit(X, y)
    # conformal threshold on pristine calibration-split scenes (INSUFFICIENT excluded, as for tau_img)
    cal = C.pmap(_cal_job, [(i, c0 + i) for i in range(n_cal)], "arbiter calibration", procs)
    bundle = dict(model=model, features=FEATURES, threshold=None)
    cal_scores = []
    for c in cal:
        if c["verdict"] == "INSUFFICIENT":
            continue
        p = model.predict_proba(np.array(c["rows"], np.float64))[:, 1] if c["rows"] else []
        cal_scores.append(float(max(p)) if len(p) else 0.0)
    thr05 = conformal_quantile(cal_scores, 0.05)
    thr10 = conformal_quantile(cal_scores, 0.10)
    note = None
    if not np.isfinite(thr05):
        thr05, note = float(max(cal_scores)), "n too small for the conformal quantile; used the maximum"
    bundle.update(threshold=float(thr05), threshold_10=float(thr10) if np.isfinite(thr10) else None)
    MODEL.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(bundle, MODEL)
    _MODEL_CACHE.clear()
    summary = dict(
        n_scenes=n, seeds=[s0, s0 + n - 1], n_rows=int(len(y)), n_pos=int(y.sum()), features=FEATURES,
        threshold=float(thr05), threshold_alpha=0.05, threshold_10=bundle["threshold_10"], threshold_note=note,
        n_cal_scenes=n_cal, cal_seeds=[c0, c0 + n_cal - 1], n_cal_scored=len(cal_scores),
        cal_insufficient_rate=1 - len(cal_scores) / max(len(cal), 1),
        heldout_scenes=len(held), heldout_rows=int(te.sum()), heldout_region_auc=held_auc,
        permutation_importance=None if imp is None else [
            dict(feature=FEATURES[j], mean=float(imp.importances_mean[j]), std=float(imp.importances_std[j]))
            for j in np.argsort(-imp.importances_mean)],
        calibration_file=CALIB_DEFAULT.name if CALIB_DEFAULT.exists() else "uncalibrated defaults",
        calibration_used=dict(h=calibrated().kde_h, T=calibrated().T, tau_img=calibrated().tau_img, w_min=calibrated().w_min),
        model="HistGradientBoostingClassifier(max_iter=200, learning_rate=0.05, max_leaf_nodes=15, l2=1.0)",
        composites="normal scenes: car (even i) / distractor (odd i); damage scenes (i % 10 >= 7): dent in panel mode; "
                   "delta ~ U[20, 180] deg; plus the pristine audit of every scene",
        timestamp=datetime.now(timezone.utc).isoformat(timespec="seconds"))
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY.write_text(json.dumps(C._py(summary), indent=1))
    return summary


if __name__ == "__main__":
    print(json.dumps(train(int(sys.argv[1]) if len(sys.argv) > 1 else 200), indent=1))
