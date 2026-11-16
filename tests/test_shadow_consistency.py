"""Shadow-consistency test (cues.shadow_pairs.shadow_consistency): pairs from one sun fit one light; a pair from a
pasted object lit by another sun breaks the fit and is singled out by leave-one-out."""
import numpy as np

from lightaudit.cues.shadow_pairs import shadow_consistency

H, W, FOV = 600, 900, 60.0
F = (W / 2) / np.tan(np.radians(FOV) / 2)


def _proj(X):
    return (W / 2 + F * X[0] / -X[2], H / 2 - F * X[1] / -X[2])


def _pairs(l, n, rng, noise=0.7):
    l = l / np.linalg.norm(l)
    out = []
    for _ in range(n):
        g = np.array([rng.uniform(-4, 4), -1.5, rng.uniform(-14, -6)])
        p = g + np.array([0, rng.uniform(0.8, 2.0), 0])  # top of a pole standing on the ground
        s = p - (p[1] + 1.5) / l[1] * l  # where the sun ray through p hits the ground
        jit = lambda q: tuple(np.array(_proj(q)) + rng.normal(0, noise, 2))  # noqa: E731
        out.append((jit(p), jit(s)))
    return out


def test_one_sun_fits_and_forged_pair_is_found():
    rng = np.random.default_rng(1)
    sun = np.array([0.6, 0.6, 0.3])
    clean = _pairs(sun, 6, rng)
    r = shadow_consistency(clean, H, W, FOV)
    assert r is not None and r["score"] < 3.0
    forged = clean[:5] + _pairs(np.array([-0.6, 0.5, -0.4]), 1, rng)
    f = shadow_consistency(forged, H, W, FOV)
    assert f["score"] > 3.0
    assert f["suspect"] == 5 and f["loo"][5] < 3.0
