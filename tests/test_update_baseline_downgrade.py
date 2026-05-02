# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""5x.F.B — through-quotation downgrade rule on update_baseline.

F.A built the cycle-scoped recall-context bag (daemon attribute
``self._cycle_recall_context``). F.B is the consumer:

  Rule (any-untrusted-tips):
    If `update_baseline` runs while the cycle's recall scope
    contains any entry tagged ``trust_tier="untrusted"``, the
    resulting baseline is stored with ``trust_tier="untrusted"``
    + ancestry metadata (promoted_from=<all recall IDs>).
    Otherwise current 5x.D.B2 behavior holds:
    introspection/lived, no promoted_from.

  Why this isn't an `allow_untrusted_ancestors=True` backdoor:
    F.B's rule IS the policy opt-in for through-quotation
    laundering. The system explicitly says "yes, route this
    promotion through the gate, but downgrade the result so
    5x.C surfaces the warning at recall time." The downgrade
    is the safety; the resulting core entry is visibly
    untrusted, not silently trusted.

  Observability:
    Every `update_baseline` call logs a structured line
    `baseline_update provenance downgraded=<bool>
    untrusted_count=N recall_count=M` so an operator can see
    in production what fraction of baselines downgrade.

Wiring: ActionEngine gains a ``daemon=None`` param. When set,
``_do_update_baseline`` reads ``self.daemon._cycle_recall_context``.
When None (tests, GUI, direct API), falls through to current
behavior — F.B does NOT cover non-daemon contexts. Documented
limitation; F.B closes the daemon-cycle baseline laundering surface
first.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))


class _CapturingMemory:
    """Mirror live MemoryManager.store_core signature exactly."""

    def __init__(self):
        self.store_core_calls: list[dict] = []

    def store_core(self, content, source="reasoning", *,
                   provenance_source=None, trust_tier=None,
                   promoted_from=None,
                   allow_untrusted_ancestors=False):
        self.store_core_calls.append({
            "content": content, "source": source,
            "provenance_source": provenance_source,
            "trust_tier": trust_tier,
            "promoted_from": promoted_from,
            "allow_untrusted_ancestors": allow_untrusted_ancestors,
        })
        return "core-fake-id"


class _FakeDaemon:
    """Minimal stand-in: just the attribute F.B reads."""

    def __init__(self, recall_context: dict | None):
        self._cycle_recall_context = recall_context


def _make_engine(memory, daemon=None):
    """Construct ActionEngine without running its heavy __init__
    side-effects (BACKUP_DIR.mkdir, _load_pending, logging)."""
    from core.actions.action_engine import ActionEngine
    engine = ActionEngine.__new__(ActionEngine)
    engine.memory = memory
    engine.telegram = None
    engine.daemon = daemon
    return engine


def _bag(*ids_and_tiers):
    """Helper: build a recall-context bag from (id, tier) pairs."""
    bag = {"ids": set(), "tiers_by_id": {}}
    for mid, tier in ids_and_tiers:
        bag["ids"].add(mid)
        bag["tiers_by_id"][mid] = tier
    return bag


# ── downgrade fires when any untrusted in scope ─────────────────────


class DowngradeFiresTests(unittest.TestCase):
    def test_downgrade_writes_untrusted_with_ancestry(self):
        """Any-untrusted-tips: a single untrusted entry in scope must
        produce an untrusted-tier baseline with full ancestry."""
        mm = _CapturingMemory()
        bag = _bag(
            ("raw-1", "lived"),
            ("raw-evil", "untrusted"),
            ("core-1", "covenant"),
        )
        engine = _make_engine(mm, daemon=_FakeDaemon(bag))
        with mock.patch(
            "core.actions.action_engine.audit_assistant_text",
            return_value="audited",
        ):
            engine._do_update_baseline("anything")

        call = mm.store_core_calls[0]
        self.assertEqual(call["source"], "baseline_update")
        self.assertEqual(call["provenance_source"], "introspection")
        # Worst-wins propagates through the gate; the baseline lands
        # at untrusted regardless of caller intent.
        self.assertEqual(call["trust_tier"], "untrusted")
        # Ancestry includes ALL recall scope IDs (sorted for
        # determinism), not just the untrusted ones — F.B records
        # the full witness set so labelers / auditors can see what
        # was in the room.
        self.assertEqual(
            sorted(call["promoted_from"]),
            ["core-1", "raw-1", "raw-evil"],
        )
        # F.B's policy opt-in: the rule itself authorizes routing
        # through the gate with downgrade rather than refusal.
        self.assertTrue(call["allow_untrusted_ancestors"])

    def test_downgrade_with_only_untrusted_in_scope(self):
        """Edge case: every entry in scope is untrusted. Same outcome
        — downgrade with full ancestry."""
        mm = _CapturingMemory()
        bag = _bag(("raw-evil-1", "untrusted"), ("raw-evil-2", "untrusted"))
        engine = _make_engine(mm, daemon=_FakeDaemon(bag))
        with mock.patch(
            "core.actions.action_engine.audit_assistant_text",
            return_value="audited",
        ):
            engine._do_update_baseline("anything")
        call = mm.store_core_calls[0]
        self.assertEqual(call["trust_tier"], "untrusted")
        self.assertEqual(
            sorted(call["promoted_from"]),
            ["raw-evil-1", "raw-evil-2"],
        )
        self.assertTrue(call["allow_untrusted_ancestors"])


