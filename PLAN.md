# LightAudit, research-first redesign (supersedes the earlier PLAN.md)

## Context

The first plan kept the original recipe: segment, predict normals, fit shading, draw cones. This pass re-derives the project from the problem statement and the literature, treating the original recipe as one candidate among several. The folder is still empty, so there is nothing to reuse and no code exploration was needed. Literature claims below come from quick web searches, which returned abstracts, not full papers. Items marked (recalled) come from memory and must be verified before they go in the report.

---

## 1. What the problem actually is

"Explainable lighting-consistency auditing of edited images, with relighting-attack evaluation" contains four separable questions:

1. **Consistency test.** Given regions of one photo, is there a single physically plausible illumination that explains all of them?
2. **Evidence.** Can the test's output be inspected and checked by a human, and is the explanation faithful to what the system computed?
3. **Calibration.** How often does it falsely accuse a pristine photo, and does it know when it cannot tell?
4. **Adversary.** What does a forger need to do to pass, and does passing leave traces another detector sees?

The original brief answered (1) with estimate-then-compare and left (3) and (4) mostly to evaluation. Most of the research value is in (3) and (4), and (1) can be made much more robust.

**Who the forger is today.** Modern edits come from generative editors (inpainting, object insertion with generated shadows and reflections: ObjectDrop, SGDiffusion) and relighting models (IC-Light, Neural Gaffer, DiffusionRenderer). These mostly produce lighting-consistent output. Lighting forensics therefore catches mainly cut-and-paste or template reuse across photos with different light, plus weakly conditioned AI edits. Any honest evaluation has to say this up front.

---

## 2. Literature map and what to adopt

