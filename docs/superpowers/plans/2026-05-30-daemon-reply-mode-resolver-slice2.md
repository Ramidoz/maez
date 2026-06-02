# Daemon Reply-Mode Resolver — Slice 2 (B4/B5 behavior fix) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development or executing-plans. Checkbox steps.
>
> From spec `docs/superpowers/specs/2026-05-30-daemon-reply-mode-resolver-design.md`. **Slice 2** — the isolated behavior change after Slice 1's byte-identical extraction (merged `main@1259aa5`). Branch off `main`.

**Goal:** Close B4 (date-addressed turns must not be pre-empted by HONEST_EMPTY) and B5 (a focused crash with a confirmed item assembled must not emit a false "no dated memory" absence claim) by flipping exactly two precedence lines in the resolver + adding the absence-vs-transport distinction in the daemon's FOCUSED fallback.

**Architecture:** `resolve_reply_mode` gains a `date_addressed` signal; FOCUSED moves above HONEST_EMPTY and HONEST_EMPTY excludes `date_addressed`. The daemon's existing dated-honesty fallback distinguishes "no `date_confirmed` item was assembled" (honest absence) from "a `date_confirmed` item WAS assembled but synthesis crashed" (transport-failure language). Because Slice 1 made precedence declared and total, this is a small, isolated, well-tested change — a routing regression here is unambiguously distinguishable from the intended fix.

**Tech Stack:** Python 3, `unittest` (`.venv/bin/python -m unittest`), `ruff`.

**HARD CONSTRAINTS:** only B4/B5 behavior changes; no other mode's routing changes; flag-gated (focused cognition behind its flag — B4/B5 only manifest when focused is on); the live triad re-witness is the graduation gate.

---

## Task 1: Resolver precedence flip (B4)

**Files:** Modify `core/routing/reply_mode.py`. Test: `tests/test_reply_mode.py`.

- [ ] **Step 1: Write the failing tests**
```python
class ResolverB4PrecedenceTests(unittest.TestCase):
    def test_date_addressed_prefers_focused_over_honest_empty(self):
        from core.routing.reply_mode import (
            ReplyDecisionSignals, ReplyMode, resolve_reply_mode,
        )
        # B4 case: both honest_empty AND focused candidate true, AND date-addressed.
        s = ReplyDecisionSignals(
            honest_empty_candidate=True, focused_candidate=True, date_addressed=True,
        )
        self.assertIs(resolve_reply_mode(s).mode, ReplyMode.FOCUSED)

    def test_non_dated_empty_web_still_honest_empty(self):
        from core.routing.reply_mode import (
            ReplyDecisionSignals, ReplyMode, resolve_reply_mode,
        )
        # not dated, empty web, nothing else → still HONEST_EMPTY (no regression)
        s = ReplyDecisionSignals(honest_empty_candidate=True, focused_candidate=False,
                                 date_addressed=False)
        self.assertIs(resolve_reply_mode(s).mode, ReplyMode.HONEST_EMPTY)

    def test_dated_empty_web_no_focused_excludes_honest_empty(self):
        from core.routing.reply_mode import (
            ReplyDecisionSignals, ReplyMode, resolve_reply_mode,
        )
        # date-addressed + empty web but focused somehow not a candidate →
        # HONEST_EMPTY must NOT fire for a dated turn; falls to LEGACY.
        s = ReplyDecisionSignals(honest_empty_candidate=True, focused_candidate=False,
                                 date_addressed=True)
        self.assertIs(resolve_reply_mode(s).mode, ReplyMode.LEGACY)
```

