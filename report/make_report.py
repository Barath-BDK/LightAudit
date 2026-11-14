"""Assembles report/REPORT.md. Tables and calibration numbers are loaded from data/results at run time;
the analysis paragraphs were written after reading the QUICK-suite results and say so. Re-run after a full
evaluation and re-read section 5 against the new tables.

    python -m lightaudit.cli report
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RES = ROOT / "data" / "results"
LIMITS = ("> **What LightAudit can and cannot do.** LightAudit checks whether the lighting of different parts of a "
          "photo is physically consistent. It does **not** detect AI-generated images in general: a generator that "
          "produces the whole picture in one pass usually gives every object the same plausible light. A careful "
          "forger who re-lights an edited region to match the scene can pass the shading check (the attack lab "
          "measures exactly how much extra work that takes). Real photos can be flagged wrongly when they contain "
          "several lights, strong reflections, or bad surface-direction estimates, and many real photos (overcast, "
          "indoor, heavily filtered, tiny or flat objects) carry too little lighting evidence, in which case "
          "LightAudit says \"insufficient evidence\". Surface directions come from pretrained neural networks and "
          "are learned guesses, not measurements. The alert threshold controls the false-alarm rate only for photos "
          "like those used for calibration. **A flag means \"send for human review\", never \"this is fraud\".** "
          "Results on synthetic scenes do not automatically transfer to real photos; real-photo results are "
          "qualitative unless stated.")


def table(name: str) -> str:
    p = RES / "tables" / f"{name}.md"
    return p.read_text(encoding="utf-8").strip() if p.exists() else f"*(table {name} not generated yet)*"


def fig(name: str, caption: str) -> str:
    return f"![{caption}](../docs/figures/{name})\n\n*{caption}*" if (ROOT / "docs" / "figures" / name).exists() else f"*(figure {name} not generated yet)*"


def real_rows() -> str:
    rows = []
    for mf in sorted((ROOT / "bundles").glob("real_*/manifest.json")):
        m = json.loads(mf.read_text())
        f = m["fusion"]
        rows.append(f"| {m['name']} | {m['normals_backend']} | {m['regions_backend']} | {len(m['regions'])} | "
                    f"{f['n_reliable']} | {f['verdict']} | {f['S_img']:.2f} |")
    if not rows:
        return "*(no real-photo bundles built)*"
    return ("| bundle | normals | regions | regions found | reliable | verdict | image score |\n|---|---|---|---|---|---|---|\n"
            + "\n".join(rows))


def attack_rows() -> str:
    p = RES / "attack_summary.json"
    if not p.exists():
        return "*(attack summary not generated yet)*"
    d = json.loads(p.read_text())
    out = ["| tier | n | detected, shading only | detected, all cues | mean abs dY |", "|---|---|---|---|---|"]
    for r in d["rows"]:
        dy = "-" if r.get("mean_abs_dY") is None else f"{r['mean_abs_dY']:.3f}"
        out.append(f"| {r['label']} | {r['n']} | {r['tpr_c1']:.2f} | {r['tpr_fused']:.2f} | {dy} |")
    return "\n".join(out) + f"\n\nSuite: {d.get('suite')}. {d.get('caveat', '')}"


def main() -> Path:
    c = json.loads((ROOT / "lightaudit" / "calib_default.json").read_text())
    suite = "unknown"
    if (RES / "attack_summary.json").exists():
        suite = json.loads((RES / "attack_summary.json").read_text()).get("suite", suite)
    text = f"""# LightAudit: Explainable Lighting-Consistency Auditing of Edited Images, with Relighting-Attack Evaluation

Interactive Computer Graphics, semester 7 course project.

> **Status of the numbers in this report.** All tables are loaded from `data/results` (evaluation suite:
> **{suite}**). The quick suite uses 10% of the planned sample sizes (often 5 to 15 scenes per cell), so the
> confidence intervals are wide and the analysis below is provisional. Scenes are synthetic and the surface
> normals are simulated unless a section says otherwise.

## Abstract

