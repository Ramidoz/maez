"""Direction (b): focused-cognition synthesis for Telegram photo turns.

The live witness proved vision works (success=True analysis_chars=342) but the
~megaprompt's "Vision: Maez cannot see" broken-systems block overrode the present
analysis. The fix synthesizes photo turns over a BOUNDED working set (analysis +
caption + voice + faithful instruction), never the full megaprompt.
"""

import sys
import unittest
from dataclasses import dataclass
from types import SimpleNamespace
from unittest import mock

from core.routing.focused_cognition import (
    FocusedResult,
    photo_freshness_search_query,
    photo_freshness_web_search_enabled,
    synthesize_photo_turn,
)


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
    def test_photo_freshness_query_extracts_model_names_from_image(self):
        query = photo_freshness_search_query(
            caption="Check out anthropic's latest model",
            analysis_text=(
                'The image title reads "Claude Mythos 5 and Fable 5". '
                "A benchmark table compares Claude Mythos 5 / Fable 5 against GPT 5.5."
            ),
        )

        self.assertIsNotNone(query)
        assert query is not None
        self.assertIn("Anthropic", query)
        self.assertIn("Claude Mythos 5", query)
        self.assertIn("Fable 5", query)
        self.assertIn("latest", query.lower())

    def test_photo_freshness_query_ignores_plain_description(self):
        query = photo_freshness_search_query(
            caption="what is this?",
            analysis_text="The image shows a red circle and a blue square.",
        )

        self.assertIsNone(query)

    def test_photo_freshness_query_ignores_person_focused_news(self):
        query = photo_freshness_search_query(
            caption="latest news about Sam Altman at OpenAI",
            analysis_text=(
                "The image shows a person named Sam Altman on a conference stage "
                "with an OpenAI logo behind him."
            ),
        )

        self.assertIsNone(query)

    def test_photo_freshness_query_does_not_treat_model_name_as_person(self):
        query = photo_freshness_search_query(
            caption="check the latest model",
            analysis_text="The image shows Claude Mythos 5 and Fable 5 in a benchmark table.",
        )

        self.assertIsNotNone(query)
        assert query is not None
        self.assertIn("Claude Mythos 5", query)

    def test_photo_freshness_web_search_is_default_off(self):
        with mock.patch.dict("os.environ", {}, clear=True):
            self.assertFalse(photo_freshness_web_search_enabled())

    def test_photo_freshness_web_search_can_be_owner_enabled(self):
        with mock.patch.dict(
            "os.environ",
            {"MAEZ_PHOTO_FRESHNESS_WEB_SEARCH": "1"},
            clear=True,
        ):
            self.assertTrue(photo_freshness_web_search_enabled())

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

    def test_fresh_web_context_is_e2_and_valid_citation(self):
        store = {}

        def fake_chat(*, model, messages, think, options):
            store["messages"] = messages
            return SimpleNamespace(
                message=SimpleNamespace(
                    content=(
                        "The chart appears to show Claude Mythos 5 and Fable 5 [E1], "
                        "and fresh web evidence says Anthropic announced them today [E2]."
                    )
                )
            )

        result = synthesize_photo_turn(
            analysis_text='The chart title reads "Claude Mythos 5 and Fable 5".',
            caption="Check out anthropic's latest model",
            surface="telegram_surface",
            fresh_context=(
                "[WEB SEARCH: 'Anthropic Claude Mythos 5 Fable 5 latest'] "
                "1 results — 2026-06-09\n"
                "  1. Claude Fable 5 and Claude Mythos 5\n"
                "     Anthropic announced Claude Fable 5 and Mythos 5 today."
            ),
            chat_fn=fake_chat,
            model="m",
        )

        system = store["messages"][0]["content"]
        self.assertEqual(result.receipt_reason, "cited_ok")
        self.assertEqual(result.cited_ids, ["E1", "E2"])
        self.assertIn("FRESH WORLD CHECK", system)
        self.assertIn("cite [E2]", system)

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


