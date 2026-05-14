# GV Falsification Result — Dynamic Recovery Harness

## Status

First clean mechanism result achieved.

## Core finding

GV warns when recoverability degrades persistently and does not self-correct.

GV stays quiet when disturbance is recoverable.

GV does not warn before abrupt collapse when no recoverability decay exists beforehand.

## Current result

Across 100 random seeds:

| Scenario | Result |
|---|---|
| stable_dynamic | 100/100 quiet |
| noisy_dynamic_recoverable | 100/100 quiet |
| critical_slowing_dynamic | 100/100 early warning |
| abrupt_collapse_dynamic | 100/100 missed |

## Interpretation

This defines a boundary:

GV is not a magic predictor.

GV is a recoverability-loss detector.

It can warn before collapse only when collapse is preceded by measurable degradation in the system's ability to return after disturbance.

## Mechanism

The current warning rule requires:

1. GV threshold pressure or recovery-time doubling
2. persistent degradation
3. failure to self-correct during cooldown

This separates:

- temporary noise
- recoverable disturbance
- persistent loss of recoverability

## Scientific statement

If a system's recovery capacity weakens before visible collapse, GV can detect that weakening before collapse.

If a system collapses abruptly without prior recovery degradation, GV should not be expected to warn.

## Next validation target

Move from synthetic systems to real or semi-real time series:

- infrastructure incidents
- model drift
- queue latency
- service recovery logs
- biological recovery curves
- economic stress data

The next test should preserve the same principle:

Do not tune GV to the dataset.

Measure whether recoverability degradation appears before failure.
