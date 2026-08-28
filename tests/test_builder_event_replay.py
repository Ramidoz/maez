# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""The builder-event replay defect — a stale-but-true event re-entering
cognition forever.

FOUND IN PRODUCTION 2026-08-28 (Codex store audit, confirmed by
execution): a single ``direct_edit`` event from 2026-06-29 appeared in
the evidence packet of **171 of 171** logged reasoning cycles. The
daemon's high-water mark file held ``1782768057.988804`` — EXACTLY the
timestamp of the newest event — and ``recent_direct_edits`` selected
``ts >= since_ts``. Both boundaries inclusive, so the newest event
matched its own watermark on every subsequent cycle, forever.

WHY THIS IS THE DANGEROUS FAILURE CLASS. Nothing lied. The event really
happened; its bytes were accurate; no fabrication gate fired and none
should have. The defect is TEMPORAL — factually true information
presented as current, two months after the fact. Maez reasoned over a
June edit as though it had just occurred, ~171 times. No honesty
machinery catches this, because honesty machinery checks whether a
claim is TRUE, not whether it is NOW.

The open-session supplement was ruled OUT as the cause by execution:
every session in the store carries a matching ``session_end``, and the
stuck rows carry ``session_id='autonomous'`` with no start event at all.

Timestamp collision was ruled out before choosing a strict boundary:
``ts`` is REAL with microsecond resolution and ZERO of the 506 rows in
the live store share a timestamp.
"""

from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from core.cognition.audit_log import (
    DIRECT_EDIT,
    DIRECT_EDIT_SESSION_END,
    DIRECT_EDIT_SESSION_START,
    AuditLog,
)
from core.infra.builder_mode_perception import format_recent_builder_events

_PROBE_ROOT = "/var/tmp"


def _log(tmp: str) -> AuditLog:
    return AuditLog(db_path=str(Path(tmp) / "audit_log.db"))


def _row(log: AuditLog, ts: float, action: str, session: str) -> None:
    """Insert one audit row at an EXACT timestamp.

    The public writer stamps ``time.time()`` internally, so the store
    state is built directly here. This constructs the fixture; the code
    under test is the READER and the watermark arithmetic.
    """
    import secrets
    import sqlite3
    from contextlib import closing

    with closing(sqlite3.connect(log.db_path)) as conn, conn:
        conn.execute(
            "INSERT INTO audit_log (request_id, ts, action, decision, "
            "session_id) VALUES (?, ?, ?, ?, ?)",
            (secrets.token_hex(12), ts, action, "allow", session),
        )


def _edit(log: AuditLog, ts: float, *, session: str = "autonomous") -> None:
    _row(log, ts, DIRECT_EDIT, session)


class BuilderEventWatermarkTests(unittest.TestCase):
    def test_an_event_is_never_surfaced_twice(self):
        """The defect, at the level the daemon actually suffers it.

        Cycle 1 surfaces the event and returns a new watermark. Cycle 2,
        given that watermark and NO new events, must surface nothing.
        """
        with TemporaryDirectory(dir=_PROBE_ROOT) as tmp:
            log = _log(tmp)
            _edit(log, 1000.5)

            block1, hwm1 = format_recent_builder_events(log, since_ts=0.0)
            self.assertTrue(block1, "cycle 1 should surface the new edit")
            self.assertEqual(hwm1, 1000.5)

            block2, hwm2 = format_recent_builder_events(log, since_ts=hwm1)
            self.assertEqual(
                block2, "",
                "THE REPLAY DEFECT: the same event was surfaced again on "
                "the next cycle. In production this put a June edit into "
                "171 of 171 reasoning cycles — factually true, temporally "
                "false.",
            )
            self.assertEqual(hwm2, hwm1, "an empty pass must not move the mark")

    def test_replay_does_not_resume_on_later_cycles(self):
        """Three cycles, because the defect is unbounded, not one-shot."""
        with TemporaryDirectory(dir=_PROBE_ROOT) as tmp:
            log = _log(tmp)
            _edit(log, 2000.25)
            _block, hwm = format_recent_builder_events(log, since_ts=0.0)
            for cycle in range(3):
                block, hwm = format_recent_builder_events(log, since_ts=hwm)
                self.assertEqual(
                    block, "", f"event re-surfaced on quiet cycle {cycle + 1}"
                )

    def test_genuinely_new_events_still_arrive(self):
        """The fix must not buy silence by dropping real events."""
        with TemporaryDirectory(dir=_PROBE_ROOT) as tmp:
            log = _log(tmp)
            _edit(log, 3000.0)
            _b1, hwm = format_recent_builder_events(log, since_ts=0.0)

            _edit(log, 3001.0)
            block, hwm2 = format_recent_builder_events(log, since_ts=hwm)
            self.assertTrue(
                block,
                "a NEW edit after the watermark must still be perceived — "
                "a fix that silences everything is not a fix",
            )
            self.assertEqual(hwm2, 3001.0)

    def test_the_boundary_event_is_excluded_but_its_successor_is_not(self):
        """The exact boundary, pinned at the reader.

        ``since_ts`` means 'everything I have ALREADY shown up to and
        including this instant'. An event AT the mark is spent; the next
        one is not.
        """
        with TemporaryDirectory(dir=_PROBE_ROOT) as tmp:
            log = _log(tmp)
            _edit(log, 4000.0)
            _edit(log, 4000.000001)

            rows = log.recent_direct_edits(since_ts=4000.0)
            times = [r["ts"] for r in rows]
            self.assertNotIn(
                4000.0, times, "the spent boundary event came back"
            )
            self.assertIn(
                4000.000001, times,
                "microsecond-later events must survive the boundary — "
                "ts is REAL with microsecond resolution",
            )

    def test_an_open_session_supplement_still_works(self):
        """Ruled out as the cause, but it must not be broken by the fix.

        A session opened before the watermark and never closed is
        DELIBERATELY re-supplied regardless of ts, so a mid-session
        restart still sees its context.
        """
        with TemporaryDirectory(dir=_PROBE_ROOT) as tmp:
            log = _log(tmp)
            _row(log, 5000.0, DIRECT_EDIT_SESSION_START, "open_one")
            _edit(log, 5001.0, session="open_one")

            block, _hwm = format_recent_builder_events(log, since_ts=9999.0)
            self.assertTrue(
                block,
                "an OPEN session must still be supplied across the "
                "watermark — that lane is intentional and separate",
            )

    def test_a_closed_session_is_not_resupplied(self):
        with TemporaryDirectory(dir=_PROBE_ROOT) as tmp:
            log = _log(tmp)
            _row(log, 6000.0, DIRECT_EDIT_SESSION_START, "done")
            _row(log, 6001.0, DIRECT_EDIT_SESSION_END, "done")
            block, _hwm = format_recent_builder_events(log, since_ts=9999.0)
            self.assertEqual(
                block, "", "a CLOSED session was resupplied past the mark"
            )


if __name__ == "__main__":
    unittest.main()
