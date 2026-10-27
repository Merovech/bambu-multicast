"""Checks for the GitHub Action that runs the whole test suite on every pull request.

Its job is to stop a change with failing tests being merged, so these tests mostly guard against the
workflow quietly being weakened: a skipped suite, a failure that is allowed, a missing check.
"""

import re

import pytest
import yaml

from config import PROJECT_ROOT

WORKFLOW = PROJECT_ROOT / ".github" / "workflows" / "tests.yml"
TEXT = WORKFLOW.read_text(encoding="utf-8")
DATA = yaml.safe_load(TEXT)
JOBS = DATA["jobs"]
AGGREGATE = "tests-passed"


def triggers():
    # YAML 1.1 reads the key `on` as the boolean True.
    return DATA.get("on", DATA.get(True))


def commands(job):
    return [step["run"] for step in JOBS[job]["steps"] if "run" in step]


class TestWhenItRuns:
    def test_runs_on_every_pull_request(self):
        assert "pull_request" in triggers()

    def test_runs_again_on_every_merge_to_main_so_the_badge_describes_main(self):
        push = triggers()["push"]
        assert push["branches"] == ["main"]
        assert "paths" not in push and "paths-ignore" not in push, "a merge must not dodge the tests by its paths"

    def test_runs_on_nothing_else(self):
        assert set(triggers()) == {"pull_request", "push"}

    def test_never_uses_pull_request_target(self):
        # That trigger runs with the base repository's permissions on code from a fork.
        assert "pull_request_target" not in triggers()

    def test_does_not_limit_which_pull_requests_it_checks(self):
        config = triggers()["pull_request"] or {}
        assert "paths" not in config and "paths-ignore" not in config, "a change must not dodge the tests by its paths"
        assert "branches" not in config, "a pull request into any branch is checked"

    def test_a_newer_push_replaces_the_older_run(self):
        assert DATA["concurrency"]["cancel-in-progress"] is True

    def test_one_merge_never_cancels_the_tests_of_another(self):
        # A push has no pull request number; without a per-commit fallback every merge would share one group.
        group = DATA["concurrency"]["group"]
        assert "github.event.pull_request.number" in group
        assert "github.sha" in group


class TestWhatItMayDo:
    def test_can_only_read_the_repository(self):
        assert DATA["permissions"] == {"contents": "read"}

    def test_uses_no_secrets(self):
        assert "secrets." not in TEXT

    def test_every_action_is_pinned_to_a_major_version(self):
        used = [step["uses"] for job in JOBS.values() for step in job["steps"] if "uses" in step]
        assert used
        for action in used:
            assert re.search(r"@v\d+$", action), f"{action} is not pinned to a version"


class TestItRunsEverything:
    def test_runs_the_python_suite_with_pytests_own_defaults(self):
        runs = [c for c in commands("python") if "pytest" in c]
        assert len(runs) == 1
        options = runs[0].split("pytest", 1)[1]  # everything after "python -m pytest"
        # No way to narrow it: no marker, keyword, path, or ignore options.
        assert not re.search(r"(^|\s)(-m|-k|--deselect|--ignore|--maxfail|-x|--co|--collect-only)(\s|=|$)", options)
        assert "tests/" not in options

    def test_installs_the_same_packages_developers_use(self):
        assert any("pip install -r requirements-dev.txt" in c for c in commands("python"))

    def test_runs_the_javascript_suite_after_a_locked_install(self):
        runs = commands("javascript")
        assert "npm ci" in runs
        assert "npm test" in runs
        assert runs.index("npm ci") < runs.index("npm test")

    def test_does_not_run_the_performance_tests(self):
        everything = " ".join(c for job in JOBS for c in commands(job))
        assert "perf" not in everything

    def test_python_versions_are_ones_the_project_supports(self):
        versions = [str(v) for v in JOBS["python"]["strategy"]["matrix"]["python-version"]]
        assert len(versions) >= 2
        for version in versions:
            major, minor = (int(part) for part in version.split("."))
            assert (major, minor) >= (3, 10), f"{version} is older than bambulabs-api supports"

    def test_a_failing_python_version_does_not_hide_the_others(self):
        assert JOBS["python"]["strategy"]["fail-fast"] is False


class TestFailuresAreNeverAllowed:
    def test_no_job_or_step_is_allowed_to_fail(self):
        assert not re.search(r"continue-on-error\s*:\s*(true|\$\{\{)", TEXT)

    def test_no_command_ignores_its_exit_status(self):
        for job in JOBS:
            for command in commands(job):
                assert "|| true" not in command and "|| :" not in command

    def test_no_test_job_is_conditional(self):
        for job in ("python", "javascript"):
            assert "if" not in JOBS[job], f"{job} must always run"
            assert all("if" not in step for step in JOBS[job]["steps"])


class TestTheOneCheckToRequire:
    def test_exists_with_a_stable_name(self):
        assert AGGREGATE in JOBS
        assert JOBS[AGGREGATE]["name"] == "All tests passed"

    def test_waits_for_every_other_job(self):
        others = set(JOBS) - {AGGREGATE}
        assert set(JOBS[AGGREGATE]["needs"]) == others

    def test_runs_even_when_a_job_failed_so_it_cannot_be_skipped_into_green(self):
        # A skipped required check counts as passing; `always()` makes this job run and fail instead.
        assert JOBS[AGGREGATE]["if"] == "always()"

    def test_fails_unless_every_result_is_success(self):
        command = commands(AGGREGATE)[0]
        assert 'needs.*.result' in TEXT
        assert '!= "success"' in command and "exit 1" in command


class TestRepositoryHousekeeping:
    def test_the_workflow_folder_stays_out_of_release_zips(self):
        import subprocess
        out = subprocess.run(["git", "check-attr", "export-ignore", "--", ".github"], cwd=PROJECT_ROOT,
                             capture_output=True, text=True).stdout
        assert out.strip().endswith(": set")

    @pytest.mark.parametrize("path", [".github/workflows/tests.yml"])
    def test_is_not_git_ignored(self, path):
        import subprocess
        ignored = subprocess.run(["git", "check-ignore", "--no-index", "-q", "--", path], cwd=PROJECT_ROOT).returncode == 0
        assert not ignored
