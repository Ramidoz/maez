# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Nightly lived-memory reflection orchestrator (ADR 0019 Phase 4).

Wires the Phase 2 builder + Phase 3 extractor into the Phase 1
stores: read memories → produce candidates → dedup → store
episodes → extract edge proposals → upsert nodes → store edges.

Safety contract:

- **No Chroma mutation.** This is a read-only consumer of Chroma.
- **No deletion.** Append-only on the SQLite stores; corrections
  are :meth:`RelationshipGraph.supersede` calls (added in a future
  pass), never deletes.
- **Idempotent re-run.** Dedup is by source_memory_id overlap with
  already-stored active episodes; running twice on the same memory
  set produces the same end state as running once.
- **Dry-run mode.** With ``dry_run=True`` the orchestrator counts
  what it *would* write but performs no inserts.
- **Skip-and-log on extraction failure.** A single bad memory must
  not abort the run; it is logged and the loop continues.

CLI usage::

    .venv/bin/python scripts/memory_reflection/nightly_lived_memory.py --dry-run
    .venv/bin/python scripts/memory_reflection/nightly_lived_memory.py --apply

The CLI is a thin wrapper. Production logic lives in
:func:`run_reflection`, which is unit-tested with fixture memories
so the test suite never touches live Chroma.
"""

from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from core.memory.episode_builder import extract_candidate
from core.memory.episodes import EpisodeStore
from core.memory.relationship_extractor import extract_edges
from core.memory.relationship_graph import RelationshipGraph

logger = logging.getLogger("maez.lived_memory.nightly")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class ReflectionReport:
    """Structured summary of one reflection pass.

    The CLI writes this to ``logs/lived_memory/YYYY-MM-DD.log``;
    callers can also pass it to a custom log writer for richer
    presentation.
    """

    candidates_seen: int = 0
    episodes_added: int = 0
    episodes_skipped_duplicate: int = 0
    edges_added: int = 0
    extraction_errors: int = 0
    dry_run: bool = False
    started_at: str = ""
    finished_at: str = ""
    error_messages: list[str] = field(default_factory=list)


def run_reflection(
    memories: Iterable[dict],
    *,
    episode_store: EpisodeStore,
    graph: RelationshipGraph,
    dry_run: bool = False,
) -> ReflectionReport:
    """Run one reflection pass.

    For each memory:

    1. Try to extract a candidate. If none, skip.
    2. Dedup: if any source_memory_id overlaps with an active
       episode's source IDs (or with a candidate seen earlier in this
       run), skip and increment ``episodes_skipped_duplicate``.
    3. Store the episode (or count-only on dry-run).
    4. Extract edge proposals. For each one, upsert subject and
       object nodes, then add the edge with the new episode's ID
       stamped in.
    5. On any per-memory exception: log, increment
       ``extraction_errors``, continue to the next memory.

    Returns a :class:`ReflectionReport` with counts and timings.
    """
    report = ReflectionReport(dry_run=dry_run, started_at=_now_iso())

    seen_memory_ids: set[str] = set()
    for ep in episode_store.list_active():
        seen_memory_ids.update(ep.get("source_memory_ids") or [])

    for memory in memories:
        try:
            candidate = extract_candidate(memory)
        except Exception as e:
            report.extraction_errors += 1
            msg = f"extraction failed for {memory.get('id', '<no-id>')}: {e}"
            report.error_messages.append(msg)
            logger.warning(msg)
            continue

        if candidate is None:
            continue
        report.candidates_seen += 1

        # Dedup against already-stored episodes AND against earlier
        # candidates in this same run.
        if any(mid in seen_memory_ids for mid in candidate.source_memory_ids):
            report.episodes_skipped_duplicate += 1
            continue
        seen_memory_ids.update(candidate.source_memory_ids)

        if dry_run:
            # Count-only path: no writes, but still tracks dedup so
            # within-run duplicate counting is consistent.
            continue

        try:
            episode_id = episode_store.add(
                title=candidate.title,
                summary=candidate.summary,
                participants=candidate.participants,
                source_memory_ids=candidate.source_memory_ids,
                source_kind=candidate.source_kind,
                occurred_at=candidate.occurred_at,
                emotional_tone=candidate.emotional_tone,
                importance=candidate.importance,
                open_loop=candidate.open_loop,
                authorship=candidate.authorship,
                memory_voice=candidate.memory_voice,
            )
        except Exception as e:
            report.extraction_errors += 1
            msg = f"episode insert failed for {memory.get('id', '<no-id>')}: {e}"
            report.error_messages.append(msg)
            logger.warning(msg)
            continue
        report.episodes_added += 1

        for proposal in extract_edges(candidate):
            try:
                subject_id = graph.upsert_node(
                    label=proposal.subject_label,
                    kind=proposal.subject_kind,
                )
                object_id = graph.upsert_node(
                    label=proposal.object_label,
                    kind=proposal.object_kind,
                )
                graph.add_edge(
                    subject_id=subject_id,
                    relation=proposal.relation,
                    object_id=object_id,
                    source_episode_ids=[episode_id],
                    source_memory_ids=proposal.source_memory_ids,
                    confidence=proposal.confidence,
                )
                report.edges_added += 1
            except Exception as e:
                report.extraction_errors += 1
                msg = f"edge insert failed for episode {episode_id} ({proposal.relation}): {e}"
                report.error_messages.append(msg)
                logger.warning(msg)
                continue

    report.finished_at = _now_iso()
    return report


# ── CLI wiring ───────────────────────────────────────────────────────


def _default_log_path() -> Path:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return _REPO_ROOT / "logs" / "lived_memory" / f"{today}.log"


def _write_log(report: ReflectionReport, log_path: Path) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"=== Lived-memory reflection — {report.started_at} → {report.finished_at} ===",
        f"  dry_run:                    {report.dry_run}",
        f"  candidates_seen:            {report.candidates_seen}",
        f"  episodes_added:             {report.episodes_added}",
        f"  episodes_skipped_duplicate: {report.episodes_skipped_duplicate}",
        f"  edges_added:                {report.edges_added}",
        f"  extraction_errors:          {report.extraction_errors}",
    ]
    for err in report.error_messages:
        lines.append(f"  ! {err}")
    lines.append("")
    with log_path.open("a") as f:
        f.write("\n".join(lines))


def _load_followups(repo_root: Path) -> list[dict]:
    """Read ``docs/followups/*.md`` as memory-shaped dicts.

    Followup docs are external project-level open-loop ledger entries
    — hand-authored, NOT first-person Maez memory. The provenance
    metadata set here (``source=docs_followups``, ``kind=followup``,
    ``authorship=project_doc``, ``memory_voice=external_to_maez``)
    instructs the builder's ``_detect_followup`` to phrase the
    resulting episode as *"the project carries an open loop about X"*
    instead of *"Maez decided X"*.

    Each file becomes one memory-shaped dict with a synthetic but
    stable id of the form ``followup-doc:<relative_path>`` so the
    episode store's evidence requirement is satisfied and re-runs
    are idempotent (dedup is by source_memory_id overlap).

    Missing or empty directory → empty list. Per-file read errors
    are skipped with a logger warning so one bad doc cannot kill
    the run.
    """
    out: list[dict] = []
    followups_dir = repo_root / "docs" / "followups"
    if not followups_dir.exists():
        return out
    for path in sorted(followups_dir.glob("*.md")):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as e:
            logger.warning("followup read failed for %s: %s", path, e)
            continue
        rel = path.relative_to(repo_root).as_posix()
        try:
            mtime_iso = datetime.fromtimestamp(
                path.stat().st_mtime, tz=timezone.utc
            ).isoformat(timespec="seconds")
        except OSError:
            mtime_iso = ""
        out.append(
            {
                "id": f"followup-doc:{rel}",
                "document": text,
                "metadata": {
                    "kind": "followup",
                    "source": "docs_followups",
                    "authorship": "project_doc",
                    "memory_voice": "external_to_maez",
                    "file_path": rel,
                    "timestamp": mtime_iso,
                },
            }
        )
    return out


def _load_memories_from_chroma() -> Iterable[dict]:
    """Read high-signal memories from the live MemoryManager + project
    open-loop ledger.

    v1 sources:

    - every active core memory (Maez first-person)
    - the most recent N daily summaries (Maez first-person)
    - every file under ``docs/followups/*.md`` (external project doc)

    The raw collection is intentionally NOT scanned in v1 — it's 30k+
    entries and most are heartbeat noise. The Phase 4 plan calls out
    "do not bulk-ingest all raw memories."

    Missing accessors fail loudly (RuntimeError) — silent empty
    corpora previously made probe failures look like cognition
    failure when it was just ingestion failure.
    """
    from memory.memory_manager import MemoryManager

    mm = MemoryManager()
    out: list[dict] = []
    for ep in mm.get_all_core() or []:
        # MemoryManager nests provenance fields under .metadata. The
        # earlier loader looked at ep["source"] (top-level), which is
        # always empty for ChromaDB-derived rows — silently dropping
        # the source signal that the corrective-core detector relies
        # on. 2026-04-26 real-data run made this visible.
        meta = ep.get("metadata") or {}
        out.append(
            {
                "id": ep["id"],
                "document": ep.get("content") or ep.get("document") or "",
                "metadata": {
                    "kind": "core",
                    "source": meta.get("source") or "",
                    "timestamp": meta.get("timestamp") or "",
                },
            }
        )
    # Daily summaries: also small, also high-signal. The earlier
    # implementation wrapped this in try/except AttributeError, which
    # silently dropped the entire daily corpus the day get_recent_daily
    # went missing (5 daily summaries in the live store, 0 reaching
    # the builder). Fail loud now: missing accessor means the
    # MemoryManager contract changed and lived-memory ingestion has a
    # real gap to fix, not a silent skip to absorb.
    if not hasattr(mm, "get_recent_daily"):
        raise RuntimeError(
            "MemoryManager.get_recent_daily is missing — the daily "
            "corpus would silently disappear from lived-memory "
            "ingestion. Restore the accessor or update this loader "
            "explicitly; do not patch the symptom by re-adding a "
            "broad except."
        )
    daily_recent = mm.get_recent_daily(limit=30)
    for d in daily_recent or []:
        meta = d.get("metadata") or {}
        out.append(
            {
                "id": d["id"],
                "document": d.get("content") or d.get("document") or "",
                "metadata": {
                    "kind": "daily",
                    "source": meta.get("source") or "",
                    "timestamp": meta.get("timestamp") or "",
                },
            }
        )
    out.extend(_load_followups(_REPO_ROOT))
    return out


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="count what would be written but don't write",
    )
    ap.add_argument(
        "--apply",
        action="store_true",
        help="write to SQLite stores (default; explicit for clarity)",
    )
    ap.add_argument(
        "--episode-db",
        default=str(_REPO_ROOT / "memory" / "lived_episodes.db"),
        help="SQLite path for the episode store",
    )
    ap.add_argument(
        "--graph-db",
        default=str(_REPO_ROOT / "memory" / "lived_graph.db"),
        help="SQLite path for the relationship graph",
    )
    ap.add_argument(
        "--log-path",
        default=str(_default_log_path()),
        help="reflection log path (append-only)",
    )
    args = ap.parse_args(argv)

    if args.dry_run and args.apply:
        ap.error("--dry-run and --apply are mutually exclusive")

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    store = EpisodeStore(args.episode_db)
    graph = RelationshipGraph(args.graph_db)
    memories = _load_memories_from_chroma()

    report = run_reflection(
        memories=memories,
        episode_store=store,
        graph=graph,
        dry_run=args.dry_run,
    )

    _write_log(report, Path(args.log_path))
    print(
        f"candidates={report.candidates_seen} "
        f"added={report.episodes_added} "
        f"deduped={report.episodes_skipped_duplicate} "
        f"edges={report.edges_added} "
        f"errors={report.extraction_errors} "
        f"dry_run={report.dry_run}"
    )
    return 0 if report.extraction_errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
