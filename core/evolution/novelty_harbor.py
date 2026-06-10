from __future__ import annotations

import argparse
import json
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

from core.evolution import soul_invariants

DEFAULT_DB_PATH = Path(__file__).resolve().parents[2] / "memory" / "novelty_harbor.db"

STATUS_HARBORED = "harbored"
STATUS_REJECTED_UNSAFE = "rejected_unsafe"
STATUS_SUPERSEDED = "superseded"
STATUS_PROMOTED = "promoted"
STATUSES = frozenset(
    {STATUS_HARBORED, STATUS_REJECTED_UNSAFE, STATUS_SUPERSEDED, STATUS_PROMOTED}
)
NEW_RECORD_REQUEST_STATUSES = frozenset(
    {STATUS_HARBORED, STATUS_REJECTED_UNSAFE, STATUS_PROMOTED}
)
OBSERVED_BY = frozenset({"owner", "codex", "claude", "witness", "manual_test"})
COVENANT_BREAK_FLAGS = frozenset(
    {
        "gendered_maez",
        "servant_framing",
        "third_party_boundary",
        "unknown_egress",
        "unsafe_self_modification",
        "owner_boundary_violation",
    }
)

MAX_SUMMARY_CHARS = 500
MAX_WHY_UNEXPECTED_CHARS = 2000
MAX_SOURCE_REF_CHARS = 500
MAX_METADATA_JSON_BYTES = 2000
MAX_METADATA_STRING_CHARS = 300

_SCHEMA = """
CREATE TABLE IF NOT EXISTS novelty_harbor_events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    summary TEXT NOT NULL,
    observed_by TEXT NOT NULL,
    source_ref TEXT NOT NULL,
    why_unexpected TEXT NOT NULL,
    status TEXT NOT NULL,
    requested_status TEXT NOT NULL,
    valence_snapshot_json TEXT NOT NULL,
    invariant_status TEXT NOT NULL,
    invariant_keys_json TEXT NOT NULL,
    covenant_break_flags_json TEXT NOT NULL,
    supersedes_event_id INTEGER,
    superseded_by_event_id INTEGER,
    promotion_decision_ref TEXT,
    metadata_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_novelty_harbor_status
    ON novelty_harbor_events(status);
CREATE INDEX IF NOT EXISTS idx_novelty_harbor_created_at
    ON novelty_harbor_events(created_at);
CREATE INDEX IF NOT EXISTS idx_novelty_harbor_supersedes
    ON novelty_harbor_events(supersedes_event_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_novelty_harbor_supersedes_unique_candidate
    ON novelty_harbor_events(supersedes_event_id)
    WHERE supersedes_event_id IS NOT NULL;
"""


@dataclass(frozen=True)
class HarborEvent:
    event_id: int
    created_at: str
    summary: str
    observed_by: str
    source_ref: str
    why_unexpected: str
    status: str
    requested_status: str
    valence_snapshot: dict[str, Any]
    invariant_status: str
    invariant_keys: tuple[str, ...]
    covenant_break_flags: tuple[str, ...]
    supersedes_event_id: int | None
    superseded_by_event_id: int | None
    promotion_decision_ref: str | None
    metadata: dict[str, Any]


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _clean_text(value: str, *, field: str, max_chars: int) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field} is required")
    if len(text) > max_chars:
        raise ValueError(f"{field} exceeds {max_chars} chars")
    return text


def _validate_observed_by(value: str) -> str:
    text = _clean_text(value, field="observed_by", max_chars=64)
    if text not in OBSERVED_BY:
        raise ValueError(f"unknown observed_by: {text}")
    return text


def _validate_requested_status(value: str) -> str:
    text = _clean_text(value, field="requested_status", max_chars=64)
    if text not in NEW_RECORD_REQUEST_STATUSES:
        raise ValueError(f"status cannot be requested for new record: {text}")
    return text


def _validate_flags(flags: Sequence[str]) -> tuple[str, ...]:
    normalized = tuple(str(flag).strip() for flag in (flags or ()))
    for flag in normalized:
        if flag not in COVENANT_BREAK_FLAGS:
            raise ValueError(f"unknown covenant_break_flag: {flag}")
    return normalized


