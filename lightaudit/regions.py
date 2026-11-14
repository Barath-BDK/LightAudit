"""Region proposals (BUILD_SPEC 7.3): slic, manual, sam (optional), ROI / panel mode, auto-exclusion.

All backends return (labels HxW int32 with 0 = unassigned, meta list of {id, name, source, excluded}).
The `gt` backend for synthetic scenes lives in lightaudit.synth.region_meta.
"""
from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np

from .config import Config
from .imageio import luminance
from .validity import erode_px


def _meta(labels, source, names=None):
    return [dict(id=int(k), name=(names or {}).get(int(k), f"region {k}"), source=source, excluded=False)
            for k in np.unique(labels) if k]


def slic_regions(rgb: np.ndarray, normals: np.ndarray | None = None, cfg: Config = Config()):
    """Superpixels, then greedy merging of adjacent ones with similar colour (Lab dE < 8) and mean normal (< 20 deg)."""
    from skimage.color import rgb2lab
    from skimage.segmentation import slic
    sp = slic(rgb, n_segments=40, compactness=10, start_label=0)
    n = sp.max() + 1
    lab = rgb2lab(rgb)
    cnt = np.bincount(sp.ravel(), minlength=n).astype(np.float64)
    col = np.stack([np.bincount(sp.ravel(), lab[..., c].ravel(), n) for c in range(3)], 1)
    nrm = None if normals is None else np.stack([np.bincount(sp.ravel(), normals[..., c].ravel(), n) for c in range(3)], 1)
    parent = np.arange(n)

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    pairs = set()
    for a, b in ((sp[:, :-1], sp[:, 1:]), (sp[:-1], sp[1:])):
        m = a != b
        pairs.update(zip(np.minimum(a[m], b[m]).tolist(), np.maximum(a[m], b[m]).tolist()))
    changed = True
    while changed:  # repeat until no adjacent pair qualifies (stats are accumulated at the roots)
        changed = False
        for a, b in sorted(pairs):
            ra, rb = find(a), find(b)
            if ra == rb:
                continue
            dE = np.linalg.norm(col[ra] / cnt[ra] - col[rb] / cnt[rb])
            ang = 0.0
            if nrm is not None:
                u, v = nrm[ra] / np.linalg.norm(nrm[ra]), nrm[rb] / np.linalg.norm(nrm[rb])
                ang = np.degrees(np.arccos(np.clip(u @ v, -1, 1)))
            if dE < 8 and ang < 20:
                parent[rb] = ra
                cnt[ra] += cnt[rb]
                col[ra] += col[rb]
                if nrm is not None:
                    nrm[ra] += nrm[rb]
                changed = True
    root = np.array([find(a) for a in range(n)])
    labels = np.zeros(sp.shape, np.int32)
    k = 0
    for r in np.unique(root):
        m = np.isin(sp, np.flatnonzero(root == r))
        if m.sum() >= cfg.min_region_px and k < 63:
            k += 1
            labels[m] = k
    return labels, _meta(labels, "slic")


def manual_regions(path, shape):
    """Label PNG (pixel value = region id) or polygon JSON: [{"name": ..., "polygon": [[x, y], ...]}, ...]."""
    path = Path(path)
    if path.suffix.lower() == ".json":
        labels = np.zeros(shape, np.int32)
        names = {}
        for k, item in enumerate(json.loads(path.read_text()), 1):
            cv2.fillPoly(labels, [np.asarray(item["polygon"], np.int32)], k)
            names[k] = item.get("name", f"region {k}")
        return labels, _meta(labels, "manual", names)
    from PIL import Image
    labels = np.asarray(Image.open(path).convert("L").resize((shape[1], shape[0]), Image.NEAREST)).astype(np.int32)
    return labels, _meta(labels, "manual")


def apply_roi(labels, meta, roi: np.ndarray, cfg: Config = Config()):
    """Panel mode: adds regions "ROI" and "ring" (the ROI's surroundings inside its parent region); the parent
    remainder is kept as "<name> (rest)"."""
    roi = roi.astype(bool)
    labels = labels.copy()
    under = labels[roi]
    under = under[under > 0]
    if roi.sum() == 0 or len(under) == 0:
        return labels, meta
    parent = int(np.bincount(under).argmax())
    H, W = labels.shape
    px = max(cfg.ring_px, 2 * erode_px(H, W, cfg))
    ring = cv2.dilate(roi.astype(np.uint8), np.ones((2 * px + 1, 2 * px + 1), np.uint8)).astype(bool)
    ring &= ~roi & (labels == parent)
    k = int(labels.max())
    labels[roi], labels[ring] = k + 1, k + 2
    meta = [dict(m) for m in meta]
    for m in meta:
        if m["id"] == parent:
            m["name"] += " (rest)"
    meta += [dict(id=k + 1, name="ROI", source="roi", excluded=False),
             dict(id=k + 2, name="ring", source="roi", excluded=False)]
    return labels, [m for m in meta if (labels == m["id"]).any()]


def auto_exclude(rgb, labels, meta, cfg: Config = Config()):
    """Marks sky, mostly-saturated and tiny regions as excluded (kept in the output with weight 0)."""
    Y = luminance(rgb)
    for m in meta:
        mask = labels == m["id"]
        y = Y[mask]
        why = None
        if mask.sum() < cfg.min_region_px:
            why = "smaller than the minimum region size"
        elif (y > cfg.sat_hi).mean() > 0.4:
            why = "mostly saturated"
        elif mask[0].any() and y.mean() > 0.6 and y.std() < 0.04:
            why = "looks like sky"
        if why:
            m.update(excluded=True, exclude_reason=why)
    return meta


def propose_regions(rgb, normals=None, backend: str = "slic", cfg: Config = Config(), log: list | None = None):
    """backend: 'sam' (falls back to slic), 'slic', or 'manual:PATH'."""
    log = log if log is not None else []
    if backend.startswith("manual:"):
        return manual_regions(backend.split(":", 1)[1], rgb.shape[:2])
    if backend == "sam":
        try:
            from .normals import sam_regions
            return sam_regions(rgb, cfg)
        except Exception as e:  # optional heavy backend: fall back, never crash
            log.append(f"regions: SAM unavailable ({type(e).__name__}: {e}); using SLIC")
    return slic_regions(rgb, normals, cfg)
