"""Tests for server/print_result.py -- reporting how the last print ended, but only
for 30 minutes afterwards."""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

SERVER_DIR = Path(__file__).resolve().parent.parent.parent / "server"
sys.path.insert(0, str(SERVER_DIR))

from print_result import PrintResultTracker  # noqa: E402

START = datetime(2026, 10, 15, 12, 0, tzinfo=timezone.utc)


def minutes(n):
    return START + timedelta(minutes=n)


def test_successful_print_is_reported_as_succeeded():
    tracker = PrintResultTracker()
    assert tracker.update(True, "RUNNING", minutes(0)) is None
    assert tracker.update(False, "FINISH", minutes(1)) == "succeeded"


def test_failed_print_is_reported_as_failed():
    tracker = PrintResultTracker()
    tracker.update(True, "RUNNING", minutes(0))
    assert tracker.update(False, "FAILED", minutes(1)) == "failed"


def test_result_stays_for_the_whole_window_then_disappears():
    tracker = PrintResultTracker()
    tracker.update(True, "RUNNING", minutes(0))
    tracker.update(False, "FINISH", minutes(1))
    assert tracker.update(False, "FINISH", minutes(31)) == "succeeded"
    assert tracker.update(False, "FINISH", minutes(32)) is None


def test_result_stays_gone_once_expired():
    tracker = PrintResultTracker()
    tracker.update(True, "RUNNING", minutes(0))
    tracker.update(False, "FINISH", minutes(1))
    tracker.update(False, "FINISH", minutes(40))
    assert tracker.update(False, "IDLE", minutes(41)) is None


def test_printer_already_finished_at_startup_reports_nothing():
    # No way to know when it ended, so plain Idle is the honest answer.
    tracker = PrintResultTracker()
    assert tracker.update(False, "FINISH", minutes(0)) is None


def test_starting_a_new_print_clears_the_old_result():
    tracker = PrintResultTracker()
    tracker.update(True, "RUNNING", minutes(0))
    tracker.update(False, "FAILED", minutes(1))
    assert tracker.update(True, "RUNNING", minutes(5)) is None
    assert tracker.update(False, "FINISH", minutes(10)) == "succeeded"


class TestWindowMinutes:
    def ended_then_checked(self, window_minutes, minutes_later):
        tracker = PrintResultTracker(window_minutes)
        tracker.update(True, "RUNNING", minutes(0))
        tracker.update(False, "FINISH", minutes(1))
        return tracker.update(False, "FINISH", minutes(1 + minutes_later))

    def test_default_window_is_thirty_minutes(self):
        tracker = PrintResultTracker()
        tracker.update(True, "RUNNING", minutes(0))
        tracker.update(False, "FAILED", minutes(1))
        assert tracker.update(False, "FAILED", minutes(31)) == "failed"
        assert tracker.update(False, "FAILED", minutes(32)) is None

    @pytest.mark.parametrize("window", [1, 5, 30, 90, 600])
    def test_window_is_measured_in_minutes(self, window):
        assert self.ended_then_checked(window, window) == "succeeded"
        assert self.ended_then_checked(window, window + 1) is None

    def test_a_short_window_expires_sooner(self):
        assert self.ended_then_checked(5, 4) == "succeeded"
        assert self.ended_then_checked(5, 6) is None

    def test_a_long_window_lasts_longer(self):
        assert self.ended_then_checked(180, 179) == "succeeded"
        assert self.ended_then_checked(180, 181) is None

    def test_fractions_of_a_minute_work(self):
        tracker = PrintResultTracker(0.5)
        tracker.update(True, "RUNNING", START)
        tracker.update(False, "FINISH", START + timedelta(seconds=10))
        assert tracker.update(False, "FINISH", START + timedelta(seconds=39)) == "succeeded"
        assert tracker.update(False, "FINISH", START + timedelta(seconds=41)) is None

    def test_zero_turns_the_message_off(self):
        tracker = PrintResultTracker(0)
        tracker.update(True, "RUNNING", minutes(0))
        # Not even on the very poll that sees the print end.
        assert tracker.update(False, "FINISH", minutes(1)) is None
        assert tracker.update(False, "FINISH", minutes(2)) is None

    def test_each_tracker_has_its_own_window(self):
        short, long = PrintResultTracker(5), PrintResultTracker(60)
        for tracker in (short, long):
            tracker.update(True, "RUNNING", minutes(0))
            tracker.update(False, "FINISH", minutes(1))
        assert short.update(False, "FINISH", minutes(20)) is None
        assert long.update(False, "FINISH", minutes(20)) == "succeeded"
