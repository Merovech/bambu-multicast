"""Checks for the GitHub Action that turns doc/install-guide.md into a PDF.

The action itself only runs on GitHub, so these check everything that can go wrong before it gets
there: when it triggers, what it can do, that the files it uses exist, and that the guide is written
in a way the converter handles.  (To try the real thing, run the build script, see its header.)
"""

import json
import re
import subprocess

import pytest
import yaml

from config import PROJECT_ROOT

WORKFLOW = PROJECT_ROOT / ".github" / "workflows" / "install-guide-pdf.yml"
BUILD_DIR = PROJECT_ROOT / ".github" / "install-guide-pdf"
GUIDE = PROJECT_ROOT / "doc" / "install-guide.md"


@pytest.fixture(scope="module")
def workflow():
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def triggers(workflow):
    # YAML 1.1 reads the key `on` as the boolean True.
    return workflow.get("on", workflow.get(True))


def steps(workflow):
    return workflow["jobs"]["build"]["steps"]


class TestWhenItRuns:
    def test_runs_on_a_push_to_main_only_when_the_install_guide_changes(self, workflow):
        push = triggers(workflow)["push"]
        assert push["branches"] == ["main"]
        assert push["paths"] == ["doc/install-guide.md"]

    def test_the_file_it_watches_exists(self):
        assert GUIDE.is_file()

    def test_does_not_run_on_pull_requests_or_a_schedule(self, workflow):
        assert set(triggers(workflow)) <= {"push", "workflow_dispatch"}

    def test_can_be_started_by_hand_for_trying_it_out(self, workflow):
        assert "workflow_dispatch" in triggers(workflow)

    def test_two_runs_never_build_at_the_same_time(self, workflow):
        assert workflow["concurrency"]["cancel-in-progress"] is False


class TestWhatItMayDo:
    def test_only_has_permission_to_write_repository_contents(self, workflow):
        assert workflow["permissions"] == {"contents": "write"}

    def test_every_action_it_uses_is_pinned_to_a_version(self, workflow):
        used = [s["uses"] for s in steps(workflow) if "uses" in s]
        assert used
        for action in used:
            assert re.search(r"@v\d+$", action), f"{action} is not pinned to a version"

    def test_pandoc_is_pinned_to_an_exact_version(self, workflow):
        pandoc = next(s for s in steps(workflow) if str(s.get("uses", "")).startswith("pandoc/actions/setup"))
        assert re.fullmatch(r"\d+\.\d+(\.\d+)?", str(pandoc["with"]["version"]))

    def test_installs_the_exact_locked_dependencies(self, workflow):
        assert any(s.get("run") == "npm ci" for s in steps(workflow))

    def test_builds_with_the_script_in_the_repository(self, workflow):
        assert any("bash .github/install-guide-pdf/build.sh" in s.get("run", "") for s in steps(workflow))

    def test_commits_only_the_pdf_and_cannot_retrigger_itself(self, workflow):
        commit = next(s["run"] for s in steps(workflow) if "git commit" in s.get("run", ""))
        assert re.search(r"git add (-f )?doc/install-guide\.pdf\b", commit)
        assert "[skip ci]" in commit
        assert "git add ." not in commit and "git add -A" not in commit

    def test_the_pdf_is_also_kept_as_a_downloadable_artifact(self, workflow):
        upload = next(s for s in steps(workflow) if str(s.get("uses", "")).startswith("actions/upload-artifact"))
        assert upload["with"]["path"] == "doc/install-guide.pdf"


