# LightAudit — handover

Written 16 November 2026. State of the repository at commit `ae2794a` on `main`
(https://github.com/Barath-BDK/LightAudit). Nothing is running and nothing is uncommitted.

Read this first, then `BUILD_LOG.md` (Updates 1–8 hold every measured number and deviation, newest first) and
`docs/LightAudit_Results.pdf` (the results report with screenshots).

---

## 1. What the project is

A course project (Interactive Computer Graphics, semester 7): an explainable lighting-consistency auditor for
edited photos, with an interactive 3D viewer and a self-attack lab. Motivating use case: vehicle-damage photos in
insurance claims. Four verdicts: `CONSISTENT`, `SUSPICIOUS`, `INSUFFICIENT`, `CONFLICT`. A flag means "send for
human review", never "this is fraud".

The original brief is `BUILD_SPEC.md` (keep untouched, like `PLAN.md`). The project has since moved away from
the brief's central idea; section 4 explains why.

## 2. One-paragraph status

Everything in the brief is built and runs. Two things are measured to work: (a) on **real photographs**, checking
a marked area of an object against the surface around it (the damage case): 5.2% false alarms, 45% of pasted areas
caught, 57% when the light differs by 80° or more, 32% after the forger matches colour and brightness; (b) on
synthetic scenes, abstaining under overcast light and recognising two-light scenes. What does **not** work:
deciding whether a whole object was pasted into a real photo (chance level on real indoor scenes, 4 of 6 unedited
outdoor photos wrongly flagged), and any whole-object splice after a physics re-shade. All synthetic numbers come
from the quick evaluation suite (5–15 scenes per cell); the full suite has never been run.

## 3. How to run

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\setup.ps1
.\.venv\Scripts\python.exe -m lightaudit.cli serve      # http://127.0.0.1:8000
```

| Task | Command (prefix with `.\.venv\Scripts\python.exe`) |
|---|---|
| Tests (63) | `-m pytest` |
| Browser/Python parity (506 checks) | run `node viewer/tests/parity.test.mjs` |
| Synthetic calibration | `-m lightaudit.cli calibrate --n-cal 200` |
| Demo bundles | `-m lightaudit.cli demo-bundles` |
| Quick / full evaluation | `-m lightaudit.cli train-arbiter --n 60` then `-m lightaudit.cli eval --suite quick` (or `full`) |
| Figures, tables, report | `-m lightaudit.cli figures`, `-m lightaudit.cli report` |
| Audit a real photo, marked area | `-m lightaudit.cli audit --image photo.jpg --roi mask.png --html` |
| Real benchmark (curved objects) | `eval/mit_bench.py prepare`, then `eval/mit_panel.py`, `eval/mit_attack.py` |
| Real benchmark (indoor scenes) | `eval/real_bench.py prepare`, then `eval/real_bench.py bench` |
| Real-object viewer demos | `tools/make_mit_demo.py` |

A full recalibration cycle (calibrate → demo-bundles → train-arbiter → eval quick → figures → report) takes
roughly 30–45 minutes on this laptop. One real photo with SAM takes 5–7 minutes on CPU.

**Environment facts**
- Windows 11, Python 3.11, no GPU. `.venv` was created with `--system-site-packages` (reuses torch 2.9 CPU).
- Working normal/segmentation backends: SAM, DSINE (needs `geffnet`, installed by the user), Depth Anything.
  StableNormal and Marigold are not available; `diffusers` is not installed.
- **Package installs were blocked for the assistant** by a permission check (`pip install geffnet` was denied).
  Ask the user to install anything new.
- Shell quoting trap: bash heredocs containing `'''` fail here. Write helper scripts with the Write tool.
- `python` seeds must not use `hash()` (randomised per process); `zlib.crc32` is used in the benchmarks.
- Browser cache trap: the server now sends `Cache-Control: no-cache`, but a browser that cached old viewer code
  needs one hard refresh (Ctrl+F5). `python -m http.server` does not send that header.

**Data that is not in git** (licence uncertainty, re-download needed)
- `data/multilum/` — MIT Multi-Illumination, six scenes at mip3 (about 17 MB). `eval/real_bench.py fetch N`
  downloads more; scene archives are `https://data.csail.mit.edu/multilum/<scene>/<scene>_mip3_jpg.zip`.
- `data/mit_intrinsic/` — MIT Intrinsic Images (102 MB tar from
  `https://www.cs.toronto.edu/~rgrosse/intrinsic/intrinsic-data.tar.gz`); extract so that
  `data/mit_intrinsic/<object>/light01.png` exists.
- `bundles/real_mit_*` — rebuilt by `tools/make_mit_demo.py`.
- `data/real/*.jpg` (six Wikimedia Commons photos, CC BY / CC BY-SA) **are** committed; attribute them if shown.

## 4. How the method works now (and how it differs from the brief)

| Piece | Brief | Now | Why |
|---|---|---|---|
| Shading cue | rank correlation (tone-curve invariant) | **least squares** (`Config.cue = "ls"`); rank kept as baseline | rank is ~3× less accurate (22–26° vs 6–8° median error) |
| Silhouette cue | on | **off** (`w_contour = 0`), still available | no gain on 60 calibration scenes |
| Verdict step 3 | exclude all candidates, need ≥3 references | also tries each candidate alone; ≥2 references | a heavy outlier among three regions otherwise always gives CONFLICT |
| Overcast | expected INSUFFICIENT from reliability | explicit **soft-light check** (shading contrast P10/P90) | sky light looks like a broad overhead light, so the direction test called it consistent |
| Two lights | expected CONFLICT from disagreement | explicit **cast-shadow-level check** on a large flat region | shading-based signals could not see a second light |
| Dent / panel mode | ROI as a region in the direction test | **shared-material + shared-light test** with band-guarded Retinex | a dent is too small and shallow for a light estimate |
| Real-photo thresholds | synthetic calibration | panel thresholds from real objects (`calib_real_panel.json`) | synthetic thresholds are several times too high on real images |

Order of checks in `lightaudit/fusion.py::fuse` (mirrored in `viewer/fusion.js`): consensus fusion → soft light
(→ INSUFFICIENT) → shadow levels (→ CONFLICT) → panel flag (→ SUSPICIOUS unless CONFLICT).

Key code: `lightaudit/pipeline.py` (audit), `fusion.py`, `residual.py` (`retinex_albedo`, `fit_light`,
`shared_material_T`, `shared_light_T`, `panel_shared`, `panel_score`, `shadow_levels`), `calibrate.py`,
`config.py` (`Config`, `calibrated`, `real_panel`), `normals.py`, `attacks.py`, `bundle.py`; viewer in `viewer/`.

Current calibration (`lightaudit/calib_default.json`, synthetic): h 14°, T 1.5, coverage 0.70 / 0.90, alarm level
6.29 (max possible ≈ 6.9), soft-light 0.42, shadow-levels 0.29, panel 1.68 (light test) / 5.65 (material test),
19.5% of clean scenes get no decision. Real panel thresholds at the 10% level: 0.85 / 2.41.

## 5. Results to quote

### Real photos — marked-area (dent) check, `eval/mit_panel.py`, 10 held-out objects, 400 clean + 400 spliced
| Setting | False alarms | Caught | 0–25° | 25–50° | 50–80° | ≥80° |
|---|---|---|---|---|---|---|
| 10% level | 5.2% | 45% | 36% | 41% | 47% | 57% |
| 5% level | 2.2% | 34% | 27% | 27% | 36% | 51% |

After colour/brightness matching of the pasted area (`eval/mit_attack.py`): 32% caught at 5.2% false alarms
(previous version of the check: 20%). With the other half of the objects calibrating: 10.2% false alarms, 52%
caught, 33% after colour matching. **Threshold transfer is uneven** (5% one way, 10–19% the other): ten objects
are too few. Per object the range is wide (pear 85% caught but 15% false alarms; box and frog 23%).

### Real photos — whole-object check
- Indoor scenes (`eval/real_bench.py`, 6 scenes): AUC 0.49–0.59, 0.64 at ≥90°. Chance.
- Six unedited outdoor photos (`data/real`): 4 flagged SUSPICIOUS. One real splice: not flagged.

### Synthetic (quick suite)
- Pasted car, AUC for ≥30°: 0.65 (rank baseline 0.57); at 90° 4 of 5 and 6 of 8 caught; clean scenes 0 of 5 flagged.
- Pasted dent: 5 of 8 caught; false alarms 4 of 15; 6 of 8 after re-shade attacks; **0 of 8 after colour matching**.
- Whole car after re-shade (T3a, T4): **0 of 8** caught; pasted object 1 of 7.
- Overcast: 4 of 5 INSUFFICIENT. Two suns: 3 of 5 CONFLICT, 2 of 5 INSUFFICIENT. Low resolution: weak.

## 6. What was found along the way (keep these in mind)

1. **The light estimator is correct on real photos.** With a gray ball's true shape the estimate is within 1–3° of
   the truth in six scenes. The weak link is the predicted surface normals.
2. **DSINE's x axis was mirrored** relative to the pipeline (46° normal error on a sphere, 18–25° after negating
   x). Fixed in `normals._run_dsine`. Every real-photo result before that fix is invalid.
3. **DSINE's hub wrapper hard-codes CUDA**; `normals.py` remaps it to CPU while loading.
4. **Averaging DSINE and Depth Anything is not better than the better one.** Synthetic: DSINE 21° light error,
   mean 27°, Depth Anything 37°. Real balls: Depth Anything steadier (DSINE fails badly in 2 of 6 scenes).
   The MIT object benchmark uses Depth Anything alone.
5. **Most regions in real scenes are flat** (smallest eigenvalue of the normal covariance ≈ 0). A flat region with
   unknown colour says nothing about the light. Curved synthetic objects sit around 0.006–0.017.
6. **False alarms scale with region count**: the max-shortfall score correlates 0.43 with the number of regions;
   a per-region likelihood-ratio test with Holm correction removes it (0.09). In the benchmark only.
7. **Retinex hides splices unless guarded.** Plain Retinex on a composite reads the paste-boundary step as paint
   (AUC 0.66, below no correction at 0.74). Guarding a 3 px band around the known boundary gives 0.81–0.86.
8. **Synthetic thresholds do not transfer to real images** (real statistics are several times smaller).
9. **The simulated normals were realistic**: DSINE's error on synthetic renders is 10°, the simulation's 9°.

## 7. Tried and did not work (do not repeat without a new idea)

| Idea | Outcome |
|---|---|
| Rank-correlation shading cue as the main cue | 3× less accurate than least squares; ranks discard brightness magnitudes |
| Weighting the rank correlation toward bright pixels | no change |
| Silhouette / contour cue | no gain; slightly more false alarms |
| Sampling several lights per bootstrap draw (to represent ridges for poles/boxes) | no gain at calibrated bandwidth; code removed |
| Score = reliability-weighted shortfall; score = second-highest shortfall | no change; worse |
| Second-light fit for two suns (also with the sky gradient removed) | AUC 0.65–0.70 |
| Summary signals for two suns (fit quality, angular spread of regions) | AUC ≤ 0.67 |
| Chromaticity clusters, unclamped first-order SH, log-domain fit on real indoor scenes | AUC 0.52–0.54 |
| Shared paint levels per segment (jointly estimated) | 0.72–0.73, no better than no correction |
| Plain Retinex; Retinex after Gaussian smoothing | worse than no correction on composites |
| Material test without Retinex as the second panel statistic | on real objects it mostly added false alarms; replaced by the light test |
| Gradient-boosted arbiter instead of the rule | not better in the quick suite |
| Averaging the two normal models | not better than the better single model |
| Real-photo audit with synthetic thresholds | no real splice flagged |

## 8. Known problems, in order of importance

1. Whole-object check fails on real photos; re-shading defeats it even on synthetic scenes.
2. The real-photo evidence is from tabletop objects with within-object splices, **not cars and not real dents**.
   Genuine damage with scratches, dirt or primer inside the marked area may raise false alarms. Unmeasured.
3. Calibration on ten real objects is unstable (5% vs 10–19% false alarms across splits).
4. Synthetic dent false alarms rose to 4 of 15 with the current pair of tests; colour matching still defeats
   synthetic dents.
5. The alarm level for the whole-object check (6.29) sits near the top of the scale (≈ 6.9).
6. The two-sun and soft-light checks are untested on real photos; the two-sun check needs a large flat surface
   and could be fooled by road markings or stains.
7. Only the quick evaluation has ever been run.
8. **Stale documents**: `report/REPORT.md` prose (`report/make_report.py`), `report/SLIDES.md`,
   `docs/LightAudit_Guide.pdf`, parts of `docs/METHOD.md` and `README.md` predate Updates 5–8 (shared-material
   test, Retinex, real calibration, two-sun check). `docs/LightAudit_Results.pdf`, `docs/DEMO_SCRIPT.md` and
   `BUILD_LOG.md` are current. PDFs were never visually checked (no PDF renderer on this machine).
9. `LightAudit.zip` in the project root predates most of this work (git-ignored).
10. Not exercised: `setup.ps1` + `run_all.ps1` as one clean run, `tools/calibrate_on_folder.py`,
    `tools/applicability_scan.py`, the viewer's "Re-run attack" button, dragging the light with the mouse.
11. The GitHub token the user pasted into the chat was never used (existing git credentials worked). It should be
    revoked if that has not been done.

## 8b. Update 16 Nov 2026 (later the same day)

See `BUILD_LOG.md` Updates 9-10 and `docs/designs/`. Seam test and light-colour cue tried and not kept; cast-shadow
consistency test added (`cues/shadow_pairs.shadow_consistency`, synthetic only). New weakness found: Poisson
blending defeats the marked-area check (38.5% -> 4.8% caught). Fallback tag: `fallback-2026-11-16`.
Blocked on the user: CarDD licence form (https://cardd-ustc.github.io/docs/CarDD_license.pdf) and
`pip install git+https://github.com/compphoto/Intrinsic` into `.venv`.

## 9. What to do next

**Short, safe steps**
1. Bring the stale documents (item 8 above) in line with `LightAudit_Results.pdf`; regenerate PDFs via headless
   Edge (`msedge --headless --print-to-pdf=...`), and have a human look at them.
2. Run the full evaluation suite (`eval --suite full`, 1–2 hours) and update the numbers.
3. Rebuild `LightAudit.zip` with `git archive --format=zip --prefix=LightAudit/ -o LightAudit.zip HEAD`.

**Steps that need the user**
4. Real car photos: 40–50 clean directional-light photos and 20–30 self-made splices with masks (the user's
   Track A plan). Without them the target domain is untested.
5. More real objects for calibrating the marked-area check (ten is too few).
6. Optional: install `diffusers` + `accelerate` to try Marigold's intrinsic-decomposition model instead of Retinex.

**Method work with measured promise**
7. Move the per-region likelihood-ratio test with Holm correction (`eval/real_bench.py::lr_scores`) into the
   whole-object fusion. It needs the same change in `viewer/fusion.js` and new parity vectors.
8. Add a normal-diversity gate (smallest eigenvalue of the normal covariance) to the reliability weight, so flat
   regions abstain instead of voting.
9. Decide the normals policy for real photos (currently DSINE + Depth Anything mean; evidence favours using one
   model for the estimate and the disagreement only as uncertainty).

## 10. Possible routes for the project

**Route A — keep pushing real-image accuracy (the user's "Track A").** Success criteria the user set: ≤10–15%
false alarms on held-out clean photos and AUC ≥ 0.75 on ≥90° splices. Met for the marked-area check on real
tabletop objects (hard-edged benchmark AUC 0.86, 0.91 at ≥80°); not met for whole-object splices. Needs the
user's own photos to go further.

**Route B — pitch as an honest, self-attacking forensic audit (the user's stated pick).** Contribution: calibrated
abstention, a measured map of when lighting evidence exists and when it does not, and the attack lab. The
findings support it: "necessary, not sufficient" for whole objects, a marked-area check that works on real
photos and survives re-shading, explicit abstention for overcast and two-light scenes. Remaining work is mostly
documentation (items 1–3 above).

**Route C — promote shadow geometry to a main cue** (Kee, O'Brien & Farid: lines from object points through their
shadow points meet at one point). Needs no surface normals, which sidesteps the weakest link found here. The
manual shadow-pair cue (C4, `cues/shadow_pairs.py`, `viewer/shadow_tool.js`) already exists; estimated 1–2 days.

**Route D — flip it into a compositor**: estimate the scene light and relight an inserted object to match, with
the auditor as the metric. The relight shader and attack lab are most of this. Graphics-heavy, demos well.

**Route E — learned patch light estimator** trained on the synthetic renderer. Fits the ML angle; sim-to-real is
the risk, and the flat-region finding applies to it too.

Recommendation recorded during the work: Route B as the framing, with the marked-area check as the real-image
result, and Route C as the next real-image cue if time allows.

## 11. Conventions the user asked for

- Commit and push to `origin main` after each step (existing git credentials work; a pasted token is not needed).
- Commit messages end with `Co-Authored-By: Claude Fable 5.2 <noreply@anthropic.com>`.
- Report results as measured, including failures; log every deviation in `BUILD_LOG.md`.
- `/graphify` (knowledge-graph skill) has not been run on this repository. If it is, exclude `.venv`, `data/`,
  `bundles/`, `viewer/vendor/`, `unslop/`, `blender/`, and re-run it after changes to `lightaudit/`, `eval/` or
  `viewer/`.
