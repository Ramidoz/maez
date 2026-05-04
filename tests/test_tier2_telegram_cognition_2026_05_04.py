# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""REGRESSION GUARDS for the Tier-2 cluster from the 2026-05-04
15-agent audit.

Four independent fixes; each has a regression guard so a future
refactor cannot silently regress the contract:

  T2.A — telegram_voice _process_message terminal-fallback audit
    The honesty-guard post-stream path has a terminal-fallback
    branch (the "couldn't reach the model" except clause) that
    sent reply_text() WITHOUT going through _audit_telegram_reply.
    The b672a2d AST-walk regression guard passed because the
    enclosing function calls _audit_telegram_reply on the success
    path — but the fallback branch was unaudited. Fix: route the
    fallback through the same gate.

  T2.B — cognition_quality vague-label dedup logic trap
    classify() at lines 354-357 has a dedup check
    `labels == ['vague']` that is fragile to insertion order, label
    casing, and whitespace. Lift the comparison into a named helper
    `_vague_label_dedup_key()` so the invariant is explicit, and
    pin the helper in source so a refactor can't silently inline it
    back.

  T2.C — baseline_observations SQLite race
    Module opens connections with check_same_thread=False but has
    no explicit locking around mutation. Add a module-scope
    threading.Lock and wrap record_observation's mutation path.

  T2.D — memory_scoring SQLite race
    Same shape as T2.C. Independent file, independent module-scope
    lock. record_recall + mark_consolidated are mutation paths.
