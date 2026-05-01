# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""MSEL natural-text probe sweep.

Complements ``scripts/validate/lived_memory_probes.py`` by wiring
in the EntityIndex + semantic mapping config that the existing
suite leaves out. Used to verify the MSEL substrate ladder
(entity index → alias seed → backfill → semantic resolver →
expansion wiring) is healthy independent of live daemon traffic.

For each natural-text query, reports:

    - elapsed_ms
    - brief length (chars)
    - did "=== ENTITY EXPANSION ===" section appear?
    - which canonical entities surfaced
    - which episode IDs (``ep-…``) surfaced
    - whether semantic mapping fired (phrase → canonical)

Sets ``MAEZ_ENTITY_EXPANSION=1`` for the duration of the run so
the expansion code path is exercised regardless of process env.

CLI::

    .venv/bin/python scripts/probe/probe_msel_natural.py

Reads the live SQLite stores under ``memory/`` and the live
``config/entity_semantics.local.yaml``.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


# ── canonical natural-text probe set ────────────────────────────────
#
# Mix of: factual recall, relationship, correction, temporal, semantic
# mapping (firstborn/the body), nickname (alias path), open-loop. All
# real-human-shape inputs, not synthetic "describe your architecture".
NATURAL_PROBES: list[tuple[str, str]] = [
    ("temporal_echo",     "What is today echoing from last week?"),
    ("open_loop",         "What have we not finished?"),
    ("correction",        "Was llama-server-vision real?"),
    ("relationship",      "What do you know I care about in Maez?"),
    ("kernel_factual",    "Have we had any kernel reboots?"),
    ("nickname_alias",    "how is Mimi doing?"),
    ("rohit_self",        "what does Rohit care about"),
    ("brain_change",      "what changed about your brain model?"),
    ("semantic_firstborn", "tell me about the firstborn"),
    ("semantic_body",     "is the body holding up?"),
]


@dataclass
class ProbeMetrics:
    name: str
    query: str
    elapsed_ms: float
    brief_chars: int
    expansion_fired: bool
    canonical_entities: list[str]
    episode_ids: list[str]
    semantic_phrases: list[str]
    has_evidence: bool


_ENTITY_SECTION_RE = re.compile(
    r"=== ENTITY EXPANSION ===(.*?)(?:===|\Z)",
    re.DOTALL,
)
_EPISODE_ID_RE = re.compile(r"\b(ep-[a-f0-9-]+)\b")
# The expansion section format (lived_recall.py) is:
#     - Name [conf X.X]: ep-..., ep-...
#     Explanation: matched N entit{y|ies}.
# Optional future annotation may add `semantic: "phrase"` somewhere.
_ENTITY_LINE_RE = re.compile(r"^\s*[-•*]\s*(.+?)\s*\[conf\s")
_SEMANTIC_PHRASE_RE = re.compile(r'\bsemantic:\s*"([^"]+)"', re.IGNORECASE)


def _parse_brief(brief: str) -> tuple[bool, list[str], list[str], list[str]]:
    """Extract (expansion_fired, canonical_entities, episode_ids,
    semantic_phrases) from the brief text. The brief is human-readable;
    the parse is best-effort but tight enough to skip the
    ``Explanation:`` summary line."""
    expansion_fired = "=== ENTITY EXPANSION ===" in brief
    canonical_entities: list[str] = []
    if expansion_fired:
        m = _ENTITY_SECTION_RE.search(brief)
        if m:
            for line in m.group(1).splitlines():
                em = _ENTITY_LINE_RE.match(line)
                if em:
                    name = em.group(1).strip()
                    if name and name not in canonical_entities:
                        canonical_entities.append(name)
    episode_ids = list(dict.fromkeys(_EPISODE_ID_RE.findall(brief)))
    semantic_phrases = list(dict.fromkeys(_SEMANTIC_PHRASE_RE.findall(brief)))
    return expansion_fired, canonical_entities, episode_ids, semantic_phrases


