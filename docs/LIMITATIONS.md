# Limitations

> **What LightAudit can and cannot do.** LightAudit checks whether the lighting of different parts of a photo is physically consistent. It does **not** detect AI-generated images in general: a generator that produces the whole picture in one pass usually gives every object the same plausible light. A careful forger who re-lights an edited region to match the scene can pass the shading check (the attack lab measures exactly how much extra work that takes). Real photos can be flagged wrongly when they contain several lights, strong reflections, or bad surface-direction estimates, and many real photos (overcast, indoor, heavily filtered, tiny or flat objects) carry too little lighting evidence, in which case LightAudit says "insufficient evidence". Surface directions come from pretrained neural networks and are learned guesses, not measurements. The alert threshold controls the false-alarm rate only for photos like those used for calibration. **A flag means "send for human review", never "this is fraud".** Results on synthetic scenes do not automatically transfer to real photos; real-photo results are qualitative unless stated.

The rest of this page expands on each point.

## 1. What is being tested

LightAudit tests one physical hypothesis: *a single distant light explains the shading of every reliable region in the photo*. It does not look at noise patterns, compression traces, semantics or metadata. Any edit that leaves the lighting consistent is invisible to it, and any lighting inconsistency that is not an edit (a second lamp, a reflection) can trigger it. The output is one signal for a human reviewer, not a decision about fraud.

## 2. Fully generated images

A generator that produces the whole image at once usually gives all objects a plausible common light, so the shading of all regions is mutually consistent and LightAudit returns CONSISTENT. Published work (see `LITERATURE.md`, Farid 2022; Sarkar et al. 2024) finds that generated images often break *geometric* constraints such as shadows and perspective. LightAudit's only geometric cue for that is the manual, experimental shadow-pair tool (C4). We make no claim about detecting generated images.

## 3. Attacks

The attack lab is part of the product because the method can be fooled:

- **Colour/brightness harmonisation (T1)** changes colours by a nearly monotone map, which leaves the rank order of brightness, and therefore the rank shading cue, essentially unchanged. We expect T1 to fail against C1; the experiments report what actually happens.
- **Physics re-shading (T3a)** with a good estimate of the scene light can make the shading cue agree. How good the estimate must be is measured against the minimum detectable inconsistency (MDI).
- Multiplicative re-shading **does not move specular highlights**, so the glint cue (C2) can still disagree. An attacker who removes the glints (T4) leaves the region with no glint evidence; the cue then abstains rather than agreeing.
- **Learned relighting tools and shadow-generating insertion models were not evaluated** (they are listed as "Later" in the build spec). They may be stronger attacks than anything tested here.
- With simulated normals (`noisy_gt`) the defender's normals do not react to the edit at all. That is the best case for the attacker in T3a/T4 and the worst case for honest evaluation of a real system. Only E10 (if a real normal backend is installed) re-predicts normals from the attacked image.

## 4. Surface normals

All shading and glint cues depend on per-pixel surface normals. On real photos these come from pretrained networks (DSINE, StableNormal, Marigold, Depth Anything as a last resort). They are learned guesses:

- They are least reliable exactly where the cues need them: glossy car paint, chrome, glass, dark or saturated surfaces, and object boundaries.
- **Circularity:** a network that has learned "bright surfaces face the light" can bend its normals toward the observed shading. A pasted region then gets normals that partly agree with its own wrong lighting, which hides the inconsistency. Re-shading attacks could also shift the predicted normals. This is not measured on the synthetic data (simulated normals do not have this behaviour) and is only partly measured by E10.
- Ensemble disagreement is used as an uncertainty estimate. Disagreement between networks trained on similar data underestimates the true error.
- Axis conventions differ between backends; an automatic check with two priors (ground faces up, visible surfaces face the camera) corrects flips, and can itself fail on unusual photos (e.g., no visible ground). Manual overrides exist.

## 5. Scene conditions

The light model is a single distant directional light plus a smooth ambient term. This fails, or carries little information, when:

- the light is **diffuse** (overcast, shade): shading is weak and the rank landscapes are flat, so regions become unreliable and the verdict is INSUFFICIENT;
- there are **several lights** (street lamps, flash plus sun, indoor fixtures): reference regions disagree and the verdict should be CONFLICT or INSUFFICIENT; it can also produce false flags;
- there are **strong reflections or interreflections** (a car body reflecting a white wall, light bounced from the ground): the shading of a region no longer follows `g(n·l)`;
- **cast shadows** fall across a region: shadowed pixels with lit-facing normals contradict the model. Deep shadow pixels are removed (`Y < 0.04`), soft or partial shadows are not;
- **albedo varies** inside a region (stickers, two-tone paint, text, wet patches): the rank cue assumes roughly constant albedo per region; segmentation must split such regions.

