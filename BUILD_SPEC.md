# LightAudit — BUILD SPEC (one-shot brief for the implementing agent)

> You are the implementing agent. Read this whole file before writing code. It contains the project context, the exact scope, the algorithms with numbers, the file layout, the data formats, the UI, the experiments, the figures, the docs and the acceptance tests. Everything marked **P0** must work. **P1** should work. **P2** is built last and may be dropped only if you record why in `BUILD_LOG.md`. Anything in section 3.2 ("Later") must NOT be built.
>
> The human has **5 days** and will submit this as a university course project. The deliverable is a **working, demo-able, honestly evaluated product**, not a research paper. Prefer boring, robust code over clever code. Never fabricate a number: every figure and table must be produced by code you actually ran.

---

## 0. Hard rules

1. **Autonomy.** Do not ask the human questions. Where this spec is silent, choose the simplest sensible default and record it in `BUILD_LOG.md` (section "Decisions").
2. **Runs on a Windows 11 laptop, Python 3.11, no GPU.** All core features (synthetic engine, cues, fusion, calibration, evaluation, attacks, viewer, server) must run on CPU with only the *core* dependencies. Heavy pretrained models (SAM, normal estimators) are **optional backends** with graceful fallback (section 7.3, 7.4). Use `pathlib`, no bash-only scripts (give PowerShell `.ps1` scripts; also `.sh` if you like). Guard multiprocessing entry points with `if __name__ == "__main__":` (Windows spawn).
3. **Existing files.** The folder already contains `PLAN.md` (background plan), and three early drafts: `lightaudit/grid.py`, `lightaudit/cues/rank_shading.py`, `tests/test_rank_shading.py`. They are **superseded** by this spec (the grid is now the equirectangular grid of section 5.2). Overwrite or delete them. Keep `PLAN.md` untouched.
4. **No stubs.** No `TODO`, `pass`, `NotImplementedError`, or fake outputs in shipped paths. If you cannot implement a P2 item, delete it from the UI and docs and log it.
5. **Determinism.** Every random process takes a seed. Seeds are specified in section 14.
6. **Honesty.** The product detects *lighting inconsistency*, not "AI images" and not "fraud". Every UI/report/doc that shows a verdict must say a flag means "send for human review". Include the limitations text of section 21 verbatim in the README, the viewer's Help panel and the report.
7. **Self-verification.** Run the test-suite and the quick evaluation before finishing. Write what you ran and the outcomes to `BUILD_LOG.md`. If something fails, fix it; if it cannot be fixed, say so plainly in the log.
8. **Dependencies.** Add to `requirements-core.txt` / `requirements-models.txt` (section 4). Do not pin exact versions unless something breaks; if you pin, say why.

---

## 1. What this project is (context)

**Title:** LightAudit — Explainable Lighting-Consistency Auditing of Edited Images, with Relighting-Attack Evaluation.

**Course:** Interactive Computer Graphics (ICG), semester 7. The project must integrate Interactive Computer Graphics with Computer Vision and/or Image Processing and AI. Graders will look at: a working interactive demo, clear use of CG (rendering/shaders/3D), CV, IP and ML, a sensible evaluation, and an honest report.

**The problem.** Edited or composited photos are hard to verify. Existing forgery detectors output an opaque score and can be fooled. In a real photo of an outdoor scene, one dominant light (the sun) lights every object, so surfaces facing the light are brighter. If an object or damage region was pasted from a photo with different lighting, the light direction implied by its shading disagrees with the rest of the scene. LightAudit estimates, for each region of a photo, **which directions the light could come from**, checks whether **one common direction explains all regions**, shows the evidence interactively, says "insufficient evidence" when it cannot tell, and then **attacks itself** (re-lights a fake to match the scene) to measure how easily a forger could pass.

**Primary use case (for the demo and narrative):** checking vehicle-damage photos in insurance claims (is the dent/scratch pasted or edited in?). The method itself is domain-generic: it works on any outdoor-like scene with a dominant directional light.

**Triage output (maps to insurance workflow):**
- `CONSISTENT` → normal processing.
- `SUSPICIOUS` (with the flagged region(s)) → send to a human adjuster with the evidence view.
- `INSUFFICIENT` → not enough usable lighting cues (overcast, tiny regions, flat surfaces): request a better photo.
- `CONFLICT` → reference regions disagree among themselves (multiple lights, bad geometry): do not decide automatically.

A flag is **never** proof of fraud. It is one signal among many.

