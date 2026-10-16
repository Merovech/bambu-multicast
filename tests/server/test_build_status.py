"""Tests for server.build_status() -- turning what a printer reports into what the browser is sent."""

import logging
from datetime import datetime, timedelta, timezone

import pytest

from print_result import PrintResultTracker
from printer_status_map import PRINTER_STATUS_MAP


@pytest.fixture
def status(server):
    """status(printer, name="p1", tracker=None) -> the dict sent to the browser."""
    def build(printer, name="p1", tracker=None):
        return server.build_status(printer, name, tracker or PrintResultTracker())
    return build


def running(printer_class, **overrides):
    values = dict(gstate="RUNNING", stage="PRINTING", percent=40, remaining_minutes=90,
                  subtask="Benchy", layer=118, total_layers=280)
    values.update(overrides)
    return printer_class(**values)


class TestIdle:
    def test_idle_printer_reports_only_idle(self, status, printer_class):
        assert status(printer_class(gstate="IDLE")) == {"state": "IDLE"}

    @pytest.mark.parametrize("gstate", ["IDLE", "FINISH", "FAILED", "UNKNOWN", "SOMETHING_NEW"])
    def test_any_inactive_job_state_is_idle(self, status, printer_class, gstate):
        info = status(printer_class(gstate=gstate, percent=100, remaining_minutes=0))
        assert info["state"] == "IDLE"

    @pytest.mark.parametrize("percent, remaining", [(None, 10), (10, None), ("n/a", 10), (10, "n/a")])
    def test_running_with_unusable_numbers_is_idle(self, status, printer_class, percent, remaining):
        # Right after connecting, the printer can report RUNNING before it has sent real numbers.
        info = status(printer_class(gstate="RUNNING", percent=percent, remaining_minutes=remaining))
        assert info == {"state": "IDLE"}


