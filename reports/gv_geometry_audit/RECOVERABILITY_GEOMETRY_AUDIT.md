# GV Recoverability Geometry Audit

## Purpose

Test whether GV is seeing a real dominant recoverability geometry or merely threading selected metrics.

## Results

| Source | PC1 Var | GV-PC1 Corr | Residual | Random Avg | Random Best | Result |
|---|---:|---:|---:|---:|---:|---|
| dominant_axis | 0.955444 | 0.998611 | 0.044556 | 0.868694 | 0.999666 | GV_NOT_DISTINCT_FROM_RANDOM_PROJECTION |
| panarchy | 0.942115 | 0.998445 | 0.057885 | 0.878389 | 0.999627 | GV_NOT_DISTINCT_FROM_RANDOM_PROJECTION |
| hypergraph | 0.950194 | 0.860845 | 0.049806 | 0.762194 | 0.997886 | GV_NOT_DISTINCT_FROM_RANDOM_PROJECTION |

## Interpretation

If GV correlation is not meaningfully better than random projection, GV may be metric-threading.

If PC1 dominates and GV aligns strongly beyond random projection, the geometry supports a dominant recoverability axis.

## Scientific posture

This audit is skeptical by design.

It does not prove GV.

It tests whether the geometry deserves continued attention.
