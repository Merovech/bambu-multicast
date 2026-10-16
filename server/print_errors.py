import json
from pathlib import Path

# print_errors.json maps the printer's 8-digit hex error codes (e.g. "03004001") to
# the plain-English text Bambu shows for them.  Unlike PRINTER_STATUS_MAP, which translates the
# printer's *stage* enum, these are a separate set of numbers: the "print_error" field.
#
# The text comes from the English error table shipped with the ha-bambulab Home Assistant
# integration (MIT license, https://github.com/greghesp/ha-bambulab), which in turn mirrors Bambu's
# own wiki.  Where Bambu words an error differently per printer model, the generic wording is used.
# See THIRD_PARTY_NOTICES.md at the project root for the full license text.
with open(Path(__file__).resolve().parent / "print_errors.json", encoding="utf-8") as f:
    PRINT_ERRORS = json.load(f)


def describe_print_error(code):
    key = f"{code:08X}"
    # Codes missing from the table still show up in a form that can be looked up on Bambu's wiki.
    return PRINT_ERRORS.get(key) or f"Printer error {key[:4]}-{key[4:]} (Unknown error)"
