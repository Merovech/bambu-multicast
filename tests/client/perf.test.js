/**
 * Performance tests for client/app.js.
 *
 * Not part of a normal `npm test`.  Run them on demand with:  npm run test:perf
 *
 * These run in jsdom (a simulated browser in Node), so the absolute times are only a rough guide --
 * a real phone browser is a different machine.  The limits are deliberately loose: they exist to
 * catch something going badly wrong (work that grows with every poll, timers that pile up, a DOM
 * that keeps growing), not to grade a particular speed.  The printed numbers are the useful part.
 */

const fs = require("fs");
const path = require("path");

const INDEX_HTML = fs.readFileSync(path.resolve(__dirname, "../../client/index.html"), "utf8");

function loadApp() {
  jest.resetModules();
  return require("../../client/app.js");
}

function mountPage() {
  const parsed = new DOMParser().parseFromString(INDEX_HTML, "text/html");
  document.body.innerHTML = parsed.body.innerHTML;
}

function config(count) {
  const printers = {};
  for (let i = 1; i <= count; i++) {
    printers[`p${i}`] = { label: `Printer ${i}`, camera_url: `https://cam${i}.test/stream` };
  }
  return { settings: { poll_interval_ms: 5000 }, printers };
}

function mockFetch(responses) {
  global.fetch = jest.fn((url) => Promise.resolve({ json: () => Promise.resolve(responses[url]) }));
}

const RUNNING = {
  state: "RUNNING", pstate: "Printing", model: "Benchy", percent: 42, layer: 118, total_layers: 280,
  remaining_seconds: 5700, eta_utc: "2026-10-16T08:05:04Z", error: "The nozzle is clogged.",
};

function statusFor(count, info) {
  const status = {};
  for (let i = 1; i <= count; i++) {
    status[`p${i}`] = info;
  }
  return status;
}

function timeIt(fn) {
  const started = performance.now();
  fn();
  return performance.now() - started;
}

function say(line) {
  process.stderr.write(`  [perf] ${line}\n`);
}

beforeEach(() => {
  // Timers are faked so "hours" pass instantly, but the real clock is kept so timings mean something.
  jest.useFakeTimers({ doNotFake: ["performance"] });
  mountPage();
});

afterEach(() => {
  jest.clearAllTimers();
  jest.useRealTimers();
  delete global.fetch;
});

test("building the page for 2, 10 and 50 printers", async () => {
  for (const count of [2, 10, 50]) {
    mountPage();
    mockFetch({ "config.json": config(count) });
    const app = loadApp();
    const started = performance.now();
    await app.loadConfig();
    const ms = performance.now() - started;
    say(`loadConfig, ${count} printers: ${ms.toFixed(1)} ms`);
    expect(document.querySelectorAll("[data-printer]")).toHaveLength(count);
    expect(ms).toBeLessThan(2000);
    jest.clearAllTimers();
  }
});

test("updating one card, idle then printing then idle, 1000 times", async () => {
  mockFetch({ "config.json": config(2) });
  const app = loadApp();
  await app.loadConfig();

  const idle = { state: "IDLE", last_result: "failed" };
  const ms = timeIt(() => {
    for (let i = 0; i < 1000; i++) {
      app.updateCard("p1", i % 2 ? RUNNING : idle);
    }
  });
  say(`updateCard x1000: ${ms.toFixed(1)} ms (${(ms / 1000).toFixed(3)} ms each)`);
  expect(ms).toBeLessThan(2000);
});

test("a full status refresh for 2, 10 and 50 printers", async () => {
  for (const count of [2, 10, 50]) {
    mountPage();
    mockFetch({ "config.json": config(count), "status.json": statusFor(count, RUNNING) });
    const app = loadApp();
    await app.loadConfig();

    const started = performance.now();
    for (let i = 0; i < 100; i++) {
      await app.refreshStatus();
    }
    const ms = (performance.now() - started) / 100;
    say(`refreshStatus, ${count} printers: ${ms.toFixed(2)} ms per refresh`);
    expect(ms).toBeLessThan(200);
    jest.clearAllTimers();
  }
});

test("refreshing for hours does not grow the page", async () => {
  mockFetch({ "config.json": config(2), "status.json": statusFor(2, RUNNING) });
  const app = loadApp();
  await app.loadConfig();
  await app.refreshStatus();

  const nodesBefore = document.getElementsByTagName("*").length;
  const htmlBefore = document.body.innerHTML.length;
  for (let i = 0; i < 2000; i++) {
    await app.refreshStatus();
  }
  say(`2000 refreshes (about 2.8 hours at 5 s): ${nodesBefore} -> ${document.getElementsByTagName("*").length} elements`);
  expect(document.getElementsByTagName("*").length).toBe(nodesBefore);
  expect(document.body.innerHTML.length).toBe(htmlBefore);
});

test("timers do not pile up over hours of camera reconnects and polling", async () => {
  mockFetch({ "config.json": config(2), "status.json": statusFor(2, RUNNING) });
  const app = loadApp();
  await app.main();
  await jest.advanceTimersByTimeAsync(0);

  const before = jest.getTimerCount();
  await jest.advanceTimersByTimeAsync(2 * 60 * 60 * 1000);
  say(`pending timers: ${before} at start, ${jest.getTimerCount()} after 2 hours`);
  expect(jest.getTimerCount()).toBeLessThanOrEqual(before);
});

test("a camera that keeps failing does not stack up retries", async () => {
  mockFetch({ "config.json": config(1) });
  const app = loadApp();
  await app.loadConfig();
  const img = document.querySelector("img");

  for (let i = 0; i < 500; i++) {
    img.dispatchEvent(new Event("error"));
    await jest.advanceTimersByTimeAsync(app.CAMERA_ERROR_RETRY_MS);
  }
  say(`500 failed reconnects: ${jest.getTimerCount()} pending timers`);
  expect(jest.getTimerCount()).toBeLessThanOrEqual(2);
  expect(img.getAttribute("src").match(/_retry=/g)).toHaveLength(1);
});
