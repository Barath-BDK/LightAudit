"""Synthetic sweep of the cast-shadow consistency test (cues.shadow_pairs.shadow_consistency).

Ground-plane scenes seen by a 60 deg camera; poles cast shadows under one sun. A forged scene replaces one object
with one lit by a second sun at a given angle from the first. Pair endpoints get Gaussian marking noise (px), as a
human clicking points would. Synthetic geometry only: this measures the test, not real-photo performance.

    python eval/shadow_bench.py      # writes data/results/shadow_bench.json
"""
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
from test_shadow_consistency import FOV, H, W, _pairs  # noqa: E402

from lightaudit.cues.shadow_pairs import shadow_consistency  # noqa: E402


def rand_sun(rng, el_lo=20, el_hi=60):
    az, el = rng.uniform(0, 2 * np.pi), np.radians(rng.uniform(el_lo, el_hi))
    return np.array([np.cos(el) * np.sin(az), np.sin(el), np.cos(el) * np.cos(az)])


def main(n_trials=60, n_pairs=5, noise=1.0, thr=3.0):
    rng = np.random.default_rng(0)
    clean = [shadow_consistency(_pairs(rand_sun(rng), n_pairs, rng, noise), H, W, FOV)["score"] for _ in range(n_trials)]
    out = dict(false_alarms=float(np.mean(np.array(clean) > thr)), threshold=thr, n_pairs=n_pairs, noise_px=noise, bins={})
    for lo, hi in ((10, 30), (30, 60), (60, 90), (90, 180)):
        hit, found = [], []
        while len(hit) < n_trials:
            a, b = rand_sun(rng), rand_sun(rng)
            d = np.degrees(np.arccos(np.clip(a @ b, -1, 1)))
            if not lo <= d < hi:
                continue
            r = shadow_consistency(_pairs(a, n_pairs - 1, rng, noise) + _pairs(b, 1, rng, noise), H, W, FOV)
            hit.append(r["score"] > thr)
            found.append(r["score"] > thr and r["suspect"] == n_pairs - 1)
        out["bins"][f"{lo}-{hi}"] = dict(detected=float(np.mean(hit)), located=float(np.mean(found)))
    print(f"{n_pairs} pairs, {noise} px noise, threshold {thr}: false alarms {out['false_alarms']:.3f} | " +
          "  ".join(f"{k} deg: detected {v['detected']:.2f}, right object {v['located']:.2f}" for k, v in out["bins"].items()))
    return out


if __name__ == "__main__":
    res = [main(noise=n) for n in (1.0, 3.0)]
    (ROOT / "data" / "results" / "shadow_bench.json").write_text(json.dumps(res, indent=1))
