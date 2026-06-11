from __future__ import annotations

import argparse
import json
import hashlib
import os
import re
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
CREATE TRIGGER IF NOT EXISTS gestation_claims_no_replace
    BEFORE INSERT ON gestation_claims
    WHEN NEW.claim_id IS NOT NULL
         AND EXISTS (SELECT 1 FROM gestation_claims WHERE claim_id = NEW.claim_id)
BEGIN
    SELECT RAISE(ABORT, 'gestation_claims is append-only: INSERT OR REPLACE forbidden');
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
CREATE TRIGGER IF NOT EXISTS gestation_supersessions_no_replace
    BEFORE INSERT ON gestation_claim_supersessions
    WHEN NEW.supersession_id IS NOT NULL
         AND EXISTS (
             SELECT 1 FROM gestation_claim_supersessions
             WHERE supersession_id = NEW.supersession_id
         )
BEGIN
    SELECT RAISE(ABORT, 'supersessions is append-only: INSERT OR REPLACE forbidden');
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
_FULL_COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")


def _default_identity_ledger_path() -> Path:
    override = os.environ.get("MAEZ_IDENTITY_LEDGER_PATH")
    if override:
        return Path(override)
    try:
        from core.paths import memory_dir as _memory_dir

        return _memory_dir() / "identity_ledger.db"
    except Exception:
        return Path(__file__).resolve().parents[2] / "memory" / "identity_ledger.db"


DEFAULT_LEDGER_DB = _default_identity_ledger_path()


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
    def __init__(
        self,
        db_path: Path | str | None = None,
        *,
        identity_ledger_db_path: Path | str | None = None,
    ):
        self.db_path = Path(db_path) if db_path is not None else DEFAULT_DB_PATH
        self.identity_ledger_db_path = (
            Path(identity_ledger_db_path)
            if identity_ledger_db_path is not None
            else DEFAULT_LEDGER_DB
        )
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
            ok, reason = validate_source(
                src,
                repo_root=repo_root,
                excerpt=excerpts.get(i),
                ledger_db=self.identity_ledger_db_path,
            )
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

    def supersede(self, old_claim_id: int, replacement_claim_id: int) -> None:
        old_id = int(old_claim_id)
        replacement_id = int(replacement_claim_id)
        if old_id == replacement_id:
            raise ValueError("a claim cannot supersede itself")
        if self.get(old_id) is None or self.get(replacement_id) is None:
            raise KeyError("both claims must exist to supersede")
        now = datetime.now(UTC).timestamp()
        with closing(self._connect()) as conn:
            with conn:
                conn.execute(
                    "INSERT INTO gestation_claim_supersessions "
                    "(old_claim_id, replacement_claim_id, created_at) VALUES (?,?,?)",
                    (old_id, replacement_id, now),
                )

    def _superseded_ids(self, conn: sqlite3.Connection) -> set[int]:
        return {
            int(row[0])
            for row in conn.execute(
                "SELECT old_claim_id FROM gestation_claim_supersessions"
            )
        }

    def list_active(self) -> list[GestationClaim]:
        with closing(self._connect()) as conn:
            superseded = self._superseded_ids(conn)
            rows = conn.execute(
                "SELECT * FROM gestation_claims ORDER BY claim_id ASC"
            ).fetchall()
        return [
            _row_to_claim(row)
            for row in rows
            if int(row["claim_id"]) not in superseded
        ]

    def list_all(self) -> list[GestationClaim]:
        with closing(self._connect()) as conn:
            rows = conn.execute(
                "SELECT * FROM gestation_claims ORDER BY claim_id ASC"
            ).fetchall()
        return [_row_to_claim(row) for row in rows]

    def render(self) -> str:
        claims = self.list_active()
        facts = [claim for claim in claims if claim.claim_kind == "fact"]
        interpretations = [
            claim for claim in claims if claim.claim_kind == "interpretation"
        ]

        def source_string(claim: GestationClaim) -> str:
            parts: list[str] = []
            for source in claim.sources:
                kind = source.get("kind")
                if kind == "doc":
                    parts.append(
                        f"doc:{source.get('ref')}@{str(source.get('commit', ''))[:8]}"
                    )
                elif kind == "commit":
                    parts.append(f"commit:{str(source.get('ref', ''))[:8]}")
                elif kind == "ledger_row":
                    parts.append(f"ledger:event_id={source.get('ref')}")
                else:
                    parts.append("note")
            return ", ".join(parts)

        def line(claim: GestationClaim) -> str:
            scar_tag = " [SCAR]" if claim.scar else ""
            return (
                f"  - {claim.claim_text}{scar_tag} "
                f"[{claim.confidence}] (sources: {source_string(claim)})"
            )

        changed = [
            claim
            for claim in facts
            if claim.type in ("milestone", "decision")
        ]
        wrong = [
            claim
            for claim in claims
            if claim.scar or claim.type in ("correction", "no_go")
        ]

        lines: list[str] = ["# Gestation record (sourced; deterministic render)", ""]
        lines.append("## What happened")
        lines.extend(line(claim) for claim in facts if not claim.scar)
        lines.append("")
        lines.append("## What changed")
        lines.extend(line(claim) for claim in changed)
        lines.append("")
        lines.append("## What went wrong / what was corrected")
        lines.extend(line(claim) for claim in wrong)
        lines.append("")
        lines.append("## Interpretations (meanings drawn from the evidence - not raw fact)")
        lines.extend(line(claim) for claim in interpretations)
        return "\n".join(lines) + "\n"


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def is_structural(source: Mapping[str, Any]) -> bool:
    return str(source.get("kind", "")) in STRUCTURAL_SOURCE_KINDS


