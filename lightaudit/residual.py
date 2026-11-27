"""Analysis by synthesis: monotone fit, residual z-score heatmap, counterfactual image (BUILD_SPEC 7.12)."""
from __future__ import annotations

from pathlib import Path

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
    """Panel mode: does the ROI share the light and material of the panel it sits on? Two statistics (see
    panel_shared), both after band-guarded Retinex: panel_Tr = shared material (the panel's light, gain and offset
    must predict the ROI) and panel_T = shared light only (the ROI keeps its own gain and offset, so brightness or
    colour matching of a pasted area cannot hide it). This pair was the best of the combinations compared on real
    objects at matched false-alarm rates (eval/mit_attack.py). roi["panel_z"] = the larger of the two divided by
    its calibrated alert level (so the alert level of panel_z is 1). None where it cannot be computed."""
    roi = next((r for r in regions if r["name"] == "ROI"), None)
    if roi is None:
        return
    roi["panel_T"] = panel_shared(Y, normals, unc, labels, regions, cfg, retinex=True, thr=cfg.retinex_thr, band=cfg.panel_band,
                                  shape_only=True)
    roi["panel_Tr"] = panel_shared(Y, normals, unc, labels, regions, cfg, retinex=True, thr=cfg.retinex_thr, band=cfg.panel_band)
    roi["panel_S"] = seam_S(Y, labels, regions, cfg)
    roi["panel_z"] = panel_ratio(roi, cfg)


def panel_ratio(r: dict, cfg: Config):
    v = [t / tau for t, tau in ((r.get("panel_T"), cfg.tau_panel_T), (r.get("panel_Tr"), cfg.tau_panel_Tr),
                                (r.get("panel_S"), cfg.tau_panel_S)) if t is not None]
    return float(max(v)) if v else None


def seam_S(Y, labels, regions: list[dict], cfg: Config = Config(), gap: int = 2, width: int = 6, sectors: int = 24,
           min_px: int = 8, y_min: float = 0.02):
    """Normal-free seam statistic (docs/designs/seam_test.md). The ROI lies on the same continuous surface as the
    panel, so the log-brightness jump across its boundary may be a constant (paint, or a forger's gain) but must
    not change round the boundary; a paste from another light makes it change. Per angular sector, each side is
    fitted as L = c + m * signed distance on the band gap..gap+width px from the boundary (skips feathering) and
    extrapolated to it. S = median |jump - median jump| over sectors; None if under half the sectors are usable."""
    from scipy import ndimage as ndi
    roi = next((r for r in regions if r["name"] == "ROI"), None)
    ring = next((r for r in regions if r["name"] == "ring"), None)
    rest = next((r for r in regions if r["name"].endswith("(rest)")), None)
    if roi is None or ring is None or rest is None:
        return None
    m_roi = labels == roi["id"]
    if not m_roi.any():
        return None
    outside = ((labels == ring["id"]) | (labels == rest["id"])) & ~m_roi
    din, (jy, jx) = ndi.distance_transform_edt(m_roi, return_indices=True)
    dout, (iy, ix) = ndi.distance_transform_edt(~m_roi, return_indices=True)
    sd = np.where(m_roi, 0.5 - din, dout - 0.5)
    cy, cx = np.argwhere(m_roi).mean(0)
    # both sides take the angle of their nearest boundary point, so a sector holds one stretch of the seam
    th = np.arctan2(np.where(m_roi, jy, iy) - cy, np.where(m_roi, jx, ix) - cx)
    sec = np.clip(((th + np.pi) / (2 * np.pi) * sectors).astype(int), 0, sectors - 1)
    band = (np.abs(sd) >= gap) & (np.abs(sd) <= gap + width) & (Y > y_min)
    L = np.log(np.maximum(Y.astype(np.float64) ** 2.2, 1e-3))
    jumps = []
    for k in range(sectors):
        c = []
        for side in (m_roi, outside):
            m = band & side & (sec == k)
            if m.sum() < min_px:
                break
            c.append(np.linalg.lstsq(np.c_[np.ones(m.sum()), sd[m]], L[m], rcond=None)[0][0])
        if len(c) == 2:
            jumps.append(c[0] - c[1])
    if len(jumps) < sectors // 2:
        return None
    j = np.array(jumps)
    return float(np.median(np.abs(j - np.median(j))))


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


_IID = {}


