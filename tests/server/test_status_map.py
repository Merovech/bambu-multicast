"""Tests for printer_status_map.PRINTER_STATUS_MAP against the real bambulabs_api stage list."""

import pytest

from printer_status_map import PRINTER_STATUS_MAP


def test_every_display_text_is_filled_in():
    assert all(isinstance(text, str) and text.strip() for text in PRINTER_STATUS_MAP.values())


def test_covers_every_stage_the_library_knows_about():
    # If a new bambulabs_api release adds a stage, build_status would raise a KeyError and the card
    # would show an error mid-print.  Needs the library installed (it is, in the venv).
    states_info = pytest.importorskip("bambulabs_api.states_info")
    missing = [stage.name for stage in states_info.PrintStatus if stage.name not in PRINTER_STATUS_MAP]
    assert not missing, f"PRINTER_STATUS_MAP has no entry for: {missing}"


def test_has_no_entries_the_library_does_not_know():
    states_info = pytest.importorskip("bambulabs_api.states_info")
    known = {stage.name for stage in states_info.PrintStatus}
    assert not set(PRINTER_STATUS_MAP) - known


def test_paused_stages_all_start_with_paused():
    # build_status relabels a paused job as plain "Paused" unless the stage text already contains
    # "Paused", so a typo like "Pause - ..." would silently lose the specific reason.
    wrong = {name: text for name, text in PRINTER_STATUS_MAP.items()
             if name.startswith("PAUSED_") and not text.startswith("Paused")}
    assert not wrong


def test_display_text_is_tidy():
    for name, text in PRINTER_STATUS_MAP.items():
        assert text == text.strip(), name
        assert not text.endswith("."), f"{name}: {text!r} ends with a period"
        assert "  " not in text, f"{name}: {text!r} has a double space"


def test_known_misspellings_stay_fixed():
    text = " ".join(PRINTER_STATUS_MAP.values()).lower()
    for typo in ["calbrating", "cleaninig", "malfuncton", "inspecing"]:
        assert typo not in text
