# GV Directional Degradation Filter

## Battle

Reduce false transitions on stable and oscillating traces.

## Problem

Persistence alone is not enough.

Stable drift and oscillation can still create repeated candidate points.

## New rule

A GV transition candidate must show:

1. persistence
2. nearby grouping
3. directional net degradation

Current filter:

- minimum run length: 3
- allowed gap: 1
- minimum net change across candidate group: 8.0

## Win condition

Stable traces should quiet down.

Oscillation should quiet down.

Gradual and collapse transition traces should remain detectable.

## Rule

If this filter kills true transition traces, GV loses this battle.
