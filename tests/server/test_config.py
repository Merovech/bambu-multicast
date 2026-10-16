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
from config import (  # noqa: E402
    DEFAULT_PORT,
    DEFAULT_POLL_INTERVAL_MS,
    DEFAULT_RECENT_RESULT_WINDOW_MINUTES,
    load_config,
)


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
        port, poll_ms, window_minutes, printers = load_config(path)
        assert port == DEFAULT_PORT
        assert poll_ms == DEFAULT_POLL_INTERVAL_MS
        assert window_minutes == DEFAULT_RECENT_RESULT_WINDOW_MINUTES
        assert printers == SAMPLE_PRINTERS

    def test_config_values_override_defaults(self, tmp_path):
        path = write_config(tmp_path, {
            "web_server_port": 9999,
            "poll_interval_ms": 2500,
            "recent_result_window_minutes": 10,
            "printers": SAMPLE_PRINTERS,
        })
        port, poll_ms, window_minutes, printers = load_config(path)

        assert port == 9999
        assert port != DEFAULT_PORT

        assert poll_ms == 2500
        assert poll_ms != DEFAULT_POLL_INTERVAL_MS

        assert window_minutes == 10
        assert window_minutes != DEFAULT_RECENT_RESULT_WINDOW_MINUTES

        assert printers == SAMPLE_PRINTERS

    def test_only_one_setting_overridden_other_still_defaults(self, tmp_path):
        # web_server_port given, poll_interval_ms omitted -- makes sure the
        # two settings are applied independently, not all-or-nothing.
        path = write_config(tmp_path, {
            "web_server_port": 1234,
            "printers": SAMPLE_PRINTERS,
        })
        port, poll_ms, window_minutes, _printers = load_config(path)
        assert port == 1234
        assert poll_ms == DEFAULT_POLL_INTERVAL_MS
        assert window_minutes == DEFAULT_RECENT_RESULT_WINDOW_MINUTES


class TestRecentResultWindow:
    """recent_result_window_minutes: how long the page keeps showing how the last print ended."""

    def window(self, tmp_path, value):
        path = write_config(tmp_path, {"recent_result_window_minutes": value, "printers": SAMPLE_PRINTERS})
        return load_config(path)[2]

    def test_default_is_thirty_minutes(self):
        assert DEFAULT_RECENT_RESULT_WINDOW_MINUTES == 30

    @pytest.mark.parametrize("value", [1, 30, 90, 1440, 0.5, 2.25])
    def test_any_number_of_minutes_is_accepted_as_given(self, tmp_path, value):
        assert self.window(tmp_path, value) == value

    def test_zero_is_allowed_and_means_off(self, tmp_path):
        assert self.window(tmp_path, 0) == 0

    @pytest.mark.parametrize("value", ["30", "thirty", "", -1, -0.5, True, False, None, [30], {"minutes": 30}])
    def test_anything_else_is_rejected_in_plain_language(self, tmp_path, value):
        with pytest.raises(SystemExit) as exc_info:
            self.window(tmp_path, value)
        message = str(exc_info.value)
        assert "recent_result_window_minutes" in message
        assert "number of minutes" in message
        assert repr(value) in message

    def test_the_error_names_the_file_so_it_can_be_found(self, tmp_path):
        path = write_config(tmp_path, {"recent_result_window_minutes": "x", "printers": SAMPLE_PRINTERS})
        with pytest.raises(SystemExit) as exc_info:
            load_config(path)
        assert str(path) in str(exc_info.value)

    def test_is_independent_of_the_other_settings(self, tmp_path):
        path = write_config(tmp_path, {"recent_result_window_minutes": 5, "printers": SAMPLE_PRINTERS})
        port, poll_ms, window_minutes, _printers = load_config(path)
        assert (port, poll_ms, window_minutes) == (DEFAULT_PORT, DEFAULT_POLL_INTERVAL_MS, 5)

    def test_the_example_config_uses_the_default(self):
        example = Path(__file__).resolve().parent.parent.parent / "config" / "config.example.json"
        data = json.loads(example.read_text(encoding="utf-8"))
        assert data["recent_result_window_minutes"] == DEFAULT_RECENT_RESULT_WINDOW_MINUTES
        assert load_config(example)[2] == DEFAULT_RECENT_RESULT_WINDOW_MINUTES
