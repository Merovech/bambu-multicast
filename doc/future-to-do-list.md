# Future To-Do List — bambu-multicast

Things planned for later, in the order they were added.

Added 2026-10-16.

## To do

- [ ] **1. Stress test**
  - The performance tests (`pytest -m perf`, `npm run test:perf`) measure the server and page on a
    desktop with fake printers. A stress test should push further and on the real hardware: run it on
    the Raspberry Pi, with the cameras and ffmpeg running, and find where it actually breaks.
  - Already fixed (found by the performance tests): `ThreadingHTTPServer` kept only 5 connections
    waiting by default, so a burst of simultaneous visitors stalled for 1 s or more. `server.py` now
    uses `WebServer` with `request_queue_size = 128`; the worst request in a 50-visitor burst went
    from about 2,000 ms to about 20 ms. Worth re-checking on the Pi, where the real limit may differ.

- [ ] **2. GitHub: set up branch security**
  - Protect `main`. Decide the rules (for example: require a pull request, require the test checks to
    pass, block force-pushes).
  - Check this against item 3: a workflow that commits a PDF back to `main` is rejected if direct
    pushes are blocked. Settled: the PDF workflow pushes with the secret `PDF_PUSH_TOKEN`, a personal
    access token of a repository admin, who may bypass the rule (see `doc/release-checklist.md`).

- [ ] **3. GitHub Actions: run tests on PR, convert install instructions to PDF**
  - **Run the tests on every pull request:** `pytest` (Python) and `npm test` (Jest). Consider making
    them required checks once item 2 is done. The performance tests stay out of the PR run.
  - **Convert the install instructions to PDF** (`doc/install-guide.md`) when a pull request is merged
    into `main`. Plan already agreed: trigger on `pull_request: closed` with `merged == true`, filtered
    to changes under `doc/`, commit the PDF back as `github-actions[bot]` with `[skip ci]`, and
    `git pull --rebase` before pushing.
  - Renderer: Pandoc with WeasyPrint (`--from=gfm --pdf-engine=weasyprint` plus a stylesheet) for a look
    close to GitHub's. On an Ubuntu runner, install both with `apt`. The `pandoc/core` Docker image does
    not include WeasyPrint, so the earlier Docker-image plan no longer fits.
  - Pin tool versions once it works, and test on a throwaway branch first.

- [ ] **4. Separate admin version that allows pausing, stopping, and resuming a print**
  - A separate build or mode, not part of the view-only public site.
  - **No user tracking or accounts.** This is a deliberate decision.
  - **Warning requirement:** the documentation and the GitHub page must say very clearly that this
    version is for people who trust their users implicitly. It must not be put on a public website:
    anonymous visitors would be able to stop your prints.
  - Open design questions for when this starts: how the admin version is kept separate from the public
    one (separate branch, separate release, or a config switch); and whether it should refuse to run
    unless the person has acknowledged the warning.

- [ ] **5. README.md**
  - The repository has none yet. Cover what the project is, a screenshot, a quick start that points to
    `doc/install-guide.md`, and the license.
  - Should mention the third-party notices (`THIRD_PARTY_NOTICES.md`) and that the site is view-only.
  - If item 4 happens, the README is also where the "trusted users only" warning belongs.

- [ ] **6. 1.0.0 release and Reddit announcement on r/bambulabs**
  - Cut the `1.0.0` release on GitHub. Release zips already leave out `tests/`, `package.json`,
    `pytest.ini` and similar dev-only files through `.gitattributes`.
  - Announce it on r/bambulabs. Read the subreddit's self-promotion rules first.
  - Suggested order: items 1 to 3, 5 and 7 first, so the repository looks finished when people arrive.
    Item 4 can come after 1.0.0.

- [ ] **7. Run stress/perf tests on the Pi**
  - Run the existing performance suite on the Raspberry Pi itself (`pytest -m perf`; install `pytest`
    and `pytest-benchmark` in its venv first, see `requirements-dev.txt`). The numbers recorded so far
    come from a desktop, and the Pi is the machine that matters.
  - Do it with the cameras and ffmpeg running, as in real use, and again with them stopped, to see how
    much the video load slows the web server.
  - Keep the results as a baseline for later comparison. The pass/fail limits in the tests were set
    loose for a desktop, so tighten them if the Pi's numbers show there is room.
  - Run it again after the stress test (item 1) is written, so both are measured on real hardware.
