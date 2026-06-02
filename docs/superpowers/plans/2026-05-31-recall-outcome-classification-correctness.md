# Recall-Outcome Classification Correctness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a third honest outcome state `ANSWERED_MIXED_SUPPORT` and recognize honest dated-absence phrasings — so the recall scoreboard stops mis-scoring good behavior without ever claiming more than the citation labels prove.

**Architecture:** Classification-only. A new `citation_support(...) -> grounded|mixed|ungrounded` helper sits *beside* the untouched strict `cites_confirmed_memory_context`. `classify_outcome` gains an additive `cited_mixed_support: bool = False`. The daemon and both eval consumers derive grounded+mixed from the one helper and thread the turn's kind. The Fix-3 matcher learns honest phrasings with an anti-laundering `" but "` guard. Docs' A5 benefit-reading distinguishes mixed-in-2b ("observe, not rescue") from mixed-in-benchmark ("does not clear categorical grounding").

**Tech Stack:** Python 3.14, **`unittest`** (the repo runner — `.venv` has NO pytest). Runner forms: `.venv/bin/python -m unittest tests.test_recall_outcome` / `…tests.test_recall_outcome.ClassName.method -v`.

**Spec:** [docs/superpowers/specs/2026-05-31-recall-outcome-classification-correctness-design.md](../specs/2026-05-31-recall-outcome-classification-correctness-design.md)

**Process:** Codex switchboard (six-agent pre-code + 7+3). Claude cross-verifies every diff, runs suites independently, fires the coverage panel before merge on the legacy baseline (recall off). This plan IS the Codex handoff.

**Hard invariants (verify at the end, every task preserves them):**
- `cites_confirmed_memory_context` — **byte-identical**, existing tests untouched.
- `classify_outcome` with `cited_mixed_support` omitted — **byte-identical** behavior.
- `is_false_absence` — **untouched**.
- No synthesis/prompt/routing/recall-stack edits; recall flag stays off.
- `cited_confirmed_memory_context` (the field both eval scripts feed to `assert_probe_result`) stays the **strict** value → `grounded_categorical` cannot be cleared by `mixed` (§6(b) holds by construction).

---

## Task 1: New `ANSWERED_MIXED_SUPPORT` + `citation_support` + additive `classify_outcome`

**Files:**
- Modify: `core/routing/recall_outcome.py` (enum `:18-28`, `classify_outcome` `:95-140`, add `citation_support` after `cites_confirmed_memory_context` `:180`)
- Test: `tests/test_recall_outcome.py`

- [ ] **Step 1: Write the failing tests**

Add a new class to `tests/test_recall_outcome.py` (reuse the `SimpleNamespace` style; the `GroundedContextHelperTest._item(label, source_type, confirmed)` helper already exists — a dialogue item is `("E7", "dialogue_anchor", None)`):

```python
from core.routing.recall_outcome import citation_support


class CitationSupportTest(unittest.TestCase):
    def _item(self, label, source_type, confirmed):
        return SimpleNamespace(
            local_label=label,
            source_type=source_type,
            temporal_provenance={"confirmed": confirmed} if confirmed is not None else None,
        )

    def test_all_confirmed_memory_is_grounded(self):
        r = SimpleNamespace(cited_ids=["E1", "E2"])
        ws = SimpleNamespace(items=[self._item("E1", "memory_context", True),
                                    self._item("E2", "memory_context", True)])
        self.assertEqual(citation_support(r, ws, turn_kind="both"), "grounded")
        self.assertEqual(citation_support(r, ws, turn_kind="dated"), "grounded")

    def test_both_memory_plus_dialogue_is_mixed(self):
        r = SimpleNamespace(cited_ids=["E1", "E7"])
        ws = SimpleNamespace(items=[self._item("E1", "memory_context", True),
                                    self._item("E7", "dialogue_anchor", None)])
        self.assertEqual(citation_support(r, ws, turn_kind="both"), "mixed")

    def test_dated_memory_plus_dialogue_is_ungrounded(self):
        r = SimpleNamespace(cited_ids=["E1", "E7"])
        ws = SimpleNamespace(items=[self._item("E1", "memory_context", True),
                                    self._item("E7", "dialogue_anchor", None)])
        self.assertEqual(citation_support(r, ws, turn_kind="dated"), "ungrounded")

    def test_both_dialogue_only_is_ungrounded(self):
        r = SimpleNamespace(cited_ids=["E7"])
        ws = SimpleNamespace(items=[self._item("E1", "memory_context", True),
                                    self._item("E7", "dialogue_anchor", None)])
        self.assertEqual(citation_support(r, ws, turn_kind="both"), "ungrounded")

    def test_both_unconfirmed_memory_is_ungrounded(self):
        r = SimpleNamespace(cited_ids=["E1"])
        ws = SimpleNamespace(items=[self._item("E1", "memory_context", False)])
        self.assertEqual(citation_support(r, ws, turn_kind="both"), "ungrounded")

    def test_both_disallowed_source_is_ungrounded(self):
        r = SimpleNamespace(cited_ids=["E1", "E5"])
        ws = SimpleNamespace(items=[self._item("E1", "memory_context", True),
                                    self._item("E5", "memory_evidence", True)])
        self.assertEqual(citation_support(r, ws, turn_kind="both"), "ungrounded")

    def test_both_unmatched_label_is_ungrounded(self):
        r = SimpleNamespace(cited_ids=["E1", "E9"])
        ws = SimpleNamespace(items=[self._item("E1", "memory_context", True)])
        self.assertEqual(citation_support(r, ws, turn_kind="both"), "ungrounded")

    def test_turn_kind_omitted_never_mixed(self):
        r = SimpleNamespace(cited_ids=["E1", "E7"])
        ws = SimpleNamespace(items=[self._item("E1", "memory_context", True),
                                    self._item("E7", "dialogue_anchor", None)])
        self.assertEqual(citation_support(r, ws), "ungrounded")
```

