# Earned-Maturity Routing — Slice 3a (veto-event ledger + re-ask signal) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Maez's vetoes *observable* and capture an honest "was the veto right?" signal — record each veto with its belief snapshot, honor an explicit exact-repeat re-ask by lifting the veto once and *going to look*, and classify the original veto `likely_wrong`/`likely_right`/`uncontested`/`ambiguous` from what that second reach found. No maturity adjustment yet.

**Architecture:** A new pure `VetoLedger` (SQLite, sibling to the routing-observations DB) records veto events + classifies them. Three flag-gated seams in `daemon/maez_daemon.py` (all behind `MAEZ_VETO_LEDGER`, off = byte-identical): record the veto at the veto-fire point; at the gate, an open same-class veto-event within the window *lifts* the veto once (override) and the turn searches; at the post-synthesis writeback, that search's `outcome_quality` classifies the original event. Silence is `uncontested` (weak, lazily materialized — no scheduler), never `likely_right`. v0 detects exact-utterance-hash repeats only.

**Tech Stack:** Python 3, stdlib `sqlite3`. Reuses Slice 1's `classify_request_class`, `_routing_quality_from_gate`, the routing-observation DB path. Tests: `MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -m unittest tests.<module> -v` (named only). Hermetic via `MAEZ_VETO_LEDGER_DB_PATH`.

**Lane:** TDD; branch via worktree `earned-maturity-slice3a`; STOP at review gate (owner-sovereign merge + restart). Claude two-stage + Codex cross-lane. `## Predicted effect` on behavior commits; docs/proof/test-only omit it. GIT HYGIENE: NO checkout/switch/reset/rebase; verify "On branch earned-maturity-slice3a" after each commit; STOP if detached. main local-only, no push.

**Flag:** `MAEZ_VETO_LEDGER` (default-off = byte-identical; on = the ledger records + the one-time exact-repeat re-ask override is live — shadow for maturity, behavior-active only for re-ask recovery). The ledger is only meaningful when `MAEZ_ROUTING_PRIORS_ENABLED=1` (vetoes must actually fire to be recorded).

---

## File Structure

- **`core/routing/veto_ledger.py`** (create): `VetoLedger` (record/find-open/attach-outcome/lazy-resolve) + `classify_outcome` (pure) + `VetoEvent` dataclass. Owns the `veto_events` table. No daemon imports.
- **`daemon/maez_daemon.py`** (modify, 3 seams behind `MAEZ_VETO_LEDGER`): record at the veto-fire (~5903); the override at the gate-top (~before 5902); classify at the writeback (~7227).
- **Tests:** `tests/test_veto_ledger.py` (the store + classifier, hermetic), `tests/test_veto_ledger_seams.py` (the daemon helper(s), hermetic).
- **Docs:** `docs/proof/2026-06-20-slice3a-task0.md`, `docs/handoffs/2026-06-20-slice3a-handoff.md`.

---

### Task 0: Prove the three seams (docs/proof only — STOP if any refutes)

**Files:** Create `docs/proof/2026-06-20-slice3a-task0.md`.

