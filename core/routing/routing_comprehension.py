from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from ..dispatcher.spec import (
    CompositionHint,
    CompositionSpec,
    ExternalSource,
    ProvenanceFraming,
)

log = logging.getLogger(__name__)

truthy_flags = frozenset({"1", "true", "yes", "on"})
turn_char_cap = 900
dialogue_turn_cap = 4
dialogue_char_cap = 600
query_char_cap = 300
reason_char_cap = 80
prompt_char_cap = 6000
source_list_cap = 5
receipt_context_char_cap = 900
receipt_kind_char_cap = 60
receipt_source_char_cap = 50
receipt_diagnostic_char_cap = 80


Decision = StrEnum(
    "Decision",
    {
        "EXTERNAL_INFO_" + "REQUESTED": "external_info_requested",
        "PERSONAL_OR_" + "RELATIONAL": "personal_or_relational",
        "THREAD_FOLLOWUP_ANSWERABLE": "thread_followup_answerable",
        "AMBIGUOUS": "ambiguous",
    },
)

external_decision = Decision("external_info_requested")
personal_decision = Decision("personal_or_relational")
followup_decision = Decision("thread_followup_answerable")
ambiguous_decision = Decision("ambiguous")
veto_decisions = frozenset({personal_decision, followup_decision})


@dataclass(frozen=True)
class SearchTrigger:
    source: str
    reason: str


@dataclass(frozen=True)
class PriorToolReceipt:
    kind: str
    query: str | None = None
    sources: tuple[str, ...] = ()
    diagnostic_id: str | None = None


@dataclass(frozen=True)
class JudgeContext:
    current_turn: str
    dialogue_tail: tuple[str, ...] = ()
    trigger: SearchTrigger | None = None
    prior_receipt: PriorToolReceipt | None = None


@dataclass(frozen=True)
class JudgeDecision:
    decision: Decision
    confidence: float
    reason_code: str

    @property
    def vetoes_web_search(self) -> bool:
        return self.decision in veto_decisions


class EligibilityJudge(Protocol):
    def decide(self, context: JudgeContext) -> JudgeDecision: ...


def shadow_enabled() -> bool:
    return _flag_on("MAEZ_ROUTING_COMPREHENSION_SHADOW")


def enabled() -> bool:
    return _flag_on("MAEZ_ROUTING_COMPREHENSION_ENABLED")


def any_enabled() -> bool:
    return shadow_enabled() or enabled()


def parse_judge_response(raw: str) -> JudgeDecision:
    try:
        text = _strip_json_fence(str(raw or "").strip())
        payload = json.loads(text)
        decision = Decision(str(payload.get("decision") or ambiguous_decision.value))
        confidence = _clamp_confidence(float(payload.get("confidence", 0.0)))
        reason_code = _compact_reason(payload.get("reason_code") or "model_decision")
        return JudgeDecision(
            decision=decision,
            confidence=confidence,
            reason_code=reason_code,
        )
    except Exception:
        return JudgeDecision(
            decision=ambiguous_decision,
            confidence=0.0,
            reason_code="parse_error",
        )


def render_judge_prompt(context: JudgeContext) -> str:
    trigger = context.trigger or SearchTrigger(source="WEB_SEARCH", reason="unknown")
    tail = tuple(context.dialogue_tail or ())[-dialogue_turn_cap:]
    tail_lines = "\n".join(
        f"- {_clip(str(item), dialogue_char_cap)}"
        for item in tail
        if str(item).strip()
    )
    prompt = (
        "You are a routing comprehension judge. Decide if the owner truly asks "
        "Maez to seek new outside information.\n\n"
        "Return ONLY JSON with keys: decision, confidence, reason_code.\n"
        "Allowed values:\n"
        "- external_info_requested: owner asks for new outside information.\n"
        "- personal_or_relational: owner shares or relates without asking lookup.\n"
        "- thread_followup_answerable: owner asks about nearby thread or tool use.\n"
        "- ambiguous: uncertain, allow lookup.\n\n"
        "High precision: when uncertain choose ambiguous. Judge the whole turn "
        "plus nearby thread, not isolated words.\n\n"
        f"PROPOSED_TOOL: {trigger.source}\n"
        f"PROPOSED_TRIGGER: {_clip(trigger.reason, 180)}\n\n"
        f"PRIOR_TOOL_CONTEXT: {_tool_context_line(context.prior_receipt)}\n\n"
        f"RECENT_DIALOGUE:\n{tail_lines or 'none'}\n\n"
        f"CURRENT_OWNER_TURN:\n{_clip(context.current_turn, turn_char_cap)}"
    )
    return prompt[:prompt_char_cap]


class LlmEligibilityJudge:
    def decide(self, context: JudgeContext) -> JudgeDecision:
        from ..llm_client import chat
        from ..model_config import PRIMARY_MODEL

        try:
            response = chat(
                model=PRIMARY_MODEL,
                messages=[
                    {"role": "system", "content": "Return strict JSON only."},
                    {"role": "user", "content": render_judge_prompt(context)},
                ],
                think=False,
                options={"temperature": 0.0, "num_predict": 120},
                purpose="routing_comprehension",
            )
            message = getattr(response, "message", None)
            return parse_judge_response(getattr(message, "content", "") or "")
        except Exception as exc:
            log.debug("routing comprehension judge unavailable: %s", exc)
            return JudgeDecision(
                decision=ambiguous_decision,
                confidence=0.0,
                reason_code="judge_unavailable",
            )


