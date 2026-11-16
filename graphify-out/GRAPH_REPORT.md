# Graph Report - Course_Project  (2026-11-16)

## Corpus Check
- 108 files · ~118,736 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 4 file(s) not represented in the graph (top: (none) 2, .joblib 1, .css 1)

## Summary
- 1176 nodes · 3399 edges · 60 communities (52 shown, 8 thin omitted)
- Extraction: 96% EXTRACTED · 4% INFERRED · 0% AMBIGUOUS · INFERRED: 129 edges (avg confidence: 0.89)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- CLI and demo bundles
- Server and dependencies
- Bundle manifest export
- Regions and normal backends
- Viewer app shell
- Real benchmark ball checks
- Attack module
- Viewer fusion mirror
- Figures
- 3D light dome
- Spec and build log docs
- Eval common helpers
- MIT object benchmark
- Related work
- Posterior calibration E3
- Viewer main app
- Viewer workspace
- Real panel attack
- Normal tests
- Real-scene estimators
- Gradient-boosted arbiter
- Silhouette cue
- Direction grid
- Relight renderer
- Viewer feature docs
- Metrics
- Fusion tests and parity
- Explain stepper
- Explanation text
- Residual light fit
- Real-image findings
- Calibration
- JS parity test
- Cue design decisions
- Eval sample cache
- Experiments E1 E2
- Experiments E7 E10
- Glint cue
- Fusion core
- Attack findings
- METHOD cluster
- BUILD_LOG cluster
- exp_e9 cluster
- regions cluster
- exp_e8 cluster
- test_eval_smoke cluster
- real_bench cluster
- mit_bench cluster
- exp_e4 cluster
- common cluster
- shadow_tool cluster
- BUILD_SPEC cluster
- exp_e6 cluster
- shadow_pairs cluster
- mit_bench cluster
- mit_panel cluster
- residual cluster
- pyproject cluster

## God Nodes (most connected - your core abstractions)
1. `Config` - 87 edges
2. `$$` - 48 edges
3. `eq_dirs()` - 44 edges
4. `calibrated()` - 39 edges
5. `get_sample()` - 29 edges
6. `angle_deg()` - 28 edges
7. `audit_sample()` - 28 edges
8. `LITERATURE.md (related work table)` - 28 edges
9. `audit()` - 26 edges
10. `esc()` - 26 edges

## Surprising Connections (you probably didn't know these)
- `LightAudit_Guide.pdf (rendered status guide)` --semantically_similar_to--> `LightAudit status guide (HTML, 14 Nov 2026)`  [INFERRED] [semantically similar]
  docs/LightAudit_Guide.pdf → docs/LightAudit_Guide.html
- `LightAudit_Results.pdf (rendered results report)` --semantically_similar_to--> `LightAudit results report: what works and what does not (HTML)`  [INFERRED] [semantically similar]
  docs/LightAudit_Results.pdf → docs/LightAudit_Results.html
- `Stale documents (REPORT, SLIDES, Guide PDF predate Updates 5-8)` --references--> `LightAudit_Guide.pdf (rendered status guide)`  [EXTRACTED]
  HANDOVER.md → docs/LightAudit_Guide.pdf
- `Agreement landscapes instead of point estimates` --semantically_similar_to--> `Region posterior (spatial block bootstrap + KDE)`  [INFERRED] [semantically similar]
  PLAN.md → docs/METHOD.md
- `std_variants()` --uses--> `Config`  [INFERRED]
  eval/common.py → lightaudit/config.py

## Import Cycles
- 3-file cycle: `lightaudit/synth/__init__.py -> lightaudit/synth/composite.py -> lightaudit/synth/scenes.py -> lightaudit/synth/__init__.py`