# ── fall-through paths ──────────────────────────────────────────────


class FallThroughTests(unittest.TestCase):
    def test_fall_through_when_no_untrusted_in_scope(self):
        """Trusted-only scope must NOT trigger downgrade. Result
        keeps current 5x.D.B2 behavior: introspection/lived, no
        promoted_from."""
        mm = _CapturingMemory()
        bag = _bag(
            ("raw-1", "lived"),
            ("raw-2", "observed"),
            ("core-1", "covenant"),
        )
        engine = _make_engine(mm, daemon=_FakeDaemon(bag))
        with mock.patch(
            "core.actions.action_engine.audit_assistant_text",
            return_value="audited",
        ):
            engine._do_update_baseline("anything")
        call = mm.store_core_calls[0]
        self.assertEqual(call["provenance_source"], "introspection")
        self.assertEqual(call["trust_tier"], "lived")
        self.assertIsNone(call["promoted_from"])
        self.assertFalse(call["allow_untrusted_ancestors"])

    def test_fall_through_when_only_unknown_legacy_in_scope(self):
        """Legacy is non-degrading — `unknown`-only scope must NOT
        trigger downgrade. Otherwise mass legacy material would
        downgrade every baseline. Matches 5x.D.A's worst-known-tier
        semantics."""
        mm = _CapturingMemory()
        bag = _bag(
            ("raw-old-1", "unknown"),
            ("raw-old-2", "unknown"),
        )
        engine = _make_engine(mm, daemon=_FakeDaemon(bag))
        with mock.patch(
            "core.actions.action_engine.audit_assistant_text",
            return_value="audited",
        ):
            engine._do_update_baseline("anything")
        call = mm.store_core_calls[0]
        self.assertEqual(call["trust_tier"], "lived")
        self.assertIsNone(call["promoted_from"])

    def test_fall_through_when_recall_context_is_empty(self):
        """Empty bag — no recall happened or this isn't a daemon
        cycle context. Falls through cleanly."""
        mm = _CapturingMemory()
        bag = _bag()  # empty
        engine = _make_engine(mm, daemon=_FakeDaemon(bag))
        with mock.patch(
            "core.actions.action_engine.audit_assistant_text",
            return_value="audited",
        ):
            engine._do_update_baseline("anything")
        call = mm.store_core_calls[0]
        self.assertEqual(call["trust_tier"], "lived")
        self.assertIsNone(call["promoted_from"])

    def test_fall_through_when_daemon_is_none(self):
        """Non-daemon contexts (chat handler, GUI, direct API) have
        no daemon back-reference. F.B falls through — documented
        limitation; daemon-cycle baselines first."""
        mm = _CapturingMemory()
        engine = _make_engine(mm, daemon=None)
        with mock.patch(
            "core.actions.action_engine.audit_assistant_text",
            return_value="audited",
        ):
            engine._do_update_baseline("anything")
        call = mm.store_core_calls[0]
        self.assertEqual(call["trust_tier"], "lived")
        self.assertIsNone(call["promoted_from"])

    def test_fall_through_when_daemon_has_no_bag_attribute(self):
        """Defensive: a daemon-shaped object without the
        ``_cycle_recall_context`` attribute (e.g., an older daemon
        version, a partial mock) must not crash. Fall through
        cleanly."""
        mm = _CapturingMemory()

        class BareDaemon:
            pass

        engine = _make_engine(mm, daemon=BareDaemon())
        with mock.patch(
            "core.actions.action_engine.audit_assistant_text",
            return_value="audited",
        ):
            engine._do_update_baseline("anything")
        call = mm.store_core_calls[0]
        self.assertEqual(call["trust_tier"], "lived")


# ── audit-before-store invariant preserved ──────────────────────────


