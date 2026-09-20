# Laborers Active Investigation V1

The Laborers workspace stores one browser-local workflow record under
`gvai.activeInvestigation.v1`. It is navigation state, not a Worker Profile and
not labor evidence.

The V1 record contains only:

- `schema_version`: `v1`
- `investigated_occupation`: O*NET-SOC code and title
- `originating_occupation`: current occupation code and title, or `null`
- `region`: public country code, latitude, longitude, and display label, or `null`
- `navigation_stage`: a recognized Laborers workspace stage

The browser validates the version, occupation identifiers, public coordinates,
text lengths, and stage before restoring the record. Invalid, stale, or
malformed records are discarded without preventing the workspace from loading.
The record contains no experience, education, credentials, skills, wage,
mobility, preferences, or other Worker Profile fields. It is not persisted on
the server and is not transmitted merely because it exists.

Related and saved occupations enter the same canonical investigation loader.
Personal Comparison receives Worker Profile data only when the worker invokes
that feature. Live Jobs receives the active occupation and public region plus
filters the worker explicitly selects; it does not receive Worker Profile data.
Provider authorization or availability failures leave the local investigation
record intact.

Evidence reads, provider capability checks, live-job searches, and opening an
Apply-at-source URL remain informational or navigation operations. They do not
call the separate GVAI Safety Systems boundary. Any future application
submission, worker-data transmission, employer contact, or external mutation
must cross that boundary before execution.