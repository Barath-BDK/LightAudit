"""NumPy SDF ray-marcher: G-buffer pass, shadow pass, lighting pass, camera pipeline (BUILD_SPEC 8.2-8.4).

Everything after the G-buffer is done in camera space (5.1): +x right, +y up, +z toward the viewer.
"""
from __future__ import annotations

import numpy as np

from ..imageio import jpeg_roundtrip
from .sdf import scene_sdf, to_local

MAX_DIST = 40.0
SKY_TINT = np.array([0.85, 0.95, 1.1], np.float32)
TONE_CURVES = ("srgb", "gamma1.8", "gamma2.6", "scurve", "filmic")


def cam_rotation(pitch_deg: float) -> np.ndarray:
    """R_cam_from_world for a camera looking along world -z, pitched down by pitch_deg."""
    t = np.radians(pitch_deg)
    return np.array([[1, 0, 0], [0, np.cos(t), -np.sin(t)], [0, np.sin(t), np.cos(t)]], np.float32)


def pixel_rays(H: int, W: int, fov_deg: float) -> np.ndarray:
    """(H*W, 3) camera-space ray directions (5.1)."""
    f = (W / 2) / np.tan(np.radians(fov_deg) / 2)
    u, v = np.meshgrid(np.arange(W) + 0.5, np.arange(H) + 0.5)
    d = np.stack([(u - W / 2) / f, -(v - H / 2) / f, -np.ones_like(u)], -1).reshape(-1, 3)
    return (d / np.linalg.norm(d, axis=1, keepdims=True)).astype(np.float32)


def render_gbuffer(scene, H: int, W: int) -> dict:
    """Sphere-trace every pixel. Returns full-resolution arrays (see keys below)."""
    prims = scene.prims
    R = cam_rotation(scene.pitch_deg)
    d_cam = pixel_rays(H, W, scene.fov_deg)
    d_w = d_cam @ R  # world = R^T cam
    o = np.array([0, scene.cam_h, 0], np.float32)
    N = H * W
    t = np.full(N, 0.1, np.float32)
    hit = np.zeros(N, bool)
    active = np.arange(N)
    for _ in range(80):
        if active.size == 0:
            break
        p = o + t[active, None] * d_w[active]
        dist = scene_sdf(p, prims)
        h = dist < 1e-3 * np.maximum(t[active], 1.0)
        hit[active[h]] = True
        t[active] += np.where(h, 0, dist)
        active = active[~h & (t[active] < MAX_DIST)]
    # pixels still marching at the step cap count as hits only if very close (grazing ground rays)
    if active.size:
        dist = scene_sdf(o + t[active, None] * d_w[active], prims)
        hit[active[dist < 0.02]] = True

    hi = np.flatnonzero(hit)
    p = o + t[hi, None] * d_w[hi]
    _, pidx = scene_sdf(p, prims, with_index=True)
    e = 1e-3
    n = np.zeros((hi.size, 3), np.float32)
    for a in range(3):
        off = np.zeros(3, np.float32)
        off[a] = e
        n[:, a] = scene_sdf(p + off, prims) - scene_sdf(p - off, prims)
    n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-9)

    obj = np.zeros(hi.size, np.uint8)
    albedo = np.zeros((hi.size, 3), np.float32)
    ks = np.zeros(hi.size, np.float32)
    shin = np.ones(hi.size, np.float32)
    dent = np.zeros(hi.size, bool)
    for i, prim in enumerate(prims):
        m = pidx == i
        if not m.any():
            continue
        obj[m] = prim["obj"]
        albedo[m] = prim["albedo"]
        ks[m] = prim["ks"]
        shin[m] = prim["shin"]
        if prim["type"] == "plane":  # low-frequency albedo noise on the ground
            albedo[m] *= (0.8 + 0.4 * scene.ground_noise(p[m, 0], p[m, 2]))[:, None]
        q = to_local(p[m], prim) if prim["type"] != "plane" else None
        if prim.get("window") is not None:  # cabin side patches -> glass material
            y0, y1, wobj = prim["window"]
            nl = to_local(n[m] + np.asarray(prim["pos"], np.float32), prim)
            w = (q[:, 1] > y0) & (q[:, 1] < y1) & (np.abs(nl[:, 1]) < 0.5)
            mi = np.flatnonzero(m)[w]
            obj[mi] = wobj
            albedo[mi] = (0.06, 0.07, 0.09)
            ks[mi] = 1.0
            shin[mi] = 200.0
        if prim.get("dent") is not None:
            cx, cy, cz, _, sig = prim["dent"]
            r = np.linalg.norm(q - np.array([cx, cy, cz], np.float32), axis=1)
            dent[np.flatnonzero(m)[r < 2.5 * sig]] = True

    def full(vals, fill=0):
        out = np.full((N,) + vals.shape[1:], fill, vals.dtype)
        out[hi] = vals
        return out.reshape((H, W) + vals.shape[1:])

    n_cam = n @ R.T
    return {
        "normal": full(n_cam), "obj": full(obj), "albedo": full(albedo), "ks": full(ks), "shin": full(shin, 1),
        "hit": hit.reshape(H, W), "pos": full(p.astype(np.float32)), "depth": full(t[hi], MAX_DIST),
        "dent": full(dent),
    }


