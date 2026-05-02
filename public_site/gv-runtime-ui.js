(function () {
  if (window.__GV_RUNTIME_UI_INSTALLED__) return;
  window.__GV_RUNTIME_UI_INSTALLED__ = true;

  const originalFetch = window.fetch.bind(window);

  function round(x) {
    return typeof x === "number" ? Math.round(x * 1000) / 1000 : x;
  }

  function footer(data) {
    if (!data || !data.gv) return "";
    const gv = data.gv || {};
    const pre = data.gv_precheck || {};
    return "\n\n---\nGV Signal\n" +
      "Mode: " + (gv.mode || "UNKNOWN") +
      " | Score: " + round(gv.survivability_score ?? 0) +
      " | Drift: " + round(gv.drift_risk ?? 0) +
      " | Recoverability: " + round(gv.recoverability ?? 0) + "\n" +
      "Precheck: " + (pre.mode || "UNKNOWN") +
      " | Enforced: " + (data.gv_enforced ? "YES" : "NO") +
      " | Provider: " + (data.model_provider || "unknown");
  }

  function showSignal(data) {
    if (!data || !data.gv) return;

    let box = document.getElementById("gv-runtime-signal");
    if (!box) {
      box = document.createElement("div");
      box.id = "gv-runtime-signal";
      document.body.appendChild(box);
    }

    const gv = data.gv || {};
    const mode = gv.mode || "UNKNOWN";
    box.className = "gv-runtime-signal mode-" + String(mode).toLowerCase();
    box.innerHTML =
      "<strong>GV</strong> <span>" + mode + "</span> " +
      "<small>score " + round(gv.survivability_score ?? 0) +
      " · drift " + round(gv.drift_risk ?? 0) +
      " · recovery " + round(gv.recoverability ?? 0) +
      "</small>";
  }

  const style = document.createElement("style");
  style.textContent = `
    #gv-runtime-signal {
      position: fixed;
      right: 18px;
      bottom: 18px;
      z-index: 99999;
      display: flex;
      gap: 8px;
      align-items: center;
      padding: 10px 12px;
      border-radius: 999px;
      border: 1px solid rgba(255,255,255,.16);
      background: rgba(8, 13, 28, .92);
      color: #eaf2ff;
      font: 13px system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      box-shadow: 0 10px 30px rgba(0,0,0,.35);
      backdrop-filter: blur(10px);
    }
    #gv-runtime-signal span {
      padding: 2px 7px;
      border-radius: 999px;
      font-weight: 700;
    }
    #gv-runtime-signal.mode-allow span { background: rgba(34,197,94,.18); color: #86efac; }
    #gv-runtime-signal.mode-qualify span { background: rgba(234,179,8,.18); color: #fde68a; }
    #gv-runtime-signal.mode-block span { background: rgba(239,68,68,.18); color: #fecaca; }
  `;
  document.head.appendChild(style);

  window.fetch = async function (...args) {
    const response = await originalFetch(...args);
    try {
      const url = String(args[0]?.url || args[0]);
      if (!url.includes("/api/chat")) return response;

      const data = await response.clone().json();
      if (!data || !data.gv) return response;

      showSignal(data);

      const modified = { ...data };
      const add = footer(data);

      if (typeof modified.reply === "string" && !modified.reply.includes("GV Signal")) modified.reply += add;
      if (typeof modified.response === "string" && !modified.response.includes("GV Signal")) modified.response += add;

      return new Response(JSON.stringify(modified), {
        status: response.status,
        statusText: response.statusText,
        headers: { "Content-Type": "application/json" }
      });
    } catch {
      return response;
    }
  };
})();
