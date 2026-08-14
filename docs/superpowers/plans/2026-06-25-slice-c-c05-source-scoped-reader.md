# Slice C — C0.5 Enforced Source-Scoped Reader — Implementation Plan

> **For agentic workers:** **Codex's build lane** (Claude drafts plan + covenant-reviews; Codex builds; owner witnesses). Strict TDD, checkbox steps. **Do NOT merge, restart, or flip flags** — stop at the review gate. This is the locked door that must ship **before** any C1 broker.

**Goal:** Give the idle heartbeat a store-level reader that can return *only* its own notebook rows — `context.source == HEARTBEAT_VERSION` — scoped at SQL level so foreign producers (`reasoning_residue`, `clinical_boundary`) are structurally unreachable regardless of store volume.

**Architecture:** Add `PrivateThoughts.recent_by_source(...)` doing exact SQL scoping (`json_extract(context_json,'$.source')`) plus consent/flow/phase enforcement, ordered + limited at SQL. Retrofit the daemon's `_lean_idle_recent_private_thoughts()` to use it; keep the pure in-memory `select_private_reader_thoughts` as belt-and-suspenders.

**Tech Stack:** Python 3, stdlib `sqlite3` (SQLite 3.46.1, JSON1 confirmed). Test runner is **unittest, NOT pytest**:
`MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -m unittest tests.<module>`

**Covenant rails:** content-light; no behavior change beyond the reader; the door must lock on `context.source` only — `provenance`/`producer_id`/`signal_class` are *type, not identity* and are forbidden as the scope key.

---

### Task 0: Confirm SQL viability + the source key (no production code)

**Files:** none; record findings in the Task 3 handoff.

- [ ] **Step 1: Confirm JSON1 scoping works on the real store**

Run:
```
MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -c "
import sqlite3; from core.infra.private_thoughts import PrivateThoughts
c=sqlite3.connect(PrivateThoughts().db_path)
print('source-scope:', c.execute(\"SELECT COUNT(*) FROM private_thoughts WHERE json_extract(context_json,'\$.source')=?\",('daemon_cycle.reasoning_residue',)).fetchone()[0])
print('flow-each:', c.execute(\"SELECT COUNT(*) FROM private_thoughts WHERE EXISTS(SELECT 1 FROM json_each(context_json,'\$.allowed_flows') WHERE value=?)\",('private_reader',)).fetchone()[0])"
```
Expected: both return counts (confirmed 2026-06-25: 4507 / 4523). **Decision recorded:** scope on `json_extract(context_json,'$.source')` — do **not** use `provenance`/`producer_id`/`signal_class` (verified: `provenance = kind_value = self_wondering`, not the version identity). If for any reason exact source-scoping cannot happen at SQL level *before* `LIMIT`, **STOP and surface it** — do not fall back to fetch-then-filter.

- [ ] **Step 2: Confirm `HEARTBEAT_VERSION` + the record_signal arg shape**

Run:
```
MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -c "
from core.cognition.lean_idle_heartbeat import HEARTBEAT_VERSION
from core.infra.private_thoughts import ConsentTier, AllowedFlow, RetentionRule, SignalKind, ProducerId
print(HEARTBEAT_VERSION, ConsentTier.OWNER_PRIVATE.value, AllowedFlow.PRIVATE_READER.value)
print([c for c in dir(ConsentTier) if not c.startswith('_')])"
```
Record `HEARTBEAT_VERSION` (`lean_idle_heartbeat.v0`), the enum string values, and whether a second `ConsentTier` value exists (for the consent-rejection test; if only `owner_private` exists, the consent-failure test inserts a crafted row via direct SQL instead of `record_signal`).

---

### Task 1: `PrivateThoughts.recent_by_source(...)`

**Files:**
- Modify: `core/infra/private_thoughts.py` (add method near `recent`, ~line 743)
- Test: `tests/test_private_thoughts_source_scope.py` (new)

- [ ] **Step 1: Write the failing tests (the two C0 findings + envelope defense)**

