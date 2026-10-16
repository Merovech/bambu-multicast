/**
 * Tests for client/app.js.
 *
 * Run from the project root with:  npm test
 * (needs `npm install` once -- Jest is a dev-only dependency; nobody running the site needs it.)
 */

const fs = require("fs");
const path = require("path");

const CLIENT_DIR = path.resolve(__dirname, "../../client");
const INDEX_HTML = fs.readFileSync(path.join(CLIENT_DIR, "index.html"), "utf8");

// A fresh copy of app.js per test, so its module-level state (poll interval, printer ids) starts
// from scratch each time.
function loadApp() {
  jest.resetModules();
  return require("../../client/app.js");
}

// The page as the browser would have it before app.js runs: index.html's real <body>.
function mountPage() {
  const parsed = new DOMParser().parseFromString(INDEX_HTML, "text/html");
  document.body.innerHTML = parsed.body.innerHTML;
}

// Point fetch at a fake server: { "config.json": {...}, "status.json": {...} }.  A value that is
// an Error makes that request fail.
function mockFetch(responses) {
  global.fetch = jest.fn((url) => {
    const body = responses[url];
    if (body === undefined) {
      return Promise.reject(new Error(`unexpected fetch: ${url}`));
    }
    if (body instanceof Error) {
      return Promise.reject(body);
    }
    return Promise.resolve({ json: () => Promise.resolve(body) });
  });
  return global.fetch;
}

const TWO_PRINTERS = {
  settings: { poll_interval_ms: 2000 },
  printers: {
    p1: { label: "Printer One", camera_url: "https://cam-one.test/stream" },
    p2: { label: "Printer Two", camera_url: "https://cam-two.test/stream?src=p2" },
  },
};

const card = (id) => document.querySelector(`[data-printer="${id}"]`);
const role = (id, name) => card(id).querySelector(`[data-role="${name}"]`);
const field = (id, name) => card(id).querySelector(`[data-field="${name}"]`).textContent;
const isHidden = (el) => el.classList.contains("hidden");

const RUNNING = {
  state: "RUNNING",
  pstate: "Printing",
  model: "Benchy",
  percent: 42,
  layer: 118,
  total_layers: 280,
  remaining_seconds: 5700,
  eta_utc: "2026-10-16T08:05:04Z",
};

beforeEach(() => {
  jest.useFakeTimers();
  jest.setSystemTime(new Date(2026, 9, 16, 12, 0, 0));
  mountPage();
});

afterEach(() => {
  jest.clearAllTimers();
  jest.useRealTimers();
  jest.restoreAllMocks();
  delete global.fetch;
});

describe("formatDuration", () => {
  const { formatDuration } = loadApp();

  test.each([
    [0, "00:00:00"],
    [59, "00:00:59"],
    [60, "00:01:00"],
    [3661, "01:01:01"],
    [5700, "01:35:00"],
    [100000, "27:46:40"],
  ])("%d seconds is %s", (seconds, expected) => {
    expect(formatDuration(seconds)).toBe(expected);
  });

  test.each([[undefined], [null], [NaN], [-30]])("%p becomes zero", (value) => {
    expect(formatDuration(value)).toBe("00:00:00");
  });

  test("rounds fractional seconds", () => {
    expect(formatDuration(59.6)).toBe("00:01:00");
    expect(formatDuration(59.4)).toBe("00:00:59");
  });
});

describe("setHidden", () => {
  test("adds and removes Tailwind's hidden class", () => {
    const { setHidden } = loadApp();
    const el = document.createElement("div");
    setHidden(el, true);
    expect(isHidden(el)).toBe(true);
    setHidden(el, false);
    expect(isHidden(el)).toBe(false);
  });

  test("is safe to repeat", () => {
    const { setHidden } = loadApp();
    const el = document.createElement("div");
    setHidden(el, true);
    setHidden(el, true);
    expect(isHidden(el)).toBe(true);
  });

  test("does not touch the native hidden attribute", () => {
    // The page hides things with a class; the attribute would do nothing there.
    const { setHidden } = loadApp();
    const el = document.createElement("div");
    setHidden(el, true);
    expect(el.hasAttribute("hidden")).toBe(false);
  });
});

