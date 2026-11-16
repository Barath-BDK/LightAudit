# Options for better real-image performance (research brief, 16 Nov 2026)

Ranked by **expected value for LightAudit**: whether it worked in published or measured tests, whether it
attacks our measured weak points (`HANDOVER.md` §6, §8: predicted normals, unknown paint, whole-object splices,
untested on real cars), and whether it runs here (Windows, CPU only; package installs need the user).

"Proven" means a published evaluation on real photos or a measurement in this repository.

| # | Option | Proven? | Fixes which weak point | Runs here? | Expected value |
|---|---|---|---|---|---|
| 1 | **Real dents from CarDD** as a clean test set for the marked-area check | dataset (4,000 photos, dent masks) | the check is untested on real damage; the reviewer's dent-rim risk (`seam_test.md`) | yes (download; Flickr/Shutterstock terms, academic use) | **very high**: the only way to know the real false-alarm rate |
| 2 | **Learned intrinsic decomposition** (Careaga & Aksoy, TOG 2023/2024, `compphoto/Intrinsic`) instead of Retinex | yes, in-the-wild benchmarks; not for forensics | paint vs shading (our Retinex is the crux: 0.74→0.86 AUC when guarded) | `pip install` from GitHub, CPU slow but feasible; academic-only licence | **high**, if it does not explain the paste edge away as paint (must use the same boundary guard idea) |
| 3 | **Cast-shadow geometry** (Kee, O'Brien & Farid, TOG 2013): object↔shadow constraints, LP feasibility | yes, on real photos; used in practice | whole-object splices; needs **no normals** | manual version exists (C4 shadow pairs); LP is a few lines with scipy | **high** for outdoor cars (they always cast shadows); manual annotation needed |
| 4 | **Automatic object–shadow pairing** (LISA CVPR 2020, SSIS/SSISv2, `stevewongv/SSIS`) to feed option 3 | yes, on SOBA (1,000 real photos) | removes the manual step of option 3 | detectron2 on Windows CPU is hard to install | medium: worth it only after option 3 works by hand |
| 5 | **Illuminant-colour maps** (Riess & Angelopoulou 2010; de Carvalho et al., TIFS 2013; Pomari et al., ICIP 2018) | yes: AUC 0.86 on DSO-1 (real splices of people), 0.83 cross-dataset; deep variant reports ~96% | foreign splices shot under a different light colour; needs **no normals** | pure numpy (inverse-intensity chromaticity / grey-edge per region) | medium-high for real-life pastes from other photos; useless for same-colour relighting; sun vs sky-shade regions differ in colour on their own, so compare like with like; colour transfer weakens it |
| 6 | **Seam test** (ours, `seam_test.md`) | measured here: no gain on plain pastes at matched false alarms; **+10 points on colour-matched pastes at 10% false alarms** (interval −1 to +15) | colour/brightness matching; normals | done | medium; stress test (feathering, Poisson blending, loose marking) decides whether it stays |
| 7 | **General learned forgery detector as a second opinion** (TruFor, CVPR 2023, Noiseprint++) | yes, strong on real benchmarks, robust to social-media compression | catches pastes by camera-noise traces, not light; complements every lighting test | weights public (research licence), CPU minutes per photo | high detection value, low fit to the course's "lighting" theme; best as an explicit baseline/second opinion |
| 8 | **Newer normal predictors** (Lotus 2024 one-step diffusion; StableNormal; Marigold) | yes, zero-shot benchmarks; GeoBench notes discriminative models (DSINE) often still win on numbers | the normals weak link | needs `diffusers` (user install); Lotus-D is one step, so CPU-feasible | medium-low: uncertain gain over Depth Anything / DSINE; test on the gray balls first (`real_bench.py ball`) |
| 9 | **Inharmonious-region localisation** (DIRL 2021, MadisNet 2022, `bcmi/*`) | yes on iHarmony4 (IoU ~0.68–0.74) | regions whose colour/tone does not fit | PyTorch, CPU OK | low-medium: trained on colour composites, not light direction; beaten by harmonisation |
| 10 | **Reflections / highlights on car paint** (Johnson & Farid's highlight and reflection geometry) | proven for eyes and known shapes; no car paper found | whole-object splices on glossy cars | glint cue (C2) exists | low-medium: research risk, manual |
| 11 | **Local light estimators** (Garon et al. CVPR 2019; DiffusionLight CVPR 2024) | yes for relighting quality, not forensics | estimate light at the object and at the scene and compare | Garon: no public code; DiffusionLight needs SDXL + GPU | low here |
| 12 | **Outdoor sun / sky models** (Hold-Geoffroy et al. CVPR 2017; Lalonde et al.) | yes for whole-image sun estimation | outdoor car scenes | model availability unclear; one estimate per image, not per object | low |
| 13 | **Face-based 3-D lighting** (Kee & Farid 2010; Peng et al. TIFS 2017) | yes, for faces | — | — | none: our photos have no faces |

## Recommended order

1. CarDD clean dents through `cli audit` in panel mode → real false-alarm rate (and the dent-rim risk).
2. Option 3 by hand on the outdoor photos in `data/real` (Route C), since the whole-object check is the part
   that fails and shadows need no normals.
3. Option 2 as a drop-in for `residual.retinex_albedo`, measured with `eval/mit_panel.py` / `eval/mit_attack.py`.
4. Option 5 as a cheap extra region cue for foreign pastes, with a set of real cross-photo splices.
5. Option 7 as a reported baseline in the results report.

## Sources

Kee, O'Brien & Farid 2013 (https://farid.berkeley.edu/downloads/publications/tog13/tog13.pdf);
Kee, O'Brien & Farid 2014 (https://farid.berkeley.edu/downloads/publications/tog14.pdf);
de Carvalho et al. 2013 (https://faui1-files.cs.fau.de/public/publications/mmsec/2013-de-Carvalho-EDI.pdf);
Riess & Angelopoulou 2010 (https://faui1-files.cs.fau.de/public/publications/mmsec/2010-Riess-SIA.pdf);
Careaga & Aksoy (https://github.com/compphoto/Intrinsic, https://yaksoy.github.io/ColorfulShading);
Instance shadow detection (https://arxiv.org/abs/1911.07034, https://github.com/stevewongv/SSIS);
TruFor (https://arxiv.org/abs/2212.10957); Lotus (https://arxiv.org/abs/2409.18124);
MadisNet (https://arxiv.org/abs/2209.15368); CarDD (https://arxiv.org/abs/2211.00945);
Garon et al. 2019 (https://openaccess.thecvf.com/content_CVPR_2019/html/Garon_Fast_Spatially-Varying_Indoor_Lighting_Estimation_CVPR_2019_paper.html);
DiffusionLight (https://diffusionlight.github.io); Hold-Geoffroy et al. 2017 (https://arxiv.org/abs/1611.06403);
Peng et al. 2017 (https://dblp.org/rec/journals/tifs/PengWDT17).
