"""E5 - detection ROC: composites with delta >= 30 deg (pooled) vs pristine test scenes, per cue set and for the
LS baseline; localisation (is k_top the pasted region?). Uses the per-image outcomes of E4."""
from __future__ import annotations

import numpy as np

from . import common as C
from . import metrics as M
from .exp_e4 import TARGETS, collect, negatives

MIN_DELTA = 30


def _pos_by_scene(rows, target, cue):
    by = {}
    for r in rows:
        if r["target"] == target and r["cue"] == cue and not r["missing"] and r["delta"] >= MIN_DELTA:
            by.setdefault(r["seed"], []).append(r)
    return list(by.values())


def run(suite: str) -> dict:
    rows = collect(suite)
    out_t = {}
    for target in TARGETS:
        variants = list(C.CUE_SETS) + ([C.BASE] if target == "car" else [])
        res = {}
        for v in variants:
            cue = C.ALT if v == C.BASE else C.MAIN
            neg = negatives(rows, target, cue)
            pos = _pos_by_scene(rows, target, cue)
            ns = [r["res"][v]["score"] for r in neg]
            ps = [[r["res"][v]["score"] for r in g] for g in pos]
            a = M.bootstrap_ci(lambda P, N: M.auc(N, [x for g in P for x in g]), ps, ns, n_boot=1000, seed=5)
            flat = [x for g in ps for x in g]
            fpr, tpr = M.roc_curve(ns, flat)
            if len(fpr) > 200:  # thin the curve for the JSON
                keep = np.unique(np.linspace(0, len(fpr) - 1, 200).astype(int))
                fpr, tpr = fpr[keep], tpr[keep]
            pr = [r for g in pos for r in g]
            sus = [r for r in pr if r["res"][v]["verdict"] == "SUSPICIOUS"]
            res[v] = dict(auc=a[0], auc_ci=[a[1], a[2]], n_pos=len(flat), n_pos_scenes=len(ps), n_neg=len(ns),
                          roc_fpr=fpr, roc_tpr=tpr,
                          tpr_fpr5_test_threshold=M.tpr_at_fpr(ns, flat, 0.05),
                          top1_all=float(np.mean([bool(r["res"][v]["top_correct"]) for r in pr])) if pr else None,
                          n_suspicious=len(sus),
                          flag_correct_among_suspicious=float(np.mean([bool(r["res"][v]["flag_correct"]) for r in sus]))
                          if sus else None,
                          abstain_pos=float(np.mean([r["res"][v]["verdict"] == "INSUFFICIENT" for r in pr])) if pr else None,
                          abstain_neg=float(np.mean([r["res"][v]["verdict"] == "INSUFFICIENT" for r in neg])) if neg else None)
        res["fused"] = dict(res["C1+C2+C3"])
        out_t[target] = res
    out = C.header("E5", suite, min_delta=MIN_DELTA, targets=out_t, score_definition=C.SCORE_NOTE,
                   fused_note=C.FUSED_NOTE,
                   localisation_note="top1_all: k_top (the region with the largest shortfall) is the pasted region, over "
                                     "all composites with delta >= 30; flag_correct_among_suspicious: among SUSPICIOUS "
                                     "verdicts, a pasted region is among the flagged ones.")
    C.write_json("e05_roc.json", out)
    return out
