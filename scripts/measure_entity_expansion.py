# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Lightweight A/B measurement for entity expansion (Step 5j).

Measures whether ``MAEZ_ENTITY_EXPANSION`` changes the lived-recall
brief on a set of queries. Calls ``build_lived_recall_brief``
directly — no daemon, no LLM, no network.

Hard contract — what this script is NOT:

  • Not a relevance judge. It can tell the operator that the
    expansion section appeared and which session_ids it added; it
    cannot say whether those sessions are useful or noisy. The
    output reflects that honestly with a banner on every run.
  • Not a writer. The entity index, episode store, and relationship
    graph are read-only. Even Step-5c temporal annotation defaults
    are bypassed via ``reference_time`` for reproducibility.
  • Not a daemon probe. Real-traffic A/B is a different scope; this
    script is for fast iteration on the substrate's behaviour
    against existing data.

Outputs:
  • Human-readable table (default): query / baseline_chars /
    expanded_chars / new_entities / new_sessions.
  • Per-query detail (``--json``): full JSON record per query
    including diff excerpts and session-id set diffs.

Default queries:
  When neither ``--query`` nor ``--queries-file`` is supplied,
  defaults are derived from the index — top-N entities by mention
  count, query template ``"tell me about <canonical_name>"``. This
  guarantees default queries hit the user's actual data and the
  A/B reflects substrate behaviour rather than query/data
  mismatch.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.memory.entity_index import EntityIndex
    from core.memory.episodes import EpisodeStore
    from core.memory.relationship_graph import RelationshipGraph


_FLAG = "MAEZ_ENTITY_EXPANSION"

DISCLAIMER = (
    "This measures whether ENTITY EXPANSION changes recall context, "
    "not whether the added context is relevant. Operator must "
    "review diff_excerpt to judge."
)

_EP_ID_RE = re.compile(r"\bep-[0-9a-fA-F]+(?:[-0-9a-zA-Z]*)?\b")
_EXPANSION_HEADER = "=== ENTITY EXPANSION ==="
_EXPANSION_BULLET_RE = re.compile(
    r"^- (?P<name>.+?) \[conf [0-9.]+\]:", re.MULTILINE,
)


# ── env control ───────────────────────────────────────────────────


@contextmanager
def _env_set(value: str | None):
    """Set or unset the entity-expansion flag for the duration of
    the block. Restores the prior state on exit so the caller's
    environment is never permanently mutated. Used twice per
    measurement: once to clear the flag for the baseline pass and
    once to set it for the expanded pass."""
    prior = os.environ.get(_FLAG)
    try:
        if value is None:
            os.environ.pop(_FLAG, None)
        else:
            os.environ[_FLAG] = value
        yield
    finally:
        if prior is None:
            os.environ.pop(_FLAG, None)
        else:
            os.environ[_FLAG] = prior


# ── parsing brief output ─────────────────────────────────────────


def _extract_session_ids(brief: str) -> list[str]:
    """All ``ep-…`` ids in the brief, in document order, deduped."""
    seen: list[str] = []
    for m in _EP_ID_RE.finditer(brief):
        eid = m.group(0)
        if eid not in seen:
            seen.append(eid)
    return seen


def _extract_entities_surfaced(brief: str) -> list[str]:
    """Canonical names from the ENTITY EXPANSION section's bullets.
    Empty list when the section isn't present."""
    if _EXPANSION_HEADER not in brief:
        return []
    section_start = brief.index(_EXPANSION_HEADER)
    section = brief[section_start:]
    return [m.group("name") for m in _EXPANSION_BULLET_RE.finditer(section)]


def _diff_excerpt(brief: str, *, lead_lines: int = 3) -> str:
    """The ENTITY EXPANSION section verbatim plus ``lead_lines``
    of context preceding it. Empty string when the section isn't
    present."""
    if _EXPANSION_HEADER not in brief:
        return ""
    lines = brief.splitlines()
    for i, line in enumerate(lines):
        if line.startswith(_EXPANSION_HEADER):
            start = max(0, i - lead_lines)
            return "\n".join(lines[start:])
    return ""


# ── single-query measurement ──────────────────────────────────────


