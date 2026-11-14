"""Composites: a target object (or the dent) lit by a different light, pasted into the scene (BUILD_SPEC 8.6)."""
from __future__ import annotations

import cv2
import numpy as np

from ..grid import angle_deg
from . import render as rd
from .scenes import CAR_OBJS, OBJ_CAR, Sample


def light_at_angle(l: np.ndarray, delta_deg: float, seed) -> np.ndarray:
    """A unit vector at `delta_deg` from l, random azimuth around l; prefers directions above the horizon
    (tries 50 azimuths, keeps the highest if none is >= 5 deg up)."""
    rng = np.random.default_rng(seed)
    l = np.asarray(l, np.float64)
    a = np.cross(l, [0, 1, 0] if abs(l[1]) < 0.9 else [1, 0, 0])
    a /= np.linalg.norm(a)
    b = np.cross(l, a)
    d = np.radians(delta_deg)
    best = None
    for phi in rng.uniform(0, 2 * np.pi, 50):
        c = np.cos(d) * l + np.sin(d) * (np.cos(phi) * a + np.sin(phi) * b)
        if best is None or c[1] > best[1]:
            best = c
        if c[1] >= np.sin(np.radians(5)):
            return c.astype(np.float32)
    return best.astype(np.float32)


def pick_distractor(sample: Sample, min_px: int = 1500) -> int | None:
    """Largest visible distractor object id (not ground/car/building)."""
    best, area = None, min_px
    for k, name in sample.names.items():
        if k in CAR_OBJS or name in ("ground", "building"):
            continue
        a = int((sample.labels == k).sum())
        if a > area:
            best, area = k, a
    return best


def target_mask(sample: Sample, target) -> tuple[np.ndarray, list[int]]:
    """Full-resolution boolean mask + the edited object ids."""
    obj = sample.G["obj"]
    if target == "car":
        return np.isin(obj, CAR_OBJS), list(CAR_OBJS)
    if target == "dent":
        return sample.G["dent"].copy(), [OBJ_CAR]
    if target == "distractor":
        target = pick_distractor(sample)
        if target is None:
            raise ValueError("no distractor large enough")
    return obj == int(target), [int(target)]


def paste(sample: Sample, target, light_world_B: np.ndarray) -> dict:
    """Scene under l_A with the target re-lit by l_B (attached shading only, no cast shadows), feathered 1.5 px,
    then the camera pipeline. Returns {rgb, mask (final res), delta_deg, edited_ids, light_cam_B}."""
    sc = sample.scene
    mask, ids = target_mask(sample, target)
    lB = sc.R @ np.asarray(light_world_B, np.float32)
    lin_B = rd.shade(sample.G, sc, [(lB, sc.I_sun)], None)
    a = np.minimum(cv2.GaussianBlur(mask.astype(np.float32), (0, 0), 1.5) * 2, 1) * mask  # feather inward only
    lin = sample.rgb_lin * (1 - a[..., None]) + lin_B * a[..., None]
    return dict(rgb=sample.finish(lin), mask=sample.down(mask, True), edited_ids=ids, light_cam_B=lB,
                delta_deg=float(angle_deg(sample.light_cam, lB)))
