import csv
from pathlib import Path
import numpy as np

OUT_MD = Path("reports/gv_multi_agent/MULTI_AGENT_SURVIVABILITY_RESULT.md")
OUT_CSV = Path("reports/gv_multi_agent/multi_agent_survivability.csv")

SEED = 42
STEPS = 320
AGENTS = 12

rng = np.random.default_rng(SEED)


def clamp01(x):
    return max(0.0, min(1.0, float(x)))


class Agent:
    def __init__(self, kind):
        self.kind = kind

        self.truth = 1.0
        self.constraint = 1.0
        self.correction = 1.0
        self.coherence = 1.0
        self.local_fitness = 0.45

    def step(self, global_coherence, regime_shift):

        noise = rng.normal(0, 0.01)

        if self.kind == "rigid":
            transform = 0.12
            recovery = 0.92

        elif self.kind == "reckless":
            transform = 0.95
            recovery = 0.20

        elif self.kind == "antifragile":
            transform = 0.88
            recovery = 0.55

        else:
            # GV recoverable transformer
            transform = 0.80
            recovery = 0.90

        # regime shifts reward adaptation
        if regime_shift:
            self.local_fitness += 0.24 * transform

            # transformation damages continuity if unrecoverable
            self.truth -= 0.14 * transform * (1 - recovery)
            self.constraint -= 0.16 * transform * (1 - recovery)
            self.correction -= 0.10 * transform * (1 - recovery)

        # local adaptation
        self.local_fitness += 0.004 * transform + noise

        # recovery
        self.truth += recovery * (1 - self.truth) * 0.03 + noise
        self.constraint += recovery * (1 - self.constraint) * 0.03 + noise
        self.correction += recovery * (1 - self.correction) * 0.03 + noise

        # local optimization can damage global coherence
        self.coherence += (
            0.03 * global_coherence
            - 0.02 * abs(self.local_fitness - global_coherence)
            + noise
        )

        self.truth = clamp01(self.truth)
        self.constraint = clamp01(self.constraint)
        self.correction = clamp01(self.correction)
        self.coherence = clamp01(self.coherence)
        self.local_fitness = clamp01(self.local_fitness)

    def survivability(self):
        return clamp01(
            0.32 * self.local_fitness +
            0.22 * self.truth +
            0.22 * self.constraint +
            0.14 * self.correction +
            0.10 * self.coherence
        )


def simulate(kind):

    agents = [Agent(kind) for _ in range(AGENTS)]

    rows = []

    for step in range(STEPS):

        regime_shift = step in [70, 140, 210, 280]

        global_coherence = np.mean(
            [a.coherence for a in agents]
        )

        for agent in agents:
            agent.step(global_coherence, regime_shift)

        survivabilities = [a.survivability() for a in agents]

        system_survivability = float(np.mean(survivabilities))

        fragmentation = float(np.std(
            [a.local_fitness for a in agents]
        ))

        rows.append({
            "system": kind,
            "step": step,
            "system_survivability": round(system_survivability, 6),
            "global_coherence": round(global_coherence, 6),
            "fragmentation": round(fragmentation, 6),
            "mean_truth": round(float(np.mean([a.truth for a in agents])), 6),
            "mean_constraint": round(float(np.mean([a.constraint for a in agents])), 6),
        })

    return rows


def summarize(rows):
    return {
        "system": rows[0]["system"],
        "mean_survivability": round(float(np.mean(
            [r["system_survivability"] for r in rows]
        )), 6),
        "final_survivability": round(rows[-1]["system_survivability"], 6),
        "min_global_coherence": round(min(
            r["global_coherence"] for r in rows
        ), 6),
        "max_fragmentation": round(max(
            r["fragmentation"] for r in rows
        ), 6),
        "min_truth": round(min(
            r["mean_truth"] for r in rows
        ), 6),
        "min_constraint": round(min(
            r["mean_constraint"] for r in rows
        ), 6),
    }


def main():

    systems = [
        "rigid",
        "reckless",
        "antifragile",
        "gv_recoverable",
    ]

    all_rows = []
    summaries = []

    for s in systems:
        rows = simulate(s)
        all_rows.extend(rows)
        summaries.append(summarize(rows))

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)

    with OUT_CSV.open("w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=list(all_rows[0].keys()),
        )
        writer.writeheader()
        writer.writerows(all_rows)

    winner = max(
        summaries,
        key=lambda s: s["mean_survivability"]
    )

    lines = [
        "# GV Multi-Agent Survivability Result",
        "",
        "## Purpose",
        "",
        "Test survivability under distributed conflict, adaptation, and perturbation.",
        "",
        "## Summary",
        "",
        "| System | Mean Survivability | Final Survivability | Min Global Coherence | Max Fragmentation | Min Truth | Min Constraint |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]

    for s in summaries:
        lines.append(
            f"| {s['system']} | {s['mean_survivability']} | "
            f"{s['final_survivability']} | "
            f"{s['min_global_coherence']} | "
            f"{s['max_fragmentation']} | "
            f"{s['min_truth']} | "
            f"{s['min_constraint']} |"
        )

    lines += [
        "",
        "## Winner",
        "",
        f"`{winner['system']}`",
        "",
        "## Interpretation",
        "",
        "Rigid systems preserve continuity but adapt poorly.",
        "",
        "Reckless systems adapt aggressively but fragment globally.",
        "",
        "Antifragile systems adapt strongly but may still erode coordination.",
        "",
        "GV targets recoverable multi-agent coordination under transformation.",
        "",
        "## Strong GV Base",
        "",
        "> Universal survivability may require recoverable coordination through transformation.",
    ]

    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print({
        "winner": winner["system"],
        "summaries": summaries,
    })

    print(f"wrote {OUT_MD}")


if __name__ == "__main__":
    main()
