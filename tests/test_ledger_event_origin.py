# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""A3 slice 1 — the ``event_origin`` carrier (owner-ruled 2026-08-27).

The owner ruled the organ-identity carrier is a NEW DEDICATED
``event_origin`` column: ``surface`` stays the conversation channel,
``raw_surface`` stays transport provenance and taint authority, and the
organ name lives in its own field. The twenty-first council round froze
the contract this file pins:

  Q1  The column enters the CHAIN PREIMAGE. The key is always present
      (``None`` default) in every canonical row constructor; it never
      joins ``chain._CHAIN_HASH_EXCLUDE``. Tampering with attribution
      must break the chain even for an adversary who drops the
      append-only triggers.
  Q2  One frozen implication: ``event_origin`` non-None ⇒
      ``turn_kind == 'system_event'``. The reverse is NOT frozen —
      genesis and generic system rows keep ``None`` legally. Every
      other kind refuses loudly in the §4.2 shape.
  Q3  Verbatim free-form value: non-empty, non-whitespace ``str``,
      stored untouched. No enum (the mouth-whitelist scar: a curated
      roster saw 0 of 5 real mouths), no SQL DEFAULT, no length cap
      (dissent recorded). ``None`` is the ONLY spelling of "no organ";
      ``""`` refuses.
  Q4  Replay causation compares the column against the writer default
      (``None``) — a check that skips what it cannot see is not a
      check.
  Q5  ``span_reader`` exposes the column BY CONTRACT (pinned here, not
      left to the ``SELECT *`` accident). ``recent_turns_by_kind`` is
      deliberately NOT widened — that SELECT feeds the prompt and is
      the owner's territory (deferred by name, beside the owed
      ``submitted_at``).
  Era The preimage edit is the first canonical-bytes change since the
      schema ratification; ``schema_version`` bumps 1 → 2 in lockstep
      (GENESIS_ROW int + embedded JSON, writer row, meta seed).