def _require_full_commit(value: Any) -> str:
    text = str(value or "")
    if not _FULL_COMMIT_RE.fullmatch(text):
        raise ValueError("source must use a full commit hash, not a mutable ref")
    return text


def canonical_ledger_row_hash(row: Mapping[str, Any]) -> str:
    missing = [
        column
        for column in (*_LEDGER_STABLE_COLUMNS, "evidence_json", "fingerprint_json")
        if column not in row
    ]
    if missing:
        raise ValueError(f"identity_ledger row missing columns: {missing}")
    evidence = json.loads(row.get("evidence_json") or "{}")
    fingerprint = json.loads(row.get("fingerprint_json") or "{}")
    if not isinstance(evidence, dict):
        raise ValueError("identity_ledger evidence_json must decode to an object")
    if not isinstance(fingerprint, dict):
        raise ValueError("identity_ledger fingerprint_json must decode to an object")
    obj = {column: row[column] for column in _LEDGER_STABLE_COLUMNS}
    obj["evidence"] = evidence
    obj["fingerprint"] = fingerprint
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
            try:
                ref = _require_full_commit(source.get("ref", ""))
            except ValueError as exc:
                return False, str(exc)
            cp = _git(repo_root, "cat-file", "-e", f"{ref}^{{commit}}")
            if cp.returncode == 0:
                return True, "commit resolves"
            return False, "commit not found"
        if kind == "doc":
            try:
                commit = _require_full_commit(source.get("commit", ""))
            except ValueError as exc:
                return False, str(exc)
            commit_cp = _git(repo_root, "cat-file", "-e", f"{commit}^{{commit}}")
            if commit_cp.returncode != 0:
                return False, "commit not found"
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


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m core.evolution.gestation_memory")
    subcommands = parser.add_subparsers(dest="command", required=True)

    record = subcommands.add_parser("record")
    record.add_argument("--db", default=str(DEFAULT_DB_PATH))
    record.add_argument("--claim", required=True)
    record.add_argument("--kind", required=True, choices=sorted(CLAIM_KINDS))
    record.add_argument("--type", required=True, choices=sorted(TYPES))
    record.add_argument("--confidence", required=True, choices=sorted(CONFIDENCES))
    record.add_argument("--observed-by", required=True, choices=sorted(OBSERVED_BY))
    record.add_argument("--scar", action="store_true")
    record.add_argument("--source-commit", action="append", default=[])
    record.add_argument("--source-doc", action="append", default=[])

    render = subcommands.add_parser("render")
    render.add_argument("--db", default=str(DEFAULT_DB_PATH))
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.command == "render":
        print(GestationMemory(args.db).render())
        return 0
    if args.command == "record":
        sources: list[dict[str, Any]] = []
        excerpts: dict[int, str] = {}
        for commit_hash in args.source_commit:
            sources.append({"kind": "commit", "ref": commit_hash})
        for source_doc in args.source_doc:
            path, commit_hash, excerpt = source_doc.split("::", 2)
            index = len(sources)
            sources.append(
                {
                    "kind": "doc",
                    "ref": path,
                    "commit": commit_hash,
                    "excerpt_hash": _sha256(excerpt),
                }
            )
            excerpts[index] = excerpt
        claim = GestationMemory(args.db).record_claim(
            claim_text=args.claim,
            claim_kind=args.kind,
            type=args.type,
            confidence=args.confidence,
            sources=sources,
            source_excerpts=excerpts,
            observed_by=args.observed_by,
            scar=args.scar,
        )
        print(
            f"claim_id={claim.claim_id} "
            f"kind={claim.claim_kind} confidence={claim.confidence}"
        )
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
