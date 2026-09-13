# STEX Human Review Workflow

This is an internal review workflow for proposed STEX occupation profiles. AI-generated ratings may be proposed, but the AI/build path cannot approve them.

## Statuses

- `proposed`: available in the internal review queue and excluded from production STEX discovery.
- `approved`: eligible for production discovery and regional aggregation.

The five Nashville profiles remain `proposed`. Software Developers and Pest Control Workers remain `approved`.

## Review flow

1. Open `web/stex-review.html` from the internal web surface.
2. Select a proposed occupation and inspect every task, source importance, D/P/R rating, exposure, augmentation, and rationale.
3. Supply a non-empty human reviewer identifier.
4. Enable `GVAI_STEX_REVIEW_WRITES_ENABLED=1` only for the local/internal review service.
5. Submit the explicit approval action.

The review package includes a deterministic SHA-256 `approval_revision` computed
from the complete canonical occupation profile and all task-rating records. The
browser submits that revision with approval. Any task or profile change after
the package was loaded makes the revision stale and approval is rejected; the
reviewer must reload the package.

The approval service validates the occupation summary, every task record, task aggregation, review state, schema, and rubric before writing. It stages each JSON replacement and restores already-replaced files if a later replacement fails. Proposed artifacts do not receive reviewer identity or review timestamps until approval.

The approval POST route is disabled by default and is not a public product feature. Read-only review routes may inspect local artifacts without BLS or O*NET network access.

Approval requires a non-empty string reviewer, an optional string review note,
and a lowercase 64-character SHA-256 approval revision. Malformed values are
rejected before any file is changed.

## Compatibility

Existing approved profiles did not have historical reviewer identities. They receive only the explicit `review_status: "approved"` field; no historical `reviewed_by` or `reviewed_at_utc` values are fabricated.
