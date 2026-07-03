#!/usr/bin/env python3
"""A3 metabolic curation ceremony.

Archive-not-delete tooling for moving reviewed introspection journals out of
hot recall indexes. The predicate proposes; Rohit's reviewed artifact decides.
"""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable


DEFAULT_ARTIFACT = Path("docs/proof/2026-07-02-a3-curation-move-list.md")
ARCHIVE_COLLECTION = "archived_introspection"


@dataclass(frozen=True, order=True)
class RowRef:
    tier: str
    row_id: str


@dataclass(frozen=True)
class ReviewParse:
    approved_moves: list[RowRef]
    kept_rows: list[RowRef]
    pending_rows: list[RowRef]


class PendingReviewError(RuntimeError):
    pass


def _is_soul_evolution(meta: dict) -> bool:
    return str(meta.get("source") or "") == "soul_evolution"


def _is_covenant(meta: dict) -> bool:
    return str(meta.get("trust_tier") or "") == "covenant"


def _is_owner_anchor(meta: dict) -> bool:
    return str(meta.get("source") or "") == "owner"


def _is_scar_or_audit(meta: dict) -> bool:
    return bool(str(meta.get("metabolic_durable_reason") or "").strip())


NEGATIVE_CONTROL_PREDICATES: tuple[Callable[[dict], bool], ...] = (
    _is_soul_evolution,
    _is_covenant,
    _is_owner_anchor,
    _is_scar_or_audit,
)


def is_journal_row(tier: str, meta: dict | None) -> bool:
    meta = dict(meta or {})
    if any(predicate(meta) for predicate in NEGATIVE_CONTROL_PREDICATES):
        return False

    tier = str(tier or "").lower()
    row_type = str(meta.get("type") or "")
    source = str(meta.get("source") or "")
    provenance = str(meta.get("provenance_source") or "")

    if tier == "daily":
        return row_type == "daily_consolidation"
    if tier == "core":
        return (
            source == "nightly_journal"
            or row_type == "nightly_journal"
            or (source == "daily_consolidation" and provenance == "introspection")
        )
    return False


_DECISION_RE = re.compile(
    r"^-\s+\[(?P<mark>[ xX])\]\s+"
    r"(?P<action>MOVE|KEEP)\s+"
    r"(?P<tier>raw|daily|core)/(?P<row_id>\S+)\b"
)
_RAW_SAMPLE_RE = re.compile(
    r"^-\s+\[(?P<mark>[ xX])\]\s+RAW-RULE-SAMPLE\s+raw/(?P<row_id>\S+)\b"
)


def _parse_ts(value: object) -> datetime | None:
    if not value:
        return None
    try:
        text = str(value).replace("Z", "+00:00")
        dt = datetime.fromisoformat(text)
    except (TypeError, ValueError):
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def is_raw_bulk_candidate(meta: dict | None, *, now_ts: object | None = None) -> bool:
    meta = dict(meta or {})
    if any(predicate(meta) for predicate in NEGATIVE_CONTROL_PREDICATES):
        return False
    if str(meta.get("provenance_source") or "") != "introspection":
        return False
    if str(meta.get("type") or "") != "reasoning":
        return False
    if meta.get("episode_id") or meta.get("scar_id") or meta.get("citation_id"):
        return False
    row_ts = _parse_ts(meta.get("timestamp"))
    now = _parse_ts(now_ts) if now_ts is not None else datetime.now(timezone.utc)
    if row_ts is None or now is None:
        return False
    return (now - row_ts).total_seconds() >= 7 * 86400


def parse_review_artifact_text(text: str) -> ReviewParse:
    approved: list[RowRef] = []
    kept: list[RowRef] = []
    pending: list[RowRef] = []
    for line in str(text or "").splitlines():
        match = _DECISION_RE.match(line.strip())
        if not match:
            continue
        ref = RowRef(match.group("tier"), match.group("row_id"))
        action = match.group("action")
        mark = match.group("mark").strip().lower()
        if action == "KEEP":
            kept.append(ref)
        elif mark == "x":
            approved.append(ref)
        else:
            pending.append(ref)
    return ReviewParse(approved, kept, pending)


