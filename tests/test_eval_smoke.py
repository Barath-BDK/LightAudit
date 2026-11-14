"""Fast smoke test of eval/metrics.py on toy data."""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from eval import metrics as M  # noqa: E402


def test_auc_basic_and_ties():
    assert M.auc([0, 1, 2], [3, 4, 5]) == 1.0
    assert M.auc([3, 4, 5], [0, 1, 2]) == 0.0
    assert abs(M.auc([1, 1], [1, 1]) - 0.5) < 1e-12
    # abstentions (-inf) tie with each other
    assert abs(M.auc([-np.inf, 0.0], [-np.inf, 1.0]) - 0.625) < 1e-12
    rng = np.random.default_rng(0)
    neg, pos = rng.normal(0, 1, 400), rng.normal(1, 1, 400)
    fpr, tpr = M.roc_curve(neg, pos)
    trap = float(np.sum(np.diff(fpr) * (tpr[1:] + tpr[:-1]) / 2))
    assert abs(trap - M.auc(neg, pos)) < 1e-3
    assert 0.70 < M.auc(neg, pos) < 0.82  # Phi(1/sqrt 2) ~ 0.76


def test_threshold_at_fpr():
    neg = np.arange(100, dtype=float)
    t = M.threshold_at_fpr(neg, 0.05)
    assert M.rate_above(neg, t) <= 0.05
    assert M.rate_above(neg, t - 1) > 0.05
    assert M.tpr_at_fpr(neg, [200, 50, 96], 0.05) == 2 / 3


def test_bootstrap_ci_and_mdi():
    x = list(np.random.default_rng(1).normal(5, 1, 200))
    p, lo, hi = M.bootstrap_ci(lambda g: float(np.mean(g)), x, n_boot=300)
    assert lo < p < hi and hi - lo < 0.6
    assert M.mdi([0, 10, 20, 30], [0.0, 0.2, 0.6, 0.9]) == (20.0, 17.5)
    assert M.mdi([0, 10], [0.1, 0.2]) == (None, None)
    assert M.mdi([0, 10], [0.7, 0.9])[0] == 0.0
