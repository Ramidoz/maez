# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Scar Tissue (A1): deterministic corrections become recallable memory.

Scars are receipt-grade correction events, not tool friction. This module
does not detect them; it validates the event, mints/reuses its consequence
receipt, composes neutral substrate text, and writes one append-only lived
episode plus an append-preserving sidecar keyed by the scar's dedup key.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

SCAR_CLASSES = frozenset(
    {
        "fabrication_catch",
        "claim_receipt_redo",
        "dream_rejected",
        "veto_proven_wrong",
        "card_rejected",
    }
)

CORRECTION_MARKER = "\x00CORRECTION\x00"

_MAX_SURFACE = 120
_MAX_CONTEXT = 800
_MAX_CORRECTION = 800
_MAX_DEDUP = 240


@dataclass(frozen=True)
class ScarEvent:
    scar_class: str
    surface: str
    context: str
    correction: str
    receipt_refs: list[str]
    dedup_key: str


def _clamp(value: str, limit: int) -> str:
    return str(value or "")[:limit]


def _ordered_unique(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if text and text not in seen:
            seen.add(text)
            out.append(text)
    return out


def _prevalidate_non_receipt_fields(event: ScarEvent) -> None:
    if event.scar_class not in SCAR_CLASSES:
        raise ValueError(f"not a scar-grade class: {event.scar_class!r}")
    if not str(event.surface or "").strip():
        raise ValueError("scar requires a surface")
    if not str(event.context or "").strip():
        raise ValueError("scar requires context")
    if not str(event.correction or "").strip():
        raise ValueError("scar requires a correction")
    if not str(event.dedup_key or "").strip():
        raise ValueError("scar requires a dedup_key")
    if len(str(event.surface)) > _MAX_SURFACE:
        raise ValueError("scar surface too long")
    if len(str(event.context)) > _MAX_CONTEXT:
        raise ValueError("scar context too long")
    if len(str(event.correction)) > _MAX_CORRECTION:
        raise ValueError("scar correction too long")
    if len(str(event.dedup_key)) > _MAX_DEDUP:
        raise ValueError("scar dedup_key too long")


def _validate_receipt_refs(refs: list[str]) -> None:
    if not refs:
        raise ValueError("scar requires at least one durable receipt ref")
    for ref in refs:
        if ":" not in ref:
            raise ValueError(f"invalid receipt ref: {ref!r}")
        prefix, rest = ref.split(":", 1)
        if not prefix.strip() or not rest.strip():
            raise ValueError(f"invalid receipt ref: {ref!r}")
        if any(ch.isspace() for ch in prefix):
            raise ValueError(f"invalid receipt ref: {ref!r}")


def validate_scar(event: ScarEvent) -> None:
    """Validate a complete scar event after durable receipts exist."""
    _prevalidate_non_receipt_fields(event)
    _validate_receipt_refs(_ordered_unique(event.receipt_refs))


def compose_scar_text(
    *,
    scar_class: str,
    surface: str,
    context: str,
    correction: str,
    receipt_refs: list[str],
    occurred_at: str,
) -> str:
    """Substrate-composed scar text.

    The scaffold is intentionally plain and non-directive. The correction is
    quoted verbatim because owner/rail wording is receipt material, not Maez's
    scaffold voice.
    """
    refs = ", ".join(_ordered_unique(receipt_refs))
    return (
        f"Correction received ({scar_class}, {surface}, {occurred_at}). "
        f"Context: {context}. "
        f'The correction: "{correction}". '
        f"Receipts: {refs}."
    )


class ScarSidecar:
    """Append-preserving evidence index keyed by scar dedup key."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as con:
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS scar_evidence (
                    dedup_key TEXT PRIMARY KEY,
                    active_episode_id TEXT NOT NULL,
                    prior_episode_ids_json TEXT NOT NULL DEFAULT '[]',
                    receipt_refs_json TEXT NOT NULL DEFAULT '[]',
                    occurrence_count INTEGER NOT NULL DEFAULT 0,
                    first_ts TEXT NOT NULL,
                    last_ts TEXT NOT NULL
                )
                """
            )
            con.commit()

    def _connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(str(self.path))
        con.row_factory = sqlite3.Row
        return con

    @staticmethod
    def _decode_list(value: str) -> list[str]:
        try:
            raw = json.loads(value or "[]")
        except Exception:
            return []
        if not isinstance(raw, list):
            return []
        return [str(item) for item in raw]

    def get(self, dedup_key: str) -> dict | None:
        with self._connect() as con:
            row = con.execute(
                "SELECT * FROM scar_evidence WHERE dedup_key = ?",
                (dedup_key,),
            ).fetchone()
        if row is None:
            return None
        data = dict(row)
        data["prior_episode_ids"] = self._decode_list(
            data.pop("prior_episode_ids_json")
        )
        data["receipt_refs"] = self._decode_list(data.pop("receipt_refs_json"))
        return data

    def active_episode(self, dedup_key: str) -> str | None:
        row = self.get(dedup_key)
        if row is None:
            return None
        return str(row["active_episode_id"])

    def register(
        self,
        dedup_key: str,
        *,
        episode_id: str,
        receipt_ref: str,
        occurred_at: str,
    ) -> None:
        refs = _ordered_unique([receipt_ref])
        with self._connect() as con:
            con.execute(
                "INSERT INTO scar_evidence "
                "(dedup_key, active_episode_id, prior_episode_ids_json, "
                "receipt_refs_json, occurrence_count, first_ts, last_ts) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    dedup_key,
                    episode_id,
                    "[]",
                    json.dumps(refs),
                    1,
                    occurred_at,
                    occurred_at,
                ),
            )
            con.commit()

    def append_evidence(
        self,
        dedup_key: str,
        *,
        receipt_ref: str,
        occurred_at: str,
    ) -> None:
        self.merge_evidence(
            dedup_key,
            receipt_refs=[receipt_ref],
            occurred_at=occurred_at,
            count_occurrence=True,
        )

    def merge_evidence(
        self,
        dedup_key: str,
        *,
        receipt_refs: list[str],
        occurred_at: str,
        count_occurrence: bool,
    ) -> None:
        row = self.get(dedup_key)
        if row is None:
            raise KeyError(f"unknown scar dedup key: {dedup_key}")
        refs = _ordered_unique([*row["receipt_refs"], *receipt_refs])
        bump = 1 if count_occurrence else 0
        with self._connect() as con:
            con.execute(
                "UPDATE scar_evidence SET receipt_refs_json = ?, "
                "occurrence_count = occurrence_count + ?, last_ts = ? "
                "WHERE dedup_key = ?",
                (json.dumps(refs), bump, occurred_at, dedup_key),
            )
            con.commit()

    def supersede_active(self, dedup_key: str, *, new_episode_id: str) -> None:
        row = self.get(dedup_key)
        if row is None:
            raise KeyError(f"unknown scar dedup key: {dedup_key}")
        prior = _ordered_unique([*row["prior_episode_ids"], row["active_episode_id"]])
        with self._connect() as con:
            con.execute(
                "UPDATE scar_evidence SET active_episode_id = ?, "
                "prior_episode_ids_json = ? WHERE dedup_key = ?",
                (new_episode_id, json.dumps(prior), dedup_key),
            )
            con.commit()


