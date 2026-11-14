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
    w_contour: float = 0.5
    # shadow pairs
    shadow_sigma_px: float = 3.0
    w_shadow: float = 0.7
    # reliability
    w_min: float = 0.35
    # verdict
    tau_img: float = 2.0  # calibrated
    tau_ref_factor: float = 1.0
    min_reliable: int = 3
    broad_consensus_frac: float = 0.35
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
                   w_min=float(calib.get("w_min", cfg.w_min)), alpha=alpha)
