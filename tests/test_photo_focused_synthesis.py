"""Direction (b): focused-cognition synthesis for Telegram photo turns.

The live witness proved vision works (success=True analysis_chars=342) but the
~megaprompt's "Vision: Maez cannot see" broken-systems block overrode the present
analysis. The fix synthesizes photo turns over a BOUNDED working set (analysis +
caption + voice + faithful instruction), never the full megaprompt.
"""

import unittest
from types import SimpleNamespace

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


if __name__ == "__main__":
    unittest.main()
