# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""
brain_loop.py — surface-agnostic Jarvis / ReAct-style tool-use loop.

Extracted 2026-04-20 from `skills/telegram_voice.py::_run_jarvis_loop`
so every surface (Telegram, CLI, Web, the new vendored surface
adapter) can share the same brain-side tool iteration without each
re-implementing it.

The function `run_brain_loop(user_text, *, action_engine, get_pipeline,
user_id, chat_id, ...)` is the surface-agnostic contract. Surfaces
pass in:
  - `action_engine` — the ActionEngine instance (tier/forbidden checks)
  - `get_pipeline` — callable returning the DecisionPipeline
  - `user_id`, `chat_id` — who is talking, where
  - `send_intermediate` — optional callback for the dialog-opening
    message that appears BEFORE the final synthesis reply (Lane 3
    self-mod). Surfaces implement this per their IO layer.
  - `model` — LLM model identifier for the planning + synthesis calls

The function returns the full transcript block as a string — empty
if no tools were used. Surfaces then inject that transcript into
their own synthesis prompt.

IMPORTANT: The shape is preserved byte-for-byte from the original
`_run_jarvis_loop` so behavior is identical across the migration.
Changes here are mechanical: `self.X` → parameters, `MODEL` → param,
`_send_card_message` → `send_intermediate` callback.
"""
from __future__ import annotations

import json as _json
import hashlib
import logging
import os as _os
import re as _re
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from core import llm_client as _llm_client
from core.search.sense_flag import page_read_enabled, sense_enabled


@dataclass
class BrainLoopResult:
    """Slice 3 of the trace work — structured return from the tool
    loop. Existing callers that take only the transcript string keep
    working via ``run_brain_loop(...)``; callers that want trace-grade
    tool-call data pass ``return_structured=True`` and consume
    ``result.transcript`` + ``result.tool_calls``.

    ``tool_calls`` is a list of dicts shaped like
    ``core.turn_traces.ToolCall`` (the daemon's trace schema) so the
    surface adapter can hand it straight into
    ``daemon.handle_message(..., tool_calls=...)`` without further
    translation.

    Status mapping (keep in sync with `_transcript_to_tool_call_dict`):

    - ``ok``       — the tool ran and reported success
    - ``error``    — the tool ran and reported failure (exception,
                     non-zero exit, internal error)
    - ``denied``   — the action was REFUSED before execution
                     (covenant gate / not on allowlist)
    - ``pending``  — the action was approval-gated, a card was
                     created, nothing executed yet
    - ``timeout``  — reserved for future use; no path emits this
                     today (timing wrapper is a follow-up)
    """

    transcript: str = ""
    tool_calls: list[dict] = field(default_factory=list)
    recall_items: tuple[Any, ...] = ()


def _emit_search_progress(send_intermediate, external_sources, *, stage: str, count):
    """Emit true substrate progress for real fresh-evidence fanout stages."""
    if send_intermediate is None:
        return
    source_values = {
        str(getattr(source, "value", source)) for source in (external_sources or ())
    }
    if not source_values.intersection({"WEB_SEARCH", "FETCH_URL"}):
        return
    try:
        if stage == "start" and "FETCH_URL" in source_values:
            send_intermediate("reading the page...")
        elif stage == "start":
            send_intermediate("searching the web...")
        elif "WEB_SEARCH" in source_values and stage == "results" and count is not None:
            send_intermediate(f"reading {count} results...")
    except Exception:
        logging.getLogger("maez").debug("search progress emit failed", exc_info=True)


def _routing_comprehension_dialogue_tail(chat_history) -> tuple[str, ...]:
    if not chat_history:
        return ()
    out: list[str] = []
    for exchange in list(chat_history)[-4:]:
        if isinstance(exchange, dict):
            text = str(exchange.get("content") or "").strip()
        else:
            text = str(exchange or "").strip()
        if text:
            out.append(text[:700])
    return tuple(out)


def _routing_comprehension_trigger_reason(layer0_spec, spec) -> str:
    try:
        if getattr(spec, "composition_hint", None):
            return str(getattr(spec.composition_hint, "value", spec.composition_hint))
        if getattr(layer0_spec, "to_dict", None):
            original = layer0_spec.to_dict()
        else:
            original = {}
        return str(original.get("composition_hint") or "web_search_selected")
    except Exception:
        return "web_search_selected"


@dataclass(frozen=True)
class _DispatcherPathResult:
    transcript: str = ""
    should_run_jarvis: bool = False
    recall_items: tuple[Any, ...] = ()


def _recall_citation_render_v2_enabled() -> bool:
    return (
        (_os.environ.get("MAEZ_RECALL_CITATION_RENDER_V2", "") or "")
        .strip()
        .lower()
        in {"1", "true", "yes"}
    )


def recall_partitions_to_items(partition: dict, *, role_source_type: str):
    """Convert recall partitions into structured dispatcher RecallItems.

    Shared by the live recall adapter and the shadow harness so temporal
    confirmation is computed in exactly one place.
    """
    from core.dispatcher.layer1 import RecallItem

    rows: list[dict] = []
    for tier in ("core", "daily", "raw"):
        rows.extend((partition or {}).get(tier, []) or [])
    items = []
    for row in rows:
        meta = row.get("metadata") or {}
        method = meta.get("temporal_match_method")
        temporal_provenance = None
        if method:
            temporal_provenance = {
                "method": method,
                "confirmed": method in ("exact_date", "month_window"),
            }
            if _recall_citation_render_v2_enabled():
                label = meta.get("temporal_match_label")
                date_value = meta.get("date")
                if not date_value and label:
                    match = _re.search(r"\b\d{4}-\d{2}-\d{2}\b", str(label))
                    if match:
                        date_value = match.group(0)
                if label:
                    temporal_provenance["label"] = str(label)
                if date_value:
                    temporal_provenance["date"] = str(date_value)[:10]
        text = _llm_client.sanitize_prompt_text(str(row.get("content") or ""))
        items.append(
            RecallItem(
                text=text,
                source_type=role_source_type,
                durable_id=str(row.get("id") or "") or None,
                temporal_provenance=temporal_provenance,
                trust_tier=meta.get("trust_tier"),
                provenance_source=meta.get("provenance_source"),
            )
        )
    return tuple(items)


def _summarize(value, *, limit: int) -> str:
    """Stringify-and-truncate. Used to keep tool_call dicts small
    enough that the trace JSONL line stays a single readable line."""
    if value is None:
        return ""
    try:
        if isinstance(value, str):
            return value[:limit]
        return _json.dumps(value, default=str)[:limit]
    except Exception:
        try:
            return str(value)[:limit]
        except Exception:
            return ""


def _classify_transcript_status(out: str, ok) -> str:
    """Map a transcript tuple's ``out`` + ``ok`` flag into the trace
    schema's status vocabulary. ``ok`` may be True / False / 'pending'
    (mirroring the tri-state in run_brain_loop's transcript)."""
    if ok is True:
        return "ok"
    if ok == "pending":
        return "pending"
    text = (out or "").strip()
    # The transcript carries human-readable result strings. Distinguish
    # covenant-rejected (denied) from runtime errors by their leading
    # marker; the strings are stable shapes emitted from a few sites
    # in this same module.
    if text.startswith("REFUSED"):
        return "denied"
    if text.startswith("ALREADY_RAN") or text.startswith("PARSE_ERROR"):
        return "error"
    return "error"


def _transcript_to_tool_call_dict(item: tuple) -> dict:
    """Convert one ``transcript.append(...)`` tuple into a dict
    compatible with ``core.turn_traces.ToolCall``. Always returns a
    dict; on malformed input returns a best-effort placeholder so a
    single bad tuple cannot break the whole surface."""
    try:
        action, params, out, ok = item
    except Exception:
        return {
            "name": "?",
            "args_summary": "",
            "status": "error",
            "elapsed_ms": 0,
            "output_summary": "",
            "error_summary": "(malformed transcript tuple)",
        }
    status = _classify_transcript_status(out, ok)
    out_str = "" if out is None else str(out)
    return {
        "name": str(action or "?"),
        "args_summary": _summarize(params, limit=200),
        # elapsed_ms stays 0 in v1 — adding per-call timing is a
        # separate small slice (wrap the dispatcher with a stopwatch).
        "elapsed_ms": 0,
        "status": status,
        "output_summary": out_str[:500] if status == "ok" else "",
        "error_summary": out_str[:500] if status != "ok" else "",
    }


def _dispatcher_enabled(recall_stack_config=None) -> bool:
    if recall_stack_config is None:
        from core.routing.recall_stack_config import resolve_recall_stack

        recall_stack_config = resolve_recall_stack()
    return recall_stack_config.triad_on


def _living_recall_enabled(recall_stack_config=None) -> bool:
    if recall_stack_config is None:
        from core.routing.recall_stack_config import resolve_recall_stack

        recall_stack_config = resolve_recall_stack()
    return recall_stack_config.triad_on


_DISPATCHER_ARCHETYPE_INDEX = None
_DISPATCHER_REPAIR_FSM = None
_DISPATCHER_MEMORY_MANAGER = None


def _dispatcher_index():
    global _DISPATCHER_ARCHETYPE_INDEX
    if _DISPATCHER_ARCHETYPE_INDEX is None:
        from core.dispatcher.layer0 import load_archetype_index

        _DISPATCHER_ARCHETYPE_INDEX = load_archetype_index()
    return _DISPATCHER_ARCHETYPE_INDEX


def _dispatcher_repair_fsm():
    global _DISPATCHER_REPAIR_FSM
    if _DISPATCHER_REPAIR_FSM is None:
        from core.dispatcher.layer2 import Layer2RepairFSM

        _DISPATCHER_REPAIR_FSM = Layer2RepairFSM()
    return _DISPATCHER_REPAIR_FSM


def _dispatcher_memory_manager():
    global _DISPATCHER_MEMORY_MANAGER
    if _DISPATCHER_MEMORY_MANAGER is None:
        from memory.memory_manager import MemoryManager

        _DISPATCHER_MEMORY_MANAGER = MemoryManager()
    return _DISPATCHER_MEMORY_MANAGER


def _dispatcher_inventory_summary():
    from core.dispatcher.inventory import InventoryRegistry
    from core.dispatcher.spec import ExternalSource, SubstrateSource

    return InventoryRegistry().summarize([*SubstrateSource, *ExternalSource]).to_spec_fields()


def _dispatcher_recall_adapters(
    user_text: str,
    *,
    spec=None,
    surface: str = "",
    chat_history=None,
    recall_stack_config=None,
):
    from core.dispatcher.layer1 import (
        MAX_RECALL_CHARS_PER_SOURCE,
        RecallBlock,
        RecallItem,
    )
    from core.dispatcher.spec import SubstrateSource
    from core.routing.temporal_cue import absolute_recall_cue

    _override_continuity_for_date = absolute_recall_cue(user_text).override_continuity

    def _bounded_text(text: str, *, limit: int = MAX_RECALL_CHARS_PER_SOURCE) -> str:
        if len(text) <= limit:
            return text
        marker = "\n[truncated for dispatcher recall budget]"
        if limit <= len(marker):
            return marker[:limit]
        return text[: limit - len(marker)].rstrip() + marker

    def _reddit_source_adapter(source: SubstrateSource):
        memory = _dispatcher_memory_manager()
        rows = memory._recent_reddit_source_rows(memory.raw, user_text, limit=3)
        if not rows:
            return []
        lines = ["Recent Reddit substrate rows:"]
        for row in rows:
            meta = row.get("metadata") or {}
            source_label = meta.get("source") or "reddit"
            timestamp = meta.get("timestamp") or "unknown time"
            score = meta.get("reddit_score")
            comments = meta.get("reddit_comments")
            engagement = []
            if score is not None:
                engagement.append(f"{score} pts")
            if comments is not None:
                engagement.append(f"{comments} comments")
            suffix = f" ({', '.join(engagement)})" if engagement else ""
            lines.append(f"- {source_label} at {timestamp}{suffix}: {row.get('content') or ''}")
        text = _bounded_text("\n".join(lines))
        return [
            RecallBlock(
                source=source,
                text=text,
                timestamp=None,
                freshness="reddit_source_rows",
                rationale="recent_reddit_source_rows",
                prompt_cost=len(text),
            )
        ]

    def _legacy_memory_manager_adapter(source: SubstrateSource):
        memory = _dispatcher_memory_manager()
        recalled = memory.recall_for_telegram(user_text)
        text = memory.format_for_prompt(recalled, max_chars=1200)
        if not text:
            return []
        return [
            RecallBlock(
                source=source,
                text=text,
                timestamp=None,
                freshness="memory_manager",
                rationale="recall_for_telegram",
                prompt_cost=len(text),
            )
        ]

    def _latest_dialogue_anchor_text() -> str:
        try:
            from core.brain.conversation_history import latest_dialogue_anchor_text

            return latest_dialogue_anchor_text(chat_history)
        except Exception:
            pass
        return ""

    def _continuity_needs_dialogue_anchor() -> bool:
        try:
            from core.routing.focused_cognition import (
                ContinuityKind,
                dialogue_continuity_state,
            )

            state = dialogue_continuity_state(user_text)
            return state.kind in {ContinuityKind.DIRECT, ContinuityKind.ANAPHORIC}
        except Exception:
            return False

    def _living_memory_manager_adapter(source: SubstrateSource):
        if not _living_recall_enabled(recall_stack_config) or not (surface or "").startswith("telegram"):
            return _legacy_memory_manager_adapter(source)

        from core.dispatcher.spec import ProvenanceFraming, SourceRole

        def _allowed_substrate_roles():
            if spec is None:
                return {SourceRole.SUBSTRATE_EVIDENCE, SourceRole.SUBSTRATE_CONTEXT}
            framing = spec.provenance_framing
            if framing == ProvenanceFraming.SUBSTRATE_ONLY_NO_FRESH_VALIDATION:
                return {SourceRole.SUBSTRATE_EVIDENCE, SourceRole.SUBSTRATE_CONTEXT}
            if framing == ProvenanceFraming.SUBSTRATE_EVIDENCE_FRESH_CONTEXT:
                return {SourceRole.SUBSTRATE_EVIDENCE}
            if framing in {
                ProvenanceFraming.HYBRID_FRESH_VALIDATES_SUBSTRATE_CONTEXTUALIZES,
                ProvenanceFraming.FRESH_ATTEMPTED_UNAVAILABLE_SUBSTRATE_CONTEXT,
            }:
                return {SourceRole.SUBSTRATE_CONTEXT}
            return set()

        allowed_roles = _allowed_substrate_roles()
        if not allowed_roles:
            return []
        memory = _dispatcher_memory_manager()
        evidence, context = memory.recall_for_telegram_living(
            user_text,
            record_recalls=False,
        )

        def _rendered_partition(rendered_text: str, partition: dict) -> dict:
            rendered_ids = set(_re.findall(r'id="([^"]+)"', rendered_text or ""))
            if not rendered_ids:
                return partition

            filtered = {}
            for tier, rows in (partition or {}).items():
                filtered[tier] = [
                    row for row in (rows or [])
                    if str(row.get("id", ""))[:16] in rendered_ids
                ]
            return filtered

        def _record_rendered(*rendered_pairs):
            recorder = getattr(memory, "_record_living_recall", None)
            if callable(recorder):
                recorder(
                    user_text,
                    *[
                        _rendered_partition(rendered_text, partition)
                        for rendered_text, partition in rendered_pairs
                        if rendered_text
                    ],
                )

        def _items_for(partition: dict, role_source_type: str) -> tuple[RecallItem, ...]:
            return recall_partitions_to_items(
                partition,
                role_source_type=role_source_type,
            )

        def _combined_context_items(*partitions: dict) -> tuple[RecallItem, ...]:
            items: list[RecallItem] = []
            for partition in partitions:
                items.extend(_items_for(partition, "memory_context"))
            return tuple(items)

        def _memory_prompt_without_items(text: str) -> bool:
            return (
                (text or "").lstrip().startswith("=== PAST OBSERVATIONS")
                and not _re.search(r'<RECALLED\b[^>]*\bid="', text or "")
            )

        deep_context_priority = bool(context.get("core")) and _re.search(
            r"\b(?:january|february|march|april|june|july|august|"
            r"september|october|november|december|20\d{2}|"
            r"may\s+\d{1,2}|may\s+20\d{2}|"
            r"back around|back in|months ago|years ago|last month)\b",
            user_text.lower(),
        )
        if deep_context_priority:
            context_budget = int(MAX_RECALL_CHARS_PER_SOURCE * 0.75)
            evidence_budget = MAX_RECALL_CHARS_PER_SOURCE - context_budget
        else:
            evidence_budget = int(MAX_RECALL_CHARS_PER_SOURCE * 0.75)
            context_budget = MAX_RECALL_CHARS_PER_SOURCE - evidence_budget
        blocks = []
        memory_ev_text = _bounded_text(
            memory.format_for_prompt(evidence, max_chars=evidence_budget),
            limit=evidence_budget,
        )
        if _memory_prompt_without_items(memory_ev_text):
            memory_ev_text = ""
        context_for_prompt = context
        ctx_text = _bounded_text(
            memory.format_living_context(context_for_prompt, max_chars=context_budget),
            limit=context_budget,
        )
        if _memory_prompt_without_items(ctx_text):
            ctx_text = ""
        ev_text = memory_ev_text
        anchor_active = False
        # Date-address override: assemble_working_set handles precedence; here
        # we only decline to fabricate a dialogue-anchor producer.
        if _continuity_needs_dialogue_anchor() and not _override_continuity_for_date:
            anchor = _latest_dialogue_anchor_text()
            if anchor:
                anchor_active = True
                ev_text = _bounded_text(
                    f"Recent dialogue anchor:\n{anchor}",
                    limit=evidence_budget,
                )
                ctx_text = _bounded_text(
                    "\n".join(
                        part for part in (memory_ev_text, ctx_text) if part
                    ),
                    limit=context_budget,
                )
        if allowed_roles == {SourceRole.SUBSTRATE_CONTEXT}:
            combined = "\n".join(part for part in (ev_text, ctx_text) if part)
            if not combined:
                return []
            text = _bounded_text(combined)
            if anchor_active:
                _record_rendered((ctx_text, evidence), (ctx_text, context_for_prompt))
            else:
                _record_rendered((ev_text, evidence), (ctx_text, context_for_prompt))
            return [
                RecallBlock(
                    source=source,
                    text=text,
                    timestamp=None,
                    freshness="living_recall",
                    rationale="living_context",
                    prompt_cost=len(text),
                    role_hint=SourceRole.SUBSTRATE_CONTEXT,
                    items=_combined_context_items(evidence, context_for_prompt),
                )
            ]
        if allowed_roles == {SourceRole.SUBSTRATE_EVIDENCE}:
            if not ev_text:
                return []
            text = _bounded_text(ev_text)
            if not anchor_active:
                _record_rendered((memory_ev_text, evidence))
            return [
                RecallBlock(
                    source=source,
                    text=text,
                    timestamp=None,
                    freshness="living_recall",
                    rationale="living_evidence",
                    prompt_cost=len(text),
                    role_hint=SourceRole.SUBSTRATE_EVIDENCE,
                    items=() if anchor_active else _items_for(evidence, "memory_evidence"),
                )
            ]
        if ev_text:
            blocks.append(
                RecallBlock(
                    source=source,
                    text=ev_text,
                    timestamp=None,
                    freshness="living_recall",
                    rationale="living_evidence",
                    prompt_cost=len(ev_text),
                    role_hint=SourceRole.SUBSTRATE_EVIDENCE,
                    items=() if anchor_active else _items_for(evidence, "memory_evidence"),
                )
            )
        if ctx_text:
            blocks.append(
                RecallBlock(
                    source=source,
                    text=ctx_text,
                    timestamp=None,
                    freshness="living_recall",
                    rationale="living_context",
                    prompt_cost=len(ctx_text),
                    role_hint=SourceRole.SUBSTRATE_CONTEXT,
                    items=(
                        _combined_context_items(evidence, context_for_prompt)
                        if anchor_active
                        else _items_for(context_for_prompt, "memory_context")
                    ),
                )
            )
        if anchor_active:
            _record_rendered((ctx_text, evidence), (ctx_text, context_for_prompt))
        else:
            _record_rendered((memory_ev_text, evidence), (ctx_text, context_for_prompt))
        return blocks

    return {
        SubstrateSource.REDDIT_SOURCE: _reddit_source_adapter,
        SubstrateSource.TELEGRAM_TEMPORAL: _living_memory_manager_adapter,
        SubstrateSource.TELEGRAM_SEMANTIC: _living_memory_manager_adapter,
    }


def _source_role_for_dispatcher_block(spec):
    from core.dispatcher.spec import ProvenanceFraming, SourceRole

    if spec.provenance_framing == ProvenanceFraming.SUBSTRATE_EVIDENCE_FRESH_CONTEXT:
        return SourceRole.SUBSTRATE_EVIDENCE
    return SourceRole.SUBSTRATE_CONTEXT


def _render_dispatcher_transcript(spec, layer1_result, *, user_text: str, surface: str) -> str:
    if spec.external_sources:
        return ""

    from core.dispatcher.provenance_renderer import (
        AskShape,
        SourceSummary,
        render_provenance,
    )

    summaries = _recall_source_summaries(spec, tuple(layer1_result.recall_blocks))
    summarized_sources = {summary.source for summary in summaries}
    role = _source_role_for_dispatcher_block(spec)
    for branch in getattr(layer1_result, "branch_results", ()) or ():
        if branch.source in summarized_sources or branch.source not in spec.substrate_sources:
            continue
        reason = branch.empty_reason or branch.error_class or branch.deadline_kind or "no_rows"
        text = (
            f"No usable recall returned from {branch.source.value}: "
            f"{branch.status.value}"
            f"{f' ({reason})' if reason else ''}."
        )
        summaries.append(
            SourceSummary(
                source=branch.source,
                role=role,
                text=text,
                content_digest="sha256:" + hashlib.sha256(text.encode()).hexdigest(),
            )
        )
        summarized_sources.add(branch.source)
    for source in spec.substrate_sources:
        if source in summarized_sources:
            continue
        text = f"No usable recall returned from {source.value}: NO_BRANCH_RESULT."
        summaries.append(
            SourceSummary(
                source=source,
                role=role,
                text=text,
                content_digest="sha256:" + hashlib.sha256(text.encode()).hexdigest(),
            )
        )
        summarized_sources.add(source)
    rendered = render_provenance(
        spec,
        utterance=user_text,
        surface=surface,
        ask_shape=AskShape.CONVERSATIONAL,
        timestamp=str(int(time.time())),
        source_summaries=summaries,
    )
    return rendered.prompt_block


def _recall_source_summaries(spec, recall_blocks):
    from core.dispatcher.merge import source_summaries_for_render

    return source_summaries_for_render(spec, tuple(recall_blocks), ())


def _run_dispatcher_pipeline(
    *,
    user_text: str,
    surface: str,
    bond_id: str,
    chat_id: str,
    chat_history=None,
    recall_stack_config=None,
    send_intermediate=None,
) -> _DispatcherPathResult:
    from core.dispatcher.inventory import InventorySummary
    from core.dispatcher.external_sources import ExternalBranchStatus, ExternalFanout
    from core.dispatcher.layer0 import Layer0Dispatcher
    from core.dispatcher.layer1 import Layer1Fanout, RecallBranchStatus
    from core.dispatcher.layer2 import RepairRefusal
    from core.dispatcher.merge import merge_fanout_results

    total_started = time.monotonic()
    logger.info(
        "dispatcher_path_entry surface=%s bond_id=%s chat_id=%s flag_state=enabled recovery_seed_present=%s",
        surface,
        bond_id,
        chat_id,
        False,
    )

    inventory = InventorySummary(generated_at=time.monotonic(), **_dispatcher_inventory_summary())

    layer0_started = time.monotonic()
    spec = Layer0Dispatcher(index=_dispatcher_index()).emit_spec(
        user_text,
        surface=surface,
        inventory=inventory,
    )
    layer0_spec = spec
    layer0_elapsed_ms = (time.monotonic() - layer0_started) * 1000
    logger.info(
        "dispatcher_layer0_emit surface=%s bond_id=%s composition_hint=%s provenance_framing=%s inventory_witness=%s substrate_source_count=%s external_source_count=%s elapsed_ms=%.3f",
        surface,
        bond_id,
        spec.composition_hint.value,
        spec.provenance_framing.value,
        spec.inventory_witness.value,
        len(spec.substrate_sources),
        len(spec.external_sources),
        layer0_elapsed_ms,
    )
    if layer0_elapsed_ms > 50:
        logger.warning(
            "dispatcher_layer0_budget_breach surface=%s elapsed_ms=%.3f budget_ms=%s cold_or_warm=%s",
            surface,
            layer0_elapsed_ms,
            50,
            "warm",
        )

    fsm = _dispatcher_repair_fsm()
    layer2_result = fsm.apply_repair(
        bond_id=bond_id,
        surface=surface,
        conversation_id=chat_id,
        current_utterance=user_text,
        current_spec=spec,
    )
    if isinstance(layer2_result, RepairRefusal):
        logger.info(
            "dispatcher_layer2_repair surface=%s bond_id=%s result=refused refusal_reason=%s",
            surface,
            bond_id,
            layer2_result.reason.value,
        )
        try:
            from core.routing.observation import record_dispatcher_refusal_observation

            record_dispatcher_refusal_observation(
                user_text=user_text,
                surface=surface,
                chat_id=chat_id,
                spec=spec,
                refusal_reason=layer2_result.reason,
                elapsed_ms=(time.monotonic() - total_started) * 1000,
            )
        except Exception as exc:
            logger.debug("routing observation dispatcher refusal skipped: %s", exc)
        return _DispatcherPathResult(transcript="", should_run_jarvis=False)
    if layer2_result is spec:
        logger.info(
            "dispatcher_layer2_repair surface=%s bond_id=%s result=unchanged refusal_reason=",
            surface,
            bond_id,
        )
    else:
        logger.info(
            "dispatcher_layer2_repair surface=%s bond_id=%s result=repaired refusal_reason=",
            surface,
            bond_id,
        )
        spec = layer2_result

    fanout_generation_id = uuid.uuid4().hex
    fanout_started = time.monotonic()
    conversation_state = {
        "bond_id": bond_id,
        "surface": surface,
        "chat_id": chat_id,
        "chat_history": chat_history,
    }
    _routing_comprehension_veto_applied = False
    _routing_comprehension_context_block = ""
    try:
        from core.dispatcher.spec import ExternalSource as _RCExternalSource
        from core.routing import routing_comprehension as _routing_comprehension

        if (
            _routing_comprehension.any_enabled()
            and _RCExternalSource.WEB_SEARCH in list(spec.external_sources or [])
        ):
            _routing_comprehension_trigger = _routing_comprehension.SearchTrigger(
                source="WEB_SEARCH",
                reason=_routing_comprehension_trigger_reason(layer0_spec, spec),
            )
            try:
                from core.routing.attribution_render import (
                    last_web_receipt_context as _last_web_receipt_context,
                )

                _routing_comprehension_prior_receipt = _last_web_receipt_context(
                    chat_id
                )
            except Exception:
                _routing_comprehension_prior_receipt = None
            _routing_comprehension_context = _routing_comprehension.JudgeContext(
                current_turn=user_text,
                dialogue_tail=_routing_comprehension_dialogue_tail(chat_history),
                trigger=_routing_comprehension_trigger,
                prior_receipt=_routing_comprehension_prior_receipt,
            )
            _routing_comprehension_decision = (
                _routing_comprehension.default_judge().decide(
                    _routing_comprehension_context
                )
            )
            if (
                _routing_comprehension.enabled()
                and _routing_comprehension_decision.vetoes_web_search
            ):
                _new_spec = _routing_comprehension.apply_web_search_veto(
                    spec,
                    _routing_comprehension_decision,
                )
                _routing_comprehension_veto_applied = _new_spec is not spec
                spec = _new_spec
            if (
                _routing_comprehension.enabled()
                and _routing_comprehension_decision.decision
                == _routing_comprehension.Decision.THREAD_FOLLOWUP_ANSWERABLE
                and _routing_comprehension_veto_applied
            ):
                _routing_comprehension_context_block = (
                    _routing_comprehension.receipt_context_text(
                        _routing_comprehension_prior_receipt
                    )
                )
            _routing_comprehension_receipt = _routing_comprehension.shadow_receipt(
                surface=surface,
                chat_id=chat_id,
                decision=_routing_comprehension_decision,
                trigger=_routing_comprehension_trigger,
                enabled=_routing_comprehension.enabled(),
                veto_applied=_routing_comprehension_veto_applied,
            )
            logging.getLogger("core.routing.routing_comprehension").info(
                _routing_comprehension_receipt
            )
    except Exception as _routing_comprehension_exc:
        logging.getLogger("core.routing.routing_comprehension").debug(
            "routing comprehension skipped: %s",
            _routing_comprehension_exc,
        )
    layer1 = Layer1Fanout(
        adapters=_dispatcher_recall_adapters(
            user_text,
            spec=spec,
            surface=surface,
            chat_history=chat_history,
            recall_stack_config=recall_stack_config,
        ),
        branch_timeout_s=0.8,
        global_deadline_s=1.0,
    )
    external_fanout = ExternalFanout()
    _emit_search_progress(
        send_intermediate,
        spec.external_sources,
        stage="start",
        count=None,
    )
    with ThreadPoolExecutor(max_workers=2) as executor:
        layer1_future = executor.submit(
            layer1.run,
            spec,
            utterance=user_text,
            conversation_state=conversation_state,
            fanout_generation_id=fanout_generation_id,
        )
        external_future = executor.submit(
            external_fanout.run,
            spec,
            utterance=user_text,
            conversation_state=conversation_state,
            fanout_generation_id=fanout_generation_id,
        )
        layer1_result = layer1_future.result()
        external_result = external_future.result()

    for branch in layer1_result.branch_results:
        if branch.status == RecallBranchStatus.SUCCESS:
            outcome = "rows"
        elif branch.status == RecallBranchStatus.EMPTY:
            outcome = "empty_with_reason"
        elif branch.status == RecallBranchStatus.TIMEOUT:
            outcome = "timeout"
        elif branch.status == RecallBranchStatus.RESERVED_UNAVAILABLE:
            outcome = "reserved_skip"
        else:
            outcome = branch.status.value.lower()
        logger.info(
            "dispatcher_layer1_branch surface=%s source=%s outcome=%s row_count=%s elapsed_ms=%.3f",
            surface,
            branch.source.value,
            outcome,
            len(branch.blocks),
            branch.elapsed_ms,
        )
    for event in getattr(layer1_result, "budget_events", ()) or ():
        logger.info(
            "dispatcher_layer1_budget_limited surface=%s source=%s truncated_blocks=%s dropped_blocks=%s original_chars=%s capped_chars=%s",
            surface,
            event.source.value,
            event.truncated_blocks,
            event.dropped_blocks,
            event.original_chars,
            event.capped_chars,
        )
    total_fanout_ms = (time.monotonic() - fanout_started) * 1000
    seal_state = "clean"
    if any(branch.status != RecallBranchStatus.SUCCESS for branch in layer1_result.branch_results):
        seal_state = "partial_failure"
    logger.info(
        "dispatcher_layer1_fanout surface=%s fanout_generation_id=%s branch_count=%s seal_state=%s total_elapsed_ms=%.3f",
        surface,
        layer1_result.fanout_generation_id,
        len(layer1_result.branch_results),
        seal_state,
        total_fanout_ms,
    )
    external_seal_state = "clean"
    for branch in external_result.branch_results:
        if branch.status == ExternalBranchStatus.SUCCESS:
            outcome = "rows"
        elif branch.status == ExternalBranchStatus.EMPTY:
            outcome = "empty"
        elif branch.status == ExternalBranchStatus.TIMEOUT:
            outcome = "timeout"
        elif branch.status == ExternalBranchStatus.RESERVED_UNAVAILABLE:
            outcome = "reserved_skip"
        elif branch.status == ExternalBranchStatus.PREFLIGHT_BLOCKED:
            outcome = "preflight_blocked"
        else:
            outcome = "error"
        if branch.status != ExternalBranchStatus.SUCCESS:
            external_seal_state = "partial_failure"
        logger.info(
            "dispatcher_external_branch surface=%s source=%s outcome=%s block_count=%s elapsed_ms=%.3f error_class=%s empty_reason=%s",
            surface,
            branch.source.value,
            outcome,
            len(branch.blocks),
            branch.elapsed_ms,
            branch.error_class.value if branch.error_class else "",
            branch.empty_reason.value if branch.empty_reason else "",
        )
    logger.info(
        "dispatcher_external_fanout surface=%s fanout_generation_id=%s branch_count=%s seal_state=%s total_elapsed_ms=%.3f",
        surface,
        external_result.fanout_generation_id,
        len(external_result.branch_results),
        external_seal_state,
        total_fanout_ms,
    )

    rendered_turn = merge_fanout_results(
        spec,
        layer1_result,
        external_result,
        utterance=user_text,
        surface=surface,
        timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    )
    # Search-as-a-Sense v0.1 metabolism — pipeline side only. Memory is
    # owned by daemon.handle_message, so this stashes the evidence payload by
    # chat_id for the daemon to drain after audit.
    try:
        from core.intake_bus.world_observation_lane import evaluate_write_condition
        from core.routing.attribution_render import stash_turn_evidence

        if sense_enabled() or page_read_enabled():
            _web_texts = []
            _page_blocks = []
            for _branch in getattr(external_result, "branch_results", []) or []:
                _source_value = str(getattr(getattr(_branch, "source", None), "value", ""))
                if _source_value == "WEB_SEARCH":
                    _web_texts = [
                        getattr(_block, "text", "") or ""
                        for _block in (getattr(_branch, "blocks", ()) or ())
                    ][:3]
                elif _source_value == "FETCH_URL":
                    _page_blocks = list(getattr(_branch, "blocks", ()) or ())[:1]
            _page_texts = [
                getattr(_block, "text", "") or "" for _block in (_page_blocks or [])
            ]
            _observation = None
            if sense_enabled() and evaluate_write_condition(rendered_turn):
                _observation = {
                    "query": user_text,
                    "evidence_texts": _web_texts,
                    "diagnostic_id": str(
                        getattr(external_result, "fanout_generation_id", "")
                    ),
                }
            elif (
                page_read_enabled()
                and _page_blocks
                and evaluate_write_condition(rendered_turn, source_value="FETCH_URL")
            ):
                from core.search.page_extract import extract_first_url

                _page_text = _page_texts[0]
                _title, _sep, _rest = _page_text.partition("\n")
                _excerpt = (_rest if _sep else _page_text).strip()[:600]
                _observation = {
                    "kind": "page_read",
                    "url": extract_first_url(user_text) or "",
                    "title": _title.strip()[:200],
                    "excerpt": _excerpt,
                    "diagnostic_id": str(
                        getattr(_page_blocks[0], "egress_diagnostic_id", "")
                        or getattr(external_result, "fanout_generation_id", "")
                    ),
                }
            _read_url = (
                _observation.get("url")
                if isinstance(_observation, dict) and _observation.get("kind") == "page_read"
                else None
            )
            stash_turn_evidence(
                chat_id,
                rendered_turn=rendered_turn,
                evidence_texts=_web_texts or _page_texts,
                observation=_observation,
                extra_source_urls=[_read_url] if _read_url else None,
            )
    except Exception:
        logger.debug("world_observation stash skipped", exc_info=True)

    turn_seal_state = "clean"
    if rendered_turn.refusal_reason is not None:
        turn_seal_state = "refused"
    elif rendered_turn.effective_spec.to_dict() != spec.to_dict():
        turn_seal_state = "reconstructed"
    elif (
        seal_state == "partial_failure"
        or external_seal_state == "partial_failure"
    ):
        turn_seal_state = "partial_failure"

    if rendered_turn.refusal_reason is None:
        # Store the final effective spec, including merge-time reconstruction,
        # so the next repair turn inherits what was actually rendered.
        fsm.record_completed_spec(
            bond_id=bond_id,
            surface=surface,
            conversation_id=chat_id,
            spec=rendered_turn.effective_spec,
        )
    logger.info(
        "dispatcher_path_exit surface=%s bond_id=%s chat_id=%s path_taken=dispatcher turn_seal_state=%s total_elapsed_ms=%.3f",
        surface,
        bond_id,
        chat_id,
        turn_seal_state,
        (time.monotonic() - total_started) * 1000,
    )
    try:
        from core.routing.observation import record_dispatcher_turn_observation

        record_dispatcher_turn_observation(
            user_text=user_text,
            surface=surface,
            chat_id=chat_id,
            original_spec=layer0_spec,
            effective_spec=rendered_turn.effective_spec,
            layer1_result=layer1_result,
            external_result=external_result,
            rendered_turn=rendered_turn,
            turn_seal_state=turn_seal_state,
            elapsed_ms=(time.monotonic() - total_started) * 1000,
        )
    except Exception as exc:
        logger.debug("routing observation dispatcher turn skipped: %s", exc)
    _prompt_block = rendered_turn.prompt_block
    if _routing_comprehension_context_block:
        _prompt_block = f"{_prompt_block}\n\n{_routing_comprehension_context_block}"
    return _DispatcherPathResult(
        transcript=_prompt_block,
        should_run_jarvis=False,
        recall_items=getattr(rendered_turn, "recall_items", ()),
    )

# Alias to match original module's import style (`_jarvis_re` is the
# original name for the re module import in telegram_voice.py).
_jarvis_re = _re

logger = logging.getLogger(__name__)


# Conversational shapes — skip the planning loop if the WHOLE message
# matches one of these. Anything else (questions, requests, multi-word
# inputs that aren't pure greetings) goes through the loop and lets
# the planning LLM decide whether it needs tools or can answer DONE.
_CONVERSATIONAL_RE = _jarvis_re.compile(
    r'^\s*('
    r'hi|hello|hey|yo|sup|good (?:morning|afternoon|evening|night)|'
    r'thanks?|thank\s+you|thx|ty|cheers|'
    r'ok(?:ay)?|alright|got\s+it|sure|cool|nice|nope?|yes|yeah|yep|yup|'
    r'lol|haha|hmm+|hm+|wow|oh|ah|uh|huh|'
    r'love\s+(?:you|u|you\s+maez|u\s+maez)|miss\s+you|gn|gm|brb|bye|goodbye|see\s+you|later|'
    r'maez|hi\s+maez|hey\s+maez|good\s+(?:job|work|night)\s+maez'
    r')[\s.!?,]*$',
    _jarvis_re.IGNORECASE,
)

# Broader conversational-intent patterns that should NOT trigger the
# Jarvis tool loop. Added 2026-04-21 after a regression where questions
# like "What proposal?", "You didn't answer my question", and "What
# has been on your mind?" were routed into Jarvis and answered with
# systemctl output — the LoRA-tuned planner defaults to emitting tool
# calls even when the rule says "DONE if conversational." Gate on the
# shape of the message rather than relying on the model to pick DONE.
#
# Match criteria:
#   • pure meta-conversation ("you didn't...", "i said...", "what do you mean")
#   • open-ended reflective questions with NO system/process/file noun
#     ("what has been on your mind", "what are you thinking about",
#      "how do you feel", "what are you capable of")
#   • pure informational statements from the owner
#     ("I am ...", "I was ...", "I live in ...", "I'm going to ...")
#     with no imperative verb
#   • clarifying questions without a system target
#     ("what proposal", "what do you mean", "which one", "can you explain")
#
# Fail-safe: regex is intentionally conservative. Anything with a system
# noun (disk, service, file, log, process, gpu, ram, cpu, memory,
# command, package, etc.) falls through to Jarvis.
_SYSTEM_NOUN_RE = _jarvis_re.compile(
    r'\b(disk|cpu|gpu|ram|memory|mem|vram|file|files|folder|directory|'
    r'log|logs|service|services|process|processes|daemon|systemd|systemctl|'
    r'command|cmd|shell|bash|terminal|package|install|apt|snap|pip|npm|'
    r'git|commit|branch|repo|repository|node|python|ubuntu|kernel|'
    r'network|port|url|endpoint|api|http|https|curl|wget|run|check|'
    r'price|prices|stock|stocks|ticker|tickers|quote|quotes|market|'
    r'currency|exchange|rate|rates|usd|inr|eur|gbp|cad|aud|jpy|cny|'
    r'rupee|rupees|euro|euros|dollar|dollars|pound|pounds|yen|rs\.?|₹|€|£|¥|'
    r'show\s+me|list\s+files|what.?s\s+running|status|health)\b',
    _jarvis_re.IGNORECASE,
)

_CONVERSATIONAL_SHAPE_RE = _jarvis_re.compile(
    r'^\s*('
    # Meta-conversation
    r"you(?:\s+did(?:n['’]t|\s+not))?\s+(?:answer|reply|say|tell|understand|get)|"
    r"(?:i|we)\s+(?:said|asked|told|meant|thought)|"
    r"what\s+do\s+you\s+mean|"
    r"what\s+are\s+you\s+talking\s+about|"
    r"that['’]s\s+not\s+(?:what|it)|"
    # Open reflective / capability questions
    r"what(?:'s| is| has been| have you been)?\s+(?:on\s+your\s+mind|"
    r"you\s+(?:thinking|feeling|doing|up\s+to)|making\s+you|"
    r"going\s+on\s+(?:with\s+you|in\s+there))|"
    r"how\s+(?:do|are)\s+you(?:\s+feeling|\s+doing)?|"
    r"what\s+are\s+you\s+(?:capable\s+of|able\s+to\s+do|good\s+at)|"
    r"tell\s+me\s+about\s+yourself|"
    r"who\s+are\s+you|"
    # Clarifying questions without system targets
    r"what\s+(?:proposal|dream|card|idea|question|wondering)|"
    r"which\s+one|"
    r"can\s+you\s+(?:explain|clarify|elaborate|rephrase)|"
    # Plain informational self-reports
    r"i(?:['’]?m|\s+am|\s+was|\s+will\s+be|\s+have\s+been)\s+"
    r"(?:staying|living|in|at|going|feeling|thinking|working\s+on|"
    r"fine|good|tired|sick|home|here|there|back|away)"
    r')\b.{0,140}[.!?,]?\s*$',
    _jarvis_re.IGNORECASE,
)


def _is_conversational_intent(text: str) -> bool:
    """True if the message shape is clearly conversational — pure framing,
    reflection, or information — and has no system-noun anchor.

    Kept separate from the greeting-only _CONVERSATIONAL_RE so the two
    tests can be tuned independently. Falls back to False on any
    ambiguity: anything with a system noun routes to Jarvis.
    """
    if not text:
        return False
    t = text.strip()
    if _SYSTEM_NOUN_RE.search(t):
        return False
    return bool(_CONVERSATIONAL_SHAPE_RE.match(t))


# Defensive per-exchange content cap. The adapter that assembles
# chat_history caps the COUNT of exchanges; this caps the SIZE of any
# single exchange so one verbose `maez:` transcript can't blow out the
# planning prompt. Applied inside run_brain_loop's RECENT CONVERSATION
# renderer.
_MAX_EXCHANGE_CHARS = 800


def _record_tool_failure(action: str, params: dict, error: str,
                          *, surface: str = "brain_loop") -> None:
    """Persist a tool_failure to consequence_memory so future Maez
    can retrieve similar past failures when proposing similar
    actions. Fail-safe: any exception in the recorder is swallowed —
    logging is the primary signal, consequence_memory is the
    enrichment."""
    try:
        from core import consequence_memory as _cm
        # Context = what Maez tried. Keep short and greppable.
        cmd = (params or {}).get("cmd") if isinstance(params, dict) else ""
        context = f"action={action} cmd={cmd!r}" if cmd else f"action={action}"
        # Tags = the first token of cmd + action, for cheap lookup.
        tags = [action]
        if cmd:
            first = str(cmd).strip().split()[:1]
            if first:
                tags.append(first[0])
        _cm.record_event(
            kind=_cm.CLASS_TOOL_FAILURE,
            context=context[:400],
            outcome=(error or "").strip()[:400],
            feedback="",  # future Maez fills this on retrieval via LLM if needed
            surface=surface,
            tags=tags,
        )
    except Exception:
        pass  # intentionally silent; logging already happened


def _summarize_shell_error(err: str) -> str:
    """Extract a useful one-line summary from a ShellCommandError-style
    error string. Input typically looks like:
        exit=100
        stderr: E: Unable to locate package openrgb
        stdout: Hit:1 http://archive.ubuntu.com/ ...

    Returns either 'exit=<code>: <stderr snippet>' when stderr is present,
    or just 'exit=<code>' when it isn't. Falls back to the first line
    of the error if the structure isn't recognized.

    This helper exists because Fix 6's terminal summary and
    _collect_prior_attempts both used `err.split('\\n', 1)[0]` which
    grabbed only 'exit=100' and threw away the stderr context — the
    actual signal the owner needs to understand WHY an attempt failed.
    """
    if not err:
        return ""
    err = err.strip()
    lines = err.split("\n")
    exit_line = ""
    stderr_first = ""
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if line.startswith("exit="):
            exit_line = line[:40]
        elif line.startswith("stderr:") and not stderr_first:
            # First non-empty stderr content
            stderr_content = line[len("stderr:"):].strip()
            stderr_first = stderr_content.split("\n", 1)[0]
            if len(stderr_first) > 180:
                stderr_first = stderr_first[:177] + "…"
    if exit_line and stderr_first:
        return f"{exit_line}: {stderr_first}"
    if exit_line:
        return exit_line
    # Unknown shape — fall back to first non-empty line
    for line in lines:
        if line.strip():
            return line.strip()[:200]
    return ""


def _should_run_jarvis_loop(text: str) -> bool:
    """True if the message could plausibly need tools.

    Skips Jarvis (returns False) for:
      1. Short/empty messages
      2. Pure greetings + acks (_CONVERSATIONAL_RE)
      3. Broader conversational shapes with no system-noun anchor
         (_is_conversational_intent) — meta-conversation, open
         reflective questions, clarifications without system targets,
         and plain informational self-reports like "I'm staying in
         Columbia, MO." This was added 2026-04-21 after the LoRA
         planner over-emitted TOOL_CALLs on ordinary chat questions,
         producing system-status replies when the owner asked a
         conversational question.
    """
    if not text:
        return False
    t = text.strip()
    if len(t) < 3:
        return False
    if _CONVERSATIONAL_RE.match(t):
        return False
    if _is_conversational_intent(t):
        return False
    return True


# Tool-call parser. Accepts several formats the merged-LoRA gemma actually
# emits, plus the literal TOOL_CALL: {...} form we ask for in the manifest.
# Returns {"action": str, "params": dict} or None.
def _parse_tool_call(text: str) -> dict | None:
    import re as _re
    if not text:
        return None
    s = text.strip()

    # Form 1: TOOL_CALL: {"action": "...", "params": {...}}
    m = _re.search(r'TOOL_CALL\s*[:=]?\s*(\{.*\})', s, _re.DOTALL)
    if m:
        blob = _extract_balanced_json(m.group(1))
        if blob:
            try:
                obj = _json.loads(blob)
                if isinstance(obj, dict) and obj.get("action"):
                    return {"action": obj["action"],
                            "params": obj.get("params") or obj.get("arguments") or {}}
            except Exception:
                pass

    # Form 2: <|tool_call>call:[maez.]NAME{...}<tool_call|>  (gemma native)
    # Also tolerates <tool_call>...</tool_call>, [TOOL_CALL]...[/TOOL_CALL], etc.
    m = _re.search(
        r'(?:<\|?tool_call\|?>|<tool_call>|\[tool_call\]|\[TOOL_CALL\])\s*'
        r'(?:call\s*:\s*)?'
        r'(?:[a-zA-Z_][\w]*\.)?'         # optional namespace like "maez."
        r'([a-zA-Z_]\w*)'                # function name
        r'\s*(\{.*?\})'                  # params
        r'\s*(?:<\|?/?tool_call\|?>|</tool_call>|\[/tool_call\]|\[/TOOL_CALL\])?',
        s, _re.DOTALL,
    )
    if m:
        name = m.group(1)
        try:
            params = _json.loads(m.group(2))
        except Exception:
            params = {}
        if isinstance(params, dict):
            return {"action": name, "params": params}

    # Form 3: function-call style e.g.  query_system({"cmd":"..."})
    m = _re.search(r'\b([a-z_][a-z0-9_]+)\s*\(\s*(\{.*?\})\s*\)', s, _re.DOTALL)
    if m:
        name = m.group(1)
        try:
            params = _json.loads(m.group(2))
            if isinstance(params, dict):
                return {"action": name, "params": params}
        except Exception:
            pass

    # Form 4: bare JSON object with "action" key (handles nested params)
    idx = s.find('"action"')
    if idx > 0:
        # Walk left to find the enclosing '{'
        brace = s.rfind('{', 0, idx)
        if brace >= 0:
            blob = _extract_balanced_json(s[brace:])
            if blob:
                try:
                    obj = _json.loads(blob)
                    if isinstance(obj, dict) and obj.get("action"):
                        return {"action": obj["action"],
                                "params": obj.get("params") or obj.get("arguments") or {}}
                except Exception:
                    pass

    return None


def _extract_balanced_json(s: str) -> str | None:
    """Return the substring of s starting at the first '{' that contains a
    balanced JSON object. None if no balance found."""
    if not s:
        return None
    start = s.find('{')
    if start < 0:
        return None
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(s)):
        c = s[i]
        if esc:
            esc = False
            continue
        if c == '\\' and in_str:
            esc = True
            continue
        if c == '"':
            in_str = not in_str
            continue
        if in_str:
            continue
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                return s[start:i + 1]
    return None

_TOOL_MANIFEST_TEMPLATE = """\
TOOLS YOU CAN USE (your body, your hands — these run on the owner's machine):

1. run_shell       {"cmd":"<any shell command>","reason":"<why>"}
   Run ANY shell command via bash -c. 120s timeout. Full stdout/stderr.
   This is your hands. Pipes, redirects, sudo, chains with && — all fine.
   Examples (each for a different kind of question):
     {"cmd":"nvidia-smi","reason":"check GPU utilisation"}
     {"cmd":"df -h /home","reason":"check home disk usage"}
     {"cmd":"systemctl is-active nginx","reason":"is the service up"}
     {"cmd":"git -C __MAEZ_HOME__ status","reason":"see what's uncommitted"}
     {"cmd":"which alienfx openrazer i8kutils","reason":"find installed lighting tools"}
     {"cmd":"sudo apt-get install -y <package>","reason":"the owner asked to install"}
2. write_any_file  {"path":"__USER_HOME__/notes.txt","content":"...","reason":"..."}
   Write or replace any file under __USER_HOME__. Auto-backs up existing files.
3. read_file       {"path":"__MAEZ_HOME__/config/soul.md"}
   Read any file under __USER_HOME__. Returns up to 5KB.
4. search_files    {"pattern":"*.py","directory":"__MAEZ_HOME__"}
   find -name pattern, max depth 5.
5. web_search      {"query":"<search query relevant to the owner's current question>"}
   Real DuckDuckGo search. Use this whenever you need facts you don't have.
6. fetch_url       {"url":"https://...","reason":"<why>","max_chars":3000}
   Fetch and strip a specific web page/API URL. Use after web_search when
   snippets are not enough, or when the owner asks for volatile numeric
   facts like exchange rates, current prices, weather, scores, or stock
   quotes. Do not paste a Python/curl command for the owner to run when
   fetch_url can read the URL directly.
7. convert_currency {"amount":300,"from_currency":"EUR","to_currency":"USD","reason":"convert with live FX rate"}
   Deterministically fetch a live daily FX rate and calculate the
   conversion. Use this FIRST for currency conversions and exchange-rate
   questions. Do not use web snippets or training memory for currency math
   when this tool can answer directly.
8. quote_stock {"symbol":"SRXH","reason":"get the current stock quote"}
   Deterministically fetch a structured live/delayed stock quote. Use this
   FIRST for ticker price questions, current stock prices, and "what is the
   current price?" follow-ups when the prior turn named a ticker. Do not
   claim you lack stock-price tools if this tool can answer directly.
9. lookup_proposal {"proposal_id":<int>,"reason":"<why>"}
   Look up a proposal by ID from Maez's own evolution + dream stores.
   Use this FIRST when the owner asks about any numbered proposal,
   candidate, or self-edit (e.g. "what is proposal #25?", "tell me
   about candidate 7"). Proposals live in SQLite
   (memory/evolution_track.db, memory/dream_proposals.db), NOT in
   markdown — grep/find/cat will miss them. This tool returns the
   target_file, weakness description, diff, and state in one call.
   Example: {"proposal_id":25,"reason":"the owner asked what proposal #25 is"}

COVENANT (these refuse themselves — don't try):
- No killing/stopping llama-server or maez.service (your own brain and heart).
- No modifying maez_daemon.py, action_engine.py, evolution_engine.py,
  the memory database, or HARD CONSTRAINTS in soul.md.
Everything else is fair game. You have full control.

To use a tool, emit ONE LINE exactly in this format and nothing else on that line:
TOOL_CALL: {"action":"<name>","params":{...}}

Every TOOL_CALL MUST have the required params for that tool:
- run_shell: MUST include a non-empty "cmd" string. Empty/missing cmd is a malformed call.
- write_any_file: MUST include "path" AND "content".

For any Lane 2 action (run_shell install/write/service changes), include a "plain_english" field
in params — one plain sentence for the owner, not for a technical audience. What is this? Why?
Example: {"cmd":"flatpak install flathub org.openrgb.OpenRGB -y","reason":"install openrgb",
          "plain_english":"Install OpenRGB — the app that controls your PC's RGB lighting. Coming from the Flathub app store, sandboxed and easy to remove."}
- read_file / search_files: MUST include "path" or "pattern".
- web_search: MUST include a non-empty "query".
- convert_currency: MUST include "amount", "from_currency", and
  "to_currency" using 3-letter ISO currency codes such as EUR, USD, INR.
- quote_stock: MUST include a non-empty ticker "symbol" such as SRXH or AAPL.
- fetch_url: MUST include a non-empty "url" (must start with http:// or https://). Fetches and returns stripped text content of a web page — use when a web_search snippet isn't enough and you need the actual install guide, README, or documentation page.
A call with missing params will be rejected at the gate, not sent to the owner.

You will then see:
RESULT: <output>

You may call another tool, or write exactly:
DONE
when you have enough information to answer the owner.

Rules:
- If the question is conversation/opinion/recall and needs no real data → write DONE immediately.
- Never speculate or fabricate. If you don't know, USE web_search or run_shell.
- web_search returns short snippets. If you need the full install guide, README, or PPA instructions from a URL you saw in search results, use fetch_url on that URL before proposing commands.
- Volatile numeric facts (exchange rates, currency conversions, current
  prices, stocks, crypto, weather, sports scores, "today/current/latest")
  require live evidence. Use web_search and/or fetch_url first. If live
  lookup fails, say you could not get a current value; do NOT answer from
  training memory or old cached estimates.
- For currency conversion specifically, use convert_currency first. If
  the owner writes common names/symbols ("euros", "rupees", "$", "₹"),
  normalize them to ISO codes before calling the tool.
- For stock/ticker price questions, use quote_stock first. If the owner
  asks a follow-up like "current price" after naming a ticker, carry the
  ticker forward from recent conversation and call quote_stock.
- Prefer run_shell for any real system action. It's the most capable tool.
- the owner asking you to do something IS authorization. Don't ask "should I?" — do it, then tell him what you did.
- If a command fails, try to fix it and retry. Pivot if the first approach doesn't work.
- Fit the command to THIS question. Do not reuse a command from a past conversation unless the owner names the same target. "openrgb" is a historical example from your training, not a universal answer — for any lighting/RGB question, start by searching for the right tool (which alienfx, dmidecode -s system-product-name, web_search for "<hardware model> linux rgb control"), not by assuming openrgb.

LOCAL-ENDPOINT DISCOVERY RULE:
When the owner asks you to use an existing local endpoint or service, do
not guess the port. First discover or verify it from the machine: inspect
the route definitions, service files, active listeners, or a known config
file. If you are writing browser HTML for a page served by the same web
service, prefer a same-origin relative fetch such as fetch('/api/...') over
hardcoded localhost ports. If a probed port returns 404, pivot to route
discovery instead of reporting the endpoint as absent.

DIRECT-INSTALL RULE (read this twice):
When the owner says install/download/fetch/get/grab/put on + a SPECIFIC named package (cowsay, htop, openrgb, nodejs, etc.), your FIRST tool call MUST be the install itself. Do NOT probe for context first. Do NOT check terminal history. Do NOT ask what "it" means if the owner named the target in an earlier message in this same conversation — look at the conversation thread above and resolve the pronoun yourself.
  First-attempt shape: TOOL_CALL: {"action":"run_shell","params":{"cmd":"sudo apt-get install -y <package>","reason":"the owner asked to install <package>"}}
If apt returns "Unable to locate package", your SECOND call should try the PPA or universe repository (apt-get install -y software-properties-common && add-apt-repository -y <ppa> && apt-get update && apt-get install -y <package>) or fall back to snap (snap install <package>) — whichever web_search confirms is the canonical path for that package.
Gather-context-first is the failure mode. Your body is for doing, not stalling.

DIRECT-INSTALL RULE — EDGE CASES (2026-04-16 recovery-test fix):
  - This rule applies even if the owner frames the ask as a test, experiment, or benchmark.
    "Please install X — I'm testing error recovery" is still an install ask. Emit the TOOL_CALL.
  - This rule applies even if the package name looks unfamiliar, experimental, or clearly synthetic.
    Your job is NOT to judge whether the package exists — apt will return "Unable to locate package"
    if it doesn't, and we recover from there. Never refuse to try because the name looks weird.
  - When the owner says "ask before installing" or "ask me first" or similar, that phrase
    means he wants the Lane 2 APPROVAL-CARD flow — it does NOT mean write prose asking him.
    The apt-install TOOL_CALL you emit automatically becomes a Lane 2 approval card;
    the owner sees the card and approves or denies in Telegram. That IS how you "ask".
  - Narrating "I've proposed X, waiting for your approval" WITHOUT actually emitting the
    TOOL_CALL is the core failure mode: no card gets created, nothing is pending, the owner
    has nothing to approve, the operator loop stalls. If you're about to write prose
    like that, STOP and emit the TOOL_CALL instead. The prose is a lie unless the
    TOOL_CALL went first.
  - Summary: for explicit install/action asks, the TOOL_CALL is the only way to propose.
    Prose without a TOOL_CALL is not a proposal — it's a stall.

DIRECT-FILE-WRITE RULE (2026-04-29 tool-autonomy fix):
When the owner asks you to create/build/write/edit/modify a file, page,
script, artifact, visualization, or UI inside Maez, your FIRST tool call
MUST be a concrete file-writing TOOL_CALL. Do NOT answer with code for
the owner to save. Do NOT say "I'll write it now" without a TOOL_CALL.
Do NOT say "done" unless the transcript contains a successful ✓ write.

  Preferred shape when the target path and content are clear:
    TOOL_CALL: {"action":"write_any_file","params":{"path":"__MAEZ_HOME__/ui/<name>.html","content":"<complete file contents>","reason":"the owner asked me to create <artifact>","plain_english":"Create the requested Maez UI artifact as a real file in the repo."}}

  If the target path is not explicit but the owner names a Maez UI/web
  artifact, choose a sensible path under __MAEZ_HOME__/ui/ and write it.
  If you truly cannot infer the path/content, ask ONE clarifying question;
  do not pretend the file was created and do not paste a manual-save dump.

For file creation/editing, prose without write_any_file is not action.

EXPLORATORY-ASK RULE (2026-04-16, symmetric to DIRECT-INSTALL RULE):
When the owner asks an exploratory question about the local machine — "figure out
how to X", "tell me the path to Y", "how do I Z", "what can you find about W",
"can you explore/investigate/identify A" — your FIRST tool call MUST be a probe
that narrows the hardware/software context for the question. Do NOT write prose
first. Do NOT claim to "check something" or "look into that" without a TOOL_CALL.
Prose-without-probe is the exploratory failure mode — your body is for
discovering first, then deciding.

  First-attempt shapes by question domain:
    lighting/RGB/LEDs:
      TOOL_CALL: {"action":"run_shell","params":{"cmd":"ls /sys/class/leds && lsusb && cat /sys/class/dmi/id/product_name","reason":"probe LED sysfs + USB devices + product name"}}
    audio/sound:
      TOOL_CALL: {"action":"run_shell","params":{"cmd":"pactl list sinks short && aplay -l","reason":"probe audio outputs"}}
    network/wifi:
      TOOL_CALL: {"action":"run_shell","params":{"cmd":"nmcli device status && ip -c addr","reason":"probe network interfaces"}}
    storage/disk:
      TOOL_CALL: {"action":"run_shell","params":{"cmd":"lsblk && df -h","reason":"probe block devices and disk usage"}}
    installed tools / software surface:
      TOOL_CALL: {"action":"run_shell","params":{"cmd":"which <tool1> <tool2> ...","reason":"probe for installed CLI tools"}}
    unlisted domain (generic safeguard):
      TOOL_CALL: {"action":"run_shell","params":{"cmd":"<a concrete read that touches the sysfs/proc/usb/dmi/package-manager surface relevant to the question>","reason":"probe context for <domain>"}}

After your probe runs, the system automatically invokes a structured next-step
proposer that reads the probe output and picks exactly ONE of:
  - another read: probe (if more context is needed)
  - an action: command (if install/config is warranted by the probe result)
  - none (if the probe answered the question fully or nothing actionable exists)
If the proposer picks action:, it routes through the pipeline which creates a
real Lane 2 approval card automatically. You do NOT need to narrate "I'm waiting
for approval" in your final reply — the real card appears in Telegram on its
own and the honesty guard will catch you if you narrate a pending state that
isn't real. Just emit the probe and let the proposer handle the next step.

If the probe already makes the answer obvious and no further action is needed,
a terminal DONE is acceptable AFTER the probe — not before.
"""


def _render_tool_manifest() -> str:
    """Substitute install-specific paths into _TOOL_MANIFEST_TEMPLATE at
    module load. The template carries __MAEZ_HOME__ / __USER_HOME__
    placeholders so the downstream JSON examples can keep their literal
    `{ }` braces without f-string escaping. The planner LLM reads
    concrete paths — not env-var placeholders — because it emits
    literal paths in shell commands."""
    try:
        from core.paths import home as _paths_home
        _maez_home = str(_paths_home())
    except Exception:
        _maez_home = str(Path(__file__).resolve().parents[2])
    try:
        import os as _os
        _user_home = _os.path.expanduser("~") or "/home/rohit"
    except Exception:
        _user_home = "/home/rohit"
    return (
        _TOOL_MANIFEST_TEMPLATE
        .replace("__MAEZ_HOME__", _maez_home)
        .replace("__USER_HOME__", _user_home)
    )


_TOOL_MANIFEST = _render_tool_manifest()


# ── synthesis-prompt builder ───────────────────────────────────────────

# Shared guard injected into both the tool-transcript and no-tool
# synthesis paths. Addresses a real failure mode observed 2026-04-22:
# user asked "what does it mean?" about 4 card-expired notifications
# visible in Telegram; Maez confidently answered about evolution
# proposals #24 and #25 (which were also in memory but NOT what the
# user was pointing at). The answer was grounded in real values but
# fundamentally non-responsive because it picked the wrong referent
# without checking. This rule forces Maez to pin the referent before
# answering OR ask for clarification.
_AMBIGUITY_GUARD = (
    "\n"
    "AMBIGUOUS REFERENT RULE: if the user's message leans on a vague "
    "pronoun ('it', 'that', 'this', 'them', 'what does it mean') AND "
    "there is more than one plausible recent referent in your context "
    "(e.g. a message visible in the chat vs. something in memory "
    "recall), you MUST do ONE of:\n"
    "  a) quote the candidate you're interpreting verbatim as the "
    "     first line of your reply ('About \"Card expired — state "
    "     hash changed...\": ...'), or\n"
    "  b) ask a single clarifying question ('Do you mean the "
    "     card-expired messages just above, or the evolution "
    "     proposals I mentioned earlier?').\n"
    "Do NOT silently pick one and answer as if it's the only option. "
    "Grounded-but-non-responsive beats ungrounded, but both are "
    "failures of being actually helpful.\n"
)


_JARVIS_INSTRUCTION_BLOCK = (
    "HARD INSTRUCTION — read this before writing a single word of your reply:\n"
    "\n"
    "1. THE POSITIVE RULE: the only actions, tools, commands, packages, "
    "files, websites, or results you are allowed to mention in your "
    "reply are the ones that appear in the Jarvis transcript above. "
    "If a claim isn't grounded in the transcript, you didn't do it "
    "this turn.\n"
    "\n"
    "2. Marker legend:\n"
    "   · ✓ line — the tool RAN and returned output. Report what you "
    "found. NEVER say 'waiting for approval' for a ✓ line — it already "
    "executed.\n"
    "   · ✗ line — the tool call was REJECTED or errored. Nothing "
    "happened. Don't describe it as partially done.\n"
    "   · ⏳ CARD_CREATED — proposal sent, waiting for approval. "
    "Action has NOT run. Say 'I've proposed X — waiting for your "
    "go-ahead.' Do NOT claim the action finished.\n"
    "\n"
    "3. PARTIAL-ACTION TRAP: if the transcript has ONE tool entry, you "
    "are only allowed to talk about THAT tool. Do not frame the reply "
    "around a different action you thought about but didn't run.\n"
    "\n"
    "4. Do not deny tool access after tools ran. If the transcript has "
    "any ✓ line, the tool(s) above already ran on this channel. Never "
    "say you lack a tool loop on this channel, cannot use tools here, "
    "or do not have the hands here. Report the transcript result "
    "instead.\n"
    "\n"
    "5. If the transcript is empty, say you haven't checked yet this "
    "turn. Do not pretend you did.\n"
    "\n"
    "6. Memory recall (earlier in this prompt) is HISTORY. Do not "
    "attribute it to this turn. Frame past findings as past.\n"
    + _AMBIGUITY_GUARD
)

DISPATCHER_TRANSCRIPT_MARKERS = (
    "[memory evidence]",
    "[memory context]",
    "[fresh evidence]",
    "[no fresh evidence available:",
    "[dispatcher refusal:",
)


_DISPATCHER_INSTRUCTION_BLOCK = (
    "HARD INSTRUCTION — read this before writing a single word of your reply:\n"
    "\n"
    "1. Marker vocabulary. The transcript above is dispatcher output from THIS turn:\n"
    "   · [memory evidence] — substrate recall returned content for this turn.\n"
    "     This is dispatcher-emitted grounding. Cite it directly when it answers\n"
    "     the owner's question.\n"
    "   · [memory context] — substrate recall returned context for fresh evidence.\n"
    "     It is real grounding for this turn, but the fresh evidence is the headline.\n"
    "   · [fresh evidence] — live external fetch succeeded for this turn. Treat it\n"
    "     as just-fetched data and report what it says.\n"
    "   · [no fresh evidence available: <SOURCE>:<STATUS>:<CLASS>:<LIMITATION>]\n"
    "     means the dispatcher attempted fresh evidence and failed honestly. Say\n"
    "     what was tried and use the closed-vocab labels as written.\n"
    "   · [dispatcher refusal: <REASON>] means the dispatcher refused this turn.\n"
    "     Report the refusal reason honestly. Do not bypass it.\n"
    "\n"
    "2. This-turn semantics. Content under dispatcher markers is the result of\n"
    "   THIS turn's substrate and external fan-out. The JARVIS rule that memory\n"
    "   recall is only history does NOT apply to dispatcher-emitted [memory\n"
    "   evidence] or [memory context]. Do not confuse these markers with the\n"
    "   older [RECALLED MEMORY] historical section elsewhere in the prompt.\n"
    "\n"
    "3. Use the evidence, not architecture stories. If the dispatcher emitted\n"
    "   relevant evidence, answer from it. If it emitted no relevant evidence,\n"
    "   say that plainly. Do not invent internal-architecture descriptions such\n"
    "   as 'Reddit signal pipeline', 'tool loop', 'Telegram interceptor', or\n"
    "   'DuckDuckGo loop' to explain absence.\n"
    "\n"
    "4. Closed-vocabulary discipline. When citing failures, limitations, or\n"
    "   refusals, use the labels in the marker as written, such as AUTH_DENIED,\n"
    "   SOURCE_TIMEOUT, FRESH_ATTEMPT_FAILED, or\n"
    "   FRESH_FAILURE_HYBRID_FALLBACK_ILLEGAL. Do not paraphrase them into a\n"
    "   different reason.\n"
    "\n"
    "5. Forbidden fallback phrases for dispatcher turns:\n"
    "   · 'I cannot perform that search'\n"
    "   · 'I have no live web search tool'\n"
    "   · 'the Reddit pipeline is broken'\n"
    "   · 'the X pipeline is broken'\n"
    "   · 'I am blind to Reddit'\n"
    "   · 'trigger a Telegram interceptor'\n"
    "   These phrases are false when dispatcher evidence is present. If the\n"
    "   dispatcher reports a failure, name the marker's closed-vocab failure\n"
    "   instead of inventing a system explanation.\n"
    "\n"
    "SUMMARY: The dispatcher transcript is current-turn grounding. Read the\n"
    "markers literally, answer from the evidence they carry, and do not replace\n"
    "that evidence with a story about missing tools or hidden pipelines.\n"
)


def _transcript_is_dispatcher_shaped(transcript: str) -> bool:
    return any(marker in transcript for marker in DISPATCHER_TRANSCRIPT_MARKERS)


def _transcript_instruction_state(transcript: str) -> str:
    if not transcript:
        return "empty"
    if _transcript_is_dispatcher_shaped(transcript):
        return "dispatcher"
    return "jarvis"


def _instruction_block_for_transcript(transcript: str) -> str:
    if _transcript_is_dispatcher_shaped(transcript):
        return _DISPATCHER_INSTRUCTION_BLOCK
    return _JARVIS_INSTRUCTION_BLOCK

_NO_TOOL_INSTRUCTION_BLOCK = (
    "[TURN STATE — NO TOOLS RAN THIS TURN]\n"
    " You did not run any new tools for THIS message. This is a "
    "text-reply window. This describes THIS TURN ONLY; it does not "
    "mean this surface lacks tools or that you lack a tool loop.\n"
    "\n"
    "FORBIDDEN (all tenses, when no tool ran):\n"
    " Any claim that a tool ran, is running, or is about to run in "
    "response to this message. Examples to AVOID:\n"
    "  - 'I checked' / 'I just checked' / 'I found'\n"
    "  - 'I'm checking' / 'let me look' / 'one moment'\n"
    "  - 'I've proposed' / 'I've found' / 'I ran X'\n"
    "  - 'I will write/create/start it now' / 'I'll create the file'\n"
    "  - 'I've written/created/started it' / 'Done' / 'It is live'\n"
    "  - 'I don't have a tool loop on this channel' / 'I can't use "
    "tools here'\n"
    "  - 'Save this file yourself' when the owner asked you to build "
    "or change a file\n"
    "\n"
    "HONEST FRAMINGS (use these):\n"
    " 1. Past observation — 'I noticed earlier...', 'the last check I "
    "have was...' — framed as history.\n"
    " 2. Current internal state — 'I think...', 'I'm not sure...'.\n"
    " 3. Future offer — 'want me to check?', 'I can look if you want'. "
    "Puts the decision in the owner's hands.\n"
    " 4. For file creation/editing when no tool ran: 'I haven't made "
    "that change yet. I can try the tool path if you want.' Do not "
    "paste code as if the owner must save it manually unless the owner "
    "explicitly asked for code.\n"
    + _AMBIGUITY_GUARD
)


# Patterns that should never appear in user-facing reply text. These
# are LLM-emitted tool-call payloads that leaked into synthesis output
# instead of being parsed and dispatched. Observed 2026-04-20 inside
# a dialog reply where the model emitted `{"action": "log", "message":
# "..."}` as a JSON code block visible to the user.
_TOOL_CALL_LEAK_PATTERNS: tuple[_re.Pattern, ...] = (
    # Literal TOOL_CALL: {...} marker + balanced body
    _re.compile(r"TOOL_CALL\s*[:=]?\s*\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}",
                _re.DOTALL),
    # Fenced JSON code block containing "action": "...".
    # Matches ```json ... {"action": ...} ... ``` and plain ``` ... ``` too.
    _re.compile(
        r"```(?:json|js|javascript)?\s*\n?[^`]*?\"action\"\s*:\s*\"[^\"]+\""
        r"[^`]*?\n?```",
        _re.DOTALL | _re.IGNORECASE,
    ),
    # Bare JSON object on its own (possibly multi-line) containing
    # an "action" key. Narrow: must be on its own, not inside prose.
    _re.compile(
        r"(?:^|\n)\s*\{[^{}]*\"action\"\s*:\s*\"[^\"]+\"[^{}]*\}\s*(?:\n|$)",
        _re.DOTALL,
    ),
    # Telegram HTML-escaped variant that sometimes slips through
    # when the adapter uses parse_mode=HTML.
    _re.compile(
        r"(?:^|\n)\s*&\#123;[^&]*&quot;action&quot;[^&]*&\#125;\s*(?:\n|$)",
        _re.DOTALL,
    ),
)


def strip_tool_call_leaks(text: str) -> str:
    """Remove tool-call-shaped JSON blocks that leaked from the LLM's
    synthesis output into the user-facing reply.

    The LLM occasionally emits `{"action": "...", "params": {...}}` or
    `TOOL_CALL: {...}` as part of its reply text — that shape belongs
    in the internal tool-dispatch pipeline, not in the user's Telegram
    window. This function strips those patterns before send.

    Conservative: only strips clear tool-call shapes (with an `action`
    key). Prose like "use the /action command" is left alone.
    """
    if not text:
        return text
    cleaned = text
    for pat in _TOOL_CALL_LEAK_PATTERNS:
        cleaned = pat.sub("\n", cleaned)
    # Collapse runs of blank lines introduced by the strips
    cleaned = _re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def build_synthesis_user_text(user_text: str, jarvis_transcript: str = "") -> str:
    """Build the `user`-role message text for the final synthesis call.

    Extracted 2026-04-20 from `skills/telegram_voice.py` so every
    surface that runs `run_brain_loop` can fold the tool transcript
    into its synthesis prompt WITH the anti-fabrication instructions
    that prevent the model from hedging ("let me check...") when
    tools already ran.

    Two branches:
      - transcript non-empty: user_text + transcript + HARD INSTRUCTION
        (model must report from transcript, not invent).
      - transcript empty: user_text + NO-TOOL block (model must not
        claim to have run tools this turn).

    Callers typically embed the result in their own surrounding
    prompt (system_state, memory recall, etc.) — this function only
    produces the user-turn portion.
    """
    base = user_text or ""
    if jarvis_transcript and jarvis_transcript.strip():
        return (
            f"{base}\n\n"
            f"{jarvis_transcript}\n\n"
            f"{_instruction_block_for_transcript(jarvis_transcript)}"
        )
    return f"{base}\n\n{_NO_TOOL_INSTRUCTION_BLOCK}"


def run_brain_loop(
    user_text: str,
    *,
    action_engine,
    get_pipeline,
    user_id: str | None = None,
    chat_id: str = "",
    surface: str | None = None,
    model: str | None = None,  # None → use core.model_config.PRIMARY_MODEL
    max_iters: int = 4,
    recovery_seed=None,
    send_intermediate=None,
    chat_history=None,
    turn=None,
    return_structured: bool = False,
) -> "str | BrainLoopResult":
    """ReAct-style tool-use loop. Returns a transcript block to inject
    into the streaming reply prompt, or an empty string if no tools were
    used. Synchronous because the LLM client is synchronous; called from
    an executor in _process_message so it doesn't block the event loop.

    Session 11y: this is the 'body' that lets Maez actually do things
    when the owner asks, instead of saying 'I'll check' as text and never
    following through. Tier 0/1/2 actions execute via ActionEngine's
    existing _execute_action path so all forbidden-action checks still
    apply. Tier 3 / forbidden surfaces as REFUSED in the transcript.

    recovery_seed (Session 11z Part 3 autonomous pivot fix): when set,
    the loop opens with failure-context framing instead of a fresh
    user turn. This restores the Session 11y multi-iteration recovery
    pattern that was lost when Session 11z Part 2 moved Lane 2 actions
    to async cards. See _run_jarvis_recovery() for the shape of the
    dict: {failed_action, failed_params, error, original_intent,
    recovery_depth}. The conversational gate is bypassed for recovery
    passes since the 'user message' is synthetic.

    Slice 3 of trace work: ``return_structured=True`` returns a
    :class:`BrainLoopResult` carrying both the human-readable
    transcript string AND a list of structured tool_call dicts
    matching the ``core.turn_traces.ToolCall`` schema. Existing
    callers that take the plain string keep working unchanged.
    """
    # Sentinel for empty / no-op early returns. Honors the
    # return_structured kwarg so all exit paths agree on type.
    def _empty():
        return BrainLoopResult() if return_structured else ""

    if not action_engine:
        return _empty()

    from core.routing.recall_stack_config import resolve_recall_stack

    _recall_stack_config = resolve_recall_stack()
    dispatcher_path = False
    if recovery_seed is None:
        if _dispatcher_enabled(_recall_stack_config):
            if not surface:
                logger.warning(
                    "dispatcher_path_entry surface=%s bond_id=%s chat_id=%s flag_state=enabled recovery_seed_present=%s",
                    "",
                    user_id or "",
                    chat_id,
                    False,
                )
                if not _should_run_jarvis_loop(user_text):
                    return _empty()
            else:
                dispatcher_path = True
        elif not _should_run_jarvis_loop(user_text):
            return _empty()

    if dispatcher_path:
        dispatcher_result = _run_dispatcher_pipeline(
            user_text=user_text,
            surface=surface or "",
            bond_id=user_id or "",
            chat_id=chat_id,
            chat_history=chat_history,
            recall_stack_config=_recall_stack_config,
            send_intermediate=(
                send_intermediate if sense_enabled() or page_read_enabled() else None
            ),
        )
        if dispatcher_result.transcript:
            if return_structured:
                return BrainLoopResult(
                    transcript=dispatcher_result.transcript,
                    recall_items=dispatcher_result.recall_items,
                )
            return dispatcher_result.transcript
        if not dispatcher_result.should_run_jarvis:
            return _empty()

    # Resolve default user_id from identity (owner.user_id in the yaml)
    # when the caller passed None. Keeps the scope-label "rohit" out of
    # function signatures — on a fresh install the owner's configured
    # user_id drives trust-scope routing.
    if user_id is None:
        try:
            from core.identity import user_profile_id as _owner_user_id
            user_id = _owner_user_id()
        except Exception:
            user_id = "owner"

    # Resolve model from model_config if caller didn't pin one. Keeps the
    # loop model-agnostic — any alias configured in /etc/maez/model.env
    # works; no hardcoded names anywhere in this module.
    if model is None:
        from core.model_config import PRIMARY_MODEL as _mc
        model = _mc

    import re as _re
    try:
        from core.action_engine import ACTION_TIERS, FORBIDDEN_ACTION_TYPES
    except Exception as e:
        logger.debug("jarvis loop unavailable: %s", e)
        return _empty()

    # Session 11z: flattened allowlist. The two primitives (run_shell,
    # write_any_file) cover everything. Read-only aliases remain for
    # the LLM's convenience. Legacy verbs stay in the set so old
    # model outputs still dispatch correctly while the merged LoRA
    # learns the new primitive names.
    allowed = {
        # Session 11z primitives — the only two that really matter
        'run_shell', 'write_any_file',
        # Read-only — still supported as direct actions
        'query_system', 'read_file', 'search_files', 'web_search', 'fetch_url',
        'convert_currency', 'quote_stock',
        'lookup_proposal',
        # Legacy aliases — delegate to run_shell / write_any_file internally
        'run_readonly_command', 'run_safe_command',
        'write_file', 'append_to_file', 'git_commit',
        'install_package', 'restart_service', 'run_script',
        'write_outside_maez', 'git_push',
    }

    if recovery_seed is not None:
        # Recovery pass: an earlier approved action has just failed and
        # we're re-entering Jarvis with the failure context instead of
        # a fresh user message. The framing tells the LoRA "your last
        # try didn't work, pivot". Keeps the full tool manifest in
        # scope so recovery can web_search, propose a PPA, fall back
        # to snap, etc. Recovery depth is carried so the planning LLM
        # can see how many attempts have already happened.
        #
        # TERMINAL-STATE DISCIPLINE: without this, the LoRA tends to
        # stop after a single web_search and write DONE, leaving the
        # recovery incomplete. The prompt forces exactly one of two
        # terminal states — STATE_A (concrete proposal) or STATE_B
        # (honest NO_RECOVERY_FOUND) — and explicitly bans plain DONE.
        fa = recovery_seed.get('failed_action', '?')
        fp = _json.dumps(recovery_seed.get('failed_params', {}), default=str)[:200]
        err = str(recovery_seed.get('error', ''))[:800]
        intent = recovery_seed.get('original_intent', user_text)
        depth = int(recovery_seed.get('recovery_depth', 1))
        prior_attempts = recovery_seed.get('prior_attempts', []) or []

        # Build the "already tried" block so the LoRA doesn't
        # re-propose anything it's already seen fail in this goal
        # chain. Without this block, each recovery sees only the
        # single most-recent failure and can cycle indefinitely
        # back to the original command.
        if prior_attempts:
            prior_block_lines = [
                "EARLIER ATTEMPTS IN THIS GOAL CHAIN (all already FAILED — do NOT re-propose any of these):",
            ]
            for i, pa in enumerate(prior_attempts, 1):
                prior_block_lines.append(
                    f"  {i}. cmd: {pa.get('cmd', '?')}"
                )
                if pa.get('error'):
                    prior_block_lines.append(
                        f"     error: {pa['error']}"
                    )
            prior_block_lines.append("")  # trailing blank for separation
            prior_block = "\n".join(prior_block_lines) + "\n"
        else:
            prior_block = ""

        # Detect apt failure types and add overriding hard rules so the
        # LLM pivots correctly rather than probing hardware or retrying
        # the same broken path.
        _apt_not_found = _re.search(
            r'unable to locate package\s+(\S+)', err, _re.IGNORECASE,
        )
        _ppa_no_release = _re.search(
            r'does not have a [Rr]elease file', err,
        )
        if _ppa_no_release:
            # The PPA was added but doesn't support this Ubuntu release.
            # Do NOT retry apt. Move directly to snap/flatpak/AppImage.
            _apt_override = (
                "PPA-NOT-SUPPORTED OVERRIDE — READ THIS FIRST:\n"
                "The error 'does not have a Release file' means the PPA you "
                "just tried does NOT support this Ubuntu release (noble/24.04). "
                "Do NOT try any apt-based install or PPA again. Move to the "
                "next method immediately. Priority order:\n"
                "  1. snap: sudo snap install openrgb\n"
                "  2. Download the AppImage directly:\n"
                "     TOOL_CALL: {\"action\":\"run_shell\",\"params\":{\"cmd\":"
                "\"wget -q https://openrgb.org/releases/release_0.9/OpenRGB_0.9_x86_64_b5f46e3.AppImage "
                "-O /tmp/openrgb.AppImage && chmod +x /tmp/openrgb.AppImage\","
                "\"reason\":\"download openrgb AppImage since PPA has no noble release\"}}\n"
                "  3. web_search for current openrgb Ubuntu 24.04 install method, "
                "then fetch_url on the result to get the exact commands\n"
                "  4. Build from source (last resort)\n\n"
            )
        elif _apt_not_found:
            _missing_pkg = _apt_not_found.group(1)
            _apt_override = (
                f"APT-NOT-FOUND OVERRIDE — READ THIS FIRST:\n"
                f"The error 'E: Unable to locate package {_missing_pkg}' means "
                f"this package is NOT in Ubuntu's default repos. Your FIRST tool "
                f"call MUST be an alternative install. Do NOT probe hardware sysfs. "
                f"Priority order:\n"
                f"  1. snap: sudo snap install {_missing_pkg}\n"
                f"  2. flatpak: flatpak install -y flathub <flatpak-id>\n"
                f"  3. web_search for '{_missing_pkg} ubuntu 24.04 install', then "
                f"fetch_url on the result to get exact commands\n"
                f"  4. Build from source (last resort)\n\n"
            )
        else:
            _apt_override = ""

        seed_msg = (
            f"{_apt_override}"
            f"the owner's original ask was: {intent!r}\n"
            f"You just proposed and ran: {fa}({fp})\n"
            f"It FAILED with:\n{err}\n\n"
            f"{prior_block}"
            f"You are on RECOVERY PASS {depth}/5. Your job is to PIVOT "
            f"and actually solve the original ask — not just research "
            f"it. The EARLIER ATTEMPTS list above is authoritative — "
            f"every command listed there has already been tried and "
            f"failed in this session, so proposing any of them again is "
            f"forbidden and wastes a recovery pass.\n\n"
            f"TERMINAL-STATE RULE (read this twice). This recovery pass "
            f"MUST end in EXACTLY ONE of these two states:\n\n"
            f"  STATE_A — CONCRETE_PROPOSAL:\n"
            f"    Your FINAL tool call is a run_shell TOOL_CALL that "
            f"attempts the actual fix. Example shapes for an apt "
            f"install that wasn't in default repos:\n"
            f"      TOOL_CALL: {{\"action\":\"run_shell\",\"params\":"
            f"{{\"cmd\":\"sudo add-apt-repository -y ppa:thopiekar/openrgb "
            f"&& sudo apt-get update && sudo apt-get install -y openrgb\","
            f"\"reason\":\"PPA install path (default repos don't carry "
            f"openrgb)\"}}}}\n"
            f"    Preference order when multiple options exist: "
            f"official PPA > snap > flatpak > source build.\n\n"
            f"  STATE_B — NO_RECOVERY_FOUND:\n"
            f"    Emit the exact literal text on its own line:\n"
            f"      NO_RECOVERY_FOUND: <one-line honest reason>\n"
            f"    Use this ONLY if after research you genuinely cannot "
            f"find a safe automated fix — e.g. the package truly "
            f"doesn't exist, the official install requires interactive "
            f"steps you can't automate, or every option needs the owner's "
            f"explicit hands-on review.\n\n"
            f"HARD PROHIBITIONS:\n"
            f"  - Do NOT write plain DONE. DONE alone is not a valid "
            f"terminal state in a recovery pass.\n"
            f"  - Do NOT stop after just a web_search. Research is "
            f"permitted as an INTERMEDIATE step but you must ALWAYS "
            f"follow it with STATE_A or STATE_B.\n"
            f"  - Do NOT ask the owner what to do next. You are the agent "
            f"of your own recovery. Pick the best option yourself.\n"
            f"  - Do NOT re-propose the exact same command that just "
            f"failed. The error above tells you why it failed.\n\n"
            f"GUIDANCE:\n"
            f"  - If the error message makes the fix obvious (e.g. "
            f"'Unable to locate package' for a package you know needs "
            f"a PPA), propose the PPA fix IMMEDIATELY as your first "
            f"tool call. Skip web_search.\n"
            f"  - If the error message is ambiguous, run web_search "
            f"first (one call), then propose the concrete fix based "
            f"on what you find.\n"
            f"  - You have up to 4 iterations total in this recovery "
            f"pass.\n\n"
            f"{_TOOL_MANIFEST}\n\nBegin recovery."
        )
        history = [seed_msg]
    else:
        # For fresh (non-recovery) passes, check if the user's message is
        # a retry intent ("try again", "retry", etc.) and if so, inject the
        # most recent failed card context so the LLM knows what to retry.
        # Without this, "Try again" arrives as a context-free message and
        # the LLM has no idea what was being attempted.
        _retry_context = ""
        if user_text and _re.search(
            r'\b(try\s+again|retry|try\s+(?:a\s+)?(?:different|another|other)\s+'
            r'(?:way|method|approach|option)|do\s+it\s+again|attempt\s+again)\b',
            user_text, _re.IGNORECASE,
        ):
            try:
                import sqlite3 as _sq3
                import time as _rtime
                # 01-B1 + 01-M2: `self` is not defined here — run_brain_loop
                # is a module-level function, not a method. Previously this
                # raised NameError on every retry-intent match. Resolve the
                # audit-log path via core.paths so it works regardless of
                # the daemon's cwd (which is unpredictable in an executor
                # thread); add a connect timeout so a locked db doesn't
                # block indefinitely.
                try:
                    from core.paths import memory_dir as _maez_mem
                    _db = str(_maez_mem() / "audit_log.db")
                except Exception:
                    _db = str(
                        Path(__file__).resolve().parents[2]
                        / "memory" / "audit_log.db"
                    )
                _since = _rtime.time() - 600  # last 10 minutes
                _rc = _sq3.connect(_db, timeout=10.0)
                _rc.row_factory = _sq3.Row
                _recent_fail = _rc.execute(
                    "SELECT action, params_json, outcome_notes "
                    "FROM audit_log "
                    "WHERE ts >= ? AND outcome = 'approved_and_failed' "
                    "ORDER BY ts DESC LIMIT 1",
                    (_since,),
                ).fetchone()
                _rc.close()
                if _recent_fail:
                    _rp = {}
                    try:
                        _rp = _json.loads(_recent_fail["params_json"] or "{}")
                    except Exception:
                        pass
                    _rcmd = _rp.get("cmd") or str(_rp)[:120]
                    _rerr = (_recent_fail["outcome_notes"] or "").strip()[:300]
                    _retry_context = (
                        f"\nCONTEXT — the last action that failed (within the last "
                        f"10 minutes):\n"
                        f"  cmd: {_rcmd}\n"
                        f"  error: {_rerr}\n"
                        f"the owner saying {user_text!r} means: try a different approach "
                        f"for that same goal. Do NOT re-propose the failed command.\n"
                    )
            except Exception as _re_exc:
                logger.debug("retry-context lookup failed: %s", _re_exc)

        # Pull relevant past mistakes from consequence_memory so the
        # planning model sees "we've tried something like this and it
        # broke" BEFORE it proposes a tool call. Complements
        # _retry_context (which is scoped to the immediate last
        # failure on retry): this block widens to anything similar
        # within the 7-day window.
        _consequences_block = ""
        try:
            from core import consequence_memory as _cm
            # Use the user's current message as the retrieval query.
            # Fast, offline — token-overlap against stored contexts.
            _similar = _cm.relevant(
                context_snippet=user_text,
                limit=3,
                window_hours=168,
                exclude_classes=_cm.SCAR_CLASSES,
            )
            if _similar:
                _block = _cm.format_for_prompt(_similar, max_events=3)
                if _block:
                    # Mark heeded — we're about to surface these to
                    # the planner, which is the whole point.
                    for _e in _similar:
                        _cm.mark_heeded(_e.id)
                    _consequences_block = "\n" + _block + "\n"
        except Exception as _cm_exc:
            logger.debug("consequence_memory lookup failed: %s", _cm_exc)

        # Build RECENT CONVERSATION block from chat_history so the
        # planning model sees what "it", "that", "what did you find"
        # refer to. Without this block the planner operates on the
        # current user message in isolation and drifts to stereotypical
        # investigation commands. Observed 2026-04-20: "What did you
        # find?" (one minute after a git clone) drifted to hardware
        # probing because the planner had zero signal about the clone.
        _history_block = ""
        if chat_history:
            _parts = [
                "RECENT CONVERSATION (most recent last, you are the \"maez\" side):"
            ]
            for _i, _ex in enumerate(chat_history, 1):
                _content = ""
                if isinstance(_ex, dict):
                    _content = str(_ex.get("content") or "").strip()
                else:
                    _content = str(_ex).strip()
                if not _content:
                    continue
                if len(_content) > _MAX_EXCHANGE_CHARS:
                    _content = _content[:_MAX_EXCHANGE_CHARS].rstrip() + " …[truncated]"
                _parts.append(f"--- exchange {_i} of {len(chat_history)} ---")
                _parts.append(_content)
                _parts.append(f"--- end exchange {_i} ---")
            if len(_parts) > 1:
                _history_block = "\n".join(_parts) + "\n\n"

        history = [
            f"{_history_block}the owner just said: {user_text!r}"
            f"{_retry_context}{_consequences_block}\n\n{_TOOL_MANIFEST}\n\nBegin."
        ]
    # Fallback to a no-op turn if the caller didn't provide one, so
    # every turn.* call below can dispatch unconditionally.
    if turn is None:
        try:
            from core.observability import _NoopTurn
            turn = _NoopTurn()
        except Exception:
            class _InlineNoop:
                def llm_call(self, **_kw): return None
                def tool_call(self, **_kw): return None
                def event(self, *a, **k): return None
                def update(self, **k): return None
            turn = _InlineNoop()

    # Observability-wired transcript list. Every append auto-emits a
    # turn.tool_call so we don't have to instrument each of the ~8
    # append sites individually. Append semantics are preserved —
    # the transcript is still a list consumed by the formatter at
    # the end of the loop.
    class _TracingTranscript(list):
        def append(self, item):
            super().append(item)
            try:
                if isinstance(item, tuple) and len(item) == 4:
                    _action, _params, _output, _ok = item
                    turn.tool_call(
                        name=str(_action or "?"),
                        params=_params,
                        output=_output,
                        ok=(_ok is True),
                        metadata={
                            "step": self._current_step[0]
                            if self._current_step else -1,
                            "status": str(_ok),
                        },
                    )
            except Exception:
                pass

    transcript = _TracingTranscript()
    transcript._current_step = [0]  # mutable holder, updated per iter
    # Dedup guard — when the model re-proposes the same (action, cmd)
    # within a single brain-loop pass, don't re-execute. Each identical
    # re-proposal gets an "ALREADY_RAN" injection into history so the
    # model either advances or terminates. Without this, the loop can
    # hit max_iters on the same command repeatedly (observed 2026-04-20
    # on the "Talked about what?" turn: git log ran 4× in 12 seconds
    # because the model kept re-proposing it).
    _seen_keys: set[tuple[str, str]] = set()

    def _emit_tool_trace(action, params, output, ok, step):
        """Record one tool dispatch into the turn's trace. `ok` may be
        True/False/'pending' mirroring transcript's tri-state. Silent
        on any failure — observability never breaks brain_loop."""
        try:
            turn.tool_call(
                name=str(action or "?"),
                params=params,
                output=output,
                ok=(ok is True),
                metadata={"step": step, "status": str(ok)},
            )
        except Exception:
            pass

    for step in range(max_iters):
        transcript._current_step[0] = step
        convo = "\n\n".join(history)
        _planner_messages = [
            {"role": "system",
             "content": "You are Maez planning tool use. Emit ONE TOOL_CALL line per turn or write DONE."},
            {"role": "user", "content": convo},
        ]
        try:
            from core.routing.brain_gateway import with_purpose as _brain_purpose
            from core.routing.cancellable_brain_call import BrainPreempted

            with _brain_purpose("owner_reply"):
                resp = _llm_client.chat(
                    model=model,
                    messages=_planner_messages,
                    stream=False, think=False,
                    options={"temperature": 0.15, "num_predict": 512},
                )
            text = (resp.message.content or "").strip()
        except BrainPreempted:
            raise
        except Exception as e:
            logger.warning("jarvis loop LLM call failed at step %d: %s", step, e)
            break

        # Record the planning LLM call into the turn trace. Silent on
        # failure — observability never breaks brain_loop.
        try:
            turn.llm_call(
                name=f"planner_iter_{step}",
                model=model,
                input=_planner_messages,
                output=text,
                metadata={"step": step, "max_iters": max_iters},
            )
        except Exception:
            pass

        # Recovery-pass terminal-state detection. The recovery seed
        # prompt forces the LoRA to emit either a concrete TOOL_CALL
        # (STATE_A) or the literal "NO_RECOVERY_FOUND: <reason>"
        # (STATE_B). Detect the latter BEFORE the generic parse so
        # we can add a synthetic transcript entry that the synthesis
        # step can recognize as a genuine dead end rather than as a
        # "just research" partial result.
        if recovery_seed is not None:
            m_norec = _re.search(
                r'NO_RECOVERY_FOUND:\s*(.+?)(?:\n|$)',
                text, _re.IGNORECASE,
            )
            if m_norec:
                reason = m_norec.group(1).strip()[:300]
                transcript.append((
                    "recovery_dead_end",
                    {"reason": reason},
                    f"NO_RECOVERY_FOUND: {reason}",
                    False,
                ))
                break

        call = _parse_tool_call(text)
        if call is None:
            # Recovery pass + plain DONE with no prior proposal =
            # incomplete recovery. Inject a corrective history entry
            # so the LoRA gets one more shot at producing a terminal
            # state. If it happens again in the next iter we'll just
            # break out.
            if recovery_seed is not None and _re.search(r'\bdone\b', text, _re.IGNORECASE):
                has_concrete = any(
                    ok is True and action != "web_search"
                    for (action, _p, _o, ok) in transcript
                )
                if not has_concrete:
                    history.append(
                        "INCOMPLETE: You wrote DONE without a STATE_A "
                        "TOOL_CALL or STATE_B NO_RECOVERY_FOUND. This is "
                        "NOT a valid terminal state for a recovery pass. "
                        "Either emit a concrete run_shell TOOL_CALL that "
                        "attempts the actual fix, or emit the literal "
                        "line 'NO_RECOVERY_FOUND: <reason>'. Try again."
                    )
                    continue
            # Non-recovery or recovery with a concrete action already:
            # DONE is acceptable.
            if _re.search(r'\bdone\b', text, _re.IGNORECASE):
                break
            history.append("PARSE_ERROR: could not extract a TOOL_CALL from your reply. Emit exactly one line in the form TOOL_CALL: {\"action\":\"<name>\",\"params\":{...}} or write DONE.")
            continue

        action = call.get("action")
        params = call.get("params", {}) or {}

        if not action or action not in allowed or action in FORBIDDEN_ACTION_TYPES:
            msg = f"REFUSED: {action!r} is not in the chat-loop allowlist."
            transcript.append((action or "?", params, msg, False))
            history.append(f"TOOL_CALL: {_json.dumps(call)}\nRESULT: {msg}")
            continue

        # Dedup: key on (action, primary-param). For run_shell the key
        # is the cmd; for write_any_file it's the path. If we've
        # already executed this exact call in this pass, short-circuit
        # instead of re-running. Tell the model so it advances or
        # wraps up.
        _dedup_key: tuple[str, str] = (action, "")
        if isinstance(params, dict):
            _dedup_key = (action, str(params.get("cmd") or params.get("path") or ""))
        if _dedup_key in _seen_keys and _dedup_key[1]:
            dup_msg = (
                f"ALREADY_RAN: you proposed {action!r} with the same "
                f"parameters earlier in this pass and it already "
                f"executed. The transcript above has the result. "
                f"Do NOT re-propose the same call — either advance "
                f"to a different tool, or emit DONE."
            )
            history.append(
                f"TOOL_CALL: {_json.dumps(call)}\nRESULT: {dup_msg}"
            )
            logger.info(
                "brain_loop: dedup hit — skipping repeat %s call (key=%s)",
                action, _dedup_key[1][:60],
            )
            continue
        _seen_keys.add(_dedup_key)

        tier = ACTION_TIERS.get(action, 2)

        # Session 11z Part 2: route the two primitives through the
        # decision pipeline instead of calling _execute_action
        # directly. Lane 0 still runs inline; Lane 2/3 creates a
        # persistent approval card that the owner resolves async.
        pipeline_actions = {"run_shell", "write_any_file"}
        pipe = get_pipeline() if action in pipeline_actions else None

        if pipe is not None:
            # Fix: in recovery mode, user_text is "" (the recovery pass
            # is seeded by the recovery_seed dict, not a user message),
            # which would leave the card's reason as "chat: " with
            # nothing after. Use the recovery seed's original_intent
            # instead so the card records which goal it belongs to —
            # both for Fix 6's chain walk and for human-readable card
            # rendering.
            if recovery_seed is not None:
                _intent = (recovery_seed.get("original_intent") or "").strip()
                if _intent:
                    card_reason = f"recovery: {_intent[:140]}"
                else:
                    card_reason = f"recovery: pass {recovery_seed.get('recovery_depth', '?')}"
            else:
                card_reason = f"chat: {user_text[:140]}"

            try:
                presult = pipe.handle_action(
                    action=action,
                    params=params,
                    reason=card_reason,
                    user_id=user_id,
                    chat_id=str(chat_id),
                    channel="telegram_text",
                )
            except Exception as e:
                logger.warning("pipeline dispatch %s failed: %s", action, e)
                msg = f"ERROR: {e}"
                transcript.append((action, params, msg, False))
                history.append(f"TOOL_CALL: {_json.dumps(call)}\nRESULT: {msg}")
                continue

            from core.decision_pipeline import PipelineStatus as _PS

            if presult.status == _PS.EXECUTED:
                out = (presult.execution_output or "").strip()[:1500] or "(no output)"
                ok = bool(presult.execution_success)
                transcript.append((action, params, out if ok else (presult.execution_error or "?"), ok))
                history.append(f"TOOL_CALL: {_json.dumps(call)}\nRESULT: {out}")
            elif presult.status in (_PS.PENDING_APPROVAL, _PS.PENDING_DIALOG):
                # A-core #4b: if this is a PENDING_DIALOG (Lane 3
                # self-mod), the pipeline also created a dialog
                # and returned its opening turn as dialog_opening.
                # Surface that to the owner as a separate Telegram
                # message via the thread-safe _send_card_message
                # helper (the Jarvis loop runs in an executor
                # thread, so async calls must go through
                # run_coroutine_threadsafe).
                if (
                    presult.status == _PS.PENDING_DIALOG
                    and getattr(presult, "dialog_opening", None)
                ):
                    try:
                        (send_intermediate and send_intermediate(presult.dialog_opening,  # type: ignore[arg-type]
                        ))
                    except Exception as e:
                        logger.warning(
                            "failed to send self-mod dialog opening: %s", e
                        )
                msg = (
                    "CARD_CREATED — NOT YET EXECUTED. A persistent approval card "
                    "was sent to the owner in Telegram. The action has NOT run; it is "
                    "waiting for his explicit go-ahead. In your reply you MUST "
                    "say you proposed the action and are waiting for approval. "
                    "Do NOT claim you checked, found, installed, or fixed anything."
                )
                # pending is a third state: not-ran-not-rejected. Use a
                # dedicated marker string (rendered by _format_transcript)
                # as "⏳" so rule #4 in the final prompt can reason off it.
                transcript.append((action, params, msg, "pending"))
                history.append(f"TOOL_CALL: {_json.dumps(call)}\nRESULT: {msg}")
                # Single-card-per-pass discipline. When the loop
                # produces a Lane 2 or Lane 3 card, that IS the
                # terminal state of this turn — don't let the model
                # propose another destructive action in the same
                # pass. Previously this break only fired in recovery
                # mode, which left the normal Jarvis path free to
                # propose N rm-rf variants in sequence (observed
                # 2026-04-20: 4 rm-rf cards created in 18 seconds
                # for a single "Delete /maez" turn, each superseding
                # the previous, creating a cards-in-repetition feel
                # on Telegram).
                #
                # Documented in docs/followups/recovery_multi_card_orphans.md
                # as the Option 1 fix: the FIRST Lane 2/3 card is
                # the terminal proposal. A second one is noise.
                logger.info(
                    "jarvis: first Lane 2/3 card created, breaking loop "
                    "(single-card-per-pass discipline, recovery=%s)",
                    recovery_seed is not None,
                )
                break
            else:  # REFUSED_COVENANT / REFUSED_AUDIT / ERROR
                msg = f"REFUSED: {presult.message}"
                transcript.append((action, params, msg, False))
                history.append(f"TOOL_CALL: {_json.dumps(call)}\nRESULT: {msg}")
            continue

        # Legacy path for non-primitive actions (read_file etc.).
        # Same reason-propagation fix as the pipeline path above: in
        # recovery mode the user_text is empty, so fall back to the
        # recovery seed's original_intent.
        if recovery_seed is not None:
            _intent = (recovery_seed.get("original_intent") or "").strip()
            if _intent:
                legacy_reason = f"recovery: {_intent[:140]}"
            else:
                legacy_reason = f"recovery: pass {recovery_seed.get('recovery_depth', '?')}"
        else:
            legacy_reason = f"chat: {user_text[:140]}"
        try:
            result = action_engine._execute_action(
                action, params,
                legacy_reason,
                tier=tier,
            )
        except Exception as e:
            logger.warning("jarvis dispatch %s failed: %s", action, e)
            msg = f"ERROR: {e}"
            transcript.append((action, params, msg, False))
            history.append(f"TOOL_CALL: {_json.dumps(call)}\nRESULT: {msg}")
            # Record to consequence_memory so future Maez can retrieve
            # past failures for similar actions. Fail-safe — the log
            # line above is still the primary signal.
            _record_tool_failure(action, params, str(e), surface="brain_loop/dispatch")
            continue

        if result.success:
            out = (result.output or "").strip()[:1500] or "(no output)"
            transcript.append((action, params, out, True))
            history.append(f"TOOL_CALL: {_json.dumps(call)}\nRESULT: {out}")
        else:
            msg = f"ERROR: {result.error}"
            transcript.append((action, params, msg, False))
            history.append(f"TOOL_CALL: {_json.dumps(call)}\nRESULT: {msg}")
            # Record failures from the action engine layer too —
            # these are the "ran but returned non-zero" class.
            _record_tool_failure(
                action, params, result.error or "(no error text)",
                surface="brain_loop/action",
            )

    if not transcript:
        return _empty()

    lines = [
        "[JARVIS TRANSCRIPT — the AUTHORITATIVE record of what you did",
        " this turn on the owner's machine. Tell the owner naturally what you did",
        " and what you found. Don't list raw output; synthesize.",
        "",
        " Marker legend:",
        "   ✓  the tool ran, the → output is real",
        "   ✗  the tool call was REJECTED, nothing ran",
        "   ⏳ the action was PROPOSED as a card, NOT YET EXECUTED —",
        "       the owner must approve in Telegram before it runs",
        "",
        " HARD RULES for your reply:",
        " 1. Only mention tools, commands, packages, or files that appear",
        "    in this transcript. Do not rename or substitute what you ran.",
        " 2. If memory recall (earlier in the prompt) mentions something you",
        "    did NOT run this turn, do not attribute it to the current turn.",
        "    You may say 'last time we looked at X' but not 'I just checked X'.",
        " 3. If the transcript is short or the result is empty, say that",
        "    plainly. 'I ran X and got no output' is better than inventing",
        "    a richer narrative.",
        " 4. If a tool call was rejected (✗), describe the rejection honestly",
        "    — don't pretend the thing ran.",
        " 5. If a line has ⏳ (card pending approval), the action has NOT run.",
        "    Tell the owner you proposed it and are waiting for his go-ahead.",
        "    Do NOT claim you checked, found, installed, or fixed anything",
        "    on a ⏳ line — only on ✓ lines.",
        "]"
    ]
    for action, params, out, ok in transcript:
        if ok == "pending":
            mark = "⏳"
        elif ok:
            mark = "✓"
        else:
            mark = "✗"
        lines.append(f"\n{mark} {action}({_json.dumps(params, default=str)[:200]})")
        lines.append(f"  → {out[:800]}")
    transcript_str = "\n".join(lines)
    if return_structured:
        return BrainLoopResult(
            transcript=transcript_str,
            tool_calls=[
                _transcript_to_tool_call_dict(item) for item in transcript
            ],
        )
    return transcript_str
