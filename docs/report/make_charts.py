"""Charts for the project report, from the saved result files (no recomputation).

    python docs/report/make_charts.py      -> docs/report/figs/*.svg
"""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
R = ROOT / "data" / "results"
OUT = Path(__file__).resolve().parent / "figs"
OUT.mkdir(exist_ok=True)
INK, MUTED, GRID = "#1d2430", "#5b6472", "#e3e6ea"
AMBER, BLUE, RED, GREEN, VIOLET = "#d9861c", "#2563c9", "#c8413b", "#2f8f4e", "#6b52c8"
plt.rcParams.update({"font.family": "Segoe UI", "font.size": 10, "axes.edgecolor": GRID, "axes.labelcolor": MUTED,
                     "xtick.color": MUTED, "ytick.color": MUTED, "axes.spines.top": False, "axes.spines.right": False,
                     "svg.fonttype": "none"})


def bars(name, cats, vals, colors, ylabel, title, fmt="{:.0f}%", ymax=None, note=None, size=(5.6, 3.0)):
    fig, ax = plt.subplots(figsize=size)
    b = ax.bar(cats, vals, color=colors, width=0.6)
    for r, v in zip(b, vals):
        ax.text(r.get_x() + r.get_width() / 2, v + (ymax or max(vals)) * 0.02, fmt.format(v), ha="center", va="bottom",
                color=INK, fontsize=10, fontweight="bold")
    ax.set_ylabel(ylabel)
    ax.set_ylim(0, ymax or max(vals) * 1.2)
    ax.yaxis.grid(True, color=GRID)
    ax.set_axisbelow(True)
    ax.set_title(title, loc="left", color=INK, fontsize=11)
    if note:
        fig.text(0.01, -0.02, note, color=MUTED, fontsize=8)
    fig.tight_layout()
    fig.savefig(OUT / f"{name}.svg", bbox_inches="tight")
    plt.close(fig)


# real marked-area check by light angle (held-out objects, 10% level; eval/mit_panel.py, pair T+Tr)
panel = json.loads((R / "real_panel.json").read_text())
lv = panel["pair_T_Tr"]["0.1"]
cats = list(lv["by_angle"].keys())
bars("real_by_angle", [c.replace("-181", "+").replace("-", "–") + "°" for c in cats],
     [100 * lv["by_angle"][c]["detected"] for c in cats], ["#b9a27a", "#d0a05a", "#e09a3c", AMBER],
     "pasted areas caught (%)", "Real objects: caught vs light-angle difference", ymax=75,
     note=f"Held-out objects, {lv['n_splice']} pasted / {lv['n_clean']} clean; false alarms {100 * lv['false_alarms']:.1f}%.")

# stress test (eval/seam_robust.py; T+Tr at the three-statistic thresholds)
rob = json.loads((R / "seam_robust.json").read_text())["variants"]
bars("stress", ["Plain paste", "8 px feather", "Poisson blend"],
     [100 * rob[v]["T+Tr"]["detected"] for v in ("base", "feather8", "poisson")], [AMBER, "#b38a4a", RED],
     "pasted areas caught (%)", "How a careful forger lowers detection", fmt="{:.1f}%", ymax=50)

# colour matching, matched false alarms (eval/panel_compare.py attack): T+Tr at 5% and 10%
att = json.loads((R / "panel_compare_attack.json").read_text())
pl = json.loads((R / "panel_compare.json").read_text())
fig, ax = plt.subplots(figsize=(5.6, 3.0))
x = [0, 1]
for k, (src, lab, col) in enumerate([(pl, "plain paste", AMBER), (att, "colour-matched paste", BLUE)]):
    v = [100 * src[f]["T+Tr"]["det"] for f in ("0.05", "0.1")]
    lo = [100 * src[f]["T+Tr"]["lo"] for f in ("0.05", "0.1")]
    hi = [100 * src[f]["T+Tr"]["hi"] for f in ("0.05", "0.1")]
    xs = [i + (k - 0.5) * 0.32 for i in x]
    ax.bar(xs, v, width=0.3, color=col, label=lab)
    ax.errorbar(xs, v, yerr=[[a - b for a, b in zip(v, lo)], [b - a for a, b in zip(v, hi)]], fmt="none", ecolor=INK, capsize=3, lw=1)
ax.set_xticks(x, ["5% false alarms", "10% false alarms"])
ax.set_ylabel("pasted areas caught (%)")
ax.set_ylim(0, 75)
ax.yaxis.grid(True, color=GRID)
ax.set_axisbelow(True)
ax.legend(frameon=False, fontsize=9)
ax.set_title("Colour matching costs detection (90% intervals)", loc="left", color=INK, fontsize=11)
fig.tight_layout()
fig.savefig(OUT / "colour_match.svg", bbox_inches="tight")
plt.close(fig)

# learned intrinsic decomposition vs guarded Retinex (eval/intrinsic_compare.py), if available
f = R / "intrinsic_bench.json"
if f.exists():
    ib = json.loads(f.read_text())
    kinds = [k for k in ("splice", "harmonised", "feather8", "poisson") if k in ib]
    labels = {"splice": "plain", "harmonised": "colour-matched", "feather8": "8 px feather", "poisson": "Poisson"}
    fig, ax = plt.subplots(figsize=(6.2, 3.1))
    for k, (key, col) in enumerate([("Retinex (T+Tr)", AMBER), ("learned (T+Tr)", VIOLET)]):
        v = [100 * ib[kd]["learned"]["0.05"][key]["det"] for kd in kinds]
        xs = [i + (k - 0.5) * 0.36 for i in range(len(kinds))]
        ax.bar(xs, v, width=0.34, color=col, label=key.replace(" (T+Tr)", ""))
        for xx, vv in zip(xs, v):
            ax.text(xx, vv + 1.2, f"{vv:.0f}", ha="center", fontsize=8.5, color=INK)
    ax.set_xticks(range(len(kinds)), [labels[k] for k in kinds])
    ax.set_ylabel("caught at 5% false alarms (%)")
    ax.set_ylim(0, 65)
    ax.yaxis.grid(True, color=GRID)
    ax.set_axisbelow(True)
    ax.legend(frameon=False, fontsize=9)
    ax.set_title("Guarded Retinex vs learned intrinsic decomposition", loc="left", color=INK, fontsize=11)
    fig.tight_layout()
    fig.savefig(OUT / "intrinsic.svg", bbox_inches="tight")
    plt.close(fig)

# shadow-consistency sweep (eval/shadow_bench.py, rendered geometry)
sh = json.loads((R / "shadow_bench.json").read_text())[0]
cats = list(sh["bins"].keys())
bars("shadow", [c.replace("-", "–") + "°" for c in cats], [100 * sh["bins"][c]["detected"] for c in cats],
     ["#9aa8c8", "#7a8fc0", BLUE, "#1d4ea0"], "second-sun objects caught (%)", "Cast-shadow consistency (synthetic geometry)",
     ymax=110, note=f"5 object–shadow pairs per scene, 1 px marking noise; clean false alarms {100 * sh['false_alarms']:.0f}% (60 scenes).")
print(sorted(p.name for p in OUT.iterdir()))
