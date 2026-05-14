# GV External Trace Loader

Purpose:

Load ugly external telemetry without changing the frozen GV detector.

First target:

Google cluster / Borg-style scheduling traces.

Important:

Do not tune GV on these traces.

External data should be converted into normalized time-series CSVs shaped like:

time,value,event

Where value may represent:

- queue depth
- task/event arrival rate
- scheduling delay
- resource pressure
- retry/backlog pressure
- recovery-time proxy

This layer adapts external traces into GV-readable telemetry.
It does not change GV scoring logic.
