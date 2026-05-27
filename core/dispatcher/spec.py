"""Closed CompositionSpec schema for ADR 0047.

This module is the first implementation seam for Decision 42 / ADR 0047:
closed vocabularies plus a serializable CompositionSpec that refuses malformed
or caller-shaped source verdicts before recall, fetch, or render can run.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


SCHEMA_VERSION = 1


class SubstrateSource(StrEnum):
    REDDIT_SOURCE = "REDDIT_SOURCE"
    TELEGRAM_TEMPORAL = "TELEGRAM_TEMPORAL"
    TELEGRAM_SEMANTIC = "TELEGRAM_SEMANTIC"
    WEB_FAST_TURNS = "WEB_FAST_TURNS"
    ENTITY_INDEX = "ENTITY_INDEX"
    LIVED_EPISODES = "LIVED_EPISODES"
    LIVED_GRAPH = "LIVED_GRAPH"
    PRIVATE_THOUGHTS = "PRIVATE_THOUGHTS"
    WONDERINGS = "WONDERINGS"
    SELF_DEV_REVIEWS = "SELF_DEV_REVIEWS"
    AUDIT_AND_FABRICATION = "AUDIT_AND_FABRICATION"
    SANDBOX_WITNESSES = "SANDBOX_WITNESSES"


class ExternalSource(StrEnum):
    WEB_SEARCH = "WEB_SEARCH"
    LIVE_REDDIT = "LIVE_REDDIT"
    FETCH_URL = "FETCH_URL"
    ARXIV_OR_PAPERCLIP = "ARXIV_OR_PAPERCLIP"
    FRONTIER_CONSULT = "FRONTIER_CONSULT"


class CompositionHint(StrEnum):
    SUBSTRATE_ONLY = "SUBSTRATE_ONLY"
    FRESH_ONLY = "FRESH_ONLY"
    PARALLEL = "PARALLEL"
    SUBSTRATE_THEN_FETCH_IF_STALE = "SUBSTRATE_THEN_FETCH_IF_STALE"
    FRESH_THEN_CONTEXTUALIZE = "FRESH_THEN_CONTEXTUALIZE"


class ProvenanceFraming(StrEnum):
    SUBSTRATE_ONLY_NO_FRESH_VALIDATION = "SUBSTRATE_ONLY_NO_FRESH_VALIDATION"
    SUBSTRATE_EVIDENCE_FRESH_CONTEXT = "SUBSTRATE_EVIDENCE_FRESH_CONTEXT"
    HYBRID_FRESH_VALIDATES_SUBSTRATE_CONTEXTUALIZES = (
        "HYBRID_FRESH_VALIDATES_SUBSTRATE_CONTEXTUALIZES"
    )
    FRESH_ATTEMPTED_UNAVAILABLE_SUBSTRATE_CONTEXT = (
        "FRESH_ATTEMPTED_UNAVAILABLE_SUBSTRATE_CONTEXT"
    )
    FRESH_ONLY = "FRESH_ONLY"


class InventoryWitness(StrEnum):
    PRESENT = "PRESENT"
    ABSENT = "ABSENT"
    UNKNOWN = "UNKNOWN"
    MIXED = "MIXED"


class SourceAvailability(StrEnum):
    EXECUTABLE_PRESENT = "EXECUTABLE_PRESENT"
    EXECUTABLE_ABSENT = "EXECUTABLE_ABSENT"
    EXECUTABLE_UNKNOWN = "EXECUTABLE_UNKNOWN"
    RESERVED_UNAVAILABLE = "RESERVED_UNAVAILABLE"
    PRIVACY_GATED = "PRIVACY_GATED"
    TRUST_SCOPE_RESTRICTED = "TRUST_SCOPE_RESTRICTED"
    TIMED_OUT = "TIMED_OUT"
    ERROR = "ERROR"


class AvailabilityLimitation(StrEnum):
    NO_RELEVANT_SUBSTRATE = "NO_RELEVANT_SUBSTRATE"
    INVENTORY_UNKNOWN = "INVENTORY_UNKNOWN"
    RESERVED_SOURCE_UNAVAILABLE = "RESERVED_SOURCE_UNAVAILABLE"
    TRUST_SCOPE_RESTRICTED = "TRUST_SCOPE_RESTRICTED"
    PRIVACY_GATED = "PRIVACY_GATED"
    FRESH_ATTEMPT_FAILED = "FRESH_ATTEMPT_FAILED"
    FETCH_BUDGET_EXHAUSTED = "FETCH_BUDGET_EXHAUSTED"
    SOURCE_TIMEOUT = "SOURCE_TIMEOUT"
    SCOPE_UNION_UNAVAILABLE = "SCOPE_UNION_UNAVAILABLE"
    SCORING_LOW_CONFIDENCE = "SCORING_LOW_CONFIDENCE"


class DispatcherRefusalReason(StrEnum):
    UNKNOWN_CLOSED_VOCABULARY_VALUE = "UNKNOWN_CLOSED_VOCABULARY_VALUE"
    INCOHERENT_HINT_FRAMING_PAIR = "INCOHERENT_HINT_FRAMING_PAIR"
    CALLER_SUPPLIED_COMPOSITION_VERDICT = "CALLER_SUPPLIED_COMPOSITION_VERDICT"
    CALLER_SUPPLIED_SOURCE_SELECTION = "CALLER_SUPPLIED_SOURCE_SELECTION"
    RESERVED_SOURCE_EXECUTION_ATTEMPTED = "RESERVED_SOURCE_EXECUTION_ATTEMPTED"
    FRONTIER_CONSULT_WITHOUT_CAPABILITY_GRANT = "FRONTIER_CONSULT_WITHOUT_CAPABILITY_GRANT"
    REPAIR_PRIOR_SPEC_INVALID = "REPAIR_PRIOR_SPEC_INVALID"
    SCHEMA_VERSION_UNSUPPORTED = "SCHEMA_VERSION_UNSUPPORTED"
    PROVENANCE_TEMPLATE_MISMATCH = "PROVENANCE_TEMPLATE_MISMATCH"


class ProvenanceAuditMismatchReason(StrEnum):
    NONE = "NONE"
    TEMPLATE_FRAMING_MISMATCH = "TEMPLATE_FRAMING_MISMATCH"
    SOURCE_ROLE_MAP_MISMATCH = "SOURCE_ROLE_MAP_MISMATCH"
    RENDERED_BLOCK_ROLE_MISMATCH = "RENDERED_BLOCK_ROLE_MISMATCH"
    UNSUPPORTED_PROVENANCE_FRAMING = "UNSUPPORTED_PROVENANCE_FRAMING"
    UNEXPECTED_FRESH_CLAIM = "UNEXPECTED_FRESH_CLAIM"
    UNEXPECTED_SUBSTRATE_CLAIM = "UNEXPECTED_SUBSTRATE_CLAIM"
    MISSING_REQUIRED_SOURCE_LABEL = "MISSING_REQUIRED_SOURCE_LABEL"
    AUDIT_ENVELOPE_SCHEMA_MISMATCH = "AUDIT_ENVELOPE_SCHEMA_MISMATCH"


SourceLabel = SubstrateSource | ExternalSource


_LEGAL_HINT_FRAMING: dict[CompositionHint, frozenset[ProvenanceFraming]] = {
    CompositionHint.SUBSTRATE_ONLY: frozenset(
        {
            ProvenanceFraming.SUBSTRATE_ONLY_NO_FRESH_VALIDATION,
            ProvenanceFraming.SUBSTRATE_EVIDENCE_FRESH_CONTEXT,
        }
    ),
    CompositionHint.FRESH_ONLY: frozenset({ProvenanceFraming.FRESH_ONLY}),
    CompositionHint.PARALLEL: frozenset(
        {
            ProvenanceFraming.HYBRID_FRESH_VALIDATES_SUBSTRATE_CONTEXTUALIZES,
            ProvenanceFraming.SUBSTRATE_EVIDENCE_FRESH_CONTEXT,
        }
    ),
    CompositionHint.SUBSTRATE_THEN_FETCH_IF_STALE: frozenset(
        {
            ProvenanceFraming.HYBRID_FRESH_VALIDATES_SUBSTRATE_CONTEXTUALIZES,
            ProvenanceFraming.SUBSTRATE_ONLY_NO_FRESH_VALIDATION,
            ProvenanceFraming.FRESH_ATTEMPTED_UNAVAILABLE_SUBSTRATE_CONTEXT,
        }
    ),
    CompositionHint.FRESH_THEN_CONTEXTUALIZE: frozenset(
        {
            ProvenanceFraming.HYBRID_FRESH_VALIDATES_SUBSTRATE_CONTEXTUALIZES,
            ProvenanceFraming.FRESH_ATTEMPTED_UNAVAILABLE_SUBSTRATE_CONTEXT,
        }
    ),
}


class DispatcherSpecRefused(ValueError):
    def __init__(self, reason: DispatcherRefusalReason, detail: str = "") -> None:
        self.reason = reason
        self.detail = detail
        message = reason.value if not detail else f"{reason.value}: {detail}"
        super().__init__(message)


def _refuse(reason: DispatcherRefusalReason, detail: str = "") -> None:
    raise DispatcherSpecRefused(reason, detail)


def _coerce_enum(enum_cls: type[StrEnum], value: Any) -> StrEnum:
    if isinstance(value, enum_cls):
        return value
    if isinstance(value, str):
        try:
            return enum_cls(value)
        except ValueError:
            _refuse(
                DispatcherRefusalReason.UNKNOWN_CLOSED_VOCABULARY_VALUE,
                f"{enum_cls.__name__}.{value}",
            )
    _refuse(
        DispatcherRefusalReason.UNKNOWN_CLOSED_VOCABULARY_VALUE,
        f"{enum_cls.__name__}.{value!r}",
    )


def _coerce_source_label(value: Any) -> SourceLabel:
    if isinstance(value, SubstrateSource | ExternalSource):
        return value
    if isinstance(value, str):
        for enum_cls in (SubstrateSource, ExternalSource):
            try:
                return enum_cls(value)
            except ValueError:
                continue
    _refuse(
        DispatcherRefusalReason.UNKNOWN_CLOSED_VOCABULARY_VALUE,
        f"SourceLabel.{value!r}",
    )


def _coerce_enum_list(enum_cls: type[StrEnum], values: Any) -> tuple[StrEnum, ...]:
    if not isinstance(values, list | tuple):
        _refuse(
            DispatcherRefusalReason.UNKNOWN_CLOSED_VOCABULARY_VALUE,
            f"{enum_cls.__name__} list expected",
        )
    return tuple(_coerce_enum(enum_cls, value) for value in values)


def _coerce_availability_map(values: Any) -> dict[SourceLabel, SourceAvailability]:
    if not isinstance(values, dict):
        _refuse(
            DispatcherRefusalReason.CALLER_SUPPLIED_SOURCE_SELECTION,
            "source_availability must be a mapping",
        )
    coerced: dict[SourceLabel, SourceAvailability] = {}
    for key, value in values.items():
        source = _coerce_source_label(key)
        coerced[source] = _coerce_enum(SourceAvailability, value)  # type: ignore[assignment]
    return coerced


@dataclass(frozen=True)
class CompositionSpec:
    substrate_sources: list[SubstrateSource]
    external_sources: list[ExternalSource]
    composition_hint: CompositionHint
    provenance_framing: ProvenanceFraming
    inventory_witness: InventoryWitness
    source_availability: dict[SourceLabel, SourceAvailability]
    availability_limitations: list[AvailabilityLimitation]
    freshness_window: dict[str, Any] | None
    trust_scope_union: dict[str, Any] | None
    schema_version: int = SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            _refuse(
                DispatcherRefusalReason.SCHEMA_VERSION_UNSUPPORTED,
                f"schema_version={self.schema_version}",
            )

        object.__setattr__(
            self,
            "substrate_sources",
            list(_coerce_enum_list(SubstrateSource, self.substrate_sources)),
        )
        object.__setattr__(
            self,
            "external_sources",
            list(_coerce_enum_list(ExternalSource, self.external_sources)),
        )
        object.__setattr__(
            self,
            "composition_hint",
            _coerce_enum(CompositionHint, self.composition_hint),
        )
        object.__setattr__(
            self,
            "provenance_framing",
            _coerce_enum(ProvenanceFraming, self.provenance_framing),
        )
        object.__setattr__(
            self,
            "inventory_witness",
            _coerce_enum(InventoryWitness, self.inventory_witness),
        )
        object.__setattr__(
            self,
            "source_availability",
            _coerce_availability_map(self.source_availability),
        )
        object.__setattr__(
            self,
            "availability_limitations",
            list(_coerce_enum_list(AvailabilityLimitation, self.availability_limitations)),
        )

        if self.provenance_framing not in _LEGAL_HINT_FRAMING[self.composition_hint]:
            _refuse(
                DispatcherRefusalReason.INCOHERENT_HINT_FRAMING_PAIR,
                f"{self.composition_hint.value} x {self.provenance_framing.value}",
            )

        selected_sources = set(self.substrate_sources) | set(self.external_sources)
        missing = sorted(
            source.value
            for source in selected_sources
            if source not in self.source_availability
        )
        if missing:
            _refuse(
                DispatcherRefusalReason.CALLER_SUPPLIED_SOURCE_SELECTION,
                f"missing availability for {', '.join(missing)}",
            )

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "CompositionSpec":
        version = payload.get("schema_version", SCHEMA_VERSION)
        return cls(
            schema_version=version,
            substrate_sources=payload["substrate_sources"],
            external_sources=payload["external_sources"],
            composition_hint=payload["composition_hint"],
            provenance_framing=payload["provenance_framing"],
            inventory_witness=payload["inventory_witness"],
            source_availability=payload["source_availability"],
            availability_limitations=payload["availability_limitations"],
            freshness_window=payload.get("freshness_window"),
            trust_scope_union=payload.get("trust_scope_union"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "substrate_sources": [source.value for source in self.substrate_sources],
            "external_sources": [source.value for source in self.external_sources],
            "composition_hint": self.composition_hint.value,
            "provenance_framing": self.provenance_framing.value,
            "inventory_witness": self.inventory_witness.value,
            "source_availability": {
                source.value: availability.value
                for source, availability in sorted(
                    self.source_availability.items(),
                    key=lambda item: item[0].value,
                )
            },
            "availability_limitations": [
                limitation.value for limitation in self.availability_limitations
            ],
            "freshness_window": self.freshness_window,
            "trust_scope_union": self.trust_scope_union,
        }

