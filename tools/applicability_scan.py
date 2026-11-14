"""E11: run the pipeline on every photo in a folder and summarise how often it can decide at all.

    python tools/applicability_scan.py data/real [--regions sam] [--normals dsine,stablenormal]

Writes data/results/applicability.json and applicability.csv. With --calibrate it instead writes a calibration
file from the folder (see tools/calibrate_on_folder.py).
"""
from __future__ import annotations

import argparse
import csv
import json
import tempfile
from collections import Counter
from pathlib import Path

from lightaudit.cli import audit_image
from lightaudit.config import ROOT

EXT = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


def scan(folder: Path, regions: str = "sam", normals: str = "dsine,stablenormal", calib=None) -> list[dict]:
    """One row per image: verdict, S_img, number of reliable regions, reasons of the unreliable ones."""
    rows = []
    with tempfile.TemporaryDirectory() as tmp:
        for p in sorted(q for q in Path(folder).iterdir() if q.suffix.lower() in EXT):
            try:
                d = audit_image(p, name=f"scan_{len(rows)}", regions=regions, normals=normals, calib=calib,
                                root=Path(tmp), progress=lambda m: None)
                m = json.loads((d / "manifest.json").read_text())
                rows.append(dict(image=p.name, verdict=m["fusion"]["verdict"], S_img=m["fusion"]["S_img"],
                                 n_reliable=m["fusion"]["n_reliable"], n_regions=len(m["regions"]),
                                 reasons=[r["reason"] for r in m["regions"] if not r["reliable"] and r["reason"]],
                                 normals=m["normals_backend"], regions_backend=m["regions_backend"]))
            except Exception as e:  # one unreadable photo must not stop the scan
                rows.append(dict(image=p.name, verdict="ERROR", S_img=None, n_reliable=0, n_regions=0,
                                 reasons=[f"{type(e).__name__}: {e}"], normals="", regions_backend=""))
            print(f"  {rows[-1]['image']}: {rows[-1]['verdict']}")
    return rows


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("folder", type=Path)
    ap.add_argument("--regions", default="sam")
    ap.add_argument("--normals", default="dsine,stablenormal")
    a = ap.parse_args()
    out = ROOT / "data" / "results"
    out.mkdir(parents=True, exist_ok=True)
    rows = scan(a.folder, a.regions, a.normals) if a.folder.is_dir() else []
    if not rows:
        print(f"No images in {a.folder}. Drop outdoor photos there and run again.")
        (out / "applicability.json").write_text(json.dumps({"status": "not run: folder empty", "n": 0}))
        return
    ok = [r for r in rows if r["verdict"] != "ERROR"]
    summary = dict(status="ok", n=len(rows), n_errors=len(rows) - len(ok),
                   frac_ge3_reliable=sum(r["n_reliable"] >= 3 for r in ok) / max(len(ok), 1),
                   verdicts=dict(Counter(r["verdict"] for r in rows)),
                   abstention_reasons=dict(Counter(x for r in ok for x in r["reasons"]).most_common()),
                   caveat="real photos, ground truth unknown: this measures applicability, not accuracy", rows=rows)
    (out / "applicability.json").write_text(json.dumps(summary, indent=1))
    with open(out / "applicability.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["image", "verdict", "S_img", "n_reliable", "n_regions"])
        w.writerows([r["image"], r["verdict"], r["S_img"], r["n_reliable"], r["n_regions"]] for r in rows)
    print(json.dumps({k: v for k, v in summary.items() if k != "rows"}, indent=1))


if __name__ == "__main__":
    main()
