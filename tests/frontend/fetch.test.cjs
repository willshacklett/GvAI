const { test, afterEach } = require("node:test");
const assert = require("node:assert/strict");
const { fetchJSON } = require("../../web/fetch.js");
const originalFetch = globalThis.fetch;
afterEach(() => { globalThis.fetch = originalFetch; });

test("successful JSON preserves the existing response interface", async () => {
  globalThis.fetch = async () => new Response(JSON.stringify({ ok: true }));
  const response = await fetchJSON("/api/region");
  assert.equal(response.ok, true);
  assert.deepEqual(await response.json(), { ok: true });
});

test("network failures are sanitized", async () => {
  globalThis.fetch = async () => { throw new Error("private backend detail"); };
  await assert.rejects(fetchJSON("/api/region"), error => error.kind === "network" && !error.message.includes("private"));
});

test("HTTP failures keep status but not raw backend text", async () => {
  globalThis.fetch = async () => new Response("private traceback", { status: 503 });
  await assert.rejects(fetchJSON("/api/region"), error => error.kind === "http" && error.status === 503 && !error.message.includes("private"));
});

test("malformed JSON is a standardized failure", async () => {
  globalThis.fetch = async () => new Response("<html>error</html>");
  await assert.rejects(fetchJSON("/api/region"), error => error.kind === "json");
});

test("timeout aborts stalled requests", async () => {
  let requestSignal;
  globalThis.fetch = (url, options) => {
    requestSignal = options.signal;
    return new Promise(() => {});
  };
  await assert.rejects(fetchJSON("/api/region", { timeoutMs: 5 }), error => error.kind === "timeout");
  assert.equal(requestSignal.aborted, true);
});

test("timeout also bounds a stalled JSON body", async () => {
  globalThis.fetch = async () => ({ ok: true, json: () => new Promise(() => {}) });
  await assert.rejects(fetchJSON("/api/region", { timeoutMs: 5 }), error => error.kind === "timeout");
});

test("caller cancellation remains distinct from timeout", async () => {
  const controller = new AbortController();
  globalThis.fetch = async () => new Promise(() => {});
  const request = fetchJSON("/api/region", { signal: controller.signal });
  controller.abort();
  await assert.rejects(request, error => error.kind === "aborted");
});

test("an already aborted request never reaches fetch", async () => {
  const controller = new AbortController();
  controller.abort();
  globalThis.fetch = async () => { assert.fail("must not fetch"); };
  await assert.rejects(fetchJSON("/api/region", { signal: controller.signal }), error => error.kind === "aborted");
});