import csv
import sys
from pathlib import Path
from collections import defaultdict

"""
Generic external trace normalizer.

Input:
Any CSV with a numeric timestamp column and one numeric metric column.

Output:
GV-compatible CSV:

time,value,event

Usage:
python3 normalize_trace_csv.py input.csv output.csv --time timestamp --value metric
"""


def parse_args(argv):
    if len(argv) < 7:
        print("Usage: python3 normalize_trace_csv.py input.csv output.csv --time time_col --value value_col")
        raise SystemExit(2)

    input_path = argv[1]
    output_path = argv[2]

    args = argv[3:]
    opts = {}
    for i in range(0, len(args), 2):
        opts[args[i]] = args[i + 1]

    return Path(input_path), Path(output_path), opts["--time"], opts["--value"]


def main():
    input_path, output_path, time_col, value_col = parse_args(sys.argv)

    rows = []
    with input_path.open(newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                t = float(row[time_col])
                v = float(row[value_col])
            except Exception:
                continue

            rows.append((t, v))

    if not rows:
        raise SystemExit("No usable rows found.")

    rows.sort(key=lambda x: x[0])

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["time", "value", "event"])
        writer.writeheader()

        for t, v in rows:
            writer.writerow({
                "time": t,
                "value": v,
                "event": "unlabeled"
            })

    print({
        "input": str(input_path),
        "output": str(output_path),
        "rows": len(rows),
        "time_col": time_col,
        "value_col": value_col
    })


if __name__ == "__main__":
    main()