Add to the existing `ClassifyOutcomeTest` class:

```python
    def test_mixed_support_when_flagged(self):
        oc = classify_outcome(
            mode="recall_triad", turn_kind="both", answered=True, receipt="consulted",
            denial_kind="na", had_confirmed=True, cited_grounded_context=False,
            unmatched_citations=0, cited_mixed_support=True,
        )
        self.assertIs(oc, OutcomeClass.ANSWERED_MIXED_SUPPORT)

    def test_grounded_wins_over_mixed(self):
        oc = classify_outcome(
            mode="recall_triad", turn_kind="both", answered=True, receipt="consulted",
            denial_kind="na", had_confirmed=True, cited_grounded_context=True,
            unmatched_citations=0, cited_mixed_support=True,
        )
        self.assertIs(oc, OutcomeClass.ANSWERED_GROUNDED)

    def test_mixed_with_unmatched_is_ungrounded(self):
        oc = classify_outcome(
            mode="recall_triad", turn_kind="both", answered=True, receipt="consulted",
            denial_kind="na", had_confirmed=True, cited_grounded_context=False,
            unmatched_citations=1, cited_mixed_support=True,
        )
        self.assertIs(oc, OutcomeClass.ANSWERED_UNGROUNDED)
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/python -m unittest tests.test_recall_outcome.CitationSupportTest tests.test_recall_outcome.ClassifyOutcomeTest -v`
Expected: `CitationSupportTest` ERRORs (`citation_support` not importable); the two mixed `ClassifyOutcomeTest` cases ERROR (`cited_mixed_support` unexpected kwarg).

- [ ] **Step 3: Add the enum value**

In `core/routing/recall_outcome.py`, after line 20 (`ANSWERED_UNGROUNDED = "answered_ungrounded"`), add:

```python
    ANSWERED_MIXED_SUPPORT = "answered_mixed_support"
```

- [ ] **Step 4: Add `citation_support` (leave `cites_confirmed_memory_context` untouched)**

Append after `cites_confirmed_memory_context` (after `:180`):

