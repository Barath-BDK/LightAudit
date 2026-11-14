"""E9 - attacks (red team of the defender's own tool).

Composites with delta ~ U[90, 135] deg (per scene) for the car and distractor (`normal` test scenes 3000+) and the
dent (`damage` scenes, panel mode); n = 75 scenes per target in the full suite. Tiers: T0 (the naive composite),
T1 colour transfer, T3a re-shade with attacker light error sigma_att in {0, 5, 10, 20, 40} deg and attacker normals
in {same (white box), independent (fresh noisy copy)}, T4 adaptive (white-box search, same normals).
Caveat (spec 10): the defender's noisy_gt normals do not change when the image is edited, which is the best case for
the attacker. An attacked region that becomes auto-excluded / not assessable counts as "passes".
Detection = SUSPICIOUS at the calibrated tau (rule), and score > threshold at FPR = 5% from the pristine test scores.
"""
from __future__ import annotations

import numpy as np

from . import common as C
from . import metrics as M

TARGETS = ("car", "distractor", "dent")
SIG = (0, 5, 10, 20, 40)
VARS = {"C1": C.CUE_SETS["C1"], "fused": C.CUE_SETS["C1+C2+C3"]}


def _eval(res, cfg, edited):
    from lightaudit.pipeline import fuse_regions
    out = {}
    for v, cues in VARS.items():
        regs = [dict(r) for r in res["regions"]]
        f = fuse_regions(regs, cfg, cues=cues)
        out[v] = C.summarize(f, regs, edited)
    return out


def _job(args):
    seed, target = args
    key = C._key("e9", seed, target)
    got = C._load(key) if key.exists() else None
    if got is not None:
        return got
    from lightaudit.attacks import run_attack
    from lightaudit.config import calibrated
    from lightaudit.grid import angle_deg
    from lightaudit.pipeline import audit_sample
    from lightaudit.synth import simulate_normals
    cfg = calibrated()
    kind = "damage" if target == "dent" else "normal"
    panel = target == "dent"
    s = C.sample(seed, kind)
    delta = float(np.random.default_rng([seed, 9]).uniform(90, 135))
    comp = C.make_composite(s, target, delta, seed)
    if comp is None:
        C._save(key, None)
        return None
    ed = C.edited_ids(s, comp, panel, cfg)
    pr = C.pristine(seed, kind, panel=panel)
    base = audit_sample(s, cfg=cfg, composite=comp, panel=panel, residual=False,
                        reuse=dict(regions=[C.unslim_region(r, cfg) for r in pr["regions"]]), changed=ed)
    edited = base["ground_truth"]["edited_region_ids"]
    cand = [r for r in base["regions"] if r["id"] in ed and not r["excluded"]]
    out = dict(seed=seed, target=target, delta=comp["delta_deg"], attacks=[])
    out["attacks"].append(dict(tier="T0", sigma=None, normals=None, res=_eval(base, cfg, edited), fidelity=None, l_err=None))
    if not cand:
        out["no_region"] = True
        C._save(key, out)
        return out
    rid = max(cand, key=lambda r: r["n_valid"])["id"]
    out["region_id"] = rid
    reaudit = lambda rgb: audit_sample(s, cfg=cfg, composite=dict(comp, rgb=rgb), panel=panel, reuse=base,  # noqa: E731
                                       changed=[rid], residual=False)
    n_ind = simulate_normals(s.normals_gt, s.labels, 8, s.scene.seed + 9999, cfg)[0]
    plan = [("T1", 0, "same", None)] + [("T3a", sg, nm, na) for nm, na in (("same", None), ("independent", n_ind))
                                         for sg in SIG] + [("T4", 0, "same", None)]
    for tier, sg, nm, na in plan:
        a = run_attack(tier, base, rid, reaudit, normals_att=na, sigma_att=float(sg), seed=seed, cfg=cfg)
        out["attacks"].append(dict(tier=tier, sigma=sg if tier == "T3a" else None, normals=nm if tier != "T1" else None,
                                   res=_eval(a["result"], cfg, edited), fidelity=a["fidelity"],
                                   l_err=float(angle_deg(a["l_hat"], s.light_cam)) if tier != "T1" else None))
    C._save(key, out)
    return out


def _label(tier, sg, nm):
    if tier == "T0":
        return "T0 naive paste"
    if tier == "T1":
        return "T1 colour transfer"
    if tier == "T4":
        return "T4 adaptive (white box)"
    return f"T3a re-shade ({'exact light' if sg == 0 else f'±{sg}° error'}{', independent normals' if nm == 'independent' else ''})"


