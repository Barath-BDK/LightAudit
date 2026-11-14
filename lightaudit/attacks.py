"""Red-team evaluation of the detector (BUILD_SPEC 10): the forger tries to make a spliced region pass.

Tiers: T0 naive paste (the composite itself), T1 colour harmonisation, T3a physics re-shade, T4 adaptive.
These only re-light a region inside a synthetic / user-supplied composite so that the audit can be stress-tested.
"""
from __future__ import annotations

import cv2
import numpy as np

from .config import Config
from .grid import angle_deg, eq_dirs
from .imageio import luminance
from .residual import apply_g, fit_g
from .synth.composite import light_at_angle

TITLES = {"T0": "T0 naive paste", "T1": "T1 colour transfer", "T3a": "T3a re-shade", "T4": "T4 adaptive"}


def _alpha(mask: np.ndarray, cfg: Config) -> np.ndarray:
    return (np.minimum(cv2.GaussianBlur(mask.astype(np.float32), (0, 0), cfg.feather_px) * 2, 1) * mask)[..., None]


def ring_of(mask: np.ndarray, labels: np.ndarray, cfg: Config) -> np.ndarray:
    px = max(cfg.ring_px, 6)
    ring = cv2.dilate(mask.astype(np.uint8), np.ones((2 * px + 1, 2 * px + 1), np.uint8)).astype(bool)
    return ring & ~mask & (labels > 0)


def t1_color_transfer(rgb: np.ndarray, mask: np.ndarray, labels: np.ndarray, cfg: Config = Config()) -> np.ndarray:
    """Reinhard colour transfer in CIE-Lab: match the region's mean/std to its surrounding ring."""
    ring = ring_of(mask, labels, cfg)
    if ring.sum() < 20:
        return rgb.copy()
    lab = cv2.cvtColor(rgb.astype(np.float32) / 255, cv2.COLOR_RGB2Lab)
    src, dst = lab[mask], lab[ring]
    out = lab.copy()
    out[mask] = (src - src.mean(0)) / np.maximum(src.std(0), 1e-3) * dst.std(0) + dst.mean(0)
    new = np.clip(cv2.cvtColor(out, cv2.COLOR_Lab2RGB), 0, 1)
    a = _alpha(mask, cfg)
    return np.round((rgb / 255 * (1 - a) + new * a) * 255).astype(np.uint8)


def remove_glints(rgb: np.ndarray, mask: np.ndarray, cfg: Config = Config()) -> np.ndarray:
    """Inpaint saturated highlight pixels inside the region (they would keep pointing at the old light)."""
    sat = (luminance(rgb) > cfg.sat_hi - 0.05) & mask
    if not sat.any():
        return rgb.copy()
    sat = cv2.dilate(sat.astype(np.uint8), np.ones((5, 5), np.uint8))
    return cv2.inpaint(rgb, sat, 3, cv2.INPAINT_TELEA)


def t3a_reshade(rgb, normals_att, mask, ys, xs, l_own, l_hat, cfg: Config = Config()) -> np.ndarray:
    """Physics re-shade: fit the region's own monotone curve g against its own light, then re-render the
    brightness under the scene light estimate l_hat. Highlights are not moved (multiplicative re-shading)."""
    Y = luminance(rgb)
    lut = fit_g(np.maximum(normals_att[ys, xs] @ np.asarray(l_own, np.float32), 0), Y[ys, xs], cfg)
    Y_new = apply_g(lut, np.maximum(normals_att[mask] @ np.asarray(l_hat, np.float32), 0))
    x = rgb.astype(np.float32) / 255
    new = x.copy()
    new[mask] = np.clip(x[mask] * ((Y_new + 0.01) / (Y[mask] + 0.01))[:, None], 0, 1)
    a = _alpha(mask, cfg)
    return np.round((x * (1 - a) + new * a) * 255).astype(np.uint8)


def fidelity(rgb0: np.ndarray, rgb1: np.ndarray, mask: np.ndarray) -> dict:
    """How much the attack changed the region: mean |dY| and 1 - SSIM inside the region's bounding box."""
    from skimage.metrics import structural_similarity
    Y0, Y1 = luminance(rgb0), luminance(rgb1)
    ys, xs = np.nonzero(mask)
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    ssim = 1.0
    if min(y1 - y0, x1 - x0) >= 7:
        _, smap = structural_similarity(Y0[y0:y1, x0:x1], Y1[y0:y1, x0:x1], data_range=1.0, full=True)
        ssim = float(smap[mask[y0:y1, x0:x1]].mean())
    return dict(mean_abs_dY=float(np.abs(Y1 - Y0)[mask].mean()), ssim_loss=float(1 - ssim))


