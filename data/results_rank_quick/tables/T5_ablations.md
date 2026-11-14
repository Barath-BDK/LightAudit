### T5 - E8 ablations (car target)

| ablation | AUC d>=30 | TPR@5%FPR d=90 | MDI (deg) | abstain pristine | abstain composites |
|---|---|---|---|---|---|
| rule, C1 (shading) | 0.62 [0.51, 0.73] | 0.40 [0.13, 0.67] | 180 | 0.13 | 0.14 |
| rule, C1+C2 | 0.64 [0.51, 0.74] | 0.40 [0.13, 0.73] | n/a | 0.13 | 0.14 |
| rule, C1+C2+C3 (default) | 0.65 [0.52, 0.77] | 0.40 [0.13, 0.67] | 180 | 0.13 | 0.12 |
| LS baseline (shading) | 0.71 [0.61, 0.81] | 0.67 [0.40, 0.87] | 90 | 0.13 | 0.12 |
| KDE calibration off (h=10, T=1) | 0.53 [0.37, 0.69] | 0.07 [0.00, 0.40] | n/a | 0.13 | 0.13 |
| w_min = 0.25 | 0.65 [0.52, 0.77] | 0.40 [0.13, 0.67] | 180 | 0.13 | 0.12 |
| w_min = 0.50 | 0.65 [0.51, 0.76] | 0.40 [0.13, 0.67] | 180 | 0.13 | 0.12 |
| no leave-one-out (global consensus) | 0.58 [0.43, 0.72] | 0.33 [0.13, 0.60] | n/a | 0.13 | 0.12 |
| arbiter (C1+C2+C3) | 0.67 [0.55, 0.79] | 0.33 [0.13, 0.73] | 180 | 0.13 | 0.12 |
| region backend gt | 0.78 | TPR@tau 0.67, FPR@tau 0.00 | - | 0.00 | 0.00 |
| region backend slic | 0.89 | TPR@tau 0.67, FPR@tau 0.00 | - | 0.00 | 0.00 |

Suite quick; region-backend rows on 3+3 scenes. Caveat: synthetic scenes with simulated normal predictors unless stated.