def run_probes(
    *,
    episode_db: Path,
    graph_db: Path,
    entity_index_db: Path,
    semantic_config: Path,
) -> list[ProbeMetrics]:
    os.environ["MAEZ_ENTITY_EXPANSION"] = "1"

    from core.memory.entity_index import EntityIndex
    from core.memory.entity_semantic_resolver import load_semantic_mappings
    from core.memory.episodes import EpisodeStore
    from core.memory.lived_recall import build_lived_recall_brief
    from core.memory.relationship_graph import RelationshipGraph

    episodes = EpisodeStore(str(episode_db))
    graph = RelationshipGraph(str(graph_db))
    ix = EntityIndex(str(entity_index_db)) if entity_index_db.exists() else None
    mappings = (
        load_semantic_mappings(semantic_config)
        if semantic_config.exists()
        else None
    )

    results: list[ProbeMetrics] = []
    for name, query in NATURAL_PROBES:
        t0 = time.perf_counter()
        brief = build_lived_recall_brief(
            query,
            episode_store=episodes,
            graph=graph,
            ix=ix,
            semantic_mappings=mappings,
        )
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        fired, canonicals, ep_ids, phrases = _parse_brief(brief)
        has_evidence = bool(ep_ids) or "core-" in brief or "raw-" in brief
        results.append(ProbeMetrics(
            name=name,
            query=query,
            elapsed_ms=elapsed_ms,
            brief_chars=len(brief),
            expansion_fired=fired,
            canonical_entities=canonicals,
            episode_ids=ep_ids,
            semantic_phrases=phrases,
            has_evidence=has_evidence,
        ))
    return results


def _format_report(metrics: list[ProbeMetrics]) -> str:
    n = len(metrics)
    n_brief = sum(1 for m in metrics if m.brief_chars > 0)
    n_fired = sum(1 for m in metrics if m.expansion_fired)
    n_evid = sum(1 for m in metrics if m.has_evidence)
    n_sem = sum(1 for m in metrics if m.semantic_phrases)

    lines = [
        "=== MSEL NATURAL-TEXT PROBE SWEEP ===",
        f"probes:               {n}",
        f"non-empty brief:      {n_brief}/{n}",
        f"entity expansion:     {n_fired}/{n}",
        f"semantic phrase fire: {n_sem}/{n}",
        f"evidence cited:       {n_evid}/{n}",
        "",
    ]
    for m in metrics:
        marks = []
        marks.append("BRIEF" if m.brief_chars else "empty")
        if m.expansion_fired:
            marks.append("EXPAND")
        if m.semantic_phrases:
            marks.append(f"SEM={m.semantic_phrases}")
        if m.has_evidence:
            marks.append("EVID")
        lines.append(
            f"[{m.name:20s}] {m.elapsed_ms:6.1f}ms  "
            f"{m.brief_chars:5d}c  {' '.join(marks)}"
        )
        lines.append(f"    q: {m.query}")
        if m.canonical_entities:
            lines.append(f"    entities: {m.canonical_entities[:6]}")
        if m.episode_ids:
            lines.append(f"    episodes: {m.episode_ids[:3]}")
        lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--episode-db",
                    default=str(_REPO_ROOT / "memory" / "lived_episodes.db"))
    ap.add_argument("--graph-db",
                    default=str(_REPO_ROOT / "memory" / "lived_graph.db"))
    ap.add_argument("--entity-index-db",
                    default=str(_REPO_ROOT / "memory" / "entity_index.db"))
    ap.add_argument("--semantic-config",
                    default=str(_REPO_ROOT / "config" /
                                "entity_semantics.local.yaml"))
    ap.add_argument("--verbose", "-v", action="store_true",
                    help="print full briefs")
    args = ap.parse_args(argv)

    results = run_probes(
        episode_db=Path(args.episode_db),
        graph_db=Path(args.graph_db),
        entity_index_db=Path(args.entity_index_db),
        semantic_config=Path(args.semantic_config),
    )
    print(_format_report(results))
    if args.verbose:
        print("\n=== FULL BRIEFS ===\n")
        from core.memory.entity_index import EntityIndex
        from core.memory.entity_semantic_resolver import (
            load_semantic_mappings,
        )
        from core.memory.episodes import EpisodeStore
        from core.memory.lived_recall import build_lived_recall_brief
        from core.memory.relationship_graph import RelationshipGraph
        episodes = EpisodeStore(args.episode_db)
        graph = RelationshipGraph(args.graph_db)
        ix = (EntityIndex(args.entity_index_db)
              if Path(args.entity_index_db).exists() else None)
        mappings = (load_semantic_mappings(args.semantic_config)
                    if Path(args.semantic_config).exists() else None)
        for name, query in NATURAL_PROBES:
            print(f"\n--- {name} :: {query} ---")
            brief = build_lived_recall_brief(
                query, episode_store=episodes, graph=graph,
                ix=ix, semantic_mappings=mappings,
            )
            print(brief or "(empty brief)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