def default_judge() -> EligibilityJudge:
    return LlmEligibilityJudge()


def apply_web_search_veto(
    spec: CompositionSpec,
    decision: JudgeDecision,
) -> CompositionSpec:
    if not decision.vetoes_web_search:
        return spec
    if ExternalSource.WEB_SEARCH not in list(spec.external_sources or []):
        return spec

    substrate_sources = list(spec.substrate_sources or [])
    external_sources = [
        source
        for source in list(spec.external_sources or [])
        if source != ExternalSource.WEB_SEARCH
    ]
    if external_sources:
        return _copy_spec(
            spec,
            substrate_sources=substrate_sources,
            external_sources=external_sources,
            hint=spec.composition_hint,
            framing=spec.provenance_framing,
        )
    return _copy_spec(
        spec,
        substrate_sources=substrate_sources,
        external_sources=[],
        hint=CompositionHint.SUBSTRATE_ONLY,
        framing=ProvenanceFraming.SUBSTRATE_ONLY_NO_FRESH_VALIDATION,
    )


def shadow_receipt(
    *,
    surface: str,
    chat_id: str | None,
    decision: JudgeDecision,
    trigger: SearchTrigger,
    enabled: bool,
    veto_applied: bool,
) -> str:
    del chat_id
    return (
        "routing_comprehension "
        f"surface={surface} "
        f"decision={decision.decision.value} "
        f"confidence={decision.confidence:.3f} "
        f"reason={decision.reason_code} "
        f"trigger={_compact_reason(trigger.reason)} "
        f"enabled={bool(enabled)} "
        f"veto_applied={bool(veto_applied)}"
    )


def receipt_context_text(receipt: PriorToolReceipt | None) -> str:
    if receipt is None:
        return (
            "=== PRIOR TOOL CONTEXT ===\n"
            "No retained web receipt is available for this chat. "
            "Say that plainly; do not invent a search."
        )
    kind = _clip(receipt.kind, receipt_kind_char_cap) or "unknown"
    query = _clip(receipt.query or "", query_char_cap) or "unknown query"
    diagnostic_id = (
        _clip(receipt.diagnostic_id or "", receipt_diagnostic_char_cap) or "unknown"
    )
    sources = "\n".join(
        f"- {_clip(str(url), receipt_source_char_cap)}"
        for url in receipt.sources[:source_list_cap]
        if str(url).strip()
    )
    if not sources:
        sources = "- none retained"
    text = (
        "=== PRIOR TOOL CONTEXT ===\n"
        f"Prior tool: {kind}\n"
        f"Prior query: {query}\n"
        f"Diagnostic id: {diagnostic_id}\n"
        f"Sources retained:\n{sources}\n"
        "Use this retained proof if the owner asks what was checked. "
        "Do not search again."
    )
    return _clip(text, receipt_context_char_cap)


def _tool_context_line(receipt: PriorToolReceipt | None) -> str:
    if receipt is None:
        return "none"
    return (
        f"kind={_clip(receipt.kind, 60)}; "
        f"query={_clip(receipt.query or '', query_char_cap)}; "
        f"sources={len(receipt.sources)}; "
        f"diagnostic_id={_clip(receipt.diagnostic_id or '', 80)}"
    )


def _copy_spec(
    spec: CompositionSpec,
    *,
    substrate_sources: list,
    external_sources: list,
    hint: CompositionHint,
    framing: ProvenanceFraming,
) -> CompositionSpec:
    return CompositionSpec(
        substrate_sources=substrate_sources,
        external_sources=external_sources,
        composition_hint=hint,
        provenance_framing=framing,
        inventory_witness=spec.inventory_witness,
        source_availability=dict(spec.source_availability or {}),
        availability_limitations=list(spec.availability_limitations or []),
        freshness_window=spec.freshness_window,
        trust_scope_union=spec.trust_scope_union,
    )


def _flag_on(name: str) -> bool:
    return (os.environ.get(name) or "").strip().lower() in truthy_flags


def _strip_json_fence(text: str) -> str:
    if not text.startswith("```"):
        return text
    lines = text.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].startswith("```"):
        lines = lines[:-1]
    return "\n".join(lines).strip()


def _clamp_confidence(value: float) -> float:
    return max(0.0, min(1.0, value))


def _clip(value: str, cap: int) -> str:
    text = str(value or "").strip()
    if cap <= 0:
        return ""
    if len(text) <= cap:
        return text
    if cap <= 3:
        return "." * cap
    return text[: cap - 3].rstrip() + "..."


def _compact_reason(value: str) -> str:
    allowed = {"_", "-", "."}
    compact = "".join(
        char if char.isalnum() or char in allowed else "_"
        for char in str(value or "")
    )
    return (compact.strip("_") or "unspecified")[:reason_char_cap]
