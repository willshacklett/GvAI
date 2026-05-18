const API = "/api/kernel/observatory";

function setText(id, value) {
  document.getElementById(id).textContent = value ?? "—";
}

function safeNum(value) {
  const n = Number(value);
  return Number.isFinite(n) ? n : 0;
}

async function loadTelemetry() {
  const feed = document.getElementById("feed");

  try {
    const res = await fetch(API);
    const data = await res.json();

    setText("rolling-gv", data.rolling_gv ?? "—");
    setText("trajectory-mode", data.trajectory_mode ?? "UNKNOWN");
    setText("intervention-level", data.intervention_level ?? "UNKNOWN");
    setText("total-events", data.total_events ?? 0);

    document.getElementById("drift-trend").value = Math.abs(safeNum(data.drift_trend));
    document.getElementById("recoverability-trend").value = Math.abs(safeNum(data.recoverability_trend));

    document.getElementById("latest-event").textContent = JSON.stringify(data.latest_event, null, 2);
    feed.textContent = JSON.stringify(data, null, 2);
  } catch (err) {
    feed.textContent = "Telemetry unavailable: " + err.message;
  }
}

document.getElementById("refresh").addEventListener("click", loadTelemetry);
loadTelemetry();
setInterval(loadTelemetry, 5000);
