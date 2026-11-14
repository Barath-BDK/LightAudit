"""Download the Three.js files the viewer needs into viewer/vendor/ so it works offline.

Usage:  python tools/fetch_viewer_vendor.py [--version 0.160.0] [--force]

Fetches the ES-module build of Three.js plus the add-ons the light dome uses (OrbitControls and the
fat-line classes Line2 / LineMaterial / LineGeometry / LineSegments2 / LineSegmentsGeometry) from jsDelivr.
viewer/index.html points its import map at these files and falls back to the same CDN URLs when they are absent.
"""
from __future__ import annotations

import argparse
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VENDOR = ROOT / "viewer" / "vendor"
CDN = "https://cdn.jsdelivr.net/npm/three@{version}/"

FILES = {
    "build/three.module.js": "three.module.js",
    "examples/jsm/controls/OrbitControls.js": "addons/controls/OrbitControls.js",
    "examples/jsm/lines/Line2.js": "addons/lines/Line2.js",
    "examples/jsm/lines/LineMaterial.js": "addons/lines/LineMaterial.js",
    "examples/jsm/lines/LineGeometry.js": "addons/lines/LineGeometry.js",
    "examples/jsm/lines/LineSegments2.js": "addons/lines/LineSegments2.js",
    "examples/jsm/lines/LineSegmentsGeometry.js": "addons/lines/LineSegmentsGeometry.js",
    "LICENSE": "LICENSE.three.txt",
}


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "lightaudit-vendor-fetch"})
    with urllib.request.urlopen(req, timeout=60) as r:
        if r.status != 200:
            raise RuntimeError(f"HTTP {r.status} for {url}")
        return r.read()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--version", default="0.160.0")
    ap.add_argument("--force", action="store_true", help="re-download files that already exist")
    a = ap.parse_args()
    base = CDN.format(version=a.version)
    ok = True
    for src, dst in FILES.items():
        out = VENDOR / dst
        if out.exists() and not a.force:
            print(f"  have {dst}")
            continue
        try:
            data = fetch(base + src)
        except Exception as e:  # network failure: report and keep going, the viewer then uses the CDN
            print(f"  FAILED {src}: {e}", file=sys.stderr)
            ok = False
            continue
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(data)
        print(f"  got  {dst} ({len(data) / 1024:.0f} KB)")
    (VENDOR / "VERSION.txt").write_text(f"three@{a.version} from {base}\n")
    print("done" if ok else "some files failed; the viewer will fall back to the CDN for them")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
