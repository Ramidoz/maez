# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Alias-candidate suggester (Step 5l).

Reads existing lived-memory episodes and proposes alias candidates
in the same YAML shape ``entity_alias_seed`` consumes. The operator
reviews the output and copy-pastes the useful suggestions into
``config/entity_aliases.local.yaml``.

Hard contract:

  • No LLM, no network, no subprocess. Pure deterministic
    heuristics over text already on disk.
  • No writes to ``config/entity_aliases.local.yaml``. v1
    deliberately does NOT support ``--write``: the cost of a bad
    auto-merge into the operator's curated file is high; the
    benefit of saving a paste is low. The CLI prints YAML to
    stdout; the operator pastes manually after review.
  • Honest about being a HEURISTIC. The CLI banner and the
    emitted YAML's leading comment make clear that suggestions
    require operator judgement before becoming canonical.

Heuristics (deterministic only):

  1. Multi-token capitalized phrases that appear in episode text
     (``extract_deterministic_entities``-shaped). Every distinct
     phrase becomes a candidate canonical entity.
  2. Standalone capitalized tokens that match a token from a
     candidate canonical name → suggested as alias for that
     canonical (e.g. "Maya" appearing on its own in episodes that
     also mentioned "Maya Ananthan").
  3. Sentence-start stopwords ("The", "Tomorrow", etc.) are NEVER
     emitted as aliases — same filter the deterministic extractor
     uses.
  4. When ``ix`` is supplied: existing canonical entities with
     ZERO aliases get short-form-token suggestions from the
     corpus. Already-aliased entities are skipped — the
     suggester fills gaps, not duplicates curated work.