def run(suite: str) -> dict:
    from .exp_e4 import collect, negatives
    C.require_calibration()
    n = C.suite_n(suite, 75)
    jobs = [(s, t) for t in TARGETS for s in C.test_seeds("comp", n)]
    rows = [r for r in C.pmap(_job, jobs, "E9 attacks") if r is not None]
    e4 = collect(suite)
    thr = {}
    for t in TARGETS:
        neg = negatives(e4, t)
        thr[t] = {"C1": M.threshold_at_fpr([r["res"]["C1"]["score"] for r in neg], 0.05),
                  "fused": M.threshold_at_fpr([r["res"]["C1+C2+C3"]["score"] for r in neg], 0.05)}
    keys = [("T0", None, None), ("T1", None, None)] + [("T3a", sg, nm) for nm in ("same", "independent") for sg in SIG] + \
           [("T4", None, "same")]
    table = []
    for tier, sg, nm in keys:
        for t in TARGETS + ("all",):
            atts = [(r["target"], a) for r in rows if t in ("all", r["target"]) for a in r["attacks"]
                    if a["tier"] == tier and a["sigma"] == sg and a["normals"] == nm]
            if not atts:
                continue
            e = dict(tier=tier, sigma_att=sg, normals=nm, target=t, label=_label(tier, sg, nm), n=len(atts))
            for v in VARS:
                e[f"tpr_tau_{v}"] = float(np.mean([a["res"][v]["verdict"] == "SUSPICIOUS" for _, a in atts]))
                e[f"tpr_fpr5_{v}"] = float(np.mean([a["res"][v]["score"] > thr[tg][v] for tg, a in atts]))
                e[f"loc_tau_{v}"] = float(np.mean([a["res"][v]["verdict"] == "SUSPICIOUS" and bool(a["res"][v]["flag_correct"])
                                                   for _, a in atts]))
            fid = [a["fidelity"] for _, a in atts if a["fidelity"]]
            e["mean_abs_dY"] = float(np.mean([f["mean_abs_dY"] for f in fid])) if fid else None
            e["ssim_loss"] = float(np.mean([f["ssim_loss"] for f in fid])) if fid else None
            le = [a["l_err"] for _, a in atts if a["l_err"] is not None]
            e["mean_attacker_light_err"] = float(np.mean(le)) if le else None
            e["defence_recovery_tau"] = e["tpr_tau_fused"] - e["tpr_tau_C1"]
            table.append(e)
    # detection vs the attacker's actual light error (T3a, same normals, all targets)
    pts = [(a["l_err"], a["res"]["C1"]["verdict"] == "SUSPICIOUS", a["res"]["fused"]["verdict"] == "SUSPICIOUS")
           for r in rows for a in r["attacks"] if a["tier"] == "T3a" and a["normals"] == "same"]
    edges = [0, 5, 10, 20, 30, 45, 90, 180]
    bins = []
    for lo, hi in zip(edges[:-1], edges[1:]):
        b = [p for p in pts if lo <= p[0] < hi]
        bins.append(dict(lo=lo, hi=hi, n=len(b), tpr_C1=float(np.mean([p[1] for p in b])) if b else None,
                         tpr_fused=float(np.mean([p[2] for p in b])) if b else None))
    e4j = C.load_json("e04_mdi.json")
    mdi = None
    if e4j and e4j.get("suite") == suite:
        mdi = {t: {v: e4j["targets"][t]["curves"][v]["mdi_tau"] for v in ("C1", "C1+C2+C3")} for t in TARGETS}
    out = C.header("E9", suite, n_scenes_per_target=n, delta_range=[90, 135], targets=list(TARGETS),
                   n_composites={t: sum(r["target"] == t for r in rows) for t in TARGETS},
                   thresholds_fpr5_from_test_pristine=thr, table=table, light_error_bins=bins, mdi_tau_from_e4=mdi,
                   caveat_attack="the defender's simulated normals are independent of the edit (best case for the "
                                 "attacker); an attacked region that becomes not assessable counts as passing.")
    C.write_json("e09_attacks.json", out)
    C.write_csv("e09_attacks.csv", table)
    summ = dict(caveat="Synthetic scenes, simulated normals that do not react to the edit (best case for the attacker); "
                       f"detection = SUSPICIOUS at the calibrated tau; pooled over car, distractor and dent targets "
                       f"(delta 90-135 deg); suite '{suite}'.",
                suite=suite,
                rows=[dict(tier=e["tier"], label=e["label"], tpr_c1=e["tpr_tau_C1"], tpr_fused=e["tpr_tau_fused"], n=e["n"],
                           mean_abs_dY=e["mean_abs_dY"]) for e in table if e["target"] == "all"])
    C.write_json("attack_summary.json", summ)
    return out