- [ ] **Step 2: Run → FAIL** (today HONEST_EMPTY wins; `date_addressed` field doesn't exist).

- [ ] **Step 3: Implement.** In `core/routing/reply_mode.py`, add the signal field:
```python
@dataclass(frozen=True)
class ReplyDecisionSignals:
    clinical_matched: bool = False
    camera_answer: str | None = None
    authoritative_tool_reply: bool = False
    echo_reply: bool = False
    honest_empty_candidate: bool = False
    focused_candidate: bool = False
    date_addressed: bool = False
```
In `resolve_reply_mode`, swap the FOCUSED and HONEST_EMPTY blocks so FOCUSED is checked first, and gate HONEST_EMPTY on `not date_addressed` (replace the current `honest_empty` then `focused` blocks):
```python
    if signals.focused_candidate:
        return ReplyDecision(ReplyMode.FOCUSED, _CALL_PURPOSE[ReplyMode.FOCUSED])
    if signals.honest_empty_candidate and not signals.date_addressed:
        return ReplyDecision(
            ReplyMode.HONEST_EMPTY, _CALL_PURPOSE[ReplyMode.HONEST_EMPTY],
        )
    return ReplyDecision(ReplyMode.LEGACY, _CALL_PURPOSE[ReplyMode.LEGACY])
```
Update the module docstring: remove the "HONEST_EMPTY before FOCUSED (B4 bug)" note; state the corrected precedence. Update the Slice-1 oracle test's `_today_oracle` is NOT touched (it documented the old order); instead the new ResolverB4PrecedenceTests assert the corrected order. (If the Slice-1 `test_matches_today_for_full_signal_matrix` now fails because the oracle encodes the OLD order, update the oracle to the corrected order in the same commit — it is no longer "today", it is the new contract.)

- [ ] **Step 4: Run → PASS** (`.venv/bin/python -m unittest tests.test_reply_mode -v`, incl. the updated oracle).
- [ ] **Step 5: Commit** `fix(daemon): resolver precedence — FOCUSED before HONEST_EMPTY; HONEST_EMPTY excludes date-addressed (B4)`

---

## Task 2: Wire `date_addressed` into the daemon's tail-phase resolve + B5 absence-vs-transport

**Files:** Modify `daemon/maez_daemon.py`. Test: `tests/test_memory_integrity_invariant.py`.

- [ ] **Step 1: Write the failing tests** (daemon-path, mirroring the existing handle_message fixtures)
```python
    def test_dated_web_trigger_does_not_honest_empty(self):
        # a date-addressed query that ALSO trips web search ("what happened on May 12")
        # with no dated match → must take FOCUSED (→ dated status), NOT honest_empty.
        # Assert the focused path / temporal_recall_status, NOT the "searched web, nothing" frame.
        ...

    def test_focused_crash_with_confirmed_item_is_transport_not_absence(self):
        # date-addressed; assemble produced a date_confirmed item; focused_synthesize raises.
        # reply must be transport-failure language, NOT "I don't have a dated memory".
        ...

    def test_focused_empty_no_confirmed_is_honest_absence(self):
        # date-addressed; no date_confirmed item; focused yields nothing →
        # reply is the honest "no dated memory for that window" absence.
        ...
```
**Executor:** reuse the module's `_build_daemon_for_handle_message` + the mocking style; for the web-trigger test, let `needs_web_search` return True and the web search return empty (don't hardcode False as the prior tests did — that's the gap the panel named).

- [ ] **Step 2: Run → FAIL.**

- [ ] **Step 3a (B4 wiring).** In `daemon/maez_daemon.py`, the tail-phase `resolve_reply_mode` call (the second one, ~line 3890) must pass `date_addressed`:
```python
        _reply_decision = resolve_reply_mode(
            ReplyDecisionSignals(
                authoritative_tool_reply=bool(authoritative_tool_reply),
                echo_reply=bool(_current_turn_echo_reply),
                honest_empty_candidate=bool(_honest_empty_candidate),
                focused_candidate=bool(_focused_candidate),
                date_addressed=bool(_date_addressed_turn),
            )
        )
```
(`_date_addressed_turn` is already computed in v2. With FOCUSED now above HONEST_EMPTY and `_focused_candidate` already including `_date_addressed_turn`, a dated turn routes to FOCUSED; the `not date_addressed` HONEST_EMPTY guard is belt-and-suspenders.)

- [ ] **Step 3b (B5 absence-vs-transport).** At the dated-honesty fallback (the `if _date_addressed_turn and not _focused_used and reply is None:` block, ~line 4051), distinguish the two cases using the assembled working set's provenance:
```python
            if _date_addressed_turn and not _focused_used and reply is None:
                _had_confirmed = bool(
                    _focused_working_set is not None
                    and any(
                        getattr(it, "temporal_provenance", None)
                        and it.temporal_provenance.get("confirmed")
                        for it in _focused_working_set.items
                    )
                )
                if _had_confirmed:
                    reply = (
                        "I have a dated memory for that, but I couldn't pull it "
                        "together just now. Ask me again in a moment."
                    )
                else:
                    reply = (
                        "I don't have a dated memory for that window. I'm not going "
                        "to answer it from recent chat or guesswork."
                    )
                _focused_used = True
```
(`_focused_working_set` is in scope in the focused branch; ensure it's initialized to `None` before the try so the fallback can read it even if `assemble_working_set` raised. Confirm/repair its scope.)

- [ ] **Step 4: Run → PASS** (the 3 new daemon tests).
- [ ] **Step 5: Commit** `fix(daemon): pass date_addressed to resolver (B4 live); dated-honesty distinguishes absence vs transport-failure (B5)`

---

## Task 3: Regression + lint

- [ ] **Step 1:** `.venv/bin/python -m unittest tests.test_reply_mode tests.test_memory_integrity_invariant tests.test_focused_cognition tests.test_living_recall tests.test_honest_empty_integration -v` → OK.
- [ ] **Step 2:** `.venv/bin/ruff check core/routing/reply_mode.py daemon/maez_daemon.py` → clean.
- [ ] **Step 3:** Broad floor: only the 2 documented pre-existing failures. Report honestly.
- [ ] **Step 4: Commit** `test(daemon): Slice 2 B4/B5 regression`

---

## Witness (Claude, after green): FULL 6-role switchboard (behavior changes), THEN live triad re-witness
Slice 2 changes behavior, so the full Claude switchboard fires on the diff (not the calibrated-down pair). Then the **live triad re-witness** (flag-on Telegram) is the graduation gate:
1. "remind me what we were doing around April 27" → recaps the April-27 record (FOCUSED/dated primary), recent thread at most a labeled side-note — NOT the prior turn.
2. "what happened on May 12" (date + web-trigger, likely no dated match) → honest dated-status (focused path), NOT "searched the web, found nothing".
3. "what were we just talking about, the 3 may bugs?" → stays continuity (date incidental — already verified at the cue layer; confirm live).
4. Plain continuity / plain recency / plain honest-empty (non-dated web miss) → all still correct.
Green → the triad graduates: eligible for the explicit default-on decision (separate step, full switchboard, Rohit's call). Red → split.

## Self-Review
**Spec coverage:** FOCUSED-above-HONEST_EMPTY + HONEST_EMPTY-excludes-date_addressed (Task 1) = spec Slice-2 precedence flip ✓; `date_addressed` signal wired into the daemon resolve (Task 2 3a) = B4 live ✓; absence-vs-transport via assembled-provenance (Task 2 3b) = B5 ✓; full switchboard + live triad re-witness = spec witness ✓.
**Placeholder scan:** Task 1 + Task 2 3a/3b are full code; the 3 daemon test bodies are described with their exact setup (web-trigger-true, confirmed-item-assembled+synthesize-raises, no-confirmed-item) — the executor wires them to the existing fixture; the assertions are concrete (FOCUSED not honest_empty; transport not absence; absence when no confirmed).
**Type consistency:** `ReplyDecisionSignals` gains `date_addressed: bool=False`; `resolve_reply_mode` unchanged signature; `_focused_working_set.items[*].temporal_provenance["confirmed"]` matches the v2 EvidenceItem field; `_date_addressed_turn` is the v2-computed daemon variable.
