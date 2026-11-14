"""Cue C4 (experimental): manual cast-shadow pairs (BUILD_SPEC 7.8). Mirrored in viewer/shadow_tool.js.

For a directional light, object point p, its shadow point s and the camera centre span a plane that contains
the light direction. With unit pixel rays r(p), r(s) (pointing from the camera into the scene) the plane normal is
m = normalize(r(p) x r(s)); a candidate light l fits when l . m = 0. This is the same constraint as "the image
line through p and s passes through the vanishing point of l", but stays finite when l is parallel to the image
plane. Sign: the shadow lies further along -l, so the image motion p -> s must follow the projection of -l.
"""
from __future__ import annotations

import numpy as np

from ..config import Config
from ..grid import eq_dirs


def pixel_ray(u: float, v: float, H: int, W: int, fov_deg: float) -> np.ndarray:
    f = (W / 2) / np.tan(np.radians(fov_deg) / 2)
    d = np.array([(u - W / 2) / f, -(v - H / 2) / f, -1.0])
    return d / np.linalg.norm(d)


def shadow_landscape(pairs, H: int, W: int, fov_deg: float = 60.0, cfg: Config = Config()) -> np.ndarray | None:
    """pairs = [((pu, pv), (su, sv)), ...] in pixels; needs >= 2 pairs. Returns a [0,1] map on the EQ grid."""
    if len(pairs) < 2:
        return None
    L = eq_dirs().astype(np.float64)
    r2 = np.zeros(len(L))
    ok = np.ones(len(L), bool)
    for (pu, pv), (su, sv) in pairs:
        rp, rs = pixel_ray(pu, pv, H, W, fov_deg), pixel_ray(su, sv, H, W, fov_deg)
        m = np.cross(rp, rs)
        m /= max(np.linalg.norm(m), 1e-9)
        sig = cfg.shadow_sigma_px / max(np.hypot(su - pu, sv - pv), 1.0)  # angular tolerance of the line (rad)
        r2 += (np.arcsin(np.clip(np.abs(L @ m), 0, 1)) / sig) ** 2
        ok &= (-(L - np.outer(L @ rp, rp)) @ (rs - rp)) > 0
    A = np.exp(-r2 / 2) * np.where(ok, 1.0, 0.0)
    return (A / A.max()).astype(np.float32) if A.max() > 0 else None