def measure(
    query: str,
    *,
    ix: "EntityIndex",
    episode_store: "EpisodeStore",
    graph: "RelationshipGraph",
    reference_time: datetime | None = None,
) -> dict:
    """Run baseline + expanded passes for one query and return the
    full per-query measurement dict.

    Both passes use the same supplied ``ix`` / ``episode_store`` /
    ``graph`` / ``reference_time``. The only thing that varies is
    the env flag, which is set/unset explicitly via ``_env_set``.
    """
    from core.memory.lived_recall import build_lived_recall_brief

    with _env_set(None):
        baseline = build_lived_recall_brief(
            query,
            episode_store=episode_store,
            graph=graph,
            reference_time=reference_time,
            ix=ix,
        )
    with _env_set("1"):
        expanded = build_lived_recall_brief(
            query,
            episode_store=episode_store,
            graph=graph,
            reference_time=reference_time,
            ix=ix,
        )

    baseline_sessions = _extract_session_ids(baseline)
    expanded_sessions = _extract_session_ids(expanded)
    new_sessions = [
        s for s in expanded_sessions if s not in baseline_sessions
    ]
    entities_surfaced = _extract_entities_surfaced(expanded)
    return {
        "query": query,
        "baseline_chars": len(baseline),
        "expanded_chars": len(expanded),
        "entity_section_present": _EXPANSION_HEADER in expanded,
        "entities_surfaced": entities_surfaced,
        "new_entities": len(entities_surfaced),
        "baseline_session_ids": baseline_sessions,
        "expanded_session_ids": expanded_sessions,
        "new_session_ids": new_sessions,
        "brief_diff_excerpt": _diff_excerpt(expanded),
        # baseline_brief / expanded_brief are kept for tests; they
        # are NOT emitted in the CLI's table or JSON to keep the
        # operator-facing output legible.
        "baseline_brief": baseline,
        "expanded_brief": expanded,
    }


# ── default queries derived from index ───────────────────────────


def default_queries_from_index(ix, *, top_n: int = 5) -> list[str]:
    """Pull the top-N entities by mention count and turn each into
    a "tell me about <canonical_name>" query. Guarantees default
    queries actually hit the user's data."""
    rows = ix._connect().execute(
        "SELECT e.canonical_name AS canonical_name, "
        "COUNT(m.id) AS n "
        "FROM entities e LEFT JOIN entity_mentions m "
        "ON m.entity_id = e.id "
        "GROUP BY e.id HAVING n > 0 "
        "ORDER BY n DESC, e.created_at ASC "
        "LIMIT ?",
        (int(top_n),),
    ).fetchall()
    return [f"tell me about {r['canonical_name']}" for r in rows]


# ── queries file ────────────────────────────────────────────────


