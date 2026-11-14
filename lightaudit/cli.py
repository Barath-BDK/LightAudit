"""Command line: python -m lightaudit.cli <command> (BUILD_SPEC 13.1)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

from .config import ROOT, SPLIT_SEEDS, calibrated, load_calib

DEMOS = [
    dict(name="demo_consistent", kind="normal", expect=("CONSISTENT",), seed=4000,
         title="Clean sunny scene", what="An unedited sunny scene."),
    dict(name="demo_splice_car", kind="normal", target="car", delta=120, expect=("SUSPICIOUS",), seed=4010, attacks=True,
         title="Car pasted from another light", what="The car was rendered under a light {delta:.0f}° away from the scene's sun and pasted in."),
    dict(name="demo_damage_genuine", kind="damage", panel=True, expect=("CONSISTENT",), seed=4020,
         title="Genuine dent (panel mode)", what="A real dent, lit by the same sun as the rest of the car. Panel mode: dent ROI + surrounding ring."),
    dict(name="demo_damage_fake", kind="damage", panel=True, target="dent", delta=120, expect=("SUSPICIOUS",), seed=4030,
         attacks=True, title="Dent pasted from another light (panel mode)",
         what="The dent area was rendered under a light {delta:.0f}° away and pasted onto the panel."),
    dict(name="demo_multilight", kind="multi", expect=("CONFLICT", "INSUFFICIENT"), seed=4040,
         title="Two suns", what="An unedited scene lit by two strong lights (outside the one-light model)."),
    dict(name="demo_overcast", kind="overcast", expect=("INSUFFICIENT",), seed=4050,
         title="Overcast", what="An unedited scene under mostly diffuse sky light."),
    dict(name="demo_failure_missed_splice", kind="normal", target="car", delta=120, expect=("CONSISTENT",), seed=4060,
         title="Failure example: a splice that passes", what="FAILURE EXAMPLE. The car was pasted from a light {delta:.0f}° away, yet the audit does not flag it."),
]


def _demo_one(d: dict, cfg, max_tries: int = 12):
    """Builds one demo: tries seeds d['seed'].. until the verdict is the intended one (count is logged)."""
    from .attacks import attack_suite
    from .pipeline import audit_sample
    from .synth import get_sample, light_at_angle, paste
    last = None
    for t in range(max_tries):
        seed = d["seed"] + t
        s = get_sample(seed, d["kind"])
        comp = None
        if d.get("target"):
            try:
                comp = paste(s, d["target"], light_at_angle(s.scene.l_world, d["delta"], seed))
            except ValueError:
                continue
        panel = d.get("panel", False)
        res = audit_sample(s, cfg=cfg, composite=comp, panel=panel)
        f = res["fusion"]
        ok = f["verdict"] in d["expect"]
        if ok and f["verdict"] == "SUSPICIOUS" and comp:
            ok = res["regions"][f["top_region"]]["id"] in res["ground_truth"]["edited_region_ids"]
        last = (seed, s, comp, res, t + 1, ok)
        if ok:
            break
    return last + (panel,) if last else None


def build_demo_bundles(only: list[str] | None = None) -> list[dict]:
    from .attacks import attack_suite
    from .bundle import BUNDLES, write_bundle
    from .pipeline import audit_sample
    cfg = calibrated()
    log = []
    for d in DEMOS:
        if only and d["name"] not in only:
            continue
        got = _demo_one(d, cfg)
        if got is None:
            log.append(dict(name=d["name"], built=False))
            continue
        seed, s, comp, res, tries, ok, panel = got
        f = res["fusion"]
        attacks = None
        ed = [r for r in res["regions"] if r["id"] in res["ground_truth"]["edited_region_ids"] and not r["excluded"]]
        if d.get("attacks") and ed:
            rid = max(ed, key=lambda r: (r["flagged"], r["n_valid"]))["id"]
            reaudit = lambda rgb: audit_sample(s, cfg=cfg, composite=dict(comp, rgb=rgb), panel=panel, reuse=res, changed=[rid])  # noqa: E731
            attacks = attack_suite(res, rid, reaudit, seed=seed)
        ls = audit_sample(s, cfg=cfg, composite=comp, panel=panel, cue="rank" if cfg.cue == "ls" else "ls", residual=False)
        what = d["what"].format(delta=comp["delta_deg"] if comp else 0)
        desc = (f"{what} Synthetic scene (seed {seed}), simulated normals. Audit verdict: {f['verdict']}"
                + ("" if ok else f" (intended: {'/'.join(d['expect'])}; shown as it is)") + ".")
        write_bundle(res, d["name"], d["title"], desc, attacks=attacks, baseline_ls=ls)
        log.append(dict(name=d["name"], built=True, seed=seed, seeds_tried=tries, intended=list(d["expect"]),
                        verdict=f["verdict"], matched=ok, S_img=f["S_img"],
                        attacks=[dict(variant=a["variant"], verdict=a["result"]["fusion"]["verdict"]) for a in attacks or []]))
        print(f"  {d['name']}: seed {seed} ({tries} tried) -> {f['verdict']}" + ("" if ok else "  [not the intended verdict]"))
    (BUNDLES / "demo_log.json").write_text(json.dumps(log, indent=1))
    return log


def audit_image(image: Path, name: str | None = None, roi: Path | None = None, regions: str = "sam",
                normals: str = "dsine,stablenormal,depth_anything", fov: float = 60.0, calib: Path | None = None,
                attacks: bool = False, html: bool = False, flips=(False, False, False), title: str | None = None,
                description: str | None = None, progress=None, root: Path | None = None) -> Path:
    """Real-photo path: normals ensemble -> regions -> audit -> bundle."""
    from PIL import Image
    from .bundle import write_bundle
    from .imageio import load_rgb
    from .normals import predict_normals
    from .pipeline import audit
    from .regions import apply_roi, auto_exclude, propose_regions
    say = progress or (lambda msg: print(" ", msg))
    cfg = calibrated(calib=load_calib(calib))
    rgb = load_rgb(image, cfg.max_side)
    log: list[str] = []
    say("estimating surface normals")
    n, unc, info = predict_normals(rgb, tuple(b for b in normals.split(",") if b), fov, flips=flips)
    log += info.get("log", [])
    say("proposing regions")
    labels, meta = propose_regions(rgb, n, regions, cfg, log)
    if roi:
        m = np.asarray(Image.open(roi).convert("L").resize((rgb.shape[1], rgb.shape[0]), Image.NEAREST)) > 127
        labels, meta = apply_roi(labels, meta, m, cfg)
    meta = auto_exclude(rgb, labels, meta, cfg)
    say("estimating per-region light directions")
    res = audit(rgb, n, unc, labels, meta, cfg, fov, seed=0)
    res.update(ground_truth=None, normals_backend="+".join(info.get("backends", [])) or "none",
               regions_backend=meta[0]["source"] if meta else regions, backends_log=log,
               calib_source=Path(calib).name if calib else "calib_default.json")
    atk = None
    if attacks and res["fusion"]["flagged"]:
        from .attacks import attack_suite
        rid = res["regions"][res["fusion"]["flagged"][0]]["id"]
        reaudit = lambda img: audit(img, n, unc, labels, meta, cfg, fov, seed=0, reuse=res, changed=[rid])  # noqa: E731
        atk = attack_suite(res, rid, reaudit)
    name = name or f"real_{Path(image).stem}"
    f = res["fusion"]
    d = write_bundle(res, name, title or Path(image).name,
                     description or f"Real photo, ground truth unknown. Audit verdict: {f['verdict']}.", "real", atk,
                     **({"root": root} if root else {}))
    if html:
        from .report_html import export_report
        export_report(d)
    return d


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="lightaudit", description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("setup-check")
    p = sub.add_parser("synth")
    p.add_argument("--split", choices=list(SPLIT_SEEDS), required=True)
    p.add_argument("--n", type=int, default=20)
    p.add_argument("--kinds", default="normal")
    p.add_argument("--out")
    p = sub.add_parser("calibrate")
    p.add_argument("--n-cal", type=int, default=200)
    sub.add_parser("train-arbiter").add_argument("--n", type=int, default=200)
    p = sub.add_parser("audit")
    p.add_argument("--image", required=True)
    p.add_argument("--roi")
    p.add_argument("--regions", default="sam")
    p.add_argument("--normals", default="dsine,stablenormal,depth_anything")
    p.add_argument("--fov", type=float, default=60.0)
    p.add_argument("--calib")
    p.add_argument("--name")
    p.add_argument("--attacks", action="store_true")
    p.add_argument("--html", action="store_true")
    for ax in "xyz":
        p.add_argument(f"--flip-{ax}", action="store_true")
    p = sub.add_parser("audit-synth")
    p.add_argument("--sample", required=True, help="KIND:SEED, e.g. normal:4000, or a png written by `synth`")
    p.add_argument("--normals", default="noisy_gt:8")
    p.add_argument("--name", required=True)
    p.add_argument("--attacks", action="store_true")
    p.add_argument("--paste", help="TARGET:DELTA, e.g. car:120")
    p = sub.add_parser("attack")
    p.add_argument("--bundle", required=True)
    p.add_argument("--region", type=int, required=True)
    p.add_argument("--variants", default="T1,T3a,T4")
    p.add_argument("--sigma-att", type=float, default=0.0)
    p = sub.add_parser("eval")
    p.add_argument("--suite", choices=["quick", "full"], default="quick")
    p.add_argument("--exp")
    sub.add_parser("figures")
    sub.add_parser("demo-bundles").add_argument("--only")
    sub.add_parser("serve").add_argument("--port", type=int, default=8000)
    sub.add_parser("report")
    a = ap.parse_args(argv)
    sys.path.insert(0, str(ROOT))  # eval/, report/, figures/ are plain folders next to the package

    if a.cmd == "setup-check":
        from . import backends_available
        for k, v in backends_available().items():
            print(f"  {k:16s} {'available' if v else 'not available'}")
        print("  calibration:", load_calib().get("source"))
    elif a.cmd == "synth":
        from .synth import build_dataset
        out = a.out or ROOT / "data" / "synth" / a.split
        print(f"rendered {len(build_dataset(a.split, a.n, a.kinds.split(','), out))} samples -> {out}")
    elif a.cmd == "calibrate":
        from .calibrate import run_calibration
        print(json.dumps(run_calibration(a.n_cal, min(120, a.n_cal)), indent=1))
    elif a.cmd == "train-arbiter":
        from .arbiter import train
        print(json.dumps(train(a.n), indent=1))
    elif a.cmd == "audit":
        d = audit_image(Path(a.image), a.name, a.roi, a.regions, a.normals, a.fov, a.calib, a.attacks, a.html,
                        (a.flip_x, a.flip_y, a.flip_z))
        print(f"bundle written: {d}  ->  open viewer/index.html?bundle={d.name}")
    elif a.cmd == "audit-synth":
        from .attacks import attack_suite
        from .bundle import write_bundle
        from .pipeline import audit_sample
        from .synth import get_sample, light_at_angle, paste
        if ":" in a.sample and not Path(a.sample).exists():
            kind, seed = a.sample.split(":")
        else:
            kind, seed = Path(a.sample).stem.rsplit("_", 1)
        s = get_sample(int(seed), kind)
        sigma = float(a.normals.split(":")[1]) if ":" in a.normals else 0.0
        comp = None
        if a.paste:
            tgt, delta = a.paste.split(":")
            comp = paste(s, tgt, light_at_angle(s.scene.l_world, float(delta), int(seed)))
        panel = kind == "damage"
        res = audit_sample(s, sigma, composite=comp, panel=panel)
        atk = None
        if a.attacks and comp and res["fusion"]["flagged"]:
            rid = res["regions"][res["fusion"]["flagged"][0]]["id"]
            atk = attack_suite(res, rid, lambda rgb: audit_sample(s, sigma, composite=dict(comp, rgb=rgb), panel=panel,
                                                                  reuse=res, changed=[rid]), seed=int(seed))
        d = write_bundle(res, a.name, f"{kind} scene {seed}", f"Synthetic scene. Audit verdict: {res['fusion']['verdict']}.",
                         attacks=atk)
        print(f"{res['fusion']['verdict']}: {res['fusion']['text']}\nbundle written: {d}")
    elif a.cmd == "attack":
        from .server import attack_bundle
        for r in attack_bundle(a.bundle, a.region, a.variants.split(","), a.sigma_att):
            print(f"  {r['variant']}: {r['verdict']}  S_img={r['S_img']:.2f}")
    elif a.cmd == "eval":
        from eval.run_eval import main as run
        run(a.suite, a.exp.split(",") if a.exp else None)
    elif a.cmd == "figures":
        import runpy
        from eval import make_figures, make_tables
        runpy.run_path(str(ROOT / "figures" / "make_illustrations.py"), run_name="__main__")
        make_figures.main()
        make_tables.main()
    elif a.cmd == "demo-bundles":
        build_demo_bundles(a.only.split(",") if a.only else None)
    elif a.cmd == "serve":
        from .server import serve
        serve(a.port)
    elif a.cmd == "report":
        from report.make_report import main as rep
        rep()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
