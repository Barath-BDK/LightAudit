"""Per-region reliability weight (BUILD_SPEC 7.10)."""
from __future__ import annotations

import numpy as np

REASONS = {
    "f_size": "too few usable pixels",
    "f_spread": "surface too flat",
    "f_sharp": "light direction poorly constrained",
    "f_dir": "weak directional shading (overcast/soft light?)",
    "f_norm": "normals unreliable",
}


def factors(n_valid, spread_deg, sharp_area, rho_max, mean_unc) -> dict:
    c = lambda x: float(np.clip(x, 0, 1))  # noqa: E731
    return {
        "f_size": c(n_valid / 800),
        "f_spread": c((spread_deg - 6) / (25 - 6)),
        "f_sharp": c(1 - sharp_area / 0.5),
        "f_dir": c((rho_max - 0.25) / (0.60 - 0.25)),
        "f_norm": c(1 - (mean_unc - 10) / (30 - 10)),
    }


def weight(f: dict) -> float:
    return float(np.prod(list(f.values())) ** (1 / 5))


def reason(f: dict) -> str:
    """Name of the smallest factor (used when a region is not reliable)."""
    return REASONS[min(f, key=f.get)]
