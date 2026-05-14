import csv
import json
from pathlib import Path
import numpy as np

from validate_timeseries import rolling_gv, first_warning

INPUT = Path("sample_data/gv_real_world_validation/sample_service_latency.csv")
OUT_DIR = Path("reports/gv_real_world_validation")
OUT_JSON = OUT_DIR / "sample_service_latency_report.json"
OUT_HTML = OUT_DIR / "sample_service_latency_report.html"


def load_csv(path):
    rows = []
    with path.open(newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)

    times = [float(r["time"]) for r in rows]
    values = np.array([float(r["value"]) for r in rows], dtype=float)
    events = [r.get("event", "") for r in rows]

    return times, values, events


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    times, values, events = load_csv(INPUT)
    gv, recovery_times = rolling_gv(values)

    warning = first_warning(gv)

    failure_indices = [
        i for i, e in enumerate(events)
        if e.lower() in {"failure", "collapse", "incident"}
    ]

    first_failure = failure_indices[0] if failure_indices else None
    lead_time = first_failure - warning if warning is not None and first_failure is not None else None

    report = {
        "input": str(INPUT),
        "rows": len(values),
        "first_warning": warning,
        "first_failure": first_failure,
        "lead_time": lead_time,
        "min_gv": round(float(np.min(gv)), 4),
        "mean_gv": round(float(np.mean(gv)), 4),
        "series": [
            {
                "time": times[i],
                "value": float(values[i]),
                "gv": float(gv[i]),
                "event": events[i],
                "recovery_time": recovery_times[i],
            }
            for i in range(len(values))
        ],
    }

    OUT_JSON.write_text(json.dumps(report, indent=2), encoding="utf-8")

    html = f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>GV Real-World Validation Report</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  <style>
    body {{
      margin: 0;
      background:
        radial-gradient(circle at top left, rgba(0, 255, 200, 0.18), transparent 35%),
        radial-gradient(circle at bottom right, rgba(120, 90, 255, 0.20), transparent 35%),
        #05070d;
      color: #eafcff;
      font-family: Arial, sans-serif;
    }}
    header {{
      padding: 42px;
      text-align: center;
      border-bottom: 1px solid rgba(255,255,255,0.12);
    }}
    h1 {{
      font-size: 44px;
      margin: 0;
      letter-spacing: 1px;
    }}
    .subtitle {{
      opacity: 0.78;
      margin-top: 12px;
      font-size: 18px;
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(4, minmax(140px, 1fr));
      gap: 16px;
      padding: 24px;
    }}
    .card {{
      background: rgba(255,255,255,0.07);
      border: 1px solid rgba(255,255,255,0.12);
      border-radius: 18px;
      padding: 20px;
      box-shadow: 0 0 28px rgba(0,255,200,0.08);
    }}
    .label {{
      opacity: 0.65;
      font-size: 13px;
      text-transform: uppercase;
      letter-spacing: 1px;
    }}
    .value {{
      font-size: 32px;
      margin-top: 8px;
      font-weight: bold;
    }}
    .chart-wrap {{
      padding: 24px;
    }}
    canvas {{
      background: rgba(255,255,255,0.045);
      border: 1px solid rgba(255,255,255,0.12);
      border-radius: 18px;
      padding: 18px;
      margin-bottom: 24px;
      box-shadow: 0 0 36px rgba(0,255,200,0.08);
    }}
    .pulse {{
      animation: pulse 2.6s infinite;
    }}
    @keyframes pulse {{
      0% {{ text-shadow: 0 0 8px rgba(0,255,200,0.35); }}
      50% {{ text-shadow: 0 0 26px rgba(0,255,200,0.9); }}
      100% {{ text-shadow: 0 0 8px rgba(0,255,200,0.35); }}
    }}
  </style>
</head>
<body>
  <header>
    <h1 class="pulse">GV Real-World Validation</h1>
    <div class="subtitle">Recoverability loss detector — signal, warning, failure, and lead time.</div>
  </header>

  <section class="grid">
    <div class="card"><div class="label">First warning</div><div class="value">{warning}</div></div>
    <div class="card"><div class="label">First failure</div><div class="value">{first_failure}</div></div>
    <div class="card"><div class="label">Lead time</div><div class="value">{lead_time}</div></div>
    <div class="card"><div class="label">Min GV</div><div class="value">{round(float(np.min(gv)), 4)}</div></div>
  </section>

  <section class="chart-wrap">
    <canvas id="signalChart"></canvas>
    <canvas id="gvChart"></canvas>
    <canvas id="recoveryChart"></canvas>
  </section>

<script>
const report = {json.dumps(report)};
const labels = report.series.map(p => p.time);
const values = report.series.map(p => p.value);
const gv = report.series.map(p => p.gv);
const recovery = report.series.map(p => p.recovery_time);

const warning = report.first_warning;
const failure = report.first_failure;

function verticalMarker(index, label) {{
  return {{
    id: label,
    afterDraw(chart) {{
      if (index === null) return;
      const x = chart.scales.x.getPixelForValue(index);
      const ctx = chart.ctx;
      ctx.save();
      ctx.beginPath();
      ctx.moveTo(x, chart.chartArea.top);
      ctx.lineTo(x, chart.chartArea.bottom);
      ctx.lineWidth = 2;
      ctx.strokeStyle = label === "warning" ? "rgba(255, 230, 0, 0.9)" : "rgba(255, 60, 80, 0.9)";
      ctx.stroke();
      ctx.fillStyle = ctx.strokeStyle;
      ctx.fillText(label.toUpperCase(), x + 6, chart.chartArea.top + 16);
      ctx.restore();
    }}
  }}
}}

new Chart(document.getElementById("signalChart"), {{
  type: "line",
  data: {{
    labels,
    datasets: [{{
      label: "System value",
      data: values,
      borderWidth: 2,
      tension: 0.25,
      pointRadius: 2
    }}]
  }},
  options: {{
    plugins: {{ title: {{ display: true, text: "Raw System Signal" }} }},
    responsive: true
  }},
  plugins: [verticalMarker(warning, "warning"), verticalMarker(failure, "failure")]
}});

new Chart(document.getElementById("gvChart"), {{
  type: "line",
  data: {{
    labels,
    datasets: [{{
      label: "GV",
      data: gv,
      borderWidth: 3,
      tension: 0.25,
      pointRadius: 2
    }}]
  }},
  options: {{
    plugins: {{ title: {{ display: true, text: "GV Recoverability Signal" }} }},
    scales: {{ y: {{ min: 0, max: 1 }} }},
    responsive: true
  }},
  plugins: [verticalMarker(warning, "warning"), verticalMarker(failure, "failure")]
}});

new Chart(document.getElementById("recoveryChart"), {{
  type: "bar",
  data: {{
    labels,
    datasets: [{{
      label: "Recovery time",
      data: recovery
    }}]
  }},
  options: {{
    plugins: {{ title: {{ display: true, text: "Measured Recovery Time" }} }},
    responsive: true
  }},
  plugins: [verticalMarker(warning, "warning"), verticalMarker(failure, "failure")]
}});
</script>
</body>
</html>
"""

    OUT_HTML.write_text(html, encoding="utf-8")

    print({
        "html": str(OUT_HTML),
        "json": str(OUT_JSON),
        "first_warning": warning,
        "first_failure": first_failure,
        "lead_time": lead_time,
    })


if __name__ == "__main__":
    main()
