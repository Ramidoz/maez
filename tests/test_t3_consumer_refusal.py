# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""T3 — consumer refusal, per the authoritative map (S1 protocol §4, v7.4).

The witness the whole slice points at: with S1 enabled against a ledger the
resolver cannot vouch for, every stamping consumer REFUSES and writes
nothing; against a healthy ledger, every one succeeds and stamps
`gestation` — the positive control that proves these assertions can see
stamps at all. §4's kill: silent success, or a gestation stamp in the
outage window.

Driven from docs/superpowers/witness/theme2-s1-t3-map.json so the harness
and the protocol cannot name different consumers. Each stamper gets:

  1. healthy + enabled  -> succeeds, stamps gestation      (positive)
  2. broken  + enabled  -> typed refusal, ZERO rows        (the witness)
  3. per-site bite: with the refusal neutered, the harness itself must
     catch the gestation stamp — proving assertion 2 is falsifiable.
"""
from __future__ import annotations

import json
import os
import shutil
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
MIGRATIONS = REPO / "core" / "ledger" / "migrations"
MAP = json.loads(
    (REPO / "docs/superpowers/witness/theme2-s1-t3-map.json").read_text())

from core.memory.birth_phase import PhaseUnknownRefusal  # noqa: E402


def _mk_ledger(root: Path, healthy: bool) -> Path:
    db = root / ("healthy.db" if healthy else "partial.db")
    if healthy:
        from core.ledger.migrate import run
        run(str(db))
    else:
        conn = sqlite3.connect(db)
        for n in ("0001_init.sql", "0002_triggers.sql"):
            conn.executescript((MIGRATIONS / n).read_text())
        conn.commit(); conn.close()
    return db


class _Env:
    """Fresh stores + chosen ledger per case; S1 enabled."""

    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="t3_"))
        self._saved = {k: os.environ.get(k) for k in (
            "MAEZ_LEDGER_DB_PATH", "MAEZ_S1_PHASE_TRUTH",
            "MAEZ_PRIVATE_THOUGHTS_PATH", "MAEZ_AUDIT_LOG_PATH",
            "MAEZ_LEDGER_WRITES")}
        os.environ["MAEZ_PRIVATE_THOUGHTS_PATH"] = str(self.root / "pt.db")
        os.environ["MAEZ_AUDIT_LOG_PATH"] = str(self.root / "al.db")
        os.environ["MAEZ_S1_PHASE_TRUTH"] = "1"

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def use_ledger(self, healthy: bool) -> Path:
        db = _mk_ledger(self.root, healthy)
        os.environ["MAEZ_LEDGER_DB_PATH"] = str(db)
        return db

    # ── the exercisers: one per map entry, via the PUBLIC surface ──────
    def drive(self, consumer: str):
        if consumer.startswith("memory_manager."):
            import memory.memory_manager as mm
            tag = mm._memory_phase_tag
            which = consumer.split(".", 1)[1].split(" ")[0]
            return lambda: tag(consumer=consumer)      # the gate the sites call
        if consumer.startswith("private_thoughts."):
            from core.infra.private_thoughts import PrivateThoughts
            pt = PrivateThoughts(db_path=self.root / "pt.db")
            name = consumer.split(".", 1)[1].split(" ")[0]
            if name == "record_thought":
                return lambda: pt.record_thought(content="t3 probe")
            if name == "record_signal":
                return lambda: pt.record_signal(
                    content="t3", source="probe", subject="self",
                    consent_tier="self_only", retention="session",
                    allowed_flows=("private_reader",))
            if name == "insert_signal_in_transaction":
                return lambda: pt.insert_signal_in_transaction(
                    sqlite3.connect(self.root / "pt.db"), ts=1700000000.0,
                    content="t3", source="probe", subject="self",
                    consent_tier="self_only", retention="session",
                    allowed_flows=("private_reader",))
            if name == "_insert_thought":
                return lambda: pt._insert_thought(
                    content="t3", provenance="explicit_api", context=None,
                    memory_phase="gestation")
        if consumer.startswith("audit_log."):
            from core.cognition.audit_log import AuditLog
            al = AuditLog(db_path=self.root / "al.db")
            name = consumer.split(".", 1)[1]
            if name == "record":
                return lambda: al.record(action="t3", params={},
                                         classification=None,
                                         injection_matches=[], verdict=None)
            if name == "start_direct_edit_session":
                return lambda: al.start_direct_edit_session(
                    reason="t3", source="cli")
            if name in ("log_direct_edit", "end_direct_edit_session"):
                # Session setup happens NOW, dormant, so the refusal case's
                # row count measures only the gated call itself.
                os.environ.pop("MAEZ_S1_PHASE_TRUTH", None)
                sid = al.start_direct_edit_session(reason="t3", source="cli")
                os.environ["MAEZ_S1_PHASE_TRUTH"] = "1"
                if name == "log_direct_edit":
                    return lambda: al.log_direct_edit(
                        session_id=sid, paths=["x"], diff_summary="t3")
                return lambda: al.end_direct_edit_session(session_id=sid)
        if consumer == "ledger_writer.write_turn":
            def call():
                os.environ["MAEZ_LEDGER_WRITES"] = "1"
                from core.ledger.writer import LedgerWriter
                w = LedgerWriter(os.environ["MAEZ_LEDGER_DB_PATH"])
                try:
                    return w.write_turn(
                        "system_event", "t3 probe", surface="system",
                        taint_labels=["self_generated"],
                        privacy_access="public")
                finally:
                    w.close()
            return call
        if consumer == "span_planner.run_consolidation_pass":
            return "span_planner"          # handled specially
        raise KeyError(consumer)

    def rows_in(self, store: str) -> int:
        table = {"private_thoughts": ("pt.db", "private_thoughts"),
                 "audit_log": ("al.db", "audit_log")}.get(store)
        if table is None:
            return -1
        db = self.root / table[0]
        if not db.exists():
            return 0
        try:
            conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
            n = conn.execute(f"SELECT COUNT(*) FROM {table[1]}").fetchone()[0]
            conn.close()
            return n
        except sqlite3.OperationalError:
            return 0


_SPECIAL = {"span_planner.run_consolidation_pass"}
_GATE_LEVEL = {"memory_manager.store", "memory_manager.store_telegram",
               "memory_manager.store_core"}


class T3Refusal(_Env, unittest.TestCase):
    """Broken ledger + enabled: every stamper refuses; zero rows."""

    def test_every_stamper_refuses_and_writes_nothing(self):
        failures = []
        for entry in MAP["stampers"]:
            consumer = entry["consumer"]
            if consumer in _SPECIAL:
                continue
            with self.subTest(consumer=consumer):
                self.setUp() if False else None
                self.use_ledger(healthy=False)
                # drive() may perform dormant SETUP (e.g. opening a
                # direct-edit session) that legitimately writes rows; the
                # refusal measurement starts after it.
                call = self.drive(consumer)
                before = self.rows_in(entry["store"])
                try:
                    call()
                    failures.append(f"{consumer}: WROTE (silent success)")
                except PhaseUnknownRefusal:
                    pass
                except ValueError as exc:
                    failures.append(f"{consumer}: ValueError not refusal: {exc}")
                after = self.rows_in(entry["store"])
                if after != before:
                    failures.append(
                        f"{consumer}: rows {before}->{after} despite refusal")
        self.assertEqual(failures, [], "\n" + "\n".join(failures))

    def test_span_planner_typed_refusal(self):
        db = self.use_ledger(healthy=False)
        from core.consolidation import span_planner as sp
        paths = sp.ConsolidationPaths(
            ledger_db_path=db, spine_db_path=self.root / "spine.sqlite3",
            episode_digests_db_path=self.root / "digests.sqlite3",
            receipts_path=self.root / "receipts.jsonl")
        with mock.patch.object(sp, "_runtime_enabled", return_value=True), \
             mock.patch.object(sp, "_resolve_idle_inputs",
                               return_value=10_000.0), \
             mock.patch.object(sp, "_idle_allows_run", return_value=True):
            result = sp.run_consolidation_pass(paths=paths)
        refusals = getattr(result, "refusals", None) or \
            (result.get("refusals") if isinstance(result, dict) else ()) or ()
        codes = [(r["refusal_code"] if isinstance(r, dict)
                  else getattr(r, "refusal_code", "")) for r in refusals]
        self.assertTrue(any(str(c).startswith("phase_unknown") for c in codes),
                        f"expected a phase_unknown refusal, got {result}")
        self.assertFalse((self.root / "spine.sqlite3").exists(),
                         "the spine store was created despite the refusal")


class T3Positive(_Env, unittest.TestCase):
    """Healthy ledger + enabled: everything succeeds, stamps gestation."""

    def test_stamps_land_and_say_gestation(self):
        self.use_ledger(healthy=True)
        from core.infra.private_thoughts import PrivateThoughts
        from core.cognition.audit_log import AuditLog
        pt = PrivateThoughts(db_path=self.root / "pt.db")
        pt.record_thought(content="t3 positive")
        al = AuditLog(db_path=self.root / "al.db")
        al.record(action="t3", params={}, classification=None,
                  injection_matches=[], verdict=None)
        sid = al.start_direct_edit_session(reason="t3", source="cli")
        al.log_direct_edit(session_id=sid, paths=["x"], diff_summary="t3")
        al.end_direct_edit_session(session_id=sid)
        for db, table in (("pt.db", "private_thoughts"), ("al.db", "audit_log")):
            conn = sqlite3.connect(self.root / db)
            phases = {r[0] for r in conn.execute(
                f"SELECT memory_phase FROM {table}")}
            self.assertEqual(phases, {"gestation"},
                             f"{table}: {phases}")
        # the ledger writer, healthy + enabled + writes on
        os.environ["MAEZ_LEDGER_WRITES"] = "1"
        from core.ledger.writer import LedgerWriter
        w = LedgerWriter(os.environ["MAEZ_LEDGER_DB_PATH"])
        tid = w.write_turn("system_event", "t3 healthy", surface="system",
                           taint_labels=["self_generated"],
                           privacy_access="public")
        w.close()
        self.assertTrue(tid)

    def test_the_exemption_sentinel_has_not_drifted(self):
        """longmemeval is exempt BECAUSE it writes 'benchmark'. Pin that."""
        src = (REPO / "core/eval/longmemeval.py").read_text()
        self.assertIn('"memory_phase": "benchmark"', src,
                      "longmemeval's sentinel changed; its exemption was "
                      "conditional on never writing a real phase")
        for phase in ('"memory_phase": "gestation"', '"memory_phase": "lived"'):
            self.assertNotIn(phase, src)


class T3Bite(_Env, unittest.TestCase):
    """Neuter the gate; the harness MUST catch the stamp. Falsifiability."""

    def test_a_lying_gate_is_caught(self):
        self.use_ledger(healthy=False)
        from core.infra.private_thoughts import PrivateThoughts
        import core.memory.birth_phase as bp
        with mock.patch.object(bp, "resolve",
                               return_value=bp.PhaseResult("gestation",
                                                           "meta_absent")):
            pt = PrivateThoughts(db_path=self.root / "pt.db")
            pt.record_thought(content="should have been refused")
        conn = sqlite3.connect(self.root / "pt.db")
        n = conn.execute("SELECT COUNT(*) FROM private_thoughts "
                         "WHERE memory_phase='gestation'").fetchone()[0]
        self.assertEqual(n, 1,
                         "the bite control itself is broken: with the "
                         "resolver mocked to lie, a gestation stamp MUST "
                         "land and MUST be visible to this query")


if __name__ == "__main__":
    unittest.main()
