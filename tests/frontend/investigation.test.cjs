const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const regional = require("../../web/regional-intelligence.js");
global.GVAIRegional = regional;
const intelligence = require("../../web/intelligence-session.js");
const decision = require("../../web/investigation.js");
const A = "US:county:47149", B = "US:county:47065";
const criterion = (key, value = "User preference", priority = "primary", direction = "higher") => ({ key, value, priority, direction });
function model(id = A) {
  return regional.unavailableModel({ id, label: id, latitude: 35.85, longitude: -86.4, country_code: "US", type: "county" }, "Synthetic gap");
}
function setup() {
  const store = regional.createStore(), session = intelligence.createStore(store);
  store.set(model());
  return { store, session };
}

test("all investigation types retain explicit question and public criteria across audiences", () => {
  for (const type of decision.TYPES) {
    const { store, session } = setup();
    session.startInvestigation(type, "Should I move or expand?");
    session.setCriteria([criterion("geography", "Tennessee", "constraint", "inspect"),
      criterion("occupations", [{ code: "37-2021.00", workers: 30 }], "constraint", "inspect")]);
    for (const audience of ["laborers", "business", "government"]) {
      store.selectAudience(audience);
      assert.equal(session.context().investigation.type, type);
      assert.equal(session.context().investigation.criteria[1].value[0].workers, 30);
      assert.equal(session.context().investigation.candidates[0].region_id, A);
    }
    assert.throws(() => session.startInvestigation(type, "Replace it"), /already active/);
  }
});

test("candidate management keeps evidence references, reasons, shortlist and removals coherent", () => {
  const { store, session } = setup();
  const first = store.get().model, second = model(B);
  session.startInvestigation("business_expansion", "Open a branch?");
  session.setCandidate(first, "shortlisted");
  session.setCandidate(second, "shortlisted");
  assert.equal(session.get().comparisons[0], first);
  assert.equal(session.get().comparisons[1], second);
  session.candidateDecision(B, "rejected", "Housing tradeoff not acceptable");
  assert.deepEqual(session.get().comparisonIds, [A]);
  assert.equal(session.context().investigation.candidates.find(item => item.region_id === B).reason, "Housing tradeoff not acceptable");
  assert.equal(session.context().regions.length, 2);
  session.candidateDecision(B, "removed");
  assert.equal(session.context().regions.length, 1);
  assert.throws(() => session.candidateDecision(B, "removed"), /not a candidate/);
  assert.throws(() => session.candidateDecision(A, "rejected", ""), /explicit reason/);
});

test("eight candidate and five shortlist bounds fail without partial state mutations", () => {
  const { session } = setup();
  session.startInvestigation("regional_comparison", "Compare?");
  for (let index = 1; index <= 7; index++) session.setCandidate(model(`US:county:4700${index}`));
  const before = JSON.stringify(session.context());
  assert.throws(() => session.setCandidate(model(B)), /eight/);
  assert.equal(JSON.stringify(session.context()), before);
  for (const item of session.get().investigation.candidates.slice(0, 5)) session.candidateDecision(item.region_id, "shortlisted");
  assert.throws(() => session.candidateDecision("US:county:47005", "shortlisted"), /five/);
  assert.equal(session.get().comparisonIds.length, 5);
});

test("selected candidate refresh preserves a prior shortlist or rejection decision", () => {
  const { session } = setup();
  session.startInvestigation("relocation", "Move?");
  session.candidateDecision(A, "shortlisted");
  session.setCandidate(model(B), "shortlisted");
  session.setCandidate(model());
  assert.deepEqual(session.get().comparisonIds, [A, B]);
  assert.deepEqual(session.get().investigation.candidates.map(item => item.region_id), [A, B]);
  assert.equal(session.get().investigation.candidates[0].status, "shortlisted");
  session.candidateDecision(A, "rejected", "Housing does not work");
  session.setCandidate(model());
  assert.equal(session.get().investigation.candidates[0].status, "rejected");
});

test("criteria merge and removal preserve unrelated criteria and invalidate the old conclusion", () => {
  const { session } = setup();
  session.startInvestigation("hiring_workforce", "Staff a branch?");
  session.setCriteria([criterion("labor_force"), criterion("housing_pressure", "Lower", "secondary", "lower")]);
  session.setDecisionRead({ current_read: "Old working conclusion" });
  const epoch = session.get().epoch;
  session.setCriteria([criterion("housing_pressure", "Lower", "primary", "lower")]);
  assert.ok(session.get().epoch > epoch);
  assert.equal(session.get().decisionRead, null);
  assert.equal(session.get().investigation.criteria[0].key, "labor_force");
  assert.equal(session.get().investigation.criteria[1].priority, "primary");
  session.removeCriterion("labor_force");
  assert.equal(session.get().investigation.criteria.length, 1);
});

