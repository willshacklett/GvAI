# GV Alpha Phase Boundary Result

## Result

GV alpha-space produced a clear behavioral boundary.

## Observed regions

| Alpha region | Behavior |
|---|---|
| below ~0.75 | under-sensitive |
| 0.75–0.85 | useful discriminating region |
| at/above ~0.90 | false-positive boundary begins |

## Best current operating region

`0.75–0.85`

## Why this matters

This is not tuning alpha to make GV pass.

This maps where GV changes behavior.

The useful scientific question is:

> What system conditions move alpha into or out of the stable discriminating region?

## Current evidence

At alpha threshold:

- `0.75`: 73% critical-slowing detection, 0% false positives
- `0.80`: 88% critical-slowing detection, 0% false positives
- `0.85`: 100% critical-slowing detection, 0% false positives
- `0.90`: 100% critical-slowing detection, 2% false positives

## Boundary statement

GV appears most useful when alpha sits below the false-positive transition but above the under-sensitive region.

Current synthetic boundary:

`0.75 <= alpha <= 0.85`

## Next validation

Test whether this alpha region survives:

- new noise regimes
- slower collapse
- faster collapse
- real service metrics
- model drift logs
- queue backlog data
- external datasets
