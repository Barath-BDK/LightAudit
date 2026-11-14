import json

import pytest
from conftest import spliced

from lightaudit.bundle import validate_bundle, write_bundle
from lightaudit.grid import NA, NE


def test_bundle_round_trip(tmp_path):
    s, comp, res = spliced(4000)
    d = write_bundle(res, "t_bundle", "test", "test bundle", root=tmp_path)
    assert validate_bundle(d) == []
    m = json.loads((d / "manifest.json").read_text())
    assert (d / "landscapes.bin").stat().st_size == len(m["regions"]) * NE * NA * 4
    assert m["fusion"]["verdict"] == res["fusion"]["verdict"]
    assert m["ground_truth"]["delta_deg"] == pytest.approx(120, abs=0.1)
    assert json.loads((tmp_path / "index.json").read_text())[0]["name"] == "t_bundle"
    (d / "heat.png").unlink()
    assert any("heat.png" in e for e in validate_bundle(d))
