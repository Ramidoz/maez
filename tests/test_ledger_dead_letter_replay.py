# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Dead-letter replay organ — classification half (read-only).

Council rulings 2026-08-24: replay by IDENTITY with explicit
reconstruction provenance (canon governs canon); refused-class records
are evidence, never blind re-submissions. This file pins the
classifier, which never writes anything:

  already_committed  — a live row carries this record's identity. The
                       write DID land; the failure was classified after
                       the commit. Never replay.
  refused_evidence   — a deterministic writer refusal. Evidence forever;
                       re-submitting bytes the door refused would invert
                       the refusal.
  already_enqueued   — a replay envelope for this identity is already in
                       the spool (pending/acked/refused). Never a second
                       one; overwriting a filename races an in-flight
                       drain.
  possibly_committed — no identity match, but a byte-identical row of
                       the same kind exists within a timestamp window.
                       Withheld for owner review: this is the
                       timeout-after-commit shape.
  replayable         — everything else.
  torn               — an unparseable/truncated line (the last line of a
                       SIGKILLed writer). Reported, never guessed at.

The (kind, raw_text) match is a SIGNAL, not identity: the owner saying
"ok" twice is two lives, and withholding one loses speech — an equal
crime to duplicating it, with a different victim. So a byte match
OUTSIDE the window flags but stays replayable.
"""
from __future__ import annotations

import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ["MAEZ_TEST_MODE"] = "1"
_TEST_DIR = tempfile.mkdtemp(prefix="maez_test_dl_replay_")

from core.ledger import migrate, spool  # noqa: E402
from core.ledger import owner as ledger_owner  # noqa: E402


def tearDownModule():
    import shutil
    shutil.rmtree(_TEST_DIR, ignore_errors=True)


def _fresh(name: str) -> str:
    base = Path(_TEST_DIR) / f"{name}_{os.urandom(4).hex()}"
    base.mkdir()
    db = str(base / "ledger.db")
    migrate.run(db)
    return db


def _write_record(db: str, **overrides) -> dict:
    """Append one dead-letter record exactly as writer._dead_letter does."""
    record = {
        "event_id": overrides.pop("event_id", os.urandom(8).hex()),
        "ts": overrides.pop("ts", time.time()),
        "pid": 4242,
        "stage": "write",
        "category": overrides.pop("category", "failed"),
        "turn_kind": overrides.pop("turn_kind", "user_message"),
        "raw_text": overrides.pop("raw_text", "an omitted life"),
        "kwargs": overrides.pop("kwargs", {
            "surface": "web_owner",
            "taint_labels": ["owner_utterance"],
            "privacy_access": "public",
        }),
        "error": "OSError('disk went away')",
    }
    record.update(overrides)
    path = Path(f"{db}.deadletter.4242.jsonl")
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, sort_keys=True) + "\n")
    return record


def _classify(db: str):
    from core.ledger import dead_letter_replay

    return dead_letter_replay.classify(db)


def _by_id(report: dict) -> dict:
    return {r["event_id"]: r for r in report["records"]}


class ClassifierTests(unittest.TestCase):
    def setUp(self):
        ledger_owner._reset_for_tests()
        self.addCleanup(ledger_owner._reset_for_tests)

    def test_plain_failed_record_is_replayable(self):
        db = _fresh("replayable")
        rec = _write_record(db)
        report = _classify(db)
        self.assertEqual(
            _by_id(report)[rec["event_id"]]["disposition"], "replayable"
        )
        self.assertEqual(report["counts"]["replayable"], 1)

    def test_refused_record_is_evidence_never_replayable(self):
        db = _fresh("refused")
        rec = _write_record(db, category="refused",
                            error="ValueError('bad provenance')")
        report = _classify(db)
        self.assertEqual(
            _by_id(report)[rec["event_id"]]["disposition"], "refused_evidence"
        )

    def test_identity_match_in_db_is_already_committed(self):
        """The timeout-after-commit case, now EXACT: owner writes persist
        their attempt identity, so the record's event_id is on the row."""
        db = _fresh("committed")
        rec = _write_record(db)
        with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
            ledger_owner.claim_ownership()
            ledger_owner.owner_write_turn(
                db, "user_message", rec["raw_text"],
                surface="web_owner",
                submission_id=rec["event_id"],
                taint_labels=["owner_utterance"],
                privacy_access="public",
            )
        row = _by_id(_classify(db))[rec["event_id"]]
        self.assertEqual(row["disposition"], "already_committed")
        self.assertTrue(row.get("turn_id"))

    def test_byte_twin_inside_window_is_withheld_for_review(self):
        db = _fresh("twin_window")
        rec = _write_record(db)
        with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
            ledger_owner.claim_ownership()
            # A row with the same bytes, no matching identity, committed
            # essentially at the same moment.
            ledger_owner.owner_write_turn(
                db, "user_message", rec["raw_text"],
                surface="web_owner",
                taint_labels=["owner_utterance"],
                privacy_access="public",
            )
        row = _by_id(_classify(db))[rec["event_id"]]
        self.assertEqual(row["disposition"], "possibly_committed")

    def test_byte_twin_outside_window_stays_replayable_but_flagged(self):
        """Two legitimately identical lives ("ok" twice, days apart) must
        not silently lose the second one."""
        db = _fresh("twin_old")
        with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
            ledger_owner.claim_ownership()
            ledger_owner.owner_write_turn(
                db, "user_message", "ok",
                surface="web_owner",
                taint_labels=["owner_utterance"],
                privacy_access="public",
            )
        rec = _write_record(db, raw_text="ok", ts=time.time() + 86400)
        row = _by_id(_classify(db))[rec["event_id"]]
        self.assertEqual(row["disposition"], "replayable")
        self.assertTrue(
            row.get("byte_twin_exists"),
            "the twin must be FLAGGED even when it does not withhold",
        )

    def test_existing_spool_envelope_is_already_enqueued(self):
        db = _fresh("enqueued")
        rec = _write_record(db)
        spool.enqueue_reconstructed(
            spool.default_spool_root(db),
            submission_id=rec["event_id"],
            submitted_at=rec["ts"],
            producer="dead_letter_replay",
            turn_kind=rec["turn_kind"],
            raw_text=rec["raw_text"],
            kwargs=dict(rec["kwargs"]),
        )
        row = _by_id(_classify(db))[rec["event_id"]]
        self.assertEqual(row["disposition"], "already_enqueued")

    def test_torn_final_line_is_reported_never_guessed(self):
        db = _fresh("torn")
        _write_record(db)
        with Path(f"{db}.deadletter.4242.jsonl").open("a") as fh:
            fh.write('{"event_id": "half-writ')
        report = _classify(db)
        self.assertEqual(report["counts"]["torn"], 1)
        self.assertEqual(report["counts"]["replayable"], 1)

    def test_classify_never_writes_anything(self):
        db = _fresh("readonly")
        _write_record(db)
        before = Path(db).stat().st_mtime_ns
        _classify(db)
        self.assertEqual(Path(db).stat().st_mtime_ns, before)
        self.assertFalse(
            Path(spool.default_spool_root(db)).exists(),
            "classification is a pure read — it must not even create dirs",
        )

    def test_duplicate_event_id_across_pid_files_is_one_record(self):
        """Same identity in two sidecars (a redrive that failed twice)
        must not become two replays."""
        db = _fresh("dupe_ids")
        rec = _write_record(db)
        other = Path(f"{db}.deadletter.9999.jsonl")
        other.write_text(json.dumps({**rec, "pid": 9999}, sort_keys=True) + "\n")
        report = _classify(db)
        self.assertEqual(len(report["records"]), 1)
        self.assertEqual(report["counts"]["replayable"], 1)