describe("setField", () => {
  test("fills in the named field", () => {
    const { setField } = loadApp();
    const root = document.createElement("div");
    root.innerHTML = '<span data-field="model">old</span>';
    setField(root, "model", "Benchy");
    expect(root.querySelector("span").textContent).toBe("Benchy");
  });

  test("ignores a field that isn't there", () => {
    const { setField } = loadApp();
    expect(() => setField(document.createElement("div"), "nope", "x")).not.toThrow();
  });

  test("only touches the card it was given", () => {
    const { setField } = loadApp();
    document.getElementById("printers").innerHTML =
      '<div id="a"><b data-field="n">a</b></div><div id="b"><b data-field="n">b</b></div>';
    setField(document.getElementById("a"), "n", "changed");
    expect(document.querySelector("#a b").textContent).toBe("changed");
    expect(document.querySelector("#b b").textContent).toBe("b");
  });

  test("shows markup as text instead of interpreting it", () => {
    const { setField } = loadApp();
    const root = document.createElement("div");
    root.innerHTML = '<span data-field="error"></span>';
    setField(root, "error", "<img src=x onerror=alert(1)>");
    expect(root.querySelector("img")).toBeNull();
    expect(root.textContent).toBe("<img src=x onerror=alert(1)>");
  });
});

describe("cacheBustedCameraUrl", () => {
  test("adds a query string when there is none", () => {
    const { cacheBustedCameraUrl } = loadApp();
    expect(cacheBustedCameraUrl("https://cam.test/stream")).toBe(
      `https://cam.test/stream?_retry=${Date.now()}`
    );
  });

  test("appends to an existing query string", () => {
    const { cacheBustedCameraUrl } = loadApp();
    expect(cacheBustedCameraUrl("https://cam.test/api/stream.mjpeg?src=p2s")).toBe(
      `https://cam.test/api/stream.mjpeg?src=p2s&_retry=${Date.now()}`
    );
  });

  test("is different each time the clock moves", () => {
    const { cacheBustedCameraUrl } = loadApp();
    const first = cacheBustedCameraUrl("https://cam.test/stream");
    jest.advanceTimersByTime(1);
    expect(cacheBustedCameraUrl("https://cam.test/stream")).not.toBe(first);
  });
});

describe("renderCard", () => {
  function render(options = {}) {
    const { renderCard } = loadApp();
    const holder = document.createElement("div");
    holder.innerHTML = renderCard({
      id: "p1",
      label: "Printer One",
      cameraUrl: "https://cam.test/stream",
      ...options,
    });
    return holder;
  }

  test("is tagged with the printer's id", () => {
    expect(render().querySelector('[data-printer="p1"]')).not.toBeNull();
  });

  test("shows the label as a heading and in the camera's alt text", () => {
    const html = render();
    expect(html.querySelector("h2").textContent).toBe("Printer One");
    expect(html.querySelector("img").alt).toBe("Printer One camera");
  });

  test("points the camera at the configured URL and remembers it for reconnects", () => {
    const img = render().querySelector('[data-role="camera-img"]');
    expect(img.getAttribute("src")).toBe("https://cam.test/stream");
    expect(img.dataset.baseSrc).toBe("https://cam.test/stream");
  });

  test("starts on the Idle view, with the details hidden", () => {
    const html = render();
    expect(isHidden(html.querySelector('[data-role="idle"]'))).toBe(false);
    expect(isHidden(html.querySelector('[data-role="detail"]'))).toBe(true);
    expect(html.querySelector('[data-role="idle"]').textContent).toBe("Idle");
  });

  test("starts with the error row hidden and a loading spinner showing", () => {
    const html = render();
    expect(isHidden(html.querySelector('[data-role="error-row"]'))).toBe(true);
    expect(isHidden(html.querySelector('[data-role="camera-spinner"]'))).toBe(false);
  });

  test("reserves a 16:9 box for the camera so the layout doesn't jump when the image loads", () => {
    const wrapper = render().querySelector('[data-role="camera-img"]').parentElement;
    expect(wrapper.classList.contains("aspect-video")).toBe(true);
  });

  test.each(["model", "percent", "layer", "total_layers", "remaining", "pstate", "eta", "error"])(
    "has the %s field that updateCard fills in",
    (name) => {
      expect(render().querySelector(`[data-field="${name}"]`)).not.toBeNull();
    }
  );

  test("has the progress bar", () => {
    expect(render().querySelector('[data-role="bar"]')).not.toBeNull();
  });
});