def _load_queries_file(path: Path | str) -> list[str]:
    """One query per line; ``#`` comments and blank lines ignored."""
    out: list[str] = []
    with open(path, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            out.append(line)
    return out


# ── CLI ─────────────────────────────────────────────────────────


@dataclass
class CliConfig:
    queries: list[str]
    write_json: bool
    reference_time: datetime | None


def _format_table(results: list[dict]) -> str:
    """Terse table: query, baseline_chars, expanded_chars,
    new_entities, new_sessions. Diff excerpts are JSON-only."""
    lines = []
    lines.append(
        f"{'query':<40}  {'base':>5}  {'exp':>5}  "
        f"{'+ent':>4}  {'+ses':>4}"
    )
    lines.append("-" * 70)
    for r in results:
        q = r["query"]
        if len(q) > 40:
            q = q[:37] + "…"
        lines.append(
            f"{q:<40}  {r['baseline_chars']:>5}  "
            f"{r['expanded_chars']:>5}  {r['new_entities']:>4}  "
            f"{len(r['new_session_ids']):>4}"
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="python -m scripts.measure_entity_expansion",
        description=(
            "Lightweight A/B measurement of MAEZ_ENTITY_EXPANSION on "
            "lived-recall briefs. Read-only over all stores. "
            "Measures behaviour change, NOT relevance — operator "
            "reviews diff_excerpt to judge usefulness."
        ),
    )
    p.add_argument(
        "--query", action="append", default=[],
        help="Add a query to measure. Repeatable.",
    )
    p.add_argument(
        "--queries-file", type=Path, default=None,
        help="One query per line; '#' comments ignored.",
    )
    p.add_argument(
        "--top-n", type=int, default=5,
        help="When deriving default queries from the index, pull "
             "the top-N entities by mention count (default: 5).",
    )
    p.add_argument(
        "--index-db", type=Path, default=None,
        help="Override entity index DB path.",
    )
    p.add_argument(
        "--episodes-db", type=Path, default=None,
        help="Override episodes DB path.",
    )
    p.add_argument(
        "--graph-db", type=Path, default=None,
        help="Override relationship graph DB path.",
    )
    p.add_argument(
        "--reference-time", type=str, default=None,
        help="ISO8601 reference time for temporal annotation. "
             "Use a fixed value for reproducible diffs across runs.",
    )
    p.add_argument(
        "--json", action="store_true",
        help="Emit JSON to stdout (default: human-readable table).",
    )
    args = p.parse_args(argv)

    print(f"NOTE: {DISCLAIMER}", file=sys.stderr)

    # Resolve store paths (defaults via core.paths).
    try:
        from core.paths import memory_dir as _memdir
        default_mem = _memdir()
    except Exception:
        default_mem = Path("memory")

    index_path = args.index_db or default_mem / "entity_index.db"
    episodes_path = args.episodes_db or default_mem / "lived_episodes.db"
    graph_path = args.graph_db or default_mem / "lived_graph.db"

    if not Path(index_path).exists():
        print(
            f"warning: entity index not found at {index_path}. "
            "Run `python -m core.memory.entity_backfill --write` to "
            "populate, or `python -m core.memory.entity_alias_seed "
            "--write` to seed aliases first.",
            file=sys.stderr,
        )
        return 0
    if not Path(episodes_path).exists():
        print(
            f"warning: episodes db not found at {episodes_path}.",
            file=sys.stderr,
        )
        return 0

    from core.memory.entity_index import EntityIndex
    from core.memory.episodes import EpisodeStore
    from core.memory.relationship_graph import RelationshipGraph

    ix = EntityIndex(index_path)
    episodes = EpisodeStore(str(episodes_path))
    graph = RelationshipGraph(str(graph_path))

    # Empty-index guard. Warn + exit 0 — automation friendly.
    n_entities = ix._connect().execute(
        "SELECT COUNT(*) FROM entities"
    ).fetchone()[0]
    n_mentions = ix._connect().execute(
        "SELECT COUNT(*) FROM entity_mentions"
    ).fetchone()[0]
    if n_entities == 0 or n_mentions == 0:
        print(
            f"warning: entity index is empty "
            f"(entities={n_entities}, mentions={n_mentions}). "
            "Nothing to measure. Run "
            "`python -m core.memory.entity_alias_seed --write` "
            "(seed aliases) and "
            "`python -m core.memory.entity_backfill --write` "
            "(populate mentions) first.",
            file=sys.stderr,
        )
        return 0

    # Resolve queries.
    queries: list[str] = list(args.query)
    if args.queries_file:
        queries.extend(_load_queries_file(args.queries_file))
    if not queries:
        queries = default_queries_from_index(ix, top_n=args.top_n)
        if not queries:
            print(
                "warning: no queries supplied and no entities with "
                "mentions in the index. Pass --query or "
                "--queries-file to override.",
                file=sys.stderr,
            )
            return 0

    ref_time: datetime | None = None
    if args.reference_time:
        try:
            ref_time = datetime.fromisoformat(args.reference_time)
        except ValueError as e:
            print(
                f"error: invalid --reference-time {args.reference_time!r}: {e}",
                file=sys.stderr,
            )
            return 2

    # Run measurements.
    results: list[dict] = []
    for q in queries:
        m = measure(
            q,
            ix=ix, episode_store=episodes, graph=graph,
            reference_time=ref_time,
        )
        # The full briefs are huge; strip from CLI output (they're
        # available to library callers via the dict).
        public = {k: v for k, v in m.items()
                  if k not in {"baseline_brief", "expanded_brief"}}
        results.append(public)

    if args.json:
        payload = {
            "disclaimer": DISCLAIMER,
            "results": results,
        }
        print(json.dumps(payload, indent=2, sort_keys=True, default=str))
    else:
        print(_format_table(results))
        # Plain-text mode: append the diff excerpt per query so the
        # operator can review without flipping to --json. Excerpts
        # are short by spec (section + 3 lead lines), so this stays
        # readable at the terminal.
        for r in results:
            if r["brief_diff_excerpt"]:
                print()
                print(f"--- {r['query']} ---")
                print(r["brief_diff_excerpt"])

    return 0


__all__ = [
    "DISCLAIMER",
    "default_queries_from_index",
    "main",
    "measure",
]


if __name__ == "__main__":
    raise SystemExit(main())
