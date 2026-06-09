"""Direction (b): focused-cognition synthesis for Telegram photo turns.

The live witness proved vision works (success=True analysis_chars=342) but the
~megaprompt's "Vision: Maez cannot see" broken-systems block overrode the present
analysis. The fix synthesizes photo turns over a BOUNDED working set (analysis +
caption + voice + faithful instruction), never the full megaprompt.
"""

import unittest
from types import SimpleNamespace
from unittest import mock

from core.routing.focused_cognition import FocusedResult, synthesize_photo_turn


ANALYSIS = (
    "The image is a screenshot of a Reddit thread about SpaceX's IPO. "
    "A user named LEFTSHOE18 asks whether the price is justified. There is a "
    "photo of two people at the top and several comments below."
)
CAPTION = "check this"


def _chat_returning(content):
    return lambda **_k: SimpleNamespace(message=SimpleNamespace(content=content))


def _capture_chat(store):
    def fake_chat(*, model, messages, think, options):
        store["model"] = model
        store["messages"] = messages
        store["think"] = think
        store["options"] = options
        return SimpleNamespace(
            message=SimpleNamespace(
                content="That's a Reddit thread on the SpaceX IPO [E1]."
            )
        )

    return fake_chat


class SynthesizePhotoTurn(unittest.TestCase):
    def test_returns_focused_result_with_brain_reply(self):
        result = synthesize_photo_turn(
            analysis_text=ANALYSIS,
            caption=CAPTION,
            surface="telegram_surface",
            chat_fn=_chat_returning("That's a Reddit thread on the SpaceX IPO [E1]."),
            model="m",
        )
        self.assertIsInstance(result, FocusedResult)
        self.assertIn("Reddit", result.reply)

    def test_caption_is_the_user_message(self):
        store = {}
        synthesize_photo_turn(
            analysis_text=ANALYSIS,
            caption=CAPTION,
            surface="telegram_surface",
            chat_fn=_capture_chat(store),
            model="m",
        )
        msgs = store["messages"]
        self.assertEqual(msgs[-1]["role"], "user")
        self.assertEqual(msgs[-1]["content"], CAPTION)

    def test_prompt_carries_the_analysis_as_evidence(self):
        store = {}
        synthesize_photo_turn(
            analysis_text=ANALYSIS,
            caption=CAPTION,
            surface="telegram_surface",
            chat_fn=_capture_chat(store),
            model="m",
        )
        system = store["messages"][0]["content"]
        self.assertIn("LEFTSHOE18", system)
        self.assertIn("[E1]", system)

    def test_prompt_is_bounded_and_excludes_megaprompt_contradictions(self):
        # THE CORE POINT: the focused prompt must NOT carry the broken-systems
        # "cannot see / screen perception" contradiction that derailed synthesis.
        store = {}
        synthesize_photo_turn(
            analysis_text=ANALYSIS,
            caption=CAPTION,
            surface="telegram_surface",
            chat_fn=_capture_chat(store),
            model="m",
        )
        system = store["messages"][0]["content"].lower()
        for forbidden in (
            "cannot see",
            "screen perception",
            "broken systems",
            "intentionally retired",
            "blank data",
            "vision pipeline is offline",
        ):
            self.assertNotIn(forbidden, system)
        self.assertLess(len(store["messages"][0]["content"]), 3000)

    def test_faithful_instruction_frames_first_party_sight(self):
        store = {}
        synthesize_photo_turn(
            analysis_text=ANALYSIS,
            caption=CAPTION,
            surface="telegram_surface",
            chat_fn=_capture_chat(store),
            model="m",
        )
        system = store["messages"][0]["content"].lower()
        self.assertIn("photo", system)
        self.assertTrue(
            "your own" in system or "you saw" in system or "looked" in system
        )

    def test_deterministic_fallback_on_empty_reply(self):
        result = synthesize_photo_turn(
            analysis_text=ANALYSIS,
            caption=CAPTION,
            surface="telegram_surface",
            chat_fn=_chat_returning("   "),
            model="m",
        )
        low = result.reply.lower()
        self.assertTrue(low.strip())
        self.assertNotIn("cannot see", low)
        self.assertNotIn("can't see", low)
        self.assertIn("saw", low)
        self.assertIn("reddit", low)

    def test_deterministic_fallback_on_chat_raise(self):
        def _boom(**_k):
            raise RuntimeError("brain down")

        result = synthesize_photo_turn(
            analysis_text=ANALYSIS,
            caption=CAPTION,
            surface="telegram_surface",
            chat_fn=_boom,
            model="m",
        )
        low = result.reply.lower()
        self.assertTrue(low.strip())
        self.assertNotIn("cannot see", low)
        self.assertIn("saw", low)


