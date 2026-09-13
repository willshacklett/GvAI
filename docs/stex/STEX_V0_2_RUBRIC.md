# GVAI Structural Task Exposure Index (STEX) v0.2

STEX v0.2 preserves the STEX v0.1 mathematics and changes only the semantic clarification of the human-presence rating.

## Dimensions

- **D, digital capability (0-4):** capability of current AI/software systems to perform the information-processing, reasoning, language, calculation, classification, planning, or documentation component.
- **P, physical execution capability (0-4):** capability of a physical automation system to execute the physical actions in the actual work environment, considering mobility, dexterity, safety, tooling, and variation.
- **R, required human presence (0-4):** degree to which successful performance intrinsically requires a human being to be physically or socially present, exercising human-specific judgment, interaction, dexterity, responsibility, trust, or another human-dependent function.
- **Augmentation (0-4):** likelihood that technology assists a worker rather than substitutes for task execution. It remains separate from exposure.

A physical task does not automatically receive `R=4`. A robot, conveyor, autonomous mobile robot, automated forklift, machine-vision system, or robotic packing system may execute physical work without a human being present for every execution.

Conversely, human presence should remain high when the task intrinsically depends on interpersonal trust, bedside care, negotiation, responsibility requiring human judgment, or irregular physical manipulation beyond defensible current or near-current automation capability.

## Occupation-wide scope rule

Rate representative occupational settings, not one optimized facility. A `P=3`
or `P=4` rating requires physical automation capability across a substantial
share of ordinary settings in the occupation. Specialized automation in a
single highly standardized facility does not by itself establish
occupation-wide exposure.

Ratings must reflect irregular manipulation, safety accountability, and
situational judgment when those conditions are representative. Do not
double-count the same constraint: use `P` for physical execution capability
and `R` for required human presence.

## Formula

The formula is unchanged:

```text
C = max(D, P) / 4
H = R / 4
E = 100 * C * (1 - H)
```

`E` is the task structural exposure score from 0 to 100. Missing or unrated importance remains excluded from weighted aggregation.

## Examples

Physical but not necessarily human-dependent examples include automated cargo sorting, autonomous material movement, and robotic labeling or packing. Strongly human-dependent examples include bedside care, trust-based interaction, negotiation, accountability decisions, and irregular manipulation where current automation is not defensible.

STEX v0.1 profiles remain valid and reproducible. A single occupation may not mix task records from different rubric versions. Production regional aggregation tolerates approved profiles using different versions and continues to report the contributing source/rubric metadata.
