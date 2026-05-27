"""Merge owner for dispatcher substrate and external fan-out results.

This module is the sole owner of reconstructing a CompositionSpec after fan-out.
It does not run Layer 2 repair, open readers, fetch external data, or wire into
brain-loop routing.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any

from core.dispatcher.external_sources import (
    ExternalBranchResult,
    ExternalFanoutResult,
    FreshBlock,
)
from core.dispatcher.layer1 import Layer1FanoutResult, RecallBlock
from core.dispatcher.provenance_renderer import (
    AskShape,
    RenderedProvenance,
    SourceRole,
    SourceSummary,
    render_provenance,
)
from core.dispatcher.spec import (
    AvailabilityLimitation,
    CompositionHint,
    CompositionSpec,
    DispatcherRefusalReason,
    ExternalBranchStatus,
    ExternalEmptyReason,
    ExternalErrorClass,
    ExternalSource,
    FreshAttemptOutcome,
    ProvenanceAuditMismatchReason,
    ProvenanceFraming,
    SourceAvailability,
)


@dataclass(frozen=True)
class RenderedTurn:
    prompt_block: str
    audit_envelope: dict[str, Any]
    audit_assistant_text_metadata: dict[str, Any]
    effective_spec: CompositionSpec
    source_summaries: tuple[SourceSummary, ...]
    fresh_attempt_outcome: FreshAttemptOutcome
    refusal_reason: DispatcherRefusalReason | None = None


def merge_fanout_results(
    spec: CompositionSpec,
    layer1_result: Layer1FanoutResult,
    external_result: ExternalFanoutResult,
    *,
    utterance: str,
    surface: str,
    timestamp: str,
    ask_shape: AskShape = AskShape.CONVERSATIONAL,
) -> RenderedTurn:
    accepted_fresh_blocks = _accepted_fresh_blocks(external_result)
    substrate_has_rows = bool(layer1_result.recall_blocks)
    fresh_outcome = _fresh_attempt_outcome(spec, accepted_fresh_blocks)
    transform = _transform_for(
        spec,
        fresh_outcome=fresh_outcome,
        substrate_has_rows=substrate_has_rows,
    )
    if transform is None:
        return _refusal_turn(
            spec,
            utterance=utterance,
            surface=surface,
            timestamp=timestamp,
            fresh_attempt_outcome=fresh_outcome,
            refusal_reason=DispatcherRefusalReason.FRESH_FAILURE_HYBRID_FALLBACK_ILLEGAL,
        )

    if transform == "_NO_FRESH_SUMMARY":
        return _no_fresh_turn(
            spec,
            external_result,
            utterance=utterance,
            surface=surface,
            timestamp=timestamp,
            fresh_attempt_outcome=fresh_outcome,
        )

    effective_spec, reconstructed_from = _effective_spec(
        spec,
        accepted_fresh_blocks=accepted_fresh_blocks,
        include_substrate=substrate_has_rows,
        new_hint=transform[0],
        new_framing=transform[1],
        external_limitations=external_result.availability_limitations,
    )
    summaries = tuple(
        _source_summaries(
            effective_spec,
            layer1_result.recall_blocks,
            accepted_fresh_blocks,
        )
    )
    rendered = render_provenance(
        effective_spec,
        utterance=utterance,
        surface=surface,
        ask_shape=ask_shape,
        timestamp=timestamp,
        source_summaries=list(summaries),
        reconstructed_from_framing=(
            spec.provenance_framing if reconstructed_from else None
        ),
        reconstructed_from_hint=spec.composition_hint if reconstructed_from else None,
        fresh_attempt_outcome=fresh_outcome,
    )
    return _rendered_turn(
        rendered,
        effective_spec=effective_spec,
        source_summaries=summaries,
        fresh_attempt_outcome=fresh_outcome,
    )


def format_no_fresh_summary(fanout_result: ExternalFanoutResult) -> str:
    if not fanout_result.branch_results:
        return "[no fresh evidence available: NO_EXTERNAL_SOURCE:EMPTY:NO_RESULTS:FRESH_ATTEMPT_FAILED]"
    cells = []
    for branch in sorted(fanout_result.branch_results, key=lambda item: item.source.value):
        limitation = _limitation_for_external_branch(branch)
        error_or_empty = _closed_failure_label(branch)
        cells.append(
            f"{branch.source.value}:{branch.status.value}:{error_or_empty}:{limitation.value}"
        )
    return "[no fresh evidence available: " + "; ".join(cells) + "]"


def _transform_for(
    spec: CompositionSpec,
    *,
    fresh_outcome: FreshAttemptOutcome,
    substrate_has_rows: bool,
) -> tuple[CompositionHint, ProvenanceFraming] | str | None:
    if (
        spec.provenance_framing == ProvenanceFraming.FRESH_ONLY
        and spec.composition_hint == CompositionHint.FRESH_ONLY
        and not substrate_has_rows
    ):
        if fresh_outcome is FreshAttemptOutcome.ALL_FAILED:
            return "_NO_FRESH_SUMMARY"
        return (spec.composition_hint, spec.provenance_framing)

    if spec.provenance_framing == ProvenanceFraming.HYBRID_FRESH_VALIDATES_SUBSTRATE_CONTEXTUALIZES:
        if substrate_has_rows and fresh_outcome in {
            FreshAttemptOutcome.ALL_SUCCEEDED,
            FreshAttemptOutcome.PARTIAL,
        }:
            return (spec.composition_hint, spec.provenance_framing)
        if substrate_has_rows and fresh_outcome is FreshAttemptOutcome.ALL_FAILED:
            hint = (
                spec.composition_hint
                if ProvenanceFraming.FRESH_ATTEMPTED_UNAVAILABLE_SUBSTRATE_CONTEXT
                in _legal_framings(spec.composition_hint)
                else CompositionHint.FRESH_THEN_CONTEXTUALIZE
            )
            return (hint, ProvenanceFraming.FRESH_ATTEMPTED_UNAVAILABLE_SUBSTRATE_CONTEXT)
        if not substrate_has_rows and fresh_outcome in {
            FreshAttemptOutcome.ALL_SUCCEEDED,
            FreshAttemptOutcome.PARTIAL,
        }:
            return (CompositionHint.FRESH_ONLY, ProvenanceFraming.FRESH_ONLY)
        return None

    if spec.provenance_framing in {
        ProvenanceFraming.SUBSTRATE_ONLY_NO_FRESH_VALIDATION,
        ProvenanceFraming.SUBSTRATE_EVIDENCE_FRESH_CONTEXT,
        ProvenanceFraming.FRESH_ATTEMPTED_UNAVAILABLE_SUBSTRATE_CONTEXT,
    }:
        if substrate_has_rows:
            return (spec.composition_hint, spec.provenance_framing)
    return None


def _effective_spec(
    spec: CompositionSpec,
    *,
    accepted_fresh_blocks: tuple[FreshBlock, ...],
    include_substrate: bool,
    new_hint: CompositionHint,
    new_framing: ProvenanceFraming,
    external_limitations: tuple[AvailabilityLimitation, ...],
) -> tuple[CompositionSpec, bool]:
    external_sources = _external_sources_for(new_framing, accepted_fresh_blocks)
    substrate_sources = list(spec.substrate_sources) if include_substrate else []
    selected = [*substrate_sources, *external_sources]
    source_availability = {
        source: spec.source_availability.get(source, SourceAvailability.EXECUTABLE_PRESENT)
        for source in selected
    }
    limitations = _combined_limitations(
        spec.availability_limitations,
        external_limitations,
    )
    if spec.substrate_sources and not include_substrate:
        limitations = _combined_limitations(
            limitations,
            (AvailabilityLimitation.NO_RELEVANT_SUBSTRATE,),
        )
    reconstructed = (
        new_hint != spec.composition_hint
        or new_framing != spec.provenance_framing
        or list(external_sources) != list(spec.external_sources)
        or substrate_sources != list(spec.substrate_sources)
    )
    return (
        CompositionSpec(
            substrate_sources=substrate_sources,
            external_sources=list(external_sources),
            composition_hint=new_hint,
            provenance_framing=new_framing,
            inventory_witness=spec.inventory_witness,
            source_availability=source_availability,
            availability_limitations=limitations,
            freshness_window=spec.freshness_window,
            trust_scope_union=spec.trust_scope_union,
        ),
        reconstructed,
    )


def _combined_limitations(
    prior: list[AvailabilityLimitation],
    fresh: tuple[AvailabilityLimitation, ...],
) -> list[AvailabilityLimitation]:
    limitations = list(prior)
    for limitation in fresh:
        if limitation not in limitations:
            limitations.append(limitation)
    return limitations


def _source_summaries(
    spec: CompositionSpec,
    recall_blocks: tuple[RecallBlock, ...],
    fresh_blocks: tuple[FreshBlock, ...],
) -> list[SourceSummary]:
    summaries: list[SourceSummary] = []
    substrate_role = _substrate_role(spec.provenance_framing)
    fresh_role = _fresh_role(spec.provenance_framing)

    for source in spec.substrate_sources:
        text = "\n".join(block.text for block in recall_blocks if block.source == source)
        if text:
            summaries.append(
                SourceSummary(
                    source=source,
                    role=substrate_role,
                    text=text,
                    content_digest=_digest_text(text),
                )
            )

    for source in spec.external_sources:
        text = "\n".join(block.text for block in fresh_blocks if block.source == source)
        if text:
            summaries.append(
                SourceSummary(
                    source=source,
                    role=fresh_role,
                    text=text,
                    content_digest=_digest_text(text),
                )
            )
    return summaries


def _substrate_role(framing: ProvenanceFraming) -> SourceRole:
    if framing in {
        ProvenanceFraming.HYBRID_FRESH_VALIDATES_SUBSTRATE_CONTEXTUALIZES,
        ProvenanceFraming.FRESH_ATTEMPTED_UNAVAILABLE_SUBSTRATE_CONTEXT,
    }:
        return SourceRole.SUBSTRATE_CONTEXT
    return SourceRole.SUBSTRATE_EVIDENCE


def _fresh_role(framing: ProvenanceFraming) -> SourceRole:
    if framing == ProvenanceFraming.SUBSTRATE_EVIDENCE_FRESH_CONTEXT:
        return SourceRole.FRESH_CONTEXT
    return SourceRole.FRESH_EVIDENCE


def _accepted_fresh_blocks(
    external_result: ExternalFanoutResult,
) -> tuple[FreshBlock, ...]:
    blocks: list[FreshBlock] = []
    for branch in external_result.branch_results:
        if branch.status is not ExternalBranchStatus.SUCCESS:
            continue
        if branch.completed_at is not None and branch.completed_at > external_result.sealed_at:
            continue
        blocks.extend(branch.blocks)
    return tuple(blocks)


def _fresh_attempt_outcome(
    spec: CompositionSpec,
    accepted_blocks: tuple[FreshBlock, ...],
) -> FreshAttemptOutcome:
    if not spec.external_sources:
        return FreshAttemptOutcome.ALL_SUCCEEDED
    successful_sources = {block.source for block in accepted_blocks}
    if len(successful_sources) == len(set(spec.external_sources)):
        return FreshAttemptOutcome.ALL_SUCCEEDED
    if successful_sources:
        return FreshAttemptOutcome.PARTIAL
    return FreshAttemptOutcome.ALL_FAILED


def _external_sources_for(
    framing: ProvenanceFraming,
    accepted_fresh_blocks: tuple[FreshBlock, ...],
) -> tuple[ExternalSource, ...]:
    if framing == ProvenanceFraming.FRESH_ATTEMPTED_UNAVAILABLE_SUBSTRATE_CONTEXT:
        return ()
    return tuple(sorted({block.source for block in accepted_fresh_blocks}, key=lambda item: item.value))


def _no_fresh_turn(
    spec: CompositionSpec,
    external_result: ExternalFanoutResult,
    *,
    utterance: str,
    surface: str,
    timestamp: str,
    fresh_attempt_outcome: FreshAttemptOutcome,
) -> RenderedTurn:
    prompt_block = format_no_fresh_summary(external_result)
    envelope = _base_audit_envelope(
        spec,
        utterance=utterance,
        surface=surface,
        timestamp=timestamp,
        fresh_attempt_outcome=fresh_attempt_outcome,
        refusal_reason=None,
    )
    return RenderedTurn(
        prompt_block=prompt_block,
        audit_envelope=envelope,
        audit_assistant_text_metadata=_assistant_metadata(envelope),
        effective_spec=spec,
        source_summaries=(),
        fresh_attempt_outcome=fresh_attempt_outcome,
    )


def _refusal_turn(
    spec: CompositionSpec,
    *,
    utterance: str,
    surface: str,
    timestamp: str,
    fresh_attempt_outcome: FreshAttemptOutcome,
    refusal_reason: DispatcherRefusalReason,
) -> RenderedTurn:
    prompt_block = f"[dispatcher refusal: {refusal_reason.value}]"
    envelope = _base_audit_envelope(
        spec,
        utterance=utterance,
        surface=surface,
        timestamp=timestamp,
        fresh_attempt_outcome=fresh_attempt_outcome,
        refusal_reason=refusal_reason,
    )
    return RenderedTurn(
        prompt_block=prompt_block,
        audit_envelope=envelope,
        audit_assistant_text_metadata=_assistant_metadata(envelope),
        effective_spec=spec,
        source_summaries=(),
        fresh_attempt_outcome=fresh_attempt_outcome,
        refusal_reason=refusal_reason,
    )


def _rendered_turn(
    rendered: RenderedProvenance,
    *,
    effective_spec: CompositionSpec,
    source_summaries: tuple[SourceSummary, ...],
    fresh_attempt_outcome: FreshAttemptOutcome,
) -> RenderedTurn:
    return RenderedTurn(
        prompt_block=rendered.prompt_block,
        audit_envelope=rendered.audit_envelope,
        audit_assistant_text_metadata=rendered.audit_assistant_text_metadata,
        effective_spec=effective_spec,
        source_summaries=source_summaries,
        fresh_attempt_outcome=fresh_attempt_outcome,
    )


def _base_audit_envelope(
    spec: CompositionSpec,
    *,
    utterance: str,
    surface: str,
    timestamp: str,
    fresh_attempt_outcome: FreshAttemptOutcome,
    refusal_reason: DispatcherRefusalReason | None,
) -> dict[str, Any]:
    spec_payload = spec.to_dict()
    return {
        "spec_digest": _digest_json(spec_payload),
        "schema_version": spec.schema_version,
        "utterance_digest": _digest_text(utterance),
        "surface": surface,
        "timestamp": timestamp,
        "composition_hint": spec.composition_hint.value,
        "provenance_framing": spec.provenance_framing.value,
        "substrate_sources": [source.value for source in spec.substrate_sources],
        "external_sources": [source.value for source in spec.external_sources],
        "source_role_map": {},
        "source_digests": {},
        "inventory_witness": spec.inventory_witness.value,
        "source_availability": {
            source.value: availability.value
            for source, availability in sorted(
                spec.source_availability.items(),
                key=lambda item: item[0].value,
            )
        },
        "availability_limitations": [
            limitation.value for limitation in spec.availability_limitations
        ],
        "rendered_block_roles": [],
        "template_id": "merge.no_fresh_or_refusal.v1",
        "template_version_hash": "sha256:adr0047-merge-v1",
        "reconstructed_from_framing": None,
        "reconstructed_from_hint": None,
        "fresh_attempt_outcome": fresh_attempt_outcome.value,
        "mismatch_reason": ProvenanceAuditMismatchReason.NONE.value,
        "refusal_reason": refusal_reason.value if refusal_reason else None,
    }


def _assistant_metadata(envelope: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "spec_digest",
        "schema_version",
        "utterance_digest",
        "surface",
        "timestamp",
        "provenance_framing",
        "source_role_map",
        "rendered_block_roles",
        "template_id",
        "template_version_hash",
        "reconstructed_from_framing",
        "reconstructed_from_hint",
        "fresh_attempt_outcome",
        "mismatch_reason",
        "refusal_reason",
    )
    return {key: envelope[key] for key in keys}


def _closed_failure_label(branch: ExternalBranchResult) -> str:
    if branch.error_class is not None:
        return branch.error_class.value
    if branch.empty_reason is not None:
        return branch.empty_reason.value
    if branch.status is ExternalBranchStatus.TIMEOUT:
        return ExternalErrorClass.TIMEOUT.value
    if branch.status is ExternalBranchStatus.RESERVED_UNAVAILABLE:
        return ExternalEmptyReason.RESERVED_SOURCE_UNAVAILABLE.value
    return ExternalErrorClass.UNCLASSIFIED.value


def _limitation_for_external_branch(branch: ExternalBranchResult) -> AvailabilityLimitation:
    if branch.status is ExternalBranchStatus.SUCCESS:
        return AvailabilityLimitation.FRESH_ATTEMPT_FAILED
    if branch.status is ExternalBranchStatus.TIMEOUT:
        return AvailabilityLimitation.SOURCE_TIMEOUT
    if branch.status is ExternalBranchStatus.RESERVED_UNAVAILABLE:
        return AvailabilityLimitation.RESERVED_SOURCE_UNAVAILABLE
    if branch.error_class is ExternalErrorClass.SUBJECT_BOUNDARY_REFUSED:
        return AvailabilityLimitation.THIRD_PARTY_SUBJECT_BOUNDARY
    return AvailabilityLimitation.FRESH_ATTEMPT_FAILED


def _legal_framings(hint: CompositionHint) -> frozenset[ProvenanceFraming]:
    if hint == CompositionHint.SUBSTRATE_ONLY:
        return frozenset(
            {
                ProvenanceFraming.SUBSTRATE_ONLY_NO_FRESH_VALIDATION,
                ProvenanceFraming.SUBSTRATE_EVIDENCE_FRESH_CONTEXT,
            }
        )
    if hint == CompositionHint.FRESH_ONLY:
        return frozenset({ProvenanceFraming.FRESH_ONLY})
    if hint == CompositionHint.PARALLEL:
        return frozenset(
            {
                ProvenanceFraming.HYBRID_FRESH_VALIDATES_SUBSTRATE_CONTEXTUALIZES,
                ProvenanceFraming.SUBSTRATE_EVIDENCE_FRESH_CONTEXT,
            }
        )
    if hint == CompositionHint.SUBSTRATE_THEN_FETCH_IF_STALE:
        return frozenset(
            {
                ProvenanceFraming.HYBRID_FRESH_VALIDATES_SUBSTRATE_CONTEXTUALIZES,
                ProvenanceFraming.SUBSTRATE_ONLY_NO_FRESH_VALIDATION,
                ProvenanceFraming.FRESH_ATTEMPTED_UNAVAILABLE_SUBSTRATE_CONTEXT,
            }
        )
    if hint == CompositionHint.FRESH_THEN_CONTEXTUALIZE:
        return frozenset(
            {
                ProvenanceFraming.HYBRID_FRESH_VALIDATES_SUBSTRATE_CONTEXTUALIZES,
                ProvenanceFraming.FRESH_ATTEMPTED_UNAVAILABLE_SUBSTRATE_CONTEXT,
            }
        )
    return frozenset()


def _digest_json(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _digest_text(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode()).hexdigest()
