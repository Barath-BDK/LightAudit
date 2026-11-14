"""Fusion, consensus, leave-one-out shortfall and verdict (BUILD_SPEC 7.11). Mirrored in viewer/fusion.js.

Parity notes for the JS port: all arithmetic in float64 on float32 inputs; argmax = first maximum;
the leave-one-out objective is computed as F_total - L_k; HPD sorts are stable (ties by cell index).
"""
from __future__ import annotations

import numpy as np

from .config import Config
from .grid import angle_deg, az_el_deg, cone_half_angle_deg, eq_dirs, hpd

VERDICTS = ("CONSISTENT", "SUSPICIOUS", "INSUFFICIENT", "CONFLICT")


def combine_cues(P, glint=None, contour=None, cfg: Config = Config()) -> np.ndarray:
    """Region-level cue combination: ln A = ln(eps+P) + w_g ln(eps+A_glint) + w_c ln(eps+A_contour); max A = 1."""
    if glint is None and contour is None:
        return np.asarray(P, np.float32)
    ln = np.log(cfg.eps + np.asarray(P, np.float64))
    if glint is not None:
        ln = ln + cfg.w_glint * np.log(cfg.eps + np.asarray(glint, np.float64))
    if contour is not None:
        ln = ln + cfg.w_contour * np.log(cfg.eps + np.asarray(contour, np.float64))
    return np.exp(ln - ln.max()).astype(np.float32)


def _loo_shortfalls(lnA, L, idx, loo=True):
    """{k: (shortfall, argmax cell of the consensus without k)} for the regions in idx."""
    F = L[idx].sum(0) if len(idx) else np.zeros(lnA.shape[1])
    out = {}
    for k in idx:
        j = int(np.argmax(F - L[k])) if (loo and len(idx) > 1) else int(np.argmax(F))
        out[int(k)] = (float(-lnA[k, j]), j)
    return out


def fuse(A, weights, excluded=None, cfg: Config = Config(), centers=None, loo: bool = True) -> dict:
    """A: (R, 8192) region maps with max 1; weights (R,); excluded (R,) bool; centers (R, 3) optional.

    Verdict step 3 (documented deviation): candidates = {s_k > tau}. If the remaining reliable regions (>= 2)
    agree among themselves -> SUSPICIOUS(candidates). Otherwise try each candidate alone, highest shortfall
    first: if the rest without that one region is mutually consistent -> SUSPICIOUS(that region). Else CONFLICT.
    """
    A = np.asarray(A, np.float64).reshape(len(weights), -1)
    w = np.asarray(weights, np.float64)
    R = len(w)
    excluded = np.zeros(R, bool) if excluded is None else np.asarray(excluded, bool)
    reliable = (w >= cfg.w_min) & ~excluded
    idx = np.flatnonzero(reliable)
    lnA = np.log(cfg.eps + A)
    L = w[:, None] * lnA
    dirs = eq_dirs().astype(np.float64)
    tau, tau_ref = cfg.tau_img, cfg.tau_ref

    per = [dict(index=k, shortfall=None, angle_deg=None, flagged=False, reliable=bool(reliable[k]),
                excluded=bool(excluded[k]), ref_index=None) for k in range(R)]
    res = dict(verdict="INSUFFICIENT", reason="no reliable regions", S_img=0.0, top_region=None, consensus=None,
               consensus_map=None, per_region=per, n_reliable=int(len(idx)), flagged=[], tau=tau)
    if len(idx) == 0:
        return res

    F = L[idx].sum(0)
    j_star = int(np.argmax(F))
    C = np.exp((F - F.max()) / w[idx].sum())
    (f68, f95), _ = hpd(C)
    (broad,), _ = hpd(np.exp(F - F.max()), (0.95,))  # breadth test uses the product map, the cones the normalised one
    az, el = az_el_deg(dirs[j_star])
    res["consensus"] = dict(dir=[float(v) for v in dirs[j_star]], index=j_star, az_deg=az, el_deg=el,
                            r68_deg=cone_half_angle_deg(f68), r95_deg=cone_half_angle_deg(f95), frac95=broad)
    res["consensus_map"] = C.astype(np.float32)

    sf = _loo_shortfalls(lnA, L, idx, loo)
    for k in range(R):
        if excluded[k]:
            continue
        s, j = sf[k] if k in sf else (float(-lnA[k, j_star]), j_star)  # unreliable: against the full consensus
        per[k].update(shortfall=s, ref_index=j,
                      angle_deg=None if centers is None else float(angle_deg(centers[k], dirs[j])))
    k_top = max(sf, key=lambda k: sf[k][0])
    res.update(S_img=sf[k_top][0], top_region=k_top)

    if len(idx) < cfg.min_reliable:
        res["reason"] = f"only {len(idx)} reliable region(s); at least {cfg.min_reliable} are needed"
        return res
    if broad > cfg.broad_consensus_frac:
        res["reason"] = "the regions together do not pin down a light direction (consensus too broad)"
        return res
    if res["S_img"] <= tau:
        res.update(verdict="CONSISTENT", reason="")
        return res

    def consistent(rest):
        return len(rest) >= 2 and max(s for s, _ in _loo_shortfalls(lnA, L, rest, loo).values()) <= tau_ref

    cand = sorted((k for k in sf if sf[k][0] > tau), key=lambda k: -sf[k][0])
    flagged = None
    if consistent(np.array([k for k in idx if k not in cand], int)):
        flagged = cand
    else:
        for k in cand:
            if consistent(idx[idx != k]):
                flagged = [k]
                break
    if flagged is None:
        res.update(verdict="CONFLICT", reason="reference regions disagree: several lights or poor geometry")
        return res
    for k in flagged:
        per[k]["flagged"] = True
    res.update(verdict="SUSPICIOUS", reason="", flagged=[int(k) for k in flagged], top_region=int(flagged[0]))
    return res
