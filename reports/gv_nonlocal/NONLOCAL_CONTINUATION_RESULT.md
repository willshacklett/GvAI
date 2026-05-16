# GV Nonlocal Continuation Result

## Purpose

Test whether nonlocal continuation structure distinguishes authentic persistence from fake local compatibility.

## Final Result

`NO_NONLOCAL_DIFFERENTIATION`

## Results

| System | Path Score | Loop Score | Attacked Path | Attacked Loop | Advantage | Result |
|---|---:|---:|---:|---:|---:|---|
| structured_continuity | 0.734664 | 0.938399 | 0.941213 | 0.967493 | -0.117821 | NO_NONLOCAL_ADVANTAGE |
| random_system | 0.893878 | 0.964964 | 0.899307 | 0.961289 | -0.000877 | NO_NONLOCAL_ADVANTAGE |
| fragmented_system | 0.709748 | 0.633121 | 0.854612 | 0.933962 | -0.222852 | NO_NONLOCAL_ADVANTAGE |

## Interpretation

This test escalates from local compatibility to nonlocal continuation structure.

Long-path consistency and loop consistency approximate continuation coherence over distance.

Random locality attacks attempt to manufacture fake continuation.

GV strengthens if authentic systems retain stronger nonlocal coherence.
