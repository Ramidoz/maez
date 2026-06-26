# Backup Coverage + Freshness Truth v0 — Implementation Plan

> **For agentic workers:** **Codex's build lane** (Claude drafts plan + covenant-reviews; Codex builds; owner witnesses). Strict TDD, checkbox steps. **Do NOT merge, restart, or flip flags.** **ORDER IS A COVENANT: coverage (Task 1) before signal (Tasks 2–3) — wiring `fresh` before the notebook is backed up is the fake green we're fixing.**

**Goal:** Make the June nervous-system stores (incl. `salience_ledger.db`, `subjective_duration.db`) part of the backup, then make the daemon report backup freshness **truthfully** — `fresh` only when the latest finalized backup is both **recent (<13h)** and **covers the welfare-critical stores**, else `coverage_gap` / `stale` / `unavailable`.

**Core invariant (a test must enforce it):** no path returns `fresh` if a `required_welfare`/`required_continuity` store is missing from the latest backup.

**Tech Stack:** Python 3, stdlib. Test runner is **unittest, NOT pytest**:
`MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -m unittest tests.<module>`

**Covenant rails:** coverage before signal; `fresh` ⇒ recent AND complete; read-only freshness reader, fail-soft to `unavailable` (never false-green); skips carry written reasons; no schedule/encryption changes.

---

### Task 0: Classify the 18 stores + confirm seams (no production code)

- [ ] **Step 1: Classify every unprotected `memory/` store**

Run:
```
cd /home/rohit/maez
for db in memory/*.db memory/*.json memory/*.jsonl; do n=$(basename "$db"); grep -q "$n" scripts/backup/backup_state_manifest.json 2>/dev/null || echo "UNPROTECTED: $n"; done
```
Record a class for each (`required_welfare` / `required_continuity` / `optional_observability` / `ephemeral_skip` + reason). **Mandatory `required_welfare`:** `salience_ledger.db`, `subjective_duration.db`, `routing_observation.db`, `veto_ledger.db` (and confirm `private_thoughts.db` stays protected). The dated `sandbox_ledger_2026_05_07/08.db` + transient `*_cooldown`/`*_queue` are candidate `ephemeral_skip` — name the reason.

- [ ] **Step 2: Confirm the seams**

Run:
```
MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -c "
import inspect, core.governance.operator_user_boundary as o
print(inspect.getsource(o.validate_operator_freshness_class))
print('--- closed set ---'); import re; print([l for l in inspect.getsource(o).splitlines() if 'fresh' in l.lower() and ('=' in l or '(' in l)][:8])"
grep -nE 'BACKUP_ROOT|maez-backups|backup_root' scripts/backup/*.py ~/.config/systemd/user/maez-backup.service 2>/dev/null | head
```
Record: the freshness **closed set** (need to add `coverage_gap`?), and where `$BACKUP_ROOT` is configured (the reader must use the same root; default `/home/rohit/maez-backups`). Confirm per-backup `manifest.json` `files[].path` are repo-relative (e.g. `memory/salience_ledger.db`).

---

### Task 1: Manifest coverage — add the missing required stores (COVERAGE FIRST)

**Files:**
- Modify: `scripts/backup/backup_state_manifest.json`
- Test: `tests/test_backup_manifest_coverage.py` (new)

- [ ] **Step 1: Write the failing test**

```python
import json, unittest, pathlib

class ManifestCoverageTest(unittest.TestCase):
    def _manifest(self):
        return json.loads(pathlib.Path("scripts/backup/backup_state_manifest.json").read_text())

    def test_welfare_stores_are_required_welfare(self):
        m = self._manifest()
        by_path = {e["path"]: e for e in m["entries"]}
        for p in ("memory/salience_ledger.db", "memory/subjective_duration.db",
                  "memory/routing_observation.db", "memory/veto_ledger.db"):
            self.assertIn(p, by_path, f"{p} not in manifest")
            self.assertEqual(by_path[p].get("class"), "required_welfare", f"{p} not required_welfare")

    def test_private_thoughts_stays_protected(self):
        m = self._manifest()
        by_path = {e["path"]: e for e in m["entries"]}
        self.assertIn("memory/private_thoughts.db", by_path)

    def test_skips_have_written_reasons(self):
        m = self._manifest()
        for s in m.get("intentionally_skipped", []):
            self.assertTrue(s.get("path") and s.get("reason"), f"skip missing reason: {s}")

    def test_every_entry_has_a_class(self):
        m = self._manifest()
        valid = {"required_continuity", "required_welfare", "optional_observability"}
        for e in m["entries"]:
            self.assertIn(e.get("class"), valid, f"entry missing/invalid class: {e['path']}")

    def test_backup_script_still_loads_manifest(self):
        # the new 'class' field + intentionally_skipped must not break backup.py's loader
        from scripts.backup.backup import load_default_manifest  # adjust import per Task 0
        m = load_default_manifest()
        self.assertTrue(m.get("entries"))
```

