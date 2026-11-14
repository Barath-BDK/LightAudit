"""Cue C1: tone-curve-invariant rank shading (BUILD_SPEC 7.5).

Model: Y_i = g(max(0, n_i . l)) with an unknown monotone g. S(l) = Spearman correlation between
max(0, n.l) and Y, with every attached-shadow pixel (n.l <= 0) tied at the mean rank of that group.
"""
from __future__ import annotations

import numpy as np
from scipy.stats import rankdata


def _pearson_rows(X: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Pearson correlation of every row of X (d, N) with the centred, unit-norm vector y (N,)."""
    X = X - X.mean(1, keepdims=True)
    den = np.linalg.norm(X, axis=1)
    return np.where(den > 1e-6, (X @ y) / np.maximum(den, 1e-6), 0.0)


def _unit(y: np.ndarray) -> np.ndarray:
    y = y.astype(np.float32) - np.float32(y.mean())
    return y / max(float(np.linalg.norm(y)), 1e-6)


def rank_landscape(normals: np.ndarray, Y: np.ndarray, dirs: np.ndarray, chunk: int = 1024) -> np.ndarray:
    """S (D,) for normals (N,3), luminance Y (N,), candidate lights dirs (D,3)."""
    normals = np.ascontiguousarray(normals, np.float32)
    N = len(Y)
    ry = _unit(rankdata(Y))
    ar = np.arange(N, dtype=np.float32)[None, :]
    out = np.empty(len(dirs), np.float32)
    for a in range(0, len(dirs), chunk):
        s = np.asarray(dirs[a:a + chunk], np.float32) @ normals.T  # (d, N)
        neg = s <= 0
        z = neg.sum(1, keepdims=True).astype(np.float32)
        order = np.argsort(s, axis=1)  # shadowed pixels sort first, so lit pixels get ranks z..N-1
        ranks = np.empty_like(s)
        np.put_along_axis(ranks, order, ar, axis=1)
        ranks = np.where(neg, (z - 1) / 2, ranks)  # zero-tie group at its mean rank
        out[a:a + chunk] = _pearson_rows(ranks, ry)
    return out
