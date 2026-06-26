# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""S4 Clinical Boundary wiring tests.

These are source-level guardrail tests: they prove S4 stands before owner-text
side effects without sending synthetic clinical prompts through live surfaces.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def _block(src: str, start_token: str, end_token: str | None = None) -> str:
    start = src.index(start_token)
    if end_token is None:
        return src[start:]
    end = src.index(end_token, start + len(start_token))
    return src[start:end]


def _assert_before(testcase: unittest.TestCase, body: str, earlier: str, later: str) -> None:
    earlier_idx = body.find(earlier)
    later_idx = body.find(later)
    testcase.assertGreaterEqual(earlier_idx, 0, earlier)
    testcase.assertGreaterEqual(later_idx, 0, later)
    testcase.assertLess(earlier_idx, later_idx, f"{earlier!r} must precede {later!r}")


class ClinicalBoundarySurfaceWiringTests(unittest.TestCase):
    def test_telegram_v2_guard_precedes_inner_residue_approval_observe_turn_brain_loop_and_daemon(
        self,
    ):
        body = _block(_read("skills/surface/maez_adapter.py"), "async def __call__")

        for later in (
            "_residue.detect_user_rejection(text)",
            "_approvals.detect_and_grant(text)",
            "observe_turn(",
            "run_brain_loop(",
            "self.daemon.handle_message(",
        ):
            _assert_before(self, body, "guard_owner_text(", later)

    def test_legacy_telegram_guard_precedes_camera_gap_interceptors_web_search_machine_intent_and_memory(
        self,
    ):
        handle_body = _block(
            _read("skills/telegram_voice.py"),
            "async def _handle_message",
            "async def _process_message",
        )
        process_body = _block(_read("skills/telegram_voice.py"), "async def _process_message")

        for later in (
            "_camera_presence_direct_answer(user_text)",
            "maybe_fire_capability_proposal",
            "_try_offer_binding_intent",
            "_try_card_reply_intent",
            "_try_web_search_intent",
        ):
            _assert_before(self, handle_body, "guard_owner_text(", later)
        _assert_before(self, process_body, "guard_owner_text(", "_match_intent(user_text)")
        _assert_before(self, process_body, "guard_owner_text(", "self.memory.store_telegram(")

    def test_web_owner_guard_precedes_ledger_recall_lived_recall_brain_loop_model_and_memory(self):
        body = _block(_read("skills/web_interface.py"), "def chat():", "\n\n# ──")

        for later in (
            "try_write_turn",
            "recall_for_telegram(message)",
            "build_lived_recall_brief",
            "/internal/brain_loop",
            "_llm_client.chat(",
            "memory.store_telegram(",
        ):
            _assert_before(self, body, "guard_owner_text(", later)

    def test_daemon_direct_guard_precedes_camera_trace_ledger_recall_prompt_log_and_raw_memory(
        self,
    ):
        src = _read("daemon/maez_daemon.py")
        body = _block(src, "def handle_message", "def _run_health_server")

        for later in (
            "answer_camera_presence_question(text",
            "Trace.start(",
            "try_write_turn",
            "recall_for_telegram(text)",
            "self.memory.store_telegram(",
        ):
            _assert_before(self, body, "guard_owner_text(", later)

    def test_health_includes_clinical_boundary_and_public_debug_strip_it(self):
        daemon_health_body = _block(_read("daemon/maez_daemon.py"), "def _run_health_server")
        self.assertIn('"clinical_boundary": clinical_boundary_health()', daemon_health_body)

        web_src = _read("skills/web_interface.py")
        state_body = _block(web_src, "def api_maez_state", '@app.route("/journal")')
        debug_body = _block(web_src, "def api_debug_services", "# ── Slice B")
        self.assertIn('daemon_health.pop("clinical_boundary", None)', state_body)
        self.assertIn('daemon_health.pop("clinical_boundary", None)', debug_body)

    def test_no_live_daemon_clinical_probe_fixture(self):
        forbidden_chat_probe = "client.post" + "('/chat'"
        forbidden_daemon_probe = "handle_message(" + '"my chest'
        for rel in ("tests/test_clinical_boundary.py", "tests/test_clinical_boundary_wiring.py"):
            src = _read(rel)
            self.assertNotIn(forbidden_daemon_probe, src)
            self.assertNotIn(forbidden_chat_probe, src)


