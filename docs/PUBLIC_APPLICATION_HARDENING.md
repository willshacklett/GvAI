# Public Application Hardening

## Verified Baseline

Audited clean `main` / `origin/main` at `7d9e1fabd22a6d1d6f9133a8f1ceb84d760a9332`.
The live `https://gvai.io` site responded successfully during inspection.
The review was checked against current code, not assumed to describe current production.

| Surface | Finding |
| --- | --- |
| `railway.json` | Installed requirements on each process boot, then ran `privacy/start_railway.sh`. |
| Railway entry point | Launcher already used `gvai.api_service:app` with Gunicorn, but implicit workers/timeout. |
| `Procfile` | Conflicting Flask development-server command with boot-time install. |
| `render.yaml` | Separate Render path via `start.sh` / `server.main:app`; external usage cannot be verified from Git. |
| Requirements / CI | Mostly unpinned runtime dependencies; specialized private-runtime CI used Python 3.14, but no normal primary product job. |
| `/api/chat` | Unbounded input, no rate limits, raw provider exception text; blocked output returned through `gv_original_reply`. |
| `/api/geocode` | Upstream timeout existed (15 seconds); no query bound or abuse budget. |
| CORS / errors | Wildcard API CORS, no global JSON error handler, additional regional handlers exposed exception text. |
| Adaptive state | Direct shared JSON writes without locking/atomic replacement; malformed reads reset silently. |
| Regional fetch | Request IDs already guarded successful responses; failures left cleared metrics as dashes and did not guard stale status updates. |
| Boundaries / globe | Separate third-party boundary and imagery requests; not the same path as API regional statistics. |
| Layout | Competing fixed desktop offsets and viewport-only grid breakpoints; rendered browser checks also verified panel/control occlusion. |
| Tracked artifacts | 5,544 generated files removed from tracking; virtual environments, logs, PID state, bytecode, backups, and generated chart. Local files retained; chart source retained. |
| Pages | Broad `web/*` copy plus dashboard, including backup and deployment files; missing manifest icons and broken dashboard logo path. |
| Internal review | Writes default-disabled, but enabling the flag previously did not authenticate the caller; internal editor was publicly published. |
| Existing tests | API/product tests and Python markup assertions; full collection failed because shared `gvai.postlabor.data.schema` was missing. |

The original requirements could run 754 tests with three gated skips only after excluding
the broken postlabor collection. The exclusion was diagnostic, not retained in CI.
Restoring the product schema exposed undeclared `openpyxl` and two tests depending on an
absent local BLS workbook. The dependency is declared, and those tests now use synthetic
workbooks while retaining the real loader/resolver. Product and experiment tests run without
that exclusion. Pinned direct versions match the exercised Python 3.14 environment.

## Implemented Boundaries

Exact production browser origins plus explicitly configured development origins;
bounded bodies/messages/queries; configurable per-client and aggregate route budgets;
stable public JSON failures with server-side exception logging; no rejected raw reply field;
authenticated opt-in internal STEX writes; locked read-modify-write and atomic file replacement.
Health and ordinary regional reads are not rate-limited by the expensive-route limiter.

The frontend retains Cesium and all three audience paths. Bounded JSON requests, guarded
failure states, retry, active-workspace-only layout, container queries, mobile control spacing,
semantic landmarks, public metadata, and keyboard globe controls are covered by regression checks.
The optional browser smoke check verifies the real Cesium canvas and all audiences at
1366, 1024, and 390 pixels, including pointer reachability and horizontal overflow.

Pages now publishes an explicit allowlist and checks local references, retaining the existing
public dashboard/reports and Carl assets. The internal editor stays in source for controlled
operator use. Railway has one startup path; no production credentials/account settings changed.

## Verification

- Broad check: `python -m pytest tests experiments middleware ai_access -q -rs`:
   858 passed, 3 skipped. No suite excluded from this command.
- Skips: one opt-in real staging sandbox test and two opt-in delegated cgroup tests.
   The existing specialized Private Runtime CI provides those infrastructure gates.
- Frontend helper: 8 Node tests passed. Optional Chromium smoke passed for all three
   audiences at 1366, 1024, and 390 pixels, regional failure/retry, and colored globe pixels.
- Editor diagnostics, dependency consistency, Pages reference/allowlist validation,
   shell syntax, Gunicorn configuration/import, and actual launcher HTTP health passed.