- [ ] **Step 2: Run to verify it fails** — `... -m unittest tests.test_backup_manifest_coverage -v` → FAIL.

- [ ] **Step 3: Extend the manifest**

Add a `class` to **every** existing entry (per Task 0 classification — existing `required:true` ones are `required_continuity` unless they're welfare stores). Add the missing `required_welfare` entries:
```json
{"type": "sqlite_db", "path": "memory/salience_ledger.db", "required": true, "class": "required_welfare",
 "comment": "Slice C salience notebook — the canary precondition store; must survive a fall"},
{"type": "sqlite_db", "path": "memory/subjective_duration.db", "required": true, "class": "required_welfare",
 "comment": "Slice A time-sense / rhythm facts"},
{"type": "sqlite_db", "path": "memory/routing_observation.db", "required": true, "class": "required_welfare"},
{"type": "sqlite_db", "path": "memory/veto_ledger.db", "required": true, "class": "required_welfare"},
```
Add the documented skips:
```json
"intentionally_skipped": [
  {"path": "memory/sandbox_ledger_2026_05_07.db", "reason": "dated sandbox scratch; not continuity state"},
  {"path": "memory/sandbox_ledger_2026_05_08.db", "reason": "dated sandbox scratch; not continuity state"}
]
```
(Classify the remaining unprotected stores per Task 0 — `optional_observability` for observability dbs, `required_continuity` for any continuity-load-bearing ones found.)

- [ ] **Step 4: Run to verify it passes** — same → PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/backup/backup_state_manifest.json tests/test_backup_manifest_coverage.py
git commit -m "fix(backup): cover the June nervous-system stores (salience/time-sense) as required_welfare"
```

---

### Task 2: `backup_freshness()` reader — recent AND complete

**Files:**
- Create: `core/health/backup_freshness.py`
- Test: `tests/test_backup_freshness.py` (new)

- [ ] **Step 1: Write the failing tests**

```python
import json, unittest, tempfile, pathlib
from datetime import datetime, timezone, timedelta
from core.health.backup_freshness import backup_freshness, FRESH_MAX_AGE_H

def _mkbackup(root, name, files, *, in_progress=False):
    d = (pathlib.Path(root) / (".in-progress" if in_progress else "") / name)
    d.mkdir(parents=True, exist_ok=True)
    (d / "manifest.json").write_text(json.dumps(
        {"timestamp": name.replace("T", "T"), "files": [{"path": p} for p in files]}))
    return d

_REQ = {"memory/salience_ledger.db", "memory/subjective_duration.db"}
def _now(): return datetime(2026, 6, 26, 2, 0, 0, tzinfo=timezone.utc)

class BackupFreshnessTest(unittest.TestCase):
    def _root(self): return tempfile.mkdtemp()

    def test_fresh_when_recent_and_complete(self):
        r = self._root()
        _mkbackup(r, "2026-06-26T01-17-03", ["memory/salience_ledger.db", "memory/subjective_duration.db"])
        self.assertEqual(backup_freshness(backup_root=r, required_paths=_REQ, now=_now()), "fresh")

    def test_coverage_gap_when_recent_but_missing_store(self):
        r = self._root()
        _mkbackup(r, "2026-06-26T01-17-03", ["memory/salience_ledger.db"])  # missing subjective_duration
        self.assertEqual(backup_freshness(backup_root=r, required_paths=_REQ, now=_now()), "coverage_gap")

    def test_stale_when_old(self):
        r = self._root()
        _mkbackup(r, "2026-06-25T00-00-00", ["memory/salience_ledger.db", "memory/subjective_duration.db"])
        self.assertEqual(backup_freshness(backup_root=r, required_paths=_REQ, now=_now()), "stale")

    def test_unavailable_when_no_finalized_backup(self):
        r = self._root()
        _mkbackup(r, "2026-06-26T01-50-00", ["memory/salience_ledger.db"], in_progress=True)  # only in-progress
        self.assertEqual(backup_freshness(backup_root=r, required_paths=_REQ, now=_now()), "unavailable")

    def test_inprogress_is_never_counted(self):
        r = self._root()
        _mkbackup(r, "2026-06-26T01-17-03", ["memory/salience_ledger.db", "memory/subjective_duration.db"])
        _mkbackup(r, "2026-06-26T01-55-00", ["memory/salience_ledger.db"], in_progress=True)  # newer but in-progress
        self.assertEqual(backup_freshness(backup_root=r, required_paths=_REQ, now=_now()), "fresh")  # uses finalized one
```

- [ ] **Step 2: Run to verify it fails** — `... -m unittest tests.test_backup_freshness -v` → FAIL.

- [ ] **Step 3: Implement (read-only)**

```python
"""Read-only backup freshness — recent AND complete. Fail-soft to 'unavailable';
never reports a false 'fresh'."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

FRESH_MAX_AGE_H = 13  # one missed 6-hour cycle + margin
_TS_FMT = "%Y-%m-%dT%H-%M-%S"


def _parse_ts(name: str) -> "datetime | None":
    try:
        return datetime.strptime(name[:19], _TS_FMT).replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None


def backup_freshness(*, backup_root, required_paths, now=None) -> str:
    now = now or datetime.now(timezone.utc)
    root = Path(backup_root)
    if not root.is_dir():
        return "unavailable"
    finals = [d for d in root.iterdir()
              if d.is_dir() and d.name != ".in-progress" and (d / "manifest.json").is_file()]
    if not finals:
        return "unavailable"
    latest = max(finals, key=lambda d: d.name)   # UTC ISO names sort chronologically
    try:
        man = json.loads((latest / "manifest.json").read_text())
    except Exception:
        return "unavailable"
    ts = _parse_ts(str(man.get("timestamp") or latest.name))
    if ts is None:
        return "unavailable"
    age_h = (now - ts).total_seconds() / 3600.0
    if age_h >= FRESH_MAX_AGE_H:
        return "stale"
    backed = {f.get("path") for f in (man.get("files") or [])}
    if set(required_paths) - backed:        # any required store missing
        return "coverage_gap"
    return "fresh"
```

- [ ] **Step 4: Run to verify it passes** — same → PASS.

- [ ] **Step 5: Commit**

```bash
git add core/health/backup_freshness.py tests/test_backup_freshness.py
git commit -m "feat(backup): freshness reader requires recent AND complete (no fake green)"
```

---

### Task 3: Extend the freshness closed-set + wire the daemon

**Files:**
- Modify: `core/governance/operator_user_boundary.py` (add `coverage_gap` to the closed set, if Task 0 showed it absent)
- Modify: `daemon/maez_daemon.py` (replace the hardcoded `backup_freshness_class="unavailable"`)
- Test: `tests/test_lean_idle_daemon.py` (or a daemon health test)

- [ ] **Step 1: Write the failing test**

```python
def test_operator_health_reads_real_backup_freshness(self):
    from daemon.maez_daemon import MaezDaemon
    from unittest import mock
    daemon = object.__new__(MaezDaemon)
    with mock.patch("core.health.backup_freshness.backup_freshness", return_value="fresh"):
        health = daemon._operator_health()
    self.assertEqual(health["backup_freshness_class"], "fresh")   # not the hardcoded 'unavailable'
```
And, if the closed set needed extending:
```python
def test_coverage_gap_is_a_valid_freshness_class(self):
    from core.governance.operator_user_boundary import validate_operator_freshness_class
    self.assertEqual(validate_operator_freshness_class("coverage_gap"), "coverage_gap")
```

- [ ] **Step 2: Run to verify it fails** — FAIL (hardcoded `unavailable` / `coverage_gap` rejected).

- [ ] **Step 3: Implement**

Add `coverage_gap` to the freshness closed set (alongside `fresh`/`stale`/`unavailable`). In `_operator_health`, replace the literal:
```python
            backup_freshness_class=self._backup_freshness_class(),
```
with a fail-soft helper that loads the required paths from the backup-state-manifest and calls the reader:
```python
def _backup_freshness_class(self) -> str:
    try:
        from core.health.backup_freshness import backup_freshness
        from scripts.backup.backup import load_default_manifest  # per Task 0
        manifest = load_default_manifest()
        required = {e["path"] for e in manifest.get("entries", [])
                    if e.get("class") in ("required_welfare", "required_continuity")}
        return backup_freshness(backup_root=<BACKUP_ROOT_FROM_TASK0>, required_paths=required)
    except Exception:
        return "unavailable"
```
Replace `<BACKUP_ROOT_FROM_TASK0>` with the confirmed root (default `Path.home() / "maez-backups"`).

- [ ] **Step 4: Run to verify it passes** — same → PASS.

- [ ] **Step 5: Full suites + ruff**

```bash
MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -m unittest \
  tests.test_backup_manifest_coverage tests.test_backup_freshness tests.test_lean_idle_daemon -v
/home/rohit/maez/.venv/bin/ruff check core/health/backup_freshness.py daemon/maez_daemon.py \
  core/governance/operator_user_boundary.py scripts/backup/backup_state_manifest.json 2>/dev/null || \
  /home/rohit/maez/.venv/bin/ruff check core/health/backup_freshness.py daemon/maez_daemon.py core/governance/operator_user_boundary.py
```
Expected: green; ruff clean.

- [ ] **Step 6: Commit (behavior commit — include the prediction)**

```bash
git add daemon/maez_daemon.py core/governance/operator_user_boundary.py tests/test_lean_idle_daemon.py
git commit -m "fix(backup): daemon reports true backup freshness, not hardcoded unavailable

## Predicted effect
_operator_health now computes backup_freshness_class from the real backup state:
'fresh' only when the latest finalized backup is <13h old AND includes the
required_welfare/continuity stores; else coverage_gap / stale / unavailable.
Replaces the hardcoded 'unavailable'. Read-only, fail-soft. The Gate's backup
axis can now legitimately report fresh once a complete backup exists."
```

---

### Task 4: Witness handoff + STOP

- [ ] **Step 1: Write `docs/handoffs/2026-06-25-backup-coverage-freshness-truth-v0-handoff.md`**

Record: Task 0 classification of all 18; the `<13h` policy; branch tip; full test + ruff output. **The owner-run witness sequence (force one backup, then verify):**
```
systemctl --user start maez-backup.service
LATEST=$(ls -d /home/rohit/maez-backups/2026-* | sort | tail -1)
test -d "$LATEST" && ! test -e /home/rohit/maez-backups/.in-progress/$(basename "$LATEST")   # finalized, not in-progress
grep -q "memory/salience_ledger.db" "$LATEST/manifest.json"      # notebook covered
grep -q "memory/subjective_duration.db" "$LATEST/manifest.json"  # time-sense covered
# then: daemon _operator_health()['backup_freshness_class'] == 'fresh'
```
Name **v1.1 (restore smoke test)** as the next, separate slice. State plainly: NOT merged, NOT restarted, NO flags.

- [ ] **Step 2: Commit + STOP**

```bash
git add docs/handoffs/2026-06-25-backup-coverage-freshness-truth-v0-handoff.md
git commit -m "docs(backup): hand off coverage + freshness truth v0"
```
Hand back to Claude for covenant review (coverage-before-signal order; the June welfare stores are `required_welfare`; `fresh` requires recent AND complete; `coverage_gap` on a missing store; read-only fail-soft reader; skips have reasons; the forced-run witness). **Then the owner runs the witness — the welfare rail is only honestly green after a real backup includes the notebook.**

---

## Self-Review

**Spec coverage:** coverage before signal (Task 1 precedes 2–3, stated as a covenant ✓); the 18 classified with the June stores as `required_welfare` (Task 0 + Task 1 tests ✓); `fresh` requires recent AND complete + the core-invariant test (`test_coverage_gap_when_recent_but_missing_store`, `test_fresh_when_recent_and_complete` ✓); `coverage_gap`/`stale`/`unavailable` classes (Task 2 ✓); `.in-progress` never counted (`test_inprogress_is_never_counted` ✓); daemon wiring replaces hardcoded + fail-soft (Task 3 ✓); skips carry reasons (`test_skips_have_written_reasons` ✓); witness = forced run + produced-manifest inspection (Task 4 ✓); v1.1 restore smoke test named-not-built (Task 4 ✓).

**Placeholder scan:** `<BACKUP_ROOT_FROM_TASK0>` and the `load_default_manifest` import are explicit Task 0 resolutions (root defaults to `~/maez-backups`); no silent TBDs.

**Type consistency:** `backup_freshness(*, backup_root, required_paths, now=None) -> str` identical across Task 2 def and Task 3 call. `FRESH_MAX_AGE_H=13`. Manifest entries carry `type`/`path`/`required`/`class`/`comment`; `intentionally_skipped` carries `path`/`reason`.
