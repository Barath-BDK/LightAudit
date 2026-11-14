"""Tables T1-T6 as CSV + Markdown in data/results/tables/ (from the result JSONs only)."""
from __future__ import annotations

import csv
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from eval.common import CAVEAT, TABLES, load_json  # noqa: E402


def _f(v, k=2):
    return "n/a" if v is None else (f"{v:.{k}f}" if isinstance(v, float) else str(v))


def _ci(p, ci, k=2):
    if p is None:
        return "n/a"
    return f"{p:.{k}f} [{ci[0]:.{k}f}, {ci[1]:.{k}f}]" if ci and ci[0] is not None and ci[1] is not None else f"{p:.{k}f}"


def _write(name, title, head, rows, note):
    TABLES.mkdir(parents=True, exist_ok=True)
    with open(TABLES / f"{name}.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(head)
        w.writerows(rows)
    md = [f"### {title}", "", "| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    md += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    md += ["", note + f" Caveat: {CAVEAT}.", ""]
    (TABLES / f"{name}.md").write_text("\n".join(md), encoding="utf-8")
    print("  wrote", name)


def main():
    d = load_json("e01_tone_curves.json")
    if d:
        rows = [[t, _ci(s["rank"]["median"], s["rank"]["median_ci"], 1), _ci(s["ls"]["median"], s["ls"]["median_ci"], 1),
                 _f(s["ls_lstsq"]["median"], 1), s["rank"]["n_regions"]] for t, s in d["summary"].items()]
        _write("T1_tone_curves", "T1 - E1 median light error (deg) by tone curve", ["tone curve", "C1 rank", "LS landscape",
               "LS closed form", "n regions"], rows, f"Suite {d['suite']}, {d['n_scenes']} scenes, exact normals, 95% bootstrap CI over scenes.")
    d = load_json("e03_calibration.json")
    if d:
        rows = [[t, d[t]["h"], d[t]["T"], _ci(d[t]["coverage"]["0.68"]["coverage"], d[t]["coverage"]["0.68"]["ci"]),
                 _ci(d[t]["coverage"]["0.95"]["coverage"], d[t]["coverage"]["0.95"]["ci"]), _f(d[t]["mean_r68"], 1)]
                for t in ("before", "after")]
        _write("T2_calibration", "T2 - E3 coverage on the test split", ["", "h", "T", "cov68", "cov95", "mean r68 (deg)"], rows,
               f"Suite {d['suite']}, n = {d['n_regions']} reliable regions / {d['n_scenes']} scenes.")
    d4, d5 = load_json("e04_mdi.json"), load_json("e05_roc.json")
    if d4:
        rows = []
        for t, r in d4["targets"].items():
            for v, c in r["curves"].items():
                if v == "fused":
                    continue
                i90 = c["deltas"].index(90) if 90 in c["deltas"] else None
                a = d5["targets"][t].get(v) if d5 else None
                rows.append([t, v, _f(c["mdi_fpr5"], 0), _f(c["mdi_tau"], 0),
                             _ci(c["tpr5"][i90], c["tpr5_ci"][i90]) if i90 is not None else "n/a",
                             _f(c["fpr_at_tau"]), _ci(a["auc"], a["auc_ci"]) if a else "n/a",
                             _f(a["top1_all"]) if a else "n/a", f"{c['n_pos'][0] if c['n_pos'] else 0}/{c['n_neg']}"])
        _write("T3_detection", "T3 - E4/E5 detection by target and cue set", ["target", "cues", "MDI@5%FPR (deg)", "MDI@tau (deg)",
               "TPR@5%FPR d=90", "FPR@tau", "AUC d>=30", "top-1 loc.", "n pos per delta / n neg"], rows,
               f"Suite {d4['suite']}. 5%FPR threshold from the pristine TEST scores (labelled as such); tau = calibrated. {d4['fused_note']}")
    d = load_json("e06_abstention.json")
    if d:
        rows = []
        for k, v in d["verdict_distribution"].items():
            for s, e in v.items():
                fr = e["fractions"]
                rows.append([k, s, e["n"]] + [_f(fr[x]) for x in ("CONSISTENT", "SUSPICIOUS", "INSUFFICIENT", "CONFLICT")] +
                            [_ci(e["accuracy_decided"], e["accuracy_decided_ci"])])
        _write("T4_verdicts_by_condition", "T4 - E6 verdict distribution by condition", ["condition", "set", "n", "CONSISTENT",
               "SUSPICIOUS", "INSUFFICIENT", "CONFLICT", "accuracy (decided)"], rows, f"Suite {d['suite']}. Spliced = car at 90 deg.")
    d = load_json("e08_ablations.json")
    if d:
        rows = [[r["ablation"], _ci(r.get("auc"), r.get("auc_ci")), _ci(r.get("tpr5_d90"), r.get("tpr5_d90_ci")),
                 _f(r.get("mdi_fpr5"), 0), _f(r.get("abstain_pristine")), _f(r.get("abstain_comp"))]
                for r in d["table"] if r.get("available")]
        rows += [[f"region backend {k}", _f(s["auc"]), f"TPR@tau {s['tpr_tau']:.2f}, FPR@tau {s['fpr_tau']:.2f}", "-",
                  _f(s["abstain_pristine"]), _f(s["abstain_comp"])] for k, s in d["region_backend"].items()]
        _write("T5_ablations", "T5 - E8 ablations (car target)", ["ablation", "AUC d>=30", "TPR@5%FPR d=90", "MDI (deg)",
               "abstain pristine", "abstain composites"], rows, f"Suite {d['suite']}; region-backend rows on {d['n_seg_scenes']}+{d['n_seg_scenes']} scenes.")
    d = load_json("e09_attacks.json")
    if d:
        rows = [[e["label"], e["target"], e["n"], _f(e["tpr_tau_C1"]), _f(e["tpr_tau_fused"]), _f(e["defence_recovery_tau"]),
                 _f(e["tpr_fpr5_fused"]), _f(e["mean_abs_dY"], 3), _f(e["ssim_loss"], 3)] for e in d["table"]]
        _write("T6_attacks", "T6 - E9 attacks", ["tier", "target", "n", "TPR@tau C1", "TPR@tau all cues", "defence recovery",
               "TPR@5%FPR all cues", "mean |dY|", "1-SSIM"], rows, f"Suite {d['suite']}. {d['caveat_attack']}")


if __name__ == "__main__":
    main()