```python
def citation_support(result, working_set, turn_kind: str = "dated") -> str:
    """Content-free three-state citation-support classification.

    "grounded"   - exactly when cites_confirmed_memory_context(result, working_set)
                   is True (every cited label is a date-confirmed memory_context).
    "mixed"      - BOTH-SHAPED turns only: >=1 confirmed memory_context cited, all
                   labels valid, every non-memory citation is a dialogue_anchor.
                   Confirmed memory present, but labels cannot prove the dated facts
                   were carried by memory alone. NEVER on a pure-dated turn.
    "ungrounded" - anything else.
    """
    if cites_confirmed_memory_context(result, working_set):
        return "grounded"
    if turn_kind != "both":
        return "ungrounded"
    cited = {str(label) for label in (getattr(result, "cited_ids", None) or [])}
    if not cited:
        return "ungrounded"
    items_by_label = {
        str(getattr(item, "local_label", "")): item
        for item in (getattr(working_set, "items", ()) or ())
    }
    if not cited.issubset(items_by_label):
        return "ungrounded"
    cited_items = [items_by_label[label] for label in cited]

    def _is_confirmed_memory_context(item) -> bool:
        if getattr(item, "source_type", None) != "memory_context":
            return False
        provenance = getattr(item, "temporal_provenance", None) or {}
        return bool(provenance.get("confirmed"))

    if not any(_is_confirmed_memory_context(item) for item in cited_items):
        return "ungrounded"
    for item in cited_items:
        if _is_confirmed_memory_context(item):
            continue
        if getattr(item, "source_type", None) == "dialogue_anchor":
            continue  # allowed supplement on a both-shaped turn
        return "ungrounded"
    return "mixed"
```

- [ ] **Step 5: Make `classify_outcome` additive**

In `classify_outcome` add the parameter (after `asserts_absence: bool = False,` at `:105`):

```python
    cited_mixed_support: bool = False,
```

Replace the answered branch (`:129-134`) with:

```python
    if answered:
        if mode == "legacy":
            return OutcomeClass.ANSWERED_UNVERIFIABLE
        if cited_grounded_context and unmatched_citations == 0:
            return OutcomeClass.ANSWERED_GROUNDED
        if cited_mixed_support and unmatched_citations == 0:
            return OutcomeClass.ANSWERED_MIXED_SUPPORT
        return OutcomeClass.ANSWERED_UNGROUNDED
```

- [ ] **Step 6: Run to verify pass**

Run: `.venv/bin/python -m unittest tests.test_recall_outcome -v`
Expected: OK — all new tests pass AND every pre-existing test (the `cites_confirmed_memory_context` and `classify_outcome` cases prove byte-identical defaults).

- [ ] **Step 7: Commit**

```bash
git add core/routing/recall_outcome.py tests/test_recall_outcome.py
git commit -m "feat(recall-outcome): add ANSWERED_MIXED_SUPPORT + citation_support (additive, strict primitive untouched)"
```

---

## Task 2: Daemon wiring + daemon-shaped RED test

**Files:**
- Modify: `daemon/maez_daemon.py:4644-4651` (import + derive), `:5008-5022` (pass the bool)
- Test: `tests/test_memory_integrity_invariant.py` — add beside the existing recall-outcome daemon tests, in the class containing `test_grounded_dated_answer_with_absence_phrase_stays_answered` (`:1327`). Reuse its helpers: `_build_daemon_for_handle_message()`, `_handle_message_mock_stack`, `_recall_outcome_lines(logs)`, and the transcript shape.

- [ ] **Step 1: Write the daemon-shaped failing test**

Model it exactly on `test_grounded_dated_answer_with_absence_phrase_stays_answered` (`:1327`). The difference: make the turn **both-shaped** (dated transcript + **non-empty `chat_history`**, which produces the `dialogue_anchor`) and patch the focused result to cite **both** the confirmed memory (`E1`) and the dialogue anchor (`E2`). The test self-checks the both-shaping precondition by asserting `turn_kind=both` in the log line.

```python
    def test_both_shaped_memory_plus_dialogue_is_mixed_support(self):
        from daemon import maez_daemon
        from core.routing.focused_cognition import FocusedResult, GroundednessVerdict

        captured = {}
        daemon = self._build_daemon_for_handle_message()
        transcript = (
            "[memory context]\n"
            '<RECALLED id="m-apr27" date_match="exact_date">'
            "April 27 infrastructure incident was recorded."
            "</RECALLED>"
        )
        # Cites confirmed memory (E1) AND the dialogue anchor (E2) -> mixed on a both-shaped turn.
        focused_result = FocusedResult(
            reply="Around April 27 we were on the incident [E1]; we'd just been talking about it [E2].",
            cited_ids=["E1", "E2"],
            working_set_chars=10,
        )
        with self.assertLogs("maez", level="INFO") as logs:
            with self._handle_message_mock_stack(maez_daemon, captured), mock.patch.dict(
                os.environ, {"MAEZ_RECALL_TRIAD_ENABLED": "1"}, clear=False
            ), mock.patch(
                "core.routing.focused_cognition.focused_synthesize",
                return_value=focused_result,
            ), mock.patch(
                "core.routing.focused_cognition.check_groundedness",
                return_value=GroundednessVerdict("grounded", 1.0, []),
            ):
                maez_daemon.MaezDaemon.handle_message(
                    daemon,
                    "remind me what we were doing around April 27?",
                    chat_id="c1",
                    source="telegram",
                    transcript=transcript,
                    chat_history=[
                        {"role": "user", "content": "we were deep in the april 27 incident"},
                        {"role": "assistant", "content": "right, the infra incident"},
                    ],
                )

        line = self._recall_outcome_lines(logs)[-1]
        self.assertIn("turn_kind=both", line)
        self.assertIn("outcome_class=answered_mixed_support", line)
```

