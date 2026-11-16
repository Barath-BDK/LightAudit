# Design: normal-free seam test for the marked-area (panel) check

Status: **built, measured, taken out of the verdict** (16 Nov 2026). Context: `HANDOVER.md` (sections 4–8).

**Outcome.** The fresh-context review predicted the two failures and the measurements confirmed them
(`BUILD_LOG.md` Update 10): a 4 px feather cuts S's detection from 20% to 4%, Poisson blending defeats it, and a
marked area drawn 4 px tight raises its false alarms to 64% (sectors near the object outline). At matched false
alarms it adds nothing on plain pastes and about +10 points on colour-matched, lightly feathered pastes. S is still
computed and stored (`panel_S`) but `tau_panel_S` is infinite, so it never votes.

## Problem

Every lighting test in LightAudit explains brightness through predicted surface normals (DSINE / Depth Anything).
On real photos the normals are the weakest link (`HANDOVER.md` §6.1: light estimator within 1–3° given true shape,
but predicted normals are 18–46° off). The marked-area ("panel") check works on real objects (45% of pasted areas
caught at 5.2% false alarms) but still depends on those normals.

## Idea (the fresh perspective)

Stop asking "which light explains this area?" and ask "does the light *join up* at the edge of the marked area?"

In the damage case the marked area (ROI) lies on the **same continuous surface** as its surroundings (a dent on a
car panel). Shading is then continuous across the ROI boundary. Across the boundary the log image can only jump by
a constant (a paint difference, or a forger's brightness/colour shift). If the ROI was pasted from a photo under a
different light, the jump is `log S_j(t) − log S_i(t)`. That ratio of two shadings changes as you go round the
boundary (parameter `t`). So:

> **the size of the log-brightness jump at the ROI boundary should be the same all the way round.**

This needs no normals, no light model and no albedo estimate. A forger's *gain* only moves the constant. (An
additive offset does not: `log(a·x + b) − log x` changes with brightness. S is computed on luminance only, so a
colour transfer acts on it through its effect on luminance.)

Why it failed and why this case differs: on whole indoor scenes (MIT Multi-Illumination, `eval/real_bench.py`) the
same statistic gave AUC 0.57–0.59. There, region boundaries are mostly occlusion edges, where shading is not
continuous: clean boundary noise (median std 0.61 in log units) was twice the injected signal (0.28). In the panel
case the boundary is inside one surface by construction, so that noise source is absent.

## Statistic `S` (`lightaudit/residual.py::seam_S`)

Inputs: linear luminance `lin`, ROI mask, panel mask (ROI ∪ ring ∪ rest), minimum valid brightness.

1. `L = log(max(lin, 1e-3))`. Signed distance `sd` to the ROI boundary (negative inside), from two Euclidean
   distance transforms.
2. Split the boundary into `K = 24` angular sectors around the ROI centroid; a pixel outside takes the angle of its
   nearest ROI pixel.
3. In each sector, fit `L = c + m·sd` by least squares separately on the inside band and the outside band,
   `GAP ≤ |sd| ≤ GAP + W` (`GAP = 2`, `W = 6` px, so feathering of a few pixels is skipped). Each side is
   extrapolated to the boundary, so a smooth shading gradient across the seam does not count as a jump.
   A side needs ≥ 8 pixels; outside pixels must be in the panel (not background).
4. Jump per sector: `j_k = c_in − c_out`. `S = median_k |j_k − median(j)|` (robust spread round the boundary).
   `None` if fewer than `K/2` sectors are usable.

## Use in the verdict

`panel_score` stores `roi["panel_S"]`. `panel_ratio` already takes the max of each statistic over its threshold;
`S / tau_panel_S` joins it. The real thresholds come from `eval/mit_panel.py` (split-conformal on even-index objects,
now `alpha/3` per statistic instead of `alpha/2`). The viewer only reads the combined `panel_z`, so
`viewer/fusion.js` and the parity vectors need no change. With no calibrated `tau_panel_S` (synthetic calibration)
the test is off (`inf`).

## Measured so far (prototype, MIT Intrinsic, same splice protocol as `eval/mit_panel.py`)

AUC 0.81 alone. Thresholds from the 10 even-index objects, rates on the 10 odd-index objects:
10% level → 10.0% false alarms, 47.9% caught; 5% level → 5.9% false alarms, 37.9% caught.
The current two-statistic check: 5.2% / 45% (10% level), 2.2% / 34% (5% level).

## To decide / risks

- Combination: does adding `S` to `T, Tr` raise detection at the same held-out false-alarm rate? (Measure in
  `eval/mit_panel.py` and under colour matching in `eval/mit_attack.py`; keep `S` only if it helps.)
- Real dents with scratches, dirt or primer inside the ROI create genuine paint edges that may cross the boundary.
  Those vary round the boundary too and would raise false alarms. Unmeasured (no real dent photos).
- The ROI must not touch the panel's outer edge or background for most of its boundary. Sectors without outside
  panel pixels are skipped.
- Very small ROIs (< ~400 px) have too few sectors; the statistic returns `None` (no vote).
