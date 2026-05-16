# GV Core Order Attack Result

## Purpose

Keep the core intuition: persistent existence requires continuity.

Test that intuition as a non-weighted order relation, then attack it.

## Final Result

`CORE_CONTINUITY_ORDER_FAILS`

## Results

| Mode | Order Survival | Flip Rate | Cycle Rate | Incomparability Rate |
|---|---:|---:|---:|---:|
| baseline | 1.0 | 0.0 | 8e-05 | 0.121069 |
| scale | 1.0 | 0.0 | 8e-05 | 0.121069 |
| monotonic | 1.0 | 0.0 | 8e-05 | 0.121069 |
| noise | 0.798176 | 0.089453 | 0.00864 | 0.126619 |
| rotation | 0.147334 | 0.172007 | 0.00016 | 0.690647 |
| condorcet_attack | 0.787652 | 0.184051 | 0.03424 | 0.086845 |
| incomparability_attack | 0.463517 | 0.456034 | 0.0 | 0.070709 |

## Interpretation

GV is not tuned here.

The test preserves the core intuition by treating continuity as relational order.

Harmless transforms should preserve order.

Hostile transforms are allowed to break it.

A real foundation should not be invincible; it should show where it holds and where it fractures.
