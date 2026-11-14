### T5 - E8 ablations (car target)

| ablation | AUC d>=30 | TPR@5%FPR d=90 | MDI (deg) | abstain pristine | abstain composites |
|---|---|---|---|---|---|
| rule, C1 (shading) | 0.69 [0.58, 0.79] | 0.47 [0.27, 0.87] | 135 | 0.13 | 0.13 |
| rule, C1+C2 | 0.71 [0.61, 0.81] | 0.67 [0.40, 0.87] | 60 | 0.13 | 0.13 |
| rule, C1+C2+C3 (default) | 0.67 [0.56, 0.77] | 0.47 [0.20, 0.73] | 135 | 0.13 | 0.13 |
| RANK baseline (shading) | 0.64 [0.51, 0.75] | 0.47 [0.20, 0.73] | 180 | 0.13 | 0.12 |
| KDE calibration off (h=10, T=1) | 0.65 [0.53, 0.78] | 0.27 [0.07, 0.60] | n/a | 0.13 | 0.12 |
| w_min = 0.25 | 0.67 [0.56, 0.77] | 0.47 [0.20, 0.73] | 135 | 0.13 | 0.13 |
| w_min = 0.50 | 0.67 [0.56, 0.77] | 0.47 [0.20, 0.73] | 135 | 0.13 | 0.13 |
| no leave-one-out (global consensus) | 0.64 [0.52, 0.76] | 0.33 [0.13, 0.60] | 180 | 0.13 | 0.13 |
| arbiter (C1+C2+C3) | 0.66 [0.53, 0.79] | 0.07 [0.00, 0.67] | n/a | 0.13 | 0.13 |
| region backend gt | 0.67 | TPR@tau 0.33, FPR@tau 0.00 | - | 0.00 | 0.00 |
| region backend slic | 0.78 | TPR@tau 0.33, FPR@tau 0.00 | - | 0.00 | 0.00 |

Suite quick; region-backend rows on 3+3 scenes. Caveat: synthetic scenes with simulated normal predictors unless stated.