- Research tests regenerate three tracked CSVs; that generated churn is restored after
   verification rather than included in the PR. Generated runtime files remain ignored.

## Pre-Merge Review

PR #87 was reviewed against current main on 2026-10-03. Its original remote checks
exposed two CI setup defects: the GodScore workflow used Python 3.11 with the pinned
Python 3.14 dependencies, and Product CI invoked real sandbox tests without Bubblewrap,
the established scoped namespace profile, or a trusted Python executable. Both workflows
are corrected without excluding tests or weakening isolation checks. Product CI also
delegates a private worker cgroup and runs from its broker leaf, matching the existing
resource harness. It opts into the real staging and cgroup tests and rejects leaked
resource groups during cleanup.

Four caught regional/STEX failures now log exception tracebacks before returning their
existing safe domain messages. Regression tests verify logs retain diagnostics while
public JSON omits exception details. No unrelated product or layout changes were made.

The strengthened browser check uses real entry/tab/close/retry clicks at 1440x900,
1366x768, 1024x768, 768x1024, and 390x844. All 15 audience/viewport combinations passed,
including regional failure/retry, search reachability, overflow, and rendered globe pixels.
The refreshed Pages output contains exactly 37 intentional public assets. All 5,544
removed files were verified as generated artifacts; no source or required fixture/asset
was removed, and future nested source directories named data are not ignored.

Final local review checks: 862 Python tests passed with the same 3 opt-in infrastructure
skips; 53 focused hardening tests and 8 Node tests passed. Dependency, Pages reference,
Gunicorn import/configuration, editor diagnostic, and whitespace checks passed.

There were no general comments, reviews, or inline threads. Existing Actions Node 20
deprecation warnings (the runner forces Node 24) and the future ubuntu-latest migration
notice are valid follow-ups, not current application correctness failures. Check the
latest GitHub run for the updated commit before merge; local results do not replace CI.

## Remaining Limitations

- CORS does not authenticate public API clients. Rate limits are abuse budgets, not a WAF.
- Default memory limiting is suitable for the default single worker, but resets on restart.
  Configure protected Redis before increasing workers/replicas. If the trusted proxy chain
  is not configured, per-client limits may group users behind the same Railway proxy.
- Local atomic state is consistent across processes on one filesystem, not across replicas;
  ephemeral Railway storage still needs an approved volume for durable history.
- Nominatim and other upstream geographic/data services retain their own availability,
  CORS, caching, and usage-policy constraints; no external provider/account settings were changed.
- Normal product CI does not replace the specialized private-runtime sandbox/resource job.
  Browser smoke needs optional Playwright, Chromium libraries, and access to public Cesium assets.
- Exact direct dependency pins are not a full transitive lockfile or supply-chain audit.
- The legacy public observatory depends on a separate telemetry backend and is not repointed
  to an unrelated Railway endpoint. Render usage remains unverified, so its alternative is retained.
- Removing files from tracking does not purge Git history. Historical secret remediation,
  if needed, is a separate approved operation.

## Manual Production Checks

1. Review Railway's build/start overrides and Python runtime. Confirm Python 3.14, build-stage
   requirements installation, `privacy/start_railway.sh`, and `/api/health` readiness in staging.
2. Confirm the real proxy chain and direct-access behavior before setting trusted proxy hops.
   Verify multiple real clients do not share an unintended rate bucket; provision Redis before scaling.
3. Verify both GVAI production origins can search a region and chat, while unrelated browser
   origins are denied. Confirm oversized and throttled requests receive JSON 4xx responses.
4. Verify cold starts, model-provider availability, county/state/country statistics, imagery,
   and boundary loading separately. Check failure/retry behavior at laptop and mobile widths.
5. Choose whether adaptive history needs durable storage; configure an approved volume/path if so.
6. Keep review writes disabled unless an operator token is securely configured server-side.
   Do not inject that token into Pages or public frontend configuration.
7. Confirm the existing Google Maps browser key has exact domain and required-API restrictions
   in Google Cloud. This requires manual approval and is not done by this PR.
8. Inspect the Pages artifact, public dashboard/Carl routes, favicon, GeoJSON, and canonical
   metadata after deployment. Confirm internal editor/backups/deployment files are absent.

The branch is intended for review; do not merge or deploy it automatically.