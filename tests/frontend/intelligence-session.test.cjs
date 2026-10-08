const { test } = require("node:test");
const assert = require("node:assert/strict");
global.GVAIRegional = require("../../web/regional-intelligence.js");
const intelligence = require("../../web/intelligence-session.js");

function model(id = "US:county:47149") {
  const result = GVAIRegional.unavailableModel({ id, label: id === "US:county:47149" ? "Rutherford County" : id,
    country_code: "US", type: "county", latitude: 35.85, longitude: -86.4 }, "Synthetic gap");
  result.metrics.labor_force.value = 200000;
  result.sources.acs = { name: "Census", dataset: "ACS", vintage: 2024 };
  result.metrics.labor_force.source_ids = ["acs"];
  return result;
}

function setup() {
  const regional = GVAIRegional.createStore();
  const session = intelligence.createStore(regional);
  regional.set(model());
  return { regional, session };
}

test("session references authoritative evidence and preserves multi-turn context across audiences", () => {
  const { regional, session } = setup();
  session.addMessage("user", "I need cheaper housing");
  session.addMessage("assistant", "We are investigating Rutherford");
  session.addMessage("user", "Compare it");
  for (const audience of ["laborers", "business", "government"]) {
    regional.selectAudience(audience);
    assert.equal(session.get().audience, audience);
    assert.equal(session.get().evidence, regional.get().model);
    assert.equal(session.context().messages[0].content, "I need cheaper housing");
  }
  assert.equal(session.get().recentIntent, "Compare it");
  assert.equal(session.context().messages.length, 2);
});

test("shortlist retains evidence references in stable order, bounds and deduplicates", () => {
  const { regional, session } = setup();
  const first = regional.get().model;
  session.addComparison(); session.addComparison();
  for (let index = 0; index < 4; index++) { regional.set(model(`US:county:4700${index}`)); session.addComparison(); }
  assert.equal(session.get().comparisons.length, 5);
  assert.equal(session.get().comparisons[0], first);
  regional.set(model("US:county:47099"));
  assert.throws(() => session.addComparison(), /five/);
  session.removeComparison(first.region.id);
  session.addComparison();
  assert.equal(session.get().comparisons.length, 5);
});

test("approved actions switch audience without changing regional truth", async () => {
  const { regional, session } = setup();
  const first = regional.get().model;
  const outcomes = await intelligence.executeActions(session, [{ type: "set_audience", audience: "business" }],
    { set_audience: action => regional.selectAudience(action.audience) });
  assert.equal(session.get().audience, "business");
  assert.equal(regional.get().model, first);
  assert.equal(outcomes[0].status, "completed");
});

test("unknown, malformed, arbitrary code, URLs and extra parameters never reach adapters", async () => {
  const { session } = setup();
  let calls = 0;
  const actions = [null, { type: "eval", code: "alert(1)" }, { type: "select_region", query: "javascript:alert(1)" },
    { type: "open_jobs", url: "https://example.org" }, { type: "focus_region", region_id: "unknown" },
    { type: "set_audience", audience: {} }, { type: "open_occupation", occupation_code: "<script>" }];
  const adapters = Object.fromEntries(["eval", "open_jobs", "focus_region", "select_region", "set_audience"].map(type => [type, () => { calls++; }]));
  const results = await intelligence.executeActions(session, actions, adapters);
  assert.equal(calls, 0);
  assert.ok(results.every(result => result.status === "rejected"));
});

test("stale region guards prevent delayed or subsequent action execution", async () => {
  const { regional, session } = setup();
  const epoch = session.get().epoch;
  let calls = 0;
  regional.begin({ label: "Newer selection", latitude: 0, longitude: 0 });
  const outcomes = await intelligence.executeActions(session, [{ type: "select_region", query: "Old county" }],
    { select_region: () => { calls++; } }, () => session.get().epoch === epoch);
  assert.equal(calls, 0);
  assert.equal(outcomes[0].status, "stale");
  assert.equal(session.get().evidence, null);
});

test("Why Here exposes evidence, unavailable signals, vintage and interpretation", () => {
  const markup = intelligence.whyMarkup(model(), "business");
  assert.match(markup, /Rutherford County/);
  assert.match(markup, /200,000/);
  assert.match(markup, /Source data/);
  assert.match(markup, /GVAI-derived/);
  assert.match(markup, /AI interpretation/);
  assert.match(markup, /Unavailable/);
  assert.match(markup, /2024/);
  assert.doesNotMatch(markup, /best place|NaN|undefined/);
  for (const audience of ["laborers", "business", "government"]) assert.ok(intelligence.whyMarkup(model(), audience));
});

test("source, derived, scenario and interpretation are separate and escaped", () => {
  for (const [classification, label] of [["source_statistic", "Source data"], ["derived_metric", "GVAI-derived"],
    ["scenario_output", "Scenario output"], ["model_interpretation", "AI interpretation"]]) {
    const markup = GVAIRegional.sourceDetails({ classification, method: "<script>alert(1)</script>" }, model());
    assert.ok(markup.includes(label));
    assert.doesNotMatch(markup, /<script>/);
  }
  const fixture = model();
  fixture.region.label = "<img onerror=alert(1)>";
  assert.doesNotMatch(intelligence.comparisonMarkup([fixture], "government"), /<img/);
});

