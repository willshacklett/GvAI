# GVAI Private Build Mode

Private Build Mode is a universal GVAI capability.

It is not specific to GVAI's creators.

Every GVAI user can create private projects protected by the same policy.

## Fundamental rule

WORLD -> GVAI = ALLOWED

PRIVATE GVAI DATA -> WORLD = DENIED BY DEFAULT

## Private Build Mode

When enabled:

- GVAI can retrieve public web information.
- GVAI can retrieve research and public datasets.
- GVAI can receive market/economic information.
- Local GVAI models and tools can process project information.
- Private project information cannot be sent to an external AI.
- Private project information cannot be written to an outside service.
- Users can explicitly authorize selected information to leave.

## Architecture

Every external provider must eventually pass through:

PrivacyRouter
    |
    +-- local ------------ ALLOW
    |
    +-- world_read ------- ALLOW
    |
    +-- external_model --- POLICY CHECK
    |
    +-- external_write --- POLICY CHECK

The router is below the interface layer.

No future GVAI interface, agent, plugin, or AI provider should be able
to bypass the privacy gate.

## Philosophy

GVAI should have access to humanity's public knowledge without requiring
people to surrender ownership of their private ideas.

## Phase 1A: trusted external model authority (inactive integration)

`privacy.external_model_authority` supplies safely testable trusted-parent
interfaces only. It implements no authentication service, approval HTTP endpoint,
model adapter, or network transmission. No existing provider is switched on or
migrated, and no production configuration is changed.

### Missing human identity boundary

The project registry records privacy modes, not authenticated project ownership.
`PrivacyContext.user_id`, project IDs, environment variables and legacy consent
tokens are not evidence of human approval. The existing STEX review endpoint's
shared operator token protects STEX writes; it does not authenticate a named
human or approve external model payloads. It is deliberately not reused.

A future application integration must inject a **trusted**
`HumanApprovalVerifier` into the parent. It must independently authenticate the
named operator, check their project rights, verify explicit human approval of
every `ApprovalBinding` field, and reject replay of approval evidence itself.
No production verifier is supplied; without one, `approve` always denies.
Literal `True` from this trusted interface is required; requester claims, token
presence, truthy values, model output and worker messages do not suffice.
The test verifier is a mock service, not an authentication implementation.

### Opt-in gate and single-use approval

The parent can construct `PrivacyRouter` with
`require_external_model_authority=True`. With no authority configured, even
public data and a legacy consent token are denied. Supplying
`external_model_authority` also enables the strict boundary.
`decide` is only a preview and always denies external model authorization in
this mode. `authorize`/`enforce` require an opaque parent-held approval receipt,
the exact destination and purpose, and the exact outbound payload bytes
(strings are encoded as UTF-8).

Approval binds the authenticated operator, project, SHA-256 digest of those
bytes, exact HTTPS endpoint, purpose and absolute expiry. Query strings,
embedded endpoint credentials and fragments are disallowed. Expiry is checked
both against wall time and a monotonic deadline to prevent a clock rollback
extending an issued grant. Receipts are in-memory object identities, not bearer
tokens supplied by a browser or worker. Each redemption attempt consumes the
receipt, including payload/scope mismatches. Concurrent redemption permits at
most one admission. Restarting the parent loses every receipt.

These objects, verifier, approval evidence and stop controls must remain
exclusively in the trusted parent. Nothing is added to the worker protocol,
environment or workspace authority, and no credentials or encryption keys are
needed by this layer. The current process boundary is the security boundary;
this is not protection against compromised code running inside the parent.

**Compatibility:** ordinary routers and existing provider paths retain their
legacy behavior: public model egress may be allowed, and legacy explicit-share
tokens are merely presence-checked. Those paths are **not** protected by Phase
1A. Local processing, world ingress and external-write policy are unchanged.
Future collaborator callers must use the strict parent router, never a legacy
fallback. No external API adapter is implemented in this phase.

### Revocation, shutdown and auditing

Parent/operator `revoke` and `shutdown` are irreversible for the lifetime of an
authority object. Both destroy outstanding receipts and deny new approvals and
outbound admission; shutdown takes precedence over all other decisions.
Shutdown does not wait for an approval verifier to return. Admission and stop
decisions are serialized. There is no model/worker reset or override operation.
An external lifecycle controller still needs to own and invoke these controls
and ensure a stopped parent cannot simply restart with a fresh authority.

This is an **admission gate**, not a transport cancellation mechanism.
An attempt admitted before shutdown/revocation can still transmit afterwards;
already-sent bytes cannot be recalled. A future transport must enforce the
gate immediately before sending the approved bytes, implement cancellation as
appropriate, and document that race. Nothing here proves API traffic is
local-only: external transmission leaves the machine even if local state is
encrypted.

The authority reuses `WorkspaceAuditSink`/`WorkspaceAuditLog` rather than the
legacy egress log for approval, admission and stop decisions. Records contain
hashed operator/project references, fixed operation/reason codes, and a digest
of the complete approval scope, never payload text, endpoint text, purpose
text, credentials, approval evidence or receipts. Audit failures deny admission
and irreversibly revoke grants. Stop state is latched before its audit write.
Missing-authority router denials omit requester identities entirely (recording
only `unverified` placeholders) and omit payloads in the legacy audit log;
they can never result in admission.

The local descriptor-anchored audit sink fsyncs writes and rejects unsafe file
permissions, symlinks and directory replacement. It does **not** detect all
same-owner edits/truncation or provide independent immutable storage; scope
digests also are not a reconstruction of the human approval record. Production
integration needs an independently protected audit sink and authenticated
approval record retention. Hash references are pseudonymous, not anonymization:
guessable identity or scope values may be inferred by an audit reader. Grants
and shutdown state are single-process, not a durable or multi-parent revocation
service.

Focused tests: `python -m pytest -q tests/test_external_model_authority.py`.
Broker regression tests require the Python 3.14 environment used by the private
runtime CI workflow; OS sandbox/cgroup tests may skip when unavailable.
