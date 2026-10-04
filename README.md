# GVAI

## Local Setup

Use Python 3.14 (also declared in `.python-version`) and Node 24 for frontend tests.
The Cesium globe and Laborer, Business, and Government workspaces remain the public product.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt -r requirements-dev.txt -r gateway/requirements.txt
```

Direct production and test dependencies are pinned to the versions exercised by CI.
Optional BLS workbooks and model downloads are not required for the primary product suite;
tests use synthetic fixtures rather than inventing production evidence.

## Running Tests

```bash
python -m pytest tests -q
node --test tests/frontend/*.test.cjs
python -m pytest tests experiments -q
python scripts/prepare_pages.py --output /tmp/gvai-public-preview
python -m gunicorn --check-config gvai.api_service:app
```

`tests/` is the primary suite, run on every normal PR by Public Application CI.
`experiments/` contains slower research checks. Private Runtime CI separately exercises
the real filesystem/network/resource sandbox. Three tests require explicit opt-in for
the real filesystem sandbox or delegated cgroup infrastructure; see their skip reasons.

Optional desktop/mobile browser regression (requires Chromium and its system libraries):

```bash
python -m pip install playwright
python -m playwright install --with-deps chromium
python -m http.server 8090 --directory /tmp/gvai-public-preview
# In a second terminal:
python tests/frontend/browser_smoke.py http://127.0.0.1:8090
```

Screenshots go to ignored `test-results/`. The check uses synthetic unavailable API responses,
not paid model calls, and tests all three workspace paths and the actual Cesium canvas.

## Starting The API

```bash
GVAI_CORS_ORIGINS=http://localhost:8090,http://127.0.0.1:8090 \
PORT=8000 privacy/start_railway.sh
```

Health is available at `/api/health`. Point a locally served copy of the frontend's
`api_config.js` at `http://localhost:8000`; restore the production URL before committing.
Do not open the frontend with `file://`, whose opaque browser origin is deliberately rejected.
The source and publication preview are separate: edit source in `web/`, then rebuild the preview.

## Frontend And API

GitHub Pages serves the static app from `web/`; `web/api_config.js` selects the Railway API.
Regional statistics, third-party geographic boundaries, and Cesium imagery are separate paths.
The shared JSON helper times out after 25 seconds and sanitizes network, HTTP, and JSON failures.
Selection tokens prevent older successes or failures from replacing the latest region.
The internal STEX editor is source-only and is not published to Pages.

The Regional Intelligence Experience uses `/api/region/intelligence` as one shared,
source-labelled baseline for Laborers, Business, and Government. Important values
distinguish source statistics, GVAI-derived metrics, scenario outputs, and interpretation.
Missing scores stay unavailable; named-place shortcuts contain no demo statistics.
Ask receives bounded structured regional context through the existing protected chat
route. Task-hours scenarios are explicit assumption-led arithmetic, not predictions.
See [the regional experience and credibility review](docs/REGIONAL_INTELLIGENCE_EXPERIENCE.md).

## Railway Production

`railway.json` is authoritative: install requirements during build, then execute
`privacy/start_railway.sh`. It launches `gvai.api_service:app` with Gunicorn, one worker,
a 120-second timeout, and `/api/health` as the deployment health check. `Procfile` delegates
to that same launcher rather than defining another backend. The existing private-build
bootstrap remains opt-in. `render.yaml` and `start.sh` describe a legacy FastAPI/Render
alternative, not the Railway app; retained because external deployment usage is unverified.

Adaptive control uses a locked, atomic JSON replacement at `data/gv_adaptive_control.json`.
Storage errors are logged and do not prevent the governance layer from returning a safe reply.
Railway's container filesystem is ephemeral unless a volume is configured; use
`GVAI_ADAPTIVE_CONTROL_PATH` on an approved persistent volume when persistence is required.
File locking coordinates processes on one filesystem, not separate Railway replicas.

## GitHub Pages

`scripts/prepare_pages.py` builds an empty output directory from an explicit asset allowlist,
then checks local HTML and manifest references. The Pages workflow uses that same builder.
The globe GeoJSON, API config, frontend assets, Carl bundle, and existing public dashboard/reports
are retained. Internal review UI, backups, logs, deployment files, and arbitrary new files are excluded.
Update the allowlist and tests when adding a public asset or rebuilding the hashed Carl bundle.
The legacy kernel observatory requires its separate telemetry service; Railway does not expose
its `/api/kernel/observatory` endpoint and the public page reports unavailable telemetry safely.

The existing Pages Google Maps browser key is injected through an environment variable and
JSON serialization, never shell interpolation. Browser keys are public by nature: restrict
them to GVAI domains and the required APIs in Google Cloud. No real key belongs in source or docs.

## Important Environment Variables

| Variable | Default / Purpose |
| --- | --- |
| `PORT` | `8080` for the API listener |
| `GVAI_CORS_ORIGINS` | Empty; comma-separated additional exact origins. `https://gvai.io` and `https://www.gvai.io` are always allowed. Explicitly opt in local origins. |
| `GVAI_MAX_REQUEST_BYTES` | `65536`, bounded JSON request body |
| `GVAI_CHAT_MAX_MESSAGE_BYTES` | `8192`, untrimmed UTF-8 chat input |
| `GVAI_GEOCODE_MAX_QUERY_BYTES` | `512`, untrimmed UTF-8 query |
| `GVAI_CHAT_RATE_LIMIT` | `10 per minute`, per client |
| `GVAI_CHAT_GLOBAL_RATE_LIMIT` | `120 per minute`, aggregate chat budget |
| `GVAI_GEOCODE_RATE_LIMIT` | `30 per minute`, per client |
| `GVAI_GEOCODE_GLOBAL_RATE_LIMIT` | `60 per minute`, aggregate geocoder budget |
| `GVAI_RATE_LIMIT_STORAGE_URI` | `memory://`; use a protected `redis://` or `rediss://` service for shared limits before adding workers/replicas |
| `GVAI_TRUSTED_PROXY_HOPS` | `0`; only set after verifying Railway's trusted proxy chain and whether direct access is prevented. Untrusted forwarded headers must not choose client identity. |
| `GVAI_WEB_WORKERS` / `GVAI_WEB_TIMEOUT` | `1` / `120`; Gunicorn settings |
| `GVAI_ADAPTIVE_CONTROL_PATH` | `data/gv_adaptive_control.json`; optional persistent-volume location |
| `GVAI_STEX_REVIEW_WRITES_ENABLED` | Disabled unless `1`; internal approval writes also require `GVAI_STEX_REVIEW_TOKEN` and an exact `Authorization: Bearer` token |
| `GVAI_GOOGLE_MAPS_API_KEY` | Existing Pages build secret; public, domain/API-restricted browser key |

Keep provider credentials and `GVAI_STEX_REVIEW_TOKEN` server-side. CORS is a browser policy,
not caller authentication; non-browser clients can still reach public read/chat endpoints.
Memory limits reset on restart. Redis limits are shared only when all instances use the same
storage and configuration. No account settings or production secrets are changed by this PR.

See [the hardening audit](docs/PUBLIC_APPLICATION_HARDENING.md) for verified baseline findings
and the manual production checks required before deployment.

## Post-Labor Capitalism Intelligence

**GVAI is a geographic intelligence platform for understanding the economic and human impact of automation, AI, robotics, demographic change, and labor displacement.**

The platform combines regional economic data, workforce composition, automation exposure, housing conditions, demographic pressure, and the God Variable (GV) survivability framework into an interactive global intelligence system.

The goal is simple:

> **Understand what happens to places and people as human labor becomes less necessary — and identify where human labor, investment, infrastructure, and adaptation are still needed.**

---

## The Platform

GVAI is being built around an interactive 3D Earth.

Users can explore the world, select a region, and examine local conditions including:

- Population
- Labor-force size
- Unemployment
- Workforce composition
- Median household income
- Housing values
- Demographic and aging pressure
- Automation exposure
- Employment vulnerability
- Industry concentration
- Regional resilience
- Transition and displacement risk

GVAI is designed to move from **global → national → state/province → county/region → local community** intelligence.

---

## Regional Intelligence

For supported U.S. locations, GVAI can resolve geographic coordinates into real county-level economic and workforce information.

Current regional data includes:

- Population
- Civilian labor force
- Unemployment rate
- Median household income
- Median home value
- Median age
- Broad occupational composition

Current occupational groups include:

- Management, business, science, and arts
- Service occupations
- Sales and office occupations
- Natural resources, construction, and maintenance
- Production, transportation, and material moving

Regional demographic and workforce information is currently sourced from the **U.S. Census Bureau American Community Survey (ACS)**.

Additional labor-market, industry, automation, and international data sources are being integrated.

---

## Post-Labor Intelligence

GVAI is intended to answer questions such as:

### For businesses

- Where is labor becoming difficult to find?
- Which occupations are most exposed to automation?
- What happens to a community when a company automates part of its workforce?
- Where should a company expand, automate, hire, or invest?
- Which regions are economically resilient enough to absorb technological disruption?

### For workers and individuals

- Where are my skills needed?
- Which occupations are growing or declining?
- How exposed is my current work to AI or robotics?
- What skills could transfer into more resilient work?
- Where might better opportunities exist?

### For communities and policymakers

- Which regions face the greatest displacement pressure?
- Where could automation create severe local economic instability?
- Which communities have enough economic diversity to adapt?
- Where will aging populations create labor shortages?
- Where should infrastructure, training, housing, or investment be directed?

---

## God Variable (GV)

GVAI grew from the **God Variable (GV)** research project.

GV is a survivability-oriented framework for measuring constraint strain, drift, instability, irreversibility risk, and recovery across changing systems.

Within GVAI, GV serves as an underlying analytical layer for asking a broader question:

> **Can this system, organization, economy, or community remain viable as its constraints change?**

GV research remains part of the project, but GVAI's primary product direction is now **Post-Labor Capitalism Intelligence**.

---

## Architecture

GVAI currently includes:

- Interactive Cesium-based 3D Earth
- Geographic coordinate selection
- Regional intelligence API
- U.S. Census geocoding
- ACS demographic and workforce data
- Occupational workforce profiles
- Automation and labor-transition modeling
- GV survivability analysis
- AI-assisted regional analysis
- Simulation infrastructure
- Privacy and outbound-model controls

The platform is being designed so additional national and international datasets can be added as geographic intelligence layers.

---

## API

The GVAI API provides services used by the interactive platform.

Example regional lookup:

```text
GET /api/region?lat=<latitude>&lon=<longitude>
```

A supported U.S. coordinate can return regional information including:

```json
{
  "state": "Tennessee",
  "county": "Rutherford County",
  "population": 360646,
  "labor_force": 201582,
  "unemployment_rate": 3.6,
  "median_household_income": 85470,
  "median_home_value": 382600,
  "median_age": 34.2
}
```

Regional responses can also contain occupational workforce composition.

---

## CLI

The original GVAI command-line interface remains available:

```bash
python -m gvai.cli "your input here"
```

---

## Conversation GV Demo

Build the conversation GV demonstration data:

```bash
PYTHONPATH=. python3 scripts/build_conversation_gv_demo.py
```

---

## Development Status

GVAI is under active development.

The current build establishes the foundation for a larger geographic intelligence system combining:

**Economics + Labor + Automation + Demographics + Geography + AI + GV**

Future development will expand:

- Labor-market time series
- Occupation-level automation exposure
- Business and industry intelligence
- Corporate automation tracking
- Regional labor shortages
- Aging-population pressure
- International datasets
- Geographic heat maps
- Scenario simulation
- AI-assisted workforce transition planning
- Community-level automation impact modeling

---

## Vision

AI and robotics may fundamentally change the relationship between human labor, production, income, and economic value.

That transition will not affect every person or every place equally.

Some regions may experience labor shortages.

Some may experience rapid displacement.

Some industries may become extraordinarily productive with very little human labor.

Some communities may struggle to adapt.

GVAI exists to make those changes **visible, measurable, geographic, and understandable**.

---

# GVAI

### Post-Labor Capitalism Intelligence
