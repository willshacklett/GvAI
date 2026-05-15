# GV Universal Scalar Contract

## Claim

GV is being tested as a universal scalar candidate.

Not universal because it explains everything.

Universal only if different domains can map into the same scalar contract without domain-specific rescue logic.

## Scalar range

0 <= GV <= 1

Where:

- 1.0 = high continuity / recoverability reserve
- 0.0 = degraded or lost recoverability

## Required evidence fields

Every domain must reduce to the same normalized evidence structure:

| Field | Meaning |
|---|---|
| recovery_strength | ability to return after disturbance |
| persistence | whether degradation self-corrects |
| directional_degradation | whether state is materially moving toward failure |
| volatility_penalty | instability pressure, secondary only |

## Scientific rule

A domain is not allowed to rewrite GV.

A domain may only translate its evidence into the universal contract.

If a domain requires custom rescue logic, GV fails universality for that domain.

## Current universal candidate

GV = 0.40 recovery_strength
   + 0.35 persistence
   + 0.20 directional_degradation
   + 0.05 (1 - volatility_penalty)

## What would prove useful universality?

GV must preserve ordering across domains:

- stable / recoverable systems score high
- transient noise scores high or recovers
- persistent degradation scores lower
- irreversible loss scores lowest

## What would falsify universality?

- stable systems repeatedly score low
- failed systems repeatedly score high
- each domain requires custom weights
- simple baselines outperform GV everywhere
- GV cannot preserve rank ordering across domains\n