def require_review_complete(parsed: ReviewParse) -> None:
    if parsed.pending_rows:
        sample = ", ".join(f"{ref.tier}/{ref.row_id}" for ref in parsed.pending_rows[:5])
        raise PendingReviewError(f"review still has pending MOVE rows: {sample}")


def require_raw_rule_samples_reviewed(text: str) -> None:
    seen = 0
    pending: list[str] = []
    for line in str(text or "").splitlines():
        match = _RAW_SAMPLE_RE.match(line.strip())
        if not match:
            continue
        seen += 1
        if match.group("mark").strip().lower() != "x":
            pending.append(match.group("row_id"))
    if pending:
        sample = ", ".join(pending[:5])
        raise PendingReviewError(f"raw-rule samples still pending: {sample}")
    if seen == 0:
        raise PendingReviewError("raw-rule apply requires reviewed RAW-RULE-SAMPLE rows")


def verify_keep_rows_still_hot(
    collections: dict[str, object],
    keep_rows: list[RowRef],
    *,
    archives: dict[str, object] | None = None,
    scar_sidecar: object | None = None,
) -> None:
    """KEEP rows must be hot — or have crossed the A1 scar bridge (2026-07-03):
    converted to a scar episode (sidecar holds exhibit:<tier>/<row_id>) AND
    archived under the prefixed id. Anything weaker is still an error."""
    for ref in keep_rows:
        collection = collections[ref.tier]
        got = collection.get(ids=[ref.row_id], include=["metadatas"])
        if ref.row_id in set(got.get("ids") or []):
            continue
        bridge_key = f"exhibit:{ref.tier}/{ref.row_id}"
        has_scar = bool(
            scar_sidecar is not None and scar_sidecar.active_episode(bridge_key)
        )
        archive = (archives or {}).get(ref.tier)
        archived = False
        if archive is not None:
            archive_got = archive.get(ids=[f"{ref.tier}/{ref.row_id}"], include=["metadatas"])
            archived = f"{ref.tier}/{ref.row_id}" in set(archive_got.get("ids") or [])
        if has_scar and archived:
            continue
        raise AssertionError(
            f"KEEP row missing from hot collection: {ref.tier}/{ref.row_id} "
            f"(scar_episode={has_scar}, archived={archived} — a KEEP may only "
            f"leave hot via the A1 scar bridge: both must be true)"
        )


def _scar_bridge_args(manager) -> dict:
    """Bridge context for KEEP verification: per-tier archives + the A1 scar
    sidecar when it exists (None before A1 ever wrote — verify then behaves
    exactly as pre-A1)."""
    archives = {
        tier: _archive_for_tier(manager, tier) for tier in ("raw", "daily", "core")
    }
    sidecar = None
    try:
        from core.paths import memory_dir
        from core.learning.scar_tissue import ScarSidecar

        sidecar_path = memory_dir() / "scar_tissue.db"
        if sidecar_path.exists():
            sidecar = ScarSidecar(sidecar_path)
    except Exception:
        sidecar = None
    return {"archives": archives, "scar_sidecar": sidecar}


def _get_one(collection: object, row_id: str) -> tuple[str, dict]:
    got = collection.get(ids=[row_id], include=["documents", "metadatas"])
    ids = got.get("ids") or []
    if row_id not in set(ids):
        raise KeyError(row_id)
    idx = ids.index(row_id)
    return (got.get("documents") or [])[idx], dict((got.get("metadatas") or [])[idx] or {})


def archive_restore_proof(hot_collection: object, archive_collection: object, ref: RowRef) -> None:
    doc, meta = _get_one(hot_collection, ref.row_id)
    archive_id = f"{ref.tier}/{ref.row_id}"
    archive_meta = {
        **meta,
        "archived_from": ref.tier,
        "archived_at": datetime.now(timezone.utc).isoformat(),
    }
    archive_collection.add(ids=[archive_id], documents=[doc], metadatas=[archive_meta])
    hot_collection.delete(ids=[ref.row_id])
    hot_collection.add(ids=[ref.row_id], documents=[doc], metadatas=[meta])
    restored_doc, restored_meta = _get_one(hot_collection, ref.row_id)
    if restored_doc != doc or restored_meta != meta:
        raise AssertionError(f"restore proof failed for {ref.tier}/{ref.row_id}")


