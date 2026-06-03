# SQLite connection-FACTORY leak sweep — NAMED FOLLOW-UP

**Date:** 2026-06-03
**Status:** NAMED FOLLOW-UP. Uncovered when Codex blocked the direct-site sweep and an AST guard revealed the factory-shaped footgun is **25 sites**, not 2. **3 are fixed** (the confirmed-leaking ones); **~22 remain.** This slice fixes the rest and lands the AST guard as a hard gate.

---

## The discovery

Codex's block on the direct-site sweep was right: the `_conn()` factory pattern is the *same* footgun, routed through a helper. A method like

```python
def _conn(self) -> sqlite3.Connection:
    conn = sqlite3.connect(self.db_path)
    return conn                      # ← raw connection escapes
```

is used by callers as `with self._conn() as conn:` — which commits but **never closes** — leaking one FD per call (Codex empirically: 30 over 30 uses). An AST guard (returns-a-raw-connection from a non-`@contextmanager`) found **25 such factories** across core/skills.

## The fix (per factory)

Convert the factory into a `@contextmanager` that yields, commits, and closes — **callers stay unchanged**:

```python
from contextlib import contextmanager
from collections.abc import Iterator

@contextmanager
def _conn(self) -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(self.db_path)
    conn.row_factory = sqlite3.Row
    try:
        with conn:              # transaction: commit on success / rollback on error
            yield conn
    finally:
        conn.close()
```

**Per-factory caller-check first** (load-bearing): confirm every caller uses `with factory() as conn:`. If any caller does a bare `conn = self._conn()` (no `with`), the `@contextmanager` conversion would break it — that site needs an explicit lifecycle instead. (The 3 already-fixed all used `with`.)

## Already fixed (this branch — `sqlite-connection-leak-sweep`)

- `core/decision/pending_cards.py` `_conn` (11 callers) — confirmed leaking, fixed + probe.
- `skills/self_mod_dialog.py` `_conn` (9 callers) — confirmed leaking, fixed + probe.
- `core/evolution/dream_state.py` `_conn` (10+ callers, WAL/check_same_thread) — confirmed pattern, fixed; behavior-verified (23 dream tests; DreamState needs deps, so no isolated probe).

## Remaining ~22 (this slice)

```
core/governance/s7_webauthn_bootstrap.py:340 (_conn)
core/infra/capability_integration_plans.py:95 (_connect)
core/infra/capability_activation_registry.py:132 (_connect)
core/infra/capability_gap_detector.py:95 (_connect)
core/infra/fast_conversation_log.py:73 (_conn)
core/infra/capability_acquisition_queue.py:110 (_connect)
core/self_dev/persistence.py:108 (_connect)
core/self_dev/workshop.py:233 (_connect)
core/routing/focused_cognition.py:954 (_connect)
core/memory/m1_lived_episode_promotion.py:336 (_connect)
core/memory/baseline_observations.py:173 (_connect)
core/memory/entity_index.py:375 (_connect)
core/memory/episodes.py:105 (_connect)
core/memory/memory_scoring.py:193 (_ensure_db)
core/memory/relationship_graph.py:126 (_connect)
core/subscription_proxy/server.py:209 (_db)
core/actions/action_engine.py:423 (_conn)
core/learning/consequence_memory.py:128 (_connect)
core/learning/fabrication_memory.py:115 (_ensure_db)
core/learning/inner_residue.py:94 (_ensure_db)
core/routing/observation/__init__.py:125 (_connect)
skills/followup_queue.py:67 (_conn)
skills/evolution_engine.py:378 (_conn)
skills/user_accounts.py:117 (_conn)
```
(Regenerate authoritatively with the AST guard below.) Most are likely **latent** (colder paths, GC keeps up) like the direct-site sweep — hygiene, not an active storm — but each is the same fragile pattern. **Note `action_engine.py:423` and `episodes.py:105` are hotter paths** worth doing first.

## Acceptance gate — the AST guard (land it hard when ~22 are fixed)

Add as a second method in `tests/test_no_bare_sqlite_connect.py` (removed from this branch because it can't pass until the 22 are fixed):

```python
def test_no_connection_returning_factories(self):
    import ast
    offenders = []
    for top in ("core", "daemon", "skills"):
        for f in (_REPO / top).rglob("*.py"):
            if "__pycache__" in str(f): continue
            try: tree = ast.parse(f.read_text(encoding="utf-8"))
            except SyntaxError: continue
            for node in ast.walk(tree):
                if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)): continue
                if "contextmanager" in {getattr(d,"id",getattr(d,"attr",None)) for d in node.decorator_list}: continue
                conn_vars = set()
                for n in ast.walk(node):
                    if isinstance(n, ast.Assign) and isinstance(n.value, ast.Call):
                        fn = n.value.func
                        if isinstance(fn, ast.Attribute) and fn.attr == "connect" and getattr(fn.value,"id",None)=="sqlite3":
                            conn_vars.update(t.id for t in n.targets if isinstance(t, ast.Name))
                for n in ast.walk(node):
                    if isinstance(n, ast.Return) and n.value is not None:
                        v = n.value
                        if (isinstance(v, ast.Name) and v.id in conn_vars) or (
                            isinstance(v, ast.Call) and isinstance(v.func, ast.Attribute)
                            and v.func.attr=="connect" and getattr(v.func.value,"id",None)=="sqlite3"):
                            offenders.append(f"{f.relative_to(_REPO)}:{n.lineno}")
    self.assertEqual(offenders, [], "connection-returning factories leak FDs:\n" + "\n".join(offenders))
```

When this is green, the direct-site guard + this factory guard together close the sqlite-leak footgun **completely** and prevent both shapes from returning.

---

**Plain English:** Claude closed the obvious faucets and the three loud hose-adapters; this slice replaces the remaining ~22 hose-adapters and installs the detector that catches the hose shape forever.
