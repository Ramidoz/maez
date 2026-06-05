"""Layer 1 substrate fan-out for ADR 0047.

Layer 1 consumes a CompositionSpec and opens substrate readers through injected
adapters. It does not choose sources, fetch external data, render prompt text,
modify repair specs, or wire into brain-loop routing.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import Future, ThreadPoolExecutor, wait
from dataclasses import dataclass, replace
from enum import StrEnum
import time
import uuid
from typing import Any

from core.dispatcher.spec import (
    CompositionSpec,
    SourceRole,
    SourceAvailability,
    SubstrateSource,
)


DEFAULT_BRANCH_TIMEOUT_S = 0.08
DEFAULT_GLOBAL_DEADLINE_S = 0.2
DEFAULT_CLEANUP_GRACE_S = 0.025
DEFAULT_MAX_PARALLEL_BRANCHES = 6
MAX_RECALL_BLOCKS_PER_SOURCE = 3
MAX_RECALL_CHARS_PER_SOURCE = 1200
MAX_TOTAL_RECALL_CHARS = 4200
TRUNCATION_MARKER = "...[truncated]"

SOURCE_PRIORITY = (
    SubstrateSource.REDDIT_SOURCE,
    SubstrateSource.TELEGRAM_TEMPORAL,
    SubstrateSource.TELEGRAM_SEMANTIC,
    SubstrateSource.ENTITY_INDEX,
    SubstrateSource.LIVED_EPISODES,
    SubstrateSource.PRIVATE_THOUGHTS,
    SubstrateSource.WONDERINGS,
    SubstrateSource.SELF_DEV_REVIEWS,
    SubstrateSource.AUDIT_AND_FABRICATION,
    SubstrateSource.SANDBOX_WITNESSES,
    SubstrateSource.LIVED_GRAPH,
    SubstrateSource.WEB_FAST_TURNS,
)


class RecallBranchStatus(StrEnum):
    SUCCESS = "SUCCESS"
    EMPTY = "EMPTY"
    TIMEOUT = "TIMEOUT"
    ERROR = "ERROR"
    RESERVED_UNAVAILABLE = "RESERVED_UNAVAILABLE"
    PRIVACY_GATED = "PRIVACY_GATED"


RecallAdapter = Callable[[SubstrateSource], Sequence["RecallBlock"]]


@dataclass(frozen=True)
class RecallItem:
    text: str
    source_type: str
    durable_id: str | None = None
    temporal_provenance: dict | None = None
    trust_tier: str | None = None


@dataclass(frozen=True)
class RecallBlock:
    source: SubstrateSource
    text: str
    timestamp: float | None
    freshness: str
    rationale: str
    prompt_cost: int
    truncated: bool = False
    original_chars: int | None = None
    role_hint: SourceRole | None = None
    items: tuple[RecallItem, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "source": self.source.value,
            "text": self.text,
            "timestamp": self.timestamp,
            "freshness": self.freshness,
            "rationale": self.rationale,
            "prompt_cost": self.prompt_cost,
            "truncated": self.truncated,
            "original_chars": self.original_chars,
        }
        if self.role_hint is not None:
            payload["role_hint"] = self.role_hint.value
        if self.items:
            payload["items"] = [
                {
                    "durable_id": item.durable_id,
                    "source_type": item.source_type,
                    "temporal_provenance": item.temporal_provenance,
                    "trust_tier": item.trust_tier,
                }
                for item in self.items
            ]
        return payload


@dataclass(frozen=True)
class RecallBranchResult:
    branch_id: str
    fanout_generation_id: str
    source: SubstrateSource
    status: RecallBranchStatus
    blocks: tuple[RecallBlock, ...] = ()
    empty_reason: str | None = None
    error_class: str | None = None
    elapsed_ms: float = 0.0
    deadline_kind: str | None = None
    cancel_requested: bool = False
    cancel_observed: bool = False
    late_result_ignored: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "branch_id": self.branch_id,
            "fanout_generation_id": self.fanout_generation_id,
            "source": self.source.value,
            "status": self.status.value,
            "blocks": [block.to_dict() for block in self.blocks],
            "empty_reason": self.empty_reason,
            "error_class": self.error_class,
            "elapsed_ms": round(self.elapsed_ms, 3),
            "deadline_kind": self.deadline_kind,
            "cancel_requested": self.cancel_requested,
            "cancel_observed": self.cancel_observed,
            "late_result_ignored": self.late_result_ignored,
        }


@dataclass(frozen=True)
class RecallBudgetEvent:
    source: SubstrateSource
    truncated_blocks: int = 0
    dropped_blocks: int = 0
    original_chars: int = 0
    capped_chars: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source.value,
            "truncated_blocks": self.truncated_blocks,
            "dropped_blocks": self.dropped_blocks,
            "original_chars": self.original_chars,
            "capped_chars": self.capped_chars,
        }


@dataclass(frozen=True)
class Layer1FanoutResult:
    fanout_generation_id: str
    sealed_at: float
    accepted_branch_ids: tuple[str, ...]
    branch_results: tuple[RecallBranchResult, ...]
    recall_blocks: tuple[RecallBlock, ...]
    budget_events: tuple[RecallBudgetEvent, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "fanout_generation_id": self.fanout_generation_id,
            "sealed_at": self.sealed_at,
            "accepted_branch_ids": list(self.accepted_branch_ids),
            "branch_results": [branch.to_dict() for branch in self.branch_results],
            "recall_blocks": [block.to_dict() for block in self.recall_blocks],
            "budget_events": [event.to_dict() for event in self.budget_events],
        }


class Layer1Fanout:
    def __init__(
        self,
        *,
        adapters: Mapping[SubstrateSource, RecallAdapter],
        branch_timeout_s: float = DEFAULT_BRANCH_TIMEOUT_S,
        global_deadline_s: float = DEFAULT_GLOBAL_DEADLINE_S,
        cleanup_grace_s: float = DEFAULT_CLEANUP_GRACE_S,
        max_parallel_branches: int = DEFAULT_MAX_PARALLEL_BRANCHES,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self.adapters = dict(adapters)
        self.branch_timeout_s = branch_timeout_s
        self.global_deadline_s = global_deadline_s
        self.cleanup_grace_s = cleanup_grace_s
        self.max_parallel_branches = max_parallel_branches
        self.clock = clock or time.monotonic

    def run(
        self,
        spec: CompositionSpec,
        *,
        utterance: str,
        conversation_state: Mapping[str, Any],
        fanout_generation_id: str | None = None,
    ) -> Layer1FanoutResult:
        del utterance, conversation_state
        generation_id = fanout_generation_id if fanout_generation_id is not None else uuid.uuid4().hex
        started_at = self.clock()
        deadline_at = started_at + self.global_deadline_s
        ordered_sources = _stable_sources(spec.substrate_sources)
        results: dict[SubstrateSource, RecallBranchResult] = {}
        accepted_branch_ids: list[str] = []
        accepted_blocks: list[RecallBlock] = []
        executor = ThreadPoolExecutor(
            max_workers=max(1, min(self.max_parallel_branches, len(ordered_sources) or 1))
        )
        futures: dict[Future[Sequence[RecallBlock]], tuple[SubstrateSource, str, float]] = {}

        try:
            for source in ordered_sources:
                branch_id = _branch_id(generation_id, source)
                preflight = self._preflight_result(spec, source, generation_id, branch_id)
                if preflight is not None:
                    results[source] = preflight
                    continue

                adapter = self.adapters.get(source)
                if adapter is None:
                    results[source] = RecallBranchResult(
                        branch_id=branch_id,
                        fanout_generation_id=generation_id,
                        source=source,
                        status=RecallBranchStatus.ERROR,
                        error_class="adapter_missing",
                    )
                    continue

                futures[executor.submit(adapter, source)] = (
                    source,
                    branch_id,
                    self.clock(),
                )

            pending = set(futures)
            while pending:
                now = self.clock()
                if now >= deadline_at:
                    for future in list(pending):
                        source, branch_id, submitted_at = futures[future]
                        results[source] = _timeout_result(
                            generation_id=generation_id,
                            branch_id=branch_id,
                            source=source,
                            elapsed_ms=(now - submitted_at) * 1000,
                            deadline_kind="global",
                            cancel_observed=future.cancel(),
                        )
                    pending.clear()
                    break

                for future in list(pending):
                    source, branch_id, submitted_at = futures[future]
                    if now - submitted_at >= self.branch_timeout_s:
                        results[source] = _timeout_result(
                            generation_id=generation_id,
                            branch_id=branch_id,
                            source=source,
                            elapsed_ms=(now - submitted_at) * 1000,
                            deadline_kind="branch",
                            cancel_observed=future.cancel(),
                        )
                        pending.remove(future)

                if not pending:
                    break

                done, _ = wait(pending, timeout=min(0.002, max(0.0, deadline_at - now)))
                for future in done:
                    source, branch_id, submitted_at = futures[future]
                    pending.remove(future)
                    elapsed_ms = (self.clock() - submitted_at) * 1000
                    results[source] = self._result_from_future(
                        future,
                        source=source,
                        branch_id=branch_id,
                        generation_id=generation_id,
                        elapsed_ms=elapsed_ms,
                    )
        finally:
            if self.cleanup_grace_s > 0:
                wait(set(futures) - {future for future in futures if future.done()}, timeout=self.cleanup_grace_s)
            executor.shutdown(wait=False, cancel_futures=True)

        sealed_at = self.clock()
        for source in ordered_sources:
            result = results[source]
            if result.status is RecallBranchStatus.SUCCESS:
                accepted_branch_ids.append(result.branch_id)
                accepted_blocks.extend(result.blocks)
        budgeted_blocks, budget_events = _budget_blocks(
            accepted_blocks,
            max_per_source=MAX_RECALL_BLOCKS_PER_SOURCE,
            max_chars_per_source=MAX_RECALL_CHARS_PER_SOURCE,
            max_total_chars=MAX_TOTAL_RECALL_CHARS,
        )

        return Layer1FanoutResult(
            fanout_generation_id=generation_id,
            sealed_at=sealed_at,
            accepted_branch_ids=tuple(accepted_branch_ids),
            branch_results=tuple(results[source] for source in ordered_sources),
            recall_blocks=tuple(budgeted_blocks),
            budget_events=budget_events,
        )

    def _preflight_result(
        self,
        spec: CompositionSpec,
        source: SubstrateSource,
        generation_id: str,
        branch_id: str,
    ) -> RecallBranchResult | None:
        availability = spec.source_availability.get(
            source,
            SourceAvailability.EXECUTABLE_UNKNOWN,
        )
        if availability is SourceAvailability.RESERVED_UNAVAILABLE:
            return RecallBranchResult(
                branch_id=branch_id,
                fanout_generation_id=generation_id,
                source=source,
                status=RecallBranchStatus.RESERVED_UNAVAILABLE,
                empty_reason="reserved_source_unavailable",
            )
        if availability in {
            SourceAvailability.PRIVACY_GATED,
            SourceAvailability.TRUST_SCOPE_RESTRICTED,
        }:
            return RecallBranchResult(
                branch_id=branch_id,
                fanout_generation_id=generation_id,
                source=source,
                status=RecallBranchStatus.PRIVACY_GATED,
                empty_reason=availability.value.lower(),
            )
        if availability is SourceAvailability.EXECUTABLE_ABSENT:
            return RecallBranchResult(
                branch_id=branch_id,
                fanout_generation_id=generation_id,
                source=source,
                status=RecallBranchStatus.EMPTY,
                empty_reason="source_absent",
            )
        return None

    def _result_from_future(
        self,
        future: Future[Sequence[RecallBlock]],
        *,
        source: SubstrateSource,
        branch_id: str,
        generation_id: str,
        elapsed_ms: float,
    ) -> RecallBranchResult:
        try:
            blocks = tuple(future.result())
        except Exception as exc:
            return RecallBranchResult(
                branch_id=branch_id,
                fanout_generation_id=generation_id,
                source=source,
                status=RecallBranchStatus.ERROR,
                error_class=type(exc).__name__,
                elapsed_ms=elapsed_ms,
            )

        if not blocks:
            return RecallBranchResult(
                branch_id=branch_id,
                fanout_generation_id=generation_id,
                source=source,
                status=RecallBranchStatus.EMPTY,
                empty_reason="no_relevant_rows",
                elapsed_ms=elapsed_ms,
            )
        return RecallBranchResult(
            branch_id=branch_id,
            fanout_generation_id=generation_id,
            source=source,
            status=RecallBranchStatus.SUCCESS,
            blocks=blocks,
            elapsed_ms=elapsed_ms,
        )


def _timeout_result(
    *,
    generation_id: str,
    branch_id: str,
    source: SubstrateSource,
    elapsed_ms: float,
    deadline_kind: str,
    cancel_observed: bool,
) -> RecallBranchResult:
    return RecallBranchResult(
        branch_id=branch_id,
        fanout_generation_id=generation_id,
        source=source,
        status=RecallBranchStatus.TIMEOUT,
        empty_reason="deadline_reached",
        elapsed_ms=elapsed_ms,
        deadline_kind=deadline_kind,
        cancel_requested=True,
        cancel_observed=cancel_observed,
        late_result_ignored=True,
    )


def _stable_sources(sources: Sequence[SubstrateSource]) -> list[SubstrateSource]:
    return sorted(sources, key=lambda source: (_source_priority(source), source.value))


def _source_priority(source: SubstrateSource) -> int:
    try:
        return SOURCE_PRIORITY.index(source)
    except ValueError:
        return len(SOURCE_PRIORITY)


def _branch_id(generation_id: str, source: SubstrateSource) -> str:
    return f"{generation_id}:{source.value}"


def _budget_blocks(
    blocks: Sequence[RecallBlock],
    *,
    max_per_source: int,
    max_chars_per_source: int,
    max_total_chars: int,
) -> tuple[list[RecallBlock], tuple[RecallBudgetEvent, ...]]:
    selected: list[RecallBlock] = []
    per_source_count: dict[SubstrateSource, int] = {}
    per_source_chars: dict[SubstrateSource, int] = {}
    events: dict[SubstrateSource, _MutableBudgetEvent] = {}
    total_chars = 0
    for block in blocks:
        block_chars = len(block.text)
        if per_source_count.get(block.source, 0) >= max_per_source:
            _record_drop(events, block.source, original_chars=block_chars)
            continue

        remaining_source_chars = max_chars_per_source - per_source_chars.get(block.source, 0)
        remaining_total_chars = max_total_chars - total_chars
        allowed_chars = min(remaining_source_chars, remaining_total_chars)
        if allowed_chars <= 0:
            _record_drop(events, block.source, original_chars=block_chars)
            continue

        selected_block = block
        if block_chars > allowed_chars:
            selected_block = _truncate_block(block, allowed_chars)
            if selected_block is None:
                _record_drop(events, block.source, original_chars=block_chars)
                continue
            _record_truncation(
                events,
                block.source,
                original_chars=block_chars,
                capped_chars=len(selected_block.text),
            )

        selected.append(selected_block)
        per_source_count[block.source] = per_source_count.get(block.source, 0) + 1
        per_source_chars[block.source] = per_source_chars.get(block.source, 0) + len(selected_block.text)
        total_chars += len(selected_block.text)
    return selected, tuple(event.freeze() for _, event in sorted(events.items(), key=lambda item: item[0].value))


@dataclass
class _MutableBudgetEvent:
    source: SubstrateSource
    truncated_blocks: int = 0
    dropped_blocks: int = 0
    original_chars: int = 0
    capped_chars: int = 0

    def freeze(self) -> RecallBudgetEvent:
        return RecallBudgetEvent(
            source=self.source,
            truncated_blocks=self.truncated_blocks,
            dropped_blocks=self.dropped_blocks,
            original_chars=self.original_chars,
            capped_chars=self.capped_chars,
        )


def _budget_event(
    events: dict[SubstrateSource, _MutableBudgetEvent],
    source: SubstrateSource,
) -> _MutableBudgetEvent:
    if source not in events:
        events[source] = _MutableBudgetEvent(source=source)
    return events[source]


def _record_drop(
    events: dict[SubstrateSource, _MutableBudgetEvent],
    source: SubstrateSource,
    *,
    original_chars: int,
) -> None:
    event = _budget_event(events, source)
    event.dropped_blocks += 1
    event.original_chars += original_chars


def _record_truncation(
    events: dict[SubstrateSource, _MutableBudgetEvent],
    source: SubstrateSource,
    *,
    original_chars: int,
    capped_chars: int,
) -> None:
    event = _budget_event(events, source)
    event.truncated_blocks += 1
    event.original_chars += original_chars
    event.capped_chars += capped_chars


def _truncate_block(block: RecallBlock, allowed_chars: int) -> RecallBlock | None:
    if allowed_chars <= len(TRUNCATION_MARKER):
        return None
    prefix_chars = allowed_chars - len(TRUNCATION_MARKER)
    text = block.text[:prefix_chars] + TRUNCATION_MARKER
    return replace(
        block,
        text=text,
        truncated=True,
        original_chars=len(block.text),
        prompt_cost=min(block.prompt_cost, len(text)),
    )
