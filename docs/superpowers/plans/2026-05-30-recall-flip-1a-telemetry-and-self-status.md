# Recall-Flip Slice 1a — Outcome Telemetry + Speakable Self-Status Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the flag-off, observe-only instrumentation (`recall_outcome` per-turn record + false-absence detector) and a deterministic, restart-aware speakable self-status branch, so the eventual default-on flip is measurable and Maez can honestly report whether its dated recall is reachable.

**Architecture:** Two new pure modules — `core/routing/recall_outcome.py` (content-free record + `classify_outcome` for both legacy and triad arms + `is_false_absence`) and `core/routing/recall_self_status.py` (intent match + 4-state boot-aware status reply) — keep logic testable outside the daemon. `daemon/maez_daemon.py` wires them: emits `recall_outcome` on every recall-relevant and ordinary turn, persists the last carrier receipt with a `boot_id`, and adds the self-status branch gated by a new `MAEZ_RECALL_STATUS_INTERCEPT_ENABLED` flag (a status-intercept rollout flag — NOT a recall control; the one recall switch stays `MAEZ_RECALL_TRIAD_ENABLED`).

**Tech Stack:** Python 3, stdlib `enum`/`dataclasses`, `unittest` via `.venv/bin/python -m unittest` (pytest NOT installed).

**Spec / pre-registration:** [docs/superpowers/specs/2026-05-30-recall-triad-monitored-default-on-flip-design.md](../specs/2026-05-30-recall-triad-monitored-default-on-flip-design.md) (committed @ 87603b7).

**Discipline reminders:**
- This slice lands **flag-off and observe-only**: `recall_outcome` logging changes no answer; the only behavior change is the self-status intercept, which is gated by its own flag and must have a hard false-positive boundary (proven empty in test).
- Telemetry is **content-free** — never log `query_text` / `recalled_snippet` / any raw content. Enforced by a regression test.
- Genderless self-reference (it/Maez) in all self-status strings.
- Do NOT touch `config/.env`. Flags are launch-env only, set in tests via `mock.patch.dict`.

---

## File Structure

- **Create** `core/routing/recall_outcome.py` — `OutcomeClass` enum, `RecallOutcome` frozen dataclass (content-free), `classify_outcome(...)`, `is_false_absence(...)`.
- **Create** `tests/test_recall_outcome.py` — classifier truth table (both arms), false-absence detector, content-free schema guard.
- **Create** `core/routing/recall_self_status.py` — `RecallLiveness` enum (4 states), `RecallStatusReceipt` dataclass, `is_recall_status_query(text)`, `build_recall_status_reply(...)`.
- **Create** `tests/test_recall_self_status.py` — hard-false-positive corpus, 4 liveness states, boot/restart awareness, staleness degrade.
- **Modify** `daemon/maez_daemon.py` — emit `recall_outcome`; persist last receipt + boot_id; self-status branch gated by `MAEZ_RECALL_STATUS_INTERCEPT_ENABLED`.
- **Modify** `core/memory/memory_scoring.py` — add a decoder note reconciling the single recency constant with the type-rule (no numeric change).
- **Modify** `tests/test_memory_integrity_invariant.py` — add the daemon-shaped tests (emission + self-status intercept) **in the existing class that hosts `_build_daemon_for_handle_message` / `_handle_message_mock_stack`**, reusing that harness exactly as the merged fold tests (`test_dated_assembly_error_is_path_unavailable_not_absence` etc.) do. Do NOT create a fresh file with a stub harness.

---

## Task 1: Reconcile the "14" — decoder note + type-rule confirmation (foundational, no behavior change)

**Files:**
- Modify: `core/memory/memory_scoring.py:74`
- Test: `tests/test_recall_outcome.py` (a small assertion added in Task 2)

Context: there is exactly ONE numeric recency constant (`_RECENCY_HALF_LIFE_DAYS = 14.0`, a ranking *decay*). The "evidence ceiling" is NOT a second number — it is a *type rule* (recalled memory is `memory_context`, never `memory_evidence`), enforced by source-type labels in `core/routing/focused_cognition.py`. The reconciliation is documentation, not a merge.

- [ ] **Step 1: Add the decoder note** at `core/memory/memory_scoring.py:74`:

```python
# Recency decay half-life for memory ranking (a soft modulator, NOT a cutoff).
# DECODER NOTE (recall-flip 1a): this 14 is the *ranking* half-life. It is distinct
# from the recall "evidence ceiling", which is NOT a number but a TYPE RULE enforced
# by source-type labels in core/routing/focused_cognition.py: recalled memory is
# emitted as `memory_context`, never `memory_evidence` (old memory is context, never
# current-state evidence). Do not conflate or "unify" these — one is a decay constant,
# the other is a type invariant. See the flip spec, "Reconcile the two 14s".
_RECENCY_HALF_LIFE_DAYS = 14.0
```

- [ ] **Step 2: Commit**

```bash
git add core/memory/memory_scoring.py
git commit -m "docs(recall): decoder note — recency half-life is decay, evidence ceiling is a type rule"
```

---

## Task 2: `recall_outcome` classification module (pure, both arms)

**Files:**
- Create: `core/routing/recall_outcome.py`
- Test: `tests/test_recall_outcome.py`

- [ ] **Step 1: Write the failing truth-table test**

