/**
 * Fails if client/tailwind.css is out of date with the classes used in index.html and app.js.
 *
 * The site ships a pre-built stylesheet so end users never need Node.  If a class is added to the
 * page and the stylesheet isn't rebuilt, that element just looks unstyled -- with no error anywhere.
 * To fix a failure here:  npm run build:css   and commit client/tailwind.css.
 */

const { execFileSync } = require("child_process");
const fs = require("fs");
const os = require("os");
const path = require("path");

const root = path.resolve(__dirname, "../..");
const normalize = (text) => text.replace(/\r\n/g, "\n").trim();

test("client/tailwind.css is up to date (run: npm run build:css)", () => {
  const out = path.join(fs.mkdtempSync(path.join(os.tmpdir(), "tailwind-check-")), "tailwind.css");
  execFileSync(
    process.execPath,
    [
      path.join(root, "node_modules/tailwindcss/lib/cli.js"),
      "-c", "tailwind.config.js",
      "-i", "tailwind.input.css",
      "-o", out,
      "--minify",
    ],
    { cwd: root, stdio: "pipe" }
  );
  const committed = normalize(fs.readFileSync(path.join(root, "client/tailwind.css"), "utf8"));
  expect(normalize(fs.readFileSync(out, "utf8"))).toBe(committed);
}, 60000);
