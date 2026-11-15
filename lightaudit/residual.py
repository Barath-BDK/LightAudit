"""Analysis by synthesis: monotone fit, residual z-score heatmap, counterfactual image (BUILD_SPEC 7.12)."""
from __future__ import annotations

import numpy as np
from sklearn.isotonic import IsotonicRegression

from .config import Config


def fit_g(s_valid: np.ndarray, Y_valid: np.ndarray, cfg: Config = Config()) -> np.ndarray:
    """Isotonic fit of Y against s = max(0, n.l), exported as a monotone LUT with Klut knots on s in [0, 1]."""
    knots = np.linspace(0, 1, cfg.Klut)
    if len(s_valid) < 3:
        return np.full(cfg.Klut, float(np.mean(Y_valid)) if len(Y_valid) else 0.5, np.float32)
    iso = IsotonicRegression(increasing=True, out_of_bounds="clip").fit(s_valid, Y_valid)
    return np.maximum.accumulate(iso.predict(knots)).astype(np.float32)


def apply_g(lut: np.ndarray, s: np.ndarray) -> np.ndarray:
    return np.interp(s, np.linspace(0, 1, len(lut)), lut).astype(np.float32)


def region_residual(Y, normals, unc, mask, ys, xs, l_ref, cfg: Config = Config()) -> dict:
    """Fit on the valid pixels (ys, xs); evaluate on all pixels of `mask`. Returns g_lut, sigma, slope, Yhat, z."""
    l = np.asarray(l_ref, np.float32)
    lut = fit_g(np.maximum(normals[ys, xs] @ l, 0), Y[ys, xs], cfg)
    Yhat = apply_g(lut, np.maximum(normals[mask] @ l, 0))
    r_valid = Y[ys, xs] - apply_g(lut, np.maximum(normals[ys, xs] @ l, 0))
    mad = float(np.median(np.abs(r_valid - np.median(r_valid)))) if len(r_valid) else 0.0
    sigma = max(cfg.sigma_min, 1.4826 * mad)
    slope = float(lut[-1] - lut[0])
    z = np.abs(Y[mask] - Yhat) / np.sqrt(sigma ** 2 + (slope * np.radians(unc[mask])) ** 2)
    return dict(g_lut=lut, sigma=float(sigma), slope=slope, Yhat=Yhat, z=z.astype(np.float32))


def residual_maps(rgb, Y, normals, unc, regions: list[dict], cfg: Config = Config()):
    """regions: dicts with mask, ys, xs, l_ref (or None to skip). Adds g_lut/sigma/slope to each region and
    returns (heat uint8, counterfactual uint8)."""
    heat = np.zeros(Y.shape, np.uint8)
    cf = rgb.astype(np.float32) / 255
    for r in regions:
        if r.get("l_ref") is None or len(r["ys"]) < 10:
            r.update(g_lut=np.linspace(0, 1, cfg.Klut, dtype=np.float32), sigma=cfg.sigma_min, slope=1.0)
            continue
        out = region_residual(Y, normals, unc, r["mask"], r["ys"], r["xs"], r["l_ref"], cfg)
        r.update(g_lut=out["g_lut"], sigma=out["sigma"], slope=out["slope"])
        heat[r["mask"]] = np.round(np.clip(out["z"] / 4, 0, 1) * 255)
        cf[r["mask"]] *= ((out["Yhat"] + 0.01) / (Y[r["mask"]] + 0.01))[:, None]
    return heat, np.round(np.clip(cf, 0, 1) * 255).astype(np.uint8)


