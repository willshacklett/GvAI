let lastAlertKey = null;

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

function ensureBanner() {
  let banner = document.getElementById("alertBanner");
  if (!banner) {
    banner = document.createElement("div");
    banner.id = "alertBanner";
    banner.style.position = "sticky";
    banner.style.top = "0";
    banner.style.zIndex = "9999";
    banner.style.padding = "14px 18px";
    banner.style.fontWeight = "700";
    banner.style.textAlign = "center";
    banner.style.display = "none";
    banner.style.borderBottom = "1px solid rgba(255,255,255,0.15)";
    document.body.prepend(banner);
  }
  return banner;
}

function beep(severity) {
  const ctx = new (window.AudioContext || window.webkitAudioContext)();
  const osc = ctx.createOscillator();
  const gain = ctx.createGain();

  osc.type = severity === "CRITICAL" ? "sawtooth" : "square";
  osc.frequency.value = severity === "CRITICAL" ? 880 : 660;
  gain.gain.value = 0.03;

  osc.connect(gain);
  gain.connect(ctx.destination);

  osc.start();
  setTimeout(() => osc.stop(), severity === "CRITICAL" ? 250 : 140);
}

function updateBanner(data) {
  const banner = ensureBanner();
  const sev = data.severity;
  const summary = data.summary || {};
  const decision = data.decision || "—";

  const show = sev === "CRITICAL" || sev === "HIGH";
  if (!show) {
    banner.style.display = "none";
    return;
  }

  banner.style.display = "block";
  banner.style.background = sev === "CRITICAL" ? "#7f1d1d" : "#92400e";
  banner.style.color = "white";
  banner.textContent = `⚠ ${sev} ALERT — ${decision} | GV ${summary.gv_score ?? "—"} | ${summary.trend ?? "—"} | ${summary.label ?? "—"}`;

  const alertKey = [
    sev,
    decision,
    summary.timestamp,
    summary.gv_score,
    summary.trend,
    summary.label
  ].join("|");

  if (alertKey !== lastAlertKey) {
    lastAlertKey = alertKey;
    beep(sev);
  }
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
  if (!tbody) return;
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
  updateBanner(data);
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
setInterval(refresh, 3000);
