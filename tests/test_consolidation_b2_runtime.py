# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""PHASE B part 2 tests for the dormant consolidation-spine runtime.

Pins docs/superpowers/specs/2026-07-08-consolidation-spine-v0-design.md
B2 only: flag-gated lazy runtime, span planning/progress, bounded digestion,
shadow stores, content-light receipts, and no live wondering writes.
"""
from __future__ import annotations

import json
import os
import shutil
import sqlite3
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest import mock
from unittest.mock import patch

os.environ["MAEZ_TEST_MODE"] = "1"
_TEST_ROOT = Path(tempfile.mkdtemp(prefix="maez_test_consolidation_b2_"))

from core.ledger import migrate, writer  # noqa: E402
from core.routing.brain_gateway import BrainPurpose  # noqa: E402
from core.routing.digestion_endpoint_guard import DigestionEndpointLocality  # noqa: E402


def tearDownModule():
    shutil.rmtree(_TEST_ROOT, ignore_errors=True)


_SYSTEM_STAMP = {"taint_labels": ["self_generated"], "privacy_access": "public"}
_OWNER_STAMP = {"taint_labels": ["owner_utterance"], "privacy_access": "public"}
_SEALED_OWNER_STAMP = {
    "taint_labels": ["owner_utterance"],
    "privacy_access": "sealed_adjacent",
}
_TOOL_STAMP = {"taint_labels": ["self_generated"], "privacy_access": "public"}
_TOOL_RESULT_STAMP = {"taint_labels": ["tool_output"], "privacy_access": "public"}
_WEB_TOOL_RESULT_STAMP = {
    "taint_labels": ["tool_output", "internet_derived"],
    "privacy_access": "public",
}
_PEER_STAMP = {"taint_labels": ["third_party"], "privacy_access": "public"}


def _root(name: str) -> Path:
    path = _TEST_ROOT / f"{name}_{os.urandom(4).hex()}"
    path.mkdir()
    return path


def _paths(root: Path, ledger_db: Path | None = None):
    from core.consolidation.span_planner import ConsolidationPaths

    return ConsolidationPaths(
        ledger_db_path=ledger_db or (root / "memory" / "ledger.db"),
        spine_db_path=root / "memory" / "consolidation" / "spine.sqlite3",
        episode_digests_db_path=(
            root / "memory" / "consolidation" / "episode_digests.sqlite3"
        ),
        receipts_path=root / "logs" / "consolidation_receipts.jsonl",
        live_wonderings_db_path=root / "memory" / "wonderings.db",
    )


def _fresh_ledger(root: Path, name: str = "ledger.db") -> Path:
    db = root / name
    db.parent.mkdir(parents=True, exist_ok=True)
    migrate.run(str(db))
    return db


def _write_synthetic_three_day_ledger(db: Path) -> dict[str, str]:
    ids: dict[str, str] = {}
    day = 24 * 60 * 60
    times = [
        1000.0,
        1010.0,
        1020.0,
        1030.0,
        1040.0,
        1050.0,
        1000.0 + day,
        1010.0 + day,
        1020.0 + day,
        1000.0 + (2 * day),
        1010.0 + (2 * day),
    ]
    with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}), \
         patch("core.ledger.writer.time.time") as fake_time:
        fake_time.side_effect = times
        w = writer.LedgerWriter(str(db))
        try:
            ids["prebirth"] = w.write_turn(
                "user_message",
                "gestation row that must not enter B2",
                surface="test",
                **_OWNER_STAMP,
            )
            ids["birth"] = w.write_turn(
                "system_event",
                '{"event":"birth"}',
                birth_anchor=True,
                **_SYSTEM_STAMP,
            )
            ids["owner"] = w.write_turn(
                "user_message",
                "owner day one",
                surface="test",
                **_OWNER_STAMP,
            )
            ids["sealed"] = w.write_turn(
                "user_message",
                "sealed adjacent secret",
                surface="test",
                **_SEALED_OWNER_STAMP,
            )
            ids["tool_call"] = w.write_turn(
                "tool_call",
                "run local probe",
                surface="test",
                action_proposal={"tool": "shell", "cmd": "printf hi"},
                **_TOOL_STAMP,
            )
            ids["tool_error"] = w.write_turn(
                "tool_result",
                "probe failed once",
                surface="test",
                parent_turn_id=ids["tool_call"],
                audit_verdict={"outcome": "error"},
                **_TOOL_RESULT_STAMP,
            )
            ids["tool_error_2"] = w.write_turn(
                "tool_result",
                "probe failed twice",
                surface="test",
                parent_turn_id=ids["tool_call"],
                audit_verdict={"outcome": "error"},
                **_WEB_TOOL_RESULT_STAMP,
            )
            ids["peer"] = w.write_turn(
                "peer_message_in",
                "third-party adjacent event",
                surface="test",
                **_PEER_STAMP,
            )
            ids["owner_day_two"] = w.write_turn(
                "user_message",
                "owner day two",
                surface="test",
                **_OWNER_STAMP,
            )
            ids["owner_day_three"] = w.write_turn(
                "user_message",
                "owner day three",
                surface="test",
                **_OWNER_STAMP,
            )
        finally:
            w.close()
    return ids


def _append_owner_row(db: Path, text: str) -> str:
    with patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
        w = writer.LedgerWriter(str(db))
        try:
            turn_id = w.write_turn(
                "user_message",
                text,
                surface="test",
                **_OWNER_STAMP,
            )
        finally:
            w.close()
    assert turn_id is not None
    return turn_id


def _connect(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def _table_names(path: Path) -> set[str]:
    if not path.exists():
        return set()
    conn = sqlite3.connect(path)
    try:
        return {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
    finally:
        conn.close()


def _rows(path: Path, sql: str) -> list[dict]:
    conn = _connect(path)
    try:
        return [dict(row) for row in conn.execute(sql).fetchall()]
    finally:
        conn.close()


def _jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _allowing_idle() -> dict[str, object]:
    return {
        "no_interaction_secs": 7200.0,
        "camera": "absent",
        "active_until_future": False,
        "activity_known": True,
    }


def _enabled_env() -> dict[str, str]:
    return {
        "MAEZ_LEDGER_WRITES": "1",
        "MAEZ_CONSOLIDATION_SHADOW": "1",
        "MAEZ_LLM_BACKEND": "llamacpp",
        "MAEZ_PRIMARY_BASE_URL": "http://127.0.0.1:8080",
    }


def _row_taint(row: dict) -> set[str]:
    return set(json.loads(row["taint_labels_json"]))


def _ordered_taint(labels: set[str]) -> list[str]:
    order = [
        "owner_utterance",
        "self_generated",
        "tool_output",
        "internet_derived",
        "third_party",
    ]
    return [label for label in order if label in labels]


class PromptAwareFakeLLM:
    def __init__(self, *, fail_on_sealed: bool = True):
        self.calls: list[dict] = []
        self.fail_on_sealed = fail_on_sealed

    def __call__(self, *, model, messages, stream, think=None, options=None, purpose=None):
        self.calls.append(
            {
                "model": model,
                "messages": messages,
                "stream": stream,
                "purpose": purpose,
            }
        )
        self.assert_non_stream_digestion_call(stream=stream, purpose=purpose)
        content = "\n".join(str(message.get("content", "")) for message in messages)
        if self.fail_on_sealed and "sealed adjacent secret" in content:
            raise AssertionError("sealed-adjacent raw text reached the digestion prompt")
        rows = self._prompt_rows(content)
        cited = [
            {"turn_id": row["turn_id"], "chain_position": row["chain_position"]}
            for row in rows
        ]
        labels: set[str] = set()
        for row in rows:
            labels |= _row_taint(row)
        cps = "-".join(str(row["chain_position"]) for row in rows)
        return json.dumps(
            {
                "episode_digest": f"observed chain positions {cps}",
                "row_citations": cited,
                "wondering_candidates": [
                    {
                        "text": f"what stayed unresolved around {cps}?",
                        "row_citations": cited[:1],
                        "taint_labels": _ordered_taint(_row_taint(rows[0]))
                        if rows else [],
                    }
                ] if rows else [],
            }
        )

    def assert_non_stream_digestion_call(self, *, stream, purpose) -> None:
        if stream is not False:
            raise AssertionError("digestion LLM call must be non-streaming")
        if purpose is not BrainPurpose.DIGESTION:
            raise AssertionError("digestion LLM call must use BrainPurpose.DIGESTION")

    @staticmethod
    def _prompt_rows(content: str) -> list[dict]:
        marker = "LEDGER_ROWS_JSON:\n"
        end_marker = "\nSKELETON_JSON:"
        if marker not in content or end_marker not in content:
            raise AssertionError("digestion prompt did not expose bounded row JSON")
        blob = content.split(marker, 1)[1].split(end_marker, 1)[0]
        rows = json.loads(blob)
        if not isinstance(rows, list):
            raise AssertionError("bounded row JSON must be a list")
        return rows


class ConsolidationB2GateTests(unittest.TestCase):
    def test_double_gate_off_is_fully_inert_and_creates_no_dirs_or_receipts(self):
        from core.consolidation import span_planner

        for env in (
            {"MAEZ_LEDGER_WRITES": "0", "MAEZ_CONSOLIDATION_SHADOW": "0"},
            {"MAEZ_LEDGER_WRITES": "1", "MAEZ_CONSOLIDATION_SHADOW": "0"},
            {"MAEZ_LEDGER_WRITES": "0", "MAEZ_CONSOLIDATION_SHADOW": "1"},
        ):
            root = _root("gate_off")
            paths = _paths(root)
            with self.subTest(env=env), \
                 patch.dict(os.environ, env, clear=False), \
                 patch.object(
                     span_planner.span_reader,
                     "read_span",
                     side_effect=AssertionError("flag-off must not read ledger"),
                 ):
                result = span_planner.run_consolidation_pass(
                    paths=paths,
                    idle_inputs=_allowing_idle(),
                    llm_callable=PromptAwareFakeLLM(),
                )

            self.assertEqual(result.status, "disabled")
            self.assertFalse((root / "memory").exists())
            self.assertFalse((root / "logs").exists())

    def test_shadow_run_writes_shadow_only_and_receipts_match_re_read_state(self):
        from core.consolidation.span_planner import run_consolidation_pass
        from core.evolution.wonderings import Wonderings

        root = _root("shadow_e2e")
        ledger = _fresh_ledger(root)
        ids = _write_synthetic_three_day_ledger(ledger)
        paths = _paths(root, ledger)
        paths.live_wonderings_db_path.parent.mkdir(parents=True, exist_ok=True)
        Wonderings(paths.live_wonderings_db_path).add("preexisting live wondering")
        before_live = paths.live_wonderings_db_path.read_bytes()
        fake_llm = PromptAwareFakeLLM()

        with patch.dict(os.environ, _enabled_env(), clear=False):
            first = run_consolidation_pass(
                paths=paths,
                idle_inputs=_allowing_idle(),
                llm_callable=fake_llm,
            )

        self.assertEqual(first.status, "completed")
        self.assertGreater(first.artifacts_committed, 0)
        self.assertGreater(len(fake_llm.calls), 0)
        self.assertEqual(paths.live_wonderings_db_path.read_bytes(), before_live)
        self.assertIn("episode_digest_shadow", _table_names(paths.episode_digests_db_path))
        self.assertNotIn("episode_digests", _table_names(paths.episode_digests_db_path))
        self.assertIn("shadow_wondering_candidates", _table_names(paths.spine_db_path))

        digests = _rows(
            paths.episode_digests_db_path,
            "SELECT * FROM episode_digest_shadow ORDER BY id ASC",
        )
        self.assertGreater(len(digests), 0)
        cited_turn_ids = {
            citation["turn_id"]
            for row in digests
            for citation in json.loads(row["row_citations_json"])
        }
        self.assertNotIn(ids["prebirth"], cited_turn_ids)
        self.assertNotIn(ids["sealed"], cited_turn_ids)
        self.assertIn(ids["birth"], cited_turn_ids)

        receipts = _jsonl(paths.receipts_path)
        receipt_text = "\n".join(json.dumps(row, sort_keys=True) for row in receipts)
        self.assertNotIn("observed chain positions", receipt_text)
        self.assertNotIn("what stayed unresolved", receipt_text)
        artifact_receipts = [
            row for row in receipts if row["event"] == "episode_artifact_committed"
        ]
        self.assertEqual(len(artifact_receipts), len(digests))
        self.assertEqual(
            {row["episode_key"] for row in artifact_receipts},
            {row["episode_key"] for row in digests},
        )
        state_rows = _rows(paths.spine_db_path, "SELECT key, value FROM state")
        state = {row["key"]: row["value"] for row in state_rows}
        self.assertEqual(int(state["last_digested_chain_position"]), first.high_water)

        _append_owner_row(ledger, "new owner row after first shadow pass")
        with patch.dict(os.environ, _enabled_env(), clear=False):
            second = run_consolidation_pass(
                paths=paths,
                idle_inputs=_allowing_idle(),
                llm_callable=PromptAwareFakeLLM(),
            )

        new_digests = _rows(
            paths.episode_digests_db_path,
            "SELECT * FROM episode_digest_shadow WHERE id > ? ORDER BY id ASC",
            # type: ignore[arg-type]
        ) if False else _rows(
            paths.episode_digests_db_path,
            "SELECT * FROM episode_digest_shadow ORDER BY id ASC",
        )[len(digests):]
        self.assertEqual(second.status, "completed")
        self.assertGreater(len(new_digests), 0)
        self.assertTrue(
            all(row["start_chain_position"] > first.high_water for row in new_digests)
        )

    def test_empty_span_is_noop_with_re_read_receipt_and_no_llm_call(self):
        from core.consolidation.span_planner import run_consolidation_pass

        root = _root("empty_span")
        ledger = _fresh_ledger(root)
        _write_synthetic_three_day_ledger(ledger)
        paths = _paths(root, ledger)
        with patch.dict(os.environ, _enabled_env(), clear=False):
            run_consolidation_pass(
                paths=paths,
                idle_inputs=_allowing_idle(),
                llm_callable=PromptAwareFakeLLM(),
            )
            second_llm = PromptAwareFakeLLM()
            second = run_consolidation_pass(
                paths=paths,
                idle_inputs=_allowing_idle(),
                llm_callable=second_llm,
            )

        self.assertEqual(second.status, "empty")
        self.assertEqual(second.artifacts_committed, 0)
        self.assertEqual(second_llm.calls, [])
        receipts = _jsonl(paths.receipts_path)
        self.assertEqual(receipts[-1]["event"], "span_empty")
        self.assertEqual(receipts[-1]["artifact_count"], 0)

    def test_crash_after_artifact_commit_reconciles_without_double_digest(self):
        from core.consolidation.span_planner import run_consolidation_pass

        root = _root("crash_reconcile")
        ledger = _fresh_ledger(root)
        _write_synthetic_three_day_ledger(ledger)
        paths = _paths(root, ledger)
        crashes = {"count": 0}

        def crash_once(_committed):
            crashes["count"] += 1
            if crashes["count"] == 1:
                raise RuntimeError("simulated crash after committed artifact re-read")

        with patch.dict(os.environ, _enabled_env(), clear=False):
            with self.assertRaisesRegex(RuntimeError, "simulated crash"):
                run_consolidation_pass(
                    paths=paths,
                    idle_inputs=_allowing_idle(),
                    llm_callable=PromptAwareFakeLLM(),
                    after_artifact_re_read=crash_once,
                )
            after_crash = _rows(
                paths.episode_digests_db_path,
                "SELECT span_id, episode_key FROM episode_digest_shadow",
            )
            resumed = run_consolidation_pass(
                paths=paths,
                idle_inputs=_allowing_idle(),
                llm_callable=PromptAwareFakeLLM(),
            )

        self.assertEqual(len(after_crash), 1)
        self.assertIn(resumed.status, {"completed", "empty"})
        rows = _rows(
            paths.episode_digests_db_path,
            "SELECT span_id, episode_key FROM episode_digest_shadow ORDER BY id ASC",
        )
        self.assertEqual(
            len(rows),
            len({(row["span_id"], row["episode_key"]) for row in rows}),
        )

    def test_partial_artifact_without_completion_marker_is_reconciled_not_skipped(self):
        from core.consolidation.span_planner import run_consolidation_pass

        root = _root("partial_artifact")
        ledger = _fresh_ledger(root)
        _write_synthetic_three_day_ledger(ledger)
        paths = _paths(root, ledger)
        paths.episode_digests_db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = _connect(paths.episode_digests_db_path)
        try:
            conn.execute(
                """
                CREATE TABLE episode_digest_shadow (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    span_id TEXT NOT NULL,
                    episode_key TEXT NOT NULL,
                    start_chain_position INTEGER NOT NULL,
                    end_chain_position INTEGER NOT NULL,
                    selection_depth TEXT NOT NULL,
                    row_count INTEGER NOT NULL,
                    digest_text TEXT NOT NULL,
                    row_citations_json TEXT NOT NULL,
                    taint_labels_json TEXT NOT NULL,
                    receipt_id TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    UNIQUE(span_id, episode_key)
                )
                """
            )
            conn.execute(
                """
                INSERT INTO episode_digest_shadow (
                    span_id, episode_key, start_chain_position, end_chain_position,
                    selection_depth, row_count, digest_text, row_citations_json,
                    taint_labels_json, receipt_id, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "span-cp2-cp10",
                    "cp2-cp6",
                    2,
                    6,
                    "deep",
                    5,
                    "partial digest without candidates or receipt",
                    "[]",
                    "[]",
                    "partial-receipt",
                    1.0,
                ),
            )
            conn.commit()
        finally:
            conn.close()

        with patch.dict(os.environ, _enabled_env(), clear=False):
            result = run_consolidation_pass(
                paths=paths,
                idle_inputs=_allowing_idle(),
                llm_callable=PromptAwareFakeLLM(),
            )

        self.assertEqual(result.status, "completed")
        state = {
            row["key"]: row["value"]
            for row in _rows(paths.spine_db_path, "SELECT key, value FROM state")
        }
        self.assertEqual(int(state["last_digested_chain_position"]), result.high_water)
        candidates = _rows(
            paths.spine_db_path,
            "SELECT * FROM shadow_wondering_candidates WHERE episode_key='cp2-cp6'",
        )
        self.assertGreater(len(candidates), 0)
        completion = _rows(
            paths.spine_db_path,
            "SELECT * FROM completed_artifacts WHERE episode_key='cp2-cp6'",
        )
        self.assertEqual(len(completion), 1)

    def test_mid_run_window_close_commits_current_episode_and_defers_remainder(self):
        from core.consolidation.span_planner import run_consolidation_pass

        root = _root("window_close")
        ledger = _fresh_ledger(root)
        _write_synthetic_three_day_ledger(ledger)
        paths = _paths(root, ledger)
        probes = iter([True, False, True, True, True])

        with patch.dict(os.environ, _enabled_env(), clear=False):
            first = run_consolidation_pass(
                paths=paths,
                idle_inputs=_allowing_idle(),
                llm_callable=PromptAwareFakeLLM(),
                window_still_open=lambda: next(probes),
            )
            first_digest_count = len(
                _rows(paths.episode_digests_db_path, "SELECT * FROM episode_digest_shadow")
            )
            state_after_first = {
                row["key"]: row["value"]
                for row in _rows(paths.spine_db_path, "SELECT key, value FROM state")
            }
            second = run_consolidation_pass(
                paths=paths,
                idle_inputs=_allowing_idle(),
                llm_callable=PromptAwareFakeLLM(),
            )

        self.assertEqual(first.status, "deferred")
        self.assertEqual(first_digest_count, 1)
        self.assertLess(int(state_after_first["last_digested_chain_position"]), first.high_water)
        self.assertIn(second.status, {"completed", "empty"})
        self.assertGreaterEqual(
            len(_rows(paths.episode_digests_db_path, "SELECT * FROM episode_digest_shadow")),
            first_digest_count,
        )