"""

from __future__ import annotations

import argparse
import logging
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.memory.entity_index import EntityIndex
    from core.memory.episodes import EpisodeStore

logger = logging.getLogger(__name__)


_TOP_EVIDENCE_EPISODES = 3


# ── dataclass ────────────────────────────────────────────────────


@dataclass
class Suggestion:
    """One candidate entity (with optional aliases) to consider for
    seeding into the local alias file. Operator decides whether to
    accept; the suggester is a search aid, not an authority."""
    canonical_name: str
    kind: str = "unknown"
    aliases: list[str] = field(default_factory=list)
    canonical_episode_count: int = 0
    canonical_evidence_episode_ids: list[str] = field(default_factory=list)
    canonical_evidence_snippets: list[str] = field(default_factory=list)
    alias_episode_counts: dict[str, int] = field(default_factory=dict)
    notes: str = ""


# ── corpus walk ──────────────────────────────────────────────────


_CAP_TOKEN_RE = re.compile(r"\b[A-Z][a-zA-Z'\-]*\b")


def _segments_for_episode(ep: dict) -> list[tuple[str, str]]:
    """``[(label, text), ...]`` for the segments the suggester
    scans. Same surfaces the backfill walks: title, summary,
    open_loop."""
    return [
        ("title", ep.get("title") or ""),
        ("summary", ep.get("summary") or ""),
        ("open_loop", ep.get("open_loop") or ""),
    ]


def _walk_corpus(episodes: "EpisodeStore"):
    """Yield ``(episode_id, label, text)`` triples for every
    non-empty text segment across all active episodes."""
    rows = episodes.list_active() or []
    for ep in rows:
        for label, text in _segments_for_episode(ep):
            if text:
                yield ep["id"], label, text


# ── candidate aggregation ────────────────────────────────────────


def _multi_token_candidates(
    episodes: "EpisodeStore",
) -> dict[str, dict]:
    """Aggregate distinct multi-token capitalized phrases the
    deterministic extractor would emit, with the episodes they
    appeared in. Returns ``{normalized_name: {canonical, episode_ids,
    snippets, count}}``."""
    from core.memory.entity_index import (
        extract_deterministic_entities, normalize_entity_name,
    )

    agg: dict[str, dict] = {}
    for ep_id, label, text in _walk_corpus(episodes):
        for cand in extract_deterministic_entities(text):
            normalized = normalize_entity_name(cand.surface)
            if not normalized:
                continue
            slot = agg.setdefault(normalized, {
                "canonical": cand.surface,
                "episode_ids": [],
                "snippets": [],
                "count": 0,
            })
            slot["count"] += 1
            if ep_id not in slot["episode_ids"]:
                slot["episode_ids"].append(ep_id)
                if (
                    label == "title"
                    and len(slot["snippets"]) < _TOP_EVIDENCE_EPISODES
                ):
                    slot["snippets"].append(text)
                elif len(slot["snippets"]) < _TOP_EVIDENCE_EPISODES:
                    span_start = cand.span_start
                    span_end = cand.span_end
                    lo = max(0, span_start - 30)
                    hi = min(len(text), span_end + 30)
                    slot["snippets"].append(text[lo:hi].strip())
    return agg


def _standalone_token_counts(
    episodes: "EpisodeStore",
    *,
    multi_token_spans_by_episode: dict[str, list[tuple[int, int, str]]],
) -> dict[str, dict[str, int]]:
    """For each capitalized standalone token in the corpus, count
    the episodes it appears in OUTSIDE any multi-token-cap span and
    NOT at sentence-start stopword position. Returns
    ``{normalized_token: {episode_id: count}}``.

    Sentence-start stopword detection mirrors the extractor's
    filter, so "Tomorrow Maya" doesn't promote "Tomorrow" as an
    alias candidate."""
    from core.memory.entity_index import (
        _SENTENCE_START_STOPWORDS, normalize_entity_name,
    )

    sentence_boundary_re = re.compile(r"(?<=[.!?])\s+")

    out: dict[str, dict[str, int]] = {}
    rows = episodes.list_active() or []
    for ep in rows:
        ep_id = ep["id"]
        for label, text in _segments_for_episode(ep):
            if not text:
                continue
            sentence_starts = {0}
            for m in sentence_boundary_re.finditer(text):
                sentence_starts.add(m.end())

            multi_spans = [
                (s, e) for s, e, ep2 in
                multi_token_spans_by_episode.get(ep_id, [])
                if ep2 == f"{ep_id}:{label}"
            ]

            for tok_match in _CAP_TOKEN_RE.finditer(text):
                ts, te = tok_match.start(), tok_match.end()
                if any(s <= ts < e or s < te <= e for s, e in multi_spans):
                    continue
                surface = tok_match.group(0)
                normalized = normalize_entity_name(surface)
                if not normalized:
                    continue
                if (
                    ts in sentence_starts
                    and normalized in _SENTENCE_START_STOPWORDS
                ):
                    continue
                out.setdefault(normalized, {}).setdefault(ep_id, 0)
                out[normalized][ep_id] += 1
    return out


def _multi_token_spans_index(
    episodes: "EpisodeStore",
) -> dict[str, list[tuple[int, int, str]]]:
    """Per-episode-segment list of multi-token spans so the
    standalone-token pass can exclude tokens already inside a
    multi-token candidate. Spans are tagged with ``f"{ep_id}:{label}"``
    to disambiguate per-segment."""
    from core.memory.entity_index import extract_deterministic_entities

    out: dict[str, list[tuple[int, int, str]]] = {}
    rows = episodes.list_active() or []
    for ep in rows:
        ep_id = ep["id"]
        seg_list = []
        for label, text in _segments_for_episode(ep):
            if not text:
                continue
            for cand in extract_deterministic_entities(text):
                seg_list.append((
                    cand.span_start, cand.span_end, f"{ep_id}:{label}",
                ))
        if seg_list:
            out[ep_id] = seg_list
    return out


# ── public API ───────────────────────────────────────────────────


def suggest_aliases(
    *,
    episodes: "EpisodeStore",
    ix: "EntityIndex | None" = None,
) -> list[Suggestion]:
    """Walk the corpus and return alias-candidate suggestions.

    Strategy:

      1. Find every multi-token capitalized phrase in the corpus.
         Each becomes a candidate canonical entity.
      2. For each candidate, look at its individual capitalized
         tokens; if any appear standalone elsewhere in the corpus
         (outside multi-token spans, not sentence-start junk),
         suggest them as aliases.
      3. If ``ix`` is supplied, also look at existing canonical
         entities with ZERO aliases — suggest standalone short
         forms found in the corpus as candidate aliases. Skip
         entities that already have aliases (the suggester fills
         gaps, not duplicates).
    """
    from core.memory.entity_index import normalize_entity_name

    multi_candidates = _multi_token_candidates(episodes)
    spans_by_ep = _multi_token_spans_index(episodes)
    standalone = _standalone_token_counts(
        episodes, multi_token_spans_by_episode=spans_by_ep,
    )

    # Snapshot ix state for "fill gaps only" behaviour.
    existing_zero_alias: dict[tuple[str, str], dict] = {}
    existing_any_alias: set[tuple[str, str]] = set()
    if ix is not None:
        con = ix._connect()
        ent_rows = con.execute(
            "SELECT id, canonical_name, normalized_name, kind "
            "FROM entities"
        ).fetchall()
        for r in ent_rows:
            key = (r["normalized_name"], r["kind"])
            alias_count = con.execute(
                "SELECT COUNT(*) FROM aliases WHERE entity_id = ?",
                (r["id"],),
            ).fetchone()[0]
            if alias_count > 0:
                existing_any_alias.add(key)
            else:
                existing_zero_alias[key] = dict(r)

    suggestions: list[Suggestion] = []

    # Pass 1 — multi-token candidates from the corpus.
    for normalized, info in sorted(
        multi_candidates.items(),
        key=lambda kv: (-kv[1]["count"], kv[0]),
    ):
        canonical = info["canonical"]
        canonical_kind = "unknown"
        # Defer to ix-recorded kind when available — the operator
        # may have already seeded this entity with a real kind.
        for (norm, kind) in existing_zero_alias.keys():
            if norm == normalized:
                canonical_kind = kind
                break
        for (norm, kind) in existing_any_alias:
            if norm == normalized:
                # Already aliased by the operator; skip duplicate
                # work (per the "fill gaps only" rule).
                canonical_kind = None
                break
        if canonical_kind is None:
            continue

        alias_candidates: list[str] = []
        alias_episode_counts: dict[str, int] = {}
        # Tokenize the canonical surface and check each individual
        # capitalized token for standalone usage elsewhere.
        for tok in _CAP_TOKEN_RE.findall(canonical):
            n = normalize_entity_name(tok)
            if n == normalized:
                # the full canonical itself; not a useful alias
                continue
            if len(n) < 2:
                # Single-letter tokens are heuristic noise — "A"
                # in "Track A" matches "A" anywhere standalone, but
                # the operator never wants single letters as alias
                # surfaces. The deterministic extractor's
                # ≥2-token rule already catches the parts that
                # matter; this filter is the alias-pass analogue.
                continue
            ep_counts = standalone.get(n, {})
            if ep_counts:
                if tok not in alias_candidates:
                    alias_candidates.append(tok)
                    alias_episode_counts[tok] = sum(ep_counts.values())

        ep_count = len(info["episode_ids"])
        notes_lines = [
            f"'{canonical}' appears in {ep_count} episode(s) "
            f"({info['count']} mentions total).",
        ]
        for tok, n in alias_episode_counts.items():
            notes_lines.append(
                f"'{tok}' standalone in {n} occurrence(s) elsewhere "
                "in the corpus."
            )

        suggestions.append(Suggestion(
            canonical_name=canonical,
            kind=canonical_kind,
            aliases=alias_candidates,
            canonical_episode_count=ep_count,
            canonical_evidence_episode_ids=list(
                info["episode_ids"][:_TOP_EVIDENCE_EPISODES],
            ),
            canonical_evidence_snippets=list(info["snippets"]),
            alias_episode_counts=alias_episode_counts,
            notes="\n".join(notes_lines),
        ))

    # Pass 2 — fill gaps for ix entities with zero aliases.
    if ix is not None:
        for (norm, kind), row in existing_zero_alias.items():
            if any(
                s.canonical_name == row["canonical_name"]
                and s.kind == kind
                for s in suggestions
            ):
                continue
            canonical = row["canonical_name"]
            alias_candidates: list[str] = []
            alias_episode_counts: dict[str, int] = {}
            for tok in _CAP_TOKEN_RE.findall(canonical):
                n = normalize_entity_name(tok)
                if n == norm:
                    continue
                if len(n) < 2:
                    continue
                ep_counts = standalone.get(n, {})
                if ep_counts:
                    if tok not in alias_candidates:
                        alias_candidates.append(tok)
                        alias_episode_counts[tok] = sum(ep_counts.values())
            if not alias_candidates:
                # Nothing to add; skip — empty-suggestion noise is
                # worse than silence.
                continue
            notes_lines = [
                "existing entity in index has 0 aliases; "
                "corpus standalone usage suggests:",
            ]
            for tok, n in alias_episode_counts.items():
                notes_lines.append(
                    f"  '{tok}' in {n} occurrence(s)."
                )
            suggestions.append(Suggestion(
                canonical_name=canonical,
                kind=kind,
                aliases=alias_candidates,
                canonical_episode_count=0,
                canonical_evidence_episode_ids=[],
                canonical_evidence_snippets=[],
                alias_episode_counts=alias_episode_counts,
                notes="\n".join(notes_lines),
            ))

    return suggestions


# ── YAML emission ────────────────────────────────────────────────


_LEAD_COMMENT = """\
# AUTO-GENERATED ALIAS-CANDIDATE SUGGESTIONS — Step 5l.
#
# These are HEURISTIC candidates produced by the deterministic
# alias suggester. They are NOT canonical until the operator
# reviews them and decides which to keep. Suggestions can include:
#
#   • Multi-token capitalized phrases the corpus mentions.
#   • Short-form tokens that co-occur with a longer canonical name.
#   • Existing entity-index entries with zero aliases that have
#     standalone short-form usage in the corpus.
#
# Workflow: review → copy useful entries into
# config/entity_aliases.local.yaml → run
# `python -m core.memory.entity_alias_seed --write` and
# `python -m core.memory.entity_backfill --write` → re-measure
# with `python -m scripts.measure_entity_expansion`.
"""


def format_yaml(suggestions: list[Suggestion]) -> str:
    """Emit the suggestions as a YAML document the alias_seed
    loader can validate. Per-entity ``notes`` capture the heuristic
    evidence so the operator can judge each candidate quickly."""
    if not suggestions:
        return _LEAD_COMMENT + "\nentities: []\n"

    lines = [_LEAD_COMMENT, "entities:"]
    for s in suggestions:
        lines.append(f"  - canonical_name: {_yaml_str(s.canonical_name)}")
        lines.append(f"    kind: {_yaml_str(s.kind)}")
        if s.aliases:
            lines.append("    aliases:")
            for a in s.aliases:
                lines.append(f"      - {_yaml_str(a)}")
        else:
            lines.append("    aliases: []")
        if s.notes:
            # YAML literal block — preserves newlines, no escapes.
            lines.append("    notes: |-")
            for note_line in s.notes.splitlines():
                lines.append(f"      {note_line}")
        if s.canonical_evidence_episode_ids:
            lines.append(
                "    # evidence (review only — alias_seed loader "
                "ignores comments):"
            )
            for eid in s.canonical_evidence_episode_ids:
                lines.append(f"    #   episode: {eid}")
            for snip in s.canonical_evidence_snippets:
                lines.append(f"    #   snippet: {_truncate(snip, 80)!r}")
    return "\n".join(lines) + "\n"


def _yaml_str(value: str) -> str:
    """Quote when the value contains characters that would
    otherwise be parsed as YAML structure. Conservative: always
    double-quote with backslash-escapes for safety."""
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _truncate(text: str, n: int) -> str:
    text = text.strip()
    if len(text) <= n:
        return text
    return text[: n - 1] + "…"


# ── CLI ──────────────────────────────────────────────────────────


def _default_episodes_path() -> Path:
    try:
        from core import paths as _paths
        return _paths.memory_dir() / "lived_episodes.db"
    except Exception:
        return Path("memory/lived_episodes.db")


def _default_index_path() -> Path:
    try:
        from core import paths as _paths
        return _paths.memory_dir() / "entity_index.db"
    except Exception:
        return Path("memory/entity_index.db")


_DISCLAIMER = (
    "This is a HEURISTIC suggester, not a labeller. Output is "
    "candidate suggestions only — review before merging into "
    "config/entity_aliases.local.yaml. No file is written by this "
    "command; copy/paste useful entries manually."
)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="python -m core.memory.entity_alias_suggester",
        description=(
            "Suggest entity-alias candidates from existing lived-"
            "memory episodes. Pure heuristic; no LLM, no network. "
            "Prints YAML to stdout for the operator to review and "
            "copy into config/entity_aliases.local.yaml."
        ),
    )
    p.add_argument(
        "--episodes-db", type=Path, default=None,
        help="Override episodes DB (default: "
             "<memory>/lived_episodes.db).",
    )
    p.add_argument(
        "--index-db", type=Path, default=None,
        help="If supplied, also surface ix entities with zero "
             "aliases that have short-form usage in the corpus. "
             "Default: <memory>/entity_index.db when present.",
    )
    p.add_argument(
        "--no-index", action="store_true",
        help="Suppress the ix-integration pass even if the index "
             "exists at the default path.",
    )
    args = p.parse_args(argv)

    print(f"NOTE: {_DISCLAIMER}", file=sys.stderr)

    ep_path = args.episodes_db or _default_episodes_path()
    if not Path(ep_path).exists():
        print(
            f"warning: episodes db not found at {ep_path}",
            file=sys.stderr,
        )
        return 0

    from core.memory.episodes import EpisodeStore

    episodes = EpisodeStore(str(ep_path))

    ix = None
    if not args.no_index:
        ix_path = args.index_db or _default_index_path()
        if Path(ix_path).exists():
            from core.memory.entity_index import EntityIndex
            ix = EntityIndex(ix_path)

    rows = episodes.list_active() or []
    if not rows:
        print(
            "# no episodes in store; nothing to suggest.",
            file=sys.stderr,
        )
        print(_LEAD_COMMENT)
        print("entities: []")
        return 0

    suggestions = suggest_aliases(episodes=episodes, ix=ix)
    yaml_text = format_yaml(suggestions)
    sys.stdout.write(yaml_text)
    if not yaml_text.endswith("\n"):
        sys.stdout.write("\n")
    return 0


__all__ = ["Suggestion", "format_yaml", "main", "suggest_aliases"]


if __name__ == "__main__":
    raise SystemExit(main())
