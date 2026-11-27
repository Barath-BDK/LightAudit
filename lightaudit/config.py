"""All numeric defaults (BUILD_SPEC section 20). Nothing is hard-coded elsewhere."""
from __future__ import annotations

import json
from dataclasses import dataclass, replace
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CALIB_DEFAULT = Path(__file__).resolve().parent / "calib_default.json"


@dataclass(frozen=True)
class Config:
    # grid
    NA: int = 128
    NE: int = 64
    coarse_step: int = 4
    refine_halfwidth: int = 6
    # image
    max_side: int = 1024
    fov_deg: float = 60.0
    # validity
    sat_hi: float = 0.97
    dark_lo: float = 0.04
    nz_min: float = 0.05
    unc_max: float = 35.0
    erode_px_frac: float = 0.008
    Nmax: int = 2500
    Nmin: int = 150
    N_exact: int = 1200  # spec says "up to 2000"; 1200 halves the cost with no visible change (logged)
    # regions
    min_region_px: int = 800
    max_region_frac: float = 0.7
    ring_px: int = 20
    # normals
    unc_floor: float = 4.0
    single_backend_unc: float = 12.0
    # posterior
    B: int = 30
    block_px: int = 24
    boot_min_px: int = 600
    draw_sigma_floor: float = 4.0
    kde_h: float = 10.0  # calibrated
    T: float = 1.0  # calibrated
    eps: float = 1e-3
    # glint
    blob_min: int = 4
    blob_max_frac: float = 0.02
    contrast_min: float = 0.15
    glint_sigma_floor: float = 8.0
    w_glint: float = 0.5
    # contour
    band_px: tuple = (3, 6)
    contour_nz_max: float = 0.5
    contour_min_px: int = 80
    contour_kappa: float = 0.1  # S -> [0,1] map: exp(-(Smax - S)/kappa)
    contour_min_rho: float = 0.3
    w_contour: float = 0.0  # silhouette cue is off by default: on 60 calibration scenes it did not help (0.5 = on)
    # shadow pairs
    shadow_sigma_px: float = 3.0
    w_shadow: float = 0.7
    # reliability
    w_min: float = 0.35
    min_spread_deg: float = 12.0  # flatter regions get no vote: on real photos they flagged clean scenes (BUILD_LOG Update 11)
    # verdict
    tau_img: float = 2.0  # calibrated
    tau_ref_factor: float = 1.0
    min_reliable: int = 3
    broad_consensus_frac: float = 0.35
    # a splice is one or two objects: more flagged regions than this (count and share of reliable) -> CONFLICT
    max_flagged: int = 2
    max_flagged_frac: float = 0.2
    # soft-light abstention: median over reliable regions of P10/P90 of linearised luminance (calibrated)
    soft_contrast: float = 0.34
    # panel mode: |mean residual| of the ROI against the panel's own shading curve, in robust sigmas (calibrated)
    tau_panel: float = 1.0  # panel_z is already a ratio to the calibrated levels below
    tau_panel_T: float = 1.0  # shared-light statistic, band-guarded Retinex (calibrated)
    tau_panel_Tr: float = 1.0  # shared-material statistic, band-guarded Retinex (calibrated)
    tau_panel_S: float = float("inf")  # seam statistic: reported, not used (4 px feathering defeats it, docs/designs/seam_test.md)
    panel_band: int = 3  # guard band (px) around the ROI boundary for Retinex: pasted regions are feathered
    retinex_thr: float = 0.10  # log-gradient above which Retinex calls an edge reflectance
    panel_min_px: int = 50
    # several lights: share of cast-shadow pixels on a large flat region that sit clearly above the darkest
    # shadow level (one sun: one level; two suns: two half-shadow levels). Above this -> CONFLICT (calibrated)
    shadow_levels_max: float = 0.30
    flat_min_frac: float = 0.05  # a flat region must cover this fraction of the image
    flat_min_R: float = 0.95  # ... and have a mean-normal resultant length of at least this
    # shading cue used by the audit: "ls" (least squares, default since it measured ~3x more accurate) or "rank"
    cue: str = "ls"
    # residual
    Klut: int = 33
    sigma_min: float = 0.015
    # calibration
    n_cal: int = 200
    n_cal_shape: int = 120
    alpha: float = 0.05
    h_grid: tuple = (4, 6, 8, 10, 14, 18, 24)
    T_grid: tuple = (0.5, 0.75, 1.0, 1.5, 2.0)
    # synth
    W: int = 512
    H: int = 352
    sigma_normals: float = 8.0
    # attacks
    sigma_att: tuple = (0, 5, 10, 20, 40)
    fidelity_max_dY: float = 0.08
    feather_px: float = 1.5
    # eval
    n_composite: int = 150
    n_pristine: int = 150
    bootstrap_CI: int = 1000

    @property
    def tau_ref(self) -> float:
        return self.tau_img * self.tau_ref_factor


SPLIT_SEEDS = {"cal": 1000, "arb": 2000, "test": 3000, "demo": 4000}


def load_calib(path: str | Path | None = None) -> dict:
    """Calibration dict; falls back to the uncalibrated defaults if no file exists yet."""
    p = Path(path) if path else CALIB_DEFAULT
    if p.exists():
        d = json.loads(p.read_text())
        d.setdefault("source", p.name)
        return d
    c = Config()
    return {"h": c.kde_h, "T": c.T, "tau_img_05": c.tau_img, "tau_img_10": c.tau_img,
            "tau_ref_factor": 1.0, "w_min": c.w_min, "source": "uncalibrated defaults"}


def calibrated(cfg: Config | None = None, calib: dict | None = None, alpha: float = 0.05) -> Config:
    """Config with h, T, tau, w_min taken from a calibration dict."""
    cfg = cfg or Config()
    calib = calib if calib is not None else load_calib()
    tau = calib["tau_img_05"] if alpha <= 0.05 else calib["tau_img_10"]
    return replace(cfg, kde_h=float(calib["h"]), T=float(calib["T"]), tau_img=float(tau),
                   tau_ref_factor=float(calib.get("tau_ref_factor", 1.0)),
                   w_min=float(calib.get("w_min", cfg.w_min)), alpha=alpha,
                   soft_contrast=float(calib.get("soft_contrast", cfg.soft_contrast)),
                   shadow_levels_max=float(calib.get("shadow_levels_max", cfg.shadow_levels_max)),
                   tau_panel_T=float(calib.get("tau_panel_T_05" if alpha <= 0.05 else "tau_panel_T_10", cfg.tau_panel_T)),
                   tau_panel_Tr=float(calib.get("tau_panel_Tr_05" if alpha <= 0.05 else "tau_panel_Tr_10", cfg.tau_panel_Tr)))


CALIB_REAL_PANEL = Path(__file__).resolve().parent / "calib_real_panel.json"


def real_panel(cfg: Config) -> Config:
    """Panel thresholds calibrated on real photographs (eval/mit_panel.py), at the 10% level: synthetic thresholds
    are several times too high for real images. Returns cfg unchanged if that file does not exist."""
    if not CALIB_REAL_PANEL.exists():
        return cfg
    c = json.loads(CALIB_REAL_PANEL.read_text())
    return replace(cfg, tau_panel_T=float(c["tau_panel_T_10"]), tau_panel_Tr=float(c["tau_panel_Tr_10"]),
                   tau_panel_S=float(c.get("tau_panel_S_10", cfg.tau_panel_S)))