class DigesterB2Tests(unittest.TestCase):
    def test_non_local_endpoint_defers_without_llm_call(self):
        from core.consolidation.digester import digest_episode
        from core.consolidation.selector import EpisodeSelection

        root = _root("non_local")
        ledger = _fresh_ledger(root)
        _write_synthetic_three_day_ledger(ledger)
        rows = _rows(ledger, "SELECT * FROM turns WHERE chain_position BETWEEN 1 AND 2")
        episode = EpisodeSelection(
            episode_key="cp1-cp2",
            start_chain_position=1,
            end_chain_position=2,
            turn_ids=tuple(row["turn_id"] for row in rows),
            row_count=len(rows),
            tool_outcome_count=0,
            tool_outcome_density=0.0,
            error_cluster_present=False,
            selection_depth="deep",
        )

        result = digest_episode(
            episode,
            rows=rows,
            span={
                "after_chain_position": 0,
                "high_water": 2,
                "anchor_chain_position": 1,
                "rows": rows,
            },
            ledger_db_path=ledger,
            llm_callable=lambda **_: (_ for _ in ()).throw(AssertionError("no LLM")),
            endpoint_guard=lambda: DigestionEndpointLocality(
                allowed=False,
                backend="llamacpp",
                endpoint="https://remote.example/v1",
                refusal_code="non_local_endpoint",
                reason="remote",
            ),
        )

        self.assertEqual(result.status, "deferred")
        self.assertEqual(result.refusal_code, "non_local_endpoint")

    def test_parse_failure_refuses_without_partial_writes_or_progress(self):
        from core.consolidation.span_planner import run_consolidation_pass

        root = _root("parse_failure")
        ledger = _fresh_ledger(root)
        _write_synthetic_three_day_ledger(ledger)
        paths = _paths(root, ledger)

        with patch.dict(os.environ, _enabled_env(), clear=False):
            result = run_consolidation_pass(
                paths=paths,
                idle_inputs=_allowing_idle(),
                llm_callable=lambda **_: "this is not json",
            )

        self.assertEqual(result.status, "refused")
        self.assertEqual(result.refusals[0]["refusal_code"], "digestion_parse_failure")
        self.assertEqual(_table_names(paths.episode_digests_db_path), set())
        state = {
            row["key"]: row["value"]
            for row in _rows(paths.spine_db_path, "SELECT key, value FROM state")
        }
        self.assertLess(int(state["last_digested_chain_position"]), result.high_water)

    def test_direct_chat_callable_is_refused_before_any_model_call(self):
        from core import llm_client
        from core.consolidation.digester import digest_episode
        from core.consolidation.selector import EpisodeSelection

        root = _root("direct_chat")
        ledger = _fresh_ledger(root)
        _write_synthetic_three_day_ledger(ledger)
        rows = _rows(ledger, "SELECT * FROM turns WHERE chain_position BETWEEN 2 AND 3")
        episode = EpisodeSelection(
            episode_key="cp2-cp3",
            start_chain_position=2,
            end_chain_position=3,
            turn_ids=tuple(row["turn_id"] for row in rows),
            row_count=len(rows),
            tool_outcome_count=0,
            tool_outcome_density=0.0,
            error_cluster_present=False,
            selection_depth="deep",
        )

        result = digest_episode(
            episode,
            rows=rows,
            span={
                "after_chain_position": 1,
                "high_water": 3,
                "anchor_chain_position": 2,
                "rows": rows,
            },
            ledger_db_path=ledger,
            llm_callable=llm_client.chat_direct,
        )

        self.assertEqual(result.status, "refused")
        self.assertEqual(result.refusal_code, "direct_chat_forbidden")

    def test_oversized_episode_is_split_and_endpoint_checked_for_each_call(self):
        from core.consolidation.digester import digest_episode
        from core.consolidation.selector import EpisodeSelection

        root = _root("split")
        ledger = _fresh_ledger(root)
        _write_synthetic_three_day_ledger(ledger)
        for index in range(18):
            _append_owner_row(ledger, f"bulk row {index}")
        rows = _rows(ledger, "SELECT * FROM turns WHERE chain_position >= 1")
        public_rows = [row for row in rows if row["privacy_access"] == "public"]
        episode = EpisodeSelection(
            episode_key=f"cp1-cp{rows[-1]['chain_position']}",
            start_chain_position=1,
            end_chain_position=int(rows[-1]["chain_position"]),
            turn_ids=tuple(row["turn_id"] for row in rows),
            row_count=len(rows),
            tool_outcome_count=0,
            tool_outcome_density=0.0,
            error_cluster_present=False,
            selection_depth="deep",
        )
        guard_calls = {"count": 0}

        def endpoint_guard():
            guard_calls["count"] += 1
            return DigestionEndpointLocality(
                allowed=True,
                backend="llamacpp",
                endpoint="http://127.0.0.1:8080/v1",
            )

        fake_llm = PromptAwareFakeLLM()
        result = digest_episode(
            episode,
            rows=rows,
            span={
                "after_chain_position": 0,
                "high_water": int(rows[-1]["chain_position"]),
                "anchor_chain_position": 1,
                "rows": rows,
            },
            ledger_db_path=ledger,
            llm_callable=fake_llm,
            endpoint_guard=endpoint_guard,
            max_rows_per_call=5,
        )

        self.assertEqual(result.status, "ok")
        self.assertGreater(len(fake_llm.calls), 1)
        self.assertEqual(guard_calls["count"], len(fake_llm.calls))
        cited_ids = {citation["turn_id"] for citation in result.row_citations}
        self.assertEqual(cited_ids, {row["turn_id"] for row in public_rows})

    def test_episode_working_set_taint_is_stamped_even_when_row_is_uncited(self):
        from core.consolidation.digester import digest_episode
        from core.consolidation.selector import EpisodeSelection

        root = _root("workset_taint")
        ledger = _fresh_ledger(root)
        _write_synthetic_three_day_ledger(ledger)
        rows = _rows(ledger, "SELECT * FROM turns WHERE chain_position BETWEEN 2 AND 7")
        episode = EpisodeSelection(
            episode_key="cp2-cp7",
            start_chain_position=2,
            end_chain_position=7,
            turn_ids=tuple(row["turn_id"] for row in rows),
            row_count=len(rows),
            tool_outcome_count=2,
            tool_outcome_density=2 / len(rows),
            error_cluster_present=True,
            selection_depth="deep",
        )
        first = rows[0]

        def cites_only_first(**kwargs):
            del kwargs
            return json.dumps(
                {
                    "episode_digest": "observed only the first cited row",
                    "row_citations": [
                        {
                            "turn_id": first["turn_id"],
                            "chain_position": first["chain_position"],
                        }
                    ],
                    "wondering_candidates": [
                        {
                            "text": "what else was nearby but uncited?",
                            "row_citations": [
                                {
                                    "turn_id": first["turn_id"],
                                    "chain_position": first["chain_position"],
                                }
                            ],
                            "taint_labels": ["self_generated"],
                        }
                    ],
                }
            )

        result = digest_episode(
            episode,
            rows=rows,
            span={
                "after_chain_position": 1,
                "high_water": 7,
                "anchor_chain_position": 2,
                "rows": rows,
            },
            ledger_db_path=ledger,
            llm_callable=cites_only_first,
        )

        self.assertEqual(result.status, "ok")
        self.assertIn("tool_output", result.taint_labels)
        self.assertIn("internet_derived", result.taint_labels)
        self.assertIn("tool_output", result.wondering_candidates[0].taint_labels)
        self.assertIn("internet_derived", result.wondering_candidates[0].taint_labels)


