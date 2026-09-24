import json
import logging
import threading
import time
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from config import PROJECT_ROOT, load_config
from printer_status_map import PRINTER_STATUS_MAP

import bambulabs_api as bl

# client/ is a sibling folder one level up from this script, at the project
# root (config/ is handled by config.py).
CLIENT_ROOT = PROJECT_ROOT / "client"

# POLL_INTERVAL_MS: how often the browser re-checks each printer's status, in
# milliseconds. Sent to the browser via /config.json below (see SETTINGS).
# PRINTERS: "label" and "camera_url" per printer are safe to expose to the
# browser (served via /config.json); "ip", "access_code", and "serial" are
# not, and never leave this script -- they're only used server-side to poll
# the printer's local status feed.
PORT, POLL_INTERVAL_MS, PRINTERS = load_config()

# Settings that apply to the whole site rather than one printer. Everything
# in here is sent to the browser via /config.json.
SETTINGS = {
    "poll_interval_ms": POLL_INTERVAL_MS,
}

status_lock = threading.Lock()
latest_status = {name: {"state": "UNKNOWN"} for name in PRINTERS}

class _IgnoreAmsNoise(logging.Filter):
    def filter(self, record):
        return "something bad happened" not in record.getMessage()

logging.getLogger("bambulabs_api").addFilter(_IgnoreAmsNoise())

def poll_printer(name, cfg):
    printer = None
    while True:
        try:
            if printer is None:
                printer = bl.Printer(cfg["ip"], cfg["access_code"], cfg["serial"])
                printer.connect()

            percent = printer.get_percentage()
            remaining_m = printer.get_time()
            gstate = str(printer.get_state()).split(".")[-1]
            printer_state = str(printer.get_current_state()).split(".")[-1]

            if (gstate not in ("RUNNING", "PAUSE", "PREPARE")
                    or not isinstance(percent, int)
                    or not isinstance(remaining_m, int)):
                info = {"state": "IDLE"}
            else:
                eta = datetime.now(timezone.utc) + timedelta(minutes=remaining_m)
                info = {
                    "state": "RUNNING",
                    "pstate": PRINTER_STATUS_MAP[printer_state],
                    "model": printer.subtask_name() or printer.gcode_file() or "Unknown",
                    "percent": percent,
                    "layer": printer.current_layer_num(),
                    "total_layers": printer.total_layer_num(),
                    "remaining_seconds": remaining_m * 60,
                    "eta_utc": eta.strftime("%Y-%m-%dT%H:%M:%SZ"),
                }
        except Exception as e:
            info = {"state": "ERROR", "error": str(e)}
            printer = None  # force a fresh reconnect attempt next loop

        with status_lock:
            latest_status[name] = info
        time.sleep(5)


# Every file the page actually requests has to be listed here -- unlike
# `python3 -m http.server`, this handler doesn't serve a whole folder
# automatically. Add a line here if another file gets added to the site.
#
# NEVER add "/config.json" (or "config.json"/"config.example.json") here.
# The local config.json file contains printer access codes; the browser
# only ever gets the filtered, safe subset built by hand in the
# "/config.json" branch below. Adding it to this map would serve the raw
# file, access codes included, to anyone who requests it.
STATIC_FILES = {
    "/": ("index.html", "text/html"),
    "/index.html": ("index.html", "text/html"),
    "/app.js": ("app.js", "application/javascript"),
    "/styles.css": ("styles.css", "text/css"),
}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/status.json":
            with status_lock:
                body = json.dumps(latest_status).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/config.json":
            # Only label/camera_url go to the browser -- never ip/access_code/serial.
            body = json.dumps({
                "settings": SETTINGS,
                "printers": {
                    name: {"label": cfg["label"], "camera_url": cfg["camera_url"]}
                    for name, cfg in PRINTERS.items()
                },
            }).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)
        elif self.path in STATIC_FILES:
            filename, content_type = STATIC_FILES[self.path]
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.end_headers()
            self.wfile.write((CLIENT_ROOT / filename).read_bytes())
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass  # keep the systemd journal quiet; remove this to see every request


if __name__ == "__main__":
    for name, cfg in PRINTERS.items():
        threading.Thread(target=poll_printer, args=(name, cfg), daemon=True).start()

    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