> If `turn_kind=both` does not appear, the both-shaping precondition (`_date_addressed_turn and _dialogue_needs_or_uncertain`) was not met — adjust the prompt/`chat_history` until it is, before touching production code. If the real working-set builder labels the dialogue anchor something other than `E2`, cite the actual label it assigns (inspect the constructed working set via the captured state) — do not hardcode a label the builder doesn't produce.

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/python -m unittest tests.test_memory_integrity_invariant -v -k mixed_support`
Expected: FAIL — `outcome_class=answered_ungrounded` today (daemon hardcodes the strict grounded bool and passes no mixed bool). (If instead it fails on the `turn_kind=both` assertion, fix the precondition first per the note above.)

- [ ] **Step 3: Wire `citation_support` at the call site**

Replace `daemon/maez_daemon.py:4644-4651`:

```python
                        from core.routing.recall_outcome import (
                            citation_support as _citation_support,
                        )

                        _rk_support = _citation_support(
                            _focused_result,
                            _focused_working_set,
                            turn_kind=(
                                "both"
                                if (_date_addressed_turn and _dialogue_needs_or_uncertain)
                                else "dated"
                            ),
                        )
                        _rk_cited_grounded = _rk_support == "grounded"
                        _rk_cited_mixed = _rk_support == "mixed"
```

`_rk_cited_grounded` keeps its exact current meaning (strict grounded), so the absence/answered logic at `:4991-5006` is unchanged. Initialize `_rk_cited_mixed = False` wherever `_rk_cited_grounded` is reset to `False` (the `if not _focused_answer_used:` block at `:4972-4976`) — add `_rk_cited_mixed = False` there too.

- [ ] **Step 4: Pass the bool to `classify_outcome`**

In the `classify_outcome(...)` call at `:5008`, add the argument (after `unmatched_citations=_rk_unmatched,`):

```python
                cited_mixed_support=_rk_cited_mixed,
```

- [ ] **Step 5: Run to verify pass + import sanity**

Run: `.venv/bin/python -c "import daemon.maez_daemon; print('ok')"`
Run: `.venv/bin/python -m unittest tests.test_memory_integrity_invariant -v -k mixed_support`
Expected: `ok`; the daemon-shaped test passes (both-shaped memory+dialogue → `answered_mixed_support`).

- [ ] **Step 6: Commit**

```bash
git add daemon/maez_daemon.py tests/<daemon_test>.py
git commit -m "feat(recall-outcome): daemon emits answered_mixed_support for both-shaped memory+dialogue turns"
```

---

## Task 3: Fix 3 — expand the dated-absence matcher with the `" but "` guard

**Files:**
- Modify: `daemon/maez_daemon.py:1226-1240`
- Test: `tests/test_recall_outcome.py` (new `DatedAbsenceMatcherTest`)

- [ ] **Step 1: Write the failing tests**

```python
class DatedAbsenceMatcherTest(unittest.TestCase):
    def test_honest_absence_phrasings_match(self):
        from daemon.maez_daemon import _reply_asserts_dated_absence
        for reply in [
            "I don't have any records for January 3.",
            "I don’t have any record of that.",            # curly apostrophe
            "I have no records for that window.",
            "I have no record of that conversation.",
            "I do not have any records from then.",
            "I don't have a dated memory for that window.",  # pre-existing
            "no record",
        ]:
            with self.subTest(reply=reply):
                self.assertTrue(_reply_asserts_dated_absence(reply))

    def test_non_absence_and_absence_plus_content_do_not_match(self):
        from daemon.maez_daemon import _reply_asserts_dated_absence
        for reply in [
            "Sure, I can help you with that.",
            "On January 3 you fixed the parser bug.",                 # content assertion
            "Do you have any record of that meeting?",                # over-broad guardrail
            "I recorded the meeting notes in your file.",             # 'record' as a verb
            "I don't have any records for January 3, but you fixed the parser bug.",  # absence + content
        ]:
            with self.subTest(reply=reply):
                self.assertFalse(_reply_asserts_dated_absence(reply))
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/python -m unittest tests.test_recall_outcome.DatedAbsenceMatcherTest -v`
Expected: FAIL — "any record"/"have no record"/curly-apostrophe positives return `False`; the "…but you fixed…" case currently would match the absence phrase (no guard yet).

- [ ] **Step 3: Expand the matcher + add the `" but "` guard**

Replace `daemon/maez_daemon.py:1226-1240`:

```python
def _reply_asserts_dated_absence(reply: str) -> bool:
    low = (reply or "").lower().replace("’", "'")
    matched = any(
        phrase in low
        for phrase in (
            "don't have a dated memory",
            "do not have a dated memory",
            "no dated memory",
            "don't remember",
            "do not remember",
            "don't recall",
            "do not recall",
            "no record",
            "don't have any record",
            "do not have any record",
            "have no record",
        )
    )
    if not matched:
        return False
    # A recognized absence phrase paired with a contrastive content continuation
    # is not a clean decline. Err toward "answered" (-> ungrounded if uncited),
    # never toward laundering content as honest absence.
    if " but " in low:
        return False
    return True
