# GV Dominant Recoverability Axis Result

## Purpose

Test whether GV behaves like a dominant recoverability axis rather than claiming to explain every dimension.

## Result

`GV_ALIGNS_WITH_DOMINANT_AXIS`

## Metrics

| Metric | Value |
|---|---:|
| PC1 explained variance | 0.9554 |
| GV correlation with PC1 | 0.9986 |

## Interpretation

If PC1 explained variance is high, recoverability in this test set is mostly scalar-like.

If GV aligns strongly with PC1, GV is behaving like a dominant recoverability axis.

If PC1 explained variance is low, recoverability is fundamentally multi-axis in this set.

If GV correlation with PC1 is low, GV is not capturing the dominant axis.

## Scientific line

This does not prove GV is universal.

It tests whether GV is aligned with the leading recoverability structure across cross-domain evidence.

## Output

See:

`reports/gv_dominant_axis/dominant_axis_cases.csv`
