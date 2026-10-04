# Regional Intelligence Experience

## Architecture Audit

Baseline: clean main at `3c360f9a5dff243a07ba62fe37af1dea70eaeace`, after PR #87.
The public product remains one Cesium geographic exploration surface with Laborer,
Business, and Government entry paths. This build does not add GV theory, activate or
copy Safety Systems, replace the framework, or reopen deployment cleanup.

Before this build, search/globe clicks selected coordinates or national/state scope.
Nominatim resolved search text; Census resolved county/state FIPS. Boundary geometry
used independent Census/Natural Earth/geocoder paths. `/api/region` retrieved ACS,
then separate regional labor and STEX calls repeated part of the evidence work.
Frontend profile objects, labels, coordinates, request IDs, and workspace fields
were separate state. Occupation/jobs routes had their own evidence contracts.

The regional panel displayed population, labor force, unemployment, age, income,
home value, the home-value/income ratio, labor availability, workforce composition,
STEX coverage/reference employment/covered employment/weighted exposure, and legacy
stability/displacement/concentration/resilience fields. Named place shortcuts included
hard-coded statistics without provenance. No live calculation backed those composite
index fields. Ask sent only display text; simulation was an alert placeholder.

## Shared Model

`GET /api/region/intelligence` accepts the existing county coordinates or state/country
scope. It resolves the baseline once, combines existing deterministic signals and
packaged STEX, and returns `gvai.regional-intelligence.v1`. The payload includes stable
region identity, metric value/unit/classification/method/source references, source
vintage, availability by section, workforce groups, STEX detail, and freshness.

County identity uses `US:county:<state FIPS><county FIPS>`, state uses `US:state:<FIPS>`,
and national identity uses `US:country`. Unsupported countries retain explicit geography
and unavailable evidence, without inheriting US statistics. Place shortcuts retain only
geographic names/coordinates; invented statistics and unsupported score classifications
are removed.

`web/regional-intelligence.js` owns one selected-region store. All three workspaces use
the same summary/source renderer and separate explicitly labelled audience interpretation.
Legacy scalar coordinates remain adapters for the existing occupation/investigation
tools, not another regional calculation. Their region-dependent requests are invalidated
on selection changes. Occupation detail routes still use their existing server evidence
contracts; this PR does not introduce a cross-service cache or trust client metrics as
authoritative occupation evidence.

Boundary geometry is still separate from statistics. The new selection path no longer
launches the duplicate client labor-synthesis/STEX requests. Existing legacy endpoints
remain compatible for other callers. ACS source requests on the new path have bounded
waits within the browser timeout; old callers retain their default timeout behavior.

## Provenance And Classification

Every shared metric carries source references and an inspectable calculation label.
Beside-value source labels distinguish source data from GVAI-derived calculations.
Source vintage is shown only when known; retrieval time is not presented as publication
or source update time. Unknown source update dates stay null. No score is derived merely
to fill an empty display.

