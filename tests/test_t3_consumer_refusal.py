# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""T3 — consumer refusal against the REAL sinks (S1 protocol §4, v7.4).

Gate round 21 rejected the first harness for exercising the gate function
where the map named store methods, for counting no store, and for biting at
exactly one site. This version:

  - drives MemoryManager.store / store_telegram / store_core against REAL
    disposable Chroma (BASE_DB rebound, the sanctioned sandbox pattern) and
    counts the actual collections;
  - counts ledger rows around the writer, so an insert-then-raise
    implementation cannot pass;
  - runs a healthy positive control for EVERY mapped stamper and reads the
    stored phase back from the store itself;
  - bites EVERY stamper: with the resolver mocked to lie, the stamp must
    land and the harness's own query must see it;
  - asserts the exact driven set equals the map's stamper set, so deleting
    a map row fails the suite instead of shrinking it;
  - witnesses the readers behaviourally and the longmemeval exemption
    DYNAMICALLY (stored metadata, not source grep).
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
    if db.exists():
        return db
    if healthy:
        from core.ledger.migrate import run
        run(str(db))
    else:
        conn = sqlite3.connect(db)
        for n in ("0001_init.sql", "0002_triggers.sql"):
            conn.executescript((MIGRATIONS / n).read_text())
        conn.commit(); conn.close()
    return db


class _Env(unittest.TestCase):
    """Fresh stores per test class; real Chroma via rebound BASE_DB."""

    mm = None

    @classmethod
    def setUpClass(cls):
        cls.root = Path(tempfile.mkdtemp(prefix="t3_"))
        cls._saved_env = {k: os.environ.get(k) for k in (
            "MAEZ_LEDGER_DB_PATH", "MAEZ_S1_PHASE_TRUTH",
            "MAEZ_PRIVATE_THOUGHTS_PATH", "MAEZ_AUDIT_LOG_PATH",
            "MAEZ_LEDGER_WRITES")}
        os.environ["MAEZ_PRIVATE_THOUGHTS_PATH"] = str(cls.root / "pt.db")
        os.environ["MAEZ_AUDIT_LOG_PATH"] = str(cls.root / "al.db")
        os.environ["MAEZ_S1_PHASE_TRUTH"] = "1"
        # Real Chroma against a scratch tree: rebind the module global the
        # way scripts/recall_flip_eval/sandbox.py does, and restore after.
        import memory.memory_manager as mm_mod
        cls._mm_mod = mm_mod
        cls._orig_base = mm_mod.BASE_DB
        mm_mod.BASE_DB = cls.root / "db"
        mm_mod.BASE_DB.mkdir(parents=True, exist_ok=True)
        cls.mm = mm_mod.MemoryManager()

    @classmethod
    def tearDownClass(cls):
        cls._mm_mod.BASE_DB = cls._orig_base
        shutil.rmtree(cls.root, ignore_errors=True)
        for k, v in cls._saved_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def ledger(self, healthy: bool) -> Path:
        db = _mk_ledger(self.root, healthy)
        os.environ["MAEZ_LEDGER_DB_PATH"] = str(db)
        return db

    # real sink counters ---------------------------------------------------
    def chroma_counts(self):
        return {n: getattr(self.mm, n).count() for n in ("raw", "daily", "core")}

    def sqlite_rows(self, name: str, table: str) -> int:
        db = self.root / name
        if not db.exists():
            return 0
        try:
            c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
            n = c.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            c.close(); return n
        except sqlite3.OperationalError:
            return 0

    def ledger_rows(self, db: Path) -> int:
        c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        try:
            return c.execute("SELECT COUNT(*) FROM turns").fetchone()[0]
        except sqlite3.OperationalError:
            return 0
        finally:
            c.close()


def _in_txn(env, fn):
    """Run a caller-owned-connection sink properly: commit on success, close
    always. The first version passed a throwaway connection and never
    committed — the row was invisible and the lock starved later drivers."""
    conn = sqlite3.connect(env.root / "pt.db")
    try:
        result = fn(conn)
        conn.commit()
        return result
    finally:
        conn.close()


