"""Bundle export: the contract between backend and viewer (BUILD_SPEC 11).

Extras beyond the spec (all optional for the viewer): thumb.jpg; cues.bin + per-region `cue_maps` (the separate
shading / glint / contour maps so the viewer can re-weight cues live); landscapes_ls.bin for the LS baseline.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image

from .config import ROOT
from .grid import NA, NE
from .imageio import encode_normals, save_png

BUNDLES = ROOT / "bundles"
PALETTE = ["#4c78a8", "#f58518", "#54a24b", "#e45756", "#72b7b2", "#eeca3b", "#b279a2", "#ff9da6", "#9d755d",
           "#bab0ac", "#59a14f", "#8cd17d", "#86bcb6", "#f1ce63", "#d37295", "#a0cbe8"]


def _py(o):
    if isinstance(o, np.ndarray):
        return [_py(v) for v in o.tolist()]
    if isinstance(o, (np.floating, float)):
        return round(float(o), 5)
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.bool_,)):
        return bool(o)
    if isinstance(o, dict):
        return {k: _py(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_py(v) for v in o]
    return o


def fusion_manifest(result: dict) -> dict:
    f, regs = result["fusion"], result["regions"]
    c = f["consensus"]
    return dict(
        verdict=f["verdict"], reason=f["reason"], S_img=f["S_img"], n_reliable=f["n_reliable"],
        top_region=None if f["top_region"] is None else regs[f["top_region"]]["id"],
        flagged=[regs[k]["id"] for k in f["flagged"]],
        consensus=None if c is None else dict(dir=c["dir"], az_deg=c["az_deg"], el_deg=c["el_deg"], r68_deg=c["r68_deg"],
                                              r95_deg=c["r95_deg"], frac95=c["frac95"]),
        per_region=[dict(id=r["id"], shortfall=p["shortfall"], angle_deg=p["angle_deg"], flagged=p["flagged"])
                    for r, p in zip(regs, f["per_region"])],
        text=f["text"])


def region_manifest(r: dict, i: int) -> dict:
    return dict(
        id=r["id"], name=r["name"], kind=r["kind"], excluded=r["excluded"], area_px=r["area_px"], bbox=r["bbox"],
        color=PALETTE[i % len(PALETTE)], n_valid=r["n_valid"], spread_deg=r["spread_deg"], rho_max=r["rho_max"],
        sharp_area=r["sharp_area"], mean_unc=r["mean_unc"], weight=r["weight"], reliable=r["reliable"],
        reason=r["reason"], factors=r.get("factors"), cues=r["cues"], center=r["center"], r68_deg=r["r68_deg"],
        r95_deg=r["r95_deg"], g_lut=r.get("g_lut"), sigma=r.get("sigma"), slope=r.get("slope"), landscape_index=i)


def _write_maps(d: Path, result: dict, manifest: dict, full: bool) -> None:
    regs = result["regions"]
    np.stack([r["A"] for r in regs]).astype("<f4").tofile(d / "landscapes.bin")
    save_png(d / "image.png", result["rgb"])
    save_png(d / "labels.png", result["labels"].astype(np.uint8))
    if result["heat"] is not None:
        save_png(d / "heat.png", result["heat"])
    if not full:
        return
    save_png(d / "normals.png", encode_normals(result["normals"]))
    save_png(d / "unc.png", np.clip(result["unc"] / 45 * 255, 0, 255).astype(np.uint8))
    save_png(d / "valid.png", result["valid"])
    save_png(d / "counterfactual.png", result["counterfactual"])
    result["fusion"]["consensus_map"] is not None and result["fusion"]["consensus_map"].astype("<f4").tofile(d / "consensus.bin")
    maps = []
    for r, m in zip(regs, manifest["regions"]):
        cm = {}
        for cue, key in (("shading", "P"), ("glint", "glint"), ("contour", "contour")):
            if r.get(key) is not None and r["kind"] != "pseudo":
                cm[cue] = len(maps)
                maps.append(r[key])
        m["cue_maps"] = cm
    if maps:
        np.stack(maps).astype("<f4").tofile(d / "cues.bin")
    (d / "grid.json").write_text(json.dumps({"NA": NA, "NE": NE}))
    Image.fromarray(result["rgb"]).resize((320, round(320 * result["rgb"].shape[0] / result["rgb"].shape[1]))).save(
        d / "thumb.jpg", quality=85)


def build_manifest(result: dict, name: str, title: str, description: str, source: str = "synthetic") -> dict:
    cfg = result["cfg"]
    H, W = result["labels"].shape
    return dict(
        version=1, name=name, title=title, description=description, cue=result.get("cue", "rank"),
        image=dict(w=W, h=H, fov_deg=result["fov_deg"], source=source),
        ground_truth=result.get("ground_truth"),
        normals_backend=result.get("normals_backend", "unknown"), regions_backend=result.get("regions_backend", "unknown"),
        calibration=dict(h=cfg.kde_h, T=cfg.T, tau_img=cfg.tau_img, tau_ref=cfg.tau_ref, w_min=cfg.w_min,
                         alpha=cfg.alpha, eps=cfg.eps, w_glint=cfg.w_glint, w_contour=cfg.w_contour,
                         min_reliable=cfg.min_reliable, broad_consensus_frac=cfg.broad_consensus_frac,
                         source=result.get("calib_source", "calib_default.json")),
        regions=[region_manifest(r, i) for i, r in enumerate(result["regions"])],
        fusion=fusion_manifest(result), baseline_ls=dict(present=False), attacks=[],
        backends_log=result.get("backends_log", []), created=datetime.now(timezone.utc).isoformat(timespec="seconds"))


def write_bundle(result: dict, name: str, title: str, description: str, source: str = "synthetic",
                 attacks: list | None = None, baseline_ls: dict | None = None, root: Path = BUNDLES) -> Path:
    """attacks: [{variant, title, result, fidelity, interpretation, region_id}]; baseline_ls: an audit result
    of the same image with cue='ls'."""
    d = Path(root) / name
    d.mkdir(parents=True, exist_ok=True)
    m = build_manifest(result, name, title, description, source)
    _write_maps(d, result, m, full=True)
    if baseline_ls is not None:
        np.stack([r["A"] for r in baseline_ls["regions"]]).astype("<f4").tofile(d / "landscapes_ls.bin")
        m["baseline_ls"] = dict(present=True, cue=baseline_ls.get("cue", "ls"), fusion=fusion_manifest(baseline_ls),
                                regions=[dict(id=r["id"], center=r["center"], r68_deg=r["r68_deg"], r95_deg=r["r95_deg"],
                                              weight=r["weight"], reliable=r["reliable"]) for r in baseline_ls["regions"]])
    for a in attacks or []:
        ad = d / "attacks" / a["variant"]
        ad.mkdir(parents=True, exist_ok=True)
        am = build_manifest(a["result"], f"{name}/{a['variant']}", a["title"], a.get("interpretation", ""), source)
        _write_maps(ad, a["result"], am, full=False)
        (ad / "manifest.json").write_text(json.dumps(_py(am), indent=1))
        m["attacks"].append(dict(variant=a["variant"], title=a["title"], verdict=a["result"]["fusion"]["verdict"],
                                 S_img=a["result"]["fusion"]["S_img"], fidelity=a["fidelity"], region_id=a["region_id"],
                                 interpretation=a.get("interpretation", "")))
    (d / "manifest.json").write_text(json.dumps(_py(m), indent=1))
    update_index(root)
    return d


def update_index(root: Path = BUNDLES) -> list:
    """Rebuilds bundles/index.json from the manifests on disk."""
    idx = []
    for mf in sorted(Path(root).glob("*/manifest.json")):
        m = json.loads(mf.read_text())
        idx.append(dict(name=m["name"], title=m["title"], description=m["description"], verdict=m["fusion"]["verdict"],
                        thumb=f"{m['name']}/thumb.jpg", source=m["image"]["source"]))
    Path(root).mkdir(parents=True, exist_ok=True)
    (Path(root) / "index.json").write_text(json.dumps(idx, indent=1))
    return idx


REQUIRED = {
    "": ["version", "name", "title", "description", "image", "ground_truth", "normals_backend", "regions_backend",
         "calibration", "regions", "fusion", "baseline_ls", "attacks", "backends_log", "created"],
    "image": ["w", "h", "fov_deg", "source"],
    "calibration": ["h", "T", "tau_img", "tau_ref", "w_min", "alpha", "source"],
    "fusion": ["verdict", "S_img", "top_region", "consensus", "per_region", "text"],
    "region": ["id", "name", "kind", "excluded", "area_px", "bbox", "color", "n_valid", "spread_deg", "rho_max",
               "sharp_area", "mean_unc", "weight", "reliable", "reason", "cues", "center", "r68_deg", "r95_deg",
               "g_lut", "sigma", "slope", "landscape_index"],
}


def validate_bundle(d: Path) -> list[str]:
    """Small schema validator. Returns a list of problems (empty = valid)."""
    d = Path(d)
    errs = []
    try:
        m = json.loads((d / "manifest.json").read_text())
    except Exception as e:
        return [f"manifest unreadable: {e}"]
    errs += [f"missing key {k}" for k in REQUIRED[""] if k not in m]
    for sec in ("image", "calibration", "fusion"):
        errs += [f"missing {sec}.{k}" for k in REQUIRED[sec] if k not in m.get(sec, {})]
    for r in m.get("regions", []):
        errs += [f"region {r.get('id')}: missing {k}" for k in REQUIRED["region"] if k not in r]
        if r.get("g_lut") is not None and len(r["g_lut"]) != 33:
            errs.append(f"region {r.get('id')}: g_lut must have 33 knots")
    if m.get("fusion", {}).get("verdict") not in ("CONSISTENT", "SUSPICIOUS", "INSUFFICIENT", "CONFLICT"):
        errs.append("bad verdict")
    n = len(m.get("regions", []))
    if (d / "landscapes.bin").stat().st_size != n * NE * NA * 4:
        errs.append("landscapes.bin has the wrong size")
    w, h = m["image"]["w"], m["image"]["h"]
    for f in ("image.png", "normals.png", "unc.png", "labels.png", "valid.png", "heat.png", "counterfactual.png"):
        if not (d / f).exists():
            errs.append(f"missing {f}")
        elif Image.open(d / f).size != (w, h):
            errs.append(f"{f} has the wrong dimensions")
    for a in m.get("attacks", []):
        if not (d / "attacks" / a["variant"] / "manifest.json").exists():
            errs.append(f"attack {a['variant']} missing files")
    return errs
