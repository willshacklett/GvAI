const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

function worker(cached) {
  const events = {};
  const context = {
    self: { location: { origin: "https://gvai.io" }, addEventListener: (name, handler) => { events[name] = handler; }, skipWaiting() {}, clients: { claim() {} } },
    URL, Response,
    fetch: async () => { throw new Error("offline fixture"); },
    caches: { match: async key => cached[key.url || key] }
  };
  vm.runInNewContext(fs.readFileSync("web/service-worker.js", "utf8"), context);
  return { events, context };
}

test("offline runtime JS remains JS and uncached scripts do not receive HTML", async () => {
  const script = new Response("window.GVAIRegional = {};", { headers: { "Content-Type": "text/javascript" } });
  const { events } = worker({ "https://gvai.io/regional-intelligence.js": script, "./index.html": new Response("<html>shell</html>") });
  let response;
  events.fetch({ request: { method: "GET", url: "https://gvai.io/regional-intelligence.js", mode: "no-cors" }, respondWith(value) { response = value; } });
  assert.equal((await response).headers.get("Content-Type"), "text/javascript");
  events.fetch({ request: { method: "GET", url: "https://gvai.io/missing.js", mode: "no-cors" }, respondWith(value) { response = value; } });
  assert.equal((await response).type, "error");
  events.fetch({ request: { method: "GET", url: "https://gvai.io/", mode: "navigate" }, respondWith(value) { response = value; } });
  assert.match(await (await response).text(), /shell/);
});

test("API and cross-origin data are never intercepted or replaced by shell", () => {
  const { events } = worker({});
  for (const url of ["https://gvai.io/api/region/intelligence", "https://backend.example/api/chat"]) {
    events.fetch({ request: { method: "GET", url }, respondWith() { assert.fail("must not intercept API data"); } });
  }
});

test("cache update publishes regional runtime and exact config reference", async () => {
  const { events, context } = worker({});
  let names;
  context.caches.open = async () => ({ addAll: async assets => { names = Array.from(assets); } });
  let pending;
  events.install({ waitUntil(value) { pending = value; } });
  await pending;
  assert.ok(names.includes("./regional-intelligence.js"));
  assert.ok(names.includes("./api_config.js?v=railway1"));
});