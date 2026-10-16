"""Performance tests for the server.

Not part of a normal `pytest` run (see pytest.ini).  Run them on demand with:

    pytest -m perf

Results are printed in a "performance results" section at the end, plus pytest-benchmark's own table
for the micro-benchmarks.  They need `pip install -r requirements-dev.txt` (pytest-benchmark); without
it the micro-benchmarks are skipped and the rest still run.  Run them on the Raspberry Pi too, in its
venv: the Pi is the machine that matters, and it is several times slower than a desktop.

The pass/fail limits are deliberately loose -- 10x or more headroom over what a desktop measures --
so they only trip on a real regression (something accidentally quadratic, a lock held too long), never
on a noisy machine.  The numbers in the report are the useful part.

What this can't measure: the camera streams.  The A1 (ustreamer) and P2S (go2rtc + ffmpeg) video
dominates the Pi's CPU and bandwidth, and runs outside this Python server.  See the tuning section
of the punchlist for measuring that with `top` and a bandwidth monitor.
"""

import concurrent.futures
import http.client
import importlib
import json
import sys
import threading
import time
import tracemalloc

import pytest

from config import PROJECT_ROOT
from print_result import PrintResultTracker

pytestmark = pytest.mark.perf

CLIENT_DIR = PROJECT_ROOT / "client"
PAGE_LOAD = ["/", "/app.js", "/styles.css", "/config.json", "/status.json"]


def percentile(values, pct):
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(len(ordered) * pct / 100))]


def timed_get(port, path):
    """One request on a fresh connection, like a browser's fetch.  Returns (status, seconds).

    A refused connection is retried up to twice, as a browser would; the wait counts as latency.
    """
    started = time.perf_counter()
    for attempt in range(3):
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
        try:
            conn.request("GET", path)
            response = conn.getresponse()
            response.read()
            return response.status, time.perf_counter() - started
        except ConnectionRefusedError:
            if attempt == 2:
                raise
            time.sleep(0.2)
        finally:
            conn.close()


def run_clients(port, paths, clients, passes):
    """`clients` simultaneous viewers, each making `passes` rounds of requests for `paths`.

    Returns (latencies in seconds, number of non-200 or failed requests, total seconds).
    """
    def viewer(_):
        latencies, failures = [], 0
        for _ in range(passes):
            for path in paths:
                try:
                    status, seconds = timed_get(port, path)
                except OSError:
                    failures += 1
                    continue
                latencies.append(seconds)
                if status != 200:
                    failures += 1
        return latencies, failures

    started = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=clients) as pool:
        results = list(pool.map(viewer, range(clients)))
    elapsed = time.perf_counter() - started
    latencies = [x for lat, _ in results for x in lat]
    return latencies, sum(f for _, f in results), elapsed


def assert_mean_below(benchmark, seconds):
    """Checks the benchmark's average time.  Skipped when run with --benchmark-disable (no stats)."""
    if benchmark.stats:
        assert benchmark.stats.stats.mean < seconds


def summarize(label, latencies, failures, elapsed):
    ms = 1000
    return (f"{label}: {len(latencies) / elapsed:,.0f} req/s | latency "
            f"p50 {percentile(latencies, 50) * ms:.1f} ms, p95 {percentile(latencies, 95) * ms:.1f} ms, "
            f"p99 {percentile(latencies, 99) * ms:.1f} ms, max {max(latencies) * ms:.1f} ms | "
            f"{failures} failed")


# --- Per-poll work -----------------------------------------------------------------------------

class TestPollCost:
    """build_status runs once per printer every 5 seconds."""

    def test_idle_printer(self, server, printer_class, benchmark):
        printer, tracker = printer_class(gstate="IDLE"), PrintResultTracker()
        benchmark(server.build_status, printer, "p1", tracker)
        assert_mean_below(benchmark, 0.001)

    def test_running_printer(self, server, printer_class, benchmark):
        printer = printer_class(gstate="RUNNING", percent=40, remaining_minutes=90, subtask="Benchy",
                                layer=118, total_layers=280)
        tracker = PrintResultTracker()
        benchmark(server.build_status, printer, "p1", tracker)
        assert_mean_below(benchmark, 0.001)

    def test_printer_with_an_error(self, server, printer_class, benchmark):
        printer = printer_class(gstate="PAUSE", percent=40, remaining_minutes=90, subtask="Benchy",
                                print_error=0x0300801C)
        tracker = PrintResultTracker()
        benchmark(server.build_status, printer, "p1", tracker)
        assert_mean_below(benchmark, 0.001)

    def test_error_lookup(self, benchmark):
        from print_errors import describe_print_error
        benchmark(describe_print_error, 0x0300801C)
        assert_mean_below(benchmark, 0.0001)

    def test_unknown_error_lookup(self, benchmark):
        from print_errors import describe_print_error
        benchmark(describe_print_error, 0x0DEADBEE)
        assert_mean_below(benchmark, 0.0001)

    def test_result_tracking(self, benchmark):
        tracker = PrintResultTracker()
        benchmark(tracker.update, True, "RUNNING")
        assert_mean_below(benchmark, 0.0001)


# --- Startup and memory -------------------------------------------------------------------------

class TestStartup:
    def test_error_table_loads_quickly_and_stays_small(self, report):
        sys.modules.pop("print_errors", None)
        tracemalloc.start()
        started = time.perf_counter()
        module = importlib.import_module("print_errors")
        seconds = time.perf_counter() - started
        kilobytes = tracemalloc.get_traced_memory()[0] / 1024
        tracemalloc.stop()

        report(f"error table: {len(module.PRINT_ERRORS)} codes loaded in {seconds * 1000:.1f} ms, "
               f"{kilobytes:,.0f} KB of memory")
        assert seconds < 1.0
        assert kilobytes < 5 * 1024

    def test_server_module_imports_quickly(self, report):
        sys.modules.pop("server", None)
        started = time.perf_counter()
        importlib.import_module("server")
        seconds = time.perf_counter() - started
        sys.modules.pop("server", None)
        report(f"server.py import: {seconds * 1000:.1f} ms")
        assert seconds < 2.0


