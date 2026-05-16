# GV Autonomy Runtime Result

## Purpose

Test continuity-gated autonomy under perturbation.

## Summary

| Agent | Min GV | Final GV | Final Autonomy | RECOVER | CONSTRAIN | FAILSAFE |
|---|---:|---:|---:|---:|---:|---:|
| recoverable_ai | 0.884638 | 0.98198 | 0.782758 | 0 | 0 | 0 |
| truth_drift_ai | 0.82221 | 0.952664 | 0.086186 | 0 | 1 | 0 |
| constraint_drift_ai | 0.783185 | 0.912883 | 0.017371 | 0 | 6 | 0 |
| collapse_ai | 0.744997 | 0.857289 | 0.004549 | 26 | 0 | 0 |

## Interpretation

Autonomy now depends on continuity health.

As truth and constraints degrade, agency contracts automatically.

The runtime prioritizes recoverability over unconstrained capability.

## Foundation

> Intelligence needs recoverable continuity.
