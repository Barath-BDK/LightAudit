"""Region posterior: exact landscape, block bootstrap, KDE, credible regions (BUILD_SPEC 7.7)."""
from __future__ import annotations

import numpy as np

from .config import Config
from .cues.rank_shading import rank_landscape
from .grid import area_weights, coarse_index, cone_half_angle_deg, eq_dirs, hpd, window_index


def _smooth_noise(rng, ys, xs, sigma_rad):
    """Spatially correlated tangent noise: a Gaussian field at 1/8 resolution, bilinearly sampled."""
    y0, x0 = ys.min(), xs.min()
    gh, gw = (ys.max() - y0) // 8 + 2, (xs.max() - x0) // 8 + 2
    f = rng.normal(0, 1.5, (gh, gw, 3)).astype(np.float32)  # 1.5 ~ compensates the variance lost by interpolation
    fy, fx = (ys - y0) / 8.0, (xs - x0) / 8.0
    iy, ix = fy.astype(int), fx.astype(int)
    ty, tx = (fy - iy)[:, None].astype(np.float32), (fx - ix)[:, None].astype(np.float32)
    v = (f[iy, ix] * (1 - tx) + f[iy, ix + 1] * tx) * (1 - ty) + (f[iy + 1, ix] * (1 - tx) + f[iy + 1, ix + 1] * tx) * ty
    return v * sigma_rad[:, None]


def bootstrap_lights(normals, Y, ys, xs, unc, seed: int, cfg: Config = Config(), landscape_fn=rank_landscape,
                     scale: float = 1.0) -> np.ndarray:
    """(B, 3) light samples. Spatial block bootstrap + smooth normal perturbation; coarse argmax then local
    refinement on the fine grid. `scale` = image resize factor (block size is defined at the original resolution)."""
    rng = np.random.default_rng(seed)
    dirs = eq_dirs()
    cidx = coarse_index(cfg.coarse_step)
    bp = max(4, round(cfg.block_px * scale))
    blk = (ys // bp) * (xs.max() // bp + 1) + xs // bp
    order = np.argsort(blk, kind="stable")
    ub, start = np.unique(blk[order], return_index=True)
    groups = np.split(order, start[1:])
    sig = np.radians(np.maximum(cfg.draw_sigma_floor, unc)).astype(np.float32)
    out = np.empty((cfg.B, 3), np.float32)
    for b in range(cfg.B):
        pick, n = [], 0
        while n < cfg.boot_min_px:
            g = groups[rng.integers(len(groups))]
            pick.append(g)
            n += len(g)
        idx = np.concatenate(pick)
        nb = normals[idx] + _smooth_noise(rng, ys, xs, sig)[idx]
        nb /= np.maximum(np.linalg.norm(nb, axis=1, keepdims=True), 1e-6)
        Yb = Y[idx]
        k = cidx[int(np.argmax(landscape_fn(nb, Yb, dirs[cidx])))]
        win = window_index(k, cfg.refine_halfwidth)
        out[b] = dirs[win[int(np.argmax(landscape_fn(nb, Yb, dirs[win])))]]
    return out


def kde_posterior(samples: np.ndarray, h_deg: float, T: float = 1.0) -> np.ndarray:
    """P (8192,) float32 with max 1: Gaussian KDE of the bootstrap lights on the sphere, tempered by 1/T."""
    th = np.degrees(np.arccos(np.clip(eq_dirs() @ samples.T.astype(np.float32), -1, 1)))  # (D, B)
    P = np.exp(-th ** 2 / (2 * h_deg ** 2)).sum(1).astype(np.float64)
    P = (P / P.max()) ** (1.0 / T)
    return (P / P.max()).astype(np.float32)


def credible(P: np.ndarray):
    """(r68_deg, r95_deg, frac68, frac95, mask68, mask95) of a map on the grid."""
    (f68, f95), (m68, m95) = hpd(P)
    return cone_half_angle_deg(f68), cone_half_angle_deg(f95), f68, f95, m68, m95


def region_posterior(normals, Y, ys, xs, unc, seed: int, cfg: Config = Config(), landscape_fn=rank_landscape,
                     scale: float = 1.0) -> dict:
    """Everything 7.7 stores for one region, from its valid pixels (normals (N,3), Y, coords, unc in degrees)."""
    rng = np.random.default_rng(seed + 1)
    sub = rng.choice(len(Y), cfg.N_exact, replace=False) if len(Y) > cfg.N_exact else slice(None)
    S = landscape_fn(normals[sub], Y[sub], eq_dirs())
    rho = float(S.max())
    sharp = float(area_weights()[S >= rho - 0.05].sum())
    mean_n = normals.mean(0)
    mean_n /= max(np.linalg.norm(mean_n), 1e-6)
    spread = float(np.percentile(np.degrees(np.arccos(np.clip(normals @ mean_n, -1, 1))), 90))
    if rho <= 0.25:  # f_dir = 0 -> weight 0 whatever the bootstrap says: skip it (uninformative map)
        return dict(S=S.astype(np.float32), P=np.ones(len(eq_dirs()), np.float32), samples=None, rho_max=rho,
                    sharp_area=sharp, spread_deg=spread, center=eq_dirs()[int(np.argmax(S))].astype(np.float64),
                    r68_deg=180.0, r95_deg=180.0)
    samples = bootstrap_lights(normals, Y, ys, xs, unc, seed, cfg, landscape_fn, scale)
    P = kde_posterior(samples, cfg.kde_h, cfg.T)
    r68, r95, *_ = credible(P)
    c = samples.astype(np.float64).mean(0)
    c = c / np.linalg.norm(c) if np.linalg.norm(c) > 1e-6 else eq_dirs()[int(np.argmax(P))].astype(np.float64)
    return dict(S=S.astype(np.float32), P=P, samples=samples, rho_max=rho, sharp_area=sharp, spread_deg=spread,
                center=c, r68_deg=r68, r95_deg=r95)