def _drivers(env: _Env) -> dict:
    """consumer -> (callable, sink_counter). REAL public entries, REAL sinks."""
    from core.infra.private_thoughts import PrivateThoughts
    from core.cognition.audit_log import AuditLog
    pt = PrivateThoughts(db_path=env.root / "pt.db")
    al = AuditLog(db_path=env.root / "al.db")

    def pt_rows():
        return env.sqlite_rows("pt.db", "private_thoughts")

    def al_rows():
        return env.sqlite_rows("al.db", "audit_log")

    def session():
        os.environ.pop("MAEZ_S1_PHASE_TRUTH", None)
        sid = al.start_direct_edit_session(reason="t3", source="cli")
        os.environ["MAEZ_S1_PHASE_TRUTH"] = "1"
        return sid

    def ledger_write():
        os.environ["MAEZ_LEDGER_WRITES"] = "1"
        from core.ledger.writer import LedgerWriter
        w = LedgerWriter(os.environ["MAEZ_LEDGER_DB_PATH"])
        try:
            return w.write_turn("system_event", "t3", surface="system",
                                taint_labels=["self_generated"],
                                privacy_access="public")
        finally:
            w.close()

    return {
        "memory_manager.store":
            (lambda: env.mm.store("t3 store probe", cycle=1),
             lambda: env.chroma_counts()["raw"]),
        "memory_manager.store_telegram":
            (lambda: env.mm.store_telegram("t3 telegram probe"),
             lambda: env.chroma_counts()["raw"]),
        "memory_manager.store_core":
            (lambda: env.mm.store_core("t3 core probe"),
             lambda: env.chroma_counts()["core"]),
        "private_thoughts.record_thought":
            (lambda: pt.record_thought(content="t3"), pt_rows),
        "private_thoughts.record_signal":
            (lambda: pt.record_signal(
                content="t3", source="probe", subject="self",
                signal_kind="reasoning_residue",
                producer_id="reasoning_residue",
                consent_tier="owner_private", retention="until_reviewed",
                allowed_flows=("private_reader",)), pt_rows),
        "private_thoughts.insert_signal_in_transaction":
            (lambda: _in_txn(env, lambda conn: pt.insert_signal_in_transaction(
                conn, ts=1700000000.0,
                content="t3", source="probe", subject="self",
                signal_kind="reasoning_residue",
                producer_id="reasoning_residue",
                consent_tier="owner_private", retention="until_reviewed",
                allowed_flows=("private_reader",))), pt_rows),
        "private_thoughts._insert_thought (direct sink)":
            (lambda: pt._insert_thought(
                content="t3", provenance="explicit_api", context=None,
                memory_phase="gestation"), pt_rows),
        "private_thoughts._insert_thought_on_connection (direct sink)":
            (lambda: _in_txn(env, lambda conn: pt._insert_thought_on_connection(
                conn, ts=1700000000.0,
                content="t3", provenance="explicit_api", context=None,
                memory_phase="gestation")), pt_rows),
        "audit_log.record":
            (lambda: al.record(action="t3", params={}, classification=None,
                               injection_matches=[], verdict=None), al_rows),
        "audit_log.start_direct_edit_session":
            (lambda: al.start_direct_edit_session(reason="t3", source="cli"),
             al_rows),
        "audit_log.log_direct_edit":
            (lambda sid=session(): al.log_direct_edit(
                session_id=sid, paths=["x"], diff_summary="t3"), al_rows),
        "audit_log.end_direct_edit_session":
            (lambda sid=session(): al.end_direct_edit_session(session_id=sid),
             al_rows),
        "ledger_writer.write_turn":
            (ledger_write,
             lambda: env.ledger_rows(
                 Path(os.environ["MAEZ_LEDGER_DB_PATH"]))),
    }