```python
import tempfile, pathlib, unittest
from core.infra.private_thoughts import (
    PrivateThoughts, SignalKind, ProducerId, ConsentTier, RetentionRule, AllowedFlow,
)
from core.cognition.lean_idle_heartbeat import HEARTBEAT_VERSION

class RecentBySourceTest(unittest.TestCase):
    def _store(self):
        tmp = pathlib.Path(tempfile.mkdtemp()) / "pt.db"
        return PrivateThoughts(db_path=tmp)

    def _add(self, store, *, source, content,
             consent=ConsentTier.OWNER_PRIVATE,
             flows=(AllowedFlow.PRIVATE_READER, AllowedFlow.AUDIT_TRACE),
             phase="gestation"):
        return store.record_signal(
            content=content, signal_kind=SignalKind.SELF_WONDERING,
            producer_id=ProducerId.SELF_WONDERING, source=source,
            subject="maez_internal_state", consent_tier=consent,
            retention=RetentionRule.UNTIL_REVIEWED, allowed_flows=flows,
            context_extra={}, memory_phase=phase)

    def test_excludes_newest_foreign_rows(self):
        # Finding 1: foreign rows that are the NEWEST never surface.
        s = self._store()
        self._add(s, source=HEARTBEAT_VERSION, content="my own note")
        self._add(s, source="daemon_cycle.reasoning_residue", content="residue (newer)")
        self._add(s, source="clinical_boundary", content="crisis (newest)")
        rows = s.recent_by_source(HEARTBEAT_VERSION, limit=5)
        self.assertEqual([r["content"] for r in rows], ["my own note"])

    def test_surfaces_heartbeat_older_than_global_newest_20(self):
        # Finding 2: SQL-scoping, not recent-window — a buried heartbeat row still surfaces.
        s = self._store()
        self._add(s, source=HEARTBEAT_VERSION, content="old heartbeat note")
        for i in range(25):
            self._add(s, source="daemon_cycle.reasoning_residue", content=f"residue {i}")
        rows = s.recent_by_source(HEARTBEAT_VERSION, limit=2)
        self.assertEqual([r["content"] for r in rows], ["old heartbeat note"])

    def test_enforces_consent_flow_phase_even_with_right_source(self):
        # Defense in depth: right source but wrong envelope => not returned.
        s = self._store()
        self._add(s, source=HEARTBEAT_VERSION, content="wrong phase", phase="lived")
        self._add(s, source=HEARTBEAT_VERSION, content="no private_reader",
                  flows=(AllowedFlow.AUDIT_TRACE,))
        self.assertEqual(s.recent_by_source(HEARTBEAT_VERSION, limit=5), [])

    def test_respects_limit_newest_first(self):
        s = self._store()
        for i in range(4):
            self._add(s, source=HEARTBEAT_VERSION, content=f"note {i}")
        rows = s.recent_by_source(HEARTBEAT_VERSION, limit=2)
        self.assertEqual([r["content"] for r in rows], ["note 3", "note 2"])
```
(If Task 0 found no second `ConsentTier` value, add a `test_rejects_wrong_consent` that inserts a crafted heartbeat-source row with a non-`owner_private` `context.consent_tier` via direct SQL and asserts it's excluded.)

- [ ] **Step 2: Run to verify they fail**

Run: `MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -m unittest tests.test_private_thoughts_source_scope -v`
Expected: FAIL (`AttributeError: ... has no attribute 'recent_by_source'`).

- [ ] **Step 3: Implement `recent_by_source`**

Add to `PrivateThoughts`, mirroring `recent()`'s connection/`_row_to_dict` pattern:
```python
def recent_by_source(
    self,
    source: str,
    *,
    limit: int = 2,
    required_flow: str = "private_reader",
    consent: str = "owner_private",
    phase: str = "gestation",
) -> list[dict]:
    """Newest-first rows for EXACTLY one source, scoped at SQL level.

    The door locks on context.source (the only exact identity — provenance is
    the generic kind). Consent/flow/phase are enforced in the same WHERE as
    defense in depth. Foreign producers (reasoning_residue, clinical_boundary)
    are structurally unreachable regardless of store volume.
    """
    conn = sqlite3.connect(self.db_path)
    try:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT * FROM private_thoughts
            WHERE json_extract(context_json, '$.source') = ?
              AND memory_phase = ?
              AND json_extract(context_json, '$.consent_tier') = ?
              AND EXISTS (
                    SELECT 1 FROM json_each(context_json, '$.allowed_flows')
                    WHERE value = ?
              )
            ORDER BY thought_id DESC
            LIMIT ?
            """,
            (str(source), str(phase), str(consent), str(required_flow), int(limit)),
        ).fetchall()
    finally:
        conn.close()
    return [self._row_to_dict(r) for r in rows]
```

- [ ] **Step 4: Run to verify they pass**

Run: same as Step 2. Expected: PASS (all four/five).

- [ ] **Step 5: Commit**

```bash
git add core/infra/private_thoughts.py tests/test_private_thoughts_source_scope.py
git commit -m "feat(nervous-system): SQL-scoped recent_by_source — the locked private shelf"
```

---

### Task 2: Retrofit `_lean_idle_recent_private_thoughts()` + regression

**Files:**
- Modify: `daemon/maez_daemon.py` (`_lean_idle_recent_private_thoughts`, ~line 5060 region)
- Test: `tests/test_lean_idle_daemon.py`

- [ ] **Step 1: Write the failing test**

```python
def test_recent_private_thoughts_uses_source_scoped_reader(self):
    from daemon.maez_daemon import MaezDaemon
    daemon = object.__new__(MaezDaemon)
    seen = {}
    class _Store:
        def recent_by_source(self, source, *, limit=2, **kw):
            seen["source"] = source; seen["limit"] = limit
            return [{"content": "kept", "memory_phase": "gestation",
                     "context": {"source": source, "consent_tier": "owner_private",
                                 "allowed_flows": ["private_reader"]}}]
        def recent(self, limit=20):
            seen["used_recent"] = True   # must NOT be called
            return []
    daemon.private_thoughts = _Store()
    out = daemon._lean_idle_recent_private_thoughts()
    from core.cognition.lean_idle_heartbeat import HEARTBEAT_VERSION
    self.assertEqual(seen["source"], HEARTBEAT_VERSION)
    self.assertNotIn("used_recent", seen)     # the fragile global read is gone
    self.assertEqual(out, ("kept",))
```

- [ ] **Step 2: Run to verify it fails**

Run: `MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -m unittest tests.test_lean_idle_daemon -k source_scoped -v`
Expected: FAIL (`used_recent` set, or `source` missing — current code calls `recent(20)`).

- [ ] **Step 3: Retrofit the adapter**

Replace the `recent(20)` read with the locked door; keep `select_private_reader_thoughts` as the in-memory belt-and-suspenders gate:
```python
def _lean_idle_recent_private_thoughts(self) -> tuple:
    try:
        store = getattr(self, "private_thoughts", None)
        if store is None:
            return ()
        from core.cognition.lean_idle_heartbeat import (
            HEARTBEAT_VERSION, select_private_reader_thoughts,
        )
        rows = store.recent_by_source(HEARTBEAT_VERSION, limit=2)
        return select_private_reader_thoughts(rows)  # double-lock: SQL door + in-memory gate
    except Exception:
        return ()
```

- [ ] **Step 4: Run to verify it passes**

Run: same as Step 2. Expected: PASS.

- [ ] **Step 5: Run the full protected suites + ruff**

```bash
MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -m unittest \
  tests.test_private_thoughts_source_scope tests.test_lean_idle_heartbeat tests.test_lean_idle_daemon -v
/home/rohit/maez/.venv/bin/ruff check core/infra/private_thoughts.py daemon/maez_daemon.py tests/test_private_thoughts_source_scope.py
```
Expected: all green; ruff clean.

- [ ] **Step 6: Commit**

```bash
git add daemon/maez_daemon.py tests/test_lean_idle_daemon.py
git commit -m "fix(nervous-system): idle loop reads its notebook through the locked door"
```
(No `## Predicted effect` — this is a correctness/safety fix to an existing read path, not a new behavior. The heartbeat's *observable* output is unchanged today; only the read's robustness + isolation change.)

---

### Task 3: Handoff + STOP

**Files:**
- Create: `docs/handoffs/2026-06-25-slice-c-c05-source-scoped-reader-handoff.md`

- [ ] **Step 1: Write the handoff**

Record: Task 0 decisions (source key = `json_extract(context_json,'$.source')`; no provenance substitution; second-ConsentTier finding); branch tip; full test + ruff output; the two C0 findings now have pinning tests; the owner-breath sequence (**merge → owner restart → confirm the heartbeat still reads its own thoughts and no foreign rows ever appear in `recent_private_thoughts`**). State plainly: NOT merged, NOT restarted, NO flags.

- [ ] **Step 2: Commit + STOP**

```bash
git add docs/handoffs/2026-06-25-slice-c-c05-source-scoped-reader-handoff.md
git commit -m "docs(nervous-system): hand off C0.5 source-scoped reader"
```
Hand back to Claude for covenant review (door locks on `context.source` only; foreign/clinical rows structurally unreachable; consent/flow/phase enforced; retrofit drops the fragile `recent(20)`; no behavior change), then the owner witnesses. **C1 broker does not begin until C0.5 is merged + witnessed.**

---

## Self-Review

**Spec coverage:** SQL-level source scoping before `LIMIT` (Task 1 §3 ✓); no provenance substitution (Task 0 §1 + the code locks on `json_extract` ✓); consent/flow/phase enforced (Task 1 §3 WHERE ✓); return only heartbeat rows (test_excludes_newest_foreign_rows ✓); retrofit `_lean_idle_recent_private_thoughts` (Task 2 ✓); test foreign-newest-excluded + buried-heartbeat-surfaces + envelope-defense (Task 1 §1 ✓); regression shape (Task 2 §1 ✓). All C0.5 spec requirements map to a task.

**Placeholder scan:** none. The only conditional is the consent-rejection test path (alternate enum vs direct-SQL insert), gated by a Task 0 finding — explicit, not a TBD.

**Type consistency:** `recent_by_source(source, *, limit, required_flow, consent, phase)` signature is identical in Task 1 (def) and Task 2 (call uses `source` positional + `limit` kw, matching). `HEARTBEAT_VERSION` import path identical across tasks. `select_private_reader_thoughts` reused unchanged from Slice B.1.
