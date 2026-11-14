"""Make a spliced twin of a real photo: paste a region of photo B into photo A, then audit it.

    python tools/make_real_splice.py --target A.jpg --source B.jpg [--mask mask.png] [--at X Y] [--audit]

--mask selects the region of B (white = paste); without it the central third of B is used.
Writes data/real/splices/<A>_from_<B>.png and the paste mask (usable as --roi for the audit).
"""
from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from lightaudit.config import ROOT, Config
from lightaudit.imageio import load_rgb, save_png


def splice(target: np.ndarray, source: np.ndarray, mask: np.ndarray, at=None, feather: float = 1.5):
    """Returns (spliced uint8, mask in target coordinates). `at` = top-left corner for the pasted bbox."""
    ys, xs = np.nonzero(mask)
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    patch, m = source[y0:y1, x0:x1], mask[y0:y1, x0:x1]
    H, W = target.shape[:2]
    h, w = min(y1 - y0, H), min(x1 - x0, W)
    ty, tx = ((H - h) // 2, (W - w) // 2) if at is None else (int(np.clip(at[1], 0, H - h)), int(np.clip(at[0], 0, W - w)))
    full = np.zeros((H, W), bool)
    full[ty:ty + h, tx:tx + w] = m[:h, :w]
    a = (np.minimum(cv2.GaussianBlur(full.astype(np.float32), (0, 0), feather) * 2, 1) * full)[..., None]
    out = target.astype(np.float32)
    out[ty:ty + h, tx:tx + w] = out[ty:ty + h, tx:tx + w] * (1 - a[ty:ty + h, tx:tx + w]) + patch[:h, :w] * a[ty:ty + h, tx:tx + w]
    return np.round(out).astype(np.uint8), full


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--target", type=Path, required=True)
    ap.add_argument("--source", type=Path, required=True)
    ap.add_argument("--mask", type=Path)
    ap.add_argument("--at", type=int, nargs=2, metavar=("X", "Y"))
    ap.add_argument("--audit", action="store_true", help="also audit the splice in panel mode (ROI = paste mask)")
    a = ap.parse_args()
    cfg = Config()
    A, B = load_rgb(a.target, cfg.max_side), load_rgb(a.source, cfg.max_side)
    if a.mask:
        m = np.asarray(Image.open(a.mask).convert("L").resize((B.shape[1], B.shape[0]), Image.NEAREST)) > 127
    else:
        m = np.zeros(B.shape[:2], bool)
        m[B.shape[0] // 3: 2 * B.shape[0] // 3, B.shape[1] // 3: 2 * B.shape[1] // 3] = True
    out, full = splice(A, B, m, a.at)
    d = ROOT / "data" / "real" / "splices"
    p = d / f"{a.target.stem}_from_{a.source.stem}.png"
    save_png(p, out)
    save_png(p.with_name(p.stem + "_mask.png"), (full * 255).astype(np.uint8))
    print(f"wrote {p} and its mask")
    if a.audit:
        from lightaudit.cli import audit_image
        b = audit_image(p, name=f"real_splice_{p.stem}", roi=p.with_name(p.stem + "_mask.png"), attacks=True,
                        description="Real photo with a region pasted from another photo (made by tools/make_real_splice.py).")
        print(f"bundle: {b}")


if __name__ == "__main__":
    main()