| Route | Key work | Adopt | Avoid or limit |
|---|---|---|---|
| Classical lighting and shadow forensics | Johnson and Farid 2005, 2007 (contour-based 2D light and SH environment) (recalled). Kee, O'Brien, Farid 2013 (shadow geometry constraints with tolerance) and 2014 (shading plus shadows) ([2013 PDF](https://farid.berkeley.edu/downloads/publications/tog13/tog13.pdf), [2014 PDF](https://farid.berkeley.edu/downloads/publications/tog14.pdf)) | Constraint view: each observation restricts the light to a region of the sphere, and the test is "is the intersection empty?". Network-free contour cue. Shadow cue | Manual correspondences. Small test sets. Hard thresholds |
| Illuminant-color and learned illumination maps | Carvalho and Riess lines (recalled). Zhu 2021 dual-stream illumination-map network. Mazumdar thesis, IIT Guwahati ([thesis](https://gyan.iitg.ac.in/items/6b3f1cb0-74ba-4c31-bb85-7fddbde7d2ad/full)) | Illuminant colour as an extra cue and as a baseline | Colour is not direction. Trained on narrow data, opaque |
| Generic forensic networks | TruFor, CVPR 2023, anomaly plus confidence map ([arXiv](https://arxiv.org/pdf/2212.10957)). Noiseprint, EXIF self-consistency, Forensic Similarity (recalled) | Run TruFor as the **opaque baseline and complementary detector**. Use its confidence-map idea for abstention | Not explainable. Degrades on re-compressed images (per its own robustness tests) |
| Probabilistic outdoor lighting from many weak cues | Lalonde, Efros, Narasimhan, ICCV 2009 / IJCV 2012: probability over sun position by fusing sky, vertical-surface, ground and convex-object cues ([CMU RI](https://ri.cmu.edu/publications/estimating-natural-illumination-from-a-single-outdoor-image)) | Direct precedent for **multi-cue fusion as a distribution over the sun direction** | Their data-driven prior needs 6M photos |
| Learned spatially-varying outdoor lighting | SOLID-Net, CVPR 2021 ([arXiv](https://arxiv.org/pdf/2104.04160)). Hold-Geoffroy sky models, DiffusionLight (recalled) | Optional global-light prior for comparison | Whole-image estimators do not localize an object |
| Neural inverse and forward rendering | DiffusionRenderer ([arXiv](https://arxiv.org/pdf/2501.18590)), RGB↔X, Neural Gaffer ([arXiv](https://arxiv.org/html/2406.07520v3)), IC-Light | Candidate learned front end (albedo, normal, irradiance). **Attack tools** | Heavy. Mostly trained on synthetic or indoor data. Unproven on glossy outdoor cars |
| Geometry cues for generated images | Sarkar et al., CVPR 2024: classifiers on perspective fields, lines, and object-shadow relations catch generated images that fool signal-based detectors ([arXiv](https://arxiv.org/pdf/2311.17138)). Farid 2022 on DALL·E 2 lighting ([arXiv](https://arxiv.org/abs/2207.13744v2)). Light2Lie, NDSS 2026 (specular reflectance) ([NDSS](https://www.ndss-symposium.org/ndss-paper/light2lie-detecting-deepfake-images-using-physical-reflectance-laws)) | **Physics features into a small classifier** is an accepted pattern | Those target generated images, which this project does not claim to detect |
| Explainable forensics with MLLMs | FakeShield, ICLR 2025 ([arXiv](https://arxiv.org/html/2410.02761v3)) | Natural-language rationale as a UI element. A **VLM-judge baseline** for lighting questions | Explanations come from a model trained on GPT-4o text, so faithfulness is unchecked |
| Attacks on forensics | GAN anti-forensics against splicing detectors, Fang and Stamm ([arXiv](https://arxiv.org/abs/2211.12314v1)). Mimicry attacks, Pasquini 2024. Fan 2012 counter-forensics for 2D lighting (from the brief) | Threat-model vocabulary: white-box, black-box, hide vs. fabricate | None of what I found used **modern relighting, harmonization or shadow-generating insertion** against a physics-based detector. That is the open slot, to be confirmed by a proper review |
| Insertion with shadows | SGDiffusion ([arXiv](https://ar5iv.labs.arxiv.org/html/2403.15234)), ObjectDrop ([arXiv](https://arxiv.org/html/2403.18818v1)), MetaShadow | Realistic attacker tiers | |

Normal-estimation front ends (state in late 2026): DSINE, MoGe-2, Lotus-2, Marigold V2 and StableNormal sit in roughly the same accuracy band on indoor benchmarks ([Lotus-2](https://arxiv.org/pdf/2512.01030), [StableNormal](https://arxiv.org/pdf/2406.16864)). No source I found compares them on **outdoor glossy cars**, so the week-1 bake-off is itself a result.

Datasets located so far:
- CarDD: 4,000 images, pixel-level masks, licence unclear, non-commercial research ([arXiv](https://arxiv.org/pdf/2211.00945)).
- DSO-1 (lighting-focused splicing benchmark): availability and licence to be verified.
- KITTI, nuScenes, Waymo (recalled): outdoor driving with timestamps and vehicle pose. See section 5.

---

## 3. Candidate routes, assessed

| # | Route | Explainable | Robust to phone processing | Effort | Verdict |
|---|---|---|---|---|---|
| A | Estimate light per region, compare (original brief) | yes | no (assumes linear radiometry) | medium | Superseded by C |
| B | End-to-end learned splice detector (TruFor-class) | no | partly | low (off-the-shelf) | **Baseline and complementary detector only** |
| C | **Constraint and agreement-landscape on the sphere, tone-curve-invariant, multi-cue, with calibrated arbiter** | yes | yes (by construction) | medium | **Recommended core** |
| D | Neural inverse renderer front end, then SH lighting consistency | partial | unknown | high | Ablation if time |
| E | Learned relight-and-compare (relight the region under context light, measure change) | weak | unknown | high | Exploratory cue |
| F | VLM-judge | text only, unverified | n/a | low | Baseline for "does physics beat a VLM?" |
| G | Fit a CAD car shape prior | yes | n/a | high | Stretch: cars are like faces, a known category, and 3D priors made face lighting forensics work |

---

## 4. Recommended approach: LightAudit-R

### 4.1 Six technical ideas

1. **Rank-based, tone-curve-invariant shading cue.** For a region with predicted normals n_i and intensities I_i, model I_i = g(n_i·l) with an *unknown monotone* g. This is a single-index model, and the classical estimator is maximum rank correlation (Han 1987) (recalled). g absorbs the camera response and gamma, HDR tone mapping, exposure, ambient offset, albedo scale and clipping. Estimate l by maximizing Spearman (or Kendall) rank correlation between I and n·l over a spherical grid of 2–5k directions. This removes the brief's weakest assumption (linear radiometry) at the cost of the directional-strength ratio, which is recovered afterwards from g's dynamic range. Each pixel pair also defines a half-sphere constraint, which links the cue to Kee's constraint view.
2. **Agreement landscapes instead of point estimates.** Each cue and region produces a score map S_k(l) over the sphere. Uncertainty comes from spatial block bootstrap plus Monte-Carlo normal noise (model ensemble disagreement and diffusion-seed variance). The viewer draws the landscape as a heat dome. "Cones" are contour levels of it. Landscapes are anisotropic and can be multimodal.
3. **Compatibility test instead of estimate-then-compare.** Maximize the weighted sum of cue landscapes to get a consensus l*. A region's score is its **shortfall**: how much its own best agreement drops when forced to use l*. This is a likelihood-ratio-like quantity (shared light vs. own light). Errors in a single light estimate no longer propagate directly into the decision, and the same quantity serves as the leave-one-out outlier score.
4. **Multiple physical cues with different failure modes** (the Lalonde principle):
   - C1 shading rank-agreement (above).
   - C2 specular glint: at saturated highlight pixels, l = reflect(view, n). These are the pixels C1 discards.
   - C3 occluding contour: silhouette normals are known without any network (Johnson-Farid).
   - C4 cast-shadow geometry (Kee-style constraints), semi-automatic, with a shadow detector proposing object-shadow pairs and the user confirming.
   - C5 optional metadata prior: solar elevation from EXIF time and GPS, compared to the ground-relative light elevation.
5. **Small learned arbiter plus distribution-free false-alarm control.** Per-region feature vector: cue shortfalls, landscape sharpness, normal-ensemble disagreement, directionality, mask size, saturation fraction. A shallow gradient-boosted classifier trained on synthetic composites with exact labels gives a score with feature attributions. The decision threshold is set by **split-conformal calibration on held-out pristine photos from the same domain**, so the false-alarm rate on pristine data is controlled to a chosen level (assumes exchangeability, so calibrate on the same camera and processing pipeline). I did not find prior conformal calibration in lighting forensics, to be confirmed. Abstain when features say the region is uninformative (low directionality, narrow normal spread, tiny mask) or the reference regions disagree among themselves (multi-light scene).
6. **Counterfactual explanation.** The evidence view shows: (a) the dome with per-region landscapes and the consensus, (b) a counterfactual render of the suspect region under the consensus light next to the observed pixels, (c) a z-score residual heatmap, (d) a rule-based text rationale generated from the structured numbers only (no free-text LLM, so nothing to hallucinate).

### 4.2 Two operating modes, matching the domain

- **Scene mode:** a vehicle against other scene content (ground, buildings, other cars, people, sky). Many regions, so this is the strong-evidence case.
- **Panel mode:** one claimed-damage ROI against its own panel, with the dent's wide spread of normals making it the best-conditioned region. A close-up of one door has no reference content, so scene mode must abstain there.

The **applicability rate** on real claim photos (what fraction of CarDD images have enough usable cues) is a headline result of its own.

### 4.3 What the CG side does

- WebGL2 relighting renderer (Lambertian plus GGX or Blinn-Phong), used for the counterfactual view and for the physics re-shade attack.
- Spherical landscape dome (Three.js plus custom shader), click-to-select region, drag-the-light with live per-region agreement (landscapes are precomputed, so dragging is a lookup, which keeps the viewer light).
- GPU or batched brute-force search over the sphere for the offline Python reference.
- Stretch: shadow-map analysis-by-synthesis (depth heightfield plus ground plane, shadow map per candidate light, IoU with the detected shadow). Fallback is Kee geometry.

---

## 5. Data and ground truth (changed from the first plan)

| Source | Gives | Use |
|---|---|---|
| **Driving datasets with timestamps and ego pose (KITTI first; nuScenes or Waymo if licences allow)** (recalled, verify fields) | Real outdoor images with many cars. **Sun direction in the camera frame computed exactly** from a solar-ephemeris library, date, time, GPS and IMU orientation | Real-image angular error, calibration of landscapes, conformal calibration set. **Real discrepancy-angle experiments**: paste a car crop from a frame with sun direction B into a frame with direction A, where the angle between the two is known from the ephemeris. Caveats: cars are small, overcast frames must be filtered by directionality, licences are non-commercial |
| Blender (Cycles, Nishita sun and sky), exported on Colab | Exact normals, light, shadows, albedo. Composites with any chosen discrepancy angle | Normal bake-off, arbiter training, ablations. CARLA is a more complete simulator but needs a GPU-capable Unreal setup, so it is probably not viable on this laptop |
| CarDD | Real damage photos with masks | Applicability analysis, damage-crop splices, panel mode |
| DSO-1 (verify access) | Lighting-focused real splices (people) | Comparability with the literature and with TruFor |
| Edit sets we generate | T0 to T4 forgeries (section 7) | Detection and attack evaluation |
| Stress sets | Overcast, multi-lamp, heavy HDR or filter, JPEG q 95/75/50, resize, noise, fully generated images | Failure table and abstention rate |

---

## 6. Evaluation

**Hypotheses**
- H1. Tone-curve-invariant rank estimation beats the linear least-squares shading fit under nonlinear camera response (test with synthetic tone curves, then on KITTI frames).
- H2. Normal-ensemble disagreement predicts light-estimation error, and normal error dominates on glossy paint.
- H3. After calibration, 68% and 95% landscape contours cover the true light at nominal rates.
- H4. Fusing cues beats any single cue for both false alarms (multi-light scenes) and misses (after relighting).
- H5. **Physics and statistical detectors have different failure modes**: attacks that beat LightAudit leave traces TruFor catches, and the reverse. Report union TPR at fixed FPR.
- H6. Detection falls T0 > T1 > T2, with T2 mostly evading. Any result is reportable.

**Experiments**
- E1 normal-model bake-off (angular error on Blender cars and a KITTI subset).
- E2 angular error and coverage on KITTI with ephemeris GT.
- E3 **minimum detectable inconsistency (MDI) curve**: TPR at fixed FPR against discrepancy angle, per cue and fused, on synthetic and on real swaps.
- E4 forgery detection by tier against TruFor and the VLM judge.
- E5 localization (heatmap IoU and pointing game).
- E6 abstention: risk-coverage curve and applicability rate.
- E7 robustness: JPEG, resize, noise, tone curve, HDR.
- E8 ablations: cue subsets, normal model, rank vs. LS, arbiter vs. fixed rule.
- E9 explanation faithfulness: does re-rendering under the claimed consensus reproduce the observed shading better than a random or shifted light? Plus a small human study (10–20 classmates): score-only vs. evidence view, accuracy and confidence.

---

## 7. Attack lab

| Tier | Attacker |
|---|---|
| T0 | Naive paste or splice |
| T1 | Colour or histogram harmonization |
| T2 | Diffusion inpainting or generative edit in place |
| T3a | Physics re-shade (divide by estimated shading, multiply by shading under consensus), using our own renderer |
| T3b | Learned relighting (IC-Light or Neural Gaffer with a target direction) |
| T3c | Insertion with generated shadows (SGDiffusion or ObjectDrop-style, where open models exist) |
| T4 | Adaptive white-box: optimize the region's shading parameters, or a perturbation, against the detector score |

**Security framing.** An attacker succeeds if their estimate error of the scene light is below the detector's MDI. Fusing cues forces the attacker to satisfy several cues at once, including glints and cast shadows that diffusion editors do not control. Measure attack success against fidelity (LPIPS) and attacker effort, and report the union with TruFor. Attack mode is a red-team evaluation of a defensive tool.

---

## 8. Risks, kill criteria and fallbacks

| Risk | Signal | Fallback |
|---|---|---|
| Normals on glossy paint are too poor | Week-3 gate: median shading error above about 35° or landscapes covering over 60% of the sphere on most car regions | Lean on C2 to C4 and non-glossy regions (ground, buildings, people). Report the shading-on-paint failure as a finding |
| KITTI ephemeris GT unusable (missing date, pose or too overcast) | Cannot compute sun direction for a sample of frames | Fall back to Blender-only GT plus a small self-shot set with phone time and GPS |
| Cars too small in driving frames | Mask under about 5k pixels for most cars | Restrict to near cars, add ground and building regions |
| Simulation-to-real gap hurts the arbiter | Arbiter AUROC drops sharply from synthetic to real | Calibrate on real pristine data (conformal), use a fixed rule on landscapes |
| Attack models not runnable on Colab T4 | OOM or licence | Skip T3c, keep T3a and T3b |
| Time | Less than the 8 weeks assumed | Compressed track below |

---

## 9. Phases (8 weeks; compressed track in brackets)

1. **Weeks 1–2 [days 1–7]** Colab pipeline: SAM2 plus semantic labels, normal-model bake-off on Blender GT, C1 (rank landscape) with block bootstrap, C3. Gate: landscapes behave on synthetic spheres and Blender cars.
2. **Week 3 [days 8–10]** KITTI ephemeris GT, E2, H1 test, C2. **Gate 1** (section 8).
3. **Week 4 [days 11–14]** Fusion, shortfall test, abstention, arbiter, conformal threshold, E3.
4. **Weeks 5–6 [days 15–21]** Viewer: dome landscapes, region select, drag-light lookup, counterfactual render, residual heatmap, evidence pack.
5. **Weeks 6–7 [days 22–26]** Attack tiers T0–T3a/b, TruFor and VLM baselines, E4 to E7.
6. **Week 8 [days 27–30]** Human study, E9, report, demo script, failure gallery. Cut C4, C5, G, D and T3c first.

**Priority if time runs out:** (1) C1 plus C2 landscapes and calibration on KITTI and Blender, (2) fusion, verdict and abstention, (3) viewer, (4) attack tiers T0–T3 with the MDI curve and the TruFor comparison, (5) arbiter and conformal, (6) C3, C4 and stretches.

---

## 10. Verification (end-to-end)

- Unit: rank-landscape recovers a known light on a rendered sphere under several monotone tone curves, and fails gracefully with noisy normals. JS lookup matches the Python landscape values.
- Synthetic suite: Blender scenes with known sun, coverage test of 68% and 95% contours.
- Real GT: KITTI sample with ephemeris light, median angular error and coverage, compared to the linear-LS baseline.
- Detection: run the T0 to T3 sets through LightAudit, TruFor and the VLM judge, produce the E3 and E4 tables.
- Viewer: load a bundle, click regions, drag the light, confirm the counterfactual render and heatmap update, and verify with the Browser pane.
- Abstention check: overcast and multi-lamp images produce "insufficient evidence", not a verdict.

---

## 11. Items I could not verify (resolve in week 1)

- Whether KITTI, nuScenes or Waymo expose the date, time, GPS and orientation needed, and their licence terms.
- DSO-1 access and licence. TruFor licence (research-only?). CarDD licence.
- Which normal model is best on outdoor cars (no public benchmark found).
- Whether prior work already applies maximum rank correlation, conformal calibration, or modern relighting and shadow-insertion attacks to lighting forensics. My searches did not find it, but they were shallow.
- The recalled references: Johnson and Farid 2005 and 2007, Han 1987, Carvalho and Riess illuminant work, Hold-Geoffroy, DiffusionLight, Forensic Similarity, EXIF self-consistency.

## 12. Assumptions (the question from the last round is still open)

Deadline and team size are unknown. The plan assumes 8 weeks and one to two people, a laptop with no discrete GPU, and Colab or Kaggle for inference and rendering. If the course grades real-time graphics heavily, shift effort from the arbiter and the human study to the shadow-map stretch.

## Critical outputs when implementation starts

`lightaudit/` (regions, normals, cues, fusion, arbiter, attacks, bundle export), `blender/` (scene and composite generator), `eval/` (E1 to E9), `viewer/` (Vite, Three.js, shaders), `report/`, plus a short `docs/literature.md` with the table in section 2. Copy this plan to `PLAN.md` in the project at that point.
