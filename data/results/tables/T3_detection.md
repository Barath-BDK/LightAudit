### T3 - E4/E5 detection by target and cue set

| target | cues | MDI@5%FPR (deg) | MDI@tau (deg) | TPR@5%FPR d=90 | FPR@tau | AUC d>=30 | top-1 loc. | n pos per delta / n neg |
|---|---|---|---|---|---|---|---|---|
| car | C1 | 180 | n/a | 0.40 [0.13, 0.67] | 0.00 | 0.62 [0.45, 0.79] | 0.62 | 15/15 |
| car | C1+C2 | n/a | n/a | 0.40 [0.20, 0.73] | 0.07 | 0.64 [0.47, 0.79] | 0.63 | 15/15 |
| car | C1+C2+C3 | 180 | 180 | 0.40 [0.13, 0.67] | 0.13 | 0.65 [0.49, 0.80] | 0.61 | 15/15 |
| car | LS | 90 | 135 | 0.67 [0.40, 0.87] | 0.00 | 0.71 [0.55, 0.86] | 0.78 | 15/15 |
| distractor | C1 | 60 | n/a | 0.60 [0.33, 0.87] | 0.00 | 0.65 [0.50, 0.81] | 0.48 | 15/15 |
| distractor | C1+C2 | 135 | n/a | 0.47 [0.27, 0.80] | 0.07 | 0.66 [0.50, 0.81] | 0.47 | 15/15 |
| distractor | C1+C2+C3 | n/a | n/a | 0.47 [0.20, 0.73] | 0.13 | 0.65 [0.50, 0.80] | 0.39 | 15/15 |
| dent | C1 | n/a | n/a | 0.13 [0.00, 0.33] | 0.00 | 0.46 [0.25, 0.66] | 0.13 | 15/15 |
| dent | C1+C2 | n/a | n/a | 0.07 [0.00, 0.27] | 0.00 | 0.43 [0.25, 0.62] | 0.07 | 15/15 |
| dent | C1+C2+C3 | n/a | n/a | 0.00 [0.00, 0.27] | 0.07 | 0.40 [0.21, 0.59] | 0.13 | 15/15 |

Suite quick. 5%FPR threshold from the pristine TEST scores (labelled as such); tau = calibrated. 'fused' = C1+C2+C3: the shadow-pair cue C4 is manual-only (clicked in the viewer), so no automatic experiment can include it; 'fused' is therefore identical to C1+C2+C3. Caveat: synthetic scenes with simulated normal predictors unless stated.
