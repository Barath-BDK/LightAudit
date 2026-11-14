"""Normal backends: convention check (BUILD_SPEC 17 item 11), ensemble uncertainty, fallback chain."""
import numpy as np
import pytest

from lightaudit import normals as N
from lightaudit.synth import get_sample


@pytest.fixture(scope="module")
def scene():
    s = get_sample(4000, "normal")
    return s.rgb, s.normals_gt.astype(np.float32), s.labels


def _fake(flip):
    """A fake backend that returns the synthetic GT normals in a different axis convention."""
    def run(rgb, fov):
        n = run.gt.copy()
        for ax, f in enumerate(flip):
            if f:
                n[..., ax] *= -1
        return n
    return run


def _err(a, b, mask):
    return float(np.median(np.degrees(np.arccos(np.clip((a * b).sum(-1), -1, 1)))[mask]))


@pytest.mark.parametrize("flip", [(False, True, False), (False, False, True), (False, True, True)])
def test_fix_convention_undoes_y_z_flips(scene, flip):
    rgb, gt, labels = scene
    fake = _fake(flip)
    fake.gt = gt
    log = []
    fixed = N.fix_convention(fake(rgb, 60), log)
    assert _err(fixed, gt, labels > 0) < 1.0
    assert log and "convention check" in log[0]
    if flip[1]:
        assert "flip y" in log[0]
    if flip[2]:
        assert "flip z" in log[0]


def test_correct_convention_is_left_alone(scene):
    rgb, gt, labels = scene
    log = []
    fixed = N.fix_convention(gt, log)
    assert _err(fixed, gt, labels > 0) < 1.0
    assert "z ok" in log[0] and "y ok" in log[0]


def test_predict_normals_with_fake_backends(scene, monkeypatch, tmp_path):
    """Two fake members (one in a flipped convention) -> fused GT, unc floored at 4 deg; x flip override works."""
    rgb, gt, labels = scene
    monkeypatch.setattr(N, "CACHE", tmp_path)
    a, b = _fake((False, False, False)), _fake((False, True, True))
    a.gt = b.gt = gt
    monkeypatch.setitem(N.BACKENDS, "fake_a", a)
    monkeypatch.setitem(N.BACKENDS, "fake_b", b)
    n, unc, info = N.predict_normals(rgb, ("fake_a", "fake_b"), 60)
    assert info["backends"] == ["fake_a", "fake_b"] and info["mode"] == "ensemble"
    assert n.shape == rgb.shape and n.dtype == np.float32 and unc.shape == rgb.shape[:2]
    assert _err(n, gt, labels > 0) < 1.5
    assert unc.min() >= 4.0 - 1e-6
    # single backend: 12 deg + a small texture term, never 0
    n1, unc1, info1 = N.predict_normals(rgb, ("fake_a",), 60)
    assert info1["mode"] == "single" and 12.0 <= unc1.min() and unc1.max() <= 16.0 + 1e-5
    # user override flips x after the automatic check
    nx, _, _ = N.predict_normals(rgb, ("fake_a",), 60, flips=(True, False, False))
    assert np.allclose(nx[..., 0], -n1[..., 0], atol=1e-5)


def test_fallback_chain_when_everything_fails(scene, monkeypatch, tmp_path):
    rgb, gt, labels = scene
    monkeypatch.setattr(N, "CACHE", tmp_path)

    def boom(rgb, fov):
        raise RuntimeError("forced failure")

    for k in list(N.BACKENDS):
        monkeypatch.setitem(N.BACKENDS, k, boom)
    n, unc, info = N.predict_normals(rgb, ("dsine", "stablenormal"), 60)
    assert info["mode"] == "pseudo" and info["backends"] == []
    assert set(info["failed"]) >= {"dsine", "stablenormal", "marigold", "depth_anything"}
    assert any("NO NORMAL BACKEND WORKED" in m for m in info["log"])
    assert np.allclose(unc, 30.0)
    assert np.isfinite(n).all() and np.allclose(np.linalg.norm(n, axis=-1), 1, atol=1e-4)
    assert (n[..., 2] > 0).all()


def test_fallback_uses_next_backend_in_chain(scene, monkeypatch, tmp_path):
    rgb, gt, labels = scene
    monkeypatch.setattr(N, "CACHE", tmp_path)

    def boom(rgb, fov):
        raise ImportError("not installed")

    good = _fake((False, False, False))
    good.gt = gt
    for k in ("dsine", "stablenormal", "marigold"):
        monkeypatch.setitem(N.BACKENDS, k, boom)
    monkeypatch.setitem(N.BACKENDS, "depth_anything", good)
    n, unc, info = N.predict_normals(rgb, ("dsine", "stablenormal"), 60)
    assert info["mode"] == "fallback" and info["backends"] == ["depth_anything"]
    assert _err(n, gt, labels > 0) < 1.0 and unc.min() >= 12.0


def test_depth_to_normals_plane():
    """A tilted plane's disparity map gives a constant normal facing the camera."""
    H, W = 60, 80
    v = np.arange(H)[:, None] * np.ones((1, W))
    n = N.depth_to_normals((v / H).astype(np.float32), 60)
    c = n[10:-10, 10:-10].reshape(-1, 3)
    assert (c[:, 2] > 0).all()
    assert c.std(0).max() < 0.15


def test_backends_available_keys():
    av = N.backends_available()
    assert set(av) == {"sam", "dsine", "stablenormal", "marigold", "depth_anything"}
    assert all(isinstance(v, bool) for v in av.values())
