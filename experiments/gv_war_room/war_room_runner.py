import csv
import subprocess
import sys
from pathlib import Path
from datetime import datetime

RUNS = [
    {
        "name": "transition_vs_magnitude",
        "cmd": [sys.executable, "experiments/gv_google_cluster/run_google_trace_pipeline.py"],
        "expected_output": "reports/gv_google_cluster/google_cluster_transition_pass.csv",
    },
    {
        "name": "external_candidate_windows",
        "cmd": [
            sys.executable,
            "experiments/gv_external_traces/extract_candidate_windows.py",
            "reports/gv_external_traces/messy_queue_pressure.normalized.csv",
            "reports/gv_external_traces/messy_queue_pressure.candidate_windows.csv",
        ],
        "expected_output": "reports/gv_external_traces/messy_queue_pressure.candidate_windows.csv",
    },
]

OUT = Path("reports/gv_war_room/war_room_latest.csv")
SUMMARY = Path("reports/gv_war_room/WAR_ROOM_SUMMARY.md")


def run_cmd(cmd):
    started = datetime.utcnow().isoformat()
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        return {
            "started_utc": started,
            "returncode": result.returncode,
            "stdout": result.stdout.strip().replace("\n", " | "),
            "stderr": result.stderr.strip().replace("\n", " | "),
        }
    except Exception as e:
        return {
            "started_utc": started,
            "returncode": -1,
            "stdout": "",
            "stderr": str(e),
        }


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)

    rows = []

    for run in RUNS:
        result = run_cmd(run["cmd"])
        expected = Path(run["expected_output"])
        rows.append({
            "name": run["name"],
            "returncode": result["returncode"],
            "expected_output": str(expected),
            "output_exists": expected.exists(),
            "started_utc": result["started_utc"],
            "stdout": result["stdout"],
            "stderr": result["stderr"],
        })

    with OUT.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    failures = [r for r in rows if int(r["returncode"]) != 0 or not r["output_exists"]]

    SUMMARY.write_text(
        "# GV War Room Latest\n\n"
        "Purpose: run the current fastest battle pipeline without changing detector logic.\n\n"
        f"Runs: {len(rows)}\n\n"
        f"Failures: {len(failures)}\n\n"
        "## Results\n\n"
        + "\n".join(
            f"- {r['name']}: returncode={r['returncode']}, output_exists={r['output_exists']}"
            for r in rows
        )
        + "\n\n## Rule\n\nFast is allowed. Hidden rescue logic is not.\n",
        encoding="utf-8",
    )

    print(SUMMARY.read_text())


if __name__ == "__main__":
    main()
