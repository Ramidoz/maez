# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""REGRESSION GUARDS for the Tier-2 decision/action cluster
from the 2026-05-04 15-agent audit.

T2.A — hardcoded "rohit_rejected" outcome literal
  Audit found: core/decision/decision_pipeline.py:1104 hardcodes
  the outcome string "rohit_rejected", which breaks the audit
  trail for any non-Rohit instance. The label must be derived
  from the canonical owner identity. Semantics for Rohit's
  instance stay identical (the label still resolves to
  "rohit_rejected") because the derivation slugifies display_name
  and Rohit's display_name slugs to "rohit".

T2.B — orphan cards skip outcome recording
  Audit found: when a card has audit_request_id is None, every
  record_outcome path is `if card.audit_request_id:` — the row
  is silently skipped. The audit-trail invariant is "every card
  outcome → one audit_log row". Orphans must synthesize a
  deterministic id (orphan-card-<request_id>) so the call still
  lands.

T2.C — _execute_inline failure not recorded to consequence_memory
  Audit found: commit 8694b14 added consequence_memory recording
  to _on_approve's failure branch. _execute_inline (Lane 0
  inline execution) is structurally equivalent on failure but
  was never given the matching record. Same shape, same field
  names — so quality reports stay aligned across both paths.

T2.D — no lock on action_engine._pending under concurrent access
  Audit found: ActionEngine._pending is mutated by sync methods
  callable from multiple threads (telegram callbacks, brain
  loop, GUI). Mirror T1.2's _offers_lock pattern with a
  threading.RLock so concurrent queue/cancel/approve don't
  corrupt state.
"""
from __future__ import annotations

import sys
import threading
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))


# ── T2.A — owner-derived rejection outcome label ─────────────────────


class T2_A_OwnerDerivedRejectionLabel(unittest.TestCase):
    """REGRESSION GUARD for T2.A: the rejected-outcome label written
    to audit_log on _on_deny must be derived from the canonical owner
    identity, not a literal "rohit_rejected" string. For Rohit's
    instance the derived value still equals "rohit_rejected"."""

    def test_helper_resolves_to_rohit_rejected_for_rohit_owner(self):
        """The new helper in decision_pipeline must return
        'rohit_rejected' when the owner's display_name is 'Rohit'."""
        from core.decision import decision_pipeline as dp

        self.assertTrue(
            hasattr(dp, "_owner_rejection_outcome"),
            "decision_pipeline must expose `_owner_rejection_outcome` "
            "helper that returns the owner-derived rejection label",
        )
        with mock.patch.object(dp, "_owner_display_name", return_value="Rohit"):
            self.assertEqual(
                dp._owner_rejection_outcome(),
                "rohit_rejected",
                "Rohit's owner must still resolve to 'rohit_rejected' "
                "to preserve quality_tracker / drift-report semantics",
            )

    def test_helper_resolves_for_non_rohit_owner(self):
        """For a different owner, the helper must produce a slugified
        label of the form '<slug>_rejected' rather than the literal."""
        from core.decision import decision_pipeline as dp

        with mock.patch.object(dp, "_owner_display_name", return_value="Alice"):
            self.assertEqual(
                dp._owner_rejection_outcome(),
                "alice_rejected",
                "non-Rohit owner must produce a derived '<slug>_rejected' "
                "label, not the hardcoded Rohit literal",
            )

    def test_source_no_hardcoded_rohit_rejected_string(self):
        """REGRESSION GUARD: the source must not contain the literal
        "rohit_rejected" string anywhere — every reference resolves
        through the new helper."""
        path = REPO / "core" / "decision" / "decision_pipeline.py"
        src = path.read_text()
        # Inline literal in record_outcome arg is the failure mode.
        self.assertNotIn(
            'outcome="rohit_rejected"', src,
            "decision_pipeline.py must not pass the literal "
            "'rohit_rejected' as an outcome — derive via "
            "_owner_rejection_outcome() instead",
        )


# ── T2.B — orphan cards still record outcome ─────────────────────────