def learned_albedo(lin: np.ndarray) -> np.ndarray:
    """Albedo from the learned intrinsic decomposition of Careaga & Aksoy (TOG 2023/2024, package `intrinsic`,
    academic use), grayscale stage: albedo = image / predicted shading. Only stages 0-1 of the v2.1 weights are
    needed (torch hub cache). lin: (H, W) linear luminance. Raises ImportError if the package is missing."""
    import torch
    from intrinsic.pipeline import load_models, run_gray_pipeline
    if "m" not in _IID:
        ck = Path(torch.hub.get_dir()) / "checkpoints"
        files = [ck / "stage_0_v21.pt", ck / "stage_1_v21.pt"]
        if all(f.exists() for f in files):
            orig = torch.load  # the package's local-file path calls torch.load without map_location (CUDA tensors)
            torch.load = lambda f, *a, **k: orig(f, *a, **{**k, "map_location": "cpu"})
            try:
                _IID["m"] = load_models([str(f) for f in files], stage=1, device="cpu")
            finally:
                torch.load = orig
        else:
            _IID["m"] = load_models("v2.1", stage=1, device="cpu")
    img = np.repeat(np.clip(lin, 0, 1)[..., None], 3, 2).astype(np.float32)
    # 512 px working size: 0.93 correlation with true paint on a MIT object vs 0.91 at full size, 2x faster
    r = run_gray_pipeline(_IID["m"], img, resize_conf=512, maintain_size=True, linear=True, device="cpu")
    shd = 1.0 / np.maximum(r["gry_shd"], 1e-3) - 1.0  # the network predicts inverse shading
    return np.clip(lin, 1e-4, None) / np.maximum(shd, 1e-4)


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


def shared_light_T(S_ref, y_ref, S_roi, y_roi) -> float:
    """Shape-only variant of shared_material_T: the test pixels must follow the reference's LIGHT, but with their
    own gain and offset. Unchanged by any affine brightness change of the test area (colour / brightness
    matching), at the price of ignoring gain mismatches."""
    j = fit_light(S_ref, y_ref)[0]
    rss = fit_light(S_roi, y_roi)[3]
    return float(np.log(max(float(rss[j]), 1e-12) / max(float(rss.min()), 1e-12)))


def shared_material_T(S_ref, y_ref, S_roi, y_roi) -> float:
    """Shared-material statistic: one shading model (light, gain, offset) is fitted on the reference pixels and
    used to predict the test pixels; T = log(RSS of that prediction / RSS of the test pixels' own best fit).
    Near 0 when the test area shares the reference's light and material, large when it does not."""
    j, a, b, _ = fit_light(S_ref, y_ref)
    r = y_roi - (a * S_roi[j] + b)
    own = fit_light(S_roi, y_roi)[3]
    return float(np.log(max(float(r @ r), 1e-12) / max(float(own.min()), 1e-12)))


def panel_shared(Y, normals, unc, labels, regions: list[dict], cfg: Config = Config(), retinex: bool = True,
                 thr: float = 0.10, max_px: int = 4000, blur: float = 0.0, band: int = 4, shape_only: bool = False,
                 alb_map: np.ndarray | None = None):
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
    if alb_map is not None:  # precomputed albedo (e.g. learned_albedo), used instead of Retinex
        alb = np.where(panel, alb_map / max(float(np.median(alb_map[panel])), 1e-9), 1.0)
    else:
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
    fn = shared_light_T if shape_only else shared_material_T
    return fn(S_ref, lin[ys, xs] / alb[ys, xs], S_roi, lin[rys, rxs] / alb[rys, rxs])


def shadow_levels(Y, normals, mask, cfg: Config = Config()):
    """Cast-shadow levels on a large flat region (typically the ground), or None if the region does not qualify.

    A flat surface has one normal, so its brightness varies only with albedo and cast shadows. Under one sun all
    cast shadows share one darkness level; under two suns each object casts two half-shadows (each blocks one sun)
    at two different levels. Returns the share of shadow pixels (darker than 0.75 x the median) that are brighter
    than 1.35 x the darkest shadow level (the 10th percentile of the shadow pixels)."""
    if mask.sum() < cfg.flat_min_frac * mask.size:
        return None
    m = normals[mask].mean(0)
    if float(np.linalg.norm(m)) < cfg.flat_min_R:
        return None
    yl = Y[mask & (Y < cfg.sat_hi)] ** 2.2
    if len(yl) < 2000:
        return None
    med = float(np.median(yl))
    dark = yl[yl < 0.75 * med]
    if len(dark) < 200:
        return None
    return float((dark > 1.35 * np.percentile(dark, 10)).mean())