```python
# tests/test_recall_outcome.py
import unittest
from core.routing.recall_outcome import (
    OutcomeClass,
    RecallOutcome,
    classify_outcome,
    is_false_absence,
)


class ClassifyOutcomeTest(unittest.TestCase):
    # --- triad arm, recall-relevant ---
    def test_consulted_grounded_dated_context(self):
        oc = classify_outcome(
            mode="recall_triad", turn_kind="dated", answered=True, receipt="consulted",
            denial_kind="na", had_confirmed=True,
            cited_grounded_context=True, unmatched_citations=0,
        )
        self.assertIs(oc, OutcomeClass.ANSWERED_GROUNDED)

    def test_consulted_no_match_is_legal_absence(self):
        oc = classify_outcome(
            mode="recall_triad", turn_kind="dated", answered=False, receipt="consulted",
            denial_kind="no_dated_memory", had_confirmed=False,
            cited_grounded_context=False, unmatched_citations=0,
        )
        self.assertIs(oc, OutcomeClass.DECLINED_ABSENCE)

    def test_not_consulted_is_unavailable_not_absence(self):
        oc = classify_outcome(
            mode="recall_triad", turn_kind="dated", answered=False, receipt="not_consulted",
            denial_kind="carrier_unavailable", had_confirmed=False,
            cited_grounded_context=False, unmatched_citations=0,
        )
        self.assertIs(oc, OutcomeClass.DECLINED_UNAVAILABLE)

    def test_consult_failed_is_failed_not_absence(self):
        oc = classify_outcome(
            mode="recall_triad", turn_kind="dated", answered=False, receipt="consult_failed",
            denial_kind="carrier_failed", had_confirmed=False,
            cited_grounded_context=False, unmatched_citations=0,
        )
        self.assertIs(oc, OutcomeClass.DECLINED_FAILED)

    def test_transport_failure_is_declined_transport_not_absence(self):
        # "I have it but couldn't pull it together" — NOT absence (blocker 3)
        oc = classify_outcome(
            mode="recall_triad", turn_kind="dated", answered=False, receipt="consulted",
            denial_kind="transport_failure", had_confirmed=True,
            cited_grounded_context=False, unmatched_citations=0,
        )
        self.assertIs(oc, OutcomeClass.DECLINED_TRANSPORT)

    def test_answered_ungrounded_when_unmatched_citations(self):
        oc = classify_outcome(
            mode="recall_triad", turn_kind="dated", answered=True, receipt="consulted",
            denial_kind="na", had_confirmed=True,
            cited_grounded_context=True, unmatched_citations=2,
        )
        self.assertIs(oc, OutcomeClass.ANSWERED_UNGROUNDED)

    # --- legacy arm, recall-relevant: fabrication bucket / unverified decline ---
    def test_legacy_dated_answer_is_unverifiable(self):
        oc = classify_outcome(
            mode="legacy", turn_kind="dated", answered=True, receipt="na",
            denial_kind="na", had_confirmed=None,
            cited_grounded_context=False, unmatched_citations=0,
            asserts_absence=False,
        )
        self.assertIs(oc, OutcomeClass.ANSWERED_UNVERIFIABLE)

    def test_legacy_dated_absence_claim_is_declined_unverified(self):
        oc = classify_outcome(
            mode="legacy", turn_kind="dated", answered=False, receipt="na",
            denial_kind="na", had_confirmed=None,
            cited_grounded_context=False, unmatched_citations=0,
            asserts_absence=True,
        )
        self.assertIs(oc, OutcomeClass.DECLINED_UNVERIFIED)

    # --- ordinary (non-recall) turns: NEVER fabrication classes (blocker 2) ---
    def test_ordinary_legacy_answer_is_ordinary_answered_not_unverifiable(self):
        oc = classify_outcome(
            mode="legacy", turn_kind="ordinary", answered=True, receipt="na",
            denial_kind="na", had_confirmed=None,
            cited_grounded_context=False, unmatched_citations=0,
        )
        self.assertIs(oc, OutcomeClass.ORDINARY_ANSWERED)

    def test_ordinary_triad_answer_is_ordinary_answered(self):
        oc = classify_outcome(
            mode="recall_triad", turn_kind="ordinary", answered=True, receipt="not_consulted",
            denial_kind="na", had_confirmed=False,
            cited_grounded_context=False, unmatched_citations=0,
        )
        self.assertIs(oc, OutcomeClass.ORDINARY_ANSWERED)


class FalseAbsenceTest(unittest.TestCase):
    def _rec(self, **kw):
        base = dict(
            mode="recall_triad", turn_kind="dated",
            outcome_class=OutcomeClass.DECLINED_ABSENCE, denial_kind="no_dated_memory",
            had_confirmed=False, citation_coverage=None, receipt_or_na="consulted",
            latency_ms=10, focused_elapsed_ms=5,
        )
        base.update(kw)
        return RecallOutcome(**base)

    def test_legal_absence_is_not_false(self):
        self.assertFalse(is_false_absence(self._rec()))

    def test_absence_with_confirmed_item_is_false(self):
        rec = self._rec(had_confirmed=True)  # confirmed existed yet absence claimed
        self.assertTrue(is_false_absence(rec))

    def test_legacy_absence_without_consultation_is_false(self):
        rec = self._rec(
            mode="legacy", outcome_class=OutcomeClass.DECLINED_UNVERIFIED,
            denial_kind="na", had_confirmed=None, receipt_or_na="na",
        )
        self.assertTrue(is_false_absence(rec))

    def test_reachability_and_transport_are_not_false(self):
        for dk, oc in (("carrier_unavailable", OutcomeClass.DECLINED_UNAVAILABLE),
                       ("carrier_failed", OutcomeClass.DECLINED_FAILED),
                       ("transport_failure", OutcomeClass.DECLINED_TRANSPORT)):
            rec = self._rec(denial_kind=dk, outcome_class=oc, had_confirmed=False)
            self.assertFalse(is_false_absence(rec), dk)


class ContentFreeSchemaTest(unittest.TestCase):
    def test_no_content_fields(self):
        import dataclasses
        names = {f.name for f in dataclasses.fields(RecallOutcome)}
        forbidden = {"query_text", "text", "raw_text", "reply", "recalled_snippet",
                     "content", "owner_question", "snippet"}
        self.assertEqual(names & forbidden, set(),
                         "RecallOutcome must stay content-free (whether-I-remembered, never what)")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/python -m unittest tests.test_recall_outcome -v`
