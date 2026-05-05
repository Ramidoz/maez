# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""REGRESSION GUARDS for the chat-audit signal-manifest fallback fix.

The 2026-05-05 09:27 wmctrl-class incident exposed
"grounding-context starvation": the chat-audit path called
audit_assistant_text() WITHOUT a signals manifest, the judge
classified true claims (model identity, disk percentage) as
ungrounded for lack of stated evidence, and the rewriter stamped
three sentinels into one reply.

This slice closes the false-positive class without weakening the
rail. New module core/safety/audit_signal_manifest.py exposes
default_audit_signals(surface) returning a (present, absent)
tuple of stable / bounded-fresh receipts (model identity from
model_config, body capability registry, capability_registry
state). audit_assistant_text fills these only when caller passes
None.

Per the agreed contract:
  - Caller-supplied manifest wins (never overwritten).
  - Fallback emits ONLY stable / bounded-fresh receipts.
  - Per-turn signals (specific disk %, specific presence state)
    require explicit caller supply — fallback does NOT pretend
    to know them.
  - Presence still flagged when absent (rail intact).
  - Judge prompt patched to recognize "configured model identity"
    as a grounded case.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))


# ── default_audit_signals shape ──────────────────────────────────────


class DefaultAuditSignalsShape(unittest.TestCase):
    """REGRESSION GUARD: default_audit_signals(surface) returns a
    (present, absent) tuple of strings."""

    def test_returns_tuple_of_two_lists(self):
        from core.safety.audit_signal_manifest import default_audit_signals
        present, absent = default_audit_signals("telegram_owner")
        self.assertIsInstance(present, list)
        self.assertIsInstance(absent, list)
        for item in present + absent:
            self.assertIsInstance(item, str)

    def test_includes_configured_model_identity(self):
        """The model identity false-positive class is closed only
        if the fallback names model_config presence."""
        from core.safety.audit_signal_manifest import default_audit_signals
        present, _ = default_audit_signals("telegram_owner")
        joined = " | ".join(present).lower()
        self.assertTrue(
            "model identity" in joined or "configured model" in joined,
            f"fallback present-signals must include model identity; "
            f"got {present}",
        )

    def test_includes_body_capability_registry(self):
        from core.safety.audit_signal_manifest import default_audit_signals
        present, _ = default_audit_signals("telegram_owner")
        joined = " | ".join(present).lower()
        self.assertTrue(
            "body capabilit" in joined or "capability registry" in joined,
            f"fallback present-signals must include body capability "
            f"registry; got {present}",
        )

    def test_does_not_pretend_specific_perception_values(self):
        """Per-turn metrics (disk percentage, CPU%, presence state)
        MUST NOT be in the fallback. The fallback can name only
        stable / bounded-fresh receipts. Specific values come from
        the caller's per-turn manifest."""
        from core.safety.audit_signal_manifest import default_audit_signals
        present, _ = default_audit_signals("telegram_owner")
        # No specific percentages or per-turn metric values
        for s in present:
            self.assertNotIn(
                "%", s,
                f"fallback must not include % values "
                f"(per-turn fact); got {s!r}",
            )

    def test_accepts_surface_argument(self):
        """surface= argument is accepted (per the contract; YAGNI
        on differentiation but signature compatibility today)."""
        from core.safety.audit_signal_manifest import default_audit_signals
        for surface in (
            "telegram_owner", "telegram_public", "web", "cli",
            "daemon_cycle", "fast_reply", "unknown_surface",
        ):
            present, absent = default_audit_signals(surface)
            self.assertIsInstance(present, list)
            self.assertIsInstance(absent, list)


# ── audit_assistant_text fallback wire ───────────────────────────────