class TestRunning:
    def test_reports_everything_the_page_shows(self, status, printer_class):
        info = status(running(printer_class))
        assert info["state"] == "RUNNING"
        assert info["pstate"] == "Printing"
        assert info["model"] == "Benchy"
        assert info["percent"] == 40
        assert info["layer"] == 118
        assert info["total_layers"] == 280
        assert info["remaining_seconds"] == 90 * 60
        assert "error" not in info

    @pytest.mark.parametrize("gstate", ["RUNNING", "PAUSE", "PREPARE"])
    def test_active_job_states(self, status, printer_class, gstate):
        assert status(running(printer_class, gstate=gstate))["state"] == "RUNNING"

    def test_zero_percent_and_zero_minutes_still_count_as_numbers(self, status, printer_class):
        info = status(running(printer_class, percent=0, remaining_minutes=0))
        assert info["state"] == "RUNNING"
        assert info["percent"] == 0

    def test_eta_is_now_plus_remaining_time_in_utc(self, status, printer_class):
        before = datetime.now(timezone.utc).replace(microsecond=0)
        info = status(running(printer_class, remaining_minutes=90))
        after = datetime.now(timezone.utc)

        assert info["eta_utc"].endswith("Z")
        eta = datetime.strptime(info["eta_utc"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        assert before + timedelta(minutes=90) <= eta <= after + timedelta(minutes=90)

    def test_remaining_time_is_converted_from_minutes(self, status, printer_class):
        # bambulabs_api documents seconds, but the printer really reports minutes.
        assert status(running(printer_class, remaining_minutes=2))["remaining_seconds"] == 120


class TestModelName:
    def test_prefers_the_subtask_name(self, status, printer_class):
        info = status(running(printer_class, subtask="Task", gcode_file="file.gcode"))
        assert info["model"] == "Task"

    def test_falls_back_to_the_gcode_file(self, status, printer_class):
        assert status(running(printer_class, subtask="", gcode_file="file.gcode"))["model"] == "file.gcode"

    def test_falls_back_to_unknown(self, status, printer_class):
        assert status(running(printer_class, subtask="", gcode_file=""))["model"] == "Unknown"


class TestStageText:
    @pytest.mark.parametrize("stage, expected", [
        ("PRINTING", "Printing"),
        ("HOMING_TOOLHEAD", "Homing toolhead"),
        ("PAUSED_FILAMENT_RUNOUT", "Paused - filament runout"),
    ])
    def test_stage_is_translated_with_the_status_map(self, status, printer_class, stage, expected):
        assert status(running(printer_class, stage=stage))["pstate"] == expected

    def test_enum_style_names_are_accepted(self, status, printer_class):
        # The real library gives back enums whose str() looks like "PrintStatus.PRINTING".
        info = status(running(printer_class, stage="PrintStatus.HOMING_TOOLHEAD"))
        assert info["pstate"] == PRINTER_STATUS_MAP["HOMING_TOOLHEAD"]

    def test_unrecognised_stage_is_reported_as_an_error_by_the_poll_loop(self, status, printer_class):
        # build_status lets the KeyError out; poll_printer turns it into an ERROR status.
        with pytest.raises(KeyError):
            status(running(printer_class, stage="A_STAGE_THAT_DOES_NOT_EXIST"))


class TestPause:
    def test_pause_overrides_a_stage_that_still_says_printing(self, status, printer_class):
        # A jammed extruder pauses the job, but the stage can stay on "Printing".
        info = status(running(printer_class, gstate="PAUSE", stage="PRINTING"))
        assert info["pstate"] == "Paused"

    def test_pause_keeps_a_more_specific_paused_stage(self, status, printer_class):
        info = status(running(printer_class, gstate="PAUSE", stage="PAUSED_USER"))
        assert info["pstate"] == PRINTER_STATUS_MAP["PAUSED_USER"]

    def test_running_is_never_relabelled_paused(self, status, printer_class):
        assert status(running(printer_class, gstate="RUNNING", stage="PRINTING"))["pstate"] == "Printing"


class TestPrintError:
    def test_error_code_becomes_plain_text(self, status, printer_class):
        info = status(running(printer_class, gstate="PAUSE", print_error=0x0300801C))
        assert "extruder may be clogged" in info["error"]

    def test_unknown_error_code_still_produces_something_to_search_for(self, status, printer_class):
        info = status(running(printer_class, print_error=0x0DEADBEE))
        assert info["error"] == "Printer error 0DEA-DBEE (Unknown error)"

    def test_no_error_means_no_error_key(self, status, printer_class):
        assert "error" not in status(running(printer_class, print_error=0))

    def test_error_is_not_attached_to_an_idle_card(self, status, printer_class):
        # The Idle card has nowhere to show one, and a stale code must not leak into it.
        info = status(printer_class(gstate="IDLE", print_error=0x0300801C))
        assert info == {"state": "IDLE"}


class TestErrorLogging:
    def test_a_new_error_is_logged_once_in_hex(self, status, printer_class, caplog):
        printer = running(printer_class, gstate="PAUSE", print_error=0x0300801C)
        with caplog.at_level(logging.WARNING):
            status(printer)
            status(printer)
            status(printer)
        messages = [r.getMessage() for r in caplog.records if "print_error" in r.getMessage()]
        assert len(messages) == 1
        assert "print_error=0300801C" in messages[0]
        assert "p1" in messages[0]

    def test_a_changed_error_is_logged_again(self, status, printer_class, caplog):
        printer = running(printer_class, print_error=0x0300801C)
        with caplog.at_level(logging.WARNING):
            status(printer)
            printer.print_error = 0x03004006
            status(printer)
        assert len([r for r in caplog.records if "print_error" in r.getMessage()]) == 2

    def test_clearing_an_error_is_logged_and_then_it_can_be_logged_again(self, status, printer_class, caplog):
        printer = running(printer_class, print_error=0x0300801C)
        with caplog.at_level(logging.WARNING):
            status(printer)
            printer.print_error = 0
            status(printer)
            printer.print_error = 0x0300801C
            status(printer)
        assert len([r for r in caplog.records if "print_error" in r.getMessage()]) == 3

    def test_no_error_is_never_logged(self, status, printer_class, caplog):
        with caplog.at_level(logging.WARNING):
            status(running(printer_class))
        assert not [r for r in caplog.records if "print_error" in r.getMessage()]

    def test_each_printer_is_tracked_separately(self, status, printer_class, caplog):
        printer = running(printer_class, print_error=0x0300801C)
        with caplog.at_level(logging.WARNING):
            status(printer, name="p1")
            status(printer, name="p2")
        assert len([r for r in caplog.records if "print_error" in r.getMessage()]) == 2


class TestLastResult:
    def test_finished_print_reports_succeeded(self, status, printer_class):
        tracker = PrintResultTracker()
        status(running(printer_class), tracker=tracker)
        info = status(printer_class(gstate="FINISH", percent=100), tracker=tracker)
        assert info == {"state": "IDLE", "last_result": "succeeded"}

    def test_failed_print_reports_failed(self, status, printer_class):
        tracker = PrintResultTracker()
        status(running(printer_class), tracker=tracker)
        info = status(printer_class(gstate="FAILED", percent=40), tracker=tracker)
        assert info == {"state": "IDLE", "last_result": "failed"}

    def test_a_job_that_was_already_over_at_startup_reports_no_result(self, status, printer_class):
        assert status(printer_class(gstate="FINISH", percent=100)) == {"state": "IDLE"}

    def test_a_running_print_never_carries_a_result(self, status, printer_class):
        tracker = PrintResultTracker()
        status(running(printer_class), tracker=tracker)
        status(printer_class(gstate="FAILED"), tracker=tracker)
        assert "last_result" not in status(running(printer_class), tracker=tracker)