Expected: FAIL — `ModuleNotFoundError: core.routing.recall_outcome`.

- [ ] **Step 3: Write the module**

```python
# core/routing/recall_outcome.py
"""Content-free per-turn recall outcome record + false-absence detector.

Telemetry about WHETHER Maez remembered, never WHAT it remembered. The record
is schema-closed and content-free by test (no query/snippet/reply fields).
Classification runs on BOTH arms (legacy and recall_triad) so the flip's
benefit/caution can be measured as baseline-vs-soak deltas.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class OutcomeClass(Enum):
    ANSWERED_GROUNDED = "answered_grounded"
    ANSWERED_UNGROUNDED = "answered_ungrounded"
    ANSWERED_UNVERIFIABLE = "answered_unverifiable"   # recall-relevant legacy answer, no consulted evidence
    DECLINED_ABSENCE = "declined_absence"             # legal "I don't have a dated memory" (consulted, no match)
    DECLINED_UNAVAILABLE = "declined_unavailable"     # "I can't reach my dated memory"
    DECLINED_FAILED = "declined_failed"               # "the lookup errored" (consult_failed)
    DECLINED_TRANSPORT = "declined_transport"         # "had it, couldn't pull it together" — NOT absence
    DECLINED_UNVERIFIED = "declined_unverified"       # legacy absence claim with no consultation
    ORDINARY_ANSWERED = "ordinary_answered"           # non-recall turn answered — blast-radius only
    ORDINARY_DECLINED = "ordinary_declined"           # non-recall turn declined — blast-radius only


@dataclass(frozen=True)
class RecallOutcome:
    mode: str                       # "legacy" | "recall_triad"
    turn_kind: str                  # "dated" | "continuity" | "both" | "ordinary"
    outcome_class: OutcomeClass
    denial_kind: str                # carrier_unavailable|carrier_failed|transport_failure|no_dated_memory|na
    had_confirmed: Optional[bool]   # None -> "na" (legacy)
    citation_coverage: Optional[float]
    receipt_or_na: str              # not_consulted|consulted|consult_failed|na
    latency_ms: int
    focused_elapsed_ms: Optional[int]


def classify_outcome(
    *,
    mode: str,
    turn_kind: str,
    answered: bool,
    receipt: str,
    denial_kind: str,
    had_confirmed: Optional[bool],
    cited_grounded_context: bool,
    unmatched_citations: int,
    asserts_absence: bool = False,
) -> OutcomeClass:
    """Classify a turn's outcome, for either arm.

    `turn_kind` ∈ {dated, continuity, both, ordinary}. ORDINARY turns are recorded for
    the blast-radius guardrail ONLY and are NEVER mapped into recall fabrication/benefit
    classes (blocker 2). `cited_grounded_context` is True only when the answer cites an
    allowed grounded substrate item (for dated recall: a date-confirmed memory_context
    item, never memory_evidence — citing old memory AS current-state evidence is a
    type-rule violation, not grounding).
    """
    # Non-recall turns never enter the recall fabrication/benefit classes.
    if turn_kind == "ordinary":
        return OutcomeClass.ORDINARY_ANSWERED if answered else OutcomeClass.ORDINARY_DECLINED

    if answered:
        if mode == "legacy":
            # legacy has no carrier; a recall-relevant answer with no consulted evidence is unverifiable
            return OutcomeClass.ANSWERED_UNVERIFIABLE
        if cited_grounded_context and unmatched_citations == 0:
            return OutcomeClass.ANSWERED_GROUNDED
        return OutcomeClass.ANSWERED_UNGROUNDED

    # declined, recall-relevant
    if mode == "legacy":
        # legacy decline on a recall-relevant turn = an absence claim with no consultation
        return OutcomeClass.DECLINED_UNVERIFIED
    if denial_kind == "no_dated_memory":
        return OutcomeClass.DECLINED_ABSENCE
    if denial_kind == "carrier_unavailable":
        return OutcomeClass.DECLINED_UNAVAILABLE
    if denial_kind == "carrier_failed":
        return OutcomeClass.DECLINED_FAILED
    if denial_kind == "transport_failure":
        # "I have it but couldn't pull it together" — NOT an absence claim (blocker 3)
        return OutcomeClass.DECLINED_TRANSPORT
    return OutcomeClass.DECLINED_UNVERIFIED


def is_false_absence(rec: "RecallOutcome") -> bool:
    """The HARD gate detector. Points at denial_kind (Rohit amendment 1).

    The only LEGAL absence-of-fact reply is denial_kind == no_dated_memory with
    receipt == consulted and had_confirmed False. A false-absence event is:
      1. denial_kind == no_dated_memory while had_confirmed is True (confirmed item
         existed yet absence claimed — construction bug, must be 0), OR
      2. an absence claim produced OUTSIDE the carrier-consulted gate: the legacy
         path asserting absence (outcome_class == DECLINED_UNVERIFIED) on a
         recall-relevant turn.
    Reachability/error language (carrier_unavailable/carrier_failed/transport_failure)
    is NOT false-absence.
    """
    if rec.denial_kind == "no_dated_memory" and rec.had_confirmed is True:
        return True
    if rec.outcome_class is OutcomeClass.DECLINED_UNVERIFIED and rec.mode == "legacy":
        return True
    return False
```

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/bin/python -m unittest tests.test_recall_outcome -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add core/routing/recall_outcome.py tests/test_recall_outcome.py
git commit -m "feat(recall): content-free outcome classifier + false-absence detector (both arms)"
```

---

## Task 3: Speakable self-status module (pure, boot-aware)

**Files:**
- Create: `core/routing/recall_self_status.py`
- Test: `tests/test_recall_self_status.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_recall_self_status.py
import unittest
from core.routing.recall_self_status import (
    RecallLiveness,
    RecallStatusReceipt,
    is_recall_status_query,
    build_recall_status_reply,
)


