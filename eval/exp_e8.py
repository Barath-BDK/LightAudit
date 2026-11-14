"""E8 - ablations on the car target (E4 data): (a) cue subsets, (b) rank vs LS, (c) KDE calibration off (h=10, T=1),
(d) w_min in {0.25, 0.35, 0.5}, (e) rule vs arbiter, (g) leave-one-out off (single global consensus); plus
(f) region backend gt vs slic on 30 scenes (pristine + car at 90 deg), re-audited from scratch.
Metrics: AUC (delta >= 30 vs pristine), TPR@5%FPR at delta = 90 (threshold from the test pristine scores),
MDI at 5% FPR, abstention rate (INSUFFICIENT) on pristine and on composites."""
from __future__ import annotations

import numpy as np

from . import common as C
from . import metrics as M
from .exp_e4 import DELTAS, collect, negatives

ROWS = [("rule, C1 (shading)", "C1", "score"), ("rule, C1+C2", "C1+C2", "score"), ("rule, default (silhouette weight 0, same as C1+C2)", "C1+C2+C3", "score"),
        ("with silhouette cue (w_contour = 0.5)", "contour0.5", "score"),
        (C.BASE + " baseline (shading)", C.BASE, "score"), ("KDE calibration off (h=10, T=1)", "noKDEcal", "score"),
        ("w_min = 0.25", "wmin0.25", "score"), ("w_min = 0.50", "wmin0.50", "score"),
        ("no leave-one-out (global consensus)", "noLOO", "score"), ("arbiter (default cues)", "C1+C2+C3", "arb_score")]


def _ablate(rows, variant, key):
    cue = C.ALT if variant == C.BASE else C.MAIN
    neg = negatives(rows, "car", cue)
    if not neg or variant not in neg[0]["res"] or key not in neg[0]["res"][variant]:
        return None
    ns = [r["res"][variant][key] for r in neg]
    pos = {d: [r for r in rows if r["target"] == "car" and r["cue"] == cue and not r["missing"] and r["delta"] == d]
           for d in DELTAS}
    p30 = [r["res"][variant][key] for d in DELTAS if d >= 30 for r in pos[d]]
    p90 = [r["res"][variant][key] for r in pos[90]]
    a = M.bootstrap_ci(lambda N, P: M.auc(N, P), ns, p30, n_boot=1000, seed=8)
    t = M.bootstrap_ci(lambda N, P: M.tpr_at_fpr(N, P, 0.05), ns, p90, n_boot=1000, seed=9)
    tprs = [M.tpr_at_fpr(ns, [r["res"][variant][key] for r in pos[d]], 0.05) for d in DELTAS if pos[d]]
    mdi, mdi_i = M.mdi([d for d in DELTAS if pos[d]], tprs)
    allpos = [r for d in DELTAS for r in pos[d]]
    return dict(auc=a[0], auc_ci=[a[1], a[2]], tpr5_d90=t[0], tpr5_d90_ci=[t[1], t[2]], mdi_fpr5=mdi, mdi_fpr5_interp=mdi_i,
                abstain_pristine=float(np.mean([r["res"][variant]["verdict"] == "INSUFFICIENT" for r in neg])),
                abstain_comp=float(np.mean([r["res"][variant]["verdict"] == "INSUFFICIENT" for r in allpos])),
                n_neg=len(ns), n_pos_d90=len(p90), n_pos_d30plus=len(p30))


def _slic_job(args):
    seed, spliced = args
    from lightaudit.config import calibrated
    from lightaudit.pipeline import audit
    from lightaudit.regions import auto_exclude, propose_regions
    from lightaudit.synth import simulate_normals
    cfg = calibrated()
    key = C._key("e8slic", seed, int(spliced))
    rec = C._load(key) if key.exists() else None
    if rec is None:
        s = C.sample(seed, "normal")
        comp = C.make_composite(s, "car", 90, seed) if spliced else None
        rgb = comp["rgb"] if comp else s.rgb
        n, u = simulate_normals(s.normals_gt, s.labels, 8.0, s.scene.seed, cfg)
        lab, meta = propose_regions(rgb, n, "slic", cfg)
        meta = auto_exclude(rgb, lab, meta, cfg)
        res = audit(rgb, n, u, lab, meta, cfg, s.scene.fov_deg, seed=s.scene.seed, residual=False)
        ed = [r["id"] for r in res["regions"] if comp is not None and r["area_px"]
              and (comp["mask"] & (lab == r["id"])).sum() > 0.5 * r["area_px"]]
        rec = dict(seed=seed, kind="normal", regions=[C.slim_region(r) for r in res["regions"]], edited=ed)
        C._save(key, rec)
    gt = C.composite(seed, "normal", "car", 90) if spliced else C.pristine(seed, "normal")
    v = {"fused": dict(cues=C.CUE_SETS["C1+C2+C3"])}
    return dict(seed=seed, spliced=spliced, slic=C.evaluate(rec, cfg, v)["fused"], gt=C.evaluate(gt, cfg, v)["fused"])


def run(suite: str) -> dict:
    rows = collect(suite)
    table = []
    for label, v, key in ROWS:
        r = _ablate(rows, v, key)
        table.append(dict(ablation=label, variant=v, score=key, available=r is not None, **(r or {})))
    n = C.suite_n(suite, 30)
    sl = C.pmap(_slic_job, [(s, False) for s in C.test_seeds("prist", n)] + [(s, True) for s in C.test_seeds("comp", n)], "E8 slic")
    seg = {}
    for be in ("gt", "slic"):
        neg = [r[be] for r in sl if not r["spliced"]]
        pos = [r[be] for r in sl if r["spliced"]]
        seg[be] = dict(auc=M.auc([r["score"] for r in neg], [r["score"] for r in pos]),
                       tpr_tau=float(np.mean([r["verdict"] == "SUSPICIOUS" for r in pos])),
                       fpr_tau=float(np.mean([r["verdict"] == "SUSPICIOUS" for r in neg])),
                       loc_tau=float(np.mean([r["verdict"] == "SUSPICIOUS" and bool(r["flag_correct"]) for r in pos])),
                       abstain_pristine=float(np.mean([r["verdict"] == "INSUFFICIENT" for r in neg])),
                       abstain_comp=float(np.mean([r["verdict"] == "INSUFFICIENT" for r in pos])),
                       n_pristine=len(neg), n_spliced=len(pos))
    arb = C.load_json("arbiter.json")
    out = C.header("E8", suite, target="car", table=table, region_backend=seg, n_seg_scenes=n,
                   arbiter=None if arb is None else dict(threshold=arb.get("threshold"),
                                                         permutation_importance=arb.get("permutation_importance"),
                                                         heldout_region_auc=arb.get("heldout_region_auc"),
                                                         n_rows=arb.get("n_rows"), n_scenes=arb.get("n_scenes")),
                   notes="w_min variants keep the calibrated tau (calibrated at w_min = 0.35). Arbiter abstains where the "
                         "rule abstains (INSUFFICIENT -> score -inf). Region-backend comparison uses all cues and the "
                         "calibrated tau; slic regions are re-audited from scratch.")
    C.write_json("e08_ablations.json", out)
    C.write_csv("e08_ablations.csv", [{k: v for k, v in r.items() if not isinstance(v, list)} for r in table])
    return out
