# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""ACTION-Hi-1 — subscription_proxy provenance hardening.

Two leakage surfaces (audit 2026-05-04):

  1. memory/subscription_proxy.db (217 rows of partial Claude-API
     previews + prompt hashes). Not currently consumed by SFT.
  2. logs/trajectories/*.jsonl (full owner-Maez turns). Designed-
     for-distillation per skills/claude_router.py:13.

Both must carry provenance fields at write time so a future
distillation pipeline can't accidentally absorb them. Default
gate: training_eligible=0 (default-deny). Caller-allowlist filter
on the exporter.

Tests cover: schema migration, write-side defaults, idempotent
re-init, exporter filter, existing-row backfill, trajectory
provenance.
"""
from __future__ import annotations

import importlib
import json
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))


class _ProxyBase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        tmp = Path(self._tmp.name)
        self.proxy_db = tmp / "proxy.db"
        self._env = mock.patch.dict(os.environ, {
            "MAEZ_SUBSCRIPTION_PROXY_DB": str(self.proxy_db),
        })
        self._env.start()
        # Reload server so DB_PATH picks up env override.
        from core.subscription_proxy import server as _srv
        importlib.reload(_srv)
        self.srv = _srv

    def tearDown(self):
        self._env.stop()
        self._tmp.cleanup()


class SchemaHasProvenanceColumns(_ProxyBase):
    def test_provenance_columns_present_after_init(self):
        """Calling _db() materializes the table; the schema must
        include all four provenance columns added in this slice."""
        with self.srv._db() as con:
            cols = [r[1] for r in con.execute("PRAGMA table_info(calls)")]
        for required in (
            "provenance_source", "trust_tier",
            "training_eligible", "provenance_version",
        ):
            self.assertIn(
                required, cols,
                f"calls table missing provenance column {required!r}",
            )

    def test_re_init_is_idempotent(self):
        """Initializing twice (existing DB + new code path) must
        not error or produce duplicate columns."""
        with self.srv._db() as con:
            cols_first = sorted(
                r[1] for r in con.execute("PRAGMA table_info(calls)")
            )
        # Second init via fresh _db() call
        with self.srv._db() as con:
            cols_second = sorted(
                r[1] for r in con.execute("PRAGMA table_info(calls)")
            )
        self.assertEqual(cols_first, cols_second)


class WriteSideDefaults(_ProxyBase):
    def test_record_writes_default_provenance(self):
        """_record on a fresh row must default to
        provenance_source='claude_tier_response',
        trust_tier='untrusted', training_eligible=0,
        provenance_version='v1'."""
        self.srv._record(
            adapter="claude", caller="test", model="claude-sonnet-4-6",
            model_used="claude-sonnet-4-6", prompt="hi", reply="ok",
            input_toks=1, output_toks=1, duration_s=0.1, status="ok",
        )
        with self.srv._db() as con:
            row = con.execute(
                "SELECT provenance_source, trust_tier, "
                "training_eligible, provenance_version "
                "FROM calls WHERE caller = 'test'"
            ).fetchone()
        self.assertIsNotNone(row)
        ps, tt, te, pv = row
        self.assertEqual(ps, "claude_tier_response")
        self.assertEqual(tt, "untrusted")
        self.assertEqual(te, 0)
        self.assertEqual(pv, "v1")


class RecordCannotBypassEligible(_ProxyBase):
    """REGRESSION GUARD: ``_record`` does not accept a
    ``training_eligible`` kwarg — every INSERT hard-codes 0 at the
    SQL site so no caller (including any future producer wiring
    new adapters) can flip the gate via the public function."""

    def test_record_signature_omits_training_eligible(self):
        import inspect
        sig = inspect.signature(self.srv._record)
        self.assertNotIn(
            "training_eligible", sig.parameters,
            "_record must NOT accept training_eligible as a kwarg "
            "— it's hard-coded to 0 at the INSERT site",
        )

    def test_record_writes_zero_eligible_always(self):
        self.srv._record(
            adapter="claude", caller="hopeful_caller",
            model="x", model_used="x", prompt="p", reply="r",
            input_toks=1, output_toks=1, duration_s=0.1, status="ok",
        )
        with self.srv._db() as con:
            row = con.execute(
                "SELECT training_eligible FROM calls "
                "WHERE caller = 'hopeful_caller'"
            ).fetchone()
        self.assertEqual(row[0], 0)


class ExistingRowBackfill(_ProxyBase):
    def test_pre_existing_rows_get_default_provenance_on_migrate(self):
        """Simulate a pre-Hi-1 DB by hand: a row inserted via the
        original schema (no provenance columns). After re-init
        through _db(), the row's provenance fields must populate
        with the SQLite column defaults."""
        # Create row by raw INSERT mimicking the old schema; rely
        # on ALTER TABLE adding columns with DEFAULT to backfill.
        con = sqlite3.connect(str(self.proxy_db))
        con.execute(
            """
            CREATE TABLE calls (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                ts              REAL    NOT NULL,
                adapter         TEXT    NOT NULL,
                caller          TEXT    NOT NULL,
                model           TEXT    NOT NULL,
                model_used      TEXT,
                prompt_hash     TEXT    NOT NULL,
                prompt_chars    INTEGER NOT NULL,
                reply_chars     INTEGER NOT NULL,
                input_toks      INTEGER,
                output_toks     INTEGER,
                duration_s      REAL    NOT NULL,
                status          TEXT    NOT NULL,
                prompt_preview  TEXT,
                reply_preview   TEXT,
                error_preview   TEXT
            )
            """
        )
        con.execute(
            "INSERT INTO calls (ts, adapter, caller, model, "
            "prompt_hash, prompt_chars, reply_chars, duration_s, "
            "status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (1.0, "claude", "longmemeval-judge", "x", "abc", 10, 5, 0.1, "ok"),
        )
        con.commit()
        con.close()

        # Re-init through server module; ALTER must run.
        with self.srv._db() as con:
            row = con.execute(
                "SELECT provenance_source, trust_tier, "
                "training_eligible, provenance_version "
                "FROM calls WHERE caller = 'longmemeval-judge'"
            ).fetchone()
        self.assertIsNotNone(row)
        ps, tt, te, pv = row
        self.assertEqual(ps, "claude_tier_response")
        self.assertEqual(tt, "untrusted")
        self.assertEqual(te, 0)
        self.assertEqual(pv, "v1")


class ExporterGuard(_ProxyBase):
    """REGRESSION GUARD for [ACTION-Hi-1] sub-task 3: exporter must
    refuse untagged rows, default-deny, and require an explicit
    caller allowlist."""

    def test_exporter_with_no_explicit_eligible_rows_returns_empty(self):
        """training_eligible defaults to 0; without any explicit
        opt-in, the exporter returns nothing even when there are
        rows."""
        self.srv._record(
            adapter="claude", caller="self_dev/review_module",
            model="x", model_used="x", prompt="p", reply="r",
            input_toks=1, output_toks=1, duration_s=0.1, status="ok",
        )
        out = self.srv.training_eligible_calls()
        self.assertEqual(out, [])

    def test_exporter_default_allowlist_excludes_longmemeval_and_selfdev(self):
        """Even if a future operator manually flips
        training_eligible=1 for a longmemeval-judge or self_dev/*
        row, the default allowlist still excludes them — caller-
        side filter is belt-and-suspenders."""
        # Insert + flip training_eligible=1 manually
        with self.srv._db() as con:
            for caller in ("longmemeval-judge", "self_dev/review_module",
                           "self_dev/propose_tests"):
                con.execute(
                    "INSERT INTO calls (ts, adapter, caller, model, "
                    "prompt_hash, prompt_chars, reply_chars, duration_s, "
                    "status, training_eligible) "
                    "VALUES (?, 'claude', ?, 'x', 'h', 1, 1, 0.1, 'ok', 1)",
                    (1.0, caller),
                )
            con.commit()
        out = self.srv.training_eligible_calls()
        callers = {r["caller"] for r in out}
        self.assertNotIn("longmemeval-judge", callers)
        self.assertNotIn("self_dev/review_module", callers)
        self.assertNotIn("self_dev/propose_tests", callers)

    def test_exporter_with_explicit_allowlist_returns_only_listed(self):
        """A caller explicitly named in the allowlist AND with
        training_eligible=1 gets through."""
        with self.srv._db() as con:
            con.execute(
                "INSERT INTO calls (ts, adapter, caller, model, "
                "prompt_hash, prompt_chars, reply_chars, duration_s, "
                "status, training_eligible) "
                "VALUES (1.0, 'claude', 'blessed-caller', 'x', 'h', "
                "1, 1, 0.1, 'ok', 1)"
            )
            con.execute(
                "INSERT INTO calls (ts, adapter, caller, model, "
                "prompt_hash, prompt_chars, reply_chars, duration_s, "
                "status, training_eligible) "
                "VALUES (1.0, 'claude', 'unblessed', 'x', 'h', "
                "1, 1, 0.1, 'ok', 1)"
            )
            con.commit()
        out = self.srv.training_eligible_calls(
            allowlist={"blessed-caller"},
        )
        callers = {r["caller"] for r in out}
        self.assertEqual(callers, {"blessed-caller"})

    def test_exporter_skips_explicit_zero_training_eligible(self):
        """training_eligible=0 rows must never surface, regardless
        of allowlist."""
        with self.srv._db() as con:
            con.execute(
                "INSERT INTO calls (ts, adapter, caller, model, "
                "prompt_hash, prompt_chars, reply_chars, duration_s, "
                "status, training_eligible) "
                "VALUES (1.0, 'claude', 'blessed-but-not-eligible', "
                "'x', 'h', 1, 1, 0.1, 'ok', 0)"
            )
            con.commit()
        out = self.srv.training_eligible_calls(
            allowlist={"blessed-but-not-eligible"},
        )
        self.assertEqual(out, [])


class TrajectoryFileProvenance(unittest.TestCase):
    """logs/trajectories/*.jsonl is the second leakage surface.
    skills/claude_router.py:13 explicitly designs it as future
    distillation source. Every entry must carry provenance fields
    at write-time."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tdir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_log_trajectory_writes_provenance_fields(self):
        """Every entry written by skills.claude_router.log_trajectory
        must carry provenance_source, trust_tier, training_eligible,
        provenance_version. Default values live in the function
        itself; callers can override per-entry for explicit local
        vs external routing."""
        from skills import claude_router as cr
        with mock.patch.object(cr, "TRAJECTORY_DIR", self.tdir):
            cr.log_trajectory({
                "profile_id": "owner",
                "channel": "test",
                "message": "hi",
                "reply": "ok",
                "source": "local",
            })
        # Find the file created
        files = list(self.tdir.glob("*.jsonl"))
        self.assertEqual(len(files), 1)
        with files[0].open() as f:
            entry = json.loads(f.readline())
        for required in (
            "provenance_source", "trust_tier",
            "training_eligible", "provenance_version",
        ):
            self.assertIn(
                required, entry,
                f"trajectory entry missing {required!r}",
            )

    def test_local_source_defaults_to_own_voice_untrusted(self):
        """source='local' rows are Maez's own voice. Default to
        trust_tier='own_voice' (informational, not free pass) and
        training_eligible=0 (explicit gate still required to
        consume)."""
        from skills import claude_router as cr
        with mock.patch.object(cr, "TRAJECTORY_DIR", self.tdir):
            cr.log_trajectory({
                "profile_id": "owner", "channel": "test",
                "message": "hi", "reply": "ok",
                "source": "local",
            })
        with next(self.tdir.glob("*.jsonl")).open() as f:
            entry = json.loads(f.readline())
        self.assertEqual(entry["provenance_source"], "local_maez")
        self.assertEqual(entry["trust_tier"], "own_voice")
        self.assertEqual(entry["training_eligible"], 0)

    def test_external_source_defaults_to_untrusted(self):
        """source='external' rows are full Claude-API responses.
        These are the higher-risk path (stranger brain absorption);
        must default trust_tier='untrusted', training_eligible=0."""
        from skills import claude_router as cr
        with mock.patch.object(cr, "TRAJECTORY_DIR", self.tdir):
            cr.log_trajectory({
                "profile_id": "owner", "channel": "test",
                "message": "hi", "reply": "ok",
                "source": "external",
                "decision": {"route": "external", "tier": "sonnet"},
            })
        with next(self.tdir.glob("*.jsonl")).open() as f:
            entry = json.loads(f.readline())
        self.assertEqual(entry["provenance_source"], "claude_external")
        self.assertEqual(entry["trust_tier"], "untrusted")
        self.assertEqual(entry["training_eligible"], 0)

    def test_caller_can_override_provenance_source_and_trust_tier(self):
        """A caller may pre-set ``provenance_source`` and
        ``trust_tier`` (own_voice / blessed / etc.). Useful for a
        future trusted producer that wants to label its own voice
        explicitly without monkey-patching the helper."""
        from skills import claude_router as cr
        with mock.patch.object(cr, "TRAJECTORY_DIR", self.tdir):
            cr.log_trajectory({
                "profile_id": "owner", "channel": "test",
                "message": "hi", "reply": "ok",
                "source": "local",
                "trust_tier": "explicitly_blessed",
            })
        with next(self.tdir.glob("*.jsonl")).open() as f:
            entry = json.loads(f.readline())
        self.assertEqual(entry["trust_tier"], "explicitly_blessed")

    def test_caller_CANNOT_override_training_eligible(self):
        """REGRESSION GUARD for reviewer Major M1: ``training_eligible``
        is hard-set to 0 in log_trajectory regardless of caller
        input. A buggy or compromised producer cannot bypass the
        default-deny gate by pre-setting this key in the entry
        dict. Opt-in MUST flow through a separate operator-reviewed
        audit path."""
        from skills import claude_router as cr
        with mock.patch.object(cr, "TRAJECTORY_DIR", self.tdir):
            cr.log_trajectory({
                "profile_id": "owner", "channel": "test",
                "message": "hi", "reply": "ok",
                "source": "local",
                "training_eligible": 1,  # caller's bypass attempt
            })
        with next(self.tdir.glob("*.jsonl")).open() as f:
            entry = json.loads(f.readline())
        self.assertEqual(
            entry["training_eligible"], 0,
            "training_eligible must be hard-set to 0 by "
            "log_trajectory, not setdefault — caller cannot bypass "
            "the default-deny gate",
        )


if __name__ == "__main__":
    unittest.main()