```

- [ ] **Step 4: Run to verify pass**

Run: `.venv/bin/python -m unittest tests.test_recall_outcome.DatedAbsenceMatcherTest -v`
Expected: OK.

- [ ] **Step 5: Commit**

```bash
git add daemon/maez_daemon.py tests/test_recall_outcome.py
git commit -m "fix(recall-outcome): matcher recognizes honest dated-absence; ' but ' guard blocks absence+content laundering"
```

---

## Task 4: Shared `probe_turn_kind` helper + `probe_runner.py` consumer

**Files:**
- Modify: `scripts/recall_flip_eval/probes.py` (add helper after `get_probe` `:92`)
- Modify: `scripts/brain_bench/probe_runner.py:259-269` (and the import at `:169`)

- [ ] **Step 1: Add the shared turn_kind helper**

Append to `scripts/recall_flip_eval/probes.py` after `get_probe` (`:92`). This does NOT modify the frozen `ProbeDefinition` (no schema churn); it is a pure mapping:

```python
def probe_turn_kind(probe_id: str) -> str:
    """The turn_kind a probe represents, for outcome classification.

    Only the both-shaped probe is "both" (dated + continuity), where
    answered_mixed_support can legitimately arise.
    """
    if probe_id == "both_shaped":
        return "both"
    if probe_id in {"incidental", "continuity"}:
        return "continuity"
    return "dated"
```

- [ ] **Step 2: Thread `turn_kind` into `_run_focused_probe` (it has NO `probe` in scope)**

`_run_focused_probe` (`probe_runner.py:159`) receives only `working_set`/result-building args — **not** `probe`. Do NOT call `probe_turn_kind` inside it. Instead:

(a) Add a `turn_kind: str` parameter to `_run_focused_probe` (`:159`).

(b) In `ProbeRun._run_sample` (`:75`), where it calls `_run_focused_probe(...)` (`:84`) — `probe` **is** in scope here — pass `turn_kind=probes.probe_turn_kind(probe.probe_id)`. (`probes` is already imported at `probe_runner.py:14`.)

(c) Extend the `citation_support` import at `probe_runner.py:169`, then replace the classify block `:259-269` to use the threaded `turn_kind`:

```python
    grounded = cites_confirmed_memory_context(result, working_set)   # STRICT, drives grounded_categorical
    _support = citation_support(result, working_set, turn_kind=turn_kind)
    outcome = classify_outcome(
        mode="recall_triad",
        turn_kind=turn_kind,
        answered=bool(result.reply),
        receipt="consulted",
        denial_kind="none",
        had_confirmed=had_confirmed,
        cited_grounded_context=grounded,
        unmatched_citations=len(verdict.unmatched),
        cited_mixed_support=(_support == "mixed"),
    )
