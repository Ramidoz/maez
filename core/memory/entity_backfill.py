# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Deterministic entity-index backfill (Step 5f).

Walks the lived-memory ``EpisodeStore``, runs the Step-5e
deterministic extractor on each episode's title + summary +
open_loop, and populates the Step-5e ``EntityIndex``. Read-only over
lived memory; only writes ``memory/entity_index.db``.

Hard contract — what this module is NOT:

  • No LLM, no network, no subprocess. Pinned by tests that
    intercept subprocess.run / socket.socket inside the public
    entry point.
  • No mutation of the EpisodeStore — episodes are read via
    ``list_active`` only.
  • No alias seeding. Aliases come from explicit owner action,
    not from the extractor; this slice intentionally leaves
    ambiguity-aware confidence at canonical-only matches.
  • No Chroma walking. Episodes-only this slice; raw/core
    walking is a separate, larger surface.

Provenance contract: title and summary are episode-level
consolidator text, not verbatim source-memory text. Every
backfilled mention sets ``source_id = session_id = episode_id``;
the source_memory_ids list on the episode is intentionally NOT
threaded through, because no extractor finding can be honestly
attributed to a specific source memory.

Time precedence (matches Step-5c temporal annotation):
``observed_at = occurred_at if present, else created_at``.

Snippet rule:
  • Title hit  → snippet = full title
  • Summary hit → snippet = 60-char window centred on the span
  • Open-loop hit → snippet = 60-char window centred on the span

