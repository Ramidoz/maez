# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Offline LLM entity extraction batch (Step 5m).

Calls a local LLM (llama.cpp / ollama via the existing
``core.routing.llm_client.chat`` entry) once per episode, parses
conservative JSON, hallucination-checks each candidate against the
source text, and (when ``--write``) populates the entity index with
the surviving entities + per-episode mentions.

Hard contract:

  • Offline batch only — NOT wired into nightly consolidation. The
    expensive mistake to avoid is paying an LLM call per
    consolidation cycle before proving the offline batch creates
    useful cross-session signal. That decision is gated on
    re-running ``scripts.measure_entity_expansion`` after a write
    pass and seeing ``new_session_ids > 0`` on real queries.

  • No external network. All inference goes through the existing
    local llama.cpp / ollama backend the rest of Maez uses.

  • Hallucination-checked. Each LLM-produced entity must have its
    canonical_name OR at least one alias appear (case-insensitive,
    word-boundary) in the source episode text. The LLM gets one
    shot per episode; entities it can't ground are rejected with
    ``rejected_hallucinated`` incremented in the report.

  • Confidence-gated. Default min_confidence=0.5 — below that the
    LLM is signalling its own uncertainty, and the spec demands
    we honour that signal rather than over-collect.

  • Dry-run default. ``--write`` opt-in is required to commit.
    Same posture as Step-5f / Step-5g writers.

  • Idempotent. Schema UNIQUE constraints in EntityIndex catch
    repeats; the report counts new vs already-present so a
    rerun with no new evidence reads ``entities_new=0``.

Public API:

  batch_extract(*, episodes, ix, write=False, limit=None,
                 extract_fn=None, min_confidence=0.5)
                                       -> ExtractionReport
  default_extract_fn(text, *, episode) -> str  # local llama.cpp
  main(argv)                           -> int  # CLI

Tests inject ``extract_fn`` to keep the suite offline and
deterministic; the production path uses
``default_extract_fn`` which dispatches through
``core.routing.llm_client.chat``.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import statistics
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from core.memory.entity_index import EntityIndex
    from core.memory.episodes import EpisodeStore

logger = logging.getLogger(__name__)


_DEFAULT_MIN_CONFIDENCE = 0.5
_TOP_N = 20
_VALID_KINDS = frozenset({
    "person", "place", "project", "organization",
    "event", "concept", "unknown",
})


# ── prompt ────────────────────────────────────────────────────────


_SYSTEM_PROMPT = """\
You extract named entities from one episode of a personal companion's memory.
Be conservative. Skip uncertain or generic entities.

Return JSON ONLY — a single array. No prose before or after.

Each entity is a JSON object with these fields:
  canonical_name : string  — the full display name
  kind           : one of person | place | project | organization
                    | event | concept | unknown
  aliases        : array of strings — short forms or nicknames
                    that appear in the text
  evidence_quote : string — verbatim phrase from the episode
                    that grounds the entity
  confidence     : number 0..1 — your own confidence

Rules:
  • Every entity MUST be grounded in the episode text. Do not
    invent names that are not literally present (or whose alias
    is not literally present) in the text.
  • Skip pronouns ("she", "he", "they") — those are not entities.
  • Skip generic descriptors ("the meeting", "the school")
    UNLESS they are clearly a proper-noun reference.
  • Empty array is a valid answer. Prefer empty over guessing.
"""


_USER_TEMPLATE = """\
Episode title: {title}
Episode summary: {summary}
{open_loop_block}
Return JSON only.
"""


def _format_user_prompt(episode: dict) -> str:
    title = episode.get("title") or ""
    summary = episode.get("summary") or ""
    open_loop = episode.get("open_loop") or ""
    open_loop_block = (
        f"Episode open_loop: {open_loop}\n" if open_loop else ""
    )
    return _USER_TEMPLATE.format(
        title=title, summary=summary, open_loop_block=open_loop_block,
    )


# ── default extract_fn (production path) ─────────────────────────


_DEFAULT_MODEL = "qwen3:30b-a3b-q4_K_M"  # placeholder; CLI flag overrides


