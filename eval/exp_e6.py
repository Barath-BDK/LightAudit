"""E6 - abstention and hard conditions.

Conditions: overcast, multi (two suns), lowres, plus `normal` as the reference. Per condition: pristine scenes
(test seeds 3150+) and spliced scenes (car pasted at delta = 90 deg, test seeds 3000+), noisy_gt(8), all cues.
Reports the verdict distribution, accuracy among decided images (decided = CONSISTENT or SUSPICIOUS; correct =
pristine -> CONSISTENT, spliced -> SUSPICIOUS), false-alarm rate on decided pristine images, and a risk-coverage
curve obtained by sweeping w_min and tau (tau as multiples of the calibrated tau_img).
"""
from __future__ import annotations

from dataclasses import replace

import numpy as np

from . import common as C
from . import metrics as M

CONDITIONS = ("normal", "overcast", "multi", "lowres")
WMINS = (0.25, 0.35, 0.5, 0.65)
TAU_MULT = (0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 3.0, 5.0)
VERDICTS = ("CONSISTENT", "SUSPICIOUS", "INSUFFICIENT", "CONFLICT")


def _job(args):
    kind, seed, spliced = args
    from lightaudit.config import calibrated
    cfg = calibrated()
    rec = C.composite(seed, kind, "car", 90) if spliced else C.pristine(seed, kind)
    out = dict(kind=kind, seed=seed, spliced=spliced, verdict={}, missing=rec is None)
    if rec is None:
        return out
    for wm in WMINS:
        for tm in TAU_MULT:
            c = replace(cfg, w_min=wm, tau_img=cfg.tau_img * tm)
            f, regs = C.refuse(rec, c)
            out["verdict"][(wm, tm)] = f["verdict"]
    return out


def run(suite: str) -> dict:
    from lightaudit.config import calibrated
    C.require_calibration()
    n = C.suite_n(suite, 50)
    jobs = [(k, s, False) for k in CONDITIONS for s in C.test_seeds("prist", n)] + \
           [(k, s, True) for k in CONDITIONS for s in C.test_seeds("comp", n)]
    rows = [r for r in C.pmap(_job, jobs, "E6") if not r["missing"]]
    op = (calibrated().w_min, 1.0)
    dist, table = {}, []
    for k in CONDITIONS:
        dist[k] = {}
        for sp in (False, True):
            rs = [r for r in rows if r["kind"] == k and r["spliced"] == sp]
            vs = [r["verdict"][op] for r in rs]
            fr = {v: float(np.mean([x == v for x in vs])) if vs else None for v in VERDICTS}
            dec = [x for x in vs if x in ("CONSISTENT", "SUSPICIOUS")]
            want = "SUSPICIOUS" if sp else "CONSISTENT"
            acc = M.bootstrap_ci(lambda g: float(np.mean([x == want for x in g if x in ("CONSISTENT", "SUSPICIOUS")]))
                                 if any(x in ("CONSISTENT", "SUSPICIOUS") for x in g) else np.nan, vs, n_boot=1000, seed=3)
            key = "spliced" if sp else "pristine"
            dist[k][key] = dict(n=len(vs), fractions=fr, decided=len(dec), coverage=len(dec) / max(len(vs), 1),
                                accuracy_decided=acc[0], accuracy_decided_ci=[acc[1], acc[2]],
                                false_alarm_decided=(float(np.mean([x == "SUSPICIOUS" for x in dec])) if (dec and not sp) else None))
            table.append(dict(condition=k, set=key, n=len(vs), **{v: fr[v] for v in VERDICTS},
                              accuracy_decided=acc[0], acc_lo=acc[1], acc_hi=acc[2]))
    # risk-coverage over all conditions pooled (and per condition)
    rc = []
    for wm in WMINS:
        for tm in TAU_MULT:
            entry = dict(w_min=wm, tau_mult=tm, tau=calibrated().tau_img * tm)
            for k in CONDITIONS + ("all",):
                rs = [r for r in rows if k == "all" or r["kind"] == k]
                dec = [r for r in rs if r["verdict"][(wm, tm)] in ("CONSISTENT", "SUSPICIOUS")]
                err = [(r["verdict"][(wm, tm)] == "SUSPICIOUS") != r["spliced"] for r in dec]
                entry[k] = dict(coverage=len(dec) / max(len(rs), 1), risk=float(np.mean(err)) if err else None, n=len(rs))
            rc.append(entry)
    out = C.header("E6", suite, conditions=list(CONDITIONS), n_per_set=n, splice="car pasted at delta = 90 deg",
                   operating_point=dict(w_min=op[0], tau=calibrated().tau_img), verdict_distribution=dist,
                   risk_coverage=rc, w_min_grid=list(WMINS), tau_mult_grid=list(TAU_MULT),
                   pristine_seeds=[C.test_seeds("prist", n)[0], C.test_seeds("prist", n)[-1]],
                   spliced_seeds=[C.test_seeds("comp", n)[0], C.test_seeds("comp", n)[-1]])
    C.write_json("e06_abstention.json", out)
    C.write_csv("e06_verdicts.csv", table)
    return out
