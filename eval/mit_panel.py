"""Panel-mode calibration and held-out test on real objects, through the pipeline's own code path.

Uses the MIT Intrinsic Images objects (see eval/mit_bench.py). Objects with an even index calibrate the two
panel thresholds (split-conformal, alpha/2 each); objects with an odd index are the held-out test: clean images
(false alarms) and feathered within-object splices (detection), by lighting-angle bin.

    python eval/mit_panel.py            # writes lightaudit/calib_real_panel.json and data/results/real_panel.json
"""
from __future__ import annotations

import json
import multiprocessing as mp
import sys
from dataclasses import replace
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
OUT = ROOT / "lightaudit" / "calib_real_panel.json"


def _one(obj):
    """All (lamp, part) clean statistics and one splice per (lamp, part) for an object."""
    from eval import mit_bench as mb
    from lightaudit.config import Config
    from lightaudit.regions import apply_roi
    from lightaudit.residual import panel_shared
    cfg = Config()
    d = mb.load(obj)
    mb.prepare(obj)
    N = np.load(mb.DATA / obj / "prep.npz")["normals_depth_anything"].astype(np.float32)
    up = 2
    big = lambda x, it: cv2.resize(x, (x.shape[1] * up, x.shape[0] * up), interpolation=it)  # noqa: E731
    n_b = big(N, cv2.INTER_LINEAR)
    n_b /= np.maximum(np.linalg.norm(n_b, axis=-1, keepdims=True), 1e-6)
    lab = mb.parts(d["mask"], 4)
    mask_b = big(d["mask"].astype(np.uint8), cv2.INTER_NEAREST).astype(np.int32)
    unc = np.full(mask_b.shape, cfg.single_backend_unc, np.float32)
    P = mb.pixel_data(obj, "normals_depth_anything", 4)
    ld = P["dirs"][mb.lamp_dirs(P["parts"])] if len(P["parts"]) >= 3 else None
    rng = np.random.default_rng(__import__("zlib").crc32(obj.encode()))  # deterministic per object
    rows = []
    for part in range(1, 5):
        roi = lab == part
        if roi.sum() < 400:
            continue
        a = np.clip(cv2.GaussianBlur(roi.astype(np.float32), (0, 0), 1.5), 0, 1)
        labels, meta = apply_roi(mask_b, [dict(id=1, name=obj, source="mask", excluded=False)], big(roi.astype(np.uint8), cv2.INTER_NEAREST).astype(bool), cfg)
        regs = [dict(id=m["id"], name=m["name"]) for m in meta]
        for i in range(mb.NL):
            j = int(rng.choice([x for x in range(mb.NL) if x != i]))
            for tag, lin in (("clean", d["lin"][i]), ("splice", d["lin"][i] * (1 - a) + d["lin"][j] * a)):
                Y = big((np.clip(lin, 0, 1) ** (1 / 2.2)).astype(np.float32), cv2.INTER_CUBIC)
                Y = np.round(np.clip(Y, 0, 1) * 255) / 255  # 8-bit, as a real photo
                T = panel_shared(Y, n_b, unc, labels, regs, cfg, retinex=True, thr=cfg.retinex_thr, band=cfg.panel_band, shape_only=True)
                Tr = panel_shared(Y, n_b, unc, labels, regs, cfg, retinex=True, thr=cfg.retinex_thr, band=cfg.panel_band)
                if T is None or Tr is None:
                    continue
                ang = float(np.degrees(np.arccos(np.clip(ld[i] @ ld[j], -1, 1)))) if ld is not None else float("nan")
                rows.append(dict(obj=obj, part=part, lamp=i, src=j, kind=tag, T=T, Tr=Tr, angle=ang))
    return rows


def main():
    from eval import mit_bench as mb
    from lightaudit.calibrate import conformal_quantile
    objs = mb.objects()
    with mp.Pool(5) as p:
        rows = [r for rs in p.map(_one, objs) for r in rs]
    cal_objs, test_objs = objs[0::2], objs[1::2]
    cal = [r for r in rows if r["obj"] in cal_objs and r["kind"] == "clean"]
    res = dict(calibration_objects=cal_objs, test_objects=test_objs, n_cal=len(cal), levels={})
    for alpha in (0.05, 0.10):
        tT = conformal_quantile([r["T"] for r in cal], alpha / 2)
        tR = conformal_quantile([r["Tr"] for r in cal], alpha / 2)
        hit = lambda r: (r["T"] > tT) or (r["Tr"] > tR)  # noqa: E731
        tc = [r for r in rows if r["obj"] in test_objs and r["kind"] == "clean"]
        ts = [r for r in rows if r["obj"] in test_objs and r["kind"] == "splice"]
        lv = dict(tau_T=tT, tau_Tr=tR, false_alarms=float(np.mean([hit(r) for r in tc])), n_clean=len(tc),
                  detected=float(np.mean([hit(r) for r in ts])), n_splice=len(ts), by_angle={}, by_object={})
        for lo, hi in ((0, 25), (25, 50), (50, 80), (80, 181)):
            b = [r for r in ts if lo <= r["angle"] < hi]
            if b:
                lv["by_angle"][f"{lo}-{hi}"] = dict(detected=float(np.mean([hit(r) for r in b])), n=len(b))
        for o in test_objs:
            lv["by_object"][o] = dict(false_alarms=float(np.mean([hit(r) for r in tc if r["obj"] == o] or [0])),
                                      detected=float(np.mean([hit(r) for r in ts if r["obj"] == o] or [0])))
        res["levels"][str(alpha)] = lv
        print(f"alpha {alpha}: tau_T {tT:.2f} tau_Tr {tR:.2f} | held-out false alarms {lv['false_alarms']:.3f} (n {len(tc)}) | "
              f"detected {lv['detected']:.3f} (n {len(ts)}) | by angle {{" + ", ".join(f"{k}: {v['detected']:.2f} (n {v['n']})" for k, v in lv["by_angle"].items()) + "}", flush=True)
    a5, a10 = res["levels"]["0.05"], res["levels"]["0.1"]
    OUT.write_text(json.dumps(dict(tau_panel_T_05=a5["tau_T"], tau_panel_Tr_05=a5["tau_Tr"], tau_panel_T_10=a10["tau_T"],
                                   tau_panel_Tr_10=a10["tau_Tr"], n_cal=len(cal), objects=cal_objs,
                                   source="MIT Intrinsic Images, even-index objects, Depth Anything normals"), indent=1))
    (ROOT / "data" / "results").mkdir(parents=True, exist_ok=True)
    (ROOT / "data" / "results" / "real_panel.json").write_text(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
