"""Matched-false-alarm comparison of panel statistic sets on held-out real objects (review finding 7 of
docs/designs/seam_test.md). Reads data/results/real_panel_rows.json (written by eval/mit_panel.py). For each set the
Bonferroni level is swept; detection is interpolated at fixed held-out false-alarm rates, with a 90% interval from
resampling the held-out objects (1000 draws).

    python eval/panel_compare.py            # plain splices (rows of eval/mit_panel.py)
    python eval/panel_compare.py attack     # plain + colour-matched splices (rows of eval/mit_attack.py)
"""
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from lightaudit.calibrate import conformal_quantile  # noqa: E402

ATTACK = "attack" in sys.argv
rows = json.loads((ROOT / "data" / "results" / ("real_panel_attack_rows.json" if ATTACK else "real_panel_rows.json")).read_text())
POS = "harmonised" if ATTACK else "splice"  # mit_attack's Tsr is mit_panel's T (shape only, Retinex)
objs = sorted({r["obj"] for r in rows})
cal_o, test_o = objs[0::2], objs[1::2]
SETS = {"T+Tr": ("Tsr", "Tr") if ATTACK else ("T", "Tr"), "T+Tr+S": ("Tsr", "Tr", "S") if ATTACK else ("T", "Tr", "S"), "S": ("S",)}
FA = (0.025, 0.05, 0.075, 0.10)
ALPHAS = np.linspace(0.005, 0.4, 80)
cal = [r for r in rows if r["obj"] in cal_o and r["kind"] == "clean"]
test = [r for r in rows if r["obj"] in test_o]


def curve(keys, sel):
    pts = []
    for a in ALPHAS:
        tau = {k: conformal_quantile([r[k] for r in cal if r[k] is not None], a / len(keys)) for k in keys}
        hit = lambda r: any(r[k] is not None and r[k] > tau[k] for k in keys)  # noqa: E731
        c = [hit(r) for r in sel if r["kind"] == "clean"]
        s = [hit(r) for r in sel if r["kind"] == POS]
        pts.append((np.mean(c), np.mean(s)))
    f, d = np.array(pts).T
    o = np.argsort(f, kind="stable")
    return np.interp(FA, f[o], d[o])


rng = np.random.default_rng(0)
by_obj = {o: [r for r in test if r["obj"] == o] for o in test_o}
point = {n: curve(k, test) for n, k in SETS.items()}
boot = {n: [] for n in SETS}
for _ in range(1000 if "--quick" not in sys.argv else 100):
    sel = [r for o in rng.choice(test_o, len(test_o)) for r in by_obj[o]]
    for n, k in SETS.items():
        boot[n].append(curve(k, sel))
diff = np.array(boot["T+Tr+S"]) - np.array(boot["T+Tr"])
out = {}
for i, fa in enumerate(FA):
    line = {n: dict(det=float(point[n][i]), lo=float(np.percentile(np.array(boot[n])[:, i], 5)), hi=float(np.percentile(np.array(boot[n])[:, i], 95))) for n in SETS}
    line["gain_T+Tr+S_vs_T+Tr"] = dict(mean=float(point["T+Tr+S"][i] - point["T+Tr"][i]), lo=float(np.percentile(diff[:, i], 5)), hi=float(np.percentile(diff[:, i], 95)))
    out[str(fa)] = line
    print(f"held-out FA {fa:.3f}: " + "  ".join(f"{n} {v['det']:.3f} [{v['lo']:.2f}, {v['hi']:.2f}]" for n, v in line.items() if n in SETS)
          + f"  | gain {line['gain_T+Tr+S_vs_T+Tr']['mean']:+.3f} [{line['gain_T+Tr+S_vs_T+Tr']['lo']:+.3f}, {line['gain_T+Tr+S_vs_T+Tr']['hi']:+.3f}]")
(ROOT / "data" / "results" / ("panel_compare_attack.json" if ATTACK else "panel_compare.json")).write_text(json.dumps(out, indent=1))