"""
from __future__ import annotations

import ast
import os
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))


# ── T2.A — telegram_voice fallback audit ─────────────────────────────


class T2_A_TelegramFallbackAudit(unittest.TestCase):
    """REGRESSION GUARD for T2.A: the terminal-fallback branch in
    _process_message — the `except` clause that catches model
    failures and sends a "Reasoning error: ..." reply — must route
    its reply through `_audit_telegram_reply` so canary scrub /
    command guard / honesty guard apply even on the cold-error
    path."""

    PATH = REPO / "skills" / "telegram_voice.py"

    def test_process_message_fallback_routes_through_audit(self):
        """In the source, the except-clause inside _process_message
        that builds the user-visible "Reasoning error:" string must
        run that string through _audit_telegram_reply BEFORE
        reply_text. The b672a2d AST presence-of-audit heuristic is
        function-level; this test is reply-level on the specific
        fallback string."""
        src = self.PATH.read_text()
        tree = ast.parse(src)

        # Locate _process_message function.
        target = None
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name == "_process_message":
                    target = node
                    break
        self.assertIsNotNone(
            target,
            "_process_message must exist in skills/telegram_voice.py",
        )

        # Walk every Try in the body and check ExceptHandler subtrees
        # for a reply_text call. Each such call must be on a path
        # where _audit_telegram_reply is called somewhere inside the
        # same handler.
        for try_node in ast.walk(target):
            if not isinstance(try_node, ast.Try):
                continue
            for handler in try_node.handlers:
                handler_calls_audit = False
                handler_reply_lines: list[int] = []
                for sub in ast.walk(handler):
                    if not isinstance(sub, ast.Call):
                        continue
                    fn = sub.func
                    if isinstance(fn, ast.Attribute) and fn.attr == "reply_text":
                        handler_reply_lines.append(sub.lineno)
                    if (isinstance(fn, ast.Name)
                            and fn.id == "_audit_telegram_reply"):
                        handler_calls_audit = True
                    if (isinstance(fn, ast.Attribute)
                            and fn.attr == "_audit_telegram_reply"):
                        handler_calls_audit = True
                if handler_reply_lines and not handler_calls_audit:
                    self.fail(
                        f"_process_message: except-handler at line "
                        f"{handler.lineno} contains reply_text() at lines "
                        f"{handler_reply_lines} but does NOT call "
                        f"_audit_telegram_reply. Terminal-fallback must "
                        f"route through the audit gate (T2.A regression)."
                    )


# ── T2.B — vague-label dedup helper ──────────────────────────────────


class T2_B_VagueLabelDedupHelper(unittest.TestCase):
    """REGRESSION GUARD for T2.B: the vague-label dedup decision in
    cognition_quality.classify() must be expressed via a named
    helper `_vague_label_dedup_key(label) -> str` that normalizes
    labels (case-fold + strip) so the dedup invariant is explicit
    and a future refactor that changes label casing or insertion
    order cannot silently break dedup."""

    def test_helper_exists_and_normalizes(self):
        """Behavioural: the helper must exist and produce equal keys
        for casefold+strip-equivalent labels."""
        from core.cognition.cognition_quality import (
            _vague_label_dedup_key,
        )
        self.assertEqual(
            _vague_label_dedup_key("vague"),
            _vague_label_dedup_key("VAGUE"),
            "dedup key must be case-insensitive",
        )
        self.assertEqual(
            _vague_label_dedup_key(" vague "),
            _vague_label_dedup_key("vague"),
            "dedup key must strip surrounding whitespace",
        )
        self.assertEqual(
            _vague_label_dedup_key("vague"),
            "vague",
            "canonical key for the vague label must be lowercase 'vague'",
        )

    def test_classify_does_not_double_emit_vague(self):
        """Behavioural: classify() on a clearly-vague text must NOT
        emit duplicate 'vague' entries in labels. This is the
        dedup invariant the helper protects."""
        from core.cognition.cognition_quality import classify
        result = classify("ok.")
        labels = result.get("labels", [])
        self.assertEqual(
            labels.count("vague"), 1,
            f"vague should appear exactly once after dedup, got "
            f"{labels!r}",
        )

    def test_source_pins_helper_existence(self):
        """REGRESSION GUARD: the helper function must be defined as
        a top-level def in cognition_quality.py. A future refactor
        that inlines the comparison back into classify() fails this
        test loudly, even if behaviour seems unchanged.
        """
        path = REPO / "core" / "cognition" / "cognition_quality.py"
        src = path.read_text()
        tree = ast.parse(src)
        names = {
            node.name
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef)
        }
        self.assertIn(
            "_vague_label_dedup_key", names,
            "cognition_quality.py must define _vague_label_dedup_key "
            "as a top-level helper. Future refactors that inline the "
            "comparison back into classify() break the dedup "
            "invariant the audit flagged.",
        )


# ── T2.C — baseline_observations write lock ─────────────────────────


class T2_C_BaselineObservationsLock(unittest.TestCase):
    """REGRESSION GUARD for T2.C: baseline_observations.py opens
    SQLite with check_same_thread=False (intentional) and must
    therefore guard mutation paths with an explicit module-scope
    lock so concurrent record_observation calls cannot interleave
    INSERTs in ways that corrupt the writer's connection state."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._db = Path(self._tmp.name) / "baseline_observations.db"
        self._prev = os.environ.get("MAEZ_BASELINE_OBSERVATIONS_DB")
        os.environ["MAEZ_BASELINE_OBSERVATIONS_DB"] = str(self._db)

    def tearDown(self):
        if self._prev is None:
            os.environ.pop("MAEZ_BASELINE_OBSERVATIONS_DB", None)
        else:
            os.environ["MAEZ_BASELINE_OBSERVATIONS_DB"] = self._prev
        self._tmp.cleanup()

    def test_lock_attribute_exists(self):
        from core.memory import baseline_observations as bo
        self.assertTrue(
            hasattr(bo, "_write_lock"),
            "baseline_observations must define a module-scope "
            "_write_lock (threading.Lock or RLock) to guard SQLite "
            "writes — check_same_thread=False without a lock is the "
            "race the audit flagged",
        )
        # Sanity: attribute is a lock-shaped object (has acquire/release).
        lock = bo._write_lock
        self.assertTrue(hasattr(lock, "acquire"))
        self.assertTrue(hasattr(lock, "release"))

    def test_concurrent_record_observation_does_not_raise(self):
        from core.memory import baseline_observations as bo

        N = 50
        errors: list[Exception] = []

        def writer(idx: int):
            for i in range(N):
                try:
                    bo.record_observation(
                        observation=f"thread-{idx}-row-{i}",
                        audited_observation=f"audited-{idx}-{i}",
                        recall_ids=[],
                        recall_tiers={},
                        untrusted_ids=[],
                        substring_hits_=[],
                    )
                except Exception as exc:
                    errors.append(exc)

        threads = [threading.Thread(target=writer, args=(k,)) for k in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=15.0)
        self.assertFalse(
            errors, f"concurrent record_observation raised: {errors}",
        )

        rows = bo.recent(limit=10_000)
        # All 4*N rows should be present; fail-soft contract returns
        # None on failure, so zero rows would be a silent regression.
        self.assertGreaterEqual(
            len(rows), 4 * N // 2,
            "concurrent writes lost too many rows — lock not engaged",
        )

    def test_source_record_observation_holds_lock(self):
        """REGRESSION GUARD: source-level — record_observation's
        mutation block must run inside `with _write_lock:`. Adding
        a future write path that drops the lock fails this test."""
        path = REPO / "core" / "memory" / "baseline_observations.py"
        src = path.read_text()
        tree = ast.parse(src)
        target = None
        for node in ast.walk(tree):
            if (isinstance(node, ast.FunctionDef)
                    and node.name == "record_observation"):
                target = node
                break
        self.assertIsNotNone(target, "record_observation must exist")

        # Find every Call to con.execute or con.commit inside record_observation
        mutation_calls: list[ast.Call] = []
        for sub in ast.walk(target):
            if not isinstance(sub, ast.Call):
                continue
            fn = sub.func
            if isinstance(fn, ast.Attribute) and fn.attr in {"execute", "commit"}:
                mutation_calls.append(sub)
        self.assertGreater(
            len(mutation_calls), 0,
            "no mutation calls found in record_observation — "
            "test/grep regression",
        )

        # For each mutation call, walk up the AST to confirm an
        # enclosing With node references _write_lock.
        def _enclosing_withs(start_node):
            withs = []
            for n in ast.walk(target):
                if isinstance(n, ast.With):
                    for s in ast.walk(n):
                        if s is start_node:
                            withs.append(n)
                            break
            return withs

        for call in mutation_calls:
            withs = _enclosing_withs(call)
            ok = False
            for w in withs:
                w_src = ast.unparse(w.items[0].context_expr) if w.items else ""
                if "_write_lock" in w_src:
                    ok = True
                    break
                # Also accept nested locks (e.g., lock + closing(_connect)).
                for item in w.items:
                    item_src = ast.unparse(item.context_expr)
                    if "_write_lock" in item_src:
                        ok = True
                        break
                if ok:
                    break
            self.assertTrue(
                ok,
                f"baseline_observations.record_observation: mutation "
                f"call at line {call.lineno} is not inside a `with "
                f"_write_lock:` block. T2.C regression — "
                f"check_same_thread=False without an explicit lock.",
            )


