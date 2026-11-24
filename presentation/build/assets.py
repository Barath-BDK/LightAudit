"""Light assets for the two LightAudit decks, drawn with numpy (no external art).

    python presentation/build/assets.py <screenshots dir>

Writes presentation/build/assets/: sun core, ray fan, light beam, scan bar, spectrum fan, and crops of the
viewer screenshots (gallery hero, audit page, light dome, sky map, verdict rail) in dark and light themes.
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image

OUT = Path(__file__).resolve().parent / "assets"
OUT.mkdir(exist_ok=True)


def save_rgba(rgb, alpha, name):
    a = np.clip(alpha, 0, 1)
    img = np.dstack([np.clip(rgb, 0, 1) * 255, a[..., None] * 255]).astype(np.uint8)
    Image.fromarray(img, "RGBA").save(OUT / name, optimize=True)


def hexrgb(h):
    return np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)]) / 255.0


def grid(n):
    y, x = np.mgrid[0:n, 0:n] / (n - 1) * 2 - 1
    return x, y, np.hypot(x, y), np.arctan2(y, x)


# ---------------------------------------------------------------- deck A: one sun
def sun_core(n=900):
    _, _, r, _ = grid(n)
    core = np.exp(-(r / 0.10) ** 2)
    glow = np.exp(-(r / 0.42) ** 2) * 0.55 + np.exp(-(r / 0.9) ** 2) * 0.18
    a = np.clip(core + glow, 0, 1) * (r < 1)
    white, amber = np.array([1, 0.97, 0.88]), hexrgb("FFB547")
    k = np.clip(core * 1.2, 0, 1)[..., None]
    save_rgba(white * k + amber * (1 - k), a, "sun_core.png")


def ray_fan(n=2400, rays=26, seed=3):
    """Rays radiating from the centre with soft edges and a radial falloff; rotating it rotates about the sun."""
    rng = np.random.default_rng(seed)
    _, _, r, th = grid(n)
    a = np.zeros_like(r)
    for _ in range(rays):
        t0 = rng.uniform(-np.pi, np.pi)
        w = rng.uniform(0.006, 0.028)          # angular half-width
        L = rng.uniform(0.55, 1.0)             # length
        s = rng.uniform(0.18, 0.55)            # strength
        d = np.angle(np.exp(1j * (th - t0)))
        a += s * np.exp(-(d / w) ** 2) * np.clip(1 - r / L, 0, 1) ** 1.6
    a *= np.clip(r / 0.08, 0, 1)                # no hard spike at the centre (the core covers it)
    a = 1 - np.exp(-a * 1.4)
    amber, gold = hexrgb("FF9F1C"), hexrgb("FFD27A")
    k = np.clip(1 - r, 0, 1)[..., None]
    save_rgba(gold * k + amber * (1 - k), a * 0.85, "ray_fan.png")


def beam(w=2400, h=360):
    y, x = np.mgrid[0:h, 0:w]
    yy = (y / (h - 1) * 2 - 1)
    xx = x / (w - 1)
    spread = 0.25 + 0.75 * xx                     # the beam widens as it travels
    a = np.exp(-(yy / spread) ** 2) * np.clip(1 - xx, 0, 1) ** 0.7 * np.clip(xx / 0.04, 0, 1)
    save_rgba(np.broadcast_to(hexrgb("FFD27A"), (h, w, 3)), a * 0.75, "beam.png")


# ---------------------------------------------------------------- deck B: prism and spectrum
SPECTRUM = ["E5484D", "F76B15", "FFC53D", "46A758", "0090FF", "6E56CF"]


def scan_bar(w=220, h=1200):
    _, x = np.mgrid[0:h, 0:w]
    xx = x / (w - 1) * 2 - 1
    a = np.exp(-(xx / 0.35) ** 2) * 0.55 + np.exp(-(xx / 0.06) ** 2) * 0.45
    rgb = np.ones((h, w, 3)) * np.array([1, 1, 1])
    save_rgba(rgb, a, "scan_bar.png")


def spectrum_fan(w=2400, h=1400, odd=None, name="spectrum_fan.png"):
    """Six coloured rays leaving a point on the left edge; `odd` bends one ray away (the pasted region)."""
    y, x = np.mgrid[0:h, 0:w].astype(float)
    ox, oy = 0, h * 0.5
    ang = np.arctan2(y - oy, x - ox)
    dist = np.hypot(x - ox, y - oy)
    rgb = np.zeros((h, w, 3))
    a = np.zeros((h, w))
    for i, c in enumerate(SPECTRUM):
        t = (i - 2.5) * 0.085
        if odd is not None and i == odd:
            t += 0.30
        d = np.abs(np.angle(np.exp(1j * (ang - t))))
        width = 0.010 + dist / w * 0.010
        k = np.exp(-(d / width) ** 2) * np.clip(dist / (w * 0.04), 0, 1) * np.clip(1.15 - dist / w, 0, 1)
        rgb += hexrgb(c) * k[..., None]
        a = np.maximum(a, k)
    rgb = rgb / np.maximum(a[..., None], 1e-6)
    save_rgba(rgb, a, name)


# ---------------------------------------------------------------- screenshots
def crops(shots: Path):
    # coordinates in the 2880 x 1800 captures (1440 x 900 at 2x)
    boxes = {
        "dome": (1940, 150, 2880, 1360),
        "sky": (1940, 1370, 2880, 1800),
        "rail": (0, 96, 720, 1050),
        "photo": (720, 190, 1930, 1800),
    }
    for theme in ("dark", "light"):
        for shot in ("pear", "car"):
            im = Image.open(shots / f"{shot}_{theme}.png").convert("RGB")
            im.save(OUT / f"{shot}_{theme}_full.jpg", quality=90)
            for k, b in boxes.items():
                c = im.crop(b)
                if k == "photo":  # trim the stage background around the photo itself
                    a = np.asarray(c).astype(int)
                    bg = a[5, 5]
                    m = np.abs(a - bg).sum(-1) > 18
                    ys, xs = np.nonzero(m[:-120])  # ignore the caption strip at the bottom
                    c = c.crop((xs.min(), ys.min(), xs.max() + 1, ys.max() + 1))
                c.save(OUT / f"{shot}_{theme}_{k}.jpg", quality=92)
        g = Image.open(shots / f"gallery_{theme}.png").convert("RGB")
        g.save(OUT / f"gallery_{theme}.jpg", quality=90)


if __name__ == "__main__":
    sun_core()
    ray_fan()
    beam()
    scan_bar()
    spectrum_fan()
    spectrum_fan(odd=4, name="spectrum_fan_odd.png")
    if len(sys.argv) > 1:
        crops(Path(sys.argv[1]))
    print(sorted(p.name for p in OUT.iterdir()))
