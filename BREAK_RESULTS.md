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

---

# Third Test Direction

This version makes the GV equation structure the base of the harness:

`Gv = integral(rho_total(x,t)) + alpha`

Operationally:

- `rho_total` = recoverability density
- `alpha` = continuity anchor
- the integral is approximated as recent mean recoverability density

`rho_total` is currently composed of:

- recovery success
- recovery speed
- recovery slowing trend
- drift away from baseline

The goal is not to protect the equation.

The goal is to make the equation executable so it can be broken.

---

# Fourth Test Direction

The equation-base harness fixed false positives but still warned too late.

New addition:

`rho_total` now includes an early-warning slope term.

Meaning:

- if recovery still succeeds but takes longer over time, GV should drop earlier
- full recovery failure is no longer required before warning
- slowing recovery is treated as loss of recoverability density

This directly tests whether critical slowing down belongs inside the GV equation.

---

# Fifth Test Direction

This adds the core scientific GV test:

`critical_slowing_before_collapse`

The visible signal remains near baseline before collapse, but the recovery force weakens over time.

This tests the key claim:

GV should detect loss of recoverability before visible collapse.

If GV cannot warn on this scenario, the current equation is missing the central mechanism.

---

# Test Design Finding

The critical slowing scenario exposed a harness flaw.

Disturbances were injected after the signal was already simulated.

That means the system was not dynamically recovering from stress. It was only showing one-point spikes.

Next correction:

Disturbances must be injected during the system update loop so recovery force actually controls the return to baseline.

---

# Sixth Test Direction

This adds a dynamic recovery harness.

Key correction:

Disturbances are injected inside the system update loop.

That means recovery force now controls actual return behavior after stress.

This test separates:

- stable dynamic recovery
- noisy but recoverable dynamics
- critical slowing before collapse
- abrupt collapse without early warning

---

# Seventh Test Direction

The dynamic harness showed the first real signal:

In `critical_slowing_dynamic`, recovery time increased before collapse.

But trial spacing was too coarse:

`TRIAL_EVERY = 60`

So GV did not sample recoverability often enough to warn before collapse.

Next correction:

`TRIAL_EVERY = 20`

This tests whether GV failed because the equation was wrong or because measurement resolution was too low.
