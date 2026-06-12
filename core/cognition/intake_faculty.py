"""Intake Understanding Faculty v0 — schema and instrument interfaces.

The faculty is an instrument: it proposes a read of owner-turn meaning. It
never grants permission and never executes an action.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import time
from typing import Any
import urllib.request

from core.model_config import JUDGE_BASE_URL

# 2026-06-11 hearing fix: the dedicated judge (llama-b9124) ignores
# chat_template_kwargs, so Qwen3.5 burns the whole budget in
# reasoning_content and returns content="". Witnessed live: 160 tok →
# empty @10.7s; 512 tok → still thinking @30.7s. The working recipe is a
# raw /completion call with the think block PRE-CLOSED (probe: valid JSON
# @8.05s). 224 tokens gives the ~90-token read headroom against rationale
# truncation (the 160-token probe cut mid-string).
_MAX_TOKENS = 224

TURN_KINDS = frozenset({
    "commitment_response",
    "boundary",
    "continuity_reference",
    "recall_request",
    "search_request",
    "topic_shift",
    "ordinary",
    "ambiguous",
})
STANCES = frozenset({"yes", "no", "ambiguous", "n_a"})
BOUNDARY_SIGNALS = frozenset({"none", "soft", "hard"})
NEEDS = frozenset({"search", "recall", "none"})
REFERENT_KINDS = frozenset({"pending_offer", "earlier_topic", "none"})
STATUSES = frozenset({"ok", "judge_busy", "timeout", "parse_error", "backend_error"})


def _bucket(confidence: Any) -> str:
    try:
        value = float(confidence)
    except (TypeError, ValueError):
        return "unknown"
    if value >= 0.75:
        return "high"
    if value >= 0.45:
        return "medium"
    if value >= 0.0:
        return "low"
    return "unknown"


@dataclass(frozen=True)
class IntakeRead:
    turn_kind: str
    stance: str
    boundary_signal: str
    needs: str
    referent_kind: str
    confidence: float | None
    rationale: str = ""
    status: str = "ok"

    @property
    def confidence_bucket(self) -> str:
        return _bucket(self.confidence)

    @classmethod
    def ambiguous(cls, *, status: str = "parse_error") -> "IntakeRead":
        safe_status = status if status in STATUSES else "parse_error"
        return cls(
            turn_kind="ambiguous",
            stance="ambiguous",
            boundary_signal="none",
            needs="none",
            referent_kind="none",
            confidence=None,
            rationale="",
            status=safe_status,
        )

    @classmethod
    def from_model(cls, data: Any) -> "IntakeRead":
        if not isinstance(data, dict):
            return cls.ambiguous(status="parse_error")

        turn_kind = data.get("turn_kind")
        stance = data.get("stance")
        boundary_signal = data.get("boundary_signal")
        needs = data.get("needs")
        referent_kind = data.get("referent_kind")
        if (
            turn_kind not in TURN_KINDS
            or stance not in STANCES
            or boundary_signal not in BOUNDARY_SIGNALS
            or needs not in NEEDS
            or referent_kind not in REFERENT_KINDS
        ):
            return cls.ambiguous(status="parse_error")
        try:
            confidence = float(data.get("confidence"))
        except (TypeError, ValueError):
            confidence = None
        if confidence is not None:
            confidence = max(0.0, min(1.0, confidence))
        rationale = str(data.get("rationale") or "")[:240]
        return cls(
            turn_kind=turn_kind,
            stance=stance,
            boundary_signal=boundary_signal,
            needs=needs,
            referent_kind=referent_kind,
            confidence=confidence,
            rationale=rationale,
            status="ok",
        )

    def to_telemetry(self, *, debug: bool = False) -> dict[str, Any]:
        rec = {
            "turn_kind": self.turn_kind,
            "stance": self.stance,
            "boundary_signal": self.boundary_signal,
            "needs": self.needs,
            "referent_kind": self.referent_kind,
            "confidence_bucket": self.confidence_bucket,
            "status": self.status,
        }
        if debug and self.rationale:
            rec["rationale"] = self.rationale
        return rec


class FakeIntakeBackend:
    """Tests only. Scripted reads; never touches the real judge service."""

    def __init__(self, scripted=None, *, default: IntakeRead | None = None, busy=False, raises=None, sleep_s=0.0):
        self._scripted = dict(scripted or {})
        self._default = default or IntakeRead(
            turn_kind="ordinary",
            stance="n_a",
            boundary_signal="none",
            needs="none",
            referent_kind="none",
            confidence=0.8,
            rationale="ordinary turn",
        )
        self._busy = busy
        self._raises = raises
        self._sleep_s = sleep_s
        self.calls: list[tuple[str, dict]] = []

    def read(self, message: str, context: dict, timeout_s: float) -> tuple[IntakeRead, float]:
        started = time.monotonic()
        self.calls.append((message, context))
        if self._raises is not None:
            raise self._raises
        if self._sleep_s:
            time.sleep(self._sleep_s)
        if self._busy:
            return IntakeRead.ambiguous(status="judge_busy"), time.monotonic() - started
        return self._scripted.get(message, self._default), time.monotonic() - started


def _json_candidates(text: str):
    """Yield progressively repaired JSON candidates from model output.

    Survives prose wrapping (text around the object) and trailing
    truncation (n_predict cutting mid-string in the rationale — witnessed
    on the 160-token probe). Repairs only ever CLOSE the object; they
    cannot invent fields, and a failed repair falls through to the honest
    parse_error read.
    """
    s = text or ""
    start = s.find("{")
    if start < 0:
        return
    end = s.rfind("}")
    if end > start:
        yield s[start : end + 1]
    tail = s[start:].rstrip()
    for suffix in ('"}', "}", '"}}'):
        yield tail + suffix


def parse_json_read(text: str) -> IntakeRead:
    for candidate in _json_candidates(text):
        try:
            data = json.loads(candidate)
        except Exception:
            continue
        read = IntakeRead.from_model(data)
        if read.status == "ok":
            return read
    return IntakeRead.ambiguous(status="parse_error")


def _context_for_prompt(context: dict) -> str:
    safe = {
        "turns": context.get("turns") or [],
        "pending_offer": context.get("pending_offer"),
        "surface": context.get("surface"),
    }
    return json.dumps(safe, ensure_ascii=False, sort_keys=True)[:6000]


def build_prompt(message: str, context: dict) -> str:
    return (
        "You are Maez's intake-understanding faculty. You do not answer the owner. "
        "You never execute actions. You emit a proposal/read of what the owner turn means. "
        "The deterministic substrate decides permissions later. Output only JSON with keys: "
        "turn_kind, stance, boundary_signal, needs, referent_kind, confidence, rationale. "
        "Allowed turn_kind values: commitment_response, boundary, continuity_reference, "
        "recall_request, search_request, topic_shift, ordinary, ambiguous. Do not create "
        "a refusal category: a no to an offer is commitment_response with stance=no; Maez's "
        "capacity to refuse is a separate sacred axis. Allowed stance: yes, no, ambiguous, n_a. "
        "Allowed boundary_signal: none, soft, hard. Allowed needs: search, recall, none. "
        "Allowed referent_kind: pending_offer, earlier_topic, none. "
        "Keep rationale under 15 words.\n\n"
        f"OWNER_MESSAGE:\n{message or ''}\n\n"
        f"CONTEXT_JSON:\n{_context_for_prompt(context or {})}\n"
    )


_SYSTEM_LINE = "You are a strict JSON classifier. Output only valid JSON."


def render_chatml(system: str, user: str) -> str:
    """ChatML with the assistant think block PRE-CLOSED.

    Qwen-template quirk adapter: the dedicated judge server build ignores
    chat_template_kwargs/enable_thinking, so we render the template by hand
    and hand the model an already-closed <think> block — it cannot spend the
    budget thinking. Model-specific by design; quirks live in this adapter,
    the IntakeRead contract stays model-agnostic.
    """
    return (
        f"<|im_start|>system\n{system}<|im_end|>\n"
        f"<|im_start|>user\n{user}<|im_end|>\n"
        f"<|im_start|>assistant\n<think>\n\n</think>\n\n"
    )


def _call_judge(prompt: str, *, timeout_s: float = 8.0) -> str:
    payload = {
        "prompt": render_chatml(_SYSTEM_LINE, prompt),
        "n_predict": _MAX_TOKENS,
        "temperature": 0.0,
        "stop": ["<|im_end|>"],
    }
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{JUDGE_BASE_URL.rstrip('/')}/completion",
        data=body,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        data = json.loads(resp.read())
    return data.get("content") or ""


class HttpIntakeBackend:
    """Local 4B judge-backed intake faculty.

    Transport and parse failures become an ambiguous read. The shadow worker
    decides when to call this; the live path must never call it directly.
    """

    def read(self, message: str, context: dict, timeout_s: float) -> tuple[IntakeRead, float]:
        started = time.monotonic()
        try:
            raw = _call_judge(build_prompt(message, context or {}), timeout_s=timeout_s)
            read = parse_json_read(raw)
        except Exception:
            read = IntakeRead.ambiguous(status="backend_error")
        return read, time.monotonic() - started