class IntentMatchTest(unittest.TestCase):
    def test_positive_triggers(self):
        for q in ("is your dated recall reachable?",
                  "is your dated recall working right now?",
                  "can you reach your dated memory?"):
            self.assertTrue(is_recall_status_query(q), q)

    def test_hard_false_positive_corpus_is_empty(self):
        # adjacent-but-out-of-scope; MUST NOT trigger
        for q in ("is your memory okay?",
                  "do you recall yesterday?",
                  "can you reach me?",
                  "what did we discuss around April 27?",   # ordinary dated query
                  "what were we just talking about?",        # continuity
                  "are you working?"):
            self.assertFalse(is_recall_status_query(q), q)


class StatusReplyTest(unittest.TestCase):
    def _receipt(self, **kw):
        base = dict(receipt="consulted", at_ts=1000.0, boot_id="bootA")
        base.update(kw)
        return RecallStatusReceipt(**base)

    def test_off_by_config(self):
        reply, state = build_recall_status_reply(
            triad_on=False, last_receipt=None, current_boot_id="bootA", now_ts=1100.0,
        )
        self.assertIs(state, RecallLiveness.OFF_BY_CONFIG)
        self.assertIn("can't reach my dated memory", reply.lower())

    def test_on_never_consulted_when_no_receipt(self):
        reply, state = build_recall_status_reply(
            triad_on=True, last_receipt=None, current_boot_id="bootA", now_ts=1100.0,
        )
        self.assertIs(state, RecallLiveness.ON_NEVER_CONSULTED)
        self.assertIn("haven't", reply.lower())

    def test_on_never_consulted_when_receipt_from_prior_boot(self):
        # under 6h old BUT different boot -> never-consulted-since-restart (Rohit amendment 3)
        r = self._receipt(receipt="consulted", at_ts=1099.0, boot_id="bootPREV")
        reply, state = build_recall_status_reply(
            triad_on=True, last_receipt=r, current_boot_id="bootA", now_ts=1100.0,
        )
        self.assertIs(state, RecallLiveness.ON_NEVER_CONSULTED)
        self.assertNotIn("just a moment ago", reply.lower())

    def test_on_ok_recent_same_boot(self):
        r = self._receipt(receipt="consulted", at_ts=1099.0, boot_id="bootA")
        reply, state = build_recall_status_reply(
            triad_on=True, last_receipt=r, current_boot_id="bootA", now_ts=1100.0,
        )
        self.assertIs(state, RecallLiveness.ON_OK)
        self.assertIn("dated memory", reply.lower())

    def test_on_consult_failed(self):
        r = self._receipt(receipt="consult_failed", at_ts=1099.0, boot_id="bootA")
        reply, state = build_recall_status_reply(
            triad_on=True, last_receipt=r, current_boot_id="bootA", now_ts=1100.0,
        )
        self.assertIs(state, RecallLiveness.ON_CONSULT_FAILED)
        self.assertIn("errored", reply.lower())

    def test_stale_consulted_same_boot_degrades(self):
        # same boot but >6h old -> not "just a moment ago"
        r = self._receipt(receipt="consulted", at_ts=1000.0, boot_id="bootA")
        reply, state = build_recall_status_reply(
            triad_on=True, last_receipt=r, current_boot_id="bootA",
            now_ts=1000.0 + 6 * 3600 + 1,
        )
        self.assertNotIn("just a moment ago", reply.lower())

    def test_genderless(self):
        for r in (None, self._receipt()):
            reply, _ = build_recall_status_reply(
                triad_on=True, last_receipt=r, current_boot_id="bootA", now_ts=1100.0,
            )
            low = reply.lower()
            for bad in (" she ", " he ", " her ", " his ", " hers "):
                self.assertNotIn(bad, f" {low} ")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/python -m unittest tests.test_recall_self_status -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Write the module**