class TestTheBuildFiles:
    @pytest.mark.parametrize("name", ["build.sh", "template.html", "github-alerts.lua"])
    def test_exist(self, name):
        assert (BUILD_DIR / name).is_file()

    def test_the_script_only_uses_files_that_exist(self):
        script = (BUILD_DIR / "build.sh").read_text(encoding="utf-8")
        for variable in ("SOURCE", "TEMPLATE", "FILTER"):
            path = re.search(rf"^{variable}=(\S+)", script, re.M).group(1)
            assert (PROJECT_ROOT / path).is_file(), f"{variable}={path}"
        assert "doc/install-guide.pdf" in script

    def test_the_template_wraps_the_page_the_way_github_styling_expects(self):
        template = (BUILD_DIR / "template.html").read_text(encoding="utf-8")
        assert '<article class="markdown-body">' in template
        assert "$body$" in template and "$for(css)$" in template
        assert "size: Letter" in template

    def test_every_page_is_numbered_in_the_bottom_margin(self):
        template = (BUILD_DIR / "template.html").read_text(encoding="utf-8")
        assert "@bottom-center" in template
        assert "counter(page)" in template and "counter(pages)" in template

    def test_the_numbers_are_not_the_chrome_header_and_footer_that_would_add_the_date_and_a_path(self):
        build = (BUILD_DIR / "build.sh").read_text(encoding="utf-8")
        assert "--no-pdf-header-footer" in build

    def test_the_template_loads_nothing_from_other_sites(self):
        template = (BUILD_DIR / "template.html").read_text(encoding="utf-8")
        assert not re.search(r"(src|href)=\"https?://", template)

    @pytest.mark.parametrize("kind", ["note", "tip", "important", "warning", "caution"])
    def test_every_callout_type_gets_github_markup_and_an_icon(self, kind):
        lua = (BUILD_DIR / "github-alerts.lua").read_text(encoding="utf-8")
        assert re.search(rf"^\s*{kind} = \[==\[<svg", lua, re.M)
        assert re.search(rf'{kind} = "{kind.capitalize()}"', lua)
        assert "markdown-alert markdown-alert-" in lua

    @pytest.mark.parametrize("path", [".github/install-guide-pdf/build.sh", ".github/install-guide-pdf/template.html",
                                      ".github/install-guide-pdf/github-alerts.lua", ".github/workflows/install-guide-pdf.yml"])
    def test_nothing_the_workflow_needs_is_git_ignored(self, path):
        # *.sh is ignored by .gitignore (personal scripts); without an exception build.sh would never reach
        # GitHub and the workflow would fail on its first run.  (--no-index: judge the rule itself, even for a
        # file that is already tracked.)
        ignored = subprocess.run(["git", "check-ignore", "--no-index", "-q", "--", path], cwd=PROJECT_ROOT)
        assert ignored.returncode == 1, f"{path} is ignored by git"

    def test_the_build_script_has_unix_line_endings_in_the_repository(self):
        attrs = subprocess.run(["git", "check-attr", "eol", "--", ".github/install-guide-pdf/build.sh"],
                               cwd=PROJECT_ROOT, capture_output=True, text=True).stdout
        assert attrs.strip().endswith(": lf")

    def test_the_github_folder_stays_out_of_release_zips(self):
        attrs = subprocess.run(["git", "check-attr", "export-ignore", "--", ".github"],
                               cwd=PROJECT_ROOT, capture_output=True, text=True).stdout
        assert attrs.strip().endswith(": set")


class TestTheGitHubStylesheet:
    def lockfile_version(self):
        lock = json.loads((PROJECT_ROOT / "package-lock.json").read_text(encoding="utf-8"))
        return lock["packages"]["node_modules/github-markdown-css"]["version"]

    def test_is_a_dev_dependency_pinned_to_an_exact_version(self):
        package = json.loads((PROJECT_ROOT / "package.json").read_text(encoding="utf-8"))
        version = package["devDependencies"]["github-markdown-css"]
        assert re.fullmatch(r"\d+\.\d+\.\d+", version), f"{version} is not an exact version"

    def test_the_lockfile_agrees_with_package_json(self):
        package = json.loads((PROJECT_ROOT / "package.json").read_text(encoding="utf-8"))
        assert package["devDependencies"]["github-markdown-css"] == self.lockfile_version()

    def test_it_is_not_a_production_dependency(self):
        package = json.loads((PROJECT_ROOT / "package.json").read_text(encoding="utf-8"))
        assert "github-markdown-css" not in package.get("dependencies", {})


class TestTheGuideIsWrittenForTheConverter:
    def table_starts(self):
        lines = GUIDE.read_text(encoding="utf-8").replace("\r\n", "\n").split("\n")
        in_fence = False
        for n, line in enumerate(lines):
            if re.match(r"^\s*```", line):
                in_fence = not in_fence
            if in_fence:
                continue
            if re.match(r"^\s*\|", line) and n + 1 < len(lines) and re.match(r"^\s*\|\s*:?-+", lines[n + 1]):
                yield n, lines

    def test_there_are_tables_to_check(self):
        assert list(self.table_starts())

    def test_no_table_directly_follows_a_line_of_text(self):
        # GitHub draws a table that starts right after a paragraph line, but pandoc prints it as a run
        # of "|" characters.  A blank line (or a heading) before every table works in both.
        bad = []
        for n, lines in self.table_starts():
            previous = lines[n - 1].strip()
            if previous and not previous.startswith("#") and not previous.startswith("|"):
                bad.append(f"line {n + 1}: {previous[:50]!r}")
        assert not bad, "put a blank line before the table at: " + "; ".join(bad)


class TestThePdfIsOnlyEverCommittedByTheAction:
    def ignored(self, path):
        return subprocess.run(["git", "check-ignore", "--no-index", "-q", "--", path],
                              cwd=PROJECT_ROOT).returncode == 0

    def test_the_pdf_is_git_ignored_so_a_hand_built_one_is_never_committed(self):
        assert self.ignored("doc/install-guide.pdf")

    def test_the_workflow_force_adds_it_anyway(self, workflow):
        # Without -f, git refuses to add an ignored file and the commit step would fail.
        commit = next(s["run"] for s in steps(workflow) if "git commit" in s.get("run", ""))
        assert "git add -f doc/install-guide.pdf" in commit

    def test_the_build_script_can_write_elsewhere_for_local_previews(self):
        script = (BUILD_DIR / "build.sh").read_text(encoding="utf-8")
        assert "OUTPUT=${OUTPUT:-doc/install-guide.pdf}" in script

    def test_other_pdfs_are_not_ignored(self):
        assert not self.ignored("doc/something-else.pdf")
