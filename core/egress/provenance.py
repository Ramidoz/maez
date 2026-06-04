from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from core.egress.gate import (
    EgressSegment,
    INTENTIONAL_OUTBOUND,
    KNOWN_ORIGINS,
    MINIMIZABLE_PRIVATE_CONTEXT,
    NON_PRIVATE,
    RESERVED_DENIED_RAW,
    UNTRUSTED_EXTERNAL_OUTPUT,
)


_RESTRICTIVENESS = {
    **{origin: 3 for origin in RESERVED_DENIED_RAW},
    **{origin: 2 for origin in MINIMIZABLE_PRIVATE_CONTEXT},
    **{origin: 2 for origin in UNTRUSTED_EXTERNAL_OUTPUT},
    **{origin: 1 for origin in INTENTIONAL_OUTBOUND},
    **{origin: 0 for origin in NON_PRIVATE},
    "unclassified": 4,
}


@dataclass(frozen=True)
class ProvenanceSpan:
    text: str
    origin_class: str
    source_ref: str
    redaction_allowed: bool

    def __post_init__(self) -> None:
        if self.origin_class not in KNOWN_ORIGINS:
            object.__setattr__(self, "origin_class", "unclassified")

    def to_egress_segment(self) -> EgressSegment:
        return EgressSegment(
            text=self.text,
            origin_class=self.origin_class,
            source_ref=self.source_ref,
            redaction_allowed=self.redaction_allowed,
        )

    def to_wire(self) -> dict:
        return {
            "text": self.text,
            "origin_class": self.origin_class,
            "source_ref": self.source_ref,
            "redaction_allowed": self.redaction_allowed,
        }

    @classmethod
    def from_wire(cls, payload: object) -> "ProvenanceSpan":
        if not isinstance(payload, dict):
            return cls(
                text="",
                origin_class="unclassified",
                source_ref="wire:invalid",
                redaction_allowed=False,
            )
        return cls(
            text=str(payload.get("text") or ""),
            origin_class=str(payload.get("origin_class") or "unclassified"),
            source_ref=str(payload.get("source_ref") or "wire:missing_source_ref"),
            redaction_allowed=bool(payload.get("redaction_allowed")),
        )


