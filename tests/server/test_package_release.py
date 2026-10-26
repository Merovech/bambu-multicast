"""Checks for scripts/package-release.sh, which builds the zip that end users download.

The first group checks the git rules that keep the script checked in but out of the zip.  The second group
is an integration test: it copies the project into a throwaway git repository, runs the script there, and
inspects the zip it makes.  Nothing is written to the real build/ folder.
"""

import hashlib
import os
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

from config import PROJECT_ROOT

SCRIPT = "scripts/package-release.sh"

REQUIRED = [
    "server/server.py", "server/config.py", "server/print_errors.py", "server/print_errors.json",
    "server/print_result.py", "server/printer_status_map.py",
    "client/index.html", "client/app.js", "client/styles.css", "client/tailwind.css",
    "config/config.example.json", "scripts/setup.sh", "requirements.txt", "LICENSE", "THIRD_PARTY_NOTICES.md",
    "doc/install-guide.md",
]
FORBIDDEN_FILES = [
    "package.json", "package-lock.json", "pytest.ini", "requirements-dev.txt", "setup-dev.sh",
    "scripts/setup-dev.sh", "scripts/upload.sh", "scripts/venv.sh", "scripts/package-release.sh",
    "tailwind.config.js", "tailwind.input.css", ".gitattributes", ".gitignore",
    "config/config.json", "doc/future-to-do-list.md", "doc/release-checklist.md",
]
FORBIDDEN_FOLDERS = ["tests", ".github", "node_modules", "build", ".claude"]


def ignored(path):
    # --no-index judges the path by the rules alone, not by whether git already tracks it.
    try:
        return subprocess.run(["git", "check-ignore", "--no-index", "-q", "--", path],
                              cwd=PROJECT_ROOT).returncode == 0
    except FileNotFoundError:
        pytest.skip("git isn't installed")


def export_ignored(path):
    try:
        out = subprocess.run(["git", "check-attr", "export-ignore", "--", path], cwd=PROJECT_ROOT,
                             capture_output=True, text=True).stdout
    except FileNotFoundError:
        pytest.skip("git isn't installed")
    return out.strip().endswith(": set")


class TestTheScriptIsCheckedInButNotShipped:
    def test_the_script_exists(self):
        assert (PROJECT_ROOT / SCRIPT).is_file()

    def test_the_script_is_not_git_ignored(self):
        assert not ignored(SCRIPT), "git would silently never commit the script: add an exception to .gitignore"

    @pytest.mark.parametrize("path", ["scripts/package-release.sh", "scripts/setup-dev.sh", "scripts/upload.sh",
                                      "scripts/venv.sh"])
    def test_the_developer_scripts_are_left_out_of_the_zip(self, path):
        assert export_ignored(path)

    def test_setup_sh_ships_even_though_it_lives_in_the_scripts_folder(self):
        # End users run it from the unzipped folder; excluding the whole scripts/ folder would drop it.
        assert not export_ignored("scripts/setup.sh")
        assert not export_ignored("scripts")

    def test_build_output_is_git_ignored(self):
        assert ignored("build/")
        assert ignored("build/bambu-multicast-1.0.0.zip")

    def test_it_has_unix_line_endings_and_a_real_shebang(self):
        text = (PROJECT_ROOT / SCRIPT).read_bytes()
        assert b"\r" not in text
        assert text.startswith(b"#!/usr/bin/env bash\n")
        assert b"set -euo pipefail" in text

    def test_it_does_not_run_the_test_suites(self):
        text = (PROJECT_ROOT / SCRIPT).read_text(encoding="utf-8")
        code = [line for line in text.splitlines() if line.strip().startswith(("pytest", "npm", "python"))]
        assert not code


# ---------------------------------------------------------------------------------------------------------
# Integration tests: run the real script in a throwaway repository.
# ---------------------------------------------------------------------------------------------------------

