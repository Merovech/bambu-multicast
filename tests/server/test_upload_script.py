"""Checks for scripts/upload.sh: that its file list matches what the server needs on the Pi, and that the
user@server it uploads to comes from the command line (so a fork uses its own, and no personal host is
written in the script)."""

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from config import PROJECT_ROOT

UPLOAD_SH = PROJECT_ROOT / "scripts" / "upload.sh"


def uploaded_files():
    text = UPLOAD_SH.read_text(encoding="utf-8")
    block = re.search(r"FILES=\((.*?)\n\)", text, re.S).group(1)
    return [line.split("#")[0].strip() for line in block.splitlines() if line.split("#")[0].strip()]


class TestTheFileList:
    def test_the_list_is_not_empty_and_has_no_duplicates(self):
        files = uploaded_files()
        assert files
        assert len(files) == len(set(files))

    def test_every_server_python_and_data_file_is_uploaded(self):
        needed = {f"server/{p.name}" for p in (PROJECT_ROOT / "server").iterdir()
                  if p.is_file() and p.suffix in (".py", ".json")}
        assert needed <= set(uploaded_files()), needed - set(uploaded_files())

    def test_every_file_the_website_serves_is_uploaded(self, server):
        served = {f"client/{filename}" for filename, _ in server.STATIC_FILES.values()}
        assert served <= set(uploaded_files()), served - set(uploaded_files())

    def test_the_live_config_and_the_venv_setup_script_are_uploaded(self):
        assert "config/config.json" in uploaded_files()
        assert "scripts/setup.sh" in uploaded_files()

    def test_only_runtime_files_are_uploaded(self, server):
        allowed_client = {f"client/{filename}" for filename, _ in server.STATIC_FILES.values()}
        for path in uploaded_files():
            if path.startswith("client/"):
                assert path in allowed_client, f"{path} is not served by the site"
            elif path.startswith("server/"):
                assert path.endswith((".py", ".json"))
            else:
                assert path in {"config/config.json", "scripts/setup.sh"}, f"{path} is not needed on the Pi"

    @pytest.mark.parametrize("unwanted", ["tests", "doc", "node_modules", "venv", "__pycache__", ".pyc",
                                          "package.json", "package-lock.json", "config.example.json",
                                          "requirements", "setup-dev.sh", "upload.sh", "package-release.sh",
                                          ".git"])
    def test_nothing_that_is_only_for_development_is_uploaded(self, unwanted):
        assert not [f for f in uploaded_files() if unwanted in f]

    def test_every_listed_file_exists_except_the_private_config(self):
        for path in uploaded_files():
            if path != "config/config.json":
                assert (PROJECT_ROOT / path).is_file(), path


def find_bash():
    if sys.platform == "win32":
        # A bare "bash" on Windows can be WSL's, which cannot run C:/ paths.  Git for Windows brings its own.
        git_exe = shutil.which("git")
        if git_exe:
            for parent in Path(git_exe).resolve().parents[:3]:
                candidate = parent / "bin" / "bash.exe"
                if candidate.is_file():
                    return str(candidate)
    return shutil.which("bash")


BASH = find_bash()
CLEAN_ENV = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}


@pytest.fixture
def project_copy(tmp_path):
    """A stand-in project folder holding the real upload script and a placeholder for each file it uploads."""
    if BASH is None:
        pytest.skip("bash isn't installed")
    root = tmp_path / "project"
    (root / "scripts").mkdir(parents=True)
    shutil.copy2(UPLOAD_SH, root / "scripts" / "upload.sh")
    for name in uploaded_files():
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("placeholder\n", encoding="utf-8")
    return root


class FakeSsh:
    """Stands in for ssh: records the host it was given, swallows the upload and answers the way a Pi would.

    SAFETY: every host these tests use ends in .invalid, a name reserved so that it can never resolve. Even if the
    stand-in were somehow not used, nothing could be uploaded to a real machine.
    """

    def __init__(self, tmp_path):
        if " " in str(tmp_path):
            pytest.skip("the stand-in ssh can't be used from a folder whose path contains a space")
        self.bin = tmp_path / "fake-bin"
        self.bin.mkdir()
        self.record = tmp_path / "ssh-host.txt"
        self.reply = tmp_path / "ssh-reply.txt"
        self.answer_with(uploaded_files())
        shim = self.bin / "ssh"
        shim.write_text('#!/usr/bin/env bash\nprintf "%s\\n" "$1" > "$SSH_RECORD"\ncat > /dev/null\ncat "$SSH_REPLY"\n',
                        encoding="utf-8", newline="\n")
        shim.chmod(0o755)

    def answer_with(self, files):
        lines = ["DEST /home/test/printer-page"] + [f"./{name}" for name in files]
        self.reply.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")

    def env(self):
        env = dict(CLEAN_ENV)
        env["UPLOAD_SSH"] = (self.bin / "ssh").as_posix()
        env["SSH_RECORD"] = self.record.as_posix()
        env["SSH_REPLY"] = self.reply.as_posix()
        return env

    def host_used(self):
        return self.record.read_text(encoding="utf-8").strip() if self.record.exists() else None