LightAudit checks whether one light direction explains every region of a photo. For each region it estimates a
map of plausible light directions from shading (a rank-correlation cue that is invariant to the camera's tone
curve), specular highlights and silhouettes; it fuses the regions, measures each region's leave-one-out
disagreement ("shortfall"), and raises a flag when the largest shortfall exceeds a split-conformal threshold.
An interactive WebGL viewer shows the evidence on a 3D light dome and re-lights the image live, and an attack
module re-shades a pasted region to measure how easily the check is defeated. The rank cue we proposed turned
out to be about three times **less** accurate than a simple least-squares shading fit, so least squares is now
the default cue and the rank cue is kept as the evaluated baseline. With it the system detects a pasted car lit
from 120 degrees away in the demo, but measured detection rates remain modest, a physics re-shade defeats the
detector almost completely, pasted dents are not detected, and real-photo results are qualitative only. We
report these results as they are.

## 1 Introduction and problem

Edited or composited photos are hard to verify, and learned forgery detectors return an opaque score. In an
outdoor photo the sun lights every object from one direction, so surfaces facing the light are brighter. A
region pasted from another photo carries the shading of another light. The use case that motivates the demo is
insurance triage of vehicle-damage photos: `CONSISTENT` goes to normal processing, `SUSPICIOUS` goes to a human
adjuster with the evidence view, `INSUFFICIENT` asks for a better photo, `CONFLICT` means the scene does not fit
the one-light model. A flag is never proof of fraud.

Contribution (engineering and evaluation, not a new forensic principle): a tone-curve-invariant rank shading
cue; a calibrated posterior on the sphere with a leave-one-out shortfall test and abstention; multi-cue fusion;
a counterfactual interactive viewer; and a tiered self-attack evaluation.

## 2 Related work

Lighting-inconsistency forensics goes back to Johnson and Farid (2005, 2007) and Kee, O'Brien and Farid (2013,
2014), who constrain the light from contours, shading and shadows. Lalonde, Efros and Narasimhan (2009, 2012)
combine several cues into a probabilistic sun estimate. Recent work examines lighting and geometry in generated
images (Farid 2022; Sarkar et al. 2024) and physically motivated deepfake detection. Learned relighting
(IC-Light, Neural Gaffer, DiffusionRenderer) is the natural attack on such detectors and is out of scope here.
The full table with links is in [docs/LITERATURE.md](../docs/LITERATURE.md); a systematic review of attacks on
physics-based detectors was not completed.

## 3 Method

{fig("pipeline.png", "I1. Pipeline: photo, regions, normals, cues, region maps, fusion with leave-one-out, calibrated verdict, viewer and attack.")}

The full derivation is in [docs/METHOD.md](../docs/METHOD.md). In brief:

- **Conventions.** Camera space with +x right, +y up, +z toward the viewer; all direction maps live on one
  128 x 64 equirectangular grid shared by Python and JavaScript.
- **C1, shading.** Default (`Config.cue = "ls"`): the light maximises the Pearson correlation between
  `max(0, n.l)` and the linearised luminance `Y^2.2`. Original proposal, kept as the baseline (`cue = "rank"`):
  `Y = g(max(0, n.l))` for an unknown monotone `g`, light = maximiser of the Spearman correlation with all
  attached-shadow pixels tied.
  {fig("rank_invariance.png", "I2. The rank cue ignores the tone curve.")}
- **C2 glints, C3 silhouettes, C4 shadow pairs.**
  {fig("cue_geometry.png", "I3. Geometry of the extra cues.")}
- **Posterior.** 30 spatial block-bootstrap draws with smooth normal perturbation, a KDE on the sphere
  (bandwidth h, temperature T), 68% / 95% highest-density sets.
  {fig("cones_vs_posterior.png", "I5. Credible sets and their cone summaries.")}
- **Reliability.** Five factors (size, normal spread, sharpness, correlation strength, normal uncertainty)
  combined by a geometric mean; regions below 0.35 do not vote.
- **Fusion and verdict.** Weighted sum of log maps, leave-one-out consensus, shortfall
  `s_k = -ln(eps + A_k(l*_-k))`.
  {fig("shortfall_diagram.png", "I6. Leave-one-out consensus and shortfall.")}
- **Calibration.** h and T are chosen for nominal coverage; the alarm level is the split-conformal quantile of
  pristine calibration scenes.
  {fig("conformal.png", "I7. Conformal alarm level.")}
- **Analysis by synthesis.** An isotonic fit predicts each region's brightness under the consensus light; the
  residual z-score is the heat map and the rescaled image is the counterfactual.

## 4 System

- `lightaudit/`: NumPy SDF ray-marcher for ground-truth scenes, the cues, posterior, fusion, calibration,
  attacks, bundle export, CLI and a FastAPI server with upload-and-audit.