class ReceiptReasonField(unittest.TestCase):
    def test_focused_result_has_receipt_reason_default_none(self):
        r = FocusedResult(reply="x", cited_ids=["E1"], working_set_chars=1)
        self.assertIsNone(r.receipt_reason)
        r2 = FocusedResult(
            reply="x", cited_ids=["E1"], working_set_chars=1,
            receipt_reason="cited_ok",
        )
        self.assertEqual(r2.receipt_reason, "cited_ok")


def _scripted_chat(contents):
    """A chat_fn that yields each content in order, then '' forever. box['i']
    counts calls (so tests can assert retry happened exactly once / not at all)."""
    box = {"i": 0}

    def chat_fn(**_k):
        i = box["i"]
        box["i"] += 1
        text = contents[i] if i < len(contents) else ""
        return SimpleNamespace(message=SimpleNamespace(content=text))

    return chat_fn, box


class PhotoContradictionSenseFields(unittest.TestCase):
    def test_focused_result_has_contradiction_receipt_defaults(self):
        r = FocusedResult(reply="x", cited_ids=["E1"], working_set_chars=1)

        self.assertIsNone(r.contradiction_receipt)
        self.assertEqual(r.contradiction_claim_count, 0)
        self.assertEqual(r.contradiction_count, 0)
        self.assertIsNone(r.contradiction_latency_ms)
        self.assertIsNone(r.contradiction_model_id)
        self.assertIsNone(r.contradiction_revision)
        self.assertIsNone(r.contradiction_sha256)
        self.assertFalse(r.contradiction_claim_limit_exceeded)

    def test_flag_off_does_not_call_contradiction_checker(self):
        chat, box = _scripted_chat(["The screenshot shows Reddit [E1]."])
        for env in ({}, {"MAEZ_PHOTO_CONTRADICTION_SENSE": ""}):
            with self.subTest(env=env):
                box["i"] = 0
                with mock.patch.dict("os.environ", env, clear=True), mock.patch(
                    "core.routing.photo_contradiction.check_photo_contradictions",
                    side_effect=AssertionError("must not run when flag off"),
                ):
                    r = synthesize_photo_turn(
                        analysis_text=ANALYSIS,
                        caption=CAPTION,
                        surface="telegram_surface",
                        chat_fn=chat,
                        model="m",
                    )

                self.assertEqual(r.receipt_reason, "cited_ok")
                self.assertIsNone(r.contradiction_receipt)
                self.assertEqual(r.contradiction_claim_count, 0)
                self.assertEqual(r.contradiction_count, 0)
                self.assertIsNone(r.contradiction_latency_ms)
                self.assertIsNone(r.contradiction_model_id)
                self.assertIsNone(r.contradiction_revision)
                self.assertIsNone(r.contradiction_sha256)
                self.assertFalse(r.contradiction_claim_limit_exceeded)
                self.assertEqual(box["i"], 1)