## Hyperedges (group relationships)
- **Audit pipeline: regions, normals, cues, posterior, fusion, shortfall, calibrated verdict** — build_spec_region_proposals, build_spec_normals_ensemble, build_spec_pixel_validity, docs_method_ls_shading_cue, docs_method_region_posterior, docs_method_reliability_weight, docs_method_fusion_consensus, docs_method_leave_one_out_shortfall, docs_method_split_conformal_calibration, docs_method_verdict_logic [EXTRACTED 1.00]
- **Marked-area (panel) check on real photos: material test + light test after guarded Retinex with real thresholds** — build_spec_panel_mode, build_log_shared_material_test, build_log_shared_light_test, build_log_band_guarded_retinex, build_log_real_panel_calibration, build_log_mit_intrinsic_benchmark [EXTRACTED 1.00]
- **Scene-level checks applied after consensus fusion: soft light, shadow levels, panel flag** — docs_method_fusion_consensus, docs_method_soft_light_abstention, build_log_shadow_levels_check, docs_method_panel_residual, build_spec_four_verdicts [EXTRACTED 1.00]

## Communities (60 total, 8 thin omitted)

### Community 0 - "CLI and demo bundles"
Cohesion: 0.05
Nodes (41): main(), attack_suite(), build_demo_bundles(), _demo_one(), main(), audit_sample(), serve(), light_at_angle() (+33 more)

### Community 1 - "Server and dependencies"
Cohesion: 0.05
Nodes (31): backends_available(), _b64_fig(), _b64_file(), export_report(), fig(), _fmt(), _heat_png(), _md() (+23 more)

### Community 2 - "Bundle manifest export"
Cohesion: 0.07
Nodes (26): require_calibration(), build_manifest(), fusion_manifest(), region_manifest(), update_index(), validate_bundle(), write_bundle(), _write_maps() (+18 more)

### Community 3 - "Regions and normal backends"
Cohesion: 0.10
Nodes (29): prepare(), _apply_flips(), backend_details(), backends_available(), _cached_backend(), depth_to_normals(), fix_convention(), _has() (+21 more)

### Community 4 - "Viewer app shell"
Cohesion: 0.13
Nodes (38): bindTheme(), onKey(), openUpload(), showGallery(), drawCompare(), heatImage(), openAttackLab(), liveRun() (+30 more)

### Community 5 - "Real benchmark ball checks"
Cohesion: 0.13
Nodes (15): ball_check(), find_ball(), gt_lights(), landscapes(), load(), sphere_normals(), coarse_index(), camera() (+7 more)

### Community 6 - "Attack module"
Cohesion: 0.15
Nodes (14): _alpha(), fidelity(), interpret(), light_error_deg(), remove_glints(), ring_of(), run_attack(), scene_light_estimate() (+6 more)

### Community 7 - "Viewer fusion mirror"
Cohesion: 0.15
Nodes (24): argmax(), cellOf(), combineCues(), DEFAULT_CFG, displayShortfalls(), fuseCore(), logMaps(), looShortfalls() (+16 more)

### Community 8 - "Figures"
Cohesion: 0.22
Nodes (20): load_json(), _bundle(), _cap(), f1(), f2(), f3(), f4(), f5() (+12 more)

### Community 9 - "3D light dome"
Cohesion: 0.15
Nodes (9): circlePoints(), css(), Dome, sunTexture(), azElDeg(), fromAzElDeg(), NA, NE (+1 more)

### Community 10 - "Spec and build log docs"
Cohesion: 0.18
Nodes (24): BUILD_LOG.md (build status, Updates 1-8, deviations), BUILD_SPEC.md (one-shot build brief), Attack module / tiered self-attack (red-team evaluation), lightaudit CLI commands, Synthetic composites (paste target under second light l_B), Demo bundles (consistent, splice car, dents, multilight, overcast, failure), Evaluation suite E1-E11 with figures F1-F9, Section 21 limitations text (verbatim in README, Help, report) (+16 more)

### Community 11 - "Eval common helpers"
Cohesion: 0.11
Nodes (12): calib_info(), cfg_dict(), header(), _indexed(), make_composite(), n_procs(), pmap(), _progress() (+4 more)

### Community 12 - "MIT object benchmark"
Cohesion: 0.14
Nodes (12): bench_shared(), _kmeans(), landscapes(), load(), part_stats(), parts(), pixel_data(), prepare() (+4 more)

