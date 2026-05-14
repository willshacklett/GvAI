# GV War Room Baseline Tournament

## Purpose

Test whether GV transition detection is actually useful against boring baselines.

## Detectors

- GV transition detector
- rolling z-score
- rolling variance

## Candidate counts

| Detector | Candidate Points |
|---|---:|
| GV transition | 4 |
| Rolling z-score | 6 |
| Rolling variance | 7 |

## Overlap

| Measure | Count |
|---|---:|
| GV unique hits | 1 |
| GV overlap with boring baselines | 3 |

## Battle checks

| Check | Result |
|---|---|
| More selective than z-score and variance | PASS |
| Has at least one unique hit | PASS |

## Battle result

`GV_SURVIVED_THIS_BATTLE`

## Rule

If GV is not more selective, it loses.

If GV is only a subset of boring baselines, it has not yet earned distinct value.

Fast is allowed. Hidden rescue logic is not.
