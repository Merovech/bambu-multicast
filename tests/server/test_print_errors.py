"""Tests for server/print_errors.py -- turning the printer's numeric print_error
into text a viewer can understand."""

import sys
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parent.parent.parent / "server"
sys.path.insert(0, str(SERVER_DIR))

from print_errors import PRINT_ERRORS, describe_print_error  # noqa: E402


def test_known_code_is_translated_to_text():
    # 0x03004001 == 50347009, the way the printer reports it over MQTT.
    assert describe_print_error(0x03004001) == PRINT_ERRORS["03004001"]
    assert "nozzle" in describe_print_error(0x03004001).lower()


def test_unknown_code_falls_back_to_a_lookup_friendly_code():
    assert describe_print_error(0x0DEADBEE) == "Printer error 0DEA-DBEE (Unknown error)"


def test_leading_zeros_are_preserved_in_lookup():
    # Codes that start with 0 must still be padded to 8 digits to match the table's keys.
    assert describe_print_error(0x0300801C) == PRINT_ERRORS["0300801C"]


def test_blank_text_is_not_stored_so_lookup_falls_back_to_the_code():
    assert describe_print_error(0x05008030).startswith("Printer error")


def test_every_table_entry_has_text():
    assert all(len(key) == 8 and text for key, text in PRINT_ERRORS.items())
