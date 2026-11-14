import base64
import json
from dataclasses import replace
from pathlib import Path

import numpy as np

from lightaudit.config import Config
from lightaudit.fusion import combine_cues, fuse
from lightaudit.grid import angle_deg, eq_dirs, from_az_el_deg

VEC = Path(__file__).parent / "vectors"
CFG = replace(Config(), tau_img=2.0)


def cone(az, el, sigma=12.0):
    return np.exp(-angle_deg(eq_dirs(), from_az_el_deg(az, el)) ** 2 / (2 * sigma ** 2)).astype(np.float32)


def run(specs, weights=None, cfg=CFG, **kw):
    A = np.stack([cone(*s) for s in specs])
    w = np.full(len(specs), 0.8) if weights is None else np.asarray(weights)
    centers = [from_az_el_deg(s[0], s[1]) for s in specs]
    return A, w, centers, fuse(A, w, None, cfg, centers, **kw)


def test_consistent():
    *_, f = run([(30, 40), (33, 42), (28, 38), (31, 41)])
    assert f["verdict"] == "CONSISTENT" and f["S_img"] < 0.5
    assert angle_deg(f["consensus"]["dir"], from_az_el_deg(30, 40)) < 6


def test_suspicious_outlier():
    *_, f = run([(30, 40), (33, 42), (28, 38), (-120, 30)])
    assert f["verdict"] == "SUSPICIOUS" and f["flagged"] == [3] and f["top_region"] == 3
    assert f["per_region"][3]["angle_deg"] > 90 and f["per_region"][3]["shortfall"] > 5


def test_heavy_outlier_among_three():
    # the outlier carries the largest weight: plain leave-one-out flags everyone; the single-removal step recovers it
    *_, f = run([(30, 40), (33, 42), (-120, 30)], weights=[0.5, 0.5, 0.95])
    assert f["verdict"] == "SUSPICIOUS" and f["flagged"] == [2]


def test_insufficient():
    *_, f = run([(30, 40), (33, 42), (28, 38)], weights=[0.8, 0.8, 0.1])
    assert f["verdict"] == "INSUFFICIENT" and f["n_reliable"] == 2
    *_, f = run([(30, 40, 100.0), (33, 42, 100.0), (28, 38, 100.0)])
    assert f["verdict"] == "INSUFFICIENT" and "broad" in f["reason"]


def test_conflict():
    *_, f = run([(30, 40), (-120, 30), (150, 10), (-30, 70)])
    assert f["verdict"] == "CONFLICT"


def test_unreliable_never_flagged():
    *_, f = run([(30, 40), (33, 42), (28, 38), (-120, 30)], weights=[0.8, 0.8, 0.8, 0.1])
    assert f["verdict"] == "CONSISTENT" and not f["per_region"][3]["flagged"]
    assert f["per_region"][3]["shortfall"] > 5  # still reported


def test_combine_cues():
    P, G = cone(30, 40), cone(35, 45, 8)
    A = combine_cues(P, G, None, CFG)
    assert abs(A.max() - 1) < 1e-6 and np.array_equal(combine_cues(P), P)


def test_write_vectors():
    """Random + structured cases for the JS parity test (viewer/tests/parity.test.mjs)."""
    rng = np.random.default_rng(7)
    cases = []
    layouts = [[(30, 40), (33, 42), (28, 38), (31, 41)], [(30, 40), (33, 42), (28, 38), (-120, 30)],
               [(30, 40), (-120, 30), (150, 10), (-30, 70)], [(30, 40), (33, 42), (-120, 30)]]
    for i in range(10):
        if i < len(layouts):
            specs = layouts[i]
        else:
            base = (rng.uniform(-180, 180), rng.uniform(10, 70))
            specs = [(base[0] + rng.normal(0, 8), base[1] + rng.normal(0, 6), rng.uniform(8, 30)) for _ in range(int(rng.integers(3, 7)))]
            if rng.random() < 0.6:
                specs[int(rng.integers(len(specs)))] = (rng.uniform(-180, 180), rng.uniform(-20, 80), 12.0)
        w = rng.uniform(0.2, 1.0, len(specs))
        excl = rng.random(len(specs)) < 0.1
        A = np.stack([cone(*s) for s in specs])
        centers = [from_az_el_deg(s[0], s[1]).tolist() for s in specs]
        f = fuse(A, w, excl, CFG, centers)
        c = f["consensus"]
        cases.append(dict(
            R=len(specs), A_b64=base64.b64encode(A.astype("<f4").tobytes()).decode(), weights=w.tolist(),
            excluded=excl.tolist(), centers=centers,
            expected=dict(verdict=f["verdict"], S_img=f["S_img"], flagged=f["flagged"], top_region=f["top_region"],
                          consensus_index=None if c is None else c["index"],
                          r68_deg=None if c is None else c["r68_deg"], r95_deg=None if c is None else c["r95_deg"],
                          per_region=[dict(shortfall=p["shortfall"], angle_deg=p["angle_deg"], ref_index=p["ref_index"],
                                           reliable=p["reliable"], flagged=p["flagged"]) for p in f["per_region"]])))
    VEC.mkdir(exist_ok=True)
    (VEC / "fusion_vectors.json").write_text(json.dumps(dict(
        cfg=dict(tau_img=CFG.tau_img, tau_ref=CFG.tau_ref, w_min=CFG.w_min, eps=CFG.eps, min_reliable=CFG.min_reliable,
                 broad_consensus_frac=CFG.broad_consensus_frac),
        note="A_b64 = base64 of little-endian float32 [R, 8192]; indices are 0-based region positions", cases=cases)))
    assert len({c["expected"]["verdict"] for c in cases}) >= 3
