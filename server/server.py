import json
import logging
import threading
import time
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from config import PROJECT_ROOT, load_bind_address, load_config
from print_errors import describe_print_error
from print_result import PrintResultTracker
from printer_status_map import PRINTER_STATUS_MAP

import bambulabs_api as bl

# client/ is a sibling folder one level up from this script, at the project
# root (config/ is handled by config.py).
CLIENT_ROOT = PROJECT_ROOT / "client"

# POLL_INTERVAL_MS: how often the browser re-checks each printer's status, in# milliseconds.
# Sent to the browser via /config.json below (see SETTINGS).
#
# PRINTERS: "label" and "camera_url" per printer are safe to expose to the browser (served 
# via /config.json); "ip", "access_code", and "serial" are not, and never leave this script -- 
# they're only used server-side to poll the printer's local status feed.
PORT, POLL_INTERVAL_MS, RECENT_RESULT_WINDOW_MINUTES, PRINTERS = load_config()
BIND_ADDRESS = load_bind_address()

# Settings that apply to the whole site rather than one printer. Everything
# in here is sent to the browser via /config.json.
SETTINGS = {
    "poll_interval_ms": POLL_INTERVAL_MS,
}

status_lock = threading.Lock()
latest_status = {name: {"state": "UNKNOWN"} for name in PRINTERS}
last_error = {}  # per printer, so a changed error code is logged once rather than every poll
last_poll_failure = {}  # per printer, so a repeating connection failure is logged once, not every poll

# What the browser is told when a printer can't be polled.  The real exception text can contain the
# printer's LAN IP address and other internals, so it goes to the log, never to the browser.
POLL_FAILURE_MESSAGE = "Unable to reach printer"

class _IgnoreAmsNoise(logging.Filter):
    def filter(self, record):
        return "something bad happened" not in record.getMessage()

logging.getLogger("bambulabs_api").addFilter(_IgnoreAmsNoise())

def build_status(printer, name, result_tracker):
    """Reads one snapshot from a connected printer and returns the dict sent to the browser."""
    percent = printer.get_percentage()
    remaining_m = printer.get_time()
    gstate = str(printer.get_state()).split(".")[-1]
    printer_state = str(printer.get_current_state()).split(".")[-1]
    print_error = printer.print_error_code()

    if print_error != last_error.get(name, 0):
        logging.warning("%s: print_error=%08X gcode_state=%s stage=%s",
                        name, print_error, gstate, printer_state)
    last_error[name] = print_error

    active = (gstate in ("RUNNING", "PAUSE", "PREPARE")
              and isinstance(percent, int)
              and isinstance(remaining_m, int))
    last_result = result_tracker.update(active, gstate)

    if not active:
        info = {"state": "IDLE"}
        if last_result:
            info["last_result"] = last_result
        return info

    # The printer reports two separate things: a coarse job state (gcode_state:
    # RUNNING/PAUSE/...) and a fine-grained stage (stg_cur, which is what
    # PRINTER_STATUS_MAP translates).  An error such as a jammed extruder pauses the
    # job but doesn't necessarily change the stage, which can stay "Printing".  So
    # the job state wins for the display, and print_error carries the actual error.
    pstate = PRINTER_STATUS_MAP[printer_state]
    if gstate == "PAUSE" and "Paused" not in pstate:
        pstate = "Paused"

    eta = datetime.now(timezone.utc) + timedelta(minutes=remaining_m)
    info = {
        "state": "RUNNING",
        "pstate": pstate,
        "model": printer.subtask_name() or printer.gcode_file() or "Unknown",
        "percent": percent,
        "layer": printer.current_layer_num(),
        "total_layers": printer.total_layer_num(),
        "remaining_seconds": remaining_m * 60,
        "eta_utc": eta.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    if print_error:
        info["error"] = describe_print_error(print_error)
    return info


def poll_printer(name, cfg):
    printer = None
    result_tracker = PrintResultTracker(RECENT_RESULT_WINDOW_MINUTES)
    while True:
        try:
            if printer is None:
                printer = bl.Printer(cfg["ip"], cfg["access_code"], cfg["serial"])
                printer.connect()
            info = build_status(printer, name, result_tracker)
            last_poll_failure.pop(name, None)
        except Exception as e:
            if last_poll_failure.get(name) != str(e):
                logging.warning("%s: polling failed: %s: %s", name, type(e).__name__, e)
            last_poll_failure[name] = str(e)
            info = {"state": "ERROR", "error": POLL_FAILURE_MESSAGE}
            printer = None  # force a fresh reconnect attempt next loop

        with status_lock:
            latest_status[name] = info
        time.sleep(5)


# Every file the page actually requests has to be listed here -- unlike `python3 -m http.server`,
# this handler doesn't serve a whole folder automatically. Add a line here if another file gets
# added to the site.
#
# NEVER add "/config.json" (or "config.json"/"config.example.json") here. The local config.json
# file contains printer access codes; the browser only ever gets the filtered, safe subset built
# by hand in the "/config.json" branch below. Adding it to this map would serve the raw file, 
# access codes included, to anyone who requests it.
#
# Is this the best way to handle this?  Probably not.  But it's dead simple, and good enough.
STATIC_FILES = {
    "/": ("index.html", "text/html"),
    "/index.html": ("index.html", "text/html"),
    "/app.js": ("app.js", "application/javascript"),
    "/styles.css": ("styles.css", "text/css"),
    "/tailwind.css": ("tailwind.css", "text/css"),
}


class WebServer(ThreadingHTTPServer):
    # How many incoming connections the operating system holds while the server catches up.
    # Python's default is 5, which is too few: when a handful of visitors connect at the same moment
    # (a few people opening the page, each page load making several requests), the extras are turned
    # away and have to retry, and each retry costs a second or more.  128 absorbs a burst like that;
    # a connection that is merely queued costs next to nothing.
    request_queue_size = 128


# Sent with every response.  The page only loads its own script and styles, talks only to this
# server, and shows camera images from any http(s) address (the camera streams live on other ports).
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "Content-Security-Policy": (
        "default-src 'self'; img-src 'self' http: https:; "
        "frame-ancestors 'none'; base-uri 'none'; form-action 'none'"
    ),
}


