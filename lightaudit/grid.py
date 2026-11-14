"""The one canonical equirectangular direction grid (BUILD_SPEC 5.2). Mirrored in viewer/grid.js."""
from __future__ import annotations

from functools import lru_cache

import numpy as np

NA, NE = 128, 64
D = NA * NE


@lru_cache(maxsize=None)
def eq_dirs() -> np.ndarray:
    """(8192, 3) float32 unit vectors, index k = j*128 + i."""
    i = np.arange(NA)
    j = np.arange(NE)
    az = -np.pi + (i + 0.5) * 2 * np.pi / NA
    lat = np.pi / 2 - (j + 0.5) * np.pi / NE
    az, lat = np.meshgrid(az, lat)  # [NE, NA]
    d = np.stack([np.cos(lat) * np.sin(az), np.sin(lat), np.cos(lat) * np.cos(az)], -1)
    d = d.reshape(-1, 3).astype(np.float32)
    d.setflags(write=False)
    return d


@lru_cache(maxsize=None)
def area_weights() -> np.ndarray:
    """(8192,) solid-angle weight per cell, sums to 1."""
    lat = np.pi / 2 - (np.arange(NE) + 0.5) * np.pi / NE
    w = np.repeat(np.cos(lat), NA)
    w = (w / w.sum()).astype(np.float64)
    w.setflags(write=False)
    return w


def dir_to_cell(d) -> tuple[int, int]:
    d = np.asarray(d, np.float64)
    d = d / np.linalg.norm(d)
    az = np.arctan2(d[0], d[2])
    lat = np.arcsin(np.clip(d[1], -1, 1))
    i = int(np.floor((az + np.pi) / (2 * np.pi) * NA)) % NA
    j = int(np.clip(np.floor((np.pi / 2 - lat) / np.pi * NE), 0, NE - 1))
    return j, i


def dir_to_index(d) -> int:
    j, i = dir_to_cell(d)
    return j * NA + i


@lru_cache(maxsize=None)
def coarse_index(step: int = 4) -> np.ndarray:
    """Every `step`-th cell in both axes (16 x 32 = 512 for step 4), as fine-grid flat indices."""
    j = np.arange(step // 2, NE, step)
    i = np.arange(step // 2, NA, step)
    return (j[:, None] * NA + i[None, :]).ravel()


def window_index(k: int, hw: int = 6) -> np.ndarray:
    """Fine cells within +-hw of cell k (wraps in azimuth, clips in elevation)."""
    j, i = divmod(int(k), NA)
    jj = np.arange(max(0, j - hw), min(NE, j + hw + 1))
    ii = np.arange(i - hw, i + hw + 1) % NA
    return (jj[:, None] * NA + ii[None, :]).ravel()


def angle_deg(a, b) -> np.ndarray:
    a = np.asarray(a, np.float64)
    b = np.asarray(b, np.float64)
    a = a / np.linalg.norm(a, axis=-1, keepdims=True)
    b = b / np.linalg.norm(b, axis=-1, keepdims=True)
    return np.degrees(np.arccos(np.clip((a * b).sum(-1), -1, 1)))


def az_el_deg(d) -> tuple[float, float]:
    """Azimuth clockwise from the camera direction seen from above (atan2(x, z)), elevation asin(y)."""
    d = np.asarray(d, np.float64)
    d = d / np.linalg.norm(d)
    return float(np.degrees(np.arctan2(d[0], d[2]))), float(np.degrees(np.arcsin(np.clip(d[1], -1, 1))))


def from_az_el_deg(az: float, el: float) -> np.ndarray:
    az, el = np.radians(az), np.radians(el)
    return np.array([np.cos(el) * np.sin(az), np.sin(el), np.cos(el) * np.cos(az)])


def hpd(P: np.ndarray, levels=(0.68, 0.95)):
    """Highest-density sets of a non-negative map on the grid.

    Returns (fracs, masks): fraction of the sphere covered by each level's set and the boolean masks.
    """
    P = np.asarray(P, np.float64).ravel()
    mass = P * area_weights()
    tot = mass.sum()
    order = np.argsort(-P, kind="stable")
    cum = np.cumsum(mass[order]) / (tot if tot > 0 else 1.0)
    aw = area_weights()[order]
    fracs, masks = [], []
    for lv in levels:
        n = int(np.searchsorted(cum, lv - 1e-12)) + 1
        n = min(n, D)
        m = np.zeros(D, bool)
        m[order[:n]] = True
        fracs.append(float(aw[:n].sum()))
        masks.append(m)
    return fracs, masks


def cone_half_angle_deg(frac: float) -> float:
    """Half-angle of the cone with the same solid angle as a set covering `frac` of the sphere."""
    return float(np.degrees(np.arccos(np.clip(1 - 2 * frac, -1, 1))))


def view_vectors(H: int, W: int, fov_deg: float = 60.0) -> np.ndarray:
    """(H, W, 3) unit vectors from each pixel's surface point toward the camera (BUILD_SPEC 5.1)."""
    f = (W / 2) / np.tan(np.radians(fov_deg) / 2)
    u, v = np.meshgrid(np.arange(W) + 0.5, np.arange(H) + 0.5)
    d = np.stack([(u - W / 2) / f, -(v - H / 2) / f, -np.ones_like(u)], -1)
    d /= np.linalg.norm(d, axis=-1, keepdims=True)
    return (-d).astype(np.float32)
