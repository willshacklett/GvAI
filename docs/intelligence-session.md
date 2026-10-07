# AI-guided geographic intelligence

The public globe now has one investigation conversation across Laborer, Business
and Government workspaces. The guide starts without a selected place, supports
follow-up questions, and retains an ordered shortlist of up to five regions.
“Why GVAI is showing this place” explains the selected evidence; it does not claim
that selection constitutes a recommendation.

## Ownership and flow

- `web/regional-intelligence.js` remains authoritative for the selected regional
  evidence, audience and latest public jobs-search contract.
- `web/intelligence-session.js` references that store and retains references to
  shortlisted evidence objects, public occupation selection, scenario assumptions
  and results, recent intent, messages, requested actions and execution outcomes.
  It does not recalculate or manufacture regional statistics.
- `web/intelligence-guide.js` renders the conversation, first-run prompts, evidence
  explanations and comparisons. `web/index.html` supplies bounded adapters to the
  existing workspaces, location lookup, Cesium and regional-selection loader.
- `/api/chat` accepts an optional `gvai.intelligence-session.v1` context. The server
  validates it, retrieves regional evidence through the existing synthesizer and
  checks resolved IDs against requested identities. Public occupation employment,
  wages, specificity and STEX reuse the Business workforce evidence helper.
- `gvai/intelligence_session.py` owns validation and the analyst instruction
  contract, independent of model provider. Existing model routing, privacy egress,
  private runtime and pre/post-generation governance remain in force.

Flow: conversation/context -> bounded evidence retrieval -> governed model
reasoning -> validated action requests -> frontend adapters -> visible results.
Client jobs-search summaries and conversation are unverified quoted context.
Scenario results are recomputed from validated assumptions on the server.
No generic web search substitutes for regional evidence in this flow.

## Action protocol

The model returns `{"reply": "advice", "actions": [...]}`. The server returns
`action_protocol: "gvai.ui-actions.v1"` and accepted actions. Plain-text model
responses remain supported but carry no actions.

| Type | Exact additional fields | Execution |
| --- | --- | --- |
| `set_audience` | `audience`: `laborers`, `business`, `government` | Open existing workspace |
| `focus_region` | `query` **or** known `region_id` | Resolve place and move camera; do not select |
| `select_region` | `query` **or** known `region_id` | Resolve, move and select through existing regional loader |
| `compare_regions` | `region_ids`: 2–5 unique known IDs **or** `queries`: 2–5 place names | Retrieve shared regional contracts, update ordered shortlist and open comparison without selecting |
| `open_region_evidence` | None | Open Why Here |
| `open_occupation` | Public `occupation_code` in audited frontend catalog | Open public STEX evidence; do not mutate saved private profile |
| `open_jobs` | None | Open existing jobs workspace; do not automatically search |
| `open_scenario` | None | Open existing scenario form; do not invent assumptions or calculate |
| `show_sources` | None | Expand existing source disclosures |

Both server and frontend validate exact keys and allowlists. Each response carries
at most eight actions. Unknown, malformed, extra-field, executable-code and URL
actions are rejected. Governance-blocked responses carry no executable requests.
Action failures and stale results are visibly reported. The model never owns the
switch: opening a UI cannot grant arbitrary JavaScript, URL, shell or backend
authority.

Newer selections or workspace changes invalidate pending advice. Location lookup
and regional evidence loading preserve selection-token guards; actions produced
for a stale investigation cannot overwrite a newer selection.
Action-owned synchronous context changes are acknowledged explicitly. User
shortlist, occupation or scenario changes during asynchronous loading remain
invalidations and cannot be adopted by a resumed action sequence.

## Evidence and privacy

Source statistics retain source IDs, geography, method and vintage. Derived
metrics retain their methodology. Scenario outputs are explicitly assumption-led
task-hours arithmetic, not forecasts. AI interpretation and criteria-dependent
recommendations remain separate from observations.

Employment/wage evidence is OEWS labor-market-area evidence, not a county wage
estimate; broader occupation matches retain their specificity disclosure. Missing
data remains unavailable, not zero. Comparisons expose gaps and vintage differences
rather than a universal score.

The generic investigation payload does not include stored worker profiles,
preferences, credentials, wage history or private comparison results. Only a
public occupation code explicitly selected for investigation is included. Existing
private worker workflows remain distinct. User-written chat text is still chat
input: users should not paste private profile fields into public conversations.

## Bounds and current limitations

- Conversations are tab-memory only, not automatically persisted or synced.
  At most 24 prior user/assistant messages are transmitted, each up to 8 KiB.
  Older history is trimmed to keep the session below 64 KiB. Long assistant
  messages are clipped for transmission; the displayed answer remains intact.
- Up to five shortlist regions plus one current region are sent. The server
  re-retrieves evidence on each turn; shortlist cards show their last-retrieved
  evidence, and source vintage is disclosed. Retrieval can be slow or unavailable.
- AI selection currently supports US regional evidence. Foreign-country evidence
  remains unavailable; the existing location search still supports exploration.
  Focus needs resolved coordinates. Location resolution uses the existing
  geocoder's first result, not a new disambiguation service.
- A requested new place is selected first; advice on that place's retrieved
  evidence arrives on the next question, including “Ask GVAI why.” The model is
  instructed not to recommend an unresolved place as though evidence were known.
- No comprehensive private-sector jobs, validated nationwide STEX, predictive
  regional forecasts, commuting-time evidence or industry hiring-competition
  signals have been added or simulated.
- Provider-independent envelopes cannot guarantee provider conversational quality.
  Automated smoke uses explicitly synthetic model/API fixtures, not a production
  model evaluation.

## Validation

Run `python -m pytest tests -q` and
`node --test tests/frontend/*.test.cjs`. For browser coverage, install Playwright
and Chromium, serve `web/` locally, and run
`python tests/frontend/browser_smoke.py http://127.0.0.1:8090`.
Browser smoke covers desktop/mobile conversation-driven audience and globe
navigation, follow-up context, comparisons, Why Here, arbitrary-action rejection,
and the existing fifteen audience/viewport combinations.

The next build should add explicit place disambiguation and criteria capture,
then an automatic evidence-backed continuation after approved navigation or
comparison retrieval, with provider-quality evaluations and no expansion of
model authority.