class CitationRail(unittest.TestCase):
    A = ANALYSIS

    def test_valid_citation_first_try_is_cited_ok(self):
        chat, box = _scripted_chat(["That's a Reddit thread [E1]."])
        r = synthesize_photo_turn(analysis_text=self.A, caption="check this",
                                  surface="telegram_surface", chat_fn=chat, model="m")
        self.assertEqual(r.receipt_reason, "cited_ok")
        self.assertEqual(r.cited_ids, ["E1"])
        self.assertEqual(box["i"], 1)  # no retry

    def test_ungrounded_then_retry_recovers(self):
        chat, box = _scripted_chat(["A Reddit thread.",
                                    "A Reddit thread [E1]."])
        r = synthesize_photo_turn(analysis_text=self.A, caption="check this",
                                  surface="telegram_surface", chat_fn=chat, model="m")
        self.assertEqual(r.receipt_reason, "retry_recovered")
        self.assertEqual(r.cited_ids, ["E1"])
        self.assertIn("[E1]", r.reply)
        self.assertEqual(box["i"], 2)  # exactly one retry

    def test_ungrounded_both_times_is_deterministic_fallback(self):
        chat, box = _scripted_chat(["WWDC2024 clip, no cite.",
                                    "Still no citation here."])
        r = synthesize_photo_turn(analysis_text=self.A, caption="check this",
                                  surface="telegram_surface", chat_fn=chat, model="m")
        self.assertEqual(r.receipt_reason, "deterministic_fallback")
        self.assertEqual(r.cited_ids, ["E1"])
        self.assertIn("[E1]", r.reply)
        self.assertIn("Reddit", r.reply)            # the sight-report (analysis)
        self.assertNotIn("WWDC2024", r.reply)       # NOT the wandering reply
        self.assertNotIn("Still no citation", r.reply)
        self.assertEqual(box["i"], 2)

    def test_fake_citation_e2_is_ungrounded(self):
        chat, box = _scripted_chat(["It shows [E2] a thread.",
                                    "Now grounded [E1]."])
        r = synthesize_photo_turn(analysis_text=self.A, caption="check this",
                                  surface="telegram_surface", chat_fn=chat, model="m")
        self.assertEqual(r.receipt_reason, "retry_recovered")
        self.assertEqual(r.cited_ids, ["E1"])

    def test_e1_plus_e2_is_ungrounded(self):
        chat, box = _scripted_chat(["A thread [E1][E2].",
                                    "no cite either"])
        r = synthesize_photo_turn(analysis_text=self.A, caption="check this",
                                  surface="telegram_surface", chat_fn=chat, model="m")
        self.assertEqual(r.receipt_reason, "deterministic_fallback")
        self.assertEqual(r.cited_ids, ["E1"])

    def test_empty_brain_first_call_no_retry(self):
        chat, box = _scripted_chat([""])
        r = synthesize_photo_turn(analysis_text=self.A, caption="check this",
                                  surface="telegram_surface", chat_fn=chat, model="m")
        self.assertEqual(r.receipt_reason, "deterministic_fallback")
        self.assertEqual(box["i"], 1)               # NO wasted retry
        self.assertEqual(r.cited_ids, ["E1"])

    def test_retry_raises_falls_back(self):
        calls = {"i": 0}

        def chat_fn(**_k):
            calls["i"] += 1
            if calls["i"] == 1:
                return SimpleNamespace(message=SimpleNamespace(content="no cite"))
            raise RuntimeError("brain down on retry")

        r = synthesize_photo_turn(analysis_text=self.A, caption="check this",
                                  surface="telegram_surface", chat_fn=chat_fn, model="m")
        self.assertEqual(r.receipt_reason, "deterministic_fallback")
        self.assertEqual(r.cited_ids, ["E1"])
        self.assertEqual(calls["i"], 2)             # at most one retry, then fallback

    def test_fallback_ignores_citation_markers_in_analysis_text(self):
        # If the vision analysis itself contains literal [E#] (e.g. image text
        # like "[E2] on a button"), the deterministic fallback must NOT pick it up
        # as a citation. Fallback cited_ids must stay exactly ["E1"].
        poisoned = "The image text literally says [E2] on a button."
        chat, box = _scripted_chat(["no cite", "still no cite"])  # both ungrounded
        r = synthesize_photo_turn(analysis_text=poisoned, caption="check this",
                                  surface="telegram_surface", chat_fn=chat, model="m")
        self.assertEqual(r.receipt_reason, "deterministic_fallback")
        self.assertEqual(r.cited_ids, ["E1"])        # NOT ["E1", "E2"]
        self.assertIn("[E1]", r.reply)
        # the analysis content is still surfaced (markers neutralized, not dropped)
        self.assertIn("button", r.reply)


if __name__ == "__main__":
    unittest.main()
