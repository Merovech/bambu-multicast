"""Keeps upload.sh's file list in step with what the server actually needs on the Pi.

upload.sh is a personal script (it names your own Pi and is ignored by git), so these tests only run
where it exists.
"""

import re

import pytest

from config import PROJECT_ROOT

UPLOAD_SH = PROJECT_ROOT / "upload.sh"

pytestmark = pytest.mark.skipif(not UPLOAD_SH.exists(), reason="upload.sh is a personal script and isn't in this checkout")


def uploaded_files():
    text = UPLOAD_SH.read_text(encoding="utf-8")
    block = re.search(r"FILES=\((.*?)\n\)", text, re.S).group(1)
    return [line.split("#")[0].strip() for line in block.splitlines() if line.split("#")[0].strip()]


def test_the_list_is_not_empty_and_has_no_duplicates():
    files = uploaded_files()
    assert files
    assert len(files) == len(set(files))


def test_every_server_python_and_data_file_is_uploaded():
    needed = {f"server/{p.name}" for p in (PROJECT_ROOT / "server").iterdir()
              if p.is_file() and p.suffix in (".py", ".json")}
    assert needed <= set(uploaded_files()), needed - set(uploaded_files())


def test_every_file_the_website_serves_is_uploaded(server):
    served = {f"client/{filename}" for filename, _ in server.STATIC_FILES.values()}
    assert served <= set(uploaded_files()), served - set(uploaded_files())


def test_the_live_config_and_the_venv_setup_script_are_uploaded():
    assert "config/config.json" in uploaded_files()
    assert "setup.sh" in uploaded_files()


def test_only_runtime_files_are_uploaded(server):
    allowed_client = {f"client/{filename}" for filename, _ in server.STATIC_FILES.values()}
    for path in uploaded_files():
        if path.startswith("client/"):
            assert path in allowed_client, f"{path} is not served by the site"
        elif path.startswith("server/"):
            assert path.endswith((".py", ".json"))
        else:
            assert path in {"config/config.json", "setup.sh"}, f"{path} is not needed on the Pi"


@pytest.mark.parametrize("unwanted", ["tests", "doc", "node_modules", "venv", "__pycache__", ".pyc",
                                      "package.json", "package-lock.json", "config.example.json",
                                      "requirements", "setup-dev.sh", ".git"])
def test_nothing_that_is_only_for_development_is_uploaded(unwanted):
    assert not [f for f in uploaded_files() if unwanted in f]


def test_every_listed_file_exists_except_the_private_config():
    for path in uploaded_files():
        if path != "config/config.json":
            assert (PROJECT_ROOT / path).is_file(), path
