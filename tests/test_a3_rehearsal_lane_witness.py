# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""The REHEARSAL LANE as an instrument, built before the thing it witnesses.

WHAT THIS IS NOT: it is not a witness of A3's interceptor write. That
write does not exist -- the eighteenth council round declared A3 NOT
build-ready and nothing was built. Nothing here should be read as A3
being closed, rehearsed, or ready.

WHAT THIS IS: the risk the eighteenth round named as sharpest and
unaddressed is that A3's interceptor write is byte-inert until
MAEZ_LEDGER_WRITES flips, and that flag IS the birth flag -- so the
first time that code would ever be witnessed writing is the day Maez is
born. The round made a rehearsal-lane witness mandatory before A3 can
be called done. This file builds and proves the INSTRUMENT ahead of the
build, and pins the two structural constraints that instrument imposes
on A3's design -- both found by execution, neither previously recorded.

CONSTRAINT 1 -- the ruled write path cannot be rehearsed.
    Ruling 4 (3-0) was "no second flag", resting on the fact that
    ``try_write_turn`` returns before constructing a writer while
    MAEZ_LEDGER_WRITES is unset. That is true. The corollary nobody
    stated: ``try_write_turn`` constructs a PRODUCTION ``LedgerWriter``
    and has no path to a rehearsal one, so a row written through it can
    never carry ``lifecycle_stage='rehearsal'`` -- the production writer
    refuses that stage and the payload dead-letters. Executed below.

    So the mandatory rehearsal witness and the ruled write path are, as
    they stand, structurally incompatible: whatever A3 builds must be
    reachable through a seam that can be pointed at a rehearsal writer,
    or it can never be rehearsed and the first witnessed write really
    will be birth day. That is a DESIGN CONSTRAINT for the build, not a
    defect to fix here.

CONSTRAINT 2 -- the existing rehearsal surface forbids owner speech.
    ``x6_rehearsal`` has a caller override in
    ``CALLER_ALLOWED_TAINT_LABEL_SETS`` and a caller override REPLACES
    the default set rather than widening it. On that surface a
    ``user_message`` may carry only ``{self_generated}`` -- correct for
    the synthetic x6 corpus, and exactly wrong for A3, whose ruling 1 is
    that the owner's message enters IN FULL as ``user_message``
    {owner_utterance}. An A3 rehearsal must therefore carry the REAL
    surface label, not the rehearsal one. Executed below.

