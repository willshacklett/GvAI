# Unlabeled Trace Policy

Unlabeled external telemetry must not be reported as success or failure.

Allowed interpretation:

- candidate stress window
- candidate degradation window
- review target
- hypothesis-generating signal

Disallowed interpretation:

- confirmed prediction
- confirmed lead time
- confirmed failure detection
- proof of external validity

Rule:

If labels are absent, GV warnings become candidate windows only.