## 6. Image conditions

- **Heavy filters and local tone mapping** (HDR modes, "vivid" filters, local contrast enhancement) are not global monotone curves. Rank invariance covers global monotone curves only.
- **Small or flat regions** constrain the light poorly. Regions with fewer than 150 usable pixels get no weight; regions with a narrow spread of normals get a low reliability weight.
- **Strong JPEG compression, downscaling and noise** degrade normals and shading; experiment E7 measures this on synthetic images without re-fitting the threshold.
- **Saturated regions** lose shading information; only small saturated blobs are used, as glints.

## 7. Calibration and statistics

- The alert level τ is a split-conformal quantile of image scores on pristine calibration scenes. It bounds the false-alarm rate **only** for new images that are exchangeable with the calibration set (same scene generator, camera pipeline, normal predictor and region backend). On real photos from other cameras it should be re-calibrated with `tools/calibrate_on_folder.py` on the user's own unedited photos.
- It says nothing about the miss rate (how often edits are caught). Detection rates come from experiments E4, E5 and E9.
- Images that return INSUFFICIENT are excluded from the calibration set; the guarantee therefore applies to images that receive a decision.
- Credible-region coverage (KDE bandwidth h, temperature T) is tuned on synthetic scenes and assumes the scene's ground-truth sun direction is the right target; the synthetic sky term biases this slightly.
- Calibrated values are stored in `lightaudit/calib_default.json`; they are not universal constants.

## 8. Evaluation scope

- Almost all quantitative results come from **synthetic** SDF scenes rendered on the CPU with **simulated** normal predictors. They show how the method behaves when its assumptions roughly hold. They do not show that it works on real claim photos.
- Composite experiments re-use the pristine posteriors of untouched regions. This is exact for the synthetic data (regions are ground-truth objects whose pixels the edit does not change) but means the experiments never exercise segmentation errors that cross the pasted boundary, except in the small `gt` vs `slic` ablation.
- Real-photo results, if any, are qualitative unless stated otherwise, and ground truth for real splices is only known for splices we made ourselves.
- No user study was run, so we do not claim that the viewer improves human decisions.

## 9. Photo types

The table below is a practical guide for which photos LightAudit can say something about. "Usable" means the method's assumptions roughly hold; it does not mean results are guaranteed. (The background plan in `PLAN.md` contains no such table, so this one was written for this document.)

| Photo type | Status | Why |
|---|---|---|
| Outdoor, direct sun, whole car plus surroundings (ground, buildings, poles, other cars) | **Usable** | One dominant light, many regions with varied surface directions; scene mode works best here. |
| Outdoor, direct sun, close-up of one panel with a dent (panel mode with ROI + ring) | **Partly usable** | The dent has a wide spread of normals, but there are few independent reference regions; scene-level consensus is weak. |
| Low sun (morning/evening), long shadows, strong directional light | **Usable** | Strong shading contrast; back-lit scenes are allowed by the full-sphere model. |
| Outdoor, hazy or thin cloud (sun still visible) | **Partly usable** | Weaker shading; expect broad posteriors and more INSUFFICIENT. |
| Overcast, rain, deep shade | **Unusable** | No dominant direction; the expected and correct output is INSUFFICIENT. |
| Night, street lamps, headlights, flash | **Unusable** | Several nearby lights; violates the single distant light model; CONFLICT or false flags. |
| Indoor (garage, showroom), several fixtures | **Unusable** | Multiple and near lights, strong interreflection. |
| Very glossy or dark paint, chrome, glass dominating the region | **Partly usable** | Shading is mostly reflection; normals from networks are poor; glints may help if the sun is reflected. |
| Heavily filtered, local HDR, beauty or "vivid" modes, screenshots of screens | **Partly usable to unusable** | Local tone mapping breaks the global monotone-curve assumption. |
| Tiny objects, low resolution (car under ~100 px tall), strong compression | **Partly usable to unusable** | Too few usable pixels; normals unreliable. |
| Flat scenes (a wall, a flat door panel filling the frame) | **Unusable** | All normals nearly equal; light is not constrained. |
| Fully AI-generated image | **Not applicable** | Lighting is usually globally consistent; LightAudit is not a generated-image detector. |