Idempotency: the EntityIndex schema's UNIQUE constraints make
double-write a no-op, but the backfill computes ``new_*`` vs
``already_present_*`` separately so a re-run that does nothing
reports honestly rather than claiming work it didn't do.
"""

from __future__ import annotations

import argparse
import logging
import statistics
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.memory.entity_index import EntityIndex
    from core.memory.episodes import EpisodeStore

logger = logging.getLogger(__name__)


_SNIPPET_WINDOW = 60  # chars centred on the span for non-title hits
_TOP_N = 20


# ── report dataclass ──────────────────────────────────────────────


@dataclass
class BackfillReport:
    """Backfill summary. The metric set is the one Step-5f's pushback
    round selected: cross-session-evidence (the MSEL-success signal)
    and extractor sparsity (the "wire vs harden" decision input)."""

    episodes_scanned: int = 0
    episodes_with_zero_entities: int = 0

    new_entities: int = 0
    already_present_entities: int = 0
    new_mentions: int = 0
    already_present_mentions: int = 0

    distinct_entities: int = 0
    entities_in_2plus_sessions: int = 0
    mentions_per_entity_median: float = 0.0
    mentions_per_entity_max: int = 0

    top_entities: list[dict] = field(default_factory=list)
    write_mode: bool = False

    def render_text(self) -> str:
        """CLI-friendly rendering. Disclaimer-led so the operator
        sees the read-only / dry-run / write status before the
        numbers."""
        head = (
            "WRITE MODE — entity_index.db updated."
            if self.write_mode
            else "DRY RUN — no writes occurred. Use --write to commit."
        )
        lines = [head, ""]
        lines.append(f"episodes scanned:              {self.episodes_scanned}")
        lines.append(
            f"episodes with zero entities:   {self.episodes_with_zero_entities}"
        )
        lines.append("")
        lines.append(f"new entities:                  {self.new_entities}")
        lines.append(
            f"already-present entities:      {self.already_present_entities}"
        )
        lines.append(f"new mentions:                  {self.new_mentions}")
        lines.append(
            f"already-present mentions:      {self.already_present_mentions}"
        )
        lines.append("")
        lines.append(f"distinct entities:             {self.distinct_entities}")
        lines.append(
            f"entities in ≥2 sessions:       {self.entities_in_2plus_sessions}"
        )
        lines.append(
            f"mentions/entity median:        "
            f"{self.mentions_per_entity_median:.2f}"
        )
        lines.append(
            f"mentions/entity max:           {self.mentions_per_entity_max}"
        )
        lines.append("")
        lines.append("top entities (canonical, mentions, distinct sessions):")
        if self.top_entities:
            for row in self.top_entities:
                lines.append(
                    f"  {row['canonical_name']:<40s}  "
                    f"{row['mention_count']:>4}  {row['distinct_sessions']:>4}"
                )
        else:
            lines.append("  (none)")
        return "\n".join(lines)


# ── extraction over one episode ───────────────────────────────────


def _observed_at_for(episode: dict) -> str:
    """Step-5c precedence: occurred_at if present, else created_at.
    Episodes always carry a created_at, so this never returns None
    for a real episode row."""
    occ = episode.get("occurred_at")
    if occ:
        return occ
    return episode["created_at"]


def _snippet_for_summary_hit(text: str, span_start: int, span_end: int) -> str:
    """60-char window centred on the span. Trims to text bounds."""
    midpoint = (span_start + span_end) // 2
    half = _SNIPPET_WINDOW // 2
    lo = max(0, midpoint - half)
    hi = min(len(text), lo + _SNIPPET_WINDOW)
    if hi - lo < _SNIPPET_WINDOW:
        lo = max(0, hi - _SNIPPET_WINDOW)
    return text[lo:hi].strip()


def _entities_from_episode(episode: dict) -> list[tuple]:
    """Return ``[(normalized, canonical_surface, snippet, confidence), ...]``
    for one episode. Runs the extractor against title, summary, and
    open_loop independently so the snippet rule can be applied
    correctly per-source-segment.

    Dedupe within an episode is left to the caller — the index's
    UNIQUE(entity_id, session_id, source_id) handles double-mentions
    from title + summary as a single mention row."""
    from core.memory.entity_index import extract_deterministic_entities

    out: list[tuple] = []
    title = episode.get("title") or ""
    summary = episode.get("summary") or ""
    open_loop = episode.get("open_loop") or ""

    for cand in extract_deterministic_entities(title):
        out.append((
            cand.normalized, cand.surface, title, cand.confidence,
        ))
    for cand in extract_deterministic_entities(summary):
        snip = _snippet_for_summary_hit(
            summary, cand.span_start, cand.span_end,
        )
        out.append((cand.normalized, cand.surface, snip, cand.confidence))
    if open_loop:
        for cand in extract_deterministic_entities(open_loop):
            snip = _snippet_for_summary_hit(
                open_loop, cand.span_start, cand.span_end,
            )
            out.append((
                cand.normalized, cand.surface, snip, cand.confidence,
            ))
    return out


# ── public entry point ────────────────────────────────────────────


def backfill(
    *,
    episodes: "EpisodeStore",
    ix: "EntityIndex",
    write: bool = False,
) -> BackfillReport:
    """Walk the EpisodeStore, extract deterministic entity candidates,
    and (when ``write=True``) populate the EntityIndex with both the
    canonical entities and per-episode mentions.

    Default ``write=False`` is the dry-run path: nothing is inserted,
    but the report still computes honest "would-insert" counts by
    checking existence per (entity, session, source) before writing.

    The handler is the only public API. Callers can construct their
    own EpisodeStore and EntityIndex (the CLI does this), or use the
    ``main`` argv entry."""

    report = BackfillReport(write_mode=write)
    rows = episodes.list_active() or []
    report.episodes_scanned = len(rows)

    # Snapshot existing state so dry-run can compute new vs
    # already-present without committing anything. The keyset is
    # cheap: normalized name + kind for entities, (entity_id,
    # session_id, source_id) for mentions.
    con = ix._connect()
    existing_entities: dict[tuple[str, str], str] = {}
    for row in con.execute(
        "SELECT id, normalized_name, kind FROM entities"
    ).fetchall():
        existing_entities[(row["normalized_name"], row["kind"])] = row["id"]

    existing_mentions: set[tuple[str, str, str]] = set()
    for row in con.execute(
        "SELECT entity_id, session_id, source_id FROM entity_mentions"
    ).fetchall():
        existing_mentions.add(
            (row["entity_id"], row["session_id"], row["source_id"]),
        )

    # In-memory plan: entity normalized → ent_id (real or planned),
    # plus per-episode mention plans. The plan drives the report
    # accounting; the ``write`` branch executes it via the index's
    # idempotent upserts.
    planned_entities: dict[tuple[str, str], str] = {}
    planned_mentions_by_ep: dict[str, list[dict]] = {}

    new_ent_count = 0
    seen_ent_count = 0
    new_men_count = 0
    seen_men_count = 0

    # Track distinct sessions per planned entity to compute
    # entities_in_2plus_sessions and the mention-distribution stats.
    sessions_per_norm: dict[tuple[str, str], set[str]] = {}
    mentions_per_norm: dict[tuple[str, str], int] = {}
    canonical_for_norm: dict[tuple[str, str], str] = {}

    for ep in rows:
        eid = ep["id"]
        observed_at = _observed_at_for(ep)
        cands = _entities_from_episode(ep)
        if not cands:
            report.episodes_with_zero_entities += 1
            continue

        # Dedup within-episode by normalized — the index's UNIQUE
        # collapses (entity, session, source) anyway, but we want
        # the "title-hit snippet wins over summary-hit snippet"
        # rule applied here so the recorded snippet is the title
        # when the entity appears in both.
        per_episode: dict[str, dict] = {}
        title_text = ep.get("title") or ""
        for normalized, surface, snippet, confidence in cands:
            slot = per_episode.get(normalized)
            is_title_snippet = snippet == title_text
            if slot is None:
                per_episode[normalized] = {
                    "surface": surface,
                    "snippet": snippet,
                    "confidence": confidence,
                }
            elif is_title_snippet:
                slot["snippet"] = title_text
                slot["confidence"] = max(slot["confidence"], confidence)

        ep_plan: list[dict] = []
        for normalized, info in per_episode.items():
            kind = "unknown"
            key = (normalized, kind)

            ent_id = existing_entities.get(key) or planned_entities.get(key)
            if ent_id is None:
                ent_id = f"<planned:{normalized}>"
                planned_entities[key] = ent_id
                new_ent_count += 1
            elif key not in canonical_for_norm:
                seen_ent_count += 1

            # First-write canonical wins; we don't overwrite a
            # canonical surface once recorded, but we keep the
            # extractor's surface as the upsert input below.
            canonical_for_norm.setdefault(key, info["surface"])
            sessions_per_norm.setdefault(key, set()).add(eid)
            mentions_per_norm[key] = mentions_per_norm.get(key, 0) + 1

            mention_key = (ent_id, eid, eid)
            if mention_key in existing_mentions:
                seen_men_count += 1
                continue
            new_men_count += 1
            ep_plan.append({
                "key": key,
                "surface": info["surface"],
                "snippet": info["snippet"],
                "confidence": info["confidence"],
                "observed_at": observed_at,
                "source_kind": "episode",
            })

        if ep_plan:
            planned_mentions_by_ep[eid] = ep_plan

    if write:
        for eid, plan in planned_mentions_by_ep.items():
            for entry in plan:
                key = entry["key"]
                normalized, kind = key
                ent_id = existing_entities.get(key)
                if ent_id is None:
                    ent_id = ix.upsert_entity(
                        canonical_for_norm[key], kind=kind,
                    )
                    existing_entities[key] = ent_id
                ix.add_mention(
                    entity_id=ent_id,
                    session_id=eid,
                    source_id=eid,
                    source_kind=entry["source_kind"],
                    observed_at=entry["observed_at"],
                    snippet=entry["snippet"],
                    confidence=entry["confidence"],
                )

    # ── report numbers ────────────────────────────────────────────
    report.new_entities = new_ent_count
    report.already_present_entities = seen_ent_count
    report.new_mentions = new_men_count
    report.already_present_mentions = seen_men_count

    # Distinct entities and cross-session metric: union of existing
    # + planned for the dry-run path; the existence checks above
    # already counted both.
    all_keys = set(existing_entities.keys()) | set(planned_entities.keys())
    report.distinct_entities = len(all_keys)
    report.entities_in_2plus_sessions = sum(
        1 for sessions in sessions_per_norm.values() if len(sessions) >= 2
    )

    if mentions_per_norm:
        counts = sorted(mentions_per_norm.values())
        report.mentions_per_entity_max = max(counts)
        report.mentions_per_entity_median = float(statistics.median(counts))
    else:
        report.mentions_per_entity_max = 0
        report.mentions_per_entity_median = 0.0

    # Top-N by total mentions, breaking ties by distinct sessions
    # (so a more cross-session entity ranks higher when counts tie).
    enriched = []
    for key, count in mentions_per_norm.items():
        enriched.append({
            "canonical_name": canonical_for_norm.get(key, key[0]),
            "kind": key[1],
            "mention_count": count,
            "distinct_sessions": len(sessions_per_norm.get(key, set())),
        })
    enriched.sort(
        key=lambda r: (r["mention_count"], r["distinct_sessions"]),
        reverse=True,
    )
    report.top_entities = enriched[:_TOP_N]

    return report


# ── CLI ───────────────────────────────────────────────────────────


def _default_episodes_path() -> Path:
    """Match the daemon's default: ``<memory>/lived_episodes.db``.
    Routed through ``core.paths`` so a non-default MAEZ_HOME works."""
    try:
        from core import paths as _paths
        return _paths.memory_dir() / "lived_episodes.db"
    except Exception:
        return Path("memory/lived_episodes.db")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="python -m core.memory.entity_backfill",
        description=(
            "Deterministic backfill of memory/entity_index.db from "
            "the lived-memory EpisodeStore. Read-only over lived "
            "memory; dry-run by default — use --write to commit."
        ),
    )
    p.add_argument(
        "--episodes-db", type=Path, default=None,
        help="Override episodes DB path "
             "(default: <memory>/lived_episodes.db).",
    )
    p.add_argument(
        "--index-db", type=Path, default=None,
        help="Override entity index DB path "
             "(default: <memory>/entity_index.db).",
    )
    p.add_argument(
        "--write", action="store_true",
        help="Commit writes to the entity index. Without this flag "
             "the run is a dry run and nothing is inserted.",
    )
    p.add_argument(
        "--dry-run", action="store_true",
        help="Explicit dry-run flag (default behaviour). Provided "
             "for symmetry with --write.",
    )
    args = p.parse_args(argv)

    if args.write and args.dry_run:
        print(
            "error: --write and --dry-run are mutually exclusive",
            file=sys.stderr,
        )
        return 2

    from core.memory.entity_index import EntityIndex
    from core.memory.episodes import EpisodeStore

    ep_path = args.episodes_db or _default_episodes_path()
    if not Path(ep_path).exists():
        print(
            f"error: episodes db not found at {ep_path}",
            file=sys.stderr,
        )
        return 2

    episodes = EpisodeStore(str(ep_path))
    ix = (
        EntityIndex(args.index_db) if args.index_db else EntityIndex()
    )

    report = backfill(episodes=episodes, ix=ix, write=bool(args.write))
    print(report.render_text())
    if not args.write:
        print(
            "\nNOTE: dry-run only. Re-run with --write to populate "
            "memory/entity_index.db. The backfill never mutates the "
            "EpisodeStore and never calls subprocess or network.",
            file=sys.stderr,
        )
    return 0


__all__ = ["BackfillReport", "backfill", "main"]


if __name__ == "__main__":
    raise SystemExit(main())
