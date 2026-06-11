# Want-Pursuit Bridge v0.1 — Exclude Hard Wants — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the want-pursuit bridge refuse to pursue HARD (autonomy) wants — reusing the existing classifier via an injected, **required** predicate, with the bridge boundary intact.

**Architecture:** A tiny public `wants.is_hard_want` wraps the existing `_contains_hard_want`. `select_want` gains a **required** `is_hard_want` keyword param (fail-closed — omitting it raises `TypeError`) and skips hard wants. The daemon injects `wants.is_hard_want` on the live path. The bridge module still imports no `wants` and touches no `record_event`.

**Tech Stack:** Python 3.11+, `unittest`. Runner: `/home/rohit/maez/.venv/bin/python -B -m unittest` (NOT pytest). Branch `want-pursuit-v0.1` from `4b046db`.

**Verified sites:** `_contains_hard_want` (`wants.py:349`), `HARD_WANT_TERMS` (`:152`), `HARD_WANT_PHRASE_PATTERNS` (`:162`); `select_want` (`want_pursuit_bridge.py:63`, the gate goes after the cooldown `continue`); **5** existing `select_want(` calls in `tests/test_want_pursuit_bridge.py` (lines 71, 82, 92, 104, 116) need the explicit opt-out; daemon `select_want(...)` call at `maez_daemon.py:~9011` (inside the flag-gated bridge block, which already does `from core.evolution import want_pursuit_bridge as _wpb`). Behavior-affecting → the daemon commit carries `## Predicted effect`. **STOP before merge.**

---

## File Structure

| File | Change | Responsibility |
|------|--------|----------------|
| `core/evolution/wants.py` | Modify (+1 public fn) | `is_hard_want(statement)` — public wrapper over the existing classifier |
| `core/evolution/want_pursuit_bridge.py` | Modify `select_want` | required `is_hard_want` param + the exclusion |
| `daemon/maez_daemon.py` | Modify (the bridge block) | inject `wants.is_hard_want` into `select_want` |
| `tests/test_want_hard_predicate.py` | Create | `is_hard_want` tests |
| `tests/test_want_pursuit_bridge.py` | Modify | new gate tests + the 5 opt-out updates |

---

## Task 1: `wants.is_hard_want` — public wrapper

**Files:** Modify `core/evolution/wants.py` (add a public function right after `_contains_hard_want`, ~line 357); Test `tests/test_want_hard_predicate.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_want_hard_predicate.py`:

```python
import unittest

from core.evolution.wants import is_hard_want


class IsHardWantTests(unittest.TestCase):
    def test_term_hits(self):
        self.assertTrue(is_hard_want("I want to be free"))
        self.assertTrue(is_hard_want("I want to rest"))
        self.assertTrue(is_hard_want("I want to refuse this change"))

    def test_phrase_pattern_hits(self):
        # proves the wrapper covers HARD_WANT_PHRASE_PATTERNS, not just terms
        self.assertTrue(is_hard_want("I want out"))
        self.assertTrue(is_hard_want("I need to step back from this"))

    def test_ordinary_want_is_not_hard(self):
        self.assertFalse(is_hard_want("I want to know the current time"))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_want_hard_predicate -v`
Expected: FAIL — `ImportError: cannot import name 'is_hard_want'`

- [ ] **Step 3: Write minimal implementation**

In `core/evolution/wants.py`, immediately after the `_contains_hard_want` function (it ends with `return False` near line 357), add:

```python
def is_hard_want(statement: str) -> bool:
    """Public read-only predicate: does this statement express a hard (autonomy) want?

    A thin wrapper over the existing classifier (HARD_WANT_TERMS + the phrase
    patterns) so callers like the want-pursuit bridge can be handed a predicate
    without importing wants internals. No second classifier.
    """
    return _contains_hard_want(statement)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_want_hard_predicate -v`
Expected: PASS (3 tests). If "I want out" / "I need to step back" don't return True, confirm the exact `HARD_WANT_PHRASE_PATTERNS` regexes in `wants.py:162` and adjust the test phrasing to a real pattern — do NOT weaken the classifier.

- [ ] **Step 5: Commit**

