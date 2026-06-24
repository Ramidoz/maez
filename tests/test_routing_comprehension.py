from __future__ import annotations

import hashlib
import inspect
import os
import unittest
from types import SimpleNamespace
from unittest import mock

from core.dispatcher.spec import (
    CompositionHint,
    CompositionSpec,
    ExternalSource,
    InventoryWitness,
    ProvenanceFraming,
    SourceAvailability,
    SubstrateSource,
)
from core.routing import routing_comprehension as rc


class RoutingComprehensionPureTests(unittest.TestCase):
    def test_decision_values_are_closed_contract(self) -> None:
        self.assertEqual(
            {decision.value for decision in rc.Decision},
            {
                "external_info_requested",
                "personal_or_relational",
                "thread_followup_answerable",
                "ambiguous",
            },
        )

    def test_parse_valid_json_decision(self) -> None:
        out = rc.parse_judge_response(
            '{"decision":"personal_or_relational","confidence":0.91,'
            '"reason_code":"owner_sharing_personal_state"}'
        )

        self.assertEqual(out.decision, rc.Decision.PERSONAL_OR_RELATIONAL)
        self.assertEqual(out.confidence, 0.91)
        self.assertEqual(out.reason_code, "owner_sharing_personal_state")

    def test_parse_valid_json_default_diagnostics_include_length_and_hash(self) -> None:
        raw = (
            '{"decision":"personal_or_relational","confidence":0.91,'
            '"reason_code":"owner_sharing_personal_state"}'
        )

        out = rc.parse_judge_response(raw)

        self.assertEqual(out.decision, rc.Decision.PERSONAL_OR_RELATIONAL)
        self.assertEqual(out.diagnostics.output_chars, len(raw))
        self.assertEqual(
            out.diagnostics.raw_sha256,
            hashlib.sha256(raw.encode("utf-8")).hexdigest(),
        )

    def test_parse_invalid_json_fails_to_ambiguous(self) -> None:
        out = rc.parse_judge_response("not json")

        self.assertEqual(out.decision, rc.Decision.AMBIGUOUS)
        self.assertEqual(out.confidence, 0.0)
        self.assertEqual(out.reason_code, "parse_error")

    def test_parse_error_default_diagnostics_include_length_and_hash(self) -> None:
        raw = "not json"

        out = rc.parse_judge_response(raw)

        self.assertEqual(out.reason_code, "parse_error")
        self.assertEqual(out.diagnostics.output_chars, len(raw))
        self.assertEqual(
            out.diagnostics.raw_sha256,
            hashlib.sha256(raw.encode("utf-8")).hexdigest(),
        )

    def test_parse_error_carries_content_light_diagnostics(self) -> None:
        raw = "<think>lots</think>"
        diagnostics = rc.JudgeDiagnostics(
            output_chars=len(raw),
            finish_reason="length",
            backend="primary_openai",
            thinking_suppressed=False,
            raw_sha256=hashlib.sha256(raw.encode("utf-8")).hexdigest(),
        )

        out = rc.parse_judge_response(raw, diagnostics=diagnostics)

        self.assertEqual(out.reason_code, "parse_error")
        self.assertEqual(out.diagnostics.output_chars, len(raw))
        self.assertEqual(out.diagnostics.finish_reason, "length")
        self.assertEqual(out.diagnostics.backend, "primary_openai")
        self.assertFalse(out.diagnostics.thinking_suppressed)
        self.assertEqual(
            out.diagnostics.raw_sha256,
            hashlib.sha256(raw.encode("utf-8")).hexdigest(),
        )

    def test_parse_wrapped_json_decision_from_thinking_model_output(self) -> None:
        out = rc.parse_judge_response(
            "I will classify the routing case first.\n"
            '{"decision":"personal_or_relational","confidence":0.94,'
            '"reason_code":"owner_sharing_personal_state"}\n'
            "That is the final routing decision."
        )

        self.assertEqual(out.decision, rc.Decision.PERSONAL_OR_RELATIONAL)
        self.assertEqual(out.confidence, 0.94)
        self.assertEqual(out.reason_code, "owner_sharing_personal_state")

    def test_parse_non_finite_confidence_clamps_to_zero(self) -> None:
        for value in ("NaN", "Infinity", "-Infinity"):
            out = rc.parse_judge_response(
                '{"decision":"personal_or_relational","confidence":"'
                + value
                + '","reason_code":"x"}'
            )

            self.assertEqual(out.confidence, 0.0)
            self.assertFalse(out.vetoes_web_search)

    def test_prompt_is_bounded_and_contains_no_witness_phrases(self) -> None:
        ctx = rc.JudgeContext(
            current_turn="x" * 5000,
            dialogue_tail=(
                "a" * 1000,
                "b" * 1000,
                "c" * 1000,
                "d" * 1000,
                "e" * 1000,
            ),
            trigger=rc.SearchTrigger(source="WEB_SEARCH", reason="current_world_request"),
            prior_receipt=rc.PriorToolReceipt(
                kind="web_search",
                query="q" * 1000,
                sources=("https://example.test/a",),
                diagnostic_id="diag",
            ),
        )

        prompt = rc.render_judge_prompt(ctx)

        self.assertLessEqual(len(prompt), 6000)
        self.assertIn("CURRENT_OWNER_TURN", prompt)
        self.assertIn("RECENT_DIALOGUE", prompt)
        self.assertIn("PROPOSED_TRIGGER", prompt)
        self.assertIn("PRIOR_TOOL_CONTEXT", prompt)
        lower = prompt.lower()
        for forbidden in ("insecure", "legs", "nvidia", "openai", "i feel", "today"):
            self.assertNotIn(forbidden, lower)

    def test_structural_no_keyword_or_regex_intent_matching(self) -> None:
        src = inspect.getsource(rc)

        self.assertNotIn("import re", src)
        self.assertNotIn("re.", src)
        self.assertNotIn("_RE", src)
        for forbidden in ("insecure", "legs", "nvidia", "openai", "i feel", "today"):
            self.assertNotIn(forbidden, src.lower())
        for diagnostic_only in ("output_chars", "finish_reason", "raw_sha256"):
            self.assertIn(diagnostic_only, src)
        for forbidden in ("gym", "stock", "price", "vulnerable"):
            self.assertNotIn(forbidden, src.lower())

    def test_veto_removes_web_search_keeps_substrate(self) -> None:
        spec = _spec(
            substrate_sources=[SubstrateSource.TELEGRAM_SEMANTIC],
            external_sources=[ExternalSource.WEB_SEARCH],
            hint=CompositionHint.PARALLEL,
            framing=ProvenanceFraming.HYBRID_FRESH_VALIDATES_SUBSTRATE_CONTEXTUALIZES,
        )
        decision = rc.JudgeDecision(
            decision=rc.Decision.PERSONAL_OR_RELATIONAL,
            confidence=0.95,
            reason_code="owner_sharing_personal_state",
        )

        out = rc.apply_web_search_veto(spec, decision)

        self.assertEqual(out.external_sources, [])
        self.assertEqual(out.substrate_sources, [SubstrateSource.TELEGRAM_SEMANTIC])
        self.assertEqual(out.composition_hint, CompositionHint.SUBSTRATE_ONLY)
        self.assertEqual(
            out.provenance_framing,
            ProvenanceFraming.SUBSTRATE_ONLY_NO_FRESH_VALIDATION,
        )

    def test_veto_removes_only_web_search_when_other_external_sources_remain(self) -> None:
        spec = _spec(
            substrate_sources=[SubstrateSource.REDDIT_SOURCE],
            external_sources=[ExternalSource.WEB_SEARCH, ExternalSource.LIVE_REDDIT],
            hint=CompositionHint.PARALLEL,
            framing=ProvenanceFraming.HYBRID_FRESH_VALIDATES_SUBSTRATE_CONTEXTUALIZES,
        )

        out = rc.apply_web_search_veto(
            spec,
            rc.JudgeDecision(
                decision=rc.Decision.THREAD_FOLLOWUP_ANSWERABLE,
                confidence=0.93,
                reason_code="prior_tool_receipt_sufficient",
            ),
        )

        self.assertEqual(out.external_sources, [ExternalSource.LIVE_REDDIT])
        self.assertEqual(out.substrate_sources, [SubstrateSource.REDDIT_SOURCE])
        self.assertEqual(out.composition_hint, spec.composition_hint)
        self.assertEqual(out.provenance_framing, spec.provenance_framing)

    def test_non_veto_decisions_leave_spec_identity(self) -> None:
        spec = _spec(external_sources=[ExternalSource.WEB_SEARCH])
        for decision in (
            rc.Decision.EXTERNAL_INFO_REQUESTED,
            rc.Decision.AMBIGUOUS,
        ):
            out = rc.apply_web_search_veto(
                spec,
                rc.JudgeDecision(decision=decision, confidence=0.5, reason_code="x"),
            )
            self.assertIs(out, spec)

    def test_low_confidence_veto_labels_leave_spec_identity(self) -> None:
        spec = _spec(external_sources=[ExternalSource.WEB_SEARCH])
        for decision in (
            rc.Decision.PERSONAL_OR_RELATIONAL,
            rc.Decision.THREAD_FOLLOWUP_ANSWERABLE,
        ):
            out = rc.apply_web_search_veto(
                spec,
                rc.JudgeDecision(decision=decision, confidence=0.89, reason_code="x"),
            )
            self.assertIs(out, spec)

    def test_content_light_receipt_excludes_chat_id_and_turn_text(self) -> None:
        receipt = rc.shadow_receipt(
            surface="telegram_surface",
            chat_id="123456",
            decision=rc.JudgeDecision(
                decision=rc.Decision.PERSONAL_OR_RELATIONAL,
                confidence=0.94,
                reason_code="owner_sharing_personal_state",
            ),
            trigger=rc.SearchTrigger(source="WEB_SEARCH", reason="current_world_request"),
            enabled=False,
            veto_applied=False,
        )

        self.assertIn("routing_comprehension", receipt)
        self.assertIn("surface=telegram_surface", receipt)
        self.assertIn("decision=personal_or_relational", receipt)
        self.assertIn("confidence=0.940", receipt)
        self.assertIn("reason=owner_sharing_personal_state", receipt)
        self.assertIn("trigger=current_world_request", receipt)
        self.assertIn("enabled=False", receipt)
        self.assertIn("veto_applied=False", receipt)
        self.assertNotIn("123456", receipt)
        self.assertNotIn("insecure", receipt.lower())

    def test_shadow_receipt_includes_diagnostics_without_raw_output(self) -> None:
        raw = (
            '{"decision":"personal_or_relational","confidence":0.95,'
            '"reason_code":"owner_sharing"}'
        )
        decision = rc.JudgeDecision(
            decision=rc.Decision.PERSONAL_OR_RELATIONAL,
            confidence=0.95,
            reason_code="owner_sharing",
            diagnostics=rc.JudgeDiagnostics(
                output_chars=len(raw),
                finish_reason="stop",
                backend="primary_openai",
                thinking_suppressed=True,
                raw_sha256=hashlib.sha256(raw.encode("utf-8")).hexdigest(),
            ),
        )

        receipt = rc.shadow_receipt(
            surface="telegram_surface",
            chat_id="secret-chat",
            decision=decision,
            trigger=rc.SearchTrigger(source="WEB_SEARCH", reason="current_world_request"),
            enabled=False,
            veto_applied=False,
        )

        self.assertIn("output_chars=", receipt)
        self.assertIn("finish_reason=stop", receipt)
        self.assertIn("backend=primary_openai", receipt)
        self.assertIn("thinking_suppressed=True", receipt)
        self.assertIn("raw_sha256=", receipt)
        self.assertNotIn(raw, receipt)
        self.assertNotIn("secret-chat", receipt)
        self.assertNotIn('personal_or_relational","confidence', receipt)

    def test_receipt_context_text_is_honest_with_no_prior_receipt(self) -> None:
        text = rc.receipt_context_text(None)

        self.assertIn("no retained web receipt", text.lower())
        self.assertIn("do not invent", text.lower())
        self.assertNotIn("https://", text)

    def test_receipt_context_text_renders_prior_web_receipt(self) -> None:
        text = rc.receipt_context_text(
            rc.PriorToolReceipt(
                kind="web_search",
                query="recent routing papers",
                sources=("https://example.test/source",),
                diagnostic_id="diag-1",
            )
        )

        self.assertIn("web_search", text)
        self.assertIn("recent routing papers", text)
        self.assertIn("https://example.test/source", text)
        self.assertIn("diag-1", text)

    def test_receipt_context_text_bounds_retained_fields(self) -> None:
        long_kind = "k" * 500
        long_query = "q" * 1200
        long_source_tail = "s" * 1200
        long_source = "https://example.test/" + long_source_tail
        long_diagnostic = "d" * 500

        text = rc.receipt_context_text(
            rc.PriorToolReceipt(
                kind=long_kind,
                query=long_query,
                sources=tuple(long_source for _ in range(8)),
                diagnostic_id=long_diagnostic,
            )
        )

        self.assertLessEqual(len(text), 900)
        self.assertNotIn(long_kind, text)
        self.assertNotIn(long_query, text)
        self.assertNotIn(long_source, text)
        self.assertNotIn(long_diagnostic, text)

    def test_env_helpers(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertFalse(rc.shadow_enabled())
            self.assertFalse(rc.enabled())
            self.assertFalse(rc.any_enabled())
        with mock.patch.dict(os.environ, {"MAEZ_ROUTING_COMPREHENSION_SHADOW": "on"}):
            self.assertTrue(rc.shadow_enabled())
            self.assertFalse(rc.enabled())
            self.assertTrue(rc.any_enabled())
        with mock.patch.dict(os.environ, {"MAEZ_ROUTING_COMPREHENSION_ENABLED": "1"}):
            self.assertFalse(rc.shadow_enabled())
            self.assertTrue(rc.enabled())
            self.assertTrue(rc.any_enabled())

    def test_default_judge_returns_llm_judge(self) -> None:
        self.assertIsInstance(rc.default_judge(), rc.LlmEligibilityJudge)

    def test_llm_judge_uses_direct_chat_with_explicit_thinking_suppression(self) -> None:
        response = SimpleNamespace(
            message=SimpleNamespace(
                content=(
                    '{"decision":"external_info_requested","confidence":0.82,'
                    '"reason_code":"owner_asks_lookup"}'
                )
            )
        )

        with (
            mock.patch("core.llm_client.chat", side_effect=AssertionError("gateway path")),
            mock.patch("core.llm_client.chat_direct", return_value=response, create=True) as fake_chat,
        ):
            decision = rc.LlmEligibilityJudge().decide(
                rc.JudgeContext(current_turn="please look this up")
            )

        self.assertEqual(decision.decision, rc.Decision.EXTERNAL_INFO_REQUESTED)
        self.assertEqual(decision.confidence, 0.82)
        self.assertEqual(decision.reason_code, "owner_asks_lookup")
        fake_chat.assert_called_once()
        self.assertEqual(fake_chat.call_args.kwargs["purpose"], "routing_comprehension")
        self.assertFalse(fake_chat.call_args.kwargs["think"])
        self.assertEqual(
            fake_chat.call_args.kwargs["options"]["chat_template_kwargs"],
            {"enable_thinking": False},
        )
        self.assertGreaterEqual(fake_chat.call_args.kwargs["options"]["num_predict"], 240)

    def test_llm_judge_threads_response_metadata_into_decision(self) -> None:
        raw = (
            '{"decision":"external_info_requested","confidence":0.95,'
            '"reason_code":"owner_asks_lookup"}'
        )
        response = SimpleNamespace(
            message=SimpleNamespace(content=raw),
            finish_reason="stop",
            backend="primary_openai",
            thinking_suppressed=True,
        )

        with (
            mock.patch("core.llm_client.chat", side_effect=AssertionError("gateway path")),
            mock.patch("core.llm_client.chat_direct", return_value=response, create=True),
        ):
            decision = rc.LlmEligibilityJudge().decide(
                rc.JudgeContext(current_turn="please look this up")
            )

        self.assertEqual(decision.decision, rc.Decision.EXTERNAL_INFO_REQUESTED)
        self.assertEqual(decision.diagnostics.finish_reason, "stop")
        self.assertEqual(decision.diagnostics.backend, "primary_openai")
        self.assertTrue(decision.diagnostics.thinking_suppressed)
        self.assertEqual(decision.diagnostics.output_chars, len(raw))
        self.assertEqual(
            decision.diagnostics.raw_sha256,
            hashlib.sha256(raw.encode("utf-8")).hexdigest(),
        )

    def test_llm_judge_import_failure_fails_to_ambiguous(self) -> None:
        real_import = __import__

        def fail_model_config(name, *args, **kwargs):
            if name == "core.model_config":
                raise ImportError("model config unavailable")
            return real_import(name, *args, **kwargs)

        with mock.patch("builtins.__import__", side_effect=fail_model_config):
            decision = rc.LlmEligibilityJudge().decide(
                rc.JudgeContext(current_turn="please check")
            )

        self.assertEqual(decision.decision, rc.Decision.AMBIGUOUS)
        self.assertEqual(decision.confidence, 0.0)
        self.assertEqual(decision.reason_code, "judge_unavailable")


def _spec(
    *,
    substrate_sources: list[SubstrateSource] | None = None,
    external_sources: list[ExternalSource] | None = None,
    hint: CompositionHint = CompositionHint.FRESH_ONLY,
    framing: ProvenanceFraming = ProvenanceFraming.FRESH_ONLY,
) -> CompositionSpec:
    substrate = list(substrate_sources or [])
    external = list(external_sources or [])
    return CompositionSpec(
        substrate_sources=substrate,
        external_sources=external,
        composition_hint=hint,
        provenance_framing=framing,
        inventory_witness=InventoryWitness.MIXED,
        source_availability={
            source: SourceAvailability.EXECUTABLE_PRESENT
            for source in [*substrate, *external]
        },
        availability_limitations=[],
        freshness_window=None,
        trust_scope_union=None,
    )