describe("updateCard", () => {
  function mount(id = "p1") {
    const app = loadApp();
    document
      .getElementById("printers")
      .insertAdjacentHTML(
        "beforeend",
        app.renderCard({ id, label: id, cameraUrl: "https://cam.test/stream" })
      );
    return app;
  }

  describe("when idle", () => {
    test("shows the Idle box and hides the details", () => {
      const { updateCard } = mount();
      updateCard("p1", { state: "IDLE" });
      expect(isHidden(role("p1", "idle"))).toBe(false);
      expect(isHidden(role("p1", "detail"))).toBe(true);
      expect(role("p1", "idle").textContent).toBe("Idle");
    });

    test.each([
      ["succeeded", "Idle (Print Succeeded)"],
      ["failed", "Idle (Print Failed)"],
    ])("shows the result of the last print when it was %s", (result, text) => {
      const { updateCard } = mount();
      updateCard("p1", { state: "IDLE", last_result: result });
      expect(role("p1", "idle").textContent).toBe(text);
    });

    test("ignores a result it doesn't recognise", () => {
      const { updateCard } = mount();
      updateCard("p1", { state: "IDLE", last_result: "exploded" });
      expect(role("p1", "idle").textContent).toBe("Idle");
    });

    test("goes back to plain Idle once the server stops sending a result", () => {
      const { updateCard } = mount();
      updateCard("p1", { state: "IDLE", last_result: "failed" });
      updateCard("p1", { state: "IDLE" });
      expect(role("p1", "idle").textContent).toBe("Idle");
    });

    test.each([["UNKNOWN", { state: "UNKNOWN" }], ["no data at all", undefined], ["null", null]])(
      "%s is treated as idle",
      (_name, info) => {
        const { updateCard } = mount();
        updateCard("p1", info);
        expect(isHidden(role("p1", "idle"))).toBe(false);
        expect(isHidden(role("p1", "detail"))).toBe(true);
        expect(role("p1", "idle").textContent).toBe("Idle");
      }
    );
  });

  describe("when printing", () => {
    test("shows the details and hides the Idle box", () => {
      const { updateCard } = mount();
      updateCard("p1", RUNNING);
      expect(isHidden(role("p1", "detail"))).toBe(false);
      expect(isHidden(role("p1", "idle"))).toBe(true);
    });

    test("fills in every number and label", () => {
      const { updateCard } = mount();
      updateCard("p1", RUNNING);
      expect(field("p1", "model")).toBe("Benchy");
      expect(field("p1", "percent")).toBe("42%");
      expect(field("p1", "layer")).toBe("118");
      expect(field("p1", "total_layers")).toBe("280");
      expect(field("p1", "remaining")).toBe("01:35:00");
      expect(field("p1", "pstate")).toBe("Printing");
    });

    test("sizes the progress bar to the percentage", () => {
      const { updateCard } = mount();
      updateCard("p1", RUNNING);
      expect(role("p1", "bar").style.width).toBe("42%");
      updateCard("p1", { ...RUNNING, percent: 100 });
      expect(role("p1", "bar").style.width).toBe("100%");
    });

    test("shows the estimated completion in the viewer's own time zone, with the date", () => {
      const { updateCard } = mount();
      updateCard("p1", RUNNING);
      const expected = new Date("2026-10-16T08:05:04Z").toLocaleString([], {
        dateStyle: "short",
        timeStyle: "short",
      });
      expect(field("p1", "eta")).toBe(expected);
      expect(field("p1", "eta")).toMatch(/2026|26/);
    });

    test("falls back to sensible text when the printer leaves things out", () => {
      const { updateCard } = mount();
      updateCard("p1", { state: "RUNNING", pstate: "Printing" });
      expect(field("p1", "model")).toBe("Unknown");
      expect(field("p1", "percent")).toBe("0%");
      expect(field("p1", "layer")).toBe("0");
      expect(field("p1", "total_layers")).toBe("0");
      expect(field("p1", "remaining")).toBe("00:00:00");
      expect(field("p1", "eta")).toBe("—");
      expect(role("p1", "bar").style.width).toBe("0%");
    });

    test("shows zero as a real value, not as missing", () => {
      const { updateCard } = mount();
      updateCard("p1", { ...RUNNING, percent: 0, layer: 0 });
      expect(field("p1", "percent")).toBe("0%");
      expect(field("p1", "layer")).toBe("0");
    });
  });

  describe("errors", () => {
    test("shows the error text in the error row", () => {
      const { updateCard } = mount();
      updateCard("p1", { ...RUNNING, pstate: "Paused", error: "The nozzle is clogged." });
      expect(isHidden(role("p1", "error-row"))).toBe(false);
      expect(field("p1", "error")).toBe("The nozzle is clogged.");
      expect(field("p1", "pstate")).toBe("Paused");
    });

    test("keeps the error row hidden when there is no error", () => {
      const { updateCard } = mount();
      updateCard("p1", RUNNING);
      expect(isHidden(role("p1", "error-row"))).toBe(true);
    });

    test("hides the error row again once the error clears", () => {
      const { updateCard } = mount();
      updateCard("p1", { ...RUNNING, error: "The nozzle is clogged." });
      updateCard("p1", RUNNING);
      expect(isHidden(role("p1", "error-row"))).toBe(true);
    });

    test("treats an error message as text, not as markup", () => {
      const { updateCard } = mount();
      updateCard("p1", { ...RUNNING, error: "<b>boom</b>" });
      expect(role("p1", "error-row").querySelector("b[data-field], b")).toBeNull();
      expect(field("p1", "error")).toBe("<b>boom</b>");
    });
  });

  describe("transitions", () => {
    test("idle -> printing -> idle", () => {
      const { updateCard } = mount();
      updateCard("p1", { state: "IDLE" });
      updateCard("p1", RUNNING);
      expect(isHidden(role("p1", "detail"))).toBe(false);
      updateCard("p1", { state: "IDLE", last_result: "succeeded" });
      expect(isHidden(role("p1", "detail"))).toBe(true);
      expect(role("p1", "idle").textContent).toBe("Idle (Print Succeeded)");
    });
  });

  test("does nothing for a printer that has no card", () => {
    const { updateCard } = mount();
    expect(() => updateCard("ghost", RUNNING)).not.toThrow();
  });

  test("only changes the card it was asked to", () => {
    const app = mount("p1");
    document
      .getElementById("printers")
      .insertAdjacentHTML("beforeend", app.renderCard({ id: "p2", label: "p2", cameraUrl: "x" }));
    app.updateCard("p1", RUNNING);
    expect(isHidden(role("p2", "detail"))).toBe(true);
    expect(field("p2", "model")).toBe("—");
  });
});

