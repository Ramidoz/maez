# Backup Restore Smoke Test v1.1 — Implementation Plan

> **For agentic workers:** **Codex's build lane** (Claude drafts plan + covenant-reviews; Codex builds; owner witnesses). Strict TDD, checkbox steps. **Do NOT merge, restart, or flip flags.** **HARD RAILS: temp-only, read-only, no writes to `memory/`, no daemon restart, no restore into live paths, no compare-to-live.**

**Goal:** A manifest-derived, artifact-self-consistent restore smoke test: for the **latest finalized backup**, verify every `required_welfare`/`required_continuity` store is present, sha256-matches its recorded hash, and (for SQLite) restores into a temp dir + opens read-only + passes `PRAGMA quick_check` + emits row counts — into `logs/backup_drill_<timestamp>.json`. Proves the saved notebook can be unpacked and read; **never** compares to live `memory/`.

**Architecture:** New functions in `scripts/backup/drill.py` (reusing its `_sha256`, `sqlite_row_count`) + a CLI. No changes to the daemon, the backup, or the existing compare-to-live drill path.

**Tech Stack:** Python 3, stdlib (`sqlite3`, `shutil`, `hashlib`, `json`, `tempfile`). Test runner is **unittest, NOT pytest**:
`MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -m unittest tests.<module>`

**Covenant rails:** artifact truth not live truth; manifest-derived (one source of truth); temp-only/read-only; type-aware; witnessed via a report artifact.

---

### Task 0: Confirm helpers + structures (no production code)

- [ ] **Step 1: Confirm reusable helpers + the backup manifest shape**

Run:
```
MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -c "
import inspect, scripts.backup.drill as d
print('_sha256:', '_sha256' in dir(d), '| sqlite_row_count:', 'sqlite_row_count' in dir(d))
print(inspect.getsource(d.sqlite_row_count))"
/home/rohit/maez/.venv/bin/python -c "import json; m=json.load(open('/home/rohit/maez-backups/2026-06-26T03-59-05/manifest.json')); f=m['files'][0]; print('file entry keys:', list(f.keys()))"
```
Confirm: `_sha256(path)->str`, `sqlite_row_count(db, table)->int|None`; the per-backup `manifest.json` `files[]` carry `path` + `sha256` (+ `size`/`source_type`). Confirm the state-manifest entries carry `type`/`path`/`class` (from the coverage slice). Record the latest finalized backup root (`~/maez-backups`).

---

### Task 1: Manifest-derived per-entry verifier (artifact-self-consistent)

**Files:**
- Modify: `scripts/backup/drill.py` (add `required_store_entries`, `verify_backup_entry`)
- Test: `tests/test_restore_smoke.py` (new)

- [ ] **Step 1: Write the failing tests**

