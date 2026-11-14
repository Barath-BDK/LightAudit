# Related work

This is the short list of work that LightAudit builds on, compares against, or explicitly leaves for later. Entries marked **(recalled)** were written from memory without a verified link. **Please check recalled entries (authors, year, venue) before citing them.** Links without the mark were supplied in the project brief; we did not re-verify every one of them either, so a quick check before final submission is still a good idea.

| Topic | Work | Link | How it relates to LightAudit |
|---|---|---|---|
| Lighting forensics (2D contour light, spherical-harmonic environment) | Johnson & Farid, 2005 / 2007 **(recalled)** | — | The original idea of comparing light directions estimated from different objects. Our contour cue C3 (normals in the image plane at occluding contours) comes from this line of work. |
| Lighting forensics with cast shadows | Kee, O'Brien & Farid, *ACM TOG* 2013 | https://farid.berkeley.edu/downloads/publications/tog13/tog13.pdf | Shadow constraints on the light; our manual shadow-pair cue C4 uses the same "lines through object point and shadow point meet at the light" geometry. |
| Lighting forensics with shading + shadows | Kee, O'Brien & Farid, *ACM TOG* 2014 | https://farid.berkeley.edu/downloads/publications/tog14.pdf | Constraint view of light estimation (each observation restricts the light to a half-space). Our rank cue C1 is a half-space voting method of the same kind, with the radiometric model replaced by an unknown monotone curve. |
| Multi-cue sun estimation | Lalonde, Efros & Narasimhan, 2009 / 2012 | https://ri.cmu.edu/publications/estimating-natural-illumination-from-a-single-outdoor-image | Probabilistic combination of sky, shadow, ground and vertical-surface cues into a distribution over sun positions. Our per-region posteriors on the sphere and their log-sum fusion follow the same probabilistic idea. |
| Projective-geometry forensics of generated images | Sarkar et al., CVPR 2024, "Shadows Don't Lie and Lines Can't Bend" | https://arxiv.org/abs/2311.17138 | Shows that generated images violate shadow/perspective geometry. Related motivation; we do not target fully generated images. |
| Lighting in generated images | Farid, 2022, lighting in DALL·E 2 images | https://arxiv.org/abs/2207.13744 | Evidence that generators get lighting only approximately right. Supports our statement that whole-image generation is out of scope (it tends to be globally plausible). |
| Physical reflectance for deepfake detection | Light2Lie, NDSS 2026 | https://www.ndss-symposium.org/ndss-paper/light2lie-detecting-deepfake-images-using-physical-reflectance-laws | Recent physics-based detector; closest in spirit for the "use physics, not a black box" argument. |
| Learned forgery detection / localisation | TruFor | https://arxiv.org/abs/2212.10957 | Strong black-box baseline. Listed under "Later" in the build spec; not run in this project. |
| Explainable forensics with MLLMs | FakeShield | https://arxiv.org/abs/2410.02761 | Explanation produced by a language model. LightAudit instead generates its explanation by rules from the computed numbers only. |
| Anti-forensic attacks | Fang & Stamm, anti-forensic GAN attack on splicing detectors | https://arxiv.org/abs/2211.12314 | Example of attacking learned forensic detectors; motivates our self-attack evaluation. |
| Anti-forensic attacks | Pasquini et al., 2024, mimicry attacks **(recalled)** | — | Attacks that imitate the statistics a detector relies on; conceptually close to our T4 adaptive tier. |
| Learned relighting (attack tools, "Later") | DiffusionRenderer | https://arxiv.org/abs/2501.18590 | A forger could use it to relight a pasted region; not used here (spec section 3.2). |
| Learned relighting (attack tools, "Later") | Neural Gaffer | https://arxiv.org/abs/2406.07520 | Same as above. |
| Learned relighting (attack tools, "Later") | IC-Light **(recalled)** | — | Same as above. |
| Shadow-generating object insertion ("Later") | SGDiffusion | https://arxiv.org/abs/2403.15234 | Would let a forger add matching cast shadows; not evaluated. |
| Shadow-generating object insertion ("Later") | ObjectDrop | https://arxiv.org/abs/2403.18818 | Same as above. |
| Lighting estimation network | SOLID-Net | https://arxiv.org/abs/2104.04160 | Learned outdoor light estimation; an alternative front end we did not use. |
| Surface-normal estimation | DSINE (CVPR 2024) **(recalled, no link given)** | — | One of the optional normal backends for real photos. |
| Surface-normal estimation | StableNormal | https://arxiv.org/abs/2406.16864 | Optional normal backend for real photos. |
| Surface-normal estimation | Lotus-2 | https://arxiv.org/abs/2512.01030 | Recent normal estimator in the same accuracy band; not integrated. |
| Dataset | CarDD (car damage detection) | https://arxiv.org/abs/2211.00945 | Real damage photos; optional / "Later" for applicability analysis. |
| Statistics | Han, 1987, maximum rank correlation estimator for single-index models **(recalled)** | — | Theoretical basis of C1: estimating the index direction of `Y = g(n·l)` with unknown monotone `g` by maximising a rank correlation. |
| Statistics | Split-conformal prediction (Vovk et al.; Lei et al., 2018) **(recalled)** | — | Basis of the alert threshold: a quantile of pristine calibration scores bounds the false-alarm rate under exchangeability. |
| Image processing | Reinhard et al., 2001, colour transfer **(recalled)** | — | Used as attack tier T1 (Lab mean/std transfer to the surrounding ring). |

## What this project contributes, and what it does not

Lighting-inconsistency forensics (Johnson & Farid; Kee, O'Brien & Farid), multi-cue probabilistic light estimation (Lalonde et al.) and relighting as an attack on detectors all exist already. The contribution of LightAudit is an engineering and evaluation one:

- a **tone-curve-invariant rank-based shading cue** (C1) that drops the linear-radiometry and albedo assumptions of least-squares light fitting;
- a **calibrated spherical-posterior formulation**: per-region block-bootstrap + KDE posteriors on a fixed sphere grid, credible regions calibrated for coverage, a **leave-one-out shortfall test**, and **abstention** (INSUFFICIENT / CONFLICT), with the alert level set by **split-conformal false-alarm control** on pristine scenes;
- a **multi-cue fusion** of shading, specular glints, silhouette edges and optional manual shadow pairs;
- a **counterfactual interactive viewer** (WebGL relighting, residual maps, a 3D light dome with live fusion);
- a **tiered self-attack evaluation** (colour transfer, physics re-shading with controlled attacker error, adaptive attack) with a minimum-detectable-inconsistency measure.

We did not complete a systematic literature review of attacks on *physics-based* forensic detectors using modern (learned) relighting. The claim above is therefore limited to what we know of the cited work; there may be prior work closer to ours that we missed.
