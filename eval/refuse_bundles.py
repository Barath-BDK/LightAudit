"""Re-run only the fusion step on the saved bundles (no normals, no torch) and print verdicts.

Used to test fusion-rule changes on the real photos in bundles/ quickly. Usage:
  python eval/refuse_bundles.py            # current rule, checks it reproduces the stored verdicts
"""
from __future__ import annotations

import json
import sys
from dataclasses import replace
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lightaudit.config import Config  # noqa: E402
from lightaudit.fusion import fuse  # noqa: E402

ROOT = Path(__file__).resolve().parents[1] / "bundles"
# Ground truth for real bundles: which ones contain an edit. Synthetic bundles carry it in the manifest.
EDITED_REAL = {"real_splice_carpark_sunny_from_peugeot_104"} | {f"real_mit_{o}_spliced" for o in
                                                               ("box", "cup2", "frog2", "pear", "potato", "turtle")}


def load(d: Path):
    m = json.loads((d / "manifest.json").read_text())
    c = m["calibration"]
    cfg = replace(Config(), tau_img=c["tau_img"], tau_ref_factor=c.get("tau_ref", c["tau_img"]) / c["tau_img"],
                  w_min=c["w_min"], eps=c["eps"], min_reliable=c["min_reliable"],
                  broad_consensus_frac=c["broad_consensus_frac"], soft_contrast=c.get("soft_contrast") or np.inf,
                  tau_panel=c.get("tau_panel") or np.inf, shadow_levels_max=c.get("shadow_levels_max") or np.inf,
                  max_flagged=c.get("max_flagged", Config.max_flagged),
                  max_flagged_frac=c.get("max_flagged_frac", Config.max_flagged_frac))
    regs = m["regions"]
    A = np.fromfile(d / "landscapes.bin", "<f4").reshape(len(regs), -1)
    return m, cfg, regs, A


def run(d: Path, cfg_override=None, weight_fn=None):
    m, cfg, regs, A = load(d)
    if cfg_override:
        cfg = replace(cfg, **cfg_override)
    w = [weight_fn(r) if weight_fn else r["weight"] for r in regs]
    f = fuse(A, w, [r["excluded"] for r in regs], cfg, centers=np.array([r["center"] for r in regs]),
             contrast=[r.get("contrast") for r in regs], panel_z=[r.get("panel_z") for r in regs],
             shadow_mid=[r.get("shadow_mid") for r in regs])
    return m, f


def edited(name: str, m: dict) -> bool:
    if name.startswith("real_"):
        return name in EDITED_REAL
    gt = m.get("ground_truth") or {}
    return bool(gt.get("edited_region_ids"))


def table(**kw):
    rows = []
    for d in sorted(p for p in ROOT.iterdir() if (p / "manifest.json").exists()):
        m, f = run(d, **kw)
        rows.append((d.name, edited(d.name, m), m["fusion"]["verdict"], f["verdict"]))
    return rows


def flat_gate(r, cfg=Config()):
    """The reliability rule pipeline.analyze_region now applies, replayed on a stored region."""
    return 0.0 if r["kind"] != "pseudo" and r["name"] != "ROI" and (r["spread_deg"] or 0) < cfg.min_spread_deg else r["weight"]


def write(d: Path) -> tuple[str, str]:
    """Applies the current reliability + fusion rules to a stored bundle and rewrites its manifest in place.
    shortcut: heat.png / counterfactual.png keep the old reference light; rebuild the bundle for exact maps."""
    from lightaudit.bundle import _py, fusion_manifest
    from lightaudit.explain_text import explain
    from lightaudit.reliability import REASONS
    m, f = run(d, weight_fn=flat_gate)
    regs = m["regions"]
    for r, p in zip(regs, f["per_region"]):
        if r["weight"] > 0 and flat_gate(r) == 0.0:
            r.update(weight=0.0, reason=REASONS["f_spread"])
        r["reliable"] = p["reliable"]
        if p["reliable"]:
            r["reason"] = None
    for k in f["panel_flagged"]:
        f["per_region"][k]["panel_z"] = regs[k]["panel_z"]
    f["text"] = explain(f, regs, m["calibration"]["eps"])
    old = m["fusion"]["verdict"]
    m["fusion"] = _py(fusion_manifest(dict(fusion=f, regions=regs)))
    c = Config()
    m["calibration"].update(max_flagged=c.max_flagged, max_flagged_frac=c.max_flagged_frac, min_spread_deg=c.min_spread_deg)
    m["description"] = m["description"].replace(f"Audit verdict: {old}.", f"Audit verdict: {f['verdict']}.")
    txt = json.dumps(_py(m), indent=1).replace(": Infinity", ": null")  # thresholds the bundle never set
    (d / "manifest.json").write_text(txt)
    return old, f["verdict"]


if __name__ == "__main__":
    if "--write" in sys.argv:
        from lightaudit.bundle import update_index
        for d in sorted(p for p in ROOT.iterdir() if (p / "manifest.json").exists()):
            old, new = write(d)
            print(f"{d.name:45s} {old:12s} -> {new}")
        update_index(ROOT)
        sys.exit(0)
    for name, ed, old, new in table():
        print(f"{name:45s} {'EDIT' if ed else 'clean':5s} stored={old:12s} refused={new:12s} {'' if old == new else 'MISMATCH'}")