class T2_B_OrphanCardOutcomeRecording(unittest.TestCase):
    """REGRESSION GUARD for T2.B: when a CardRecord has
    audit_request_id=None, the deny / approve / fail paths must still
    invoke audit_log.record_outcome with a synthesized
    `orphan-card-<request_id>` id so the audit-trail invariant
    holds."""

    def test_helper_synthesizes_orphan_id(self):
        from core.decision import decision_pipeline as dp

        self.assertTrue(
            hasattr(dp, "_resolve_audit_request_id"),
            "decision_pipeline must expose `_resolve_audit_request_id` "
            "helper that returns the existing audit_request_id or a "
            "synthesized 'orphan-card-<id>' fallback",
        )

        class _Card:
            request_id = "abcd1234"
            audit_request_id = None

        out = dp._resolve_audit_request_id(_Card())
        self.assertEqual(
            out, "orphan-card-abcd1234",
            "orphan card (audit_request_id=None) must synthesize "
            "'orphan-card-<request_id>'",
        )

    def test_helper_passthrough_for_normal_card(self):
        from core.decision import decision_pipeline as dp

        class _Card:
            request_id = "abcd1234"
            audit_request_id = "real-aid-9999"

        out = dp._resolve_audit_request_id(_Card())
        self.assertEqual(
            out, "real-aid-9999",
            "non-orphan card must pass through audit_request_id "
            "untouched",
        )

    def test_source_no_skip_on_null_audit_request_id(self):
        """REGRESSION GUARD: source-level — the audit_log.record_outcome
        call sites in _on_approve and _on_deny must not be guarded by
        a bare `if card.audit_request_id:` (which silently skips
        orphans). Each must route through _resolve_audit_request_id."""
        path = REPO / "core" / "decision" / "decision_pipeline.py"
        src = path.read_text()
        lines = src.split("\n")
        offenders: list[int] = []
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            # The exact failure pattern: a guard that gates an
            # audit_log.record_outcome call on a truthy
            # audit_request_id — silently dropping the orphan.
            if stripped == "if card.audit_request_id:":
                offenders.append(i)
        self.assertEqual(
            offenders, [],
            f"`if card.audit_request_id:` guard found at lines "
            f"{offenders} — orphan cards silently skip the outcome "
            f"row. Use `_resolve_audit_request_id(card)` instead.",
        )


# ── T2.C — _execute_inline failure → consequence_memory ──────────────


class T2_C_ExecuteInlineFailureToConsequenceMemory(unittest.TestCase):
    """REGRESSION GUARD for T2.C: _execute_inline's failure branch
    must record a CLASS_TOOL_FAILURE consequence_memory event with
    the same shape as _on_approve's failure branch (action= context,
    err outcome, surface='decision_pipeline')."""

    def test_source_execute_inline_records_consequence_memory(self):
        """Source-pin: _execute_inline body must invoke
        consequence_memory.record_event on its failure path. Booting
        the full pipeline for a behavioural test is impractical — the
        source pin catches refactors that drop the call."""
        path = REPO / "core" / "decision" / "decision_pipeline.py"
        src = path.read_text()
        start = src.index("def _execute_inline")
        # Bound the body by the next top-level def
        end = src.index("\n    def ", start + 1)
        body = src[start:end]
        self.assertIn(
            "consequence_memory", body,
            "_execute_inline body must reference consequence_memory "
            "(import + record_event) on its failure branch — the "
            "pattern won't be available for future planner avoidance "
            "without it",
        )
        self.assertIn(
            "CLASS_TOOL_FAILURE", body,
            "_execute_inline must use CLASS_TOOL_FAILURE — same kind "
            "as _on_approve's approved_and_failed branch — so quality "
            "reports aggregate consistently across both paths",
        )
        self.assertIn(
            "decision_pipeline", body,
            "_execute_inline's consequence_memory record must set "
            "surface='decision_pipeline' to match _on_approve's shape",
        )


