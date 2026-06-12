"""World-observation lane — the Search-as-a-Sense metabolism.

One bounded observation per evidence-admitted search, through the intake bus.
The record claims exactly what it proves: web evidence entered the synthesis
context. It does not claim Maez used that evidence in a final sentence.
"""
from __future__ import annotations

import hashlib
import logging
import re
import time

from core.intake_bus.admit import admit
from core.intake_bus.contract import IntakeFact, PromotionPosture
from core.search.sense_flag import sense_enabled
from memory.memory_manager import ProvenanceSource

logger = logging.getLogger("maez")

# This is validated by core.intake_bus.admit against core.egress.gate.KNOWN_ORIGINS.
# "sovereign_local_search" is a receipt egress class, not a memory-origin class.
WORLD_OBSERVATION_EGRESS = "tool_result_public"

_MAX_ROWS = 3
_URL_RE = re.compile(r"https?://[^\s\)\]]+")


class _SingleFactAdapter:
    """Minimal StoreAdapter: one pending fact, admitted synchronously."""

    def __init__(self, fact: IntakeFact):
        self._fact = fact
        self.admitted_body_id: str | None = None

    def oldest_pending(self):
        return self._fact

    def mark_admitted(self, source_ref: str, *, body_memory_id: str) -> None:
        self.admitted_body_id = body_memory_id
        self._fact = None


def _has_web_search(values) -> bool:
    return any(str(getattr(v, "value", v)) == "WEB_SEARCH" for v in (values or ()))


def _summaries_include_web(summaries) -> bool:
    for summary in summaries or ():
        source = getattr(summary, "source", None)
        if str(getattr(source, "value", source)) == "WEB_SEARCH":
            return True
    return False


def _outcome_ok(outcome) -> bool:
    return str(getattr(outcome, "value", outcome)) in {"ALL_SUCCEEDED", "PARTIAL"}


def extract_source_urls(evidence_texts: list[str], cap: int = 5) -> list[str]:
    """Extract distinct URLs from FreshBlock.text evidence."""
    seen: list[str] = []
    for text in evidence_texts or ():
        for url in _URL_RE.findall(text or ""):
            if url not in seen:
                seen.append(url)
            if len(seen) >= cap:
                return seen
    return seen


def build_observation_content(query: str, evidence_texts: list[str]) -> str:
    """Build a bounded structural digest from the actual evidence text."""
    lines = [
        f"Web observation — web evidence entered the synthesis context for: {(query or '')[:200]}",
    ]
    for text in (evidence_texts or [])[:_MAX_ROWS]:
        excerpt = " ".join((text or "").split())[:600]
        if excerpt:
            lines.append(f"- {excerpt}")
    lines.append(f"observed_at: {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}")
    return "\n".join(lines)


def evaluate_write_condition(rendered_turn) -> bool:
    """Pure three-leg condition: web requested, web summarized, web succeeded."""
    try:
        spec = getattr(rendered_turn, "effective_spec", None)
        return (
            _has_web_search(getattr(spec, "external_sources", None))
            and _summaries_include_web(getattr(rendered_turn, "source_summaries", None))
            and _outcome_ok(getattr(rendered_turn, "fresh_attempt_outcome", None))
        )
    except Exception:
        return False


def write_world_observation(
    memory,
    *,
    query: str,
    evidence_texts: list[str],
    diagnostic_id: str,
) -> str:
    """Write one intake-bus observation; never raise into the caller."""
    if not sense_enabled():
        return "disabled"
    try:
        qhash = hashlib.sha256((query or "").encode("utf-8")).hexdigest()[:12]
        fact = IntakeFact(
            source_kind="world_observation",
            source_ref=f"web_search:{diagnostic_id}:{qhash}",
            content=build_observation_content(query, evidence_texts),
            provenance_source=ProvenanceSource.EXTERNAL_WEB,
            egress_origin_class=WORLD_OBSERVATION_EGRESS,
            promotion_posture=PromotionPosture.ADMIT_TO_BODY,
            fetch_batch_id=str(diagnostic_id),
            metadata={"lane": "world_observation", "query_hash": qhash},
        )
        outcome = admit(_SingleFactAdapter(fact), memory)
        logger.info(
            "world_observation lane: %s ref=%s",
            outcome.status,
            outcome.source_ref,
        )
        return outcome.status if outcome.status != "nothing_pending" else "skipped"
    except Exception as exc:
        logger.warning("world_observation lane dropped: %s", exc)
        return "error_dropped"
