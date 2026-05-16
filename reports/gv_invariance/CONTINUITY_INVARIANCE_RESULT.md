# GV Continuity Invariance Result

## Purpose

Test whether GV preserves continuity ordering under harmless representation changes better than random projections.

## Final Result

`GV_FAILS_CONTINUITY_INVARIANCE`

## Transformation Results

| Mode | GV Rank Stability | GV Violation Rate | Random Avg Stability | Random P95 Stability | Random Avg Violation | Random P05 Violation | Result |
|---|---:|---:|---:|---:|---:|---:|---|
| scale | -0.906182 | 0.0 | 0.008503 | 0.954376 | 0.497281 | 0.073869 | GV_NOT_INVARIANT_BEYOND_RANDOM |
| monotonic | -0.762056 | 0.736766 | -0.045876 | 0.95751 | 0.519854 | 0.0724 | GV_NOT_INVARIANT_BEYOND_RANDOM |
| noise | -0.747252 | 0.742625 | -0.0289 | 0.899552 | 0.511862 | 0.122893 | GV_NOT_INVARIANT_BEYOND_RANDOM |
| rotation | 0.830172 | 0.20146 | -0.023153 | 0.952319 | 0.510778 | 0.076526 | GV_ABOVE_AVERAGE_INVARIANCE |

## Interpretation

Random projections can correlate with low-dimensional data.

This test asks a harder question: does GV preserve continuity ordering under transformations that should not change meaning?

If GV fails here, it is not yet behaving like a foundational invariant.

If GV survives here, it earns a stronger claim than PC1 correlation.