describe("startCameraStream", () => {
  function setup(baseSrc = "https://cam.test/stream") {
    const app = loadApp();
    const img = document.createElement("img");
    img.dataset.baseSrc = baseSrc;
    img.setAttribute("src", baseSrc);
    const spinner = document.createElement("div");
    app.startCameraStream(img, spinner);
    return { app, img, spinner };
  }

  test("hides the spinner once the first frame loads", () => {
    const { img, spinner } = setup();
    img.dispatchEvent(new Event("load"));
    expect(isHidden(spinner)).toBe(true);
  });

  test("hides the spinner if the stream fails, so it doesn't spin forever", () => {
    const { img, spinner } = setup();
    img.dispatchEvent(new Event("error"));
    expect(isHidden(spinner)).toBe(true);
  });

  test("retries a failed stream after the short retry delay, not before", () => {
    const { app, img } = setup();
    img.dispatchEvent(new Event("error"));
    jest.advanceTimersByTime(app.CAMERA_ERROR_RETRY_MS - 1);
    expect(img.getAttribute("src")).toBe("https://cam.test/stream");
    jest.advanceTimersByTime(1);
    expect(img.getAttribute("src")).toBe(`https://cam.test/stream?_retry=${Date.now()}`);
  });

  test("keeps retrying if the retry fails too", () => {
    const { app, img } = setup();
    img.dispatchEvent(new Event("error"));
    jest.advanceTimersByTime(app.CAMERA_ERROR_RETRY_MS);
    const firstRetry = img.getAttribute("src");
    img.dispatchEvent(new Event("error"));
    jest.advanceTimersByTime(app.CAMERA_ERROR_RETRY_MS);
    expect(img.getAttribute("src")).not.toBe(firstRetry);
    expect(img.getAttribute("src")).toContain("_retry=");
  });

  test("retries from the original URL, so query strings don't pile up", () => {
    const { app, img } = setup();
    for (let i = 0; i < 3; i++) {
      img.dispatchEvent(new Event("error"));
      jest.advanceTimersByTime(app.CAMERA_ERROR_RETRY_MS);
    }
    expect(img.getAttribute("src").match(/_retry=/g)).toHaveLength(1);
  });

  test("keeps an existing query string when retrying", () => {
    const { app, img } = setup("https://cam.test/api/stream.mjpeg?src=p2s");
    img.dispatchEvent(new Event("error"));
    jest.advanceTimersByTime(app.CAMERA_ERROR_RETRY_MS);
    expect(img.getAttribute("src")).toBe(
      `https://cam.test/api/stream.mjpeg?src=p2s&_retry=${Date.now()}`
    );
  });

  describe("watchdog", () => {
    // A stream that dies silently never fires "error", so this timer is what actually recovers it.
    test("reconnects on a fixed timer even though no event ever fired", () => {
      const { app, img } = setup();
      jest.advanceTimersByTime(app.CAMERA_WATCHDOG_MS - 1);
      expect(img.getAttribute("src")).toBe("https://cam.test/stream");
      jest.advanceTimersByTime(1);
      expect(img.getAttribute("src")).toBe(`https://cam.test/stream?_retry=${Date.now()}`);
    });

    test("keeps going, indefinitely", () => {
      const { app, img } = setup();
      const seen = new Set();
      for (let i = 0; i < 5; i++) {
        jest.advanceTimersByTime(app.CAMERA_WATCHDOG_MS);
        seen.add(img.getAttribute("src"));
      }
      expect(seen.size).toBe(5);
    });

    test("runs per camera, independently", () => {
      const app = loadApp();
      const make = (url) => {
        const img = document.createElement("img");
        img.dataset.baseSrc = url;
        img.setAttribute("src", url);
        app.startCameraStream(img, document.createElement("div"));
        return img;
      };
      const a = make("https://a.test/stream");
      const b = make("https://b.test/stream");
      jest.advanceTimersByTime(app.CAMERA_WATCHDOG_MS);
      expect(a.getAttribute("src")).toMatch(/^https:\/\/a\.test\/stream\?_retry=/);
      expect(b.getAttribute("src")).toMatch(/^https:\/\/b\.test\/stream\?_retry=/);
    });

    test("is much slower than the quick retry", () => {
      const { CAMERA_ERROR_RETRY_MS, CAMERA_WATCHDOG_MS } = loadApp();
      expect(CAMERA_WATCHDOG_MS).toBeGreaterThan(CAMERA_ERROR_RETRY_MS);
    });
  });
});

