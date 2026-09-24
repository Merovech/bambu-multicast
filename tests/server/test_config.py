"""Tests for server/config.py -- missing config, invalid config, and that
values from config.json correctly override the built-in defaults.

Run with (from the project root):
    pytest

Requires pytest (``pip install pytest``) -- a dev-only dependency: nobody
running the packaged site ever needs it, only someone working on this code.
"""

import json
import sys
from pathlib import Path

import pytest

# config.py lives in server/, a sibling of tests/ at the project root. This
# project has no package/build setup, so we add server/ to sys.path the same
# simple way server.py itself finds printer_status_map.py.
SERVER_DIR = Path(__file__).resolve().parent.parent.parent / "server"
sys.path.insert(0, str(SERVER_DIR))

# Need the server path before we can import from config.  This technically
# violates the E402 guideline ("Module level import not at top of file"), but 
# that's fine for the test.
from config import DEFAULT_PORT, DEFAULT_POLL_INTERVAL_MS, load_config  # noqa: E402


# A minimal but complete printer entry, reused across tests so each test
# only has to vary the thing it's actually testing.
SAMPLE_PRINTERS = {
    "a1": {
        "label": "Test A1",
        "camera_url": "http://example.invalid/stream",
        "ip": "127.0.0.1",
        "access_code": "00000000",
        "serial": "TESTSERIAL0001",
    }
}


def write_config(tmp_path, data):
    """Write a dict as config.json in tmp_path and return its path."""
    path = tmp_path / "config.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def write_raw_config(tmp_path, text):
    """Write literal text as config.json in tmp_path and return its path."""
    path = tmp_path / "config.json"
    path.write_text(text, encoding="utf-8")
    return path


class TestMissingConfig:
    """The config file itself, or required settings inside it, are missing."""

    def test_missing_file_raises_system_exit(self, tmp_path):
        missing_path = tmp_path / "config.json"  # never created
        with pytest.raises(SystemExit) as exc_info:
            load_config(missing_path)
        # Plain substring check, not pytest.raises(match=...): the path
        # contains backslashes on Windows, which `match` would treat as
        # regex escapes rather than literal characters.
        assert str(missing_path) in str(exc_info.value)

    def test_missing_printers_key_raises_system_exit(self, tmp_path):
        path = write_config(tmp_path, {"poll_interval_ms": 5000})
        with pytest.raises(SystemExit) as exc_info:
            load_config(path)
        assert "no printers listed" in str(exc_info.value)

    def test_empty_printers_raises_system_exit(self, tmp_path):
        path = write_config(tmp_path, {"poll_interval_ms": 5000, "printers": {}})
        with pytest.raises(SystemExit) as exc_info:
            load_config(path)
        assert "no printers listed" in str(exc_info.value)


class TestInvalidConfig:
    """The config file exists but its contents are broken in some way."""

    def test_malformed_json_raises_system_exit(self, tmp_path):
        # Trailing comma after the last item -- the exact mistake a
        # non-programmer hand-editing JSON is most likely to make.
        path = write_raw_config(tmp_path, '{"poll_interval_ms": 5000, "printers": {},}')
        with pytest.raises(SystemExit) as exc_info:
            load_config(path)
        assert "not valid JSON" in str(exc_info.value)

    def test_top_level_json_array_raises_system_exit(self, tmp_path):
        # Valid JSON, but not the object shape load_config() expects.
        path = write_raw_config(tmp_path, "[1, 2, 3]")
        with pytest.raises(SystemExit) as exc_info:
            load_config(path)
        assert "no printers listed" in str(exc_info.value)


class TestDefaultsOverride:
    """Settings present in config.json take priority over the built-in
    defaults; settings absent from config.json fall back to those defaults."""

    def test_missing_optional_settings_fall_back_to_defaults(self, tmp_path):
        path = write_config(tmp_path, {"printers": SAMPLE_PRINTERS})
        port, poll_ms, printers = load_config(path)
        assert port == DEFAULT_PORT
        assert poll_ms == DEFAULT_POLL_INTERVAL_MS
        assert printers == SAMPLE_PRINTERS

    def test_config_values_override_defaults(self, tmp_path):
        path = write_config(tmp_path, {
            "web_server_port": 9999,
            "poll_interval_ms": 2500,
            "printers": SAMPLE_PRINTERS,
        })
        port, poll_ms, printers = load_config(path)

        assert port == 9999
        assert port != DEFAULT_PORT

        assert poll_ms == 2500
        assert poll_ms != DEFAULT_POLL_INTERVAL_MS

        assert printers == SAMPLE_PRINTERS

    def test_only_one_setting_overridden_other_still_defaults(self, tmp_path):
        # web_server_port given, poll_interval_ms omitted -- makes sure the
        # two settings are applied independently, not all-or-nothing.
        path = write_config(tmp_path, {
            "web_server_port": 1234,
            "printers": SAMPLE_PRINTERS,
        })
        port, poll_ms, _printers = load_config(path)
        assert port == 1234
        assert poll_ms == DEFAULT_POLL_INTERVAL_MS
