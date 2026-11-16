"""Does the real-photo panel test survive brightness / colour matching of the pasted area?

Same protocol as eval/mit_panel.py (10 objects calibrate, 10 test, feathered 8-bit within-object splices), with
two splice variants (plain, and harmonised with attacks.t1_color_transfer) and four statistics:
T / Tr (shared material: light + gain + offset) and Ts / Tsr (shared light only: own gain and offset).

    python eval/mit_attack.py        # writes data/results/real_panel_attack.json
"""
from __future__ import annotations

import json
import multiprocessing as mp
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
KEYS = ("T", "Tr", "Ts", "Tsr", "S")


def _one(obj):
    from eval import mit_bench as mb
    from lightaudit.attacks import t1_color_transfer
    from lightaudit.config import Config
    from lightaudit.regions import apply_roi
    from lightaudit.residual import panel_shared, seam_S
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
    rng = np.random.default_rng(__import__("zlib").crc32(obj.encode()))  # deterministic per object
    rows = []

    def stats(Y, labels, regs):
        a = (Y, n_b, unc, labels, regs, cfg)
        kw = dict(thr=cfg.retinex_thr, band=cfg.panel_band)
        v = (panel_shared(*a, retinex=False), panel_shared(*a, retinex=True, **kw),
             panel_shared(*a, retinex=False, shape_only=True), panel_shared(*a, retinex=True, shape_only=True, **kw),
             seam_S(Y, labels, regs, cfg))
        return None if any(x is None for x in v[:4]) else dict(zip(KEYS, v))  # S may be None: no vote

    for part in range(1, 5):
        roi = lab == part
        if roi.sum() < 400:
            continue
        a = np.clip(cv2.GaussianBlur(roi.astype(np.float32), (0, 0), 1.5), 0, 1)
        roi_b = big(roi.astype(np.uint8), cv2.INTER_NEAREST).astype(bool)
        labels, meta = apply_roi(mask_b, [dict(id=1, name=obj, source="mask", excluded=False)], roi_b, cfg)
        regs = [dict(id=m["id"], name=m["name"]) for m in meta]
        roi_id = next(m["id"] for m in meta if m["name"] == "ROI")
        for i in range(mb.NL):
            j = int(rng.choice([x for x in range(mb.NL) if x != i]))
            for tag, lin in (("clean", d["lin"][i]), ("splice", d["lin"][i] * (1 - a) + d["lin"][j] * a)):
                Y = np.round(np.clip(big((np.clip(lin, 0, 1) ** (1 / 2.2)).astype(np.float32), cv2.INTER_CUBIC), 0, 1) * 255) / 255
                st = stats(Y.astype(np.float32), labels, regs)
                if st:
                    rows.append(dict(obj=obj, kind=tag, **st))
                if tag == "splice":
                    rgb = np.repeat((Y * 255).astype(np.uint8)[..., None], 3, 2)
                    h = t1_color_transfer(rgb, labels == roi_id, labels, cfg)
                    st = stats(h[..., 0].astype(np.float32) / 255, labels, regs)
                    if st:
                        rows.append(dict(obj=obj, kind="harmonised", **st))
    return rows


def main():
    from eval import mit_bench as mb
    from lightaudit.calibrate import conformal_quantile
    objs = mb.objects()
    with mp.Pool(5) as p:
        rows = [r for rs in p.map(_one, objs) for r in rs]
    (ROOT / "data" / "results" / "real_panel_attack_rows.json").write_text(json.dumps(rows))
    cal = [r for r in rows if r["obj"] in objs[0::2] and r["kind"] == "clean"]
    test = [r for r in rows if r["obj"] in objs[1::2]]
    out = dict(n_cal=len(cal), sets={})
    for name, keys in (("material (T, Tr)", ("T", "Tr")), ("light only (Ts, Tsr)", ("Ts", "Tsr")), ("all four", KEYS),
                       ("T, Tr, Tsr", ("T", "Tr", "Tsr")), ("Tr, Tsr", ("Tr", "Tsr")), ("T, Tsr", ("T", "Tsr")), ("T, Tr, Ts", ("T", "Tr", "Ts")),
                       ("seam S alone", ("S",)), ("Tr, Tsr, S (pipeline)", ("Tr", "Tsr", "S"))):
        tau = {k: conformal_quantile([r[k] for r in cal if r[k] is not None], 0.10 / len(keys)) for k in keys}
        hit = lambda r: any(r[k] is not None and r[k] > tau[k] for k in keys)  # noqa: E731
        res = {kind: (float(np.mean([hit(r) for r in test if r["kind"] == kind])), sum(r["kind"] == kind for r in test))
               for kind in ("clean", "splice", "harmonised")}
        out["sets"][name] = dict(tau=tau, **{k: dict(rate=v[0], n=v[1]) for k, v in res.items()})
        print(f"{name:22s} false alarms {res['clean'][0]:.3f} (n {res['clean'][1]})  plain splices caught {res['splice'][0]:.3f}  "
              f"harmonised splices caught {res['harmonised'][0]:.3f} (n {res['harmonised'][1]})", flush=True)
    (ROOT / "data" / "results" / "real_panel_attack.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
