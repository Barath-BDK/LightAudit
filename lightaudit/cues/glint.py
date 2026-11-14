"""Cue C2: specular glints (BUILD_SPEC 7.6). A highlight sits where the mirror direction points at the light."""
from __future__ import annotations

import cv2
import numpy as np

from ..config import Config
from ..grid import eq_dirs


def find_glints(Y, normals, unc, mask, view, cfg: Config) -> list[dict]:
    """Accepted glint blobs in a region: [{l (unit), sigma_deg, centroid (x, y), area}]."""
    sat = (Y > cfg.sat_hi) & mask
    if not sat.any():
        return []
    area_max = cfg.blob_max_frac * mask.sum()
    n_lab, lab, stats, cent = cv2.connectedComponentsWithStats(sat.astype(np.uint8), connectivity=8)
    out = []
    k5, k2 = np.ones((11, 11), np.uint8), np.ones((5, 5), np.uint8)
    for b in range(1, n_lab):
        x, y, w, h, area = stats[b]
        if not (cfg.blob_min <= area <= area_max):
            continue
        y0, y1, x0, x1 = max(0, y - 6), y + h + 6, max(0, x - 6), x + w + 6
        blob = lab[y0:y1, x0:x1] == b
        m, Yc = mask[y0:y1, x0:x1], Y[y0:y1, x0:x1]
        ring = cv2.dilate(blob.astype(np.uint8), k5).astype(bool) & m & ~(Yc > cfg.sat_hi)
        if ring.sum() < 4 or Yc[blob].mean() - Yc[ring].mean() < cfg.contrast_min:
            continue
        near = cv2.dilate(blob.astype(np.uint8), k2).astype(bool) & m
        n = normals[y0:y1, x0:x1][near].mean(0)
        n /= max(np.linalg.norm(n), 1e-6)
        v = view[int(round(cent[b][1])), int(round(cent[b][0]))]
        l = 2 * float(n @ v) * n - v
        sig = float(np.hypot(unc[y0:y1, x0:x1][blob].mean(), cfg.glint_sigma_floor))
        out.append(dict(l=l / np.linalg.norm(l), sigma_deg=sig, centroid=(float(cent[b][0]), float(cent[b][1])),
                        area=int(area)))
    return out


def glint_landscape(blobs: list[dict]) -> np.ndarray | None:
    """Normalised mean over blobs (not a product: a reflection of some other bright thing must not veto the sun)."""
    if not blobs:
        return None
    A = np.zeros(len(eq_dirs()), np.float32)
    for b in blobs:
        th = np.degrees(np.arccos(np.clip(eq_dirs() @ b["l"].astype(np.float32), -1, 1)))
        A += np.exp(-th ** 2 / (2 * b["sigma_deg"] ** 2))
    return A / A.max()
