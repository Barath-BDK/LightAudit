"""Evaluation metrics (BUILD_SPEC 14): ROC/AUC, TPR at a fixed FPR, bootstrap confidence intervals, MDI.

Conventions used by every experiment:
- A *score* is larger for "more suspicious". Images on which the audit abstains (INSUFFICIENT) get score -inf,
  i.e. abstention counts as "not flagged" at every threshold.
- Detection at a threshold t means score > t (strict).
- A threshold "at FPR = f" is chosen on a set of negative (pristine) scores so that at most a fraction f of them
  lie strictly above it.
"""
from __future__ import annotations

import math

import numpy as np


def _clean(x) -> np.ndarray:
    x = np.asarray(x, np.float64).ravel()
    return x[~np.isnan(x)]


def auc(neg, pos) -> float:
    """Area under the ROC curve = P(pos > neg) + 0.5 P(pos == neg) (Mann-Whitney, ties handled, -inf allowed)."""
    neg, pos = _clean(neg), _clean(pos)
    if len(neg) == 0 or len(pos) == 0:
        return float("nan")
    allv = np.concatenate([neg, pos])
    # average ranks with ties; -inf values tie among themselves
    order = np.argsort(allv, kind="mergesort")
    ranks = np.empty(len(allv))
    sv = allv[order]
    i = 0
    while i < len(sv):
        j = i
        while j + 1 < len(sv) and sv[j + 1] == sv[i]:
            j += 1
        ranks[order[i:j + 1]] = (i + j) / 2 + 1
        i = j + 1
    rp = ranks[len(neg):].sum()
    return float((rp - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg)))


def roc_curve(neg, pos):
    """(fpr, tpr) arrays from (0,0) to (1,1); one point per distinct threshold."""
    neg, pos = _clean(neg), _clean(pos)
    th = np.unique(np.concatenate([neg, pos]))[::-1]
    fpr = [0.0] + [float((neg >= t).mean()) for t in th]
    tpr = [0.0] + [float((pos >= t).mean()) for t in th]
    if fpr[-1] < 1 or tpr[-1] < 1:
        fpr.append(1.0)
        tpr.append(1.0)
    return np.array(fpr), np.array(tpr)


def threshold_at_fpr(neg, fpr: float = 0.05) -> float:
    """Smallest threshold t (among the negative scores) with mean(neg > t) <= fpr."""
    neg = np.sort(_clean(neg))[::-1]
    if len(neg) == 0:
        return float("nan")
    k = int(math.floor(fpr * len(neg)))  # at most k negatives may exceed t
    if k >= len(neg):
        return float("-inf")
    t = neg[k]
    return float(t)


def rate_above(scores, t: float) -> float:
    s = _clean(scores)
    return float((s > t).mean()) if len(s) else float("nan")


def tpr_at_fpr(neg, pos, fpr: float = 0.05) -> float:
    return rate_above(pos, threshold_at_fpr(neg, fpr))


def bootstrap_ci(fn, *groups, n_boot: int = 1000, seed: int = 0, level: float = 0.95):
    """Percentile bootstrap CI of fn(*groups). Each group is a sequence indexed by scene and is resampled
    independently (with replacement) at the scene level. Returns (point, lo, hi)."""
    groups = [list(g) for g in groups]
    point = fn(*groups)
    if any(len(g) == 0 for g in groups):
        return float(point), float("nan"), float("nan")
    rng = np.random.default_rng(seed)
    vals = []
    for _ in range(n_boot):
        gs = [[g[i] for i in rng.integers(0, len(g), len(g))] for g in groups]
        v = fn(*gs)
        if v is not None and np.isfinite(v):
            vals.append(v)
    if not vals:
        return float(point), float("nan"), float("nan")
    a = (1 - level) / 2
    return float(point), float(np.quantile(vals, a)), float(np.quantile(vals, 1 - a))


def mdi(deltas, tprs, level: float = 0.5):
    """Minimum detectable inconsistency: the smallest grid delta whose TPR >= level (None if never reached),
    and the linearly interpolated crossing between that grid point and the previous one."""
    d = np.asarray(deltas, np.float64)
    t = np.asarray(tprs, np.float64)
    order = np.argsort(d)
    d, t = d[order], t[order]
    for i in range(len(d)):
        if np.isfinite(t[i]) and t[i] >= level:
            if i == 0 or not np.isfinite(t[i - 1]) or t[i] == t[i - 1]:
                return float(d[i]), float(d[i])
            x = d[i - 1] + (level - t[i - 1]) / (t[i] - t[i - 1]) * (d[i] - d[i - 1])
            return float(d[i]), float(x)
    return None, None


def median_ci(x, n_boot: int = 1000, seed: int = 0):
    x = _clean(x)
    if len(x) == 0:
        return float("nan"), float("nan"), float("nan")
    return bootstrap_ci(lambda g: float(np.median(g)), list(x), n_boot=n_boot, seed=seed)


def fmt_ci(p, lo, hi, digits: int = 2) -> str:
    if p is None or not np.isfinite(p):
        return "n/a"
    if not (np.isfinite(lo) and np.isfinite(hi)):
        return f"{p:.{digits}f}"
    return f"{p:.{digits}f} [{lo:.{digits}f}, {hi:.{digits}f}]"