describe("loadConfig", () => {
  test("asks for config.json by a relative URL, so it works under /printers/ too", async () => {
    const fetch = mockFetch({ "config.json": TWO_PRINTERS });
    await loadApp().loadConfig();
    expect(fetch).toHaveBeenCalledTimes(1);
    const [url, options] = fetch.mock.calls[0];
    expect(url).toBe("config.json");
    expect(url.startsWith("/")).toBe(false);
    expect(options).toEqual({ cache: "no-store" });
  });

  test("builds one card per printer, in order", async () => {
    mockFetch({ "config.json": TWO_PRINTERS });
    const app = loadApp();
    await app.loadConfig();
    const ids = [...document.querySelectorAll("[data-printer]")].map((el) => el.dataset.printer);
    expect(ids).toEqual(["p1", "p2"]);
    expect(app.getPrinterIds()).toEqual(["p1", "p2"]);
  });

  test("gives each card its own label and camera", async () => {
    mockFetch({ "config.json": TWO_PRINTERS });
    await loadApp().loadConfig();
    expect(card("p1").querySelector("h2").textContent).toBe("Printer One");
    expect(card("p2").querySelector("h2").textContent).toBe("Printer Two");
    expect(card("p1").querySelector("img").getAttribute("src")).toBe("https://cam-one.test/stream");
    expect(card("p2").querySelector("img").getAttribute("src")).toBe(
      "https://cam-two.test/stream?src=p2"
    );
  });

  test("replaces cards instead of adding to them if run again", async () => {
    mockFetch({ "config.json": TWO_PRINTERS });
    const app = loadApp();
    await app.loadConfig();
    await app.loadConfig();
    expect(document.querySelectorAll("[data-printer]")).toHaveLength(2);
  });

  test("takes the poll interval from the server's settings", async () => {
    mockFetch({ "config.json": TWO_PRINTERS });
    const app = loadApp();
    await app.loadConfig();
    expect(app.getPollIntervalMs()).toBe(2000);
  });

  test("shows the poll interval in the page header", async () => {
    mockFetch({ "config.json": TWO_PRINTERS });
    await loadApp().loadConfig();
    expect(document.querySelector('[data-field="pollIntervalMs"]').textContent).toBe("2000");
  });

  test.each([
    ["no settings at all", { printers: TWO_PRINTERS.printers }],
    ["settings without an interval", { settings: {}, printers: TWO_PRINTERS.printers }],
    ["an interval of zero", { settings: { poll_interval_ms: 0 }, printers: TWO_PRINTERS.printers }],
  ])("keeps the 5 second default with %s", async (_name, config) => {
    mockFetch({ "config.json": config });
    const app = loadApp();
    await app.loadConfig();
    expect(app.getPollIntervalMs()).toBe(5000);
    expect(document.querySelector('[data-field="pollIntervalMs"]').textContent).toBe("5000");
  });

  test("copes with a page that has no poll interval display", async () => {
    mockFetch({ "config.json": TWO_PRINTERS });
    document.querySelector('[data-field="pollIntervalMs"]').remove();
    await expect(loadApp().loadConfig()).resolves.not.toThrow();
  });

  test("hides each camera's spinner when its first frame arrives", async () => {
    mockFetch({ "config.json": TWO_PRINTERS });
    await loadApp().loadConfig();
    expect(isHidden(role("p1", "camera-spinner"))).toBe(false);
    card("p1").querySelector("img").dispatchEvent(new Event("load"));
    expect(isHidden(role("p1", "camera-spinner"))).toBe(true);
    expect(isHidden(role("p2", "camera-spinner"))).toBe(false);
  });

  test("keeps every camera alive with the reconnect watchdog", async () => {
    mockFetch({ "config.json": TWO_PRINTERS });
    const app = loadApp();
    await app.loadConfig();
    jest.advanceTimersByTime(app.CAMERA_WATCHDOG_MS);
    for (const id of ["p1", "p2"]) {
      expect(card(id).querySelector("img").getAttribute("src")).toContain("_retry=");
    }
  });

  test("fails loudly if the server can't be reached, so main() can report it", async () => {
    mockFetch({ "config.json": new Error("network down") });
    await expect(loadApp().loadConfig()).rejects.toThrow("network down");
  });
});

