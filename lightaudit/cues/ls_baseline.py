"""Baseline cue (BUILD_SPEC 7.13): linear-radiometry least squares, plugged into the same posterior machinery.

Landscape S(l) = Pearson(Y^2.2, max(0, n.l)): the "assume gamma 2.2 and a linear Lambert fit" approach.
"""
from __future__ import annotations

import numpy as np

from .rank_shading import _pearson_rows, _unit


def ls_landscape(normals: np.ndarray, Y: np.ndarray, dirs: np.ndarray) -> np.ndarray:
    y = _unit(np.asarray(Y, np.float32) ** 2.2)
    s = np.maximum(np.asarray(dirs, np.float32) @ np.ascontiguousarray(normals, np.float32).T, 0)
    return _pearson_rows(s, y).astype(np.float32)


def ls_direction(normals: np.ndarray, Y: np.ndarray) -> np.ndarray:
    """Closed-form variant: Y_lin ~ a + L.n, light = L/|L| (used in tests / illustrations)."""
    A = np.c_[np.ones(len(Y)), normals]
    L = np.linalg.lstsq(A, np.asarray(Y, np.float64) ** 2.2, rcond=None)[0][1:]
    return L / max(np.linalg.norm(L), 1e-9)
