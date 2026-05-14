# GV Regime Stability Result

## Result

GV detection appears precursor-strength limited, not primarily noise-limited.

## Key finding

Across alpha values `0.75`, `0.80`, and `0.85`, GV stayed stable across noise regimes once recovery weakening was strong enough.

## Observed boundary

| Slowing strength | Result |
|---|---|
| 0.0005 | no reliable detection |
| 0.0010 | reliable detection begins |
| 0.0015 | strong detection |
| 0.0020 | strong detection with longer lead time |

## Boundary statement

GV detects persistent recoverability degradation when the degradation exceeds a measurable precursor-strength threshold.

Current synthetic lower bound:

`slowing_strength ≈ 0.0010`

## Current limitation

GV does not detect weak precursor degradation at `0.0005`.
