"""Self-contained HTML evidence report for one bundle (BUILD_SPEC 3.1 P1, `export_report`).

Everything (images, the light-map figure) is embedded as base64, so `report.html` can be e-mailed or printed.
The light map is an equirectangular plot (azimuth = atan2(x, z), elevation = asin(y), camera convention of
BUILD_SPEC 5.1) with each reliable region's 68% (solid) and 95% (dashed) highest-density sets computed from
`landscapes.bin`, the consensus marker and, for synthetic scenes, the ground-truth light as a star.
"""
from __future__ import annotations

import base64
import html
import io
import json
import re
from pathlib import Path

import numpy as np

from .grid import NA, NE, az_el_deg, hpd

LIMITATIONS = (
    "**What LightAudit can and cannot do.** LightAudit checks whether the lighting of different parts of a photo is "
    "physically consistent. It does **not** detect AI-generated images in general: a generator that produces the whole "
    "picture in one pass usually gives every object the same plausible light. A careful forger who re-lights an edited "
    "region to match the scene can pass the shading check (the attack lab measures exactly how much extra work that "
    "takes). Real photos can be flagged wrongly when they contain several lights, strong reflections, or bad "
    "surface-direction estimates, and many real photos (overcast, indoor, heavily filtered, tiny or flat objects) carry "
    "too little lighting evidence, in which case LightAudit says \"insufficient evidence\". Surface directions come from "
    "pretrained neural networks and are learned guesses, not measurements. The alert threshold controls the false-alarm "
    "rate only for photos like those used for calibration. **A flag means \"send for human review\", never \"this is "
    "fraud\".** Results on synthetic scenes do not automatically transfer to real photos; real-photo results are "
    "qualitative unless stated."
)

VERDICT_STYLE = {
    "CONSISTENT": ("#1b7f3b", "Consistent lighting", "Normal processing."),
    "SUSPICIOUS": ("#b3261e", "Suspicious region(s)", "Send for human review with this evidence."),
    "INSUFFICIENT": ("#8a6d00", "Insufficient evidence", "Not enough usable lighting cues: request a better photo."),
    "CONFLICT": ("#6b3fa0", "Reference regions conflict", "Several lights or bad geometry: no automatic decision."),
}

CSS = """
:root{--ink:#1d2433;--muted:#5b6475;--line:#d9dde5;--bg:#ffffff;--soft:#f5f7fa}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.5 "Segoe UI",system-ui,
-apple-system,Roboto,Helvetica,Arial,sans-serif}main{max-width:1060px;margin:0 auto;padding:28px 24px 48px}
h1{font-size:24px;margin:0 0 4px}h2{font-size:17px;margin:28px 0 10px;padding-bottom:4px;border-bottom:1px solid var(--line)}
.sub{color:var(--muted);margin:0 0 18px}.verdict{border-radius:8px;padding:14px 18px;color:#fff;margin:12px 0}
.verdict .big{font-size:20px;font-weight:700;letter-spacing:.02em}.verdict p{margin:6px 0 0}
.note{background:var(--soft);border-left:4px solid var(--ink);padding:10px 14px;margin:12px 0}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:16px}.grid3{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}
figure{margin:0}figure img{width:100%;border:1px solid var(--line);border-radius:4px;display:block}
figcaption{color:var(--muted);font-size:12px;margin-top:4px}
table{border-collapse:collapse;width:100%;font-size:13px}th,td{border-bottom:1px solid var(--line);padding:5px 6px;text-align:left;
vertical-align:top}th{background:var(--soft);font-weight:600}td.num{text-align:right;font-variant-numeric:tabular-nums}
.chip{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:6px;vertical-align:middle}
.st-flag{color:#b3261e;font-weight:700}.st-ok{color:#1b7f3b}.st-unrel,.st-excl{color:var(--muted)}
.bar{background:#e8ebf0;height:8px;border-radius:4px;position:relative;min-width:80px}
.bar span{position:absolute;left:0;top:0;bottom:0;border-radius:4px;background:#4c78a8}
.bar i{position:absolute;top:-3px;bottom:-3px;width:2px;background:#b3261e}
code,pre{font-family:Consolas,"SF Mono",Menlo,monospace;font-size:12px}pre{background:var(--soft);padding:10px;
white-space:pre-wrap;border-radius:4px;margin:0}.limits{font-size:13px}footer{color:var(--muted);font-size:12px;margin-top:30px}
@media (max-width:720px){.grid2,.grid3{grid-template-columns:1fr}}
@media print{main{max-width:none;padding:0}h2{break-after:avoid}figure,table,.verdict{break-inside:avoid}
.verdict{-webkit-print-color-adjust:exact;print-color-adjust:exact}}
"""


