from __future__ import annotations

import itertools
import unittest


def _today_oracle(s) -> str:
    """Reference replica of handle_message's current routing order.

    Slice 1 deliberately preserves the B4 bug: honest-empty wins before focused.
    """
    if s.clinical_matched:
        return "CLINICAL"
    if s.camera_answer is not None:
        return "CAMERA"
    if s.authoritative_tool_reply:
        return "TOOL"
    if s.echo_reply:
        return "ECHO"
    if s.honest_empty_candidate:
        return "HONEST_EMPTY"
    if s.focused_candidate:
        return "FOCUSED"
    return "LEGACY"


class ResolveReplyModeOracleTests(unittest.TestCase):
    def test_matches_today_for_full_signal_matrix(self):
        from core.routing.reply_mode import ReplyDecisionSignals, resolve_reply_mode

        bool_fields = [
            "clinical_matched",
            "authoritative_tool_reply",
            "echo_reply",
            "honest_empty_candidate",
            "focused_candidate",
        ]
        for combo in itertools.product([False, True], repeat=len(bool_fields)):
            for camera in (None, "the camera is on"):
                kw = dict(zip(bool_fields, combo, strict=True))
                kw["camera_answer"] = camera
                signals = ReplyDecisionSignals(**kw)
                with self.subTest(**kw):
                    self.assertEqual(
                        resolve_reply_mode(signals).mode.value,
                        _today_oracle(signals),
                    )

    def test_skip_tail_only_for_clinical_and_camera(self):
        from core.routing.reply_mode import (
            ReplyDecisionSignals,
            ReplyMode,
            resolve_reply_mode,
        )

        for kw, expect_skip in [
            ({"clinical_matched": True}, True),
            ({"camera_answer": "on"}, True),
            ({"authoritative_tool_reply": True}, False),
            ({"echo_reply": True}, False),
            ({"honest_empty_candidate": True}, False),
            ({"focused_candidate": True}, False),
            ({}, False),
        ]:
            decision = resolve_reply_mode(ReplyDecisionSignals(**kw))
            with self.subTest(**kw):
                self.assertEqual(decision.skip_tail, expect_skip)
                if expect_skip:
                    self.assertEqual(
                        decision.skip_reason,
                        "deterministic_policy_reply",
                    )
                    self.assertIn(
                        decision.mode,
                        (ReplyMode.CLINICAL, ReplyMode.CAMERA),
                    )

    def test_call_purpose_matches_today_labels(self):
        from core.routing.reply_mode import ReplyDecisionSignals, resolve_reply_mode

        self.assertEqual(
            resolve_reply_mode(
                ReplyDecisionSignals(authoritative_tool_reply=True)
            ).call_purpose,
            "authoritative_tool",
        )
        self.assertEqual(
            resolve_reply_mode(ReplyDecisionSignals(echo_reply=True)).call_purpose,
            "echo_reply",
        )
        self.assertEqual(
            resolve_reply_mode(
                ReplyDecisionSignals(honest_empty_candidate=True)
            ).call_purpose,
            "honest_empty",
        )
        self.assertEqual(
            resolve_reply_mode(
                ReplyDecisionSignals(focused_candidate=True)
            ).call_purpose,
            "legacy_candidate",
        )
        self.assertEqual(
            resolve_reply_mode(ReplyDecisionSignals()).call_purpose,
            "llm_synthesis",
        )
