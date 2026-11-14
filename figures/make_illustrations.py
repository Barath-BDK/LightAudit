"""Conceptual illustrations I1-I9 for LightAudit (BUILD_SPEC section 15).

Run:  python figures/make_illustrations.py

Writes PNG (200 dpi) and SVG versions of every illustration to docs/figures/.
Self-contained: uses only numpy + matplotlib and does NOT import `lightaudit`.
The few formulas needed (EQ grid, rank landscape, leave-one-out shortfall,
conformal quantile, HPD sets) are re-implemented here in a few lines each.
All random draws use fixed seeds, so the output is deterministic.

These are *schematics and toy examples*, not experimental results. Every
numeric value drawn here is computed from toy inputs defined in this file.
"""

from __future__ import annotations

import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.patches import Circle, FancyArrowPatch, FancyBboxPatch, Polygon, Rectangle  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "figures"

# ----------------------------------------------------------------------------
# One palette for every illustration (Tableau-10 based)
# ----------------------------------------------------------------------------
INK = "#222222"
MUTED = "#6B6B6B"
LIGHT = "#EDEDED"
BLUE = "#4E79A7"
ORANGE = "#F28E2B"
RED = "#E15759"
TEAL = "#76B7B2"
GREEN = "#59A14F"
YELLOW = "#EDC948"
PURPLE = "#B07AA1"
BROWN = "#9C755F"
GREY = "#79706E"

TAG_COLORS = {"CG": BLUE, "CV": GREEN, "IP": ORANGE, "ML": PURPLE}
VERDICT_COLORS = {"CONSISTENT": GREEN, "SUSPICIOUS": RED, "INSUFFICIENT": GREY, "CONFLICT": ORANGE}
REGION_COLORS = [BLUE, TEAL, GREEN, PURPLE, BROWN]

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 11,
    "axes.titlesize": 12,
    "axes.labelsize": 11,
    "xtick.labelsize": 10,
    "ytick.labelsize": 10,
    "legend.fontsize": 10,
    "axes.edgecolor": INK,
    "axes.labelcolor": INK,
    "xtick.color": INK,
    "ytick.color": INK,
    "text.color": INK,
    "figure.facecolor": "white",
    "axes.facecolor": "white",
    "savefig.facecolor": "white",
    "axes.spines.top": False,
    "axes.spines.right": False,
    "svg.fonttype": "path",
})


