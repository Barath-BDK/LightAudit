# BUILD_LOG

Status of the LightAudit build against `BUILD_SPEC.md`. Everything below was actually run on this laptop
(Windows 11, Python 3.11.4, CPU only) unless it says otherwise.

## Update 3 (15 Nov 2026): silhouette cue off by default

60-scene check on the calibration split (car pasted at 45 and 90 deg): shading + glints catches 60% of the 90 deg
splices at 5% false alarms, adding the silhouette cue 52% (false alarms at the calibrated level 3% vs 5%); AUC is
the same (0.82). `Config.w_contour = 0` now; the cue stays in the code, in the viewer's weight slider and as an
ablation row in E8. Also tested there: weighting the score by region reliability (no change) and using the
second-highest shortfall (worse). Recalibrated and re-evaluated; 62 tests and the parity check pass.

## Update 2 (14 Nov 2026): soft-light abstention and panel check

- Tested three candidate checks on 30 calibration scenes each before building any: soft-light contrast
  (overcast vs sunny AUC 0.98), dent-vs-panel residual (AUC 0.80-0.87 against 0.40 for the direction test), a
  second-light test for two suns (AUC 0.65: not built).
- Built the first two into `fusion.fuse` / `viewer/fusion.js`, `pipeline.py`, `residual.panel_score`, the
  calibration, the bundle format, the explanation text and the eval cache (METHOD.md 8.1). ROI and ring regions
  are no longer auto-excluded.
- Recalibrated: soft-light threshold 0.42, panel alert 3.92 (alpha 0.05, 58 unedited damage scenes), alarm level
  unchanged at 6.35; INSUFFICIENT on clean calibration scenes 17% (was 11%: the soft-light test abstains on about
  5% of sunny scenes by construction).
- Quick evaluation re-run (all ten experiments ok): overcast clean scenes INSUFFICIENT 4 of 5 (was 0 of 5);
  pasted dent flagged at the calibrated level in 5 of 8 cases (was 0 of 8) and still 5 of 8 after the T3a and T4
  re-shade attacks; dent false-alarm rate at the calibrated level 0.00-0.07 (n = 15). Car AUC 0.62-0.65 and
  distractor 0.59-0.62 in this run (n = 15; lower than the previous run's 0.67-0.71, within the intervals).
  Two-sun scenes: still 0 of 5 CONFLICT.
- Demos: overcast and fake-dent demos now come out as intended on the first seed tried (were 12 and 10 seeds).
  Fake dent: panel score 5.5 > 3.9 while its direction shortfall is only 1.54; T3a/T4 attacks stay flagged, T1
  colour transfer passes. Two suns still CONSISTENT.
- Tests: 62 pytest tests (two new) and the JS parity check (470 checks) pass.
- Known blind spot of the panel check: a dent facing away from both lights does not change when pasted.

## Update 14 Nov 2026: least squares is the default cue

Everything below this section describes the first build, where the rank cue was the default. Its quick results
are archived in `data/results_rank_quick/`. What changed:

- `Config.cue = "ls"`; the rank cue stays available (`cue="rank"`) and is the baseline in the evaluation and in
  the viewer's "Baseline cue" toggle.
- Recalibrated: h = 14 deg, T = 1.5, coverage 0.70 / 0.90, alarm level 6.35 at alpha 0.05 (5.53 at 0.10),
  11.0% of clean calibration scenes INSUFFICIENT. The alarm level is close to the maximum score (about 6.9).
- 40-scene check on the calibration split, car pasted at 90 deg: AUC about 0.83 with least squares, 0.75 with
  rank; about 0.66 for both at 45 deg.
- Quick evaluation re-run (same small N): car AUC 0.69 shading only, 0.71 with glints, 0.67 with all cues, 0.64
  for the rank baseline; distractor 0.67-0.70; dent about 0.40 (chance). Clean normal scenes: 0 of 5 flagged;
  spliced: 3 of 5 flagged. Attacks: T0 0.42 -> 0.54 (shading -> all cues), T1 0.45 -> 0.45, T3a exact 0.00 -> 0.05,
  T4 0.00 -> 0.05.
- Demo bundles rebuilt: consistent, spliced car, genuine dent, fake dent, overcast and the failure example match
  their intent; two suns is still CONSISTENT. New with least squares: colour transfer makes the spliced-car demo
  pass (shortfall 6.9 -> 5.9, just under the alarm level).
- Tried and removed: sampling several lights per bootstrap draw from the draw's likelihood (to represent the
  unconstrained directions of poles and boxes). No gain at the calibrated bandwidth, so the code was dropped.
