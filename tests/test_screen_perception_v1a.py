from __future__ import annotations

import time
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import skills.screen_perception as sp
from skills.screen_perception import ScreenObservation


class ScreenObservationShapeTests(unittest.TestCase):
    def _obs(self, **kw):
        base = dict(
            activity="",
            application="",
            detail="",
            focus_level="",
            raw_response="",
            timestamp=0.0,
            success=False,
        )
        base.update(kw)
        return ScreenObservation(**base)

    def test_new_fields_default(self):
        o = self._obs(state="ok", success=True, activity="coding")
        self.assertFalse(o.third_party_content_present)
        self.assertEqual(o.egress_origin_class, "owner_screen_context")

    def test_paused_and_excluded_are_honest_blind(self):
        for state in ("paused", "excluded"):
            with self.subTest(state=state):
                o = self._obs(state=state, detail="SHOULD_NOT_APPEAR")
                ctx = o.format_for_context()
                self.assertNotIn("SHOULD_NOT_APPEAR", ctx)

    def test_observation_defaults_to_unvalidated_provenance(self):
        # A screen glance is one uncorroborated model-described frame; its
        # provenance marker must travel with it so nothing downstream mistakes
        # it for ground truth (2026-07-09 covenant stamp).
        o = self._obs(state="ok", success=True, activity="coding")
        self.assertEqual(o.validation, "unvalidated_single_frame")

    def test_successful_context_carries_honest_hedge(self):
        # The prompt-facing string must frame the glance as a first impression,
        # not fact — "looked like", not "Activity:".
        o = self._obs(
            state="ok", success=True, activity="coding", timestamp=time.time()
        )
        ctx = o.format_for_context()
        self.assertIn("unvalidated glance", ctx)
        self.assertIn("looked like", ctx.lower())
        self.assertIn("not fact", ctx.lower())
        # Memory-facing string is hedged too — no bare "Screen observation: X" fact.
        mem = o.format_for_memory()
        self.assertIn("unvalidated glance", mem)

    def test_context_marks_missing_observation_fields_unknown(self):
        o = self._obs(
            state="ok",
            success=True,
            activity="Browsing",
            application="",
            detail="",
            focus_level="",
            timestamp=time.time(),
        )

        ctx = o.format_for_context()

        self.assertIn("activity: Browsing", ctx)
        self.assertIn("application: unknown", ctx)
        self.assertIn(
            "specific window/content: not discernible at this resolution",
            ctx,
        )
        self.assertIn("focus: unknown", ctx)
        self.assertIn("third-party content: not indicated", ctx)

    def test_owner_fact_receipt_carries_field_scope(self):
        from daemon.maez_daemon import _screen_perception_owner_fact

        o = self._obs(
            state="ok",
            success=True,
            activity="Browsing",
            application="",
            detail="",
            focus_level="",
            timestamp=time.time(),
        )

        with mock.patch.dict(os.environ, {"MAEZ_SCREEN_PERCEPTION": "1"}, clear=False):
            block, receipt = _screen_perception_owner_fact(o, now=time.time())

        self.assertIn("application: unknown", block)
        self.assertIsNotNone(receipt)
        self.assertEqual(receipt["fields"]["activity"], "Browsing")
        self.assertIn("application", receipt["unknown_fields"])
        self.assertIn("specific_window_content", receipt["unknown_fields"])
        self.assertEqual(receipt["evidence"], block)


class PausePrimitiveTests(unittest.TestCase):
    def test_paused_skips_capture_probe_vision(self):
        tmp = tempfile.mkdtemp()
        pause = os.path.join(tmp, "paused")
        open(pause, "w").close()

        with mock.patch.dict(
            os.environ,
            {"MAEZ_SCREEN_PERCEPTION": "1", "MAEZ_SCREEN_PAUSE_FILE": pause},
            clear=False,
        ), mock.patch.object(sp, "_capture_screenshot") as cap, mock.patch.object(
            sp, "_vision_endpoint_probe"
        ) as probe, mock.patch.object(sp.requests, "post") as post:
            obs = sp.observe()

        self.assertEqual(obs.state, "paused")
        cap.assert_not_called()
        probe.assert_not_called()
        post.assert_not_called()


class PreflightExclusionTests(unittest.TestCase):
    def test_excluded_app_is_never_looked_at(self):
        with tempfile.TemporaryDirectory() as tmp:
            pause = os.path.join(tmp, "absent")
            with mock.patch.dict(
                os.environ,
                {"MAEZ_SCREEN_PERCEPTION": "1", "MAEZ_SCREEN_PAUSE_FILE": pause},
                clear=False,
            ), mock.patch(
                "core.memory.ambient.active_window_for_preflight",
                return_value={"class": "KeePassXC", "title": "vault"},
            ), mock.patch.object(sp, "_vision_endpoint_probe") as probe, mock.patch.object(
                sp, "_capture_screenshot"
            ) as cap, mock.patch.object(sp.requests, "post") as post:
                obs = sp.observe()

        self.assertEqual(obs.state, "excluded")
        probe.assert_not_called()
        cap.assert_not_called()
        post.assert_not_called()

    def test_non_excluded_app_proceeds_to_probe(self):
        with tempfile.TemporaryDirectory() as tmp:
            pause = os.path.join(tmp, "absent")
            with mock.patch.dict(
                os.environ,
                {"MAEZ_SCREEN_PERCEPTION": "1", "MAEZ_SCREEN_PAUSE_FILE": pause},
                clear=False,
            ), mock.patch(
                "core.memory.ambient.active_window_for_preflight",
                return_value={"class": "code", "title": "plan.md"},
            ), mock.patch.object(sp, "_vision_endpoint_probe", return_value=False) as probe:
                obs = sp.observe()

        probe.assert_called_once()
        self.assertEqual(obs.state, "unavailable")


