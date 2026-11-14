"""Recalibrate the alarm level on a folder of your own UNEDITED photos (BUILD_SPEC 9.2).

    python tools/calibrate_on_folder.py data/real_unedited --out calib_real.json

Keeps the posterior shape (h, T) of the default calibration and replaces tau_img_05 / tau_img_10 by the
split-conformal quantiles of the photos' image scores. Needs roughly 20+ decided photos for alpha = 0.05.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from applicability_scan import scan  # noqa: E402

from lightaudit.calibrate import conformal_quantile  # noqa: E402
from lightaudit.config import load_calib  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("folder", type=Path)
    ap.add_argument("--out", type=Path, default=Path("calib_real.json"))
    ap.add_argument("--regions", default="sam")
    ap.add_argument("--normals", default="dsine,stablenormal")
    a = ap.parse_args()
    rows = scan(a.folder, a.regions, a.normals) if a.folder.is_dir() else []
    scores = [r["S_img"] for r in rows if r["verdict"] not in ("ERROR", "INSUFFICIENT")]
    if not scores:
        raise SystemExit(f"No decided photos in {a.folder}: nothing to calibrate on.")
    calib = dict(load_calib())
    for key, alpha in (("tau_img_05", 0.05), ("tau_img_10", 0.10)):
        q = conformal_quantile(scores, alpha)
        if not math.isfinite(q):  # too few photos for this alpha: the largest score is the best available bound
            q = max(scores)
            calib[key + "_note"] = f"only {len(scores)} photos; used the maximum score, no {alpha:.0%} guarantee"
        calib[key] = q
    calib.update(source=a.out.name, n_cal=len(rows), n_scored=len(scores),
                 insufficient_rate=1 - len(scores) / len(rows), normals=a.normals, folder=str(a.folder))
    a.out.write_text(json.dumps(calib, indent=1))
    print(json.dumps(calib, indent=1))


if __name__ == "__main__":
    main()
