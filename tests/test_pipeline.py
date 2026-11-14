"""End-to-end checks on synthetic scenes (BUILD_SPEC 17.6)."""
from conftest import CFG, SEEDS, pristine, spliced

from lightaudit.pipeline import audit_sample


def test_consistent_scenes():
    assert sum(pristine(sd)[1]["fusion"]["verdict"] == "CONSISTENT" for sd in SEEDS) >= 2


def test_spliced_car_is_flagged():
    ok = 0
    for sd in SEEDS:
        _, _, res = spliced(sd)
        f = res["fusion"]
        ok += f["verdict"] == "SUSPICIOUS" and res["regions"][f["top_region"]]["name"] == "car body"
    assert ok >= 2


def test_overcast_not_suspicious():
    assert sum(pristine(sd, "overcast")[1]["fusion"]["verdict"] != "SUSPICIOUS" for sd in SEEDS) >= 2


def test_reuse_is_exact_and_text_is_honest():
    s, base = pristine(4000)
    again = audit_sample(s, cfg=CFG, reuse=base, changed=[])
    assert again["fusion"]["S_img"] == base["fusion"]["S_img"]
    for sd in SEEDS:
        f = spliced(sd)[2]["fusion"]
        assert f["verdict"] != "SUSPICIOUS" or "human review" in f["text"]
