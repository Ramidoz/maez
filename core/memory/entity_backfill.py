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
import re
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
    and extractor sparsity (the "wire vs harden" decision input).

    Step-5h adds split deterministic-vs-alias counts plus the
    per-alias hit map so the operator can see whether owner-curated
    seeding actually paid off in cross-session evidence."""

    episodes_scanned: int = 0
    episodes_with_zero_entities: int = 0

    new_entities: int = 0
    already_present_entities: int = 0
    new_mentions: int = 0
    already_present_mentions: int = 0

    # Step-5h split: deterministic = extractor-driven mentions;
    # alias = mentions created from owner-curated alias hits. Sums
    # equal new_mentions / already_present_mentions respectively.
    deterministic_mentions_new: int = 0
    deterministic_mentions_existing: int = 0
    alias_mentions_new: int = 0
    alias_mentions_existing: int = 0
    ambiguous_alias_mentions: int = 0
    alias_matches_by_alias: dict[str, int] = field(default_factory=dict)

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

        # Step-5h split + alias hit map. Suppressed when there is
        # no alias activity at all so the report stays terse for
        # plain Step-5f deterministic runs.
        if (
            self.alias_mentions_new
            or self.alias_mentions_existing
            or self.alias_matches_by_alias
        ):
            lines.append("")
            lines.append(
                f"deterministic mentions new/existing:  "
                f"{self.deterministic_mentions_new}/"
                f"{self.deterministic_mentions_existing}"
            )
            lines.append(
                f"alias mentions new/existing:          "
                f"{self.alias_mentions_new}/"
                f"{self.alias_mentions_existing}"
            )
            lines.append(
                f"ambiguous alias mentions:             "
                f"{self.ambiguous_alias_mentions}"
            )
            if self.alias_matches_by_alias:
                lines.append("")
                lines.append("alias matches by alias (episodes hit):")
                items = sorted(
                    self.alias_matches_by_alias.items(),
                    key=lambda kv: (-kv[1], kv[0]),
                )
                for surface, count in items:
                    lines.append(f"  {surface:<40s}  {count:>4}")

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


def _entities_from_episode(episode: dict) -> tuple:
    """Return ``(deterministic_findings, segment_extractor_spans)``
    for one episode.

    ``deterministic_findings`` is a list of
    ``(normalized, surface, snippet, confidence)`` tuples — same
    shape Step 5f produced. ``segment_extractor_spans`` maps each
    text-segment label ("title" / "summary" / "open_loop") to the
    list of ``(span_start, span_end)`` ranges the extractor
    claimed in that segment. The Step-5h alias pass needs those
    spans to enforce the overlap rule.
    """
    from core.memory.entity_index import extract_deterministic_entities

    findings: list[tuple] = []
    spans: dict[str, list[tuple[int, int]]] = {
        "title": [], "summary": [], "open_loop": [],
    }
    title = episode.get("title") or ""
    summary = episode.get("summary") or ""
    open_loop = episode.get("open_loop") or ""

    for cand in extract_deterministic_entities(title):
        spans["title"].append((cand.span_start, cand.span_end))
        findings.append((
            cand.normalized, cand.surface, title, cand.confidence,
        ))
    for cand in extract_deterministic_entities(summary):
        spans["summary"].append((cand.span_start, cand.span_end))
        snip = _snippet_for_summary_hit(
            summary, cand.span_start, cand.span_end,
        )
        findings.append(
            (cand.normalized, cand.surface, snip, cand.confidence),
        )
    if open_loop:
        for cand in extract_deterministic_entities(open_loop):
            spans["open_loop"].append((cand.span_start, cand.span_end))
            snip = _snippet_for_summary_hit(
                open_loop, cand.span_start, cand.span_end,
            )
            findings.append(
                (cand.normalized, cand.surface, snip, cand.confidence),
            )
    return findings, spans


# ── alias pass ────────────────────────────────────────────────────


def _spans_overlap(
    a: tuple[int, int], b: tuple[int, int],
) -> bool:
    """Half-open span overlap. ``[a0, a1)`` and ``[b0, b1)``."""
    return a[0] < b[1] and b[0] < a[1]


def _load_aliases_sorted_long_first(ix) -> list[dict]:
    """Load every alias row, sorted by alias length DESC so the
    overlap-drop rule reliably prefers longer aliases over shorter
    when they apply to the same span. Returns dicts shaped for the
    matcher: ``{alias, normalized_alias, entity_id}``."""
    with ix._connect() as con:
        rows = con.execute(
            "SELECT alias, normalized_alias, entity_id FROM aliases"
        ).fetchall()
    out = [dict(r) for r in rows]
    out.sort(key=lambda r: len(r["alias"]), reverse=True)
    return out


def _alias_pass(
    *,
    ix,
    episode: dict,
    extractor_spans_by_segment: dict[str, list[tuple[int, int]]],
    aliases_long_first: list[dict],
) -> list[dict]:
    """Run the alias scan on one episode. Returns a list of mention
    plans of the shape::

        {entity_id, snippet, confidence, observed_at, alias_surface,
         is_ambiguous_alias}

    Match contract:
      • ``\\b<re.escape(alias)>\\b``, case-insensitive (regex flag).
      • Exact spacing/punctuation; literal surface only. Owner adds
        variants explicitly — no fuzzy matching.
      • Overlap-drop: alias spans whose range overlaps any
        extractor-recorded span in the same segment, OR any earlier
        (longer) alias span recorded during this same pass, are
        dropped.

    Confidence:
      • Resolved via ``ix.find_entities(alias)`` so ambiguity-aware
        confidence (Step 5e) is preserved automatically: a unique
        alias hits at 1.0; an alias claimed by N entities returns
        each candidate at 1.0/N. The mention's stored confidence is
        the per-entity value, not the sum.
    """
    if not aliases_long_first:
        return []

    title = episode.get("title") or ""
    summary = episode.get("summary") or ""
    open_loop = episode.get("open_loop") or ""

    segments = (
        ("title", title),
        ("summary", summary),
        ("open_loop", open_loop),
    )

    # Cache resolution so the same alias surface doesn't re-query
    # the index per-segment.
    resolution_cache: dict[str, list] = {}

    def _resolve(alias_surface: str) -> list:
        if alias_surface not in resolution_cache:
            resolution_cache[alias_surface] = ix.find_entities(
                alias_surface,
            )
        return resolution_cache[alias_surface]

    plans: list[dict] = []

    # Track per-segment alias spans claimed during this pass so a
    # shorter alias can't slip in inside a longer alias's span.
    alias_spans_by_segment: dict[str, list[tuple[int, int]]] = {
        "title": [], "summary": [], "open_loop": [],
    }
    observed_at = _observed_at_for(episode)

    for alias_row in aliases_long_first:
        surface = alias_row["alias"]
        if not surface:
            continue
        # \b boundaries on a re.escape'd literal — exact spacing,
        # exact punctuation, case-insensitive only.
        try:
            pattern = re.compile(
                r"\b" + re.escape(surface) + r"\b",
                re.IGNORECASE,
            )
        except re.error:
            # An alias that escapes to an invalid regex never
            # matches; skip silently. Owners shouldn't be able to
            # craft one through normal seeding.
            continue

        for label, text in segments:
            if not text:
                continue
            extractor_spans = extractor_spans_by_segment.get(label, [])
            claimed_alias_spans = alias_spans_by_segment[label]
            for m in pattern.finditer(text):
                span = (m.start(), m.end())
                # Overlap rule: drop if any extractor span overlaps,
                # or any longer-alias span recorded earlier this
                # pass overlaps. Either way the slot is taken.
                if any(_spans_overlap(span, s) for s in extractor_spans):
                    continue
                if any(
                    _spans_overlap(span, s) for s in claimed_alias_spans
                ):
                    continue
                claimed_alias_spans.append(span)

                matches = _resolve(surface)
                if not matches:
                    continue
                is_ambiguous = len(matches) >= 2
                snippet = (
                    text if label == "title"
                    else _snippet_for_summary_hit(
                        text, span[0], span[1],
                    )
                )
                for ent in matches:
                    plans.append({
                        "entity_id": ent.entity_id,
                        "snippet": snippet,
                        "confidence": ent.confidence,
                        "observed_at": observed_at,
                        "alias_surface": surface,
                        "is_ambiguous_alias": is_ambiguous,
                    })
    return plans


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
    with ix._connect() as con:
        _entity_rows = con.execute(
            "SELECT id, normalized_name, kind FROM entities"
        ).fetchall()
        _mention_rows = con.execute(
            "SELECT entity_id, session_id, source_id FROM entity_mentions"
        ).fetchall()
    existing_entities: dict[tuple[str, str], str] = {}
    # Reverse map by normalized_name only — when the deterministic
    # pass finds 'Maya Ananthan' and an alias-seeded entity already
    # exists at that normalized name with kind='person', we should
    # use the seeded entity rather than minting a parallel
    # ('maya ananthan', 'unknown') row. Owner-curated kind wins
    # over the extractor's default.
    existing_by_normalized: dict[str, tuple[str, str]] = {}
    for row in _entity_rows:
        existing_entities[(row["normalized_name"], row["kind"])] = row["id"]
        prior = existing_by_normalized.get(row["normalized_name"])
        # Prefer a non-'unknown' kind when multiple kinds share a
        # normalized name; that's the curated-wins-over-default rule.
        if prior is None or (
            prior[1] == "unknown" and row["kind"] != "unknown"
        ):
            existing_by_normalized[row["normalized_name"]] = (
                row["id"], row["kind"],
            )

    existing_mentions: set[tuple[str, str, str]] = set()
    for row in _mention_rows:
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

    # Step-5h split counters. Sums match new_men_count and
    # seen_men_count respectively after both passes finish.
    det_new = 0
    det_existing = 0
    alias_new = 0
    alias_existing = 0
    ambiguous_alias = 0
    alias_match_episodes: dict[str, set[str]] = {}

    # Track distinct sessions per planned entity to compute
    # entities_in_2plus_sessions and the mention-distribution stats.
    sessions_per_norm: dict[tuple[str, str], set[str]] = {}
    mentions_per_norm: dict[tuple[str, str], int] = {}
    canonical_for_norm: dict[tuple[str, str], str] = {}

    # Index-wide alias rows, sorted longest-first for the overlap
    # rule. Loaded once outside the per-episode loop so we don't
    # re-query for every row.
    aliases_long_first = _load_aliases_sorted_long_first(ix)

    # Per-episode mention dedup against deterministic mentions —
    # alias resolution that produces the same (entity, episode)
    # pair as the deterministic pass should not be double-counted.
    # The index's UNIQUE catches it on write, but we want the
    # report to reflect "alias added a mention that wasn't already
    # there" vs "alias re-found a mention extractor already filed".
    # Tracked inside the per-episode loop via det_entities_this_episode.

    for ep in rows:
        eid = ep["id"]
        observed_at = _observed_at_for(ep)
        findings, extractor_spans_by_segment = _entities_from_episode(ep)
        alias_plans = _alias_pass(
            ix=ix,
            episode=ep,
            extractor_spans_by_segment=extractor_spans_by_segment,
            aliases_long_first=aliases_long_first,
        )
        if not findings and not alias_plans:
            report.episodes_with_zero_entities += 1
            continue
        cands = findings  # legacy name retained for the dedup loop below

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
        # Track which entities the deterministic pass placed in this
        # episode so the alias pass below can avoid double-counting.
        det_entities_this_episode: set[str] = set()
        for normalized, info in per_episode.items():
            # If an entity with this normalized name already exists
            # at any kind (alias seeding, prior backfill), use it
            # instead of minting a parallel kind='unknown' row.
            seeded = existing_by_normalized.get(normalized)
            if seeded is not None:
                kind = seeded[1]
            else:
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
            det_entities_this_episode.add(ent_id)
            if mention_key in existing_mentions:
                seen_men_count += 1
                det_existing += 1
                continue
            new_men_count += 1
            det_new += 1
            ep_plan.append({
                "key": key,
                "surface": info["surface"],
                "snippet": info["snippet"],
                "confidence": info["confidence"],
                "observed_at": observed_at,
                "source_kind": "episode",
                "_planned_mention_key": mention_key,
            })

        # ── alias pass dedup + accounting ─────────────────────────
        # Plans from _alias_pass already enforce span-level overlap
        # against extractor spans (the load-bearing rule). Here we
        # also dedup across entities the deterministic pass already
        # filed in THIS episode — an alias that resolves to the same
        # canonical entity the extractor caught is the same mention,
        # not a fresh one.
        already_planned_alias_keys: set[tuple[str, str, str]] = set()
        for plan in alias_plans:
            ent_id = plan["entity_id"]
            mention_key = (ent_id, eid, eid)
            if ent_id in det_entities_this_episode:
                # Same physical mention as the deterministic pass
                # already recorded; don't count or write again.
                continue
            if mention_key in already_planned_alias_keys:
                # Two aliases (e.g. canonical-shaped surface plus a
                # shorter alias) that resolved to the same entity
                # in the same episode. First wins; subsequent are
                # silently deduped.
                continue
            already_planned_alias_keys.add(mention_key)

            # Track per-alias episode hits regardless of write
            # status, so the alias_matches_by_alias dict reflects
            # actual matches (not derived from the index).
            alias_match_episodes.setdefault(
                plan["alias_surface"], set(),
            ).add(eid)

            if plan["is_ambiguous_alias"]:
                ambiguous_alias += 1

            if mention_key in existing_mentions:
                seen_men_count += 1
                alias_existing += 1
                continue
            new_men_count += 1
            alias_new += 1
            # Sessions-per-norm bookkeeping for alias-driven mentions:
            # we don't have a (normalized, kind) key for the alias
            # entity (we resolved by id). Count via a synthetic key
            # so the cross-session metric stays correct.
            ent_row = ix.get_entity(ent_id)
            if ent_row is not None:
                ent_key = (ent_row["normalized_name"], ent_row["kind"])
                canonical_for_norm.setdefault(
                    ent_key, ent_row["canonical_name"],
                )
                sessions_per_norm.setdefault(ent_key, set()).add(eid)
                mentions_per_norm[ent_key] = (
                    mentions_per_norm.get(ent_key, 0) + 1
                )
            ep_plan.append({
                "key": None,
                "surface": plan["alias_surface"],
                "snippet": plan["snippet"],
                "confidence": plan["confidence"],
                "observed_at": plan["observed_at"],
                "source_kind": "episode",
                "_alias_entity_id": ent_id,
                "_planned_mention_key": mention_key,
            })

        if ep_plan:
            planned_mentions_by_ep[eid] = ep_plan

    if write:
        for eid, plan in planned_mentions_by_ep.items():
            for entry in plan:
                if "_alias_entity_id" in entry:
                    # Alias-driven mention: entity already exists in
                    # the index (it was looked up by find_entities).
                    ent_id = entry["_alias_entity_id"]
                else:
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
    report.deterministic_mentions_new = det_new
    report.deterministic_mentions_existing = det_existing
    report.alias_mentions_new = alias_new
    report.alias_mentions_existing = alias_existing
    report.ambiguous_alias_mentions = ambiguous_alias
    report.alias_matches_by_alias = {
        surface: len(eps)
        for surface, eps in alias_match_episodes.items()
    }

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
