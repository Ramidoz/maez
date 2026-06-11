# Gestation-Memory v0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build Maez's developmental self-history *reader* — a truly append-only index of atomic, provenance-validated claims about how Maez was built, plus a deterministic renderer ("a baby book made from receipts").

**Architecture:** One offline/manual module `core/evolution/gestation_memory.py` (mirrors `novelty_harbor.py`'s validate-computes-not-trusts shape and `want_events`'s `RAISE(ABORT)` append-only triggers) + a CLI. Two insert-only tables: `gestation_claims` (immutable) and `gestation_claim_supersessions` (edges). Sources are validated at record-time against git and a read-only `identity_ledger` query; invalid → rejected, not stored. No daemon wiring, no LLM, no writes to any ledger.

**Tech Stack:** Python 3.11+, stdlib `sqlite3` / `hashlib` / `json` / `subprocess`, `unittest`. Runner: `/home/rohit/maez/.venv/bin/python -B -m unittest` (NOT pytest). Branch `gestation-memory-v0` from `ae9488b`.

**Verified precedents:** `want_events` append-only triggers (`core/evolution/wants.py:278-295` — `BEFORE UPDATE/DELETE ... RAISE(ABORT,...)`); `novelty_harbor.py` (frozen dataclass, `record_event` validation, `_clean_text`, CLI, AST boundary test); git via `["git","-C",repo_root,...]`; `identity_ledger` columns = `event_id, ts, event_type, continuity_id, parent_continuity_id, severity, reason, evidence_json, fingerprint_json` (read read-only, `mode=ro`, no `IdentityLedger` import). Offline organ → **no `## Predicted effect`**; witness is manual.

---

## File Structure

| File | Change | Responsibility |
|------|--------|----------------|
| `core/evolution/gestation_memory.py` | Create | schema+triggers, `GestationClaim`, source validators, `GestationMemory` store, deterministic renderer, CLI |
| `tests/test_gestation_memory.py` | Create | store/validation/quarantine/supersede/renderer tests |
| `tests/test_gestation_memory_sources.py` | Create | source-validator tests (git + ledger canonical hash) |
| `tests/test_gestation_memory_boundary.py` | Create | AST boundary: no llm/daemon/ledger-writer/wants-writer imports |

---

## Task 1: Schema + append-only triggers + store skeleton

**Files:** Create `core/evolution/gestation_memory.py`; Test `tests/test_gestation_memory.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_gestation_memory.py`:

```python
import sqlite3
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from core.evolution.gestation_memory import GestationMemory


class SchemaTests(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.db = Path(self._tmp.name) / "g.db"
        self.gm = GestationMemory(self.db)

    def tearDown(self):
        self._tmp.cleanup()

    def test_tables_exist(self):
        with sqlite3.connect(self.db) as c:
            names = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertIn("gestation_claims", names)
        self.assertIn("gestation_claim_supersessions", names)

    def test_gestation_claims_update_is_aborted(self):
        # insert a raw row, then prove UPDATE/DELETE abort (append-only triggers)
        with sqlite3.connect(self.db) as c:
            c.execute(
                "INSERT INTO gestation_claims "
                "(created_at, claim_text, claim_kind, type, confidence, scar, "
                " sources_json, observed_by, metadata_json) "
                "VALUES (1.0,'x','fact','milestone','witnessed',0,'[]','owner','{}')"
            )
            with self.assertRaises(sqlite3.IntegrityError):
                c.execute("UPDATE gestation_claims SET claim_text='y' WHERE claim_id=1")
            with self.assertRaises(sqlite3.IntegrityError):
                c.execute("DELETE FROM gestation_claims WHERE claim_id=1")

    def test_supersessions_update_is_aborted(self):
        with sqlite3.connect(self.db) as c:
            c.execute(
                "INSERT INTO gestation_claim_supersessions "
                "(old_claim_id, replacement_claim_id, created_at) VALUES (1,2,1.0)"
            )
            with self.assertRaises(sqlite3.IntegrityError):
                c.execute("UPDATE gestation_claim_supersessions SET old_claim_id=9 WHERE supersession_id=1")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_gestation_memory.SchemaTests -v`
Expected: FAIL — `ModuleNotFoundError`/`ImportError`

- [ ] **Step 3: Write minimal implementation**

Create `core/evolution/gestation_memory.py` (start it). The triggers mirror `want_events` (`wants.py:278-295`):

