"""Figures F1-F9, the qualitative gallery and per-bundle light maps (BUILD_SPEC 14.3, 14.4).
Reads only data/results/*.json|csv and bundles/; every title is generated from the numbers it shows."""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from eval.common import CAVEAT, FIGS, RESULTS, load_json  # noqa: E402

PAL = {"C1": "#4c78a8", "C1+C2": "#f58518", "C1+C2+C3": "#54a24b", "fused": "#54a24b", "LS": "#e45756",
       "rank": "#4c78a8", "ls": "#e45756", "ls_lstsq": "#9d755d", "arbiter": "#b279a2", "grey": "#888888"}
plt.rcParams.update({"font.size": 10, "axes.titlesize": 11, "axes.labelsize": 10, "legend.fontsize": 9,
                     "xtick.labelsize": 9, "ytick.labelsize": 9, "axes.spines.top": False, "axes.spines.right": False})


def _save(fig, name, caption):
    FIGS.mkdir(parents=True, exist_ok=True)
    fig.text(0.01, 0.005, caption, fontsize=8.5, color="#444", ha="left", va="bottom", wrap=True)
    fig.savefig(FIGS / f"{name}.png", dpi=200)
    fig.savefig(FIGS / f"{name}.svg")
    plt.close(fig)
    print("  wrote", name)


def _cap(d, extra=""):
    return f"Suite: {d.get('suite')}. {extra} Caveat: {CAVEAT}."


def f1():
    d = load_json("e01_tone_curves.json")
    p = RESULTS / "e01_rows.csv"
    if not d or not p.exists():
        return
    rows = [r for r in csv.DictReader(open(p)) if r.get("err_rank") and float(r["n_valid"]) >= 150
            and float(r.get("spread_deg") or 0) >= 10]
    tones = d["tones"]
    fig, ax = plt.subplots(figsize=(8, 4.4))
    for k, (m, off) in enumerate((("rank", -0.2), ("ls", 0.2))):
        data = [[float(r[f"err_{m}"]) for r in rows if r["tone"] == t] for t in tones]
        bp = ax.boxplot(data, positions=np.arange(len(tones)) + off, widths=0.35, patch_artist=True, showfliers=False)
        for b in bp["boxes"]:
            b.set(facecolor=PAL[m], alpha=0.6)
        ax.plot([], [], color=PAL[m], lw=8, alpha=0.6, label={"rank": "C1 rank", "ls": "LS baseline"}[m])
    ax.set_xticks(range(len(tones)), tones)
    ax.set_xlabel("tone curve of the camera pipeline")
    ax.set_ylabel("light direction error (deg)")
    s = d["summary"]
    mr = [s[t]["rank"]["median"] for t in tones]
    ml = [s[t]["ls"]["median"] for t in tones]
    ax.set_title(f"Median error: rank {min(mr):.1f}-{max(mr):.1f} deg, LS {min(ml):.1f}-{max(ml):.1f} deg across tone curves")
    ax.legend()
    n = s[tones[0]]["rank"]["n_regions"]
    fig.subplots_adjust(bottom=0.2)
    _save(fig, "F1_tone_curves", _cap(d, f"n = {n} regions from {d['n_scenes']} scenes per curve, exact normals; boxes = IQR, whiskers 1.5 IQR."))


