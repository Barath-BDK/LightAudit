import json
from pathlib import Path

import numpy as np

from lightaudit import grid

VEC = Path(__file__).parent / "vectors"


def test_shapes_and_weights():
    d = grid.eq_dirs()
    assert d.shape == (8192, 3)
    assert np.allclose(np.linalg.norm(d, axis=1), 1, atol=1e-5)
    assert abs(grid.area_weights().sum() - 1) < 1e-9
    assert d[0][1] > 0.99 and d[-1][1] < -0.99  # top row = up


def test_round_trip():
    d = grid.eq_dirs()
    for k in np.random.default_rng(0).integers(0, 8192, 300):
        assert grid.dir_to_index(d[k]) == k


def test_axes():
    assert grid.az_el_deg([0, 0, 1]) == (0.0, 0.0)  # az 0 = toward the viewer
    az, el = grid.az_el_deg([1, 0, 0])
    assert abs(az - 90) < 1e-6 and abs(el) < 1e-6
    assert np.allclose(grid.from_az_el_deg(30, 40), grid.from_az_el_deg(*grid.az_el_deg(grid.from_az_el_deg(30, 40))))


def test_window_wraps_and_coarse():
    w = grid.window_index(5 * 128 + 0, 6)
    assert len(w) == 12 * 13 and (w % 128).max() == 127  # clipped at the pole, wrapped in azimuth
    assert len(grid.coarse_index(4)) == 512


def test_hpd_monotone():
    P = np.exp(-grid.angle_deg(grid.eq_dirs(), [0, 1, 0]) ** 2 / (2 * 15 ** 2))
    (f68, f95), (m68, m95) = grid.hpd(P)
    assert f68 < f95 and m68.sum() < m95.sum() and (m95 | m68).sum() == m95.sum()
    assert 10 < grid.cone_half_angle_deg(f68) < 30


def test_write_vectors():
    rng = np.random.default_rng(1)
    d, aw = grid.eq_dirs(), grid.area_weights()
    ks = rng.integers(0, 8192, 60).tolist()
    rnd = rng.normal(size=(60, 3))
    rnd /= np.linalg.norm(rnd, axis=1, keepdims=True)
    out = dict(NA=grid.NA, NE=grid.NE,
               cells=[dict(k=k, dir=d[k].tolist(), area=float(aw[k])) for k in ks],
               dir_to_index=[dict(dir=v.tolist(), k=grid.dir_to_index(v)) for v in rnd],
               az_el=[dict(dir=v.tolist(), az_el=list(grid.az_el_deg(v))) for v in rnd[:10]])
    VEC.mkdir(exist_ok=True)
    (VEC / "grid_vectors.json").write_text(json.dumps(out))