def _md(s: str) -> str:
    """HTML-escape, then render the **bold** markers used by the rule-based texts."""
    return re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", html.escape(s or "", quote=False))


def _b64_file(p: Path, mime: str = "image/png") -> str | None:
    return f"data:{mime};base64," + base64.b64encode(p.read_bytes()).decode() if p.is_file() else None


def _b64_fig(fig) -> str:
    import matplotlib.pyplot as plt
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def _heat_png(p: Path) -> str | None:
    if not p.is_file():
        return None
    from matplotlib import colormaps
    from PIL import Image
    g = np.asarray(Image.open(p).convert("L"), np.float32) / 255.0
    rgb = (colormaps["inferno"](g)[..., :3] * 255).astype(np.uint8)
    buf = io.BytesIO()
    Image.fromarray(rgb).save(buf, "PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def lightmap_figure(m: dict, landscapes: np.ndarray | None, consensus: np.ndarray | None):
    """Equirectangular light map: per reliable region 68/95% HPD contours, consensus marker, GT star."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    fig, ax = plt.subplots(figsize=(8.6, 4.6))
    ext = (-180, 180, -90, 90)
    if consensus is not None:
        ax.imshow(consensus.reshape(NE, NA), extent=ext, origin="upper", cmap="Greys", alpha=0.35, aspect="auto",
                  vmin=0, vmax=1)
    az = -180 + (np.arange(NA) + 0.5) * 360 / NA
    el = 90 - (np.arange(NE) + 0.5) * 180 / NE
    handles = []
    if landscapes is not None:
        for r in m["regions"]:
            if not r.get("reliable"):
                continue
            A = landscapes[r["landscape_index"]]
            _, masks = hpd(A, (0.68, 0.95))
            for msk, ls in zip(masks, ("-", "--")):
                mm = msk.reshape(NE, NA).astype(float)
                if 0 < mm.sum() < mm.size:
                    ax.contour(az, el, mm, levels=[0.5], colors=[r["color"]], linestyles=ls, linewidths=1.6)
            caz, cel = az_el_deg(r["center"])
            ax.plot(caz, cel, "o", ms=5, color=r["color"], mec="k", mew=0.5)
            handles.append(Line2D([], [], color=r["color"], lw=2, label=f"{r['name']} (#{r['id']})"))
    c = (m.get("fusion") or {}).get("consensus")
    if c:
        caz, cel = az_el_deg(c["dir"])
        ax.plot(caz, cel, marker="P", ms=13, color="#ffd400", mec="k", mew=1.2, ls="none")
        handles.append(Line2D([], [], marker="P", color="#ffd400", mec="k", ls="none", ms=10, label="consensus"))
    gt = m.get("ground_truth") or {}
    if gt.get("light_cam"):
        gaz, gel = az_el_deg(gt["light_cam"])
        ax.plot(gaz, gel, marker="*", ms=17, color="#ff3b30", mec="k", mew=1.0, ls="none")
        handles.append(Line2D([], [], marker="*", color="#ff3b30", mec="k", ls="none", ms=12, label="true light (synthetic)"))
    handles += [Line2D([], [], color="k", lw=1.4, ls="-", label="68% set"),
                Line2D([], [], color="k", lw=1.4, ls="--", label="95% set")]
    ax.set_xlim(-180, 180)
    ax.set_ylim(-90, 90)
    ax.set_xticks(range(-180, 181, 45))
    ax.set_yticks(range(-90, 91, 30))
    ax.axhline(0, color="#888", lw=0.6)
    ax.axvline(0, color="#888", lw=0.6)
    ax.grid(alpha=0.25)
    ax.set_xlabel("azimuth (deg; 0 = toward the camera, +90 = right)")
    ax.set_ylabel("elevation (deg)")
    ax.set_title("Where could the light come from? (each region's credible sets)")
    ax.legend(handles=handles, loc="upper left", bbox_to_anchor=(1.01, 1.0), fontsize=8, frameon=False)
    return fig


def _status(r: dict, p: dict | None) -> tuple[str, str]:
    if r.get("excluded"):
        return "st-excl", f"excluded: {r.get('reason') or 'excluded'}"
    if not r.get("reliable"):
        return "st-unrel", f"unreliable: {r.get('reason') or '-'}"
    if p and p.get("flagged"):
        return "st-flag", "FLAGGED"
    return "st-ok", "agrees"


def _fmt(v, nd=1, unit=""):
    return "–" if v is None else f"{float(v):.{nd}f}{unit}"


def export_report(bundle_dir) -> Path:
    """Writes <bundle_dir>/report.html (self-contained) and returns its path."""
    d = Path(bundle_dir)
    m = json.loads((d / "manifest.json").read_text())
    nreg = len(m.get("regions", []))
    L = None
    lp = d / "landscapes.bin"
    if lp.is_file() and lp.stat().st_size == nreg * NE * NA * 4 and nreg:
        L = np.fromfile(lp, "<f4").reshape(nreg, NE * NA)
    C = None
    cp = d / "consensus.bin"
    if cp.is_file() and cp.stat().st_size == NE * NA * 4:
        C = np.fromfile(cp, "<f4")
    f = m.get("fusion", {})
    verdict = f.get("verdict", "INSUFFICIENT")
    color, headline, action = VERDICT_STYLE.get(verdict, ("#444", verdict, ""))
    per = {p["id"]: p for p in f.get("per_region", [])}
    tau = m.get("calibration", {}).get("tau_img")
    cons = f.get("consensus")

    rows = []
    max_s = max([abs(p["shortfall"]) for p in per.values() if p.get("shortfall") is not None] + [tau or 1.0, 1.0])
    for r in m.get("regions", []):
        p = per.get(r["id"])
        cls, st = _status(r, p)
        s = p.get("shortfall") if p else None
        bar = ""
        if s is not None:
            bar = (f'<div class="bar"><span style="width:{100 * max(0.0, s) / max_s:.0f}%"></span>'
                   + (f'<i style="left:{100 * tau / max_s:.0f}%"></i>' if tau else "") + "</div>")
        rows.append(
            f"<tr><td><span class='chip' style='background:{html.escape(r.get('color', '#888'))}'></span>"
            f"{html.escape(str(r['id']))}</td><td>{html.escape(r['name'])}</td><td class='num'>{_fmt(r.get('weight'), 2)}</td>"
            f"<td class='num'>{_fmt(s, 2)}</td><td>{bar}</td><td class='num'>{_fmt(p.get('angle_deg') if p else None, 0, '°')}</td>"
            f"<td>{html.escape(', '.join(r.get('cues') or []))}</td><td class='num'>{r.get('n_valid', 0)}</td>"
            f"<td class='{cls}'>{html.escape(st)}</td></tr>")

    figs = {
        "image": _b64_file(d / "image.png"),
        "heat": _heat_png(d / "heat.png"),
        "cf": _b64_file(d / "counterfactual.png"),
        "normals": _b64_file(d / "normals.png"),
        "lightmap": _b64_fig(lightmap_figure(m, L, C)),
    }

    def fig(key, cap):
        return f"<figure><img src='{figs[key]}' alt='{html.escape(cap)}'><figcaption>{_md(cap)}</figcaption></figure>" \
            if figs.get(key) else f"<figure><figcaption>{html.escape(cap)}: not available in this bundle.</figcaption></figure>"

    cal = m.get("calibration", {})
    cal_rows = "".join(f"<tr><th>{html.escape(k)}</th><td>{html.escape(str(v))}</td></tr>" for k, v in cal.items())
    gt = m.get("ground_truth")
    gt_html = ("<p>Ground truth is <strong>unknown</strong> (real photo); results are qualitative.</p>" if not gt else
               f"<p>Synthetic scene: true light (camera space) {html.escape(str([round(x, 3) for x in gt['light_cam']]))}; "
               f"edited region ids {html.escape(str(gt.get('edited_region_ids')))}; discrepancy "
               f"{_fmt(gt.get('delta_deg'), 0, '°')}.</p>")
    cons_html = "<p>No consensus (too few reliable regions).</p>"
    if cons:
        caz, cel = az_el_deg(cons["dir"])
        cons_html = (f"<p>Consensus light: azimuth {caz:.0f}°, elevation {cel:.0f}° "
                     f"(68% cone {_fmt(cons.get('r68_deg'), 0, '°')}, 95% cone {_fmt(cons.get('r95_deg'), 0, '°')}); "
                     f"image score S<sub>img</sub> = {_fmt(f.get('S_img'), 2)} vs alert level τ = {_fmt(tau, 2)}.</p>")
    atk = m.get("attacks") or []
    atk_html = ""
    if atk:
        atk_html = ("<h2>Attack lab (self-attack results)</h2><table><tr><th>variant</th><th>verdict after</th>"
                    "<th class='num'>S<sub>img</sub></th><th class='num'>mean |ΔY|</th><th class='num'>SSIM loss</th>"
                    "<th>interpretation</th></tr>" + "".join(
                        f"<tr><td>{html.escape(a.get('title', a['variant']))}</td><td>{html.escape(str(a.get('verdict')))}</td>"
                        f"<td class='num'>{_fmt(a.get('S_img'), 2)}</td>"
                        f"<td class='num'>{_fmt((a.get('fidelity') or {}).get('mean_abs_dY'), 3)}</td>"
                        f"<td class='num'>{_fmt((a.get('fidelity') or {}).get('ssim_loss'), 3)}</td>"
                        f"<td>{_md(a.get('interpretation', ''))}</td></tr>" for a in atk) + "</table>")
    log = m.get("backends_log") or []
    img = m.get("image", {})
    doc = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>LightAudit report – {html.escape(m.get('title', m.get('name', '')))}</title><style>{CSS}</style></head>
<body><main>
<h1>LightAudit evidence report</h1>
<p class="sub">{html.escape(m.get('title', ''))} · bundle <code>{html.escape(m.get('name', ''))}</code> ·
{html.escape(str(img.get('w')))}×{html.escape(str(img.get('h')))} px, FOV {_fmt(img.get('fov_deg'), 0, '°')} ·
source: {html.escape(str(img.get('source')))} · created {html.escape(str(m.get('created', '')))}</p>
<div class="verdict" style="background:{color}"><div class="big">{html.escape(verdict)} – {html.escape(headline)}</div>
<p>{_md(f.get('text', ''))}</p><p><strong>Recommended action:</strong> {html.escape(action)}</p></div>
<div class="note"><strong>How to use this result.</strong> This report checks whether the lighting of different parts of
the image is physically consistent. A flag means "send for human review", never "this is fraud". It is one signal
among many.</div>
<p>{_md(m.get('description', ''))}</p>
<h2>Image and light map</h2>
<div class="grid2">{fig('image', 'The audited image.')}{fig('lightmap', 'Light map: solid = 68% set, dashed = 95% set per reliable region; + = consensus; ★ = true light (synthetic only).')}</div>
{cons_html}{gt_html}
<h2>Regions</h2>
<table><tr><th>id</th><th>region</th><th class="num">weight</th><th class="num">shortfall</th><th>vs alert</th>
<th class="num">angle to consensus</th><th>cues</th><th class="num">usable px</th><th>status</th></tr>{''.join(rows)}</table>
<p class="sub">Shortfall = −ln(agreement of the region's light map with the consensus of the other regions); 0 = full
agreement, ~6.9 = no overlap. The red tick marks the alert level. Unreliable and excluded regions are never flagged.</p>
<h2>Where the shading does not fit</h2>
<div class="grid3">{fig('heat', 'Residual z-score heat map (bright = observed brightness does not match the consensus light).')}
{fig('cf', 'Counterfactual: each region re-shaded as the consensus light predicts.')}
{fig('normals', 'Surface directions used (RGB-encoded normals).')}</div>
{atk_html}
<h2>Calibration and backends</h2>
<div class="grid2"><div><table>{cal_rows}</table></div>
<div><p>Normals: <code>{html.escape(str(m.get('normals_backend')))}</code> · regions: <code>{html.escape(str(m.get('regions_backend')))}</code></p>
<pre>{html.escape(chr(10).join(log) if log else 'no backend messages')}</pre></div></div>
<h2>Limitations</h2>
<p class="limits">{_md(LIMITATIONS)}</p>
<footer>Generated by LightAudit from the bundle files. All numbers are computed by the pipeline; no manual edits.</footer>
</main></body></html>"""
    out = d / "report.html"
    out.write_text(doc, encoding="utf-8")
    return out


if __name__ == "__main__":
    import sys
    for a in sys.argv[1:]:
        print(export_report(Path(a)))