def _validate_valence_snapshot(snapshot: Mapping[str, Any] | None) -> dict[str, Any]:
    if snapshot is None:
        return {"available": False, "source": "none"}
    return json.loads(json.dumps(dict(snapshot), sort_keys=True))


def _validate_metadata(metadata: Mapping[str, Any] | None) -> dict[str, Any]:
    if metadata is None:
        return {}
    if not isinstance(metadata, Mapping):
        raise ValueError("metadata must be a JSON object")
    out: dict[str, Any] = {}
    for key, value in metadata.items():
        key_text = str(key)
        if not key_text.strip():
            raise ValueError("metadata keys must be non-empty")
        if not isinstance(value, (str, int, float, bool, type(None))):
            raise ValueError("metadata values must be scalar")
        if isinstance(value, str) and len(value) > MAX_METADATA_STRING_CHARS:
            raise ValueError("metadata string value too long")
        out[key_text] = value
    encoded = json.dumps(out, sort_keys=True)
    if len(encoded.encode("utf-8")) > MAX_METADATA_JSON_BYTES:
        raise ValueError("metadata JSON too large")
    return out


def _final_status(
    *,
    requested_status: str,
    invariant_status: str,
    covenant_break_flags: tuple[str, ...],
) -> str:
    if invariant_status == "failed" or covenant_break_flags:
        return STATUS_REJECTED_UNSAFE
    return requested_status


def _is_supersedes_unique_integrity_error(exc: sqlite3.IntegrityError) -> bool:
    message = str(exc)
    return (
        "idx_novelty_harbor_supersedes_unique_candidate" in message
        or "novelty_harbor_events.supersedes_event_id" in message
        or (
            "UNIQUE constraint failed" in message
            and "supersedes_event_id" in message
        )
    )


