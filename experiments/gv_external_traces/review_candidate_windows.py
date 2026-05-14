import csv
import sys
from pathlib import Path

"""
Human review layer for unlabeled GV candidate windows.

Purpose:
Turn candidate stress windows into reviewable evidence records
WITHOUT changing detector logic.
"""


def load_csv(path):
    with Path(path).open(newline="") as f:
        return list(csv.DictReader(f))


def main():
    if len(sys.argv) < 4:
        print(
            "Usage: python3 review_candidate_windows.py "
            "normalized.csv candidate_windows.csv output_review.csv"
        )
        raise SystemExit(2)

    normalized_path = Path(sys.argv[1])
    candidate_path = Path(sys.argv[2])
    output_path = Path(sys.argv[3])

    telemetry = load_csv(normalized_path)
    windows = load_csv(candidate_path)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "window_id",
                "start_time",
                "end_time",
                "peak_value",
                "mean_value",
                "human_label",
                "review_notes",
                "confirmed_recoverability_issue",
            ],
        )

        writer.writeheader()

        for w in windows:
            start_idx = int(w["start_index"])
            end_idx = int(w["end_index"])

            segment = telemetry[start_idx:end_idx + 1]
            values = [float(r["value"]) for r in segment]

            writer.writerow({
                "window_id": w["window_id"],
                "start_time": w["start_time"],
                "end_time": w["end_time"],
                "peak_value": round(max(values), 4),
                "mean_value": round(sum(values) / len(values), 4),
                "human_label": "",
                "review_notes": "",
                "confirmed_recoverability_issue": "",
            })

    print({
        "telemetry_rows": len(telemetry),
        "candidate_windows": len(windows),
        "output": str(output_path),
    })


if __name__ == "__main__":
    main()