def scene_light_estimate(base: dict, region_id: int) -> np.ndarray:
    """What a forger would aim for: the consensus of the other regions (leave-one-out reference of the region)."""
    i = next(i for i, r in enumerate(base["regions"]) if r["id"] == region_id)
    p = base["fusion"]["per_region"][i]
    if p["ref_index"] is not None:
        return eq_dirs()[p["ref_index"]].astype(np.float64)
    return np.asarray(base["regions"][i]["center"], np.float64)


def run_attack(variant: str, base: dict, region_id: int, reaudit, normals_att=None, sigma_att: float = 0.0,
               seed: int = 0, cfg: Config | None = None) -> dict:
    """variant in {T1, T3a, T4}. base = the defender's audit of the un-attacked composite; reaudit(rgb) -> result
    re-runs the audit on an attacked image. Returns {variant, title, rgb, result, fidelity, region_id, l_hat}."""
    cfg = cfg or base["cfg"]
    rgb0, labels = base["rgb"], base["labels"]
    reg = next(r for r in base["regions"] if r["id"] == region_id)
    mask = labels == region_id
    normals_att = base["normals"] if normals_att is None else normals_att
    l_hat = scene_light_estimate(base, region_id)
    if sigma_att > 0:
        l_hat = light_at_angle(l_hat, sigma_att, [seed, int(sigma_att)]).astype(np.float64)
    name, title = variant, TITLES[variant]
    if variant == "T1":
        rgb = t1_color_transfer(rgb0, mask, labels, cfg)
        res = reaudit(rgb)
    elif variant == "T3a":
        name = f"T3a_{int(sigma_att)}"
        title = f"T3a re-shade ({'exact light' if sigma_att == 0 else f'±{int(sigma_att)}° error'})"
        rgb = t3a_reshade(rgb0, normals_att, mask, reg["ys"], reg["xs"], reg["center"], l_hat, cfg)
        res = reaudit(rgb)
    elif variant == "T4":
        clean = remove_glints(rgb0, mask, cfg)
        cands = [l_hat] + [light_at_angle(l_hat, 5, [seed, 77, j]).astype(np.float64) for j in range(6)]
        best = None
        for l in cands:  # white-box search with the defender's score as the oracle
            img = t3a_reshade(clean, normals_att, mask, reg["ys"], reg["xs"], reg["center"], l, cfg)
            fid = fidelity(rgb0, img, mask)
            r = reaudit(img)
            s = next(x for x in r["regions"] if x["id"] == region_id)["shortfall"]
            key = (fid["mean_abs_dY"] > cfg.fidelity_max_dY, s if s is not None else 0.0)
            if best is None or key < best[0]:
                best = (key, img, r, l)
        _, rgb, res, l_hat = best
    else:
        raise ValueError(variant)
    return dict(variant=name, title=title, rgb=rgb, result=res, fidelity=fidelity(rgb0, rgb, mask),
                region_id=region_id, l_hat=l_hat, interpretation=interpret(base, res, region_id, title))


def interpret(base: dict, res: dict, region_id: int, title: str) -> str:
    """One rule-based sentence comparing the region before and after the attack."""
    b = next(r for r in base["regions"] if r["id"] == region_id)
    a = next(r for r in res["regions"] if r["id"] == region_id)
    vb, va = base["fusion"]["verdict"], res["fusion"]["verdict"]
    if a["angle_deg"] is None or b["angle_deg"] is None:
        return f"{title}: verdict {vb} → {va}."
    s = (f"{title} moved the estimate for {a['name']} from {b['angle_deg']:.0f}° to {a['angle_deg']:.0f}° off the "
         f"consensus (shortfall {b['shortfall']:.1f} → {a['shortfall']:.1f}); verdict {vb} → {va}.")
    if a["flagged"]:
        extra = [c for c in a["cues"] if c != "shading"]
        s += (" The region is still flagged" + (f" (cues: shading + {', '.join(extra)})." if extra else "."))
    elif vb == "SUSPICIOUS" and va == "CONSISTENT":
        s += " The lighting check is fooled."
    elif abs(a["angle_deg"] - b["angle_deg"]) < 5:
        s += " A monotone brightness/colour change leaves the rank order of the shading intact, so nothing moves."
    return s


def attack_suite(base: dict, region_id: int, reaudit, normals_att=None, seed: int = 0,
                 variants=(("T1", 0), ("T3a", 0), ("T3a", 10), ("T3a", 20), ("T4", 0))) -> list[dict]:
    return [run_attack(v, base, region_id, reaudit, normals_att, s, seed) for v, s in variants]


def light_error_deg(l_hat, l_true) -> float:
    return float(angle_deg(l_hat, l_true))
