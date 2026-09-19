# GVAI Safety Systems Integration Boundary

GVAI and GVAI Safety Systems are separate products. This repository provides
only the boundary in `gvai.safety_boundary`; it does not embed or claim to run
the Safety Systems implementation.

## Decision contract

Future consequential actions must call `SafetySystemsBoundary.decide` before
execution. The action name and minimum public context are passed to an
external decider, which returns one of:

- `allow`
- `deny`
- `warn`
- `unavailable`

An unconfigured boundary returns `unavailable`. GVAI must not describe an
action as governed when the boundary is unavailable. The external service may
define authentication, authorization, audit, policy, and failure behavior
independently.

## Scope

Public labor evidence reads and public job-listing retrieval are ordinary read
operations. Applying at source in Live Jobs V1 is navigation only: GVAI opens
the original provider URL and does not submit an application, transmit Worker
Profile data, contact an employer, modify an external record, or run an
autonomous agent action.

Any future implementation of those consequential actions must pass through
this boundary first. Worker Profile data must not be included in a job-provider
search request or in the minimum context sent for governance unless a future
product contract explicitly authorizes that use.