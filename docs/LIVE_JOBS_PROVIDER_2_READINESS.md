# Live Jobs Provider #2 Readiness

## Finding

The repository contains no credential, client, licensed feed, data-use
agreement, or documented authorization for a second live-opening provider.
Test fixtures named as additional providers are not real access. No Provider #2
was integrated, and no endpoint or credential was guessed.

The existing registry can register multiple providers for one country. The
orchestrator queries every configured provider that can honor the selected
filters, normalizes the results, isolates provider failures, and deduplicates
only provider IDs or shared canonical source URLs. Provider priority controls
query order only; it does not make a provider authoritative or rank jobs.

## Legitimate acquisition paths

| Source category | Coverage value | Access required before implementation |
| --- | --- | --- |
| National Labor Exchange (NLx) | Broad U.S. public and private-sector listings; complements federal-only USAJOBS | A DirectEmployers/NASWA NLx data-use or distribution agreement, approved API/feed access, credentials, current schema documentation, attribution rules, redistribution/display terms, and deletion/expiry requirements |
| State workforce exchanges | State and local openings, often including employers absent from federal listings | A documented state API or licensed feed, written authorization where required, credentials, rate limits, schema/version contract, attribution, geographic scope, and reuse/retention terms |
| Commercial job data API | Broad multi-employer or international coverage | Executed provider terms or contract, production API credentials, permitted countries, search/filter documentation, source-link and attribution requirements, quotas, caching/retention rules, and confirmation that displaying normalized listings is allowed |
| Employer or ATS feeds | High-fidelity first-party openings from participating employers | Employer/ATS authorization or a documented public feed intended for redistribution, stable tenant/feed identifiers, schema and pagination contract, attribution/source URL requirements, and lifecycle rules for closed jobs |
| Public-sector country portals outside the U.S. | Legitimate expansion to a supported country | An official documented API or downloadable feed, confirmation of reuse rights, any required registration/credentials, authoritative country scope, schema/version contract, and attribution requirements |

Public web pages without an authorized API/feed are not candidates. Search
engine results, undocumented endpoints, scraping, and credentials obtained for
another purpose do not satisfy readiness.

## Adapter acceptance checklist

Before registration, Provider #2 must have:

1. Written or published authorization for the intended API/feed use.
2. Documented request fields, response schema, pagination, limits, and failure behavior.
3. A declared country boundary and exact supported factual filters.
4. Stable provider job IDs and original source/apply URLs.
5. Rules for attribution, caching, expiry, deletion, and redistribution.
6. Tests proving unknown fields stay unknown and no Worker Profile data is transmitted.
7. Deterministic identity evidence for any cross-provider deduplication.

An application-submission, employer-contact, or worker-data transmission API is
outside this discovery adapter. Such a feature would require a separate product
contract and the existing GVAI Safety Systems boundary before execution.