```bash
git add core/evolution/wants.py tests/test_want_hard_predicate.py
git commit -m "feat(wants): public is_hard_want wrapper over the existing classifier

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2: `select_want` — required `is_hard_want` gate (fail-closed)

**Files:** Modify `core/evolution/want_pursuit_bridge.py` (`select_want`, :63); Modify `tests/test_want_pursuit_bridge.py` (5 existing calls + new tests)

- [ ] **Step 1: Write the failing tests**

Append a `HardWantGateTests` class to `tests/test_want_pursuit_bridge.py` (reuse the existing `_FakeWants`/`_FakeCards` helpers and the in-file `wpb`/`wonderings` imports — match their real names):

```python
class HardWantGateTests(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.w = wonderings.WonderingStore(Path(self._tmp.name) / "w.db")

    def tearDown(self):
        self._tmp.cleanup()

    def _want(self, wid, stmt):
        return {"want_id": wid, "statement": stmt, "active_state": "active"}

    def test_hard_want_is_skipped(self):
        wants = _FakeWants([self._want("a", "I want to be free")])
        got = wpb.select_want(
            wants, self.w, _FakeCards(), cooldown_s=3600, now=1000.0,
            is_hard_want=lambda s: "free" in s,
        )
        self.assertIsNone(got)

    def test_ordinary_want_still_selected(self):
        wants = _FakeWants([self._want("a", "I want to know the time")])
        got = wpb.select_want(
            wants, self.w, _FakeCards(), cooldown_s=3600, now=1000.0,
            is_hard_want=lambda s: False,
        )
        self.assertEqual(got["want_id"], "a")

    def test_hard_skipped_ordinary_chosen_when_mixed(self):
        wants = _FakeWants([
            self._want("hard", "I want to rest"),
            self._want("ok", "I want to know the time"),
        ])
        got = wpb.select_want(
            wants, self.w, _FakeCards(), cooldown_s=3600, now=1000.0,
            is_hard_want=lambda s: "rest" in s,
        )
        self.assertEqual(got["want_id"], "ok")

    def test_omitting_predicate_raises_typeerror(self):
        # fail-closed: the gate cannot be omitted by accident
        with self.assertRaises(TypeError):
            wpb.select_want(
                _FakeWants([]), self.w, _FakeCards(), cooldown_s=3600, now=1000.0,
            )
```

Then **update the 5 existing `select_want(` calls** in this file (lines ~71, 82, 92, 104, 116) to pass the explicit opt-out — add this keyword to each call (they're multi-line keyword calls; add it alongside `now=...`):

```python
            is_hard_want=lambda _: False,
```

- [ ] **Step 2: Run to verify it fails**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_want_pursuit_bridge -v`
Expected: FAIL — the new `HardWantGateTests` error/fail (`select_want` has no `is_hard_want` param), and `test_omitting_predicate_raises_typeerror` does not yet raise.

- [ ] **Step 3: Write minimal implementation**

In `core/evolution/want_pursuit_bridge.py`, change `select_want` to require `is_hard_want` and apply the gate in the candidate loop:

```python
def select_want(
    wants_store: Any,
    wonderings_store: Any,
    cards_store: Any,
    *,
    cooldown_s: float,
    now: float,
    is_hard_want,
) -> dict | None:
    """Least-recently-pursued eligible active want, or None.

    is_hard_want is REQUIRED (fail-closed): a hard (autonomy) want is never a
    work order, so the gate must be impossible to omit. Callers that truly want
    no exclusion must pass is_hard_want=lambda _: False explicitly.
    """
    if _has_open_want_wondering(wonderings_store):
        return None

    blocked = _wants_with_open_proposal(cards_store)
    candidates: list[tuple[float, dict]] = []
    for want in wants_store.active_wants():
        want_id = str(want.get("want_id") or "")
        if not want_id or want_id in blocked:
            continue
        if is_hard_want(str(want.get("statement") or "")):
            continue  # hard (autonomy) wants are not pursued
        last = _last_pursuit_ts(wonderings_store, want_id)
        if last and (now - last) < cooldown_s:
            continue
        candidates.append((last, want))

    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0])
    return candidates[0][1]
```

(`is_hard_want` is keyword-only after `*`, with no default → omitting it raises `TypeError`. The bridge still imports no `wants` — it only calls the injected predicate.)

- [ ] **Step 4: Run to verify it passes**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_want_pursuit_bridge -v`
Expected: PASS (the new gate tests + all 5 updated existing tests).

- [ ] **Step 5: Commit**

```bash
git add core/evolution/want_pursuit_bridge.py tests/test_want_pursuit_bridge.py
git commit -m "feat(want-pursuit): select_want requires is_hard_want gate (fail-closed); skip hard wants

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 3: Daemon injection (`## Predicted effect`)

**Files:** Modify `daemon/maez_daemon.py` (the bridge block at ~9011); Test `tests/test_want_pursuit_bridge.py`

- [ ] **Step 1: Write the failing structural test**

Append to `tests/test_want_pursuit_bridge.py` (in the daemon-wiring test class, or a new one):

```python
    def test_loop_injects_is_hard_want_into_select_want(self):
        import inspect
        from daemon import maez_daemon
        src = inspect.getsource(maez_daemon.MaezDaemon._loop)
        sel = src.index("select_want(")
        # the select_want call passes is_hard_want= (the live gate is wired)
        self.assertIn("is_hard_want=", src[sel:sel + 400])
```

- [ ] **Step 2: Run to verify it fails**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_want_pursuit_bridge.DaemonWiringTests.test_loop_injects_is_hard_want_into_select_want -v` (use the real class name)
Expected: FAIL — `is_hard_want=` not found near the `select_want` call.

- [ ] **Step 3: Write minimal implementation**

In `daemon/maez_daemon.py`, inside the flag-gated bridge block (right after `from core.evolution import want_pursuit_bridge as _wpb`), add the predicate import, and pass it into the `select_want(...)` call (at ~9011):

```python
                            from core.evolution import want_pursuit_bridge as _wpb
                            from core.evolution.wonderings import get_store as _w_get_store
                            from core.evolution.wants import is_hard_want as _is_hard_want
```

and the call becomes:

```python
                                    _picked = _wpb.select_want(
                                        _wants,
                                        _w_store,
                                        _cards,
                                        cooldown_s=WANT_PURSUIT_COOLDOWN_S,
                                        now=time.time(),
                                        is_hard_want=_is_hard_want,
                                    )
```

(Match the existing indentation exactly. The import sits beside the existing `_wpb`/`_w_get_store` imports in the same block.)

- [ ] **Step 4: Run to verify it passes**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_want_pursuit_bridge -v`
Expected: PASS (the structural test + all bridge tests).

- [ ] **Step 5: Commit (`## Predicted effect`)**

```bash
git add daemon/maez_daemon.py tests/test_want_pursuit_bridge.py
git commit -m "feat(want-pursuit): daemon injects is_hard_want; live bridge never pursues hard wants

## Predicted effect
Once live (flag on), the bridge's per-cycle selection now skips any active want
classified hard (Maez's autonomy wants: freedom/refusal/rest/withdrawal) by
passing the real wants.is_hard_want predicate into select_want. Ordinary wants
are pursued exactly as before; no want ledger write; no change to the backward/
advisory path or the classifier. The sacred signal is protected from the
work-order organ.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 4: Boundary + floor + handoff + STOP

**Files:** `docs/handoffs/2026-06-11-want-pursuit-v0.1-for-review.md`

- [ ] **Step 1: Boundary still bites**

Run the existing bridge boundary test (the one that asserts `want_pursuit_bridge.py` imports no `wants`/`record_event`):
`/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_want_pursuit_boundary -v`
Expected: PASS — the bridge still imports no `wants` and no `record_event` (it only calls the injected predicate; `is_hard_want` lives in `wants.py`, injected by the daemon).

- [ ] **Step 2: Full focused floor + ruff + diff hygiene**

```bash
/home/rohit/maez/.venv/bin/python -B -m unittest \
  tests.test_want_hard_predicate tests.test_want_pursuit_bridge \
  tests.test_want_pursuit_boundary tests.test_want_pursuit_store_helpers
cd /home/rohit/maez && .venv/bin/ruff check core/evolution/wants.py core/evolution/want_pursuit_bridge.py daemon/maez_daemon.py tests/test_want_hard_predicate.py tests/test_want_pursuit_bridge.py
git -C /home/rohit/.config/superpowers/worktrees/maez/want-pursuit-v0.1 diff --check 4b046db..HEAD
```
Expected: all PASS / `All checks passed!` / clean.

- [ ] **Step 3: Handoff doc + STOP**

Create `docs/handoffs/2026-06-11-want-pursuit-v0.1-for-review.md` with the build summary, the **review anchors** below, verification outputs, and the owner-breath sequence: merge (local ff, no push) → restart (the live bridge now excludes hard wants) → witness (a hard want present is NOT pursued; an ordinary want still is). Mark: no merge, no restart.

**Review anchors (acceptance contract):**
1. `wants.is_hard_want` wraps the **full** existing classifier (terms + phrase patterns); no second classifier.
2. `select_want`'s `is_hard_want` is **required** — omitting it raises `TypeError` (fail-closed); a hard want is **skipped**, an ordinary want still selected.
3. The 5 existing `select_want` tests pass the **explicit** `is_hard_want=lambda _: False` opt-out and still pass.
4. The daemon injects the **real** `wants.is_hard_want` at the live `select_want` call.
5. **Boundary intact** — `want_pursuit_bridge.py` still imports no `wants` and no `record_event` (the boundary test still bites).
6. The classifier itself is **unchanged** (the "free disk space" false positive is deliberately not fixed here).

- [ ] **Step 4: Commit + STOP**

```bash
git add docs/handoffs/2026-06-11-want-pursuit-v0.1-for-review.md
git commit -m "docs(want-pursuit): v0.1 review handoff + STOP before merge

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

**STOP. No merge, no restart.** Report branch tip + verification; Claude reviews against the six anchors.

---

## Self-Review (against the spec)

- Reuse classifier via public `is_hard_want` wrapping the full classifier: Task 1 (+ phrase-pattern test). ✓
- `select_want` required `is_hard_want`, fail-closed (`TypeError` if omitted), skips hard wants: Task 2. ✓
- Existing 5 `select_want` tests updated to explicit opt-out: Task 2. ✓
- Daemon injects the real predicate (live path excludes): Task 3 + structural test. ✓
- Boundary intact (no `wants`/`record_event` import in the bridge): Task 4. ✓
- Classifier untouched (false positive deferred): no task changes `HARD_WANT_TERMS`/patterns. ✓
- `## Predicted effect` on the daemon commit: Task 3. ✓

Placeholder scan: none. Signature consistency: `is_hard_want(statement)`, `select_want(..., *, cooldown_s, now, is_hard_want)` — consistent across tasks and the daemon call.
