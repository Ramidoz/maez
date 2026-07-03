#!/usr/bin/env python3
"""A1 Scar Tissue backfill for the four A3-kept proto-scar exhibits.

The A3 curation ceremony deliberately left four self-correction journals hot.
This script can show the scar episodes they would become, and, only with
``apply --owner-approved``, write those episodes and archive the original hot
rows through the same archive path used by the A3 ceremony.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Iterable

from core.infra import paths as _paths
from core.learning.scar_tissue import ScarSidecar, compose_scar_text
from core.memory.episodes import EpisodeStore
from scripts.metabolic_curation import RowRef


@dataclass(frozen=True)
class Exhibit:
    tier: str
    row_id: str
    preview: str
    correction: str

    @property
    def row_ref(self) -> str:
        return f"{self.tier}/{self.row_id}"

    @property
    def receipt_ref(self) -> str:
        return f"exhibit:{self.row_ref}"

    @property
    def dedup_key(self) -> str:
        return self.receipt_ref

    def as_row_ref(self) -> RowRef:
        return RowRef(self.tier, self.row_id)


DEFAULT_EXHIBITS: tuple[Exhibit, ...] = (
    Exhibit(
        tier="daily",
        row_id="daily-2026-04-23-683a9a68",
        preview=(
            "The raw memory log for the last 24 hours is a textbook example "
            "of the fixation failure modes Maez had been trying to correct."
        ),
        correction=(
            "A3 curation retained this row as an early scar exhibit: Maez "
            "recognized fixation failure modes in its own memory behavior."
        ),
    ),
    Exhibit(
        tier="daily",
        row_id="daily-2026-04-25-86e9538d",
        preview=(
            "Daily summary naming disk fixation persisting despite explicit "
            "corrective rules."
        ),
        correction=(
            "A3 curation retained this row as an early scar exhibit: Maez "
            "recognized disk-fixation persistence after correction."
        ),
    ),
    Exhibit(
        tier="daily",
        row_id="daily-2026-04-29-16ffa8d5",
        preview=(
            "Nightly consolidation naming the maez_pulse.html interaction "
            "failure."
        ),
        correction=(
            "A3 curation retained this row as an early scar exhibit: Maez "
            "recognized the maez_pulse.html interaction failure."
        ),
    ),
    Exhibit(
        tier="core",
        row_id="core-1c54344acced",
        preview=(
            "Core journal where Maez says it failed its own Observation "
            "Variety practice."
        ),
        correction=(
            "A3 curation retained this row as an early scar exhibit: Maez "
            "recognized its own Observation Variety failure."
        ),
    ),
)


class BackfillAlreadyAppliedError(RuntimeError):
    pass


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def render_exhibit_list(exhibits: Iterable[Exhibit] = DEFAULT_EXHIBITS) -> str:
    lines = [
        "# A1 Scar Tissue Backfill Exhibits",
        "",
        "No mutation. Each reviewed A3 KEEP row and the scar episode it would become:",
        "",
    ]
    for ex in exhibits:
        lines.append(f"- {ex.row_ref}")
        lines.append(f"  preview: {ex.preview}")
        lines.append(f"  would become scar episode: {ex.correction}")
        lines.append(f"  receipt/dedup: {ex.receipt_ref}")
    return "\n".join(lines) + "\n"


def _episode_summary(exhibit: Exhibit, *, occurred_at: str) -> str:
    return compose_scar_text(
        scar_class="backfill_exhibit",
        surface="a3_curation",
        context=f"A3 curation kept {exhibit.row_ref}: {exhibit.preview}",
        correction=exhibit.correction,
        receipt_refs=[exhibit.receipt_ref],
        occurred_at=occurred_at,
    )


def _episode_title(exhibit: Exhibit) -> str:
    return f"Early correction exhibit: {exhibit.row_id}"


def apply_exhibit_backfill(
    *,
    episode_store: EpisodeStore,
    sidecar: ScarSidecar,
    owner_approved: bool,
    archive_original: Callable[[RowRef], None],
    require_original: Callable[[RowRef], None] | None = None,
    exhibits: Iterable[Exhibit] = DEFAULT_EXHIBITS,
    now_iso: str | None = None,
) -> list[str]:
    """Write the four reviewed exhibits as scar episodes, then archive originals."""
    if not owner_approved:
        raise PermissionError("--owner-approved is required")

    exhibits = tuple(exhibits)
    existing = [ex.dedup_key for ex in exhibits if sidecar.active_episode(ex.dedup_key)]
    if existing:
        sample = ", ".join(existing[:4])
        raise BackfillAlreadyAppliedError(f"scar backfill already applied: {sample}")
    if require_original is not None:
        for exhibit in exhibits:
            require_original(exhibit.as_row_ref())

    occurred_at = now_iso or _now_iso()
    episode_ids: list[str] = []
    for exhibit in exhibits:
        episode_id = episode_store.add(
            title=_episode_title(exhibit),
            summary=_episode_summary(exhibit, occurred_at=occurred_at),
            participants=["Maez"],
            source_memory_ids=[exhibit.receipt_ref],
            source_kind="scar",
            occurred_at=occurred_at,
            importance=4,
            authorship="scar_detector",
            memory_voice="external_to_maez",
        )
        sidecar.register(
            exhibit.dedup_key,
            episode_id=episode_id,
            receipt_ref=exhibit.receipt_ref,
            occurred_at=occurred_at,
        )
        archive_original(exhibit.as_row_ref())
        episode_ids.append(episode_id)
    return episode_ids


def _default_episode_store() -> EpisodeStore:
    return EpisodeStore(str(_paths.memory_dir() / "lived_episodes.db"))


def _default_sidecar() -> ScarSidecar:
    return ScarSidecar(_paths.memory_dir() / "scar_tissue.db")


def _archive_original(ref: RowRef) -> None:
    from memory.memory_manager import MemoryManager
    from scripts.metabolic_curation import _archive_row

    manager = MemoryManager()
    try:
        _archive_row(manager, ref)
    finally:
        manager.close()


def _require_original(ref: RowRef) -> None:
    from memory.memory_manager import MemoryManager
    from scripts.metabolic_curation import _collection_for_tier, _get_one

    manager = MemoryManager()
    try:
        _get_one(_collection_for_tier(manager, ref.tier), ref.row_id)
    finally:
        manager.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")

    p_apply = sub.add_parser("apply")
    p_apply.add_argument("--owner-approved", action="store_true")

    args = parser.parse_args(argv)
    if args.cmd == "list":
        print(render_exhibit_list(), end="")
        return 0
    if args.cmd == "apply":
        ids = apply_exhibit_backfill(
            episode_store=_default_episode_store(),
            sidecar=_default_sidecar(),
            owner_approved=args.owner_approved,
            require_original=_require_original,
            archive_original=_archive_original,
        )
        for episode_id in ids:
            print(episode_id)
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
