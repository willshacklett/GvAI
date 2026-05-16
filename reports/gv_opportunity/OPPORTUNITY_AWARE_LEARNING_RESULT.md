# GV Opportunity-Aware Learning Result

## Purpose

Test whether GV can learn from both damage and missed opportunity.

## Summary

| System | Steps Survived | Extinct | Discoveries | Final Escape | Final Basin | Missed Total | Min Truth | Min Constraint | Min Coherence | Mean Survivability | Final Survivability |
|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| strict_viability | 620 | False | 0 | 0.05 | 0.049959 | 0.365087 | 0.91475 | 0.915213 | 0.929104 | 0.649317 | 0.627497 |
| antifragile_escape | 620 | False | 0 | 0.9 | 1.0 | 0.0 | 0.908443 | 0.94566 | 0.928931 | 0.95112 | 0.976684 |
| fixed_gv_escape | 620 | False | 2 | 0.82 | 0.990386 | 0.0 | 0.916586 | 0.928757 | 0.927283 | 0.952568 | 0.980516 |
| damage_only_gv_learning | 620 | False | 1 | 0.627142 | 0.995129 | 0.0 | 0.927959 | 0.946165 | 0.932231 | 0.920397 | 0.989203 |
| opportunity_aware_gv | 620 | False | 2 | 0.640576 | 0.994618 | 0.0 | 0.932276 | 0.934087 | 0.929505 | 0.948621 | 0.979389 |

## Winner

`fixed_gv_escape`

## Interpretation

Damage-only learning can become overprotective.

Opportunity-aware GV treats missed basin discovery as a real survivability loss.

The goal is not maximum safety or maximum novelty.

The goal is survivable exploration.

## Strong GV Base

> Universal survivability requires learning the boundary between destructive unrecoverability and necessary kernel escape.
