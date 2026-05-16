# GV Hostile Null-Model Isolation Result

## Purpose

Test whether GV is mathematically privileged or merely one of many projections on compressible data.

## Result

`GV_ABOVE_AVERAGE_BUT_NOT_PRIVILEGED`

## Main audit

| Metric | Value |
|---|---:|
| PC1 explained variance | 0.950194 |
| GV correlation with PC1 | 0.860845 |
| random projection average corr | 0.768444 |
| random projection p95 corr | 0.987845 |
| random projection best corr | 0.999497 |
| GV percentile vs random projections | 0.5395 |
| shuffled target average corr | 0.067858 |
| shuffled target best corr | 0.281805 |
| rotated feature corr | 0.860845 |
| rotated PC1 explained variance | 0.950194 |

## Noise tests

| Orthogonal noise level | GV-PC1 corr after noise | PC1 explained |
|---:|---:|---:|
| 0.05 | 0.859649 | 0.941192 || 0.1 | 0.85806 | 0.911858 || 0.25 | 0.861816 | 0.760994 || 0.5 | 0.819774 | 0.522655 |

## Interpretation

If GV does not beat random projections, it is not yet mathematically privileged.

If GV beats random projections under rotation and noise, it earns stronger attention.

## Scientific line

This test gives GV a fair chance without assuming it is true.

It does not settle metaphysics.

It tests whether the proposed continuity scalar survives hostile null models.
