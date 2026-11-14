"""E4 - minimum detectable inconsistency (H4, headline).

Composite scenes = test seeds 3000-3149 (n_comp); pristine reference scenes = test seeds 3150-3299 (n_pristine).
For each composite scene and each delta in DELTAS the target is re-lit by l_B at `delta` from the sun l_A (random
azimuth around l_A drawn from the scene seed, the same for every delta) and pasted (8.6); noisy_gt(8) normals.
Targets: car (`normal` scenes), the largest distractor (`normal` scenes; skipped if none >= 1500 px), the dent
(`damage` scenes, panel mode). Negatives: pristine `normal` scenes (car / distractor) or pristine `damage`
scenes in panel mode (dent), all from the pristine half of the test split.

Two operating points:
  * TPR@FPR=5% with the threshold taken from the pristine TEST score distribution (as the spec asks; labelled so),
  * TPR at the calibrated tau_img (verdict SUSPICIOUS; the threshold comes from the calibration split).
MDI = smallest delta on the grid with TPR >= 0.5 (and the linearly interpolated crossing).
The raw per-image outcomes (also used by E5 and E8) are computed here by `collect`.
"""
from __future__ import annotations

import pickle

import numpy as np

from . import common as C
from . import metrics as M

DELTAS = (0, 10, 20, 30, 45, 60, 90, 135, 180)
TARGETS = ("car", "distractor", "dent")


def _variants(cfg, ablations: bool):
    from dataclasses import replace
    from lightaudit.arbiter import MODEL
    v = C.std_variants(cfg, arbiter=MODEL.exists())
    if ablations:
        v.update({
            "noKDEcal": dict(cues=C.CUE_SETS["C1+C2+C3"], h=10.0, T=1.0),
            "wmin0.25": dict(cues=C.CUE_SETS["C1+C2+C3"], cfg=replace(cfg, w_min=0.25)),
            "wmin0.50": dict(cues=C.CUE_SETS["C1+C2+C3"], cfg=replace(cfg, w_min=0.50)),
            "noLOO": dict(cues=C.CUE_SETS["C1+C2+C3"], loo=False),
            "contour0.5": dict(cues=C.CUE_SETS["C1+C2+C3"], cfg=replace(cfg, w_contour=0.5)),
        })
    return v


def _job(args) -> list[dict]:
    part, seed, deltas = args
    from lightaudit.config import calibrated
    cfg = calibrated()
    out = []

    def add(rec, target, cue, variants):
        if rec is None:
            out.append(dict(seed=seed, part=part, target=target, delta=None, cue=cue, missing=True))
            return
        out.append(dict(seed=seed, part=part, target=target, delta=rec.get("delta_nominal", 0.0),
                        delta_actual=rec.get("delta", 0.0), cue=cue, kind=rec["kind"], missing=False,
                        res=C.evaluate(rec, cfg, variants)))

    full_v, std_v, ls_v = _variants(cfg, True), _variants(cfg, False), {C.BASE: dict(cues=("shading",))}
    if part == "prist":
        add(C.pristine(seed, "normal"), "pristine_normal", C.MAIN, full_v)
        add(C.pristine(seed, "normal", cue=C.ALT), "pristine_normal", C.ALT, ls_v)
        add(C.pristine(seed, "damage"), "pristine_damage", C.MAIN, std_v)
        return out
    for d in deltas:
        add(C.composite(seed, "normal", "car", d), "car", C.MAIN, full_v)
        add(C.composite(seed, "normal", "car", d, cue=C.ALT), "car", C.ALT, ls_v)
        add(C.composite(seed, "normal", "distractor", d), "distractor", C.MAIN, std_v)  # None: no distractor
        add(C.composite(seed, "damage", "dent", d), "dent", C.MAIN, std_v)
    return out


def collect(suite: str) -> list[dict]:
    """All per-image outcomes of the composite + pristine test sets (cached per suite/calibration/arbiter)."""
    from lightaudit.arbiter import MODEL
    C.require_calibration()
    n_c, n_p = C.suite_n(suite, 150), C.suite_n(suite, 150)
    sig = dict(calib=C.calib_info(), arb=MODEL.stat().st_mtime if MODEL.exists() else None, n=(n_c, n_p),
               deltas=DELTAS, v=C.CACHE_VERSION)
    p = C.CACHE / f"e04_raw_{suite}.pkl"
    if p.exists():
        got = C._load(p)
        if got and got.get("sig") == sig:
            return got["rows"]
    jobs = [("comp", s, DELTAS) for s in C.test_seeds("comp", n_c)] + [("prist", s, DELTAS) for s in C.test_seeds("prist", n_p)]
    rows = [r for rs in C.pmap(_job, jobs, "E4 audits") for r in rs]
    C._save(p, dict(sig=sig, rows=rows))
    return rows


def negatives(rows, target: str, cue: str = C.MAIN):
    t = "pristine_damage" if target == "dent" else "pristine_normal"
    return [r for r in rows if r["target"] == t and r["cue"] == cue and not r["missing"]]


def positives(rows, target: str, delta, cue: str = C.MAIN):
    return [r for r in rows if r["target"] == target and r["cue"] == cue and not r["missing"] and r["delta"] == delta]


