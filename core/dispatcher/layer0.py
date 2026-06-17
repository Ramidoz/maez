"""Layer 0 composition-spec emitter for ADR 0047.

Layer 0 learns the shape of an ask and emits a CompositionSpec. It does not
read substrate rows, fetch external data, render answers, or touch brain-loop
routing.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
import hashlib
import json
import math
import re
from pathlib import Path

from core.cognition.capability_card import evidence_precedence_enabled
from core.dispatcher.inventory import InventorySummary
from core.dispatcher.spec import (
    AvailabilityLimitation,
    CompositionHint,
    CompositionSpec,
    ExternalSource,
    InventoryWitness,
    ProvenanceFraming,
    SourceAvailability,
    SourceLabel,
    SubstrateSource,
)
from core.search.page_extract import extract_first_url
from core.search.sense_flag import page_read_enabled, sense_enabled
from memory.embedder import MiniLMEncoder, get_encoder


DEFAULT_ARCHETYPE_MANIFEST = (
    Path(__file__).resolve().parents[2]
    / "docs"
    / "roadmap"
    / "dispatcher-archetypes-v0-2026-05-26.md"
)
DEFAULT_ARCHETYPE_CACHE = (
    Path(__file__).resolve().parents[2] / "memory" / "dispatcher_archetype_cache.json"
)

MIN_ACCEPT = 0.62
DOMINANCE_MARGIN = 0.08
MULTI_MATCH_DELTA = 0.04
NO_MATCH_BELOW = 0.50

CLASS_ORDER = (
    "A_EXPLICIT_SUBSTRATE_RECALL",
    "B_EXPLICIT_LIVE_FETCH",
    "C_HYBRID_CONTENT_ANCHORED",
    "D_TEMPORAL_RECALL",
    "E_SOURCE_SHAPED_RECALL",
    "F_ENTITY_RECALL",
    "G_PROCEDURAL_RECALL",
    "H_REPAIR_FOLLOWUP",
    "I_CONTRADICTION_OR_SELF_CORRECTION",
    "J_AMBIENT_LIMB_STATE",
    "K_GRAPH_ASSISTED_RELATIONAL",
)

_LEGACY_CLASS_MAP = {
    "RECALL_FROM_SUBSTRATE": "A_EXPLICIT_SUBSTRATE_RECALL",
    "LIVE_FETCH": "B_EXPLICIT_LIVE_FETCH",
    "MEMORY_THEN_FRESHNESS": "C_HYBRID_CONTENT_ANCHORED",
    "TOOL_ACTION": "G_PROCEDURAL_RECALL",
    "SOURCE_ANCHORED": "E_SOURCE_SHAPED_RECALL",
    "TEMPORAL_ANCHORED": "D_TEMPORAL_RECALL",
    "ENTITY_ANCHORED": "F_ENTITY_RECALL",
    "PROCEDURAL": "G_PROCEDURAL_RECALL",
    "META": "J_AMBIENT_LIMB_STATE",
    "REPAIR_FOLLOWUP": "H_REPAIR_FOLLOWUP",
    "CONTRADICTION": "I_CONTRADICTION_OR_SELF_CORRECTION",
}

_DEFAULT_SUBSTRATE_FALLBACK = [
    SubstrateSource.TELEGRAM_SEMANTIC,
    SubstrateSource.ENTITY_INDEX,
    SubstrateSource.LIVED_EPISODES,
]

_EXPLICIT_FETCH_RE = re.compile(
    r"\b(search|google|look up|fetch|check the internet|go check)\b",
    re.IGNORECASE,
)
_EXPLICIT_MEMORY_RE = re.compile(
    r"\b(what do you remember|from memory|in your notebook|what's in your notebook)\b",
    re.IGNORECASE,
)
_CONTENT_ANCHOR_RE = re.compile(
    r"\b(qwen|reddit|online|local ?llama|telegram|github|calendar|project|status)\b",
    re.IGNORECASE,
)
_QUESTION_SHAPE_RE = re.compile(
    r"^\s*(what|who|when|where|why|how|is|are|do|does|did|can|could|should|has|have|tell me|any)\b|[?]",
    re.IGNORECASE,
)
_CURRENT_WORLD_MARKER_RE = re.compile(
    r"\b(latest|nowadays|current|recent|news|release|price|today)\b"
    r"|what(?:'s| is) (?:new|happening)",
    re.IGNORECASE,
)
_CONVERSATIONAL_TODAY_RE = re.compile(
    r"\b(how are you|how're you|how you doing|how are things|how is your day|how's your day)\b.*\btoday\b",
    re.IGNORECASE,
)
_SELF_CAPABILITY_RE = re.compile(
    r"\b(?:you|your|maez|yourself)\b.*\b(?:web search|search tools?|page read|page reading|"
    r"web sense|search sense|tools?|capabilit(?:y|ies))\b"
    r"|\b(?:web search|search tools?|page read|page reading|web sense|search sense|tools?|"
    r"capabilit(?:y|ies))\b.*\b(?:you|your|maez|yourself)\b",
    re.IGNORECASE,
)
_SELF_REF_RE = re.compile(r"\b(?:you|your|maez|yourself)\b", re.IGNORECASE)
_SELF_CAPABILITY_COMPLAINT_RE = re.compile(
    r"\b(?:unable|can't|cannot|can not|won't|fail(?:ed|ing|s)?|broken|useless)\b"
    r"|does(?:n't| not) work|don't work|not working"
    r"|\bkeep(?:s)?\b.{0,60}\b(?:wrong|fail(?:ed|ing|s)?)\b"
    r"|\bseem(?:s|ed)?\b.{0,40}\bunable\b",
    re.IGNORECASE,
)
# Generic Reddit talk selects the owned Reddit substrate.
_REDDIT_ANCHOR_RE = re.compile(r"\b(reddit|local ?llama|r/[A-Za-z0-9_]+)\b", re.IGNORECASE)
# A syntactically valid subreddit anchor additionally selects LIVE_REDDIT.
_SUBREDDIT_ANCHOR_RE = re.compile(r"\br/[A-Za-z0-9_][A-Za-z0-9_]{1,20}\b", re.IGNORECASE)


@dataclass(frozen=True)
class ScoringThresholds:
    min_accept: float = MIN_ACCEPT
    dominance_margin: float = DOMINANCE_MARGIN
    multi_match_delta: float = MULTI_MATCH_DELTA
    no_match_below: float = NO_MATCH_BELOW


@dataclass(frozen=True)
class Archetype:
    archetype_id: str
    class_id: str
    text: str


@dataclass(frozen=True)
class ArchetypeIndex:
    manifest_path: str
    manifest_hash: str
    encoder_model: str
    encoder_dimension: int
    archetypes: list[Archetype]
    embeddings: list[list[float]]


@dataclass(frozen=True)
class ClassScore:
    class_id: str
    score: float


def load_archetype_index(
    *,
    manifest_path: Path | str = DEFAULT_ARCHETYPE_MANIFEST,
    cache_path: Path | str | None = DEFAULT_ARCHETYPE_CACHE,
    encoder: MiniLMEncoder | None = None,
) -> ArchetypeIndex:
    manifest = Path(manifest_path)
    raw = manifest.read_text(encoding="utf-8")
    manifest_hash = _digest_text(raw)
    encoder = encoder or get_encoder()
    encoder_model = getattr(encoder, "model")
    encoder_dimension = int(getattr(encoder, "dimension"))
    archetypes = _parse_manifest(raw)

    cache = Path(cache_path) if cache_path is not None else None
    if cache is not None and cache.exists():
        cached = json.loads(cache.read_text(encoding="utf-8"))
        if (
            cached.get("manifest_hash") == manifest_hash
            and cached.get("encoder_model") == encoder_model
            and cached.get("encoder_dimension") == encoder_dimension
            and cached.get("archetype_texts") == [item.text for item in archetypes]
        ):
            return ArchetypeIndex(
                manifest_path=str(manifest),
                manifest_hash=manifest_hash,
                encoder_model=encoder_model,
                encoder_dimension=encoder_dimension,
                archetypes=archetypes,
                embeddings=[list(vector) for vector in cached["embeddings"]],
            )

    embeddings = _json_embedding_matrix(encoder.encode_many([item.text for item in archetypes]))
    index = ArchetypeIndex(
        manifest_path=str(manifest),
        manifest_hash=manifest_hash,
        encoder_model=encoder_model,
        encoder_dimension=encoder_dimension,
        archetypes=archetypes,
        embeddings=embeddings,
    )
    if cache is not None:
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(
            json.dumps(
                {
                    "manifest_path": str(manifest),
                    "manifest_hash": manifest_hash,
                    "encoder_model": encoder_model,
                    "encoder_dimension": encoder_dimension,
                    "archetype_texts": [item.text for item in archetypes],
                    "embeddings": embeddings,
                },
                sort_keys=True,
            ),
            encoding="utf-8",
        )
    return index


def _json_embedding_matrix(embeddings: Sequence[Sequence[float]]) -> list[list[float]]:
    return [[float(value) for value in vector] for vector in embeddings]


class Layer0Dispatcher:
    def __init__(
        self,
        *,
        index: ArchetypeIndex,
        encoder: MiniLMEncoder | None = None,
        thresholds: ScoringThresholds | None = None,
    ) -> None:
        self.index = index
        self.encoder = encoder
        self.thresholds = thresholds or ScoringThresholds()

    def emit_spec(
        self,
        utterance: str,
        *,
        surface: str,
        inventory: InventorySummary,
    ) -> CompositionSpec:
        del surface  # Layer 0 records shape; downstream surfaces consume separately.
        explicit_memory = bool(_EXPLICIT_MEMORY_RE.search(utterance))
        self_capability_complaint = (
            evidence_precedence_enabled() and _is_self_capability_complaint(utterance)
        )
        explicit_fetch = (
            bool(_EXPLICIT_FETCH_RE.search(utterance)) and not self_capability_complaint
        )
        content_anchored = bool(_CONTENT_ANCHOR_RE.search(utterance))
        owner_url_present = page_read_enabled() and bool(extract_first_url(utterance))
        self_capability_question = (
            evidence_precedence_enabled() and _is_self_capability_question(utterance)
        )
        current_world_request = sense_enabled() and _is_current_world_request(utterance)
        source_anchor_candidates = _source_anchor_candidates(utterance)
        live_reddit_anchor = (
            _has_subreddit_anchor(utterance) and not self_capability_complaint
        )
        scores = self.score_classes(utterance)
        accepted = _accepted_classes(scores, self.thresholds)
        limitations = list(inventory.availability_limitations)

        if not accepted and scores and scores[0].score >= self.thresholds.no_match_below:
            _append_once(limitations, AvailabilityLimitation.SCORING_LOW_CONFIDENCE)

        if owner_url_present and not explicit_memory:
            substrate_sources = []
            external_sources = [ExternalSource.FETCH_URL]
            hint = CompositionHint.FRESH_ONLY
            framing = ProvenanceFraming.FRESH_ONLY
        elif live_reddit_anchor and not explicit_memory:
            substrate_sources = _available_substrates(
                inventory,
                _substrate_candidates(source_anchor_candidates),
            )
            external_sources = [ExternalSource.LIVE_REDDIT]
            if substrate_sources:
                hint = CompositionHint.PARALLEL
                framing = ProvenanceFraming.HYBRID_FRESH_VALIDATES_SUBSTRATE_CONTEXTUALIZES
            else:
                hint = CompositionHint.FRESH_ONLY
                framing = ProvenanceFraming.FRESH_ONLY
        elif (self_capability_question or self_capability_complaint) and not explicit_memory:
            substrate_sources = _available_substrates(
                inventory,
                _substrate_candidates(source_anchor_candidates),
            )
            external_sources = []
            hint = CompositionHint.SUBSTRATE_ONLY
            framing = ProvenanceFraming.SUBSTRATE_ONLY_NO_FRESH_VALIDATION
        elif explicit_fetch and not explicit_memory:
            substrate_sources: list[SubstrateSource] = []
            external_sources = [ExternalSource.WEB_SEARCH]
            hint = CompositionHint.FRESH_ONLY
            framing = ProvenanceFraming.FRESH_ONLY
        elif current_world_request and not explicit_memory:
            substrate_sources = _available_substrates(
                inventory,
                _substrate_candidates(source_anchor_candidates),
            )
            external_sources = [ExternalSource.WEB_SEARCH]
            if substrate_sources:
                hint = CompositionHint.PARALLEL
                framing = ProvenanceFraming.HYBRID_FRESH_VALIDATES_SUBSTRATE_CONTEXTUALIZES
            else:
                hint = CompositionHint.FRESH_ONLY
                framing = ProvenanceFraming.FRESH_ONLY
        elif explicit_memory and not explicit_fetch:
            substrate_sources = _available_substrates(
                inventory,
                _substrate_candidates(source_anchor_candidates),
            )
            external_sources = []
            hint = CompositionHint.SUBSTRATE_ONLY
            framing = ProvenanceFraming.SUBSTRATE_ONLY_NO_FRESH_VALIDATION
        elif _class_won("B_EXPLICIT_LIVE_FETCH", accepted):
            substrate_sources = []
            external_sources = [ExternalSource.WEB_SEARCH]
            hint = CompositionHint.FRESH_ONLY
            framing = ProvenanceFraming.FRESH_ONLY
        elif _class_won("A_EXPLICIT_SUBSTRATE_RECALL", accepted):
            substrate_sources = _available_substrates(
                inventory,
                _substrate_candidates(source_anchor_candidates),
            )
            external_sources = []
            hint = CompositionHint.SUBSTRATE_ONLY
            framing = ProvenanceFraming.SUBSTRATE_ONLY_NO_FRESH_VALIDATION
        else:
            substrate_sources, external_sources, hint, framing = _fallback_spec_shape(
                inventory,
                content_anchored=content_anchored or _class_won(
                    "C_HYBRID_CONTENT_ANCHORED", accepted
                ),
                source_anchor_candidates=source_anchor_candidates,
                live_reddit_anchor=live_reddit_anchor,
                limitations=limitations,
            )

        source_availability = _availability_for_selected(
            inventory,
            substrate_sources=substrate_sources,
            external_sources=external_sources,
        )
        return CompositionSpec(
            substrate_sources=substrate_sources,
            external_sources=external_sources,
            composition_hint=hint,
            provenance_framing=framing,
            inventory_witness=inventory.inventory_witness,
            source_availability=source_availability,
            availability_limitations=limitations,
            freshness_window=None,
            trust_scope_union=None,
        )

    def score_classes(self, utterance: str) -> list[ClassScore]:
        encoder = self.encoder or get_encoder()
        query_vector = encoder.encode(utterance)
        best: dict[str, float] = {}
        for archetype, embedding in zip(self.index.archetypes, self.index.embeddings, strict=True):
            score = _cosine(query_vector, embedding)
            best[archetype.class_id] = max(score, best.get(archetype.class_id, -1.0))
        return sorted(
            (ClassScore(class_id=class_id, score=score) for class_id, score in best.items()),
            key=lambda item: (-item.score, _class_order(item.class_id), item.class_id),
        )


def _parse_manifest(raw: str) -> list[Archetype]:
    archetypes: list[Archetype] = []
    current_class: str | None = None
    in_archetype_table = False
    for line in raw.splitlines():
        heading_match = re.match(r"### Class [A-Z] .+`([^`]+)`", line)
        if heading_match:
            current_class = _canonical_class_id(heading_match.group(1))
            in_archetype_table = False
            continue
        if line.startswith("## "):
            current_class = None
            in_archetype_table = False
        if current_class is None or not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) < 3:
            continue
        if cells[0] == "Archetype":
            in_archetype_table = True
            continue
        if cells[0] == "---":
            continue
        if not in_archetype_table:
            continue
        text = cells[0]
        archetypes.append(
            Archetype(
                archetype_id=f"{current_class}:{len(archetypes):03d}",
                class_id=current_class,
                text=text,
            )
        )
    if not archetypes:
        raise ValueError("archetype manifest contains no archetype rows")
    return archetypes


def _canonical_class_id(raw: str) -> str:
    return _LEGACY_CLASS_MAP.get(raw, raw)


def _accepted_classes(
    scores: Sequence[ClassScore],
    thresholds: ScoringThresholds,
) -> list[str]:
    if not scores or scores[0].score < thresholds.min_accept:
        return []
    if len(scores) == 1:
        return [scores[0].class_id]
    top = scores[0]
    second = scores[1]
    if top.score - second.score >= thresholds.dominance_margin:
        return [top.class_id]
    contributors = [
        score.class_id
        for score in scores
        if top.score - score.score <= thresholds.multi_match_delta
    ]
    if contributors:
        return sorted(contributors, key=lambda class_id: (_class_order(class_id), class_id))
    return [top.class_id]


def _class_won(class_id: str, accepted: Sequence[str]) -> bool:
    return class_id in accepted


def _fallback_spec_shape(
    inventory: InventorySummary,
    *,
    content_anchored: bool,
    source_anchor_candidates: Sequence[SubstrateSource],
    live_reddit_anchor: bool,
    limitations: list[AvailabilityLimitation],
) -> tuple[
    list[SubstrateSource],
    list[ExternalSource],
    CompositionHint,
    ProvenanceFraming,
]:
    if inventory.inventory_witness == InventoryWitness.ABSENT:
        _append_once(limitations, AvailabilityLimitation.NO_RELEVANT_SUBSTRATE)
        external = [ExternalSource.WEB_SEARCH] if content_anchored else []
        return [], external, CompositionHint.FRESH_ONLY, ProvenanceFraming.FRESH_ONLY

    if inventory.inventory_witness == InventoryWitness.UNKNOWN:
        _append_once(limitations, AvailabilityLimitation.INVENTORY_UNKNOWN)

    substrate = _available_substrates(
        inventory,
        _substrate_candidates(source_anchor_candidates),
    )
    if live_reddit_anchor:
        external = [ExternalSource.LIVE_REDDIT]
    elif source_anchor_candidates:
        external = []
    else:
        external = [ExternalSource.WEB_SEARCH] if content_anchored else []
    if external:
        return (
            substrate,
            external,
            CompositionHint.PARALLEL if live_reddit_anchor else CompositionHint.SUBSTRATE_THEN_FETCH_IF_STALE,
            ProvenanceFraming.HYBRID_FRESH_VALIDATES_SUBSTRATE_CONTEXTUALIZES,
        )
    return (
        substrate,
        [],
        CompositionHint.SUBSTRATE_ONLY,
        ProvenanceFraming.SUBSTRATE_ONLY_NO_FRESH_VALIDATION,
    )


def _available_substrates(
    inventory: InventorySummary,
    candidates: Sequence[SubstrateSource],
) -> list[SubstrateSource]:
    selected: list[SubstrateSource] = []
    for source in candidates:
        availability = inventory.source_availability.get(source)
        if availability in {
            SourceAvailability.EXECUTABLE_PRESENT,
            SourceAvailability.EXECUTABLE_UNKNOWN,
        }:
            selected.append(source)
    return selected


def _source_anchor_candidates(utterance: str) -> list[SubstrateSource]:
    if _REDDIT_ANCHOR_RE.search(utterance):
        return [SubstrateSource.REDDIT_SOURCE]
    return []


def _has_subreddit_anchor(utterance: str) -> bool:
    return bool(_SUBREDDIT_ANCHOR_RE.search(utterance))


def _is_current_world_request(utterance: str) -> bool:
    """True when the utterance asks for current-world information.

    This used to require question shape (``_QUESTION_SHAPE_RE``), so bare current-world
    fragments like "news about Anthropic" or "latest Elon news" fell through to
    SUBSTRATE_ONLY and the brain answered (and confabulated current specifics) from
    memory instead of fetching. We now accept any utterance carrying a current-world
    marker (news/latest/recent/today/…) — question-shaped or a bare fragment — and
    exclude only the conversational "how are you … today" greeting. Explicit-memory
    forms ("what do you remember …") are still blocked downstream at the ``emit_spec``
    branch via its ``and not explicit_memory`` guard, so they stay substrate-only.
    """
    if not _CURRENT_WORLD_MARKER_RE.search(utterance):
        return False
    return not _CONVERSATIONAL_TODAY_RE.search(utterance)


def _is_self_capability_question(utterance: str) -> bool:
    if not _QUESTION_SHAPE_RE.search(utterance):
        return False
    return bool(_SELF_CAPABILITY_RE.search(utterance or ""))


def _is_self_capability_complaint(utterance: str) -> bool:
    text = utterance or ""
    return bool(_SELF_REF_RE.search(text) and _SELF_CAPABILITY_COMPLAINT_RE.search(text))


def _substrate_candidates(source_anchor_candidates: Sequence[SubstrateSource]) -> list[SubstrateSource]:
    if source_anchor_candidates:
        return list(source_anchor_candidates)
    return list(_DEFAULT_SUBSTRATE_FALLBACK)


def _availability_for_selected(
    inventory: InventorySummary,
    *,
    substrate_sources: Sequence[SubstrateSource],
    external_sources: Sequence[ExternalSource],
) -> dict[SourceLabel, SourceAvailability]:
    availability: dict[SourceLabel, SourceAvailability] = {}
    for source in [*substrate_sources, *external_sources]:
        availability[source] = inventory.source_availability.get(
            source,
            SourceAvailability.EXECUTABLE_UNKNOWN,
        )
    return availability


def _append_once(values: list[AvailabilityLimitation], value: AvailabilityLimitation) -> None:
    if value not in values:
        values.append(value)


def _class_order(class_id: str) -> int:
    try:
        return CLASS_ORDER.index(class_id)
    except ValueError:
        return len(CLASS_ORDER)


def _cosine(left: Sequence[float], right: Sequence[float]) -> float:
    numerator = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return numerator / (left_norm * right_norm)


def _digest_text(raw: str) -> str:
    return "sha256:" + hashlib.sha256(raw.encode()).hexdigest()
