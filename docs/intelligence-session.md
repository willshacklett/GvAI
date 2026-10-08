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
  candidate/shortlisted evidence objects, public occupation selection, scenario assumptions
  and results, recent intent, messages, requested actions and execution outcomes.
  It does not recalculate or manufacture regional statistics.
- `web/investigation.js` owns the public investigation shape, criteria/candidate
  validation and compact decision panel. `gvai/decision_intelligence.py` validates
  the same contract and recomputes an explainable working read from server evidence.
  Client-authored conclusions and private fields are never trusted or forwarded.
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
| `start_investigation` | `investigation_type`, `question` | Start an explicit decision; preserve current region/shortlist |
| `set_criteria` | `criteria` | Merge exact user-stated criteria by key; invalidate previous read |
| `add_candidate` | `query` **or** known `region_id` | Retrieve authoritative evidence, retain candidate and focus globe without selecting |
| `remove_candidate` | Known `region_id` | Remove candidate and shortlist membership |
| `shortlist_candidate` | Known `region_id` | Add candidate to bounded shortlist |
| `reject_candidate` | Known `region_id`, bounded `reason` | Retain rejection rationale as interpretation; exclude from active comparison |
| `focus_candidate` | Known `region_id` | Focus globe without selecting |
| `compare_candidates` | None | Compare shortlist, or 2–5 active candidates; do not silently truncate |

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
Criteria and candidate edits also invalidate pending advice and clear the old
working read. A pending ambiguous-place choice is cancelled by a newer context.

## Investigation and criteria

The memory-only `gvai.investigation.v1` context contains `type`, `question`,
`criteria` and `candidates`. Types are `worker_opportunity`, `relocation`,
`career_transition`, `business_expansion`, `hiring_workforce`,
`government_monitoring` and `regional_comparison`. Each candidate has a verified
`region_id`, `status` (`candidate`, `shortlisted`, `rejected`) and optional `reason`;
rejection requires a reason. Removing a candidate also removes shortlist membership.

Each criterion has exactly `key`, `value`, `direction` (`higher`, `lower`,
`inspect`) and `priority` (`primary`, `secondary`, `constraint`). Keys cover public
occupations, workforce availability, wage level, housing pressure, labor-force size,
radius, geography, current jobs, occupational composition, STEX and user priority.
`occupations` holds up to five `{code, workers}` requirements; workers are assumed
hiring counts or null, never actual private employment records. `distance_radius`
is `{miles, center}`. Other values are bounded user-stated text.
The panel labels criteria as AI-parsed, permits priority/direction/removal corrections,
and lets the user reassess. Merely changing criteria never leaves an old leader visible.

The server returns `decision_read`: missing criteria, a single material clarification,
direct signal comparisons, material evidence gaps, a conditional working leader,
per-candidate supporting/contradicting signals and `could_change_if`. These are
interpretation, not new statistics. Source values preserve classification, geography
and vintage separately. No numeric composite score or hidden weights exist.

Only same-scope, same-vintage supported signals can be compared. Labor-force size
is not hiring ease; housing value/income is not rent or personal affordability.
Occupation employment/wages require exact matches and identified OEWS areas.
Broad occupation matches remain available to inspect but cannot decide a leader.
Primary-signal winners must agree; conflicts, ties and missing primary evidence do
not force an overall winner. A partial working read is explicitly provisional and
discloses unresolved constraints. Secondary disadvantages remain visible.
STEX, job-search counts, occupational composition and unverified radius/corridor
constraints cannot drive a manufactured ranking. Government investigations return
neutral monitoring reads, not political jurisdiction recommendations or invented trends.

AI-driven evidence/criteria changes trigger **one** automatic conversational
continuation. It includes the full latest reply and completed action outcomes,
fresh server retrieval and recomputed read. Continuation actions are stripped by
the server and ignored by the frontend; no recursive tool loop is permitted.
Both initial and continuation replies retain provider routing and governance.
`guide.send(text)` and `guide.ask(text, audience)` are reusable, keyboard-independent
entry points for future voice integration. No new voice capture is enabled.

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
- Up to eight candidates, five shortlist regions and one current region are bounded
  (overlapping references are deduplicated). The server
  re-retrieves evidence on each turn; shortlist cards show their last-retrieved
  evidence, and source vintage is disclosed. Retrieval can be slow or unavailable.
- AI selection currently supports US regional evidence. Foreign-country evidence
  remains unavailable; the existing location search still supports exploration.
  Focus needs resolved coordinates. AI place resolution requests up to five real
  results from `/api/geocode?candidates=1`; multiple results require explicit user
  choice. No first result is silently selected. Legacy location-search responses
  remain compatible. Choices are not recommendations or invented place records.
- Candidate discovery currently retrieves explicit place names, not a nationwide
  search or geospatial radius/corridor filter. Distance constraints are captured
  but remain unverified. Public occupation evidence can still be absent.
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
Decision journeys additionally cover criteria, multiple candidates, real globe
focus, shortlist changes, why a working leader is ahead, priority-sensitive
recommendation changes and explicit place disambiguation on desktop/mobile.

The next build should add source-verified candidate discovery with genuine
geographic constraint checks and provider-quality decision evaluations, without
expanding model authority or pretending missing hiring/commuting data exists.