def f2():
    d = load_json("e02_normal_noise.json")
    if not d:
        return
    sg = d["sigmas"]
    fig, axs = plt.subplots(1, 3, figsize=(12, 4))
    for sub, ls in (("all", "-"), ("reliable", "--")):
        m = [d["by_sigma"][str(s)][sub]["median_err"] for s in sg]
        lo = [d["by_sigma"][str(s)][sub]["median_err_ci"][0] for s in sg]
        hi = [d["by_sigma"][str(s)][sub]["median_err_ci"][1] for s in sg]
        axs[0].errorbar(sg, m, yerr=[np.subtract(m, lo), np.subtract(hi, m)], ls=ls, marker="o", color=PAL["rank"],
                        capsize=3, label=f"{sub} regions")
        axs[0].plot(sg, [d["by_sigma"][str(s)][sub]["median_r68"] for s in sg], ls=ls, marker="s", color=PAL["grey"],
                    label=f"median r68 ({sub})")
    axs[0].set_xlabel("simulated normal noise sigma (deg)")
    axs[0].set_ylabel("deg")
    axs[0].legend(fontsize=8)
    for ax, key, xl in ((axs[1], "size_bins_sigma8", "valid pixels per region"), (axs[2], "spread_bins_sigma8", "normal spread (deg)")):
        b = [x for x in d[key] if x["median"] is not None]
        ax.bar(range(len(b)), [x["median"] for x in b], color=PAL["rank"], alpha=0.7)
        ax.set_xticks(range(len(b)), [f"{x['lo']:g}-{x['hi']:g}".replace("-1e+09", "+") + f"\nn={x['n']}" for x in b], fontsize=8)
        ax.set_xlabel(xl + " (sigma = 8)")
        ax.set_ylabel("median error (deg)")
    a, b = d["by_sigma"][str(sg[0])]["all"]["median_err"], d["by_sigma"][str(sg[-1])]["all"]["median_err"]
    fig.suptitle(f"Median region error {a:.1f} deg at sigma={sg[0]} vs {b:.1f} deg at sigma={sg[-1]}")
    rho = d.get("spearman_unc_err_pooled") or {}
    fig.subplots_adjust(bottom=0.25, wspace=0.3)
    _save(fig, "F2_normal_noise", _cap(d, f"{d['n_scenes']} pristine scenes; n per sigma = {d['by_sigma'][str(sg[0])]['all']['n_regions']} regions; "
                                         f"Spearman(mean unc, error) = {rho.get('rho', float('nan')):.2f} (pooled). Error bars: bootstrap 95% CI."))


def f3():
    d = load_json("e03_calibration.json")
    if not d:
        return
    lv = d["levels"]
    fig, ax = plt.subplots(figsize=(5.5, 5))
    ax.plot([0, 1], [0, 1], color=PAL["grey"], ls=":", label="ideal")
    for tag, c in (("before", PAL["LS"]), ("after", PAL["rank"])):
        cv = [d[tag]["coverage"][str(q)]["coverage"] for q in lv]
        ax.plot(lv, cv, marker="o", color=c, label=f"{tag}: h={d[tag]['h']:g}, T={d[tag]['T']:g}, mean r68={d[tag]['mean_r68']:.0f} deg")
    ax.set_xlabel("nominal credible level")
    ax.set_ylabel("empirical coverage of the GT light")
    a, b = d["after"]["coverage"]["0.68"]["coverage"], d["after"]["coverage"]["0.95"]["coverage"]
    ax.set_title(f"Test coverage after calibration: 68% -> {a:.2f}, 95% -> {b:.2f}")
    ax.legend(fontsize=8, loc="upper left")
    fig.subplots_adjust(bottom=0.18)
    _save(fig, "F3_calibration", _cap(d, f"n = {d['n_regions']} reliable regions from {d['n_scenes']} test scenes."))