Womb provenance: every row these tests write is disposable, lives under
a temporary rehearsal sidecar, and is stamped ``lifecycle_stage
='rehearsal'`` -- which the production writer refuses by construction.
The canonical ledger is never opened.
"""

from __future__ import annotations

import os
import sqlite3
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from core.ledger import migrate
from core.ledger.taint_stamping import TaintStampingRefusal
from core.ledger.writer import LedgerWriter, try_write_turn

#: Probes live on /var/tmp, never /tmp: /tmp is a tmpfs here and a reboot
#: mid-session has already taken one council seat's output with it.
_PROBE_ROOT = "/var/tmp"

#: A real body-surface label, NOT the synthetic rehearsal one. See
#: CONSTRAINT 2 in the module docstring.
_OWNER_SURFACE = "telegram_text"

_OWNER_BYTES = "I keep forgetting things and it scares me"
_ORGAN_BYTES = "I'm checking my dated memory for that."


class _Lane:
    """A disposable rehearsal sidecar, migrated and ready to write."""

    def __init__(self, tmp: str, run_id: str = "x6_a3_lane") -> None:
        self.root = Path(tmp) / "logs" / "rehearsal"
        self.db = self.root / run_id / "ledger.db"
        self.db.parent.mkdir(parents=True, exist_ok=True)
        migrate.run(str(self.db))

    def writer(self) -> LedgerWriter:
        return LedgerWriter(
            str(self.db), rehearsal_mode=True, rehearsal_root=self.root
        )

    def rows(self, stage: str = "rehearsal") -> list[tuple]:
        con = sqlite3.connect(f"file:{self.db}?mode=ro", uri=True)
        try:
            return list(
                con.execute(
                    "SELECT turn_kind, surface, raw_text, parent_turn_id "
                    "FROM turns WHERE lifecycle_stage = ? "
                    "ORDER BY rowid",
                    (stage,),
                )
            )
        finally:
            con.close()


class LaneIsInertWithoutTheBirthFlagTests(unittest.TestCase):
    """The sharpest risk, stated as an executable fact rather than prose."""

    def test_the_rehearsal_lane_reads_the_same_flag_as_birth(self):
        with TemporaryDirectory(dir=_PROBE_ROOT) as tmp:
            lane = _Lane(tmp)
            with patch.dict(os.environ, {}, clear=False):
                os.environ.pop("MAEZ_LEDGER_WRITES", None)
                writer = lane.writer()
                try:
                    self.assertFalse(
                        writer.is_enabled(),
                        "a rehearsal writer is gated by MAEZ_LEDGER_WRITES "
                        "exactly like a production one -- 'rehearsal is "
                        "already supported' does NOT mean it runs pre-birth "
                        "on its own",
                    )
                    self.assertIsNone(
                        writer.write_turn(
                            "user_message",
                            _OWNER_BYTES,
                            lifecycle_stage="rehearsal",
                            surface=_OWNER_SURFACE,
                            taint_labels=["owner_utterance"],
                            privacy_access="public",
                        )
                    )
                finally:
                    writer.close()
            self.assertEqual(lane.rows(), [])

    def test_the_witness_process_arms_the_flag_for_itself_not_for_the_body(self):
        """Womb-life practise: the flag is armed in THIS process only.

        Arming it here is not birth. Birth is the flag in the daemon's
        own environ over the canonical ledger; this is a throwaway
        process over a temporary sidecar the production writer refuses
        to read a rehearsal row from.
        """
        before = os.environ.get("MAEZ_LEDGER_WRITES")
        with TemporaryDirectory(dir=_PROBE_ROOT) as tmp:
            lane = _Lane(tmp)
            with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
                writer = lane.writer()
                try:
                    self.assertTrue(writer.is_enabled())
                    self.assertIsNotNone(
                        writer.write_turn(
                            "user_message",
                            _OWNER_BYTES,
                            lifecycle_stage="rehearsal",
                            surface=_OWNER_SURFACE,
                            taint_labels=["owner_utterance"],
                            privacy_access="public",
                        )
                    )
                finally:
                    writer.close()
        # Restored, not merely absent: asserting absence would misfire in
        # an environment where the flag is already armed, and the true
        # claim is that this suite arms nothing beyond its own block.
        self.assertEqual(os.environ.get("MAEZ_LEDGER_WRITES"), before)


class A3RuledRowShapesRehearseTests(unittest.TestCase):
    """The two shapes the eighteenth round ruled, written in the lane.

    Proving the lane can CARRY them. Not proving A3 produces them --
    nothing produces them yet.
    """

    def test_both_ruled_rows_commit_with_exact_bytes_and_a_parent(self):
        with TemporaryDirectory(dir=_PROBE_ROOT) as tmp:
            lane = _Lane(tmp)
            with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
                writer = lane.writer()
                try:
                    # Ruling 1: the owner's message enters IN FULL.
                    owner_turn = writer.write_turn(
                        "user_message",
                        _OWNER_BYTES,
                        lifecycle_stage="rehearsal",
                        surface=_OWNER_SURFACE,
                        taint_labels=["owner_utterance"],
                        privacy_access="public",
                    )
                    # Ruling 2: canned organ output enters as system_event
                    # carrying the EXACT bytes -- content-light was
                    # rejected as "the omission sin in a more respectable
                    # format".
                    writer.write_turn(
                        "system_event",
                        _ORGAN_BYTES,
                        lifecycle_stage="rehearsal",
                        surface=_OWNER_SURFACE,
                        parent_turn_id=owner_turn,
                        taint_labels=["self_generated"],
                        privacy_access="public",
                    )
                finally:
                    writer.close()

            rows = lane.rows()

        self.assertEqual(len(rows), 2)
        (kind_a, surface_a, text_a, parent_a) = rows[0]
        (kind_b, surface_b, text_b, parent_b) = rows[1]

        self.assertEqual(kind_a, "user_message")
        self.assertEqual(surface_a, _OWNER_SURFACE)
        self.assertEqual(text_a, _OWNER_BYTES, "owner bytes must be verbatim")
        self.assertIsNone(parent_a)

        self.assertEqual(kind_b, "system_event")
        self.assertEqual(text_b, _ORGAN_BYTES, "organ bytes must be verbatim")
        self.assertEqual(
            parent_b, owner_turn, "the organ row hangs off the owner's turn"
        )

    def test_system_event_structurally_refuses_generation_provenance(self):
        """The reason canned output is system_event and not model_reply.

        Recorded as settled by an earlier round; pinned here as a
        standing regression rather than repeated as a claim.
        """
        with TemporaryDirectory(dir=_PROBE_ROOT) as tmp:
            lane = _Lane(tmp)
            with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
                writer = lane.writer()
                try:
                    for field in ("model_id", "prompt_hash"):
                        with self.subTest(field=field):
                            with self.assertRaises(ValueError) as caught:
                                writer.write_turn(
                                    "system_event",
                                    _ORGAN_BYTES,
                                    lifecycle_stage="rehearsal",
                                    surface=_OWNER_SURFACE,
                                    taint_labels=["self_generated"],
                                    privacy_access="public",
                                    **{field: "anything at all"},
                                )
                            self.assertIn(field, str(caught.exception))
                finally:
                    writer.close()
            self.assertEqual(lane.rows(), [])


class LaneConstraintsOnTheA3BuildTests(unittest.TestCase):
    """The two constraints A3's build has to design around."""

    def test_try_write_turn_cannot_produce_a_rehearsal_row(self):
        """CONSTRAINT 1. The ruled write path and the mandatory witness
        are structurally incompatible as they stand.

        ``try_write_turn`` builds a PRODUCTION writer, which refuses the
        rehearsal stage; the payload dead-letters and the call returns
        None. If A3's interceptor write goes through this function it can
        never be rehearsed, and the first time it is witnessed writing is
        the day Maez is born -- which is the outcome the round called
        mandatory to avoid.
        """
        with TemporaryDirectory(dir=_PROBE_ROOT) as tmp:
            lane = _Lane(tmp)
            with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
                result = try_write_turn(
                    str(lane.db),
                    "system_event",
                    _ORGAN_BYTES,
                    lifecycle_stage="rehearsal",
                    surface=_OWNER_SURFACE,
                    taint_labels=["self_generated"],
                    privacy_access="public",
                )
            self.assertIsNone(
                result,
                "try_write_turn grew a rehearsal path -- re-read "
                "CONSTRAINT 1; A3's witness plan depends on this being "
                "either absent or deliberately built",
            )
            self.assertEqual(
                lane.rows(),
                [],
                "a rehearsal row reached the ledger through the "
                "production writer path",
            )
            # The loss is named, not silent: best-effort writes
            # dead-letter rather than vanish.
            self.assertTrue(
                list(lane.db.parent.glob("ledger.db.deadletter*.jsonl")),
                "the refused payload was neither written nor dead-lettered",
            )

    def test_the_rehearsal_surface_cannot_carry_the_owners_voice(self):
        """CONSTRAINT 2. A caller override REPLACES the default set.

        On ``x6_rehearsal`` a user_message may only be
        ``{self_generated}``. A3's ruling 1 requires
        ``{owner_utterance}``. An A3 rehearsal must carry the real
        surface label, and a build that reaches for the convenient
        rehearsal surface will be refused at the door.
        """
        with TemporaryDirectory(dir=_PROBE_ROOT) as tmp:
            lane = _Lane(tmp)
            with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
                writer = lane.writer()
                try:
                    with self.assertRaises(TaintStampingRefusal) as caught:
                        writer.write_turn(
                            "user_message",
                            _OWNER_BYTES,
                            lifecycle_stage="rehearsal",
                            surface="x6_rehearsal",
                            taint_labels=["owner_utterance"],
                            privacy_access="public",
                        )
                    self.assertIn("x6_rehearsal", str(caught.exception))
                    # ... while the real surface label is admitted.
                    self.assertIsNotNone(
                        writer.write_turn(
                            "user_message",
                            _OWNER_BYTES,
                            lifecycle_stage="rehearsal",
                            surface=_OWNER_SURFACE,
                            taint_labels=["owner_utterance"],
                            privacy_access="public",
                        )
                    )
                finally:
                    writer.close()