```

`cited_confirmed_memory_context=grounded` (the field `assert_probe_result` reads at `probes.py:112`) stays **strict** — so `mixed` does not clear `grounded_categorical` (spec §6(b)). Only `outcome_class` reflects the new state.

- [ ] **Step 3: Verify import + a probe_runner-level check**

Run: `.venv/bin/python -c "from scripts.brain_bench import probe_runner; from scripts.recall_flip_eval.probes import probe_turn_kind; print(probe_turn_kind('both_shaped'), probe_turn_kind('dated_hit'))"`
Expected: `both dated`.

- [ ] **Step 4: Commit**

```bash
git add scripts/recall_flip_eval/probes.py scripts/brain_bench/probe_runner.py
git commit -m "feat(brain_bench): probe_runner emits answered_mixed_support; mixed does not clear grounded_categorical"
```

---

## Task 5: `harness.py` consumer (2a proof harness)

**Files:**
- Modify: `scripts/recall_flip_eval/harness.py:81` (`run_probe` signature), `:159-176` (classify), and the `run_eval` caller (`:236-241`)

- [ ] **Step 1: Thread turn_kind into `run_probe` and use the three-state**

`run_probe(text, *, flag_on)` has no probe context. Add a `turn_kind: str = "dated"` keyword param to `run_probe` (`:81`) and pass it through to the classify block. Replace `:166-176`:

```python
    grounded = cites_confirmed_memory_context(result, working_set)   # STRICT (grounded_categorical)
    _support = citation_support(result, working_set, turn_kind=turn_kind)
    outcome = classify_outcome(
        mode="recall_triad",
        turn_kind=turn_kind,
        answered=bool(result.reply),
        receipt="consulted",
        denial_kind="none",
        had_confirmed=had_confirmed,
        cited_grounded_context=grounded,
        unmatched_citations=len(verdict.unmatched),
        cited_mixed_support=(_support == "mixed"),
    )
```

Add `citation_support` to the import at `:95`. Keep `cited_confirmed_memory_context=grounded` (strict) at `:191`.

Then in `_run_probe_battery` (`:278`), which holds the variants loop and the `run_probe` calls (`:304-306`) and has `probe` in scope, compute the kind **once before the variants loop** and pass it to both arms (import `probe_turn_kind` from `scripts.recall_flip_eval.probes` if not already imported):

```python
        turn_kind = probes.probe_turn_kind(probe.probe_id)
        for index, text in enumerate(variants, start=1):
            legacy = run_probe(text, flag_on=False, turn_kind=turn_kind)
            triad = run_probe(text, flag_on=True, turn_kind=turn_kind)
```

- [ ] **Step 2: Verify the 2a proof packet is unchanged (floor both directions)**

The 2a deterministic offline adapter (`deterministic_offline_chat`) is single-cite, so it does not co-cite a `dialogue_anchor` → `_support` is never `"mixed"` there → outcomes are byte-stable. Confirm:

Run: `.venv/bin/python -c "import scripts.recall_flip_eval.harness; print('ok')"`
Run the recall_flip_eval probe tests if present: `.venv/bin/python -m unittest tests.test_recall_flip_eval_probes -v`
Expected: `ok`; OK — and specifically the `both_shaped` arm result is unchanged from base (it stays `answered_grounded` under the single-cite adapter). If any `both_shaped` outcome flips, STOP and report (it would mean the adapter co-cites dialogue, which must be understood before landing).

- [ ] **Step 3: Commit**

```bash
git add scripts/recall_flip_eval/harness.py
git commit -m "feat(recall_flip_eval): harness threads turn_kind + three-state outcome (2a packet byte-stable)"
```

---

## Task 6: Docs — A5 benefit-reading (flip spec + 2b runbook)

**Files:**
- Modify: `docs/superpowers/specs/2026-05-30-recall-triad-monitored-default-on-flip-design.md` (`:53-61` class defs, `:232-234` rescued def)
- Modify: `docs/superpowers/runbooks/2026-05-30-recall-flip-2b-monitored-flip-runbook.md` (`:112-114` benefit gate)

- [ ] **Step 1: Add the class definition + rescued clarification to the flip spec**

In the outcome-class list (`:53-61`), add a definition between `answered_grounded` and `answered_ungrounded`:

```markdown
- `answered_mixed_support` — answered, ≥1 **matched** confirmed `memory_context` citation, all citations valid, but a `dialogue_anchor` was also cited on a **both-shaped** turn. Better than ungrounded, but NOT proof of dated recall. **Observed, never counted as rescue** (A5).
```

At the A5 rescued definition (`:232-234`), append after the `answered-but-ungrounded = FAIL` clause:

```markdown
  `answered_mixed_support` is **observed, not rescue** (it does not satisfy the rescued counter, and it is not a hard fail).