class ManualRunnerB2Tests(unittest.TestCase):
    def test_custom_ledger_requires_output_root(self):
        from scripts import run_consolidation_shadow

        root = _root("manual_requires_output")
        ledger = root / "ledger.db"

        stderr = StringIO()
        with redirect_stderr(stderr):
            rc = run_consolidation_shadow.main(["--ledger-db", str(ledger)])

        self.assertEqual(rc, 2)
        self.assertIn("--output-root", stderr.getvalue())

    def test_output_root_keeps_manual_witness_outputs_beside_custom_ledger(self):
        from scripts import run_consolidation_shadow

        root = _root("manual_output_root")
        ledger = root / "ledger.db"
        output_root = root / "witness"
        seen = {}

        def fake_run(*, paths, **kwargs):
            seen["paths"] = paths
            seen["kwargs"] = kwargs
            return SimpleNamespace(status="disabled")

        with mock.patch.object(
            run_consolidation_shadow,
            "run_consolidation_pass",
            side_effect=fake_run,
        ), redirect_stdout(StringIO()):
            rc = run_consolidation_shadow.main(
                [
                    "--ledger-db",
                    str(ledger),
                    "--output-root",
                    str(output_root),
                ]
            )

        self.assertEqual(rc, 0)
        paths = seen["paths"]
        self.assertEqual(paths.ledger_db_path, ledger)
        self.assertEqual(
            paths.spine_db_path,
            output_root / "memory" / "consolidation" / "spine.sqlite3",
        )
        self.assertEqual(
            paths.receipts_path,
            output_root / "logs" / "consolidation_receipts.jsonl",
        )


if __name__ == "__main__":
    unittest.main()
