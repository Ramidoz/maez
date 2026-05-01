# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Semantic entity resolver (Step 5n).

The Step-5j A/B against real lived-memory showed that natural
queries like "tell me about Maez" never benefit from entity
expansion: keyword recall already finds every episode that mentions
Maez literally, so the substrate has nothing to add. The Step-5m
LLM extractor populated the index with 38 entities and 8 in
≥2 sessions but couldn't change the A/B because both passes
require entity surfaces to literally appear in episode text — a
property of grounding, not a bug.

The missing layer is owner-language. "The firstborn" means Maez.
"Your body" means the hardware/runtime. "Birth" means Track A.
None of these phrases appear in episode text, so no extractor
(deterministic OR LLM-with-grounding-check) can produce them as
aliases. They are NOT in the corpus; they are in the operator's
head — a curated semantic bridge between how the operator talks
about things and which canonical entities the index knows about.

This module is that bridge. v1 is exact-phrase, owner-curated, no
LLM:

  • Read ``config/entity_semantics.local.yaml`` (gitignored).
  • For each phrase that appears in the query (case-insensitive,
    word-boundary), look up each declared target in the
    EntityIndex.
  • Return ``EntityMatch`` shapes that the lived-recall expansion
    section already knows how to render. Step 5o wires this into
    the recall path; this slice ships the resolver and config
    only.

Hard contract:

  • No LLM, no network, no subprocess. Pure config-driven.
  • If a target is not present in the EntityIndex, RETURN A
    WARNING. Do not synthesize an entity row from the config.
    The config names what to LOOK UP, not what to CREATE — the
    extractor + backfill remain the source of truth for what
    entities exist.
  • Word-boundary matching: "birth" must not match "birthday".
  • Multiple targets per phrase are allowed (e.g. "body" maps to
    BOTH the GPU and the runtime); all surfacing targets are
    returned.

Public API:

  load_semantic_mappings(path) -> list[SemanticMapping]
  resolve_semantic_entities(query, ix, mappings=None)
                             -> SemanticResolution
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

if TYPE_CHECKING:
    from core.memory.entity_index import EntityIndex

logger = logging.getLogger(__name__)


# ── exceptions / dataclasses ──────────────────────────────────────


class SemanticConfigError(ValueError):
    """Raised when ``entity_semantics.local.yaml`` is malformed:
    invalid YAML, missing required fields, out-of-range
    confidence, etc. Distinct from a runtime resolution miss
    (which is just a warning)."""


@dataclass
class SemanticMapping:
    """One owner-curated semantic mapping. Targets is a list of
    ``{canonical_name, kind}`` dicts — the resolver looks each up
    in the EntityIndex at resolve time, so a mapping that points
    at an entity that doesn't exist yet is a recoverable warning,
    not a hard error."""
    phrase: str
    targets: list[dict]
    confidence: float = 1.0
    notes: str | None = None


# Importing EntityMatch from entity_index would create a circular
# dependency at module load time. Instead, re-construct the same
# shape via a local dataclass mirroring the relevant fields. The
# expansion-section formatter in lived_recall reads via attribute
# access, so any shape with .entity_id / .canonical_name / .kind /
# .confidence / .matched_via is interchangeable.

@dataclass
class SemanticEntityMatch:
    """Surface-compatible with ``entity_index.EntityMatch`` so the
    same expansion-section formatter can render either."""
    entity_id: str
    canonical_name: str
    kind: str
    confidence: float
    matched_via: str  # "semantic_phrase"


@dataclass
class SemanticResolution:
    """Output of ``resolve_semantic_entities``. Counterpart of
    ``QueryExpansion`` from entity_index, scoped to semantic
    bridging only."""
    original_query: str
    matched_phrases: list[str]
    resolved_entities: list[SemanticEntityMatch]
    confidence: float = 0.0
    explanation: str = ""
    warnings: list[str] = field(default_factory=list)


# ── load + validate ──────────────────────────────────────────────


def _validate_target(target: Any, *, mapping_idx: int, target_idx: int) -> dict:
    if not isinstance(target, dict):
        raise SemanticConfigError(
            f"mappings[{mapping_idx}].targets[{target_idx}] must be "
            f"a YAML mapping, got {type(target).__name__}"
        )
    canonical = target.get("canonical_name")
    if not isinstance(canonical, str) or not canonical.strip():
        raise SemanticConfigError(
            f"mappings[{mapping_idx}].targets[{target_idx}] missing "
            "required string 'canonical_name'"
        )
    kind = target.get("kind", "unknown")
    if not isinstance(kind, str) or not kind.strip():
        raise SemanticConfigError(
            f"mappings[{mapping_idx}].targets[{target_idx}] 'kind' "
            "must be a non-empty string"
        )
    return {
        "canonical_name": canonical.strip(),
        "kind": kind.strip(),
    }


def _validate_mapping(raw: Any, *, idx: int) -> SemanticMapping:
    if not isinstance(raw, dict):
        raise SemanticConfigError(
            f"mappings[{idx}] must be a YAML mapping, got "
            f"{type(raw).__name__}"
        )
    phrase = raw.get("phrase")
    if not isinstance(phrase, str) or not phrase.strip():
        raise SemanticConfigError(
            f"mappings[{idx}] missing required string 'phrase'"
        )
    targets_raw = raw.get("targets")
    if not isinstance(targets_raw, list) or not targets_raw:
        raise SemanticConfigError(
            f"mappings[{idx}] ({phrase!r}) 'targets' must be a "
            "non-empty list"
        )
    targets = [
        _validate_target(t, mapping_idx=idx, target_idx=j)
        for j, t in enumerate(targets_raw)
    ]
    confidence_raw = raw.get("confidence", 1.0)
    try:
        confidence = float(confidence_raw)
    except (TypeError, ValueError):
        raise SemanticConfigError(
            f"mappings[{idx}] ({phrase!r}) 'confidence' must be a "
            f"number, got {type(confidence_raw).__name__}"
        )
    if not (0.0 <= confidence <= 1.0):
        raise SemanticConfigError(
            f"mappings[{idx}] ({phrase!r}) 'confidence' must be in "
            f"[0, 1], got {confidence}"
        )
    notes = raw.get("notes")
    if notes is not None and not isinstance(notes, str):
        raise SemanticConfigError(
            f"mappings[{idx}] ({phrase!r}) 'notes' must be a string "
            "or absent"
        )
    return SemanticMapping(
        phrase=phrase.strip(),
        targets=targets,
        confidence=confidence,
        notes=notes,
    )


