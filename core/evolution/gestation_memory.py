from __future__ import annotations

import json
import hashlib
import sqlite3
import subprocess
from contextlib import closing
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

DEFAULT_DB_PATH = Path(__file__).resolve().parents[2] / "memory" / "gestation_claims.db"

CLAIM_KINDS = frozenset({"fact", "interpretation"})
TYPES = frozenset({"milestone", "decision", "scar", "correction", "no_go"})
CONFIDENCES = frozenset({"witnessed", "documented", "inferred"})
OBSERVED_BY = frozenset({"owner", "codex", "claude", "witness"})
SOURCE_KINDS = frozenset({"doc", "commit", "ledger_row", "witness_note"})
STRUCTURAL_SOURCE_KINDS = frozenset({"doc", "commit", "ledger_row"})

MAX_CLAIM_CHARS = 500
MAX_WITNESS_NOTE_CHARS = 500
MAX_EXCERPT_CHARS = 2000

_SCHEMA = """
CREATE TABLE IF NOT EXISTS gestation_claims (
    claim_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at    REAL    NOT NULL,
    claim_text    TEXT    NOT NULL,
    claim_kind    TEXT    NOT NULL,
    type          TEXT    NOT NULL,
    confidence    TEXT    NOT NULL,
    scar          INTEGER NOT NULL,
    sources_json  TEXT    NOT NULL,
    observed_by   TEXT    NOT NULL,
    metadata_json TEXT    NOT NULL
);
CREATE TABLE IF NOT EXISTS gestation_claim_supersessions (
    supersession_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    old_claim_id         INTEGER NOT NULL,
    replacement_claim_id INTEGER NOT NULL,
    created_at           REAL    NOT NULL
);
CREATE TRIGGER IF NOT EXISTS gestation_claims_no_update
    BEFORE UPDATE ON gestation_claims
BEGIN
    SELECT RAISE(ABORT, 'gestation_claims is append-only: UPDATE forbidden');
END;
CREATE TRIGGER IF NOT EXISTS gestation_claims_no_delete
    BEFORE DELETE ON gestation_claims
BEGIN
    SELECT RAISE(ABORT, 'gestation_claims is append-only: DELETE forbidden');
END;
CREATE TRIGGER IF NOT EXISTS gestation_supersessions_no_update
    BEFORE UPDATE ON gestation_claim_supersessions
BEGIN
    SELECT RAISE(ABORT, 'supersessions is append-only: UPDATE forbidden');
END;
CREATE TRIGGER IF NOT EXISTS gestation_supersessions_no_delete
    BEFORE DELETE ON gestation_claim_supersessions
BEGIN
    SELECT RAISE(ABORT, 'supersessions is append-only: DELETE forbidden');
END;
CREATE INDEX IF NOT EXISTS idx_gestation_supersedes
    ON gestation_claim_supersessions(old_claim_id);
"""

_LEDGER_STABLE_COLUMNS = (
    "event_id",
    "ts",
    "event_type",
    "continuity_id",
    "parent_continuity_id",
    "severity",
    "reason",
)
DEFAULT_LEDGER_DB = Path(__file__).resolve().parents[2] / "memory" / "identity_ledger.db"


@dataclass(frozen=True)
class GestationClaim:
    claim_id: int
    created_at: float
    claim_text: str
    claim_kind: str
    type: str
    confidence: str
    scar: bool
    sources: tuple[dict[str, Any], ...]
    observed_by: str
    metadata: dict[str, Any]