class ThirdPartyMinimizationTests(unittest.TestCase):
    def test_vision_prompt_requests_third_party_flag(self):
        self.assertIn("THIRD_PARTY:", sp.VISION_PROMPT)

    def test_parse_vision_response_carries_third_party_field(self):
        parsed = sp._parse_vision_response(
            "ACTIVITY: reading\n"
            "APPLICATION: mail\n"
            "DETAIL: inbox\n"
            "FOCUS_LEVEL: browsing\n"
            "THIRD_PARTY: yes\n"
        )
        self.assertEqual(parsed["third_party"], "yes")

    def test_third_party_detail_is_minimized(self):
        parsed = {
            "activity": "reading email",
            "application": "thunderbird",
            "detail": "Email from Jane Doe about the lawsuit settlement",
            "focus_level": "browsing",
            "third_party": "yes",
        }
        obs = sp._apply_screen_governance(parsed, timestamp=0.0, raw="r")
        self.assertTrue(obs.third_party_content_present)
        self.assertEqual(obs.egress_origin_class, "third_party_private_context")
        self.assertNotIn("Jane", obs.detail)
        self.assertNotIn("lawsuit", obs.detail)
        self.assertNotIn("Jane", obs.format_for_context())

    def test_uncertain_or_missing_is_third_party(self):
        parsed = {
            "activity": "x",
            "application": "unknown",
            "detail": "d",
            "focus_level": "x",
            "third_party": "",
        }
        self.assertTrue(sp._looks_third_party(parsed))
        self.assertTrue(sp._looks_third_party({**parsed, "third_party": "unsure"}))
        self.assertTrue(
            sp._looks_third_party({**parsed, "application": "Signal", "third_party": "no"})
        )

    def test_missing_third_party_field_is_marked_unknown_not_seen(self):
        parsed = {
            "activity": "reading",
            "application": "unknown",
            "detail": "not readable",
            "focus_level": "browsing",
            "third_party": "",
        }
        obs = sp._apply_screen_governance(parsed, timestamp=time.time(), raw="r")

        self.assertTrue(obs.third_party_content_present)
        self.assertIn("third_party_content", obs.field_scope()["unknown_fields"])
        self.assertNotIn("third_party_content", obs.field_scope()["available_fields"])
        self.assertIn(
            "third-party content: unknown; private details minimized",
            obs.format_for_context(),
        )
        self.assertNotIn(
            "third-party content: present",
            obs.format_for_context(),
        )

    def test_owner_only_keeps_detail(self):
        parsed = {
            "activity": "coding",
            "application": "code",
            "detail": "editing plan.md",
            "focus_level": "deep_work",
            "third_party": "no",
        }
        obs = sp._apply_screen_governance(parsed, timestamp=0.0, raw="r")
        self.assertFalse(obs.third_party_content_present)
        self.assertEqual(obs.egress_origin_class, "owner_screen_context")
        self.assertIn("plan.md", obs.detail)


class ScreenEgressOriginTests(unittest.TestCase):
    def _decide(self, origin):
        from core.egress.gate import EgressRequest, EgressSegment, decide_egress

        return decide_egress(
            EgressRequest(
                call_class="cloud_model_inference",
                destination="anthropic",
                segments=[
                    EgressSegment(
                        text="email a@b.test",
                        origin_class=origin,
                        source_ref="raw:screen",
                        redaction_allowed=True,
                    )
                ],
                caller="screen-v1a",
                request_id="t",
            )
        )

    def test_owner_screen_context_redacts(self):
        decision = self._decide("owner_screen_context")
        self.assertEqual(decision.decision, "redact")
        self.assertNotIn("a@b.test", decision.sanitized_text())

    def test_third_party_private_context_redacts(self):
        self.assertEqual(
            self._decide("third_party_private_context").decision,
            "redact",
        )


class NoDurableScreenStorageTests(unittest.TestCase):
    def test_format_for_memory_not_appended_in_daemon(self):
        src = Path("daemon/maez_daemon.py").read_text()
        self.assertNotIn(
            "format_for_memory()",
            src,
            "v1a must not append screen observations to durable memory",
        )
        self.assertNotIn(
            "screen_activity = self._last_screen_obs.activity",
            src,
            "v1a must not persist screen activity into memory metadata",
        )


if __name__ == "__main__":
    unittest.main()