def f4():
    d = load_json("e04_mdi.json")
    if not d:
        return
    tg = list(d["targets"])
    fig, axs = plt.subplots(1, len(tg), figsize=(4.3 * len(tg), 4.2), sharey=True)
    parts = []
    for ax, t in zip(np.atleast_1d(axs), tg):
        for v, c in d["targets"][t]["curves"].items():
            if v == "fused" or not c["deltas"]:
                continue
            lo = [x[0] for x in c["tpr5_ci"]]
            hi = [x[1] for x in c["tpr5_ci"]]
            ax.plot(c["deltas"], c["tpr5"], marker="o", color=PAL[v], label=f"{v} (MDI {c['mdi_fpr5'] if c['mdi_fpr5'] is not None else '>180'})")
            ax.fill_between(c["deltas"], lo, hi, color=PAL[v], alpha=0.12)
            ax.plot(c["deltas"], c["tpr_tau"], ls="--", color=PAL[v], alpha=0.7)
        ax.axhline(0.5, color=PAL["grey"], ls=":")
        ax.set_title(f"{t} (n = {d['targets'][t]['n_scenes']} scenes)")
        ax.set_xlabel("discrepancy delta (deg)")
        ax.legend(fontsize=8)
        m = d["targets"][t]["curves"]["C1+C2+C3"]["mdi_fpr5"]
        parts.append(f"{t} {m if m is not None else '>180'} deg")
    np.atleast_1d(axs)[0].set_ylabel("TPR")
    fig.suptitle("MDI at 5% FPR (all cues): " + ", ".join(parts))
    fig.subplots_adjust(bottom=0.22, top=0.86)
    _save(fig, "F4_mdi", _cap(d, f"Solid: TPR@FPR=5% (threshold from the pristine TEST scores, n = {d['n_pristine_scenes']}) with "
                                 "bootstrap 95% band; dashed: TPR at the calibrated tau. LS = LS landscape, shading only."))


def f5():
    d = load_json("e05_roc.json")
    if not d:
        return
    tg = list(d["targets"])
    fig, axs = plt.subplots(1, len(tg), figsize=(4.3 * len(tg), 4.3), sharey=True)
    parts = []
    for ax, t in zip(np.atleast_1d(axs), tg):
        for v, r in d["targets"][t].items():
            if v == "fused":
                continue
            ax.plot(r["roc_fpr"], r["roc_tpr"], color=PAL[v], label=f"{v} AUC {r['auc']:.2f}")
        ax.plot([0, 1], [0, 1], color=PAL["grey"], ls=":")
        r = d["targets"][t]["C1+C2+C3"]
        ax.set_title(f"{t} (n+ = {r['n_pos']}, n- = {r['n_neg']})")
        ax.set_xlabel("false-positive rate")
        ax.legend(fontsize=8, loc="lower right")
        parts.append(f"{t} {r['auc']:.2f}")
    np.atleast_1d(axs)[0].set_ylabel("true-positive rate")
    fig.suptitle("AUC (all cues, delta >= 30 deg): " + ", ".join(parts))
    fig.subplots_adjust(bottom=0.2, top=0.86)
    _save(fig, "F5_roc", _cap(d, "Abstentions count as not flagged."))


def f6():
    d = load_json("e06_abstention.json")
    if not d:
        return
    V = ("CONSISTENT", "SUSPICIOUS", "INSUFFICIENT", "CONFLICT")
    cols = {"CONSISTENT": "#54a24b", "SUSPICIOUS": "#e45756", "INSUFFICIENT": "#bab0ac", "CONFLICT": "#eeca3b"}
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(12, 4.5), gridspec_kw=dict(width_ratios=[1.4, 1]))
    labels, bottoms = [], None
    bars = []
    for k in d["conditions"]:
        for s in ("pristine", "spliced"):
            labels.append(f"{k}\n{s}\nn={d['verdict_distribution'][k][s]['n']}")
            bars.append(d["verdict_distribution"][k][s]["fractions"])
    bottoms = np.zeros(len(bars))
    for v in V:
        h = np.array([b[v] or 0 for b in bars])
        a1.bar(range(len(bars)), h, bottom=bottoms, color=cols[v], label=v)
        bottoms += h
    a1.set_xticks(range(len(bars)), labels, fontsize=8)
    a1.set_ylabel("fraction of images")
    a1.legend(fontsize=8, ncol=4, loc="upper center", bbox_to_anchor=(0.5, 1.12))
    for wm in d["w_min_grid"]:
        pts = [(e["all"]["coverage"], e["all"]["risk"]) for e in d["risk_coverage"] if e["w_min"] == wm and e["all"]["risk"] is not None]  # tau order
        if pts:
            a2.plot(*zip(*pts), marker="o", label=f"w_min = {wm}")
    a2.set_xlabel("coverage (fraction decided)")
    a2.set_ylabel("risk (error among decided)")
    a2.legend(fontsize=8)
    a2.set_title("risk-coverage, tau swept")
    ov = d["verdict_distribution"]["overcast"]["pristine"]["fractions"]["INSUFFICIENT"]
    mu = d["verdict_distribution"]["multi"]["pristine"]["fractions"]
    fig.suptitle(f"Pristine overcast: {ov:.0%} INSUFFICIENT; pristine multi-light: {mu['CONFLICT']:.0%} CONFLICT, {mu['SUSPICIOUS']:.0%} SUSPICIOUS")
    fig.subplots_adjust(bottom=0.25, top=0.82)
    _save(fig, "F6_abstention", _cap(d, "Spliced = car pasted at 90 deg. Pooled risk-coverage over all conditions."))


