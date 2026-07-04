# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Instrument-only narrative weave proposals.

The weave is an instrument, not an author: MiniLM may propose that two
episodes look close, but durable history changes only when a later receipt
creates the same thread under the universal joinability rule.
"""

from __future__ import annotations

import ast
from itertools import combinations
from math import sqrt
from typing import Any, Sequence

from .narrative import (
    DETECTOR_VERSION,
    LinkCandidate,
    NarrativeStore,
    classify_citation,
)

# Conservative named threshold for L1 suspicion only. It creates proposals,
# never durable links; reality must later confirm them with joinable receipts.
WEAVE_DISTANCE_THRESHOLD = 0.18
WEAVE_DETECTOR_VERSION = "weave:v0"


def _embedder_id(encoder: Any) -> str:
    return f"{getattr(encoder, 'model', 'unknown')}:{getattr(encoder, 'dimension', 'unknown')}"


def _episode_text(episode: dict) -> str:
    return str(episode.get("summary") or episode.get("title") or "").strip()


def _episode_id(episode: dict) -> str:
    return str(episode.get("id") or "").strip()


def _cosine_distance(left: list[float], right: list[float]) -> float | None:
    dot = sum(float(a) * float(b) for a, b in zip(left, right, strict=False))
    left_norm = sqrt(sum(float(a) * float(a) for a in left))
    right_norm = sqrt(sum(float(b) * float(b) for b in right))
    if left_norm == 0.0 or right_norm == 0.0:
        return None
    return 1.0 - (dot / (left_norm * right_norm))


def _linked_or_pending(store: NarrativeStore, ep_a: str, ep_b: str) -> bool:
    endpoints = {ep_a, ep_b}
    for link in store.links_for(ep_a):
        if link.get("link_type") != "same_thread":
            continue
        if {str(link.get("from_episode_id")), str(link.get("to_episode_id"))} == endpoints:
            return True
    for proposal in store.pending_proposals():
        if {str(proposal["ep_a"]), str(proposal["ep_b"])} == endpoints:
            return True
    return False


def _connected_after_candidate(
    store: NarrativeStore,
    *,
    left: str,
    right: str,
    candidate: LinkCandidate,
) -> bool:
    parent: dict[str, str] = {}

    def find(value: str) -> str:
        parent.setdefault(value, value)
        while parent[value] != value:
            parent[value] = parent[parent[value]]
            value = parent[value]
        return value

    def union(a: str, b: str) -> None:
        root_a, root_b = find(a), find(b)
        if root_a != root_b:
            parent[root_b] = root_a

    for thread in store.threads():
        if len(thread) < 2:
            continue
        first = thread[0]
        for item in thread[1:]:
            union(first, item)
    before = find(left) == find(right)
    union(candidate.from_id, candidate.to_id)
    return not before and find(left) == find(right)


def propose_same_story_candidates(
    episodes: Sequence[dict],
    store: NarrativeStore,
    *,
    encoder: Any | None = None,
    distance_threshold: float = WEAVE_DISTANCE_THRESHOLD,
) -> int:
    """Write same_story proposals for close, unlinked episode pairs."""

    if encoder is None:
        from memory.embedder import get_encoder

        encoder = get_encoder()
    embedder_id = _embedder_id(encoder)
    vectors: dict[str, list[float]] = {}
    texts: dict[str, str] = {}
    for episode in episodes:
        episode_id = _episode_id(episode)
        text = _episode_text(episode)
        if not episode_id or not text:
            continue
        texts[episode_id] = text
        vectors[episode_id] = encoder.encode(text)

    written = 0
    for ep_a, ep_b in combinations(sorted(texts), 2):
        if _linked_or_pending(store, ep_a, ep_b):
            continue
        distance = _cosine_distance(vectors[ep_a], vectors[ep_b])
        if distance is None or distance >= distance_threshold:
            continue
        store.add_proposal(
            kind="same_story",
            ep_a=ep_a,
            ep_b=ep_b,
            embedder_id=embedder_id,
            distance=distance,
        )
        written += 1
    return written


def _joinable_confirmation(candidate: LinkCandidate) -> bool:
    if candidate.link_type != "same_thread":
        return False
    if candidate.trust != "derived":
        return False
    return all(
        classify_citation(evidence_id) in {"raw_uuid", "receipt_store", "followup", "exhibit"}
        for evidence_id in candidate.evidence_ids
    )


def promote_confirmed_same_thread(
    store: NarrativeStore,
    candidate: LinkCandidate,
) -> int:
    """Promote matching same_story proposals when real receipts confirm them."""

    if not _joinable_confirmation(candidate):
        return 0
    endpoints = {candidate.from_id, candidate.to_id}
    promoted = 0
    for proposal in store.pending_proposals():
        ep_a = str(proposal["ep_a"])
        ep_b = str(proposal["ep_b"])
        direct_match = {ep_a, ep_b} == endpoints
        thread_match = _connected_after_candidate(
            store,
            left=ep_a,
            right=ep_b,
            candidate=candidate,
        )
        if not (direct_match or thread_match):
            continue
        link_id = store.upsert_link(
            link_type="same_thread",
            from_episode_id=candidate.from_id,
            to_episode_id=candidate.to_id,
            trust="confirmed",
            evidence_ids=candidate.evidence_ids,
            detector_version=DETECTOR_VERSION,
        )
        store.upsert_link(
            link_type="same_thread",
            from_episode_id=candidate.from_id,
            to_episode_id=candidate.to_id,
            trust="confirmed",
            evidence_ids=[f"proposal:{proposal['proposal_id']}"],
            detector_version=WEAVE_DETECTOR_VERSION,
        )
        store.promote_proposal(str(proposal["proposal_id"]), promoted_link_id=link_id)
        promoted += 1
    return promoted


def assert_no_llm_in_weave_source(source: str) -> None:
    """Structural guard: L1 weave may use instruments, never an LLM path."""

    tree = ast.parse(source)
    offenders: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = []
            if isinstance(node, ast.ImportFrom):
                names.append(node.module or "")
            names.extend(alias.name for alias in node.names)
            if any("llm_client" in name or name.endswith(".chat") for name in names):
                offenders.append(f"import:{getattr(node, 'lineno', '?')}")
        elif isinstance(node, ast.Call):
            fn = node.func
            if isinstance(fn, ast.Attribute) and fn.attr == "chat":
                offenders.append(f"chat:{getattr(node, 'lineno', '?')}")
            elif isinstance(fn, ast.Name) and fn.id == "chat":
                offenders.append(f"chat:{getattr(node, 'lineno', '?')}")
    if offenders:
        raise AssertionError(f"LLM path is forbidden in narrative weave: {offenders}")
