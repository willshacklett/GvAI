# GV Hypergraph / Manifold Adversarial Result

## Purpose

Attack scalar GV with topology evolution and hidden delayed collapse.

## Result

`GV_SCALAR_SURVIVES_HYPERGRAPH_TEST`

## Metrics

| Metric | Value |
|---|---:|
| base PC1 explained variance | 0.965623 |
| topology PC1 explained variance | 0.881227 |
| full PC1 explained variance | 0.910916 |
| GV correlation with base PC1 | 0.985451 |
| GV correlation with topology PC1 | 0.870754 |
| GV correlation with full PC1 | 0.992052 |
| max local-global gap | 0.895766 |
| late local GV | 0.934518 |
| late global GV | 0.207772 |
| late fragmentation | 0.092437 |
| late beta1 cycles | 8.571429 |

## Interpretation

If GV aligns with base recoverability but not topology, scalar GV may be incomplete.

If full PC1 remains dominant and GV aligns with it, scalar GV survives this first topology attack.

If full PC1 collapses, recoverability likely requires multi-axis geometry.

## Scientific line

This does not prove GV universal.

It tests whether scalar GV survives topology evolution, hidden strain, and hypergraph fragmentation.
