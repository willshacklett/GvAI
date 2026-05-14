import csv
import sys
from pathlib import Path

WARNING_THRESHOLD = 0.70
DEFAULT_RADIUS = 5


def load_normalized(path):
    rows = []
    with Path(path).open(newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return rows


def load_gv_values(path):
    """
    Simple candidate extraction proxy.

    For now, this reads normalized telemetry and flags rising stress windows.
    This does NOT claim failure prediction.

    It only creates review windows.
    """

    rows = load_normalized(path)
    values = [float(r["value"]) for r in rows]

    candidates = []

    for i in range(2, len(values)):
        rising = values[i] > values[i - 1] > values[i - 2]
        elevated = values[i] > max(values[:max(1, i)]) * 0.85

        if rising and elevated:
            candidates.append(i)

    return rows, candidates


def merge_windows(indices, radius, total_len):
    windows = []

    for idx in indices:
        start = max(0, idx - radius)
        end = min(total_len - 1, idx + radius)

        if not windows or start > windows[-1]["end"] + 1:
            windows.append({"start": start, "end": end})
        else:
            windows[-1]["end"] = max(windows[-1]["end"], end)

    return windows


def main():
    if len(sys.argv) < 3:
        print("Usage: python3 extract_candidate_windows.py normalized.csv output.csv")
        raise SystemExit(2)

    input_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2])

    rows, candidates = load_gv_values(input_path)
    windows = merge_windows(candidates, DEFAULT_RADIUS, len(rows))

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "window_id",
                "start_index",
                "end_index",
                "start_time",
                "end_time",
                "label",
                "notes",
            ],
        )
        writer.writeheader()

        for n, w in enumerate(windows, start=1):
            writer.writerow({
                "window_id": n,
                "start_index": w["start"],
                "end_index": w["end"],
                "start_time": rows[w["start"]]["time"],
                "end_time": rows[w["end"]]["time"],
                "label": "candidate_stress_window",
                "notes": "Unlabeled telemetry window for human review; not a claimed prediction.",
            })

    print({
        "input": str(input_path),
        "output": str(output_path),
        "candidate_points": len(candidates),
        "windows": len(windows),
    })


if __name__ == "__main__":
    main()
