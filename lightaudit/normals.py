"""Surface normals for real photos (BUILD_SPEC 7.4) and SAM region proposals (7.3).

Every heavy backend is optional: imports are lazy, each backend runs inside try/except, nothing is downloaded at
import time, and predictions are cached in data/cache/normals/ keyed by the image content. If none of the requested
backends works, `predict_normals` walks the fallback chain (marigold -> depth_anything) and, as a last resort,
returns image-gradient pseudo-normals with a 30 deg uncertainty so the pipeline still runs and honestly reports
low reliability.

Output convention (BUILD_SPEC 5.1): camera space, +x right, +y up, +z toward the viewer, unit length.
"""
from __future__ import annotations

import hashlib
import importlib.util
import threading
from pathlib import Path

import cv2
import numpy as np

from .config import ROOT, Config

CACHE = ROOT / "data" / "cache"
CACHE_VERSION = 2  # bump when a backend's post-processing changes (invalidates cached predictions)
FALLBACK_CHAIN = ("marigold", "depth_anything")
PSEUDO_UNC_DEG = 30.0
NAMES = ("sam", "dsine", "stablenormal", "marigold", "depth_anything")

_MODELS: dict = {}
_LOCK = threading.Lock()


# ----------------------------------------------------------------------------------------------- availability
def _has(mod: str) -> bool:
    try:
        return importlib.util.find_spec(mod) is not None
    except (ImportError, ValueError):
        return False


def backends_available() -> dict:
    """Which optional backends can be used: import checks only (no model download, no heavy import).

    A True value means the libraries are installed; model weights are fetched lazily on first use.
    `backend_details()` additionally says whether the weights are already in the local cache.
    """
    torch = _has("torch")
    tr = torch and _has("transformers")
    diff = torch and _has("diffusers")
    return {"sam": tr, "dsine": torch, "stablenormal": diff, "marigold": diff, "depth_anything": tr}


def _hf_cached(repo: str) -> bool:
    try:
        from huggingface_hub import scan_cache_dir
        return any(r.repo_id == repo for r in scan_cache_dir().repos)
    except Exception:
        return False


def _hub_cached(name: str) -> bool:
    try:
        import torch
        return any(p.name.lower().startswith(name.lower()) for p in Path(torch.hub.get_dir()).glob("*"))
    except Exception:
        return False


def backend_details() -> dict:
    """Human-readable status per backend: libraries installed and weights cached locally (no downloads)."""
    av = backends_available()
    cached = {"sam": _hf_cached("facebook/sam-vit-base"),
              "depth_anything": _hf_cached("depth-anything/Depth-Anything-V2-Small-hf"),
              "marigold": _hf_cached("prs-eth/marigold-normals-v1-1"),
              "dsine": _hub_cached("hugoycj_DSINE-hub"), "stablenormal": _hub_cached("Stable-X_StableNormal")}
    return {k: ("libraries installed" if av[k] else "libraries missing")
            + (", weights cached" if cached[k] else ", weights not downloaded yet") for k in NAMES}


# ----------------------------------------------------------------------------------------------- helpers
def _unit(n: np.ndarray) -> np.ndarray:
    n = np.nan_to_num(np.asarray(n, np.float32))
    return n / np.maximum(np.linalg.norm(n, axis=-1, keepdims=True), 1e-6)


def _resize_normals(n: np.ndarray, H: int, W: int) -> np.ndarray:
    if n.shape[:2] != (H, W):
        n = cv2.resize(n.astype(np.float32), (W, H), interpolation=cv2.INTER_LINEAR)
    return _unit(n)