@pytest.fixture
def ssh(tmp_path):
    return FakeSsh(tmp_path)


def run_upload(project, ssh, *args, cwd=None):
    return subprocess.run([BASH, (project / "scripts" / "upload.sh").as_posix(), *args],
                          cwd=cwd or project, env=ssh.env(), capture_output=True, text=True)


class TestTheHostComesFromTheCommandLine:
    def test_no_personal_host_is_written_in_the_script(self):
        text = UPLOAD_SH.read_text(encoding="utf-8")
        assert "dionysus" not in text
        assert not re.search(r"\bari@", text)

    def test_the_script_is_committed_so_forks_get_it(self):
        ignored = subprocess.run(["git", "check-ignore", "--no-index", "-q", "--", "scripts/upload.sh"],
                                 cwd=PROJECT_ROOT).returncode == 0
        assert not ignored

    @pytest.mark.parametrize("host", ["tester@upload-test.invalid", "pi@raspberrypi.invalid", "me@192.0.2.60",
                                      "my_user@my-server.example.invalid", "upload-test.invalid"])
    def test_a_valid_host_is_passed_to_ssh_exactly_as_given(self, project_copy, ssh, host):
        result = run_upload(project_copy, ssh, host)
        assert result.returncode == 0, result.stderr
        assert ssh.host_used() == host
        assert f"uploaded to {host}:" in result.stdout

    def test_it_works_from_any_folder(self, project_copy, ssh, tmp_path):
        elsewhere = tmp_path / "elsewhere"
        elsewhere.mkdir()
        result = run_upload(project_copy, ssh, "tester@upload-test.invalid", cwd=elsewhere)
        assert result.returncode == 0, result.stderr
        assert ssh.host_used() == "tester@upload-test.invalid"

    def test_without_a_host_it_stops_and_shows_an_example(self, project_copy, ssh):
        result = run_upload(project_copy, ssh)
        assert result.returncode != 0
        assert "user@server" in result.stderr
        assert "bash scripts/upload.sh" in result.stderr
        assert ssh.host_used() is None

    @pytest.mark.parametrize("host", ["-oProxyCommand=evil", "tester@", "@upload-test.invalid", "tester@upload test.invalid",
                                      "tester;rm", "$(whoami)@upload-test.invalid", "tester@upload-test.invalid/x",
                                      "a@b@c.invalid", "tester@-bad.invalid"])
    def test_a_host_that_could_be_read_as_anything_but_a_place_to_connect_is_refused(self, project_copy, ssh, host):
        result = run_upload(project_copy, ssh, host)
        assert result.returncode != 0
        assert ssh.host_used() is None

    def test_two_hosts_are_refused(self, project_copy, ssh):
        result = run_upload(project_copy, ssh, "a@one", "b@two")
        assert result.returncode != 0
        assert "only one" in result.stderr
        assert ssh.host_used() is None

    def test_list_needs_no_host_and_sends_nothing(self, project_copy, ssh):
        result = run_upload(project_copy, ssh, "--list")
        assert result.returncode == 0
        assert result.stdout.split() == uploaded_files()
        assert ssh.host_used() is None

    def test_list_with_a_host_still_sends_nothing(self, project_copy, ssh):
        result = run_upload(project_copy, ssh, "--list", "tester@upload-test.invalid")
        assert result.returncode == 0
        assert ssh.host_used() is None

    def test_help_explains_the_parameter(self, project_copy, ssh):
        result = run_upload(project_copy, ssh, "--help")
        assert result.returncode == 0
        assert "user@server" in result.stdout
        assert ssh.host_used() is None

    def test_an_unknown_option_is_refused(self, project_copy, ssh):
        result = run_upload(project_copy, ssh, "--force", "tester@upload-test.invalid")
        assert result.returncode != 0
        assert "Unknown option" in result.stderr


class TestTheUploadItself:
    def test_it_reports_every_file_and_where_they_arrived(self, project_copy, ssh):
        result = run_upload(project_copy, ssh, "tester@upload-test.invalid")
        assert result.returncode == 0, result.stderr
        for name in uploaded_files():
            assert name in result.stdout
        assert "/home/test/printer-page" in result.stdout

    def test_a_file_the_pi_does_not_report_is_a_failure(self, project_copy, ssh):
        ssh.answer_with([f for f in uploaded_files() if f != "client/app.js"])
        result = run_upload(project_copy, ssh, "tester@upload-test.invalid")
        assert result.returncode != 0
        assert "client/app.js" in result.stderr

    def test_a_missing_local_file_is_refused_before_anything_is_sent(self, project_copy, ssh):
        (project_copy / "client" / "tailwind.css").unlink()
        result = run_upload(project_copy, ssh, "tester@upload-test.invalid")
        assert result.returncode != 0
        assert "npm run build:css" in result.stderr
        assert ssh.host_used() is None