```python
import json, sqlite3, hashlib, unittest, tempfile, pathlib
from scripts.backup.drill import required_store_entries, verify_backup_entry

def _mkdb(path, table, rows):
    con = sqlite3.connect(str(path)); con.execute(f"CREATE TABLE {table}(id INTEGER)")
    con.executemany(f"INSERT INTO {table} VALUES (?)", [(i,) for i in range(rows)]); con.commit(); con.close()

def _sha(p): return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()

class RestoreSmokeTest(unittest.TestCase):
    def _backup(self):
        """A synthetic finalized backup dir with one sqlite store + its manifest."""
        root = pathlib.Path(tempfile.mkdtemp())
        (root / "memory").mkdir()
        db = root / "memory" / "salience_ledger.db"; _mkdb(db, "salience_ledger", 7)
        (root / "manifest.json").write_text(json.dumps(
            {"timestamp": "2026-06-26T03-59-05",
             "files": [{"path": "memory/salience_ledger.db", "sha256": _sha(db), "source_type": "sqlite_db"}]}))
        return root

    def test_selects_required_welfare_and_continuity(self):
        sm = {"entries": [
            {"type": "sqlite_db", "path": "memory/salience_ledger.db", "class": "required_welfare"},
            {"type": "sqlite_db", "path": "memory/site_analytics.db", "class": "optional_observability"}]}
        paths = {e["path"] for e in required_store_entries(sm)}
        self.assertEqual(paths, {"memory/salience_ledger.db"})   # optional excluded

    def test_sqlite_entry_present_hash_and_quickcheck(self):
        b = self._backup()
        man = json.loads((b / "manifest.json").read_text())
        files_by_path = {f["path"]: f for f in man["files"]}
        rec = verify_backup_entry(
            {"type": "sqlite_db", "path": "memory/salience_ledger.db", "class": "required_welfare"},
            backup_dir=b, files_by_path=files_by_path, tmp_root=pathlib.Path(tempfile.mkdtemp()))
        self.assertEqual(rec["status"], "pass")
        self.assertEqual(rec["quick_check"], "ok")
        self.assertEqual(rec["row_counts"]["salience_ledger"], 7)

    def test_missing_required_store_fails(self):
        b = self._backup()
        rec = verify_backup_entry(
            {"type": "sqlite_db", "path": "memory/subjective_duration.db", "class": "required_welfare"},
            backup_dir=b, files_by_path={}, tmp_root=pathlib.Path(tempfile.mkdtemp()))
        self.assertEqual(rec["status"], "fail")

    def test_sha256_mismatch_fails(self):
        b = self._backup()
        man = json.loads((b / "manifest.json").read_text())
        fbp = {f["path"]: dict(f, sha256="deadbeef") for f in man["files"]}   # corrupt recorded hash
        rec = verify_backup_entry(
            {"type": "sqlite_db", "path": "memory/salience_ledger.db", "class": "required_welfare"},
            backup_dir=b, files_by_path=fbp, tmp_root=pathlib.Path(tempfile.mkdtemp()))
        self.assertEqual(rec["status"], "fail")
        self.assertIn("sha256", rec["detail"].lower())
```

- [ ] **Step 2: Run to verify they fail** — `... -m unittest tests.test_restore_smoke -v` → FAIL.

- [ ] **Step 3: Implement**

```python
import shutil, sqlite3
from pathlib import Path

_REQUIRED_CLASSES = ("required_welfare", "required_continuity")


def required_store_entries(state_manifest: dict) -> list[dict]:
    return [e for e in (state_manifest.get("entries") or [])
            if e.get("class") in _REQUIRED_CLASSES]


def verify_backup_entry(entry: dict, *, backup_dir: Path, files_by_path: dict, tmp_root: Path) -> dict:
    """Artifact-self-consistent check of one required entry in a finalized backup.
    Never touches live memory/; copies into tmp_root (read-only opens only)."""
    path = entry["path"]
    etype = entry.get("type")
    base = {"path": path, "type": etype, "class": entry.get("class")}

    def _check_file(rel: str) -> "str | None":
        rec = files_by_path.get(rel)
        if rec is None:
            return f"{rel} not present in backup manifest"
        src = backup_dir / rel
        if not src.is_file():
            return f"{rel} missing in backup dir"
        if _sha256(src) != rec.get("sha256"):
            return f"{rel} sha256 mismatch"
        return None

    if etype in ("sqlite_db", "file", "secret_file"):
        err = _check_file(path)
        if err:
            return {**base, "status": "fail", "detail": err}
        if etype != "sqlite_db":
            return {**base, "status": "pass", "detail": "present + hash ok"}
        tmp = tmp_root / Path(path).name
        shutil.copy2(backup_dir / path, tmp)
        con = sqlite3.connect(f"file:{tmp}?mode=ro", uri=True)
        try:
            qc = con.execute("PRAGMA quick_check").fetchone()[0]
            tables = [r[0] for r in con.execute(
                "SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
            row_counts = {t: con.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0] for t in tables}
        finally:
            con.close()
        return {**base, "status": "pass" if qc == "ok" else "fail",
                "quick_check": qc, "row_counts": row_counts}

    if etype == "directory":
        children = [p for p in files_by_path if p == path or p.startswith(path.rstrip("/") + "/")]
        if not children:
            return {**base, "status": "fail", "detail": "no children backed up under directory"}
        for rel in children:
            err = _check_file(rel)
            if err:
                return {**base, "status": "fail", "detail": err}
        return {**base, "status": "pass", "detail": f"{len(children)} child files present + hash ok"}

    return {**base, "status": "skip", "detail": f"unhandled type {etype}"}
```