Named residual, pinned not fixed: the spool door deliberately passes
``event_origin`` (it is a producer ASSERTION in the same trust class as
the free-form ``surface``/``raw_surface`` labels the door already
passes). Refusing it as authority was executed into a wall: replay
reconstruction refuses stranded authority kwargs, so organ dead-letters
would become permanently unreplayable — and the web ``/chat`` S4
closure runs in a NON-OWNER process whose only custody IS the spool.
The recorder seam (slice 2) binds production constants; the door stays
honest about what it does not verify.
"""

from __future__ import annotations

import json
import os
import sqlite3
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from core.infra.sqlite_runtime import has_wal_reset_fix
from core.ledger import chain, migrate, spool
from core.ledger.taint_stamping import CALLER_ALLOWED_TAINT_LABEL_SETS
from core.ledger.writer import LedgerWriter, try_write_turn

_needs_enabled_writer = unittest.skipUnless(
    has_wal_reset_fix(),
    "an enabled ledger writer requires SQLite >= 3.51.3 "
    "(run with LD_LIBRARY_PATH=vendor/sqlite/lib)",
)

#: Probes live on /var/tmp, never /tmp (tmpfs; a reboot has already
#: eaten one council seat's output there).
_PROBE_ROOT = "/var/tmp"

_ORGAN = "recall_receipt"
_ORGAN_BYTES = "I'm checking my dated memory for that."


def _select_star(db_path: Path | str) -> list[dict]:
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        con.row_factory = sqlite3.Row
        return [
            dict(r)
            for r in con.execute(
                "SELECT * FROM turns ORDER BY chain_position"
            )
        ]
    finally:
        con.close()


def _enabled_writer(db_path: Path | str) -> LedgerWriter:
    return LedgerWriter(str(db_path))


def _write_system_event(writer: LedgerWriter, text: str = _ORGAN_BYTES, **kw):
    return writer.write_turn(
        "system_event",
        text,
        taint_labels=["self_generated"],
        privacy_access="public",
        **kw,
    )


class MigrationEventOriginTests(unittest.TestCase):
    """Migration 0007: the column exists on fresh dbs; populated
    pre-0007 dbs refuse instead of silently breaking their chains."""

    def test_fresh_db_has_nullable_event_origin_column_without_default(self):
        with TemporaryDirectory(dir=_PROBE_ROOT) as tmp:
            db = Path(tmp) / "ledger.db"
            migrate.run(str(db))
            con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
            try:
                info = {
                    r[1]: r for r in con.execute("PRAGMA table_info(turns)")
                }
            finally:
                con.close()
        self.assertIn("event_origin", info)
        col_type, notnull, dflt = (
            info["event_origin"][2],
            info["event_origin"][3],
            info["event_origin"][4],
        )
        self.assertEqual(col_type, "TEXT")
        self.assertEqual(notnull, 0, "event_origin must be nullable")
        self.assertIsNone(
            dflt,
            "a SQL DEFAULT would fabricate attribution no caller made",
        )

    def test_populated_pre_0007_db_refuses_the_migration(self):
        """The owner's 'free now and never again', encoded as a refusal.

        A db whose turns table already holds rows (the four retained x6
        rehearsal sidecars are the live example) must surface-and-ask,
        never have its chain silently invalidated. The state is
        produced with the real migration runner: migrate fully, then
        un-record 0007 (schema_migrations is legitimately mutable) so
        0007 is pending over a populated table.
        """
        with TemporaryDirectory(dir=_PROBE_ROOT) as tmp:
            db = Path(tmp) / "ledger.db"
            migrate.run(str(db))
            con = sqlite3.connect(str(db))
            try:
                con.execute(
                    "DELETE FROM schema_migrations WHERE name LIKE '0007%'"
                )
                con.commit()
            finally:
                con.close()
            with self.assertRaises(migrate.LedgerMigrationRefusal) as caught:
                migrate.run(str(db))
        self.assertIn("event_origin", str(caught.exception))


class SchemaVersionEraTests(unittest.TestCase):
    """The preimage edit is a schema era: v2, in lockstep everywhere."""

    def test_genesis_row_and_meta_carry_schema_version_2(self):
        self.assertEqual(migrate.GENESIS_ROW["schema_version"], 2)
        embedded = json.loads(migrate.GENESIS_ROW["raw_text"])
        self.assertEqual(embedded.get("schema_version"), 2)
        with TemporaryDirectory(dir=_PROBE_ROOT) as tmp:
            db = Path(tmp) / "ledger.db"
            migrate.run(str(db))
            con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
            try:
                meta = con.execute(
                    "SELECT value FROM meta WHERE key='schema_version'"
                ).fetchone()[0]
            finally:
                con.close()
        self.assertEqual(meta, "2")

    def test_genesis_row_carries_the_event_origin_key_as_none(self):
        self.assertIn("event_origin", migrate.GENESIS_ROW)
        self.assertIsNone(migrate.GENESIS_ROW["event_origin"])

    @_needs_enabled_writer
    def test_written_rows_carry_schema_version_2(self):
        with TemporaryDirectory(dir=_PROBE_ROOT) as tmp:
            db = Path(tmp) / "ledger.db"
            migrate.run(str(db))
            with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
                w = _enabled_writer(db)
                try:
                    _write_system_event(w)
                finally:
                    w.close()
            rows = _select_star(db)
        self.assertEqual(
            [r["schema_version"] for r in rows], [2, 2],
            "genesis and written rows are both v2 era",
        )


class ChainPreimageTests(unittest.TestCase):
    """Q1: attribution is inside the tamper-evidence, always-present."""

    def test_event_origin_is_not_in_the_chain_hash_strip_set(self):
        self.assertNotIn(
            "event_origin",
            chain._CHAIN_HASH_EXCLUDE,
            "the twenty-first round ruled the preimage TAKES the "
            "column; adding it to the strip set makes attribution "
            "forgery chain-invisible",
        )

    @_needs_enabled_writer
    def test_read_back_rows_verify_with_and_without_an_origin(self):
        with TemporaryDirectory(dir=_PROBE_ROOT) as tmp:
            db = Path(tmp) / "ledger.db"
            migrate.run(str(db))
            with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
                w = _enabled_writer(db)
                try:
                    _write_system_event(w, event_origin=_ORGAN)
                    _write_system_event(w, "no organ claimed")
                finally:
                    w.close()
            rows = _select_star(db)
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[1]["event_origin"], _ORGAN)
        self.assertIsNone(rows[2]["event_origin"])
        self.assertEqual(
            chain.verify_chain(rows), [],
            "SELECT * read-back (which carries the event_origin key on "
            "every row) must verify: the writer's preimage and the "
            "stored row are the same bytes",
        )

    @_needs_enabled_writer
    def test_forged_attribution_breaks_the_chain_even_without_triggers(self):
        """The adversary the chain exists for has file access and can
        drop the append-only triggers. The trigger is enforcement; the
        chain is evidence; evidence must survive the trigger."""
        with TemporaryDirectory(dir=_PROBE_ROOT) as tmp:
            db = Path(tmp) / "ledger.db"
            migrate.run(str(db))
            with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
                w = _enabled_writer(db)
                try:
                    _write_system_event(w, event_origin=_ORGAN)
                finally:
                    w.close()
            con = sqlite3.connect(str(db))
            try:
                con.execute("DROP TRIGGER turns_no_update")
                con.execute(
                    "UPDATE turns SET event_origin='forged_organ' "
                    "WHERE event_origin IS NOT NULL"
                )
                con.commit()
            finally:
                con.close()
            violations = chain.verify_chain(_select_star(db))
        self.assertTrue(
            violations,
            "a forged event_origin verified clean — attribution is "
            "outside the tamper-evidence",
        )
        self.assertTrue(
            any(v["reason"] == "chain-hash-mismatch" for v in violations)
        )

    @_needs_enabled_writer
    def test_null_attribution_is_tamper_evident_too(self):
        """'No organ claimed' is itself a claim the chain covers:
        flipping NULL to a value must break verification."""
        with TemporaryDirectory(dir=_PROBE_ROOT) as tmp:
            db = Path(tmp) / "ledger.db"
            migrate.run(str(db))
            with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
                w = _enabled_writer(db)
                try:
                    _write_system_event(w)
                finally:
                    w.close()
            con = sqlite3.connect(str(db))
            try:
                con.execute("DROP TRIGGER turns_no_update")
                con.execute(
                    "UPDATE turns SET event_origin='late_claim' "
                    "WHERE turn_id != 'genesis'"
                )
                con.commit()
            finally:
                con.close()
            violations = chain.verify_chain(_select_star(db))
        self.assertTrue(
            any(v["reason"] == "chain-hash-mismatch" for v in violations)
        )


class KindContractTests(unittest.TestCase):
    """Q2/Q3: non-None ⇒ system_event; verbatim value; loud refusals."""

    #: Minimal VALID payloads per kind, taint sets from the DEFAULT map.
    _VALID_KWARGS: dict[str, dict] = {
        "user_message": {
            "taint_labels": ["owner_utterance"],
        },
        "model_reply": {
            "model_id": "m",
            "prompt_hash": "p",
            "soul_hash": "s",
            "evidence_envelope": {},
            "audit_verdict": {},
            "taint_labels": ["self_generated"],
        },
        "tool_call": {
            "action_proposal": {},
            "taint_labels": ["self_generated"],
        },
        "tool_result": {
            "parent_turn_id": "genesis",
            "taint_labels": ["tool_output"],
        },
        "daemon_cycle": {
            "model_id": "m",
            "prompt_hash": "p",
            "soul_hash": "s",
            "evidence_envelope": {},
            "audit_verdict": {},
            "taint_labels": ["self_generated"],
        },
        "approval_decision": {
            "audit_verdict": {},
            "pending_card_id": 1,
            "taint_labels": ["owner_utterance"],
        },
        "self_mod_dialog_step": {
            "audit_verdict": {},
            "self_mod_dialog_id": 1,
            "taint_labels": ["owner_utterance", "self_generated"],
        },
        "peer_message_in": {
            "taint_labels": ["third_party"],
        },
        "peer_message_out": {
            "evidence_envelope": {},
            "audit_verdict": {},
            "taint_labels": ["self_generated"],
        },
    }

    @_needs_enabled_writer
    def test_system_event_stores_the_organ_name_verbatim(self):
        """No trim, no case-fold, no aliasing — the registry precedent."""
        odd = "  Recall_Receipt v2 (shadow)  "
        with TemporaryDirectory(dir=_PROBE_ROOT) as tmp:
            db = Path(tmp) / "ledger.db"
            migrate.run(str(db))
            with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
                w = _enabled_writer(db)
                try:
                    _write_system_event(w, event_origin=odd)
                finally:
                    w.close()
            rows = _select_star(db)
        self.assertEqual(rows[1]["event_origin"], odd)

    @_needs_enabled_writer
    def test_every_other_kind_refuses_an_origin_naming_kind_and_field(self):
        with TemporaryDirectory(dir=_PROBE_ROOT) as tmp:
            db = Path(tmp) / "ledger.db"
            migrate.run(str(db))
            with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
                w = _enabled_writer(db)
                try:
                    for kind, kwargs in self._VALID_KWARGS.items():
                        with self.subTest(turn_kind=kind):
                            with self.assertRaises(ValueError) as caught:
                                w.write_turn(
                                    kind,
                                    "some bytes",
                                    privacy_access="public",
                                    event_origin=_ORGAN,
                                    **kwargs,
                                )
                            msg = str(caught.exception)
                            self.assertIn("event_origin", msg)
                            self.assertIn(kind, msg)
                finally:
                    w.close()
            # Refusals wrote nothing: genesis only.
            self.assertEqual(len(_select_star(db)), 1)

    @_needs_enabled_writer
    def test_none_is_the_only_spelling_of_no_organ(self):
        """'' / whitespace / non-str refuse — under preimage inclusion
        an empty string would be a second, forgeable encoding of
        'nobody'."""
        with TemporaryDirectory(dir=_PROBE_ROOT) as tmp:
            db = Path(tmp) / "ledger.db"
            migrate.run(str(db))
            with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
                w = _enabled_writer(db)
                try:
                    for bad in ("", "   ", 7, b"organ"):
                        with self.subTest(value=repr(bad)):
                            with self.assertRaises(ValueError) as caught:
                                _write_system_event(w, event_origin=bad)
                            self.assertIn(
                                "event_origin", str(caught.exception)
                            )
                finally:
                    w.close()
            self.assertEqual(len(_select_star(db)), 1)


class DeadLetterPassthroughTests(unittest.TestCase):
    """The never-silent contract carries attribution with the payload."""

    @_needs_enabled_writer
    def test_a_failed_enabled_write_dead_letters_the_origin(self):
        with TemporaryDirectory(dir=_PROBE_ROOT) as tmp:
            # Deliberately UNMIGRATED: construction succeeds (pragmas
            # only), the write fails at the head-pointer read, and the
            # payload must land in the sidecar with its kwargs intact.
            db = Path(tmp) / "unmigrated.db"
            with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
                result = try_write_turn(
                    str(db),
                    "system_event",
                    _ORGAN_BYTES,
                    event_origin=_ORGAN,
                    taint_labels=["self_generated"],
                    privacy_access="public",
                )
            self.assertIsNone(result)
            sidecars = list(Path(tmp).glob("unmigrated.db.deadletter.*.jsonl"))
            self.assertTrue(sidecars, "the loss was silent")
            records = [
                json.loads(line)
                for line in sidecars[0].read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["kwargs"].get("event_origin"), _ORGAN)


class ReplayCausationTests(unittest.TestCase):
    """Q4: the causation predicate compares event_origin vs None default."""

    def _committed_row(self, tmp: str) -> Path:
        db = Path(tmp) / "ledger.db"
        migrate.run(str(db))
        with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
            w = _enabled_writer(db)
            try:
                _write_system_event(
                    w,
                    event_origin=_ORGAN,
                    submission_id="sid-causation",
                    submitted_at=123.0,
                )
            finally:
                w.close()
        return db

    def _envelope(self, **kwargs_extra) -> dict:
        kw = {
            "surface": "system",
            "privacy_access": "public",
            "taint_labels": ["self_generated"],
        }
        kw.update(kwargs_extra)
        return {
            "submission_id": "sid-causation",
            "submitted_at": 123.0,
            "turn_kind": "system_event",
            "raw_text": _ORGAN_BYTES,
            "kwargs": kw,
        }

    @_needs_enabled_writer
    def test_an_envelope_blind_to_the_origin_is_not_ours(self):
        from core.ledger.dead_letter_replay import _row_is_our_replay

        with TemporaryDirectory(dir=_PROBE_ROOT) as tmp:
            db = self._committed_row(tmp)
            ours, why = _row_is_our_replay(str(db), self._envelope())
        self.assertFalse(
            ours,
            "a committed row carrying an organ name was claimed by an "
            "envelope that never asserted one — a check that skips "
            "what it cannot see is not a check",
        )
        self.assertIn("event_origin", why)

    @_needs_enabled_writer
    def test_a_matching_envelope_is_ours_and_a_differing_one_is_not(self):
        from core.ledger.dead_letter_replay import _row_is_our_replay

        with TemporaryDirectory(dir=_PROBE_ROOT) as tmp:
            db = self._committed_row(tmp)
            ours_match, _ = _row_is_our_replay(
                str(db), self._envelope(event_origin=_ORGAN)
            )
            ours_diff, why = _row_is_our_replay(
                str(db), self._envelope(event_origin="another_organ")
            )
        self.assertTrue(ours_match)
        self.assertFalse(ours_diff)
        self.assertIn("event_origin", why)


class SpoolDoorResidualTests(unittest.TestCase):
    """The NAMED residual: the door passes event_origin, deliberately.

    A producer envelope asserting an organ name is the same trust class
    as the free-form surface/raw_surface labels the door already
    passes: honest-producer evidence, verified nowhere at this door.
    Refusing it as authority was executed into a wall (replay refuses
    stranded authority kwargs → organ dead-letters become permanently
    unreplayable; the web /chat S4 closure records from a NON-OWNER
    process whose only custody is this spool). This test DOCUMENTS the
    pass-through; it must not be read as a boundary.
    """

    def test_the_door_passes_event_origin_and_the_digest_covers_it(self):
        with TemporaryDirectory(dir=_PROBE_ROOT) as tmp:
            root = Path(tmp) / "ledger_spool"
            sid = spool.enqueue(
                str(root),
                producer="web_owner",
                turn_kind="system_event",
                raw_text=_ORGAN_BYTES,
                kwargs={
                    "event_origin": _ORGAN,
                    "taint_labels": ["self_generated"],
                    "privacy_access": "public",
                },
            )
            pending = root / "web_owner" / "pending" / f"{sid}.json"
            envelope = json.loads(pending.read_text(encoding="utf-8"))
        self.assertEqual(envelope["kwargs"].get("event_origin"), _ORGAN)
        self.assertNotIn(
            "event_origin",
            spool._AUTHORITY_KWARGS,
            "the twenty-first round ruled event_origin STAYS "
            "spool-expressible (2-1); making it authority strands "
            "organ attribution on every non-owner mouth closure — "
            "revisit the round before changing this",
        )


class ReaderExposureTests(unittest.TestCase):
    """Q5: span_reader exposure is a CONTRACT, not a SELECT * accident;
    the prompt-feeding reader is deliberately not widened."""

    @_needs_enabled_writer
    def test_span_reader_rows_carry_event_origin(self):
        from core.ledger.span_reader import read_span

        with TemporaryDirectory(dir=_PROBE_ROOT) as tmp:
            db = Path(tmp) / "ledger.db"
            migrate.run(str(db))
            with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
                w = _enabled_writer(db)
                try:
                    _write_system_event(w, event_origin=_ORGAN)
                finally:
                    w.close()
            result = read_span(str(db), after_chain_position=-1)
            by_kind = {r["turn_kind"]: r for r in result.rows}
        self.assertEqual(
            by_kind["system_event"]["event_origin"],
            _ORGAN,
        )

    def test_recent_turns_is_deliberately_not_widened(self):
        """Deferred BY NAME (twenty-first round, Codex dissent
        recorded): that SELECT feeds the prompt's self_history builder
        and prompt-content changes are the OWNER's call — the same
        line that left the owed submitted_at unselected. This test
        goes red when someone widens it, so the widening must cite an
        owner ruling."""
        import inspect

        from core.ledger import recent_turns

        src = inspect.getsource(recent_turns)
        self.assertNotIn(
            "event_origin",
            src,
            "recent_turns_by_kind grew event_origin exposure — that is "
            "a prompt-adjacent change reserved for the owner (twenty-"
            "first round Q5); revert or cite the owner's ruling",
        )


class TaintCouplingPinTests(unittest.TestCase):
    """The twentieth round's carried regression: the taint-caller
    coupling is REMOVED by the dedicated column, and no caller override
    may ever key on an organ label."""

    def test_the_caller_override_inventory_is_frozen(self):
        self.assertEqual(
            set(CALLER_ALLOWED_TAINT_LABEL_SETS),
            {("user_message", "x6_rehearsal")},
            "a new caller override appeared; a human must confirm it "
            "does not key on an event_origin organ label (owner ruling "
            "2026-08-27: the coupling is removed, not pinned around)",
        )

    @_needs_enabled_writer
    def test_taint_admission_is_invariant_to_event_origin(self):
        """The organ name must never feed the taint caller lookup:
        admission outcomes are identical with and without it."""
        with TemporaryDirectory(dir=_PROBE_ROOT) as tmp:
            db = Path(tmp) / "ledger.db"
            migrate.run(str(db))
            with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
                w = _enabled_writer(db)
                try:
                    # Admitted without an origin ⇒ admitted with one,
                    # including an origin string that COLLIDES with the
                    # one registered override caller name.
                    for origin in (None, _ORGAN, "x6_rehearsal"):
                        with self.subTest(origin=origin):
                            kw = {}
                            if origin is not None:
                                kw["event_origin"] = origin
                            self.assertIsNotNone(
                                _write_system_event(w, **kw)
                            )
                    # Refused without an origin ⇒ refused with one.
                    from core.ledger.taint_stamping import (
                        TaintStampingRefusal,
                    )

                    for kw in ({}, {"event_origin": _ORGAN}):
                        with self.subTest(refusal_with=kw):
                            with self.assertRaises(TaintStampingRefusal):
                                w.write_turn(
                                    "system_event",
                                    _ORGAN_BYTES,
                                    taint_labels=["owner_utterance"],
                                    privacy_access="public",
                                    **kw,
                                )
                finally:
                    w.close()


if __name__ == "__main__":
    unittest.main()
