# Private runtime staging checks

These checks do not activate Private Build or establish production readiness.
Use synthetic data only until deployment isolation, cgroup delegation, approved
model assets, key management, and audit storage have been independently
reviewed.

## Configuration and namespace preflight

Run from the repository root:

```bash
python -m privacy.staging_readiness
```

The command reports sanitized JSON and exits 0 only when all implemented
preflight checks pass. Missing configuration, unsupported process APIs,
Bubblewrap failures, namespace failures, insecure audit destinations, invalid
resource policies, unavailable cgroup containment, or worker overrides yield
exit 1. It does not print keys, environment values, approved paths, audit paths,
resource-policy values, or raw exceptions.

Required configuration:

- `GVAI_PRIVATE_BUILD_MODE=1`
- `GVAI_PRIVATE_ENCRYPTED_WORKSPACE=1`
- `GVAI_PRIVATE_WORKSPACE_KEY`: base64 encoding of exactly 32 bytes
- `GVAI_LOCAL_MODEL_COMMAND`: syntactically valid local engine command
- Linux with permitted unprivileged user namespaces
- a root-owned executable Bubblewrap binary that is not group- or world-writable
- cgroup v2 with `cpu`, `memory`, and `pids` controllers enabled for
  child cgroups plus `cgroup.kill`
- a canonical cgroup root owned by root or the trusted broker account, with no
  group or world write permission

Optional configuration:

- `GVAI_PRIVATE_WORKSPACE_AUDIT_DIR`: absolute local reference-audit directory;
  when omitted, the runtime uses its private temporary-directory default
- `GVAI_PRIVATE_SANDBOX_READ_PATHS`: operator-controlled, path-separated list
  of canonical absolute files or directories mounted read-only for the worker
- `GVAI_PRIVATE_CGROUP_ROOT`: externally administered cgroup-v2 directory;
  defaults to `/sys/fs/cgroup`
- `GVAI_PRIVATE_MEMORY_MAX_BYTES`: aggregate worker-tree memory limit; defaults
  to 8 GiB
- `GVAI_PRIVATE_PIDS_MAX`: aggregate worker-tree process limit; defaults to 64
- `GVAI_PRIVATE_CPU_QUOTA_US`: aggregate CPU quota; defaults to 400,000
  microseconds
- `GVAI_PRIVATE_CPU_PERIOD_US`: CPU accounting period; defaults to 100,000
  microseconds

The preflight checks model-command syntax, not model availability or execution.
It initializes and validates the local reference audit destination, including
canonical-path, ownership, permission, link-count, and descriptor-identity
requirements. It validates the resource policy, creates a real empty cgroup-v2
boundary, verifies its controls and independent kill interface, and removes it.
It then launches a bounded synthetic worker inside the stock Bubblewrap
boundary. The probe verifies separate network, mount, and PID namespaces; no
non-loopback network interface; a private writable home and temporary directory;
and absence of the repository and host home from the worker filesystem.

`ready_for_smoke_test` covers only this preflight scope. `production_ready` is
always false. Configured model execution, encrypted storage and audit round
trips, independently protected audit storage, cross-resource audit atomicity,
approved model-asset content, production key management, and protection from a
privileged hostile host remain explicitly unverified.

## Synthetic runtime smoke test

Install the repository's declared dependencies and pytest first. Run:

```bash
GVAI_RUN_STAGING_SMOKE=1 timeout 60s python -m pytest -q \
  tests/integration/test_private_runtime_staging_smoke.py
```

This opt-in Linux test uses a generated temporary key, synthetic prompts, and a
Python mock engine through the real encrypted runtime and Bubblewrap boundary.
It verifies network, mount, and PID namespace separation; absence of the
repository, host home, encrypted workspace, and audit destination; a private
writable `/tmp`; selected secret-environment exclusion; broker-only encrypted
workspace access; audit redaction and local audit permissions; aggregate
cgroup-v2 containment; and cleanup of both workspace storage and the exact
per-worker cgroup.

The test does not execute the operator's configured model. Without the opt-in
variable, it is skipped and therefore not verified. Separate encrypted-workspace
tests cover ciphertext storage, authentication, tampering, and descriptor-
anchored path traversal.

## Limits and deployment blockers

- Bubblewrap isolates the encrypted worker, not the trusted broker or host.
- A hostile process with sufficient host permissions may still inspect
  ciphertext, rename or delete files, cause denial of service, or attack an
  insufficiently protected audit destination.
- Operator-approved model assets are trusted deployment inputs and require
  independent provenance and content review.
- The broker-owned cgroup applies aggregate CPU, memory, and process limits and
  uses `cgroup.kill` to terminate the complete contained tree. Process-group
  signaling remains fallback cleanup.
- A privileged hostile host process can still alter cgroup controls, migrate
  processes, or interfere with termination. The delegated cgroup root must
  remain externally administered and independently verifiable.
- The environment-based key loader is development-grade, not a production
  secret-management solution.
- Independently protected audit storage, cross-resource audit reconciliation,
  appropriate host permissions, storage quotas, rollback detection, key
  rotation, and stronger deployment isolation remain separate work.

Never let the thing behind the switch own the switch: shutdown, authorization,
permission contraction, rollback, and recovery authority must remain externally
controlled and independently verifiable.