class GestationMemory:
    def __init__(self, db_path: Path | str | None = None):
        self.db_path = Path(db_path) if db_path is not None else DEFAULT_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.executescript(_SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _repo_root(self) -> Path:
        return Path(__file__).resolve().parents[2]

    def record_claim(
        self,
        *,
        claim_text: str,
        claim_kind: str,
        type: str,
        confidence: str,
        sources: Sequence[Mapping[str, Any]],
        observed_by: str,
        source_excerpts: Mapping[int, str] | None = None,
        scar: bool = False,
        metadata: Mapping[str, Any] | None = None,
    ) -> GestationClaim:
        text = str(claim_text or "").strip()
        if not text:
            raise ValueError("claim_text is required")
        if len(text) > MAX_CLAIM_CHARS:
            raise ValueError("claim_text too long")
        if claim_kind not in CLAIM_KINDS:
            raise ValueError(f"unknown claim_kind {claim_kind!r}")
        if type not in TYPES:
            raise ValueError(f"unknown type {type!r}")
        if confidence not in CONFIDENCES:
            raise ValueError(f"unknown confidence {confidence!r}")
        if observed_by not in OBSERVED_BY:
            raise ValueError(f"unknown observed_by {observed_by!r}")
        if claim_kind == "fact" and confidence == "inferred":
            raise ValueError(
                "a fact may not be inferred (inferred is for interpretations)"
            )

        excerpts = source_excerpts or {}
        repo_root = self._repo_root()
        resolved_structural = 0
        clean_sources: list[dict[str, Any]] = []
        for i, src in enumerate(sources):
            kind = str(src.get("kind", ""))
            if kind not in SOURCE_KINDS:
                raise ValueError(f"unknown source kind {kind!r}")
            if kind == "witness_note":
                note = str(src.get("ref", "")).strip()
                if not note or len(note) > MAX_WITNESS_NOTE_CHARS:
                    raise ValueError("witness_note ref invalid")
                clean_sources.append({"kind": "witness_note", "ref": note})
                continue
            ok, reason = validate_source(src, repo_root=repo_root, excerpt=excerpts.get(i))
            if not ok:
                raise ValueError(f"source[{i}] ({kind}) did not resolve: {reason}")
            resolved_structural += 1
            clean_sources.append(dict(src))
        if resolved_structural < 1:
            raise ValueError("at least one resolvable structural source is required")

        meta = json.loads(json.dumps(dict(metadata or {}), sort_keys=True))
        now = datetime.now(UTC).timestamp()
        with closing(self._connect()) as conn:
            with conn:
                cur = conn.execute(
                    "INSERT INTO gestation_claims "
                    "(created_at, claim_text, claim_kind, type, confidence, scar, "
                    "sources_json, observed_by, metadata_json) "
                    "VALUES (?,?,?,?,?,?,?,?,?)",
                    (
                        now,
                        text,
                        claim_kind,
                        type,
                        confidence,
                        int(bool(scar)),
                        json.dumps(clean_sources, sort_keys=True),
                        observed_by,
                        json.dumps(meta, sort_keys=True),
                    ),
                )
                claim_id = int(cur.lastrowid)
        got = self.get(claim_id)
        if got is None:
            raise RuntimeError("inserted gestation claim could not be read back")
        return got

    def get(self, claim_id: int) -> GestationClaim | None:
        with closing(self._connect()) as conn:
            row = conn.execute(
                "SELECT * FROM gestation_claims WHERE claim_id = ?",
                (int(claim_id),),
            ).fetchone()
        return None if row is None else _row_to_claim(row)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def is_structural(source: Mapping[str, Any]) -> bool:
    return str(source.get("kind", "")) in STRUCTURAL_SOURCE_KINDS


def canonical_ledger_row_hash(row: Mapping[str, Any]) -> str:
    obj = {column: row.get(column) for column in _LEDGER_STABLE_COLUMNS}
    obj["evidence"] = json.loads(row.get("evidence_json") or "{}")
    obj["fingerprint"] = json.loads(row.get("fingerprint_json") or "{}")
    return _sha256(json.dumps(obj, sort_keys=True, separators=(",", ":")))


def _git(repo_root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo_root), *args],
        capture_output=True,
        text=True,
        timeout=15,
    )


def _read_only_sqlite_uri(path: Path) -> str:
    return f"file:{path.resolve()}?mode=ro"


def _row_to_claim(row: sqlite3.Row) -> GestationClaim:
    return GestationClaim(
        claim_id=int(row["claim_id"]),
        created_at=float(row["created_at"]),
        claim_text=str(row["claim_text"]),
        claim_kind=str(row["claim_kind"]),
        type=str(row["type"]),
        confidence=str(row["confidence"]),
        scar=bool(row["scar"]),
        sources=tuple(json.loads(row["sources_json"])),
        observed_by=str(row["observed_by"]),
        metadata=json.loads(row["metadata_json"]),
    )


def validate_source(
    source: Mapping[str, Any],
    *,
    repo_root: Path,
    excerpt: str | None = None,
    ledger_db: Path | None = None,
) -> tuple[bool, str]:
    """Return (ok, reason). Any error or mismatch fails closed."""
    kind = str(source.get("kind", ""))
    if kind not in SOURCE_KINDS:
        return False, f"unknown source kind {kind!r}"
    try:
        if kind == "witness_note":
            return True, "context-only (not structural)"
        if kind == "commit":
            ref = str(source.get("ref", ""))
            cp = _git(repo_root, "cat-file", "-e", f"{ref}^{{commit}}")
            if cp.returncode == 0:
                return True, "commit resolves"
            return False, "commit not found"
        if kind == "doc":
            commit = str(source.get("commit", ""))
            ref = str(source.get("ref", ""))
            cp = _git(repo_root, "show", f"{commit}:{ref}")
            if cp.returncode != 0:
                return False, "doc not found at commit"
            if excerpt is None or not excerpt or len(excerpt) > MAX_EXCERPT_CHARS:
                return False, "excerpt missing or invalid"
            if excerpt not in cp.stdout:
                return False, "excerpt not present in file at commit"
            if _sha256(excerpt) != str(source.get("excerpt_hash", "")):
                return False, "excerpt_hash mismatch"
            return True, "doc excerpt verified"
        if kind == "ledger_row":
            db = ledger_db if ledger_db is not None else DEFAULT_LEDGER_DB
            with closing(
                sqlite3.connect(_read_only_sqlite_uri(Path(db)), uri=True)
            ) as conn:
                conn.row_factory = sqlite3.Row
                row = conn.execute(
                    "SELECT * FROM identity_ledger WHERE event_id = ?",
                    (int(source.get("ref")),),
                ).fetchone()
            if row is None:
                return False, "ledger event_id not found"
            if canonical_ledger_row_hash(dict(row)) != str(
                source.get("excerpt_hash", "")
            ):
                return False, "ledger canonical hash mismatch"
            return True, "ledger row verified"
    except Exception as exc:
        return False, f"source validation error: {exc}"
    return False, "unhandled source kind"
