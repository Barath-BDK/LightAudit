import numpy as np
from conftest import CFG, c1_shortfall, spliced

from lightaudit.attacks import fidelity, ring_of, run_attack, t1_color_transfer
from lightaudit.imageio import luminance
from lightaudit.pipeline import audit_sample


def test_t3a_reduces_shading_shortfall():
    """T3a with the exact scene light and the defender's own normals (white-box). Spec: 10 scenes; we use 4
    to keep the suite fast (the full measurement is experiment E9)."""
    before, after = [], []
    for sd in (4000, 4001, 4003, 4005):
        s, comp, base = spliced(sd)
        rid = next(r["id"] for r in base["regions"] if r["name"] == "car body")
        reaudit = lambda rgb: audit_sample(s, cfg=CFG, composite=dict(comp, rgb=rgb), reuse=base, changed=[rid], residual=False)  # noqa: E731
        a = run_attack("T3a", base, rid, reaudit, sigma_att=0, seed=sd)
        assert a["fidelity"]["mean_abs_dY"] > 0 and 0 <= a["fidelity"]["ssim_loss"] <= 1
        sb, sa = c1_shortfall(base, rid), c1_shortfall(a["result"], rid)
        if sb is None or sa is None:  # region auto-excluded (e.g. saturated after re-shading): not assessed
            continue
        before.append(sb)
        after.append(sa)
    assert len(before) >= 3
    print("C1 shortfall before/after T3a:", np.round(before, 2), np.round(after, 2))
    assert np.mean(after) <= 0.5 * np.mean(before)


def test_t1_moves_colour_towards_ring():
    s, comp, base = spliced(4000)
    mask = base["labels"] == next(r["id"] for r in base["regions"] if r["name"] == "car body")
    out = t1_color_transfer(base["rgb"], mask, base["labels"], CFG)
    ring = ring_of(mask, base["labels"], CFG)
    Y0, Y1 = luminance(base["rgb"]), luminance(out)
    assert abs(Y1[mask].mean() - Y0[ring].mean()) < abs(Y0[mask].mean() - Y0[ring].mean())
    assert fidelity(base["rgb"], out, mask)["mean_abs_dY"] > 0
    assert (out[~mask] == base["rgb"][~mask]).all()
