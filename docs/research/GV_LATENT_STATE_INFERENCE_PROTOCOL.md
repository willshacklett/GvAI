# GV Latent State Inference Protocol

## Purpose

Attack the idea that observable continuity can reveal hidden recoverability structure.

This protocol explicitly avoids assuming GV is correct.

## Core question

Can hidden recoverability degradation be inferred from observable behavior alone?

## Important distinction

GV does not directly observe hidden state.

GV only observes:
- disturbance response
- recovery lag
- persistence
- directional degradation
- volatility
- hysteresis

The test is whether those observables contain enough information
to infer latent degradation better than naive baselines.

## Hostile posture

The hidden layer is intentionally partially masked.

Observable performance may remain temporarily stable
while hidden degradation accumulates.

## Competing explanations

Possible outcomes:

1. GV inference works
2. simple moving averages work equally well
3. random noise dominates
4. hidden state is fundamentally unidentifiable
5. multiple hidden states collapse into the same observable pattern

## Win condition

GV survives only if:
- inferred latent degradation tracks true hidden degradation
- lead time emerges before visible collapse
- inference beats naive baselines
- performance survives noise and masking

## Loss condition

GV loses if:
- inference collapses under masking
- baseline methods perform equally well
- hidden degradation remains unrecoverable from observables
- no stable mapping exists

## Scientific posture

Best break wins.
