from datetime import datetime, timedelta, timezone

from config import DEFAULT_RECENT_RESULT_WINDOW_MINUTES


class PrintResultTracker:
    """Remembers how the last print ended, but only for window_minutes afterwards.

    A window of 0 turns this off: no result is ever reported.

    The printer keeps reporting FINISH or FAILED indefinitely after a print and never says when it
    ended, so the moment is captured here: the poll where a running print turns into FINISH/FAILED.
    If the server starts up when the printer is already in one of those states, the end time is
    unknown and no result is reported.  One tracker per printer.
    """

    def __init__(self, window_minutes=DEFAULT_RECENT_RESULT_WINDOW_MINUTES):
        self._window = timedelta(minutes=window_minutes)
        self._was_active = False
        self._outcome = None
        self._ended_at = None

    def update(self, active, gcode_state, now=None):
        """Returns "succeeded", "failed", or None (no recent result to report)."""
        now = now or datetime.now(timezone.utc)

        if active:
            self._was_active = True
            self._outcome = None
            return None

        if self._was_active and gcode_state in ("FINISH", "FAILED"):
            self._outcome = "succeeded" if gcode_state == "FINISH" else "failed"
            self._ended_at = now
        self._was_active = False

        if self._outcome and self._window > timedelta(0) and now - self._ended_at <= self._window:
            return self._outcome
        return None