```python
from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from dataclasses import dataclass
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
    supersession_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    old_claim_id        INTEGER NOT NULL,
    replacement_claim_id INTEGER NOT NULL,
    created_at          REAL    NOT NULL
);
CREATE TRIGGER IF NOT EXISTS gestation_claims_no_update
    BEFORE UPDATE ON gestation_claims
BEGIN SELECT RAISE(ABORT, 'gestation_claims is append-only: UPDATE forbidden'); END;
CREATE TRIGGER IF NOT EXISTS gestation_claims_no_delete
    BEFORE DELETE ON gestation_claims
BEGIN SELECT RAISE(ABORT, 'gestation_claims is append-only: DELETE forbidden'); END;
CREATE TRIGGER IF NOT EXISTS gestation_supersessions_no_update
    BEFORE UPDATE ON gestation_claim_supersessions
BEGIN SELECT RAISE(ABORT, 'supersessions is append-only: UPDATE forbidden'); END;
CREATE TRIGGER IF NOT EXISTS gestation_supersessions_no_delete
    BEFORE DELETE ON gestation_claim_supersessions
BEGIN SELECT RAISE(ABORT, 'supersessions is append-only: DELETE forbidden'); END;
CREATE INDEX IF NOT EXISTS idx_gestation_supersedes
    ON gestation_claim_supersessions(old_claim_id);
"""


@dataclass(frozen=True)
class GestationClaim:
    claim_id: int
    created_at: float
    claim_text: str
    claim_kind: str
    type: str
    confidence: str
    scar: bool
    sources: tuple[dict, ...]
    observed_by: str
    metadata: dict


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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_gestation_memory.SchemaTests -v`
Expected: PASS (3 tests). The `sqlite3.IntegrityError` is what `RAISE(ABORT)` triggers raise.

- [ ] **Step 5: Commit**

```bash
git add core/evolution/gestation_memory.py tests/test_gestation_memory.py
git commit -m "feat(gestation-memory): append-only two-table schema + triggers + store skeleton

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2: Source validators (the immune system)

**Files:** Modify `core/evolution/gestation_memory.py`; Test `tests/test_gestation_memory_sources.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_gestation_memory_sources.py`:

```python
import hashlib
import json
import subprocess
import unittest
from pathlib import Path

from core.evolution import gestation_memory as gm

REPO = Path(__file__).resolve().parents[1]