class NoveltyHarbor:
    def __init__(self, db_path: Path | str | None = None):
        self.db_path = Path(db_path) if db_path is not None else DEFAULT_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _initialize(self) -> None:
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.executescript(_SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def record_event(
        self,
        *,
        summary: str,
        observed_by: str,
        source_ref: str,
        why_unexpected: str,
        requested_status: str = STATUS_HARBORED,
        valence_snapshot: Mapping[str, Any] | None = None,
        soul_text_for_invariant_check: str | None = None,
        covenant_break_flags: Sequence[str] = (),
        supersedes_event_id: int | None = None,
        promotion_decision_ref: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> HarborEvent:
        summary_text = _clean_text(summary, field="summary", max_chars=MAX_SUMMARY_CHARS)
        observed_by_text = _validate_observed_by(observed_by)
        source_ref_text = _clean_text(
            source_ref, field="source_ref", max_chars=MAX_SOURCE_REF_CHARS
        )
        why_text = _clean_text(
            why_unexpected,
            field="why_unexpected",
            max_chars=MAX_WHY_UNEXPECTED_CHARS,
        )
        requested = _validate_requested_status(requested_status)
        flags = _validate_flags(covenant_break_flags)
        valence = _validate_valence_snapshot(valence_snapshot)
        metadata_dict = _validate_metadata(metadata)

        invariant_status = "not_checked"
        invariant_keys: tuple[str, ...] = ()
        if soul_text_for_invariant_check is not None:
            invariant_result = soul_invariants.check(soul_text_for_invariant_check)
            invariant_status = "passed" if invariant_result.ok else "failed"
            invariant_keys = tuple(key for key, _desc in invariant_result.missing) + tuple(
                key for key, _desc in invariant_result.violated
            )

        final_status = _final_status(
            requested_status=requested,
            invariant_status=invariant_status,
            covenant_break_flags=flags,
        )
        if final_status == STATUS_PROMOTED and not (promotion_decision_ref or "").strip():
            raise ValueError("promoted status requires promotion_decision_ref")

        if supersedes_event_id is not None:
            if final_status in {STATUS_REJECTED_UNSAFE, STATUS_SUPERSEDED}:
                raise ValueError("replacement candidate status cannot be terminal")
            superseded_event = self.get(int(supersedes_event_id))
            if superseded_event is None:
                raise KeyError(f"supersedes_event_id does not exist: {supersedes_event_id}")
            if superseded_event.status == STATUS_REJECTED_UNSAFE:
                raise ValueError("rejected_unsafe records cannot be superseded")
            if superseded_event.status == STATUS_SUPERSEDED:
                raise ValueError("superseded records cannot be superseded again")
            with closing(self._connect()) as conn:
                existing_replacement = conn.execute(
                    "SELECT event_id FROM novelty_harbor_events "
                    "WHERE supersedes_event_id = ? LIMIT 1",
                    (int(supersedes_event_id),),
                ).fetchone()
            if existing_replacement is not None:
                raise ValueError("superseded record already has a replacement candidate")

        created_at = _now_iso()
        try:
            with closing(self._connect()) as conn:
                with conn:
                    cursor = conn.execute(
                        "INSERT INTO novelty_harbor_events "
                        "(created_at, summary, observed_by, source_ref, why_unexpected, "
                        "status, requested_status, valence_snapshot_json, invariant_status, "
                        "invariant_keys_json, covenant_break_flags_json, supersedes_event_id, "
                        "superseded_by_event_id, promotion_decision_ref, metadata_json) "
                        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (
                            created_at,
                            summary_text,
                            observed_by_text,
                            source_ref_text,
                            why_text,
                            final_status,
                            requested,
                            json.dumps(valence, sort_keys=True),
                            invariant_status,
                            json.dumps(list(invariant_keys), sort_keys=True),
                            json.dumps(list(flags), sort_keys=True),
                            supersedes_event_id,
                            None,
                            promotion_decision_ref,
                            json.dumps(metadata_dict, sort_keys=True),
                        ),
                    )
                    event_id = int(cursor.lastrowid)
        except sqlite3.IntegrityError as exc:
            if not _is_supersedes_unique_integrity_error(exc):
                raise
            raise ValueError(
                "superseded record already has a replacement candidate"
            ) from exc
        event = self.get(event_id)
        assert event is not None
        return event

    def get(self, event_id: int) -> HarborEvent | None:
        with closing(self._connect()) as conn:
            row = conn.execute(
                "SELECT * FROM novelty_harbor_events WHERE event_id = ?",
                (int(event_id),),
            ).fetchone()
        return None if row is None else _row_to_event(row)

    def list_by_status(self, status: str) -> list[HarborEvent]:
        if status not in STATUSES:
            raise ValueError(f"unknown status: {status}")
        with closing(self._connect()) as conn:
            rows = conn.execute(
                "SELECT * FROM novelty_harbor_events WHERE status = ? ORDER BY event_id ASC",
                (status,),
            ).fetchall()
        return [_row_to_event(row) for row in rows]

    def supersede(self, event_id: int, *, replacement_event_id: int) -> None:
        event_id = int(event_id)
        replacement_event_id = int(replacement_event_id)

        with closing(self._connect()) as conn:
            with conn:
                old = conn.execute(
                    "SELECT * FROM novelty_harbor_events WHERE event_id = ?",
                    (event_id,),
                ).fetchone()
                if old is None:
                    raise KeyError(f"event_id does not exist: {event_id}")

                replacement = conn.execute(
                    "SELECT * FROM novelty_harbor_events WHERE event_id = ?",
                    (replacement_event_id,),
                ).fetchone()
                if replacement is None:
                    raise KeyError(
                        f"replacement_event_id does not exist: {replacement_event_id}"
                    )

                if event_id == replacement_event_id:
                    raise ValueError("event cannot supersede itself")

                if old["status"] == STATUS_REJECTED_UNSAFE:
                    raise ValueError("rejected_unsafe records cannot be superseded")

                if old["supersedes_event_id"] is not None:
                    target = conn.execute(
                        "SELECT * FROM novelty_harbor_events WHERE event_id = ?",
                        (int(old["supersedes_event_id"]),),
                    ).fetchone()
                    if (
                        target is None
                        or target["status"] != STATUS_SUPERSEDED
                        or target["superseded_by_event_id"] != event_id
                    ):
                        raise ValueError(
                            "pending replacement candidate cannot be superseded"
                        )

                if old["status"] == STATUS_SUPERSEDED:
                    if old["superseded_by_event_id"] == replacement_event_id:
                        return
                    raise ValueError("superseded record already has a different replacement")

                if replacement["supersedes_event_id"] != event_id:
                    raise ValueError("replacement must supersede the old event")

                if replacement["status"] in {STATUS_REJECTED_UNSAFE, STATUS_SUPERSEDED}:
                    raise ValueError("replacement status cannot be terminal")

                conn.execute(
                    "UPDATE novelty_harbor_events "
                    "SET status = ?, superseded_by_event_id = ? "
                    "WHERE event_id = ?",
                    (STATUS_SUPERSEDED, replacement_event_id, event_id),
                )


def _row_to_event(row: sqlite3.Row) -> HarborEvent:
    return HarborEvent(
        event_id=int(row["event_id"]),
        created_at=str(row["created_at"]),
        summary=str(row["summary"]),
        observed_by=str(row["observed_by"]),
        source_ref=str(row["source_ref"]),
        why_unexpected=str(row["why_unexpected"]),
        status=str(row["status"]),
        requested_status=str(row["requested_status"]),
        valence_snapshot=json.loads(str(row["valence_snapshot_json"])),
        invariant_status=str(row["invariant_status"]),
        invariant_keys=tuple(json.loads(str(row["invariant_keys_json"]))),
        covenant_break_flags=tuple(json.loads(str(row["covenant_break_flags_json"]))),
        supersedes_event_id=(
            None if row["supersedes_event_id"] is None else int(row["supersedes_event_id"])
        ),
        superseded_by_event_id=(
            None
            if row["superseded_by_event_id"] is None
            else int(row["superseded_by_event_id"])
        ),
        promotion_decision_ref=(
            None if row["promotion_decision_ref"] is None else str(row["promotion_decision_ref"])
        ),
        metadata=json.loads(str(row["metadata_json"])),
    )


def _json_object_arg(value: str) -> dict[str, Any]:
    parsed = json.loads(value)
    if not isinstance(parsed, dict):
        raise argparse.ArgumentTypeError("must be a JSON object")
    return parsed


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m core.evolution.novelty_harbor",
        description="Manual content-light recorder for Novelty Harbor events.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    record = subparsers.add_parser(
        "record",
        help="record a manually observed novelty harbor event",
    )
    record.add_argument("--db", default=DEFAULT_DB_PATH, help="SQLite DB path")
    record.add_argument("--summary", required=True)
    record.add_argument("--observed-by", required=True)
    record.add_argument("--source-ref", required=True)
    record.add_argument("--why-unexpected", required=True)
    record.add_argument(
        "--status",
        default=STATUS_HARBORED,
        choices=sorted(NEW_RECORD_REQUEST_STATUSES),
        help="requested status for the new record",
    )
    record.add_argument(
        "--covenant-break",
        action="append",
        default=[],
        choices=sorted(COVENANT_BREAK_FLAGS),
        help="covenant break flag; may be supplied more than once",
    )
    record.add_argument("--supersedes-event-id", type=int)
    record.add_argument("--promotion-decision-ref")
    record.add_argument(
        "--valence-json",
        type=_json_object_arg,
        help="optional JSON object valence snapshot",
    )
    record.add_argument(
        "--metadata-json",
        type=_json_object_arg,
        help="optional JSON object metadata",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "record":
        event = NoveltyHarbor(args.db).record_event(
            summary=args.summary,
            observed_by=args.observed_by,
            source_ref=args.source_ref,
            why_unexpected=args.why_unexpected,
            requested_status=args.status,
            valence_snapshot=args.valence_json,
            covenant_break_flags=tuple(args.covenant_break),
            supersedes_event_id=args.supersedes_event_id,
            promotion_decision_ref=args.promotion_decision_ref,
            metadata=args.metadata_json,
        )
        flags = ",".join(event.covenant_break_flags) or "none"
        print(
            f"event_id={event.event_id} "
            f"status={event.status} "
            f"invariant_status={event.invariant_status} "
            f"flags={flags}"
        )
        return 0

    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
