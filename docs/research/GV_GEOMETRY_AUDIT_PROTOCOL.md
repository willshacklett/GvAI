# GV Recoverability Geometry Audit

## Purpose

Test whether GV is discovering real low-dimensional recoverability structure
or whether we are accidentally threading the needle with selected metrics.

## Skeptical posture

Do not trust GV.

Do not trust the framing.

Do not trust AI interpretation.

Measure the geometry directly.

## Core question

Is recoverability actually low-dimensional in the generated evidence,
or are we choosing observables that force low-dimensional results?

## Audit tests

- PCA explained variance
- eigenvalue decay ratio
- GV correlation with dominant component
- residual variance after PC1
- correlation between GV and residual dimensions
- baseline comparison against random scalar projections

## Interpretation

If PC1 dominates and GV aligns with PC1 while residuals remain weak,
GV may be capturing a real dominant recoverability axis.

If residuals are strong or random projections perform similarly,
GV may be metric selection / needle-threading.

## Rule

This audit does not protect GV.

It measures whether the geometry supports GV.
