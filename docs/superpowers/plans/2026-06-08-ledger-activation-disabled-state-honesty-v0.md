# Ledger Activation / Disabled-State Honesty v0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the ledger honest about its own state — one switch (`MAEZ_LEDGER_WRITES`) says "writing is allowed," a strict schema check says "the notebook is real," and the disabled path opens no SQLite at all (killing today's `no such table: meta` noise).

**Architecture:** A shared leaf helper consolidates the forked enabled-predicate. `model_reply_persistence` gates on it (then on a strict `ledger_is_initialized`) before touching SQLite. An explicit init CLI builds the ledger; nothing auto-initializes at startup. Activation stays an owner act.

**Tech Stack:** Python, `unittest` (NOT pytest), SQLite. Run from the worktree with `/home/rohit/maez/.venv/bin/python -B -m unittest`.

**Worktree:** `/home/rohit/maez-wt-ledger` (branch `ledger-activation-v0`). Run all commands there.

---

## File Structure

- **Create** `core/ledger/writes_flag.py` — leaf: `ledger_writes_enabled()` + `_TRUE_VALUES`/`_FALSE_VALUES` + the unrecognized-value warning. Imports only `os`/`logging`.
- **Modify** `core/ledger/writer.py` — `_parse_flag` and the module-level `try_write_turn` inline parse delegate to the helper; drop the now-unused local value sets.
- **Modify** `core/ledger/reconcile.py` — `_writes_enabled()` delegates to the helper; drop its local `_TRUE_VALUES`.
- **Modify** `core/ledger/migrate.py` — add `ledger_is_initialized(db_path) -> bool` (strict, read-only, never raises).
- **Modify** `core/ledger/model_reply_persistence.py` — gate `persist_model_reply` on enabled → initialized before any SQLite.
- **Create** `core/ledger/init.py` — `python -m core.ledger.init` CLI.
- **Create** `tests/test_ledger_activation_v0.py` — the slice's tests.

---

### Task 1: Shared `writes_flag.py` helper

**Files:**
- Create: `core/ledger/writes_flag.py`
- Test: `tests/test_ledger_activation_v0.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_ledger_activation_v0.py`:

```python
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock


class LedgerWritesEnabled(unittest.TestCase):
    def _enabled(self, value):
        env = {} if value is None else {"MAEZ_LEDGER_WRITES": value}
        with mock.patch.dict(os.environ, env, clear=False):
            if value is None:
                os.environ.pop("MAEZ_LEDGER_WRITES", None)
            from core.ledger.writes_flag import ledger_writes_enabled
            return ledger_writes_enabled()

    def test_true_values_enable(self):
        for v in ("1", "true", "TRUE", " true "):
            self.assertTrue(self._enabled(v), v)

    def test_false_and_unset_disable(self):
        for v in (None, "", "0", "false", "no", "off"):
            self.assertFalse(self._enabled(v), repr(v))

    def test_unrecognized_disables_with_warning(self):
        from core.ledger import writes_flag
        with mock.patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "yarp"}):
            with self.assertLogs("core.ledger.writes_flag", level="WARNING") as logs:
                self.assertFalse(writes_flag.ledger_writes_enabled())
        self.assertIn("unrecognized", "\n".join(logs.output).lower())
```

- [ ] **Step 2: Run to verify it fails**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_ledger_activation_v0.LedgerWritesEnabled`
Expected: FAIL — `ModuleNotFoundError: No module named 'core.ledger.writes_flag'`.

- [ ] **Step 3: Create the helper**

Create `core/ledger/writes_flag.py`:

```python
# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Single source of truth for "is the ledger allowed to write?".

