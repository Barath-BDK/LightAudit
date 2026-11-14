"""Cue C3: silhouette / occluding contour (BUILD_SPEC 7.9). Needs no neural network for the normals it uses:
at a true occluding contour the normal lies in the image plane, n = (cos phi, sin phi, 0)."""
from __future__ import annotations

import cv2
import numpy as np

from ..config import Config
from ..grid import eq_dirs
from .rank_shading import rank_landscape


def contour_pixels(Y, normals, mask, cfg: Config):
    """(ys, xs, geometric normals) for boundary-band pixels where the predicted normal is grazing too."""
    m = cv2.copyMakeBorder(mask.astype(np.uint8), 1, 1, 1, 1, cv2.BORDER_CONSTANT, value=0)
    dist = cv2.distanceTransform(m, cv2.DIST_L2, 5)[1:-1, 1:-1]
    gx = cv2.Sobel(dist, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(dist, cv2.CV_32F, 0, 1, ksize=3)
    mag = np.hypot(gx, gy)
    lo, hi = cfg.band_px
    band = (dist >= lo) & (dist <= hi) & (normals[..., 2] < cfg.contour_nz_max) & (mag > 4.0)  # Sobel gain is 8
    band &= (Y <= cfg.sat_hi) & (Y >= cfg.dark_lo)
    ys, xs = np.nonzero(band)
    # distance grows inward, so outward = -grad; image v points down, camera y up
    n = np.stack([-gx[ys, xs] / mag[ys, xs], gy[ys, xs] / mag[ys, xs], np.zeros(len(ys), np.float32)], 1)
    return ys, xs, n


def contour_landscape(Y, normals, mask, cfg: Config) -> np.ndarray | None:
    """A ridge-shaped map in [0,1] (the depth component of the light is unconstrained), or None if no cue."""
    ys, xs, n = contour_pixels(Y, normals, mask, cfg)
    if len(ys) < cfg.contour_min_px:
        return None
    if len(ys) > 800:
        pick = np.random.default_rng(len(ys)).choice(len(ys), 800, replace=False)
        ys, xs, n = ys[pick], xs[pick], n[pick]
    S = rank_landscape(n, Y[ys, xs], eq_dirs())
    if S.max() < cfg.contour_min_rho:
        return None
    return np.exp(-(S.max() - S) / cfg.contour_kappa).astype(np.float32)
