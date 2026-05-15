# GV Transition Persistence Filter

## Battle

Reduce false transitions on stable traces without killing transition sensitivity.

## Rule

Single-point transition signals are not enough.

A GV transition candidate must persist across a short run of nearby points.

Current filter:

- minimum run length: 3
- allowed gap: 1

## Why

A true recoverability transition should not look like a one-off flicker.

If it is real, it should persist.

If this kills real transition traces, GV loses this battle.