@dataclass(frozen=True)
class _FakeContradictionReceipt:
    reason: str
    sense_note: str | None = None
    claim_count: int = 1
    contradiction_count: int = 0
    latency_ms: int | None = 12
    model_id: str | None = "fake-nli"
    revision: str | None = "fake-rev"
    sha256: str | None = "fake-sha"
    claim_limit_exceeded: bool = False


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

    def test_flag_off_does_not_import_or_call_contradiction_checker(self):
        chat, box = _scripted_chat(["The screenshot shows Reddit [E1]."])
        module_name = "core.routing.photo_contradiction"
        real_import = __import__

        def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name == module_name or (
                name == "core.routing" and "photo_contradiction" in fromlist
            ):
                raise AssertionError("must not import contradiction organ when flag off")
            return real_import(name, globals, locals, fromlist, level)

        for env in ({}, {"MAEZ_PHOTO_CONTRADICTION_SENSE": ""}):
            with self.subTest(env=env):
                box["i"] = 0
                previous_module = sys.modules.pop(module_name, None)
                try:
                    with mock.patch.dict("os.environ", env, clear=True), mock.patch(
                        "builtins.__import__",
                        side_effect=guarded_import,
                    ):
                        r = synthesize_photo_turn(
                            analysis_text=ANALYSIS,
                            caption=CAPTION,
                            surface="telegram_surface",
                            chat_fn=chat,
                            model="m",
                        )
                    self.assertNotIn(module_name, sys.modules)
                finally:
                    if previous_module is not None:
                        sys.modules[module_name] = previous_module

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


