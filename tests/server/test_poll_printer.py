"""Tests for server.poll_printer() -- the background loop that keeps latest_status current.

The loop never returns, so each test replaces time.sleep with something that lets a set number of
iterations run and then raises Stop to break out.
"""

import json
import pytest


class Stop(Exception):
    pass


@pytest.fixture
def run_loop(server, monkeypatch):
    """run_loop(iterations, name="p1") runs poll_printer for that many passes, then returns."""
    def run(iterations, name="p1"):
        sleeps = []

        def fake_sleep(seconds):
            sleeps.append(seconds)
            if len(sleeps) >= iterations:
                raise Stop

        monkeypatch.setattr(server.time, "sleep", fake_sleep)
        with pytest.raises(Stop):
            server.poll_printer(name, server.PRINTERS[name])
        return sleeps
    return run


class FlakyPrinter:
    """Raises on the first N status reads, then behaves like an idle printer."""

    def __init__(self, failures, error=RuntimeError("connection lost")):
        self.failures = failures
        self.error = error

    def get_percentage(self):
        if self.failures > 0:
            self.failures -= 1
            raise self.error
        return 0

    def get_time(self):
        return 0

    def get_state(self):
        return "IDLE"

    def get_current_state(self):
        return "IDLE"

    def print_error_code(self):
        return 0


def test_connects_with_the_printers_own_credentials(server, run_loop, monkeypatch, printer_class):
    created = []

    class RecordingPrinter(printer_class):
        def __init__(self, ip, access_code, serial):
            super().__init__()
            created.append((ip, access_code, serial))
            self.connected = False

        def connect(self):
            self.connected = True

    monkeypatch.setattr(server.bl, "Printer", RecordingPrinter)
    run_loop(1)
    assert created == [("10.99.99.1", "ACCESS-CODE-1", "SERIAL-1")]


def test_publishes_the_printers_status(server, run_loop, monkeypatch, printer_class):
    class RunningPrinter(printer_class):
        def __init__(self, *args):
            super().__init__(gstate="RUNNING", percent=25, remaining_minutes=60, subtask="Benchy")

        def connect(self):
            pass

    monkeypatch.setattr(server.bl, "Printer", RunningPrinter)
    run_loop(1)
    assert server.latest_status["p1"]["state"] == "RUNNING"
    assert server.latest_status["p1"]["percent"] == 25


def test_only_updates_its_own_printer(server, run_loop, monkeypatch, printer_class):
    class RunningPrinter(printer_class):
        def __init__(self, *args):
            super().__init__(gstate="RUNNING", percent=25, remaining_minutes=60)

        def connect(self):
            pass

    monkeypatch.setattr(server.bl, "Printer", RunningPrinter)
    run_loop(1, name="p1")
    assert server.latest_status["p2"] == {"state": "UNKNOWN"}


def test_polls_every_five_seconds(server, run_loop, monkeypatch, printer_class):
    class IdlePrinter(printer_class):
        def connect(self):
            pass

        def __init__(self, *args):
            super().__init__()

    monkeypatch.setattr(server.bl, "Printer", IdlePrinter)
    assert run_loop(3) == [5, 5, 5]


def test_a_failed_connection_is_reported_and_retried(server, run_loop, monkeypatch):
    attempts = []

    class Unreachable:
        def __init__(self, *args):
            attempts.append(1)

        def connect(self):
            raise OSError("printer is off")

    monkeypatch.setattr(server.bl, "Printer", Unreachable)
    run_loop(3)
    assert server.latest_status["p1"] == {"state": "ERROR", "error": server.POLL_FAILURE_MESSAGE}
    assert len(attempts) == 3


def test_the_browser_never_sees_the_real_exception_text(server, run_loop, monkeypatch, caplog):
    # Exception text can include the printer's LAN address; it belongs in the log only.
    class Unreachable:
        def __init__(self, *args):
            pass

        def connect(self):
            raise OSError("cannot reach 10.99.99.1:8883")

    monkeypatch.setattr(server.bl, "Printer", Unreachable)
    with caplog.at_level("WARNING"):
        run_loop(3)
    assert "10.99.99.1" not in json.dumps(server.latest_status)
    logged = [r.getMessage() for r in caplog.records if "polling failed" in r.getMessage()]
    assert len(logged) == 1 and "10.99.99.1" in logged[0]


def test_a_dropped_connection_triggers_a_fresh_reconnect(server, run_loop, monkeypatch):
    created = []

    class Printer(FlakyPrinter):
        def __init__(self, *args):
            super().__init__(failures=1 if not created else 0)
            created.append(self)

        def connect(self):
            pass

    monkeypatch.setattr(server.bl, "Printer", Printer)
    run_loop(1)
    assert server.latest_status["p1"]["state"] == "ERROR"
    assert len(created) == 1

    run_loop(1)
    assert len(created) == 2
    assert server.latest_status["p1"] == {"state": "IDLE"}


def test_recovers_to_normal_status_after_an_error(server, run_loop, monkeypatch):
    created = []

    class Printer(FlakyPrinter):
        def __init__(self, *args):
            super().__init__(failures=1 if not created else 0)
            created.append(self)

        def connect(self):
            pass

    monkeypatch.setattr(server.bl, "Printer", Printer)
    run_loop(2)
    assert server.latest_status["p1"] == {"state": "IDLE"}


def test_an_unknown_stage_becomes_an_error_status_instead_of_killing_the_thread(
        server, run_loop, monkeypatch, printer_class):
    # If the printer firmware adds a stage the status map doesn't know, the page should show an
    # error and carry on, not stop updating.
    class WeirdPrinter(printer_class):
        def __init__(self, *args):
            super().__init__(gstate="RUNNING", stage="BRAND_NEW_STAGE", percent=5, remaining_minutes=5)

        def connect(self):
            pass

    monkeypatch.setattr(server.bl, "Printer", WeirdPrinter)
    run_loop(2)
    assert server.latest_status["p1"]["state"] == "ERROR"


def test_the_result_of_a_print_survives_across_polls(server, run_loop, monkeypatch, printer_class):
    # One tracker lives for the whole loop, so RUNNING -> FINISH across polls yields "succeeded".
    states = iter(["RUNNING", "FINISH"])

    class Printer(printer_class):
        def __init__(self, *args):
            super().__init__(percent=50, remaining_minutes=10)

        def connect(self):
            pass

        def get_state(self):
            self.gstate = next(states)
            return self.gstate

    monkeypatch.setattr(server.bl, "Printer", Printer)
    run_loop(2)
    assert server.latest_status["p1"] == {"state": "IDLE", "last_result": "succeeded"}


def test_the_configured_result_window_reaches_each_tracker(server, run_loop, monkeypatch, printer_class):
    # conftest configures recent_result_window_minutes = 45.
    windows = []

    class RecordingTracker(server.PrintResultTracker):
        def __init__(self, window_minutes):
            windows.append(window_minutes)
            super().__init__(window_minutes)

    class Printer(printer_class):
        def __init__(self, *args):
            super().__init__()

        def connect(self):
            pass

    monkeypatch.setattr(server, "PrintResultTracker", RecordingTracker)
    monkeypatch.setattr(server.bl, "Printer", Printer)
    run_loop(1)
    assert server.RECENT_RESULT_WINDOW_MINUTES == 45
    assert windows == [45]
