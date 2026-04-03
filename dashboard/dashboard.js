async function loadData() {
  const candidates = [
    "./data/sentinel_output.json",
    "data/sentinel_output.json",
    "/data/sentinel_output.json"
  ];

  let data = null;
  let lastError = null;

  for (const path of candidates) {
    try {
      const res = await fetch(path, { cache: "no-store" });
      if (!res.ok) throw new Error(`HTTP ${res.status} for ${path}`);
      data = await res.json();
      console.log("Loaded dashboard data from:", path);
      break;
    } catch (err) {
      lastError = err;
      console.warn("Failed path:", path, err);
    }
  }

  if (!data) {
    throw lastError || new Error("Could not load dashboard data");
  }

  document.getElementById("scenario").textContent = data.scenario ?? "-";
  document.getElementById("status").textContent = data.result.status ?? "-";
  document.getElementById("leadTime").textContent = data.result.lead_time ?? "-";
  document.getElementById("fired").textContent = String(data.result.fired);
  document.getElementById("driftStep").textContent = data.result.drift_step ?? "-";
  document.getElementById("breachStep").textContent = data.result.breach_step ?? "-";
  document.getElementById("collapseStep").textContent = data.result.collapse_step ?? "-";
  document.getElementById("reasons").textContent = (data.result.reasons || []).join(" | ");

  document.getElementById("firstWarning").textContent = data.summary.first_warning ?? "-";
  document.getElementById("firstCritical").textContent = data.summary.first_critical ?? "-";
  document.getElementById("firstCollapse").textContent = data.summary.first_collapse ?? "-";

  const timelineEl = document.getElementById("timeline");
  timelineEl.innerHTML = "";

  for (const row of data.timeline || []) {
    const div = document.createElement("div");
    const status = row.status || "stable";
    div.className = `cell ${status}`;
    const mean = typeof row.mean === "number" ? row.mean.toFixed(3) : "-";
    const variance = typeof row.var === "number" ? row.var.toFixed(4) : "-";
    div.title = `t=${row.t} | ${status} | mean=${mean} | var=${variance}`;
    timelineEl.appendChild(div);
  }
}

loadData().catch(err => {
  console.error(err);
  document.body.insertAdjacentHTML(
    "beforeend",
    `<p style="color:#ff6b6b;padding:16px;">Failed to load dashboard data: ${String(err.message || err)}</p>`
  );
});