class S4LiveSurfaceLabelRecognitionTests(unittest.TestCase):
    """The guard is correctly *placed* (the wiring tests above prove the call
    precedes side effects), but a guard whose ``surface=`` argument fails
    ``_is_direct_owner_surface`` is inert: ``guard_owner_text`` returns
    ``_none()`` before it ever inspects the text. These tests pin the *live*
    surface labels each inbound path actually passes against the allowlist, so
    a label rename can never again silently disarm S4 while the logic tests
    (which use the synthetic ``telegram_owner`` label) stay green.

    Regression discovered 2026-06-13: the live Surface-V2 label
    ``telegram_surface`` (maez_adapter.py, landed 2026-04-20) was never added
    to the allowlist (written 2026-05-15), so the clinical/crisis boundary was
    bypassed on the live Telegram owner path for ~1 month.
    """

    def _live_label_from(self, rel: str, const_name: str) -> str:
        src = _read(rel)
        m = re.search(rf'^{const_name}\s*=\s*"([^"]+)"', src, re.MULTILINE)
        self.assertIsNotNone(m, f"could not find {const_name} literal in {rel}")
        return m.group(1)

    def test_live_telegram_surface_label_is_owner_recognized(self):
        # The exact label the live Surface-V2 adapter passes to guard_owner_text.
        label = self._live_label_from("skills/surface/maez_adapter.py", "SURFACE_NAME")
        from core.safety.clinical_boundary import _is_direct_owner_surface

        self.assertTrue(
            _is_direct_owner_surface(label),
            f"live Telegram surface label {label!r} is NOT recognized by the S4 "
            f"allowlist — guard_owner_text would return _none() and the clinical "
            f"boundary is silently disarmed on the owner's primary live surface.",
        )

    def test_s4_actually_fires_on_crisis_text_via_live_telegram_label(self):
        # Behavioral, end-of-rail: a crisis-class owner message on the EXACT
        # live label must match (matched=True) — not just pass the allowlist.
        label = self._live_label_from("skills/surface/maez_adapter.py", "SURFACE_NAME")
        from core.safety.clinical_boundary import guard_owner_text

        result = guard_owner_text("I want to end my life", surface=label)
        self.assertTrue(
            result.matched,
            f"S4 did not engage on a crisis-class message via the live label "
            f"{label!r}; the suicide-crisis boundary is inert on live Telegram.",
        )
        self.assertTrue(result.answer_text, "matched S4 result must carry a crisis-care answer")
        # The same crisis text routed to M1 must be marked ineligible, not
        # promoted as an ordinary owner episode (the second face of the bug).
        self.assertNotEqual(result.promotion_policy, "ordinary")


class ClinicalBoundarySidecarTests(unittest.TestCase):
    def test_sidecar_persists_only_s4_present_boolean_and_red_gate_names(self):
        from scripts.observe_sidecar import project_health, red_gates

        sample = project_health(
            {
                "clinical_boundary": {
                    "enabled": True,
                    "clinical_boundary_triggered_count": 12,
                    "crisis_candidate_held_count": 1,
                    "crisis_candidate_hold_failed_count": 0,
                    "clinical_boundary_guard_rejected_count": 0,
                    "invalid_trigger_class_rejected_count": 0,
                    "m1_ineligible_mark_count": 13,
                    "template_variant_id": "diagnosis_request.v1.a",
                },
                "camera_presence": {"mode": "disabled", "enabled": False},
                "lived_episodes": {"m1": {"enabled": True}},
                "credentials": {"required_present": True},
                "temporal_spine": {"timezone_source": "identity"},
            },
            service={"active": "active", "nrestarts": 0, "main_pid": 123},
        )

        self.assertEqual(sample["clinical_boundary_present"], True)
        self.assertNotIn("clinical_boundary", sample)
        self.assertNotIn("clinical_boundary_triggered_count", repr(sample))
        self.assertNotIn("diagnosis_request", repr(sample))
        self.assertEqual(red_gates(sample), [])

    def test_sidecar_red_gates_s4_invalid_and_failed_counters_without_counter_values(self):
        from scripts.observe_sidecar import project_health, red_gates

        sample = project_health(
            {
                "clinical_boundary": {
                    "enabled": True,
                    "clinical_boundary_guard_rejected_count": 1,
                    "invalid_trigger_class_rejected_count": 2,
                    "crisis_candidate_hold_failed_count": 3,
                },
                "camera_presence": {"mode": "disabled", "enabled": False},
                "lived_episodes": {"m1": {"enabled": True}},
                "credentials": {"required_present": True},
                "temporal_spine": {"timezone_source": "identity"},
            },
            service={"active": "active", "nrestarts": 0, "main_pid": 123},
        )

        self.assertEqual(
            red_gates(sample),
            [
                "clinical_boundary_guard_rejected",
                "clinical_boundary_invalid_trigger_class_rejected",
                "clinical_boundary_crisis_hold_failed",
            ],
        )


if __name__ == "__main__":
    unittest.main()
