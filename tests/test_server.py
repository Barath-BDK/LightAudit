"""FastAPI server: health, redirect, static mounts, input validation (no heavy audits are run here)."""
import io

import numpy as np
import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")
from fastapi.testclient import TestClient  # noqa: E402

from lightaudit import server  # noqa: E402


@pytest.fixture(scope="module")
def client():
    return TestClient(server.app)


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    j = r.json()
    assert j["status"] == "ok" and set(j["backends"]) == {"sam", "dsine", "stablenormal", "marigold", "depth_anything"}


def test_root_redirects_to_viewer(client):
    r = client.get("/", follow_redirects=False)
    assert r.status_code in (302, 307) and r.headers["location"] == "/viewer/index.html"


def test_static_mounts_read_only(client):
    if (server.BUNDLES / "index.json").exists():
        assert client.get("/bundles/index.json").status_code == 200
        assert client.post("/bundles/index.json").status_code == 405
    assert client.get("/bundles/../lightaudit/config.py").status_code == 404


def test_job_status_404(client):
    assert client.get("/api/jobs/" + "0" * 32).status_code == 404
    assert client.get("/api/jobs/not-a-job").status_code == 404


@pytest.mark.parametrize("bad", ["../demo_consistent", "a/b", "x y", "..", "demo.consistent", ""])
def test_attack_rejects_bad_bundle_names(client, bad):
    r = client.post("/api/attack", json={"bundle": bad, "region": 1, "variants": ["T1"]})
    assert r.status_code == 400
    with pytest.raises(ValueError):
        server.check_bundle_name(bad)


def test_attack_unknown_bundle_and_variant(client):
    assert client.post("/api/attack", json={"bundle": "no_such_bundle_xyz", "region": 1}).status_code == 404
    if (server.BUNDLES / "demo_consistent" / "manifest.json").exists():
        r = client.post("/api/attack", json={"bundle": "demo_consistent", "region": 1, "variants": ["T9"]})
        assert r.status_code == 400


def test_audit_upload_validation(client):
    r = client.post("/api/audit", files={"image": ("x.png", b"not an image", "image/png")})
    assert r.status_code == 400
    from PIL import Image
    buf = io.BytesIO()
    Image.fromarray(np.zeros((8, 8, 3), np.uint8)).save(buf, "PNG")
    r = client.post("/api/audit", files={"image": ("x.png", buf.getvalue(), "image/png")}, data={"regions": "manual:../x"})
    assert r.status_code == 400
    r = client.post("/api/audit", files={"image": ("x.png", buf.getvalue(), "image/png")}, data={"normals": "evil"})
    assert r.status_code == 400
    big = b"0" * (server.MAX_UPLOAD + 10)
    assert client.post("/api/audit", files={"image": ("x.png", big, "image/png")}).status_code == 413


def test_sanitize_stem():
    assert server.sanitize_stem("../../evil name!.png") == "evil_name"
    assert server.sanitize_stem(None) == "upload"
    assert server.sanitize_stem("....") == "upload"