def default_extract_fn(text: str, *, episode: dict, model: str | None = None) -> str:
    """Production path: dispatch to ``llm_client.chat`` with the
    curated system prompt + the per-episode user prompt. Returns
    the raw response text. Failures (backend down, model missing)
    raise ``RuntimeError`` with the underlying error message — the
    CLI catches and exits cleanly with an actionable message."""
    try:
        from core.routing.llm_client import BackendError, chat
    except Exception as e:
        raise RuntimeError(
            f"local LLM client unavailable: {e}. "
            "This script requires a working local backend "
            "(llama.cpp or ollama). Set MAEZ_LLM_BACKEND and "
            "verify the model is loaded."
        ) from e

    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": _format_user_prompt(episode)},
    ]
    try:
        resp = chat(
            model=model or _DEFAULT_MODEL,
            messages=messages,
            stream=False,
            think=False,
            options={"temperature": 0.1},
        )
    except BackendError as e:
        raise RuntimeError(
            f"LLM backend error during extraction: {e}"
        ) from e
    # ollama-shaped response: resp.message.content
    try:
        return resp.message.content
    except AttributeError:
        return resp["message"]["content"]


# ── JSON extraction ──────────────────────────────────────────────


_JSON_ARRAY_RE = re.compile(r"\[\s*(?:\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}\s*,?\s*)*\]", re.DOTALL)


def _parse_json_array(raw: str) -> list[dict] | None:
    """Try strict JSON first. Fall back to extracting the first
    JSON array from prose framing ('Sure, here is the JSON: [...]').
    Returns None on unrecoverable parse failure — caller logs and
    skips the episode."""
    if raw is None:
        return None
    text = raw.strip()
    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return parsed
    except json.JSONDecodeError:
        pass
    m = _JSON_ARRAY_RE.search(text)
    if m is None:
        return None
    try:
        parsed = json.loads(m.group(0))
        if isinstance(parsed, list):
            return parsed
    except json.JSONDecodeError:
        return None
    return None


# ── per-entity validation + grounding ────────────────────────────


@dataclass
class ExtractedEntity:
    """One LLM-produced entity that passed parse + validation +
    grounding. ``aliases`` is the LLM-supplied list filtered to
    strings; ``confidence`` is clamped to [0, 1]."""
    canonical_name: str
    kind: str
    aliases: list[str]
    evidence_quote: str
    confidence: float


def _word_boundary_in_text(needle: str, text: str) -> bool:
    """Case-insensitive word-boundary substring check. Used by the
    grounding filter to verify the canonical_name (or an alias)
    actually appears in the source episode text."""
    if not needle or not text:
        return False
    try:
        return re.search(
            r"\b" + re.escape(needle) + r"\b", text,
            re.IGNORECASE,
        ) is not None
    except re.error:
        return False


def _validate_and_ground(
    raw_entry: Any, *, source_text: str, min_confidence: float,
) -> tuple[ExtractedEntity | None, str]:
    """Returns ``(entity, reason)`` — ``entity`` is None when the
    candidate fails validation or grounding; ``reason`` is one of
    ``"ok"``, ``"shape"``, ``"low_confidence"``, ``"hallucinated"``,
    ``"empty"``."""
    if not isinstance(raw_entry, dict):
        return None, "shape"
    canonical = raw_entry.get("canonical_name")
    if not isinstance(canonical, str) or not canonical.strip():
        return None, "shape"
    canonical = canonical.strip()
    kind = raw_entry.get("kind") or "unknown"
    if not isinstance(kind, str) or kind not in _VALID_KINDS:
        kind = "unknown"
    aliases_raw = raw_entry.get("aliases") or []
    if not isinstance(aliases_raw, list):
        return None, "shape"
    aliases = [
        a.strip() for a in aliases_raw
        if isinstance(a, str) and a.strip()
    ]
    evidence_quote = raw_entry.get("evidence_quote") or ""
    if not isinstance(evidence_quote, str):
        evidence_quote = ""
    try:
        confidence = float(raw_entry.get("confidence", 0))
    except (TypeError, ValueError):
        return None, "shape"
    confidence = max(0.0, min(1.0, confidence))
    if confidence < min_confidence:
        return None, "low_confidence"
    grounded = _word_boundary_in_text(canonical, source_text) or any(
        _word_boundary_in_text(a, source_text) for a in aliases
    )
    if not grounded:
        return None, "hallucinated"
    return ExtractedEntity(
        canonical_name=canonical,
        kind=kind,
        aliases=aliases,
        evidence_quote=evidence_quote,
        confidence=confidence,
    ), "ok"


# ── snippet rule ─────────────────────────────────────────────────


_SNIPPET_WINDOW = 60