test("malformed criteria, unknown fields and executable actions cannot enter the store", () => {
  const { session } = setup();
  session.startInvestigation("business_expansion", "Expand?");
  const malformed = [
    criterion("profile", "PRIVATE_SENTINEL"), criterion("labor_force", "", "primary"),
    criterion("distance_radius", { miles: false, center: "Nashville" }),
    criterion("occupations", [{ code: "37-2021.00", workers: true }]),
    criterion("occupations", [{ code: "37-2021.00", workers: 30, private_wage: 62000 }]),
    { ...criterion("labor_force"), code: "alert(1)" }
  ];
  for (const item of malformed) {
    assert.equal(intelligence.validateAction({ type: "set_criteria", criteria: [item] }, [A]), false);
    assert.throws(() => session.setCriteria([item]), /Invalid/);
  }
  assert.equal(intelligence.validateAction({ type: "add_candidate", query: "https://example.org" }, []), false);
  assert.equal(intelligence.validateAction({ type: "reject_candidate", region_id: A, reason: "" }, [A]), false);
  assert.doesNotMatch(JSON.stringify(session.context()), /PRIVATE_SENTINEL/);
});

test("disambiguation has no implicit first choice, retains criteria, then resumes explicit choice", async () => {
  const { session } = setup();
  session.startInvestigation("relocation", "Move to Springfield?");
  session.setCriteria([criterion("housing_pressure", "Lower", "primary", "lower")]);
  let resolved = false;
  const pending = session.choosePlace("Springfield", [{ label: "Springfield TN" }, { label: "Springfield MO" }]).then(place => { resolved = true; return place; });
  await Promise.resolve();
  assert.equal(resolved, false);
  assert.equal(session.get().placeChoice.candidates.length, 2);
  assert.equal(session.get().investigation.criteria[0].key, "housing_pressure");
  session.resolvePlaceChoice(1);
  assert.equal((await pending).label, "Springfield MO");
  assert.equal(session.get().placeChoice, null);
});

test("new criteria or navigation cancels pending place choice without granting stale actions authority", async () => {
  for (const mutate of [session => session.invalidateNavigation(), session => session.setCriteria([criterion("labor_force")])]) {
    const { session } = setup();
    session.startInvestigation("business_expansion", "Expand?");
    const context = intelligence.createActionContext(session);
    const pending = session.choosePlace("Springfield", [{ label: "TN" }, { label: "MO" }]);
    mutate(session);
    assert.equal(await pending, null);
    let executed = false;
    const outcomes = await intelligence.executeActions(session, [{ type: "open_jobs" }],
      { open_jobs: () => { executed = true; } }, context.isCurrent);
    assert.equal(executed, false);
    assert.equal(context.isCurrent(), false);
    assert.equal(outcomes[0].status, "stale");
  }
});

test("investigation panel shows question, rejected rationale, gaps, classified evidence and what changes", () => {
  const { session } = setup();
  session.startInvestigation("business_expansion", "<script>Expand?</script>");
  session.setCriteria([criterion("distance_radius", { miles: 100, center: "Nashville" }, "constraint", "inspect")]);
  session.candidateDecision(A, "rejected", "<img onerror=alert(1)>");
  session.setDecisionRead({ classification: "model_interpretation", current_read: "No defensible winner",
    missing_criteria: ["occupations"], clarification: "Which occupation?", evidence_gaps: [{ criterion: "distance_radius", reason: "Not verified" }],
    could_change_if: ["Your primary priority changes"], region_reads: {}, signals: [
      { criterion: "labor_force", values: [{ region_id: A, value: null, classification: "source_statistic",
        sources: { acs: { name: "Census", vintage: 2024 } }, geography: { acs: { label: "County evidence" } } }], priority: "primary", direction: "higher", comparable: false, note: "Not ranked" }] });
  const markup = decision.render(session.get());
  for (const expected of ["Question", "Criteria", "Candidates", "Evidence gaps", "Current read", "Could change if", "rejection reason",
    "unverified boundary", "Unavailable, not zero", "2024", "source_statistic", "County evidence", "Which occupation?", "priority changes"]) assert.ok(markup.includes(expected), expected);
  assert.doesNotMatch(markup, /<script>|<img|GVAI Score/);
});

function mounted(fetcher, selected = true) {
  const store = regional.createStore(), session = intelligence.createStore(store);
  if (selected) store.set(model());
  const elements = new Map();
  const document = { getElementById(id) {
    if (!elements.has(id)) elements.set(id, {
      value: "", textContent: "", innerHTML: "", listeners: {}, focus() {},
      classList: { toggle() {} },
      addEventListener(type, callback) { this.listeners[type] = callback; },
      querySelector() { return document.getElementById("submit"); }
    });
    return elements.get(id);
  } };
  const root = { GVAIIntelligence: intelligence, GVAIRegional: regional, GVAIInvestigation: decision };
  vm.runInNewContext(fs.readFileSync(require.resolve("../../web/intelligence-guide.js"), "utf8"), {
    window: root, document, fetch: fetcher, TextEncoder
  });
  const guide = root.GVAIIntelligenceGuide.mount(session, store, {
    start_investigation: (action, current, update) => update(() => session.startInvestigation(action.investigation_type, action.question)),
    set_criteria: (action, current, update) => update(() => session.setCriteria(action.criteria)),
    add_candidate: (action, current, update) => update(() => session.setCandidate(model(B)))
  });
  return { session, store, guide, elements, requestBody: root.GVAIIntelligenceGuide.requestBody };
}
const reply = data => ({ ok: true, async json() { return { ok: true, reply: "Evidence-backed explanation", ...data }; } });