def find_bash():
    if sys.platform == "win32":
        # On Windows, a bare "bash" can be WSL's, which can't run a C:/ path.  Git for Windows brings its own.
        git_exe = shutil.which("git")
        if git_exe:
            for parent in Path(git_exe).resolve().parents[:3]:
                candidate = parent / "bin" / "bash.exe"
                if candidate.is_file():
                    return str(candidate)
    return shutil.which("bash")


BASH = find_bash()

# Variables such as GIT_DIR (set when run from a git hook) would point git at the wrong repository.
CLEAN_ENV = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}


def run(args, cwd, check=True):
    result = subprocess.run(args, cwd=cwd, capture_output=True, text=True, env=CLEAN_ENV)
    if check and result.returncode != 0:
        raise AssertionError(f"{args} failed:\n{result.stdout}\n{result.stderr}")
    return result


def git_in(repo, *args):
    return run(["git", *args], repo)


def commit_all(repo, message="change", force=False):
    # force: also commit files .gitignore would normally keep out (to simulate someone forcing them in)
    git_in(repo, "add", "-A", *(["-f"] if force else []))
    git_in(repo, "commit", "-q", "-m", message)


@pytest.fixture(scope="module")
def committed_repo(tmp_path_factory):
    """A copy of the project's files (as they are now, committed or not) as a fresh one-commit git repo."""
    if shutil.which("git") is None:
        pytest.skip("git isn't installed")
    if BASH is None:
        pytest.skip("bash isn't installed")
    repo = tmp_path_factory.mktemp("project") / "bambu-multicast"
    repo.mkdir()
    listed = run(["git", "ls-files", "-co", "--exclude-standard", "-z"], PROJECT_ROOT).stdout
    for name in filter(None, listed.split("\0")):
        source = PROJECT_ROOT / name
        # .claude/ holds this machine's tool logs, not the project; deleted-but-tracked files aren't there to copy.
        if name.startswith(".claude/") or not source.is_file():
            continue
        (repo / name).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, repo / name)
    git_in(repo, "init", "-q")
    for key, value in [("user.name", "Test"), ("user.email", "test@example.test"),
                       ("commit.gpgsign", "false"), ("core.autocrlf", "false")]:
        git_in(repo, "config", key, value)
    commit_all(repo, "release candidate")
    return repo


@pytest.fixture
def repo(committed_repo, tmp_path):
    """A private copy of the committed repo that a test may change."""
    mine = tmp_path / "work" / "bambu-multicast"
    shutil.copytree(committed_repo, mine)
    return mine


@pytest.fixture
def out(tmp_path):
    return tmp_path / "out"


def package(repo, out, *args, cwd=None):
    return run([BASH, (repo / SCRIPT).as_posix(), "--out", out.as_posix(), *args], cwd or repo, check=False)


def names(zip_path):
    with zipfile.ZipFile(zip_path) as z:
        return z.namelist()


def built(out):
    return sorted(p.name for p in out.glob("*")) if out.exists() else []