def f7():
    d = load_json("e07_robustness.json")
    if not d:
        return
    P = d["perturbations"]
    fig, axs = plt.subplots(1, 4, figsize=(14, 4), sharey=True)
    base = P["none:None"]
    for ax, kind, xl in zip(axs, ("jpeg", "resize", "noise", "tone"), ("JPEG quality", "resize factor", "noise sigma (8-bit/255)", "tone change")):
        ks = ["none:None"] + [k for k, v in P.items() if v["kind"] == kind]
        xs = ["none"] + [str(P[k]["param"]) for k in ks[1:]]
        for v, c in (("C1", PAL["C1"]), ("fused", PAL["fused"])):
            ax.plot(xs, [P[k][f"tpr_{v}"] for k in ks], marker="o", color=c, label=f"TPR {v}")
            ax.plot(xs, [P[k][f"fpr_{v}"] for k in ks], marker="x", ls="--", color=c, label=f"FPR {v}")
        ax.set_xlabel(xl)
        ax.tick_params(axis="x", labelsize=8)
    axs[0].set_ylabel("rate at calibrated tau")
    axs[0].legend(fontsize=8)
    worst = min(P, key=lambda k: P[k]["tpr_fused"])
    fig.suptitle(f"TPR (all cues) {base['tpr_fused']:.2f} unperturbed; lowest {P[worst]['tpr_fused']:.2f} at {worst}")
    fig.subplots_adjust(bottom=0.22, top=0.86)
    _save(fig, "F7_robustness", _cap(d, f"n = {d['n_pristine']} pristine + {d['n_spliced']} spliced (car, 90 deg); tau not re-fit."))


def f8():
    d = load_json("e09_attacks.json")
    if not d:
        return
    T = [e for e in d["table"] if e["target"] == "all" and (e["normals"] in (None, "same"))]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(13, 4.8), gridspec_kw=dict(width_ratios=[1.6, 1]))
    x = np.arange(len(T))
    a1.bar(x - 0.2, [e["tpr_tau_C1"] for e in T], 0.4, color=PAL["C1"], label="shading only (C1)")
    a1.bar(x + 0.2, [e["tpr_tau_fused"] for e in T], 0.4, color=PAL["fused"], label="all cues (C1+C2+C3)")
    a1.set_xticks(x, [e["label"].replace(" (", "\n(").replace("re-shade", "") for e in T], fontsize=8, rotation=0)
    a1.set_ylabel("detection rate at calibrated tau")
    a1.legend(fontsize=8)
    for e, xi in zip(T, x):
        a1.text(xi, -0.12, f"n={e['n']}", ha="center", fontsize=7, transform=a1.get_xaxis_transform())
    b = [x for x in d["light_error_bins"] if x["n"]]
    a2.plot([(x["lo"] + x["hi"]) / 2 for x in b], [x["tpr_C1"] for x in b], marker="o", color=PAL["C1"], label="C1")
    a2.plot([(x["lo"] + x["hi"]) / 2 for x in b], [x["tpr_fused"] for x in b], marker="o", color=PAL["fused"], label="all cues")
    m = (d.get("mdi_tau_from_e4") or {}).get("car", {}).get("C1")
    if m is not None:
        a2.axvline(m, color=PAL["grey"], ls=":", label=f"E4 MDI car C1 ({m} deg)")
    a2.set_xlabel("attacker's actual light error (deg, T3a)")
    a2.set_ylabel("detection rate")
    a2.legend(fontsize=8)
    t0 = T[0]
    t3 = next(e for e in T if e["tier"] == "T3a" and e["sigma_att"] == 0)
    fig.suptitle(f"Detection: T0 {t0['tpr_tau_fused']:.2f} -> T3a exact light {t3['tpr_tau_fused']:.2f} (all cues), {t3['tpr_tau_C1']:.2f} (shading only)")
    fig.subplots_adjust(bottom=0.26, top=0.86)
    _save(fig, "F8_attacks", _cap(d, "Pooled car/distractor/dent, delta 90-135 deg, attacker normals = defender's (white box). "
                                     "Defender normals do not react to the edit (best case for the attacker)."))