- `viewer/`: static ES modules. A WebGL2 fragment shader re-lights the photo (Lambert via the fitted curve plus
  a Blinn-Phong or GGX highlight), draws the live residual and the counterfactual; a Three.js dome shows each
  region's map, the credible cones, the consensus and a draggable light; the fusion is re-run in the browser
  when regions are toggled (a parity test checks it against Python).

{fig("viewer_main.png", "Viewer: image view, light dome, verdict and region table (spliced-car demo).")}

{fig("viewer_attack.png", "Attack lab: original against attacked image, verdict before and after.")}

{fig("light_dome.png", "I4. Reading the light dome.")}

## 5 Experiments

Data: synthetic scenes (a car, 3 to 5 distractor objects, ground, optional building; random sun, tone curve,
noise, JPEG). Splits by seed: calibration 1000-1199, arbiter 2000-2199, test 3000-3299, demo 4000-4099.
Normals are the ground truth perturbed by spatially correlated noise of 8 degrees plus occasional gross patches.

### 5.1 Calibration (E3)

Calibration chose h = {c['h']} degrees and T = {c['T']}; on the calibration split the 68% / 95% sets cover the true
light {c['cov68']:.2f} / {c['cov95']:.2f} of the time ({c['n_shape_regions']} reliable regions). The alarm level is
{c['tau_img_05']:.2f} at alpha = 0.05 and {c['tau_img_10']:.2f} at alpha = 0.10; {100 * c['insufficient_rate']:.1f}% of
pristine calibration scenes return INSUFFICIENT.

{table("T2_calibration")}

{fig("F3_calibration.png", "F3. Reliability diagram on the test split.")}

These are the values for the least-squares cue. The alarm level is close to the maximum possible shortfall
(about 6.9): clean scenes often contain one region that disagrees strongly, so a 5% false-alarm rate forces a
high threshold. For comparison the rank cue calibrated to h = 18, T = 1.5 and an alarm level of 4.95
(`data/results_rank_quick/calib_rank.json`).

### 5.2 Cue accuracy under camera non-linearity (E1) - hypothesis H1 fails

{table("T1_tone_curves")}

{fig("F1_tone_curves.png", "F1. Light-direction error of the rank cue and the least-squares baseline per tone curve.")}

The rank cue is stable across tone curves, as designed, but it is **several times less accurate than the
least-squares baseline on every curve**, including the non-linear ones. We checked this separately on 39 regions
with exact normals (median error 26.8 degrees for rank against 8.3 for least squares) and tried weighting the
rank correlation toward bright pixels, which did not help. Our explanation: ranks discard the *magnitude* of
brightness differences. For shapes with few distinct normals (the box-like car, buildings) many light directions
produce the same ordering of the faces, so the rank landscape has a wide plateau, whereas the least-squares fit
uses the brightness ratios between faces. The tone curves in the test set are mild enough that assuming gamma 2.2
costs the baseline little. The tone-curve invariance is real, but in this benchmark it does not pay for itself.
**Consequence: least squares became the default cue.** A separate 40-scene check on the calibration split gave
an AUC of about 0.83 for a car pasted from 90 degrees away with least squares against 0.75 with the rank cue
(about 0.66 for both at 45 degrees). The price is that least squares is not invariant to monotone brightness
changes: in the spliced-car demo a plain colour transfer now lowers the car's shortfall below the alarm level.

### 5.3 Normal quality (E2)

{fig("F2_normal_noise.png", "F2. Error against simulated normal noise, region size and normal spread.")}

### 5.4 Detection (E4, E5)

{table("T3_detection")}

{fig("F4_mdi.png", "F4. Detection rate against the discrepancy angle, per cue set.")}

{fig("F5_roc.png", "F5. ROC curves, discrepancy of 30 degrees or more against pristine.")}

In this table C1 is the default least-squares shading cue and RANK is the rank-cue baseline. Detection is
modest: a pasted car or distractor needs a discrepancy of roughly 60 to 135 degrees to reach 50% detection at 5%
false alarms, pasted dents are at chance, and the rank baseline is worse than least squares. Adding the glint cue
helps a little in this sample; adding the silhouette cue does not. With 15 scenes per cell these differences are
within the confidence intervals; read the exact values from the table.

### 5.5 Abstention and hard conditions (E6)

{table("T4_verdicts_by_condition")}

{fig("F6_abstention.png", "F6. Verdict distribution by condition.")}