class TestBuildsTheZip:
    def test_makes_a_zip_with_one_top_level_folder(self, repo, out):
        result = package(repo, out, "1.0.0")
        assert result.returncode == 0, result.stderr
        assert built(out) == ["bambu-multicast-1.0.0.zip"]
        entries = names(out / "bambu-multicast-1.0.0.zip")
        assert all(e.startswith("bambu-multicast-1.0.0/") for e in entries)
        assert {e.split("/")[0] for e in entries} == {"bambu-multicast-1.0.0"}

    def test_has_everything_the_site_needs(self, repo, out):
        assert package(repo, out, "1.0.0").returncode == 0
        entries = set(names(out / "bambu-multicast-1.0.0.zip"))
        for path in REQUIRED:
            assert f"bambu-multicast-1.0.0/{path}" in entries, f"{path} is missing"

    def test_has_nothing_that_is_only_for_developers(self, repo, out):
        assert package(repo, out, "1.0.0").returncode == 0
        for entry in names(out / "bambu-multicast-1.0.0.zip"):
            rel = entry.split("/", 1)[1]
            assert rel not in FORBIDDEN_FILES, f"{rel} must not ship"
            assert rel.split("/")[0] not in FORBIDDEN_FOLDERS, f"{rel} must not ship"
            assert "__pycache__" not in rel and not rel.endswith(".pyc"), f"{rel} must not ship"

    def test_the_stylesheet_in_the_zip_is_the_committed_one(self, repo, out):
        assert package(repo, out, "1.0.0").returncode == 0
        with zipfile.ZipFile(out / "bambu-multicast-1.0.0.zip") as z:
            assert z.read("bambu-multicast-1.0.0/client/tailwind.css") == (repo / "client/tailwind.css").read_bytes()

    def test_reports_the_path_size_file_count_and_checksum(self, repo, out):
        result = package(repo, out, "1.0.0")
        zip_path = out / "bambu-multicast-1.0.0.zip"
        text = result.stdout
        assert zip_path.name in text
        assert f"{zip_path.stat().st_size} bytes" in text
        files = [e for e in names(zip_path) if not e.endswith("/")]
        assert re.search(rf"Files:\s+{len(files)}\b", text)
        assert hashlib.sha256(zip_path.read_bytes()).hexdigest() in text

    def test_reminds_about_the_checks_it_cannot_make(self, repo, out):
        text = package(repo, out, "1.0.0").stdout
        assert "pytest" in text and "npm test" in text and "browser" in text

    def test_does_not_need_to_be_run_from_the_project_folder(self, repo, out, tmp_path):
        elsewhere = tmp_path / "elsewhere"
        elsewhere.mkdir()
        result = package(repo, out, "1.0.0", cwd=elsewhere)
        assert result.returncode == 0, result.stderr
        assert (out / "bambu-multicast-1.0.0.zip").is_file()
        assert list(elsewhere.iterdir()) == []

    def test_a_relative_output_folder_is_relative_to_where_you_ran_it(self, repo, tmp_path):
        elsewhere = tmp_path / "elsewhere"
        elsewhere.mkdir()
        result = run([BASH, (repo / SCRIPT).as_posix(), "--out", "zips", "1.0.0"], elsewhere, check=False)
        assert result.returncode == 0, result.stderr
        assert (elsewhere / "zips" / "bambu-multicast-1.0.0.zip").is_file()

    def test_builds_into_build_by_default(self, repo):
        result = run([BASH, (repo / SCRIPT).as_posix(), "1.0.0"], repo, check=False)
        assert result.returncode == 0, result.stderr
        assert (repo / "build" / "bambu-multicast-1.0.0.zip").is_file()

    def test_replaces_a_zip_of_the_same_name(self, repo, out):
        assert package(repo, out, "1.0.0").returncode == 0
        assert package(repo, out, "1.0.0").returncode == 0
        assert built(out) == ["bambu-multicast-1.0.0.zip"]


