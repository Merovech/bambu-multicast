/**
 * Tests for client/index.html -- the page skeleton that app.js fills in.
 */

const fs = require("fs");
const path = require("path");

const html = fs.readFileSync(path.resolve(__dirname, "../../client/index.html"), "utf8");
const doc = new DOMParser().parseFromString(html, "text/html");

describe("index.html", () => {
  test("has the elements app.js looks for", () => {
    expect(doc.getElementById("page-title")).not.toBeNull();
    expect(doc.getElementById("printers")).not.toBeNull();
    expect(doc.querySelector('[data-field="pollIntervalMs"]')).not.toBeNull();
  });

  test("loads app.js and styles.css", () => {
    expect([...doc.scripts].map((s) => s.getAttribute("src"))).toContain("app.js");
    expect([...doc.querySelectorAll("link[rel=stylesheet]")].map((l) => l.getAttribute("href"))).toContain(
      "styles.css"
    );
  });

  test("links to its own files relatively, so it works at / and at /printers/", () => {
    // A leading slash would resolve against the domain root and 404 under /printers/.
    const local = [...doc.querySelectorAll("[src], [href]")]
      .map((el) => el.getAttribute("src") || el.getAttribute("href"))
      .filter((url) => !/^(https?:)?\/\//.test(url));
    expect(local.length).toBeGreaterThan(0);
    for (const url of local) {
      expect(url.startsWith("/")).toBe(false);
    }
  });

  test("is set up for phones", () => {
    expect(doc.querySelector('meta[name="viewport"]').content).toContain("width=device-width");
  });

  test("is a standards-mode HTML5 page in English", () => {
    expect(html.trimStart().toLowerCase().startsWith("<!doctype html>")).toBe(true);
    expect(doc.documentElement.lang).toBe("en");
  });

  test("has a title for the browser tab", () => {
    expect(doc.title.trim()).not.toBe("");
  });

  test("starts with no printer cards; app.js builds them from config.json", () => {
    expect(doc.getElementById("printers").children).toHaveLength(0);
  });

  test("loads app.js after the elements it needs", () => {
    const body = [...doc.body.children];
    const container = body.indexOf(doc.getElementById("printers"));
    const script = body.findIndex((el) => el.tagName === "SCRIPT" && el.getAttribute("src") === "app.js");
    expect(container).toBeGreaterThanOrEqual(0);
    expect(script).toBeGreaterThan(container);
  });
});
