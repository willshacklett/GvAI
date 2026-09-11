# GVAI Structural Task Exposure Index (STEX) v0.1

## Purpose

STEX estimates the structural exposure of occupational task content to current AI
and automation capabilities.

STEX is not:

- a probability that a worker will lose a job;
- a forecast of layoffs;
- a measure of observed AI adoption;
- a direct measure of productivity change;
- a claim that an occupation is "automatable."

The unit of analysis is the O*NET task statement.

---

## Source Layer

Primary task source:

- O*NET occupation-specific task statements
- O*NET task importance
- O*NET task category
- O*NET task source vintage

Source task data must be frozen before scoring.

---

## Task-Level Dimensions

Each task is assessed on four separate dimensions.

### 1. Digital Capability

Question:

Can current AI/software systems perform the information-processing, reasoning,
language, calculation, classification, planning, or documentation component of
this task?

Values:

- 0 = negligible
- 1 = limited
- 2 = moderate
- 3 = high
- 4 = very high

This dimension measures capability, not adoption.

---

### 2. Physical Execution

Question:

Can current commercially plausible automation or robotics perform the physical
actions required by this task in the actual work environment?

Values:

- 0 = negligible
- 1 = limited
- 2 = moderate
- 3 = high
- 4 = very high

This must consider unstructured environments, mobility, dexterity, tool use,
safety constraints, and environmental variability.

---

### 3. Human Presence Requirement

Question:

How strongly does successful execution depend on a human being physically
present at the work site?

Values:

- 0 = no meaningful physical human presence required
- 1 = low
- 2 = moderate
- 3 = high
- 4 = inherently requires human presence under current conditions

This is a constraint variable.

Higher values reduce substitution exposure.

---

### 4. Augmentation Likelihood

Question:

Under current capabilities, is technology more likely to assist a human worker
than replace execution of the task?

Values:

- 0 = primarily substitution-oriented
- 1 = low augmentation tendency
- 2 = mixed
- 3 = high augmentation tendency
- 4 = primarily augmentation-oriented

This is reported separately from structural exposure.

---

## Missing or Unrated O*NET Importance

A task with O*NET importance = 0 MUST NOT automatically be interpreted as
having zero importance.

If the task category or source metadata indicates the task is new or unrated,
the task must be marked:

    importance_status = "unrated"

and excluded from importance-weighted aggregation until a documented treatment
rule is applied.

Raw O*NET values must never be overwritten.

---

## Task Exposure Calculation

For STEX v0.1, task structural exposure is derived only from:

- digital capability
- physical execution
- human presence requirement

Augmentation likelihood is retained as a separate explanatory dimension and
does not modify the structural exposure score.

Let:

    D = digital capability rating, 0-4
    P = physical execution rating, 0-4
    R = human presence requirement rating, 0-4

Normalize the primary execution channel:

    C = max(D, P) / 4

Normalize the human-presence constraint:

    H = R / 4

Task structural exposure is:

    E = 100 * C * (1 - H)

where E is bounded from 0 to 100.

### Rationale

The maximum of digital and physical capability is used because exposure may
arise through either an information-processing pathway or a physical automation
pathway.

Averaging digital and physical capability would incorrectly penalize tasks for
which one execution channel is irrelevant.

Human presence is treated as a constraint on substitution exposure.

A task rated as inherently requiring human presence under current conditions
(R = 4) therefore receives zero structural substitution exposure, regardless
of digital assistance potential.

Such a task may still have high augmentation likelihood.

### Examples

Digital documentation task:

    D = 4
    P = 0
    R = 0

    C = 1.00
    H = 0.00
    E = 100

Highly physical task in an unstructured environment:

    D = 0
    P = 1
    R = 4

    C = 0.25
    H = 1.00
    E = 0

Mixed task with moderate human-presence requirement:

    D = 3
    P = 1
    R = 2

    C = 0.75
    H = 0.50
    E = 37.5

### Consistency Checks

Ratings must be reviewed if:

- physical execution is rated very high while human presence requirement is
  also rated very high;
- rationale does not explain which execution channel drives exposure;
- a task statement combines materially different actions that produce
  conflicting ratings.

A consistency warning does not automatically change the score.

### Preservation Requirements

All component ratings must be preserved alongside the derived result.

No task score may be stored without:

- source task ID
- source occupation code
- rubric version
- scorer or scoring system identifier
- scoring timestamp
- rationale
- source-data vintage

---

## Interpretation

STEX measures exposure of task content.

Preferred language:

"employment-weighted share of task content rated as structurally exposed under
the current STEX capability rubric"

Avoid:

- "jobs at risk"
- "percent of jobs automatable"
- "workers likely to be replaced"
- "layoff probability"

---

## Versioning

Rubric version:

    STEX v0.1

Any change to:

- dimensions
- definitions
- scoring levels
- aggregation method
- missing-data treatment

requires a new rubric version.

Historical scores must remain reproducible under the rubric version that
created them.
