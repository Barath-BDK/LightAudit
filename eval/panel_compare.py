"""Matched-false-alarm comparison of panel statistic sets on held-out real objects (review finding 7 of
docs/designs/seam_test.md). For each set the Bonferroni level is swept; detection is interpolated at fixed held-out
false-alarm rates, with a 90% interval from resampling the held-out objects. Even-index objects calibrate.

    python eval/panel_compare.py            # plain splices (rows of eval/mit_panel.py)
    python eval/panel_compare.py attack     # colour-matched splices (rows of eval/mit_attack.py)
"""
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from lightaudit.calibrate import conformal_quantile  # noqa: E402

FA = (0.025, 0.05, 0.075, 0.10)
ALPHAS = np.linspace(0.005, 0.4, 80)


def compare(rows, sets: dict, pos: str, base: str, new: str, n_boot: int = 1000, verbose: bool = True) -> dict:
    """rows: dicts with obj, kind ('clean' or pos) and the statistics. sets: name -> keys. Returns, per false-alarm
    rate, detection (with 90% interval) of every set and the gain of set `new` over set `base`."""
    objs = sorted({r["obj"] for r in rows})
    cal_o, test_o = objs[0::2], objs[1::2]
    cal = [r for r in rows if r["obj"] in cal_o and r["kind"] == "clean"]
    test = [r for r in rows if r["obj"] in test_o]

    def curve(keys, sel):
        pts = []
        for a in ALPHAS:
            tau = {k: conformal_quantile([r[k] for r in cal if r.get(k) is not None], a / len(keys)) for k in keys}
            hit = lambda r: any(r.get(k) is not None and r[k] > tau[k] for k in keys)  # noqa: E731
            pts.append((np.mean([hit(r) for r in sel if r["kind"] == "clean"]), np.mean([hit(r) for r in sel if r["kind"] == pos])))
        f, d = np.array(pts).T
        o = np.argsort(f, kind="stable")
        return np.interp(FA, f[o], d[o])

    rng = np.random.default_rng(0)
    by_obj = {o: [r for r in test if r["obj"] == o] for o in test_o}
    point = {n: curve(k, test) for n, k in sets.items()}
    boot = {n: [] for n in sets}
    for _ in range(n_boot):
        sel = [r for o in rng.choice(test_o, len(test_o)) for r in by_obj[o]]
        for n, k in sets.items():
            boot[n].append(curve(k, sel))
    diff = np.array(boot[new]) - np.array(boot[base])
    out = {}
    for i, fa in enumerate(FA):
        line = {n: dict(det=float(point[n][i]), lo=float(np.percentile(np.array(boot[n])[:, i], 5)),
                        hi=float(np.percentile(np.array(boot[n])[:, i], 95))) for n in sets}
        g = dict(mean=float(point[new][i] - point[base][i]), lo=float(np.percentile(diff[:, i], 5)), hi=float(np.percentile(diff[:, i], 95)))
        line[f"gain_{new}_vs_{base}"] = g
        out[str(fa)] = line
        if verbose:
            print(f"held-out FA {fa:.3f}: " + "  ".join(f"{n} {line[n]['det']:.3f} [{line[n]['lo']:.2f}, {line[n]['hi']:.2f}]" for n in sets)
                  + f"  | gain {g['mean']:+.3f} [{g['lo']:+.3f}, {g['hi']:+.3f}]", flush=True)
    return out


if __name__ == "__main__":
    attack = "attack" in sys.argv
    rows = json.loads((ROOT / "data" / "results" / ("real_panel_attack_rows.json" if attack else "real_panel_rows.json")).read_text())
    t = "Tsr" if attack else "T"  # mit_attack's Tsr is mit_panel's T (shape only, Retinex)
    sets = {"T+Tr": (t, "Tr"), "T+Tr+S": (t, "Tr", "S"), "S": ("S",)}
    out = compare(rows, sets, "harmonised" if attack else "splice", "T+Tr", "T+Tr+S", n_boot=100 if "--quick" in sys.argv else 1000)
    (ROOT / "data" / "results" / ("panel_compare_attack.json" if attack else "panel_compare.json")).write_text(json.dumps(out, indent=1))
