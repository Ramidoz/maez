# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""A3 slice 2 — the recorder seam (twenty-second round, folded 3-0).

The ONE universal contract for every mouth: attempt custody; classify
durably if possible; make loss loud; egress regardless. This file pins
the seam that carries it:

  * a TYPED, IDENTITY-BEARING result — DORMANT | COMMITTED(turn_id) |
    CUSTODY(submission_id, producer) | DEAD_LETTERED(attempt_id,
    category) | LOST(attempt_id). CUSTODY is the twenty-second round's
    fold: the twentieth round's four states were read off
    try_write_turn alone, and both custody lanes (pause, spool) are
    shipped rulings it never probed.
  * routing INSIDE the seam by the full three-condition precedent:
    non-owner process -> spool; commits paused -> spool; parent held
    only as a submission id -> spool (a child must not
    owner-direct-write before its parent drains).
  * producer = the real conversation surface. Never the organ, never
    owner_daemon for interceptor speech, never blank — and the
    empty-producer class is swept upstream (_producer_dirs refuses).
  * the type cannot express "don't write": recorder=None raises; the
    production default is a module singleton identity-pinned on BOTH
    public methods; dormancy is a RESULT, not a different recorder.
  * event_origin is REQUIRED at record_organ_event — the seam is the
    first caller that KNOWS it records organ output (the twenty-first
    round's permitted-not-required lands here).
  * never-silent: seam misuse with a payload dead-letters as
    category=refused and the reply ships; custody failure dead-letters
    (closing the executed pause-lane hole where enqueue failure was
    LOST with no artifact); LOST only when even the dead-letter append
    fails, at CRITICAL.
  * the flag gates BEFORE any residue: spool.enqueue never reads
    MAEZ_LEDGER_WRITES, so an ungated seam would grow a pre-birth pile
    that drains as life on flip.

Latency posture (stated, zero code): one synchronous recording
attempt; no recorder-added retries or sleeps; never raises on the
record path; NOT hard latency-bounded.

Model-generated speech is NAMED OUT: persist_model_reply is the
shipped model-speech recorder; this seam records only the two ruled
canned shapes.
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
from core.ledger import migrate, owner, recorder, spool
from core.ledger.recorder import (
    PRODUCTION,
    ProductionRecorder,
    RecordResult,
    RecordState,
    RehearsalRecorder,
    record_organ_event,
    record_owner_message,
    recorder_status,
)

_needs_enabled_writer = unittest.skipUnless(
    has_wal_reset_fix(),
    "an enabled ledger writer requires SQLite >= 3.51.3 "
    "(run with LD_LIBRARY_PATH=vendor/sqlite/lib)",
)

_PROBE_ROOT = "/var/tmp"

_SURFACE = "telegram_text"
_ORGAN = "s4_crisis"
_OWNER_BYTES = "I keep forgetting things and it scares me"
_ORGAN_BYTES = "You are not alone. I am here with you."


def _rows(db: Path | str) -> list[dict]:
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        con.row_factory = sqlite3.Row
        return [
            dict(r)
            for r in con.execute(
                "SELECT * FROM turns WHERE turn_id != 'genesis' "
                "ORDER BY chain_position"
            )
        ]
    finally:
        con.close()


def _pending_envelopes(db: Path | str) -> list[tuple[str, dict]]:
    """(producer, envelope) for every pending spool submission."""
    root = Path(spool.default_spool_root(str(db)))
    out = []
    for p in sorted(root.glob("*/pending/*.json")):
        out.append((p.parent.parent.name, json.loads(p.read_text())))
    return out


class _Env:
    """Scratch canonical ledger + env patch, owner state restored."""

    def __init__(self, tmp: str, *, migrated: bool = True) -> None:
        self.db = Path(tmp) / "ledger.db"
        if migrated:
            migrate.run(str(self.db))
        self._patch = patch.dict(
            os.environ,
            {
                "MAEZ_LEDGER_DB_PATH": str(self.db),
                "MAEZ_LEDGER_WRITES": "1",
            },
        )

    def __enter__(self) -> "_Env":
        self._patch.__enter__()
        return self

    def __exit__(self, *exc) -> None:
        owner._reset_for_tests()
        os.environ.pop("MAEZ_LEDGER_COMMITS_PAUSED", None)
        self._patch.__exit__(*exc)


class ResultTypeTests(unittest.TestCase):
    """The typed result: five states, no sixth, no skip — and it cannot
    state contradictions (Codex boundary walk B3)."""

    def test_the_result_cannot_state_contradictions(self):
        cases = (
            dict(state=RecordState.COMMITTED),  # committed without a turn
            dict(state=RecordState.COMMITTED, turn_id="t",
                 submission_id="s"),  # two identities
            dict(state=RecordState.CUSTODY),  # custody without a sid
            dict(state=RecordState.CUSTODY, submission_id="s",
                 producer="web_owner", turn_id="t"),  # custody + turn
            dict(state=RecordState.DEAD_LETTERED),  # no attempt identity
            dict(state=RecordState.LOST),  # no attempt identity
            dict(state=RecordState.DORMANT, turn_id="t"),  # dormant + id
            dict(state="committed", turn_id="t"),  # raw string state
        )
        for kwargs in cases:
            with self.subTest(kwargs=kwargs):
                with self.assertRaises((ValueError, TypeError)):
                    RecordResult(**kwargs)

    def test_the_states_are_exactly_five(self):
        self.assertEqual(
            {s.name for s in RecordState},
            {"DORMANT", "COMMITTED", "CUSTODY", "DEAD_LETTERED", "LOST"},
            "the twenty-second round folded EXACTLY one state (CUSTODY) "
            "onto the twentieth round's four — widening again needs its "
            "own fold trace",
        )

    def test_a_none_recorder_raises_before_any_backend_call(self):
        for fn, kwargs in (
            (record_owner_message, dict(surface=_SURFACE, raw_text=_OWNER_BYTES)),
            (
                record_organ_event,
                dict(
                    surface=_SURFACE,
                    event_origin=_ORGAN,
                    raw_text=_ORGAN_BYTES,
                ),
            ),
        ):
            with self.subTest(fn=fn.__name__):
                with self.assertRaises(TypeError):
                    fn(recorder=None, **kwargs)


class DormancyTests(unittest.TestCase):
    """The flag gates BEFORE any residue — dormancy is exact."""

    def test_dormant_seam_returns_dormant_and_leaves_zero_residue(self):
        with TemporaryDirectory(dir=_PROBE_ROOT) as tmp:
            db = Path(tmp) / "ledger.db"
            with patch.dict(
                os.environ, {"MAEZ_LEDGER_DB_PATH": str(db)}
            ):
                os.environ.pop("MAEZ_LEDGER_WRITES", None)
                r1 = record_owner_message(
                    surface=_SURFACE, raw_text=_OWNER_BYTES
                )
                r2 = record_organ_event(
                    surface=_SURFACE,
                    event_origin=_ORGAN,
                    raw_text=_ORGAN_BYTES,
                    parent=r1,
                )
            self.assertEqual(r1.state, RecordState.DORMANT)
            self.assertEqual(r2.state, RecordState.DORMANT)
            leftovers = sorted(str(p) for p in Path(tmp).rglob("*"))
            self.assertEqual(
                leftovers, [],
                "a dormant seam left residue — pre-birth piles drain as "
                f"life on flip: {leftovers}",
            )


class OwnerLaneTests(unittest.TestCase):
    """The owner-direct lane: COMMITTED with identity, threading, and
    the classified refusal path."""

    @_needs_enabled_writer
    def test_both_shapes_commit_with_identity_and_a_parent_edge(self):
        with TemporaryDirectory(dir=_PROBE_ROOT) as tmp, _Env(tmp) as env:
            owner.claim_ownership(str(env.db))
            r1 = record_owner_message(surface=_SURFACE, raw_text=_OWNER_BYTES)
            r2 = record_organ_event(
                surface=_SURFACE,
                event_origin=_ORGAN,
                raw_text=_ORGAN_BYTES,
                parent=r1,
            )
            rows = _rows(env.db)
        self.assertEqual(r1.state, RecordState.COMMITTED)
        self.assertEqual(r2.state, RecordState.COMMITTED)
        self.assertEqual(len(rows), 2)
        owner_row, organ_row = rows
        self.assertEqual(owner_row["turn_id"], r1.turn_id)
        self.assertEqual(owner_row["turn_kind"], "user_message")
        self.assertEqual(owner_row["raw_text"], _OWNER_BYTES)
        self.assertEqual(owner_row["surface"], _SURFACE)
        self.assertEqual(
            json.loads(owner_row["taint_labels_json"]), ["owner_utterance"]
        )
        self.assertIsNone(owner_row["event_origin"])
        self.assertTrue(
            owner_row["submission_id"],
            "the committed row must carry the pre-minted identity",
        )
        self.assertEqual(organ_row["turn_kind"], "system_event")
        self.assertEqual(organ_row["raw_text"], _ORGAN_BYTES)
        self.assertEqual(organ_row["event_origin"], _ORGAN)
        self.assertEqual(
            organ_row["parent_turn_id"], r1.turn_id,
            "the organ row hangs off the owner's turn by turn edge on "
            "the owner lane",
        )

    @_needs_enabled_writer
    def test_a_blank_origin_dead_letters_as_refused_and_ships(self):
        with TemporaryDirectory(dir=_PROBE_ROOT) as tmp, _Env(tmp) as env:
            owner.claim_ownership(str(env.db))
            result = record_organ_event(
                surface=_SURFACE,
                event_origin="   ",
                raw_text=_ORGAN_BYTES,
            )
            self.assertEqual(result.state, RecordState.DEAD_LETTERED)
            self.assertEqual(result.category, "refused")
            self.assertEqual(_rows(env.db), [])
            sidecars = list(Path(tmp).glob("ledger.db.deadletter.*.jsonl"))
            self.assertTrue(sidecars, "the refusal was silent")
            record = json.loads(
                sidecars[0].read_text(encoding="utf-8").splitlines()[0]
            )
        self.assertEqual(record["event_id"], result.attempt_id)
        self.assertEqual(record["category"], "refused")

    @_needs_enabled_writer
    def test_a_paused_owner_takes_custody_under_the_surface_producer(self):
        with TemporaryDirectory(dir=_PROBE_ROOT) as tmp, _Env(tmp) as env:
            owner.claim_ownership(str(env.db))
            os.environ["MAEZ_LEDGER_COMMITS_PAUSED"] = "1"
            result = record_organ_event(
                surface=_SURFACE,
                event_origin=_ORGAN,
                raw_text=_ORGAN_BYTES,
            )
            envelopes = _pending_envelopes(env.db)
            self.assertEqual(_rows(env.db), [])
        self.assertEqual(result.state, RecordState.CUSTODY)
        self.assertEqual(result.producer, _SURFACE)
        self.assertEqual(len(envelopes), 1)
        producer, env_payload = envelopes[0]
        self.assertEqual(
            producer, _SURFACE,
            "interceptor speech mailboxes under the SURFACE, not "
            "owner_daemon — one conversation, one mailbox",
        )
        self.assertEqual(env_payload["submission_id"], result.submission_id)
        self.assertEqual(env_payload["kwargs"].get("event_origin"), _ORGAN)
        self.assertEqual(env_payload["raw_text"], _ORGAN_BYTES)

    @_needs_enabled_writer
    def test_a_custody_parent_routes_the_child_to_the_spool(self):
        """Third routing condition: a child holding only a submission id
        must not owner-direct-write before its parent drains."""
        with TemporaryDirectory(dir=_PROBE_ROOT) as tmp, _Env(tmp) as env:
            owner.claim_ownership(str(env.db))
            custody_parent = RecordResult(
                state=RecordState.CUSTODY,
                submission_id="sid-parent",
                producer=_SURFACE,
            )
            result = record_organ_event(
                surface=_SURFACE,
                event_origin=_ORGAN,
                raw_text=_ORGAN_BYTES,
                parent=custody_parent,
            )
            envelopes = _pending_envelopes(env.db)
            self.assertEqual(_rows(env.db), [])
        self.assertEqual(result.state, RecordState.CUSTODY)
        self.assertEqual(len(envelopes), 1)
        self.assertEqual(
            envelopes[0][1]["parent_submission_id"], "sid-parent"
        )

    @_needs_enabled_writer
    def test_a_failed_parent_record_never_withholds_the_child(self):
        """Half-recorded exchanges, ruled by name: record what you
        have, thread what you can, never refuse."""
        with TemporaryDirectory(dir=_PROBE_ROOT) as tmp, _Env(tmp) as env:
            owner.claim_ownership(str(env.db))
            dead_parent = RecordResult(
                state=RecordState.DEAD_LETTERED,
                attempt_id="a1",
                category="failed",
            )
            result = record_organ_event(
                surface=_SURFACE,
                event_origin=_ORGAN,
                raw_text=_ORGAN_BYTES,
                parent=dead_parent,
            )
            rows = _rows(env.db)
        self.assertEqual(result.state, RecordState.COMMITTED)
        self.assertEqual(len(rows), 1)
        self.assertIsNone(
            rows[0]["parent_turn_id"],
            "record-without-join: the organ row lands unparented",
        )


class NonOwnerLaneTests(unittest.TestCase):
    """The non-owner lane IS the spool — never a latch collision."""

    @_needs_enabled_writer
    def test_a_non_owner_process_takes_custody_without_touching_the_latch(self):
        with TemporaryDirectory(dir=_PROBE_ROOT) as tmp, _Env(tmp) as env:
            from core.ledger.writer import LedgerWriter

            holder = LedgerWriter(str(env.db))  # the daemon's posture
            try:
                os.environ.pop("MAEZ_LEDGER_OWNER_PID", None)
                result = record_organ_event(
                    surface="web_owner",
                    event_origin=_ORGAN,
                    raw_text=_ORGAN_BYTES,
                )
                envelopes = _pending_envelopes(env.db)
                sidecars = list(
                    Path(tmp).glob("ledger.db.deadletter.*.jsonl")
                )
            finally:
                holder.close()
        self.assertEqual(result.state, RecordState.CUSTODY)
        self.assertEqual(
            sidecars, [],
            "the non-owner lane dead-lettered instead of taking spool "
            "custody — that is pure replay debt by construction",
        )
        self.assertEqual(len(envelopes), 1)
        self.assertEqual(envelopes[0][0], "web_owner")

    @_needs_enabled_writer
    def test_a_blank_origin_on_the_custody_lane_dead_letters_at_the_seam(self):
        """The seam check is load-bearing HERE: on the spool lane the
        writer's own validation only runs at drain, so without the
        fail-closed seam a blank origin would take custody and
        quarantine later instead of refusing now."""
        with TemporaryDirectory(dir=_PROBE_ROOT) as tmp, _Env(tmp) as env:
            os.environ.pop("MAEZ_LEDGER_OWNER_PID", None)
            result = record_organ_event(
                surface="web_owner",
                event_origin="",
                raw_text=_ORGAN_BYTES,
            )
            self.assertEqual(result.state, RecordState.DEAD_LETTERED)
            self.assertEqual(result.category, "refused")
            self.assertEqual(
                _pending_envelopes(env.db), [],
                "a blank organ label took spool custody",
            )

    @_needs_enabled_writer
    def test_total_loss_is_named_lost_with_the_attempt_identity(self):
        """LOST: custody failed AND the dead-letter append failed. The
        one outcome with no disk artifact — named at CRITICAL."""
        with TemporaryDirectory(dir=_PROBE_ROOT) as tmp:
            jail = Path(tmp) / "jail"
            jail.mkdir()
            db = jail / "ledger.db"
            os.chmod(jail, 0o500)  # no writes: enqueue AND sidecar fail
            try:
                with patch.dict(
                    os.environ,
                    {
                        "MAEZ_LEDGER_DB_PATH": str(db),
                        "MAEZ_LEDGER_WRITES": "1",
                    },
                ):
                    os.environ.pop("MAEZ_LEDGER_OWNER_PID", None)
                    with self.assertLogs(
                        "core.ledger.recorder", level="CRITICAL"
                    ) as logs:
                        result = record_organ_event(
                            surface="web_owner",
                            event_origin=_ORGAN,
                            raw_text=_ORGAN_BYTES,
                        )
            finally:
                os.chmod(jail, 0o700)
        self.assertEqual(result.state, RecordState.LOST)
        self.assertTrue(result.attempt_id)
        self.assertTrue(any("LOST" in line for line in logs.output))

    @_needs_enabled_writer
    def test_custody_failure_dead_letters_instead_of_vanishing(self):
        """Closes the executed pause-lane hole: enqueue failure was LOST
        with zero artifacts; the seam dead-letters it."""
        with TemporaryDirectory(dir=_PROBE_ROOT) as tmp, _Env(tmp) as env:
            os.environ.pop("MAEZ_LEDGER_OWNER_PID", None)
            # Occupy the spool root path with a FILE so enqueue fails.
            Path(spool.default_spool_root(str(env.db))).write_text("x")
            result = record_organ_event(
                surface="web_owner",
                event_origin=_ORGAN,
                raw_text=_ORGAN_BYTES,
            )
            sidecars = list(Path(tmp).glob("ledger.db.deadletter.*.jsonl"))
            self.assertTrue(sidecars, "the custody failure was silent")
            record = json.loads(
                sidecars[0].read_text(encoding="utf-8").splitlines()[0]
            )
        self.assertEqual(result.state, RecordState.DEAD_LETTERED)
        self.assertEqual(result.category, "failed")
        self.assertEqual(record["event_id"], result.attempt_id)
        self.assertEqual(record["kwargs"].get("event_origin"), _ORGAN)


class BrakeRaceTests(unittest.TestCase):
    """Codex boundary walk B2: writes-off wins. A flag that flips off
    between the seam's gate and the custody enqueue must yield DORMANT
    with zero residue, not a CUSTODY envelope."""

    @_needs_enabled_writer
    def test_a_mid_call_brake_flip_yields_dormant_not_custody(self):
        with TemporaryDirectory(dir=_PROBE_ROOT) as tmp, _Env(tmp) as env:
            os.environ.pop("MAEZ_LEDGER_OWNER_PID", None)

            # The flip lands DURING routing (after the seam's gate, before
            # custody) — the exact window the walk's probe exercised. A
            # flip inside the enqueue syscall itself stays a named race no
            # pre-call check can win.
            def _flip_then_false():
                os.environ.pop("MAEZ_LEDGER_WRITES", None)
                return False

            with patch.object(
                owner, "this_process_is_owner", _flip_then_false
            ):
                result = record_organ_event(
                    surface="web_owner",
                    event_origin=_ORGAN,
                    raw_text=_ORGAN_BYTES,
                )
            self.assertEqual(result.state, RecordState.DORMANT)
            self.assertEqual(
                _pending_envelopes(env.db), [],
                "the brake lost the race: custody residue exists with "
                "the flag off",
            )


class DeadLetterEdgeTests(unittest.TestCase):
    """Codex boundary walk B3: a failed custody enqueue must not drop
    the parent edge — the dead-letter record carries it top-level
    (never inside kwargs, which must stay writer-legal for replay)."""

    @_needs_enabled_writer
    def test_failed_custody_preserves_the_parent_submission_edge(self):
        with TemporaryDirectory(dir=_PROBE_ROOT) as tmp, _Env(tmp) as env:
            os.environ.pop("MAEZ_LEDGER_OWNER_PID", None)
            Path(spool.default_spool_root(str(env.db))).write_text("x")
            parent = RecordResult(
                state=RecordState.CUSTODY,
                submission_id="sid-parent",
                producer="web_owner",
            )
            result = record_organ_event(
                surface="web_owner",
                event_origin=_ORGAN,
                raw_text=_ORGAN_BYTES,
                parent=parent,
            )
            sidecars = list(Path(tmp).glob("ledger.db.deadletter.*.jsonl"))
            self.assertTrue(sidecars)
            record = json.loads(
                sidecars[0].read_text(encoding="utf-8").splitlines()[0]
            )
        self.assertEqual(result.state, RecordState.DEAD_LETTERED)
        self.assertEqual(record.get("parent_submission_id"), "sid-parent")
        self.assertNotIn(
            "parent_submission_id", record["kwargs"],
            "the edge leaked into replay kwargs, which the writer would "
            "refuse at drain",
        )


class SpoolProducerSweepTests(unittest.TestCase):
    """The empty-producer class, swept upstream (twenty-second round):
    enqueue(producer='') published into the spool ROOT where drain
    never looks and spool_status reported pending_total=0 — custody
    that health cannot see."""

    def test_producer_dirs_refuses_blank_producers(self):
        with TemporaryDirectory(dir=_PROBE_ROOT) as tmp:
            for bad in ("", "   "):
                with self.subTest(producer=repr(bad)):
                    with self.assertRaises(ValueError):
                        spool._producer_dirs(tmp, bad)

    def test_enqueue_refuses_a_blank_producer_loudly(self):
        with TemporaryDirectory(dir=_PROBE_ROOT) as tmp:
            root = Path(tmp) / "ledger_spool"
            with self.assertRaises(ValueError):
                spool.enqueue(
                    str(root),
                    producer="",
                    turn_kind="system_event",
                    raw_text=_ORGAN_BYTES,
                    kwargs={},
                )
            self.assertEqual(
                sorted(root.rglob("*.json")) if root.exists() else [],
                [],
                "a refused enqueue still published an envelope",
            )

    @_needs_enabled_writer
    def test_the_seam_refuses_a_blank_surface_before_enqueue(self):
        with TemporaryDirectory(dir=_PROBE_ROOT) as tmp, _Env(tmp) as env:
            os.environ.pop("MAEZ_LEDGER_OWNER_PID", None)
            result = record_organ_event(
                surface="",
                event_origin=_ORGAN,
                raw_text=_ORGAN_BYTES,
            )
            self.assertEqual(result.state, RecordState.DEAD_LETTERED)
            self.assertEqual(result.category, "refused")
            self.assertEqual(_pending_envelopes(env.db), [])


class IdentityPinTests(unittest.TestCase):
    """The production default cannot be silently rebound, swapped for a
    no-op, or bypassed by dormancy."""

    def test_both_public_defaults_are_the_one_production_singleton(self):
        self.assertIs(
            record_owner_message.__kwdefaults__["recorder"], PRODUCTION
        )
        self.assertIs(
            record_organ_event.__kwdefaults__["recorder"], PRODUCTION
        )
        self.assertIs(type(PRODUCTION), ProductionRecorder)

    def test_exactly_one_production_construction_in_the_module(self):
        import inspect

        src = inspect.getsource(recorder)
        self.assertEqual(
            src.count("ProductionRecorder()"), 1,
            "a second production construction is how the wrong instance "
            "ends up in a default",
        )

    def test_an_injected_recorder_is_used_and_the_singleton_is_not(self):
        calls = []

        class _Sentinel:
            def _record(self, turn_kind, raw_text, **kwargs):
                calls.append((turn_kind, raw_text))
                return RecordResult(
                    state=RecordState.COMMITTED, turn_id="sentinel-turn"
                )

        before = dict(PRODUCTION.counts)
        result = record_organ_event(
            surface=_SURFACE,
            event_origin=_ORGAN,
            raw_text=_ORGAN_BYTES,
            recorder=_Sentinel(),
        )
        self.assertEqual(result.turn_id, "sentinel-turn")
        self.assertEqual(calls, [("system_event", _ORGAN_BYTES)])
        self.assertEqual(
            dict(PRODUCTION.counts), before,
            "the production singleton was touched by an injected call",
        )

    def test_a_dormant_flag_does_not_swap_the_default(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("MAEZ_LEDGER_WRITES", None)
            self.assertIs(
                record_owner_message.__kwdefaults__["recorder"], PRODUCTION,
                "dormancy is a RESULT, not a different recorder",
            )


class RehearsalInjectionTests(unittest.TestCase):
    """The ONLY way A3 can ever be rehearsed: inject a rehearsal-writer
    recorder. Real surface labels; the production singleton untouched."""

    @_needs_enabled_writer
    def test_both_ruled_shapes_rehearse_through_the_injected_recorder(self):
        with TemporaryDirectory(dir=_PROBE_ROOT) as tmp:
            root = Path(tmp) / "logs" / "rehearsal"
            db = root / "x6_recorder_seam" / "ledger.db"
            db.parent.mkdir(parents=True)
            migrate.run(str(db))
            with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
                lane = RehearsalRecorder(str(db), rehearsal_root=root)
                before = dict(PRODUCTION.counts)
                try:
                    r1 = record_owner_message(
                        surface=_SURFACE,
                        raw_text=_OWNER_BYTES,
                        recorder=lane,
                    )
                    r2 = record_organ_event(
                        surface=_SURFACE,
                        event_origin=_ORGAN,
                        raw_text=_ORGAN_BYTES,
                        parent=r1,
                        recorder=lane,
                    )
                finally:
                    lane.close()
            rows = _rows(db)
        self.assertEqual(r1.state, RecordState.COMMITTED)
        self.assertEqual(r2.state, RecordState.COMMITTED)
        self.assertEqual(dict(PRODUCTION.counts), before)
        self.assertEqual(len(rows), 2)
        self.assertEqual(
            [r["lifecycle_stage"] for r in rows],
            ["rehearsal", "rehearsal"],
        )
        self.assertEqual(rows[0]["surface"], _SURFACE)
        self.assertEqual(rows[1]["event_origin"], _ORGAN)
        self.assertEqual(rows[1]["parent_turn_id"], r1.turn_id)
        self.assertEqual(rows[1]["raw_text"], _ORGAN_BYTES)


class HealthTests(unittest.TestCase):
    """Counters + recorder_status() this slice; loss never invisible."""

    def test_recorder_status_reports_counts_and_process_scope(self):
        PRODUCTION._reset_counts_for_tests()
        with TemporaryDirectory(dir=_PROBE_ROOT) as tmp:
            db = Path(tmp) / "ledger.db"
            with patch.dict(os.environ, {"MAEZ_LEDGER_DB_PATH": str(db)}):
                os.environ.pop("MAEZ_LEDGER_WRITES", None)
                record_owner_message(surface=_SURFACE, raw_text=_OWNER_BYTES)
        status = recorder_status()
        self.assertEqual(status["pid"], os.getpid())
        self.assertEqual(status["counts"]["dormant"], 1)
        for key in ("committed", "custody", "dead_lettered", "lost"):
            self.assertEqual(status["counts"][key], 0)

    def test_cockpit_admission_block_carries_the_recorder_and_pages_on_loss(self):
        from types import SimpleNamespace

        from daemon import maez_daemon as md

        PRODUCTION._reset_counts_for_tests()
        with TemporaryDirectory(dir=_PROBE_ROOT) as tmp:
            db = Path(tmp) / "ledger.db"
            with patch.object(md, "LEDGER_DB_PATH", db), patch.dict(
                os.environ, {}, clear=False
            ):
                os.environ.pop("MAEZ_LEDGER_WRITES", None)
                block = md._ledger_admission_health(SimpleNamespace())
                self.assertIn("recorder", block)
                self.assertEqual(
                    block["recorder"]["scope"], "daemon_process",
                    "module counters are process-local; claiming more "
                    "would be false (twenty-second round)",
                )
                self.assertFalse(block["attention"])
                # A loss in THIS process pages.
                PRODUCTION.counts["lost"] += 1
                try:
                    block2 = md._ledger_admission_health(SimpleNamespace())
                finally:
                    PRODUCTION._reset_counts_for_tests()
        self.assertTrue(
            block2["attention"],
            "a LOST life-event did not page the cockpit",
        )


if __name__ == "__main__":
    unittest.main()
