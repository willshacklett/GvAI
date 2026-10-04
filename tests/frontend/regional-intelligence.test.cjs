const { test } = require("node:test");
const assert = require("node:assert/strict");
const regional = require("../../web/regional-intelligence.js");

function model() {
  const metric = (label, value, unit = "people", classification = "source_statistic") => ({ label, value, unit, classification, source_ids: ["acs"], method: "Synthetic fixture" });
  return { schema_version: "gvai.regional-intelligence.v1", region: { id: "US:county:47149", label: "Rutherford County, Tennessee", type: "county", country_code: "US" },
    metrics: { population: metric("Population", 363000), labor_force: metric("Labor force", 200000), labor_availability: metric("Labor availability", "balanced", "classification", "derived_metric"),
      home_value_to_income_ratio: metric("Home value / income", 5, "ratio", "derived_metric"), stex_coverage: metric("STEX coverage", null, "%", "derived_metric"), automation_exposure: metric("Audited exposure", null, "STEX points", "derived_metric") },
    sources: { acs: { name: "Census", dataset: "ACS 5-year", vintage: 2024 } }, workforce_mix: [],
    availability: { status: "partial", sections: { workforce: { status: "unavailable" } } }, freshness: { retrieved_at: "2026-10-03" } };
}

test("one store holds shared identity while audience switching preserves evidence", () => {
  const store = regional.createStore();
  const evidence = model();
  store.set(evidence);
  for (const audience of ["laborers", "business", "government"]) {
    store.selectAudience(audience);
    assert.equal(store.get().model, evidence);
    assert.equal(store.get().audience, audience);
  }
});

test("partial numbers keep explicit source and derived attribution", () => {
  const markup = regional.briefMarkup(model());
  assert.match(markup, /363,000/);
  assert.match(markup, /Partial evidence/);
  assert.match(markup, /Source data/);
  assert.match(markup, /GVAI-derived/);
  assert.match(markup, /Census · 2024/);
  assert.match(markup, /Unavailable/);
  assert.doesNotMatch(markup, /undefined|NaN/);
});

test("each audience receives distinct interpretation, not a new score", () => {
  assert.match(regional.briefMarkup(model(), "laborers"), /durable or augmentable tasks/);
  assert.match(regional.briefMarkup(model(), "business"), /augmentation before assuming replacement/);
  assert.match(regional.briefMarkup(model(), "government"), /not policy mandates or jurisdiction rankings/);
});

test("Ask carries stable identity, sources, audience and gaps", () => {
  const context = regional.contextForChat(model(), "government");
  assert.equal(context.region.id, "US:county:47149");
  assert.equal(context.audience, "government");
  assert.equal(context.availability.status, "partial");
  assert.equal(context.sources.acs.vintage, 2024);
});

test("scenario is transparent assumed task-hours arithmetic, not employment prediction", () => {
  const result = regional.scenario({ workers: 10, weeklyHours: 40, taskShare: 20, timeSaving: 50 });
  assert.equal(result.baselineHours, 400);
  assert.equal(result.potentialHours, 40);
  assert.equal(result.classification, "scenario_output");
  assert.match(result.method, /Not a forecast/);
});

test("scenario does not replace missing inputs with invented zero", () => {
  assert.throws(() => regional.scenario({ workers: "", weeklyHours: 40, taskShare: 20, timeSaving: 50 }));
  assert.equal(regional.formatMetric({ value: null }), "Unavailable");
  assert.equal(regional.formatMetric({ value: 0, unit: "%" }), "0%");
});

test("source and region strings are escaped", () => {
  const fixture = model();
  fixture.region.label = '<img src=x onerror="alert(1)">';
  assert.doesNotMatch(regional.briefMarkup(fixture), /<img/);
});

