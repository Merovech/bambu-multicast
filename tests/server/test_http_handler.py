"""Tests for server.Handler -- what a browser can and can't get from the web server.

Each request goes over a real socket to a real Handler, so routing, headers and status codes are
tested the way a browser (or Cloudflare) would see them.
"""

import json

import pytest

PAGE = b"<html>index page</html>"


class TestStaticFiles:
    @pytest.mark.parametrize("path, body, content_type", [
        ("/", b"<html>index page</html>", "text/html"),
        ("/index.html", b"<html>index page</html>", "text/html"),
        ("/app.js", b"console.log('app');", "application/javascript"),
        ("/styles.css", b"body { color: red; }", "text/css"),
    ])
    def test_serves_each_site_file(self, get, path, body, content_type):
        status, headers, content = get(path)
        assert status == 200
        assert content == body
        assert headers["Content-Type"] == content_type

    def test_edits_to_a_file_show_up_without_restarting(self, get, server):
        # Files are read from disk on every request, so uploading a new app.js needs no restart.
        (server.CLIENT_ROOT / "app.js").write_text("console.log('v2');", encoding="utf-8")
        assert get("/app.js")[2] == b"console.log('v2');"


class TestCaching:
    @pytest.mark.parametrize("path", ["/", "/app.js", "/styles.css", "/status.json", "/config.json"])
    def test_everything_is_revalidated_so_a_redeploy_is_never_hidden(self, get, path):
        # Cloudflare's edge once served a stale app.js for hours; no-cache prevents that.
        assert get(path)[1]["Cache-Control"] == "no-cache"


class TestStatusJson:
    def test_returns_the_latest_status_for_every_printer(self, get, server):
        server.latest_status["p1"] = {"state": "RUNNING", "percent": 12}
        status, headers, body = get("/status.json")
        assert status == 200
        assert headers["Content-Type"] == "application/json"
        data = json.loads(body)
        assert data["p1"] == {"state": "RUNNING", "percent": 12}
        assert data["p2"] == {"state": "UNKNOWN"}

    def test_reflects_new_status_on_the_next_request(self, get, server):
        assert json.loads(get("/status.json")[2])["p1"] == {"state": "UNKNOWN"}
        server.latest_status["p1"] = {"state": "IDLE", "last_result": "failed"}
        assert json.loads(get("/status.json")[2])["p1"] == {"state": "IDLE", "last_result": "failed"}


class TestConfigJson:
    def test_sends_the_settings_and_each_printers_label_and_camera(self, get):
        status, headers, body = get("/config.json")
        assert status == 200
        assert headers["Content-Type"] == "application/json"
        assert json.loads(body) == {
            "settings": {"poll_interval_ms": 7000},
            "printers": {
                "p1": {"label": "Printer One", "camera_url": "https://cam-one.example.test/stream"},
                "p2": {"label": "Printer Two", "camera_url": "https://cam-two.example.test/stream"},
            },
        }

    def test_never_sends_ip_access_code_or_serial(self, get, secrets):
        body = get("/config.json")[2].decode()
        for secret in secrets:
            assert secret not in body

    def test_printers_keep_their_configured_order(self, get):
        assert list(json.loads(get("/config.json")[2])["printers"]) == ["p1", "p2"]


class TestSecretsAreNeverServed:
    @pytest.mark.parametrize("path", [
        "/config/config.json",
        "/config/config.example.json",
        "/../config/config.json",
        "/%2e%2e/config/config.json",
        "/server.py",
        "/server/server.py",
        "/config.py",
        "/print_errors.json",
        "/printer_status_map.py",
        "/index.html/../../config/config.json",
        "/.git/config",
    ])
    def test_files_outside_the_whitelist_are_404(self, get, path):
        assert get(path)[0] == 404

    @pytest.mark.parametrize("path", ["/", "/index.html", "/app.js", "/styles.css", "/status.json",
                                      "/config.json", "/printers/", "/printers/config.json", "/nope"])
    def test_no_response_ever_contains_a_secret(self, get, secrets, path):
        body = get(path)[2].decode(errors="replace")
        for secret in secrets:
            assert secret not in body


class TestPrintersPrefix:
    """Cloudflare forwards /printers/... as-is, so the server has to understand that prefix."""

    def test_bare_printers_redirects_to_the_trailing_slash_form(self, get):
        status, headers, _ = get("/printers")
        assert status == 301
        assert headers["Location"] == "/printers/"

    @pytest.mark.parametrize("path, body", [
        ("/printers/", PAGE),
        ("/printers/index.html", PAGE),
        ("/printers/app.js", b"console.log('app');"),
        ("/printers/styles.css", b"body { color: red; }"),
    ])
    def test_site_files_are_served_under_the_prefix(self, get, path, body):
        status, _, content = get(path)
        assert status == 200
        assert content == body

    def test_json_endpoints_work_under_the_prefix(self, get):
        assert get("/printers/status.json")[0] == 200
        assert "printers" in json.loads(get("/printers/config.json")[2])

    @pytest.mark.parametrize("path", ["/printersFoo", "/printers2/", "/printer/", "/printers/missing.js",
                                      "/printers/printers/"])
    def test_lookalike_and_unknown_paths_are_404(self, get, path):
        assert get(path)[0] == 404

    def test_the_prefix_only_counts_at_the_start(self, get):
        assert get("/x/printers/app.js")[0] == 404

    def test_unprefixed_paths_still_work_for_local_testing(self, get):
        assert get("/")[2] == PAGE


class TestUnknownPaths:
    @pytest.mark.parametrize("path", ["/nope", "/status", "/status.json/extra", "/app.js/", "/APP.JS"])
    def test_return_404(self, get, path):
        assert get(path)[0] == 404


class TestQueryStrings:
    # Shared links often pick up tracking parameters (?utm_source=...); they must not break routing.
    @pytest.mark.parametrize("path", ["/?a=b", "/index.html?v=2", "/printers/?utm_source=chat",
                                      "/printers/app.js?v=2", "/status.json?x=1", "/config.json?x=1",
                                      "/status.json?"])
    def test_query_strings_are_ignored_when_routing(self, get, path):
        assert get(path)[0] == 200

    def test_the_right_content_is_served_for_a_path_with_a_query(self, get):
        assert get("/app.js?v=2")[2] == b"console.log('app');"

    def test_bare_printers_with_a_query_still_redirects(self, get):
        status, headers, _ = get("/printers?utm_source=chat")
        assert status == 301
        assert headers["Location"] == "/printers/"

    def test_a_query_cannot_be_used_to_reach_other_files(self, get):
        assert get("/server.py?/app.js")[0] == 404
        assert get("/config/config.json?x=/app.js")[0] == 404

    def test_unknown_paths_are_still_404_with_a_query(self, get):
        assert get("/nope?x=1")[0] == 404


class TestConnectionQueue:
    def test_the_server_can_hold_a_burst_of_waiting_connections(self, server):
        # Python's default of 5 made a burst of simultaneous visitors stall for a second or more.
        assert server.WebServer.request_queue_size >= 64

    def test_the_server_class_is_what_the_site_actually_runs(self, server):
        # server.py starts WebServer, a threading server: one slow visitor can't block the others.
        import socketserver
        assert issubclass(server.WebServer, socketserver.ThreadingMixIn)
        assert server.WebServer.daemon_threads is True