- [ ] **Step 4: Run to verify they pass** — same → PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/backup/drill.py tests/test_restore_smoke.py
git commit -m "feat(backup): manifest-derived artifact verifier for required stores"
```

---

### Task 2: Latest-finalized finder + report + CLI

**Files:**
- Modify: `scripts/backup/drill.py` (add `run_restore_smoke_test`, `_latest_finalized_backup`, CLI hook in `__main__`)
- Test: `tests/test_restore_smoke.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_smoke_run_writes_report_and_passes_clean_backup(self):
    import tempfile, pathlib, json
    from scripts.backup.drill import run_restore_smoke_test
    # synthetic backup_root with one finalized backup + an .in-progress that must be ignored
    root = pathlib.Path(tempfile.mkdtemp())
    good = self._backup(); (good).rename(root / "2026-06-26T03-59-05")
    (root / ".in-progress").mkdir(); (root / ".in-progress" / "2026-06-26T04-10-00").mkdir()
    sm = {"entries": [{"type": "sqlite_db", "path": "memory/salience_ledger.db", "class": "required_welfare"}]}
    log_dir = pathlib.Path(tempfile.mkdtemp())
    report = run_restore_smoke_test(backup_root=root, state_manifest=sm, log_dir=log_dir)
    self.assertEqual(report["verdict"], "pass")
    self.assertEqual(report["backup"], "2026-06-26T03-59-05")   # finalized, not in-progress
    self.assertTrue(list(log_dir.glob("backup_drill_*.json")))   # report artifact written

def test_smoke_run_unavailable_when_no_finalized_backup(self):
    import tempfile, pathlib
    from scripts.backup.drill import run_restore_smoke_test
    root = pathlib.Path(tempfile.mkdtemp()); (root / ".in-progress").mkdir()
    report = run_restore_smoke_test(backup_root=root, state_manifest={"entries": []},
                                    log_dir=pathlib.Path(tempfile.mkdtemp()))
    self.assertEqual(report["verdict"], "unavailable")
```

- [ ] **Step 2: Run to verify they fail** — FAIL.

- [ ] **Step 3: Implement**

```python
def _latest_finalized_backup(backup_root: Path) -> "Path | None":
    root = Path(backup_root)
    if not root.is_dir():
        return None
    finals = [d for d in root.iterdir()
              if d.is_dir() and d.name != ".in-progress" and (d / "manifest.json").is_file()]
    return max(finals, key=lambda d: d.name) if finals else None


def run_restore_smoke_test(*, backup_root, state_manifest, log_dir, timestamp=None) -> dict:
    import json, tempfile
    backup = _latest_finalized_backup(Path(backup_root))
    if backup is None:
        report = {"verdict": "unavailable", "detail": "no finalized backup", "checks": []}
    else:
        man = json.loads((backup / "manifest.json").read_text())
        files_by_path = {f["path"]: f for f in (man.get("files") or [])}
        tmp_root = Path(tempfile.mkdtemp(prefix="maez-restore-smoke-"))
        try:
            checks = [verify_backup_entry(e, backup_dir=backup, files_by_path=files_by_path, tmp_root=tmp_root)
                      for e in required_store_entries(state_manifest)]
        finally:
            shutil.rmtree(tmp_root, ignore_errors=True)   # temp-only, cleaned up
        verdict = "pass" if checks and all(c["status"] != "fail" for c in checks) else \
                  ("fail" if any(c["status"] == "fail" for c in checks) else "skip")
        report = {"verdict": verdict, "backup": backup.name, "checks": checks,
                  "required_count": len(checks)}
    Path(log_dir).mkdir(parents=True, exist_ok=True)
    name = f"backup_drill_{timestamp or report.get('backup', 'none')}.json"
    (Path(log_dir) / name).write_text(json.dumps(report, indent=2, sort_keys=True))
    return report
