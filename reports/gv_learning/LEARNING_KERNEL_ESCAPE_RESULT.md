# GV Learning Kernel Escape Result

## Purpose

Test whether GV can learn when to risk kernel escape.

## Summary

| System | Steps Survived | Extinct | Discoveries | Final Escape | Final Basin | Min Truth | Min Constraint | Min Coherence | Mean Survivability | Final Survivability |
|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|
| strict_viability | 520 | False | 0 | 0.05 | 0.082363 | 0.922662 | 0.915213 | 0.929104 | 0.653302 | 0.649816 |
| antifragile_escape | 520 | False | 3 | 0.9 | 1.0 | 0.827304 | 0.851203 | 0.83775 | 0.930837 | 0.975231 |
| fixed_gv_escape | 520 | False | 2 | 0.82 | 1.0 | 0.916586 | 0.936132 | 0.932785 | 0.951374 | 0.970086 |
| gv_learning_escape | 520 | False | 2 | 0.684572 | 0.994489 | 0.930345 | 0.929443 | 0.927829 | 0.915261 | 0.981814 |

## Winner

`fixed_gv_escape`

## Interpretation

Strict viability avoids danger but misses higher basins.

Antifragile escape searches aggressively but accepts greater recoverability damage.

Fixed GV controlled escape preserves structure but uses a fixed escape posture.

GV learning escape updates its escape policy from success and damage.

## Strong GV Base

> Universal survivability may require learning when to risk unrecoverability, then recovering stronger.
