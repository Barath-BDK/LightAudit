# LightAudit — 12-slide outline

Numbers on slides 9 and 10 come from the quick evaluation suite; replace them from `data/results/tables/`
after a full run.

## 1. Title
LightAudit: explainable lighting-consistency auditing of edited images, with a relighting-attack evaluation.
*Notes:* one sentence: "does one light direction explain every part of this photo, and can we show why?"

## 2. Problem
Edited photos are hard to verify; learned detectors give an opaque score. Use case: vehicle-damage photos in
insurance claims.
*Notes:* a flag means "send for human review", never "fraud". Say it early.

## 3. Idea
One sun lights everything. A pasted region carries another light. Estimate the light per region, test agreement,
abstain when the evidence is thin. Figure: `docs/figures/light_dome.png`.
*Notes:* four verdicts: CONSISTENT, SUSPICIOUS, INSUFFICIENT, CONFLICT (`triage.png`).

## 4. Pipeline
Figure: `docs/figures/pipeline.png`.
*Notes:* point out where CG, CV, image processing and ML each appear.

## 5. Cues
Figures: `rank_invariance.png`, `cue_geometry.png`.
*Notes:* the shading cue uses only the rank order of brightness, so the camera's tone curve does not matter.
Glints and silhouettes add geometry-based evidence.

## 6. From cue to verdict
Figures: `cones_vs_posterior.png`, `shortfall_diagram.png`.
*Notes:* bootstrap gives a map of plausible lights per region; leave-one-out shortfall measures disagreement.

## 7. The viewer (live demo)
Screenshots: `viewer_main.png`, `viewer_dome.png`, `viewer_explain.png`.
*Notes:* follow `docs/DEMO_SCRIPT.md`: drag the light, watch relit image, residual and verdict update.

## 8. Calibration and abstention
Figure: `conformal.png`, `F3_calibration.png`.
*Notes:* alarm level 4.95 keeps false alarms at 5% on clean calibration scenes; 11.5% of them return
INSUFFICIENT. Coverage of the true light: 0.66 / 0.93 for the 68% / 95% sets.

## 9. Attacks
Figures: `attack_ladder.png`, `F8_attacks.png`, screenshot `viewer_attack.png`.
*Notes:* colour transfer does not fool the check. Physics re-shade does: detection falls to about 0–0.09 even
with a 20° error in the forger's light. The extra cues recover almost nothing.

## 10. Results
Figures: `F4_mdi.png`, `F1_tone_curves.png`.
*Notes:* honest headline: detection is modest (AUC about 0.65 for a pasted car in the quick suite) and the rank
cue is about three times less accurate than a least-squares baseline (about 22° against 7° median error).

## 11. Failure cases and real photos
`demo_failure_missed_splice`, `demo_multilight`, and the real-photo bundles.
*Notes:* a 120° splice that passes; two suns called CONSISTENT; unedited real photos flagged. Explain why:
synthetic-only calibration, weak normals, texture and cast shadows.

## 12. Limitations and conclusion
The limitations text from the README.
*Notes:* what worked (viewer, analysis by synthesis, honest evaluation), what did not (the rank cue, robustness
to re-shading), and the next steps: least-squares or hybrid cue, stronger normal estimator, calibration on real
unedited photos.
