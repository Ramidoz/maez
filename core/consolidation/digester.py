# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Bounded local-brain digestion for consolidation B2.

The digester has no durable side effects. It prepares a focused working set,
preflights the active endpoint before every model call, parses structured
output, and validates every proposed artifact through the B1 citation lock.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

from core import llm_client, model_config
from core.consolidation import citation_lock, skeleton
from core.ledger.taint_stamping import TAINT_LABEL_ORDER
from core.routing.brain_gateway import BrainPurpose
from core.routing.digestion_endpoint_guard import (
    DigestionEndpointLocality,
    check_digestion_endpoint_locality,
)

MAX_ROWS_PER_LLM_CALL = 80

_SYSTEM_PROMPT = (
    "You are Maez's local digestion mechanism. Report only observable "
    "patterns tied to cited ledger rows. Do not grade, rate, praise, shame, "
    "or compare Maez's value. Return one JSON object with keys "
    "episode_digest, row_citations, and wondering_candidates."
)


@dataclass(frozen=True)
class WonderingCandidateDigest:
    text: str
    row_citations: tuple[dict[str, Any], ...]
    taint_labels: tuple[str, ...]


@dataclass(frozen=True)
class DigestionResult:
    status: str
    episode_key: str
    episode_digest: str = ""
    row_citations: tuple[dict[str, Any], ...] = ()
    taint_labels: tuple[str, ...] = ()
    wondering_candidates: tuple[WonderingCandidateDigest, ...] = ()
    refusal_code: str | None = None
    refusal_detail: str = ""
    call_count: int = 0


def _reject(
    *,
    episode_key: str,
    status: str,
    refusal_code: str,
    refusal_detail: str = "",
    call_count: int = 0,
) -> DigestionResult:
    return DigestionResult(
        status=status,
        episode_key=episode_key,
        refusal_code=refusal_code,
        refusal_detail=refusal_detail,
        call_count=call_count,
    )


def _response_text(response: Any) -> str:
    message = getattr(response, "message", None)
    content = getattr(message, "content", None)
    if isinstance(content, str):
        return content
    if isinstance(response, str):
        return response
    return str(response)


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )


def _ordered_taints(labels: Iterable[str]) -> tuple[str, ...]:
    label_set = {label for label in labels if label in TAINT_LABEL_ORDER}
    return tuple(label for label in TAINT_LABEL_ORDER if label in label_set)


def _row_taints(row: Mapping[str, Any]) -> tuple[str, ...]:
    raw = row.get("taint_labels_json", "[]")
    try:
        labels = json.loads(raw if isinstance(raw, str) else "[]")
    except json.JSONDecodeError:
        labels = []
    return _ordered_taints(label for label in labels if isinstance(label, str))


def _taints_for_rows(rows: Iterable[Mapping[str, Any]]) -> tuple[str, ...]:
    labels: set[str] = set()
    for row in rows:
        labels.update(_row_taints(row))
    return _ordered_taints(labels)


def _clean_citation(value: Any) -> dict[str, Any] | None:
    if isinstance(value, str) and value.strip():
        return {"turn_id": value.strip()}
    if isinstance(value, Mapping):
        turn_id = value.get("turn_id")
        if isinstance(turn_id, str) and turn_id.strip():
            out: dict[str, Any] = {"turn_id": turn_id.strip()}
            if "chain_position" in value:
                out["chain_position"] = value["chain_position"]
            return out
    return None


def _clean_citations(value: Any) -> tuple[dict[str, Any], ...]:
    if not isinstance(value, list):
        return ()
    out: list[dict[str, Any]] = []
    for item in value:
        cleaned = _clean_citation(item)
        if cleaned is not None:
            out.append(cleaned)
    return tuple(out)


def _clean_candidate(value: Any) -> WonderingCandidateDigest | None:
    if not isinstance(value, Mapping):
        return None
    text = value.get("text")
    if not isinstance(text, str) or not text.strip():
        return None
    citations = _clean_citations(value.get("row_citations"))
    labels = value.get("taint_labels")
    if not isinstance(labels, list):
        labels = []
    return WonderingCandidateDigest(
        text=text.strip(),
        row_citations=citations,
        taint_labels=_ordered_taints(label for label in labels if isinstance(label, str)),
    )