@dataclass(frozen=True)
class ProvenancedText:
    spans: tuple[ProvenanceSpan, ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "spans",
            tuple(span for span in self.spans if span.text),
        )

    @property
    def text(self) -> str:
        return "".join(span.text for span in self.spans)

    def __str__(self) -> str:
        return self.text

    def __bool__(self) -> bool:
        return bool(self.text)

    def __add__(self, other: "ProvenancedText") -> "ProvenancedText":
        return ProvenancedText(self.spans + other.spans)

    def to_wire(self) -> list[dict]:
        return [span.to_wire() for span in self.spans]

    def to_egress_segments(self) -> list[EgressSegment]:
        return [span.to_egress_segment() for span in self.spans]

    @classmethod
    def from_spans(cls, spans: Iterable[ProvenanceSpan]) -> "ProvenancedText":
        return cls(tuple(spans))

    @classmethod
    def from_wire(cls, payload: object) -> "ProvenancedText":
        if not isinstance(payload, list):
            return cls.from_raw_conservative("", source_ref="wire:invalid")
        return cls.from_spans(ProvenanceSpan.from_wire(item) for item in payload)

    @classmethod
    def from_raw_conservative(
        cls,
        text: str,
        *,
        source_ref: str,
    ) -> "ProvenancedText":
        return cls.from_spans([
            ProvenanceSpan(
                text=text,
                origin_class="unclassified",
                source_ref=source_ref,
                redaction_allowed=False,
            )
        ])

    @classmethod
    def public_fact(cls, text: str, *, source_ref: str) -> "ProvenancedText":
        return cls.from_spans([
            ProvenanceSpan(text, "public_fact", source_ref, False)
        ])

    @classmethod
    def weather_data(cls, text: str, *, source_ref: str) -> "ProvenancedText":
        return cls.from_spans([
            ProvenanceSpan(text, "weather_data", source_ref, False)
        ])

    @classmethod
    def system_bounded_query(
        cls,
        text: str,
        *,
        source_ref: str,
    ) -> "ProvenancedText":
        return cls.from_spans([
            ProvenanceSpan(text, "system_bounded_query", source_ref, False)
        ])

    @classmethod
    def tool_result_public(
        cls,
        text: str,
        *,
        source_ref: str,
    ) -> "ProvenancedText":
        return cls.from_spans([
            ProvenanceSpan(text, "tool_result_public", source_ref, False)
        ])

    @classmethod
    def memory(cls, text: str, *, source_ref: str) -> "ProvenancedText":
        return cls.from_spans([
            ProvenanceSpan(text, "memory", source_ref, True)
        ])

    @classmethod
    def lived_store(cls, text: str, *, source_ref: str) -> "ProvenancedText":
        return cls.from_spans([
            ProvenanceSpan(text, "lived_store", source_ref, True)
        ])

    @classmethod
    def owner_message_context(
        cls,
        text: str,
        *,
        source_ref: str,
    ) -> "ProvenancedText":
        return cls.from_spans([
            ProvenanceSpan(text, "owner_message_context", source_ref, True)
        ])

    @classmethod
    def owner_account_context(
        cls,
        text: str,
        *,
        source_ref: str,
    ) -> "ProvenancedText":
        # Personal-account-derived data (GitHub/Reddit/Gmail/...).
        # Categorical cloud-egress block by default; the gate ignores
        # redaction_allowed for this class, so fail closed here too.
        return cls.from_spans([
            ProvenanceSpan(text, "owner_account_context", source_ref, False)
        ])

    @classmethod
    def third_party_private_context(
        cls,
        text: str,
        *,
        source_ref: str,
    ) -> "ProvenancedText":
        return cls.from_spans([
            ProvenanceSpan(text, "third_party_private_context", source_ref, True)
        ])

    @classmethod
    def model_output(cls, text: str, *, source_ref: str) -> "ProvenancedText":
        return cls.from_spans([
            ProvenanceSpan(text, "model_output", source_ref, True)
        ])

    @classmethod
    def maez_authored_public_third_party_transport(
        cls,
        text: str,
        *,
        source_ref: str,
    ) -> "ProvenancedText":
        return cls.from_spans([
            ProvenanceSpan(
                text,
                "maez_authored_public_third_party_transport",
                source_ref,
                False,
            )
        ])

    @classmethod
    def maez_authored_owner_third_party_transport(
        cls,
        text: str,
        *,
        source_ref: str,
    ) -> "ProvenancedText":
        return cls.from_spans([
            ProvenanceSpan(
                text,
                "maez_authored_owner_third_party_transport",
                source_ref,
                False,
            )
        ])

    @classmethod
    def reserved_raw(
        cls,
        text: str,
        *,
        origin_class: str,
        source_ref: str,
    ) -> "ProvenancedText":
        if origin_class not in RESERVED_DENIED_RAW:
            origin_class = "unclassified"
        return cls.from_spans([
            ProvenanceSpan(text, origin_class, source_ref, False)
        ])

    @classmethod
    def blended_summary(
        cls,
        text: str,
        *,
        sources: Iterable["ProvenancedText"],
        source_ref: str,
    ) -> "ProvenancedText":
        origin = _most_restrictive_origin(
            span.origin_class
            for source in sources
            for span in source.spans
        )
        return cls.from_spans([
            ProvenanceSpan(
                text=text,
                origin_class=origin,
                source_ref=source_ref,
                redaction_allowed=(
                    origin in MINIMIZABLE_PRIVATE_CONTEXT
                    or origin in UNTRUSTED_EXTERNAL_OUTPUT
                ),
            )
        ])

    @classmethod
    def derived_output(
        cls,
        text: str,
        *,
        source: "ProvenancedText",
        source_ref: str,
    ) -> "ProvenancedText":
        origin = _most_restrictive_origin(span.origin_class for span in source.spans)
        return cls.from_spans([
            ProvenanceSpan(
                text=text,
                origin_class=origin,
                source_ref=source_ref,
                redaction_allowed=(
                    origin in MINIMIZABLE_PRIVATE_CONTEXT
                    or origin in UNTRUSTED_EXTERNAL_OUTPUT
                ),
            )
        ])


def _most_restrictive_origin(origins: Iterable[str]) -> str:
    best = "unclassified"
    best_score = _RESTRICTIVENESS[best]
    for origin in origins:
        score = _RESTRICTIVENESS.get(origin, _RESTRICTIVENESS["unclassified"])
        if score > best_score or best == "unclassified":
            best = origin if origin in KNOWN_ORIGINS else "unclassified"
            best_score = score
    return best