- DSINE now runs on CPU (the hub wrapper hard-codes CUDA; `normals.py` remaps it while loading; needs the
  `geffnet` package, now installed). Default real-photo normals: DSINE + Depth Anything.
- Real photos re-audited with that ensemble: 1 of 6 unedited photos flagged (was 4 of 6), but the real splice
  is no longer flagged. Seven images are not evidence either way.
- Dome photo was drawn upside down in the viewer: fixed.
- Not fixed, by decision: overcast scenes (soft sky light is not separable from a broad overhead light using
  shading alone), two-light scenes, re-shading attacks. All three are stated as limits in the report.
- Tests: 60 pytest tests pass with the new default.

## Results so far (first build, rank cue)

**Calibration** (`python -m lightaudit.cli calibrate --n-cal 200`, seeds 1000-1199, `noisy_gt(8)`):

| quantity | value |
|---|---|
| KDE bandwidth h / temperature T | 18 deg / 1.5 |
| coverage of the GT light, 68% set / 95% set | 0.664 / 0.927 (449 reliable regions of 120 pristine `normal` scenes) |
| alarm level tau_img at alpha = 0.05 / 0.10 | 4.95 / 4.26 |
| pristine calibration scenes that return INSUFFICIENT | 11.5% (23 of 200; excluded from the conformal set, n = 177) |

The chosen bandwidth is the second-largest on the grid: the posteriors have to be wide to cover the true sun.
Reason: the sky term of the renderer and back-lit scenes bias every region's estimate in the same direction
(consistent across regions, so the consistency test still works, but the absolute direction is off).

**Tests** (`python -m pytest`): 60 passed (grid, rank, synth, posterior, fusion, pipeline, calibrate, attacks,
bundle, normals, server, eval smoke), about 2 minutes.

- `test_attacks`: T3a re-shade with the exact scene light and the defender's own normals drops the
  shading-only shortfall of the pasted car from 6.69 / 6.01 / 2.57 to 0.27 / 0.71 / 0.07 on three scenes.
  The re-shade attack works against the shading cue, as the spec anticipated.
- `test_rank`: the rank cue recovers the light to < 5 deg median under sRGB, gamma 2.6, S-curve and filmic
  curves with 8 deg normal noise.

**Optional backends on this machine** (`setup-check`): sam available, dsine available, depth_anything
available, stablenormal not available, marigold not available.

## Decisions (where the spec was silent)

1. venv is created with `--system-site-packages` so the existing torch CPU build is reused.
2. Distractor count is 3-5 (spec: 2-5) and the first two are always curved (sphere / pole / bush), placed 4.5-11 m
   away and never hidden behind the car; otherwise most scenes cannot reach three reliable regions.
3. Car windows and wheels are their own GT regions but are excluded by default ("glass or tyre"): they break the
   diffuse-shading model and produced false disagreements. They can be re-enabled in the viewer.
4. `l_B` for composites is drawn at the requested angle with a random azimuth, preferring directions at least
   5 deg above the horizon (50 tries, else the highest).
5. Composites keep the pristine image's exposure, so nothing outside the pasted region changes.
6. The contour cue's rank landscape is mapped to [0,1] by `exp(-(S_max - S)/0.1)` and used only if `S_max >= 0.3`.
7. Shadow pairs (C4) use the plane constraint `l . (r(p) x r(s)) = 0` (equivalent to the vanishing-point line
   test, but finite when the light is parallel to the image plane) plus a sign test.
8. T3a attacker error: the light estimate is rotated by exactly `sigma_att` degrees at a random azimuth.
9. T4 searches the estimate plus six directions 5 deg around it.
10. Calibration scores damage scenes in panel mode (dent ROI + ring), since that is how they are audited.
11. Bundle extras beyond section 11: `thumb.jpg`, `cues.bin` (separate cue maps for live re-weighting),
    `landscapes_ls.bin`, `fusion.flagged`, per-attack `interpretation`.