def _parse_payload(text: str) -> tuple[str, tuple[dict[str, Any], ...], tuple[WonderingCandidateDigest, ...]]:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"digestion JSON parse failed: {exc}") from exc
    if not isinstance(payload, Mapping):
        raise ValueError("digestion payload must be a JSON object")
    digest = payload.get("episode_digest")
    if not isinstance(digest, str) or not digest.strip():
        raise ValueError("episode_digest must be a non-empty string")
    citations = _clean_citations(payload.get("row_citations"))
    candidates_raw = payload.get("wondering_candidates", [])
    if not isinstance(candidates_raw, list):
        raise ValueError("wondering_candidates must be a list")
    candidates = tuple(
        candidate
        for candidate in (_clean_candidate(item) for item in candidates_raw)
        if candidate is not None
    )
    return digest.strip(), citations, candidates


def _public_prompt_rows(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        if row.get("privacy_access") == "sealed_adjacent":
            continue
        out.append(
            {
                "turn_id": row.get("turn_id"),
                "chain_position": row.get("chain_position"),
                "timestamp": row.get("timestamp"),
                "turn_kind": row.get("turn_kind"),
                "surface": row.get("surface") or row.get("raw_surface"),
                "raw_text": row.get("raw_text"),
                "action_proposal_json": row.get("action_proposal_json"),
                "audit_verdict_json": row.get("audit_verdict_json"),
                "taint_labels_json": row.get("taint_labels_json"),
                "privacy_access": row.get("privacy_access"),
            }
        )
    return out


def _chunks(rows: list[dict[str, Any]], max_rows: int) -> list[list[dict[str, Any]]]:
    size = max(1, int(max_rows))
    return [rows[index:index + size] for index in range(0, len(rows), size)]


def _messages_for_chunk(*, episode_key: str, rows: list[dict[str, Any]]) -> list[dict[str, str]]:
    skel = skeleton.build(rows)
    content = (
        f"EPISODE_KEY: {episode_key}\n"
        "LEDGER_ROWS_JSON:\n"
        f"{_canonical_json(rows)}\n"
        "SKELETON_JSON:\n"
        f"{_canonical_json(asdict(skel))}\n"
        "Return JSON only."
    )
    return [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": content},
    ]


def _call_llm(
    llm_callable: Callable[..., Any],
    *,
    messages: list[dict[str, str]],
    model: str,
) -> str:
    response = llm_callable(
        model=model,
        messages=messages,
        stream=False,
        think=False,
        options=None,
        purpose=BrainPurpose.DIGESTION,
    )
    return _response_text(response)


def _forbidden_direct_chat_callable(llm_callable: Callable[..., Any]) -> bool:
    return llm_callable is getattr(llm_client, "chat_direct", None)


def _validate_digest_artifact(
    *,
    episode_key: str,
    digest_text: str,
    row_citations: tuple[dict[str, Any], ...],
    taint_labels: tuple[str, ...],
    span: Any,
    ledger_db_path: str | Path,
    call_count: int,
) -> DigestionResult | None:
    verdict = citation_lock.validate(
        {
            "episode_digest": digest_text,
            "row_citations": list(row_citations),
            "taint_labels": list(taint_labels),
        },
        span,
        ledger_db_path,
    )
    if verdict.ok:
        return None
    return _reject(
        episode_key=episode_key,
        status="refused",
        refusal_code=verdict.refusal_code or "citation_lock_refusal",
        refusal_detail=",".join(verdict.detail_codes),
        call_count=call_count,
    )


def _validate_wondering_candidate(
    *,
    episode_key: str,
    candidate: WonderingCandidateDigest,
    span: Any,
    ledger_db_path: str | Path,
    call_count: int,
) -> DigestionResult | None:
    verdict = citation_lock.validate(
        {
            "text": candidate.text,
            "row_citations": list(candidate.row_citations),
            "taint_labels": list(candidate.taint_labels),
        },
        span,
        ledger_db_path,
    )
    if verdict.ok:
        return None
    return _reject(
        episode_key=episode_key,
        status="refused",
        refusal_code=verdict.refusal_code or "citation_lock_refusal",
        refusal_detail=",".join(verdict.detail_codes),
        call_count=call_count,
    )


def digest_episode(
    episode: Any,
    *,
    rows: Iterable[Mapping[str, Any]],
    span: Any,
    ledger_db_path: str | Path,
    llm_callable: Callable[..., Any] | None = None,
    endpoint_guard: Callable[[], DigestionEndpointLocality] = check_digestion_endpoint_locality,
    max_rows_per_call: int = MAX_ROWS_PER_LLM_CALL,
    model: str | None = None,
) -> DigestionResult:
    """Digest one selected episode, returning only validated structured data."""
    episode_key = str(getattr(episode, "episode_key", "episode"))
    all_rows = [dict(row) for row in rows]
    prompt_rows = _public_prompt_rows(all_rows)
    if not prompt_rows:
        return _reject(
            episode_key=episode_key,
            status="refused",
            refusal_code="citations_empty",
            refusal_detail="episode has no public citable rows",
        )

    caller = llm_callable or llm_client.chat
    if _forbidden_direct_chat_callable(caller):
        return _reject(
            episode_key=episode_key,
            status="refused",
            refusal_code="direct_chat_forbidden",
        )
    model_name = model or model_config.PRIMARY_MODEL
    workset_taints = _taints_for_rows(all_rows)
    digests: list[str] = []
    all_citations: list[dict[str, Any]] = []
    candidates: list[WonderingCandidateDigest] = []
    call_count = 0

    for chunk in _chunks(prompt_rows, max_rows_per_call):
        locality = endpoint_guard()
        if not locality.allowed:
            return _reject(
                episode_key=episode_key,
                status="deferred",
                refusal_code=locality.refusal_code or "non_local_endpoint",
                refusal_detail=locality.reason,
                call_count=call_count,
            )
        call_count += 1
        try:
            response_text = _call_llm(
                caller,
                messages=_messages_for_chunk(episode_key=episode_key, rows=chunk),
                model=model_name,
            )
        except Exception as exc:
            return _reject(
                episode_key=episode_key,
                status="deferred",
                refusal_code="brain_unavailable",
                refusal_detail=str(exc),
                call_count=call_count,
            )
        try:
            digest_text, citations, proposed = _parse_payload(response_text)
        except Exception as exc:
            return _reject(
                episode_key=episode_key,
                status="deferred",
                refusal_code="digestion_parse_failure",
                refusal_detail=str(exc),
                call_count=call_count,
            )
        stamped_candidates = tuple(
            WonderingCandidateDigest(
                text=candidate.text,
                row_citations=candidate.row_citations,
                taint_labels=workset_taints,
            )
            for candidate in proposed
        )
        rejected = _validate_digest_artifact(
            episode_key=episode_key,
            digest_text=digest_text,
            row_citations=citations,
            taint_labels=workset_taints,
            span=span,
            ledger_db_path=ledger_db_path,
            call_count=call_count,
        )
        if rejected is not None:
            return rejected
        for candidate in stamped_candidates:
            rejected = _validate_wondering_candidate(
                episode_key=episode_key,
                candidate=candidate,
                span=span,
                ledger_db_path=ledger_db_path,
                call_count=call_count,
            )
            if rejected is not None:
                return rejected
        digests.append(digest_text)
        all_citations.extend(citations)
        candidates.extend(stamped_candidates)

    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for citation in all_citations:
        turn_id = str(citation.get("turn_id", ""))
        if turn_id and turn_id not in seen:
            seen.add(turn_id)
            deduped.append(citation)

    final_taints = workset_taints
    final_digest = "\n".join(digests)
    rejected = _validate_digest_artifact(
        episode_key=episode_key,
        digest_text=final_digest,
        row_citations=tuple(deduped),
        taint_labels=final_taints,
        span=span,
        ledger_db_path=ledger_db_path,
        call_count=call_count,
    )
    if rejected is not None:
        return rejected

    return DigestionResult(
        status="ok",
        episode_key=episode_key,
        episode_digest=final_digest,
        row_citations=tuple(deduped),
        taint_labels=final_taints,
        wondering_candidates=tuple(candidates),
        call_count=call_count,
    )
