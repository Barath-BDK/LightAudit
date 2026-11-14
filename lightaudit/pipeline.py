"""End-to-end audit: regions -> per-region cues/posterior -> fusion -> residuals -> text (BUILD_SPEC 7)."""
from __future__ import annotations

import numpy as np

from . import reliability
from .config import Config, calibrated
from .cues import contour_landscape, find_glints, glint_landscape, ls_landscape, rank_landscape
from .explain_text import explain
from .fusion import combine_cues, fuse
from .grid import eq_dirs, view_vectors
from .imageio import luminance
from .posterior import region_posterior
from .residual import residual_maps
from .validity import valid_pixels

ALL_CUES = ("shading", "glint", "contour")
LANDSCAPES = {"rank": rank_landscape, "ls": ls_landscape}


def analyze_region(Y, normals, unc, mask, view, cfg: Config, seed: int, cue: str = "rank", scale: float = 1.0) -> dict:
    """All per-region evidence, independent of every other region (so experiments can cache it)."""
    ys, xs, n_valid = valid_pixels(Y, normals, unc, mask, cfg, seed)
    r = dict(n_valid=int(n_valid), ys=ys, xs=xs, glint=None, contour=None, glint_blobs=[])
    if n_valid < cfg.Nmin:
        D = len(eq_dirs())
        r.update(P=np.ones(D, np.float32), S=np.zeros(D, np.float32), samples=None, rho_max=0.0, sharp_area=1.0,
                 spread_deg=0.0, mean_unc=float(unc[mask].mean()) if mask.any() else 0.0, center=np.array([0, 1.0, 0]),
                 r68_deg=180.0, r95_deg=180.0, factors=None, weight=0.0, reason="too few usable pixels")
        return r
    r.update(region_posterior(normals[ys, xs], Y[ys, xs], ys, xs, unc[ys, xs], seed, cfg, LANDSCAPES[cue], scale))
    r["mean_unc"] = float(unc[ys, xs].mean())
    f = reliability.factors(n_valid, r["spread_deg"], r["sharp_area"], r["rho_max"], r["mean_unc"])
    r.update(factors=f, weight=reliability.weight(f), reason=reliability.reason(f))
    if r["samples"] is None:
        return r
    r["glint_blobs"] = find_glints(Y, normals, unc, mask, view, cfg)
    r["glint"] = glint_landscape(r["glint_blobs"])
    r["contour"] = contour_landscape(Y, normals, mask, cfg)
    return r


def fuse_regions(regions: list[dict], cfg: Config, cues=ALL_CUES, loo: bool = True) -> dict:
    """Builds each region's A map from the selected cues, runs the fusion, and writes the per-region outcome
    (A, cues, reliable, shortfall, angle_deg, flagged) back into the region dicts. Pass copies for ablations."""
    for r in regions:
        if r.get("kind") == "pseudo":
            continue
        g = r["glint"] if "glint" in cues else None
        c = r["contour"] if "contour" in cues else None
        r["A"] = combine_cues(r["P"], g, c, cfg)
        r["cues"] = ["shading"] + (["glint"] if g is not None else []) + (["contour"] if c is not None else [])
    fusion = fuse([r["A"] for r in regions], [r["weight"] for r in regions], [r["excluded"] for r in regions], cfg,
                  centers=[r["center"] for r in regions], loo=loo)
    for r, p in zip(regions, fusion["per_region"]):
        r.update(reliable=p["reliable"], shortfall=p["shortfall"], angle_deg=p["angle_deg"], flagged=p["flagged"])
        if p["reliable"]:
            r["reason"] = None
        elif r["excluded"]:
            r["reason"] = r.get("exclude_reason", "excluded")
    fusion["text"] = explain(fusion, regions, cfg.eps)
    return fusion