class TestVersion:
    def test_a_version_with_a_suffix_is_fine(self, repo, out):
        assert package(repo, out, "1.0.0-rc1").returncode == 0
        assert built(out) == ["bambu-multicast-1.0.0-rc1.zip"]
        assert names(out / "bambu-multicast-1.0.0-rc1.zip")[0] == "bambu-multicast-1.0.0-rc1/"

    def test_without_a_version_it_uses_the_tag_on_head_without_the_v(self, repo, out):
        git_in(repo, "tag", "v2.3.4")
        result = package(repo, out)
        assert result.returncode == 0, result.stderr
        assert built(out) == ["bambu-multicast-2.3.4.zip"]

    def test_the_argument_wins_over_the_tag(self, repo, out):
        git_in(repo, "tag", "v2.3.4")
        assert package(repo, out, "9.9.9").returncode == 0
        assert built(out) == ["bambu-multicast-9.9.9.zip"]

    def test_a_tag_on_an_older_commit_is_not_used(self, repo, out):
        git_in(repo, "tag", "v2.3.4")
        (repo / "LICENSE").write_text("changed\n")
        commit_all(repo)
        result = package(repo, out)
        assert result.returncode != 0
        assert built(out) == []

    def test_with_neither_it_stops_and_says_how_to_give_a_version(self, repo, out):
        result = package(repo, out)
        assert result.returncode != 0
        assert "bash scripts/package-release.sh 1.0.0" in result.stderr
        assert built(out) == []

    def test_a_tag_that_is_not_a_version_is_refused(self, repo, out):
        git_in(repo, "tag", "release-final")
        result = package(repo, out)
        assert result.returncode != 0
        assert "not a valid version" in result.stderr
        assert built(out) == []

    @pytest.mark.parametrize("bad", ["../evil", "1.0/../..", "1.0.0/x", "a.b.c", "v1.0.0", "1..0", "1.0.",
                                     "1.0.0-", "1.0.0-rc/1", "1.0.0 beta", "1.0.0;ls", "$(ls)", "-1.0"])
    def test_an_invalid_version_is_refused_and_creates_nothing(self, repo, out, tmp_path, bad):
        assert package(repo, out, bad).returncode != 0
        assert list(tmp_path.rglob("*.zip")) == []

    def test_help_shows_the_usage_and_builds_nothing(self, repo, out, tmp_path):
        result = package(repo, out, "--help")
        assert result.returncode == 0
        assert "package-release.sh" in result.stdout
        assert list(tmp_path.rglob("*.zip")) == []

    def test_two_versions_are_refused(self, repo, out):
        assert package(repo, out, "1.0.0", "2.0.0").returncode != 0
        assert built(out) == []


class TestPreflightChecks:
    def test_changes_to_a_tracked_file_that_are_not_committed_are_refused(self, repo, out):
        with (repo / "client" / "app.js").open("a") as f:
            f.write("\n// not committed\n")
        result = package(repo, out, "1.0.0")
        assert result.returncode != 0
        assert "not committed" in result.stderr and "--allow-dirty" in result.stderr
        assert "client/app.js" in result.stderr
        assert built(out) == []

    def test_allow_dirty_builds_the_committed_files_not_the_changed_ones(self, repo, out):
        with (repo / "client" / "app.js").open("a") as f:
            f.write("\n// not committed\n")
        result = package(repo, out, "--allow-dirty", "1.0.0")
        assert result.returncode == 0, result.stderr
        with zipfile.ZipFile(out / "bambu-multicast-1.0.0.zip") as z:
            assert b"not committed" not in z.read("bambu-multicast-1.0.0/client/app.js")

    def test_new_files_that_are_not_tracked_do_not_matter(self, repo, out):
        (repo / ".claude").mkdir()
        (repo / ".claude" / "notes.log").write_text("x")
        (repo / "scratch.txt").write_text("x")
        result = package(repo, out, "1.0.0")
        assert result.returncode == 0, result.stderr
        assert not any("scratch" in e or ".claude" in e for e in names(out / "bambu-multicast-1.0.0.zip"))

    def test_a_ref_other_than_head_can_be_chosen(self, repo, out):
        (repo / "LICENSE").write_text("second version\n")
        commit_all(repo)
        assert package(repo, out, "--ref", "HEAD~1", "1.0.0").returncode == 0
        with zipfile.ZipFile(out / "bambu-multicast-1.0.0.zip") as z:
            assert z.read("bambu-multicast-1.0.0/LICENSE") != b"second version\n"

    def test_an_unknown_ref_is_refused(self, repo, out):
        result = package(repo, out, "--ref", "no-such-branch", "1.0.0")
        assert result.returncode != 0
        assert "no-such-branch" in result.stderr
        assert built(out) == []

    def test_a_missing_stylesheet_is_refused(self, repo, out):
        git_in(repo, "rm", "-q", "client/tailwind.css")
        git_in(repo, "commit", "-q", "-m", "oops")
        result = package(repo, out, "1.0.0")
        assert result.returncode != 0
        assert "client/tailwind.css" in result.stderr and "build:css" in result.stderr
        assert built(out) == []

    def test_a_stylesheet_that_is_only_on_disk_does_not_count(self, repo, out):
        # Deleting it from the commit but leaving the file in the folder must still be refused.
        git_in(repo, "rm", "-q", "--cached", "client/tailwind.css")
        git_in(repo, "commit", "-q", "-m", "oops")
        assert (repo / "client" / "tailwind.css").is_file()
        assert package(repo, out, "1.0.0").returncode != 0
        assert built(out) == []

    def test_a_folder_that_is_not_a_git_repository_is_refused(self, committed_repo, tmp_path):
        plain = tmp_path / "plain"
        (plain / "scripts").mkdir(parents=True)
        shutil.copy2(committed_repo / SCRIPT, plain / SCRIPT)
        result = run([BASH, (plain / SCRIPT).as_posix(), "--out", (tmp_path / "o").as_posix(), "1.0.0"],
                     plain, check=False)
        assert result.returncode != 0
        assert "not a git repository" in result.stderr