test("homepage discloses region, investigation and comparison controls only in context", () => {
  const app = mounted(async () => reply({}), false);
  for (const id of ["regional-outlook-panel", "intelligence-context", "intelligence-clear", "intelligence-why",
    "intelligence-investigation", "intelligence-comparison", "intelligence-audience-control", "intelligence-disclaimer"]) {
    assert.equal(app.elements.get(id).hidden, true, id);
  }
  app.store.begin({ label: "A requested region", latitude: 35.85, longitude: -86.4 });
  assert.equal(app.elements.get("regional-outlook-panel").hidden, false);
  app.store.fail();
  assert.equal(app.elements.get("regional-outlook-panel").hidden, false);
  app.store.set(model());
  assert.equal(app.elements.get("regional-outlook-panel").hidden, false);
  assert.equal(app.elements.get("intelligence-why").hidden, false);
  assert.equal(app.elements.get("intelligence-investigation").hidden, true);
  app.session.startInvestigation("business_expansion", "Where should I hire?");
  assert.equal(app.elements.get("intelligence-investigation").hidden, false);
  assert.equal(app.elements.get("intelligence-audience-control").hidden, false);
});

test("starters retain intent and audience without opening a full workspace", async () => {
  const calls = [];
  const app = mounted(async (url, options) => {
    calls.push(JSON.parse(options.body));
    return reply({});
  }, false);
  await app.guide.ask("Help me find better work", "laborers");
  await app.guide.ask("Help me find where to hire", "business");
  await app.guide.ask("Help me compare places", "business");
  await app.guide.ask("Help me understand my region", "government");
  assert.deepEqual(calls.map(call => call.intelligence_session.audience), ["laborers", "business", "business", "government"]);
  assert.ok(calls.every(call => call.intelligence_session.selected_region_id === null));
  assert.equal(calls[3].message, "Help me understand my region");
});

test("voice-ready send performs exactly one fresh-evidence continuation and ignores its action requests", async () => {
  const calls = [];
  const app = mounted(async (url, options) => {
    calls.push(JSON.parse(options.body));
    return reply({ action_protocol: "gvai.ui-actions.v1", actions: calls.length === 1 ?
      [{ type: "start_investigation", investigation_type: "business_expansion", question: "Open a branch?" },
        { type: "set_criteria", criteria: [criterion("labor_force")] }, { type: "add_candidate", query: "Hamilton" }] :
      [{ type: "start_investigation", investigation_type: "relocation", question: "Injected reset?" }],
      decision_read: { current_read: "Current evidence with tradeoffs" } });
  });
  await app.guide.send("Open a branch");
  assert.equal(calls.length, 2);
  assert.equal(calls[1].continuation, true);
  assert.equal(calls[1].intelligence_session.investigation.criteria[0].key, "labor_force");
  assert.equal(calls[1].intelligence_session.regions.length, 2);
  assert.equal(calls[1].intelligence_session.messages.at(-1).role, "assistant");
  assert.equal(app.session.get().investigation.type, "business_expansion");
  assert.equal(app.session.get().decisionRead.current_read, "Current evidence with tradeoffs");
  assert.equal(app.session.get().messages.length, 3);
});

test("stale automatic continuation cannot overwrite new user priorities", async () => {
  let release, ready;
  const waiting = new Promise(resolve => { ready = resolve; });
  let calls = 0;
  const app = mounted(async () => {
    calls++;
    if (calls === 2) { ready(); return new Promise(resolve => { release = resolve; }); }
    return reply({ action_protocol: "gvai.ui-actions.v1",
      actions: [{ type: "start_investigation", investigation_type: "business_expansion", question: "Expand?" }] });
  });
  const pending = app.guide.send("Expand?");
  await waiting;
  app.session.setCriteria([criterion("housing_pressure", "Lower housing", "primary", "lower")]);
  release(reply({ reply: "STALE_LEADER", decision_read: { current_read: "STALE_LEADER" } }));
  await pending;
  assert.equal(app.session.get().decisionRead, null);
  assert.ok(app.session.get().messages.every(message => !message.content.includes("STALE_LEADER")));
  assert.match(app.elements.get("regional-ask-status").textContent, /old continuation was ignored/);
});

test("full UTF-8 request bound includes user message, regional evidence and investigation criteria", () => {
  const app = mounted(async () => reply({ actions: [] }));
  const context = { messages: Array.from({ length: 24 }, () => ({ role: "user", content: "€".repeat(2500) })) };
  const body = app.requestBody("€".repeat(2700), context, { notes: "x".repeat(32000) });
  assert.ok(new TextEncoder().encode(body).length <= 64000);
  assert.ok(JSON.parse(body).intelligence_session.messages.length < 24);
  assert.throws(() => app.requestBody("hello", { messages: [] }, { notes: "x".repeat(65000) }), /too large/);
});
