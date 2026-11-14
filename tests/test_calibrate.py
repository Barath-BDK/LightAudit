import numpy as np

from lightaudit.calibrate import conformal_quantile


def test_conformal_quantile_controls_false_alarms():
    """Held-out pristine scores exceed the conformal threshold with probability <= alpha (averaged over splits)."""
    rng = np.random.default_rng(0)
    for alpha in (0.05, 0.10):
        fpr = []
        for _ in range(300):
            cal, test = rng.gamma(2.0, 0.5, 200), rng.gamma(2.0, 0.5, 400)
            fpr.append((test > conformal_quantile(cal, alpha)).mean())
        assert np.mean(fpr) <= alpha + 0.03


def test_conformal_quantile_edge_cases():
    assert conformal_quantile([1, 2, 3, 4], 0.5) == 3  # ceil(5 * 0.5) = 3rd smallest
    assert conformal_quantile([1.0, 2.0], 0.05) == float("inf")  # too few scores for this alpha