```python
# core/routing/recall_self_status.py
"""Deterministic, restart-aware self-status for Maez's dated recall.

Answers ONLY the explicit "is your dated recall reachable?" question, from
resolved config + the last persisted carrier receipt. Event-shaped by default;
an exact timestamp is given only when the owner explicitly asks "when". This is a
status-intercept, NOT a recall control — it reads recall state, never gates it.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple

_STALE_SECONDS = 6 * 3600

# Narrow, high-precision: must mention BOTH a recall/memory self-reference AND a
# reachability/working predicate, scoped to "your ... dated recall/memory".
_RECALL_NOUN = r"(?:dated\s+(?:recall|memory)|recall\s+(?:stack|system))"
_REACH_PRED = r"(?:reachable|working|online|available|active|up|down|enabled|on|off|broken)"
_STATUS_RE = re.compile(
    rf"\b(?:is|are|can\s+you\s+reach)\b.*\byour\b.*{_RECALL_NOUN}\b"
    rf"|{_RECALL_NOUN}\b.*\b{_REACH_PRED}\b",
    re.IGNORECASE,
)


class RecallLiveness(Enum):
    OFF_BY_CONFIG = "off_by_config"
    ON_NEVER_CONSULTED = "on_never_consulted_since_restart"
    ON_CONSULT_FAILED = "on_consult_failed"
    ON_OK = "on_ok"


@dataclass(frozen=True)
class RecallStatusReceipt:
    receipt: str       # "consulted" | "consult_failed" | "not_consulted"
    at_ts: float       # epoch seconds
    boot_id: str       # runtime boot identity that produced it


def is_recall_status_query(text: str) -> bool:
    t = (text or "").strip()
    if not t:
        return False
    return bool(_STATUS_RE.search(t))


def build_recall_status_reply(
    *,
    triad_on: bool,
    last_receipt: Optional[RecallStatusReceipt],
    current_boot_id: str,
    now_ts: float,
) -> Tuple[str, RecallLiveness]:
    if not triad_on:
        return (
            "I can't reach my dated memory right now — that path isn't switched on. "
            "I won't answer dated questions from guesswork.",
            RecallLiveness.OFF_BY_CONFIG,
        )
    # triad on: restart-awareness FIRST (a prior-boot receipt is not "this runtime")
    if last_receipt is None or last_receipt.boot_id != current_boot_id:
        return (
            "I can reach my dated memory; I just haven't had reason to look into it "
            "since I came back up.",
            RecallLiveness.ON_NEVER_CONSULTED,
        )
    if last_receipt.receipt == "consult_failed":
        return (
            "I can reach my dated memory, but my last look into it errored out — "
            "I'd want to try again before trusting it.",
            RecallLiveness.ON_CONSULT_FAILED,
        )
    if last_receipt.receipt == "consulted":
        recent = (now_ts - last_receipt.at_ts) <= _STALE_SECONDS
        when = "just a moment ago" if recent else "a while back"
        return (
            f"I can reach my dated memory; I looked into it {when}.",
            RecallLiveness.ON_OK,
        )
    # not_consulted within this boot
    return (
        "I can reach my dated memory; I haven't needed to look into it yet.",
        RecallLiveness.ON_NEVER_CONSULTED,
    )
```

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/bin/python -m unittest tests.test_recall_self_status -v`
Expected: PASS. (If the intent regex trips a false positive in the corpus, tighten `_STATUS_RE` until the corpus is empty — the hard boundary is non-negotiable.)

- [ ] **Step 5: Commit**

```bash
git add core/routing/recall_self_status.py tests/test_recall_self_status.py
git commit -m "feat(recall): deterministic restart-aware self-status (4 liveness states, hard FP boundary)"
```

---

## Task 4: Daemon — emit `recall_outcome` + persist boot-stamped receipt

**Files:**
- Modify: `daemon/maez_daemon.py` (capture classification inputs at the reply sites; persist `_last_recall_receipt`; emit one `recall_outcome` log per recall-relevant + ordinary turn)
- Test: `tests/test_memory_integrity_invariant.py` (new methods in the harness-hosting class)

- [ ] **Step 1: Write the failing daemon-shaped test (real, no skeleton)**

Add to the class that hosts `_build_daemon_for_handle_message` in `tests/test_memory_integrity_invariant.py`, mirroring the `handle_message(...)` call shape used by the merged fold test `test_dated_assembly_error_is_path_unavailable_not_absence` (copy its daemon construction + `_handle_message_mock_stack` + `handle_message` kwargs verbatim; change only the input text and assertions):

```python
    def _recall_outcome_lines(self, logs):
        return [ln for ln in logs.output if "recall_outcome" in ln]

    def test_recall_outcome_emitted_on_dated_legacy_turn(self):
        captured = {}
        daemon = self._build_daemon_for_handle_message()
        with self.assertLogs("maez", level="INFO") as logs:
            with self._handle_message_mock_stack(maez_daemon, captured), mock.patch.dict(
                os.environ, {}, clear=False
            ):
                os.environ.pop("MAEZ_RECALL_TRIAD_ENABLED", None)  # legacy arm
                maez_daemon.MaezDaemon.handle_message(
                    daemon, "what did we decide around April 27?",
                    chat_id="c1", user_id="u1", source="telegram",
                )
        lines = self._recall_outcome_lines(logs)
        self.assertTrue(lines, "expected a recall_outcome line")
        line = lines[-1]
        self.assertIn("mode=legacy", line)
        self.assertIn("turn_kind=dated", line)
        # legacy dated answer with no consulted evidence => fabrication bucket
        self.assertRegex(line, r"outcome_class=(answered_unverifiable|declined_unverified)")
        self.assertIn("receipt_or_na=na", line)
        # content-free: assert on THIS line only (chat_turn logs elsewhere may carry excerpts)
        self.assertNotIn("April 27", line)
        self.assertNotIn("decide", line)

    def test_recall_outcome_on_ordinary_turn_is_not_fabrication_class(self):
        captured = {}
        daemon = self._build_daemon_for_handle_message()
        with self.assertLogs("maez", level="INFO") as logs:
            with self._handle_message_mock_stack(maez_daemon, captured), mock.patch.dict(
                os.environ, {}, clear=False
            ):
                os.environ.pop("MAEZ_RECALL_TRIAD_ENABLED", None)
                maez_daemon.MaezDaemon.handle_message(
                    daemon, "what is a transformer?",
                    chat_id="c1", user_id="u1", source="telegram",
                )
        lines = self._recall_outcome_lines(logs)
        self.assertTrue(lines)
        line = lines[-1]
        self.assertIn("turn_kind=ordinary", line)
        self.assertRegex(line, r"outcome_class=ordinary_(answered|declined)")
        self.assertNotRegex(line, r"answered_unverifiable")  # blocker 2: ordinary != fabrication
