"""Shared test setup for server/.

server.py can't simply be imported by a test: it needs the (Pi-only) bambulabs_api package, and it
reads config/config.json at import time and exits if that file is missing.  The `server` fixture
below gets around both, so the tests run on any machine with nothing but pytest installed.
"""

import http.client
import importlib
import json
import sys
import threading
import types
from pathlib import Path

import pytest

SERVER_DIR = Path(__file__).resolve().parent.parent.parent / "server"
sys.path.insert(0, str(SERVER_DIR))

# The values here are deliberately recognizable, so a test can check that none of the secret ones
# ever show up in something sent to a browser.
SECRETS = ["10.99.99.1", "ACCESS-CODE-1", "SERIAL-1", "10.99.99.2", "ACCESS-CODE-2", "SERIAL-2"]
TEST_PRINTERS = {
    "p1": {"label": "Printer One", "ip": "10.99.99.1", "access_code": "ACCESS-CODE-1",
           "serial": "SERIAL-1", "camera_url": "https://cam-one.example.test/stream"},
    "p2": {"label": "Printer Two", "ip": "10.99.99.2", "access_code": "ACCESS-CODE-2",
           "serial": "SERIAL-2", "camera_url": "https://cam-two.example.test/stream"},
}


class FakePrinter:
    """Stands in for bambulabs_api.Printer.  Set the attributes to script what it reports."""

    def __init__(self, gstate="IDLE", stage="PRINTING", percent=0, remaining_minutes=0,
                 print_error=0, subtask="", gcode_file="", layer=0, total_layers=0):
        self.gstate = gstate
        self.stage = stage
        self.percent = percent
        self.remaining_minutes = remaining_minutes
        self.print_error = print_error
        self.subtask = subtask
        self.gcode = gcode_file
        self.layer = layer
        self.total_layers = total_layers

    def get_percentage(self):
        return self.percent

    def get_time(self):
        return self.remaining_minutes

    def get_state(self):
        return self.gstate

    def get_current_state(self):
        return self.stage

    def print_error_code(self):
        return self.print_error

    def subtask_name(self):
        return self.subtask

    def gcode_file(self):
        return self.gcode

    def current_layer_num(self):
        return self.layer

    def total_layer_num(self):
        return self.total_layers


@pytest.fixture
def printer_class():
    return FakePrinter


@pytest.fixture
def secrets():
    return SECRETS


@pytest.fixture
def server(monkeypatch, tmp_path):
    """A freshly imported server.py with a fake bambulabs_api, fake config, and a temp client/ dir."""
    fake_api = types.ModuleType("bambulabs_api")
    fake_api.Printer = FakePrinter
    monkeypatch.setitem(sys.modules, "bambulabs_api", fake_api)

    import config
    printers = json.loads(json.dumps(TEST_PRINTERS))
    monkeypatch.setattr(config, "load_config", lambda: (0, 7000, 45, printers))
    # server.py also reads bind_address from config.json when it is imported.  A fresh checkout (such as the one
    # GitHub tests) has no config.json, so that read has to be replaced too.
    monkeypatch.setattr(config, "load_bind_address", lambda: "127.0.0.1")

    sys.modules.pop("server", None)
    module = importlib.import_module("server")

    client_dir = tmp_path / "client"
    client_dir.mkdir()
    (client_dir / "index.html").write_text("<html>index page</html>", encoding="utf-8")
    (client_dir / "app.js").write_text("console.log('app');", encoding="utf-8")
    (client_dir / "styles.css").write_text("body { color: red; }", encoding="utf-8")
    monkeypatch.setattr(module, "CLIENT_ROOT", client_dir)

    yield module
    sys.modules.pop("server", None)


@pytest.fixture
def http_port(server):
    """The port of a real server.Handler running on a throwaway local port."""
    httpd = server.WebServer(("127.0.0.1", 0), server.Handler)
    threading.Thread(target=httpd.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True).start()
    yield httpd.server_address[1]
    httpd.shutdown()
    httpd.server_close()


@pytest.fixture
def get(http_port):
    """get(path) -> (status, headers, body) from the test server.

    Uses http.client rather than urllib so redirects are reported, not followed.
    """
    def request(path):
        conn = http.client.HTTPConnection("127.0.0.1", http_port, timeout=5)
        try:
            conn.request("GET", path)
            response = conn.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            conn.close()

    return request


# Lines that performance tests want shown after the run, whether or not they pass.
PERF_LINES = []

# The micro-benchmarks need the pytest-benchmark plugin, which is only needed for performance
# testing.  Without it, pytest would report an error ("fixture 'benchmark' not found"); this stand-in
# turns that into a skip that says what to do.  When the plugin is installed it provides the real one.
try:
    import pytest_benchmark  # noqa: F401
except ImportError:
    @pytest.fixture
    def benchmark():
        pytest.skip("pytest-benchmark isn't installed; run: pip install -r requirements-dev.txt")


@pytest.fixture
def report():
    """report("text") adds a line to the "performance results" section printed at the end."""
    return PERF_LINES.append


def pytest_terminal_summary(terminalreporter):
    if PERF_LINES:
        terminalreporter.section("performance results")
        for line in PERF_LINES:
            terminalreporter.write_line(line)