class AuditAssistantTextFallbackWire(unittest.TestCase):
    """REGRESSION GUARD: when caller passes None for signals,
    audit_assistant_text fills from default_audit_signals."""

    def test_caller_supplied_manifest_is_never_overwritten(self):
        """If the caller passes signals_present/absent (even empty
        lists), the fallback MUST NOT overwrite. Caller-supplied
        manifest wins."""
        from core.safety import audited_output
        from core.safety import self_claim_audit as sca
        captured = {}

        def _capture(text, **kw):
            captured["signals_present"] = kw.get("signals_present")
            captured["signals_absent"] = kw.get("signals_absent")
            from core.safety.self_claim_audit import AuditResult
            return AuditResult(text=text, rewritten=False, mode="noop")

        # Pass an explicit empty manifest — caller said "no signals
        # are present, no signals are absent." The fallback must
        # NOT replace this with the default.
        with mock.patch.object(sca, "audit", side_effect=_capture):
            audited_output.audit_assistant_text(
                "i have run a deep system scan",
                surface="test_caller_wins",
                signals_present=[],
                signals_absent=[],
            )
        self.assertEqual(
            captured["signals_present"], [],
            "explicit empty signals_present must be preserved, "
            "not replaced by fallback",
        )
        self.assertEqual(captured["signals_absent"], [])

    def test_none_caller_triggers_fallback(self):
        """When BOTH signals are None (the surface didn't supply),
        audit_assistant_text fills from default_audit_signals so
        the judge sees stable receipts."""
        from core.safety import audited_output
        from core.safety import self_claim_audit as sca
        captured = {}

        def _capture(text, **kw):
            captured["signals_present"] = kw.get("signals_present")
            captured["signals_absent"] = kw.get("signals_absent")
            from core.safety.self_claim_audit import AuditResult
            return AuditResult(text=text, rewritten=False, mode="noop")

        with mock.patch.object(sca, "audit", side_effect=_capture):
            audited_output.audit_assistant_text(
                "i'm running on a configured local model",
                surface="test_fallback",
                # signals_present + signals_absent both omitted (None)
            )
        # The fallback must have filled signals_present with at
        # least the model-identity + body-cap entries.
        present = captured["signals_present"] or []
        joined = " | ".join(present).lower()
        self.assertTrue(
            len(present) > 0,
            "fallback must populate at least one present signal "
            "when caller passed None",
        )
        self.assertTrue(
            "model identity" in joined or "configured model" in joined,
            f"fallback must include model identity in present; "
            f"got {present}",
        )


# ── Behavioural: false-positive class closed ─────────────────────────


class FalsePositiveModelIdentityClosed(unittest.TestCase):
    """REGRESSION GUARD: a reply naming the configured model +
    inference engine is no longer flagged as ungrounded under
    the fallback manifest. Mocks the judge to verify the manifest
    that gets BUILT — we don't run the live LLM."""

    def test_model_identity_passes_through_fallback_manifest(self):
        """End-to-end: when audit_assistant_text is called without
        a manifest, the judge call receives a manifest that
        includes 'model identity' so a claim like 'I'm running on
        Qwen3.6-27B via llama.cpp' is grounded.

        The judge is mocked to verify the manifest shape, not the
        live LLM verdict."""
        from core.safety import audited_output
        from core.cognition import grounding_judge as gj
        captured_manifest = {}

        def _capture_judge(*, text, signals_present, signals_absent,
                           few_shots=None, model=None):
            captured_manifest["present"] = signals_present
            captured_manifest["absent"] = signals_absent
            return []  # judge says clean

        with mock.patch.object(gj, "judge", side_effect=_capture_judge):
            audited_output.audit_assistant_text(
                "I'm running on Qwen3.6-27B-UD-Q4_K_XL via llama.cpp.",
                surface="telegram_surface",
                # No manifest — fallback path
            )
        present = captured_manifest.get("present") or []
        joined = " | ".join(present).lower()
        self.assertTrue(
            "model identity" in joined or "configured model" in joined,
            f"the chat-audit fallback path must surface model "
            f"identity to the judge; got present={present}",
        )

    def test_presence_remains_flagged_when_absent(self):
        """The fallback must not regress the 'while you were out'
        class. Presence-related signals stay absent unless caller
        explicitly supplies them — the rail still catches false
        presence claims."""
        from core.safety import audit_signal_manifest as asm
        present, absent = asm.default_audit_signals("telegram_surface")
        # presence should be in the absent list (no presence signal
        # by default — caller must supply if they have one)
        joined_absent = " | ".join(absent).lower()
        self.assertTrue(
            "presence" in joined_absent or "screen" in joined_absent,
            f"fallback absent-signals must list presence/screen "
            f"as unavailable so claims about owner activity stay "
            f"flagged; got absent={absent}",
        )

    def test_caller_can_supply_per_turn_system_stats(self):
        """When the daemon passes signals_present including 'system
        stats' (current perception snapshot), the audit honors it
        — claims like 'disk at 82.9%' become grounded."""
        from core.safety import audited_output
        from core.cognition import grounding_judge as gj
        captured = {}

        def _capture(*, text, signals_present, signals_absent,
                     few_shots=None, model=None):
            captured["present"] = signals_present
            return []

        with mock.patch.object(gj, "judge", side_effect=_capture):
            audited_output.audit_assistant_text(
                "Root disk is at 82.9%.",
                surface="daemon_cycle",
                signals_present=["system stats"],
                signals_absent=[],
            )
        # Caller's "system stats" must be in the present list,
        # not replaced by fallback.
        present = captured["present"] or []
        self.assertIn(
            "system stats", present,
            "explicit system stats from caller must reach the judge",
        )