def _collection_for_tier(manager, tier: str):
    if tier == "raw":
        return manager.raw
    if tier == "daily":
        return manager.daily
    if tier == "core":
        return manager.core
    raise KeyError(tier)


def _archive_for_tier(manager, tier: str):
    if tier == "raw":
        client = manager._raw_client
    elif tier == "daily":
        client = manager._daily_client
    elif tier == "core":
        client = manager._core_client
    else:
        raise KeyError(tier)
    return client.get_or_create_collection(ARCHIVE_COLLECTION)


def _rows(collection: object, *, batch_size: int = 5000) -> list[tuple[str, str, dict]]:
    total = collection.count()
    if total <= 0:
        return []
    rows: list[tuple[str, str, dict]] = []
    offset = 0
    while offset < total:
        got = collection.get(
            limit=min(batch_size, total - offset),
            offset=offset,
            include=["documents", "metadatas"],
        )
        ids = got.get("ids") or []
        if not ids:
            break
        rows.extend(
            (row_id, doc, dict(meta or {}))
            for row_id, doc, meta in zip(
                ids,
                got.get("documents") or [],
                got.get("metadatas") or [],
                strict=False,
            )
        )
        offset += len(ids)
    return rows


def _preview(text: str, limit: int = 140) -> str:
    one_line = " ".join(str(text or "").split())
    return one_line[:limit]


def _signature(meta: dict) -> str:
    bits = []
    for key in ("type", "source", "provenance_source", "trust_tier"):
        if key in meta:
            bits.append(f"{key}={meta[key]}")
    return " ".join(bits) or "metadata=empty"


def enumerate_move_list(path: Path = DEFAULT_ARTIFACT) -> Path:
    from memory.memory_manager import MemoryManager

    manager = MemoryManager()
    try:
        lines = [
            "# A3 Metabolic Curation Move List",
            "",
            "Review every row. Leave `[ ] MOVE` pending, change to `[x] MOVE` to approve, or change `MOVE` to `KEEP` to retain hot.",
            "",
        ]
        counts = {}
        for tier in ("daily", "core"):
            matches = [
                (row_id, doc, meta)
                for row_id, doc, meta in _rows(_collection_for_tier(manager, tier))
                if is_journal_row(tier, meta)
            ]
            counts[tier] = len(matches)
            lines.append(f"## {tier} candidates ({len(matches)})")
            lines.append("")
            for row_id, doc, meta in matches:
                lines.append(
                    f"- [ ] MOVE {tier}/{row_id} -- {_preview(doc)} -- {_signature(meta)}"
                )
            lines.append("")
        lines.append("## Negative Controls")
        lines.append("")
        for tier in ("daily", "core"):
            offenders = [
                row_id
                for row_id, _doc, meta in _rows(_collection_for_tier(manager, tier))
                if any(predicate(meta) for predicate in NEGATIVE_CONTROL_PREDICATES)
                and is_journal_row(tier, meta)
            ]
            lines.append(f"- {tier}: {len(offenders)} negative-control matches")
        lines.append("")
        raw_candidates = [
            (row_id, doc, meta)
            for row_id, doc, meta in _rows(manager.raw)
            if is_raw_bulk_candidate(meta)
        ]
        lines.append(f"## Raw Rule Samples ({len(raw_candidates)} candidates)")
        lines.append("")
        lines.append(
            "Review these samples before any separate `apply --raw-rule` run. "
            "Check each sample with `[x]` only if the rule looks correct."
        )
        lines.append("")
        for row_id, doc, meta in raw_candidates[:20]:
            lines.append(
                f"- [ ] RAW-RULE-SAMPLE raw/{row_id} -- {_preview(doc)} -- {_signature(meta)}"
            )
        lines.append("")
        lines.append(f"Counts: daily={counts.get('daily', 0)} core={counts.get('core', 0)}")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return path
    finally:
        manager.close()


