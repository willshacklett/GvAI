(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.GVAIInvestigation = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";
  const VERSION = "gvai.investigation.v1", MAX_CANDIDATES = 8;
  const TYPES = ["worker_opportunity", "relocation", "career_transition", "business_expansion", "hiring_workforce", "government_monitoring", "regional_comparison"];
  const KEYS = ["occupations", "workforce_availability", "wage_level", "housing_pressure", "labor_force", "distance_radius", "geography", "current_jobs", "occupational_composition", "stex", "user_priority"];
  const text = (value, limit) => typeof value === "string" && value.trim().length > 0 && Array.from(value).length <= limit;
  const exact = (item, keys) => !!item && typeof item === "object" && !Array.isArray(item) && Object.keys(item).sort().join(",") === keys.slice().sort().join(",");
  const esc = value => String(value ?? "").replace(/[&<>"']/g, char => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[char]));
  const label = key => key.replace(/_/g, " ");
  function criteriaValid(items) {
    if (!Array.isArray(items) || items.length > KEYS.length) return false;
    const seen = new Set();
    return items.every(item => {
      if (!exact(item, ["key", "value", "direction", "priority"]) || !KEYS.includes(item.key) || seen.has(item.key) ||
          !["lower", "higher", "inspect"].includes(item.direction) || !["primary", "secondary", "constraint"].includes(item.priority)) return false;
      seen.add(item.key);
      if (item.key === "occupations") {
        const codes = new Set();
        return Array.isArray(item.value) && item.value.length >= 1 && item.value.length <= 5 && item.value.every(occupation => {
          if (!exact(occupation, ["code", "workers"]) || typeof occupation.code !== "string" || !/^\d{2}-\d{4}(?:\.\d{2})?$/.test(occupation.code) || codes.has(occupation.code) ||
              !(occupation.workers === null || (Number.isInteger(occupation.workers) && occupation.workers >= 1 && occupation.workers <= 1000000))) return false;
          codes.add(occupation.code);
          return true;
        });
      }
      if (item.key === "distance_radius") return exact(item.value, ["miles", "center"]) && Number.isFinite(item.value.miles) &&
        item.value.miles >= 1 && item.value.miles <= 3000 && text(item.value.center, 160);
      return text(item.value, 400);
    });
  }
  function validAction(action, known) {
    switch (action?.type) {
      case "start_investigation": return exact(action, ["type", "investigation_type", "question"]) && TYPES.includes(action.investigation_type) && text(action.question, 1000);
      case "set_criteria": return exact(action, ["type", "criteria"]) && criteriaValid(action.criteria);
      case "remove_candidate": case "shortlist_candidate": case "focus_candidate":
        return exact(action, ["type", "region_id"]) && known.has(action.region_id);
      case "reject_candidate": return exact(action, ["type", "region_id", "reason"]) && known.has(action.region_id) && text(action.reason, 500);
      case "compare_candidates": return exact(action, ["type"]);
      default: return false;
    }
  }
  function create(type, question) {
    if (!TYPES.includes(type) || !text(question, 1000)) throw new Error("Invalid decision type or question.");
    return { schema_version: VERSION, type, question, criteria: [], candidates: [] };
  }
  function mergeCriteria(investigation, criteria) {
    if (!investigation) throw new Error("Start an investigation before setting criteria.");
    if (!criteriaValid(criteria)) throw new Error("Invalid investigation criteria.");
    const merged = new Map(investigation.criteria.map(item => [item.key, item]));
    criteria.forEach(item => merged.set(item.key, structuredClone(item)));
    return { ...investigation, criteria: [...merged.values()] };
  }
  function mutateCandidate(investigation, regionId, status, reason = null) {
    if (!investigation) throw new Error("Start an investigation before managing candidates.");
    let candidates = investigation.candidates.filter(item => item.region_id !== regionId);
    if (status !== "removed") {
      if (!["candidate", "shortlisted", "rejected"].includes(status) || (status === "rejected" && !text(reason, 500))) throw new Error("A rejection needs an explicit reason.");
      if (candidates.length >= MAX_CANDIDATES) throw new Error("Investigation limit: eight candidates. Remove one before adding another.");
      if (status === "shortlisted" && candidates.filter(item => item.status === "shortlisted").length >= 5) throw new Error("Shortlist limit: five regions.");
      const replacement = { region_id: regionId, status, reason };
      candidates = investigation.candidates.some(item => item.region_id === regionId)
        ? investigation.candidates.map(item => item.region_id === regionId ? replacement : item)
        : [...candidates, replacement];
    }
    return { ...investigation, candidates };
  }
  function render(state) {
    const investigation = state.investigation;
    if (!investigation) return "<p>Start with a decision. Your question, criteria and candidate places will appear here.</p>";
    const read = state.decisionRead;
    const criteria = investigation.criteria.map(item => {
      const value = item.key === "occupations" ? item.value.map(occupation => `${occupation.workers ?? "unspecified"} workers · ${occupation.code}`).join("; ") :
        item.key === "distance_radius" ? `${item.value.miles} miles of ${item.value.center} (unverified boundary)` : item.value;
      return `<li><strong>${esc(label(item.key))}</strong>: ${esc(value)} · ${esc(item.priority)} / ${esc(item.direction)}</li>`;
    }).join("");
    const editors = investigation.criteria.map(item =>
      `<li><strong>${esc(label(item.key))}</strong>
        <select aria-label="Priority for ${esc(label(item.key))}" data-criterion-key="${esc(item.key)}" data-criterion-field="priority">${["primary", "secondary", "constraint"].map(option => `<option ${item.priority === option ? "selected" : ""}>${option}</option>`).join("")}</select>
        <select aria-label="Direction for ${esc(label(item.key))}" data-criterion-key="${esc(item.key)}" data-criterion-field="direction">${["higher", "lower", "inspect"].map(option => `<option ${item.direction === option ? "selected" : ""}>${option}</option>`).join("")}</select>
        <button type="button" data-remove-criterion="${esc(item.key)}">Remove criterion</button></li>`
    ).join("");
    const candidates = investigation.candidates.map(item => {
      const region = state.knownRegions.find(region => region.id === item.region_id);
      const explanation = read?.region_reads?.[item.region_id];
      const supports = explanation?.supports?.map(signal => `${label(signal.criterion)}${signal.occupation_code ? ` (${signal.occupation_code})` : ""}`).join(", ");
      const tradeoffs = explanation?.tradeoffs?.map(signal => `${label(signal.criterion)}${signal.occupation_code ? ` (${signal.occupation_code})` : ""}`).join(", ");
      return `<li><strong>${esc(region?.label || item.region_id)}</strong> · ${esc(item.status)}
        ${item.reason ? `<p>Interpretation / rejection reason: ${esc(item.reason)}</p>` : ""}
        <p>Why here: ${supports ? `Ahead on ${esc(supports)}.` : "No comparable favorable signal established."} ${tradeoffs ? `Behind on ${esc(tradeoffs)}.` : ""}</p>
        <details><summary>What moves it up or eliminates it?</summary>
          <p>Moves up if: ${esc(explanation?.could_move_up?.join(" ") || "Comparable evidence closes a primary gap, or your accepted tradeoff changes.")}</p>
          <p>Eliminated if: ${esc(explanation?.could_eliminate?.join(" ") || "Verified constraints rule it out or it no longer meets your primary criteria.")}</p>
        </details>
        ${["focus_candidate", "shortlist_candidate", "remove_candidate"].map(type => `<button type="button" data-candidate-action="${type}" data-region-id="${esc(item.region_id)}">${type === "focus_candidate" ? "Focus" : type === "shortlist_candidate" ? "Shortlist" : "Remove"}</button>`).join("")}
        <details><summary>Reject this place</summary><label>Reason to reject <input maxlength="500" data-rejection-for="${esc(item.region_id)}" placeholder="Tradeoff you will not accept"></label>
        <button type="button" data-candidate-action="reject_candidate" data-region-id="${esc(item.region_id)}">Reject</button></details></li>`;
    }).join("");
    const gaps = read?.evidence_gaps?.map(gap => `<li>${esc(label(gap.criterion))}: ${esc(gap.reason)}</li>`).join("");
    const signals = read?.signals?.map(signal => `<li><strong>${esc(label(signal.criterion))}${signal.occupation_code ? ` · ${esc(signal.occupation_code)}` : ""}</strong> (${esc(signal.priority)}, ${esc(signal.direction)}) · ${signal.comparable ? "Comparable" : "Not ranked"}
      <ul>${signal.values.map(value => `<li>${esc(state.knownRegions.find(region => region.id === value.region_id)?.label || value.region_id)}: ${value.value == null ? "Unavailable, not zero" : esc(value.value)} · ${esc(value.classification || "unavailable")} · ${esc(Object.values(value.sources || {}).map(source => `${source.name || source.dataset || "source"} ${source.vintage ?? "vintage unavailable"}`).join("; "))} · ${esc(value.geography?.id || Object.values(value.geography || {}).map(area => area?.label || area?.id || "").join("; ") || "geography unavailable")}</li>`).join("")}</ul>
      <small>${esc(signal.note)}</small></li>`).join("");
    return `<p><strong>Question</strong> · ${esc(investigation.question)}</p><small>${esc(label(investigation.type))} · public, memory-only investigation</small>
      <h3>Current read · interpretation</h3><p>${esc(read?.current_read || "Criteria or evidence changed. Reassess before relying on a conclusion.")}</p>
      <h3>Criteria</h3><p class="intelligence-note">AI-parsed user criteria. Correct priorities here, or tell the guide what to change. No private profile is imported.</p><ul>${criteria || "<li>Not captured yet.</li>"}</ul>
      <details data-criteria-editor><summary>Edit priorities and directions</summary><ul>${editors}</ul></details>
      <h3>Candidates</h3><ul>${candidates || "<li>Name places to retrieve evidence. No nationwide candidate search is connected.</li>"}</ul>
      <button type="button" data-investigation-command="compare">Compare candidates</button>
      <details><summary>Evidence gaps (${read?.evidence_gaps?.length ?? "not assessed"})</summary><ul>${gaps || "<li>Reassess to establish current coverage.</li>"}</ul></details>
      ${read?.missing_criteria?.length ? `<p>Missing criteria: ${esc(read.missing_criteria.map(label).join(", "))}</p>` : ""}
      ${read?.clarification ? `<p>${esc(read.clarification)}</p>` : ""}
      ${signals ? `<details><summary>Evidence behind the tradeoffs</summary><ul>${signals}</ul></details>` : ""}
      <h3>Could change if</h3><ul>${read?.could_change_if?.map(value => `<li>${esc(value)}</li>`).join("") || "<li>Current evidence and priorities need assessment.</li>"}</ul>
      <button type="button" data-investigation-command="reassess">Reassess with these criteria</button>
      <button type="button" data-investigation-command="leader">Ask why the working leader is ahead</button>`;
  }
  return { VERSION, MAX_CANDIDATES, TYPES, KEYS, criteriaValid, validAction, create, mergeCriteria, mutateCandidate, render };
});
