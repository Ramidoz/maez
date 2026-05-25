from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Callable
from urllib.parse import quote

from core.egress import external_fetch
from core.policies.exceptions import CrossBondAccessError
from core.policies.third_party_subject_gate import (
    SubjectKind,
    enforce_subject_boundary,
)


DiagnosticSink = Callable[[dict], None]


@dataclass(frozen=True)
class ProvenancedQuery:
    bond_id: str
    query_text: str
    subject_kind: SubjectKind | str
    subject_ref: str | None = None
    provider_hint: str | None = None


def _digest(value: str | None) -> str | None:
    if not value:
        return None
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def _provider_url_for_query(query: ProvenancedQuery) -> str:
    encoded = quote(query.query_text.strip(), safe="")
    return f"https://www.google.com/search?q={encoded}"


def _emit_cross_bond_refusal(
    *,
    requested_bond_id: str,
    query: ProvenancedQuery,
    diagnostic_sink: DiagnosticSink | None,
) -> None:
    if diagnostic_sink is None:
        return
    diagnostic_sink(
        {
            "event_type": "CROSS_BOND_ACCESS_REFUSED",
            "requested_bond_digest": _digest(requested_bond_id),
            "query_bond_digest": _digest(query.bond_id),
            "surface": "fetch_for_curiosity",
        }
    )


def fetch_for_curiosity(
    *,
    bond_id: str,
    query: ProvenancedQuery,
    request_id: str | None = None,
    diagnostic_sink: DiagnosticSink | None = None,
):
    if query.bond_id != bond_id:
        _emit_cross_bond_refusal(
            requested_bond_id=bond_id,
            query=query,
            diagnostic_sink=diagnostic_sink,
        )
        raise CrossBondAccessError("query bond_id does not match requested bond")
    enforce_subject_boundary(query, diagnostic_sink=diagnostic_sink)
    return external_fetch.fetch_text(
        fetch_type="web_search",
        url=_provider_url_for_query(query),
        caller="curiosity_probe",
        request_id=request_id,
    )
