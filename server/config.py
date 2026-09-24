"""Loads and validates config/config.json.

Kept separate from server.py on purpose: this has no dependency on
bambulabs_api or anything printer-specific, so it can be imported and
tested (see /tests/server/) on its own, without needing that (Pi-only)
package installed or a real printer available.
"""

import json
from pathlib import Path

DEFAULT_PORT = 8090
DEFAULT_POLL_INTERVAL_MS = 5000

# This file lives in server/; config/ is a sibling folder one level up, at
# the project root.
PROJECT_ROOT = Path(__file__).parent.parent
CONFIG_PATH = PROJECT_ROOT / "config" / "config.json"


def load_config(config_path=CONFIG_PATH):
    """Read and validate a config JSON file.

    Returns (web_server_port, poll_interval_ms, printers). Missing optional
    settings fall back to DEFAULT_PORT/DEFAULT_POLL_INTERVAL_MS. Raises
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

    return (
        data.get("web_server_port", DEFAULT_PORT),
        data.get("poll_interval_ms", DEFAULT_POLL_INTERVAL_MS),
        data["printers"],
    )