class CodexValidationTests(unittest.TestCase):
    """Codex council seat (2026-08-24) on the shipped classifier. Its
    strongest attack: the classifier converted UNVERIFIED db state into
    ABSENT and then called the record replayable — so an APPLY built on
    top would duplicate committed life exactly when the organ knows
    least."""

    def setUp(self):
        ledger_owner._reset_for_tests()
        self.addCleanup(ledger_owner._reset_for_tests)

    def test_unreadable_db_is_unverified_never_replayable(self):
        db = _fresh("unverified")
        rec = _write_record(db)
        # A file that opens as SQLite but cannot be queried.
        Path(db).write_bytes(b"not a database, but it exists" * 8)
        row = _by_id(_classify(db))[rec["event_id"]]
        self.assertEqual(
            row["disposition"], "unverified",
            "DB state that cannot be read is UNKNOWN, not ABSENT — "
            "replaying here could duplicate committed life",
        )

    def test_missing_db_is_unverified_not_replayable(self):
        db = _fresh("nodb")
        rec = _write_record(db)
        Path(db).unlink()
        row = _by_id(_classify(db))[rec["event_id"]]
        self.assertEqual(row["disposition"], "unverified")

    def test_divergent_duplicate_ids_are_an_identity_conflict(self):
        db = _fresh("conflict")
        rec = _write_record(db, raw_text="version A")
        other = Path(f"{db}.deadletter.9999.jsonl")
        other.write_text(json.dumps(
            {**rec, "pid": 9999, "raw_text": "version B",
             "category": "refused"}, sort_keys=True) + "\n")
        row = _by_id(_classify(db))[rec["event_id"]]
        self.assertEqual(
            row["disposition"], "identity_conflict",
            "two DIFFERENT payloads under one identity are evidence, "
            "never a silent first-file-wins replay",
        )

    def test_unknown_category_is_not_replayable(self):
        db = _fresh("unknown_cat")
        rec = _write_record(db, category="something_new")
        row = _by_id(_classify(db))[rec["event_id"]]
        self.assertEqual(row["disposition"], "unknown_category")

    def test_missing_category_is_not_replayable(self):
        db = _fresh("no_cat")
        rec = _write_record(db)
        path = Path(f"{db}.deadletter.4242.jsonl")
        env = json.loads(path.read_text().splitlines()[0])
        env.pop("category")
        path.write_text(json.dumps(env, sort_keys=True) + "\n")
        row = _by_id(_classify(db))[rec["event_id"]]
        self.assertEqual(row["disposition"], "unknown_category")

    def test_mixed_timestamp_types_never_raise(self):
        db = _fresh("mixed_ts")
        _write_record(db, ts=1.0)
        _write_record(db, ts="2026-01-01T00:00:00")
        try:
            report = _classify(db)
        except Exception as exc:  # noqa: BLE001 — that is the defect
            self.fail(f"classify must never raise; got {exc!r}")
        self.assertEqual(len(report["records"]), 2)

    def test_same_identity_under_another_producer_is_already_enqueued(self):
        """An envelope carrying this identity anywhere in the spool means
        the submission is published; the producer label is not a
        namespace."""
        db = _fresh("cross_producer")
        rec = _write_record(db)
        spool.enqueue_reconstructed(
            spool.default_spool_root(db),
            submission_id=rec["event_id"],
            submitted_at=rec["ts"],
            producer="web_owner",
            turn_kind=rec["turn_kind"],
            raw_text=rec["raw_text"],
            kwargs=dict(rec["kwargs"]),
        )
        row = _by_id(_classify(db))[rec["event_id"]]
        self.assertEqual(row["disposition"], "already_enqueued")

    def test_reconstruction_seam_is_not_public_api(self):
        """'private reconstruction seam' must be mechanism, not prose:
        it accepts arbitrary identity, lived time, producer and parent,
        so it must not sit in the module's public surface."""
        self.assertNotIn("enqueue_reconstructed", spool.__all__)


if __name__ == "__main__":
    unittest.main()