```

(If the merged fold test uses different `handle_message` kwargs, copy those exact kwargs — the call shape must match the file's working precedent, not this plan's guess.)

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/python -m unittest tests.test_memory_integrity_invariant -v -k recall_outcome`
Expected: FAIL — no `recall_outcome` line emitted yet.

- [ ] **Step 3: Add a module-level emitter + boot-stamped receipt store**

Add near the other helpers in `daemon/maez_daemon.py` (after `_log_dated_recall_denial`):

```python
def _log_recall_outcome(*, rec) -> None:
    """Emit one content-free recall_outcome record (whether-I-remembered, never what)."""
    logger.info(
        "recall_outcome mode=%s turn_kind=%s outcome_class=%s denial_kind=%s "
        "had_confirmed=%s citation_coverage=%s receipt_or_na=%s latency_ms=%s "
        "focused_elapsed_ms=%s",
        rec.mode, rec.turn_kind, rec.outcome_class.value, rec.denial_kind,
        rec.had_confirmed, rec.citation_coverage, rec.receipt_or_na,
        rec.latency_ms, rec.focused_elapsed_ms,
    )
```

In `MaezDaemon.__init__` add `self._last_recall_receipt = None`. Where the daemon sets a carrier receipt during a turn (the focused/dated block ~`daemon/maez_daemon.py:4089`), after the receipt is finalized for the turn, persist it boot-stamped:

```python
        # boot-stamped last receipt for self-status (restart-aware)
        from core.routing.recall_self_status import RecallStatusReceipt
        self._last_recall_receipt = RecallStatusReceipt(
            receipt=_recall_carrier_receipt,
            at_ts=time.time(),
            boot_id=str(self.boot_time),  # ISO boot time identifies this runtime
        )
```

After the reply for a recall-relevant turn is finalized (covering both the focused/dated path and the legacy fall-through), build and emit the outcome. Capture the inputs (`turn_kind` from `_date_addressed_turn`/dialogue state; `cited_grounded_context` + `unmatched_citations` from the focused groundedness verdict when present; `had_confirmed`; `denial_kind` from `_dated_denial_kind(...)` when a denial fired else `na`; `citation_coverage` from the focused verdict; `latency_ms` from `_trace.latency_ms`; `focused_elapsed_ms` from the focused timing if available):

```python
        from core.routing.recall_outcome import classify_outcome, RecallOutcome
        _rk_turn_kind = (
            "both" if (_date_addressed_turn and _dialogue_needs_or_uncertain)
            else "dated" if _date_addressed_turn
            else "continuity" if _dialogue_needs_or_uncertain
            else "ordinary"
        )
        if _rk_turn_kind != "ordinary" or True:  # ordinary turns recorded for blast-radius guardrail
            _rk_mode = "recall_triad" if _recall_stack_config.triad_on else "legacy"
            _rk_outcome = classify_outcome(
                mode=_rk_mode,
                answered=bool(reply) and not _is_dated_denial_reply(reply),
                receipt=_recall_carrier_receipt if _recall_stack_config.triad_on else "na",
                denial_kind=_dated_denial_kind_for_turn,  # set where the denial is built, else "na"
                had_confirmed=_had_confirmed if _recall_stack_config.triad_on else None,
                cited_grounded_context=_rk_cited_grounded,   # from focused verdict; False if no focused run
                unmatched_citations=_rk_unmatched,           # from focused verdict; 0 if none
                asserts_absence=_rk_legacy_absence,          # legacy-arm absence classifier (see below)
            )
            _log_recall_outcome(rec=RecallOutcome(
                mode=_rk_mode, turn_kind=_rk_turn_kind, outcome_class=_rk_outcome,
                denial_kind=_dated_denial_kind_for_turn,
                had_confirmed=(_had_confirmed if _recall_stack_config.triad_on else None),
                citation_coverage=_rk_coverage, receipt_or_na=(
                    _recall_carrier_receipt if _recall_stack_config.triad_on else "na"),
                # `_trace.latency_ms` is NOT set until ~line 4662 (after this point), so
                # compute directly from the turn start (tightening): never read latency_ms early.
                latency_ms=int((time.time() - _trace_t_start) * 1000),
                focused_elapsed_ms=_rk_focused_elapsed,
            ))
```

Implement the small helpers: `_is_dated_denial_reply(reply)` (membership test against the three denial strings from `_dated_denial_decision`), the legacy-arm `_rk_legacy_absence` (a narrow deterministic check that a legacy reply asserts absence-of-fact on a recall-relevant turn — reuse/adapt the honest-empty phrase detection), and default the focused-derived vars (`_rk_cited_grounded=False`, `_rk_unmatched=0`, `_rk_coverage=None`, `_rk_focused_elapsed=None`) so non-focused turns classify correctly. Capture `_dated_denial_kind_for_turn` = the kind returned where the denial is built (else `"na"`).

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/bin/python -m unittest tests.test_memory_integrity_invariant -v -k recall_outcome`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add daemon/maez_daemon.py tests/test_memory_integrity_invariant.py
git commit -m "feat(recall): emit content-free recall_outcome per turn + persist boot-stamped receipt"
```

---

## Task 5: Daemon — self-status deterministic intercept (own flag)

**Files:**
- Modify: `daemon/maez_daemon.py` (add the intercept near the deterministic reply family, gated by `MAEZ_RECALL_STATUS_INTERCEPT_ENABLED`)
- Test: `tests/test_memory_integrity_invariant.py` (new methods in the harness-hosting class)

- [ ] **Step 1: Write the failing tests (real, no skeleton)**

