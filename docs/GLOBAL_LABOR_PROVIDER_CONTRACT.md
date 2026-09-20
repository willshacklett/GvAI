# Global Labor Provider Contract V1

`gvai.postlabor.labor_providers` is the country/provider boundary for Laborers.

## Occupations

`OccupationReference` preserves `country_code`, `provider`,
`provider_occupation_code`, and `title`. `international_identifier` is optional
and remains `None` unless an authoritative provider mapping is supplied. GVAI
does not infer occupation equivalence or create crosswalks.

## Evidence

`ProviderMetadata` declares the evidence capabilities a configured provider
actually supports: occupation profiles, employment, wages, preparation,
structural exposure, and live job openings. The current U.S. provider is
`us_onet_oews_stex`; it adapts the existing O*NET, OEWS, and STEX paths without
changing their identifiers or behavior.

Unsupported countries and capabilities return an `unavailable` value with a
reason and a null evidence value. They never use another country's evidence or
replace an unavailable observation with zero, 50, or a synthetic estimate.

## Live Jobs

`LiveJobsProvider` is an adapter protocol for authorized APIs, feeds,
aggregators, government services, and other authorized providers. It accepts an
occupation reference and country only. It does not accept a Worker Profile.

`NormalizedJobOpening` preserves provider, provider job ID, occupation when
known, title, employer, location, country, employment type, published
compensation, published remote/hybrid information, posting date, retrieval
time, source attribution, and original apply URL. Unknown upstream values are
null.

`gvai.postlabor.live_jobs.LiveJobsRegistry` distinguishes
`available_with_results`, `available_zero_results`, `provider_unavailable`,
`unsupported_country`, and `provider_failure`. It validates adapter output and
deduplicates by provider and provider job ID. The worker API accepts only
public occupation and geographic search context; it never accepts a Worker
Profile.

## Compatibility And Limits

Existing callers default to `country_code=US`; U.S. O*NET/OEWS/STEX behavior
continues through the compatibility boundary. Provider #1 is the optional
USAJOBS API adapter in `gvai.postlabor.usajobs_provider`. It is registered only
when both `USAJOBS_API_KEY` and `USAJOBS_USER_AGENT` are configured. The
worker's occupation title is sent as `Keyword` with `mapping_type=search_query`;
it is not treated as a USAJOBS occupation mapping. Optional
`USAJOBS_TIMEOUT_SECONDS`, `USAJOBS_RESULT_LIMIT`, and
`GVAI_LIVE_JOBS_RESULT_LIMIT` settings are bounded by the adapter/registry.
Missing configuration remains `provider_unavailable`; no scraping or fallback
to another country's evidence occurs.

The adapter preserves USAJOBS job IDs, titles, employer/location fields,
published schedule/telework/date fields when supplied, the original apply URL,
retrieval time, and USAJOBS attribution. It sends only public occupation and
location search context and never accepts Worker Profile fields. Public job
retrieval and opening the source URL remain ordinary reads/navigation; no
application submission or employer contact is governed or claimed.

This work adds no LLM inference, semantic matching, crosswalk guessing,
ranking, recommendation, fit score, credential equivalence, or synthetic
labor-market data.

## Global Job Provider Coverage Registry V1

`gvai.postlabor.provider_registry.GlobalProviderRegistry` is a separate,
additive capability registry. It represents multiple live-job providers per
country and providers spanning multiple countries, and it never fetches jobs,
scrapes, ranks by quality/fit, or exposes adapter credentials.

Each `ProviderRegistration` declares a `country_code`, `provider`,
`capability`, `priority`, `attribution`, and an `adapter` reference. `priority`
only orders provider selection; it never implies job quality or worker fit.

Per-provider state (`ProviderRuntimeState`) is one of `configured` (registered
and authorized), `authorization_required` (registered but missing
credentials), or `temporarily_unavailable` (registered, authorized, but inside
a failure cooldown window set by `GVAI_PROVIDER_UNAVAILABLE_COOLDOWN_SECONDS`,
default 300 seconds).

Country/capability aggregate state (`CountryCapabilityState`) is one of
`available` (at least one configured provider), `temporarily_unavailable`,
`authorization_required`, or `unsupported` (no provider registered at all).

`gvai.postlabor.live_jobs.DEFAULT_PROVIDER_REGISTRY` registers the existing
USAJOBS adapter unchanged; `DEFAULT_LIVE_JOBS_REGISTRY` records provider
success/failure into it after each search so `temporarily_unavailable`
reflects real recent failures. The USAJOBS adapter itself is untouched.

`GET /api/worker/live-jobs/capabilities?country=XX` reports the registry
state for `live_job_openings` without exposing secrets: provider name,
priority, attribution, and state only. The Laborers workspace calls this
endpoint before searching so it can truthfully tell the worker whether live
jobs are unsupported, awaiting authorization, temporarily unavailable, or
available for the selected country, instead of assuming U.S. behavior.
