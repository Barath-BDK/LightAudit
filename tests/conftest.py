"""Shared, cached synthetic scenes and audits so the suite stays fast (scenes also hit the on-disk G-buffer cache)."""
from functools import lru_cache

from lightaudit.config import calibrated
from lightaudit.pipeline import audit_sample, fuse_regions
from lightaudit.synth import get_sample, light_at_angle, paste

CFG = calibrated()
SEEDS = (4000, 4001, 4003)


@lru_cache(maxsize=None)
def pristine(seed, kind="normal"):
    s = get_sample(seed, kind)
    return s, audit_sample(s, cfg=CFG)


@lru_cache(maxsize=None)
def spliced(seed):
    """Car pasted from a light 120 degrees away; only the car body is re-analysed."""
    s, base = pristine(seed)
    comp = paste(s, "car", light_at_angle(s.scene.l_world, 120, seed))
    ids = [r["id"] for r in base["regions"] if r["id"] in comp["edited_ids"] and not r["excluded"]]
    return s, comp, audit_sample(s, cfg=CFG, composite=comp, reuse=base, changed=ids)


def c1_shortfall(res, rid):
    """Shortfall of region `rid` with the shading cue only."""
    regs = [dict(r) for r in res["regions"]]
    fuse_regions(regs, CFG, cues=("shading",))
    return next(r for r in regs if r["id"] == rid)["shortfall"]