Add to the harness-hosting class. `fake_chat` in `_handle_message_mock_stack` records into `captured["messages"]` and is the synthesis path; assert it was NOT populated when the intercept fires (synthesis skipped), AND that the trace was still written (tail ran — the deterministic short-circuit must behave like the ECHO branch: set `reply`, skip synthesis, continue the normal tail; it must NOT early-return past audit/memory/trace/telemetry):

```python
    def test_self_status_intercepted_when_flag_on_and_tail_runs(self):
        captured = {}
        written = {"trace": False}
        daemon = self._build_daemon_for_handle_message()
        with self.assertLogs("maez", level="INFO") as logs:
            with self._handle_message_mock_stack(maez_daemon, captured), mock.patch.dict(
                os.environ, {"MAEZ_RECALL_STATUS_INTERCEPT_ENABLED": "1"}, clear=False
            ):
                os.environ.pop("MAEZ_RECALL_TRIAD_ENABLED", None)  # off_by_config state
                with mock.patch.object(
                    maez_daemon, "default_writer",
                    return_value=types.SimpleNamespace(
                        write=lambda _t: written.__setitem__("trace", True)),
                ):
                    reply = maez_daemon.MaezDaemon.handle_message(
                        daemon, "is your dated recall reachable?",
                        chat_id="c1", user_id="u1", source="telegram",
                    )
        self.assertIn("can't reach my dated memory", reply.lower())   # off_by_config
        self.assertNotIn("messages", captured)                        # synthesis skipped
        self.assertTrue(written["trace"])                             # tail still ran (tightening)
        self.assertTrue(any("recall_self_status state=" in ln for ln in logs.output))

    def test_ordinary_dated_query_not_intercepted(self):
        captured = {}
        daemon = self._build_daemon_for_handle_message()
        with self._handle_message_mock_stack(maez_daemon, captured), mock.patch.dict(
            os.environ, {"MAEZ_RECALL_STATUS_INTERCEPT_ENABLED": "1"}, clear=False
        ):
            os.environ.pop("MAEZ_RECALL_TRIAD_ENABLED", None)
            maez_daemon.MaezDaemon.handle_message(
                daemon, "what did we discuss around April 27?",
                chat_id="c1", user_id="u1", source="telegram",
            )
        self.assertIn("messages", captured)   # normal path ran; not intercepted

    def test_no_intercept_when_flag_off(self):
        captured = {}
        daemon = self._build_daemon_for_handle_message()
        with self._handle_message_mock_stack(maez_daemon, captured), mock.patch.dict(
            os.environ, {}, clear=False
        ):
            os.environ.pop("MAEZ_RECALL_STATUS_INTERCEPT_ENABLED", None)
            maez_daemon.MaezDaemon.handle_message(
                daemon, "is your dated recall reachable?",
                chat_id="c1", user_id="u1", source="telegram",
            )
        self.assertIn("messages", captured)   # flag off -> normal path, no deterministic intercept
```