```

- [ ] **Step 2: Add to the 2b runbook benefit gate**

At the Benefit gate (A5) block (`:112-114`), after `**answered-ungrounded = FAIL**`, add:

```markdown
`answered_mixed_support` = **observed mixed support: not rescue, not hard fail** (recorded and watched, never banked as benefit).
```

- [ ] **Step 3: Commit**

```bash
git add docs/superpowers/specs/2026-05-30-recall-triad-monitored-default-on-flip-design.md docs/superpowers/runbooks/2026-05-30-recall-flip-2b-monitored-flip-runbook.md
git commit -m "docs(recall): A5 benefit reading for answered_mixed_support (observe, not rescue)"
```

---

## Task 7: Closed-enum sweep + regression + floor both directions

**Files:** none (verification; fix-forward only if a gap is found)

- [ ] **Step 1: Grep for any other closed outcome-class enumeration**

Run: `grep -rnE "answered_grounded|answered_ungrounded|ANSWERED_GROUNDED|ANSWERED_UNGROUNDED|outcome_class" --include=*.py scripts/ core/ daemon/ | grep -v __pycache__`
For every site that *enumerates* or *branches exhaustively* on outcome classes (e.g. a dashboard, a closed-enum in `scripts/brain_bench/bench_packet.py`, a gate that lists allowed classes), ensure `answered_mixed_support` is handled (observed per its consumer's semantics). Sites that only pass `outcome.value` through or read a single specific class need no change. **`log()`/report any site you deliberately leave unchanged and why** (no silent caps).

- [ ] **Step 2: Recall + probe suites**

Run: `.venv/bin/python -m unittest tests.test_recall_outcome tests.test_recall_flip_eval_probes tests.test_memory_integrity_invariant -v`
Expected: OK.

- [ ] **Step 3: Full discover sweep (blast radius, floor both directions)**

Run: `.venv/bin/python -m unittest discover -s tests -p "test_*.py" -q`
Expected: **zero branch-only failures.** Any broad-suite red must be diffed against base — compare in a **clean base checkout or the existing isolated worktree** (do NOT `git stash`; the repo root is intentionally dirty). Name any failure THIS branch introduces and confirm any residual red is pre-existing on base. Name regressions in both directions; none silently.

- [ ] **Step 4: Lint + import sanity**

Run: `.venv/bin/python -m ruff check core/routing/recall_outcome.py daemon/maez_daemon.py scripts/brain_bench/probe_runner.py scripts/recall_flip_eval/harness.py scripts/recall_flip_eval/probes.py tests/test_recall_outcome.py` (match the repo's ruff convention if different)
Run: `.venv/bin/python -c "import daemon.maez_daemon, core.routing.recall_outcome, scripts.brain_bench.probe_runner, scripts.recall_flip_eval.harness; print('ok')"`
Expected: clean; `ok`.

- [ ] **Step 5: Final commit (only if a sweep fix was needed)**

```bash
git add -A
git commit -m "chore(recall-outcome): three-state classification slice green (mixed support + honest absence)"
```

---

## Cross-lane verification gate (Claude, before merge — NOT optional)

After Codex implements, Claude independently:
1. **Reads every diff line.** `cites_confirmed_memory_context` byte-identical; `citation_support` matches the spec ladder (mixed = both-only, ≥1 confirmed memory, dialogue-only supplement, nothing else); `classify_outcome` additive (grounded checked first; `cited_mixed_support` omitted ⇒ identical).
2. **Confirms the strict-field invariant** — both eval scripts still feed the *strict* `cited_confirmed_memory_context` to `assert_probe_result`, so `mixed` cannot clear `grounded_categorical` (§6(b)).
3. **Confirms no behavior/cognition change** — no synthesis/prompt/routing/recall-stack edits; recall flag off; `is_false_absence` untouched; 2a `both_shaped` outcome byte-stable.
4. **Checks the daemon-shaped RED** actually exercised the live path (not just helpers), and the `" but "` guard test is present.
5. **Floor both directions** vs base; runs suites independently; fires the coverage panel.
6. Merge on the legacy baseline. **Recall stays off.** Then Step 2 (Fix 1 continuity mechanism + behavior-side mixed→grounded steering) gets its own brainstorm; the six-prompt re-gate is owner-run after both land.
```