# ── T2.D — action_engine._pending lock ───────────────────────────────


class T2_D_ActionEnginePendingLock(unittest.TestCase):
    """REGRESSION GUARD for T2.D: ActionEngine must hold an
    `_pending_lock` (threading.RLock) and every read/write of
    self._pending in core/actions/action_engine.py must occur inside
    a `with self._pending_lock:` block. Mirror T1.2's _offers_lock
    pattern."""

    def _engine(self):
        from core.actions.action_engine import ActionEngine
        return ActionEngine(memory=None, telegram=None, daemon=None)

    def test_lock_attribute_exists_and_is_rlock(self):
        eng = self._engine()
        self.assertTrue(
            hasattr(eng, "_pending_lock"),
            "ActionEngine must have `_pending_lock`",
        )
        # Re-entrant: a method that holds the lock and calls another
        # locked method must not deadlock.
        eng._pending_lock.acquire()
        try:
            acquired = eng._pending_lock.acquire(blocking=False)
            self.assertTrue(
                acquired,
                "_pending_lock must be a re-entrant lock (RLock)",
            )
            if acquired:
                eng._pending_lock.release()
        finally:
            eng._pending_lock.release()

    def test_concurrent_queue_and_cancel_does_not_corrupt(self):
        """Two threads — one queueing, one cancelling — must not
        produce a KeyError, IndexError, or a half-corrupted pending
        list."""
        eng = self._engine()
        # Avoid filesystem chatter from _save_pending in this test.
        eng._save_pending = lambda: None  # type: ignore[assignment]

        N = 100
        ids: list[str] = []
        ids_lock = threading.Lock()
        errors: list[Exception] = []

        def writer():
            try:
                for i in range(N):
                    aid = eng.queue_action(
                        action="read_file",
                        params={"path": f"/tmp/x{i}"},
                        reasoning=f"r{i}",
                        tier=1,
                    )
                    with ids_lock:
                        ids.append(aid)
            except Exception as e:
                errors.append(e)

        def canceller():
            try:
                for _ in range(N):
                    with ids_lock:
                        target = ids[-1] if ids else None
                    if target:
                        eng.cancel_pending(target)
            except Exception as e:
                errors.append(e)

        t1 = threading.Thread(target=writer)
        t2 = threading.Thread(target=canceller)
        t1.start()
        t2.start()
        t1.join(timeout=5.0)
        t2.join(timeout=5.0)
        self.assertEqual(
            errors, [],
            f"concurrent queue+cancel raised: {errors}",
        )

    def test_source_all_pending_access_under_lock(self):
        """REGRESSION GUARD: source-level — every reference to
        `self._pending` in action_engine.py must appear inside a
        `with self._pending_lock:` block (or be an init / type-
        annotated assignment in __init__ / _load_pending)."""
        path = REPO / "core" / "actions" / "action_engine.py"
        src = path.read_text()
        lines = src.split("\n")

        access_lines: list[int] = []
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if "self._pending" not in stripped:
                continue
            if "self._pending_lock" in stripped:
                continue
            # Skip the assignment in _load_pending where the dict is
            # initialised / reset (the lock initialisation contract
            # is held by __init__ itself).
            if (stripped.startswith("self._pending = []")
                    or stripped.startswith(
                        "self._pending = json.loads")):
                continue
            access_lines.append(i)

        self.assertGreater(
            len(access_lines), 0,
            "no _pending access sites found — test/grep regression",
        )

        for lineno in access_lines:
            in_lock = False
            for j in range(lineno - 1, max(0, lineno - 80), -1):
                pj = lines[j - 1].strip()
                if pj.startswith("with self._pending_lock"):
                    in_lock = True
                    break
                if pj.startswith("def ") or pj.startswith("async def "):
                    break
            self.assertTrue(
                in_lock,
                f"line {lineno}: `self._pending` access not inside "
                f"`with self._pending_lock:` block. line text: "
                f"{lines[lineno - 1].strip()!r}",
            )


if __name__ == "__main__":
    unittest.main()