class PhotoContradictionSenseIntegration(unittest.TestCase):
    def _flag_on(self):
        return mock.patch.dict(
            "os.environ",
            {"MAEZ_PHOTO_CONTRADICTION_SENSE": "1"},
            clear=True,
        )

    def _patch_contradiction(self, receipts):
        fake_verifier = object()
        return (
            fake_verifier,
            mock.patch(
                "core.routing.photo_contradiction.LocalNLIContradictionVerifier",
                return_value=fake_verifier,
            ),
            mock.patch(
                "core.routing.photo_contradiction.check_photo_contradictions",
                side_effect=receipts,
            ),
        )

    def test_clear_receipt_does_not_revise(self):
        clear = _FakeContradictionReceipt(
            reason="clear",
            claim_count=2,
            contradiction_count=0,
        )
        chat, box = _scripted_chat(["The screenshot shows Reddit [E1]."])
        _verifier, verifier_patch, check_patch = self._patch_contradiction([clear])

        with self._flag_on(), verifier_patch, check_patch as check:
            result = synthesize_photo_turn(
                analysis_text=ANALYSIS,
                caption=CAPTION,
                surface="telegram_surface",
                chat_fn=chat,
                model="m",
            )

        self.assertEqual(result.receipt_reason, "cited_ok")
        self.assertEqual(result.contradiction_receipt, "clear")
        self.assertEqual(result.contradiction_claim_count, 2)
        self.assertEqual(result.contradiction_count, 0)
        self.assertFalse(result.contradiction_claim_limit_exceeded)
        self.assertEqual(box["i"], 1)
        self.assertEqual(check.call_count, 1)
        self.assertEqual(check.call_args.kwargs["premise"], ANALYSIS)
        self.assertEqual(check.call_args.kwargs["reply"], result.reply)

    def test_contradiction_revises_and_must_recheck_before_revised_clear(self):
        sense_note = (
            "Photo contradiction sense: claim conflicts with E1; revise from E1."
        )
        first = _FakeContradictionReceipt(
            reason="trust_demoted",
            sense_note=sense_note,
            contradiction_count=1,
        )
        second = _FakeContradictionReceipt(
            reason="clear",
            claim_count=1,
            contradiction_count=0,
        )
        systems: list[str] = []
        replies = iter(
            [
                "The screenshot shows a YouTube video [E1].",
                "The screenshot shows a Reddit thread [E1].",
            ]
        )

        def chat_fn(**kwargs):
            systems.append(kwargs["messages"][0]["content"])
            return SimpleNamespace(
                message=SimpleNamespace(content=next(replies, ""))
            )

        _verifier, verifier_patch, check_patch = self._patch_contradiction(
            [first, second]
        )
        with self._flag_on(), verifier_patch, check_patch as check:
            result = synthesize_photo_turn(
                analysis_text=ANALYSIS,
                caption=CAPTION,
                surface="telegram_surface",
                chat_fn=chat_fn,
                model="m",
            )

        self.assertEqual(result.reply, "The screenshot shows a Reddit thread [E1].")
        self.assertEqual(result.contradiction_receipt, "revised_clear")
        self.assertEqual(result.contradiction_count, 0)
        self.assertEqual(len(systems), 2)
        self.assertIn(sense_note, systems[1])
        self.assertIn("sense, not a verdict", systems[1])
        self.assertIn("still believe what you saw", systems[1])
        self.assertEqual(check.call_count, 2)
        self.assertEqual(
            check.call_args_list[0].kwargs["reply"],
            "The screenshot shows a YouTube video [E1].",
        )
        self.assertEqual(
            check.call_args_list[1].kwargs["reply"],
            "The screenshot shows a Reddit thread [E1].",
        )

    def test_revision_still_contradicting_is_not_laundered_clear(self):
        first = _FakeContradictionReceipt(
            reason="trust_demoted",
            sense_note="Photo contradiction sense: YouTube conflicts with Reddit.",
            contradiction_count=1,
        )
        second = _FakeContradictionReceipt(
            reason="trust_demoted",
            sense_note="Photo contradiction sense: video still conflicts.",
            contradiction_count=1,
        )
        chat, box = _scripted_chat(
            [
                "The screenshot shows a YouTube video [E1].",
                "It is still definitely YouTube [E1].",
            ]
        )
        _verifier, verifier_patch, check_patch = self._patch_contradiction(
            [first, second]
        )

        with self._flag_on(), verifier_patch, check_patch as check:
            result = synthesize_photo_turn(
                analysis_text=ANALYSIS,
                caption=CAPTION,
                surface="telegram_surface",
                chat_fn=chat,
                model="m",
            )

        self.assertEqual(result.reply, "It is still definitely YouTube [E1].")
        self.assertEqual(result.contradiction_receipt, "trust_demoted")
        self.assertEqual(result.contradiction_count, 1)
        self.assertEqual(box["i"], 2)
        self.assertEqual(check.call_count, 2)

    def test_partial_unchecked_receipt_is_not_laundered_clear(self):
        receipt = _FakeContradictionReceipt(
            reason="partial_unchecked",
            claim_count=5,
            contradiction_count=0,
            claim_limit_exceeded=True,
        )
        chat, box = _scripted_chat(["The screenshot shows Reddit [E1]."])
        _verifier, verifier_patch, check_patch = self._patch_contradiction([receipt])

        with self._flag_on(), verifier_patch, check_patch:
            result = synthesize_photo_turn(
                analysis_text=ANALYSIS,
                caption=CAPTION,
                surface="telegram_surface",
                chat_fn=chat,
                model="m",
            )

        self.assertEqual(result.contradiction_receipt, "partial_unchecked")
        self.assertEqual(result.contradiction_claim_count, 5)
        self.assertEqual(result.contradiction_count, 0)
        self.assertTrue(result.contradiction_claim_limit_exceeded)
        self.assertEqual(box["i"], 1)

    def test_deterministic_fallback_skips_contradiction_checker_when_flag_on(self):
        chat, box = _scripted_chat([""])

        with self._flag_on(), mock.patch(
            "core.routing.photo_contradiction.LocalNLIContradictionVerifier"
        ) as verifier, mock.patch(
            "core.routing.photo_contradiction.check_photo_contradictions",
            side_effect=AssertionError("deterministic fallback is grounded"),
        ) as check:
            result = synthesize_photo_turn(
                analysis_text=ANALYSIS,
                caption=CAPTION,
                surface="telegram_surface",
                chat_fn=chat,
                model="m",
            )

        self.assertEqual(result.receipt_reason, "deterministic_fallback")
        self.assertIsNone(result.contradiction_receipt)
        self.assertEqual(box["i"], 1)
        verifier.assert_not_called()
        check.assert_not_called()

    def test_revision_failure_keeps_original_reply_and_retry_failed_receipt(self):
        first = _FakeContradictionReceipt(
            reason="trust_demoted",
            sense_note="Photo contradiction sense: YouTube conflicts with Reddit.",
            contradiction_count=1,
        )

        def chat_fn(**_kwargs):
            if not hasattr(chat_fn, "calls"):
                chat_fn.calls = 0
            chat_fn.calls += 1
            if chat_fn.calls == 1:
                return SimpleNamespace(
                    message=SimpleNamespace(
                        content="The screenshot shows a YouTube video [E1]."
                    )
                )
            raise RuntimeError("revision model down")

        _verifier, verifier_patch, check_patch = self._patch_contradiction([first])
        with self._flag_on(), verifier_patch, check_patch as check:
            result = synthesize_photo_turn(
                analysis_text=ANALYSIS,
                caption=CAPTION,
                surface="telegram_surface",
                chat_fn=chat_fn,
                model="m",
            )

        self.assertEqual(result.reply, "The screenshot shows a YouTube video [E1].")
        self.assertEqual(result.contradiction_receipt, "retry_failed")
        self.assertEqual(result.contradiction_count, 1)
        self.assertEqual(chat_fn.calls, 2)
        self.assertEqual(check.call_count, 1)


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