| Metric | Classification | Source | Method / Notes |
| --- | --- | --- | --- |
| Population | A: source statistic | Census ACS 5-year | B01003_001E; default available dataset vintage 2024 |
| Civilian labor force / unemployed | A: source statistic | Census ACS 5-year | B23025_003E / B23025_005E |
| Median income / home value / age | A: source statistic | Census ACS 5-year | B19013_001E / B25077_001E / B01002_001E |
| Unemployment rate | B: derived metric | ACS labor force and unemployed | Unemployed / civilian labor force times 100 |
| Labor availability | B: derived classification | ACS unemployment rate | Existing thresholds: below 3.5% tight, 3.5-5.5% balanced, above 5.5% available; not hiring demand |
| Workforce group employment | A: source statistic | ACS S2401 | Broad occupation-group counts, not industry employment |
| Workforce group share | B: derived metric | ACS S2401 counts | Group employed / ACS employed population |
| Home value / income | B: derived metric | ACS medians | Home value / household income; not rent burden or a pressure category |
| OEWS reference employment | A: source statistic | Packaged BLS OEWS | Labor-market-area All Occupations denominator; source year returned by the snapshot |
| STEX-covered employment / coverage | B: derived metric | OEWS plus approved task audits | Sum audited occupation employment / OEWS denominator; zero coverage does not mean zero exposure |
| Audited structural exposure | B: GVAI-derived metric | Approved STEX and OEWS weights | Employment-weighted exposure over covered audited occupations only; not percent automatable or job-loss probability |
| Occupation STEX/task patterns | B: GVAI-derived metric | O*NET task content plus STEX rubric | Importance-weighted profile; lower-exposure/higher-augmentation patterns are within-audit comparisons, not employment guarantees |
| Occupation employment and wages | A: source statistic | Packaged BLS OEWS | Existing exact/broader-category specificity retained; source/vintage shown |
| Education survey and Job Zone | A: source statistic/profile | O*NET | Published preparation evidence, not an assessment of a person's qualifications; no invented survey year |
| Live job listings / published pay | A: source listing data | Configured provider attribution | Search-limited results, not total regional vacancies; latest result status can accompany regional Ask |
| Scenario task hours | C: scenario output | Explicit user assumptions | Workers times weekly hours times assumed task share times assumed time saving; not forecast, staffing/ROI estimate, or observed regional hours |
| Audience implications and Ask reply | D: interpretation | Supplied attributed evidence | Deterministic audience framing or model interpretation; not a source statistic or policy mandate |
| Stability / displacement / concentration / resilience indices | Unavailable | No connected validated regional methodology | Explicitly unavailable; no manufactured composite values or county rankings |

## Audience Experience

Laborers move from regional evidence into the existing occupation/profile, task audit,
adjacent roles, current job listings, and Ask tools. Task rationale and source vintage
stay inspectable. Exposure does not rate personal background or guarantee outcomes.

Business shares that baseline but frames workforce, exposure, housing constraints,
occupation plans, assumptions, and sources for planning. Automation is not declared
preferable to hiring; neither ROI nor staffing reductions are inferred from STEX.

Government sees observed conditions and signals to monitor. Missing evidence remains
explicit. No jurisdiction rankings, laws, partisan advice, candidate recommendations,
or active Safety Systems governance are introduced.

The one Ask/scenario surface follows the active audience workspace. Ask passes explicit
identity, metrics, sources, audience, STEX, jobs-search status, and availability flags.
The server bounds the quoted context, treats it as unverified data rather than commands,
keeps the existing limiter/governance enforcement, and returns interpretation content
without internal governance fields. Private worker profiles are not included.

The old simulator was not a mature prediction engine. Its replacement is deliberately
limited task-hours arithmetic with blank required inputs, visible published baseline,
scenario change, and potential effect. Assumed hours are not regional measurements.

## Partial Data

A workforce failure preserves ACS baseline; an ACS failure after county resolution
preserves geography so packaged STEX may remain usable. Missing values stay null, not
zero. ACS retry is offered only for a retryable source, not absent configuration or
missing packaged coverage. Same-region refresh retains last-retrieved evidence with
an explicit freshness/status message. New selections clear old evidence and invalidate
stale regional, task/occupation, Business, and jobs responses.

## Verification And Manual Review

Regression coverage includes normalized identity, provenance/classification, partial
source failures, unknown exposure with zero audit coverage, structured bounded Ask,
regional reply privacy, shared audience state, source escaping, scenario assumptions,
task patterns, jobs-result scope, and removal of demo numbers. The browser smoke uses
synthetic labelled API evidence and real Cesium at 1440x900, 1366x768, 1024x768,
768x1024, and 390x844. It tests all audiences, source disclosures, inline Ask context,
scenario output, failure/retry, navigation, overflow, and rendered canvas pixels.

Manual review should confirm real ACS credentials/availability, the currently configured
dataset vintage, packaged OEWS geography coverage, approved STEX profile coverage, jobs
provider authorization/filter behavior, and real model/provider output attribution.
STEX is limited to packaged labor-market areas (currently Tennessee mappings) and the
approved audit catalog, not comprehensive county exposure. State/country STEX remains
unavailable where no packaged aggregate exists. Source freshness is not known beyond
reported vintage. Model interpretations and scenario assumptions still require judgment.

No secrets, account settings, or separate Safety Systems repository are changed.