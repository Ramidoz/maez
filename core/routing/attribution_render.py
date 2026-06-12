"""Post-audit natural rendering for Search-as-a-Sense.

Audits consume the marked draft first. This module only runs at the final
reply boundary: retain the marked draft for /receipts, then render the owner
facing string naturally.
"""
from __future__ import annotations

import re
from collections import OrderedDict

from core.search.sense_flag import sense_enabled

_CITE_RE = re.compile(r"\s*\[E(\d+)\]")
_WEB_SUFFIX = "\n\n-- I looked at the live web for this (ask /receipts for sources)."

_RECEIPTS: "OrderedDict[str, dict]" = OrderedDict()
_MAX_RECEIPTS = 16

_TURN_EVIDENCE: dict[str, dict] = {}
_EMPTY_TURN = {"web_present": False, "sources": [], "observation": None}


def render_natural(marked_draft, *, web_evidence_present: bool):
    if not sense_enabled():
        return marked_draft
    try:
        if not isinstance(marked_draft, str) or not marked_draft:
            return marked_draft
        out = _CITE_RE.sub("", marked_draft)
        out = re.sub(r"[ \t]{2,}", " ", out)
        out = re.sub(r" +([.,;:!?])", r"\1", out).strip()
        if web_evidence_present:
            out = out + _WEB_SUFFIX
        return out
    except Exception:
        return marked_draft


def retain_receipt(chat_id: str, *, marked: str, sources: list[str]) -> None:
    try:
        key = str(chat_id)
        _RECEIPTS[key] = {"marked": marked, "sources": list(sources or [])}
        _RECEIPTS.move_to_end(key)
        while len(_RECEIPTS) > _MAX_RECEIPTS:
            _RECEIPTS.popitem(last=False)
    except Exception:
        pass


def last_receipt(chat_id: str):
    return _RECEIPTS.get(str(chat_id))


def receipts_reply(chat_id: str) -> str:
    receipt = last_receipt(chat_id)
    if receipt is None:
        return "No receipts retained for the last reply."
    lines = [receipt["marked"], ""]
    if receipt["sources"]:
        lines.append("Sources:")
        lines.extend(f"- {url}" for url in receipt["sources"][:5])
    return "\n".join(lines)[:3900]


def stash_turn_evidence(chat_id, *, rendered_turn, evidence_texts, observation) -> None:
    try:
        from core.intake_bus.world_observation_lane import extract_source_urls

        web_present = any(
            str(getattr(getattr(summary, "source", None), "value", getattr(summary, "source", "")))
            == "WEB_SEARCH"
            for summary in (getattr(rendered_turn, "source_summaries", None) or [])
        )
        _TURN_EVIDENCE[str(chat_id or "")] = {
            "web_present": web_present,
            "sources": extract_source_urls(evidence_texts or []),
            "observation": observation,
        }
        while len(_TURN_EVIDENCE) > 8:
            _TURN_EVIDENCE.pop(next(iter(_TURN_EVIDENCE)))
    except Exception:
        pass


def pop_turn_evidence(chat_id) -> dict:
    return _TURN_EVIDENCE.pop(str(chat_id or ""), dict(_EMPTY_TURN))
