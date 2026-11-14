"""Image I/O helpers and the luminance / normal-map encodings of BUILD_SPEC 5.1 and 5.3."""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image


def load_rgb(path, max_side: int | None = None) -> np.ndarray:
    """uint8 RGB, optionally downscaled so the long side is <= max_side."""
    im = Image.open(path).convert("RGB")
    if max_side and max(im.size) > max_side:
        s = max_side / max(im.size)
        im = im.resize((round(im.width * s), round(im.height * s)), Image.LANCZOS)
    return np.asarray(im)


def save_png(path, arr: np.ndarray) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(arr).save(path)


def luminance(rgb: np.ndarray) -> np.ndarray:
    """Y on sRGB-encoded values in [0, 1] (display domain)."""
    x = rgb.astype(np.float32) / 255.0 if rgb.dtype == np.uint8 else rgb.astype(np.float32)
    return x @ np.array([0.2126, 0.7152, 0.0722], np.float32)


def encode_normals(n: np.ndarray) -> np.ndarray:
    return np.clip(np.round((n + 1) / 2 * 255), 0, 255).astype(np.uint8)


def decode_normals(png: np.ndarray) -> np.ndarray:
    n = png.astype(np.float32) / 255 * 2 - 1
    return n / np.maximum(np.linalg.norm(n, axis=-1, keepdims=True), 1e-6)


def jpeg_roundtrip(rgb: np.ndarray, quality: int) -> np.ndarray:
    import io
    buf = io.BytesIO()
    Image.fromarray(rgb).save(buf, "JPEG", quality=int(quality))
    return np.asarray(Image.open(io.BytesIO(buf.getvalue())).convert("RGB"))