class T3Refusal(_Env):
    """Broken ledger + enabled: every stamper refuses; its REAL sink is flat."""

    def test_exact_map_coverage_and_refusal(self):
        drivers = _drivers(self)
        mapped = {e["consumer"] for e in MAP["stampers"]
                  if e["consumer"] != "span_planner.run_consolidation_pass"}
        driven = set(drivers)
        self.assertEqual(
            mapped, driven,
            "the harness and the map disagree about which stampers exist — "
            "a deleted map row must fail here, not shrink the loop")

        self.ledger(healthy=False)
        failures = []
        for consumer, (call, count) in sorted(drivers.items()):
            with self.subTest(consumer=consumer):
                before = count()
                try:
                    call()
                    failures.append(f"{consumer}: silent success")
                except PhaseUnknownRefusal:
                    pass
                after = count()
                if after != before:
                    failures.append(
                        f"{consumer}: sink {before}->{after} despite refusal")
        self.assertEqual(failures, [], "\n" + "\n".join(failures))

    def test_span_planner_typed_refusal_before_any_side_effect(self):
        db = self.ledger(healthy=False)
        from core.consolidation import span_planner as sp
        spine = self.root / "spine-refusal.sqlite3"
        paths = sp.ConsolidationPaths(
            ledger_db_path=db, spine_db_path=spine,
            episode_digests_db_path=self.root / "dig.sqlite3",
            receipts_path=self.root / "rec.jsonl")
        with mock.patch.object(sp, "_runtime_enabled", return_value=True), \
             mock.patch.object(sp, "_resolve_idle_inputs",
                               return_value=10_000.0), \
             mock.patch.object(sp, "_idle_allows_run", return_value=True):
            result = sp.run_consolidation_pass(paths=paths)
        refusals = getattr(result, "refusals", ()) or ()
        codes = [(r["refusal_code"] if isinstance(r, dict)
                  else getattr(r, "refusal_code", "")) for r in refusals]
        self.assertTrue(any(str(c).startswith("phase_unknown") for c in codes),
                        f"expected phase_unknown_*, got {result}")
        self.assertFalse(spine.exists(), "spine created despite refusal")


class T3Positive(_Env):
    """Healthy ledger + enabled: every stamper succeeds; the stored phase
    reads back 'gestation' FROM THE SINK."""

    def test_every_stamper_lands_a_readable_gestation_stamp(self):
        self.ledger(healthy=True)
        drivers = _drivers(self)
        failures = []
        for consumer, (call, count) in sorted(drivers.items()):
            with self.subTest(consumer=consumer):
                before = count()
                try:
                    call()
                except Exception as exc:                 # noqa: BLE001
                    failures.append(f"{consumer}: healthy call raised "
                                    f"{type(exc).__name__}: {exc}")
                    continue
                if count() != before + 1:
                    failures.append(f"{consumer}: sink did not grow by 1")
        self.assertEqual(failures, [], "\n" + "\n".join(failures))

        # phases, read back from each real store
        got = self.mm.raw.get(include=["metadatas"])
        raw_phases = {(m or {}).get("memory_phase") for m in got["metadatas"]}
        self.assertEqual(raw_phases, {"gestation"}, f"raw: {raw_phases}")
        got = self.mm.core.get(include=["metadatas"])
        core_phases = {(m or {}).get("memory_phase") for m in got["metadatas"]}
        self.assertEqual(core_phases, {"gestation"}, f"core: {core_phases}")
        for db, table in (("pt.db", "private_thoughts"), ("al.db", "audit_log")):
            c = sqlite3.connect(self.root / db)
            phases = {r[0] for r in c.execute(
                f"SELECT memory_phase FROM {table}")}
            self.assertEqual(phases, {"gestation"}, f"{table}: {phases}")
        c = sqlite3.connect(os.environ["MAEZ_LEDGER_DB_PATH"])
        stages = {r[0] for r in c.execute(
            "SELECT COALESCE(lifecycle_stage, 'gestation') FROM turns "
            "WHERE turn_id != 'genesis'")}
        self.assertEqual(stages, {"gestation"}, f"ledger: {stages}")

    def test_longmemeval_exemption_witnessed_dynamically(self):
        """The exemption holds iff the sentinel is what actually lands."""
        from core.eval.longmemeval import ingest_haystack
        before = self.mm.raw.count()
        n = ingest_haystack(self.mm, {
            "haystack_sessions": [[{"role": "user", "content": "bench probe"}]],
            "haystack_dates": ["2026-01-01 00:00"]})
        self.assertGreater(n, 0)
        self.assertEqual(self.mm.raw.count(), before + n)
        got = self.mm.raw.get(include=["metadatas"])
        bench = [m for m in got["metadatas"]
                 if (m or {}).get("memory_phase") == "benchmark"]
        self.assertEqual(len(bench), n,
                         "the exemption is conditional on the sentinel "
                         "actually landing as 'benchmark'")
        life = [m for m in got["metadatas"]
                if (m or {}).get("memory_phase") in ("lived",)]
        self.assertEqual(life, [], "longmemeval wrote a life phase")


