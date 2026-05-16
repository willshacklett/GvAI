# GV Order-Invariant Continuity Result

## Purpose

Test GV without tuned scalar weights.

Instead of optimizing an equation, this measures whether pairwise continuity order survives transformations.

## Final Result

`GV_ORDER_INVARIANT_SURVIVES`

## Results

| Mode | Order Survival | Flip Rate | Null Avg Survival | Null P95 Survival | Null Avg Flip | Null P05 Flip | Result |
|---|---:|---:|---:|---:|---:|---:|---|
| scale | 1.0 | 0.0 | 0.427035 | 0.469972 | 0.426391 | 0.380847 | ORDER_INVARIANT_BEYOND_NULL |
| monotonic | 1.0 | 0.0 | 0.426816 | 0.468785 | 0.426842 | 0.385156 | ORDER_INVARIANT_BEYOND_NULL |
| noise | 0.832086 | 0.06478 | 0.426229 | 0.471042 | 0.427047 | 0.382478 | ORDER_INVARIANT_BEYOND_NULL |
| rotation | 0.561155 | 0.251988 | 0.425044 | 0.468317 | 0.428076 | 0.382361 | ORDER_INVARIANT_BEYOND_NULL |

## Interpretation

This test removes weighted tuning.

GV is tested as a preserved continuity order relation.

If this survives, GV becomes less arbitrary than a scalar projection.

If this fails, the current continuity relation is not yet invariant.
