"""Provenance rendering for ADR 0047 dispatcher composition specs.

This module is the prompt/audit boundary for the dispatcher. It turns an
already-validated CompositionSpec into provenance-marked prompt text and a
closed audit envelope. It does not choose sources or run recall.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import hashlib
import json
from typing import Any

from core.cognition.fetch_screen_flags import fetch_containment_enabled
from core.dispatcher import fresh_containment as _fc
from core.dispatcher.spec import (
    CompositionHint,
    CompositionSpec,
    DispatcherRefusalReason,
    DispatcherSpecRefused,
    ExternalSource,
    ProvenanceAuditMismatchReason,
    ProvenanceFraming,
    SourceRole,
    SourceLabel,
    SubstrateSource,
)


TEMPLATE_VERSION_HASH = "sha256:adr0047-provenance-renderer-v1"


class AskShape(StrEnum):
    CONVERSATIONAL = "CONVERSATIONAL"
    REPORT = "REPORT"


@dataclass(frozen=True)
class SourceSummary:
    source: SourceLabel
    role: SourceRole
    text: str
    content_digest: str


@dataclass(frozen=True)
class RenderedProvenance:
    prompt_block: str
    audit_envelope: dict[str, Any]
    audit_assistant_text_metadata: dict[str, Any]


def render_provenance(
    spec: CompositionSpec,
    *,
    utterance: str,
    surface: str,
    ask_shape: AskShape,
    timestamp: str,
    source_summaries: list[SourceSummary],
    reconstructed_from_framing: ProvenanceFraming | None = None,
    reconstructed_from_hint: CompositionHint | None = None,
    fresh_attempt_outcome: Any | None = None,
) -> RenderedProvenance:
    ask_shape = AskShape(ask_shape)
    _validate_source_roles(spec, source_summaries)

    template_id = _template_id(spec.provenance_framing, ask_shape)
    prompt_block, rendered_roles = _render_prompt_block(
        spec,
        ask_shape=ask_shape,
        source_summaries=source_summaries,
    )
    envelope = _audit_envelope(
        spec,
        utterance=utterance,
        surface=surface,
        timestamp=timestamp,
        source_summaries=source_summaries,
        rendered_block_roles=rendered_roles,
        template_id=template_id,
        reconstructed_from_framing=reconstructed_from_framing,
        reconstructed_from_hint=reconstructed_from_hint,
        fresh_attempt_outcome=fresh_attempt_outcome,
    )
    return RenderedProvenance(
        prompt_block=prompt_block,
        audit_envelope=envelope,
        audit_assistant_text_metadata=_assistant_text_metadata(envelope),
    )


def _validate_source_roles(
    spec: CompositionSpec,
    source_summaries: list[SourceSummary],
) -> None:
    expected = _allowed_roles(spec.provenance_framing)
    selected = set(spec.substrate_sources) | set(spec.external_sources)
    seen: set[SourceLabel] = set()

    for summary in source_summaries:
        seen.add(summary.source)
        if summary.source not in selected:
            _refuse_template_mismatch(f"unselected source {summary.source.value}")
        if summary.role not in expected:
            _refuse_template_mismatch(
                f"{summary.source.value} rendered as {summary.role.value}"
            )
        if isinstance(summary.source, SubstrateSource) and summary.role not in {
            SourceRole.SUBSTRATE_CONTEXT,
            SourceRole.SUBSTRATE_EVIDENCE,
        }:
            _refuse_template_mismatch(
                f"{summary.source.value} must render as substrate role"
            )
        if isinstance(summary.source, ExternalSource) and summary.role not in {
            SourceRole.FRESH_CONTEXT,
            SourceRole.FRESH_EVIDENCE,
        }:
            _refuse_template_mismatch(
                f"{summary.source.value} must render as fresh role"
            )

    missing = sorted(source.value for source in selected - seen)
    if missing:
        _refuse_template_mismatch(f"missing source summaries for {', '.join(missing)}")


def _allowed_roles(framing: ProvenanceFraming) -> frozenset[SourceRole]:
    if framing == ProvenanceFraming.SUBSTRATE_ONLY_NO_FRESH_VALIDATION:
        return frozenset({SourceRole.SUBSTRATE_CONTEXT, SourceRole.SUBSTRATE_EVIDENCE})
    if framing == ProvenanceFraming.SUBSTRATE_EVIDENCE_FRESH_CONTEXT:
        return frozenset({SourceRole.SUBSTRATE_EVIDENCE, SourceRole.FRESH_CONTEXT})
    if framing == ProvenanceFraming.HYBRID_FRESH_VALIDATES_SUBSTRATE_CONTEXTUALIZES:
        return frozenset({SourceRole.SUBSTRATE_CONTEXT, SourceRole.FRESH_EVIDENCE})
    if framing == ProvenanceFraming.FRESH_ATTEMPTED_UNAVAILABLE_SUBSTRATE_CONTEXT:
        return frozenset({SourceRole.SUBSTRATE_CONTEXT})
    if framing == ProvenanceFraming.FRESH_ONLY:
        return frozenset({SourceRole.FRESH_EVIDENCE})
    _refuse_template_mismatch(f"unsupported framing {framing.value}")


def _template_id(framing: ProvenanceFraming, ask_shape: AskShape) -> str:
    if framing == ProvenanceFraming.HYBRID_FRESH_VALIDATES_SUBSTRATE_CONTEXTUALIZES:
        base = "hybrid"
    elif framing == ProvenanceFraming.SUBSTRATE_ONLY_NO_FRESH_VALIDATION:
        base = "substrate_only_no_fresh_validation"
    elif framing == ProvenanceFraming.SUBSTRATE_EVIDENCE_FRESH_CONTEXT:
        base = "substrate_evidence"
    elif framing == ProvenanceFraming.FRESH_ATTEMPTED_UNAVAILABLE_SUBSTRATE_CONTEXT:
        base = "fresh_attempted_unavailable"
    elif framing == ProvenanceFraming.FRESH_ONLY:
        base = "fresh_only"
    else:
        _refuse_template_mismatch(f"unsupported framing {framing.value}")
    return f"{ask_shape.value.lower()}.{base}.v1"


def _render_prompt_block(
    spec,
    *,
    ask_shape: AskShape,
    source_summaries: list[SourceSummary],
) -> tuple[str, list[str]]:
    rendered_roles: list[str] = []
    _contain = fetch_containment_enabled()
    _nonce = _fc.new_nonce() if _contain else ""
    _fresh_roles = {SourceRole.FRESH_EVIDENCE, SourceRole.FRESH_CONTEXT}
    _fresh_digests: list[str] = []

    def _text_for(summary):
        if _contain and summary.role in _fresh_roles:
            _fresh_digests.append(summary.content_digest)
            return _fc.contain_fresh_text(
                summary.text,
                nonce=_nonce,
                source=getattr(summary.source, "value", str(summary.source)),
                content_digest=summary.content_digest,
            )
        return summary.text

    def _emit_dispatcher_receipt(block: str) -> None:
        if not (_contain and _fresh_digests):
            return
        from core.routing import web_containment as _wc  # local import: keep off provenance_renderer's import path (no cycle)
        _digest = ",".join(dict.fromkeys(_fresh_digests))[:80]
        _wc.emit_receipt(_wc.containment_receipt(
            block, nonce=_nonce, path="dispatcher",
            expected_segments=len(_fresh_digests), digest=_digest))

    if ask_shape == AskShape.REPORT:
        sections = []
        if _contain and any(s.role in _fresh_roles for s in source_summaries):
            sections.append(_fc.standing_instruction())
        for summary in source_summaries:
            title = _section_title(summary.role)
            rendered_roles.append(summary.role.value)
            sections.append(f"## {title}\n{_text_for(summary)}")
        _block = "\n\n".join(sections)
        _emit_dispatcher_receipt(_block)
        return _block, rendered_roles

    parts = []
    if _contain and any(s.role in _fresh_roles for s in source_summaries):
        parts.append(_fc.standing_instruction())
    for summary in source_summaries:
        marker = _inline_marker(summary.role)
        rendered_roles.append(summary.role.value)
        parts.append(f"{marker} {_text_for(summary)}")

    if (
        spec.composition_hint == CompositionHint.SUBSTRATE_ONLY
        and spec.provenance_framing
        == ProvenanceFraming.SUBSTRATE_ONLY_NO_FRESH_VALIDATION
    ):
        parts.append(
            "[fresh validation] No fresh source was used for this answer; "
            "the substrate is not being framed as unreliable."
        )
        rendered_roles.append("NO_FRESH_VALIDATION")
    _block = "\n".join(parts)
    _emit_dispatcher_receipt(_block)
    return _block, rendered_roles


def _inline_marker(role: SourceRole) -> str:
    if role == SourceRole.SUBSTRATE_CONTEXT:
        return "[memory context]"
    if role == SourceRole.SUBSTRATE_EVIDENCE:
        return "[memory evidence]"
    if role == SourceRole.FRESH_EVIDENCE:
        return "[fresh evidence]"
    if role == SourceRole.FRESH_CONTEXT:
        return "[fresh context]"
    _refuse_template_mismatch(f"unsupported role {role.value}")


def _section_title(role: SourceRole) -> str:
    if role == SourceRole.SUBSTRATE_CONTEXT:
        return "Memory context"
    if role == SourceRole.SUBSTRATE_EVIDENCE:
        return "Memory evidence"
    if role == SourceRole.FRESH_EVIDENCE:
        return "Fresh evidence"
    if role == SourceRole.FRESH_CONTEXT:
        return "Fresh context"
    _refuse_template_mismatch(f"unsupported role {role.value}")


def _audit_envelope(
    spec: CompositionSpec,
    *,
    utterance: str,
    surface: str,
    timestamp: str,
    source_summaries: list[SourceSummary],
    rendered_block_roles: list[str],
    template_id: str,
    reconstructed_from_framing: ProvenanceFraming | None,
    reconstructed_from_hint: CompositionHint | None,
    fresh_attempt_outcome: Any | None,
) -> dict[str, Any]:
    spec_payload = spec.to_dict()
    # Compatibility maps are source-keyed and therefore lossy when a source
    # intentionally renders multiple roles. They preserve the first rendered role;
    # source_role_entries is authoritative.
    source_role_map: dict[str, str] = {}
    source_digests: dict[str, str] = {}
    for summary in source_summaries:
        source_role_map.setdefault(summary.source.value, summary.role.value)
        source_digests.setdefault(summary.source.value, summary.content_digest)
    source_role_entries = [
        {
            "source": summary.source.value,
            "role": summary.role.value,
            "digest": summary.content_digest,
        }
        for summary in source_summaries
    ]
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
        "source_role_map": source_role_map,
        "source_digests": source_digests,
        "source_role_entries": source_role_entries,
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
        "rendered_block_roles": rendered_block_roles,
        "template_id": template_id,
        "template_version_hash": TEMPLATE_VERSION_HASH,
        "reconstructed_from_framing": (
            reconstructed_from_framing.value if reconstructed_from_framing else None
        ),
        "reconstructed_from_hint": (
            reconstructed_from_hint.value if reconstructed_from_hint else None
        ),
        "fresh_attempt_outcome": (
            fresh_attempt_outcome.value
            if hasattr(fresh_attempt_outcome, "value")
            else fresh_attempt_outcome
        ),
        "mismatch_reason": ProvenanceAuditMismatchReason.NONE.value,
        "refusal_reason": None,
    }


def _assistant_text_metadata(envelope: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "spec_digest",
        "schema_version",
        "utterance_digest",
        "surface",
        "timestamp",
        "provenance_framing",
        "source_role_map",
        "source_role_entries",
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


def _digest_json(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _digest_text(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode()).hexdigest()


def _refuse_template_mismatch(detail: str) -> None:
    raise DispatcherSpecRefused(
        DispatcherRefusalReason.PROVENANCE_TEMPLATE_MISMATCH,
        detail,
    )