def _snippet_for(text: str, evidence: str) -> str:
    """If ``evidence`` literally appears in ``text``, return a
    60-char window centred on it. Otherwise fall back to the
    title-shaped first 80 chars of ``text``."""
    if evidence and evidence in text:
        idx = text.index(evidence)
        midpoint = idx + len(evidence) // 2
        half = _SNIPPET_WINDOW // 2
        lo = max(0, midpoint - half)
        hi = min(len(text), lo + _SNIPPET_WINDOW)
        if hi - lo < _SNIPPET_WINDOW:
            lo = max(0, hi - _SNIPPET_WINDOW)
        return text[lo:hi].strip()
    return text[:80].strip()


# ── report ───────────────────────────────────────────────────────


@dataclass
class ExtractionReport:
    """Step-5m batch summary. ``entities_new`` / ``mentions_new``
    are the would-write counts in dry-run mode (snapshot-then-plan
    accounting), the actual-write counts when ``write=True``."""
    episodes_scanned: int = 0
    episodes_extracted: int = 0
    parse_failures: int = 0
    rejected_low_confidence: int = 0
    rejected_hallucinated: int = 0
    rejected_shape: int = 0

    entities_new: int = 0
    entities_existing: int = 0
    mentions_new: int = 0
    mentions_existing: int = 0
    distinct_entities: int = 0
    entities_in_2plus_sessions: int = 0
    mentions_per_entity_median: float = 0.0
    mentions_per_entity_max: int = 0
    top_entities: list[dict] = field(default_factory=list)
    rejected_examples: list[dict] = field(default_factory=list)
    write_mode: bool = False

    def render_text(self) -> str:
        head = (
            "WRITE MODE — entity_index.db updated."
            if self.write_mode
            else "DRY RUN — no writes occurred. Use --write to commit."
        )
        lines = [head, ""]
        lines.append(f"episodes scanned:              {self.episodes_scanned}")
        lines.append(
            f"episodes extracted:            "
            f"{self.episodes_extracted}"
        )
        lines.append(f"parse failures:                {self.parse_failures}")
        lines.append("")
        lines.append(
            f"rejected (low confidence):     "
            f"{self.rejected_low_confidence}"
        )
        lines.append(
            f"rejected (hallucinated):       "
            f"{self.rejected_hallucinated}"
        )
        lines.append(f"rejected (bad shape):          {self.rejected_shape}")
        lines.append("")
        lines.append(f"entities new:                  {self.entities_new}")
        lines.append(
            f"entities existing:             {self.entities_existing}"
        )
        lines.append(f"mentions new:                  {self.mentions_new}")
        lines.append(
            f"mentions existing:             {self.mentions_existing}"
        )
        lines.append("")
        lines.append(
            f"distinct entities:             {self.distinct_entities}"
        )
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
        lines.append("top entities:")
        if self.top_entities:
            for r in self.top_entities:
                lines.append(
                    f"  {r['canonical_name']:<40s}  "
                    f"{r['mention_count']:>4}  "
                    f"{r['distinct_sessions']:>4}"
                )
        else:
            lines.append("  (none)")
        if self.rejected_examples:
            lines.append("")
            lines.append("rejected examples (first 5):")
            for r in self.rejected_examples[:5]:
                lines.append(
                    f"  [{r['reason']}] {r['canonical_name']!r} "
                    f"(conf {r.get('confidence', 0):.2f}) — "
                    f"episode {r['episode_id']}"
                )
        return "\n".join(lines)


# ── public API ───────────────────────────────────────────────────


def _observed_at_for(episode: dict) -> str:
    occ = episode.get("occurred_at")
    if occ:
        return occ
    return episode["created_at"]