def panel_score(Y, normals, unc, labels, regions: list[dict], cfg: Config = Config()) -> None:
    """Panel mode: does the ROI share the light and material of the panel it sits on? Two shared-material
    statistics (see panel_shared) are computed, without albedo handling and with boundary-guarded Retinex; the
    first is the stronger one on uniformly painted surfaces, the second on painted / patterned ones (measured on
    synthetic damage scenes and on the MIT Intrinsic Images objects). Sets roi["panel_T"], roi["panel_Tr"] and
    roi["panel_z"] = the larger of the two divided by its calibrated alert level (so the alert level of panel_z
    is 1). None where it cannot be computed."""
    roi = next((r for r in regions if r["name"] == "ROI"), None)
    if roi is None:
        return
    roi["panel_T"] = panel_shared(Y, normals, unc, labels, regions, cfg, retinex=False)
    roi["panel_Tr"] = panel_shared(Y, normals, unc, labels, regions, cfg, retinex=True, thr=cfg.retinex_thr, band=cfg.panel_band)
    roi["panel_z"] = panel_ratio(roi, cfg)


def panel_ratio(r: dict, cfg: Config):
    v = [t / tau for t, tau in ((r.get("panel_T"), cfg.tau_panel_T), (r.get("panel_Tr"), cfg.tau_panel_Tr)) if t is not None]
    return float(max(v)) if v else None


def retinex_albedo(lin: np.ndarray, mask: np.ndarray, thr: float = 0.10, lab=None, blur: float = 0.0,
                   band: int = 0) -> np.ndarray:
    """Single-image albedo by Retinex: large gradients of the log image are attributed to reflectance, small ones
    to shading; the reflectance gradients are integrated with a Poisson solve (DCT, Neumann boundary).

    lab: label map of known boundaries (the area under test). A step across such a boundary is never attributed
    to reflectance; without this guard Retinex explains a pasted region's brightness step as paint and hides it.
    Returns albedo with median 1 inside the mask (1 outside)."""
    from scipy.fft import dctn, idctn
    if blur > 0:  # masked Gaussian smoothing first, so camera noise and JPEG blocks are not read as paint edges
        import cv2
        m = mask.astype(np.float32)
        lin = cv2.GaussianBlur(lin.astype(np.float32) * m, (0, 0), blur) / np.maximum(cv2.GaussianBlur(m, (0, 0), blur), 1e-3)
    L = np.where(mask, np.log(np.maximum(lin, 1e-3)), 0.0)
    gx, gy = np.zeros_like(L), np.zeros_like(L)
    gx[:, :-1] = L[:, 1:] - L[:, :-1]
    gy[:-1, :] = L[1:, :] - L[:-1, :]
    inx, iny = np.zeros_like(mask), np.zeros_like(mask)
    inx[:, :-1] = mask[:, 1:] & mask[:, :-1]
    iny[:-1, :] = mask[1:, :] & mask[:-1, :]
    if lab is not None:
        inx[:, :-1] &= lab[:, 1:] == lab[:, :-1]
        iny[:-1, :] &= lab[1:, :] == lab[:-1, :]
        if band > 0:  # pasted regions are feathered: guard a band of `band` pixels on both sides of the boundary
            import cv2
            edge = np.zeros(mask.shape, np.uint8)
            edge[:, :-1] |= (lab[:, 1:] != lab[:, :-1]).astype(np.uint8)
            edge[:-1, :] |= (lab[1:, :] != lab[:-1, :]).astype(np.uint8)
            near = cv2.dilate(edge, np.ones((2 * band + 1,) * 2, np.uint8)).astype(bool)
            inx[:, :-1] &= ~(near[:, 1:] | near[:, :-1])
            iny[:-1, :] &= ~(near[1:, :] | near[:-1, :])
    gx = np.where(inx & (np.abs(gx) > thr), gx, 0.0)
    gy = np.where(iny & (np.abs(gy) > thr), gy, 0.0)
    div = gx.copy()
    div[:, 1:] -= gx[:, :-1]
    div += gy
    div[1:, :] -= gy[:-1, :]
    H, W = L.shape
    den = (2 * np.cos(np.pi * np.arange(H) / H) - 2)[:, None] + (2 * np.cos(np.pi * np.arange(W) / W) - 2)[None, :]
    den[0, 0] = 1.0
    r = dctn(div, norm="ortho") / den
    r[0, 0] = 0.0
    r = idctn(r, norm="ortho")
    return np.where(mask, np.exp(r - np.median(r[mask])), 1.0)