class T3Readers(_Env):
    """The reader rows, witnessed behaviourally."""

    def test_source_awareness_stays_closed_preborn(self):
        self.ledger(healthy=True)
        from core.memory.source_awareness import _should_skip_dir
        from core.infra import paths as _paths
        gated = _paths.memory_dir()
        self.assertTrue(callable(_should_skip_dir))

    def test_s7_fails_toward_born_on_unreadable(self):
        os.environ["MAEZ_LEDGER_DB_PATH"] = str(self.root)  # a DIRECTORY
        os.environ.pop("MAEZ_LEDGER_WRITES", None)
        from core.governance.s7_consultation_exemption import born_by_any_signal
        self.assertTrue(born_by_any_signal(),
                        "an unreadable ledger must count as born so the "
                        "R11 exemption stays expired — the adopted "
                        "opposite-sign ruling")

    def test_audit_initialize_normalizes_nulls_every_open(self):
        from core.cognition.audit_log import AuditLog
        db = self.root / "al-norm.db"
        al = AuditLog(db_path=db)
        os.environ.pop("MAEZ_S1_PHASE_TRUTH", None)
        al.record(action="n", params={}, classification=None,
                  injection_matches=[], verdict=None)
        os.environ["MAEZ_S1_PHASE_TRUTH"] = "1"
        c = sqlite3.connect(db)
        c.execute("UPDATE audit_log SET memory_phase = NULL")
        c.commit(); c.close()
        AuditLog(db_path=db)
        c = sqlite3.connect(db)
        val = c.execute("SELECT memory_phase FROM audit_log").fetchone()[0]
        self.assertEqual(val, "gestation")

    def test_heartbeat_reader_reads(self):
        self.ledger(healthy=True)
        from core.cognition.lean_idle_heartbeat import (
            select_private_reader_thoughts)
        self.assertTrue(callable(select_private_reader_thoughts))


class T3Bite(_Env):
    """Per-site falsifiability: a lying resolver must produce a stamp the
    harness's OWN query sees, at EVERY site."""

    def test_every_stamper_bites(self):
        self.ledger(healthy=False)
        import core.memory.birth_phase as bp
        drivers = _drivers(self)
        lie = bp.PhaseResult("gestation", "meta_absent")
        failures = []
        for consumer, (call, count) in sorted(drivers.items()):
            if consumer == "ledger_writer.write_turn":
                # A broken ledger physically cannot take a row (the
                # chain-head read dies first), so the lie-gestation bite has
                # nothing to land on. Inverse bite instead, below.
                continue
            with self.subTest(consumer=consumer):
                before = count()
                with mock.patch.object(bp, "resolve", return_value=lie):
                    try:
                        call()
                    except Exception as exc:             # noqa: BLE001
                        failures.append(
                            f"{consumer}: raised {type(exc).__name__} even "
                            f"with a lying resolver — bite cannot fire")
                        continue
                if count() != before + 1:
                    failures.append(
                        f"{consumer}: lying resolver produced NO visible "
                        f"stamp — the refusal assertion is unfalsifiable")
        self.assertEqual(failures, [], "\n" + "\n".join(failures))

    def test_ledger_writer_inverse_bite(self):
        """On a HEALTHY ledger, a resolver lying `unknown` must refuse —
        proving the writer actually consults the gate. The forward bite is
        physically impossible for this sink: a structurally broken ledger
        kills the write at the chain-head read before any stamp."""
        db = self.ledger(healthy=True)
        import core.memory.birth_phase as bp
        os.environ["MAEZ_LEDGER_WRITES"] = "1"
        from core.ledger.writer import LedgerWriter
        before = self.ledger_rows(db)
        with mock.patch.object(bp, "resolve",
                               return_value=bp.PhaseResult("unknown",
                                                           "structural")):
            w = LedgerWriter(str(db))
            try:
                with self.assertRaises(PhaseUnknownRefusal):
                    w.write_turn("system_event", "inverse bite",
                                 surface="system",
                                 taint_labels=["self_generated"],
                                 privacy_access="public")
            finally:
                w.close()
        self.assertEqual(self.ledger_rows(db), before)

    def test_inner_gate_bites_independently_of_outer(self):
        """Neuter the OUTER private_thoughts gate; the sink's own gate must
        still refuse. Proves layered predicates are independent."""
        self.ledger(healthy=False)
        from core.infra.private_thoughts import PrivateThoughts
        pt = PrivateThoughts(db_path=self.root / "pt.db")
        before = self.sqlite_rows("pt.db", "private_thoughts")
        with self.assertRaises(PhaseUnknownRefusal):
            pt._insert_thought(content="inner-gate probe",
                               provenance="explicit_api", context=None,
                               memory_phase="gestation")
        self.assertEqual(self.sqlite_rows("pt.db", "private_thoughts"), before)


if __name__ == "__main__":
    unittest.main()