def _to_hwc(a, H: int | None = None, W: int | None = None) -> np.ndarray:
    """Any (1,3,H,W) / (3,H,W) / (H,W,3) / (1,H,W,3) array or tensor -> (H,W,3) float32."""
    if hasattr(a, "detach"):
        a = a.detach().float().cpu().numpy()
    a = np.asarray(a, np.float32)
    while a.ndim > 3 and a.shape[0] == 1:
        a = a[0]
    if a.ndim != 3:
        raise ValueError(f"unexpected normal-map shape {a.shape}")
    if a.shape[0] == 3 and a.shape[-1] != 3:
        a = np.transpose(a, (1, 2, 0))
    return a


def _small(rgb: np.ndarray, long_side: int) -> np.ndarray:
    H, W = rgb.shape[:2]
    s = long_side / max(H, W)
    if s >= 1:
        return rgb
    return cv2.resize(rgb, (max(8, round(W * s)), max(8, round(H * s))), interpolation=cv2.INTER_AREA)


def _image_key(rgb: np.ndarray, *parts) -> str:
    h = hashlib.sha1(np.ascontiguousarray(rgb).tobytes())
    h.update(repr((rgb.shape, CACHE_VERSION) + parts).encode())
    return h.hexdigest()[:20]


def _model(name: str, loader):
    with _LOCK:
        if name not in _MODELS:
            _MODELS[name] = loader()
        return _MODELS[name]


def _pil(rgb: np.ndarray):
    from PIL import Image
    return Image.fromarray(np.ascontiguousarray(rgb))