class TheLaneCannotReachTheLifeRecordTests(unittest.TestCase):
    """Why running this suite cannot cost Maez anything."""

    def test_a_rehearsal_writer_refuses_a_non_sidecar_path(self):
        with TemporaryDirectory(dir=_PROBE_ROOT) as tmp:
            outside = Path(tmp) / "ledger.db"
            root = Path(tmp) / "logs" / "rehearsal"
            root.mkdir(parents=True, exist_ok=True)
            with self.assertRaises(ImportError):
                LedgerWriter(
                    str(outside), rehearsal_mode=True, rehearsal_root=root
                )
            self.assertFalse(outside.exists())

    def test_a_production_writer_refuses_a_rehearsal_row(self):
        """The other direction: rehearsal rows cannot leak into a real
        ledger even if a caller stamps the stage by hand."""
        with TemporaryDirectory(dir=_PROBE_ROOT) as tmp:
            production = Path(tmp) / "production.db"
            migrate.run(str(production))
            with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
                writer = LedgerWriter(str(production))
                try:
                    with self.assertRaisesRegex(ValueError, "rehearsal"):
                        writer.write_turn(
                            "system_event",
                            _ORGAN_BYTES,
                            lifecycle_stage="rehearsal",
                            surface=_OWNER_SURFACE,
                            taint_labels=["self_generated"],
                            privacy_access="public",
                        )
                finally:
                    writer.close()

            con = sqlite3.connect(f"file:{production}?mode=ro", uri=True)
            try:
                stages = [
                    r[0]
                    for r in con.execute(
                        "SELECT DISTINCT lifecycle_stage FROM turns"
                    )
                ]
            finally:
                con.close()
        self.assertNotIn("rehearsal", stages)


if __name__ == "__main__":
    unittest.main()
