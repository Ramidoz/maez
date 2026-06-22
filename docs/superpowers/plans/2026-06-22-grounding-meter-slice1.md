# Grounding Meter (reply-relative) — Coherence Slice 1 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a reply-relative grounding meter — `reply_grounding = grounded_sentences / total_sentences` — computed in `check_groundedness`, flowing through BOTH witness pipes (focused store + `RecallOutcome` record/log), as a pure content-light instrument that changes no behavior.

**Architecture:** Compute three numbers in `check_groundedness` (a sentence is grounded iff it carries a valid `[E#]`); carry them on `GroundednessVerdict` via **defaulted** fields (no constructor breaks); persist all three to the `focused_cognition_runs` store via an idempotent `ALTER TABLE` migration; thread the rate onto the `RecallOutcome` dataclass + `_log_recall_outcome` line (the live witness). No flag, no behavior gate, no reply text persisted.

**Tech Stack:** Python 3, `unittest` (NOT pytest), sqlite3, the existing `focused_cognition` / `recall_outcome` modules.

**Test runner (EVERY test step):** `MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -m unittest tests.<module> -v`

**Git hygiene:** Work on a branch/worktree (NO checkout/switch/reset/rebase mid-task; verify "On branch X" after each commit; STOP if detached). `main` is local-only, NO push. No `## Predicted effect` needed (zero behavior change); commits note "measurement-only". Commits end with `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.

**Spec:** [docs/superpowers/specs/2026-06-21-grounding-meter-slice1-design.md](../specs/2026-06-21-grounding-meter-slice1-design.md).

---

## File Structure
- **Modify `core/routing/focused_cognition.py`** — `GroundednessVerdict` (+3 defaulted fields), a local sentence splitter + grounded check, the `reply_grounding` computation in `check_groundedness`, the store `_init_schema` migration + `record()` threading.
- **Modify `core/routing/recall_outcome.py`** — `RecallOutcome` (+`reply_grounding` optional field).
- **Modify `daemon/maez_daemon.py`** — thread `_rk_reply_grounding` from the verdict into the `RecallOutcome` construction; add it to `_log_recall_outcome`.
- **Create `tests/test_grounding_meter.py`** — verdict defaults/compat, metric correctness, store migration/columns/record.
- **Create `tests/test_grounding_meter_seam.py`** — `RecallOutcome` field, `_log_recall_outcome` emission, daemon threading assertion.
- **Create `docs/proof/2026-06-22-grounding-meter-task0.md`** — constructor inventory.
- **Create `docs/handoffs/2026-06-22-grounding-meter-handoff.md`** — Codex cross-lane handoff.

---

## Task 0: Constructor inventory (prove the defaults — no code)

**Files:** Create `docs/proof/2026-06-22-grounding-meter-task0.md`

- [ ] **Step 1: Enumerate every `GroundednessVerdict(` and `RecallOutcome(` constructor**

Run:
```bash
cd <worktree>
echo "=== GroundednessVerdict constructors ==="; grep -rn "GroundednessVerdict(" core/ daemon/ tests/ --include=*.py
echo "=== RecallOutcome constructors ==="; grep -rn "RecallOutcome(" core/ daemon/ tests/ --include=*.py
```

- [ ] **Step 2: Classify each call site**

For EACH `GroundednessVerdict(` site, record whether it is **positional** (e.g. `GroundednessVerdict("grounded", 1.0, [])`) or keyword. Confirm: adding the 3 new fields **as trailing defaulted fields** (`reply_grounding=0.0`, `grounded_sentences=0`, `total_sentences=0`) leaves every existing positional/keyword call valid (since `verdict, citation_coverage, unmatched` stay first and the new fields default). Do the same for `RecallOutcome(` vs the new trailing `reply_grounding: float | None = None`.

**STOP condition:** if any existing constructor passes MORE than the current 3 positional args to `GroundednessVerdict` (so a new trailing field would collide), or constructs `RecallOutcome` positionally past its current defaulted tail, STOP and report — the defaults are not safe as-specified and the field order must be reconsidered.

- [ ] **Step 3: Write + commit the proof**

Write the inventory (each site: file:line, positional/keyword, safe-under-defaults yes/no) + the verdict (ALL SAFE or STOP) to `docs/proof/2026-06-22-grounding-meter-task0.md`.
```bash
git add docs/proof/2026-06-22-grounding-meter-task0.md
git commit --no-verify -m "docs(proof): grounding-meter Task 0 — constructor inventory (defaults proven safe)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```
If STOP: commit the proof recording the STOP + reason, and HALT (report to owner).

---

## Task 1: The metric + defaulted verdict fields

**Files:** Modify `core/routing/focused_cognition.py`; Create `tests/test_grounding_meter.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_grounding_meter.py`:
```python
import unittest

from core.routing.focused_cognition import (
    GroundednessVerdict,
    check_groundedness,
    FocusedResult,
    WorkingSet,
    EvidenceItem,
)


def _ws(n):
    items = tuple(
        EvidenceItem(local_label=f"E{i+1}", source_type="memory_evidence",
                     text=f"item {i+1}", durable_id=f"d{i+1}")
        for i in range(n)
    )
    # WorkingSet requires the fields used by check_groundedness (.items)
    return WorkingSet(items=items, owner_question="q", ordered_evidence_text="",
                      working_set_chars=0, working_set_tokens_est=0)


def _result(reply, cited):
    return FocusedResult(reply=reply, cited_ids=list(cited), working_set_chars=0)


class TestGroundednessVerdictCompat(unittest.TestCase):
    def test_existing_positional_constructor_still_builds(self):
        v = GroundednessVerdict("grounded", 1.0, [])
        self.assertEqual(v.verdict, "grounded")
        self.assertEqual(v.reply_grounding, 0.0)
        self.assertEqual(v.grounded_sentences, 0)
        self.assertEqual(v.total_sentences, 0)


class TestReplyGrounding(unittest.TestCase):
    def test_denominator_is_reply_not_working_set(self):
        # 16-item set, a 2-sentence reply both validly cited -> 1.0 (NOT 0.125)
        ws = _ws(16)
        r = _result("The sky is blue [E1]. It is sunny [E2].", {"E1", "E2"})
        v = check_groundedness(r, ws)
        self.assertEqual(v.total_sentences, 2)
        self.assertEqual(v.grounded_sentences, 2)
        self.assertEqual(v.reply_grounding, 1.0)
        self.assertEqual(v.citation_coverage, 2 / 16)  # old metric UNCHANGED

    def test_uncited_self_narrative_is_zero(self):
        ws = _ws(16)
        r = _result("I am the engine keeping the lights on. I hold the space.", set())
        v = check_groundedness(r, ws)
        self.assertEqual(v.grounded_sentences, 0)
        self.assertEqual(v.reply_grounding, 0.0)

    def test_invalid_citation_not_grounded(self):
        ws = _ws(2)
        r = _result("A real fact [E1]. A hallucinated one [E99].", {"E1", "E99"})
        v = check_groundedness(r, ws)
        self.assertEqual(v.grounded_sentences, 1)   # only the [E1] sentence
        self.assertEqual(v.total_sentences, 2)
        self.assertEqual(v.reply_grounding, 0.5)
        self.assertIn("E99", v.unmatched)           # existing path UNCHANGED

    def test_deterministic(self):
        ws = _ws(3)
        r = _result("Fact one [E1]. Fact two [E2].", {"E1", "E2"})
        self.assertEqual(check_groundedness(r, ws).reply_grounding,
                         check_groundedness(r, ws).reply_grounding)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run to verify it fails**

Run: `MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -m unittest tests.test_grounding_meter -v`
Expected: FAIL — `AttributeError: 'GroundednessVerdict' object has no attribute 'reply_grounding'` (and the metric assertions fail).

NOTE: verify `WorkingSet` / `EvidenceItem` / `FocusedResult` constructor kwargs match the real dataclasses (read their definitions ~lines 270-415). If a required field is missing in the test helpers, add it minimally — do not change the dataclasses.

- [ ] **Step 3: Add the defaulted fields + the metric**

In `core/routing/focused_cognition.py`, extend `GroundednessVerdict` (currently at ~line 432):
```python
@dataclass(frozen=True)
class GroundednessVerdict:
    verdict: str
    citation_coverage: float
    unmatched: list[str]
    reply_grounding: float = 0.0
    grounded_sentences: int = 0
    total_sentences: int = 0
```

Add two helpers near `_CITE_RE` (which is `re.compile(r"\[E(\d+)\]")` at line 113) — place them just above `check_groundedness`:
```python
_REPLY_SENTENCE_RE = re.compile(r"[^.!?]+[.!?]?")


def _reply_sentences(reply: str) -> list[str]:
    """Deterministic sentence split; keeps inline [E#] markers with their sentence."""
    return [s.strip() for s in _REPLY_SENTENCE_RE.findall(reply or "") if s.strip()]


def _sentence_is_grounded(sentence: str, valid_labels: set[str]) -> bool:
    return any(f"E{m.group(1)}" in valid_labels for m in _CITE_RE.finditer(sentence))
```

In `check_groundedness` (line ~1475), after `coverage = ...` and before the `if not cited:` block, add:
```python
    sentences = _reply_sentences(result.reply)
    total_sentences = len(sentences)
    grounded_sentences = sum(
        1 for s in sentences if _sentence_is_grounded(s, valid_labels)
    )
    reply_grounding = grounded_sentences / total_sentences if total_sentences else 0.0
```
And extend the return:
```python
    return GroundednessVerdict(
        verdict=verdict,
        citation_coverage=coverage,
        unmatched=unmatched,
        reply_grounding=reply_grounding,
        grounded_sentences=grounded_sentences,
        total_sentences=total_sentences,
    )
```

- [ ] **Step 4: Run to verify it passes**

Run: `MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -m unittest tests.test_grounding_meter -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Run the existing focused-cognition tests (existing-outputs-unchanged guard)**

Run: `MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -m unittest tests.test_memory_integrity_invariant -v 2>&1 | tail -5`
Expected: PASS (the positional `GroundednessVerdict("grounded", 1.0, [])` mocks still build; nothing existing changed). If a focused-cognition unit-test module exists, run it too.

- [ ] **Step 6: Commit**

```bash
git add core/routing/focused_cognition.py tests/test_grounding_meter.py
git commit --no-verify -m "feat(grounding-meter): reply_grounding in check_groundedness (defaulted verdict fields)

Measurement-only: reply_grounding = grounded_sentences/total_sentences (a sentence is grounded iff it
carries a valid [E#]). New GroundednessVerdict fields default (0.0/0/0) so existing constructors are
unbroken; citation_coverage/verdict/unmatched unchanged.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2: Focused store — 3 columns + idempotent migration + record threading

**Files:** Modify `core/routing/focused_cognition.py`; Modify `tests/test_grounding_meter.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_grounding_meter.py`:
```python
import tempfile, os
from pathlib import Path
from core.routing.focused_cognition import FocusedCognitionStore


class TestStoreColumns(unittest.TestCase):
    def _store(self):
        d = tempfile.mkdtemp()
        return FocusedCognitionStore(db_path=Path(d) / "fc.db")

    def test_record_persists_grounding_numbers(self):
        store = self._store()
        ws = _ws(3)
        r = _result("Fact [E1]. Filler.", {"E1"})
        v = check_groundedness(r, ws)
        rid = store.record(surface="telegram_surface", chat_id=None, working_set=ws,
                           result=r, verdict=v, legacy_prompt_chars=None,
                           fallback_reason=None, routing_observation_id=None)
        row = store.get(rid)
        self.assertAlmostEqual(row["reply_grounding"], 0.5)
        self.assertEqual(row["grounded_sentences"], 1)
        self.assertEqual(row["total_sentences"], 2)
        # content-light: no reply text column
        self.assertNotIn("Fact", " ".join(str(row[k]) for k in row.keys()))

    def test_migration_idempotent(self):
        d = tempfile.mkdtemp()
        p = Path(d) / "fc.db"
        FocusedCognitionStore(db_path=p)   # creates + migrates
        FocusedCognitionStore(db_path=p)   # re-open: migration must not error
        self.assertTrue(p.exists())
```

- [ ] **Step 2: Run to verify it fails**

Run: `MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -m unittest tests.test_grounding_meter -v`
Expected: FAIL — `sqlite3.OperationalError: no such column: reply_grounding` (or KeyError on row access).

- [ ] **Step 3: Add the migration + record threading**

In `FocusedCognitionStore._init_schema` (line ~1515), AFTER the `CREATE TABLE IF NOT EXISTS focused_cognition_runs (...)` execute block but still inside `with self._connect() as conn: with conn:`, add an idempotent column migration:
```python
                for _col, _coltype in (
                    ("reply_grounding", "REAL"),
                    ("grounded_sentences", "INTEGER"),
                    ("total_sentences", "INTEGER"),
                ):
                    try:
                        conn.execute(
                            f"ALTER TABLE focused_cognition_runs ADD COLUMN {_col} {_coltype}"
                        )
                    except sqlite3.OperationalError:
                        pass  # column already exists — idempotent
```

In `record()` (the `row = {...}` dict, ~line 1565), add three entries (numbers only, never reply text):
```python
            "reply_grounding": (
                float(verdict.reply_grounding) if verdict is not None else None
            ),
            "grounded_sentences": (
                int(verdict.grounded_sentences) if verdict is not None else None
            ),
            "total_sentences": (
                int(verdict.total_sentences) if verdict is not None else None
            ),
```
(The INSERT builds columns from `row.keys()`, so these flow automatically.)

- [ ] **Step 4: Run to verify it passes**

Run: `MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -m unittest tests.test_grounding_meter -v`
Expected: PASS (all Task-1 + Task-2 tests).

- [ ] **Step 5: Commit**

```bash
git add core/routing/focused_cognition.py tests/test_grounding_meter.py
git commit --no-verify -m "feat(grounding-meter): persist 3 grounding numbers to focused store (idempotent migration)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 3: RecallOutcome field + daemon threading + live log

**Files:** Modify `core/routing/recall_outcome.py`, `daemon/maez_daemon.py`; Create `tests/test_grounding_meter_seam.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_grounding_meter_seam.py`:
```python
import os, unittest
from unittest import mock

os.environ.setdefault("MAEZ_IPHONE_INGEST_TOKEN", "dummy-test")
os.environ.setdefault("MAEZ_SECRETS_DISABLE_NEW_LOADER", "1")

from core.routing.recall_outcome import RecallOutcome, OutcomeClass, ReplyPath


def _rec(**kw):
    base = dict(mode="recall_triad", turn_kind="ordinary",
                outcome_class=OutcomeClass.ORDINARY_ANSWERED, denial_kind="na",
                had_confirmed=False, citation_coverage=0.1, receipt_or_na="not_consulted",
                latency_ms=10, focused_elapsed_ms=5, reply_path=ReplyPath.FOCUSED)
    base.update(kw)
    return RecallOutcome(**base)


class TestRecallOutcomeField(unittest.TestCase):
    def test_reply_grounding_defaults_none(self):
        self.assertIsNone(_rec().reply_grounding)   # existing constructors unaffected

    def test_reply_grounding_set(self):
        self.assertEqual(_rec(reply_grounding=0.75).reply_grounding, 0.75)


class TestLogEmitsReplyGrounding(unittest.TestCase):
    def test_log_line_carries_reply_grounding(self):
        import daemon.maez_daemon as d
        with self.assertLogs(d.logger.name) as logs:
            d._log_recall_outcome(rec=_rec(reply_grounding=0.5))
        self.assertTrue(any("reply_grounding=0.5" in m for m in logs.output))


class TestDaemonThreadsBothPipes(unittest.TestCase):
    def test_daemon_threads_reply_grounding_to_record_and_outcome(self):
        import inspect, daemon.maez_daemon as d
        src = inspect.getsource(d)
        # verdict -> _rk_reply_grounding -> RecallOutcome(reply_grounding=...)
        self.assertIn("_rk_reply_grounding", src)
        self.assertIn("reply_grounding=_rk_reply_grounding", src)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run to verify it fails**

Run: `MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -m unittest tests.test_grounding_meter_seam -v`
Expected: FAIL — `TypeError: __init__() got an unexpected keyword argument 'reply_grounding'` and the source-threading assertions fail.

- [ ] **Step 3: Add the RecallOutcome field**

In `core/routing/recall_outcome.py`, add to the `RecallOutcome` dataclass among the DEFAULTED fields (after `citation_coverage` is non-default, so place it with the trailing defaulted block, e.g. after `ack_emit_ms`):
```python
    reply_grounding: float | None = None
```
(Keep `schema_version` as `recall_outcome.v2` — purely-additive optional field.)

- [ ] **Step 4: Thread it through the daemon**

In `daemon/maez_daemon.py`:
- Next to `_rk_coverage = None` at line ~6649, add: `_rk_reply_grounding = None`
- After `_rk_coverage = getattr(_focused_verdict, "citation_coverage", None)` at line ~7008, add: `_rk_reply_grounding = getattr(_focused_verdict, "reply_grounding", None)`
- Next to the second `_rk_coverage = None` at line ~7389, add: `_rk_reply_grounding = None`
- In the `RecallOutcome(...)` construction at line ~7478, next to `citation_coverage=_rk_coverage,`, add: `reply_grounding=_rk_reply_grounding,`

- [ ] **Step 5: Add it to `_log_recall_outcome`**

In `_log_recall_outcome` (line ~1336): add `reply_grounding=%s ` to the format string (e.g. right after `citation_coverage=%s `), and add the matching arg in order: `format_log_value(getattr(rec, "reply_grounding", None)),` (place it right after the `format_log_value(rec.citation_coverage),` arg to match position).

- [ ] **Step 6: Run to verify it passes**

Run: `MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -m unittest tests.test_grounding_meter_seam tests.test_grounding_meter -v`
Expected: PASS (all).

- [ ] **Step 7: Regression — existing recall-outcome + focused tests**

Run: `MAEZ_CONFIG=/home/rohit/maez/config /home/rohit/maez/.venv/bin/python -B -m unittest tests.test_memory_integrity_invariant -v 2>&1 | tail -5`
Expected: PASS. Also grep-confirm the new field name matches everywhere (`grep -rn "reply_grounding" core/ daemon/`).

- [ ] **Step 8: Commit**

```bash
git add core/routing/recall_outcome.py daemon/maez_daemon.py tests/test_grounding_meter_seam.py
git commit --no-verify -m "feat(grounding-meter): thread reply_grounding onto RecallOutcome + _log_recall_outcome (live witness)

Measurement-only. The focused store holds all 3 numbers; the RecallOutcome record + log carry the rate
only (the live witness mouth). schema_version stays recall_outcome.v2 (additive optional field).

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 4: Handoff + STOP for Codex cross-lane

**Files:** Create `docs/handoffs/2026-06-22-grounding-meter-handoff.md`

- [ ] **Step 1: Write the handoff**

Content: branch tip; Task-0 inventory result (defaults proven safe); what changed (the metric, the two pipes, defaulted fields); the invariants held (citation_coverage/verdict/unmatched/reply-text/fallback unchanged; content-light; no flag/behavior); Codex anchors to verify — (a) defaults break no constructor, (b) both pipes carry it (store all 3, record/log the rate), (c) no reply text persisted anywhere, (d) `citation_coverage` formula + `verdict.verdict` untouched, (e) migration idempotent; and the owner-breath (restart `maez`, observe a few focused turns, confirm `recall_outcome … reply_grounding=` appears + reads sanely low on diary-recite turns; record the baseline).

- [ ] **Step 2: Commit + STOP**

```bash
git add docs/handoffs/2026-06-22-grounding-meter-handoff.md
git commit --no-verify -m "docs(handoff): grounding-meter Slice 1 — Codex cross-lane anchors + owner breath

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```
STOP. Do NOT merge/restart/witness. Report branch tip + verification outputs + the owner-breath. Hold for `merge it`.

---

## Self-Review
**Spec coverage:** reply_grounding metric (Task 1) ✓; keep citation_coverage + verdict.verdict (Task 1, asserted) ✓; defaulted verdict fields / no constructor break (Task 0 inventory + Task 1 compat test) ✓; both pipes — store all 3 (Task 2) + RecallOutcome rate + _log_recall_outcome (Task 3) ✓; content-light no reply text (Task 2 + Task 3 asserts) ✓; idempotent migration (Task 2) ✓; deterministic (Task 1) ✓; no flag / no behavior gate (no flag added anywhere) ✓; segmented-by-turn_kind is a READING discipline (no code) — covered in handoff/spec ✓; witness-forward baseline (handoff owner-breath) ✓.

**Placeholder scan:** every code step has concrete code; the one NOTE (verify dataclass kwargs) is an explicit verification with a concrete fallback, not a TBD.

**Type consistency:** `GroundednessVerdict.reply_grounding/grounded_sentences/total_sentences` consistent across Tasks 1/2; `RecallOutcome.reply_grounding` consistent Task 3 def↔daemon↔log↔test; `_rk_reply_grounding` consistent across the four daemon seams; helper names `_reply_sentences`/`_sentence_is_grounded`/`_REPLY_SENTENCE_RE` consistent Task 1.
