"""Learned intrinsic decomposition (Careaga & Aksoy, package `intrinsic`) vs band-guarded Retinex in the
marked-area check, on real objects (MIT Intrinsic Images), same protocol as eval/mit_panel.py and eval/mit_attack.py.

Per image both albedo estimates feed the same two statistics: T (shared light, shape only) and Tr (shared
material). Splice variants: plain (1.5 px feather), colour-matched (attacks.t1_color_transfer), 8 px feather and
Poisson blending (cv2.seamlessClone). The network's albedo is cached per image (data/mit_intrinsic/<obj>/iid/).
Comparison at matched held-out false alarms via eval/panel_compare.compare (even-index objects calibrate).

    python eval/intrinsic_bench.py [n_lamps] [n_parts] [--resume]   # default 10 lamps, 4 parts; --resume skips saved objects
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "eval"))
VARIANTS = ("splice", "harmonised", "feather8", "poisson")


def albedo_cached(obj_dir: Path, lin: np.ndarray) -> np.ndarray:
    from lightaudit.residual import learned_albedo
    key = hashlib.sha1(np.ascontiguousarray(np.round(lin * 4096).astype(np.uint16)).tobytes()).hexdigest()[:16]
    f = obj_dir / "iid" / f"{key}.npy"
    if f.exists():
        return np.load(f).astype(np.float64)
    f.parent.mkdir(exist_ok=True)
    a = learned_albedo(lin)
    np.save(f, a.astype(np.float32))
    return a


def run_obj(obj: str, n_lamps: int, n_parts: int) -> list[dict]:
    from eval import mit_bench as mb
    from lightaudit.attacks import t1_color_transfer
    from lightaudit.config import Config
    from lightaudit.regions import apply_roi
    from lightaudit.residual import panel_shared
    cfg = Config()
    d = mb.load(obj)
    N = np.load(mb.DATA / obj / "prep.npz")["normals_depth_anything"].astype(np.float32)
    up = 2
    big = lambda x, it: cv2.resize(x, (x.shape[1] * up, x.shape[0] * up), interpolation=it)  # noqa: E731
    n_b = big(N, cv2.INTER_LINEAR)
    n_b /= np.maximum(np.linalg.norm(n_b, axis=-1, keepdims=True), 1e-6)
    lab = mb.parts(d["mask"], 4)
    mask_b = big(d["mask"].astype(np.uint8), cv2.INTER_NEAREST).astype(np.int32)
    unc = np.full(mask_b.shape, cfg.single_backend_unc, np.float32)
    to8 = lambda lin: np.round(np.clip(big((np.clip(lin, 0, 1) ** (1 / 2.2)).astype(np.float32), cv2.INTER_CUBIC), 0, 1) * 255) / 255  # noqa: E731
    g3 = lambda Y: np.repeat((Y * 255).astype(np.uint8)[..., None], 3, 2)  # noqa: E731
    rng = np.random.default_rng(__import__("zlib").crc32(obj.encode()))
    rows = []
    for part in range(1, 1 + n_parts):
        roi = lab == part
        if roi.sum() < 400:
            continue
        roi_b = big(roi.astype(np.uint8), cv2.INTER_NEAREST)
        labels, meta = apply_roi(mask_b, [dict(id=1, name=obj, source="mask", excluded=False)], roi_b.astype(bool), cfg)
        regs = [dict(id=m["id"], name=m["name"]) for m in meta]
        roi_id = next(m["id"] for m in meta if m["name"] == "ROI")
        a15 = np.clip(cv2.GaussianBlur(roi.astype(np.float32), (0, 0), 1.5), 0, 1)
        a8 = np.clip(cv2.GaussianBlur(roi.astype(np.float32), (0, 0), 4.0), 0, 1)  # 4 px before 2x upscale = 8 px
        ys, xs = np.nonzero(roi_b)
        centre = (int((xs.min() + xs.max() + 1) // 2), int((ys.min() + ys.max() + 1) // 2))
        for i in range(min(n_lamps, mb.NL)):
            j = int(rng.choice([x for x in range(mb.NL) if x != i]))
            li, lj = d["lin"][i], d["lin"][j]
            Yi = to8(li)
            imgs = {"clean": Yi, "splice": to8(li * (1 - a15) + lj * a15), "feather8": to8(li * (1 - a8) + lj * a8)}
            imgs["harmonised"] = t1_color_transfer(g3(imgs["splice"]), labels == roi_id, labels, cfg)[..., 0].astype(np.float32) / 255
            try:
                imgs["poisson"] = cv2.seamlessClone(g3(to8(lj)), g3(Yi), (roi_b * 255).astype(np.uint8), centre, cv2.NORMAL_CLONE)[..., 0].astype(np.float32) / 255
            except cv2.error:
                pass
            for kind, Y in imgs.items():
                Y = Y.astype(np.float32)
                alb = albedo_cached(mb.DATA / obj, Y.astype(np.float64) ** 2.2)
                kw = dict(thr=cfg.retinex_thr, band=cfg.panel_band)
                rows.append(dict(obj=obj, part=part, lamp=i, kind=kind,
                                 T=panel_shared(Y, n_b, unc, labels, regs, cfg, shape_only=True, **kw),
                                 Tr=panel_shared(Y, n_b, unc, labels, regs, cfg, **kw),
                                 Tl=panel_shared(Y, n_b, unc, labels, regs, cfg, shape_only=True, alb_map=alb),
                                 Trl=panel_shared(Y, n_b, unc, labels, regs, cfg, alb_map=alb)))
    return rows


def main():
    from eval import mit_bench as mb
    from panel_compare import compare
    n_lamps = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    n_parts = int(sys.argv[2]) if len(sys.argv) > 2 else 4
    out_rows = ROOT / "data" / "results" / "intrinsic_rows.json"
    rows = json.loads(out_rows.read_text()) if "--resume" in sys.argv and out_rows.exists() else []
    done, t0 = {r["obj"] for r in rows}, time.time()
    for k, obj in enumerate(mb.objects()):
        if obj in done:
            continue
        rows += run_obj(obj, n_lamps, n_parts)
        print(f"{obj} done ({k + 1}/20, {time.time() - t0:.0f}s)", flush=True)
        (ROOT / "data" / "results" / "intrinsic_rows.json").write_text(json.dumps(rows))
    sets = {"Retinex (T+Tr)": ("T", "Tr"), "learned (T+Tr)": ("Tl", "Trl"), "both (4 tests)": ("T", "Tr", "Tl", "Trl")}
    out = {}
    for v in VARIANTS:
        sub = [r for r in rows if r["kind"] in ("clean", v)]
        print(f"--- {v}", flush=True)
        out[v] = dict(learned=compare(sub, sets, v, "Retinex (T+Tr)", "learned (T+Tr)"),
                      both=compare(sub, sets, v, "Retinex (T+Tr)", "both (4 tests)", verbose=False))
    (ROOT / "data" / "results" / "intrinsic_bench.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