def load_semantic_mappings(path: Path | str) -> list[SemanticMapping]:
    """Parse and validate a semantics YAML file. Raises
    ``SemanticConfigError`` on any malformed input. Returns the
    list in file order — mapping precedence is left to the caller
    (resolver does not auto-rank)."""
    p = Path(path)
    try:
        raw = yaml.safe_load(p.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        raise SemanticConfigError(
            f"could not parse {p} as YAML: {e}"
        ) from e
    except OSError as e:
        raise SemanticConfigError(f"could not read {p}: {e}") from e

    if not isinstance(raw, dict):
        raise SemanticConfigError(
            f"{p}: top-level must be a mapping, got "
            f"{type(raw).__name__}"
        )
    if "mappings" not in raw:
        raise SemanticConfigError(f"{p}: missing required key 'mappings'")
    mappings_raw = raw["mappings"]
    if not isinstance(mappings_raw, list):
        raise SemanticConfigError(
            f"{p}: 'mappings' must be a list, got "
            f"{type(mappings_raw).__name__}"
        )
    return [
        _validate_mapping(m, idx=i)
        for i, m in enumerate(mappings_raw)
    ]


# ── resolution ───────────────────────────────────────────────────


def _phrase_in_query(phrase: str, query: str) -> bool:
    """Case-insensitive word-boundary substring match. 'birth' must
    not match 'birthday'."""
    try:
        return re.search(
            r"\b" + re.escape(phrase) + r"\b",
            query, re.IGNORECASE,
        ) is not None
    except re.error:
        return False


def _lookup_entity(ix: "EntityIndex", canonical_name: str, kind: str) -> dict | None:
    """Return ``{id, canonical_name, kind}`` for an entity matching
    ``(canonical_name, kind)`` after normalization, or None if
    not present in the index."""
    from core.memory.entity_index import normalize_entity_name

    normalized = normalize_entity_name(canonical_name)
    row = ix._connect().execute(
        "SELECT id, canonical_name, kind FROM entities "
        "WHERE normalized_name = ? AND kind = ?",
        (normalized, kind),
    ).fetchone()
    return dict(row) if row else None


def resolve_semantic_entities(
    query: str | None,
    *,
    ix: "EntityIndex",
    mappings: list[SemanticMapping] | None = None,
) -> SemanticResolution:
    """Resolve owner-language phrases in ``query`` to canonical
    entities via the supplied ``mappings``. ``mappings=None``
    returns an empty resolution (callers wire in the default
    config path explicitly via ``load_semantic_mappings``).

    Missing targets emit warnings on the result, not exceptions —
    the rest of the resolution remains useful even when one
    target is absent.
    """
    if not query or not isinstance(query, str) or not query.strip():
        return SemanticResolution(
            original_query=query or "",
            matched_phrases=[],
            resolved_entities=[],
            confidence=0.0,
            explanation="empty query",
            warnings=[],
        )
    if mappings is None:
        mappings = []

    matched_phrases: list[str] = []
    resolved: list[SemanticEntityMatch] = []
    warnings: list[str] = []
    seen_entity_ids: set[str] = set()
    matched_confidences: list[float] = []

    for mapping in mappings:
        if not _phrase_in_query(mapping.phrase, query):
            continue
        if mapping.phrase not in matched_phrases:
            matched_phrases.append(mapping.phrase)
        matched_confidences.append(mapping.confidence)

        for target in mapping.targets:
            row = _lookup_entity(
                ix, target["canonical_name"], target["kind"],
            )
            if row is None:
                msg = (
                    f"semantic mapping for phrase {mapping.phrase!r}: "
                    f"target ({target['canonical_name']!r}, "
                    f"{target['kind']!r}) not found in entity index. "
                    "Skipping; run extraction or seed the entity to "
                    "make this resolvable."
                )
                warnings.append(msg)
                logger.debug("entity_semantic_resolver: %s", msg)
                continue
            if row["id"] in seen_entity_ids:
                continue
            seen_entity_ids.add(row["id"])
            resolved.append(SemanticEntityMatch(
                entity_id=row["id"],
                canonical_name=row["canonical_name"],
                kind=row["kind"],
                confidence=mapping.confidence,
                matched_via="semantic_phrase",
            ))

    confidence = max(matched_confidences) if matched_confidences else 0.0
    if matched_phrases:
        explanation = (
            f"matched {len(matched_phrases)} semantic "
            f"phrase{'s' if len(matched_phrases) != 1 else ''}: "
            + ", ".join(repr(p) for p in matched_phrases)
        )
    else:
        explanation = "no semantic mapping matched"

    return SemanticResolution(
        original_query=query,
        matched_phrases=matched_phrases,
        resolved_entities=resolved,
        confidence=confidence,
        explanation=explanation,
        warnings=warnings,
    )


__all__ = [
    "SemanticConfigError",
    "SemanticEntityMatch",
    "SemanticMapping",
    "SemanticResolution",
    "load_semantic_mappings",
    "resolve_semantic_entities",
]
