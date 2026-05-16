# GV Adaptive Runtime Result

## Purpose

Test whether adaptive escalation preserves continuity better than passive observation.

## Summary

| Agent | Min GV | Final GV | WATCH | RECOVER | CONSTRAIN | FAILSAFE | Final Autonomy | Escalation |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| recoverable_runtime | 0.848801 | 0.974758 | 0 | 0 | 0 | 0 | 1.0 | 0 |
| truth_drift_runtime | 0.794697 | 0.907034 | 5 | 0 | 3 | 0 | 0.551368 | 6 |
| constraint_drift_runtime | 0.797873 | 0.936013 | 3 | 0 | 2 | 0 | 0.6724 | 4 |
| collapse_prone_runtime | 0.722193 | 0.893198 | 0 | 19 | 2 | 0 | 0.6724 | 23 |

## Interpretation

This runtime changes future behavior when continuity degrades.

Constraint and truth degradation reduce autonomy and increase escalation.

The runtime attempts continuity preservation instead of passive observation.

## Foundation

> Intelligence needs recoverable continuity.
