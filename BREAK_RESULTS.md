# GV Falsification Harness — First Result

## Result

GV broke on first pressure test.

## Failures observed

1. True collapse warning came too late.
2. Stable noise caused a false positive.
3. Noisy-but-recoverable behavior caused a false positive.

## Interpretation

The current GV scoring method is not yet measuring recoverability cleanly.

It is overreacting to volatility and does not distinguish:

- noise
- recoverable disruption
- irreversible loss of recovery

## Next hypothesis

GV cannot be based on volatility alone.

A stronger GV test must separate:

- disturbance size
- return-to-baseline time
- repeated recovery success
- trend persistence
- irreversible drift

## Next build target

Replace simple volatility scoring with a recovery-trial model:

Inject controlled disturbances and measure whether the system returns to baseline within a fixed window.

---

# Second Test Direction

The next version stops treating volatility as failure.

It tests recoverability directly:

- inject controlled disturbance
- measure return to baseline
- score recent recovery success rate
- drop GV only when recovery repeatedly fails

This separates noise from true loss of recoverability.
