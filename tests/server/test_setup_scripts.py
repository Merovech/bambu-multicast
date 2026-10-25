"""Keeps the two setup scripts and the requirements files consistent.

scripts/setup.sh is for end users and is used in the install guide: production packages only.
scripts/setup-dev.sh is for people changing the code: production plus everything needed to test.
They are deliberately different scripts, and these tests keep it that way.
"""

import re
import subprocess

import pytest

from config import PROJECT_ROOT

TEST_ONLY = ["pytest", "pytest-benchmark", "jest", "npm", "node"]


def read(name):
    return (PROJECT_ROOT / name).read_text(encoding="utf-8")


def package_names(text):
    """Package names from a requirements file's lines, ignoring comments, -r lines and versions."""
    names = []
    for line in text.splitlines():
        line = line.split("#")[0].strip()
        if line and not line.startswith("-"):
            names.append(re.split(r"[<>=!~\[; ]", line)[0].lower().replace("_", "-"))
    return names


def packages_setup_sh_installs():
    names = []
    for line in read("scripts/setup.sh").splitlines():
        match = re.search(r"pip install (.+)", line.split("#")[0])
        if match:
            names += [re.split(r"[<>=!~\[;]", t)[0].lower().replace("_", "-")
                      for t in match.group(1).split() if not t.startswith("-")]
    return names


class TestProductionSetup:
    def test_setup_sh_installs_exactly_the_packages_in_requirements_txt(self):
        assert sorted(packages_setup_sh_installs()) == sorted(package_names(read("requirements.txt")))

    def test_setup_sh_installs_something(self):
        assert packages_setup_sh_installs()

    @pytest.mark.parametrize("tool", TEST_ONLY)
    def test_setup_sh_has_nothing_for_testing(self, tool):
        assert not re.search(rf"\b{re.escape(tool)}\b", read("scripts/setup.sh").lower())

    @pytest.mark.parametrize("tool", ["pytest", "pytest-benchmark"])
    def test_requirements_txt_has_nothing_for_testing(self, tool):
        assert tool not in package_names(read("requirements.txt"))

    def test_setup_sh_does_not_depend_on_other_project_files(self):
        # An end user may have only what the install guide told them to download.
        text = read("scripts/setup.sh")
        assert "requirements" not in text
        assert "config" not in text


class TestDeveloperSetup:
    def test_dev_requirements_include_the_production_ones(self):
        assert re.search(r"^-r\s+requirements\.txt\s*$", read("requirements-dev.txt"), re.M)

    @pytest.mark.parametrize("tool", ["pytest", "pytest-benchmark"])
    def test_dev_requirements_add_the_test_tools(self, tool):
        assert tool in package_names(read("requirements-dev.txt"))

    def test_setup_dev_installs_from_the_dev_requirements(self):
        assert "requirements-dev.txt" in read("scripts/setup-dev.sh")

    def test_setup_dev_installs_the_javascript_tools_exactly_as_locked(self):
        assert re.search(r"^npm ci\b", read("scripts/setup-dev.sh"), re.M)

    def test_setup_dev_never_overwrites_an_existing_config(self):
        text = read("scripts/setup-dev.sh")
        assert re.search(r'if \[ -f config/config\.json \]', text)

    def test_the_two_scripts_are_not_the_same_script(self):
        assert read("scripts/setup.sh") != read("scripts/setup-dev.sh")
        assert "npm" in read("scripts/setup-dev.sh") and "npm" not in read("scripts/setup.sh")


class TestScriptsAreUsable:
    @pytest.mark.parametrize("script", ["scripts/setup.sh", "scripts/setup-dev.sh"])
    def test_scripts_exist(self, script):
        assert (PROJECT_ROOT / script).is_file()

    def test_setup_dev_starts_with_a_real_shebang(self):
        assert read("scripts/setup-dev.sh").startswith("#!/usr/bin/env bash")

    def test_every_package_the_server_imports_is_a_requirement(self):
        # server.py imports bambulabs_api; if it ever imports another third-party package, this
        # will remind whoever adds it to list it in requirements.txt (and setup.sh).
        imported = set(re.findall(r"^\s*(?:import|from)\s+([A-Za-z_][\w]*)", read("server/server.py"), re.M))
        local = {p.stem for p in (PROJECT_ROOT / "server").glob("*.py")}
        stdlib = {"json", "logging", "threading", "time", "datetime", "http", "pathlib", "sys", "os"}
        third_party = {name.lower().replace("_", "-") for name in imported - local - stdlib}
        assert third_party <= set(package_names(read("requirements.txt")))


class TestSupplyChain:
    def test_production_packages_are_pinned_to_an_exact_version(self):
        for line in read("requirements.txt").splitlines():
            line = line.split("#")[0].strip()
            if line:
                assert re.search(r"==\d", line), f"{line} is not pinned with =="

    def test_setup_sh_pins_the_same_versions_as_requirements_txt(self):
        pinned = set(re.findall(r"[\w.-]+==[\w.]+", read("requirements.txt")))
        assert pinned and pinned <= set(re.findall(r"[\w.-]+==[\w.]+", read("scripts/setup.sh")))

    def test_setup_sh_starts_with_a_real_shebang_and_stops_on_errors(self):
        text = read("scripts/setup.sh")
        assert text.startswith("#!/bin/bash")
        assert "set -euo pipefail" in text


class TestScriptsInTheScriptsFolder:
    SCRIPTS = sorted(p.name for p in (PROJECT_ROOT / "scripts").glob("*.sh"))

    def test_there_are_scripts_to_check(self):
        assert {"setup.sh", "setup-dev.sh", "upload.sh", "package-release.sh"} <= set(self.SCRIPTS)

    @pytest.mark.parametrize("script", ["setup-dev.sh", "upload.sh", "package-release.sh"])
    def test_scripts_that_work_on_project_files_change_to_the_project_root_not_their_own_folder(self, script):
        # They live in scripts/, so the project root is one level up from the script.
        assert 'cd "$(dirname "${BASH_SOURCE[0]}")/.."' in read(f"scripts/{script}") or \
            'cd "$(dirname "$SELF")/.."' in read(f"scripts/{script}")

    @pytest.mark.parametrize("script", SCRIPTS)
    def test_every_script_would_be_committed_not_git_ignored(self, script):
        ignored = subprocess.run(["git", "check-ignore", "--no-index", "-q", "--", f"scripts/{script}"],
                                 cwd=PROJECT_ROOT).returncode == 0
        assert not ignored, f"scripts/{script} is ignored by git"

    @pytest.mark.parametrize("script", SCRIPTS)
    def test_every_script_has_unix_line_endings(self, script):
        assert b"\r" not in (PROJECT_ROOT / "scripts" / script).read_bytes()

    def test_the_install_guide_points_at_where_the_zip_puts_the_script(self):
        guide = (PROJECT_ROOT / "doc" / "install-guide.md").read_text(encoding="utf-8")
        assert "chmod +x scripts/setup.sh" in guide
        assert "./scripts/setup.sh" in guide
        assert not re.search(r"(?<![/\w-])setup\.sh", guide.replace("scripts/setup.sh", "")), \
            "the guide still mentions setup.sh without its scripts/ folder"