def batch_extract(
    *,
    episodes: "EpisodeStore",
    ix: "EntityIndex",
    extract_fn: Callable[..., str] | None = None,
    write: bool = False,
    limit: int | None = None,
    min_confidence: float = _DEFAULT_MIN_CONFIDENCE,
) -> ExtractionReport:
    """Walk active episodes, extract entities via the LLM, validate
    + ground against source text, and (when ``write=True``) populate
    the index with surviving entities and mentions.

    ``extract_fn`` is the LLM round-trip — must accept
    ``(text, *, episode, **kw) -> str``. Defaults to
    ``default_extract_fn``. Tests inject deterministic fakes."""
    if extract_fn is None:
        extract_fn = default_extract_fn

    report = ExtractionReport(write_mode=write)
    rows = episodes.list_active() or []
    if limit is not None:
        rows = rows[:max(0, int(limit))]
    report.episodes_scanned = len(rows)

    # Snapshot existing keys for new-vs-existing accounting.
    con = ix._connect()
    existing_entities_by_norm: dict[str, tuple[str, str]] = {}
    for row in con.execute(
        "SELECT id, normalized_name, kind FROM entities"
    ).fetchall():
        prior = existing_entities_by_norm.get(row["normalized_name"])
        if prior is None or (
            prior[1] == "unknown" and row["kind"] != "unknown"
        ):
            existing_entities_by_norm[row["normalized_name"]] = (
                row["id"], row["kind"],
            )
    existing_mentions: set[tuple[str, str, str]] = set()
    for row in con.execute(
        "SELECT entity_id, session_id, source_id FROM entity_mentions"
    ).fetchall():
        existing_mentions.add(
            (row["entity_id"], row["session_id"], row["source_id"]),
        )

    sessions_per_norm: dict[str, set[str]] = {}
    mentions_per_norm: dict[str, int] = {}
    canonical_for_norm: dict[str, str] = {}

    from core.memory.entity_index import normalize_entity_name

    for ep in rows:
        eid = ep["id"]
        observed_at = _observed_at_for(ep)
        title = ep.get("title") or ""
        summary = ep.get("summary") or ""
        open_loop = ep.get("open_loop") or ""
        source_text = "\n".join(
            t for t in (title, summary, open_loop) if t
        )

        try:
            raw_response = extract_fn(source_text, episode=ep)
        except Exception as e:
            logger.warning(
                "entity_llm_extractor: extract_fn raised on episode %s: %s",
                eid, e,
            )
            report.parse_failures += 1
            continue

        parsed = _parse_json_array(raw_response)
        if parsed is None:
            logger.debug(
                "entity_llm_extractor: parse failure on episode %s; "
                "raw response begins with %r",
                eid, (raw_response or "")[:60],
            )
            report.parse_failures += 1
            continue

        episode_kept = 0
        for raw_entry in parsed:
            entity, reason = _validate_and_ground(
                raw_entry,
                source_text=source_text,
                min_confidence=min_confidence,
            )
            if entity is None:
                if reason == "low_confidence":
                    report.rejected_low_confidence += 1
                elif reason == "hallucinated":
                    report.rejected_hallucinated += 1
                else:
                    report.rejected_shape += 1
                if isinstance(raw_entry, dict):
                    report.rejected_examples.append({
                        "reason": reason,
                        "canonical_name": raw_entry.get(
                            "canonical_name", "<missing>",
                        ),
                        "confidence": raw_entry.get("confidence", 0.0),
                        "episode_id": eid,
                    })
                continue

            normalized = normalize_entity_name(entity.canonical_name)
            if not normalized:
                continue

            seeded = existing_entities_by_norm.get(normalized)
            if seeded is not None:
                ent_id, kind_to_use = seeded
                report.entities_existing += 1
            else:
                ent_id = None
                kind_to_use = entity.kind
                report.entities_new += 1
                # Plan the entity. Reserve the normalized → canonical
                # mapping so subsequent episodes that surface the
                # same entity don't double-count.
                existing_entities_by_norm[normalized] = (
                    f"<planned:{normalized}>", kind_to_use,
                )

            canonical_for_norm.setdefault(normalized, entity.canonical_name)
            sessions_per_norm.setdefault(normalized, set()).add(eid)
            mentions_per_norm[normalized] = (
                mentions_per_norm.get(normalized, 0) + 1
            )

            if write:
                if ent_id is None or ent_id.startswith("<planned:"):
                    ent_id = ix.upsert_entity(
                        entity.canonical_name,
                        kind=kind_to_use,
                        aliases=entity.aliases,
                    )
                    existing_entities_by_norm[normalized] = (
                        ent_id, kind_to_use,
                    )
                else:
                    for alias in entity.aliases:
                        ix.add_alias(ent_id, alias)
                mention_key = (ent_id, eid, eid)
                if mention_key in existing_mentions:
                    report.mentions_existing += 1
                else:
                    ix.add_mention(
                        entity_id=ent_id,
                        session_id=eid,
                        source_id=eid,
                        source_kind="episode",
                        observed_at=observed_at,
                        snippet=_snippet_for(source_text, entity.evidence_quote),
                        confidence=entity.confidence,
                    )
                    existing_mentions.add(mention_key)
                    report.mentions_new += 1
            else:
                # Dry-run: would-be mention id is synthetic.
                synthetic_ent_id = (
                    ent_id if ent_id else f"<planned:{normalized}>"
                )
                mention_key = (synthetic_ent_id, eid, eid)
                if mention_key in existing_mentions:
                    report.mentions_existing += 1
                else:
                    report.mentions_new += 1
                    existing_mentions.add(mention_key)
            episode_kept += 1

        if episode_kept > 0:
            report.episodes_extracted += 1

    # Aggregate metrics.
    report.distinct_entities = len(canonical_for_norm) + sum(
        1 for k in existing_entities_by_norm
        if k not in canonical_for_norm
    )
    report.entities_in_2plus_sessions = sum(
        1 for s in sessions_per_norm.values() if len(s) >= 2
    )
    if mentions_per_norm:
        counts = sorted(mentions_per_norm.values())
        report.mentions_per_entity_max = max(counts)
        report.mentions_per_entity_median = float(statistics.median(counts))
    enriched = []
    for norm, count in mentions_per_norm.items():
        enriched.append({
            "canonical_name": canonical_for_norm.get(norm, norm),
            "mention_count": count,
            "distinct_sessions": len(sessions_per_norm.get(norm, set())),
        })
    enriched.sort(
        key=lambda r: (r["mention_count"], r["distinct_sessions"]),
        reverse=True,
    )
    report.top_entities = enriched[:_TOP_N]
    return report


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


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="python -m core.memory.entity_llm_extractor",
        description=(
            "Offline LLM entity extraction batch (Step 5m). "
            "Calls the local LLM once per episode; populates the "
            "entity index when --write. NOT wired into "
            "consolidation. Dry-run by default."
        ),
    )
    p.add_argument("--episodes-db", type=Path, default=None)
    p.add_argument("--index-db", type=Path, default=None)
    p.add_argument("--limit", type=int, default=None,
                   help="Cap number of episodes (default: all).")
    p.add_argument("--min-confidence", type=float,
                   default=_DEFAULT_MIN_CONFIDENCE,
                   help="Reject entities with confidence below this "
                        "threshold (default: 0.5).")
    p.add_argument("--model", type=str, default=None,
                   help="LLM model id; default uses the routing "
                        "client's default.")
    p.add_argument("--write", action="store_true",
                   help="Commit to entity_index.db (otherwise dry run).")
    p.add_argument("--dry-run", action="store_true",
                   help="Explicit dry-run (default).")
    args = p.parse_args(argv)

    if args.write and args.dry_run:
        print(
            "error: --write and --dry-run are mutually exclusive",
            file=sys.stderr,
        )
        return 2

    ep_path = args.episodes_db or _default_episodes_path()
    if not Path(ep_path).exists():
        print(
            f"error: episodes db not found at {ep_path}",
            file=sys.stderr,
        )
        return 2

    from core.memory.entity_index import EntityIndex
    from core.memory.episodes import EpisodeStore

    episodes = EpisodeStore(str(ep_path))
    ix = (
        EntityIndex(args.index_db) if args.index_db
        else EntityIndex(_default_index_path())
    )

    # Sanity-check the LLM backend is reachable BEFORE walking the
    # corpus — otherwise the operator gets per-episode warnings
    # and a broken summary at the end.
    extract_fn: Callable[..., str]
    if args.model:
        def extract_fn(text, *, episode, **_):
            return default_extract_fn(text, episode=episode, model=args.model)
    else:
        extract_fn = default_extract_fn

    try:
        # One-shot probe with a tiny payload.
        rows = episodes.list_active() or []
        if rows:
            extract_fn("ping", episode={
                "title": "ping", "summary": "ping",
                "open_loop": "", "occurred_at": "2026-01-01T00:00:00",
                "created_at": "2026-01-01T00:00:00",
            })
    except Exception as e:
        print(
            f"error: LLM backend probe failed: {e}\n"
            "Verify that llama.cpp / ollama is running and "
            "MAEZ_LLM_BACKEND is set correctly.",
            file=sys.stderr,
        )
        return 2

    report = batch_extract(
        episodes=episodes, ix=ix,
        extract_fn=extract_fn,
        write=bool(args.write),
        limit=args.limit,
        min_confidence=args.min_confidence,
    )
    print(report.render_text())
    if not args.write:
        print(
            "\nNOTE: dry-run only. Re-run with --write to commit. "
            "Then re-run `python -m scripts.measure_entity_expansion` "
            "to see whether the new entities improved A/B "
            "new_session_ids before considering wiring this into "
            "consolidation.",
            file=sys.stderr,
        )
    return 0


__all__ = [
    "ExtractionReport",
    "ExtractedEntity",
    "batch_extract",
    "default_extract_fn",
    "main",
]


if __name__ == "__main__":
    raise SystemExit(main())
