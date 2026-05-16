# GV Continuity Invariance Protocol

## Purpose

Move GV away from arbitrary projection comparison.

The question is no longer:

Does GV correlate with PC1?

The question becomes:

Does GV preserve continuity ordering under transformations that should not change recoverability meaning?

## Core idea

A foundational continuity scalar should be invariant under harmless representation changes.

If GV is real as a baseline continuity constraint, it should preserve ordering under:

- scale changes
- monotonic transformations
- feature rotations that preserve continuity relationships
- noise that does not alter recovery order

## What would make GV non-arbitrary?

GV becomes less arbitrary if it preserves recoverability ordering
better than random projections under invariance tests.

## Hostile condition

Random projections can correlate with PC1.

But random projections should struggle to preserve continuity ordering
across repeated transformations.

## Win condition

GV survives if:

- ordering stability is high
- pairwise rank violations are low
- GV beats random projections on invariance preservation

## Loss condition

GV fails if:

- random projections preserve ordering equally well
- GV ordering breaks under harmless transformations
- GV is only PC1 correlation dressed up as theory

## Scientific posture

This test does not prove GV.

It tests whether GV behaves like a continuity invariant rather than an arbitrary projection.