The switch is the env flag MAEZ_LEDGER_WRITES. This is intentionally a leaf
module (imports only os + logging) so writer, reconcile, and model_reply
persistence can share ONE predicate without a circular import — and so the
parse (including the unrecognized-value warning) does not fork.
"""

from __future__ import annotations

import logging
import os

_LOGGER = logging.getLogger("core.ledger.writes_flag")

_TRUE_VALUES = {"1", "true"}
_FALSE_VALUES = {"0", "false", "no", "off", ""}


def ledger_writes_enabled() -> bool:
    """True only when MAEZ_LEDGER_WRITES is an explicit true value.

    Unset / falsy → False (default-off). An unrecognized non-empty value →
    False, with a single WARNING (do not silently treat junk as enabled).
    """
    raw = os.environ.get("MAEZ_LEDGER_WRITES", "")
    stripped = raw.strip().lower()
    if stripped in _TRUE_VALUES:
        return True
    if stripped in _FALSE_VALUES:
        return False
    _LOGGER.warning(
        "MAEZ_LEDGER_WRITES has unrecognized value %r; treating as disabled. "
        "Use '1' or 'true' to enable.",
        raw,
    )
    return False
```

- [ ] **Step 4: Run to verify it passes**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_ledger_activation_v0.LedgerWritesEnabled`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd /home/rohit/maez-wt-ledger
git add core/ledger/writes_flag.py tests/test_ledger_activation_v0.py
git commit -m "feat(ledger): shared ledger_writes_enabled() leaf helper (one source of truth)"
```

---

### Task 2: writer + reconcile delegate to the helper (no fork)

**Files:**
- Modify: `core/ledger/writer.py:213-225` (`_parse_flag`), `:521-527` (inline parse in `try_write_turn`), drop `:64-65` value sets
- Modify: `core/ledger/reconcile.py:41` (drop `_TRUE_VALUES`), `:44-46` (`_writes_enabled`)
- Test: `tests/test_ledger_activation_v0.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_ledger_activation_v0.py`:

```python
class PredicateDoesNotFork(unittest.TestCase):
    def test_writer_and_reconcile_delegate_to_helper(self):
        from core.ledger import reconcile, writes_flag
        from core.ledger.writer import LedgerWriter
        for v in ("1", "true", "0", "", "off", "garbage"):
            with mock.patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": v}):
                expected = writes_flag.ledger_writes_enabled()
                self.assertEqual(LedgerWriter().is_enabled(), expected, v)
                self.assertEqual(reconcile._writes_enabled(), expected, v)

    def test_writer_module_no_longer_defines_value_sets(self):
        # The value sets live ONLY in writes_flag now (no fork).
        import core.ledger.writer as w
        self.assertFalse(hasattr(w, "_TRUE_VALUES"))
        import core.ledger.reconcile as r
        self.assertFalse(hasattr(r, "_TRUE_VALUES"))
```

(If `LedgerWriter()` requires constructor args, check `core/ledger/writer.py:173` and pass the minimal ones; it reads the flag at construction.)

- [ ] **Step 2: Run to verify it fails**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_ledger_activation_v0.PredicateDoesNotFork`
Expected: FAIL — `writer._TRUE_VALUES` / `reconcile._TRUE_VALUES` still exist.

- [ ] **Step 3: Refactor to delegate**

In `core/ledger/writer.py`:
- Delete the module-level `_TRUE_VALUES = {"1", "true"}` and `_FALSE_VALUES = {...}` (lines 64-65).
- Add near the top imports: `from core.ledger.writes_flag import ledger_writes_enabled`.
- Replace the `_parse_flag` method body with:

```python
    def _parse_flag(self) -> bool:
        return ledger_writes_enabled()
```

- In the module-level `try_write_turn`, replace the inline parse (the
  `raw_flag = os.environ.get(...)` block through its warning/return) with:

```python
    if not ledger_writes_enabled():
        return None
```

In `core/ledger/reconcile.py`:
- Delete `_TRUE_VALUES = {"1", "true"}` (line 41).
- Add: `from core.ledger.writes_flag import ledger_writes_enabled`.
- Replace `_writes_enabled`:

```python
def _writes_enabled() -> bool:
    return ledger_writes_enabled()
```

- [ ] **Step 4: Run to verify it passes**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_ledger_activation_v0 tests.test_model_reply_persistence`
Expected: PASS (the delegation tests + no regression to existing ledger tests).

- [ ] **Step 5: Commit**

```bash
git add core/ledger/writer.py core/ledger/reconcile.py tests/test_ledger_activation_v0.py
git commit -m "refactor(ledger): writer + reconcile delegate to ledger_writes_enabled (de-fork)"
```

---

### Task 3: `ledger_is_initialized(db_path)` in migrate.py (strict, read-only)

**Files:**
- Modify: `core/ledger/migrate.py` (add the function; near `run` at :189)
- Test: `tests/test_ledger_activation_v0.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_ledger_activation_v0.py`:

```python
class LedgerIsInitialized(unittest.TestCase):
    def _fresh(self, name):
        p = str(Path(tempfile.mkdtemp()) / f"{name}.db")
        return p

    def test_true_on_migrated_db(self):
        from core.ledger import migrate
        p = self._fresh("ok")
        migrate.run(p)
        self.assertTrue(migrate.ledger_is_initialized(p))

    def test_false_on_zero_byte_and_missing(self):
        from core.ledger import migrate
        missing = self._fresh("missing")
        self.assertFalse(migrate.ledger_is_initialized(missing))   # no file
        self.assertFalse(Path(missing).exists())                   # read-only: not created
        zero = self._fresh("zero")
        Path(zero).touch()
        self.assertFalse(migrate.ledger_is_initialized(zero))      # 0 bytes

    def test_false_on_hash_mismatch(self):
        from core.ledger import migrate
        p = self._fresh("tamper")
        migrate.run(p)
        conn = sqlite3.connect(p)
        conn.execute("UPDATE meta SET value='deadbeef' WHERE key='last_chain_hash'")
        conn.commit()
        conn.close()
        self.assertFalse(migrate.ledger_is_initialized(p))         # half-built/corrupt fails

    def test_false_on_missing_genesis_row(self):
        from core.ledger import migrate
        p = self._fresh("nogen")
        migrate.run(p)
        conn = sqlite3.connect(p)
        conn.execute("DELETE FROM turns WHERE turn_id='genesis'")
        conn.commit()
        conn.close()
        self.assertFalse(migrate.ledger_is_initialized(p))

    def test_never_raises_on_garbage(self):
        from core.ledger import migrate
        p = self._fresh("garbage")
        Path(p).write_text("this is not a sqlite database at all")
        self.assertFalse(migrate.ledger_is_initialized(p))         # no exception
```

- [ ] **Step 2: Run to verify it fails**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_ledger_activation_v0.LedgerIsInitialized`
Expected: FAIL — `migrate.ledger_is_initialized` does not exist.

- [ ] **Step 3: Implement the check**

Add to `core/ledger/migrate.py` (after `run`, or near it):

```python
def ledger_is_initialized(db_path: str) -> bool:
    """Strict, read-only proof that db_path is a REAL ledger.

    True only if: meta + turns tables exist; the canonical genesis row is
    present (turns.turn_id='genesis'); meta.genesis_hash and meta.last_chain_hash
    are present; AND the genesis row's chain_hash equals BOTH meta values (on a
    freshly-migrated ledger all three are the same canonical genesis hash). This
    rejects a half-built / corrupt notebook, not merely an empty one.

    Opens read-only (never creates the file). Returns False — never raises — on
    a missing/zero-byte/corrupt DB, missing tables/rows/keys, or a hash mismatch.
    """
    if not os.path.exists(db_path) or os.path.getsize(db_path) == 0:
        return False
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    except Exception:
        return False
    try:
        names = {
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        if not {"meta", "turns"} <= names:
            return False
        gen = conn.execute(
            "SELECT chain_hash FROM turns WHERE turn_id = 'genesis'"
        ).fetchone()
        if not gen or not gen[0]:
            return False
        genesis_chain_hash = gen[0]
        meta = {
            k: v
            for (k, v) in conn.execute(
                "SELECT key, value FROM meta WHERE key IN "
                "('genesis_hash', 'last_chain_hash')"
            )
        }
        if "genesis_hash" not in meta or "last_chain_hash" not in meta:
            return False
        return (
            meta["genesis_hash"] == genesis_chain_hash
            and meta["last_chain_hash"] == genesis_chain_hash
        )
    except Exception:
        return False
    finally:
        conn.close()
```

(`os` and `sqlite3` are already imported in `migrate.py`.)

- [ ] **Step 4: Run to verify it passes**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_ledger_activation_v0.LedgerIsInitialized`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add core/ledger/migrate.py tests/test_ledger_activation_v0.py
git commit -m "feat(ledger): ledger_is_initialized — strict read-only 'notebook is real' proof"
```

---

### Task 4: Gate `model_reply_persistence` (the headline)

**Files:**
- Modify: `core/ledger/model_reply_persistence.py` (`persist_model_reply` :137, top guard)
- Test: `tests/test_ledger_activation_v0.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_ledger_activation_v0.py`:

```python
_PERSIST_KW = dict(
    raw_text="audited reply text",
    surface="telegram_surface",
    parent_turn_id=None,
    model_id="qwen36-27b",
    prompt_material={"p": 1},
    soul_material={"s": 1},
    evidence_envelope={"claimable": [], "forbidden": []},
    audit_verdict={"verdict": "grounded"},
)


class ModelReplyGate(unittest.TestCase):
    def test_disabled_opens_no_sqlite(self):
        # HEADLINE: ledger off → silent no-op, NO SQLite opened, no warning.
        from core.ledger import model_reply_persistence as mrp
        os.environ.pop("MAEZ_LEDGER_WRITES", None)
        with mock.patch("core.ledger.model_reply_persistence.sqlite3.connect") as conn:
            out = mrp.persist_model_reply(db_path="/nonexistent/ledger.db", **_PERSIST_KW)
        self.assertIsNone(out)
        conn.assert_not_called()

    def test_enabled_uninitialized_warns_once_no_write(self):
        from core.ledger import model_reply_persistence as mrp
        from core.ledger import model_reply_persistence_warning as warn
        warn._WARNED_KEYS.clear()
        zero = str(Path(tempfile.mkdtemp()) / "z.db")
        Path(zero).touch()  # enabled but uninitialized
        with mock.patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
            with self.assertLogs("core.ledger.model_reply_persistence", level="WARNING") as logs:
                out1 = mrp.persist_model_reply(db_path=zero, **_PERSIST_KW)
                out2 = mrp.persist_model_reply(db_path=zero, **_PERSIST_KW)
        self.assertIsNone(out1)
        self.assertIsNone(out2)
        joined = "\n".join(logs.output).lower()
        self.assertIn("uninitialized", joined)
        self.assertIn("run ledger init", joined)
        # once per process: the uninitialized warning appears exactly once
        self.assertEqual(joined.count("uninitialized"), 1)

    def test_enabled_initialized_proceeds(self):
        from core.ledger import migrate
        from core.ledger import model_reply_persistence as mrp
        db = str(Path(tempfile.mkdtemp()) / "real.db")
        migrate.run(db)
        with mock.patch.dict(os.environ, {"MAEZ_LEDGER_WRITES": "1"}):
            out = mrp.persist_model_reply(db_path=db, **_PERSIST_KW)
        # initialized + enabled → it actually writes a model_reply turn id
        self.assertTrue(out)
```

- [ ] **Step 2: Run to verify they fail**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_ledger_activation_v0.ModelReplyGate`
Expected: FAIL — disabled path currently opens SQLite (via `_ensure_persistence_marker`); no uninitialized warning exists.

- [ ] **Step 3: Add the gate**

In `core/ledger/model_reply_persistence.py`, add near the imports:

```python
from core.ledger.writes_flag import ledger_writes_enabled
from core.ledger.migrate import ledger_is_initialized
```

In `persist_model_reply`, immediately after the existing
`if not raw_text or evidence_envelope is None: return None` guard and BEFORE
`_ensure_persistence_marker(db_path)`, insert:

```python
    if not ledger_writes_enabled():
        # Disabled: silent no-op. Do NOT open SQLite or probe meta.
        return None
    if not ledger_is_initialized(db_path):
        _warn_once(
            "uninitialized",
            "ledger enabled but uninitialized; run ledger init",
        )
        return None
```

(`_warn_once` is already imported as
`warn_model_reply_persistence_once as _warn_once` at line 21; it is keyed
once-per-process via `_WARNED_KEYS`.)

- [ ] **Step 4: Run to verify they pass**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_ledger_activation_v0.ModelReplyGate tests.test_model_reply_persistence`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add core/ledger/model_reply_persistence.py tests/test_ledger_activation_v0.py
git commit -m "feat(ledger): gate model_reply persistence on enabled+initialized (silent when off)

## Predicted effect

With the ledger off (today's state), model_reply persistence opens no SQLite and
emits no 'no such table: meta' warning. Enabled-but-uninitialized warns once
('ledger enabled but uninitialized; run ledger init') and does not write.
Initialized+enabled writes as before. No non-ledger path changes."
```

---

### Task 5: `core/ledger/init.py` CLI

**Files:**
- Create: `core/ledger/init.py`
- Test: `tests/test_ledger_activation_v0.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_ledger_activation_v0.py`:

```python
class InitCLI(unittest.TestCase):
    def test_init_creates_and_verifies_idempotent(self):
        import subprocess
        from core.ledger import migrate
        db = str(Path(tempfile.mkdtemp()) / "cli.db")
        cmd = ["/home/rohit/maez/.venv/bin/python", "-B", "-m", "core.ledger.init", db]
        r1 = subprocess.run(cmd, cwd="/home/rohit/maez-wt-ledger",
                            capture_output=True, text=True)
        self.assertEqual(r1.returncode, 0, r1.stderr)
        self.assertIn("ledger initialized", r1.stdout.lower())
        self.assertTrue(migrate.ledger_is_initialized(db))
        # idempotent: second run still succeeds
        r2 = subprocess.run(cmd, cwd="/home/rohit/maez-wt-ledger",
                            capture_output=True, text=True)
        self.assertEqual(r2.returncode, 0, r2.stderr)
        self.assertTrue(migrate.ledger_is_initialized(db))
```

- [ ] **Step 2: Run to verify it fails**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_ledger_activation_v0.InitCLI`
Expected: FAIL — `No module named core.ledger.init`.

- [ ] **Step 3: Create the CLI**

Create `core/ledger/init.py`:

```python
# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Explicit, witnessed ledger initialization. Run:

    python -m core.ledger.init [path]   (default: memory/ledger.db)

Runs migrate.run (idempotent), verifies the result is a real ledger, and prints
a CONTENT-FREE status line. NEVER auto-run from the daemon — initialization is a
deliberate owner act.
"""

