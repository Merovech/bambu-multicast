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

## Whenever you change the install guide
- Pushing a change to `doc/install-guide.md` on `main` rebuilds `doc/install-guide.pdf` in GitHub's style (`.github/workflows/install-guide-pdf.yml`) and commits it. You can run it by hand from the Actions tab, or locally with `bash .github/install-guide-pdf/build.sh` (needs pandoc 3.9 and Chrome; run `npm ci` first).
- `doc/install-guide.pdf` is git-ignored on purpose: only the workflow commits it (with `git add -f`). To try the build yourself without touching it, write elsewhere: `OUTPUT=build/install-guide.pdf bash .github/install-guide-pdf/build.sh`. (Once the bot has committed the PDF, git tracks it and no longer ignores edits to it, so a rebuild in place would show as modified; restore it with `git checkout -- doc/install-guide.pdf`.)
- Put a blank line before every table. GitHub draws a table that follows a line of text, but the PDF converter doesn't; a test checks this.
- `main` requires a pull request, which the built-in Actions token cannot get past. The workflow therefore pushes the PDF with a personal access token of a repository admin (admins may bypass the rule), stored as the repository secret `PDF_PUSH_TOKEN`. If the secret is missing or the token has expired, the workflow fails on its first step, or at the push, and no PDF is committed.
  - Create it: GitHub > Settings > Developer settings > Personal access tokens > Fine-grained tokens > Generate new token. Resource owner: you. Repository access: only `Merovech/bambu-multicast`. Permission: Repository permissions > Contents: Read and write (nothing else). Set an expiry (a year is reasonable) and put the renewal date in your calendar.
  - Store it: repository Settings > Secrets and variables > Actions > New repository secret, name `PDF_PUSH_TOKEN`.
  - Renew it before it expires by replacing the secret's value. Revoke it at once if it ever leaks.

## Whenever you change dependencies
- `bambulabs-api`: change the version in `requirements.txt` and `scripts/setup.sh` together. Both are pinned with `==`.
- Dev tooling goes in `requirements-dev.txt` or `package.json`, never in the production files.

## Before cutting a release
1. `pytest` and `npm test` both pass, and `client/tailwind.css` is committed.
2. Commit everything, then make the zip: `bash scripts/package-release.sh 1.0.0` (or tag the commit `v1.0.0` and leave the version off). It writes `build/bambu-multicast-<version>.zip` with `git archive`, so only committed files go in and the `export-ignore` rules in `.gitattributes` apply. It refuses to run if tracked files have uncommitted changes (`--allow-dirty` overrides that) or `client/tailwind.css` isn't committed.
3. The script checks the zip's contents itself and deletes the zip if something is wrong: it must contain `client/tailwind.css`, the server, the client, `setup.sh` and the docs, and must not contain `tests/`, `scripts/`, `.github/`, `node_modules/`, `package.json`, the Tailwind config files or `config/config.json`. When it passes it prints the zip's size, file count and SHA-256.
4. Open the page from the zip (or a deploy of it) once in a browser: confirm it is styled, the cameras load and nothing is blocked in the browser console.