### Community 13 - "Related work"
Cohesion: 0.15
Nodes (24): 'Later' scope: learned relighting, TruFor/VLM baselines, KITTI ephemeris (not built), Fully generated images out of scope, LITERATURE.md (related work table), CarDD car damage dataset, DiffusionRenderer, FakeShield (explainable forensics with MLLMs), Fang & Stamm (anti-forensic GAN attack), Farid 2022 (lighting in DALL-E 2 images) (+16 more)

### Community 14 - "Posterior calibration E3"
Cohesion: 0.16
Nodes (11): _job(), run(), coverage(), hpd(), bootstrap_lights(), credible(), kde_posterior(), region_posterior() (+3 more)

### Community 15 - "Viewer main app"
Cohesion: 0.14
Nodes (20): hexRgb(), main(), params, root, sort, updateImageParams(), loadSummary(), mapArgmax() (+12 more)

### Community 16 - "Viewer workspace"
Cohesion: 0.23
Nodes (23): allRegions(), bindImage(), bindWorkspace(), cfgFromManifest(), ctx(), lsMaps(), openTune(), placeSplit() (+15 more)

### Community 17 - "Real panel attack"
Cohesion: 0.18
Nodes (11): main(), _one(), stats(), region_pixels(), Config, apply_roi(), panel_shared(), erode() (+3 more)

### Community 18 - "Normal tests"
Cohesion: 0.14
Nodes (10): _err(), _fake(), scene(), test_correct_convention_is_left_alone(), test_depth_to_normals_plane(), test_fallback_chain_when_everything_fails(), boom(), test_fallback_uses_next_backend_in_chain() (+2 more)

### Community 19 - "Real-scene estimators"
Cohesion: 0.18
Nodes (11): _clusters(), _corr(), est_ls(), est_ls_alb(), est_ls_log(), est_sh1(), est_sh1_alb(), fetch() (+3 more)

### Community 20 - "Gradient-boosted arbiter"
Cohesion: 0.16
Nodes (9): _arb_job(), _cal_job(), features(), load(), region_probs(), _rows(), score(), train() (+1 more)

### Community 21 - "Silhouette cue"
Cohesion: 0.20
Nodes (6): contour_landscape(), contour_pixels(), ls_landscape(), _pearson_rows(), rank_landscape(), _unit()

### Community 22 - "Direction grid"
Cohesion: 0.18
Nodes (11): area_weights(), dir_to_cell(), dir_to_index(), eq_dirs(), view_vectors(), window_index(), test_hpd_monotone(), test_round_trip() (+3 more)

### Community 23 - "Relight renderer"
Cohesion: 0.16
Nodes (4): compile(), ImageView, MODE_LABELS, MODES

### Community 24 - "Viewer feature docs"
Cohesion: 0.18
Nodes (15): Attack lab (viewer tab with precomputed attack variants), Bundle format (manifest.json + maps; backend-viewer contract), EQ grid (128x64 equirectangular direction grid), Explain stepper (7-step 'how this verdict was made'), FastAPI server with upload-and-audit, 3D light dome (dome.js, landscape shader, cones, draggable light), WebGL2 relighting renderer (relight.js image modes), Three.js (vendored r160) (+7 more)

### Community 25 - "Metrics"
Cohesion: 0.16
Nodes (10): auc(), bootstrap_ci(), _clean(), fmt_ci(), mdi(), median_ci(), rate_above(), roc_curve() (+2 more)

### Community 26 - "Fusion tests and parity"
Cohesion: 0.25
Nodes (15): fuse(), from_az_el_deg(), cone(), run(), test_combine_cues(), test_conflict(), test_consistent(), test_heavy_outlier_among_three() (+7 more)

### Community 27 - "Explain stepper"
Cohesion: 0.16
Nodes (15): drawFit(), drawFitPlot(), hexRgb(), INFERNO, layer(), LIMITATIONS, render(), zoom() (+7 more)

### Community 28 - "Explanation text"
Cohesion: 0.15
Nodes (6): explain(), combine_cues(), fuse_regions(), panel_ratio(), panel_score(), shadow_levels()

### Community 29 - "Residual light fit"
Cohesion: 0.17
Nodes (7): apply_g(), fit_g(), fit_light(), region_residual(), residual_maps(), shared_light_T(), shared_material_T()