def _archive_row(manager, ref: RowRef) -> None:
    hot = _collection_for_tier(manager, ref.tier)
    archive = _archive_for_tier(manager, ref.tier)
    doc, meta = _get_one(hot, ref.row_id)
    archive.add(
        ids=[f"{ref.tier}/{ref.row_id}"],
        documents=[doc],
        metadatas=[
            {
                **meta,
                "archived_from": ref.tier,
                "archived_at": datetime.now(timezone.utc).isoformat(),
            }
        ],
    )
    hot.delete(ids=[ref.row_id])


def apply_reviewed_moves(path: Path, *, owner_approved: bool, raw_rule: bool = False) -> None:
    if not owner_approved:
        raise PermissionError("--owner-approved is required")
    if not path.exists():
        raise FileNotFoundError(path)
    artifact_text = path.read_text(encoding="utf-8")
    parsed = parse_review_artifact_text(artifact_text)
    require_review_complete(parsed)
    if raw_rule:
        require_raw_rule_samples_reviewed(artifact_text)

    from memory.memory_manager import MemoryManager

    manager = MemoryManager()
    try:
        collections = {
            "raw": manager.raw,
            "daily": manager.daily,
            "core": manager.core,
        }
        for ref in parsed.approved_moves:
            _archive_row(manager, ref)
        if raw_rule:
            for row_id, _doc, meta in _rows(manager.raw):
                if is_raw_bulk_candidate(meta):
                    _archive_row(manager, RowRef("raw", row_id))
        verify_keep_rows_still_hot(
            collections, parsed.kept_rows, **_scar_bridge_args(manager)
        )
    finally:
        manager.close()


def verify_reviewed_state(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(path)
    parsed = parse_review_artifact_text(path.read_text(encoding="utf-8"))
    require_review_complete(parsed)

    from memory.memory_manager import MemoryManager

    manager = MemoryManager()
    try:
        collections = {
            "raw": manager.raw,
            "daily": manager.daily,
            "core": manager.core,
        }
        verify_keep_rows_still_hot(
            collections, parsed.kept_rows, **_scar_bridge_args(manager)
        )
        for ref in parsed.approved_moves:
            hot = _collection_for_tier(manager, ref.tier)
            hot_got = hot.get(ids=[ref.row_id], include=["metadatas"])
            if ref.row_id in set(hot_got.get("ids") or []):
                raise AssertionError(f"approved MOVE still hot: {ref.tier}/{ref.row_id}")
            archive = _archive_for_tier(manager, ref.tier)
            archive_id = f"{ref.tier}/{ref.row_id}"
            archive_got = archive.get(ids=[archive_id], include=["metadatas"])
            if archive_id not in set(archive_got.get("ids") or []):
                raise AssertionError(f"approved MOVE missing from archive: {archive_id}")
    finally:
        manager.close()


def run_restore_proof(ref_text: str) -> None:
    tier, row_id = ref_text.split("/", 1)
    ref = RowRef(tier, row_id)
    from memory.memory_manager import MemoryManager

    manager = MemoryManager()
    try:
        archive_restore_proof(
            _collection_for_tier(manager, ref.tier),
            _archive_for_tier(manager, ref.tier),
            ref,
        )
    finally:
        manager.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_enum = sub.add_parser("enumerate")
    p_enum.add_argument("--artifact", type=Path, default=DEFAULT_ARTIFACT)

    p_restore = sub.add_parser("restore-proof")
    p_restore.add_argument("row_ref", help="tier/id, chosen by owner from reviewed artifact")

    p_apply = sub.add_parser("apply")
    p_apply.add_argument("--artifact", type=Path, default=DEFAULT_ARTIFACT)
    p_apply.add_argument("--owner-approved", action="store_true")
    p_apply.add_argument("--raw-rule", action="store_true")

    p_verify = sub.add_parser("verify")
    p_verify.add_argument("--artifact", type=Path, default=DEFAULT_ARTIFACT)

    args = parser.parse_args(argv)
    if args.cmd == "enumerate":
        print(enumerate_move_list(args.artifact))
        return 0
    if args.cmd == "restore-proof":
        run_restore_proof(args.row_ref)
        return 0
    if args.cmd == "apply":
        apply_reviewed_moves(
            args.artifact,
            owner_approved=args.owner_approved,
            raw_rule=args.raw_rule,
        )
        return 0
    if args.cmd == "verify":
        verify_reviewed_state(args.artifact)
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