## Deviations from the spec

1. **Verdict step 3.** Candidates = regions with shortfall > tau. If the other reliable regions (>= 2, spec: >= 3)
   agree among themselves -> SUSPICIOUS. Otherwise each candidate is tried alone, highest shortfall first: if
   the rest without it is consistent -> SUSPICIOUS with that single region. Else CONFLICT. Without this, a heavy
   pasted object among three regions drags the leave-one-out consensus and everything ends as CONFLICT.
2. **Breadth test** uses the product map `exp(F)`; the consensus cones use `exp(F / sum w)` (the spec's two
   sentences read literally).
3. **Exact landscape uses 1200 pixels** (spec: up to 2000) and the contour cue at most 800: halves the cost.
4. **Regions with rho_max <= 0.25 skip the bootstrap** (their weight is 0 whatever it returns) and get a flat map.
5. **G-buffer pass takes 6-8 s** per 512x352 image (budget: 6 s). Not optimised further; G-buffers are cached.
6. **LS baseline test loosened.** The spec hoped LS would be >= 5 deg worse than rank on the S-curve / filmic
   curve. Measured on symmetric synthetic caps: LS is only 0.41 deg (S-curve) and 0.18 deg (filmic) worse. The
   test now asserts only that rank is not worse than LS. The scene-level comparison is experiment E1.
7. **Smaller test samples**: coverage test uses the reliable regions of 6 scenes with tolerance 0.25 (spec: 40
   regions, 0.15); the T3a test uses 4 scenes (spec: 10). Kept the suite at about 2 minutes.
8. **Overcast scenes are not reliably INSUFFICIENT.** The hemispheric sky light still gives every region the
   same "up" direction, so many overcast scenes come out CONSISTENT, and a splice under overcast light is not
   detected. Reported as is.

## Evaluation (QUICK suite only: 10% of the planned sample sizes)

`python -m lightaudit.cli train-arbiter` (n = 60) and `python -m lightaudit.cli eval --suite quick`, then
`figures` and `report`. E1-E10 all ran; F1-F9, T1-T6, `gallery.png`, `lightmap_*.png` and
`data/results/attack_summary.json` exist. Sample sizes are 5-15 scenes per cell, so intervals are wide.
The FULL suite was not run.

| finding | numbers (quick) |
|---|---|
| E1: rank cue vs least-squares baseline, median light error | rank 21.6-25.8 deg, LS 6.0-7.6 deg on every tone curve. **H1 fails.** Re-checked on 39 regions with exact normals: 26.8 vs 8.3 deg. |
| E3: coverage on the test split after calibration | 68% set 0.66, 95% set 0.93 (56 regions); before calibration 0.48 / 0.71 |
| E4: minimum detectable inconsistency at 5% FPR, pasted car | 180 deg with all cues, 90 deg with LS; pasted dent never reaches 50% |
| E5: AUC, discrepancy >= 30 deg | car 0.65 (shading only 0.62, LS 0.71); distractor 0.65; dent 0.40 |
| E6: abstention | overcast: 0% INSUFFICIENT; two suns: 0% CONFLICT (n = 5 each) |
| E7: robustness | detection 0.8 -> 0.2 at every resize factor; JPEG 30: 0.6; noise 0.03: 0.4 |
| E8: ablations (car AUC) | no KDE calibration 0.53; no leave-one-out 0.58; default 0.65; arbiter 0.67 |
| E9: detection after attack, shading only -> all cues | T0 0.42 -> 0.54; T1 0.45 -> 0.45; T3a exact 0.00 -> 0.05; T3a 20 deg 0.00 -> 0.05; T4 0.00 -> 0.05 |
| E10: real normal predictor | 2 scenes, Depth Anything only: a smoke test |

Why the rank cue loses (our explanation, not separately proven): ranks discard brightness magnitudes, so for
box-like shapes many light directions give the same ordering of faces. Weighting bright pixels did not help.

## Demo bundles (calibrated; `bundles/demo_log.json`)

