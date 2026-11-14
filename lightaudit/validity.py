"""Pixel validity filtering and stratified subsampling (BUILD_SPEC 7.2)."""
from __future__ import annotations

import cv2
import numpy as np

from .config import Config


def erode_px(H: int, W: int, cfg: Config) -> int:
    return max(3, round(cfg.erode_px_frac * min(H, W)))


def erode(mask: np.ndarray, px: int) -> np.ndarray:
    """Binary erosion that also erodes from the image border."""
    m = cv2.copyMakeBorder(mask.astype(np.uint8), px, px, px, px, cv2.BORDER_CONSTANT, value=0)
    return cv2.erode(m, np.ones((2 * px + 1, 2 * px + 1), np.uint8))[px:-px, px:-px].astype(bool)


def valid_mask(Y, normals, unc, mask, cfg: Config) -> np.ndarray:
    H, W = Y.shape
    return (erode(mask, erode_px(H, W, cfg)) & (Y <= cfg.sat_hi) & (Y >= cfg.dark_lo)
            & (normals[..., 2] >= cfg.nz_min) & (unc <= cfg.unc_max))


def valid_pixels(Y, normals, unc, mask, cfg: Config, seed: int):
    """Returns (ys, xs, n_valid): coordinates of at most Nmax valid pixels (stratified in space) and the full count."""
    ys, xs = np.nonzero(valid_mask(Y, normals, unc, mask, cfg))
    n = len(ys)
    if n > cfg.Nmax:
        rng = np.random.default_rng(seed)
        c = int(np.ceil(np.sqrt(n / cfg.Nmax)))
        perm = rng.permutation(n)
        key = (ys[perm] // c) * (xs.max() // c + 1) + xs[perm] // c
        _, first = np.unique(key, return_index=True)  # one random pixel per grid cell
        pick = perm[first]
        if len(pick) > cfg.Nmax:
            pick = rng.choice(pick, cfg.Nmax, replace=False)
        pick.sort()
        ys, xs = ys[pick], xs[pick]
    return ys, xs, n
