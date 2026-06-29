"""Lean idle heartbeat v0.

Private quiet-floor thoughts for Maez's existing daemon loop. This module
builds a small factual prompt and validates one private notebook note. It does
not schedule cycles, search, act, broadcast, or touch soul/user-facing memory.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import hashlib
import json
import re

from core.infra.private_thoughts import (
    AllowedFlow,
    ConsentTier,
    ProducerId,
    RetentionRule,
    SignalKind,
)


HEARTBEAT_VERSION = "lean_idle_heartbeat.v0"
HEARTBEAT_OK = "HEARTBEAT_OK"
MAX_PRIVATE_NOTE_CHARS = 600  # TEMPORARY scaffold, not learned salience.
FORBIDDEN_RENDER_WORDS = ("lonely", "missed", "long", "should", "worry", "feel")

_FINAL_TAG_RE = re.compile(r"<final>(.*?)</final>", re.DOTALL | re.IGNORECASE)
_OWNER_ADDRESS_RE = re.compile(
    r"(?:\brohit\s*,|\b(?:tell|ask|message|send)\s+rohit\b)",
    re.IGNORECASE,
)
_ACTION_RE = re.compile(
    r"\b(search\s+the\s+web|run\s+a\s+command|execute|open\s+the\s+browser|send\s+a\s+message)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class LeanIdleFacts:
    cycle: int
    doorman_reason: str
    self_card_text: str
    private_signal_summary: Mapping[str, object] | None = None
    time_facts: Mapping[str, object] | None = None
    body_state: Mapping[str, object] | None = None
    body_state_window: tuple[Mapping[str, object], ...] = ()
    open_loops: Mapping[str, object] | None = None
    recent_private_thoughts: tuple[str, ...] = ()


@dataclass(frozen=True)
class LeanIdlePrompt:
    text: str
    fact_keys: tuple[str, ...]
    sha256: str
    chars: int
    version: str = HEARTBEAT_VERSION


@dataclass(frozen=True)
class PrivateNote:
    text: str
    sha256: str
    chars: int


@dataclass(frozen=True)
class ModelDiagnostics:
    output_chars: int = 0
    finish_reason: str = ""
    backend: str = ""
    thinking_suppressed: bool = False
    raw_sha256: str = ""


@dataclass(frozen=True)
class LeanIdleResult:
    intercepted: bool
    stored: bool
    thought_id: int | None
    return_text: str | None
    skip_reason: str
    receipt: dict[str, object]


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _sha256_full(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _compact(text: object) -> str:
    return " ".join(str(text or "").split())


def _content_light_json(value: Mapping[str, object] | None) -> str:
    if not value:
        return "{}"
    safe: dict[str, object] = {}
    for key, item in value.items():
        if isinstance(item, (int, float, bool)) or item is None:
            safe[str(key)] = item
        elif isinstance(item, str):
            safe[str(key)] = _compact(item)[:80]
        else:
            safe[str(key)] = str(type(item).__name__)
    return json.dumps(safe, sort_keys=True)


def _render_facts_block(title: str, items: list[tuple[str, object]]) -> str:
    lines = [f"- {key}: {value}" for key, value in items if value is not None]
    if not lines:
        return ""
    return f"\n{title}\n" + "\n".join(lines) + "\n"


def _time_block(time_facts: Mapping[str, object] | None) -> str:
    if not time_facts:
        return ""
    order = (
        "owner_contact_gap_s",
        "recent_usual_gap_s",
        "all_time_usual_gap_s",
        "gap_percentile_all_time",
    )
    return _render_facts_block("TIME", [(key, time_facts.get(key)) for key in order])


def _body_block(body_state: Mapping[str, object] | None) -> str:
    if not body_state:
        return ""
    order = ("daemon_overall", "watchdog", "backup_freshness")
    return _render_facts_block("BODY", [(key, body_state.get(key)) for key in order])


def _body_state_window_block(deltas: tuple[Mapping[str, object], ...]) -> str:
    if not deltas:
        return ""
    lines: list[str] = []
    for delta in deltas:
        phrase = _compact(delta.get("phrase"))
        if not phrase:
            continue
        provenance = _compact(delta.get("provenance"))
        sensitivity = _compact(delta.get("sensitivity"))
        parts = [phrase]
        if provenance:
            parts.append(f"provenance: {provenance}")
        if sensitivity:
            parts.append(f"sensitivity: {sensitivity}")
        lines.append("- " + "; ".join(parts))
    if not lines:
        return ""
    return "\nBODY-STATE WINDOW (changes since last beat)\n" + "\n".join(lines) + "\n"


def _loops_block(open_loops: Mapping[str, object] | None) -> str:
    if not open_loops:
        return ""
    classes = open_loops.get("open_loop_classes") or []
    classes_str = ", ".join(str(item) for item in classes) if classes else None
    return _render_facts_block(
        "OPEN LOOPS",
        [
            ("open_loop_count", open_loops.get("open_loop_count")),
            ("open_loop_classes", classes_str),
        ],
    )


def _recent_thoughts_block(thoughts: tuple[str, ...]) -> str:
    if not thoughts:
        return ""
    body = "\n".join(
        f'- "{_compact(thought)}"'
        for thought in thoughts
        if _compact(thought)
    )
    if not body:
        return ""
    return (
        "\nRECENT PRIVATE THOUGHTS\n"
        "These are what you already thought; only carry something new, not a restatement.\n"
        f"{body}\n"
    )


def build_lean_idle_prompt(facts: LeanIdleFacts) -> LeanIdlePrompt:
    self_card = _compact(facts.self_card_text)
    private_summary = _content_light_json(facts.private_signal_summary)
    fact_keys = (
        "self_card",
        "cycle",
        "doorman_reason",
        "private_signal_summary",
        "time_facts",
        "body_state",
        "body_state_window",
        "open_loops",
        "recent_private_thoughts",
    )
    text = (
        "LEAN IDLE HEARTBEAT\n"
        "This is a private notebook beat, not a reply to the owner.\n"
        "Use only the facts below. Do not search, act, message, or propose contacting the owner.\n"
        f"If nothing is worth privately carrying, answer exactly {HEARTBEAT_OK}.\n"
        f"If there is a private note, write at most {MAX_PRIVATE_NOTE_CHARS} characters.\n\n"
        "FACTS\n"
        f"- cycle: {int(facts.cycle)}\n"
        f"- doorman_reason: {_compact(facts.doorman_reason)}\n"
        f"- private_signal_summary: {private_summary}\n\n"
        "SELF CARD\n"
        f"{self_card}\n"
        + _time_block(facts.time_facts)
        + _body_block(facts.body_state)
        + _body_state_window_block(facts.body_state_window)
        + _loops_block(facts.open_loops)
        + _recent_thoughts_block(facts.recent_private_thoughts)
    )
    return LeanIdlePrompt(
        text=text,
        fact_keys=fact_keys,
        sha256=_sha256(text),
        chars=len(text),
    )


def _extract_final(text: str) -> str:
    match = _FINAL_TAG_RE.search(text or "")
    return match.group(1).strip() if match else (text or "").strip()


def sanitize_private_note(raw_text: object) -> PrivateNote | None:
    text = _compact(_extract_final(str(raw_text or "")))
    if not text:
        return None
    if text.strip().upper() == HEARTBEAT_OK:
        return None
    if _OWNER_ADDRESS_RE.search(text) or _ACTION_RE.search(text):
        return None
    if len(text) > MAX_PRIVATE_NOTE_CHARS:
        text = text[: MAX_PRIVATE_NOTE_CHARS - 4].rstrip() + " ..."
    return PrivateNote(text=text, sha256=_sha256(text), chars=len(text))


def select_private_reader_thoughts(
    rows: list[dict],
    *,
    version: str = HEARTBEAT_VERSION,
    limit: int = 2,
    clip: int = 140,
) -> tuple[str, ...]:
    """Surface heartbeat thoughts only through the full private-reader envelope."""
    out: list[str] = []
    for row in rows or []:
        context = row.get("context") or {}
        if context.get("source") != version:
            continue
        if context.get("consent_tier") != ConsentTier.OWNER_PRIVATE.value:
            continue
        flows = context.get("allowed_flows") or []
        if AllowedFlow.PRIVATE_READER.value not in flows:
            continue
        if (row.get("memory_phase") or context.get("memory_phase")) != "gestation":
            continue
        text = _compact(row.get("content"))
        if not text:
            continue
        out.append(text[:clip])
        if len(out) >= limit:
            break
    return tuple(out)


def _response_content(response: object) -> str:
    message = getattr(response, "message", None)
    if message is not None and hasattr(message, "content"):
        return str(message.content or "")
    return str(response or "")


def _response_diagnostics(raw: str, response: object) -> ModelDiagnostics:
    return ModelDiagnostics(
        output_chars=len(str(raw or "")),
        finish_reason=_compact(getattr(response, "finish_reason", ""))[:80],
        backend=_compact(getattr(response, "backend", ""))[:80],
        thinking_suppressed=bool(getattr(response, "thinking_suppressed", False)),
        raw_sha256=_sha256_full(raw),
    )


def _recent_output_hashes(private_thoughts: object, *, limit: int = 3) -> set[str]:
    try:
        rows = private_thoughts.recent(limit=20)
    except Exception:
        return set()
    hashes: set[str] = set()
    for row in rows:
        context = row.get("context") or {}
        if context.get("source") != HEARTBEAT_VERSION:
            continue
        extra = context.get("extra") or {}
        value = extra.get("output_sha256")
        if isinstance(value, str) and value:
            hashes.add(value)
            if len(hashes) >= limit:
                break
    return hashes


def _base_receipt(
    *,
    prompt: LeanIdlePrompt,
    facts: LeanIdleFacts,
    mode: str,
    llm_called: bool,
    note: PrivateNote | None = None,
    diagnostics: ModelDiagnostics | None = None,
    skip_reason: str = "none",
    would_store: bool = False,
    stored: bool = False,
) -> dict[str, object]:
    diagnostics = diagnostics or ModelDiagnostics()
    return {
        "schema_version": HEARTBEAT_VERSION,
        "eligible": True,
        "mode": mode,
        "cycle": int(facts.cycle),
        "doorman_reason": facts.doorman_reason,
        "prompt_chars": prompt.chars,
        "prompt_sha256": prompt.sha256,
        "fact_keys": ",".join(prompt.fact_keys),
        "llm_called": bool(llm_called),
        "would_store": bool(would_store),
        "stored": bool(stored),
        "skip_reason": skip_reason,
        "output_chars": diagnostics.output_chars,
        "finish_reason": diagnostics.finish_reason,
        "backend": diagnostics.backend,
        "thinking_suppressed": diagnostics.thinking_suppressed,
        "raw_sha256": diagnostics.raw_sha256,
        "note_chars": 0 if note is None else note.chars,
        "output_sha256": "" if note is None else note.sha256,
    }


def run_lean_idle_heartbeat(
    *,
    facts: LeanIdleFacts,
    chat_fn,
    model: str,
    private_thoughts: object | None,
    enabled: bool,
    shadow: bool,
) -> LeanIdleResult:
    prompt = build_lean_idle_prompt(facts)
    mode = "enabled" if enabled else "shadow" if shadow else "disabled"
    if not enabled and not shadow:
        receipt = _base_receipt(
            prompt=prompt,
            facts=facts,
            mode=mode,
            llm_called=False,
            skip_reason="disabled",
        )
        return LeanIdleResult(False, False, None, None, "disabled", receipt)

    response = chat_fn(
        model=model,
        messages=[
            {"role": "system", "content": "You are writing a private idle notebook note."},
            {"role": "user", "content": prompt.text},
        ],
        think=False,
        options={
            "temperature": 0.35,
            "num_predict": 220,
            "chat_template_kwargs": {"enable_thinking": False},
        },
        purpose="lean_idle_heartbeat",
    )
    raw_response = _response_content(response)
    diagnostics = _response_diagnostics(raw_response, response)
    note = sanitize_private_note(raw_response)
    if note is None:
        receipt = _base_receipt(
            prompt=prompt,
            facts=facts,
            mode=mode,
            llm_called=True,
            diagnostics=diagnostics,
            skip_reason="heartbeat_ok_or_rejected",
        )
        return LeanIdleResult(
            intercepted=bool(enabled),
            stored=False,
            thought_id=None,
            return_text=HEARTBEAT_OK if enabled else None,
            skip_reason="heartbeat_ok_or_rejected",
            receipt=receipt,
        )

    if not enabled:
        receipt = _base_receipt(
            prompt=prompt,
            facts=facts,
            mode=mode,
            llm_called=True,
            note=note,
            diagnostics=diagnostics,
            would_store=True,
            stored=False,
        )
        return LeanIdleResult(False, False, None, None, "shadow_only", receipt)

    if private_thoughts is None:
        receipt = _base_receipt(
            prompt=prompt,
            facts=facts,
            mode=mode,
            llm_called=True,
            note=note,
            diagnostics=diagnostics,
            would_store=True,
            stored=False,
            skip_reason="private_thoughts_unavailable",
        )
        return LeanIdleResult(
            True,
            False,
            None,
            HEARTBEAT_OK,
            "private_thoughts_unavailable",
            receipt,
        )

    if note.sha256 in _recent_output_hashes(private_thoughts):
        receipt = _base_receipt(
            prompt=prompt,
            facts=facts,
            mode=mode,
            llm_called=True,
            note=note,
            diagnostics=diagnostics,
            would_store=True,
            stored=False,
            skip_reason="duplicate_recent_output",
        )
        return LeanIdleResult(True, False, None, HEARTBEAT_OK, "duplicate_recent_output", receipt)

    thought_id = private_thoughts.record_signal(
        content=note.text,
        signal_kind=SignalKind.SELF_WONDERING,
        producer_id=ProducerId.SELF_WONDERING,
        source=HEARTBEAT_VERSION,
        subject="maez_internal_state",
        consent_tier=ConsentTier.OWNER_PRIVATE,
        retention=RetentionRule.UNTIL_REVIEWED,
        allowed_flows=(AllowedFlow.PRIVATE_READER, AllowedFlow.AUDIT_TRACE),
        context_extra={
            "cycle": int(facts.cycle),
            "doorman_reason": facts.doorman_reason,
            "prompt_chars": prompt.chars,
            "prompt_sha256": prompt.sha256,
            "output_chars": note.chars,
            "output_sha256": note.sha256,
            "model_output_chars": diagnostics.output_chars,
            "finish_reason": diagnostics.finish_reason,
            "backend": diagnostics.backend,
            "thinking_suppressed": diagnostics.thinking_suppressed,
            "raw_sha256": diagnostics.raw_sha256,
            "model": str(model),
            "producer_version": HEARTBEAT_VERSION,
            "fact_keys": list(prompt.fact_keys),
            "shadow": bool(shadow),
            "enabled": bool(enabled),
        },
        memory_phase="gestation",
    )
    receipt = _base_receipt(
        prompt=prompt,
        facts=facts,
        mode=mode,
        llm_called=True,
        note=note,
        diagnostics=diagnostics,
        would_store=True,
        stored=True,
    )
    return LeanIdleResult(True, True, int(thought_id), HEARTBEAT_OK, "none", receipt)
