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
continues through the compatibility boundary. No live-jobs integration is
configured in V1. This work adds no scraping, LLM inference, semantic matching,
crosswalk guessing, ranking, recommendation, fit score, credential equivalence,
or synthetic labor-market data.