class AuditPreservationTests(unittest.TestCase):
    def test_downgrade_path_still_audits_before_store(self):
        """The 5x.D.B2 audit-before-store invariant must hold on the
        downgrade path too — the stored content is the audited form,
        not the raw observation."""
        mm = _CapturingMemory()
        bag = _bag(("raw-evil", "untrusted"))
        engine = _make_engine(mm, daemon=_FakeDaemon(bag))
        with mock.patch(
            "core.actions.action_engine.audit_assistant_text",
            return_value="AUDITED-DOWNGRADED",
        ):
            engine._do_update_baseline("raw original")
        stored = mm.store_core_calls[0]["content"]
        self.assertIn("AUDITED-DOWNGRADED", stored)
        self.assertNotIn("raw original", stored)

    def test_audit_runs_with_expected_surface(self):
        """Surface stays ``action_baseline_update`` regardless of
        downgrade decision — bucketable in cockpit / log analysis."""
        mm = _CapturingMemory()
        bag = _bag(("raw-evil", "untrusted"))
        engine = _make_engine(mm, daemon=_FakeDaemon(bag))
        with mock.patch(
            "core.actions.action_engine.audit_assistant_text",
            return_value="audited",
        ) as audit_mock:
            engine._do_update_baseline("anything")
        audit_mock.assert_called_once()
        self.assertEqual(
            audit_mock.call_args.kwargs["surface"],
            "action_baseline_update",
        )


# ── observability log ───────────────────────────────────────────────


class ObservabilityLogTests(unittest.TestCase):
    LOG_NEEDLE = "baseline_update provenance"

    def test_logs_structured_line_on_downgrade(self):
        mm = _CapturingMemory()
        bag = _bag(
            ("raw-1", "lived"),
            ("raw-evil-a", "untrusted"),
            ("raw-evil-b", "untrusted"),
        )
        engine = _make_engine(mm, daemon=_FakeDaemon(bag))
        with self.assertLogs("maez.actions", level="INFO") as ctx:
            with mock.patch(
                "core.actions.action_engine.audit_assistant_text",
                return_value="audited",
            ):
                engine._do_update_baseline("anything")
        msgs = [m for m in ctx.output if self.LOG_NEEDLE in m]
        self.assertEqual(len(msgs), 1, ctx.output)
        msg = msgs[0]
        self.assertIn("downgraded=True", msg)
        self.assertIn("untrusted_count=2", msg)
        self.assertIn("recall_count=3", msg)

    def test_logs_structured_line_on_fall_through(self):
        mm = _CapturingMemory()
        bag = _bag(("raw-1", "lived"), ("raw-2", "observed"))
        engine = _make_engine(mm, daemon=_FakeDaemon(bag))
        with self.assertLogs("maez.actions", level="INFO") as ctx:
            with mock.patch(
                "core.actions.action_engine.audit_assistant_text",
                return_value="audited",
            ):
                engine._do_update_baseline("anything")
        msgs = [m for m in ctx.output if self.LOG_NEEDLE in m]
        self.assertEqual(len(msgs), 1)
        msg = msgs[0]
        self.assertIn("downgraded=False", msg)
        self.assertIn("untrusted_count=0", msg)
        self.assertIn("recall_count=2", msg)

    def test_logs_structured_line_when_daemon_is_none(self):
        """The log line fires even on the empty-context fall-through
        so an operator sees the action's frequency. recall_count=0
        is the signal that the action ran outside a daemon cycle."""
        mm = _CapturingMemory()
        engine = _make_engine(mm, daemon=None)
        with self.assertLogs("maez.actions", level="INFO") as ctx:
            with mock.patch(
                "core.actions.action_engine.audit_assistant_text",
                return_value="audited",
            ):
                engine._do_update_baseline("anything")
        msgs = [m for m in ctx.output if self.LOG_NEEDLE in m]
        self.assertEqual(len(msgs), 1)
        msg = msgs[0]
        self.assertIn("downgraded=False", msg)
        self.assertIn("untrusted_count=0", msg)
        self.assertIn("recall_count=0", msg)


# ── ActionEngine __init__ accepts daemon kwarg ──────────────────────


class ActionEngineInitTests(unittest.TestCase):
    def test_action_engine_init_accepts_daemon_param(self):
        """The wiring change: ActionEngine gains ``daemon=None``.
        Existing callers (tests, future contexts) without a daemon
        keep working; the production daemon passes ``daemon=self``."""
        from core.actions.action_engine import ActionEngine
        import inspect
        sig = inspect.signature(ActionEngine.__init__)
        self.assertIn("daemon", sig.parameters)
        self.assertEqual(
            sig.parameters["daemon"].default, None,
            "daemon must default to None so non-daemon callers "
            "(tests, GUI, direct API) keep working unchanged",
        )


# ── integration: real MemoryManager + 5x.D.A gate ────────────────────