### Community 30 - "Real-image findings"
Cohesion: 0.17
Nodes (15): DSINE mirrored x-axis bug, Finding: light estimator is right on real photos; predicted normals are the weak link, Finding: most real regions are flat and carry no light information, Per-region likelihood-ratio test with Holm correction, MIT Multi-Illumination benchmark (real indoor scenes), Six unedited Wikimedia outdoor car photos (data/real), Depth Anything V2 normal backend, Marigold normals backend (+7 more)

### Community 31 - "Calibration"
Cohesion: 0.20
Nodes (8): cal_kind(), conformal_quantile(), n_procs(), run_calibration(), _score_job(), _shape_job(), test_conformal_quantile_controls_false_alarms(), test_conformal_quantile_edge_cases()

### Community 32 - "JS parity test"
Cohesion: 0.12
Nodes (9): cfg, fpath, fv, gpath, gv, idxPath, ROOT, VEC (+1 more)

### Community 33 - "Cue design decisions"
Cohesion: 0.19
Nodes (10): Gradient-boosted arbiter (HistGradientBoostingClassifier), Han 1987 (maximum rank correlation estimator), Johnson & Farid 2005/2007 (lighting-inconsistency forensics), Kee, O'Brien & Farid 2014 (shading + shadows, ACM TOG), Lalonde, Efros & Narasimhan 2009/2012 (multi-cue sun estimation), C3 silhouette / occluding-contour cue, 68% / 95% credible sets and cone summaries, Posterior shape calibration (KDE bandwidth h, temperature T) (+2 more)

### Community 34 - "Eval sample cache"
Cohesion: 0.21
Nodes (10): composite(), edited_ids(), _key(), _load(), pristine(), sample(), _save(), slim_region() (+2 more)

### Community 35 - "Experiments E1 E2"
Cohesion: 0.20
Nodes (8): eligible(), _job(), run(), _binned(), _job(), run(), ls_direction(), angle_deg()

### Community 36 - "Experiments E7 E10"
Cohesion: 0.23
Nodes (9): _audit(), _job(), run(), _job(), perturb(), run(), jpeg_roundtrip(), audit() (+1 more)

### Community 37 - "Glint cue"
Cohesion: 0.16
Nodes (6): find_glints(), glint_landscape(), analyze_region(), factors(), reason(), weight()

### Community 38 - "Fusion core"
Cohesion: 0.17
Nodes (7): _fuse_core(), consistent(), _loo_shortfalls(), az_el_deg(), cone_half_angle_deg(), lightmap_figure(), test_axes()

### Community 39 - "Attack findings"
Cohesion: 0.18
Nodes (13): Finding: rank cue ~3x less accurate than least squares (H1 fails), Quick evaluation suite results (10% sample sizes), Finding: physics re-shade defeats the whole-object check, T1 Reinhard colour/brightness harmonisation, T3a physics re-shade attack, T4 adaptive white-box attack, DEMO_SCRIPT.md (5-minute demo walkthrough), LightAudit status guide (HTML, 14 Nov 2026) (+5 more)

### Community 40 - "METHOD cluster"
Cohesion: 0.19
Nodes (9): Rule-based explanation text (no LLM), Python/JS fusion parity test (parity.test.mjs), Live fusion in the browser (viewer/fusion.js), Pixel validity filtering (validity.py), Kee, O'Brien & Farid 2013 (shadow constraints, ACM TOG), C2 specular glint cue, C4 cast-shadow pair cue (manual, experimental), Fusion and consensus (weighted log-linear pool) (+1 more)

### Community 41 - "BUILD_LOG cluster"
Cohesion: 0.28
Nodes (7): MIT Intrinsic Images benchmark (real curved objects), Shared-material test (T = log RSS shared / RSS own), Panel mode (ROI + ring on the same panel), LightAudit results report: what works and what does not (HTML), Capability scorecard (works / partly / defeated), Marked-area (dent) check result on real objects (5.2% FA, 45% caught), Route A: push real-image accuracy (Track A)

### Community 42 - "exp_e9 cluster"
Cohesion: 0.27
Nodes (8): collect(), negatives(), _pos_by_scene(), run(), _eval(), _job(), _label(), run()