describe("refreshStatus", () => {
  async function ready(status) {
    mockFetch({ "config.json": TWO_PRINTERS, "status.json": status });
    const app = loadApp();
    await app.loadConfig();
    return app;
  }

  test("asks for status.json by a relative URL, bypassing the cache", async () => {
    const app = await ready({ p1: { state: "IDLE" }, p2: { state: "IDLE" } });
    await app.refreshStatus();
    const [url, options] = global.fetch.mock.calls.find(([u]) => u === "status.json");
    expect(url.startsWith("/")).toBe(false);
    expect(options).toEqual({ cache: "no-store" });
  });

  test("updates every printer's card from the one response", async () => {
    const app = await ready({
      p1: RUNNING,
      p2: { state: "IDLE", last_result: "failed" },
    });
    await app.refreshStatus();
    expect(field("p1", "percent")).toBe("42%");
    expect(isHidden(role("p1", "detail"))).toBe(false);
    expect(role("p2", "idle").textContent).toBe("Idle (Print Failed)");
  });

  test("shows Idle for a printer the server didn't mention", async () => {
    const app = await ready({ p1: RUNNING });
    await app.refreshStatus();
    expect(isHidden(role("p2", "idle"))).toBe(false);
    expect(role("p2", "idle").textContent).toBe("Idle");
  });

  test("ignores status for printers that have no card", async () => {
    const app = await ready({ p1: RUNNING, p2: RUNNING, p3: RUNNING });
    await expect(app.refreshStatus()).resolves.toBeUndefined();
    expect(document.querySelector('[data-printer="p3"]')).toBeNull();
  });

  test("logs a failed request and leaves the cards as they were", async () => {
    const error = jest.spyOn(console, "error").mockImplementation(() => {});
    const app = await ready({ p1: RUNNING, p2: { state: "IDLE" } });
    await app.refreshStatus();

    mockFetch({ "status.json": new Error("offline") });
    await expect(app.refreshStatus()).resolves.toBeUndefined();
    expect(error).toHaveBeenCalledWith("status fetch failed", expect.any(Error));
    expect(field("p1", "percent")).toBe("42%");
  });

  test("survives a response that isn't JSON", async () => {
    const error = jest.spyOn(console, "error").mockImplementation(() => {});
    const app = await ready({ p1: RUNNING });
    global.fetch = jest.fn(() => Promise.resolve({ json: () => Promise.reject(new SyntaxError("bad")) }));
    await expect(app.refreshStatus()).resolves.toBeUndefined();
    expect(error).toHaveBeenCalled();
  });
});

