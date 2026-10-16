"""Checks that the server and the real client/ folder agree about which files make up the site."""

import re

import pytest

from config import PROJECT_ROOT

CLIENT_DIR = PROJECT_ROOT / "client"
INDEX_HTML = (CLIENT_DIR / "index.html").read_text(encoding="utf-8")
APP_JS = (CLIENT_DIR / "app.js").read_text(encoding="utf-8")


def local_references(html):
    """Every src/href in the page that points at one of the site's own files."""
    urls = re.findall(r'(?:src|href)="([^"]+)"', html)
    return [u for u in urls if not re.match(r"(https?:)?//", u)]


def test_every_whitelisted_file_exists(server):
    for url, (filename, _content_type) in server.STATIC_FILES.items():
        assert (CLIENT_DIR / filename).is_file(), f"{url} is served but client/{filename} is missing"


def test_every_file_the_page_loads_is_served(server):
    served = set(server.STATIC_FILES)
    for url in local_references(INDEX_HTML):
        assert "/" + url in served, f"index.html loads {url} but server.py would 404 it"


def test_every_json_file_app_js_fetches_is_a_route(get):
    for url in re.findall(r'fetch\("([^"]+)"', APP_JS):
        assert get("/" + url)[0] == 200, f"app.js fetches {url} but the server doesn't answer it"
        assert get("/printers/" + url)[0] == 200


def test_the_real_site_files_are_served_unchanged(server, get, monkeypatch):
    monkeypatch.setattr(server, "CLIENT_ROOT", CLIENT_DIR)
    for url, (filename, content_type) in server.STATIC_FILES.items():
        status, headers, body = get(url)
        assert status == 200
        assert headers["Content-Type"] == content_type
        assert body == (CLIENT_DIR / filename).read_bytes()


def test_the_whitelist_never_includes_a_config_file(server):
    for url, (filename, _content_type) in server.STATIC_FILES.items():
        assert "config" not in url.lower().replace("/printers", ""), url
        assert "config" not in filename.lower(), filename


@pytest.mark.parametrize("name", ["config.json", "config.example.json"])
def test_config_files_stay_out_of_the_client_folder(name):
    # Anything in client/ is a candidate for being served; config belongs in config/.
    assert not (CLIENT_DIR / name).exists()
