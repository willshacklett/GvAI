# GV Transition Baseline Comparison

## Purpose

Compare GV transition behavior against simple baselines.

## Results

| Detector | Candidate Points |
|---|---:|
| GV transition detector | 4 |
| Rolling z-score | 6 |
| Rolling variance | 7 |

## Interpretation

GV should ideally:

- remain more selective than naive variance
- remain more transition-focused than raw z-score
- avoid flagging the entire trace

## Current outcome

GV transition detector candidate points:

[40, 41, 42, 43]

Rolling z-score candidate points:

[10, 11, 35, 36, 44, 45]

Rolling variance candidate points:

[37, 38, 39, 40, 41, 42, 45]