def _mint_consequence_receipt(event: ScarEvent) -> int | None:
    from core.learning import consequence_memory

    return consequence_memory.record_event(
        kind=event.scar_class,
        context=_clamp(event.context, 400),
        outcome=_clamp(event.correction, 300),
        feedback=_clamp(event.correction, 300),
        surface=_clamp(event.surface, _MAX_SURFACE),
        tags=["scar", event.scar_class],
        extra={
            "dedup_key": event.dedup_key,
            "receipt_refs": list(event.receipt_refs or []),
        },
    )


def _episode_title(event: ScarEvent) -> str:
    label = event.scar_class.replace("_", " ")
    return f"Correction received: {label}"


def record_scar(
    event: ScarEvent,
    *,
    episode_store,
    sidecar: ScarSidecar,
    consequence_id: int | None = None,
    now_iso: str | None = None,
) -> dict:
    """Record a scar with the pinned A1 order.

    1. Pre-validate non-receipt fields.
    2. Mint or reuse the consequence row.
    3. Validate the combined receipt set.
    4. Write sidecar evidence and, on first occurrence, a lived episode.
    """
    _prevalidate_non_receipt_fields(event)

    minted_id = consequence_id
    if minted_id is None:
        minted_id = _mint_consequence_receipt(event)
    if minted_id is None:
        raise ValueError("scar consequence receipt could not be minted")

    occurred_at = now_iso or _now_iso()
    refs = _ordered_unique([*event.receipt_refs, f"consequence:{int(minted_id)}"])
    validate_scar(
        ScarEvent(
            scar_class=event.scar_class,
            surface=event.surface,
            context=event.context,
            correction=event.correction,
            receipt_refs=refs,
            dedup_key=event.dedup_key,
        )
    )

    active_episode_id = sidecar.active_episode(event.dedup_key)
    if active_episode_id:
        sidecar.merge_evidence(
            event.dedup_key,
            receipt_refs=refs,
            occurred_at=occurred_at,
            count_occurrence=True,
        )
        return {
            "episode_id": active_episode_id,
            "consequence_id": int(minted_id),
            "new_episode": False,
        }

    summary = compose_scar_text(
        scar_class=event.scar_class,
        surface=event.surface,
        context=event.context,
        correction=event.correction,
        receipt_refs=refs,
        occurred_at=occurred_at,
    )
    episode_id = episode_store.add(
        title=_episode_title(event),
        summary=summary,
        participants=["Maez"],
        source_memory_ids=refs,
        source_kind="scar",
        occurred_at=occurred_at,
        importance=4,
        authorship="scar_detector",
        memory_voice="external_to_maez",
    )
    sidecar.register(
        event.dedup_key,
        episode_id=episode_id,
        receipt_ref=refs[0],
        occurred_at=occurred_at,
    )
    for ref in refs[1:]:
        sidecar.merge_evidence(
            event.dedup_key,
            receipt_refs=[ref],
            occurred_at=occurred_at,
            count_occurrence=False,
        )
    return {
        "episode_id": episode_id,
        "consequence_id": int(minted_id),
        "new_episode": True,
    }


def _now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat(timespec="seconds")