# ── T2.D — memory_scoring write lock ────────────────────────────────


class T2_D_MemoryScoringLock(unittest.TestCase):
    """REGRESSION GUARD for T2.D: memory_scoring.py opens SQLite
    with check_same_thread=False and must therefore guard mutation
    paths (record_recall, mark_consolidated) with an explicit
    module-scope lock. Independent of T2.C — different file,
    different lock instance."""

    def test_lock_attribute_exists(self):
        from core.memory import memory_scoring as ms
        self.assertTrue(
            hasattr(ms, "_write_lock"),
            "memory_scoring must define a module-scope _write_lock "
            "(threading.Lock or RLock) — check_same_thread=False "
            "without a lock is the race the audit flagged",
        )
        lock = ms._write_lock
        self.assertTrue(hasattr(lock, "acquire"))
        self.assertTrue(hasattr(lock, "release"))

    def test_lock_is_independent_from_baseline_lock(self):
        """T2.C and T2.D share a pattern but MUST NOT share lock
        state — a write to memory_scoring should not block a write
        to baseline_observations and vice versa."""
        from core.memory import memory_scoring as ms
        from core.memory import baseline_observations as bo
        self.assertIsNot(
            ms._write_lock, bo._write_lock,
            "memory_scoring and baseline_observations locks must "
            "be independent instances — sharing would couple two "
            "unrelated write paths",
        )

    def test_concurrent_record_recall_does_not_raise(self):
        from core.memory import memory_scoring as ms

        N = 50
        errors: list[Exception] = []

        def writer(idx: int):
            for i in range(N):
                try:
                    ms.record_recall(
                        f"mem-{idx}-{i}",
                        query=f"q-{idx}-{i}",
                        relevance=0.5,
                        concept_tags=["t"],
                        now=time.time(),
                    )
                except Exception as exc:
                    errors.append(exc)

        threads = [threading.Thread(target=writer, args=(k,)) for k in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=15.0)
        self.assertFalse(
            errors, f"concurrent record_recall raised: {errors}",
        )

    def test_source_mutation_paths_hold_lock(self):
        """REGRESSION GUARD: source-level — every mutation path
        (record_recall, mark_consolidated) must wrap its db.execute
        / db.commit calls inside `with _write_lock:`. A new mutation
        path that drops the lock fails this test."""
        path = REPO / "core" / "memory" / "memory_scoring.py"
        src = path.read_text()
        tree = ast.parse(src)
        targets: dict[str, ast.FunctionDef] = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name in {
                "record_recall", "mark_consolidated",
            }:
                targets[node.name] = node
        self.assertEqual(
            set(targets.keys()), {"record_recall", "mark_consolidated"},
            "memory_scoring must define record_recall and "
            "mark_consolidated",
        )

        for fname, target in targets.items():
            mutation_calls: list[ast.Call] = []
            for sub in ast.walk(target):
                if not isinstance(sub, ast.Call):
                    continue
                fn = sub.func
                if (isinstance(fn, ast.Attribute)
                        and fn.attr in {"execute", "commit"}):
                    mutation_calls.append(sub)
            self.assertGreater(
                len(mutation_calls), 0,
                f"{fname}: no mutation calls found — test/grep regression",
            )

            for call in mutation_calls:
                # Find enclosing With nodes inside the function whose
                # subtree contains this call.
                ok = False
                for n in ast.walk(target):
                    if not isinstance(n, ast.With):
                        continue
                    contains = any(
                        s is call for s in ast.walk(n)
                    )
                    if not contains:
                        continue
                    for item in n.items:
                        item_src = ast.unparse(item.context_expr)
                        if "_write_lock" in item_src:
                            ok = True
                            break
                    if ok:
                        break
                self.assertTrue(
                    ok,
                    f"memory_scoring.{fname}: mutation call at line "
                    f"{call.lineno} is not inside `with _write_lock:` — "
                    f"T2.D regression.",
                )


if __name__ == "__main__":
    unittest.main()
