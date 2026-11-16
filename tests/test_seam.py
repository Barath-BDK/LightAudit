"""Seam statistic (residual.seam_S): a gain change of the marked area leaves it near zero, a paste from another
light raises it."""
import numpy as np

from lightaudit.residual import seam_S


def _scene():
    yy, xx = np.mgrid[:200, :200] / 200.0
    shade_a = 0.2 + 0.6 * xx  # light from the right
    shade_b = 0.2 + 0.6 * yy  # light from below
    labels = np.full((200, 200), 3, np.int32)  # panel remainder
    r = np.hypot(yy - 0.5, xx - 0.5)
    labels[r < 0.30] = 2  # ring
    labels[r < 0.15] = 1  # ROI
    regs = [dict(id=1, name="ROI"), dict(id=2, name="ring"), dict(id=3, name="panel (rest)")]
    return shade_a, shade_b, labels, regs


def test_seam_gain_invariant_and_paste_sensitive():
    a, b, labels, regs = _scene()
    roi = labels == 1
    enc = lambda lin: (np.clip(lin, 0, 1) ** (1 / 2.2)).astype(np.float32)  # noqa: E731
    clean = seam_S(enc(a), labels, regs)
    gain = seam_S(enc(np.where(roi, 0.7 * a, a)), labels, regs)
    paste = seam_S(enc(np.where(roi, b, a)), labels, regs)
    assert clean is not None and gain is not None and paste is not None
    assert clean < 0.02 and gain < 0.02
    assert paste > 5 * max(clean, gain, 0.01)
