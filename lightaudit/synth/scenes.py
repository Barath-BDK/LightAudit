"""Random scenes, cached samples and the normal-predictor simulation (BUILD_SPEC 8.1, 8.5, 8.6)."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np

from ..config import ROOT, Config
from ..imageio import save_png
from . import render as rd

KINDS = ("normal", "overcast", "multi", "lowres", "damage")
CACHE = ROOT / "data" / "synth" / "cache"
OBJ_GROUND, OBJ_CAR, OBJ_WINDOWS, OBJ_WHEELS = 1, 2, 3, 4
CAR_OBJS = (OBJ_CAR, OBJ_WINDOWS, OBJ_WHEELS)


def sun_dir(az_deg: float, el_deg: float) -> np.ndarray:
    a, e = np.radians(az_deg), np.radians(el_deg)
    return np.array([np.cos(e) * np.sin(a), np.sin(e), np.cos(e) * np.cos(a)], np.float32)


@dataclass
class Scene:
    seed: int
    kind: str
    prims: list
    names: dict  # obj id -> region name
    cam_h: float
    pitch_deg: float
    fov_deg: float
    l_world: np.ndarray
    I_sun: float
    I_sky: float
    l2_world: np.ndarray | None
    I_sun2: float
    cam: dict  # camera pipeline: target, tone, noise, jpeg
    scale: float = 1.0
    noise_grid: np.ndarray = field(default=None, repr=False)

    def ground_noise(self, x, z):
        """Multi-octave value noise in [0, 1] (bilinear lookups into a random grid)."""
        g = self.noise_grid
        out = np.zeros(len(x), np.float32)
        for o, amp in enumerate((0.5, 0.3, 0.2)):
            fx, fz = x * 0.35 * 2 ** o + 100.0, z * 0.35 * 2 ** o + 100.0
            x0, z0 = np.floor(fx).astype(int), np.floor(fz).astype(int)
            tx, tz = (fx - x0).astype(np.float32), (fz - z0).astype(np.float32)
            n = g.shape[0]
            a, b = g[z0 % n, x0 % n], g[z0 % n, (x0 + 1) % n]
            c, d = g[(z0 + 1) % n, x0 % n], g[(z0 + 1) % n, (x0 + 1) % n]
            out += amp * ((a * (1 - tx) + b * tx) * (1 - tz) + (c * (1 - tx) + d * tx) * tz)
        return out

    @property
    def R(self):
        return rd.cam_rotation(self.pitch_deg)

    def lights_world(self):
        L = [(self.l_world, self.I_sun)]
        if self.l2_world is not None:
            L.append((self.l2_world, self.I_sun2))
        return L


def _color(rng, lo=0.25, hi=0.8):
    return rng.uniform(lo, hi, 3).astype(np.float32)


def make_scene(seed: int, kind: str = "normal", dent: bool | None = None) -> Scene:
    """Deterministic random scene. `dent` overrides whether the car body is dented (default: kind == 'damage')."""
    assert kind in KINDS, kind
    rng = np.random.default_rng([seed, KINDS.index(kind)])
    cam_h, pitch = rng.uniform(1.4, 1.8), rng.uniform(3, 10)
    dist = {"lowres": rng.uniform(8, 9), "damage": rng.uniform(6, 7.5)}.get(kind, rng.uniform(6, 10))
    cx, yaw = rng.uniform(-0.8, 0.8), np.radians(rng.uniform(-60, 60))
    c, s = np.cos(yaw), np.sin(yaw)
    car_pos = np.array([cx, 0, -dist])

    def at(off):  # car-local offset -> world
        return (car_pos + [c * off[0] + s * off[2], off[1], -s * off[0] + c * off[2]]).astype(np.float32)

    paint = dict(albedo=_color(rng, 0.15, 0.85), ks=rng.uniform(0.5, 1.0), shin=rng.uniform(60, 160))
    dent_p = (rng.uniform(-1.2, 1.2), rng.uniform(-0.05, 0.08), 0.9, rng.uniform(0.03, 0.06), rng.uniform(0.12, 0.20))
    has_dent = (kind == "damage") if dent is None else dent
    prims = [
        dict(type="plane", pos=(0, 0, 0), obj=OBJ_GROUND, albedo=_color(rng, 0.28, 0.45), ks=0.0, shin=1.0),
        dict(type="rbox", pos=at((0, 0.6, 0)), yaw=yaw, b=(2.1, 0.35, 0.9), r=0.18, obj=OBJ_CAR, **paint,
             dent=dent_p if has_dent else None),
        dict(type="rbox", pos=at((-0.2, 1.2, 0)), yaw=yaw, b=(1.1, 0.3, 0.75), r=0.22, obj=OBJ_CAR, **paint,
             window=(-0.12, 0.2, OBJ_WINDOWS)),
    ]
    for wx in (-1.35, 1.35):
        for wz in (-0.82, 0.82):
            prims.append(dict(type="cyl", axis="z", pos=at((wx, 0.35, wz)), yaw=yaw, r=0.35, h=0.125,
                              obj=OBJ_WHEELS, albedo=np.full(3, 0.07, np.float32), ks=0.05, shin=20.0))
    names = {OBJ_GROUND: "ground", OBJ_CAR: "car body", OBJ_WINDOWS: "car windows", OBJ_WHEELS: "wheels"}

    # distractors: at least two curved ones so that three regions can be reliable (logged decision)
    n_d = int(rng.integers(3, 6))
    types = list(rng.choice(["sphere", "pole", "bush"], 2)) + list(rng.choice(["sphere", "box", "pole", "bush"], n_d - 2))
    placed = []  # (x, z, radius)
    obj = 5
    for t in types:
        size = {"sphere": rng.uniform(0.45, 0.9), "box": rng.uniform(0.45, 0.85),
                "pole": rng.uniform(0.18, 0.3), "bush": rng.uniform(0.6, 1.0)}[t]
        for _ in range(200):
            z = -rng.uniform(4.5, 11)
            x = rng.uniform(-1, 1) * max(0.3, abs(z) * 0.5 - size)
            if np.hypot(x - cx, z + dist) < 2.7 + size:
                continue
            if abs(x / -z - cx / dist) < 2.3 / dist + size / -z:  # would occlude the car or hide behind it
                continue
            if any(np.hypot(x - px, z - pz) < size + pr + 0.3 for px, pz, pr in placed):
                continue
            break
        else:
            continue
        placed.append((x, z, size))
        mat = dict(albedo=_color(rng), ks=rng.choice([0.0, 0.0, 0.1, 0.15]), shin=rng.uniform(20, 60), obj=obj)
        if t == "sphere":
            prims.append(dict(type="sphere", pos=(x, size, z), r=size, **mat))
        elif t == "box":
            prims.append(dict(type="rbox", pos=(x, size, z), yaw=rng.uniform(0, np.pi), b=(size,) * 3,
                              r=rng.uniform(0.08, 0.3) * size, **mat))
        elif t == "pole":
            hh = rng.uniform(1.0, 1.7)
            prims.append(dict(type="cyl", axis="y", pos=(x, hh, z), r=size, h=hh, **mat))
        else:
            mat.update(ks=0.0, albedo=np.array([0.15, 0.4, 0.12], np.float32) * rng.uniform(0.7, 1.4))
            prims.append(dict(type="bush", pos=(x, size * 0.8, z), r=size, k=rng.uniform(5, 8) / size, step=0.6, **mat))
        names[obj] = f"{t} {obj - 4}"
        obj += 1
    if rng.random() < 0.7:
        b = (rng.uniform(3, 6), rng.uniform(2, 4), rng.uniform(2, 3))
        prims.append(dict(type="rbox", pos=(rng.uniform(-8, 8), b[1], -rng.uniform(20, 26)), yaw=rng.uniform(-0.5, 0.5),
                          b=b, r=0.05, obj=obj, albedo=_color(rng, 0.4, 0.75), ks=0.0, shin=1.0))
        names[obj] = "building"
    for p in prims:
        p["pos"] = tuple(float(v) for v in p["pos"])

    l = sun_dir(rng.uniform(0, 360), rng.uniform(15, 70))
    I_sun, I_sky = rng.uniform(1.6, 3.0), rng.uniform(0.25, 0.5)
    l2, I2 = None, 0.0
    if kind == "overcast":
        I_sky = rng.uniform(0.8, 1.2)
        I_sun = I_sky * rng.uniform(0.1, 0.4)
    if kind == "multi":
        while True:
            l2 = sun_dir(rng.uniform(0, 360), rng.uniform(10, 70))
            if np.degrees(np.arccos(np.clip(l @ l2, -1, 1))) >= 60:
                break
        I2 = I_sun * rng.uniform(0.4, 0.8)
    cam = dict(target=0.7 * rng.uniform(0.8, 1.2), tone=str(rng.choice(rd.TONE_CURVES)),
               noise=float(rng.uniform(0.003, 0.02)), jpeg=int(rng.choice([0, 95, 85, 70])))
    return Scene(seed, kind, prims, names, float(cam_h), float(pitch), 60.0, l, float(I_sun), float(I_sky), l2,
                 float(I2), cam, 0.5 if kind == "lowres" else 1.0, rng.random((64, 64)).astype(np.float32))


@dataclass
class Sample:
    scene: Scene
    G: dict  # full-resolution G-buffer (camera space)
    shadows: list  # one cast-shadow map per scene light
    rgb_lin: np.ndarray  # pristine linear render, full resolution
    rgb: np.ndarray  # final uint8 image (after downscale + camera pipeline)
    normals_gt: np.ndarray  # final resolution
    labels: np.ndarray  # final resolution, 0 = sky
    dent_mask: np.ndarray  # final resolution bool
    light_cam: np.ndarray  # GT unit vector toward the (first) sun, camera space
    meta: dict

    @property
    def names(self):
        return self.scene.names

    def lights_cam(self):
        return [(self.scene.R @ l, I) for l, I in self.scene.lights_world()]

    def down(self, a: np.ndarray, nearest: bool = False) -> np.ndarray:
        """Full resolution -> final resolution."""
        if self.scene.scale == 1.0:
            return a
        if nearest:
            return a[::2, ::2]
        return cv2.resize(a, (a.shape[1] // 2, a.shape[0] // 2), interpolation=cv2.INTER_AREA)

    def finish(self, rgb_lin: np.ndarray) -> np.ndarray:
        """Downscale (lowres scenes) and run the camera pipeline; deterministic per scene. The exposure is always
        the pristine image's, so a composite changes nothing outside the pasted region (as in a real splice)."""
        ref = rd.exposure_ref(self.down(self.rgb_lin), self.down(self.G["hit"], True))
        return rd.camera(self.down(rgb_lin), ref, self.scene.cam, self.scene.seed + 7)