def scores(rs, variant, key="score"):
    return [r["res"][variant][key] for r in rs]


def curve(rows, target, variant, cue=C.MAIN, n_boot=1000):
    """TPR@5%FPR (test-pristine threshold) and TPR@tau per delta, with scene-bootstrap CIs."""
    neg = negatives(rows, target, cue)
    ns = scores(neg, variant)
    t5 = M.threshold_at_fpr(ns, 0.05)
    neg_flag = [r["res"][variant]["verdict"] == "SUSPICIOUS" for r in neg]
    out = dict(variant=variant, cue=cue, n_neg=len(neg), threshold_fpr5_from_test_pristine=t5,
               fpr_at_tau=float(np.mean(neg_flag)) if neg else None,
               neg_abstain=float(np.mean([r["res"][variant]["verdict"] == "INSUFFICIENT" for r in neg])) if neg else None,
               deltas=[], n_pos=[], tpr5=[], tpr5_ci=[], tpr_tau=[], tpr_tau_ci=[], loc_tau=[], top1=[], abstain=[],
               mean_delta_actual=[])
    for d in DELTAS:
        pos = positives(rows, target, d, cue)
        if not pos:
            continue
        ps = scores(pos, variant)
        a = M.bootstrap_ci(lambda P, N: M.tpr_at_fpr(N, P, 0.05), ps, ns, n_boot=n_boot, seed=int(d))
        fl = [float(r["res"][variant]["verdict"] == "SUSPICIOUS") for r in pos]
        b = M.bootstrap_ci(lambda P: float(np.mean(P)), fl, n_boot=n_boot, seed=int(d) + 1)
        out["deltas"].append(d)
        out["n_pos"].append(len(pos))
        out["tpr5"].append(a[0])
        out["tpr5_ci"].append([a[1], a[2]])
        out["tpr_tau"].append(b[0])
        out["tpr_tau_ci"].append([b[1], b[2]])
        out["loc_tau"].append(float(np.mean([r["res"][variant]["verdict"] == "SUSPICIOUS" and r["res"][variant]["flag_correct"]
                                             for r in pos])))
        out["top1"].append(float(np.mean([bool(r["res"][variant]["top_correct"]) for r in pos])))
        out["abstain"].append(float(np.mean([r["res"][variant]["verdict"] == "INSUFFICIENT" for r in pos])))
        out["mean_delta_actual"].append(float(np.mean([r["delta_actual"] for r in pos])))
    out["mdi_fpr5"], out["mdi_fpr5_interp"] = M.mdi(out["deltas"], out["tpr5"])
    out["mdi_tau"], out["mdi_tau_interp"] = M.mdi(out["deltas"], out["tpr_tau"])
    return out


def run(suite: str) -> dict:
    rows = collect(suite)
    res = {}
    for target in TARGETS:
        cur = {v: curve(rows, target, v) for v in C.CUE_SETS}
        if target == "car":
            cur[C.BASE] = curve(rows, target, C.BASE, cue=C.ALT)
        cur["fused"] = dict(cur["C1+C2+C3"], variant="fused")
        n_scenes = len({r["seed"] for r in rows if r["target"] == target and not r["missing"]})
        n_missing = len({r["seed"] for r in rows if r["target"] == target and r["missing"]})
        res[target] = dict(curves=cur, n_scenes=n_scenes, n_scenes_without_target=n_missing)
    comp = C.test_seeds("comp", C.suite_n(suite, 150))
    prist = C.test_seeds("prist", C.suite_n(suite, 150))
    out = C.header("E4", suite, deltas=list(DELTAS), targets=res, normals="noisy_gt(8)",
                   comp_seeds=[comp[0], comp[-1]], pristine_seeds=[prist[0], prist[-1]],
                   n_comp_scenes=len(comp), n_pristine_scenes=len(prist), score_definition=C.SCORE_NOTE,
                   fused_note=C.FUSED_NOTE,
                   threshold_note="TPR@FPR=5%: threshold from the pristine TEST score distribution (spec 14.2 E4); "
                                  "TPR@tau: calibrated tau_img from the calibration split.",
                   ls_note="LS baseline = the LS landscape in place of C1, shading cue only (compare with C1).")
    C.write_json("e04_mdi.json", out)
    flat = []
    for t, r in res.items():
        for v, c in r["curves"].items():
            for i, d in enumerate(c["deltas"]):
                flat.append(dict(target=t, variant=v, delta=d, n_pos=c["n_pos"][i], n_neg=c["n_neg"], tpr_fpr5=c["tpr5"][i],
                                 tpr_fpr5_lo=c["tpr5_ci"][i][0], tpr_fpr5_hi=c["tpr5_ci"][i][1], tpr_tau=c["tpr_tau"][i],
                                 tpr_tau_lo=c["tpr_tau_ci"][i][0], tpr_tau_hi=c["tpr_tau_ci"][i][1],
                                 loc_tau=c["loc_tau"][i], top1=c["top1"][i]))
    C.write_csv("e04_tpr_vs_delta.csv", flat)
    return out