class Handler(BaseHTTPRequestHandler):
    # Don't announce "BaseHTTP/0.6 Python/3.x" on every response and error page.
    server_version = "printer-site"
    sys_version = ""

    def _send_headers(self, content_type):
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        # Everything this server sends is either live status data or a small script/page that can
        # change on any redeploy -- never something that should be cached and silently served stale.
        # Without this, some providers and browsers cache static extensions like .js/.css by default,
        # and a real code change can sit invisibly stale for hours with no error anywhere to explain
        # why. `no-cache` still allows caching, but forces a revalidation with the origin before ever
        # reusing a cached copy.
        self.send_header("Cache-Control", "no-cache")
        for name, value in SECURITY_HEADERS.items():
            self.send_header(name, value)
        self.end_headers()

    def do_GET(self):
        # Routing ignores any query string, so a shared link like /printers/?utm_source=chat works.
        path = self.path.split("?", 1)[0]
        if path == "/printers":
            # Redirect to the trailing-slash form instead of serving content here directly,
            # to avoid breaking relative URLs.
            self.send_response(301)
            self.send_header("Location", "/printers/")
            self.end_headers()
            return
        if path.startswith("/printers/"):
            path = path[len("/printers"):] or "/"

        if path == "/status.json":
            with status_lock:
                body = json.dumps(latest_status).encode()
            self._send_headers("application/json")
            self.wfile.write(body)
        elif path == "/config.json":
            # Only label/camera_url go to the browser -- never ip/access_code/serial.  That is information
            # others can use to access the printer's API directly, which can control the printer.  That would
            # be bad.
            #
            # The camera URL doesn't contain the ip/access_code/serial.  It was put behind a URL to the server
            # when setting up the cameras via go2rtc and Bambu Connect.
            body = json.dumps({
                "settings": SETTINGS,
                "printers": {
                    name: {"label": cfg["label"], "camera_url": cfg["camera_url"]}
                    for name, cfg in PRINTERS.items()
                },
            }).encode()
            self._send_headers("application/json")
            self.wfile.write(body)
        elif path in STATIC_FILES:
            filename, content_type = STATIC_FILES[path]
            self._send_headers(content_type)
            self.wfile.write((CLIENT_ROOT / filename).read_bytes())
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass  # keep the systemd journal quiet; remove this to see every request


if __name__ == "__main__":
    for name, cfg in PRINTERS.items():
        threading.Thread(target=poll_printer, args=(name, cfg), daemon=True).start()

    WebServer((BIND_ADDRESS, PORT), Handler).serve_forever()