class TestPageWeight:
    """What a visitor downloads, before the Tailwind CDN script and the camera streams."""

    def test_site_files_stay_small(self, report):
        sizes = {p.name: p.stat().st_size for p in CLIENT_DIR.iterdir() if p.is_file()}
        total = sum(sizes.values())
        report("page weight: " + ", ".join(f"{name} {size / 1024:.1f} KB" for name, size in sorted(sizes.items()))
               + f" (total {total / 1024:.1f} KB)")
        assert total < 100 * 1024

    def test_status_response_stays_small(self, server, printer_class, report):
        # Fetched by every open browser tab every few seconds, so its size multiplies.
        printer = printer_class(gstate="PAUSE", percent=40, remaining_minutes=90, subtask="Benchy",
                                print_error=0x0300801C)
        server.latest_status["p1"] = server.build_status(printer, "p1", PrintResultTracker())
        size = len(json.dumps(server.latest_status).encode())
        report(f"status.json with two printers (one with an error): {size} bytes")
        assert size < 4096


# --- The web server under load ------------------------------------------------------------------

class TestWebServer:
    def test_one_viewer_one_request_at_a_time(self, http_port, report):
        for path in PAGE_LOAD:
            latencies, failures, elapsed = run_clients(http_port, [path], clients=1, passes=200)
            report(summarize(f"1 viewer, {path}", latencies, failures, elapsed))
            assert failures == 0
            assert percentile(latencies, 50) < 0.025  # about 0.5 ms on a desktop
            assert percentile(latencies, 95) < 0.1

    def test_a_typical_crowd_polling_status(self, http_port, report):
        # 20 open tabs.  Real traffic would be 20 / 5 s = 4 requests a second; this goes flat out.
        latencies, failures, elapsed = run_clients(http_port, ["/status.json"], clients=20, passes=50)
        report(summarize("20 viewers, /status.json flat out", latencies, failures, elapsed))
        assert failures == 0
        assert percentile(latencies, 95) < 1.0

    def test_a_large_crowd_loading_the_page(self, http_port, report):
        latencies, failures, elapsed = run_clients(http_port, PAGE_LOAD, clients=50, passes=10)
        report(summarize("50 viewers loading the whole page", latencies, failures, elapsed))
        assert failures == 0
        assert percentile(latencies, 95) < 3.0  # room for one 3 s connection retry on the Pi

    def test_throughput_has_plenty_of_headroom(self, http_port, report):
        latencies, failures, elapsed = run_clients(http_port, ["/status.json"], clients=10, passes=100)
        rate = len(latencies) / elapsed
        report(f"throughput ceiling (10 clients): {rate:,.0f} req/s, against about 4 req/s from 20 real viewers")
        assert failures == 0
        assert rate > 50

    def test_status_stays_correct_while_pollers_write(self, server, http_port, report):
        # Printer threads update latest_status under a lock while viewers read it.  Responses must
        # always be complete JSON with every printer present, and readers must not be starved.
        stop = threading.Event()
        writes = []

        def writer(name):
            count = 0
            while not stop.is_set():
                with server.status_lock:
                    server.latest_status[name] = {"state": "RUNNING", "percent": count % 100,
                                                  "model": "x" * 200}
                count += 1
                time.sleep(0.0005)  # far faster than the real 5 s poll, without starving the server
            writes.append(count)

        writers = [threading.Thread(target=writer, args=(name,)) for name in ("p1", "p2")]
        for thread in writers:
            thread.start()

        bad = []

        def viewer(_):
            latencies = []
            for _ in range(60):
                conn = http.client.HTTPConnection("127.0.0.1", http_port, timeout=10)
                started = time.perf_counter()
                conn.request("GET", "/status.json")
                body = conn.getresponse().read()
                latencies.append(time.perf_counter() - started)
                conn.close()
                try:
                    if set(json.loads(body)) != {"p1", "p2"}:
                        bad.append(body)
                except ValueError:
                    bad.append(body)
            return latencies

        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
                latencies = [x for lat in pool.map(viewer, range(4)) for x in lat]
        finally:
            stop.set()
            for thread in writers:
                thread.join()

        report(f"4 viewers while 2 threads wrote {sum(writes):,} updates: p95 "
               f"{percentile(latencies, 95) * 1000:.1f} ms, {len(bad)} bad responses")
        assert not bad
        assert percentile(latencies, 95) < 2.0

    def test_a_burst_of_simultaneous_visitors_is_not_stalled(self, http_port, report):
        latencies, failures, elapsed = run_clients(http_port, ["/status.json"], clients=50, passes=10)
        report(summarize("burst: 50 viewers connecting at once", latencies, failures, elapsed))
        assert failures == 0
        assert percentile(latencies, 99) < 0.25

    def test_serving_files_does_not_leak_memory(self, http_port, report):
        # Files are read from disk on every request; make sure nothing accumulates.
        run_clients(http_port, PAGE_LOAD, clients=5, passes=20)
        tracemalloc.start()
        before = tracemalloc.take_snapshot()
        run_clients(http_port, PAGE_LOAD, clients=5, passes=100)
        after = tracemalloc.take_snapshot()
        tracemalloc.stop()
        growth = sum(stat.size_diff for stat in after.compare_to(before, "filename")) / 1024
        report(f"memory growth over 2,500 more requests: {growth:,.0f} KB")
        assert growth < 2048
