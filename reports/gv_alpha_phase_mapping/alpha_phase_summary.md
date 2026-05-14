# GV Alpha Phase Map

Purpose:

Map where GV behavior changes across alpha-space.

This is NOT parameter tuning.

Goal:
- identify stability regions
- identify false-positive transitions
- identify critical-slowing sensitivity boundaries
- identify detector failure regions

| alpha_threshold | critical_slowing_detection | false_positive_rate | abrupt_collapse_detection | avg_lead_time |
|---|---:|---:|---:|---:|
| 0.45 | 0.0% | 0.0% | 0.0% | 0.0 |
| 0.50 | 1.0% | 0.0% | 0.0% | 20.0 |
| 0.55 | 3.0% | 0.0% | 0.0% | 20.0 |
| 0.60 | 15.0% | 0.0% | 0.0% | 20.0 |
| 0.65 | 24.0% | 0.0% | 0.0% | 21.67 |
| 0.70 | 49.0% | 0.0% | 0.0% | 24.08 |
| 0.75 | 73.0% | 0.0% | 0.0% | 26.85 |
| 0.80 | 88.0% | 0.0% | 0.0% | 30.68 |
| 0.85 | 100.0% | 0.0% | 0.0% | 54.0 |
| 0.90 | 100.0% | 2.0% | 0.0% | 122.2 |

## Interpretation

Alpha-space defines behavioral regions.

Possible regions:

- under-sensitive stable region
- useful discriminating region
- over-sensitive false-positive region
- unstable detector region

The objective is not maximizing detection at all costs.

The objective is locating stable discriminating regions.