test("same-region failed refresh preserves useful retrieved evidence", () => {
  const store = regional.createStore();
  const selection = { label: "Rutherford County", latitude: 35.85, longitude: -86.4 };
  store.begin(selection);
  store.set(model());
  const evidence = store.get().model;
  store.begin(selection);
  store.fail();
  assert.equal(store.get().model, evidence);
  assert.match(store.get().error, /Last-retrieved/);
  store.begin({ label: "Another region" });
  assert.equal(store.get().model, null);
});

test("unavailable country never inherits US statistics or offers meaningless retry", () => {
  const evidence = regional.unavailableModel({ id: "FR:country", label: "France", type: "country", country_code: "FR" }, "No connected source.");
  assert.equal(evidence.metrics.population.value, null);
  const markup = regional.briefMarkup(evidence, "government");
  assert.match(markup, /France/);
  assert.doesNotMatch(markup, /Census|data-regional-refresh|363,000/);
});

test("task patterns use rated audit evidence only and do not invent durability", () => {
  const patterns = regional.taskPatterns([
    { task_title: "Low-rated task", importance_status: "rated", source_importance: 100, structural_exposure: 10, augmentation_likelihood: 20 },
    { task_title: "High-rated task", importance_status: "rated", source_importance: 100, structural_exposure: 80, augmentation_likelihood: 60 },
    { task_title: "Unknown", importance_status: "unrated", structural_exposure: 0, augmentation_likelihood: 100 }
  ]);
  assert.equal(patterns.lowerExposure[0].task_title, "Low-rated task");
  assert.equal(patterns.augmentation[0].task_title, "High-rated task");
  assert.equal(patterns.lowerExposure.length, 2);
});

test("job listing counts remain scoped source results, not regional totals", () => {
  const store = regional.createStore();
  store.set(model());
  store.updateJobs({ status: "available_with_results", result_count: 3, source_names: ["Synthetic provider"] }, "US:county:47149");
  assert.equal(store.get().model.jobs.result_count, 3);
  assert.match(store.get().model.jobs.method, /not total regional vacancies/);
  assert.equal(regional.contextForChat(store.get().model, "laborers").jobs.result_count, 3);
  store.updateJobs({ status: "available_with_results", result_count: 999 }, "another region");
  assert.equal(store.get().model.jobs.result_count, 3);
});

test("scenario rejects blank, coercible, nonfinite and out-of-bound assumptions", () => {
  const valid = { workers: 10, weeklyHours: 40, taskShare: 20, timeSaving: 50 };
  for (const key of Object.keys(valid)) {
    for (const value of ["", " ", null, undefined, -1, 1e30, NaN, Infinity, "Infinity", "NaN", "abc", "0x10", true, [], {}]) {
      assert.throws(() => regional.scenario({ ...valid, [key]: value }), `${key}: ${String(value)}`);
    }
  }
  assert.throws(() => regional.scenario({ ...valid, workers: 0 }));
  assert.throws(() => regional.scenario({ ...valid, workers: 1.5 }));
  assert.throws(() => regional.scenario({ ...valid, weeklyHours: 0 }));
  for (const key of ["taskShare", "timeSaving"]) assert.throws(() => regional.scenario({ ...valid, [key]: 101 }));
  assert.equal(regional.scenario({ ...valid, taskShare: 0 }).potentialHours, 0);
  assert.equal(regional.scenario({ ...valid, timeSaving: 0 }).potentialHours, 0);
  assert.equal(regional.scenario({ ...valid, taskShare: 100, timeSaving: 100 }).potentialHours, 400);
});

test("job search geography remains explicit when it differs from the selected county", () => {
  const fixture = model();
  fixture.jobs = { status: "available_with_results", result_count: 3, source_names: ["Provider"], search_context: { location: "Austin, Texas" } };
  const markup = regional.briefMarkup(fixture, "government");
  assert.match(markup, /Search geography: Austin, Texas/);
  assert.match(markup, /not necessarily confined|necessarily confined/);
  assert.match(markup, /Rutherford County/);
});