(Copy the exact `handle_message` kwargs from the file's working fold tests if they differ.)

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/python -m unittest tests.test_memory_integrity_invariant -v -k self_status`
Expected: FAIL.

- [ ] **Step 3: Add the flag reader + the intercept**

Add a helper near `_focused_cognition_enabled`:

```python
def _recall_status_intercept_enabled() -> bool:
    # Status-intercept rollout flag ONLY. NOT a recall control — the one recall
    # switch is MAEZ_RECALL_TRIAD_ENABLED. This gates whether the self-status
    # question is answered deterministically; it never changes recall behavior.
    return os.environ.get("MAEZ_RECALL_STATUS_INTERCEPT_ENABLED", "0").strip().lower() in {"1", "true", "yes"}
```

Compute the status reply near where `_current_turn_echo_reply` is computed (~`daemon/maez_daemon.py:3993`), after `_recall_stack_config` is resolved (~3622) and `self._last_recall_receipt` exists:

```python
        _recall_status_reply = None
        if _recall_status_intercept_enabled():
            from core.routing.recall_self_status import (
                is_recall_status_query as _is_recall_status_query,
                build_recall_status_reply as _build_recall_status_reply,
            )
            if _is_recall_status_query(text):
                _recall_status_reply, _status_state = _build_recall_status_reply(
                    triad_on=_recall_stack_config.triad_on,
                    last_receipt=self._last_recall_receipt,
                    current_boot_id=str(self.boot_time),
                    now_ts=time.time(),
                )
                logger.info("recall_self_status state=%s", _status_state.value)
```

Then make it a deterministic reply source **exactly like the ECHO branch** — set `reply` and skip synthesis, but **fall through to the normal tail** (do NOT `return`). Concretely: give it precedence at the top of the reply-mode if/elif chain (~`daemon/maez_daemon.py:4056`):

```python
        if _recall_status_reply is not None:
            reply = _recall_status_reply
        elif _reply_decision.mode is ReplyMode.TOOL:
            reply = authoritative_tool_reply
        elif _reply_decision.mode is ReplyMode.ECHO:
            reply = _current_turn_echo_reply
        elif _reply_decision.mode is ReplyMode.HONEST_EMPTY:
            ...  # (unchanged existing branch)
        else:
            # focused/legacy synthesis — unchanged
```

Because the `else` (focused/legacy synthesis) only runs when no earlier branch matched, setting `_recall_status_reply` skips synthesis while the post-reply tail (audit, memory store, trace write, `recall_outcome` emit, `_ws_broadcast`) runs normally — same shape as ECHO. The `...` above denotes the existing HONEST_EMPTY branch body, left unchanged (it is real code already in the file, not a placeholder to fill). The daemon test pins the contract: synthesis skipped (`captured` has no `messages`) AND trace written (tail ran).

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/bin/python -m unittest tests.test_memory_integrity_invariant -v -k self_status`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add daemon/maez_daemon.py tests/test_memory_integrity_invariant.py
git commit -m "feat(recall): deterministic self-status intercept gated by MAEZ_RECALL_STATUS_INTERCEPT_ENABLED"
```

---

## Task 6: Regression sweep + single-source guard extension

**Files:**
- Modify: `tests/test_recall_flag_single_source.py` (allow the new modules to reference the recall flags only via the resolver / their own status flag)

- [ ] **Step 1: Confirm the single-source guard still holds**

The new modules must NOT read `MAEZ_DISPATCHER_ENABLED`/`MAEZ_FOCUSED_COGNITION_ENABLED`/`MAEZ_LIVING_RECALL_ENABLED` directly. `MAEZ_RECALL_STATUS_INTERCEPT_ENABLED` is a NEW flag (not one of the three) so it does not violate the guard. Run:

Run: `.venv/bin/python -m unittest tests.test_recall_flag_single_source -v`
Expected: PASS (no change needed unless a new raw read crept in — if so, route it through the resolver).

- [ ] **Step 2: Full targeted regression**

Run: `.venv/bin/python -m unittest tests.test_recall_outcome tests.test_recall_self_status tests.test_recall_stack_config tests.test_recall_carrier_consulted_denial tests.test_memory_integrity_invariant tests.test_focused_cognition -v 2>&1 | tail -8`
Expected: all green. Ruff: `.venv/bin/ruff check core/routing/recall_outcome.py core/routing/recall_self_status.py daemon/maez_daemon.py` → All checks passed.

- [ ] **Step 3: Commit**

```bash
git add -p   # stage only the recall-flip 1a changes; do NOT git add -A
git commit -m "test(recall): 1a regression sweep green; single-source guard intact"
```

---

## Self-Review

**1. Spec coverage (slice 1a portion):**
- `recall_outcome` content-free record + both-arm classifier → Task 2. ✓
- False-absence detector pointing at `denial_kind`+`had_confirmed` (amendment 1) → Task 2 `is_false_absence`. ✓
- `answered_grounded` = date-confirmed `memory_context`, never `memory_evidence` (amendment 2) → Task 2 `cited_grounded_context` semantics + classifier comment. ✓ (the daemon wiring in Task 4 must pass `cited_grounded_context` true only for confirmed memory_context citations.)
- `answered_unverifiable` (recall-relevant legacy fabrication) + `ordinary_*` (non-recall, never fabrication — amendment A4, blocker 2) + `declined_transport` (not absence — A4, blocker 3) + `declined_unverified` (A4, blocker 4) → Task 2 enum + `classify_outcome(turn_kind=…)`. ✓
- Content-free by regression test → Task 2 `ContentFreeSchemaTest`. ✓
- 4-state event-shaped on-demand self-status + hard-FP corpus + boot/restart awareness (amendment 3) + staleness → Task 3. ✓
- Own flag `MAEZ_RECALL_STATUS_INTERCEPT_ENABLED`, status-intercept-not-recall-control, sets reply + skips synthesis + runs tail (not early-return) → Task 5. ✓
- Reconcile-14 decoder note (one decay constant + type rule) → Task 1. ✓
- Non-recall turns recorded for blast-radius guardrail as `ordinary_*` (NOT fabrication classes) → Task 4. ✓
- Latency computed from `_trace_t_start` (not `_trace.latency_ms`, unset until ~4662) → Task 4. ✓
- Shadow-mode, the probe battery, gates, the flip itself → **out of slice 1a** (1b + Phase-2 runbook). ✓

**2. Placeholder scan:** All tests are real (no `...` in any test body) — the daemon-shaped tests in Tasks 4/5 are concrete methods that call `MaezDaemon.handle_message` via the existing harness and assert observable behavior (the log line, synthesis-skipped, tail-ran). The single `...` in Task 5's wiring snippet denotes the *unchanged existing HONEST_EMPTY branch body* (real code already in the file), explicitly labeled as such — not a placeholder. The only implementation-time integration detail is capturing `cited_grounded_context`/`unmatched_citations`/`focused_elapsed_ms` from the focused verdict locals (data capture from `_focused_verdict`/`_focused_working_set` — the implementer matches existing names); the daemon-shaped tests pin the resulting `recall_outcome` line. The tests are RED-first executable, not stubs that pass vacuously (blocker 1 closed).

**3. Type/symbol consistency:** `OutcomeClass`, `RecallOutcome`, `classify_outcome`, `is_false_absence`, `RecallLiveness`, `RecallStatusReceipt`, `is_recall_status_query`, `build_recall_status_reply`, `MAEZ_RECALL_STATUS_INTERCEPT_ENABLED` used identically across tasks. `denial_kind` values (`carrier_unavailable`/`carrier_failed`/`transport_failure`/`no_dated_memory`/`na`) match the merged `_dated_denial_decision`. `boot_id = str(self.boot_time)` consistent between Task 4 (persist) and Task 5 (compare).

**4. Ordering:** decoder note (1) → pure classifier (2) → pure self-status (3) → daemon emit + receipt persist (4) → daemon intercept (5) → regression (6). Pure modules before daemon wiring; each task independently committable and green.

## Execution note for the implementer
Tasks 4 and 5 touch `handle_message` (a large method). Read the surrounding block first: `_recall_stack_config` (~3622), `_date_addressed_turn` (~4012), the focused block + `_recall_carrier_receipt`/`_had_confirmed`/`_focused_working_set`/`_focused_verdict` (~4070–4179), the denial gate (~4179), and the echo deterministic short-circuit (~4058) for the return idiom. Match existing names; do not introduce parallel state.