class _FakeChromaCollection:
    """Minimal stand-in for a Chroma collection. Implements the
    handful of methods MemoryManager exercises during the F.B path:
    ``add`` (write), ``get(ids=...)`` (ancestor lookup for the gate)."""

    def __init__(self):
        self.rows: dict[str, dict] = {}

    def add(self, *, ids, documents, metadatas):
        for i, mid in enumerate(ids):
            self.rows[mid] = {
                "id": mid,
                "document": documents[i],
                "metadata": metadatas[i],
            }

    def get(self, *, ids, include=None):
        out_ids: list[str] = []
        out_docs: list[str] = []
        out_metas: list[dict] = []
        for mid in ids:
            if mid in self.rows:
                row = self.rows[mid]
                out_ids.append(mid)
                out_docs.append(row["document"])
                out_metas.append(row["metadata"])
        return {"ids": out_ids, "documents": out_docs,
                "metadatas": out_metas}


class GateIntegrationTests(unittest.TestCase):
    """Reviewer M2: the kwarg-recording fake in earlier classes
    proves what F.B PASSES to ``store_core``, but not what actually
    lands in storage AFTER 5x.D.A's worst-wins gate runs. If the
    gate's signature drifts (kwarg renamed, ancestor-lookup path
    changes), every kwarg-level test passes silently while
    production launders. This class stands up a real
    ``MemoryManager`` against fake Chroma collections so the
    end-to-end gate-then-store flow is exercised."""

    def _real_mm_with_seeded_untrusted(self, raw_id="raw-evil"):
        """Build a real MemoryManager whose `raw` collection holds
        one untrusted entry — ancestor lookup will find it during
        store_core's promotion-gate check."""
        from memory.memory_manager import MemoryManager
        mm = MemoryManager.__new__(MemoryManager)
        mm.raw = _FakeChromaCollection()
        mm.core = _FakeChromaCollection()
        mm.raw.rows[raw_id] = {
            "id": raw_id,
            "document": "external claim from a stranger",
            "metadata": {
                "trust_tier": "untrusted",
                "provenance_source": "external_web",
            },
        }
        return mm

    def test_downgrade_lands_as_untrusted_through_real_gate(self):
        """The contract-edge test: F.B passes promoted_from + the
        `allow_untrusted_ancestors` flag, then 5x.D.A's gate
        runs against the real MemoryManager and writes a core row
        whose metadata carries trust_tier=untrusted. Asserts
        end-to-end behavior, not just the F.B kwargs."""
        mm = self._real_mm_with_seeded_untrusted()
        bag = _bag(("raw-evil", "untrusted"))
        engine = _make_engine(mm, daemon=_FakeDaemon(bag))
        with mock.patch(
            "core.actions.action_engine.audit_assistant_text",
            return_value="audited",
        ):
            engine._do_update_baseline("anything")
        # Exactly one core row landed.
        self.assertEqual(len(mm.core.rows), 1)
        core_row = next(iter(mm.core.rows.values()))
        meta = core_row["metadata"]
        # The gate's worst-wins computation produced trust_tier=
        # untrusted from the ancestor's tier — this asserts the
        # production behavior, not just F.B's kwargs.
        self.assertEqual(meta["trust_tier"], "untrusted")
        self.assertEqual(
            meta["provenance_source"], "introspection",
        )
        # Ancestor lineage persisted as the gate documents it.
        self.assertIn("ancestor_tiers", meta)
        self.assertIn("untrusted", meta["ancestor_tiers"])
        self.assertIn("promoted_from", meta)
        self.assertIn("raw-evil", meta["promoted_from"])

    def test_fall_through_lands_as_lived_through_real_mm(self):
        """Symmetry: trusted-only scope produces a core row at
        trust_tier=lived with NO promoted_from / ancestor_tiers
        keys. Confirms the fall-through path doesn't accidentally
        invoke the gate via lingering kwargs."""
        from memory.memory_manager import MemoryManager
        mm = MemoryManager.__new__(MemoryManager)
        mm.raw = _FakeChromaCollection()
        mm.core = _FakeChromaCollection()

        bag = _bag(("raw-trusted", "lived"))
        engine = _make_engine(mm, daemon=_FakeDaemon(bag))
        with mock.patch(
            "core.actions.action_engine.audit_assistant_text",
            return_value="audited",
        ):
            engine._do_update_baseline("anything")
        self.assertEqual(len(mm.core.rows), 1)
        core_row = next(iter(mm.core.rows.values()))
        meta = core_row["metadata"]
        self.assertEqual(meta["trust_tier"], "lived")
        self.assertEqual(meta["provenance_source"], "introspection")
        # No ancestor metadata on the fall-through path.
        self.assertNotIn("ancestor_tiers", meta)
        self.assertNotIn("promoted_from", meta)


if __name__ == "__main__":
    unittest.main()