test("scenario and jobs retain scoped contracts without leaking arbitrary private fields", () => {
  const { regional, session } = setup();
  regional.get().model.region.profile = { secret: "PRIVATE_SENTINEL" };
  session.setScenario({ workers: 10, weeklyHours: 40, taskShare: 20, timeSaving: 50 }, GVAIRegional.scenario({ workers: 10, weeklyHours: 40, taskShare: 20, timeSaving: 50 }));
  assert.equal(session.get().scenario.result.classification, "scenario_output");
  assert.doesNotMatch(JSON.stringify(session.context()), /PRIVATE_SENTINEL/);
  regional.updateJobs({ status: "available_zero_results", result_count: 0 }, "US:county:47149");
  assert.equal(session.get().jobs.result_count, 0);
  regional.begin({ label: "Other region" });
  assert.equal(session.get().scenario, null);
  assert.equal(session.get().jobs.status, "not_requested");
});

test("comparison markup explains missing signals and provides no universal scores", () => {
  const markup = intelligence.comparisonMarkup([model(), model("US:county:47065")], "business");
  assert.match(markup, /Regional evidence shortlist \(2\/5\)/);
  assert.match(markup, /Unavailable/);
  assert.match(markup, /missing occupation wages and competition/);
  assert.match(markup, /Source data/);
  assert.doesNotMatch(markup, /score|ranked #/);
});

test("AI comparison retrieval holds only shared resolved contracts and trims old shortlist references", () => {
  const { session, regional } = setup();
  assert.equal(intelligence.validateAction({ type: "compare_regions", queries: ["Rutherford County", "Hamilton County"] }, []), true);
  assert.equal(intelligence.validateAction({ type: "compare_regions", queries: ["County", "javascript:alert(1)"] }, []), false);
  session.setComparisons([model("US:county:47065"), model("US:county:47099")]);
  const first = session.get().comparisons[0];
  assert.equal(session.get().comparisons[0], first);
  session.setComparisons([model("US:county:47001"), model("US:county:47003")]);
  assert.equal(session.context().regions.length, 3);
  assert.equal(session.get().evidence, regional.get().model);
  assert.throws(() => session.setComparisons([model(), model()]), /distinct/);
});

test("UTF-8 history clipping remains within byte bounds without partial characters", () => {
  const { session } = setup();
  session.addMessage("assistant", "x".repeat(8191) + "€".repeat(100));
  session.addMessage("user", "Follow up");
  const message = session.context().messages[0].content;
  assert.ok(new TextEncoder().encode(message).length <= 8192);
  assert.doesNotMatch(message, /\uFFFD/);
});

test("action failures are visible and their diagnostic text is not transmitted in generic context", async () => {
  const { session } = setup();
  await intelligence.executeActions(session, [{ type: "open_jobs" }], {
    open_jobs: () => { throw new Error("Public workflow unavailable"); }
  });
  assert.equal(session.get().outcomes[0].status, "failed");
  assert.equal(session.get().outcomes[0].detail, "Public workflow unavailable");
  assert.doesNotMatch(JSON.stringify(session.context()), /Public workflow unavailable/);
});

test("action-owned updates preserve a sequence but delayed adapters cannot adopt user shortlist changes", async () => {
    const { session, regional } = setup();
    session.setComparisons([model("US:county:47065"), model("US:county:47099")]);
    const context = intelligence.createActionContext(session);
    let release;
    const pending = new Promise(resolve => { release = resolve; });
    let focused = false;
    const running = intelligence.executeActions(session, [
      { type: "open_occupation", occupation_code: "37-2021.00" }, { type: "focus_region", query: "Rutherford County" }
    ], {
      open_occupation: async action => {
        context.update(() => session.selectOccupation(action.occupation_code));
        await pending;
        return context.isCurrent() ? undefined : false;
      },
      focus_region: () => { focused = true; }
    }, context.isCurrent);
    assert.equal(context.isCurrent(), true);
    session.removeComparison("US:county:47065");
    release();
    const outcomes = await running;
    assert.equal(focused, false);
    assert.ok(outcomes.every(outcome => outcome.status === "stale"));
    // Even a later action-owned regional update cannot reauthorize the stale sequence.
    context.update(() => regional.set(model("US:county:47003")));
    assert.equal(context.isCurrent(), false);
});

test("action-owned audience and region changes retain authority only while the user context is unchanged", () => {
    const { session, regional } = setup();
    const context = intelligence.createActionContext(session);
    context.update(() => regional.selectAudience("business"));
    context.update(() => regional.begin({ latitude: 35.2, longitude: -85.2, label: "Hamilton" }));
    context.update(() => regional.set(model("US:county:47065")));
    assert.equal(context.isCurrent(), true);
    session.setScenario({ workers: 1, weeklyHours: 40, taskShare: 10, timeSaving: 10 },
      GVAIRegional.scenario({ workers: 1, weeklyHours: 40, taskShare: 10, timeSaving: 10 }));
    assert.equal(context.isCurrent(), false);
});

test("the actual Business selector handler sends the helper's public occupation_code", () => {
    const fs = require("node:fs");
    const vm = require("node:vm");
    const html = fs.readFileSync(require.resolve("../../web/index.html"), "utf8");
    const helper = html.slice(html.indexOf("function businessSelectedOccupation()"), html.indexOf("\nfunction ", html.indexOf("function businessSelectedOccupation()") + 1));
    const start = html.indexOf('document.getElementById("business-occupation-select").addEventListener("change",');
    const handler = html.slice(start, html.indexOf("\n});", start) + 4);
    let listener;
    let selected;
    vm.runInNewContext(`${helper}\n${handler}`, {
      document: { getElementById: () => ({ value: "37-2021.00|Pest Control Workers", addEventListener: (event, fn) => { listener = fn; } }) },
      intelligenceSession: { selectOccupation: code => { selected = code; } }
    });
    listener();
    assert.equal(selected, "37-2021.00");
});