def render_sample(scene: Scene, cfg: Config = Config(), G: dict | None = None, shadows: list | None = None) -> Sample:
    if G is None:
        G = rd.render_gbuffer(scene, cfg.H, cfg.W)
        shadows = [rd.shadow_pass(scene, G, l) for l, _ in scene.lights_world()]
    lights_cam = [(scene.R @ l, I) for l, I in scene.lights_world()]
    lin = rd.shade(G, scene, lights_cam, shadows)
    s = Sample(scene, G, shadows, lin, None, None, None, None, lights_cam[0][0].astype(np.float32), {})
    s.rgb = s.finish(lin)
    n = s.down(G["normal"])
    s.normals_gt = n / np.maximum(np.linalg.norm(n, axis=-1, keepdims=True), 1e-6)
    s.labels = s.down(G["obj"], True)
    s.dent_mask = s.down(G["dent"], True)
    s.meta = dict(seed=scene.seed, kind=scene.kind, light_cam=[float(v) for v in s.light_cam],
                  light_world=[float(v) for v in scene.l_world], I_sun=scene.I_sun, I_sky=scene.I_sky,
                  camera=scene.cam, names={int(k): v for k, v in scene.names.items()},
                  second_light_cam=[float(v) for v in lights_cam[1][0]] if len(lights_cam) > 1 else None)
    return s


