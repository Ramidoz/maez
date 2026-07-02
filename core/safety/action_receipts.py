"""Typed action receipts for claim/receipt reconciliation.

These helpers are deliberately content-light. They expose the action type and
coarse outcome needed to ground a reply claim without carrying snippets, URLs,
or reply text into telemetry.
"""
from __future__ import annotations

from typing import Iterable

ACTION_WEB_SEARCH = "web_search"


def _safe_query(value: object, *, limit: int = 120) -> str:
    text = " ".join(str(value or "").split())
    return text[:limit]


def _result_count(result: dict) -> int:
    try:
        return int(result.get("result_count", 0) or 0)
    except (TypeError, ValueError):
        return 0


def build_search_tool_result(*, query: str, result: dict, source: str) -> dict:
    """Return a typed evidence-envelope ``tool_results`` entry for search."""
    count = _result_count(result)
    success = bool(result.get("success"))
    status = "ok" if success and count > 0 else "empty" if success else "failed"
    backend = str(result.get("source") or result.get("source_type") or "web")
    summary = f"web_search {status} result_count={count} backend={backend}"
    return {
        "name": ACTION_WEB_SEARCH,
        "tool": ACTION_WEB_SEARCH,
        "action_type": ACTION_WEB_SEARCH,
        "status": status,
        "summary": summary,
        "query": _safe_query(query),
        "result_count": count,
        "backend": backend,
        "source": source,
    }


def iter_action_receipts(evidence_envelope: dict | None) -> Iterable[dict]:
    if not isinstance(evidence_envelope, dict):
        return ()
    tool_results = evidence_envelope.get("tool_results") or []
    if not isinstance(tool_results, list):
        return ()
    return (receipt for receipt in tool_results if isinstance(receipt, dict))


def has_action_receipt(evidence_envelope: dict | None, action_type: str) -> bool:
    """True iff the envelope has a type-matched receipt for ``action_type``."""
    for receipt in iter_action_receipts(evidence_envelope):
        if (
            receipt.get("action_type") == action_type
            or receipt.get("tool") == action_type
            or receipt.get("name") == action_type
        ):
            return True
    return False
