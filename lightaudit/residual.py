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