def f9():
    d = load_json("e08_ablations.json")
    if not d:
        return
    rows = [r for r in d["table"] if r.get("available")]
    imp = (d.get("arbiter") or {}).get("permutation_importance") or []
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(13, 4.8), gridspec_kw=dict(width_ratios=[1.7, 1]))
    a1.axis("off")
    f = lambda v, k=2: "n/a" if v is None else f"{v:.{k}f}"  # noqa: E731
    cell = [[r["ablation"], f(r["auc"]), f(r["tpr5_d90"]), "n/a" if r["mdi_fpr5"] is None else f"{r['mdi_fpr5']:g}",
             f(r["abstain_pristine"])] for r in rows]
    for be, s in d["region_backend"].items():
        cell.append([f"regions: {be} (n={s['n_pristine']}+{s['n_spliced']})", f(s["auc"]), "-", "-", f(s["abstain_pristine"])])
    tb = a1.table(cellText=cell, colLabels=["ablation", "AUC", "TPR@5% d=90", "MDI (deg)", "abstain"], loc="center",
                  colWidths=[0.5, 0.12, 0.15, 0.12, 0.11])
    tb.auto_set_font_size(False)
    tb.set_fontsize(8.5)
    tb.scale(1, 1.25)
    if imp:
        a2.barh([i["feature"] for i in imp][::-1], [i["mean"] for i in imp][::-1], xerr=[i["std"] for i in imp][::-1],
                color=PAL["arbiter"])
        a2.set_xlabel("permutation importance (drop in region AUC)")
        a2.set_title("arbiter features (held-out arb scenes)")
    best = max(rows, key=lambda r: r["auc"] or 0)
    fig.suptitle(f"Highest AUC: {best['ablation']} ({best['auc']:.2f})")
    fig.subplots_adjust(bottom=0.12, top=0.88, wspace=0.35)
    _save(fig, "F9_ablations", _cap(d, f"Car target. AUC: delta >= 30 vs pristine; n per row in e08_ablations.json."))


# --------------------------------------------------------------------------------------------- bundles
def _bundle(name):
    from PIL import Image
    from lightaudit.bundle import BUNDLES
    b = BUNDLES / name
    m = json.loads((b / "manifest.json").read_text())
    L = np.fromfile(b / "landscapes.bin", "<f4").reshape(len(m["regions"]), 64, 128)
    img = lambda f: np.asarray(Image.open(b / f)) if (b / f).exists() else None  # noqa: E731
    return m, L, img


