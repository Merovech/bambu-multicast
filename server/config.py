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

# Which network address the site listens on.  "0.0.0.0" means every network interface, so anyone on
# the local network can reach it directly.  If a tunnel such as cloudflared runs on the same machine,
# "127.0.0.1" is safer: only that machine can connect.
DEFAULT_BIND_ADDRESS = "0.0.0.0"

# Every printer needs all of these, and each must be a non-empty string.
REQUIRED_PRINTER_FIELDS = ("label", "camera_url", "ip", "access_code", "serial")

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

    if not isinstance(data, dict) or "printers" not in data or not data["printers"]:
        raise SystemExit(f"{config_path} has no printers listed under \"printers\".")

    _validate_printers(config_path, data["printers"])

    port = data.get("web_server_port", DEFAULT_PORT)
    if isinstance(port, bool) or not isinstance(port, int) or not 1 <= port <= 65535:
        raise SystemExit(
            f"{config_path} has an invalid \"web_server_port\": {port!r}.\n"
            "It must be a whole number from 1 to 65535, such as 8090, with no quotes around it."
        )

    poll_ms = data.get("poll_interval_ms", DEFAULT_POLL_INTERVAL_MS)
    if isinstance(poll_ms, bool) or not isinstance(poll_ms, (int, float)) or poll_ms <= 0:
        raise SystemExit(
            f"{config_path} has an invalid \"poll_interval_ms\": {poll_ms!r}.\n"
            "It must be a number of milliseconds greater than 0, such as 5000, with no quotes around it."
        )

    window = data.get("recent_result_window_minutes", DEFAULT_RECENT_RESULT_WINDOW_MINUTES)
    # bool is a number to Python (True == 1), but "true" is never what someone meant here.
    if isinstance(window, bool) or not isinstance(window, (int, float)) or window < 0:
        raise SystemExit(
            f"{config_path} has an invalid \"recent_result_window_minutes\": {window!r}.\n"
            "It must be a number of minutes, such as 30 (or 0 to turn the message off), "
            "with no quotes around it."
        )

    return (port, poll_ms, window, data["printers"])


def _validate_printers(config_path, printers):
    if not isinstance(printers, dict):
        raise SystemExit(
            f"{config_path} has an invalid \"printers\" section: it must be a list of named printers "
            "between { and }, as in config/config.example.json."
        )
    for name, cfg in printers.items():
        if not isinstance(cfg, dict):
            raise SystemExit(f"{config_path}: printer \"{name}\" must be an object between {{ and }}.")
        for field in REQUIRED_PRINTER_FIELDS:
            value = cfg.get(field)
            if not isinstance(value, str) or not value.strip():
                raise SystemExit(
                    f"{config_path}: printer \"{name}\" is missing \"{field}\", "
                    "or it is not text in quotes."
                )
        # Only web addresses (or a path on this site) can be shown as a camera image; this also
        # rules out things like javascript: and data: addresses.
        if not cfg["camera_url"].startswith(("http://", "https://", "/")):
            raise SystemExit(
                f"{config_path}: printer \"{name}\" has a \"camera_url\" that doesn't start with "
                "http:// or https://."
            )


def load_bind_address(config_path=CONFIG_PATH):
    """The network address to listen on: "bind_address" from config.json, else DEFAULT_BIND_ADDRESS.

    Call after load_config(), which has already checked that the file exists and is valid JSON.
    """
    with open(config_path, encoding="utf-8") as f:
        address = json.load(f).get("bind_address", DEFAULT_BIND_ADDRESS)
    if not isinstance(address, str) or not address.strip():
        raise SystemExit(
            f"{config_path} has an invalid \"bind_address\": {address!r}.\n"
            "It must be text in quotes, such as \"127.0.0.1\" or \"0.0.0.0\"."
        )
    return address