```
Wire a CLI in `__main__` (or `scripts/backup/__main__.py`): `python -m scripts.backup.drill --smoke` loads the real manifest (`scripts.backup.inventory.load_default_manifest`), runs against `~/maez-backups` (or `$MAEZ_BACKUP_ROOT`), writes to `logs/`, prints the verdict, exits non-zero on `fail`.

- [ ] **Step 4: Run to verify they pass** — same → PASS.

- [ ] **Step 5: Full suite + ruff**

```bash
MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -m unittest tests.test_restore_smoke -v
/home/rohit/maez/.venv/bin/ruff check scripts/backup/drill.py tests/test_restore_smoke.py
```
Expected: green; ruff clean.

- [ ] **Step 6: Commit**

```bash
git add scripts/backup/drill.py tests/test_restore_smoke.py
git commit -m "feat(backup): on-demand restore smoke test — latest finalized, temp-only, report artifact"
```

---

### Task 3: Handoff + witnessed run + STOP

- [ ] **Step 1: Write `docs/handoffs/2026-06-25-backup-restore-smoke-test-v1.1-handoff.md`**

Record branch tip + test/ruff output, and the **owner-run witness** (read-only, temp-only):
```
MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -m scripts.backup.drill --smoke
# expect: verdict=pass; report logs/backup_drill_<ts>.json shows
#   memory/salience_ledger.db: status=pass, quick_check=ok, row_counts{...}
#   memory/subjective_duration.db: status=pass, quick_check=ok, row_counts{...}
#   (+ every other required_welfare/required_continuity store)
# confirm: no writes under memory/, no daemon restart, temp dir cleaned up
```
Name **scheduling the drill on a timer** as a future step. State plainly: NOT merged, NOT restarted, NO flags; temp-only/read-only throughout.

- [ ] **Step 2: Commit + STOP**

```bash
git add docs/handoffs/2026-06-25-backup-restore-smoke-test-v1.1-handoff.md
git commit -m "docs(backup): hand off restore smoke test v1.1"
```
Hand back to Claude for covenant review (manifest-derived, no second list; artifact-self-consistent — no compare-to-live; latest finalized only, `.in-progress` ignored; sha256 + quick_check + row-counts; temp-only/read-only; report artifact). Then the owner runs the witness — the report proving the notebook unpacks and reads is the raft-floating proof.

---

## Self-Review

**Spec coverage:** manifest-derived selection of `required_welfare`+`required_continuity` (`required_store_entries` + `test_selects_required_welfare_and_continuity` ✓); artifact-self-consistent, no compare-to-live (verifier reads backup vs its own manifest only ✓); latest finalized only, `.in-progress` ignored (`_latest_finalized_backup` + `test_smoke_run_writes_report...` ✓); present + sha256 + quick_check + row-counts (`test_sqlite_entry_...`, `test_sha256_mismatch_fails` ✓); type-aware file/dir/sqlite (verifier branches ✓); temp-only/read-only/cleanup (`tempfile` + `shutil.rmtree` ✓); report artifact (`test_smoke_run_writes_report...` ✓); reuse `_sha256`/`sqlite_row_count` (Task 0 ✓).

**Placeholder scan:** the CLI manifest loader (`load_default_manifest`) + backup root (`~/maez-backups`/`$MAEZ_BACKUP_ROOT`) are the same confirmed seams as the coverage slice — no TBDs.

**Type consistency:** `required_store_entries(state_manifest) -> list[dict]`, `verify_backup_entry(entry, *, backup_dir, files_by_path, tmp_root) -> dict`, `run_restore_smoke_test(*, backup_root, state_manifest, log_dir, timestamp=None) -> dict` — consistent across defs, tests, and the CLI. `class` values match the coverage-slice manifest.
