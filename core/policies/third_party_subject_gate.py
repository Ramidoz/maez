from __future__ import annotations

import hashlib
from enum import Enum
from typing import Callable, Protocol

from core.policies.exceptions import SubjectBoundaryRefused


class SubjectKind(Enum):
    PUBLIC_TOPIC = "public_topic"
    OWNER_SELF = "owner_self"
    OWNER_BOND_RELATIONAL = "owner_bond_relational"
    SELF_MODEL = "self_model"
    NAMED_THIRD_PARTY = "named_third_party"
    UNKNOWN = "unknown"


class SubjectBoundaryQuery(Protocol):
    bond_id: str
    subject_kind: SubjectKind | str
    subject_ref: str | None


DiagnosticSink = Callable[[dict], None]


def _digest(value: str | None) -> str | None:
    if not value:
        return None
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def _coerce_subject_kind(value: SubjectKind | str) -> SubjectKind:
    if isinstance(value, SubjectKind):
        return value
    try:
        return SubjectKind(str(value))
    except ValueError:
        return SubjectKind.UNKNOWN


def _emit_refusal(
    *,
    query: SubjectBoundaryQuery,
    refusal_kind: str,
    diagnostic_sink: DiagnosticSink | None,
) -> None:
    if diagnostic_sink is None:
        return
    if getattr(diagnostic_sink, "accepts_raw_diagnostic_fields", False):
        diagnostic_sink(
            {
                "event_type": "SUBJECT_BOUNDARY_REFUSED",
                "refusal_kind": refusal_kind,
                "bond_id": query.bond_id,
                "subject_ref": query.subject_ref,
                "surface": "fetch_for_curiosity",
            }
        )
        return
    diagnostic_sink(
        {
            "event_type": "SUBJECT_BOUNDARY_REFUSED",
            "refusal_kind": refusal_kind,
            "bond_digest": _digest(query.bond_id),
            "subject_ref_digest": _digest(query.subject_ref),
            "surface": "fetch_for_curiosity",
        }
    )


def enforce_subject_boundary(
    query: SubjectBoundaryQuery,
    *,
    diagnostic_sink: DiagnosticSink | None = None,
) -> None:
    kind = _coerce_subject_kind(query.subject_kind)
    if kind is SubjectKind.UNKNOWN:
        _emit_refusal(
            query=query,
            refusal_kind="unknown_subject",
            diagnostic_sink=diagnostic_sink,
        )
        raise SubjectBoundaryRefused("UNKNOWN subject_kind refused")
    if kind is SubjectKind.NAMED_THIRD_PARTY:
        _emit_refusal(
            query=query,
            refusal_kind="named_third_party",
            diagnostic_sink=diagnostic_sink,
        )
        raise SubjectBoundaryRefused(
            "NAMED_THIRD_PARTY subject requires OWNER_EXPLICIT consent"
        )