_G_KEYS = ("normal", "albedo", "ks", "shin")


def get_sample(seed: int, kind: str = "normal", cfg: Config = Config(), cache: Path | None = CACHE) -> Sample:
    """Render a sample, re-using the cached G-buffer + shadow maps (.npz) when present."""
    scene = make_scene(seed, kind)
    f = None if cache is None else Path(cache) / f"{kind}_{seed}_{cfg.W}x{cfg.H}.npz"
    if f is not None and f.exists():
        z = np.load(f)
        G = {k: z[k].astype(np.float32) for k in _G_KEYS}
        G.update(obj=z["obj"], hit=z["obj"] > 0, dent=z["dent"].astype(bool))
        return render_sample(scene, cfg, G, list(z["shadows"].astype(np.float32) / 255))
    s = render_sample(scene, cfg)
    if f is not None:
        f.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(f, obj=s.G["obj"], dent=s.G["dent"],
                            shadows=np.round(np.stack(s.shadows) * 255).astype(np.uint8),
                            **{k: s.G[k].astype(np.float16) for k in _G_KEYS})
        # reload so cached and fresh samples are bit-identical (float16 / 8-bit shadow rounding)
        return get_sample(seed, kind, cfg, cache)
    return s


def simulate_normals(normals: np.ndarray, labels: np.ndarray, sigma: float, seed: int, cfg: Config = Config()):
    """`noisy_gt(sigma)`: spatially correlated rotation noise + occasional gross-error patches. Returns (n, unc_deg)."""
    H, W = labels.shape
    if sigma <= 0:
        return normals.copy(), np.full((H, W), cfg.unc_floor, np.float32)

    def copy(sd):
        rng = np.random.default_rng(sd)
        f = rng.normal(0, 1, (H // 16 + 2, W // 16 + 2, 3)).astype(np.float32)
        f = cv2.GaussianBlur(cv2.resize(f, (W, H), interpolation=cv2.INTER_CUBIC), (0, 0), 4)
        f *= np.radians(sigma) / max(f.std(), 1e-6)
        n = normals + f
        for k in np.unique(labels):
            if k == 0 or rng.random() > 0.15:
                continue
            m = labels == k
            ys, xs = np.nonzero(m)
            if len(ys) < 200:
                continue
            edge = m & ~cv2.erode(m.astype(np.uint8), np.ones((9, 9), np.uint8)).astype(bool)
            ey, ex = np.nonzero(edge)
            if len(ey) == 0:
                continue
            j = rng.integers(len(ey))
            r = np.sqrt(0.08 * len(ys) / np.pi) * 1.5
            patch = m & ((np.arange(H)[:, None] - ey[j]) ** 2 + (np.arange(W)[None, :] - ex[j]) ** 2 < r * r)
            tilt = rng.normal(0, 1, 3)
            n[patch] += (np.tan(np.radians(40)) * tilt / np.linalg.norm(tilt)).astype(np.float32)
        return n / np.maximum(np.linalg.norm(n, axis=-1, keepdims=True), 1e-6)

    a, b = copy([seed, 1]), copy([seed, 2])
    unc = np.degrees(np.arccos(np.clip((a * b).sum(-1), -1, 1)))
    unc = np.maximum(cv2.GaussianBlur(unc, (0, 0), 2), cfg.unc_floor).astype(np.float32)
    return a.astype(np.float32), unc


def region_meta(sample: Sample) -> list[dict]:
    """GT regions (`gt` backend): one per visible object id."""
    out = []
    for k in np.unique(sample.labels):
        if k:
            m = dict(id=int(k), name=sample.names.get(int(k), f"object {k}"), source="gt", excluded=False)
            if k in (OBJ_WINDOWS, OBJ_WHEELS):  # glass / tyres break the diffuse-shading model (logged decision)
                m.update(excluded=True, exclude_reason="glass or tyre (not a diffuse surface)")
            out.append(m)
    return out


def build_dataset(split: str, n: int, kinds, out_dir, cfg: Config = Config(), start: int | None = None) -> list[Path]:
    """Render n scenes (kinds cycled) to png + json; G-buffers go to the shared .npz cache."""
    from ..config import SPLIT_SEEDS
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    seed0 = SPLIT_SEEDS[split] if start is None else start
    jobs = [(seed0 + i, kinds[i % len(kinds)], str(out_dir)) for i in range(n)]
    import multiprocessing as mp
    import os
    with mp.Pool(max(1, (os.cpu_count() or 2) - 1)) as pool:
        return [Path(p) for p in pool.imap(_build_one, jobs)]


def _build_one(job):
    seed, kind, out = job
    s = get_sample(seed, kind)
    p = Path(out) / f"{kind}_{seed}.png"
    save_png(p, s.rgb)
    p.with_suffix(".json").write_text(json.dumps(s.meta, indent=1))
    return str(p)