**What is novel / what is not (do not overclaim).** Lighting-inconsistency forensics (Johnson & Farid 2005; Kee, O'Brien & Farid 2013/2014), multi-cue probabilistic light estimation (Lalonde et al. 2009/2012), and relighting as an attack on detectors already exist. Our contribution is an engineering + evaluation one: a **tone-curve-invariant rank-based shading cue**, a **calibrated spherical-posterior formulation with leave-one-out shortfall test and abstention (conformal false-alarm control)**, a **multi-cue fusion** (shading, specular glints, silhouette edges, optional shadow pairs), a **counterfactual interactive viewer**, and a **tiered self-attack evaluation**.

---

## 2. Course-grade mapping (what must be visibly present)

| Area | Where it appears | Must be demonstrable |
|---|---|---|
| **Computer Graphics** | (a) NumPy SDF ray-marching renderer producing synthetic ground-truth scenes (section 8); (b) WebGL2 fragment-shader **relighting renderer** (Lambert + Blinn-Phong/GGX) used for the relit view, the counterfactual and the residual heatmap; (c) Three.js **3D light dome** with per-region probability landscape shader, cones, draggable light; (d) the physics re-shade attack | Dragging the light on the dome updates the relit image, per-region agreement and the live verdict at interactive frame rates |
| **Computer Vision** | Segmentation (SAM / superpixels), surface-normal estimation (pretrained ensemble), per-region light-direction estimation, glint and silhouette cues, consistency test, abstention | Run on real photos and on synthetic scenes |
| **Image Processing** | Pixel validity filtering (saturation, deep shadow, borders), robust statistics, block bootstrap, color transfer (Reinhard), JPEG/resize/noise robustness, residual z-score heatmaps | Robustness figure (F8) |
| **ML / AI** | Pretrained SAM and normal models as black boxes; ensemble disagreement as uncertainty; a small gradient-boosted **arbiter** trained on synthetic composites (P1); conformal calibration of the alarm threshold | Arbiter vs rule ablation; calibration plot |

---

## 3. Scope

### 3.1 Build now (this spec)

P0 (must):
- Core library `lightaudit` (sections 5–7, 9, 10).
- Synthetic data engine with ground truth (section 8).
- Calibration (section 9).
- Evaluation suite + all figures and tables (section 14, 15).
- Static web viewer with dome, relight shader, heatmaps, live verdict, explain stepper, attack lab (section 12).
- Bundle export (section 11), CLI (section 13), demo bundles (section 13.3).
- Docs: README, METHOD, LIMITATIONS, LITERATURE, DEMO_SCRIPT, REPORT, SLIDES outline (section 16).
- Tests (section 17).

P1 (should):
- FastAPI server with upload-and-audit (13.2).
- Real-photo path with SAM + normal-model ensemble (7.3, 7.4) and `tools/make_real_splice.py`.
- Contour cue C3 and rank-vs-LS baseline in the viewer.
- Gradient-boosted arbiter and its ablation.
- Self-contained HTML evidence report per image (`export_report`).
- Real-normal-predictor-in-the-loop evaluation on synthetic renders (14, E10), only if `torch` + a normal backend are available.

P2 (last):
- Cast-shadow pair cue C4 (manual pairs in the viewer + backend math, 7.8).
- Live `/api/attack` endpoint.
- Applicability scan script for a folder of real photos.

### 3.2 Later — do NOT build

Learned relighting attacks (IC-Light, Neural Gaffer, DiffusionRenderer), diffusion inpainting forgery, shadow-generating insertion models, TruFor/VLM baselines, KITTI/nuScenes sun-ephemeris ground truth, EXIF sun-position check, CAD car shape prior, GPU shadow-map analysis, spherical-harmonic environment lighting, mixture-of-lights models, user study, authentication.

---

## 4. Environment and dependencies

Existing environment: Windows 11, Python 3.11.4, numpy 2.x, scipy 1.17. Create a venv `.venv`.

`requirements-core.txt` (must be enough for everything except real-photo models):
```
numpy
scipy
scikit-learn
scikit-image
opencv-python
pillow
matplotlib
tqdm
pytest
fastapi
uvicorn
python-multipart
pandas
```
`requirements-models.txt` (optional, heavy; CPU build of torch is fine):
```
torch
torchvision
transformers
diffusers
accelerate
```
Provide `setup.ps1` that creates the venv, installs core, and *tries* models (continue on failure, print which backends are available). Provide `lightaudit/backends_available()` returning a dict like `{"sam": bool, "dsine": bool, "stablenormal": bool, "marigold": bool, "depth_anything": bool}` determined by import/try-load checks (do not download models during import; download lazily on first use).

Viewer: no bundler. Static ES modules. Vendor Three.js (r160 or newer stable) and `OrbitControls` into `viewer/vendor/` using `npm pack three` or by downloading from `https://cdn.jsdelivr.net/npm/three@0.160.0/` (module build + `examples/jsm/controls/OrbitControls.js`). `viewer/index.html` uses an import map pointing at the vendored copy, with the CDN as a fallback. The viewer must work offline once vendored.

---

## 5. Conventions (get these exactly right; most bugs live here)

### 5.1 Coordinate systems
- **Camera space:** `+x` right, `+y` up, `+z` toward the viewer (out of the screen). A visible surface normal has `n_z > 0`.
- **Image pixels:** `(u, v)` with `u` right, `v` down. Pixel `(u, v)` ↔ ray direction (pinhole, principal point at the image centre, horizontal FOV `fov_deg`, default 60°, square pixels): `d = normalize([(u−cx)/f, −(v−cy)/f, −1])` where `f = (W/2)/tan(fov/2)`. The **view vector** from a surface point toward the camera is `v_cam = −d` (so pointing roughly `+z`).
- **Light direction `l`:** unit vector from the surface point **toward the light**. Full sphere allowed (backlit and behind-camera lights are legal).
- **Normal-map PNG encoding:** `RGB = round((n + 1)/2 · 255)` with `(x, y, z)` in the convention above.

### 5.2 The one canonical direction grid ("EQ grid")
Equirectangular, `NA = 128` azimuth columns × `NE = 64` elevation rows = 8192 directions. Cell `(j, i)`, `j ∈ [0, 64)` row (top = up), `i ∈ [0, 128)` column:
```
az  = -π + (i + 0.5) · 2π / 128          # azimuth, 0 = +z (toward viewer), +x = +π/2 (right)
lat = π/2 − (j + 0.5) · π / 64           # elevation, +π/2 = +y (up)
x = cos(lat)·sin(az);  y = sin(lat);  z = cos(lat)·cos(az)
area_weight[j] = cos(lat)                # solid-angle weight (normalize to sum 1)
```
Python and JavaScript must implement this identically (a shared test vector file `tests/vectors/grid_vectors.json` is produced by Python and checked by JS). All landscapes, posteriors, fusion and the dome texture live on this grid. Arrays are shaped `[64, 128]` row-major (`j` major) and flattened with index `k = j·128 + i`.

Coarse grid for bootstrap: every 4th cell in both axes (`16 × 32 = 512` directions), then local refinement on the fine grid (7.5).

### 5.3 Intensity
`Y = 0.2126 R + 0.7152 G + 0.0722 B` on the **sRGB-encoded** values in `[0, 1]` (display domain). Rank-based cues do not need linearisation. Where a linear value is needed (synthetic renderer, LS baseline) say so explicitly and use gamma 2.2.

---

## 6. Repository layout (create exactly this)

```
Course_Project/
  README.md                BUILD_LOG.md          BUILD_SPEC.md (this file)   PLAN.md (keep)
  requirements-core.txt    requirements-models.txt   setup.ps1   run_all.ps1   pyproject.toml
  lightaudit/
    __init__.py            config.py            grid.py           imageio.py
    regions.py             normals.py           validity.py
    cues/__init__.py       cues/rank_shading.py cues/glint.py     cues/contour.py   cues/shadow_pairs.py   cues/ls_baseline.py
    posterior.py           fusion.py            reliability.py    residual.py       explain_text.py
    calibrate.py           arbiter.py           pipeline.py       bundle.py
    attacks.py             synth/__init__.py    synth/sdf.py      synth/render.py   synth/scenes.py   synth/composite.py
    cli.py                 server.py            report_html.py
  eval/
    run_eval.py   exp_*.py (one per experiment)   metrics.py   make_figures.py   make_tables.py
  figures/
    make_illustrations.py          # conceptual diagrams and the pipeline SVG
  tools/
    make_real_splice.py   applicability_scan.py   calibrate_on_folder.py   fetch_viewer_vendor.py
  viewer/
    index.html  style.css  app.js  state.js  fusion.js  grid.js  dome.js  relight.js  ui.js  explain.js  attack.js  text.js  shadow_tool.js
    vendor/   tests/parity.test.mjs
  bundles/        index.json + one folder per bundle (generated)
  data/           real/ (user photos, may be empty)   synth/ (generated, gitignored)   results/ (JSON/CSV from experiments)
  docs/           METHOD.md  LIMITATIONS.md  LITERATURE.md  DEMO_SCRIPT.md  figures/ (generated PNG/SVG)
  report/         REPORT.md  SLIDES.md  make_report.py
  tests/          test_grid.py test_rank.py test_synth.py test_posterior.py test_fusion.py test_pipeline.py test_calibrate.py test_attacks.py test_bundle.py vectors/
```

---

## 7. Core algorithms (the heart of the product)

All numeric defaults live in `lightaudit/config.py` as a frozen dataclass `Config` (section 20). Nothing is hard-coded elsewhere.

### 7.1 Inputs to the core
A region-level audit needs: `Y` (H×W float), `rgb`, `normals` (H×W×3, camera space, unit), `unc` (H×W, normal uncertainty in **degrees**; 0 for GT normals), `labels` (H×W int, 0 = unassigned, `1..R` regions) and `fov_deg`.

### 7.2 Pixel validity (`validity.py`)
For each region `k`, valid pixels are those that satisfy **all**:
1. Inside the region mask eroded by `erode_px = max(3, round(0.008·min(H,W)))` (kills unreliable boundary normals).
2. `Y ≤ 0.97` (not saturated; saturated pixels go to the glint cue) and `Y ≥ 0.04` (not deep shadow).
3. `n_z ≥ 0.05` and `unc ≤ 35°`.
Then, if more than `Nmax = 2500` valid pixels remain, subsample with a **stratified spatial** scheme (random pick within a regular grid of cells) using the region seed. Keep the pixel coordinates (`ys, xs`) because block bootstrap needs them. If fewer than `Nmin = 150` valid pixels remain the region gets weight 0 (`reason = "too few usable pixels"`).

### 7.3 Region proposals (`regions.py`)
Return a label map and per-region metadata `{id, name, area, bbox, source}`. Backends:
- `gt` — synthetic ground-truth object ids (used for all large experiments).
- `sam` (P1) — `transformers` `pipeline("mask-generation", model="facebook/sam-vit-base", device=-1)`; run at long side ≤ 768; keep masks with area ≥ `min_region_px = 800` and ≤ 70% of the image; paint masks in descending area order so smaller masks overwrite larger ones; drop regions left with < 800 px; merge masks with IoU > 0.85. Verify the actual transformers API at runtime (it has changed across versions) and log failures.
- `slic` — `skimage.segmentation.slic` (n_segments≈40, compactness≈10) then greedily merge adjacent superpixels with similar mean colour (Lab ΔE < 8) and similar mean normal (angle < 20°) until ≥ 800 px; this is the always-available fallback.
- `manual` — user-provided label PNG or polygon JSON (`--regions manual:path`).
- ROI mode (**panel mode**): `--roi roi_mask.png` creates region `"ROI"` from the mask, region `"ring"` = `dilate(ROI, ring_px=max(20, 2·erode_px)) − ROI` restricted to pixels that were in the same original region as the ROI, and removes both from the parent region (the parent remainder is kept as `"<name> (rest)"`).
Auto-exclusion (`auto_exclude=True`): mark `excluded=True` (kept in output, weight 0, shown greyed in the UI) for: *sky* (touches the top border, mean `Y > 0.6`, std(Y) < 0.04); regions where > 40% of pixels are saturated; regions with `area < 800`. The user can toggle exclusion in the viewer (the fusion is re-run client-side).

### 7.4 Normals (`normals.py`)
Public function `predict_normals(rgb, backends=("dsine","stablenormal"), fov_deg=60) -> (normals, unc, info)`.
- Backends (each wrapped in `try/except`, lazy imports, results cached to `data/cache/`):
  - `gt` / `noisy_gt` (synthetic only; see 8.5).
  - `dsine`: `torch.hub.load("hugoycj/DSINE-hub", "DSINE", trust_repo=True)`; call `model.infer_cv2(rgb)`; output `(3,H,W)`-like normals in `[-1,1]`.
  - `stablenormal`: `torch.hub.load("Stable-X/StableNormal", "StableNormal", trust_repo=True)`; returns a PIL normal image → decode `n = img/127.5 − 1`.
  - `marigold`: `diffusers.MarigoldNormalsPipeline.from_pretrained("prs-eth/marigold-normals-v1-1")`; output `.prediction`.
  - `depth_anything`: `transformers.pipeline("depth-estimation", model="depth-anything/Depth-Anything-V2-Small-hf")`; convert relative depth to normals via image-space gradients of pseudo-depth with the pinhole model (low quality; last resort).
  These APIs change; **verify them at runtime, adapt, and log**. Each backend must pass `normalize_convention()`:
- **Convention check (mandatory).** Backends disagree on axis directions. For each backend implement `fix_convention(normals)` that (a) normalises vectors, (b) tests the three flips of x, y, z using these priors on the *image itself*: the median normal of the bottom 15% of image rows (usually ground) should have `y > 0` (up); the median of all pixels should have `z > 0`; surfaces on the left half of a convex object tend to face left (`x < 0`)… use only the first two priors for automatic decisions, log the decision, and expose overrides `--flip-x/--flip-y/--flip-z`. Include a unit test with a synthetic sphere render passed through a fake backend that applies a flip.
- **Ensemble:** run every available backend in `backends`; resample to the image size; the fused normal = normalised mean; `unc` = per-pixel mean angular deviation (degrees) between each member and the fused normal, **floored at `unc_floor = 4°`** (a single backend gets `unc = 12°` constant plus a small texture term; never claim 0). Log which backends ran in `info`.

### 7.5 Cue C1 — tone-curve-invariant rank shading (`cues/rank_shading.py`) **[P0, the main cue]**
Model: within a region (same material, roughly constant albedo), `Y_i = g(max(0, n_i · l))` with an **unknown monotone non-decreasing `g`**. This absorbs camera response, gamma, HDR tone-mapping, exposure, ambient offset and albedo scale. Estimate `l` by maximising a rank correlation.

Landscape on direction set `Ldirs` (`D×3`):
```
s   = normals_valid @ Ldirs.T                  # (N, D)
sc  = max(s, 0)
rs  = column-wise ranks of sc, with all s<=0 entries tied at the mean rank of the zero group
ry  = ranks of Y (ties → average rank)
S(l) = Pearson(rs[:, l], ry)                   # = Spearman with ties handled
```
Implementation notes (performance matters):
- Compute the zero-tie group as: for each column `z = count(s ≤ 0)`; those entries get rank `(z−1)/2`; the rest get `argsort(argsort(sc))`. Vectorise; use `float32`.
- `rank_landscape(normals, Y, dirs) -> S (D,)` is the exact function. Test: on a Lambertian synthetic sphere cap, recovers the light to < 5° under several monotone tone curves.
- Per-region summary: `rho_max = max S`, `argmax`, `spread_deg` = 90th percentile of the angle between each valid normal and the mean valid normal, `sharp_area` = fraction of sphere (solid-angle weighted) with `S ≥ rho_max − 0.05`.
- **Why this cue:** it removes the brief's fragile assumption of linear radiometry and independent albedo scale; it is also a half-space-voting method (each pixel pair constrains `l` to a half-sphere), which links it to Kee's constraint view. Say this in `METHOD.md`.

### 7.6 Cue C2 — specular glints (`cues/glint.py`) **[P0]**
Pixels the C1 cue discards (`Y > 0.97`) carry strong information on glossy paint: a highlight appears where the mirror direction of the view vector about the normal points at the light.
- Detect glint blobs inside the region: connected components of `Y > 0.97` with area between 4 px and 2% of region area, whose local contrast `mean(Y_blob) − mean(Y in a 5-px ring excluding saturated pixels) ≥ 0.15`. Reject blobs larger than that (they are white paint or sky reflections).
- For each blob: `n_h` = normalised mean of the (ensemble) normals over the blob dilated by 2 px; `v` = view vector at the blob centroid (5.1); `l_h = 2 (n_h·v) n_h − v`; angular std `σ_h = sqrt(σ_n² + σ_floor²)` with `σ_n = mean(unc over blob)` and `σ_floor = 8°`.
- Landscape: `A_glint(l) = exp(−θ(l, l_h)² / (2 σ_h²))` per blob; the region's C2 landscape = normalised **mean** over blobs (not product; a reflection of some other bright thing must not veto the sun), multiplied by a cue weight `w_glint = 0.5` when entering the fusion (7.7).
- A region has C2 only if ≥ 1 blob is accepted.

### 7.7 Region posterior (`posterior.py`) **[P0]**
Goal: for each region, a normalised **posterior-like map** `P_k` on the EQ grid (max = 1), plus the credible-region summaries (the cones).

1. **Exact landscape** `S_k` on the full EQ grid (8192 dirs) from C1 using up to 2000 pixels.
2. **Block bootstrap, `B = 30` draws** (config). Spatial blocks: tile the region's bounding box with square blocks of side `block_px = 24` px (in the *original image resolution*; scale if the image is resized); a bootstrap draw resamples blocks with replacement until ≥ 600 pixels. In each draw also perturb the normals with spatially smooth noise: a Gaussian vector field of std `σ_draw = max(4°, unc)` per pixel, generated at 1/8 resolution and bilinearly upsampled so errors are spatially correlated, then renormalise. Compute the coarse landscape (512 dirs, 7.1) → pick the coarse argmax → refine by evaluating all fine-grid cells within ±6 cells (13×13 window, wrap in azimuth) → sample `l_b` = refined argmax.
3. **KDE posterior:** `P_raw(l) = Σ_b exp( θ(l, l_b)² / (−2 h²) )` with bandwidth `h` degrees (calibrated, default 10°), then `P = P_raw^{1/T}` (temperature `T`, calibrated, default 1.0), then `P ← P / max P`. Sum with the area weight not needed here.
4. **Credible regions:** sort cells by `P` descending, accumulate `area_weight`-weighted mass; the 68% and 95% highest-density sets give solid angles `Ω68`, `Ω95`; equivalent cone half-angles `r = arccos(1 − Ω/(2π))`. `center` = the direction of the bootstrap circular mean (normalised mean of `l_b`).
5. **Summaries stored per region** (`region_result`): `id, name, n_valid, spread_deg, rho_max, sharp_area, center (xyz), center_az_el_deg, r68_deg, r95_deg, P (8192 float32), S (8192 float32), cues_used, has_glint, weight, reliable, reason`.
Credible-region *calibration* (choosing `h`, `T`) is section 9.

### 7.8 Cue C4 — cast-shadow pairs (`cues/shadow_pairs.py`) **[P2]**
Manual: the user clicks an object point `p` and the corresponding shadow point `s` of that point (2D image coordinates) in the viewer; ≥ 2 pairs. For a directional light, the 3D light rays through each `(point, shadow point)` pair are parallel, so the image lines through `p_j, s_j` meet at the vanishing point `vp` of the light direction, and the 3D direction is `d ∝ K⁻¹ vp`. For a candidate light `l`, let `vp(l) = K · (l with camera-space sign convention applied)` in homogeneous image coordinates (document the sign handling carefully; the line through `p_j, s_j` should pass through `vp(l)`). Residual for pair `j` = point-to-line distance of `vp(l)` to line `(p_j, s_j)` normalised by the line length and a pixel-uncertainty `σ_px = 3`; landscape `A_shadow(l) = exp(−Σ_j r_j² / 2)` normalised. Entered into the fusion as a **scene-level** region `"shadow pairs"` with its own weight 0.7. The viewer tool (`shadow_tool.js`) lets the user click pairs, shows the lines, sends them to the fusion client-side (compute `A_shadow` in JS on the EQ grid). Mark with an on-screen "experimental" badge. Include a test with a synthetic scene (shadow pairs computed from the renderer's GT).

### 7.9 Cue C3 — silhouette/contour (`cues/contour.py`) **[P1]**
At true occluding contours the surface normal lies in the image plane. For each region, take boundary pixels (3–6 px inside the mask boundary) where the *predicted* normal has `n_z < 0.5` (the network agrees the surface is grazing) and whose contour direction has stable orientation; assume `n = (cos φ, sin φ, 0)` with `φ` the outward 2D contour normal in camera axes (`y` up → remember the image `v` flip). Run C1's `rank_landscape` on these pixels with these *geometric* normals (needs ≥ 80 pixels; else no C3). The landscape is a ridge (the depth component of `l` is unconstrained) — correct and expected; render it faithfully. Cue weight `0.5`. This cue needs no neural network.

### 7.10 Reliability weight (`reliability.py`) **[P0]**
Per region, five factors in `[0,1]`:
```
f_size   = clip(n_valid / 800, 0, 1)
f_spread = clip((spread_deg − 6) / (25 − 6), 0, 1)
f_sharp  = clip(1 − sharp_area / 0.5, 0, 1)
f_dir    = clip((rho_max − 0.25) / (0.60 − 0.25), 0, 1)
f_norm   = clip(1 − (mean_unc − 10) / (30 − 10), 0, 1)
weight w = (f_size · f_spread · f_sharp · f_dir · f_norm) ** (1/5)       # geometric mean
reliable = (w ≥ w_min = 0.35) and not excluded
```
`reason` = the name of the smallest factor when `reliable` is false (used for text: "too few usable pixels", "surface too flat", "light direction poorly constrained", "weak directional shading (overcast/soft light?)", "normals unreliable"). With the arbiter (P1) the factors are features but the rule above remains the default.

### 7.11 Fusion, consensus, shortfall, verdict (`fusion.py`) **[P0]** — must be mirrored in JS (`viewer/fusion.js`)

Region-level cue combination: `ln A_k(l) = ln(ε + P_k^{C1}(l)) + w_g · ln(ε + A_glint) + w_c · ln(ε + A_contour)` (cues present only), then `A_k = exp(ln A_k − max)` so `max A_k = 1`. `ε = 1e-3`. (If only C1 exists, `A_k = P_k`.) Scene-level cues (shadow pairs) are separate pseudo-regions.

Consensus over a set `R` of reliable regions with weights `w_j`:
```
F_R(l)  = Σ_{j ∈ R} w_j · ln(ε + A_j(l))
l*_R    = argmax_l F_R(l)                      # on the EQ grid
```
Leave-one-out **shortfall** of region `k`:
```
l*_{-k}  = argmax_l Σ_{j ∈ R, j≠k} w_j ln(ε + A_j(l))
s_k      = −ln(ε + A_k(l*_{-k}))               # 0 = region fully agrees, up to −ln(ε) ≈ 6.9
```
Also report `angle_k = angle(center_k, l*_{-k})` in degrees.

Image-level score `S_img = max_{k ∈ R} s_k`, `k_top = argmax`.

Verdict logic (thresholds from calibration, section 9; defaults `tau_img = 2.0`):
1. If `|R| < 3` **or** the consensus is uninformative (`max F_R` posterior is broad: the 95% HPD of the product map covers > 35% of the sphere) → `INSUFFICIENT`, reason = the dominant cause.
2. Else compute `S_img`. If `S_img ≤ tau_img` → `CONSISTENT`.
3. Else the candidate set = `{k : s_k > tau_img}`. Re-compute consensus **excluding all candidates**; if the remaining reliable regions (≥ 3 needed) have their own max shortfall `> tau_ref` (default `tau_img`) → `CONFLICT` ("reference regions disagree: several lights or poor geometry"). Otherwise `SUSPICIOUS` with the candidates sorted by `s_k`.
4. A candidate that is *unreliable* is never flagged (it appears under "regions that could not be assessed").

Outputs: `verdict, S_img, k_top, per-region {s_k, angle_k, flagged}, consensus {direction, az/el, r68, r95}, consensus_map (F_R normalised)`. The consensus 68/95% cones come from HPD sets of `exp(F_R/Σw)` (normalised).

The JS port must produce identical `l*`, `s_k` and verdict for the same inputs (parity test, 17).

### 7.12 Residual heatmap, counterfactual and albedo-free relight (`residual.py`) **[P0]**
For each reliable (and each non-excluded) region with consensus `l*` (the leave-one-out consensus for flagged candidates, the full consensus otherwise):
1. `s = max(0, n · l*)` on **all** region pixels.
2. Fit an isotonic regression `ĝ_k` (increasing, `sklearn.isotonic.IsotonicRegression`, `out_of_bounds="clip"`) on the valid pixels `(s, Y)`. Export it as a LUT with `Klut = 33` knots `s = 0, 1/32, …, 1` (linear interpolate, enforce monotonicity).
3. Predicted display luminance `Ŷ = ĝ_k(s)`; residual `r = Y − Ŷ`; `σ_k = max(0.015, 1.4826 · MAD(r over valid pixels))`; slope `m_k = (ĝ_k(1) − ĝ_k(0))`.
4. Per-pixel z-score: `z = |r| / sqrt(σ_k² + (m_k · u_rad)²)` where `u_rad = unc·π/180`.
5. Heatmap PNG: `clip(z/4, 0, 1)` (inferno colormap in the viewer; export the raw 8-bit grey).
6. Counterfactual image: per pixel `rgb_cf = rgb · (Ŷ + 0.01)/(Y + 0.01)` clipped to [0,1] (observed colours rescaled to the brightness the model predicts under `l*`).
7. Export per region: `g_lut (33)`, `sigma`, `slope`.
This is "analysis by synthesis": estimate the light, predict how the region *should* look, compare to the real pixels.

### 7.13 Rank-vs-LS baseline (`cues/ls_baseline.py`) **[P1]**
The original approach: linearise `Y_lin = Y^2.2`, solve `Y_lin ≈ a + L·n` by (Huber-robust) least squares, light = `L/|L|`. Plug it into the **same** posterior machinery (bootstrap + KDE + calibration) by providing an alternative `landscape_fn`: define its landscape as `S(l) = Pearson(Y_lin, max(0, n·l))`; this is a fair "same pipeline, different cue" ablation. Used in F1, F5, E8.

### 7.14 Explanation text (`explain_text.py`, mirrored in `viewer/text.js`) **[P0]**
Rule-based sentences generated **only** from the numbers (no LLM). Templates, e.g.:
- `CONSISTENT`: "{n} regions agree on one light direction (about {az}° azimuth, {el}° elevation). The largest disagreement is {name} at {angle}° (below the alert level)."
- `SUSPICIOUS`: "The estimate for **{name}** points {angle}° away from where {m} other regions agree. Its own light map does not overlap the consensus (agreement {A:.2f}; shortfall {s:.1f} > alert {tau:.1f}). Cues: {cues}. Please review manually."
- `INSUFFICIENT`: "Not enough usable lighting evidence: {reason_counts}. Try a photo outdoors in direct light with several objects visible."
- `CONFLICT`: "The reference regions disagree among themselves, which usually means several lights or unreliable geometry. No automatic decision."
Azimuth/elevation display: azimuth measured clockwise from the camera direction when viewed from above (`atan2(x, z)`), elevation `asin(y)`; add a tiny diagram in the Help panel explaining it.

---

## 8. Synthetic data engine (`lightaudit/synth/`) — the ground-truth backbone

Pure NumPy, CPU, deterministic by seed. Purpose: exact normals, exact light, object masks, composites at any discrepancy angle, realistic camera effects. Size default `W×H = 512×352`.

### 8.1 Scene model
World: `y` up, ground plane `y = 0`. Camera at height 1.4–1.8 m, pitched down 3–10°, horizontal FOV 60°; camera space per 5.1 (`z_cam` toward viewer). Provide `R_cam_from_world` and test that a world light maps to the right camera-space vector.
Objects as signed distance functions (SDFs) with material ids:
- **Car** (always): body = rounded box ~4.2×0.7×1.8 m at `y≈0.55`; cabin = rounded box/ellipsoid ~2.2×0.55×1.5 m on top, slightly set back; four wheels = cylinders (r 0.35, width 0.25); windows = cabin side patches flagged by a different material id; random yaw in `[−60°, 60°]` relative to the camera so a long side is visible; distance 6–10 m.
- **Distractors** 2–5: spheres, boxes, cylinders ("poles"), noisy rough spheres ("bushes"), one big box far behind ("building"), all with random Lambertian albedo, occasionally slightly glossy.
- **Ground:** plane with low-frequency albedo noise (multi-octave value noise). **Sky:** vertical gradient (excluded from audit; region id 0).
- **Dent (damage scenes):** a Gaussian displacement `−depth·exp(−|p−c|²/(2σ²))` applied to the body SDF near a centre `c` on the camera-facing side panel, `depth ∈ [0.03, 0.06]` m, `σ ∈ [0.12, 0.20]` m, giving normal deviations up to ~20°. The dent mask = pixels with hit-point within `2.5σ` of `c`.

### 8.2 G-buffer pass (`render.py: render_gbuffer`)
Sphere-trace (≤ 80 steps, ε = 1e-3, max distance 40) for every pixel; vectorised with an *active-pixel* compress to keep it fast. For hits, compute normal by central differences of the SDF (ε = 1e-3), world position, material id, object id, albedo. Output arrays: `normal_cam (H,W,3)`, `pos_world`, `obj_id (H,W)`, `albedo (H,W,3)`, `spec_k, shininess`, `hit mask`, `depth`. Budget: ≤ 6 s per image on a laptop CPU at 512×352. If slower, reduce steps adaptively and say so.

### 8.3 Lighting pass (`render.py: shade`)
Given G-buffer and a light setup, return linear RGB. Light setup: sun direction `l_world`, sun intensity `I_sun`, sky ambient `I_sky` (hemispheric: `I_sky·(0.6 + 0.4·n_y)` tinted `(0.85, 0.95, 1.1)`), optional second sun (multi-light scenes).
```
lambert = max(0, n·l)
shadow  = soft hard-ish shadow ray (40 steps, softness k=24) from p + 1e-3·n toward l (ground and objects receive cast shadows)
diff    = albedo · (I_sun · lambert · shadow + sky(n))
spec    = ks · I_sun · shadow · max(0, n·h)^shin · (lambert > 0)        # Blinn-Phong; h = normalize(l + v)
rgb_lin = diff + spec
```
Typical ranges: `I_sun ∈ [1.6, 3.0]`, `I_sky ∈ [0.25, 0.5]` (sun-dominant); overcast scenes (`I_sun/I_sky ∈ [0.1, 0.4]`); car paint: `ks ∈ [0.5, 1.0]`, `shin ∈ [60, 160]`; others `ks ≤ 0.15`. Sun elevation `∈ [15°, 70°]`, azimuth uniform in `[0, 360)` (front-lit, side-lit and back-lit all occur).

### 8.4 Camera pipeline (`render.py: camera`)
`rgb_lin → exposure scaling (auto: map the 90th-percentile luminance of non-sky pixels to ~0.7·U[0.8,1.2]) → tone curve (random from {sRGB OETF, gamma 1.8, gamma 2.6, S-curve (smoothstep-like), filmic (Reinhard-extended)}) → additive Gaussian noise σ ∈ [0.003, 0.02] → quantise to 8 bits → optional JPEG round-trip (quality ∈ {95, 85, 70}, chosen per image)`. Record the chosen tone curve, noise and JPEG quality in the sample metadata.

### 8.5 Normal-predictor simulation (`scenes.py: simulate_normals`)
Because the real predictors cannot be used for thousands of experiments, simulate them:
- `gt`: exact normals, `unc = 0` (reported as `unc_floor`).
- `noisy_gt(σ)`: rotate each GT normal by a spatially correlated random rotation: a smooth Gaussian vector field at 1/16 resolution (std `σ` degrees per axis, upsampled with a Gaussian blur) plus, with probability 0.15 per object, a *gross error patch* near the object boundary (tilt by ~40°) covering ~8% of the object. `unc` = absolute difference between two independent noisy copies (an "ensemble disagreement" proxy), floor 4°. Default σ = 8° (realistic mid-quality), sweeps over σ ∈ {0, 4, 8, 12, 16, 20}.

### 8.6 Samples and composites (`scenes.py`, `composite.py`)
`make_scene(seed, kind) -> Scene` where `kind ∈ {"normal", "overcast", "multi", "lowres", "damage"}`:
- `normal`: sun-dominant, one sun.
- `overcast`: `I_sun/I_sky ∈ [0.1, 0.4]` (weak directionality; the tool should abstain).
- `multi`: a second sun at ≥ 60° from the first with 40–80% of its intensity (the tool should return CONFLICT or INSUFFICIENT; this is the expected failure mode).
- `lowres`: render, then downsample ×0.5 with the car at 8–9 m (smaller regions).
- `damage`: `normal` plus a dent on the car body with the dent mask recorded.
`render_sample(scene, light_world, ...) -> Sample` returns `rgb (uint8), normals_gt, unc, labels (object ids → region ids), masks (car, dent, objects), light_cam (GT unit vector), meta`.
**Composites** (`composite.py`): `paste(scene, target_object | dent, light_world_B, ...)`: render the whole scene under `l_A`; render the target object (or dent region) under `l_B` using the **same** G-buffer (including its own attached shading, not its cast shadows); replace only the target mask pixels (feather the mask edge by 1.5 px Gaussian) before the camera pipeline so tone/noise/JPEG apply to the composite uniformly. Return the image, the mask and `delta_deg = angle(l_A, l_B)` (computed in camera space). Targets: `"car"`, `"distractor"`, `"dent"` (damage scenes: dent lit by `l_B` pasted on a body lit by `l_A`).
Pristine = `paste` with `l_B = l_A` is *not* used; pristine images are rendered directly.
Dataset builders: `build_dataset(split, n, kinds, out_dir)` saving `png + json` and `.npz` G-buffer arrays (normals/labels/unc) for fast reuse.

---

## 9. Calibration (`calibrate.py`) **[P0]**

Calibrate on a **separate calibration split** (seeds, section 14). Procedure:
1. **Posterior shape:** for each calibration `normal` scene (n = 120) compute bootstrap light samples for each *non-sky, valid* region (using `noisy_gt σ=8°`) once; evaluate coverage of the GT light by the 68% and 95% HPD sets for each `(h, T)` in `h ∈ {4, 6, 8, 10, 14, 18, 24}°`, `T ∈ {0.5, 0.75, 1.0, 1.5, 2.0}`; choose the pair minimising `|cov68 − 0.68| + |cov95 − 0.95|` among *reliable* regions only. Save `h, T` and the achieved coverages. Note: for a region lit by the global sun, the ground-truth direction is the scene's GT light (true for the synthetic sun + sky model approximately; the sky term biases it slightly; document).
2. **Alarm threshold (split conformal):** on `n_cal = 200` pristine scenes (mix: 70% normal, 30% damage scenes unedited), compute the image-level score `S_img` (7.11). For significance level `α ∈ {0.05, 0.10}`: `tau_img(α) = quantile of S_img at level ⌈(n+1)(1−α)⌉/n` (the conformal quantile). Scenes that return `INSUFFICIENT` are excluded from this set (and their rate is reported). Save `tau_img_05`, `tau_img_10`; the default operating point is `α = 0.05`. State in the docs: this controls the *false-alarm rate on pristine images of the calibration distribution* (exchangeability assumption); on other domains/cameras recalibrate (`tools/calibrate_on_folder.py` does this with a folder of the user's own unedited photos: it runs the pipeline and writes `calib_real.json`; the viewer/CLI can select `--calib calib_real.json`).
3. **Reliability floor** `w_min` fixed at 0.35 (document; optionally report the effect of {0.25, 0.35, 0.5} in E8).
4. Output `lightaudit/calib_default.json`: `{h, T, cov68, cov95, tau_img_05, tau_img_10, tau_ref_factor:1.0, w_min, n_cal, seeds, date}`. The pipeline loads it automatically; `--calib` overrides. **Never** use test-split data to set any threshold.

### 9.1 Arbiter (P1, `arbiter.py`)
`sklearn.ensemble.HistGradientBoostingClassifier` trained on the *arbiter-train* split composites (region-level rows: label = region is the pasted target; features = `s_k, angle_k, w, f_size, f_spread, f_sharp, f_dir, f_norm, rho_max, sharp_area, mean_unc, has_glint, n_valid, spread_deg, is_largest_region`). Image-level arbiter score = max over reliable regions of the predicted probability. Its alarm threshold is set by the **same conformal procedure** on pristine calibration scenes. Report both "rule" and "arbiter" in E8; permutation importance → figure. Default decision mode stays `rule` (explainable); `--mode arbiter` switches.

---

## 10. Attack module (`attacks.py`) **[P0 for T0, T1, T3a, T4; red-team evaluation of a defensive tool]**

Threat model: the forger wants a spliced region to pass the audit. Tiers:
- **T0 naive paste** — the composite from 8.6 (no extra processing).
- **T1 colour/brightness harmonisation** — Reinhard colour transfer in CIE-Lab of the pasted region to match the mean/std of its surrounding ring (the ring defined as in ROI mode). Expectation: does **not** fool rank-based shading (monotone brightness changes leave the rank order intact) — report this honestly as a result.
- **T3a physics re-shade** — the forger estimates the scene light `l̂` (the defender's own consensus rotated by a random error of `σ_att ∈ {0°, 5°, 10°, 20°, 40°}`; hence the "attacker accuracy" sweep) and re-shades the fake region: using the region's fitted `ĝ` (7.12 with the region's *own* estimated light `l_own` as reference),
  `Y'_i = ĝ(max(0, n_i·l̂))` and colours `rgb' = rgb · (Y' + 0.01)/(Y + 0.01)`. Normals used by the attacker: `attacker_normals ∈ {"same" (white-box, best case for the attacker), "independent" (a fresh noisy copy)}`. Highlights are **not** moved (multiplicative re-shading does not relocate specular glints). Boundary feathering 1.5 px.
- **T4 adaptive** — T3a plus (a) removal of saturated glint blobs in the region by inpainting them with the local median (`cv2.inpaint` or median fill), and (b) a 1-D search over the attacker's light direction error residual using the *defender's* score as the oracle: grid over `l'` in a 5° neighbourhood of `l̂` minimising the region's shortfall, under the fidelity constraint `mean |ΔY| ≤ 0.08` on the region. This is a white-box upper bound on attacker strength (without learned models).
- After each attack, re-run the audit (full pipeline on the edited image, **re-estimating the normals backend** — with `noisy_gt` the defender's normals are independent of the edit, which is the best case for the attacker; state this caveat in the docs and in the figure caption. If the real normal backend is available, E10 re-predicts normals from the edited image).
- Metrics: detection rate (TPR) at the calibrated `tau_img` and at fixed FPR 5%, top-1 localisation, fidelity (mean `|ΔY|` and `1−SSIM` inside the region), with and without the glint/contour cues (shows "defence recovery").
- **Minimum detectable inconsistency (MDI):** the smallest `δ` (discrepancy between the pasted region's light and the scene light) at which TPR@5%FPR ≥ 50% — reported per cue set (C1 only, C1+C2, C1+C2+C3, fused) — the headline security result.

The viewer's attack lab shows precomputed attack variants for the demo bundles (section 12.7).

---

## 11. Bundle format (`bundle.py`) — the contract between backend and viewer

A bundle is a folder `bundles/<name>/` plus an entry in `bundles/index.json` (`[{"name","title","description","verdict","thumb"}]`).
```
manifest.json                 # all scalars/metadata (schema below)
image.png                     # the audited image (RGB, original resolution up to 1024 long side)
normals.png                   # RGB-encoded normals (5.1)
unc.png                       # 8-bit: min(255, unc_deg / 45 · 255)
labels.png                    # 8-bit label map: 0 = unassigned, k = region id (k ≤ 63)
valid.png                     # 8-bit mask of pixels used by C1 (union over regions)
heat.png                      # 8-bit z-score heatmap (7.12.5), 0 outside regions
counterfactual.png            # counterfactual image (7.12.6)
landscapes.bin                # float32 [R_total, 64, 128]: A_k maps (7.11), R_total = regions + pseudo-regions, order = manifest.regions
consensus.bin                 # float32 [64,128]: F_R normalised map (exp(F/Σw), max=1)
attacks/<variant>/{image.png, manifest.json, landscapes.bin, heat.png, labels.png}   # optional
grid.json                     # {"NA":128,"NE":64}
```
`manifest.json` schema (all angles in degrees unless noted):
```json
{
  "version": 1, "name": "...", "title": "...", "description": "...",
  "image": {"w": 512, "h": 352, "fov_deg": 60.0, "source": "synthetic|real"},
  "ground_truth": {"light_cam": [x,y,z], "edited_region_ids": [3], "delta_deg": 110.0},   // synthetic only, else null
  "normals_backend": "noisy_gt(8)|dsine+stablenormal|...", "regions_backend": "gt|sam|slic|manual",
  "calibration": {"h": 10, "T": 1.0, "tau_img": 2.0, "tau_ref": 2.0, "w_min": 0.35, "alpha": 0.05, "source": "calib_default.json"},
  "regions": [{
    "id": 1, "name": "car body", "kind": "region|pseudo", "excluded": false,
    "area_px": 12345, "bbox": [x0,y0,x1,y1], "color": "#4c78a8",
    "n_valid": 1800, "spread_deg": 31.2, "rho_max": 0.71, "sharp_area": 0.08, "mean_unc": 9.1,
    "weight": 0.62, "reliable": true, "reason": null,
    "cues": ["shading","glint"], "center": [x,y,z], "r68_deg": 12.0, "r95_deg": 25.0,
    "g_lut": [33 floats], "sigma": 0.021, "slope": 0.7, "landscape_index": 0
  }],
  "fusion": {"verdict": "SUSPICIOUS", "S_img": 4.1, "top_region": 3, "consensus": {"dir": [x,y,z], "r68_deg": 9, "r95_deg": 19},
             "per_region": [{"id":1,"shortfall":0.2,"angle_deg":4.0,"flagged":false}, ...], "text": "…"},
  "baseline_ls": {"present": false},                    // P1: same structure for the LS baseline landscapes (landscapes_ls.bin)
  "attacks": [{"variant":"T3a_exact","title":"…","verdict":"CONSISTENT","S_img":0.9,"fidelity":{"mean_abs_dY":0.05,"ssim_loss":0.02}}],
  "backends_log": ["…"], "created": "ISO-8601"
}
```
Binary arrays are little-endian float32, C-order. The viewer must tolerate missing optional files.

---

## 12. The viewer (`viewer/`) — the interactive CG showpiece **[P0]**

Static web app. `index.html?bundle=<name>`. If no `bundle` param, show a gallery from `bundles/index.json` (cards with thumbnail, title, verdict chip). Serve with `python -m http.server` from the project root **or** the FastAPI server. Vanilla ES modules + Three.js + WebGL2. Dark UI with an accessible light theme toggle; colour tokens in CSS variables; works at 1280×720 and above; no horizontal scroll at 1024 px.

### 12.1 Layout (desktop)
```
┌──────────────────────────────────────────────────────────────────────────────────────┐
│ LightAudit · <title>                         [Gallery] [Explain] [Attack lab] [Help]│
├───────────────────────────────┬──────────────────────────────────────────────────────┤
│  IMAGE VIEW (WebGL2 canvas)   │  LIGHT DOME (Three.js)                               │
│  mode tabs: Observed | Regions│   photo billboard at the centre, full sphere shell,  │
│  | Relit | Counterfactual |   │   per-region cones, consensus marker, your light     │
│  Residual | Normals           │   [region landscape ▼ | consensus | none] [cones ☐]  │
│  light-direction readout      │                                                      │
├───────────────────────────────┴──────────────┬───────────────────────────────────────┤
│ VERDICT banner (colour + text) + live S_img  │ REGION TABLE: ☑ use | name | weight | │
│ Why (rule-based text)                         │ shortfall bar | angle | cues | flag   │
└──────────────────────────────────────────────┴───────────────────────────────────────┘
```

### 12.2 Image view (relight renderer) — `relight.js` + GLSL (WebGL2, `#version 300 es`)
Textures: `image`, `normals`, `labels` (NEAREST), `unc`, `heat`, `counterfactual`, plus a small float texture `regionParams` (RGBA32F, width = 40 regions × rows) holding per region `g_lut` (33 floats packed across 9 texels), `sigma`, `slope`, `weight` (use a data texture or a uniform array ≤ 64 regions; pick the one that works on WebGL2 contexts).
Uniforms: `uMode`, `uLight` (vec3, camera space, the **user light**), `uRef` (vec3 = consensus `l*`), `uSpecK`, `uShin`, `uShowOutline`, `uSelected` (int), `uHeatGain`.
Modes:
1. **Observed** — the photo.
2. **Regions** — label colours (alpha 0.45) over the photo, selected region outlined, excluded regions hatched.
3. **Relit @ your light** — per pixel in a region: `Y_ref = ĝ_k(max(0, n·uRef))`, `Y_new = ĝ_k(max(0, n·uLight))`, `rgb' = rgb · (Y_new + 0.01)/(Y_ref + 0.01)`; plus an optional Blinn-Phong highlight (`uSpecK`, `uShin`, with view vector from the pinhole model) toggle "glossy". Add a second selector to choose Blinn-Phong or GGX for the highlight (GGX: D = α²/(π((n·h)²(α²−1)+1)²), Smith G, Schlick F; document in METHOD.md).
4. **Counterfactual @ consensus** — the exported counterfactual image (or recomputed the same way in-shader).
5. **Residual** — `z = |Y − ĝ_k(max(0, n·uLight))| / sqrt(σ_k² + (slope_k·u)²)`, shown with an inferno colour ramp and `uHeatGain`; updates **live as the user drags the light** (with `uLight` = consensus the residual equals the exported heat map; assert this in a test or a debug overlay).
6. **Normals** — the normal map as RGB.
A split-view slider (Observed | selected mode) is a P1 nicety. Clicking a pixel selects its region (also updates the dome and the table). Hover shows a tooltip with the region name and its shortfall.

### 12.3 Light dome — `dome.js` (Three.js)
- Scene: a unit sphere shell (radius 1) rendered with a custom `ShaderMaterial`; a textured quad (the photo, aspect-correct, width 0.8) at the origin facing `+z` (the viewer camera starts at `(0.8, 0.5, 2.2)` looking at the origin with OrbitControls); a ground disc at `y = 0` (translucent), axis arrows (x red, y green, z blue) with labels "right", "up", "toward viewer", and a small compass of azimuth ticks at the equator.
- **Landscape shader:** the shell fragment shader converts the fragment direction to the EQ-grid UV (`az = atan(x, z)`, `lat = asin(y)`) and samples the selected `landscapes.bin` slice (uploaded as an R32F texture, LINEAR filtering, wrap in azimuth) and colours it (viridis-like ramp; opacity ∝ value; pole-safe sampling). Modes: *selected region*, *consensus*, *none*, and *all regions overlay* (additive, per-region colour at low alpha).
- **Cones:** for each region draw the 68% (solid ring) and 95% (dashed ring) circles of angular radius `r68/r95` around `center` on the sphere (computed on the CPU from the manifest as great-circle circles; line width via `Line2` or thin tubes), a small arrow/dot at `center` coloured with the region colour; the consensus drawn as a white ring plus a yellow "sun" sprite; flagged regions get a red pulsing outline (CSS/uniform, not distracting).
- **Your light:** a draggable orange handle on the sphere (raycast onto the sphere; also keyboard arrows ±2°), numerical readout (az/el), a "Snap to consensus" button and "Snap to selected region" button.
- **Hemisphere cue:** the lower half (y<0) is drawn with lower opacity plus the label "below the horizon".
- Selecting a region in the table/image highlights its cone and switches the shell to its landscape.
- 60 fps with up to 24 regions.

### 12.4 Live fusion and verdict — `fusion.js`
Port of 7.11 operating on the `[64×128]` landscapes in the browser. Recomputed when the user toggles `use`/`exclude` for regions, changes the cue weights (advanced panel: sliders for `w_glint`, `w_contour`, alert level `tau`, `w_min`), or drags the light. The "your light" does not change the verdict by itself; instead the **agreement readout** shows, for the dragged light, each region's `A_k(l_user)` as a bar chart ("how much each region likes this light") and a "what-if verdict": the verdict you would get if the consensus were forced to `l_user` (shortfall of each region against `l_user`, flag if > `tau`). The banner shows both: *Audit verdict* (data-driven) and *What-if at your light*.
Parity with Python: `viewer/tests/parity.test.mjs` runs under Node (if available) against `tests/vectors/fusion_vectors.json` emitted by Python (random landscapes, weights, expected `l*`, `s_k`, verdict) and asserts equality (angles within 1e-3°, shortfalls within 1e-4).

### 12.5 Region table
Columns: checkbox `use`; colour chip; name; weight bar; shortfall bar with the alert line; angle to consensus; cue badges (`S` shading, `G` glint, `C` contour, `P` shadow pairs); status chip (`agrees`, `FLAGGED`, `unreliable: <reason>`, `excluded`). Sortable. Clicking a row selects the region.

### 12.6 Explain stepper — `explain.js` **[P0]**
A guided overlay "How this verdict was made" with 7 steps. Each step shows an image/illustration and 2–3 sentences:
1. Photo → 2. Regions (labels) → 3. Surface directions (normals) with the uncertainty map toggle → 4. Usable pixels (valid.png) → 5. Per-region light maps (dome with one region's landscape; a small side plot of Y vs `n·l` showing the monotone curve `ĝ_k`) → 6. Do the maps overlap? (dome with all cones + consensus; the shortfall bars) → 7. Where does it not fit? (heat map) and the verdict. Next/Previous buttons, keyboard arrows. Include the static conceptual SVGs from `docs/figures` (generated by `figures/make_illustrations.py`) for the tone-curve invariance and the cue geometry (glint reflection, contour normals, shadow lines).

### 12.7 Attack lab — `attack.js` **[P0 static; P2 live]**
Tab "Attack lab": the user picks a flagged region (default top region) and a **variant** from the bundle's `attacks[]` (`T1 colour transfer`, `T3a re-shade (exact light)`, `T3a re-shade (±10° error)`, `T3a (±20°)`, `T4 adaptive`). The view shows *Original* vs *Attacked* side-by-side with a swipe slider, the attacked region's landscape on the dome next to the original cone (so the user sees the cone **move** onto the consensus), the new verdict chip, `S_img` before→after, fidelity numbers (mean |ΔY|, SSIM loss), and a one-line interpretation produced by rules (e.g., "Re-shading moved this region's estimate from 108° to 9° off the consensus; shading-only check is fooled, but the specular highlight cue still disagrees by 71° → still flagged"). A small table lists the *detection by tier* summary from `data/results/attack_summary.json` (generated by the evaluation). Live mode (P2): if served by FastAPI, a button "Re-run attack" posts to `/api/attack`.

### 12.8 Help panel
Plain-language "How to read this" with the azimuth/elevation diagram, the legend (cones = 68% solid / 95% dashed), the triage meaning, the limitations text of section 21 verbatim, and keyboard shortcuts: `1–6` image modes, `R` toggle regions, `H` heatmap, `C` cones, `E` explain, `A` attack lab, `Esc` close overlays, arrows move your light.

### 12.9 Performance and robustness
- Handles bundles with up to 40 regions. Debounce fusion at 30 ms during dragging. No console errors. Graceful messages for missing files (e.g., no attacks).
- Resize-safe canvases; `devicePixelRatio` capped at 2.
- Provide `viewer/tests/smoke.md` with the manual checklist (drag light, toggle region, open each tab) and also a Playwright/pytest-free automated smoke test if Node is available (optional).

---

## 13. CLI, server, bundles

### 13.1 CLI (`python -m lightaudit.cli <command>`)
- `setup-check` — prints available backends.
- `synth --split {cal,arb,test,demo} --n N --kinds normal,overcast,multi,lowres,damage --out data/synth/<split>` — builds samples.
- `calibrate [--n-cal 200]` — writes `lightaudit/calib_default.json` and `docs/figures/` calibration plot data to `data/results/calibration.json`.
- `train-arbiter` (P1).
- `audit --image PATH [--roi MASK] [--regions sam|slic|manual:PATH] [--normals dsine,stablenormal|depth_anything] [--fov 60] [--calib PATH] [--name NAME] [--attacks]` — full pipeline → bundle (+ `--html` for the evidence report).
- `audit-synth --sample PATH --normals noisy_gt:8 --name NAME [--attacks]` — audits a synthetic sample with GT regions.
- `attack --bundle NAME --region ID --variants T1,T3a,T4 [--sigma-att 10]`.
- `eval --suite {quick,full} [--exp E1,E3,...]` — runs experiments, writes `data/results/*.json|csv`.
- `figures` — creates all figures/tables from `data/results`.
- `demo-bundles` — builds the demo bundles of 13.3 (deterministic seeds) and `bundles/index.json`.
- `serve [--port 8000]` — FastAPI app serving the viewer, `bundles/`, `docs/`, plus the API.
- `report` — fills the report from results (section 16).
`run_all.ps1` runs: setup-check → tests → `synth` (cal, arb, test, demo) → `calibrate` → `train-arbiter` → `demo-bundles` → `eval --suite full` → `figures` → `report`; with `-Quick` using `--suite quick` (small N; completes in ≤ 15 minutes on the laptop).

### 13.2 Server (`server.py`, FastAPI) **[P1]**
- `GET /` → viewer, static mounts `/viewer`, `/bundles`, `/docs`, `/results` (read-only).
- `POST /api/audit` (multipart: `image`, optional `roi`, `normals`, `regions`, `fov`) → `{job_id}`; run in a background thread; `GET /api/jobs/{id}` → `{status: queued|running|done|error, progress, bundle, log}`; completed bundles go to `bundles/user_<timestamp>/` and are added to `index.json`.
- `POST /api/attack` (P2).
- Limit upload to 15 MB; downscale to long side 1024; sanitise filenames; bind to `127.0.0.1` by default. In the viewer gallery add an "Upload a photo" card (disabled with a tooltip if not served by FastAPI).

### 13.3 Demo bundles (all P0; synthetic ones use GT regions, `noisy_gt(8)`)
Built with fixed seeds (section 14):
- `demo_consistent` — a clean sunny scene; `CONSISTENT`.
- `demo_splice_car` — the car pasted lit from ≥ 100° away; `SUSPICIOUS` (car flagged) + attack variants T1, T3a(0°/10°/20°), T4.
- `demo_damage_genuine` — a dent lit consistently (panel mode with ROI + ring); `CONSISTENT`.
- `demo_damage_fake` — the dent pasted from a different light (panel mode); expected `SUSPICIOUS` (if the arbiter/rule detects it; whatever the real result is must be reported as is) + attack variants.
- `demo_multilight` — two suns; expected `CONFLICT`/`INSUFFICIENT`.
- `demo_overcast` — expected `INSUFFICIENT`.
- `real_*` (P1) — for each image placed in `data/real/` (jpg/png): audit with the best available backends (SAM or SLIC regions + the normal ensemble), flag in the manifest that GT is unknown, and, for each, a **spliced twin** created by `tools/make_real_splice.py` (paste a region from another photo into this photo using a user mask or SAM mask; with and without T1/T3a). If `data/real/` is empty, skip and print a clear message (and make the README tell the user to drop 10–20 outdoor photos of parked cars/street scenes there).
The pass/fail of the expected verdicts is **not** a requirement (the system is what it is); the requirement is that each demo is produced, loads, and is described truthfully in `docs/DEMO_SCRIPT.md` using the actual verdicts. If a demo scene does not behave as intended, you may change its seed to find a representative (not cherry-picked beyond reason) example and state in the log how many seeds were tried; also include one failure example (`demo_failure_*`: e.g. a spliced scene that passes, or a clean scene that is flagged) with an honest caption.

---

## 14. Evaluation suite (`eval/`) **[P0]** — every experiment writes JSON/CSV to `data/results/` and is plotted by `make_figures.py`

### 14.1 Splits and seeds
| split | seeds | contents |
|---|---|---|
| cal | 1000–1199 | pristine scenes for calibration |
| arb | 2000–2199 | composites for the arbiter |
| test | 3000–3299 | everything reported (150 scenes for composite experiments, 150 for pristine/robustness) |
| demo | 4000–4099 | demo bundles |
`--suite quick` = 10% of the counts (smoke-quality plots); `full` = the counts above. Use `multiprocessing.Pool(os.cpu_count()−1)` with scene-level tasks and **cache** G-buffers (`.npz`) and per-region posteriors by `(scene seed, region id, light id, σ)`; in composite experiments only the pasted region's posterior is recomputed per `δ` (all other regions reuse the pristine posteriors; this is exact because regions are GT objects and their pixels are unchanged). State this in the code docs and in `METHOD.md`.

### 14.2 Experiments
- **E1 — cue accuracy under camera non-linearity (H1).** Single-region light estimation on `normal` scenes (cars + distractors), exact normals, tone curves {sRGB, gamma 1.8, 2.6, S-curve, filmic}: median/mean angular error of **C1 rank** vs **LS baseline** (7.13). Output: boxplots per tone curve. Expected: rank is stable across curves; LS degrades on the nonlinear ones (report whatever occurs).
- **E2 — effect of normal quality (H2).** `noisy_gt σ ∈ {0,4,8,12,16,20}`: angular error and `r68` vs σ; and error vs region size and vs `spread_deg` (scatter + binned medians); correlation between mean `unc` and error.
- **E3 — calibration (H3).** On the test split: coverage of 68%/95% credible sets before and after calibration, reliability diagram (nominal vs empirical for levels 0.1…0.95), sharpness (mean `r68`).
- **E4 — minimum detectable inconsistency (H4, headline).** On test `normal` scenes, composites with the **car** pasted at `δ ∈ {0, 10, 20, 30, 45, 60, 90, 135, 180}°` (choose `l_B` at the given angle to `l_A` with random azimuth around `l_A`; for each scene use the same direction pair set), `noisy_gt σ=8`. Detection by cue set {C1, C1+C2, C1+C2+C3, fused (all P0/P1 cues present)} and by LS-baseline. Output: TPR@FPR=5% (threshold from the pristine **test** images' score distribution, and also at the calibrated `tau_img`) vs `δ`; MDI (smallest δ with TPR ≥ 0.5); also for `distractor` and `dent` targets.
- **E5 — detection ROC.** ROC and AUC pooled over `δ ≥ 30°` vs pristine, per cue set + LS baseline; localisation top-1 accuracy (is `k_top` the pasted region?).
- **E6 — abstention and hard conditions (H4/limits).** For `overcast`, `multi`, `lowres` scenes (pristine and spliced): fraction of INSUFFICIENT / CONFLICT / decided, accuracy among the decided, risk–coverage curve (sweep `w_min` and `tau`), false-alarm rate on pristine decided images. Include a table "Verdict distribution by condition".
- **E7 — robustness (IP).** Apply to test images (pristine and `δ=90°` composites): JPEG quality {95, 75, 50, 30}, resize ×{1.0, 0.75, 0.5, 0.35} (resample back not required; the pipeline handles the smaller image), Gaussian noise σ {0, 0.01, 0.03, 0.06}, extra tone curve changes (gamma 1.5/2.8, contrast ×1.5). Output: TPR@calibrated τ and FPR vs perturbation. For each perturbation the calibrated threshold is **not** re-fit (state it).
- **E8 — ablations.** (a) cue subsets; (b) rank vs LS; (c) KDE calibration on/off; (d) `w_min ∈ {0.25, 0.35, 0.5}`; (e) rule vs arbiter (P1) incl. permutation importance; (f) region backend `gt` vs `slic` on 30 scenes (shows the effect of imperfect segmentation); (g) with/without leave-one-out (single global consensus instead). Output: a single ablation table (AUC, TPR@5%FPR at δ=90°, MDI, abstention rate).
- **E9 — attacks (red team).** On composites with `δ = 90°`–`135°` (car, distractor and dent targets): tiers T0, T1, T3a with `σ_att ∈ {0, 5, 10, 20, 40}` and `attacker_normals ∈ {same, independent}`, T4. Metrics: TPR at calibrated τ and at 5% FPR **before/after** attack; for T3a/T4 also the version with only C1 ("shading-only detector") vs fused ("with glint + contour cues") to measure **defence recovery**; fidelity metrics; the MDI relation (success when the attacker's light error < the detector's MDI). Output: grouped bar chart (detection by tier) + MDI-vs-attacker-error plot + table. Write `data/results/attack_summary.json` (also consumed by the viewer).
- **E10 — real normal predictor in the loop (P1, only if a backend is available).** On 30 test scenes (pristine + 30 composites δ=90°), run `predict_normals` on the rendered **image** instead of `noisy_gt`: report normal angular error vs GT (this is a *sim-to-real* measurement), light-estimation error, detection, and the T3a attack **with normals re-predicted from the attacked image** (the circularity effect: does re-shading shift the predicted normals?). If no backend is available, write a results file stating "not run: no backend" and make the figure script skip it gracefully.
- **E11 — applicability on real photos (P2).** `tools/applicability_scan.py <folder>`: run the pipeline on every image (SAM/SLIC + normals), report the fraction with ≥ 3 reliable regions, the verdict distribution and the dominant abstention reasons; table + bar chart.
All reported numbers carry the sample size; where a point estimate is shown, add a bootstrap 95% CI (1000 resamples over scenes) in the tables.

### 14.3 Figures and tables (generated, saved to `docs/figures/*.png` at 200 dpi and `.svg` where easy)
- **F1** E1 boxplots (rank vs LS across tone curves).
- **F2** E2 error vs normal noise; error vs region size/spread.
- **F3** E3 reliability diagram + coverage table.
- **F4** E4 TPR vs discrepancy angle (per cue set, plus LS) with MDI marked.
- **F5** E5 ROC curves.
- **F6** E6 verdict distribution by condition + risk–coverage.
- **F7** E7 robustness curves (3 small multiples).
- **F8** E9 attack results (grouped bars; defence recovery; MDI-vs-attacker error).
- **F9** E8 ablation table as an image + permutation importance bars (P1).
- **T1–T6** the corresponding CSV and Markdown tables in `data/results/tables/`.
Style: consistent colour palette, readable fonts (≥ 10 pt at figure scale), titles stating the takeaway, axis labels with units, captions that include sample sizes and the caveat "synthetic scenes with simulated normal predictors unless stated".

### 14.4 Qualitative gallery (`make_figures.py`)
A 6-row figure (one row per demo bundle) with columns: image | regions | normals | light map (equirectangular plot with each region's 68/95% sets, consensus, GT light as a star) | residual heatmap | verdict text. File `docs/figures/gallery.png`. Also `docs/figures/lightmap_<bundle>.png` for each demo bundle (used in the HTML evidence report).

---

## 15. Illustrations (`figures/make_illustrations.py`) **[P0]** — conceptual diagrams for the docs, the report, the slides and the viewer's explain mode

Produce clean PNG + SVG (matplotlib or hand-built SVG) in `docs/figures/`:
- **I1 pipeline.svg** — the block diagram of section 7 (photo → regions → normals → cues C1–C4 → region landscapes → fusion + leave-one-out → calibrated verdict → viewer / attack), with the ML/CV/IP/CG tags colour-coded.
- **I2 rank_invariance.png** — three panels: the same region under three different tone curves: (a) intensity vs `n·l` curves, (b) after ranking they coincide, (c) LS fit failing vs rank estimate succeeding.
- **I3 cue_geometry.png** — three schematics: glint (view, normal, light mirror geometry), contour (normals in the image plane at the silhouette), shadow lines converging at the light's vanishing point.
- **I4 light_dome.png** — a 3D-style schematic of the dome: photo at the centre, region cones, consensus, the outlier cone far away (consistent vs spliced side by side).
- **I5 cones_vs_posterior.png** — why a cone is an approximation of the HPD set (a real anisotropic landscape with its 68/95% sets and the inscribed cone).
- **I6 shortfall_diagram.png** — leave-one-out consensus and shortfall explained with a toy example.
- **I7 conformal.png** — the pristine score histogram, the conformal quantile `tau`, and the false-alarm guarantee wording.
- **I8 attack_ladder.png** — the tiers T0, T1, T3a, T4 and what each one can and cannot move (shading, glints, silhouettes).
- **I9 triage.png** — the four verdicts and the recommended actions (insurance workflow).
All illustrations are generated by code (no stock images) and are referenced from `docs/METHOD.md`, the report, the slides outline and the viewer's explain mode.

---

## 16. Documentation, report, slides **[P0]**

- `README.md`: what it is, 5-line quickstart (`setup.ps1` → `run_all.ps1 -Quick` → `python -m lightaudit.cli serve` → open `http://127.0.0.1:8000`), the feature list, folder map, how to audit your own photo (CLI and upload), how to recalibrate on your own photos, the limitations text (section 21), credits/citations.
- `docs/METHOD.md`: the math of sections 5–10 with the illustrations (I1–I9), the equations, defaults, and the "why" for each design choice, including the honest caveats (circularity of normal networks; glossy paint; synthetic-first evaluation; conformal exchangeability).
- `docs/LIMITATIONS.md`: expanded version of section 21 plus the table of photo types (usable / partly / unusable) from the project brief.
- `docs/LITERATURE.md`: the table below, with links (mark `(recalled)` where the link is not given and tell the reader to verify):
  - Johnson & Farid 2005/2007 (contour-based 2D light, SH environment) (recalled); Kee, O'Brien, Farid 2013 (shadows) https://farid.berkeley.edu/downloads/publications/tog13/tog13.pdf; Kee, O'Brien, Farid 2014 (shading + shadows) https://farid.berkeley.edu/downloads/publications/tog14.pdf
  - Lalonde, Efros, Narasimhan 2009/2012 (multi-cue sun estimation) https://ri.cmu.edu/publications/estimating-natural-illumination-from-a-single-outdoor-image
  - Sarkar et al., CVPR 2024, "Shadows Don't Lie and Lines Can't Bend" https://arxiv.org/abs/2311.17138
  - Farid 2022, lighting in DALL·E 2 images https://arxiv.org/abs/2207.13744
  - Light2Lie, NDSS 2026 https://www.ndss-symposium.org/ndss-paper/light2lie-detecting-deepfake-images-using-physical-reflectance-laws
  - TruFor https://arxiv.org/abs/2212.10957 (baseline in "Later")
  - FakeShield https://arxiv.org/abs/2410.02761 (explainable forensics with MLLMs)
  - Fang & Stamm, anti-forensic GAN attack on splicing detectors https://arxiv.org/abs/2211.12314; Pasquini et al. 2024 mimicry attacks (recalled)
  - DiffusionRenderer https://arxiv.org/abs/2501.18590; Neural Gaffer https://arxiv.org/abs/2406.07520; IC-Light (recalled) — relighting tools (attacks in "Later")
  - SGDiffusion https://arxiv.org/abs/2403.15234; ObjectDrop https://arxiv.org/abs/2403.18818 — shadow-generating insertion (attacks in "Later")
  - SOLID-Net https://arxiv.org/abs/2104.04160
  - DSINE (CVPR 2024), StableNormal https://arxiv.org/abs/2406.16864, Lotus-2 https://arxiv.org/abs/2512.01030 (normal estimators)
  - CarDD https://arxiv.org/abs/2211.00945 (dataset, "Later"/optional)
  - Han 1987, maximum rank correlation estimator (single-index models) (recalled); split-conformal prediction (Vovk; Lei et al. 2018) (recalled); Reinhard et al. 2001 colour transfer (recalled).
  A closing paragraph states the contribution precisely (section 1) and that a systematic literature review of attacks on *physics-based* detectors with modern relighting was not completed.
- `docs/DEMO_SCRIPT.md`: a 5-minute demo script (what to click, what to say, in order: gallery → consistent → splice (dome, cones, shortfall, heatmap, counterfactual, drag light) → explain stepper → attack lab (T1 fails, T3a with exact light fools shading, glint recovers, T4) → damage panel mode → abstention (overcast/multi) → failure example → limits). Use the **actual** verdicts and numbers of the built bundles (load them from the manifests when writing).
- `report/make_report.py` + `report/REPORT.md`: ~12–15 pages when rendered. Sections: Abstract; 1 Introduction & problem; 2 Related work; 3 Method (with I1–I9); 4 System (architecture, viewer with screenshots); 5 Experiments (data, E1–E10 with F1–F9 and tables, all numbers loaded from `data/results`); 6 Attack evaluation and discussion; 7 Limitations & ethics; 8 Conclusion; References; Appendix (hyperparameters, seeds, reproduction commands). Write the analysis paragraphs **after** reading the actual results; never describe an effect that the numbers do not show; if a hypothesis fails, say so. Include screenshots: capture them with a headless browser if available (Playwright/Chromium via `playwright`, optional install) — otherwise leave labelled placeholders `docs/figures/viewer_*.png` and list them in `BUILD_LOG.md` as "human to capture (instructions in DEMO_SCRIPT.md)".
- `report/SLIDES.md`: a 12-slide outline (title, problem, idea, pipeline I1, cues I2–I3, dome/viewer screenshots, calibration + abstention, attack ladder I8, results F4/F8, failure cases, limitations, conclusion) with speaker notes.

---

## 17. Tests (`pytest`) and acceptance criteria **[P0]**

Unit/integration tests (all must pass; keep the whole suite under ~3 minutes):
1. `test_grid.py` — EQ grid mapping round-trip, area weights sum to 1, dir↔cell consistent; writes `tests/vectors/grid_vectors.json`.
2. `test_rank.py` — `rank_landscape` recovers a known light (error < 5° median over 30 trials) on Lambertian caps under each of 4 monotone tone curves, with normal noise 8°; the zero-tie handling is correct (a region where half the pixels are in attached shadow); LS baseline fails measurably on at least one nonlinear curve (assert it is worse than rank by ≥ 5° median on the sigmoid/HDR curve — if this assertion is not true with your implementation, loosen it and log the finding honestly rather than faking it).
3. `test_synth.py` — GT consistency: re-rendering with the stored GT light reproduces the stored linear image; `light_cam` equals the world light rotated into camera space; masks are disjoint; the dent changes normals within the dent mask only; composite replaces only the target mask pixels; `delta_deg` is correct.
4. `test_posterior.py` — bootstrap posterior is deterministic with a seed; HPD areas monotone; `r68 < r95`; coverage on 40 synthetic regions within ±0.15 of nominal *after* calibration defaults.
5. `test_fusion.py` — hand-built landscapes (cones at known centres) give the expected consensus, shortfall, and the four verdicts; writes `tests/vectors/fusion_vectors.json` consumed by the JS parity test.
6. `test_pipeline.py` — end-to-end on 3 synthetic scenes: consistent → `CONSISTENT`; car pasted at 120° → `SUSPICIOUS` with `top_region == car` (allow retry over 3 seeds; the test asserts ≥ 2/3); overcast → `INSUFFICIENT` or `CONSISTENT` (not `SUSPICIOUS`) in ≥ 2/3.
7. `test_calibrate.py` — conformal quantile function property test (empirical FPR ≤ α + 0.03 on held-out pristine scores).
8. `test_attacks.py` — T3a with `σ_att = 0`, same normals reduces the C1 shortfall of the target region by ≥ 50% on average over 10 scenes; T1 changes the region's mean/std colour towards the ring; fidelity metrics computed.
9. `test_bundle.py` — a built bundle validates against the manifest schema (write a small validator), `landscapes.bin` has the expected size, PNG dimensions match.
10. `viewer/tests/parity.test.mjs` — JS fusion matches Python vectors (skipped with a printed notice if Node is not installed).
11. A convention test (7.4): a synthetic render passed through a fake backend that flips axes is corrected by `fix_convention`.

**Definition of Done (checklist to copy into `BUILD_LOG.md` with ✅/❌ and evidence):**
- [ ] `setup.ps1` and `run_all.ps1 -Quick` run end-to-end on a clean checkout without GPU, within ~15 minutes.
- [ ] All tests pass (list failures if any, with explanation).
- [ ] 6 demo bundles + 1 failure bundle exist and load in the viewer without console errors.
- [ ] Viewer: image modes 1–6, dome with landscape shader, cones, draggable light, live relit/residual updates, live fusion with region toggles, region table, explain stepper, attack lab with precomputed variants, help panel.
- [ ] Calibration file present and used; the coverage and false-alarm numbers printed in `BUILD_LOG.md`.
- [ ] E1–E9 (and E10 if possible) executed (`full` suite if time permits; otherwise `quick` — state which) and F1–F8 + tables generated.
- [ ] All illustrations I1–I9 generated.
- [ ] README, METHOD, LIMITATIONS, LITERATURE, DEMO_SCRIPT, REPORT, SLIDES written; every number in the report traceable to `data/results`.
- [ ] Section 21 text present in README, viewer Help, report.
- [ ] `BUILD_LOG.md` lists: decisions, deviations from this spec, known issues, what was not run, and the exact commands to reproduce.

---

## 18. Build order (follow this; verify at each milestone)

1. **M0 scaffold** — repo layout, `config.py`, `grid.py`, test vectors, `setup.ps1`.
2. **M1 synth engine** — SDF scenes, G-buffer, shading, camera pipeline, composites, dataset builder; view a contact sheet (save `docs/figures/synth_samples.png`).
3. **M2 core cues** — validity, C1 rank landscape, posterior (bootstrap/KDE/HPD), reliability; sanity script printing angular errors on 20 scenes.
4. **M3 fusion + calibration** — fusion/shortfall/verdict, explain text, calibrate; unit tests.
5. **M4 pipeline + bundle** — `pipeline.py`, `residual.py`, `bundle.py`, `audit-synth`, demo bundles (without attacks).
6. **M5 viewer** — grid.js, fusion.js (parity), relight.js, dome.js, ui; verify visually with a headless browser or manual run; fix.
7. **M6 attacks** — T0, T1, T3a, T4 + bundle `attacks/`; attack lab in the viewer.
8. **M7 extra cues** — glint (C2) then contour (C3) (these feed E4/E9); then LS baseline; arbiter.
9. **M8 evaluation** — E1–E9, figures, tables, illustrations.
10. **M9 real-photo path (P1)** — SAM/SLIC regions, normal ensemble + convention check, `audit` CLI, `make_real_splice`, server upload.
11. **M10 docs/report** — README, METHOD, LIMITATIONS, LITERATURE, DEMO_SCRIPT, REPORT, SLIDES, `BUILD_LOG.md`.
12. **M11 P2 items** — shadow pairs C4, live attack API, applicability scan (only after everything else passes).
If time/budget runs short, protect in this order: M0–M5 and M8's E1/E3/E4 → viewer (M5) → attacks (M6) → docs → the rest.

---

## 19. Pitfalls (read before coding)

- **Sign/axis conventions** (section 5) — write a tiny visual debug that draws the GT light direction on a synthetic sphere to confirm the camera-space vector; test world→camera conversion explicitly.
- **Rank ties:** saturated or flat regions produce ties; shading with `max(0, ·)` produces a big tie group at 0; do not let an arbitrary argsort order create fake structure.
- **Performance:** never compute a full `N × 8192` rank matrix inside the bootstrap loop; use the coarse+refine scheme. Keep arrays `float32`. Cache everything in experiments.
- **Wrap-around** in azimuth when refining and when computing HPD sets/cones near `az = ±π`.
- **Pole cells:** area weights and the dome shader must be pole-safe.
- **Mask erosion** can delete small regions; handle empty regions gracefully.
- **Circularity:** with `noisy_gt` normals do not claim anything about real predictors; say so in captions. E10 is the real-predictor measurement.
- **Dent geometry:** the dent must be visible after erosion; make it large enough (≥ 600 px) in the demo scenes.
- **Browser:** WebGL2 float textures need `EXT_color_buffer_float` only for render targets, not for sampling R32F with NEAREST/LINEAR — use `OES_texture_float_linear` check; fall back to NEAREST if absent. Avoid reading back large textures every frame.
- **Windows:** long paths, backslashes, multiprocessing spawn, PowerShell execution policy (document `Set-ExecutionPolicy -Scope Process Bypass`).
- **Reporting:** do not cherry-pick demo scenes silently; log seed counts.

---

## 20. Config defaults (`config.py`)

```
grid: NA=128, NE=64, coarse_step=4, refine_halfwidth=6
image: max_side=1024, fov_deg=60
validity: sat_hi=0.97, dark_lo=0.04, nz_min=0.05, unc_max=35, erode_px_frac=0.008, Nmax=2500, Nmin=150
regions: min_region_px=800, max_region_frac=0.7, ring_px=20
normals: unc_floor=4, single_backend_unc=12
posterior: B=30, block_px=24, boot_min_px=600, draw_sigma_floor=4, kde_h=10 (calibrated), T=1.0 (calibrated), eps=1e-3
glint: blob_min=4, blob_max_frac=0.02, contrast_min=0.15, sigma_floor=8, w_glint=0.5
contour: band_px=(3,6), nz_max=0.5, min_px=80, w_contour=0.5
shadow_pairs: sigma_px=3, w_shadow=0.7
reliability: w_min=0.35; factors as in 7.10
verdict: tau_img=2.0 (calibrated), tau_ref=tau_img, min_reliable=3, broad_consensus_frac=0.35
calibration: n_cal=200, alpha=0.05, h_grid=[4,6,8,10,14,18,24], T_grid=[0.5,0.75,1,1.5,2]
synth: W=512, H=352, sigma_normals=8
attacks: sigma_att=[0,5,10,20,40], fidelity_max_dY=0.08
eval: seeds per 14.1; n_composite=150, n_pristine=150; bootstrap_CI=1000
```

---

## 21. Limitations text (include verbatim in README, viewer Help and report)

> **What LightAudit can and cannot do.** LightAudit checks whether the lighting of different parts of a photo is physically consistent. It does **not** detect AI-generated images in general: a generator that produces the whole picture in one pass usually gives every object the same plausible light. A careful forger who re-lights an edited region to match the scene can pass the shading check (the attack lab measures exactly how much extra work that takes). Real photos can be flagged wrongly when they contain several lights, strong reflections, or bad surface-direction estimates, and many real photos (overcast, indoor, heavily filtered, tiny or flat objects) carry too little lighting evidence, in which case LightAudit says "insufficient evidence". Surface directions come from pretrained neural networks and are learned guesses, not measurements. The alert threshold controls the false-alarm rate only for photos like those used for calibration. **A flag means "send for human review", never "this is fraud".** Results on synthetic scenes do not automatically transfer to real photos; real-photo results are qualitative unless stated.

---

## 22. Inputs the human provides (the agent should not wait for these)

- Optional: 10–20 of their own outdoor photos (parked cars / street scenes, sunny, different times of day) in `data/real/`, plus a few unedited photos for `tools/calibrate_on_folder.py`. The product must be complete and demo-able **without** them.
- Optional: install of `requirements-models.txt` for the real-photo path.
- The human will run `run_all.ps1`, open the viewer, rehearse `docs/DEMO_SCRIPT.md`, and read `report/REPORT.md`.

Finish by writing `BUILD_LOG.md` (decisions, deviations, results summary with the headline numbers, known issues, reproduction commands, and the list of anything the human still has to do: screenshots, adding real photos, optional model install).
