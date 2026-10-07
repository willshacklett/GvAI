(function (root) {
  const MAX_REGIONS = 5;
  const audiences = ["laborers", "business", "government"];
  const simple = ["open_region_evidence", "open_jobs", "open_scenario", "show_sources"];
  const escape = value => String(value ?? "").replace(/[&<>"']/g, character => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;"
  }[character]));

  function validateAction(action, knownIds) {
    if (!action || typeof action !== "object" || Array.isArray(action)) return false;
    const exact = keys => Object.keys(action).sort().join() === keys.sort().join();
    if (action.type === "set_audience") return exact(["type", "audience"]) && audiences.includes(action.audience);
    if (["focus_region", "select_region"].includes(action.type)) {
      return (exact(["type", "region_id"]) && knownIds.includes(action.region_id)) ||
        (exact(["type", "query"]) && typeof action.query === "string" && /^[\p{L}\p{N}_ .,'()-]{1,160}$/u.test(action.query));
    }
    if (action.type === "compare_regions") {
      if (exact(["type", "queries"])) return Array.isArray(action.queries) && action.queries.length >= 2 &&
        action.queries.length <= MAX_REGIONS && new Set(action.queries).size === action.queries.length &&
        action.queries.every(query => typeof query === "string" && /^[\p{L}\p{N}_ .,'()-]{1,160}$/u.test(query));
      return exact(["type", "region_ids"]) && Array.isArray(action.region_ids) &&
        action.region_ids.length >= 2 && action.region_ids.length <= MAX_REGIONS &&
        new Set(action.region_ids).size === action.region_ids.length && action.region_ids.every(id => knownIds.includes(id));
    }
    if (action.type === "open_occupation") return exact(["type", "occupation_code"]) &&
      typeof action.occupation_code === "string" && /^\d{2}-\d{4}(?:\.\d{2})?$/.test(action.occupation_code);
    return simple.includes(action.type) && exact(["type"]);
  }

  function createStore(regional) {
    let messages = [], comparisons = [], occupation = null, scenario = null, intent = "", epoch = 0;
    let requestedActions = [], outcomes = [];
    let occupationEvidence = {};
    const evidence = new Map();
    const listeners = new Set();
    const prune = () => {
      const selected = regional.get().model?.region.id;
      for (const key of evidence.keys()) if (!comparisons.includes(key) && key !== selected) evidence.delete(key);
    };
    let lastSelection, lastAudience, lastRegionId;
    const get = () => ({
      audience: regional.get().audience, selectedRegion: regional.get().model?.region || null,
      evidence: regional.get().model, regionalStatus: regional.get().status,
      jobs: regional.get().model?.jobs || { status: "not_requested" },
      comparisons: comparisons.map(id => evidence.get(id)).filter(Boolean), comparisonIds: [...comparisons],
      knownRegions: [...evidence.values()].map(model => model.region),
      occupation, scenario, messages: [...messages], recentIntent: intent,
      requestedActions, outcomes, occupationEvidence, epoch
    });
    const notify = () => listeners.forEach(listener => listener(get()));
    regional.subscribe(state => {
      const id = state.model?.region.id;
      if (state.selection !== lastSelection || state.audience !== lastAudience || id !== lastRegionId) {
        epoch += 1;
        scenario = null;
      }
      lastSelection = state.selection; lastAudience = state.audience; lastRegionId = id;
      if (id) evidence.set(id, state.model);
      // Retain only shortlist evidence plus the current selection.
      for (const key of evidence.keys()) if (!comparisons.includes(key) && key !== id) evidence.delete(key);
      notify();
    });
    return {
      get,
      invalidateNavigation() { epoch += 1; notify(); },
      subscribe(listener) { listeners.add(listener); listener(get()); return () => listeners.delete(listener); },
      addMessage(role, content) {
        if (!["user", "assistant"].includes(role) || typeof content !== "string") throw new Error("Invalid conversation message");
        messages = [...messages, { role, content }].slice(-25);
        if (role === "user") intent = content;
        notify();
      },
      addComparison() {
        const model = regional.get().model;
        if (!model?.region.id) throw new Error("Select a resolved region first.");
        if (comparisons.includes(model.region.id)) return;
        if (comparisons.length >= MAX_REGIONS) throw new Error("The shortlist holds up to five regions. Remove one first.");
        comparisons = [...comparisons, model.region.id]; evidence.set(model.region.id, model); epoch += 1; notify();
      },
      compare(ids) {
        if (!validateAction({ type: "compare_regions", region_ids: ids }, [...evidence.keys()])) throw new Error("Comparison requires two to five known regions.");
        comparisons = [...ids]; prune(); epoch += 1; notify();
      },
      setComparisons(models) {
        if (!Array.isArray(models) || models.length < 2 || models.length > MAX_REGIONS ||
            models.some(model => model?.schema_version !== "gvai.regional-intelligence.v1" || !model.region?.id || !model.metrics || !model.availability) ||
            new Set(models.map(model => model.region.id)).size !== models.length) {
          throw new Error("Comparisons need two to five distinct resolved regions with regional evidence contracts.");
        }
        models.forEach(model => evidence.set(model.region.id, model));
        comparisons = models.map(model => model.region.id); prune(); epoch += 1; notify();
      },
      removeComparison(id) { comparisons = comparisons.filter(item => item !== id); if (id !== regional.get().model?.region.id) evidence.delete(id); epoch += 1; notify(); },
      selectOccupation(code) {
        if (typeof code !== "string" || !/^\d{2}-\d{4}(?:\.\d{2})?$/.test(code)) throw new Error("Invalid occupation code.");
        occupation = code; occupationEvidence = {}; epoch += 1; notify();
      },
      setOccupationEvidence(value) { occupationEvidence = value || {}; notify(); },
      setScenario(assumptions, result) {
        scenario = { region_id: regional.get().model?.region.id, assumptions, result };
        epoch += 1; notify();
      },
      beginActions(actions) { requestedActions = actions; outcomes = []; notify(); },
      actionResult(type, status, detail = null) {
        outcomes = [...outcomes, { type, status, ...(detail ? { detail: String(detail).slice(0, 240) } : {}) }].slice(-8); notify();
      },
      context() {
        const state = get();
        return { schema_version: "gvai.intelligence-session.v1", audience: state.audience,
          selected_region_id: state.selectedRegion?.id || null,
          regions: state.knownRegions.map(({ id, latitude, longitude }) => ({ id, latitude, longitude })),
          comparison_ids: [...comparisons], occupation_code: occupation,
          scenario: scenario ? { region_id: scenario.region_id, assumptions: scenario.assumptions } : null,
          messages: messages.slice(0, -1).map(message => ({
            ...message, content: new TextDecoder().decode(new TextEncoder().encode(message.content).slice(0, 8192), { stream: true })
          })), action_outcomes: outcomes.map(({ type, status }) => ({ type, status })) };
      },
      clearConversation() { messages = []; intent = ""; requestedActions = []; outcomes = []; notify(); }
    };
  }

  function createActionContext(store) {
    let expectedEpoch = store.get().epoch;
    return {
      isCurrent: () => store.get().epoch === expectedEpoch,
      update(mutation) {
        const current = store.get().epoch === expectedEpoch;
        const result = mutation();
        if (current) expectedEpoch = store.get().epoch;
        return result;
      }
    };
  }

  async function executeActions(store, actions, adapters, isCurrent = () => true) {
    if (!Array.isArray(actions)) {
      store.beginActions([]);
      store.actionResult("invalid", "rejected");
      return store.get().outcomes;
    }
    const bounded = actions.slice(0, 8);
    store.beginActions(bounded);
    for (const action of bounded) {
      if (!isCurrent()) { store.actionResult(action?.type || "invalid", "stale"); break; }
      if (!validateAction(action, store.get().knownRegions.map(region => region.id))) {
        store.actionResult("invalid", "rejected"); continue;
      }
      const adapter = adapters[action.type];
      if (typeof adapter !== "function") { store.actionResult(action.type, "unavailable"); continue; }
      try {
        const result = await adapter(action, isCurrent);
        store.actionResult(action.type, result === false ? "stale" : "completed");
      } catch (error) {
        store.actionResult(action.type, "failed", error.message);
        if (root.console) root.console.warn("GVAI interface request failed", action.type, error.message);
      }
    }
    if (actions.length > 8) store.actionResult("invalid", "rejected");
    return store.get().outcomes;
  }

  function occupationMarkup(evidence) {
    if (!evidence) return "<p>Occupation employment / wages: not requested in this conversation. Choose an occupation to investigate.</p>";
    const employment = evidence.employment || {}, wage = evidence.wage || {};
    return `<p>Source data · Occupation ${escape(evidence.occupation_code)} · OEWS area ${escape(evidence.geography?.id || "unavailable")}, not a county estimate.
      Employment: ${escape(root.GVAIRegional.formatMetric({ value: employment.employment, unit: "jobs" }))}.
      Median annual wage: ${escape(root.GVAIRegional.formatMetric({ value: wage.median_annual_wage, unit: "USD" }))}.
      ${escape(employment.source || wage.source || "Source unavailable")} · vintage ${escape(employment.source_year || wage.source_year || "not supplied")}.
      ${escape(evidence.oews_specificity?.disclosure || "Occupation specificity unavailable")}.</p>`;
  }

  function whyMarkup(model, audience) {
    if (!model) return '<p>Select a region to see why it matters. No regional evidence is assumed.</p>';
    const lens = {
      laborers: "For your work: inspect pay and occupation evidence alongside housing. Regional signals do not determine your personal prospects.",
      business: "For hiring: inspect labor-force size and occupation wages alongside housing pressure. Unemployment alone does not measure technician availability.",
      government: "For planning: inspect workforce composition and housing constraints. These observations are not policy mandates or displacement forecasts."
    }[audience];
    const metrics = ["labor_availability", "labor_force", "unemployment_rate", "median_household_income",
      "median_home_value", "home_value_to_income_ratio", "total_employment", "stex_coverage", "automation_exposure"];
    const rows = metrics.map(key => {
      const metric = model.metrics[key];
      if (!metric) return "";
      return `<div class="regional-stat"><dt>${escape(metric.label)}</dt><dd>${escape(root.GVAIRegional.formatMetric(metric))}</dd>${root.GVAIRegional.sourceDetails(metric, model)}</div>`;
    }).join("");
    const jobs = model.jobs || { status: "not_requested" };
    return `<h3>${escape(model.region.label)}</h3><p>AI interpretation · ${escape(lens)}</p>
      <p>This is your selected place, not an opaque GVAI ranking.</p><dl class="regional-key-signals">${rows}</dl>
      <p>Workforce composition · source employment counts / GVAI-derived shares:
      ${model.workforce_mix?.length ? model.workforce_mix.map(group => `${escape(group.label)}: ${escape(root.GVAIRegional.formatMetric({ value: group.employed, unit: "people" }))} employed / ${escape(root.GVAIRegional.formatMetric({ value: group.share_percent, unit: "%" }))} share`).join(" · ") : "Unavailable"}</p>
      <p>Jobs search: ${escape(jobs.status)}${jobs.result_count == null ? "" : ` · ${escape(jobs.result_count)} source listings, not total vacancies`}.
      ${escape((jobs.source_names || []).join(", "))}${jobs.retrieved_at ? ` · retrieved ${escape(jobs.retrieved_at)}` : ""}.
      Search geography: ${escape(jobs.search_context?.location || "not supplied")}. Hiring competition is not connected.</p>
      <p>Source vintage: ${escape(Object.values(model.sources || {}).map(source => `${source.name}: ${source.vintage ?? "not supplied"}`).join(" · "))}</p>`;
  }

  function comparisonMarkup(models, audience, occupationEvidence = {}) {
    if (!models.length) return "<p>Add the selected region, visit another place, and add it to compare. Up to five places; no universal ranking.</p>";
    const keys = ["labor_force", "unemployment_rate", "median_household_income", "median_home_value", "home_value_to_income_ratio", "labor_availability", "total_employment", "stex_coverage"];
    return `<p>AI interpretation · ${escape({
      laborers: "Look at housing and occupation pay; these are not personal job guarantees.",
      business: "Look at workforce size and housing pressure; missing occupation wages and competition limit hiring recommendations. Inspect available occupation evidence separately below.",
      government: "Look at observed differences and coverage gaps, not jurisdiction rankings."
    }[audience])}</p><p>Source geography and vintage may differ. Values are not necessarily comparable estimates.</p>
      <div class="intelligence-comparison-scroll"><table><caption>Regional evidence shortlist (${models.length}/5)</caption>
      <thead><tr><th scope="col">Signal</th>${models.map(model => `<th scope="col">${escape(model.region.label)}<button type="button" data-remove-region="${escape(model.region.id)}" aria-label="Remove ${escape(model.region.label)}">Remove</button></th>`).join("")}</tr></thead>
      <tbody>${keys.map(key => `<tr><th scope="row">${escape(models.find(model => model.metrics[key])?.metrics[key].label || key)}</th>${models.map(model => {
        const metric = model.metrics[key];
        return `<td>${escape(root.GVAIRegional.formatMetric(metric))}${metric ? root.GVAIRegional.sourceDetails(metric, model) : "<small>Evidence unavailable</small>"}</td>`;
      }).join("")}</tr>`).join("")}<tr><th scope="row">Occupation evidence</th>${models.map(model =>
        `<td>${occupationMarkup(occupationEvidence[model.region.id])}</td>`).join("")}</tr></tbody></table></div>`;
  }

  const api = { MAX_REGIONS, createStore, createActionContext, validateAction, executeActions, whyMarkup, comparisonMarkup, occupationMarkup, escape };
  root.GVAIIntelligence = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
})(typeof window !== "undefined" ? window : globalThis);