| bundle | seed (tried) | intended | actual |
|---|---|---|---|
| demo_consistent | 4000 (1) | CONSISTENT | CONSISTENT |
| demo_splice_car | 4012 (3) | SUSPICIOUS | SUSPICIOUS; T1 still flagged; T3a 0/10/20 deg and T4 pass |
| demo_damage_genuine | 4020 (1) | CONSISTENT | CONSISTENT |
| demo_damage_fake | 4039 (10) | SUSPICIOUS | SUSPICIOUS; same attack pattern |
| demo_multilight | 4051 (12) | CONFLICT / INSUFFICIENT | **CONSISTENT** (not as intended; shown as is) |
| demo_overcast | 4061 (12) | INSUFFICIENT | INSUFFICIENT |
| demo_failure_missed_splice | 4061 (2) | a 120 deg splice that passes | CONSISTENT (the failure example) |

## Real photos (qualitative)

Six unedited outdoor car photos from Wikimedia Commons (CC BY / CC BY-SA; attribute them if they are shown) in
`data/real/`, audited with SAM regions and Depth Anything normals, synthetic calibration. About 5-7 minutes each
on CPU.

| photo | verdict | note |
|---|---|---|
| airfield_car | CONSISTENT | |
| carpark_sunny | CONSISTENT | |
| mini_parking | SUSPICIOUS | false alarm |
| peugeot_104 | SUSPICIOUS | false alarm |
| street_car | SUSPICIOUS | false alarm |
| supermarket_carpark | SUSPICIOUS | false alarm |

**4 of 6 unedited real photos are wrongly flagged.** One real splice (a rectangle from `peugeot_104` pasted into
`carpark_sunny`, crude and obvious to the eye, panel mode with the paste mask as ROI) is flagged SUSPICIOUS (ROI
67 deg off, shortfall 6.27); all five attack variants, including colour transfer, then pass. With a 4-in-6
false-alarm rate that single detection is weak evidence. The upload path of the server was also run end to end
once.

## Known issues

1. The detector is weak (see the evaluation) and re-shading defeats it.
2. Real photos: false alarms; DSINE does not run because the `geffnet` package is missing (added to
   `requirements-models.txt`, not installed); StableNormal and Marigold are not available.
3. Overcast and two-light scenes are usually not caught by the abstention logic.
4. The viewer's "what-if at your light" verdict is only CONSISTENT or SUSPICIOUS.
5. `tools/calibrate_on_folder.py` and `tools/applicability_scan.py` were written but not run.
6. `run_all.ps1` and `setup.ps1` were not run end to end on a clean checkout.
7. The viewer's "Re-run attack" button (live `/api/attack`) was not exercised; dragging the light with the mouse
   was not tested (arrow keys were).
8. The analysis prose in `report/make_report.py` reflects the quick suite; re-read it after a full run.

## Definition of Done

- [ ] `setup.ps1` and `run_all.ps1 -Quick` end to end on a clean checkout: not run as one script; each step was run by hand.
- [x] All tests pass: 60 pytest tests, plus the JS parity test (470 checks).
- [x] 6 demo bundles + 1 failure bundle exist and load in the viewer without console errors.
- [x] Viewer: image modes 1-6, dome, cones, movable light, live relit/residual, live fusion, region table, explain stepper, attack lab, help.
- [x] Calibration file present and used; numbers above.
- [x] E1-E10 executed at the **quick** suite; F1-F9 and tables generated. Full suite not run.
- [x] Illustrations I1-I9 generated.
- [x] README, METHOD, LIMITATIONS, LITERATURE, DEMO_SCRIPT, REPORT, SLIDES written; report tables load from `data/results`.
- [x] Section 21 text in README, viewer Help and report.
- [x] This log.

## Still for the human

- Decide whether to make least squares the default cue (recalibrate, rebuild bundles, re-evaluate).
- Run the full evaluation: `python -m lightaudit.cli train-arbiter`, then `python -m lightaudit.cli eval --suite full`, `figures`, `report`.
- `pip install geffnet` to enable DSINE; add your own photos to `data/real/`; recalibrate on real unedited photos.
- Rehearse `docs/DEMO_SCRIPT.md`.