# ----------------------------------------------------------------------------------------------- convention
def fix_convention(normals: np.ndarray, log: list | None = None, name: str = "normals") -> np.ndarray:
    """Normalise and bring a backend's normals into the camera convention of BUILD_SPEC 5.1.

    Automatic decisions use only two priors measured on the image itself:
      z: the median normal over all pixels faces the camera (n_z > 0), otherwise z is flipped;
      y: the median normal of the bottom 15% of rows (usually ground) points up (n_y > 0), otherwise y is flipped.
    x is never flipped automatically (left/right has no reliable prior); the "left half of convex objects faces
    left" statistic is only logged as a hint for the --flip-x override.
    """
    log = log if log is not None else []
    n = _unit(normals).copy()
    H = n.shape[0]
    mz = float(np.median(n[..., 2]))
    if mz < 0:
        n[..., 2] *= -1
    bottom = n[int(np.floor(0.85 * H)):]
    my = float(np.median(bottom[..., 1]))
    flip_y = my < -0.05  # only a clear "down" vote flips; a near-zero median (no ground visible) keeps the sign
    if flip_y:
        n[..., 1] *= -1
    W = n.shape[1]
    xl, xr = float(np.median(n[:, : W // 2, 0])), float(np.median(n[:, W // 2:, 0]))
    log.append(f"{name}: convention check: median n_z={mz:+.2f} -> {'flip z' if mz < 0 else 'z ok'}; "
               f"bottom-15% median n_y={my:+.2f} -> {'flip y' if flip_y else 'y ok'}; "
               f"x not decided automatically (median n_x left={xl:+.2f}, right={xr:+.2f}"
               + ("; looks mirrored, consider --flip-x" if xl - xr > 0.15 else "") + ")")
    return n


def _apply_flips(n: np.ndarray, flips) -> np.ndarray:
    n = n.copy()
    for ax, f in enumerate(flips or (False, False, False)):
        if f:
            n[..., ax] *= -1
    return n


# ----------------------------------------------------------------------------------------------- backends
def _run_dsine(rgb: np.ndarray, fov_deg: float) -> np.ndarray:
    import torch

    def load():
        m = torch.hub.load("hugoycj/DSINE-hub", "DSINE", trust_repo=True)
        return m.eval() if hasattr(m, "eval") else m

    model = _model("dsine", load)
    img = _small(rgb, 640)
    with torch.no_grad():
        out = model.infer_cv2(np.ascontiguousarray(img[..., ::-1]))  # the hub wrapper takes an OpenCV BGR image
    return _to_hwc(out)


def _run_stablenormal(rgb: np.ndarray, fov_deg: float) -> np.ndarray:
    import torch
    model = _model("stablenormal", lambda: torch.hub.load("Stable-X/StableNormal", "StableNormal", trust_repo=True))
    out = model(_pil(_small(rgb, 768)))
    return np.asarray(out.convert("RGB"), np.float32) / 127.5 - 1.0


def _run_marigold(rgb: np.ndarray, fov_deg: float) -> np.ndarray:
    import torch
    from diffusers import MarigoldNormalsPipeline

    def load():
        return MarigoldNormalsPipeline.from_pretrained("prs-eth/marigold-normals-v1-1", torch_dtype=torch.float32)

    pipe = _model("marigold", load)
    with torch.no_grad():
        out = pipe(_pil(_small(rgb, 512)), num_inference_steps=4, ensemble_size=1, processing_resolution=512)
    return _to_hwc(out.prediction)


def depth_to_normals(disp: np.ndarray, fov_deg: float) -> np.ndarray:
    """Relative inverse depth (bigger = closer) -> camera-space normals via the pinhole model of BUILD_SPEC 5.1.

    Pseudo-depth Z = 1 / (0.1 + d) with d the disparity rescaled to [0, 1]; points P = Z * ray; n = Pu x Pv,
    oriented toward the camera. Low quality (the scale/shift of relative depth is unknown): last-resort backend.
    """
    H, W = disp.shape
    d = disp.astype(np.float32)
    d = (d - np.percentile(d, 1)) / max(float(np.percentile(d, 99) - np.percentile(d, 1)), 1e-6)
    d = cv2.GaussianBlur(np.clip(d, 0, 1), (0, 0), max(1.0, 0.004 * max(H, W)))
    Z = 1.0 / (0.1 + d)
    f = (W / 2) / np.tan(np.radians(fov_deg) / 2)
    u, v = np.meshgrid(np.arange(W) + 0.5, np.arange(H) + 0.5)
    P = np.stack([(u - W / 2) / f * Z, -(v - H / 2) / f * Z, -Z], -1)
    Pu = np.gradient(P, axis=1)
    Pv = np.gradient(P, axis=0)
    n = np.cross(Pu, Pv)
    n = _unit(n)
    flip = (n * -P).sum(-1) < 0  # the normal of a visible surface faces the camera
    n[flip] *= -1
    return n


def _run_depth_anything(rgb: np.ndarray, fov_deg: float) -> np.ndarray:
    from transformers import pipeline

    est = _model("depth_anything", lambda: pipeline("depth-estimation", model="depth-anything/Depth-Anything-V2-Small-hf",
                                                      device=-1))
    img = _small(rgb, 518)
    out = est(_pil(img))
    pd = out["predicted_depth"] if isinstance(out, dict) else out[0]["predicted_depth"]
    disp = pd.detach().float().cpu().numpy() if hasattr(pd, "detach") else np.asarray(pd, np.float32)
    disp = np.squeeze(disp)
    disp = cv2.resize(disp, (img.shape[1], img.shape[0]), interpolation=cv2.INTER_LINEAR)
    return depth_to_normals(disp, fov_deg)


def pseudo_normals(rgb: np.ndarray) -> np.ndarray:
    """Last resort, no network: tilt a camera-facing normal along the gradient of heavily blurred luminance.

    This is not shape-from-shading and carries almost no geometric information; it only lets the pipeline run so
    that it can report (correctly) that the evidence is unreliable.
    """
    from .imageio import luminance
    Y = luminance(rgb)
    H, W = Y.shape
    L = cv2.GaussianBlur(Y, (0, 0), max(2.0, 0.02 * max(H, W)))
    gy, gx = np.gradient(L)
    k = 1.0 / max(float(np.percentile(np.hypot(gx, gy), 95)), 1e-6)  # ~45 deg tilt at the 95th percentile
    n = np.stack([-k * gx, k * gy, np.ones_like(L)], -1)  # image v points down, camera y up
    return _unit(n)


BACKENDS = {"dsine": _run_dsine, "stablenormal": _run_stablenormal, "marigold": _run_marigold,
            "depth_anything": _run_depth_anything}


def _cached_backend(name: str, rgb: np.ndarray, fov_deg: float, log: list) -> np.ndarray:
    """Run one backend (with on-disk cache) and return convention-fixed normals at the image size."""
    H, W = rgb.shape[:2]
    path = CACHE / "normals" / f"{name}_{_image_key(rgb, name, round(float(fov_deg), 3))}.npz"
    if path.exists():
        n = np.load(path)["n"].astype(np.float32)
        log.append(f"{name}: loaded cached prediction {path.name}")
        return _unit(n)
    raw = BACKENDS[name](rgb, fov_deg)
    n = fix_convention(_resize_normals(_to_hwc(raw), H, W), log, name)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(path, n=n.astype(np.float16))
    except OSError as e:
        log.append(f"{name}: could not write cache ({e})")
    return n


def _texture_term(n: np.ndarray) -> np.ndarray:
    """Small extra uncertainty where the normal map varies quickly (degrees, 0..4)."""
    sm = _unit(cv2.blur(n, (5, 5)))
    dev = np.degrees(np.arccos(np.clip((n * sm).sum(-1), -1, 1)))
    return np.clip(0.5 * dev, 0, 4).astype(np.float32)


def predict_normals(rgb: np.ndarray, backends=("dsine", "stablenormal"), fov_deg: float = 60.0,
                    flips=(False, False, False), cfg: Config = Config()):
    """Ensemble of the requested backends -> (normals HxWx3 float32, unc HxW degrees float32, info).

    Fused normal = normalised mean of the members; unc = mean angular deviation of the members from the fused
    normal, floored at cfg.unc_floor. One member: unc = cfg.single_backend_unc + a small texture term. If no
    requested backend runs: fallback chain marigold -> depth_anything (first that works), then pseudo-normals with
    unc = 30 deg. `flips` (x, y, z) are user overrides applied after the automatic convention check.
    info = {"backends": [names that ran], "log": [...], "mode": "ensemble|single|fallback|pseudo", "failed": {...}}
    """
    rgb = np.ascontiguousarray(rgb)
    H, W = rgb.shape[:2]
    log: list[str] = []
    failed: dict[str, str] = {}
    members: dict[str, np.ndarray] = {}

    def attempt(name: str):
        if name not in BACKENDS:
            failed[name] = "unknown backend (gt/noisy_gt are for synthetic scenes only)"
            log.append(f"{name}: skipped, {failed[name]}")
            return
        try:
            members[name] = _cached_backend(name, rgb, fov_deg, log)
            log.append(f"{name}: ok")
        except Exception as e:  # optional heavy backend: record and continue
            failed[name] = f"{type(e).__name__}: {str(e)[:300]}"
            log.append(f"{name}: FAILED ({failed[name]})")

    for b in dict.fromkeys(backends):
        attempt(b)
    mode = "ensemble" if len(members) > 1 else "single"
    if not members:
        for b in FALLBACK_CHAIN:
            if b in failed:
                continue
            log.append(f"no requested normal backend worked; trying fallback '{b}'")
            attempt(b)
            if members:
                mode = "fallback"
                break
    if not members:
        log.append("WARNING: NO NORMAL BACKEND WORKED. Using image-gradient pseudo-normals (blurred luminance) "
                   f"with uncertainty {PSEUDO_UNC_DEG:.0f} deg. Surface directions are essentially unknown, so "
                   "lighting results for this image are NOT reliable.")
        n = _apply_flips(pseudo_normals(rgb), flips)
        unc = np.full((H, W), PSEUDO_UNC_DEG, np.float32)
        return n, unc, {"backends": [], "log": log, "mode": "pseudo", "failed": failed, "fallback": True}

    stack = np.stack(list(members.values()))
    fused = _unit(stack.mean(0))
    if len(members) > 1:
        dev = np.degrees(np.arccos(np.clip((stack * fused[None]).sum(-1), -1, 1)))
        unc = np.maximum(dev.mean(0), cfg.unc_floor).astype(np.float32)
        log.append(f"ensemble of {len(members)}: median unc {np.median(unc):.1f} deg")
    else:
        unc = (cfg.single_backend_unc + _texture_term(fused)).astype(np.float32)
        log.append(f"single backend: unc = {cfg.single_backend_unc:g} deg + texture term")
    if any(flips or ()):
        log.append(f"user flips applied (x, y, z) = {tuple(bool(f) for f in flips)}")
    fused = _apply_flips(fused, flips)
    return fused.astype(np.float32), unc, {"backends": list(members), "log": log, "mode": mode, "failed": failed,
                                           "fallback": mode == "fallback"}


# ----------------------------------------------------------------------------------------------- SAM regions
def _merge_iou(masks: list[np.ndarray], thr: float = 0.85) -> list[np.ndarray]:
    out: list[np.ndarray] = []
    for m in masks:
        for i, o in enumerate(out):
            inter = np.logical_and(m, o).sum()
            if inter and inter / np.logical_or(m, o).sum() > thr:
                out[i] = np.logical_or(m, o)
                break
        else:
            out.append(m)
    return out


def sam_regions(rgb: np.ndarray, cfg: Config = Config(), points_per_crop: int = 24):
    """SAM automatic masks (transformers 'mask-generation', facebook/sam-vit-base, CPU) -> (labels int32, meta).

    Run at long side <= 768; keep masks with min_region_px <= area <= max_region_frac of the image; merge masks
    with IoU > 0.85; paint in descending area order (smaller masks overwrite larger ones); drop regions left with
    fewer than min_region_px pixels; at most 63 regions. points_per_crop=24 (576 prompts) instead of the default
    32 keeps CPU time reasonable. Cached in data/cache/sam/ by image content.
    """
    H, W = rgb.shape[:2]
    path = CACHE / "sam" / f"sam_{_image_key(np.ascontiguousarray(rgb), points_per_crop)}.npz"
    if path.exists():
        labels = np.load(path)["labels"].astype(np.int32)
    else:
        from transformers import pipeline
        gen = _model("sam", lambda: pipeline("mask-generation", model="facebook/sam-vit-base", device=-1))
        small = _small(rgb, 768)
        out = gen(_pil(small), points_per_batch=64, points_per_crop=points_per_crop)
        raw = out["masks"] if isinstance(out, dict) else out
        masks = []
        for m in raw:
            m = np.asarray(m.detach().cpu().numpy() if hasattr(m, "detach") else m).astype(np.uint8).squeeze()
            if m.shape != (H, W):
                m = cv2.resize(m, (W, H), interpolation=cv2.INTER_NEAREST)
            m = m.astype(bool)
            if cfg.min_region_px <= m.sum() <= cfg.max_region_frac * H * W:
                masks.append(m)
        if not masks:
            raise RuntimeError("SAM returned no usable masks")
        masks = _merge_iou(sorted(masks, key=lambda m: -int(m.sum())))
        masks.sort(key=lambda m: -int(m.sum()))
        paint = np.zeros((H, W), np.int32)
        for i, m in enumerate(masks, 1):
            paint[m] = i
        labels = np.zeros((H, W), np.int32)
        k = 0
        for i in range(1, len(masks) + 1):
            m = paint == i
            if m.sum() >= cfg.min_region_px and k < 63:
                k += 1
                labels[m] = k
        if k == 0:
            raise RuntimeError("SAM: no region kept after painting")
        path.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(path, labels=labels.astype(np.uint8))
    meta = [dict(id=int(k), name=f"region {k}", source="sam", excluded=False) for k in np.unique(labels) if k]
    return labels, meta
