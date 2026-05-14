# GV Baseline Scorecard

Purpose: compare GV against simpler detectors without protecting GV.

| Detector | True Positive Rate | False Positive Rate | Abrupt Miss Rate | Avg Lead Time |
|---|---:|---:|---:|---:|
| gv_recoverability | 49.0% | 0.0% | 100.0% | 24.08 |
| rolling_variance | 100.0% | 100.0% | 0.0% | 699.0 |
| rolling_z_score | 0.0% | 0.0% | 100.0% | 0.0 |

## Interpretation

- Rolling variance is too sensitive and false-alarms on stable/noisy recoverable systems.
- Rolling z-score is quiet but misses critical slowing.
- GV currently occupies the useful middle: low false positives with partial critical-slowing sensitivity.

## Current honest limitation

GV is not yet sensitive enough. It must improve critical-slowing detection without increasing false positives.
