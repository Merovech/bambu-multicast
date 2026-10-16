"""Loads and validates config/config.json.

Kept separate from server.py on purpose: this has no dependency on
bambulabs_api or anything printer-specific, so it can be imported and
tested (see /tests/server/) on its own, without needing that (Pi-only)
package installed or a real printer available.
"""

import json
from pathlib import Path

# The default for what port to run this site on
DEFAULT_PORT = 8090
# The default for how often to poll the backend for updates, in milliseconds
DEFAULT_POLL_INTERVAL_MS = 5000
# The default for ow long after a print ends the page keeps saying whether it succeeded or failed.
DEFAULT_RECENT_RESULT_WINDOW_MINUTES = 30

# This file lives in server/; config/ is a sibling folder one level up, at
# the project root.
PROJECT_ROOT = Path(__file__).parent.parent
CONFIG_PATH = PROJECT_ROOT / "config" / "config.json"


def load_config(config_path=CONFIG_PATH):
    """Read and validate a config JSON file.

    Returns (web_server_port, poll_interval_ms, recent_result_window_minutes,
    printers). Missing optional settings fall back to the DEFAULT_* values. Raises
    SystemExit with a plain-language message (not just a bare exception) if
    the file is missing, isn't valid JSON, or lists no printers -- this is
    meant to be read by someone setting up the site, not just logged.
    """
    if not config_path.exists():
        raise SystemExit(
            f"Missing {config_path}.\n"
            "Create it (see config/config.example.json for the expected "
            "format) with your poll interval and printer details, then try "
            "again."
        )
    try:
        with open(config_path, encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise SystemExit(
            f"{config_path} is not valid JSON: {e}\n"
            "Common causes: a trailing comma after the last item in a list "
            "or object, or a missing quote/brace. Fix the file and try again."
        )

    if "printers" not in data or not data["printers"]:
        raise SystemExit(f"{config_path} has no printers listed under \"printers\".")

    window = data.get("recent_result_window_minutes", DEFAULT_RECENT_RESULT_WINDOW_MINUTES)
    # bool is a number to Python (True == 1), but "true" is never what someone meant here.
    if isinstance(window, bool) or not isinstance(window, (int, float)) or window < 0:
        raise SystemExit(
            f"{config_path} has an invalid \"recent_result_window_minutes\": {window!r}.\n"
            "It must be a number of minutes, such as 30 (or 0 to turn the message off), "
            "with no quotes around it."
        )

    return (
        data.get("web_server_port", DEFAULT_PORT),
        data.get("poll_interval_ms", DEFAULT_POLL_INTERVAL_MS),
        window,
        data["printers"],
    )