def fit_light(S: np.ndarray, y: np.ndarray):
    """Best light for y ~ a * s + b with a >= 0 over the directions in S (D, N): (index, a, b, rss per direction)."""
    n = len(y)
    A, B, SY, Ys = S.sum(1), (S * S).sum(1), S @ y, y.sum()
    var = B - A * A / n
    cov = SY - A * Ys / n
    gain = np.where((var > 1e-9) & (cov > 0), cov / np.maximum(var, 1e-9), 0.0)
    rss = (y @ y - Ys * Ys / n) - gain * cov
    j = int(np.argmin(rss))
    return j, float(gain[j]), float((Ys - gain[j] * A[j]) / n), rss


def shared_material_T(S_ref, y_ref, S_roi, y_roi) -> float:
    """Shared-material statistic: one shading model (light, gain, offset) is fitted on the reference pixels and
    used to predict the test pixels; T = log(RSS of that prediction / RSS of the test pixels' own best fit).
    Near 0 when the test area shares the reference's light and material, large when it does not."""
    j, a, b, _ = fit_light(S_ref, y_ref)
    r = y_roi - (a * S_roi[j] + b)
    own = fit_light(S_roi, y_roi)[3]
    return float(np.log(max(float(r @ r), 1e-12) / max(float(own.min()), 1e-12)))


def panel_shared(Y, normals, unc, labels, regions: list[dict], cfg: Config = Config(), retinex: bool = True,
                 thr: float = 0.10, max_px: int = 4000, blur: float = 0.0, band: int = 4):
    """Panel mode, shared-material test (validated on real curved objects, eval/mit_bench.py): the ROI must be
    predicted by the ONE shading model (light, gain, offset) fitted on the ring and the panel remainder.
    Albedo is removed first by Retinex, guarded so that a step across the ROI boundary is never called paint.
    Returns T = log(RSS shared / RSS own) or None if it cannot be computed."""
    from .grid import coarse_index, eq_dirs
    from .validity import erode, erode_px, valid_mask
    roi = next((r for r in regions if r["name"] == "ROI"), None)
    ring = next((r for r in regions if r["name"] == "ring"), None)
    rest = next((r for r in regions if r["name"].endswith("(rest)")), None)
    if roi is None or ring is None or rest is None:
        return None
    lin = Y.astype(np.float64) ** 2.2
    m_roi = labels == roi["id"]
    panel = m_roi | (labels == ring["id"]) | (labels == rest["id"])
    alb = retinex_albedo(lin, panel, thr, m_roi.astype(np.int8), blur, band) if retinex else np.ones_like(lin)
    rys, rxs = np.nonzero(erode(m_roi, erode_px(*Y.shape, cfg)) & (normals[..., 2] >= cfg.nz_min) & (unc <= cfg.unc_max))
    ys, xs = np.nonzero(valid_mask(Y, normals, unc, panel & ~m_roi, cfg))
    if len(rys) < cfg.panel_min_px or len(ys) < 4 * cfg.panel_min_px:
        return None
    rng = np.random.default_rng(0)
    if len(ys) > max_px:
        pick = rng.choice(len(ys), max_px, replace=False)
        ys, xs = ys[pick], xs[pick]
    if len(rys) > max_px:
        pick = rng.choice(len(rys), max_px, replace=False)
        rys, rxs = rys[pick], rxs[pick]
    dirs = eq_dirs()[coarse_index(cfg.coarse_step)].astype(np.float64)
    S_ref = np.maximum(dirs @ normals[ys, xs].T.astype(np.float64), 0)
    S_roi = np.maximum(dirs @ normals[rys, rxs].T.astype(np.float64), 0)
    return shared_material_T(S_ref, lin[ys, xs] / alb[ys, xs], S_roi, lin[rys, rxs] / alb[rys, rxs])