# ── Judge prompt vocabulary patch ────────────────────────────────────


class JudgePromptRecognizesConfiguredModelIdentity(unittest.TestCase):
    """REGRESSION GUARD: the judge prompt's GROUNDED-cases section
    explicitly mentions configured model identity, so even with
    the manifest fix the prompt's instruction reinforces the
    correct verdict."""

    def test_judge_prompt_mentions_configured_model_identity(self):
        from core.cognition.grounding_judge import _build_judge_prompt
        prompt = _build_judge_prompt(
            text="example", signals_present=[], signals_absent=[],
            few_shots=[],
        )
        # The grounded-cases instruction block must mention
        # configured model identity / model_config-style language
        # so the judge knows model-name claims are grounded when
        # the configured-model signal is present.
        prompt_lower = prompt.lower()
        self.assertTrue(
            ("configured model" in prompt_lower)
            or ("model identity" in prompt_lower
                and "configured" in prompt_lower)
            or ("model_config" in prompt_lower),
            "judge prompt must explicitly recognize configured "
            "model identity as grounded — without this, the "
            "manifest fix may still leave the false-positive open",
        )


class DaemonChatPerTurnManifest(unittest.TestCase):
    """REGRESSION GUARD: daemon.handle_message must pass per-turn
    perception receipts to the audit. The fallback manifest is only
    for stable / bounded-fresh facts; it deliberately marks system
    stats absent. Since handle_message puts perception_snapshot()
    output into the synthesis prompt, it must also tell the audit
    that system stats were present for this turn."""

    def test_handle_message_builds_chat_audit_manifest_from_snapshot(self):
        src = (REPO / "daemon" / "maez_daemon.py").read_text()
        start = src.find("def handle_message(")
        self.assertGreater(start, 0, "handle_message() not found")
        end = src.find("\n    def ", start + 1)
        body = src[start:end if end > start else len(src)]

        snap_idx = body.find("snap = perception_snapshot()")
        audit_idx = body.find("reply = audit_assistant_text(")
        self.assertGreater(snap_idx, 0, "handle_message must capture perception snapshot")
        self.assertGreater(audit_idx, snap_idx, "audit must happen after snapshot capture")

        pre_audit = body[snap_idx:audit_idx]
        self.assertIn(
            "_chat_signals_present",
            pre_audit,
            "handle_message must build an explicit chat audit manifest "
            "from the turn's perception snapshot before auditing",
        )
        self.assertIn(
            "system stats",
            pre_audit,
            "handle_message must mark system stats present because the "
            "same perception snapshot is shown to the model",
        )

        audit_call = body[audit_idx:body.find(")", audit_idx) + 1]
        self.assertIn(
            "signals_present=_chat_signals_present",
            audit_call,
            "handle_message must pass the per-turn chat manifest to "
            "audit_assistant_text, not rely on fallback-only receipts",
        )
        self.assertIn(
            "signals_absent=_chat_signals_absent",
            audit_call,
            "handle_message must pass absent per-turn signals too so "
            "presence/screen/calendar claims stay constrained",
        )


if __name__ == "__main__":
    unittest.main()
