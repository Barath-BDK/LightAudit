"""Real-image panel-mode demos from the MIT Intrinsic Images objects (needs data/mit_intrinsic, see eval/mit_bench.py).

For an object: a clean image (all of it under lamp i) and a spliced one (one part taken from lamp j, feathered),
each audited in panel mode with that part as the ROI and written as a viewer bundle.

    python tools/make_mit_demo.py                      # a default set of objects
    python tools/make_mit_demo.py cup2 3 8             # object, lamp i, lamp j
"""
from __future__ import annotations

import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from eval import mit_bench as mb  # noqa: E402
from lightaudit.bundle import write_bundle  # noqa: E402
from lightaudit.config import calibrated  # noqa: E402
from lightaudit.pipeline import audit  # noqa: E402
from lightaudit.regions import apply_roi, auto_exclude  # noqa: E402


def real_cfg():
    """Default calibration with the panel thresholds learned on real clean objects (eval/mit_panel.py)."""
    from lightaudit.config import real_panel
    return real_panel(calibrated())


def demo(obj: str, i: int, j: int, part: int = 1, k: int = 4, up: int = 2, feather: float = 1.5) -> list[dict]:
    d = mb.load(obj)
    mb.prepare(obj)
    N = np.load(mb.DATA / obj / "prep.npz")["normals_depth_anything"].astype(np.float32)
    lab = mb.parts(d["mask"], k)
    roi = lab == part
    a = np.clip(cv2.GaussianBlur(roi.astype(np.float32), (0, 0), feather), 0, 1)
    out = []
    for tag, lin in (("clean", d["lin"][i]), ("spliced", d["lin"][i] * (1 - a) + d["lin"][j] * a)):
        rgb = (np.clip(lin, 0, 1) ** (1 / 2.2) * 255).astype(np.uint8)
        rgb = np.repeat(rgb[..., None], 3, 2)
        big = lambda x, interp: cv2.resize(x, (x.shape[1] * up, x.shape[0] * up), interpolation=interp)  # noqa: E731
        rgb_b = big(rgb, cv2.INTER_CUBIC)
        n_b = big(N, cv2.INTER_LINEAR)
        n_b /= np.maximum(np.linalg.norm(n_b, axis=-1, keepdims=True), 1e-6)
        labels = big(d["mask"].astype(np.uint8), cv2.INTER_NEAREST).astype(np.int32)
        meta = [dict(id=1, name=obj, source="mask", excluded=False)]
        cfg = real_cfg()
        labels, meta = apply_roi(labels, meta, big(roi.astype(np.uint8), cv2.INTER_NEAREST).astype(bool), cfg)
        meta = auto_exclude(rgb_b, labels, meta, cfg)
        unc = np.full(labels.shape, cfg.single_backend_unc, np.float32)
        res = audit(rgb_b, n_b, unc, labels, meta, cfg, 60.0, seed=0)
        res.update(calib_source="calib_default.json + calib_real_panel.json (panel thresholds from real objects)", ground_truth=None, normals_backend="depth_anything", regions_backend="mask + ROI",
                   backends_log=[f"MIT Intrinsic Images object '{obj}', lamp {i + 1}" + (f", ROI from lamp {j + 1}" if tag == "spliced" else "")])
        f = res["fusion"]
        r = next(x for x in res["regions"] if x["name"] == "ROI")
        truth = ("unedited: the whole object is under one lamp" if tag == "clean"
                 else f"edited: the ROI was taken from a photo of the same object under a different lamp (lamp {j + 1})")
        name = f"real_mit_{obj}_{tag}"
        write_bundle(res, name, f"Real object ({obj}), {tag}",
                     f"Real photo from the MIT Intrinsic Images dataset, panel mode. Truth: {truth}. "
                     f"Audit verdict: {f['verdict']}.", source="real")
        out.append(dict(name=name, verdict=f["verdict"], panel_T=r.get("panel_T"), panel_Tr=r.get("panel_Tr"), panel_z=r.get("panel_z")))
        print(f"  {name}: {f['verdict']}  T {r.get('panel_T')}  Tr {r.get('panel_Tr')}  ratio {r.get('panel_z')}", flush=True)
    return out


if __name__ == "__main__":
    if len(sys.argv) >= 4:
        demo(sys.argv[1], int(sys.argv[2]) - 1, int(sys.argv[3]) - 1)
    else:
        for obj, i, j in (("cup2", 1, 8), ("potato", 2, 9), ("turtle", 3, 9), ("pear", 0, 6), ("frog2", 1, 7), ("box", 0, 5)):  # held-out objects
            demo(obj, i, j)