The intended behaviour (overcast gives INSUFFICIENT, two suns give CONFLICT) is mostly **not** observed.
Soft sky light shades a surface almost like a broad light from above, so overcast scenes keep a consistent "up"
direction and are usually called CONSISTENT; shading alone cannot tell the two apart, and a splice under
overcast light is not detected. Two-sun scenes rarely produce CONFLICT. We treat both as limits of the method.

### 5.6 Robustness (E7)

{fig("F7_robustness.png", "F7. Detection and false alarms under JPEG, resize and noise. The threshold is not re-fitted.")}

Down-scaling the image hurts most: detection drops sharply at every resize factor tested.

### 5.7 Ablations (E8)

{table("T5_ablations")}

{fig("F9_ablations.png", "F9. Ablations and arbiter feature importance.")}

Calibrating the posterior shape and the leave-one-out test both help; the reliability floor barely matters; the
gradient-boosted arbiter is not better than the explainable rule in this sample.

### 5.8 Real normal predictor in the loop (E10)

A smoke test on 2 scenes, not a measurement; see `data/results/e10_real_normals.json` for what ran.

### 5.9 Real photos (qualitative)

Six unedited outdoor car photos from Wikimedia Commons and one splice made from them (a rectangle of one photo
pasted into another, audited with the paste mask as the region of interest). SAM regions, DSINE + Depth
Anything normal ensemble, alarm level calibrated on synthetic scenes only:

{real_rows()}

Among the six unedited photos one is flagged (a false alarm); with the earlier rank cue and a single normal
estimator four of the six were flagged. The splice (`real_splice_*`), which the earlier configuration flagged,
is **not** flagged now. So the current settings are quieter on real photos but also miss the one real splice we
tried. Seven images prove nothing either way: real-photo use needs a recalibration on real unedited photos
(`tools/calibrate_on_folder.py`) and a proper test set.

## 6 Attack evaluation and discussion

{fig("attack_ladder.png", "I8. Attack tiers and what each can move.")}

{attack_rows()}

{table("T6_attacks")}

{fig("F8_attacks.png", "F8. Detection by attack tier, shading only against all cues.")}

Colour and brightness harmonisation (T1) leaves the pooled detection rate about where it was, although with the
least-squares cue it can flip individual cases (the spliced-car demo passes after colour transfer; the rank cue
was immune to that by construction). A physics re-shade (T3a) defeats the detector almost completely, even when
the forger's estimate of the scene light is 20 degrees off, and the highlight and silhouette cues recover only a
few percent. The re-shade changes the region's brightness noticeably (see the mean |dY| column), which is the
forger's cost. Caveat: the defender's simulated normals do not react to the edit, the best case for the attacker.

## 7 Limitations and ethics

{LIMITS}

{fig("triage.png", "I9. The four verdicts and the recommended action.")}

Further limits found in this work: the rank cue we proposed loses to a simple least-squares fit; the alarm level
that keeps false alarms at 5% on synthetic scenes misses many splices; small or shallow regions such as dents
carry too little evidence; overcast and two-light scenes are not recognised as such. A tool like this must not
be used to accuse anyone: it produces one signal for a human reviewer.

## 8 Conclusion

We built a complete, inspectable lighting-consistency auditor with an interactive 3D evidence viewer and a
self-attack lab, and evaluated it honestly. The viewer and the analysis-by-synthesis views do what they were
designed to do. The detector itself is modest: the rank cue we proposed was less accurate than least squares
and was replaced as the default, detection still needs large lighting discrepancies, re-shading defeats it, and
real-photo behaviour is untested beyond seven images. The most useful next steps are a full-size evaluation,
calibration and testing on real photos, and an explicit test for soft or multiple light sources.

## References

See [docs/LITERATURE.md](../docs/LITERATURE.md).

## Appendix: reproduction

- Hyperparameters: `lightaudit/config.py`; calibration: `lightaudit/calib_default.json`.
- Seeds: calibration 1000-1199, arbiter 2000-2199, test 3000-3299, demo 4000-4099.
- Commands: `setup.ps1`, then `run_all.ps1` (or `-Quick`); individual steps are listed in `README.md`.
- What was actually run, and every deviation from the build spec: `BUILD_LOG.md`.
"""
    out = ROOT / "report" / "REPORT.md"
    out.write_text(text, encoding="utf-8")
    print(f"wrote {out}")
    return out


if __name__ == "__main__":
    main()
