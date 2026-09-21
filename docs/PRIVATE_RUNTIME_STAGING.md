# Private runtime staging checks

These checks do not activate Private Build or establish production readiness.
Use synthetic data only until deployment isolation and key management have
been independently reviewed.

## Configuration and network preflight

Run from the repository root:

```bash
python -m privacy.staging_readiness
```

The command reports sanitized JSON and exits 0 only when all implemented
preflight checks pass. Missing configuration, unsupported process APIs,
network-sandbox failures, and worker overrides yield exit 1.
It does not print keys, environment values, or raw exceptions.

Required configuration:

- `GVAI_PRIVATE_BUILD_MODE=1`
- `GVAI_PRIVATE_ENCRYPTED_WORKSPACE=1`
- `GVAI_PRIVATE_WORKSPACE_KEY`: base64 encoding of exactly 32 bytes
- `GVAI_LOCAL_MODEL_COMMAND`: syntactically valid local engine command

The preflight checks command syntax, not model availability or execution.
It launches a bounded synthetic probe through the stock network sandbox
with a minimal environment. The probe checks namespace separation and
the absence of non-loopback interfaces; it contacts no external endpoint.

`ready_for_smoke_test` covers only this preflight scope.
`production_ready` is always false. Storage and audit round trips are
explicitly reported as unverified by this command.

## Synthetic runtime smoke test

Install the repository's declared dependencies and pytest first. Run:

```bash
GVAI_RUN_STAGING_SMOKE=1 timeout 45s python -m pytest -q \
  tests/integration/test_private_runtime_staging_smoke.py
```

This opt-in Linux test uses a generated temporary key, synthetic prompts,
and a Python mock engine through the real runtime and network sandbox.
It checks the reply, network namespace, interface list, selected secret
environment-variable exclusion, audit redaction, and workspace cleanup.
It does not execute the operator's configured model.
Without the opt-in variable, the test is skipped, not verified.

The smoke test does not inspect ciphertext bytes; separate encrypted-workspace
tests cover storage encryption and tampering.

## Limits and deployment blockers

- Network namespaces do not provide filesystem isolation.
- Environment filtering does not prevent same-user host access to secrets.
- Failure cleanup signals the original worker process group before reaping
  the failed leader. Descendants that escape that group are not contained.
- Successful worker exit does not guarantee background descendants are gone.
- Concurrent hostile filesystem mutation can race current path validation.
- The environment-based key loader is development-grade, not a production
  secret-management solution.
- Resource limits, rollback detection, key rotation, and stronger OS-level
  isolation remain separate deployment work.

Never let the thing behind the switch own the switch: shutdown, authorization,
and recovery authority must remain externally controlled.