describe("setPageTitleDate", () => {
  test("puts today's date, in the viewer's locale, in the title", () => {
    const { setPageTitleDate } = loadApp();
    setPageTitleDate();
    expect(document.getElementById("page-title").textContent).toBe(
      `Printer Status: ${new Date().toLocaleDateString()}`
    );
  });

  test("uses the browser's clock, not a fixed date", () => {
    const { setPageTitleDate } = loadApp();
    jest.setSystemTime(new Date(2030, 0, 2, 12, 0, 0));
    setPageTitleDate();
    expect(document.getElementById("page-title").textContent).toBe(
      `Printer Status: ${new Date(2030, 0, 2).toLocaleDateString()}`
    );
  });

  test("copes with a page that has no title element", () => {
    const { setPageTitleDate } = loadApp();
    document.getElementById("page-title").remove();
    expect(() => setPageTitleDate()).not.toThrow();
  });
});

describe("main", () => {
  const countStatusFetches = () => global.fetch.mock.calls.filter(([u]) => u === "status.json").length;

  test("sets the title, loads the config and fetches status straight away", async () => {
    mockFetch({ "config.json": TWO_PRINTERS, "status.json": { p1: RUNNING, p2: { state: "IDLE" } } });
    await loadApp().main();
    await jest.advanceTimersByTimeAsync(0);

    expect(document.getElementById("page-title").textContent).toContain("Printer Status:");
    expect(document.querySelectorAll("[data-printer]")).toHaveLength(2);
    expect(countStatusFetches()).toBe(1);
    expect(field("p1", "percent")).toBe("42%");
  });

  test("keeps polling at the interval the server asked for", async () => {
    mockFetch({ "config.json": TWO_PRINTERS, "status.json": { p1: RUNNING, p2: { state: "IDLE" } } });
    await loadApp().main();
    await jest.advanceTimersByTimeAsync(0);
    expect(countStatusFetches()).toBe(1);

    await jest.advanceTimersByTimeAsync(1999);
    expect(countStatusFetches()).toBe(1);
    await jest.advanceTimersByTimeAsync(1);
    expect(countStatusFetches()).toBe(2);
    await jest.advanceTimersByTimeAsync(2000);
    expect(countStatusFetches()).toBe(3);
  });

  test("uses the 5 second default when the server doesn't set an interval", async () => {
    mockFetch({
      "config.json": { printers: TWO_PRINTERS.printers },
      "status.json": { p1: { state: "IDLE" }, p2: { state: "IDLE" } },
    });
    await loadApp().main();
    await jest.advanceTimersByTimeAsync(0);
    await jest.advanceTimersByTimeAsync(4999);
    expect(countStatusFetches()).toBe(1);
    await jest.advanceTimersByTimeAsync(1);
    expect(countStatusFetches()).toBe(2);
  });

  test("shows changes as they happen: idle, then printing, then a finished print", async () => {
    mockFetch({ "config.json": TWO_PRINTERS, "status.json": { p1: { state: "IDLE" }, p2: { state: "IDLE" } } });
    await loadApp().main();
    await jest.advanceTimersByTimeAsync(0);
    expect(role("p1", "idle").textContent).toBe("Idle");

    mockFetch({ "status.json": { p1: RUNNING, p2: { state: "IDLE" } } });
    await jest.advanceTimersByTimeAsync(2000);
    expect(isHidden(role("p1", "detail"))).toBe(false);

    mockFetch({ "status.json": { p1: { state: "IDLE", last_result: "succeeded" }, p2: { state: "IDLE" } } });
    await jest.advanceTimersByTimeAsync(2000);
    expect(role("p1", "idle").textContent).toBe("Idle (Print Succeeded)");
  });

  test("keeps polling through a failed request and recovers on its own", async () => {
    jest.spyOn(console, "error").mockImplementation(() => {});
    mockFetch({ "config.json": TWO_PRINTERS, "status.json": { p1: { state: "IDLE" }, p2: { state: "IDLE" } } });
    await loadApp().main();
    await jest.advanceTimersByTimeAsync(0);

    mockFetch({ "status.json": new Error("offline") });
    await jest.advanceTimersByTimeAsync(2000);
    mockFetch({ "status.json": { p1: RUNNING, p2: { state: "IDLE" } } });
    await jest.advanceTimersByTimeAsync(2000);
    expect(field("p1", "percent")).toBe("42%");
  });

  test("if the config can't be loaded it says so and never starts polling", async () => {
    const error = jest.spyOn(console, "error").mockImplementation(() => {});
    mockFetch({ "config.json": new Error("503") });
    await loadApp().main();
    await jest.advanceTimersByTimeAsync(60000);

    expect(error).toHaveBeenCalled();
    expect(countStatusFetches()).toBe(0);
    expect(document.querySelectorAll("[data-printer]")).toHaveLength(0);
  });

  test("still shows the date in the title when the config can't be loaded", async () => {
    jest.spyOn(console, "error").mockImplementation(() => {});
    mockFetch({ "config.json": new Error("503") });
    await loadApp().main();
    expect(document.getElementById("page-title").textContent).toContain("Printer Status:");
  });
});

describe("loading the script", () => {
  test("in a browser (no `module`) it starts the page by itself", async () => {
    // Evaluate app.js the way a <script> tag would: no `module`/`exports` in scope.
    mockFetch({ "config.json": TWO_PRINTERS, "status.json": { p1: RUNNING, p2: { state: "IDLE" } } });
    const source = fs.readFileSync(path.join(CLIENT_DIR, "app.js"), "utf8");
    new Function("module", "exports", `${source}`).call(window, undefined, undefined);
    await jest.advanceTimersByTimeAsync(0);
    expect(document.querySelectorAll("[data-printer]")).toHaveLength(2);
  });

  test("under Jest it exports its functions and does not start itself", () => {
    mockFetch({});
    const app = loadApp();
    expect(typeof app.main).toBe("function");
    expect(global.fetch).not.toHaveBeenCalled();
  });
});
