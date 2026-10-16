# Release checklist (maintainers)

Most of this is enforced by the tests (`pytest` and `npm test`); run both before you commit and before you cut a release.

## Whenever you change the page's look
- Added or changed a Tailwind class in `client/index.html` or `client/app.js`? Run `npm run build:css` and commit `client/tailwind.css`. End users never build it. If you forget, `npm test` fails (`tests/client/tailwind.test.js`).
- Write class names out in full. A name assembled at run time (`` `text-${color}-400` ``) is never detected, so it won't be in the stylesheet.
- Classes in a new file are only picked up if the file is listed under `content` in `tailwind.config.js`.
- After upgrading `tailwindcss`, rebuild and commit the stylesheet.

## Whenever you add or change a file
- New file in `client/`: add it to `STATIC_FILES` in `server/server.py`, or it returns a 404.
- The page's Content-Security-Policy allows only this site's own scripts and styles. No inline `<script>`, `<style>`, `style=` or `onclick=`, and nothing loaded from another site. Camera images may come from any http(s) address. To change the policy, edit `SECURITY_HEADERS` in `server/server.py` on purpose.
- Never serve `config.json`; it holds printer access codes.

## Whenever you add or change a setting
- Validate it in `server/config.py`, with a plain-language error.
- Add it to `config/config.example.json` and to the table in `doc/install-guide.md`.

## Whenever you change dependencies
- `bambulabs-api`: change the version in `requirements.txt` and `setup.sh` together. Both are pinned with `==`.
- Dev tooling goes in `requirements-dev.txt` or `package.json`, never in the production files.

## Before cutting a release
1. `pytest` and `npm test` both pass, and `client/tailwind.css` is committed.
2. Make the zip with `git archive` so the `export-ignore` rules in `.gitattributes` apply.
3. Check the zip contains `client/tailwind.css`, and does not contain `tests/`, `node_modules/`, `package.json` or the Tailwind config files.
4. Open the page from the zip (or a deploy of it) once in a browser: confirm it is styled, the cameras load and nothing is blocked in the browser console.
