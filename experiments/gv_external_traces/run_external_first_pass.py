import subprocess
import sys
from pathlib import Path

RAW = Path("sample_data/gv_external_traces/messy_queue_pressure.csv")
NORMALIZED = Path("reports/gv_external_traces/messy_queue_pressure.normalized.csv")
VALIDATOR = Path("experiments/gv_real_world_validation/validate_timeseries.py")
NORMALIZER = Path("experiments/gv_external_traces/normalize_trace_csv.py")


def run(cmd):
    print("RUN:", " ".join(str(x) for x in cmd))
    subprocess.check_call([str(x) for x in cmd])


def main():
    run([
        sys.executable,
        NORMALIZER,
        RAW,
        NORMALIZED,
        "--time",
        "timestamp",
        "--value",
        "queue_pressure",
    ])

    run([
        sys.executable,
        VALIDATOR,
        NORMALIZED,
    ])


if __name__ == "__main__":
    main()