def _lightmap(ax, m, L):
    from lightaudit.grid import az_el_deg, hpd
    az = -180 + (np.arange(128) + 0.5) * 360 / 128
    el = 90 - (np.arange(64) + 0.5) * 180 / 64
    for r in m["regions"]:
        if r["excluded"] or r.get("kind") == "pseudo":
            continue
        _, (m68, m95) = hpd(L[r["landscape_index"]].ravel())
        lw = 1.6 if r["reliable"] else 0.7
        ax.contour(az, el, m95.reshape(64, 128).astype(float), [0.5], colors=[r["color"]], linewidths=lw, linestyles="--")
        ax.contour(az, el, m68.reshape(64, 128).astype(float), [0.5], colors=[r["color"]], linewidths=lw)
    c = m["fusion"].get("consensus")
    if c:
        a, e = az_el_deg(c["dir"])
        ax.plot(a, e, "o", mfc="none", mec="k", ms=10, label="consensus")
    gt = m.get("ground_truth")
    if gt and gt.get("light_cam"):
        a, e = az_el_deg(gt["light_cam"])
        ax.plot(a, e, "*", color="gold", mec="k", ms=13, label="GT light")
    ax.set_xlim(-180, 180)
    ax.set_ylim(-90, 90)
    ax.set_xlabel("azimuth (deg)")
    ax.set_ylabel("elevation (deg)")


def lightmaps_and_gallery():
    from lightaudit.bundle import BUNDLES
    idx = BUNDLES / "index.json"
    if not idx.exists():
        return
    names = [e["name"] for e in json.loads(idx.read_text()) if (BUNDLES / e["name"] / "manifest.json").exists()]
    for n in names:
        m, L, _ = _bundle(n)
        fig, ax = plt.subplots(figsize=(7, 3.8))
        _lightmap(ax, m, L)
        ax.legend(fontsize=8, loc="lower right")
        ax.set_title(f"{m['title']}: {m['fusion']['verdict']}")
        fig.subplots_adjust(bottom=0.2)
        _save(fig, f"lightmap_{n}", "Solid = 68%, dashed = 95% sets per region (thin = unreliable). " + CAVEAT + ".")
    demos = [n for n in names if n.startswith("demo_")][:7]
    if not demos:
        return
    fig, axs = plt.subplots(len(demos), 6, figsize=(18, 2.6 * len(demos)))
    for row, n in zip(np.atleast_2d(axs), demos):
        m, L, img = _bundle(n)
        cols = {r["id"]: r["color"] for r in m["regions"]}
        lab = img("labels.png")
        from matplotlib.colors import to_rgb
        seg = np.zeros(lab.shape + (3,))
        for k, c in cols.items():
            seg[lab == k] = to_rgb(c)
        for ax, (im, t) in zip(row[:5], ((img("image.png"), "image"), (seg, "regions"), (img("normals.png"), "normals"),
                                          (None, "light map"), (img("heat.png"), "residual z"))):
            if t == "light map":
                _lightmap(ax, m, L)
                ax.set_xlabel("")
                ax.set_ylabel("")
                ax.tick_params(labelsize=7)
            else:
                if im is not None:
                    ax.imshow(im, cmap="inferno" if t == "residual z" else None)
                ax.axis("off")
            ax.set_title(t, fontsize=9)
        row[5].axis("off")
        txt = m["fusion"]["text"]
        row[5].text(0, 0.5, f"{m['title']}\n{m['fusion']['verdict']}  S_img={m['fusion']['S_img']:.2f}\n\n" +
                    "\n".join(txt[i:i + 48] for i in range(0, min(len(txt), 240), 48)), fontsize=8, va="center")
    fig.tight_layout(rect=(0, 0.02, 1, 1))
    _save(fig, "gallery", "Demo bundles. Light map: solid 68% / dashed 95% sets, circle = consensus, star = GT light. " + CAVEAT + ".")


def main():
    for fn in (f1, f2, f3, f4, f5, f6, f7, f8, f9, lightmaps_and_gallery):
        try:
            fn()
        except Exception as e:  # one broken result file must not stop the others
            import traceback
            traceback.print_exc()
            print(f"  {fn.__name__} skipped: {type(e).__name__}: {e}")
    e10 = load_json("e10_real_normals.json")
    if e10 and e10.get("status") != "ran":
        print("  E10 figure skipped:", e10.get("status"))


if __name__ == "__main__":
    main()