def audit(rgb, normals, unc, labels, meta, cfg: Config | None = None, fov_deg: float = 60.0, seed: int = 0,
          cue: str = "rank", cues=ALL_CUES, scale: float = 1.0, reuse: dict | None = None, changed=None,
          residual: bool = True, pseudo: list | None = None, loo: bool = True) -> dict:
    """Full audit of one image.

    meta: [{id, name, source, excluded}]. `reuse` + `changed` (region ids): take every region not in `changed`
    from a previous result of the same scene (exact when the other regions' pixels and normals are unchanged).
    pseudo: scene-level cues [{name, A, weight, cue}] entered as pseudo-regions (e.g. shadow pairs).
    """
    cfg = cfg or calibrated()
    Y = luminance(rgb)
    H, W = Y.shape
    view = view_vectors(H, W, fov_deg)
    old = {r["id"]: r for r in reuse["regions"]} if reuse else {}
    regions = []
    for m in meta:
        mask = labels == m["id"]
        ys, xs = np.nonzero(mask)
        base = dict(id=m["id"], name=m["name"], kind="region", source=m.get("source", ""),
                    excluded=bool(m.get("excluded", False)), exclude_reason=m.get("exclude_reason", "excluded"),
                    area_px=int(mask.sum()), bbox=[int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1])
        if m["id"] in old and (changed is None or m["id"] not in changed):
            r = dict(old[m["id"]])
        elif base["excluded"]:
            r = analyze_region(Y, normals, unc, np.zeros_like(mask), view, cfg, 0)
            r.update(weight=0.0, mean_unc=float(unc[mask].mean()))
        else:
            r = analyze_region(Y, normals, unc, mask, view, cfg, seed * 1000 + m["id"], cue, scale)
        r.update(base)
        regions.append(r)
    for p in pseudo or []:
        D = len(eq_dirs())
        regions.append(dict(id=max([r["id"] for r in regions] + [0]) + 1, name=p["name"], kind="pseudo", excluded=False,
                            area_px=0, bbox=[0, 0, 0, 0], n_valid=0, ys=np.zeros(0, int), xs=np.zeros(0, int),
                            spread_deg=0.0, rho_max=0.0, sharp_area=0.0, mean_unc=0.0, factors=None,
                            weight=float(p["weight"]), reason=None, P=p["A"], A=p["A"], S=np.zeros(D, np.float32),
                            glint=None, contour=None, cues=[p.get("cue", "shadow")], r68_deg=0.0, r95_deg=0.0,
                            center=eq_dirs()[int(np.argmax(p["A"]))].astype(np.float64)))
    fusion = fuse_regions(regions, cfg, cues, loo)

    out = dict(rgb=rgb, Y=Y, normals=normals, unc=unc, labels=labels, regions=regions, fusion=fusion, cfg=cfg,
               fov_deg=fov_deg, cue=cue, heat=None, counterfactual=None, valid=None)
    if residual:
        dirs = eq_dirs()
        valid = np.zeros((H, W), np.uint8)
        for r, p in zip(regions, fusion["per_region"]):
            r["mask"] = labels == r["id"]
            valid[r["ys"], r["xs"]] = 255
            if r["excluded"] or r["kind"] == "pseudo":
                r["l_ref"] = None
            elif fusion["consensus"] is None:
                r["l_ref"] = r["center"]
            else:  # leave-one-out consensus for flagged regions, the full consensus otherwise
                r["l_ref"] = dirs[p["ref_index"]] if p["flagged"] else fusion["consensus"]["dir"]
        out["heat"], out["counterfactual"] = residual_maps(rgb, Y, normals, unc, regions, cfg)
        out["valid"] = valid
    return out


def audit_sample(sample, sigma: float | None = None, cfg: Config | None = None, composite: dict | None = None,
                 panel: bool = False, **kw) -> dict:
    """Audit a synthetic sample with GT regions and simulated normals (`noisy_gt(sigma)`).

    composite: the dict returned by synth.paste (its image is audited instead of the pristine one).
    panel: panel mode with the dent mask as the ROI (damage scenes).
    The simulated normals depend only on the scene seed, i.e. they are independent of any edit.
    """
    from .regions import apply_roi, auto_exclude
    from .synth import region_meta, simulate_normals
    cfg = cfg or calibrated()
    sigma = cfg.sigma_normals if sigma is None else sigma
    normals, unc = simulate_normals(sample.normals_gt, sample.labels, sigma, sample.scene.seed, cfg)
    rgb = composite["rgb"] if composite else sample.rgb
    labels, meta = sample.labels.astype(np.int32), region_meta(sample)
    if panel and sample.dent_mask.any():
        labels, meta = apply_roi(labels, meta, sample.dent_mask, cfg)
    meta = auto_exclude(rgb, labels, meta, cfg)
    res = audit(rgb, normals, unc, labels, meta, cfg, sample.scene.fov_deg, seed=sample.scene.seed,
                scale=sample.scene.scale, **kw)
    edited = []
    if composite:
        m = composite["mask"]
        edited = [r["id"] for r in res["regions"] if r["area_px"] and (m & (labels == r["id"])).sum() > 0.5 * r["area_px"]]
    res["ground_truth"] = dict(light_cam=[float(v) for v in sample.light_cam], edited_region_ids=edited,
                               delta_deg=composite["delta_deg"] if composite else 0.0)
    res["normals_backend"] = f"noisy_gt({sigma:g})" if sigma > 0 else "gt"
    res["regions_backend"] = "gt"
    return res
