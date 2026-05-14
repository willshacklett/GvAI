import csv
import statistics
from pathlib import Path

INPUT = Path("reports/gv_google_cluster/google_cluster_transition_pass.csv")
OUT_MD = Path("reports/gv_war_room/WAR_ROOM_BASELINE_TOURNAMENT.md")
OUT_CSV = Path("reports/gv_war_room/war_room_baseline_tournament.csv")

WINDOW = 8
Z_THRESHOLD = 2.5
VAR_THRESHOLD = 200


def load_rows():
    rows = []
    with INPUT.open(newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append({
                "time": float(row["time"]),
                "value": float(row["value"]),
                "gv_transition": float(row["gv_transition"]),
                "gv_hit": row["candidate_transition"] == "True",
            })
    return rows


def main():
    rows = load_rows()
    values = [r["value"] for r in rows]

    z_hits = set()
    var_hits = set()
    gv_hits = {i for i, r in enumerate(rows) if r["gv_hit"]}

    for i in range(WINDOW, len(values)):
        segment = values[i - WINDOW:i]
        mean = statistics.mean(segment)
        std = statistics.pstdev(segment) or 1.0
        var = statistics.pvariance(segment)

        z = abs(values[i] - mean) / std

        if z > Z_THRESHOLD:
            z_hits.add(i)

        if var > VAR_THRESHOLD:
            var_hits.add(i)

    all_hits = sorted(gv_hits | z_hits | var_hits)

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)

    with OUT_CSV.open("w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "index",
                "time",
                "value",
                "gv_hit",
                "zscore_hit",
                "variance_hit",
                "gv_unique",
                "boring_baseline_overlap",
            ],
        )
        writer.writeheader()

        for i in all_hits:
            writer.writerow({
                "index": i,
                "time": rows[i]["time"],
                "value": rows[i]["value"],
                "gv_hit": i in gv_hits,
                "zscore_hit": i in z_hits,
                "variance_hit": i in var_hits,
                "gv_unique": i in gv_hits and i not in z_hits and i not in var_hits,
                "boring_baseline_overlap": i in gv_hits and (i in z_hits or i in var_hits),
            })

    gv_unique = gv_hits - z_hits - var_hits
    gv_overlap = gv_hits & (z_hits | var_hits)

    # Honest scoring:
    # GV should be selective, but if it only duplicates simpler detectors,
    # it has not earned distinct value yet.
    if len(gv_hits) < len(z_hits) and len(gv_hits) < len(var_hits):
        selectivity = "PASS"
    else:
        selectivity = "FAIL"

    if len(gv_unique) > 0:
        distinctness = "PASS"
    else:
        distinctness = "FAIL"

    if selectivity == "PASS" and distinctness == "PASS":
        battle_result = "GV_SURVIVED_THIS_BATTLE"
    elif selectivity == "PASS":
        battle_result = "GV_SELECTIVE_BUT_NOT_DISTINCT"
    else:
        battle_result = "GV_DID_NOT_WIN_THIS_BATTLE"

    OUT_MD.write_text(f"""# GV War Room Baseline Tournament

## Purpose

Test whether GV transition detection is actually useful against boring baselines.

## Detectors

- GV transition detector
- rolling z-score
- rolling variance

## Candidate counts

| Detector | Candidate Points |
|---|---:|
| GV transition | {len(gv_hits)} |
| Rolling z-score | {len(z_hits)} |
| Rolling variance | {len(var_hits)} |

## Overlap

| Measure | Count |
|---|---:|
| GV unique hits | {len(gv_unique)} |
| GV overlap with boring baselines | {len(gv_overlap)} |

## Battle checks

| Check | Result |
|---|---|
| More selective than z-score and variance | {selectivity} |
| Has at least one unique hit | {distinctness} |

## Battle result

`{battle_result}`

## Rule

If GV is not more selective, it loses.

If GV is only a subset of boring baselines, it has not yet earned distinct value.

Fast is allowed. Hidden rescue logic is not.
""", encoding="utf-8")

    print({
        "gv_hits": len(gv_hits),
        "z_hits": len(z_hits),
        "var_hits": len(var_hits),
        "gv_unique": len(gv_unique),
        "gv_overlap": len(gv_overlap),
        "battle_result": battle_result,
    })


if __name__ == "__main__":
    main()
