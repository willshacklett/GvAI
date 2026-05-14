# Working Abstract

We propose GV as an operational recoverability-loss detector for complex systems. Rather than predicting collapse directly, GV measures whether a system's capacity to return after disturbance is degrading persistently over time.

Synthetic falsification tests show that GV does not warn on stable or noisy-but-recoverable systems, does not warn before abrupt collapse without precursor degradation, and does warn when recovery force weakens before visible failure.

Baseline comparisons show that rolling variance is over-sensitive while rolling z-score is under-sensitive; GV occupies a selective middle regime.

Alpha phase mapping identifies a current stable discriminating region near 0.75–0.85, with false positives beginning near 0.90.

Regime stability tests suggest GV is precursor-strength limited rather than primarily noise-limited, with reliable synthetic detection beginning near slowing strength 0.001.

These results do not establish a universal law, but they define a falsifiable framework for testing recoverability degradation as an early-warning signal across operational, biological, economic, and AI systems.
