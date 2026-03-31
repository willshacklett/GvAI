async function loadData() {
  const res = await fetch("gvai_state.json?_=" + Date.now());
  if (!res.ok) throw new Error("Could not load gvai_state.json");
  return res.json();
}

function severityClass(sev) {
  if (sev === "CRITICAL") return "badge badge-critical";
  if (sev === "HIGH") return "badge badge-high";
  if (sev === "MEDIUM") return "badge badge-medium";
  return "badge badge-info";
}

function setText(id, value) {
  document.getElementById(id).textContent = value ?? "—";
}

function renderHistory(rows) {
  const tbody = document.querySelector("#historyTable tbody");
  tbody.innerHTML = "";
  rows.forEach(row => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${row.timestamp ?? "—"}</td>
      <td>${row.label ?? "—"}</td>
      <td>${row.gv_score ?? "—"}</td>
      <td>${row.recoverability ?? "—"}</td>
      <td>${row.risk ?? "—"}</td>
    `;
    tbody.appendChild(tr);
  });
}

function renderAlerts(alerts) {
  const tbody = document.querySelector("#alertsTable tbody");
  tbody.innerHTML = "";
  alerts.forEach(alert => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${alert.logged_at ?? "—"}</td>
      <td><span class="${severityClass(alert.severity)}">${alert.severity ?? "—"}</span></td>
      <td>${alert.decision ?? "—"}</td>
      <td>${(alert.reasons || []).join(", ")}</td>
      <td>${alert.summary?.gv_score ?? "—"}</td>
      <td>${alert.summary?.trend ?? "—"}</td>
      <td>${alert.summary?.label ?? "—"}</td>
    `;
    tbody.appendChild(tr);
  });
}

function render(data) {
  const s = data.summary;

  setText("decision", data.decision);
  setText("gvScore", s.gv_score);
  setText("trend", s.trend);
  setText("recoveryState", s.recovery_state);
  setText("response", data.response);
  setText("action", data.action);
  setText("question", data.question);

  setText("avgGv", s.avg_gv);
  setText("deltaGv", s.delta_gv);
  setText("volatility", s.volatility);
  setText("risk", s.risk);
  setText("recoverability", s.recoverability);
  setText("recoveryConfidence", s.recovery_confidence);

  setText("timestamp", s.timestamp);
  setText("label", s.label);

  const sev = document.getElementById("severity");
  sev.innerHTML = `<span class="${severityClass(data.severity)}">${data.severity}</span>`;

  renderHistory(data.history || []);
  renderAlerts(data.alerts || []);
}

async function refresh() {
  try {
    const data = await loadData();
    render(data);
  } catch (err) {
    console.error(err);
  }
}

document.getElementById("refreshBtn").addEventListener("click", refresh);
refresh();
setInterval(refresh, 5000);
