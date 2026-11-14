"""Signed distance primitives. A scene is a list of prim dicts; `scene_sdf` returns distance + prim index.

Prim dict keys: type, pos (world xyz), yaw (rad, about +y), obj (object id), plus per-type params:
  plane | sphere(r) | rbox(b, r) | cyl(axis 'y'|'z', r, h) | bush(r, k)
  optional dent=(cx, cy, cz, depth, sigma) in the prim's local frame; step = safe-step factor (<1 for inexact SDFs).
"""
from __future__ import annotations

import numpy as np


def to_local(p: np.ndarray, prim: dict) -> np.ndarray:
    d = p - np.asarray(prim["pos"], np.float32)
    yaw = prim.get("yaw", 0.0)
    if yaw == 0.0:
        return d
    c, s = np.float32(np.cos(yaw)), np.float32(np.sin(yaw))
    return np.stack([c * d[:, 0] - s * d[:, 2], d[:, 1], s * d[:, 0] + c * d[:, 2]], 1)


def prim_sdf(p: np.ndarray, prim: dict) -> np.ndarray:
    t = prim["type"]
    if t == "plane":
        return p[:, 1].copy()
    q = to_local(p, prim)
    if t == "sphere":
        d = np.linalg.norm(q, axis=1) - prim["r"]
    elif t == "rbox":
        a = np.abs(q) - (np.asarray(prim["b"], np.float32) - prim["r"])
        d = np.linalg.norm(np.maximum(a, 0), axis=1) + np.minimum(a.max(1), 0) - prim["r"]
    elif t == "cyl":
        ax = 1 if prim["axis"] == "y" else 2
        o = [i for i in range(3) if i != ax]
        dr = np.hypot(q[:, o[0]], q[:, o[1]]) - (prim["r"] - 0.02)
        dh = np.abs(q[:, ax]) - (prim["h"] - 0.02)
        d = np.minimum(np.maximum(dr, dh), 0) + np.hypot(np.maximum(dr, 0), np.maximum(dh, 0)) - 0.02
    elif t == "bush":
        k = prim["k"]
        d = np.linalg.norm(q, axis=1) - prim["r"] + 0.09 * prim["r"] * (
            np.sin(k * q[:, 0]) * np.sin(k * q[:, 1] + 1.3) * np.sin(k * q[:, 2] + 2.1))
    else:
        raise ValueError(t)
    if prim.get("dent") is not None:
        cx, cy, cz, depth, sig = prim["dent"]
        r2 = ((q - np.array([cx, cy, cz], np.float32)) ** 2).sum(1)
        d = d + depth * np.exp(-r2 / (2 * sig * sig))
    return (d * prim.get("step", 1.0)).astype(np.float32)


def scene_sdf(p: np.ndarray, prims: list[dict], with_index: bool = False):
    best = prim_sdf(p, prims[0])
    idx = np.zeros(len(p), np.int16) if with_index else None
    for i, prim in enumerate(prims[1:], 1):
        d = prim_sdf(p, prim)
        if with_index:
            m = d < best
            idx[m] = i
        best = np.minimum(best, d)
    return (best, idx) if with_index else best