def save(fig, name: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for ext, kw in (("png", {"dpi": 200}), ("svg", {})):
        fig.savefig(OUT / f"{name}.{ext}", bbox_inches="tight", pad_inches=0.2,
                    facecolor="white", edgecolor="none", **kw)
    plt.close(fig)
    print(f"wrote docs/figures/{name}.png / .svg")


def suptitle(fig, text: str, y: float = 1.0) -> None:
    fig.suptitle(text, fontsize=14, fontweight="bold", y=y, color=INK)


# ----------------------------------------------------------------------------
# Small math helpers (re-implemented; mirrors BUILD_SPEC 5.2 / 7.5 / 7.7 / 7.11)
# ----------------------------------------------------------------------------
NA, NE = 128, 64


def eq_grid():
    """EQ grid of BUILD_SPEC 5.2: returns az, lat (NE, NA) and dirs (NE, NA, 3), weights (NE, NA)."""
    i = np.arange(NA)
    j = np.arange(NE)
    az = -np.pi + (i + 0.5) * 2 * np.pi / NA
    lat = np.pi / 2 - (j + 0.5) * np.pi / NE
    AZ, LAT = np.meshgrid(az, lat)
    dirs = np.stack([np.cos(LAT) * np.sin(AZ), np.sin(LAT), np.cos(LAT) * np.cos(AZ)], axis=-1)
    w = np.cos(LAT)
    w = w / w.sum()
    return AZ, LAT, dirs, w


def unit(v):
    v = np.asarray(v, dtype=float)
    return v / np.linalg.norm(v, axis=-1, keepdims=True)


def dir_from_az_el(az_deg, el_deg):
    a, e = np.radians(az_deg), np.radians(el_deg)
    return np.array([np.cos(e) * np.sin(a), np.sin(e), np.cos(e) * np.cos(a)])


def angle_deg(a, b):
    return float(np.degrees(np.arccos(np.clip(np.dot(unit(a), unit(b)), -1, 1))))


def fibonacci_sphere(n):
    k = np.arange(n) + 0.5
    phi = np.arccos(1 - 2 * k / n)
    theta = np.pi * (1 + 5 ** 0.5) * k
    return np.stack([np.sin(phi) * np.cos(theta), np.cos(phi), np.sin(phi) * np.sin(theta)], axis=1)


def ranks(x):
    """Average ranks (ties -> mean rank), 1-D."""
    order = np.argsort(x, kind="mergesort")
    r = np.empty(len(x))
    xs = x[order]
    i = 0
    while i < len(x):
        j = i
        while j + 1 < len(x) and xs[j + 1] == xs[i]:
            j += 1
        r[order[i:j + 1]] = 0.5 * (i + j)
        i = j + 1
    return r


def rank_landscape(normals, Y, dirs):
    """C1 rank landscape (BUILD_SPEC 7.5): Pearson(rank(max(0,n.l)), rank(Y)) with the zero group tied."""
    s = normals @ dirs.T
    sc = np.maximum(s, 0.0)
    rs = np.argsort(np.argsort(sc, axis=0), axis=0).astype(float)
    z = (s <= 0).sum(axis=0)
    rs = np.where(s <= 0, (z - 1) / 2.0, rs)
    ry = ranks(Y)
    rs = rs - rs.mean(axis=0)
    ry = ry - ry.mean()
    num = (rs * ry[:, None]).sum(axis=0)
    den = np.sqrt((rs ** 2).sum(axis=0) * (ry ** 2).sum()) + 1e-12
    return num / den


def hpd_mask(P, w, level):
    order = np.argsort(-P, axis=None)
    mass = (P * w).ravel()
    cum = np.cumsum(mass[order]) / mass.sum()
    k = int(np.searchsorted(cum, level))
    thr = P.ravel()[order][min(k, len(order) - 1)]
    return P >= thr, thr


def cone_radius_deg(mask, w):
    omega = 4 * np.pi * float(w[mask].sum())
    return float(np.degrees(np.arccos(1 - omega / (2 * np.pi))))


def tangent_basis(c):
    c = unit(c)
    up = np.array([0.0, 1.0, 0.0]) if abs(c[1]) < 0.95 else np.array([1.0, 0.0, 0.0])
    e1 = unit(np.cross(up, c))
    e2 = np.cross(c, e1)
    return e1, e2


def small_circle(center, radius_deg, n=180):
    c = unit(center)
    e1, e2 = tangent_basis(c)
    t = np.linspace(0, 2 * np.pi, n)
    r = np.radians(radius_deg)
    return (np.cos(r) * c[None, :]
            + np.sin(r) * (np.cos(t)[:, None] * e1[None, :] + np.sin(t)[:, None] * e2[None, :]))


# ----------------------------------------------------------------------------
# Drawing helpers
# ----------------------------------------------------------------------------
def arrow(ax, p0, p1, color=INK, lw=1.8, style="-|>", ls="-", ms=14, zorder=3, **kw):
    a = FancyArrowPatch(p0, p1, arrowstyle=style, mutation_scale=ms, color=color, lw=lw,
                        linestyle=ls, shrinkA=0, shrinkB=0, zorder=zorder, **kw)
    ax.add_patch(a)
    return a


def pill(ax, x, y, text, color, fs=10):
    ax.text(x, y, text, fontsize=fs, fontweight="bold", color="white", ha="center", va="center",
            bbox=dict(boxstyle="round,pad=0.25,rounding_size=0.6", fc=color, ec="none"), zorder=6)


def node(ax, cx, cy, w, h, title, body, tags=(), fc="white", ec=INK, title_color=INK):
    box = FancyBboxPatch((cx - w / 2, cy - h / 2), w, h, boxstyle="round,pad=0.0,rounding_size=1.2",
                         fc=fc, ec=ec, lw=1.6, zorder=2)
    ax.add_patch(box)
    ax.text(cx, cy + h / 2 - 1.9, title, ha="center", va="center", fontsize=12, fontweight="bold",
            color=title_color, zorder=5)
    ax.text(cx, cy + 0.2 - (0.9 if tags else 0) + 0.6, body, ha="center", va="center", fontsize=10,
            color=INK, zorder=5, linespacing=1.3)
    if tags:
        n = len(tags)
        spacing = 4.0
        x0 = cx - spacing * (n - 1) / 2
        for k, t in enumerate(tags):
            pill(ax, x0 + k * spacing, cy - h / 2 + 1.7, t, TAG_COLORS[t])


# ----------------------------------------------------------------------------
# I1 pipeline
# ----------------------------------------------------------------------------
def fig_pipeline():
    fig, ax = plt.subplots(figsize=(16, 7.6))
    ax.set_xlim(0, 100)
    ax.set_ylim(-2, 50)
    ax.axis("off")

    W, H = 17.0, 14.0
    ytop, ybot = 36.5, 16.0
    xs = [10, 30, 50, 70, 90]

    node(ax, xs[0], ytop, W, H, "Input photo",
         "real photo, or a synthetic\nSDF ray-marched render\n(exact normals + light)", ("CG", "IP"))
    node(ax, xs[1], ytop, W, H, "Regions",
         "objects / surfaces:\nSAM or SLIC (real),\nGT object ids (synthetic)", ("CV", "ML"))
    node(ax, xs[2], ytop, W, H, "Surface normals",
         "pretrained ensemble\n+ per-pixel uncertainty\n(member disagreement)", ("CV", "ML"))
    node(ax, xs[3], ytop, W, H, "Usable pixels",
         "erode borders, drop\nsaturated / deep shadow,\ngrazing, uncertain", ("IP",))
    node(ax, xs[4], ytop, W, H, "Lighting cues",
         "C1 rank shading (main)\nC2 specular glints\nC3 silhouettes\nC4 shadow pairs (manual)", ("CV",))

    node(ax, xs[4], ybot, W, H, "Region light maps",
         "block bootstrap + KDE\nposterior P_k on sphere,\n68/95% cones, weight w_k", ("ML", "CV"))
    node(ax, xs[3], ybot, W, H, "Fusion",
         "weighted log-sum F(l),\nconsensus l*, leave-one-\nout shortfall s_k", ("CV",))
    node(ax, xs[2], ybot, W, H, "Calibrated verdict",
         "S_img = max s_k vs alert τ\nCONSISTENT / SUSPICIOUS\nINSUFFICIENT / CONFLICT", ("ML",))
    node(ax, xs[1], ybot, W, H, "Interactive viewer",
         "WebGL2 relight shader,\nThree.js light dome,\nresidual heatmap", ("CG",))
    node(ax, xs[0], ybot, W, H, "Attack lab",
         "T1 colour transfer,\nT3a re-shade, T4 adaptive;\nre-audit the result", ("IP", "CG"))

    # Calibration box below the verdict
    node(ax, xs[2], 1.9, 38, 6.2, "", "", ())
    ax.text(xs[2], 3.3, "Calibration on pristine scenes", ha="center", va="center",
            fontsize=11.5, fontweight="bold")
    ax.text(xs[2], 0.9, "KDE bandwidth h, temperature T, conformal alert level τ", ha="center",
            va="center", fontsize=10)
    pill(ax, xs[2] - 15.5, 3.3, "ML", PURPLE)
    arrow(ax, (xs[2], 5.0), (xs[2], ybot - H / 2))

    g = 0.4
    for a, b in zip(xs[:-1], xs[1:]):
        arrow(ax, (a + W / 2 + g, ytop), (b - W / 2 - g, ytop))
    arrow(ax, (xs[4], ytop - H / 2 - g), (xs[4], ybot + H / 2 + g))
    for a, b in zip(xs[::-1][:-1], xs[::-1][1:]):
        arrow(ax, (a - W / 2 - g, ybot), (b + W / 2 + g, ybot))

    # Attack loop back to input (dashed)
    arrow(ax, (xs[0], ybot + H / 2 + g), (xs[0], ytop - H / 2 - g), color=RED, ls="--", lw=1.8)
    ax.text(xs[0] + 1.0, (ybot + ytop) / 2, "edited image\nre-audited", color=RED, fontsize=10,
            ha="left", va="center")

    # Legend
    lx = 72.0
    ax.text(lx, 4.4, "Course areas:", fontsize=11, fontweight="bold", va="center", ha="left")
    names = [("CG", "graphics"), ("CV", "vision"), ("IP", "image processing"), ("ML", "learning")]
    for k, (t, nm) in enumerate(names):
        x = lx + 1.2 + (k % 2) * 15.5
        yy = 1.6 - (k // 2) * 2.9
        pill(ax, x, yy, t, TAG_COLORS[t])
        ax.text(x + 2.0, yy, nm, fontsize=10.5, va="center", ha="left")
    ax.text(0.5, 47.6, "LightAudit: one light should explain every region; the audit tests that,\n"
            "abstains when evidence is weak, and then attacks itself", fontsize=14,
            fontweight="bold", va="center", ha="left", linespacing=1.25)
    save(fig, "pipeline")


# ----------------------------------------------------------------------------
# I2 rank invariance
# ----------------------------------------------------------------------------
def fig_rank_invariance():
    rng = np.random.default_rng(2)
    n = 1500
    axis = unit([-0.35, 0.25, 1.0])
    e1, e2 = tangent_basis(axis)
    # Normals of a curved panel: a cap of half-angle 60 deg around `axis`
    u = rng.uniform(np.cos(np.radians(60)), 1.0, n)
    t = rng.uniform(0, 2 * np.pi, n)
    sin_r = np.sqrt(1 - u ** 2)
    normals = (u[:, None] * axis[None] + sin_r[:, None] * (np.cos(t)[:, None] * e1[None] + np.sin(t)[:, None] * e2[None]))
    light = unit([0.55, 0.55, 0.62])
    ndl = normals @ light
    radiance = 0.06 + np.maximum(ndl, 0.0)  # ambient offset + Lambert (linear)

    curves = {
        "sRGB-like (gamma 2.2)": lambda x: np.clip(0.85 * x, 0, 1) ** (1 / 2.2),
        "S-curve (contrast)": lambda x: (lambda y: y * y * (3 - 2 * y))(np.clip(0.6 * x, 0, 1) ** (1 / 2.2)),
        "filmic / HDR": lambda x: (lambda y: (y / (1 + y)) ** (1 / 2.2))(4.0 * x),
    }
    colors = [BLUE, ORANGE, PURPLE]
    dirs = fibonacci_sphere(6000)

    fig, axs = plt.subplots(1, 3, figsize=(16, 5.0), gridspec_kw={"wspace": 0.32})
    errs_rank, errs_ls = [], []
    for (name, g), col in zip(curves.items(), colors):
        Y = g(radiance) + rng.normal(0, 0.006, n)
        Y = np.clip(Y, 0, 0.96)
        order = np.argsort(ndl)
        axs[0].scatter(ndl, Y, s=3, color=col, alpha=0.35, rasterized=True)
        axs[0].plot([], [], color=col, lw=3, label=name)
        # (b) ranks
        sc = np.maximum(ndl, 0)
        zr = (ndl <= 0).sum()
        rs = np.where(ndl <= 0, (zr - 1) / 2.0, np.argsort(np.argsort(sc)).astype(float)) / (n - 1)
        ry = ranks(Y) / (n - 1)
        axs[1].scatter(rs, ry, s=3, color=col, alpha=0.35, rasterized=True)
        # (c) estimates
        S = rank_landscape(normals, Y, dirs)
        l_rank = dirs[np.argmax(S)]
        Ylin = Y ** 2.2
        A = np.hstack([np.ones((n, 1)), normals])
        coef, *_ = np.linalg.lstsq(A, Ylin, rcond=None)
        l_ls = unit(coef[1:])
        errs_rank.append(angle_deg(l_rank, light))
        errs_ls.append(angle_deg(l_ls, light))
        del order

    axs[0].set_xlabel("n · l  (true light)")
    axs[0].set_ylabel("pixel brightness Y")
    axs[0].set_title("(a) Same region, three tone curves:\nbrightness vs. n·l differs", loc="left")
    axs[0].legend(loc="upper left", frameon=False, handlelength=1.2)
    axs[0].set_xlim(-0.3, 1.02)
    axs[0].set_ylim(0, 1.0)

    axs[1].plot([0, 1], [0, 1], color=INK, lw=1, ls="--")
    axs[1].set_xlabel("rank of max(0, n·l)  (normalised)")
    axs[1].set_ylabel("rank of Y  (normalised)")
    axs[1].set_title("(b) After ranking, the three\nclouds coincide on the diagonal", loc="left")
    axs[1].set_xlim(0, 1)
    axs[1].set_ylim(0, 1)
    axs[1].annotate("attached-shadow pixels\n(n·l ≤ 0) share one tied rank", (0.1, 0.12), (0.2, 0.03),
                    fontsize=10, color=MUTED, va="bottom", ha="left",
                    arrowprops=dict(arrowstyle="-", color=MUTED, lw=1))

    x = np.arange(3)
    bw = 0.36
    b1 = axs[2].bar(x - bw / 2, errs_ls, bw, color=LIGHT, edgecolor=INK, label="linear least squares\n(Y^2.2 ≈ a + L·n)")
    b2 = axs[2].bar(x + bw / 2, errs_rank, bw, color=GREEN, edgecolor=INK, label="rank correlation (C1)")
    for bars in (b1, b2):
        for b in bars:
            axs[2].text(b.get_x() + b.get_width() / 2, b.get_height() + 0.4, f"{b.get_height():.1f}°",
                        ha="center", va="bottom", fontsize=10)
    axs[2].set_xticks(x)
    axs[2].set_xticklabels(["sRGB-like", "S-curve", "filmic"])
    axs[2].set_ylabel("light direction error (degrees)")
    top = max(max(errs_ls), max(errs_rank))
    axs[2].set_ylim(0, top * 1.45 + 2)
    axs[2].legend(loc="upper left", frameon=False)
    axs[2].set_title("(c) Toy estimate: LS is biased by the\ncurve and the shadow clamp; rank is not", loc="left")

    suptitle(fig, "Rank shading (C1) is invariant to the unknown tone curve: only the order of brightness is used",
             y=1.06)
    fig.text(0.5, -0.04, "Toy example: one curved region (1,500 pixels), exact normals, ambient offset, "
             "small noise. Not an experimental result (see E1 for the evaluation).",
             ha="center", fontsize=10, color=MUTED)
    save(fig, "rank_invariance")
    return errs_ls, errs_rank


# ----------------------------------------------------------------------------
# I3 cue geometry
# ----------------------------------------------------------------------------
def draw_sun(ax, x, y, r=0.35, color=YELLOW):
    ax.add_patch(Circle((x, y), r, fc=color, ec="#B8860B", lw=1.2, zorder=5))
    for a in np.linspace(0, 2 * np.pi, 8, endpoint=False):
        ax.plot([x + 1.35 * r * np.cos(a), x + 1.85 * r * np.cos(a)],
                [y + 1.35 * r * np.sin(a), y + 1.85 * r * np.sin(a)], color="#B8860B", lw=1.4, zorder=5)


def fig_cue_geometry():
    fig, axs = plt.subplots(1, 3, figsize=(16, 5.0), gridspec_kw={"wspace": 0.08})
    for a in axs:
        a.set_aspect("equal")
        a.axis("off")

    # (a) glint: mirror geometry ------------------------------------------------
    ax = axs[0]
    ax.set_xlim(-4.2, 4.2)
    ax.set_ylim(-1.6, 5.0)
    th = np.linspace(np.radians(35), np.radians(145), 200)
    R = 6.0
    cx, cy = 0, -R + 0.4
    ax.fill_between(cx + R * np.cos(th), cy + R * np.sin(th), -1.6, color="#DCE6F0", zorder=1)
    ax.plot(cx + R * np.cos(th), cy + R * np.sin(th), color=BLUE, lw=2.5, zorder=2)
    p = np.array([0.6, cy + np.sqrt(R ** 2 - 0.6 ** 2)])
    nvec = unit(p - np.array([cx, cy]))
    v = unit(np.array([-1.0, 1.05]))  # toward camera
    lh = 2 * np.dot(nvec, v) * nvec - v
    L = 3.0
    arrow(ax, p, p + 2.3 * nvec, color=GREEN, lw=2.2)
    arrow(ax, p, p + L * v, color=INK, lw=2.2)
    arrow(ax, p, p + L * lh, color=ORANGE, lw=2.2)
    ax.text(*(p + 2.3 * nvec + np.array([-0.2, -0.1])), "n (normal)", color=GREEN, fontsize=11, ha="right",
            va="center")
    camp = p + (L + 0.45) * v
    # camera body (rotated square) with the lens pointing back along -v
    perp = np.array([-v[1], v[0]])
    body = [camp + 0.32 * (a * v + b * perp) for a, b in ((1, 1), (1, -1), (-1, -1), (-1, 1))]
    ax.add_patch(Polygon(body, fc=INK, zorder=5))
    lens = [camp - 0.3 * v + 0.12 * perp, camp - 0.3 * v - 0.12 * perp,
            camp - 0.62 * v - 0.26 * perp, camp - 0.62 * v + 0.26 * perp]
    ax.add_patch(Polygon(lens, fc=INK, zorder=5))
    ax.text(camp[0], camp[1] + 0.55, "camera (view v)", fontsize=11, ha="center")
    sunp = p + (L + 0.55) * lh
    draw_sun(ax, *sunp)
    ax.text(sunp[0] + 0.5, sunp[1] + 0.8, "light  l = 2(n·v)n − v", fontsize=11, ha="right", color=ORANGE)
    ax.add_patch(Circle(p, 0.13, fc="white", ec=ORANGE, lw=2, zorder=6))
    ax.text(p[0], p[1] - 0.75, "glint (saturated blob)", fontsize=10.5, ha="center", color=INK, zorder=6)
    ax.text(0, -1.35, "glossy paint", fontsize=10.5, ha="center", color=BLUE)
    ax.set_title("(a) Specular glint: the light is the\nmirror image of the view about n", fontsize=12.5, loc="center")

    # (b) contour -----------------------------------------------------------------
    ax = axs[1]
    ax.set_xlim(-4.2, 4.2)
    ax.set_ylim(-2.6, 4.0)
    ax.add_patch(Rectangle((-3.8, -2.4), 7.6, 6.2, fc="#F7F7F7", ec=MUTED, lw=1.2))
    ax.text(-3.65, 3.55, "image plane", fontsize=10.5, color=MUTED, va="center")
    tt = np.linspace(0, 2 * np.pi, 300)
    a_, b_ = 2.2, 1.45
    ex, ey = a_ * np.cos(tt), 0.55 + b_ * np.sin(tt)
    ax.fill(ex, ey, color="#DDEBD8", zorder=1)
    ax.plot(ex, ey, color=GREEN, lw=2.5, zorder=2)
    for t0 in np.radians([20, 70, 115, 160, 200, 250, 290, 335]):
        px, py = a_ * np.cos(t0), 0.55 + b_ * np.sin(t0)
        nx, ny = np.cos(t0) / a_, np.sin(t0) / b_
        nn = np.hypot(nx, ny)
        arrow(ax, (px, py), (px + 0.8 * nx / nn, py + 0.8 * ny / nn), color=INK, lw=1.8, ms=12)
    ax.text(0, 0.75, "object silhouette", fontsize=11, ha="center", color=INK)
    ax.text(0, 0.1, "n = (cos φ, sin φ, 0)", fontsize=11, ha="center", color=INK)
    ax.text(0, -2.05, "no network needed; light depth\ncomponent unconstrained (a ridge)", fontsize=10.5,
            ha="center", va="center", color=MUTED)
    ax.set_title("(b) Occluding contour: normals lie in\nthe image plane, pointing outward", fontsize=12.5)

    # (c) shadow lines ------------------------------------------------------------
    ax = axs[2]
    ax.set_xlim(-0.2, 10.2)
    ax.set_ylim(-0.4, 8.1)
    horizon = 3.4
    top = 7.6
    vp = np.array([5.2, 7.3])
    gvp = np.array([vp[0], horizon])
    ax.add_patch(Rectangle((0, 0), 10, horizon, fc="#F3EEE7", ec="none", zorder=0))
    ax.add_patch(Rectangle((0, horizon), 10, top - horizon, fc="#EEF3F8", ec="none", zorder=0))
    ax.add_patch(Rectangle((0, 0), 10, top, fc="none", ec=MUTED, lw=1.2, zorder=1))
    ax.text(9.85, horizon + 0.2, "horizon", fontsize=10, color=MUTED, ha="right")
    ax.plot([0, 10], [horizon, horizon], color=MUTED, lw=1, ls=":")

    def inter(p1, d1, p2, d2):
        A = np.array([d1, -d2]).T
        t = np.linalg.solve(A, p2 - p1)
        return p1 + t[0] * d1

    for bx, by, hgt in [(2.2, 2.0, 1.0), (4.5, 2.8, 0.8), (7.9, 1.6, 1.1)]:
        b = np.array([bx, by])
        tip = b + np.array([0, hgt])
        s = inter(vp, tip - vp, b, b - gvp)
        ax.plot([b[0], tip[0]], [b[1], tip[1]], color=BROWN, lw=4, solid_capstyle="round", zorder=4)
        ax.plot([b[0], s[0]], [b[1], s[1]], color="#555555", lw=5, alpha=0.55, solid_capstyle="round", zorder=3)
        ax.plot([s[0], vp[0]], [s[1], vp[1]], color=ORANGE, lw=1.5, ls="--", zorder=2)
        ax.plot(*tip, "o", color=INK, ms=5, zorder=5)
        ax.plot(*s, "o", color=INK, ms=5, zorder=5, mfc="white")
    draw_sun(ax, *vp, r=0.3)
    ax.text(vp[0] - 0.6, vp[1], "light's vanishing point", fontsize=10.5, va="center", ha="right")
    ax.text(0.25, 0.4, "● object point   ○ its shadow", fontsize=10.5, va="center")
    ax.set_title("(c) Shadow pairs: lines through each point\nand its shadow meet at the light", fontsize=12.5)

    suptitle(fig, "Three extra cues measure the light with different geometry, so one edit rarely fools them all",
             y=1.03)
    save(fig, "cue_geometry")


# ----------------------------------------------------------------------------
# I4 light dome
# ----------------------------------------------------------------------------
def view_basis(az_deg=68, el_deg=22):
    c = dir_from_az_el(az_deg, el_deg)
    right = unit(np.cross([0.0, 1.0, 0.0], c))
    up = np.cross(c, right)
    return c, right, up


def proj(P, basis):
    c, r, u = basis
    P = np.atleast_2d(P)
    return P @ r, P @ u, P @ c


def draw_dome(ax, cones, consensus, basis, flagged=None):
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_xlim(-1.35, 1.35)
    ax.set_ylim(-1.25, 1.3)
    ax.add_patch(Circle((0, 0), 1.0, fc="#F4F7FB", ec=INK, lw=1.5, zorder=0))
    # equator and a meridian
    t = np.linspace(0, 2 * np.pi, 361)
    eq = np.stack([np.sin(t), np.zeros_like(t), np.cos(t)], 1)
    x, y, d = proj(eq, basis)
    for front, style in ((d >= 0, "-"), (d < 0, ":")):
        xx, yy = np.where(front, x, np.nan), np.where(front, y, np.nan)
        ax.plot(xx, yy, color=MUTED, lw=1.0, ls=style, zorder=1)
    # photo billboard (plane z = 0, facing +z)
    wq, hq = 0.42, 0.29
    corners = np.array([[-wq, -hq, 0], [wq, -hq, 0], [wq, hq, 0], [-wq, hq, 0]])
    x, y, _ = proj(corners, basis)
    ax.add_patch(Polygon(np.stack([x, y], 1), fc="#C9C9C9", ec=INK, lw=1.2, zorder=3))
    ax.text(np.mean(x), np.mean(y), "photo", ha="center", va="center", fontsize=10.5, zorder=4)
    # up axis
    x, y, _ = proj(np.array([[0, 0.29, 0], [0, 1.18, 0], [0, 0, 0.42], [0, 0, 1.25]]), basis)
    arrow(ax, (x[0], y[0]), (x[1], y[1]), color=MUTED, lw=1.2, ms=10, zorder=2)
    ax.text(x[1] + 0.05, y[1], "up", fontsize=10, color=MUTED, va="center")
    arrow(ax, (x[2], y[2]), (x[3], y[3]), color=MUTED, lw=1.2, ms=10, zorder=2)
    ax.text(x[3] - 0.04, y[3] - 0.08, "toward\ncamera", fontsize=10, color=MUTED, va="top", ha="right")
    # cones
    for k, (cdir, r, col) in enumerate(cones):
        pts = small_circle(cdir, r)
        x, y, d = proj(pts, basis)
        alpha = 0.45 if np.mean(d) >= 0 else 0.18
        ec = RED if (flagged is not None and k == flagged) else col
        ax.add_patch(Polygon(np.stack([x, y], 1), fc=col, ec=ec, lw=2.2 if ec == RED else 1.4,
                             alpha=1.0, zorder=5, fill=False))
        ax.add_patch(Polygon(np.stack([x, y], 1), fc=col, ec="none", alpha=alpha, zorder=4))
        xc, yc, _ = proj(unit(cdir), basis)
        ax.plot([0, xc[0]], [0, yc[0]], color=col, lw=1.0, alpha=0.6, zorder=2)
    xs_, ys_, _ = proj(unit(consensus), basis)
    ax.plot([0, xs_[0]], [0, ys_[0]], color="#B8860B", lw=1.4, ls="--", zorder=6)
    ax.plot(xs_, ys_, marker="*", ms=22, color=YELLOW, mec="#8A6D00", mew=1.2, zorder=7)
    return xs_[0], ys_[0]


def fig_light_dome():
    basis = view_basis()
    cons = dir_from_az_el(30, 45)
    offs = [(-8, 4), (6, -5), (-3, -8), (9, 6)]
    radii = [11, 14, 9, 13]
    good = [(dir_from_az_el(30 + a, 45 + e), r, REGION_COLORS[k]) for k, ((a, e), r) in enumerate(zip(offs, radii))]

    fig, axs = plt.subplots(1, 2, figsize=(14, 7.0), gridspec_kw={"wspace": 0.05})
    sx, sy = draw_dome(axs[0], good, cons, basis)
    axs[0].annotate("consensus light", (sx, sy), (sx + 0.08, sy + 0.38), fontsize=11,
                    arrowprops=dict(arrowstyle="-", color=INK, lw=1), ha="left")
    axs[0].text(0, -1.17, "four regions' 68% cones overlap around one direction",
                ha="center", fontsize=11)
    axs[0].set_title("Consistent photo", fontsize=13, fontweight="bold", color=GREEN)

    bad = list(good)
    bad[3] = (dir_from_az_el(140, 30), 13, RED)
    cons_b = dir_from_az_el(29, 44)
    draw_dome(axs[1], bad, cons_b, basis, flagged=3)
    xb, yb, _ = proj(small_circle(bad[3][0], 13), basis)
    axs[1].annotate("pasted region:\nits cone is far from\nthe others", (xb.mean(), yb.max()),
                    (0.5, 1.02), fontsize=11, color=RED,
                    arrowprops=dict(arrowstyle="-", color=RED, lw=1), ha="left", va="center")
    axs[1].text(0, -1.17, "one cone does not overlap the consensus → flagged",
                ha="center", fontsize=11)
    axs[1].set_title("Spliced photo", fontsize=13, fontweight="bold", color=RED)

    suptitle(fig, "The light dome: each region votes for where the light can be; a pasted region votes elsewhere",
             y=0.99)
    fig.text(0.5, 0.02, "Schematic. The photo sits at the centre of a unit sphere of light directions; "
             "shaded disks are 68% credible cones; the star is the consensus light.",
             ha="center", fontsize=10, color=MUTED)
    save(fig, "light_dome")


# ----------------------------------------------------------------------------
# I5 cones vs posterior
# ----------------------------------------------------------------------------
def fig_cones_vs_posterior():
    AZ, LAT, dirs, w = eq_grid()
    c = dir_from_az_el(30, 32)
    e1, e2 = tangent_basis(c)
    rot = np.radians(28)
    f1 = np.cos(rot) * e1 + np.sin(rot) * e2
    f2 = -np.sin(rot) * e1 + np.cos(rot) * e2

    def landscape(D):
        cosr = np.clip(D @ c, -1, 1)
        rho = np.degrees(np.arccos(cosr))
        sinr = np.sqrt(np.maximum(1 - cosr ** 2, 1e-12))
        a = rho * (D @ f1) / sinr
        b = rho * (D @ f2) / sinr
        p = np.exp(-0.5 * ((a / 24.0) ** 2 + (b / 6.5) ** 2))
        p += 0.45 * np.exp(-0.5 * (((a - 34) / 10.0) ** 2 + ((b - 9) / 7.0) ** 2))
        return p / p.max()

    P = landscape(dirs)
    m68, t68 = hpd_mask(P, w, 0.68)
    m95, t95 = hpd_mask(P, w, 0.95)
    r68, r95 = cone_radius_deg(m68, w), cone_radius_deg(m95, w)
    center = unit((P[..., None] * w[..., None] * dirs).reshape(-1, 3).sum(0))

    # local azimuthal-equidistant view around c
    ext = 75
    g = np.linspace(-ext, ext, 401)
    GX, GY = np.meshgrid(g, g)
    rho = np.radians(np.hypot(GX, GY))
    beta = np.arctan2(GY, GX)
    Dloc = (np.cos(rho)[..., None] * c + np.sin(rho)[..., None] *
            (np.cos(beta)[..., None] * e1 + np.sin(beta)[..., None] * e2))
    Ploc = landscape(Dloc)

    def to_local(D):
        D = np.atleast_2d(D)
        cosr = np.clip(D @ c, -1, 1)
        rr = np.degrees(np.arccos(cosr))
        bb = np.arctan2(D @ e2, D @ e1)
        return rr * np.cos(bb), rr * np.sin(bb)

    fig, axs = plt.subplots(1, 2, figsize=(15.5, 5.3), gridspec_kw={"width_ratios": [1.55, 1], "wspace": 0.22})

    ax = axs[0]
    ax.imshow(P, extent=[-180, 180, -90, 90], origin="upper", cmap="viridis", aspect="equal",
              interpolation="bilinear")
    azd, latd = np.degrees(AZ), np.degrees(LAT)
    ax.contour(azd, latd, P, levels=[t95], colors="white", linewidths=2.0, linestyles="--")
    ax.contour(azd, latd, P, levels=[t68], colors="white", linewidths=2.2)
    for r, ls in ((r68, "-"), (r95, "--")):
        pts = small_circle(center, r, 360)
        az_ = np.degrees(np.arctan2(pts[:, 0], pts[:, 2]))
        el_ = np.degrees(np.arcsin(np.clip(pts[:, 1], -1, 1)))
        ax.plot(az_, el_, color=ORANGE, lw=2.2, ls=ls)
    ax.set_xlim(-180, 180)
    ax.set_ylim(-90, 90)
    ax.set_xticks(np.arange(-180, 181, 60))
    ax.set_yticks(np.arange(-90, 91, 30))
    ax.set_xlabel("azimuth (degrees, 0 = toward the camera)")
    ax.set_ylabel("elevation (degrees)")
    ax.set_title("(a) A region's light map on the EQ grid (equirectangular)", loc="left")

    ax = axs[1]
    ax.imshow(Ploc, extent=[-ext, ext, -ext, ext], origin="lower", cmap="viridis", interpolation="bilinear")
    ax.contour(GX, GY, Ploc, levels=[t95], colors="white", linewidths=2.0, linestyles="--")
    ax.contour(GX, GY, Ploc, levels=[t68], colors="white", linewidths=2.2)
    for r, ls in ((r68, "-"), (r95, "--")):
        x, y = to_local(small_circle(center, r, 360))
        ax.plot(x, y, color=ORANGE, lw=2.2, ls=ls)
    cx_, cy_ = to_local(center)
    ax.plot(cx_, cy_, "+", color=ORANGE, ms=14, mew=2.5)
    ax.set_xlim(-ext, ext)
    ax.set_ylim(-ext, ext)
    ax.set_xlabel("degrees from the map's peak")
    ax.set_ylabel("degrees from the map's peak")
    ax.set_title("(b) Zoom (angle-preserving view)", loc="left")
    ax.spines["top"].set_visible(True)
    ax.spines["right"].set_visible(True)

    from matplotlib.lines import Line2D
    handles = [Line2D([], [], color="white", lw=2.4, label="68% HPD set (exact)"),
               Line2D([], [], color="white", lw=2.0, ls="--", label="95% HPD set (exact)"),
               Line2D([], [], color=ORANGE, lw=2.4, label=f"68% cone, same solid angle (r = {r68:.0f}°)"),
               Line2D([], [], color=ORANGE, lw=2.2, ls="--", label=f"95% cone, same solid angle (r = {r95:.0f}°)")]
    leg = fig.legend(handles=handles, loc="lower center", ncol=4, frameon=True, bbox_to_anchor=(0.5, -0.04),
                     facecolor="#3A3A3A", edgecolor="none", labelcolor="white", fontsize=10.5)
    leg.get_frame().set_alpha(1.0)

    suptitle(fig, "A cone is a summary: same area as the credible set, but it ignores elongated and "
             "two-lobed shapes", y=1.02)
    fig.text(0.5, -0.1, "Toy landscape (elongated ridge plus a weaker second lobe). Fusion always uses the "
             "full map; cones are only drawn for display and reported as r68/r95.",
             ha="center", fontsize=10, color=MUTED)
    save(fig, "cones_vs_posterior")


# ----------------------------------------------------------------------------
# I6 shortfall diagram
# ----------------------------------------------------------------------------
def fig_shortfall():
    eps = 1e-3
    th = np.arange(-180, 180, 1.0)

    def bump(mu, sig):
        d = (th - mu + 180) % 360 - 180
        return np.exp(-0.5 * (d / sig) ** 2)

    regions = [("car body", 34, 16, BLUE), ("ground", 22, 30, TEAL), ("building", 42, 20, GREEN),
               ("pole", 14, 24, PURPLE), ("pasted object", 150, 18, RED)]
    A = np.array([bump(m, s) for _, m, s, _ in regions])
    wts = np.array([0.9, 0.7, 0.8, 0.6, 0.85])
    logA = np.log(eps + A)
    F_all = (wts[:, None] * logA).sum(0)
    l_all = th[np.argmax(F_all)]
    sk, lstar = [], []
    for k in range(len(regions)):
        m = np.arange(len(regions)) != k
        Fk = (wts[m, None] * logA[m]).sum(0)
        lk = int(np.argmax(Fk))
        lstar.append(th[lk])
        sk.append(-np.log(eps + A[k, lk]))
    sk = np.array(sk)
    tau = 2.0

    fig, axs = plt.subplots(1, 3, figsize=(17, 5.2), gridspec_kw={"width_ratios": [1.15, 1.15, 0.9], "wspace": 0.3})
    ax = axs[0]
    for (name, _, _, col), a in zip(regions, A):
        ax.plot(th, a, color=col, lw=2.2, label=name)
    ax.axvline(l_all, color="#B8860B", lw=1.6, ls="--")
    ax.text(l_all + 3, 1.06, f"consensus of all\n(l* = {l_all:.0f}°)", fontsize=10, color="#8A6D00", va="bottom")
    ax.set_xlim(-180, 180)
    ax.set_ylim(0, 1.32)
    ax.set_xticks(np.arange(-180, 181, 90))
    ax.set_xlabel("light direction (1-D toy, degrees)")
    ax.set_ylabel("agreement A_k(l)")
    ax.set_title("(a) Each region's light map", loc="left")
    ax.legend(loc="upper left", frameon=False, ncol=1, fontsize=10)

    ax = axs[1]
    k = 4
    m = np.arange(len(regions)) != k
    Fk = (wts[m, None] * logA[m]).sum(0)
    cons_k = np.exp((Fk - Fk.max()) / wts[m].sum())
    ax.fill_between(th, cons_k, color=GREY, alpha=0.25, label="others' consensus")
    ax.plot(th, A[k], color=RED, lw=2.4, label="pasted object A_k")
    lk = lstar[k]
    ak = A[k, int(np.argmax(Fk))]
    ax.axvline(lk, color=INK, lw=1.4, ls="--")
    ax.plot([lk], [ak], "o", color=RED, ms=8, zorder=5)
    ax.annotate(f"A_k(l*_-k) = {ak:.1e}\nshortfall s_k = −ln(ε + A_k)\n= {sk[k]:.1f}",
                (lk, ak), (-172, 0.55), fontsize=10.5,
                arrowprops=dict(arrowstyle="-", color=INK, lw=1), va="center", ha="left")
    ax.text(lk + 4, 1.02, f"l*_-k = {lk:.0f}°", ha="left", fontsize=10, va="bottom")
    ax.set_xlim(-180, 180)
    ax.set_ylim(0, 1.32)
    ax.set_xticks(np.arange(-180, 181, 90))
    ax.set_xlabel("light direction (1-D toy, degrees)")
    ax.set_ylabel("agreement")
    ax.set_title("(b) Leave the region out, then ask it", loc="left")
    ax.legend(loc="upper left", frameon=False, fontsize=10)

    ax = axs[2]
    names = [r[0] for r in regions]
    cols = [r[3] for r in regions]
    y = np.arange(len(names))[::-1]
    ax.barh(y, sk, color=cols, edgecolor=INK, height=0.6)
    ax.axvline(tau, color=INK, lw=1.6, ls="--")
    ax.text(tau + 0.15, 1.5, f"alert level τ\n(default {tau:.1f})", fontsize=10, va="center")
    for yy, s in zip(y, sk):
        ax.text(s + 0.1, yy, f"{s:.2f}", va="center", fontsize=10)
    ax.set_yticks(y)
    ax.set_yticklabels(names)
    ax.set_xlim(0, 8.2)
    ax.set_xlabel("leave-one-out shortfall s_k")
    ax.set_title("(c) Only the pasted object\nexceeds the alert level", loc="left")

    suptitle(fig, "Leave-one-out shortfall: how badly does a region fit the light that all other regions agree on?",
             y=1.05)
    fig.text(0.5, -0.05, "Toy 1-D example with ε = 1e-3, so the shortfall is capped at −ln ε ≈ 6.9. "
             "The real computation runs on the 64 × 128 sphere grid with reliability weights w_k.",
             ha="center", fontsize=10, color=MUTED)
    save(fig, "shortfall_diagram")


# ----------------------------------------------------------------------------
# I7 conformal threshold
# ----------------------------------------------------------------------------
def fig_conformal():
    rng = np.random.default_rng(7)
    n, alpha = 200, 0.05
    s_pristine = rng.gamma(2.0, 0.42, n)
    s_edit = np.clip(rng.normal(4.8, 1.3, 400), 0, 6.9)
    k = math.ceil((n + 1) * (1 - alpha))
    tau = np.sort(s_pristine)[k - 1]

    fig, ax = plt.subplots(figsize=(12, 5.4))
    bins = np.linspace(0, 7, 43)
    ax.hist(s_pristine, bins=bins, color=BLUE, alpha=0.85, edgecolor="white", label=f"pristine calibration images (n = {n})")
    ax.hist(s_edit, bins=bins, histtype="step", color=RED, lw=2.0, ls="-",
            weights=np.full(len(s_edit), n / len(s_edit)), label="edited images (for contrast, scaled)")
    ax.axvline(tau, color=INK, lw=2.0, ls="--")
    ymax = ax.get_ylim()[1]
    ax.axvspan(tau, 7, color=RED, alpha=0.06)
    ax.text(tau + 0.08, ymax * 0.97, f"τ = {k}-th smallest of {n} scores\n= ⌈(n+1)(1−α)⌉-th, α = {alpha}",
            fontsize=10.5, va="top")
    ax.text(6.9, ymax * 0.55, "flag:\nsend for\nhuman review", ha="right", fontsize=11, color=RED, va="center")
    ax.text(tau - 0.1, ymax * 0.55, "pass:\nnormal\nprocessing", ha="right", fontsize=11, color=BLUE, va="center")
    ax.set_xlim(0, 7)
    ax.set_xlabel("image score S_img = max leave-one-out shortfall")
    ax.set_ylabel("number of images")
    ax.legend(loc="upper right", frameon=False)
    box = ("Guarantee (split conformal): if a new unedited photo is exchangeable with the calibration\n"
           f"photos, P(S_new > τ) ≤ α = {alpha}. It says nothing about photos from other cameras or scenes\n"
           "(recalibrate on your own unedited photos) and nothing about how often edits are caught.")
    fig.text(0.5, -0.1, box, ha="center", va="center", fontsize=10.5,
             bbox=dict(boxstyle="round,pad=0.6", fc="#F5F5F5", ec=MUTED))
    suptitle(fig, "The alert level τ is a quantile of pristine scores: it bounds false alarms, not misses", y=0.99)
    fig.text(0.5, -0.2, "Illustrative scores drawn from toy distributions (seeded), not results. "
             "Calibrated values are stored in lightaudit/calib_default.json.",
             ha="center", fontsize=10, color=MUTED)
    save(fig, "conformal")


# ----------------------------------------------------------------------------
# I8 attack ladder
# ----------------------------------------------------------------------------
def fig_attack_ladder():
    tiers = [
        ("T0", "Naive paste", "copy the region as is"),
        ("T1", "Colour transfer", "match mean/std of colour\nto the surrounding ring"),
        ("T3a", "Physics re-shade", "estimate scene light, re-shade\nwith fitted tone curve ĝ"),
        ("T4", "Adaptive", "T3a + inpaint glints +\nsearch light using our score"),
    ]
    needs = ["nothing", "colour statistics", "light estimate +\nnormals of the region", "white-box access\nto the detector"]
    # status: 0 = still exposes, 1 = depends / partly, 2 = can be matched, 3 = cue removed
    status = [
        [0, 0, 0],
        [0, 0, 0],
        [1, 0, 1],
        [2, 3, 1],
    ]
    texts = [
        ["still disagrees", "still disagrees", "still disagrees"],
        ["ranks unchanged:\nstill disagrees", "still disagrees", "still disagrees"],
        ["matched if light\nerror < MDI", "glints not moved:\nstill disagrees", "partly re-shaded"],
        ["matched\n(oracle search)", "removed:\nno glint evidence", "partly re-shaded"],
    ]
    cell_col = {0: "#D5E8D0", 1: "#FBE3C6", 2: "#F6CFCF", 3: "#E3E3E3"}
    cols = ["Shading (C1)", "Glints (C2)", "Silhouettes (C3)"]

    fig, ax = plt.subplots(figsize=(16, 7.4))
    ax.set_xlim(0, 100)
    ax.set_ylim(-9, 58.5)
    ax.axis("off")

    x_tier, w_tier = 2, 28
    x_cells = [33, 49, 65]
    w_cell = 15
    x_need, w_need = 82, 16
    row_h = 11
    y0 = 46

    hdr_y = y0 + 6.5
    ax.text(x_tier + w_tier / 2, hdr_y, "Attack tier (forger's edit)", ha="center", fontsize=12, fontweight="bold")
    for xc, cname in zip(x_cells, cols):
        ax.text(xc + w_cell / 2, hdr_y, cname, ha="center", fontsize=12, fontweight="bold")
    ax.text(x_need + w_need / 2, hdr_y, "Forger needs", ha="center", fontsize=12, fontweight="bold")
    ax.text((x_cells[0] + x_cells[-1] + w_cell) / 2, hdr_y + 3.6, "expected state of each cue after the attack",
            ha="center", fontsize=10.5, color=MUTED)

    for r, ((code, name, desc), need) in enumerate(zip(tiers, needs)):
        yb = y0 - r * row_h - row_h / 2 + 0.6
        indent = r * 1.2
        ax.add_patch(FancyBboxPatch((x_tier + indent, yb), w_tier - indent, row_h - 1.2,
                                    boxstyle="round,pad=0,rounding_size=1.0", fc="white", ec=INK, lw=1.4))
        ax.text(x_tier + indent + 1.4, yb + (row_h - 1.2) / 2, code, fontsize=15, fontweight="bold",
                va="center", color=INK)
        ax.text(x_tier + indent + 7.5, yb + (row_h - 1.2) - 2.0, name, fontsize=12, fontweight="bold", va="center")
        ax.text(x_tier + indent + 7.5, yb + 3.1, desc, fontsize=10, va="center", linespacing=1.2)
        for c, xc in enumerate(x_cells):
            st = status[r][c]
            ax.add_patch(FancyBboxPatch((xc, yb), w_cell, row_h - 1.2, boxstyle="round,pad=0,rounding_size=1.0",
                                        fc=cell_col[st], ec="white", lw=1.0))
            ax.text(xc + w_cell / 2, yb + (row_h - 1.2) / 2, texts[r][c], ha="center", va="center", fontsize=10.5,
                    linespacing=1.2)
        ax.text(x_need + w_need / 2, yb + (row_h - 1.2) / 2, need, ha="center", va="center", fontsize=10.5,
                linespacing=1.2)

    # effort arrow
    arrow(ax, (0.6, y0 + 4), (0.6, y0 - 3 * row_h - 4), color=MUTED, lw=2.0)
    ax.text(-0.4, y0 - 1.5 * row_h, "more attacker effort", rotation=90, ha="right", va="center", fontsize=10.5,
            color=MUTED)

    # legend
    lg = [(0, "cue still exposes the edit"), (1, "depends on attacker accuracy / partly"),
          (2, "cue can be matched"), (3, "cue removed (abstains)")]
    for (st, label), x in zip(lg, (4, 26, 56, 76)):
        ax.add_patch(FancyBboxPatch((x, -6.5), 3.0, 3.0, boxstyle="round,pad=0,rounding_size=0.5",
                                    fc=cell_col[st], ec=MUTED, lw=0.8))
        ax.text(x + 4.0, -5.0, label, fontsize=10.5, va="center")
    ax.text(50, -1.0, "Expected behaviour by design; measured detection rates are in experiment E9. "
            "Multiplicative re-shading cannot move specular highlights.", ha="center", fontsize=10, color=MUTED)

    suptitle(fig, "The attack ladder: each tier fixes more cues, but re-shading cannot move the glints", y=0.97)
    save(fig, "attack_ladder")


# ----------------------------------------------------------------------------
# I9 triage
# ----------------------------------------------------------------------------
def fig_triage():
    fig, ax = plt.subplots(figsize=(16, 6.6))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 52)
    ax.axis("off")

    node(ax, 50, 45, 30, 7, "", "", ())
    ax.text(50, 46.3, "LightAudit audit of a claim photo", ha="center", va="center", fontsize=12.5,
            fontweight="bold")
    ax.text(50, 43.4, "regions → light maps → leave-one-out shortfall", ha="center", va="center", fontsize=10.5)

    cards = [
        ("CONSISTENT", "One light explains all\nreliable regions; every\nshortfall ≤ τ.",
         "Normal processing."),
        ("SUSPICIOUS", "One or a few regions\ndisagree with the light the\nothers agree on.",
         "Send to a human adjuster\nwith the evidence view\n(flagged region, dome,\nheatmap)."),
        ("INSUFFICIENT", "Fewer than 3 reliable\nregions, or the consensus\nis too broad (overcast,\nflat, tiny objects).",
         "Ask for a better photo\n(outdoors, direct light,\nseveral objects)."),
        ("CONFLICT", "The reference regions\ndisagree among themselves\n(several lights, bad\ngeometry).",
         "No automatic decision;\nmanual handling."),
    ]
    xs = [13, 37, 61, 85]
    cw, ch = 21.5, 30
    ytop = 37.5
    for x, (v, when, act) in zip(xs, cards):
        col = VERDICT_COLORS[v]
        arrow(ax, (50 + (x - 50) * 0.25, 41.4), (x, ytop + 0.3), color=MUTED, lw=1.5)
        ax.add_patch(FancyBboxPatch((x - cw / 2, ytop - ch), cw, ch, boxstyle="round,pad=0,rounding_size=1.2",
                                    fc="white", ec=col, lw=2.2))
        ax.add_patch(FancyBboxPatch((x - cw / 2, ytop - 5.2), cw, 5.2, boxstyle="round,pad=0,rounding_size=1.2",
                                    fc=col, ec=col, lw=2.2))
        ax.add_patch(Rectangle((x - cw / 2, ytop - 5.2), cw, 2.6, fc=col, ec=col, lw=2.2))
        ax.text(x, ytop - 2.6, v, ha="center", va="center", fontsize=13, fontweight="bold", color="white")
        ax.text(x - cw / 2 + 1.2, ytop - 7.3, "When", fontsize=10.5, fontweight="bold", color=MUTED, va="center")
        ax.text(x - cw / 2 + 1.2, ytop - 9.0, when, fontsize=10.5, va="top", linespacing=1.25)
        ax.plot([x - cw / 2 + 1.2, x + cw / 2 - 1.2], [ytop - 18.6, ytop - 18.6], color=LIGHT, lw=1.2)
        ax.text(x - cw / 2 + 1.2, ytop - 20.3, "Action", fontsize=10.5, fontweight="bold", color=MUTED, va="center")
        ax.text(x - cw / 2 + 1.2, ytop - 22.0, act, fontsize=10.5, va="top", linespacing=1.25, color=INK)

    ax.text(50, 1.2, "A flag means \"send for human review\", never \"this is fraud\". "
            "Lighting consistency is one signal among many.", ha="center", fontsize=11.5, fontweight="bold",
            color=RED)
    suptitle(fig, "Four verdicts, four actions: the tool decides only when the lighting evidence is clear", y=0.98)
    save(fig, "triage")


def main() -> None:
    np.random.seed(0)
    fig_pipeline()
    errs = fig_rank_invariance()
    print("I2 toy errors (LS, rank):", [f"{e:.1f}" for e in errs[0]], [f"{e:.1f}" for e in errs[1]])
    fig_cue_geometry()
    fig_light_dome()
    fig_cones_vs_posterior()
    fig_shortfall()
    fig_conformal()
    fig_attack_ladder()
    fig_triage()


if __name__ == "__main__":
    main()