def shadow_pass(scene, G: dict, l_world: np.ndarray, k: float = 24.0) -> np.ndarray:
    """Soft shadow factor in [0,1] for every hit pixel (40 steps)."""
    hit = G["hit"]
    R = cam_rotation(scene.pitch_deg)
    p = G["pos"][hit] + 5e-3 * (G["normal"][hit] @ R)
    l = np.asarray(l_world, np.float32)
    res = np.ones(len(p), np.float32)
    t = np.full(len(p), 0.03, np.float32)
    active = np.arange(len(p))
    for _ in range(40):
        if active.size == 0:
            break
        h = scene_sdf(p[active] + t[active, None] * l, scene.prims)
        res[active] = np.minimum(res[active], np.clip(k * h / t[active], 0, 1))
        t[active] += np.clip(h, 0.02, 2.0)
        active = active[(res[active] > 1e-3) & (t[active] < 25.0)]
    out = np.ones(hit.shape, np.float32)
    out[hit] = res
    return out


def view_cam(H: int, W: int, fov_deg: float) -> np.ndarray:
    return (-pixel_rays(H, W, fov_deg)).reshape(H, W, 3)


def shade(G: dict, scene, lights: list, shadows: list | None) -> np.ndarray:
    """Linear RGB. lights = [(l_cam, intensity), ...]; shadows = one map per light, or None for no cast shadows."""
    H, W = G["hit"].shape
    n = G["normal"]
    v = view_cam(H, W, scene.fov_deg)
    up_cam = cam_rotation(scene.pitch_deg) @ np.array([0, 1, 0], np.float32)
    sky = scene.I_sky * (0.6 + 0.4 * (n @ up_cam))[..., None] * SKY_TINT
    diff = sky.copy()
    spec = np.zeros((H, W), np.float32)
    for i, (l, I) in enumerate(lights):
        l = np.asarray(l, np.float32)
        lam = np.maximum(n @ l, 0)
        sh = shadows[i] if shadows is not None else 1.0
        h = l + v
        h /= np.maximum(np.linalg.norm(h, axis=-1, keepdims=True), 1e-9)
        diff += (I * lam * sh)[..., None]
        spec += G["ks"] * I * sh * np.maximum((n * h).sum(-1), 0) ** G["shin"] * (lam > 0)
    rgb = G["albedo"] * diff + spec[..., None]
    # sky pixels: vertical gradient by ray elevation
    el = np.clip((-v) @ up_cam, 0, 1)[..., None]
    sky_rgb = scene.I_sky * 2.2 * ((1 - el) * np.array([0.8, 0.88, 1.0], np.float32)
                                   + el * np.array([0.3, 0.5, 0.95], np.float32))
    return np.where(G["hit"][..., None], rgb, sky_rgb).astype(np.float32)


def tone_curve(x: np.ndarray, name: str) -> np.ndarray:
    """Monotone map of linear [0, inf) to display [0, 1]."""
    if name == "filmic":  # Reinhard-extended (white point 2.5), then gamma 2.2
        x = np.maximum(x, 0)
        return np.clip(x * (1 + x / 6.25) / (1 + x), 0, 1) ** (1 / 2.2)
    x = np.clip(x, 0, 1)
    if name == "srgb":
        return np.where(x <= 0.0031308, 12.92 * x, 1.055 * x ** (1 / 2.4) - 0.055)
    if name.startswith("gamma"):
        return x ** (1 / float(name[5:]))
    if name == "scurve":
        t = x ** (1 / 2.2)
        return t * t * (3 - 2 * t)
    if name == "linear":
        return x
    raise ValueError(name)


def exposure_ref(rgb_lin: np.ndarray, nonsky: np.ndarray) -> float:
    lum = rgb_lin @ np.array([0.2126, 0.7152, 0.0722], np.float32)
    return float(np.percentile(lum[nonsky], 90) if nonsky.any() else np.percentile(lum, 90))


def camera(rgb_lin: np.ndarray, ref: float, cam: dict, seed: int) -> np.ndarray:
    """Exposure (90th-percentile luminance `ref` -> cam['target']) -> tone curve -> noise -> 8-bit -> optional JPEG."""
    x = tone_curve(rgb_lin * (cam["target"] / max(ref, 1e-6)), cam["tone"])
    x = x + np.random.default_rng(seed).normal(0, cam["noise"], x.shape)
    out = np.clip(np.round(x * 255), 0, 255).astype(np.uint8)
    return jpeg_roundtrip(out, cam["jpeg"]) if cam.get("jpeg") else out
