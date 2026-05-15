import csv
import statistics
from pathlib import Path

TRACE_DIR = Path("sample_data/gv_multi_trace")
OUT = Path("reports/gv_multi_trace/MULTI_TRACE_RESULTS.md")

WINDOW = 8
Z_THRESHOLD = 2.5
VAR_THRESHOLD = 200
GV_THRESHOLD = 0.70


def clamp01(x):
    return max(0.0, min(1.0, float(x)))



def persistent_hits(raw_hits, min_run=3, max_gap=1):
    """
    Keep only transition candidates that persist.

    Single-point spikes are not enough.
    A transition must sustain across repeated nearby points.
    """
    raw_hits = sorted(raw_hits)

    if not raw_hits:
        return set()

    groups = []
    current = [raw_hits[0]]

    for idx in raw_hits[1:]:
        if idx - current[-1] <= max_gap + 1:
            current.append(idx)
        else:
            groups.append(current)
            current = [idx]

    groups.append(current)

    kept = set()

    for group in groups:
        if len(group) >= min_run:
            kept.update(group)

    return kept


def gv_scores(values):
    scores = []

    for i in range(len(values)):
        if i < WINDOW * 2:
            scores.append(1.0)
            continue

        recent = values[i-WINDOW:i]
        prior = values[i-(WINDOW*2):i-WINDOW]

        recent_slope = statistics.mean([
            recent[j] - recent[j-1]
            for j in range(1, len(recent))
        ])

        prior_slope = statistics.mean([
            prior[j] - prior[j-1]
            for j in range(1, len(prior))
        ])

        acceleration = recent_slope - prior_slope

        local_std = statistics.pstdev(values[max(0, i-WINDOW*2):i]) or 1.0

        pressure = (
            0.45 * clamp01(max(0.0, recent_slope) / max(1.0, local_std))
            + 0.55 * clamp01(max(0.0, acceleration) / max(1.0, local_std))
        )

        scores.append(round(clamp01(1.0 - pressure), 4))

    return scores


results = []

for trace in sorted(TRACE_DIR.glob("*.csv")):

    rows = list(csv.DictReader(trace.open()))
    values = [float(r["value"]) for r in rows]

    gv = gv_scores(values)

    raw_gv_hits = {
        i for i, g in enumerate(gv)
        if g < GV_THRESHOLD
    }

    gv_hits = persistent_hits(raw_gv_hits, min_run=3, max_gap=1)

    z_hits = set()
    var_hits = set()

    for i in range(WINDOW, len(values)):
        segment = values[i-WINDOW:i]

        mean = statistics.mean(segment)
        std = statistics.pstdev(segment) or 1.0
        var = statistics.pvariance(segment)

        z = abs(values[i] - mean) / std

        if z > Z_THRESHOLD:
            z_hits.add(i)

        if var > VAR_THRESHOLD:
            var_hits.add(i)

    gv_unique = gv_hits - z_hits - var_hits

    if len(gv_hits) < len(z_hits) and len(gv_hits) < len(var_hits):
        selective = "PASS"
    else:
        selective = "FAIL"

    if len(gv_unique) > 0:
        distinct = "PASS"
    else:
        distinct = "FAIL"

    results.append({
        "trace": trace.name,
        "raw_gv_hits": len(raw_gv_hits),
        "gv_hits": len(gv_hits),
        "z_hits": len(z_hits),
        "var_hits": len(var_hits),
        "gv_unique": len(gv_unique),
        "selective": selective,
        "distinct": distinct,
    })

OUT.write_text(
    "# GV Multi-Trace Tournament\n\n"
    + "| Trace | Raw GV | Persistent GV | Z | VAR | GV Unique | Selective | Distinct |\n"
    + "|---|---:|---:|---:|---:|---:|---|---|\n"
    + "\n".join(
        f"| {r['trace']} | {r['raw_gv_hits']} | {r['gv_hits']} | {r['z_hits']} | {r['var_hits']} | {r['gv_unique']} | {r['selective']} | {r['distinct']} |"
        for r in results
    )
    + "\n",
    encoding="utf-8"
)

print(results)
