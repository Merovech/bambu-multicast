"""Checks that keep a release zip (made with `git archive`) and its docs complete.

These exist so the release checklist (doc/release-checklist.md) is enforced by the tests wherever it can be.
"""

import json
import re
import subprocess

import pytest

from config import PROJECT_ROOT

INSTALL_GUIDE = (PROJECT_ROOT / "doc" / "install-guide.md").read_text(encoding="utf-8")
INDEX_HTML = (PROJECT_ROOT / "client" / "index.html").read_text(encoding="utf-8")


def git(*args):
    try:
        return subprocess.run(["git", *args], cwd=PROJECT_ROOT, capture_output=True, text=True).stdout
    except FileNotFoundError:
        pytest.skip("git isn't installed")


def export_ignored(path):
    # "export-ignore: set" means `git archive` leaves the file out of the zip.
    return git("check-attr", "export-ignore", "--", path).strip().endswith(": set")


class TestReleaseArchive:
    @pytest.mark.parametrize("path", [
        "client/index.html", "client/app.js", "client/styles.css", "client/tailwind.css",
        "server/server.py", "config/config.example.json", "requirements.txt", "scripts/setup.sh",
    ])
    def test_files_the_site_needs_are_in_the_zip(self, path):
        assert (PROJECT_ROOT / path).is_file()
        assert not export_ignored(path), f"{path} would be left out of the release zip"

    @pytest.mark.parametrize("path", [
        "tests/", "scripts/package-release.sh", "package.json", "package-lock.json", "tailwind.config.js",
        "tailwind.input.css", "requirements-dev.txt", "scripts/setup-dev.sh", "scripts/upload.sh", "scripts/venv.sh", "pytest.ini",
        ".claude", "doc/release-checklist.md", "doc/future-to-do-list.md",
    ])
    def test_developer_only_files_stay_out_of_the_zip(self, path):
        assert export_ignored(path), f"{path} would be shipped to end users"

    def test_the_built_stylesheet_is_not_git_ignored(self):
        assert git("check-ignore", "client/tailwind.css").strip() == ""


class TestPageUnderItsSecurityPolicy:
    # The Content-Security-Policy allows only the site's own files, so these would silently not work.
    def test_index_html_has_no_inline_script_or_style(self):
        assert not re.search(r"<script(?![^>]*\bsrc=)", INDEX_HTML, re.I), "inline <script>"
        assert "<style" not in INDEX_HTML.lower(), "inline <style>"
        assert not re.search(r"\sstyle=", INDEX_HTML, re.I), "inline style attribute"
        assert not re.search(r"\son\w+=", INDEX_HTML, re.I), "inline event handler"

    def test_index_html_loads_nothing_from_other_sites(self):
        assert not re.findall(r'(?:src|href)="(?:https?:)?//', INDEX_HTML)


class TestConfigIsDocumented:
    def example(self):
        return json.loads((PROJECT_ROOT / "config" / "config.example.json").read_text(encoding="utf-8"))

    def test_every_setting_in_the_example_config_is_in_the_install_guide(self):
        example = self.example()
        keys = set(example) - {"printers"}
        for printer in example["printers"].values():
            keys |= set(printer)
        for key in keys:
            assert f"`{key}`" in INSTALL_GUIDE, f"{key} is in config.example.json but not the install guide"


class TestToolingFilesAreNotPartOfTheProject:
    def test_the_claude_folder_is_git_ignored(self):
        ignored = subprocess.run(["git", "check-ignore", "--no-index", "-q", "--", ".claude/observations/x.log"],
                                 cwd=PROJECT_ROOT).returncode == 0
        assert ignored

    def test_nothing_in_the_claude_folder_is_tracked(self):
        assert git("ls-files", ".claude").strip() == ""

    def test_the_maintainer_checklist_is_still_in_the_repository(self):
        # Excluded from the zip, but it must stay checked in for maintainers.
        assert (PROJECT_ROOT / "doc" / "release-checklist.md").is_file()
        assert git("ls-files", "doc/release-checklist.md").strip() != ""