### Community 43 - "regions cluster"
Cohesion: 0.18
Nodes (3): manual_regions(), _meta(), slic_regions()

### Community 44 - "exp_e8 cluster"
Cohesion: 0.24
Nodes (6): _ablate(), run(), _slic_job(), audit_image(), auto_exclude(), propose_regions()

### Community 46 - "real_bench cluster"
Cohesion: 0.21
Nodes (7): angle_curve(), bench_composite(), analyse(), analyse2(), sc_fn(), ang(), auc()

### Community 47 - "mit_bench cluster"
Cohesion: 0.18
Nodes (6): bench_levels(), _fit(), lamp_dirs(), _learn_levels(), levels_scores(), _seg_levels()

### Community 48 - "exp_e4 cluster"
Cohesion: 0.29
Nodes (6): curve(), _job(), positives(), run(), scores(), _variants()

### Community 49 - "common cluster"
Cohesion: 0.25
Nodes (4): evaluate(), refuse(), summarize(), unslim_region()

### Community 51 - "BUILD_SPEC cluster"
Cohesion: 0.33
Nodes (5): Triage verdicts: CONSISTENT / SUSPICIOUS / INSUFFICIENT / CONFLICT, Vehicle-damage insurance claim use case, LightAudit (explainable lighting-consistency auditor), Photo-type usability table, Single distant light model assumption

### Community 52 - "exp_e6 cluster"
Cohesion: 0.53
Nodes (3): _job(), run(), calibrated()

### Community 54 - "mit_bench cluster"
Cohesion: 0.50
Nodes (3): bench(), sc_fn(), lr_scores()

## Knowledge Gaps
- **28 isolated node(s):** `lightaudit`, `root`, `params`, `sort`, `TIERS` (+23 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 340 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **8 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Config` connect `Real panel attack` to `CLI and demo bundles`, `Server and dependencies`, `Bundle manifest export`, `Regions and normal backends`, `Attack module`, `Eval common helpers`, `MIT object benchmark`, `Posterior calibration E3`, `Real-scene estimators`, `Gradient-boosted arbiter`, `Silhouette cue`, `Fusion tests and parity`, `Explanation text`, `Residual light fit`, `Calibration`, `Eval sample cache`, `Experiments E1 E2`, `Experiments E7 E10`, `Glint cue`, `Fusion core`, `regions cluster`, `exp_e8 cluster`, `test_eval_smoke cluster`, `common cluster`, `exp_e6 cluster`, `shadow_pairs cluster`, `mit_panel cluster`?**
  _High betweenness centrality (0.046) - this node is a cross-community bridge._
- **Are the 47 inferred relationships involving `Config` (e.g. with `cfg_dict()` and `edited_ids()`) actually correct?**
  _`Config` has 47 INFERRED edges - model-reasoned connections that need verification._
- **What connects `lightaudit`, `root`, `params` to the rest of the system?**
  _28 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `CLI and demo bundles` be split into smaller, more focused modules?**
  _Cohesion score 0.050645007166746296 - nodes in this community are weakly interconnected._
- **Why does `calibrated()` connect `exp_e6 cluster` to `CLI and demo bundles`, `Eval sample cache`, `Experiments E1 E2`, `Experiments E7 E10`, `Bundle manifest export`, `exp_e9 cluster`, `Eval common helpers`, `exp_e8 cluster`, `regions cluster`, `Posterior calibration E3`, `test_eval_smoke cluster`, `exp_e4 cluster`, `Real panel attack`, `Gradient-boosted arbiter`, `Explanation text`?**
  _High betweenness centrality (0.017) - this node is a cross-community bridge._
- **Should `Server and dependencies` be split into smaller, more focused modules?**
  _Cohesion score 0.050203527815468114 - nodes in this community are weakly interconnected._
- **Why does `panel_shared()` connect `Real panel attack` to `Real benchmark ball checks`, `MIT object benchmark`, `Direction grid`, `mit_panel cluster`, `residual cluster`, `Explanation text`, `Residual light fit`?**
  _High betweenness centrality (0.015) - this node is a cross-community bridge._