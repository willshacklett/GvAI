(function (root) {
  const escape = value => String(value ?? "").replace(/[&<>"']/g, character => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;"
  }[character]));
  const audiences = {
    laborers: {
      title: "Your region and your work",
      note: "Interpretation: regional conditions are context, not a verdict on you or a guarantee of work.",
      steps: "Region → occupation → task exposure → durable or augmentable tasks → adjacent roles → local jobs",
      implication: "Use the occupation and task evidence below to inspect what remains human-led and what may be augmented. Compare adjacent roles and current openings separately; regional STEX does not rate your personal background."
    },
    business: {
      title: "Workforce planning in this region",
      note: "Interpretation: published conditions support investigation, not a hiring, replacement, or ROI recommendation.",
      steps: "Region → workforce → exposure → constraints → scenarios → sources",
      implication: "Compare the workforce mix with the occupations your operation needs. Review employment, wages, and task evidence in your plan; examine augmentation before assuming replacement. Housing value / income is a regional constraint signal, not a hiring-cost estimate."
    },
    government: {
      title: "Observed conditions and signals to monitor",
      note: "Interpretation: planning implications are neutral observations, not policy mandates or jurisdiction rankings.",
      steps: "Observed conditions → structural exposure → constraints → scenarios → sources",
      implication: "Monitor labor availability, workforce composition, the housing ratio, and gaps in audited task coverage. Concentrated exposure may warrant further investigation, but these data do not forecast displacement or determine laws, candidates, or policy priorities."
    }
  };

  function createStore() {
    let state = { model: null, audience: "laborers", status: "idle", error: null };
    const listeners = new Set();
    const notify = () => listeners.forEach(listener => listener(state));
    return {
      get: () => state,
      subscribe(listener) { listeners.add(listener); listener(state); return () => listeners.delete(listener); },
      begin(selection = null) {
        const sameSelection = JSON.stringify(selection) === JSON.stringify(state.selection);
        state = { ...state, model: sameSelection ? state.model : null, selection, status: sameSelection && state.model ? "refreshing" : "loading", error: null };
        notify();
      },
      set(model) {
        if (model?.schema_version !== "gvai.regional-intelligence.v1" || !model.region || !model.metrics || !model.availability) {
          throw new Error("Regional evidence response is invalid.");
        }
        state = { ...state, model, status: model.availability.status, error: null };
        notify();
      },
      fail() { state = { ...state, status: state.model ? "partial" : "unavailable", error: state.model ? "Refresh temporarily unavailable. Last-retrieved evidence remains visible; inspect its freshness." : "Regional data temporarily unavailable. Retry or select another region." }; notify(); },
      selectAudience(audience) {
        if (!audiences[audience]) throw new Error("Unknown audience");
        state = { ...state, audience };
        notify();
      },
      updateJobs(evidence, regionId) {
        if (!state.model || state.model.region.id !== regionId) return;
        const available = ["available_with_results", "available_zero_results"].includes(evidence.status);
        state = { ...state, model: { ...state.model, jobs: { ...evidence, classification: "source_statistic",
          method: "Provider listing results for this occupation/search, not total regional vacancies.", last_updated: null },
          availability: { ...state.model.availability, sections: { ...state.model.availability.sections,
            jobs: { status: available ? "available" : "unavailable", retryable: evidence.status === "temporarily_unavailable" } } } } };
        notify();
      }
    };
  }

  function formatMetric(metric) {
    const value = metric?.value;
    if (value === null || value === undefined || (typeof value === "number" && !Number.isFinite(value))) return "Unavailable";
    if (typeof value === "string") return value.charAt(0).toUpperCase() + value.slice(1);
    if (metric.unit === "USD") return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 }).format(value);
    const number = new Intl.NumberFormat("en-US", { maximumFractionDigits: metric.unit === "people" || metric.unit === "jobs" ? 0 : 1 }).format(value);
    return number + (metric.unit === "%" ? "%" : metric.unit === "ratio" ? "×" : metric.unit === "years" ? " years" : metric.unit === "STEX points" ? " points" : "");
  }

  function sourceDetails(metric, model) {
    const sources = (metric.source_ids || []).map(id => model.sources?.[id]).filter(Boolean);
    const category = { source_statistic: "Source data", derived_metric: "GVAI-derived",
      scenario_output: "Scenario output", model_interpretation: "AI interpretation" }[metric.classification] || "Classification unavailable";
    const labels = sources.map(source => `${source.name}${source.vintage ? ` · ${source.vintage}` : ""}${source.geography?.type === "oews_labor_market_area" ? ` · ${source.geography.label}` : ""}`).join(" + ");
    const links = sources.map(source => {
      const link = source.url && /^https:\/\//.test(source.url)
        ? `<a href="${escape(source.url)}" target="_blank" rel="noopener noreferrer">${escape(source.name)}</a>`
        : escape(source.name);
      return `<li>${link}: ${escape(source.dataset)}${source.vintage ? ` · vintage ${escape(source.vintage)}` : " · vintage not specified"}${source.last_updated ? ` · updated ${escape(source.last_updated)}` : " · source update date not supplied"}</li>`;
    }).join("");
    return `<details class="regional-source-note"><summary>${category}${labels ? ` · ${escape(labels)}` : " · methodology unavailable"}</summary><p>${escape(metric.method)}</p>${metric.reason ? `<p>${escape(metric.reason)}</p>` : ""}<ul>${links}</ul></details>`;
  }

  function metricMarkup(key, model) {
    const metric = model.metrics[key];
    if (!metric) return "";
    return `<div class="regional-stat" data-regional-metric="${escape(key)}"><dt>${escape(metric.label)}</dt><dd>${escape(formatMetric(metric))}</dd>${sourceDetails(metric, model)}</div>`;
  }

  function briefMarkup(model, audience = null) {
    if (!model) return '<p class="regional-empty">Select a region on the globe to inspect its evidence.</p>';
    const metrics = model.metrics;
    const known = ["labor_availability", "home_value_to_income_ratio", "stex_coverage"].filter(key => metrics[key]?.value !== null && metrics[key]?.value !== undefined);
    const outlook = known.length
      ? known.map(key => `${metrics[key].label}: ${formatMetric(metrics[key])}`).join(" · ")
      : "Published signals are unavailable for this selection.";
    const selected = audiences[audience];
    const groups = model.workforce_mix || [];
    const workforce = groups.length ? `<details class="regional-workforce"><summary>Workforce mix · ACS S2401${model.sources.workforce.vintage ? ` · ${escape(model.sources.workforce.vintage)}` : ""}</summary><ul>${groups.map(group => `<li>${escape(group.label)}: ${group.employed == null ? "Unavailable" : escape(new Intl.NumberFormat("en-US").format(group.employed))} employed · ${group.share_percent == null ? "share unavailable" : `${escape(group.share_percent)}% share`}</li>`).join("")}</ul><p>Employment counts: source data. Shares: GVAI-derived counts / ACS employed population. Broad groups are not industry-specific hiring demand.</p></details>` : "";
    const retryable = Object.entries(model.availability.sections || {}).some(([key, section]) => ["acs", "workforce"].includes(key) && section.status === "unavailable" && section.retryable);
    const retry = retryable ? '<button type="button" class="regional-summary-retry" data-regional-refresh>Retry ACS evidence</button>' : "";
    const jobs = model.jobs;
    const search = jobs?.search_context || {};
    const searchLabel = search.location || (Number.isFinite(search.latitude) && Number.isFinite(search.longitude) ? `${search.latitude}, ${search.longitude}` : search.country_code || "search geography not supplied");
    const jobsMarkup = jobs && jobs.status !== "not_requested" ? `<p class="regional-jobs-signal">Source data · Latest occupation jobs search: ${jobs.result_count == null ? "unavailable" : `${escape(jobs.result_count)} listings returned`} · ${escape((jobs.source_names || []).join(", ") || "source unavailable")}. Search geography: ${escape(searchLabel)}. Not total regional vacancies or necessarily confined to the selected county. ${jobs.retrieved_at ? `Retrieved ${escape(jobs.retrieved_at)}.` : ""}</p>` : "";
    return [
      `<h2 class="regional-region-title">${escape(model.region.label)}</h2>`,
      `<p class="regional-outlook-line">${escape(outlook)}</p>`,
      `<p class="regional-availability">${model.availability.status === "partial" ? "Partial evidence" : model.availability.status === "unavailable" ? "Evidence unavailable" : "Published evidence available"} · ${escape(model.region.type)}${model.region.id ? ` · ${escape(model.region.id)}` : " · stable identifier unavailable"}</p>`,
      `<dl class="regional-key-signals">${["population", "labor_force", "labor_availability", "automation_exposure", "home_value_to_income_ratio", "stex_coverage"].map(key => metricMarkup(key, model)).join("")}</dl>`,
      workforce, retry, jobsMarkup,
      selected ? `<section class="regional-interpretation" data-audience-section="${audience}"><h3>${selected.title}</h3><p class="regional-journey">${selected.steps}</p><p>${selected.implication}</p><small>${selected.note}</small></section>` : "",
      `<details class="regional-methods"><summary>Sources, freshness, and data gaps</summary><p>Retrieved ${escape(model.freshness?.retrieved_at || "time unavailable")}. Retrieval is not the publication date; source update dates are unknown unless supplied.</p><dl class="regional-extra-metrics">${["unemployment_rate", "median_household_income", "median_home_value", "median_age", "stex_covered_employment", "total_employment", "stability_index"].map(key => metricMarkup(key, model)).join("")}</dl><p>STEX coverage is labor-market-area evidence, not a county estimate. It covers audited occupations only; missing task audits do not imply zero exposure.</p><p>Live job listings require an occupation search. No regional vacancy total or validated displacement, industry concentration, resilience, or stability composite is connected.</p></details>`
    ].join("");
  }

  function contextForChat(model, audience) {
    if (!model || !audiences[audience]) throw new Error("Select a region and audience first.");
    return {
      schema_version: model.schema_version, region: model.region, metrics: model.metrics,
      sources: model.sources, availability: model.availability, jobs: model.jobs, audience,
      stex: { coverage: model.metrics.stex_coverage, audited_exposure: model.metrics.automation_exposure }
    };
  }

  function scenario(inputs) {
    const limits = { workers: [1, 1000000], weeklyHours: [1, 168], taskShare: [0, 100], timeSaving: [0, 100] };
    for (const [key, [minimum, maximum]] of Object.entries(limits)) {
      const value = inputs[key];
      const decimal = typeof value === "number" || (typeof value === "string" && /^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:e[+-]?\d+)?$/i.test(value.trim()));
      if (!decimal || !Number.isFinite(Number(value)) || Number(value) < minimum || Number(value) > maximum || (key === "workers" && !Number.isInteger(Number(value)))) {
        throw new Error("Enter all four assumptions within the stated ranges.");
      }
    }
    const baselineHours = Number(inputs.workers) * Number(inputs.weeklyHours);
    const affectedHours = baselineHours * Number(inputs.taskShare) / 100;
    return { classification: "scenario_output", baselineHours, affectedHours, potentialHours: affectedHours * Number(inputs.timeSaving) / 100,
      method: "Assumed workers × weekly hours × affected task share × assumed task time saving. Not a forecast, job count, staffing recommendation, or ROI estimate." };
  }

  function baselineFromModel(model) {
    const region = model.region;
    const data = { ...region, supported: region.country_code === "US", data_available: model.availability.status !== "unavailable", scope: region.type,
      name: region.label, source: "U.S. Census Bureau ACS 5-year", acs_year: model.sources.acs?.vintage,
      occupation_profile: { data_available: model.availability.sections.workforce.status === "available", groups: model.workforce_mix } };
    for (const key of ["population", "labor_force", "unemployed", "unemployment_rate", "median_household_income", "median_home_value", "home_value_to_income_ratio", "median_age"]) data[key] = model.metrics[key]?.value ?? null;
    return data;
  }

  function taskPatterns(contributors) {
    const rated = contributors.filter(task => task.importance_status === "rated" && Number.isFinite(task.structural_exposure) && task.structural_exposure >= 0 && task.structural_exposure <= 100
      && Number.isFinite(task.source_importance) && task.source_importance > 0);
    return {
      lowerExposure: [...rated].sort((first, second) => first.structural_exposure - second.structural_exposure).slice(0, 3),
      augmentation: [...rated].filter(task => Number.isFinite(task.augmentation_likelihood) && task.augmentation_likelihood > 0)
        .sort((first, second) => second.augmentation_likelihood - first.augmentation_likelihood).slice(0, 3)
    };
  }

  function mount(store) {
    if (!root.document) return;
    store.subscribe(state => {
      root.document.querySelectorAll("[data-regional-brief]").forEach(element => {
        element.innerHTML = state.model ? `${state.error ? `<p role="status">${escape(state.error)}</p>` : state.status === "refreshing" ? '<p role="status">Refreshing public evidence; last-retrieved values remain visible.</p>' : ""}${briefMarkup(state.model, element.dataset.audience || null)}`
          : `<p class="regional-empty">${escape(state.error || (state.status === "loading" ? "Loading selected-region evidence…" : "Select a region on the globe to inspect its evidence."))}</p>`;
      });
      root.document.querySelectorAll("[data-region-label]").forEach(element => {
        element.textContent = state.model?.region.label || state.selection?.label || "Choose a region on the globe";
      });
      const selector = root.document.getElementById("regional-ask-audience");
      if (selector) selector.value = state.audience;
      const status = root.document.getElementById("regional-tools-context");
      if (status) status.textContent = state.model ? `${state.model.region.label} · ${state.audience}` : "Select a region before asking or building a scenario.";
    });
    root.document.addEventListener("click", event => {
      if (event.target.closest("[data-regional-refresh]")) root.document.getElementById("regional-retry").click();
    });
  }

  function unavailableModel(region, reason) {
    const names = { population: "Population", labor_force: "Civilian labor force", labor_availability: "Labor availability",
      automation_exposure: "Audited structural exposure", home_value_to_income_ratio: "Home value / income", stex_coverage: "STEX audit coverage",
      unemployed: "Unemployed", unemployment_rate: "Unemployment rate", median_household_income: "Median household income", median_home_value: "Median home value",
      median_age: "Median age", stex_covered_employment: "STEX-covered employment", total_employment: "OEWS reference employment", stability_index: "Post-Labor Stability Index",
      job_displacement: "Job displacement estimate", industry_concentration: "Industry concentration index", economic_resilience: "Economic resilience index" };
    const sourceFields = ["population", "labor_force", "unemployed", "median_household_income", "median_home_value", "median_age", "total_employment"];
    return { schema_version: "gvai.regional-intelligence.v1", region, sources: {}, workforce_mix: [], signals: [], summary: reason, constraints: [reason], freshness: {},
      metrics: Object.fromEntries(Object.entries(names).map(([key, label]) => [key, { label, value: null, unit: "", classification: sourceFields.includes(key) ? "source_statistic" : "derived_metric", source_ids: [], method: reason, availability: "unavailable", reason }])),
      availability: { status: "unavailable", sections: Object.fromEntries(["acs", "workforce", "stex", "jobs", "stability"].map(key => [key, { status: "unavailable", retryable: false }])) } };
  }

  root.GVAIRegional = { createStore, formatMetric, sourceDetails, briefMarkup, contextForChat, scenario, baselineFromModel, unavailableModel, taskPatterns, mount };
  if (typeof module !== "undefined" && module.exports) module.exports = root.GVAIRegional;
})(globalThis);