- [ ] **Step 1: Seam 1 — record point (HARD).** Confirm at [maez_daemon.py:5903](../../daemon/maez_daemon.py#L5903) the veto fires (`_reflex = False`) when `MAEZ_ROUTING_PRIORS_ENABLED=1 and _prior_vetoes_reflex(_prior)`, and that `_cls` (the class, [:5896](../../daemon/maez_daemon.py#L5896)), `_prior`, `_user_msg_turn_id` ([:5659](../../daemon/maez_daemon.py#L5659)), and `source` (surface) are all in scope there. Note that `_cls`/`_prior` are computed only inside the `SHADOW or ENABLED` block — so a `_cls = None` guard is needed before use.
- [ ] **Step 2: Seam 2 — override point + the "would a search run" conditions (HARD).** Confirm the gate condition's `_reflex` ([:5911](../../daemon/maez_daemon.py#L5911)) is the single lever; an override must run BEFORE [:5903](../../daemon/maez_daemon.py#L5903) so it can prevent the veto from forcing `_reflex=False`. **Record the EXACT search-gate conditions** ([:5905-5912](../../daemon/maez_daemon.py#L5905)): `not authoritative_tool_reply and _daemon_parallel_web_search_enabled(transcript, recall_stack_config=_recall_stack_config) and _reflex` — `_would_web_search` (Task 2) MUST mirror these so a veto is recorded only when a search would otherwise have fired (must-fix 1). Confirm `authoritative_tool_reply`, `transcript`, `_recall_stack_config` are all in scope at the gate-top.
- [ ] **Step 3: Seam 3 — classify point (HARD).** Confirm at the writeback block ([:7227](../../daemon/maez_daemon.py#L7227)) the override turn's `outcome_quality` is computed (`_routing_quality_from_gate` → `_q`, or the insert-time `structured_evidence` when `_q is None`), and that a function-scoped `_override_event_id` set at seam 2 is still in scope there to attach. Record the exact `outcome_quality` values available: `structured_evidence` (useful), `unusable`/`empty_but_honest` (reach failed), `tool_error`/`closed_refusal` (indeterminate).
- [ ] **Step 4: Window + lazy `uncontested` + scope.** Record the window definition (`_REASK_WINDOW_S`, default 3600s — a "what counts as a re-ask" definition, NOT a trust knob) and that `uncontested` is resolved lazily on ledger read (no scheduler). Confirm scope is only `veto_ledger.py` + the 3 daemon seams + tests + docs; nothing touches the strict honesty gate, S7, Telegram, time-sense, cockpit-reauth. Commit.

```bash
git add docs/proof/2026-06-20-slice3a-task0.md
git commit -m "docs(proof): slice3a Task 0 — veto-ledger 3 seams proven (record/override/classify)"
```

**GO/NO-GO:** all three HARD seams confirmed, else STOP/REFUTED.

---

### Task 1: The `VetoLedger` store + classifier (pure, hermetic)

**Files:** Create `core/routing/veto_ledger.py`; Test `tests/test_veto_ledger.py`.

- [ ] **Step 1: Write the failing test**

```python
import os, tempfile, unittest
os.environ.setdefault("MAEZ_IPHONE_INGEST_TOKEN", "dummy-test")
os.environ.setdefault("MAEZ_SECRETS_DISABLE_NEW_LOADER", "1")
from core.routing.veto_ledger import VetoLedger, classify_outcome

class VetoLedgerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.led = VetoLedger(db_path=self.tmp.name)
    def tearDown(self):
        self.tmp.close()
        try: os.unlink(self.tmp.name)
        except OSError: pass

    def _veto(self, t=1000.0):
        return self.led.record_veto(class_id="SIG", tool="web_search",
            prior_n=5, prior_success_rate=0.0, prior_confidence=0.625,
            turn_id="t1", surface="cockpit", now=t)

    def test_classify_outcome_mapping(self):
        self.assertEqual(classify_outcome("structured_evidence"), "likely_wrong")  # reach helped -> overcaution
        self.assertEqual(classify_outcome("unusable"), "likely_right")             # reach also junk -> wisdom
        self.assertEqual(classify_outcome("empty_but_honest"), "likely_right")     # reach found nothing -> wisdom
        self.assertEqual(classify_outcome("tool_error"), "ambiguous")

    def test_record_then_find_open_within_window(self):
        self._veto(1000.0)
        e = self.led.find_open_for_class("SIG", "web_search", now=1100.0)   # 100s later, in window
        self.assertIsNotNone(e); self.assertEqual(e.class_id, "SIG"); self.assertIsNone(e.classification)

    def test_reask_outcome_classifies_likely_wrong(self):
        self._veto(1000.0)
        e = self.led.find_open_for_class("SIG", "web_search", now=1100.0)
        cls = self.led.attach_reask_outcome(e.id, reask_turn_id="t2", reask_outcome_quality="structured_evidence")
        self.assertEqual(cls, "likely_wrong")
        self.assertIsNone(self.led.find_open_for_class("SIG", "web_search", now=1200.0))  # now closed

    def test_no_reask_past_window_is_uncontested_lazily(self):
        self._veto(1000.0)
        # read AFTER the window closes -> the open event is lazily resolved to uncontested, not returned as open
        self.assertIsNone(self.led.find_open_for_class("SIG", "web_search", now=1000.0 + 4000))
        rows = self.led.all_events()
        self.assertEqual(rows[0].classification, "uncontested")
```

- [ ] **Step 2: Run it; expect FAIL** (module missing).

- [ ] **Step 3: Implement `core/routing/veto_ledger.py`**

```python
"""Veto-event ledger (Slice 3a). Records every learned veto with its belief snapshot, and
classifies whether the veto was right from an explicit exact-repeat re-ask's second reach.
Silence -> 'uncontested' (weak), never 'likely_right'. Pure; no daemon imports."""
from __future__ import annotations
import sqlite3, uuid, os
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

_REASK_WINDOW_S = 3600          # "what counts as a re-ask" window (1h). A definition, not a trust knob.
_USEFUL = {"structured_evidence"}                 # reach produced useful evidence -> veto was overcautious
_REACH_FAILED = {"unusable", "empty_but_honest"}  # reach also produced nothing useful -> restraint was wise

def classify_outcome(outcome_quality: str) -> str:
    """The re-ask's second reach -> verdict on the ORIGINAL veto. Never 'uncontested' (that is the
    no-re-ask case, set elsewhere)."""
    if outcome_quality in _USEFUL:
        return "likely_wrong"
    if outcome_quality in _REACH_FAILED:
        return "likely_right"
    return "ambiguous"

@dataclass(frozen=True)
class VetoEvent:
    id: str
    class_id: str
    tool: str
    prior_n: int
    prior_success_rate: float
    prior_confidence: float
    turn_id: str | None
    surface: str
    created_at: float
    reask_turn_id: str | None
    reask_outcome_quality: str | None
    classification: str | None   # None = open; else likely_wrong/likely_right/uncontested/ambiguous

def _default_db_path() -> Path:
    override = os.environ.get("MAEZ_VETO_LEDGER_DB_PATH")
    if override:
        return Path(override)
    # sibling to the routing-observation DB
    from core.routing.observation import _default_db_path as _obs_db
    return _obs_db().parent / "veto_ledger.db"

class VetoLedger:
    def __init__(self, *, db_path: str | Path | None = None) -> None:
        self.db_path = Path(db_path) if db_path is not None else _default_db_path()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(self.db_path); conn.row_factory = sqlite3.Row
        try: yield conn
        finally: conn.close()

    def _init_schema(self) -> None:
        with self._connect() as conn, conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS veto_events (
                    id TEXT PRIMARY KEY, class_id TEXT NOT NULL, tool TEXT NOT NULL,
                    prior_n INTEGER NOT NULL, prior_success_rate REAL NOT NULL, prior_confidence REAL NOT NULL,
                    turn_id TEXT, surface TEXT NOT NULL, created_at REAL NOT NULL,
                    reask_turn_id TEXT, reask_outcome_quality TEXT, classification TEXT )""")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_veto_open ON veto_events(class_id, tool, classification)")

    def record_veto(self, *, class_id, tool, prior_n, prior_success_rate, prior_confidence,
                    turn_id, surface, now) -> str:
        eid = uuid.uuid4().hex
        with self._connect() as conn, conn:
            conn.execute("INSERT INTO veto_events (id,class_id,tool,prior_n,prior_success_rate,"
                "prior_confidence,turn_id,surface,created_at,reask_turn_id,reask_outcome_quality,classification)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (eid, class_id, tool, int(prior_n), float(prior_success_rate), float(prior_confidence),
                 turn_id, surface, float(now), None, None, None))
        return eid

    def _resolve_expired(self, now) -> None:
        """Lazy: open events past the window with no re-ask -> 'uncontested' (weak). No scheduler."""
        with self._connect() as conn, conn:
            conn.execute("UPDATE veto_events SET classification='uncontested' "
                "WHERE classification IS NULL AND reask_turn_id IS NULL AND created_at < ?",
                (float(now) - _REASK_WINDOW_S,))

    def find_open_for_class(self, class_id, tool, *, now, within_s=_REASK_WINDOW_S) -> VetoEvent | None:
        self._resolve_expired(now)   # materialize uncontested first (lazy)
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM veto_events WHERE class_id=? AND tool=? "
                "AND classification IS NULL AND created_at >= ? ORDER BY created_at DESC LIMIT 1",
                (class_id, tool, float(now) - within_s)).fetchone()
        return _row_to_event(row) if row else None

    def attach_reask_outcome(self, event_id, *, reask_turn_id, reask_outcome_quality) -> str:
        cls = classify_outcome(reask_outcome_quality)
        with self._connect() as conn, conn:
            conn.execute("UPDATE veto_events SET reask_turn_id=?, reask_outcome_quality=?, classification=? "
                "WHERE id=?", (reask_turn_id, reask_outcome_quality, cls, event_id))
        return cls

    def all_events(self) -> list[VetoEvent]:
        with self._connect() as conn:
            return [_row_to_event(r) for r in conn.execute("SELECT * FROM veto_events ORDER BY created_at")]

def _row_to_event(row) -> VetoEvent:
    return VetoEvent(row["id"], row["class_id"], row["tool"], row["prior_n"], row["prior_success_rate"],
        row["prior_confidence"], row["turn_id"], row["surface"], row["created_at"],
        row["reask_turn_id"], row["reask_outcome_quality"], row["classification"])
```

- [ ] **Step 4: Run it; expect PASS.** Ruff: `/home/rohit/maez/.venv/bin/python -m ruff check core/routing/veto_ledger.py tests/test_veto_ledger.py`.

- [ ] **Step 5: Commit** (pure module — no `## Predicted effect`).

```bash
git add core/routing/veto_ledger.py tests/test_veto_ledger.py
git commit -m "feat(veto-ledger): record vetoes + classify re-ask outcomes (uncontested lazy, silence!=right)"
```

---

### Task 2: Wire the three seams behind `MAEZ_VETO_LEDGER` (FULL two-stage — live reply path)

**Files:** Modify `daemon/maez_daemon.py` (3 seams). Test `tests/test_veto_ledger_seams.py`.

- [ ] **Step 1: Write the failing test** — a pure helper `_veto_ledger_enabled()` + the override-decision helper so the seam logic is unit-testable without a full daemon turn:

```python
import os, unittest
os.environ.setdefault("MAEZ_IPHONE_INGEST_TOKEN", "dummy-test")
os.environ.setdefault("MAEZ_SECRETS_DISABLE_NEW_LOADER", "1")

class SeamHelperTest(unittest.TestCase):
    def test_ledger_disabled_by_default(self):
        from daemon.maez_daemon import _veto_ledger_enabled
        os.environ.pop("MAEZ_VETO_LEDGER", None)
        self.assertFalse(_veto_ledger_enabled())
    def test_ledger_enabled_flag(self):
        from daemon.maez_daemon import _veto_ledger_enabled
        os.environ["MAEZ_VETO_LEDGER"] = "1"
        try: self.assertTrue(_veto_ledger_enabled())
        finally: os.environ.pop("MAEZ_VETO_LEDGER", None)
```

- [ ] **Step 2: Run it; expect FAIL.**

- [ ] **Step 3: Add the helper** (module-level, near `_prior_vetoes_reflex` ~:1080):

```python
def _veto_ledger_enabled() -> bool:
    return os.environ.get("MAEZ_VETO_LEDGER") == "1"
```

- [ ] **Step 4: Initialize the seam locals + the "would a search actually run" guard (must-fix 1 & 3).** Near `_prior = None` (~5889) add `_cls = None`, `_override_event_id = None`, `_ledger = None`, `_routing_turn_outcome_quality = None` (so an exception in the prior block never leaves them unbound). Then, AFTER `_reflex = needs_web_search(text)` (5902) and BEFORE the veto application (5903), compute the guard + the override — **a veto is only real evidence if a search would otherwise have fired** (same conditions as the actual search gate 5905-5912, NOT just `_prior_vetoes_reflex`):

```python
        _reflex = needs_web_search(text)
        _would_web_search = None
        if _veto_ledger_enabled() and os.environ.get("MAEZ_ROUTING_PRIORS_ENABLED") == "1":
            # The prior only truly SUPPRESSES a search when one would otherwise have run.
            _would_web_search = bool(
                not authoritative_tool_reply
                and _daemon_parallel_web_search_enabled(transcript, recall_stack_config=_recall_stack_config)
                and _reflex
            )
            if _cls is not None and _would_web_search and _prior_vetoes_reflex(_prior):
                try:  # seam 2: an open same-class veto within the window -> lift the veto ONCE (re-ask)
                    from core.routing.veto_ledger import VetoLedger
                    _ledger = VetoLedger()
                    _open = _ledger.find_open_for_class(_cls, "web_search", now=time.time())
                    _override_event_id = _open.id if _open is not None else None
                except Exception as _le:
                    logger.debug("veto ledger override check skipped: %s", _le)
```

- [ ] **Step 5: Seam 1 — fire the veto + record ONLY a veto that suppressed a real search (must-fix 1).** Replace the Slice-1 veto application (5903-5904) so (a) the override prevents the veto, and (b) a fired veto is recorded only when `_would_web_search` was true:

```python
        if os.environ.get("MAEZ_ROUTING_PRIORS_ENABLED") == "1" and _prior_vetoes_reflex(_prior) \
           and _override_event_id is None:
            _reflex = False  # learned veto
            if _veto_ledger_enabled() and _cls is not None and _would_web_search:
                try:
                    (_ledger or VetoLedger()).record_veto(
                        class_id=_cls, tool="web_search", prior_n=_prior.n,
                        prior_success_rate=_prior.success_rate, prior_confidence=_prior.confidence,
                        turn_id=_user_msg_turn_id, surface=source, now=time.time())
                except Exception as _re:
                    logger.debug("veto event record skipped: %s", _re)
```
Byte-identical off: when `MAEZ_VETO_LEDGER` is off, `_would_web_search`/`_override_event_id` stay None → the `if` reduces to Slice 1's `if ENABLED and _prior_vetoes_reflex(_prior) and None is None: _reflex=False`. (Keep the lazy `from core.routing.veto_ledger import VetoLedger` available in scope; `_ledger` is reused from Step 4 when present.)

- [ ] **Step 6: Capture the REAL turn outcome (must-fix 2), then Seam 3 — classify only from it.**
  - (a) Where the routing observation is recorded with its insert-time quality (~5950, `outcome_quality=("structured_evidence" if _routing_obs_count > 0 else "empty_but_honest")`), ALSO set `_routing_turn_outcome_quality` to that exact value (capture the same expression into the var).
  - (b) At the writeback block (~7227), when the calibrated outcome is computed and non-None (Slice 1's `_q` / its real name per Task 0 Step 3), set `_routing_turn_outcome_quality = <that value>` (the `unusable` revision overrides the insert-time value).
  - (c) Then classify — **only from a real outcome, never a default**:

```python
        if _veto_ledger_enabled() and _override_event_id is not None \
           and _routing_turn_outcome_quality is not None:
            try:
                from core.routing.veto_ledger import VetoLedger
                (_ledger or VetoLedger()).attach_reask_outcome(
                    _override_event_id, reask_turn_id=_user_msg_turn_id,
                    reask_outcome_quality=_routing_turn_outcome_quality)
            except Exception as _ce:
                logger.debug("veto reask classify skipped: %s", _ce)
```
If `_routing_turn_outcome_quality` is None (no real second reach happened), do **NOT** classify — leave the event open (it becomes `uncontested` on the next ledger read after the window, or stays open for a later indeterminate reach). **Never invent `structured_evidence`.**

- [ ] **Step 7: Off = byte-identical.** With `MAEZ_VETO_LEDGER` unset: `_veto_ledger_enabled()` is False → no override check, no record, no classify → the veto behaves exactly as Slice 1 (and with `PRIORS_ENABLED` also off, the whole block is inert). State how you confirmed.

- [ ] **Step 8: Run + ruff + commit** (behavior commit — `## Predicted effect`):

```bash
MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -m unittest tests.test_veto_ledger_seams tests.test_veto_ledger tests.test_routing_priors_veto_seam -v
/home/rohit/maez/.venv/bin/python -m ruff check daemon/maez_daemon.py
git add daemon/maez_daemon.py tests/test_veto_ledger_seams.py
git commit -m "feat(routing): veto-event ledger + one-time exact-repeat re-ask override

## Predicted effect
With MAEZ_VETO_LEDGER=1 (and PRIORS_ENABLED=1), a fired veto is recorded with its belief snapshot; an
exact-repeat re-ask of that class within the window LIFTS the veto once (Maez goes and looks) and that
search's outcome classifies the original veto likely_wrong/likely_right/ambiguous; no re-ask -> uncontested
(lazy). No maturity adjustment. Off => byte-identical to Slice 1."
```

---

### Task 3: Receipt + whole-slice green + handoff (STOP at the review gate)

**Files:** Create `docs/handoffs/2026-06-20-slice3a-handoff.md`.

- [ ] **Step 1: Green + ruff.**

```bash
MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -m unittest \
  tests.test_veto_ledger tests.test_veto_ledger_seams tests.test_routing_priors \
  tests.test_routing_priors_veto_seam tests.test_routing_observation -v
/home/rohit/maez/.venv/bin/python -m ruff check core/routing/veto_ledger.py daemon/maez_daemon.py
```

- [ ] **Step 2: Off byte-identical confirm** — grep each seam: with `MAEZ_VETO_LEDGER` unset, no `VetoLedger` constructed, no override, no record/classify.

- [ ] **Step 3: Handoff** — Codex anchors: (1) off=byte-identical; (2) `uncontested` ≠ `likely_right` (silence weak, lazy, no scheduler); (3) `likely_right` requires the re-ask's own reach to ALSO fail (`unusable`/`empty_but_honest`); (4) exact-repeat-only v0 (utterance-hash; rephrase invisible; no keyword/regex); (5) the override lifts ONCE per window (no loop) + serves an explicit re-ask; (6) no maturity adjustment (3a records only); (7) untouched: strict honesty gate, S7, Telegram, time-sense, cockpit-reauth. **Owner-breath:** restart `maez` (needs `MAEZ_ROUTING_PRIORS_ENABLED=1` already live), set `MAEZ_VETO_LEDGER=1`; trigger a veto (a "today's signals" turn), then exact-repeat it within the window; paste `sqlite3 ~/maez/memory/veto_ledger.db "SELECT class_id, prior_confidence, reask_outcome_quality, classification FROM veto_events;"` — expect the veto row + the re-ask's outcome + an honest classification. No autonomous check.

- [ ] **Step 4: Commit handoff. STOP** (no merge/restart — owner-sovereign).

---

## Self-Review

**Spec coverage:** veto-event ledger w/ prior snapshot → Task 1 (`record_veto`) + seam 1; **record only a veto that suppressed a REAL search (must-fix 1)** → `_would_web_search` guard (Task 2 Step 4/5); exact-repeat override (lift once) → seam 2 + the `_override_event_id` guard (no loop: an open event is found once, then classified→closed); **classify only from a REAL second outcome, never a default (must-fix 2)** → `_routing_turn_outcome_quality` captured at the actual search, classify gated on `is not None` (Task 2 Step 6); four-way honest classification incl. `uncontested` distinct + lazy → Task 1 (`_resolve_expired`, `classify_outcome`); `likely_right` requires reach-also-failed → `_REACH_FAILED` mapping; exact-repeat-only v0 → `find_open_for_class` keys on the exact-hash class from `classify_request_class`; off=byte-identical → flag guards every seam (Task 2 Step 7); shadow-for-maturity (no threshold change) → no maturity code in 3a; window-not-a-trust-knob → `_REASK_WINDOW_S` named + Task 0 Step 4. OUT (3b/3c) untouched. Covered.

**Placeholder scan:** seam 3 binds the writeback's REAL outcome var (Task 0 Step 3 pins the name) into `_routing_turn_outcome_quality` — the dangerous `_q in dir() else "structured_evidence"` default is removed; classification only fires when a real outcome exists. `_cls`/`_override_event_id`/`_ledger`/`_routing_turn_outcome_quality` all initialized before use (must-fix 3). No TBD/TODO; all code concrete.

**Type consistency:** `VetoLedger.record_veto(*, class_id, tool, prior_n, prior_success_rate, prior_confidence, turn_id, surface, now) -> str`; `find_open_for_class(class_id, tool, *, now, within_s) -> VetoEvent|None`; `attach_reask_outcome(event_id, *, reask_turn_id, reask_outcome_quality) -> str`; `classify_outcome(str) -> str`; `VetoEvent` fields consistent across Task 1 ↔ Task 2 usage. The seam reads `_prior.n/.success_rate/.confidence` — matches `RoutingPrior(request_class, chosen_tool, n, success_rate, confidence)` from Slice 1.