class TestTheZipIsCheckedAfterBuilding:
    def test_a_file_that_must_not_ship_deletes_the_zip_and_fails(self, repo, out):
        (repo / "config" / "config.json").write_text("{}")
        commit_all(repo, force=True)  # a committed config.json is exactly the mistake being guarded against
        result = package(repo, out, "1.0.0")
        assert result.returncode != 0
        assert "config/config.json" in result.stderr
        assert built(out) == []

    def test_a_developer_folder_in_the_archive_deletes_the_zip_and_fails(self, repo, out):
        attributes = repo / ".gitattributes"
        attributes.write_text(attributes.read_text().replace("tests/ export-ignore\n", ""))
        commit_all(repo)
        result = package(repo, out, "1.0.0")
        assert result.returncode != 0
        assert "tests/" in result.stderr
        assert built(out) == []

    def test_the_packaging_script_shipping_would_be_caught(self, repo, out):
        attributes = repo / ".gitattributes"
        attributes.write_text(re.sub(r"^scripts/package-release\.sh export-ignore\n", "", attributes.read_text(),
                                     flags=re.M))
        commit_all(repo)
        result = package(repo, out, "1.0.0")
        assert result.returncode != 0
        assert "scripts/package-release.sh" in result.stderr
        assert built(out) == []

    def test_a_missing_required_file_deletes_the_zip_and_fails(self, repo, out):
        git_in(repo, "rm", "-q", "server/print_errors.json")
        git_in(repo, "commit", "-q", "-m", "oops")
        result = package(repo, out, "1.0.0")
        assert result.returncode != 0
        assert "server/print_errors.json" in result.stderr and "missing" in result.stderr
        assert built(out) == []

    def test_python_cache_in_the_archive_is_caught(self, repo, out):
        (repo / "server" / "__pycache__").mkdir()
        (repo / "server" / "__pycache__" / "config.cpython-312.pyc").write_bytes(b"x")
        commit_all(repo, force=True)
        result = package(repo, out, "1.0.0")
        assert result.returncode != 0
        assert "__pycache__" in result.stderr
        assert built(out) == []

    def test_a_bad_build_does_not_leave_an_older_good_zip_looking_current(self, repo, out):
        assert package(repo, out, "1.0.0").returncode == 0
        (repo / "config" / "config.json").write_text("{}")
        commit_all(repo, force=True)
        assert package(repo, out, "1.0.0").returncode != 0
        assert built(out) == []

    def test_the_install_guide_pdf_may_be_there_or_not(self, repo, out):
        assert package(repo, out, "1.0.0").returncode == 0
        (repo / "doc" / "install-guide.pdf").write_bytes(b"%PDF-1.4\n")
        commit_all(repo, force=True)  # git-ignored on purpose; the GitHub Action adds it with -f too
        assert package(repo, out, "1.0.1").returncode == 0
        assert "bambu-multicast-1.0.1/doc/install-guide.pdf" in names(out / "bambu-multicast-1.0.1.zip")
