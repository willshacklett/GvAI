# Global Labor Provider Contract V2

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
aggregators, government services, and other authorized providers. It accepts
an occupation reference and explicit public search context only. Adapters
declare their supported search filters and provider-specific option values.
They do not accept a Worker Profile.

`NormalizedJobOpening` preserves provider, provider job ID, occupation when
known, title, employer, location, country, employment type, published
compensation, published remote/hybrid information, posting date, retrieval
time, source attribution, and original apply URL. Unknown upstream values are
null.

`gvai.postlabor.live_jobs.LiveJobsRegistry` distinguishes results, zero results,
authorization required, provider unavailable, temporary unavailability,
unsupported filters, unsupported countries, and provider failure. It queries
all eligible providers for a country and isolates one provider's failure from
successful providers. It deduplicates the same provider ID and exact normalized
source URLs only. A shared source URL retains every provider ID and attribution;
similar titles alone are never merged.

The normalized V2 request supports location, provider-supported radius,
remote-only inclusion/exclusion, provider schedule codes, and posting recency.
USAJOBS maps these to its documented `LocationName`, `Radius`,
`RemoteIndicator`, `PositionScheduleTypeCode`, and `DatePosted` parameters.
Unsupported filters are reported rather than silently ignored. Missing opening
fields remain null; GVAI does not infer compensation, remote status, schedule,
qualifications, distance, or occupational fit.

## Compatibility And Limits

Existing callers default to `country_code=US`; U.S. O*NET/OEWS/STEX behavior
continues through the compatibility boundary. Provider #1 is the optional
USAJOBS API adapter in `gvai.postlabor.usajobs_provider`. It is registered only
when both `USAJOBS_API_KEY` and `USAJOBS_USER_AGENT` are configured. The
worker's occupation title is sent as `Keyword` with `mapping_type=search_query`;
it is not treated as a USAJOBS occupation mapping. Optional
`USAJOBS_TIMEOUT_SECONDS`, `USAJOBS_RESULT_LIMIT`, and
`GVAI_LIVE_JOBS_RESULT_LIMIT` settings are bounded by the adapter/registry.
Missing USAJOBS credentials produce `authorization_required` through the
registered default capability. No scraping or fallback to another country's
evidence occurs.

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

`GET /api/worker/live-jobs/capabilities?country=XX` reports the registry state
for `live_job_openings` without exposing secrets: provider name, priority,
attribution, state, supported public filters, and non-secret filter options.
The Laborers workspace uses that response to enable only controls an active
provider can honor.