from __future__ import annotations

import sqlite3
import sys

from core.ledger import migrate

_DEFAULT_PATH = "memory/ledger.db"


def _head_prefix(db_path: str) -> str:
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        row = conn.execute(
            "SELECT value FROM meta WHERE key='last_chain_hash'"
        ).fetchone()
        return (row[0][:8] if row and row[0] else "?")
    finally:
        conn.close()


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    path = args[0] if args else _DEFAULT_PATH
    migrate.run(path)
    if not migrate.ledger_is_initialized(path):
        print(f"ledger init FAILED to verify: {path}", file=sys.stderr)
        return 1
    print(
        f"ledger initialized: {path} | meta=ok turns=ok genesis=ok "
        f"schema_version=1 head={_head_prefix(path)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run to verify it passes**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_ledger_activation_v0.InitCLI`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add core/ledger/init.py tests/test_ledger_activation_v0.py
git commit -m "feat(ledger): python -m core.ledger.init CLI (explicit, witnessed, idempotent)"
```

---

### Task 6: No auto-init at daemon startup (structural guard)

**Files:**
- Test: `tests/test_ledger_activation_v0.py`

- [ ] **Step 1: Write the failing-then-passing structural test**

The daemon currently does NOT call `migrate.run` / the init entrypoint — this test
locks that in so a future change can't silently start auto-initializing the
production ledger. Add to `tests/test_ledger_activation_v0.py`:

```python
class NoDaemonAutoInit(unittest.TestCase):
    def test_daemon_does_not_auto_initialize_the_ledger(self):
        src = Path("/home/rohit/maez-wt-ledger/daemon/maez_daemon.py").read_text()
        self.assertNotIn("migrate.run", src)
        self.assertNotIn("core.ledger.init", src)
        self.assertNotIn("ledger_init", src)
```

- [ ] **Step 2: Run to verify the current state**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_ledger_activation_v0.NoDaemonAutoInit`
Expected: PASS immediately (the daemon has no such call today — this is a guard, not a fix). If it FAILS, an auto-init crept in; stop and investigate.

- [ ] **Step 3: Commit**

```bash
git add tests/test_ledger_activation_v0.py
git commit -m "test(ledger): guard against daemon auto-initializing the production ledger"
```

---

### Task 7: Regression + floor sweep + Codex handoff

**Files:** none (verification + handoff doc)

- [ ] **Step 1: Run ledger + adjacent suites**

Run:
```bash
/home/rohit/maez/.venv/bin/python -B -m unittest \
  tests.test_ledger_activation_v0 tests.test_model_reply_persistence \
  tests.test_envelope_builder tests.test_photo_focused_routing
```
Expected: all OK (note `test_model_reply_persistence` has a known cross-suite ledger order-flake; if it appears, run it in isolation to confirm it still passes).

- [ ] **Step 2: Full discover floor check (AFTER the last change)**

Run `discover` on the branch and diff branch-only failures vs the `07a4185` baseline
(generate the baseline by `git checkout -q 07a4185` in the worktree, discover, then
`git checkout -q ledger-activation-v0`). Every branch-only delta must pass in
isolation. Zero real regressions.

- [ ] **Step 3: Write the Codex handoff** in `docs/handoffs/` noting: branch, commits,
the three-state contract, the strict init proof, the headline "disabled opens no
SQLite" test, that activation (prod init + `MAEZ_LEDGER_WRITES=1` + restart) is an
OWNER breath not taken by Claude, and the floor result. Then STOP for Codex review.

---

## Self-Review

**Spec coverage:** shared `ledger_writes_enabled()` (Task 1) + de-fork (Task 2); strict `ledger_is_initialized` (Task 3); model_reply gate enabled→initialized, disabled-opens-no-sqlite headline (Task 4); init CLI `core/ledger/init.py` (Task 5); no-auto-init guard (Task 6); the 7 spec tests map onto Tasks 1/3/4/5/6 (disabled-no-sqlite=T4, uninitialized-one-warning=T4, initialized-proceeds=T4, predicate-no-fork=T2, ledger_is_initialized-strict=T3, init-CLI=T5, no-auto-init=T6). All covered.

**Placeholder scan:** none — full code/commands in every step.

**Type consistency:** `ledger_writes_enabled() -> bool` and `ledger_is_initialized(db_path) -> bool` used identically across tasks; `_warn_once("uninitialized", …)` matches the existing `warn_model_reply_persistence_once(key, message)` signature; `migrate.run` / `migrate.ledger_is_initialized` consistent.