def _sha(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


class DocSourceTests(unittest.TestCase):
    def setUp(self):
        # a real committed file + commit on this branch: the spec itself
        self.path = "docs/superpowers/specs/2026-06-10-gestation-memory-v0-design.md"
        self.commit = subprocess.run(
            ["git", "-C", str(REPO), "rev-parse", "HEAD"],
            capture_output=True, text=True,
        ).stdout.strip()
        content = subprocess.run(
            ["git", "-C", str(REPO), "show", f"{self.commit}:{self.path}"],
            capture_output=True, text=True,
        ).stdout
        # take a real line as the excerpt
        self.excerpt = next(line for line in content.splitlines() if "baby book" in line)

    def test_valid_doc_source_resolves(self):
        src = {"kind": "doc", "ref": self.path, "commit": self.commit,
               "excerpt_hash": _sha(self.excerpt)}
        ok, _ = gm.validate_source(src, repo_root=REPO, excerpt=self.excerpt)
        self.assertTrue(ok)

    def test_doc_excerpt_hash_mismatch_rejected(self):
        src = {"kind": "doc", "ref": self.path, "commit": self.commit,
               "excerpt_hash": _sha("a line that is not in the file")}
        ok, reason = gm.validate_source(src, repo_root=REPO, excerpt="a line that is not in the file")
        self.assertFalse(ok)

    def test_commit_source_resolves(self):
        src = {"kind": "commit", "ref": self.commit}
        ok, _ = gm.validate_source(src, repo_root=REPO)
        self.assertTrue(ok)

    def test_bad_commit_rejected(self):
        ok, _ = gm.validate_source({"kind": "commit", "ref": "0" * 40}, repo_root=REPO)
        self.assertFalse(ok)

    def test_witness_note_is_not_structural(self):
        self.assertFalse(gm.is_structural({"kind": "witness_note", "ref": "I saw it"}))
        self.assertTrue(gm.is_structural({"kind": "commit", "ref": self.commit}))


class LedgerRowHashTests(unittest.TestCase):
    def test_canonical_row_hash_is_byte_defined(self):
        row = {
            "event_id": 7, "ts": 1.5, "event_type": "restart",
            "continuity_id": "c1", "parent_continuity_id": None,
            "severity": "info", "reason": "ok",
            "evidence_json": '{"b":2,"a":1}', "fingerprint_json": '{"z":9}',
        }
        h = gm.canonical_ledger_row_hash(row)
        obj = {
            "event_id": 7, "ts": 1.5, "event_type": "restart",
            "continuity_id": "c1", "parent_continuity_id": None,
            "severity": "info", "reason": "ok",
            "evidence": {"a": 1, "b": 2}, "fingerprint": {"z": 9},
        }
        expected = hashlib.sha256(
            json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        self.assertEqual(h, expected)
```

- [ ] **Step 2: Run to verify it fails**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_gestation_memory_sources -v`
Expected: FAIL — `AttributeError: module ... has no attribute 'validate_source'`

- [ ] **Step 3: Write minimal implementation**

Append to `core/evolution/gestation_memory.py`:

```python
import hashlib
import subprocess

_LEDGER_STABLE_COLUMNS = (
    "event_id", "ts", "event_type", "continuity_id", "parent_continuity_id",
    "severity", "reason",
)
DEFAULT_LEDGER_DB = Path(__file__).resolve().parents[2] / "memory" / "identity_ledger.db"


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def is_structural(source: Mapping[str, Any]) -> bool:
    return str(source.get("kind", "")) in STRUCTURAL_SOURCE_KINDS


def canonical_ledger_row_hash(row: Mapping[str, Any]) -> str:
    obj = {c: row.get(c) for c in _LEDGER_STABLE_COLUMNS}
    obj["evidence"] = json.loads(row.get("evidence_json") or "{}")
    obj["fingerprint"] = json.loads(row.get("fingerprint_json") or "{}")
    return _sha256(json.dumps(obj, sort_keys=True, separators=(",", ":")))


def _git(repo_root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(repo_root), *args],
        capture_output=True, text=True, timeout=15,
    )


def validate_source(
    source: Mapping[str, Any],
    *,
    repo_root: Path,
    excerpt: str | None = None,
    ledger_db: Path | None = None,
) -> tuple[bool, str]:
    """Return (ok, reason). Fail-closed: any error/mismatch -> (False, reason)."""
    kind = str(source.get("kind", ""))
    if kind not in SOURCE_KINDS:
        return False, f"unknown source kind {kind!r}"
    try:
        if kind == "witness_note":
            return True, "context-only (not structural)"
        if kind == "commit":
            cp = _git(repo_root, "cat-file", "-e", f"{source.get('ref','')}^{{commit}}")
            return (cp.returncode == 0), ("commit resolves" if cp.returncode == 0 else "commit not found")
        if kind == "doc":
            commit = str(source.get("commit", ""))
            ref = str(source.get("ref", ""))
            cp = _git(repo_root, "show", f"{commit}:{ref}")
            if cp.returncode != 0:
                return False, "doc not found at commit"
            if excerpt is None or excerpt not in cp.stdout:
                return False, "excerpt not present in file at commit"
            if _sha256(excerpt) != str(source.get("excerpt_hash", "")):
                return False, "excerpt_hash mismatch"
            return True, "doc excerpt verified"
        if kind == "ledger_row":
            db = ledger_db if ledger_db is not None else DEFAULT_LEDGER_DB
            uri = Path(db).resolve().as_uri() + "?mode=ro"
            with closing(sqlite3.connect(uri, uri=True)) as conn:
                conn.row_factory = sqlite3.Row
                row = conn.execute(
                    "SELECT * FROM identity_ledger WHERE event_id = ?",
                    (int(source.get("ref")),),
                ).fetchone()
            if row is None:
                return False, "ledger event_id not found"
            if canonical_ledger_row_hash(dict(row)) != str(source.get("excerpt_hash", "")):
                return False, "ledger canonical hash mismatch"
            return True, "ledger row verified"
    except Exception as exc:  # fail-closed
        return False, f"source validation error: {exc}"
    return False, "unhandled source kind"
```

- [ ] **Step 4: Run to verify it passes**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_gestation_memory_sources -v`
Expected: PASS. (The doc test cites this very spec file at HEAD — a real, committed receipt.)

- [ ] **Step 5: Commit**

```bash
git add core/evolution/gestation_memory.py tests/test_gestation_memory_sources.py
git commit -m "feat(gestation-memory): source validators (doc git-fingerprint, commit, ledger canonical hash)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 3: `record_claim` — validation + quarantine + content-light

**Files:** Modify `core/evolution/gestation_memory.py`; Test `tests/test_gestation_memory.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_gestation_memory.py` (uses the real spec doc as a source, like Task 2):

```python
import subprocess
import hashlib

REPO = Path(__file__).resolve().parents[1]


def _doc_source():
    path = "docs/superpowers/specs/2026-06-10-gestation-memory-v0-design.md"
    commit = subprocess.run(["git", "-C", str(REPO), "rev-parse", "HEAD"],
                            capture_output=True, text=True).stdout.strip()
    content = subprocess.run(["git", "-C", str(REPO), "show", f"{commit}:{path}"],
                             capture_output=True, text=True).stdout
    excerpt = next(line for line in content.splitlines() if "baby book" in line)
    h = hashlib.sha256(excerpt.encode("utf-8")).hexdigest()
    return {"kind": "doc", "ref": path, "commit": commit, "excerpt_hash": h}, excerpt


class RecordClaimTests(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.gm = GestationMemory(Path(self._tmp.name) / "g.db")
        self.src, self.excerpt = _doc_source()

    def tearDown(self):
        self._tmp.cleanup()

    def test_valid_fact_stored(self):
        c = self.gm.record_claim(
            claim_text="The spec calls this a baby book made from receipts.",
            claim_kind="fact", type="milestone", confidence="documented",
            sources=[self.src], source_excerpts={0: self.excerpt}, observed_by="claude",
        )
        self.assertEqual(self.gm.get(c.claim_id).claim_text, c.claim_text)

    def test_witness_note_only_rejected(self):
        with self.assertRaises(ValueError):
            self.gm.record_claim(
                claim_text="x", claim_kind="fact", type="milestone", confidence="witnessed",
                sources=[{"kind": "witness_note", "ref": "I saw it"}], observed_by="claude",
            )

    def test_inferred_fact_rejected(self):
        with self.assertRaises(ValueError):
            self.gm.record_claim(
                claim_text="x", claim_kind="fact", type="milestone", confidence="inferred",
                sources=[self.src], source_excerpts={0: self.excerpt}, observed_by="claude",
            )

    def test_inferred_interpretation_accepted(self):
        c = self.gm.record_claim(
            claim_text="Maez learned to try without declaring victory.",
            claim_kind="interpretation", type="milestone", confidence="inferred",
            sources=[self.src], source_excerpts={0: self.excerpt}, observed_by="claude",
        )
        self.assertEqual(c.confidence, "inferred")

    def test_doc_excerpt_mismatch_rejected(self):
        bad = dict(self.src, excerpt_hash="deadbeef")
        with self.assertRaises(ValueError):
            self.gm.record_claim(
                claim_text="x", claim_kind="fact", type="milestone", confidence="documented",
                sources=[bad], source_excerpts={0: self.excerpt}, observed_by="claude",
            )
```

- [ ] **Step 2: Run to verify it fails**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_gestation_memory.RecordClaimTests -v`
Expected: FAIL — `AttributeError: ... 'record_claim'`

- [ ] **Step 3: Write minimal implementation**

Append the methods to the `GestationMemory` class (the `repo_root` is the maez repo root; the doc/commit validators run against it). Add `import json` is already present:

```python
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
        text = (claim_text or "").strip()
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
        # fact/interpretation quarantine
        if claim_kind == "fact" and confidence == "inferred":
            raise ValueError("a fact may not be inferred (inferred is for interpretations)")
        # sources: >=1 resolvable structural source
        excerpts = source_excerpts or {}
        repo_root = self._repo_root()
        resolved_structural = 0
        clean_sources: list[dict] = []
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

        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).timestamp()
        meta = json.loads(json.dumps(dict(metadata or {})))  # content-light copy
        with closing(self._connect()) as conn:
            with conn:
                cur = conn.execute(
                    "INSERT INTO gestation_claims "
                    "(created_at, claim_text, claim_kind, type, confidence, scar, "
                    " sources_json, observed_by, metadata_json) VALUES (?,?,?,?,?,?,?,?,?)",
                    (now, text, claim_kind, type, confidence, int(bool(scar)),
                     json.dumps(clean_sources, sort_keys=True), observed_by,
                     json.dumps(meta, sort_keys=True)),
                )
                claim_id = int(cur.lastrowid)
        got = self.get(claim_id)
        assert got is not None
        return got

    def get(self, claim_id: int) -> GestationClaim | None:
        with closing(self._connect()) as conn:
            row = conn.execute(
                "SELECT * FROM gestation_claims WHERE claim_id = ?", (int(claim_id),)
            ).fetchone()
        return None if row is None else _row_to_claim(row)
```

And add the row mapper at module scope:

```python
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
```

- [ ] **Step 4: Run to verify it passes**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_gestation_memory.RecordClaimTests -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add core/evolution/gestation_memory.py tests/test_gestation_memory.py
git commit -m "feat(gestation-memory): record_claim with strict sources + fact/interp quarantine

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 4: `list_active` + `supersede` (edge append, old row byte-identical)

**Files:** Modify `core/evolution/gestation_memory.py`; Test `tests/test_gestation_memory.py`

- [ ] **Step 1: Write the failing test**

Append a `SupersedeTests` class to `tests/test_gestation_memory.py` (reuse `_doc_source`):

```python
class SupersedeTests(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.gm = GestationMemory(Path(self._tmp.name) / "g.db")
        self.src, self.excerpt = _doc_source()

    def tearDown(self):
        self._tmp.cleanup()

    def _claim(self, text):
        return self.gm.record_claim(
            claim_text=text, claim_kind="fact", type="milestone", confidence="documented",
            sources=[self.src], source_excerpts={0: self.excerpt}, observed_by="claude",
        )

    def test_supersede_appends_edge_and_leaves_old_row_byte_identical(self):
        old = self._claim("We believed the bridge wrote the ledger.")
        before = self.gm.get(old.claim_id)
        new = self._claim("Corrected: the bridge writes no ledger.")
        self.gm.supersede(old.claim_id, new.claim_id)
        after = self.gm.get(old.claim_id)
        self.assertEqual(before, after)  # old row unchanged
        active_ids = {c.claim_id for c in self.gm.list_active()}
        self.assertNotIn(old.claim_id, active_ids)  # old superseded
        self.assertIn(new.claim_id, active_ids)     # new active

    def test_both_claims_persist_after_supersede(self):
        old = self._claim("old"); new = self._claim("new")
        self.gm.supersede(old.claim_id, new.claim_id)
        self.assertIsNotNone(self.gm.get(old.claim_id))
        self.assertIsNotNone(self.gm.get(new.claim_id))
```

- [ ] **Step 2: Run to verify it fails**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_gestation_memory.SupersedeTests -v`
Expected: FAIL — `AttributeError: ... 'supersede'`/`'list_active'`

- [ ] **Step 3: Write minimal implementation**

Append to the `GestationMemory` class:

```python
    def supersede(self, old_claim_id: int, replacement_claim_id: int) -> None:
        from datetime import datetime, timezone
        old = self.get(int(old_claim_id))
        new = self.get(int(replacement_claim_id))
        if old is None or new is None:
            raise KeyError("both claims must exist to supersede")
        if int(old_claim_id) == int(replacement_claim_id):
            raise ValueError("a claim cannot supersede itself")
        now = datetime.now(timezone.utc).timestamp()
        with closing(self._connect()) as conn:
            with conn:
                conn.execute(
                    "INSERT INTO gestation_claim_supersessions "
                    "(old_claim_id, replacement_claim_id, created_at) VALUES (?,?,?)",
                    (int(old_claim_id), int(replacement_claim_id), now),
                )

    def _superseded_ids(self, conn) -> set[int]:
        return {int(r[0]) for r in conn.execute(
            "SELECT old_claim_id FROM gestation_claim_supersessions")}

    def list_active(self) -> list[GestationClaim]:
        with closing(self._connect()) as conn:
            superseded = self._superseded_ids(conn)
            rows = conn.execute(
                "SELECT * FROM gestation_claims ORDER BY claim_id ASC").fetchall()
        return [_row_to_claim(r) for r in rows if int(r["claim_id"]) not in superseded]

    def list_all(self) -> list[GestationClaim]:
        with closing(self._connect()) as conn:
            rows = conn.execute(
                "SELECT * FROM gestation_claims ORDER BY claim_id ASC").fetchall()
        return [_row_to_claim(r) for r in rows]
```

- [ ] **Step 4: Run to verify it passes**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_gestation_memory.SupersedeTests -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add core/evolution/gestation_memory.py tests/test_gestation_memory.py
git commit -m "feat(gestation-memory): supersede via edge table (old row byte-identical) + list_active

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 5: Deterministic renderer (sections + interpretation quarantine + every line sourced)

**Files:** Modify `core/evolution/gestation_memory.py`; Test `tests/test_gestation_memory.py`

- [ ] **Step 1: Write the failing test**

Append a `RenderTests` class (reuse `_doc_source`):

```python
class RenderTests(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.gm = GestationMemory(Path(self._tmp.name) / "g.db")
        self.src, self.excerpt = _doc_source()

    def tearDown(self):
        self._tmp.cleanup()

    def _claim(self, text, kind, typ, conf, scar=False):
        return self.gm.record_claim(
            claim_text=text, claim_kind=kind, type=typ, confidence=conf,
            sources=[self.src], source_excerpts={0: self.excerpt}, observed_by="claude", scar=scar,
        )

    def test_facts_and_interpretations_in_separate_sections(self):
        self._claim("A fact happened.", "fact", "milestone", "documented")
        self._claim("A meaning we drew.", "interpretation", "milestone", "inferred")
        self._claim("It went wrong then was fixed.", "fact", "no_go", "documented", scar=True)
        out = self.gm.render()
        self.assertIn("What happened", out)
        self.assertIn("What went wrong", out)
        self.assertIn("Interpretations", out)
        # interpretation text must appear under Interpretations, after the fact sections
        self.assertLess(out.index("A fact happened."), out.index("Interpretations"))
        self.assertLess(out.index("Interpretations"), out.index("A meaning we drew."))
        # the scar appears in the corrections section
        self.assertLess(out.index("What went wrong"), out.index("It went wrong then was fixed."))

    def test_every_rendered_claim_carries_a_source(self):
        self._claim("A fact happened.", "fact", "milestone", "documented")
        out = self.gm.render()
        # the doc ref appears next to the claim
        self.assertIn("2026-06-10-gestation-memory-v0-design.md", out)
```

- [ ] **Step 2: Run to verify it fails**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_gestation_memory.RenderTests -v`
Expected: FAIL — `AttributeError: ... 'render'`

- [ ] **Step 3: Write minimal implementation**

Append to the `GestationMemory` class (pure string formatting — no LLM):

```python
    def render(self) -> str:
        claims = self.list_active()
        facts = [c for c in claims if c.claim_kind == "fact"]
        interps = [c for c in claims if c.claim_kind == "interpretation"]

        def _src_str(c: GestationClaim) -> str:
            parts = []
            for s in c.sources:
                if s.get("kind") == "doc":
                    parts.append(f"doc:{s.get('ref')}@{str(s.get('commit',''))[:8]}")
                elif s.get("kind") == "commit":
                    parts.append(f"commit:{str(s.get('ref',''))[:8]}")
                elif s.get("kind") == "ledger_row":
                    parts.append(f"ledger:event_id={s.get('ref')}")
                else:
                    parts.append("note")
            return ", ".join(parts)

        def _line(c: GestationClaim) -> str:
            tag = " [SCAR]" if c.scar else ""
            return f"  - {c.claim_text}{tag}  [{c.confidence}] (sources: {_src_str(c)})"

        lines: list[str] = ["# Gestation record (sourced; deterministic render)\n"]
        happened = [c for c in facts if c.type in ("milestone",) or not c.scar]
        changed = [c for c in claims if c.type in ("milestone", "decision") and c.claim_kind == "fact"]
        wrong = [c for c in claims if c.scar or c.type in ("correction", "no_go")]

        lines.append("## What happened")
        for c in [c for c in facts if not c.scar]:
            lines.append(_line(c))
        lines.append("\n## What changed")
        for c in changed:
            lines.append(_line(c))
        lines.append("\n## What went wrong / what was corrected")
        for c in wrong:
            lines.append(_line(c))
        lines.append("\n## Interpretations (meanings drawn from the evidence — not raw fact)")
        for c in interps:
            lines.append(_line(c))
        return "\n".join(lines) + "\n"
```

- [ ] **Step 4: Run to verify it passes**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_gestation_memory.RenderTests -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add core/evolution/gestation_memory.py tests/test_gestation_memory.py
git commit -m "feat(gestation-memory): deterministic renderer (sections + interpretation quarantine + sourced)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 6: CLI (`record` + `render`)

**Files:** Modify `core/evolution/gestation_memory.py`; Test `tests/test_gestation_memory.py`

- [ ] **Step 1: Write the failing test**

Append a `CliTests` class:

```python
class CliTests(unittest.TestCase):
    def test_render_subcommand_runs_on_empty_db(self):
        from core.evolution import gestation_memory as g
        with TemporaryDirectory() as td:
            rc = g.main(["render", "--db", str(Path(td) / "g.db")])
            self.assertEqual(rc, 0)
```

- [ ] **Step 2: Run to verify it fails**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_gestation_memory.CliTests -v`
Expected: FAIL — `AttributeError: ... 'main'`

- [ ] **Step 3: Write minimal implementation**

Append the CLI at module scope (mirror `novelty_harbor.py`'s argparse `main`). `record` accepts `--source-doc PATH COMMIT EXCERPT_FILE` (repeatable) and `--source-commit HASH`; `render` prints the binder:

```python
import argparse


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m core.evolution.gestation_memory")
    sub = p.add_subparsers(dest="command", required=True)
    rec = sub.add_parser("record")
    rec.add_argument("--db", default=str(DEFAULT_DB_PATH))
    rec.add_argument("--claim", required=True)
    rec.add_argument("--kind", required=True, choices=sorted(CLAIM_KINDS))
    rec.add_argument("--type", required=True, choices=sorted(TYPES))
    rec.add_argument("--confidence", required=True, choices=sorted(CONFIDENCES))
    rec.add_argument("--observed-by", required=True, choices=sorted(OBSERVED_BY))
    rec.add_argument("--scar", action="store_true")
    rec.add_argument("--source-commit", action="append", default=[])
    # doc source: "PATH::COMMIT::EXCERPT"  (excerpt read literally)
    rec.add_argument("--source-doc", action="append", default=[])
    ren = sub.add_parser("render")
    ren.add_argument("--db", default=str(DEFAULT_DB_PATH))
    return p


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.command == "render":
        print(GestationMemory(args.db).render())
        return 0
    if args.command == "record":
        sources: list[dict] = []
        excerpts: dict[int, str] = {}
        for h in args.source_commit:
            sources.append({"kind": "commit", "ref": h})
        for spec in args.source_doc:
            path, commit, excerpt = spec.split("::", 2)
            i = len(sources)
            sources.append({"kind": "doc", "ref": path, "commit": commit,
                            "excerpt_hash": _sha256(excerpt)})
            excerpts[i] = excerpt
        claim = GestationMemory(args.db).record_claim(
            claim_text=args.claim, claim_kind=args.kind, type=args.type,
            confidence=args.confidence, sources=sources, source_excerpts=excerpts,
            observed_by=args.observed_by, scar=args.scar,
        )
        print(f"claim_id={claim.claim_id} kind={claim.claim_kind} confidence={claim.confidence}")
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run to verify it passes**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_gestation_memory.CliTests -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add core/evolution/gestation_memory.py tests/test_gestation_memory.py
git commit -m "feat(gestation-memory): CLI record + render

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 7: Boundary test + floor + handoff + STOP

**Files:** Create `tests/test_gestation_memory_boundary.py`; Create `docs/handoffs/2026-06-10-gestation-memory-v0-for-review.md`

- [ ] **Step 1: Boundary test (AST)**

Create `tests/test_gestation_memory_boundary.py`:

```python
import ast
import unittest
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1] / "core" / "evolution" / "gestation_memory.py"
FORBIDDEN = {
    "llm_client", "focused_cognition", "daemon", "maez_daemon", "telegram", "voice", "speak",
    "wants", "valence_live", "soul_editor", "soul_loader", "memory_manager",
}


def _imports(tree):
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                yield a.name
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            yield module
            for a in node.names:
                yield f"{module}.{a.name}" if module else a.name


class BoundaryTests(unittest.TestCase):
    def test_no_llm_daemon_or_writer_imports(self):
        tree = ast.parse(MODULE.read_text(encoding="utf-8"))
        offenders = []
        for name in _imports(tree):
            blocked = sorted(set(name.split(".")) & FORBIDDEN)
            if blocked:
                offenders.append((name, blocked))
        self.assertEqual(offenders, [])

    def test_no_ledger_writer_import(self):
        # reads identity_ledger.db directly read-only; never imports the writer class,
        # and never imports the birth-gated per-turn ledger writer.
        src = MODULE.read_text(encoding="utf-8")
        self.assertNotIn("from core.memory.identity_ledger", src)
        self.assertNotIn("from core.ledger", src)
        self.assertNotIn("record_event", src)
```

- [ ] **Step 2: Run it**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_gestation_memory_boundary -v`
Expected: PASS — the module imports only stdlib (no llm/daemon/writer; reads `identity_ledger.db` via raw read-only sqlite, not the writer class).

- [ ] **Step 3: Full focused floor + ruff + diff hygiene**

Run:
```bash
/home/rohit/maez/.venv/bin/python -B -m unittest \
  tests.test_gestation_memory tests.test_gestation_memory_sources tests.test_gestation_memory_boundary -v
cd /home/rohit/maez && .venv/bin/ruff check core/evolution/gestation_memory.py tests/test_gestation_memory*.py
git -C /home/rohit/.config/superpowers/worktrees/maez/gestation-memory-v0 diff --check ae9488b..HEAD
```
Expected: all PASS / `All checks passed!` / clean.

- [ ] **Step 4: Handoff doc + STOP**

Create `docs/handoffs/2026-06-10-gestation-memory-v0-for-review.md` documenting the build + the **review anchors** (below) + verification outputs + the owner-breath: merge (local ff, no push) → **manual witness** (offline organ, no restart): record real claims sourced to committed docs, render the binder, confirm the rails bite. Mark: no merge, no witness.

**Review anchors (acceptance contract):**
1. `gestation_claims` + `gestation_claim_supersessions` are append-only — `RAISE(ABORT)` triggers on UPDATE/DELETE; a supersede leaves the old row byte-identical.
2. Every claim has ≥1 resolvable structural source; `witness_note` alone is rejected; a doc source is git-fingerprint-validated (excerpt present at commit + hash match); ledger_row uses the byte-exact canonical hash.
3. Fact/interpretation quarantine: `fact` + `inferred` rejected; interpretations may be inferred.
4. Renderer is deterministic (no LLM import), facts and interpretations in separate sections, every rendered claim carries its source.
5. Boundary: no llm/daemon/ledger-writer/wants-writer imports; reads `identity_ledger.db` read-only; writes no ledger anywhere.
6. Offline/manual: no daemon wiring, no `## Predicted effect`.

- [ ] **Step 5: Commit + STOP**

```bash
git add docs/handoffs/2026-06-10-gestation-memory-v0-for-review.md
git commit -m "docs(gestation-memory): v0 review handoff + STOP before merge

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

**STOP. No merge, no witness.** Report branch tip + verification outputs; Claude reviews against the six anchors.

---

## Self-Review (against the spec)

- True append-only (triggers + edge table, old row byte-identical): Tasks 1, 4. ✓
- Strict sources (≥1 resolvable structural; doc git-fingerprint; commit; ledger canonical hash; witness_note context-only): Tasks 2, 3. ✓
- Fact/interpretation quarantine (no inferred facts): Task 3. ✓
- ledger_row canonical hash byte-exact (the 9 columns, parse JSON, sorted keys, compact separators): Task 2 `canonical_ledger_row_hash` + its test. ✓
- Deterministic renderer (sections + interpretation tab + every line sourced, no LLM): Task 5. ✓
- Manual maker-tagged + content-light: Task 3 (`observed_by` validated, length caps). ✓
- Boundary (no writer/llm/daemon; read-only ledger): Task 7. ✓
- Offline/manual, no `## Predicted effect`: confirmed throughout. ✓
- Witness cites committed docs only: the tests + CLI use committed doc sources; the handoff witness uses committed docs. ✓

Placeholder scan: none. Signature consistency: `record_claim(*, claim_text, claim_kind, type, confidence, sources, observed_by, source_excerpts, scar, metadata)`, `validate_source(src, *, repo_root, excerpt, ledger_db)`, `canonical_ledger_row_hash(row)`, `is_structural(src)`, `supersede(old, new)`, `list_active()`, `render()`, `main(argv)` — consistent across tasks.
