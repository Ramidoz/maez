# Slice 3a — Evidence Precedence Steer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When Maez holds real evidence this turn, inject a computed directive as the final tail of the system message telling it to answer from that evidence and never claim the source is blocked/missing — so it stops reciting stale capability stories (Obs 13).

**Architecture:** A new pure module `core/routing/evidence_state.py` computes the turn's evidence-state from the RAW `transcript` + `web_context` and builds the directive + combined final tail. `daemon/maez_daemon.py::handle_message` calls it at the system-assembly site, makes the directive the `final_system_part` tail, captures it for telemetry, and widens the seam-logging guard so legacy-evidence turns are observable. No verifier/fallback/judge (that is Slice 3b), no soul edit, `_DISPATCHER_INSTRUCTION_BLOCK` untouched.

**Tech Stack:** Python 3.14, `unittest`, `core/routing/`, `daemon/maez_daemon.py`, `core/dispatcher` marker vocabulary.

---

## Spec

`docs/superpowers/specs/2026-05-28-slice3a-evidence-precedence-steer-design.md`

## File Structure

- **Create:** `core/routing/evidence_state.py` — pure functions: `turn_evidence_state()`, `EvidenceState`, `build_evidence_precedence_directive()`, `build_turn_final_context()`. No I/O, no LLM. (Parallels `core/routing/observation/`.)
- **Modify:** `daemon/maez_daemon.py`
  - `handle_message` system-assembly site (`:3744-3769`): compute evidence-state, build directive, make `turn_final_context` the `final_system_part`, append the `evidence_precedence_directive` capture label, widen the seam guard.
  - `_summarize_daemon_prompt_messages` (`:1022-1066`): add `evidence_directive` param + `evidence_directive_is_suffix` field.
  - `_log_daemon_prompt_payload_shape` (~`:1070`): thread `evidence_directive` through.
- **Create tests:** `tests/test_evidence_state.py` (pure-function tests).
- **Modify tests:** `tests/test_memory_integrity_invariant.py` — add integration + telemetry tests; update the `:297` and `:430` suffix-contract assertions.

## Reference: verified source facts

- Marker vocabulary (raw transcript): positive = `[memory evidence]`, `[memory context]`, `[fresh evidence]`; negative-only (NOT evidence) = `[no fresh evidence available:`, `[dispatcher refusal:`.
- `web_format` empty form (Slice 2 / `format_for_context`): `[WEB SEARCH: '<q>'] No results found.` — the `No results found.` fragment marks "no real results."
- Assembly site `:3748-3756`: `_premise_flag` appended to `messages` (pre-consolidation), then `system_part_capture.append(("transcript_context", transcript_context))`, then `_consolidate_system_messages(messages, final_system_part=transcript_context)`.
- Seam guard `:3758` `if transcript_context:` gates BOTH `_log_daemon_system_part_shape` and `_log_daemon_prompt_payload_shape`.
- Raw `transcript` (param) and `web_context` (assigned `:3463`/`:3476`) are both in scope at the assembly site. `transcript_context = f"{transcript}\n\n{instruction_block}"` is built at `:3607`, and `_DISPATCHER_INSTRUCTION_BLOCK` contains the literal string `HARD INSTRUCTION` plus the marker examples — so the detector must receive raw `transcript`, never `transcript_context`.
- `_summarize_daemon_prompt_messages` signature: `(messages, *, transcript_context="")`, computes `transcript_is_suffix = bool(transcript_context and system_content.endswith(transcript_context))` at `:1060`.

---

### Task 1: Pure evidence-state module

**Files:**
- Create: `core/routing/evidence_state.py`
- Test: `tests/test_evidence_state.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_evidence_state.py`:

```python
from __future__ import annotations

import unittest

from core.routing.evidence_state import (
    EvidenceState,
    build_evidence_precedence_directive,
    build_turn_final_context,
    turn_evidence_state,
)


class TurnEvidenceStateTests(unittest.TestCase):
    def test_detects_positive_markers(self):
        state = turn_evidence_state(
            transcript="[memory context] Recent Reddit substrate rows:\n- r/LocalLLaMA ...",
            web_context="",
        )
        self.assertTrue(state.evidence_present)
        self.assertIn("memory context", state.marker_labels)

    def test_negative_markers_not_evidence(self):
        state = turn_evidence_state(
            transcript="[no fresh evidence available: LIVE_REDDIT:EMPTY:NONE:FRESH_ATTEMPT_FAILED]",
            web_context="",
        )
        self.assertFalse(state.evidence_present)

    def test_legacy_web_results_present_vs_empty(self):
        present = turn_evidence_state(
            transcript="",
            web_context="[WEB SEARCH: 'x'] 3 results — 2026\n  1. Title\n     snippet",
        )
        self.assertTrue(present.evidence_present)
        self.assertIn("web search results", present.marker_labels)
        empty = turn_evidence_state(
            transcript="",
            web_context="[WEB SEARCH: 'x'] No results found.",
        )
        self.assertFalse(empty.evidence_present)

    def test_excludes_background(self):
        state = turn_evidence_state(
            transcript="some lived recall and ambient context, no markers",
            web_context="",
        )
        self.assertFalse(state.evidence_present)

    def test_directive_names_markers_and_forbids_blocked_claim(self):
        state = turn_evidence_state(
            transcript="[fresh evidence] LIVE_REDDIT: recent posts",
            web_context="",
        )
        directive = build_evidence_precedence_directive(state)
        self.assertIn("EVIDENCE PRESENT THIS TURN", directive)
        self.assertIn("fresh evidence", directive)
        self.assertTrue(
            directive.rstrip().endswith("the evidence above contradicts that.")
        )

    def test_build_turn_final_context_dispatcher_and_legacy(self):
        directive = "DIRECTIVE"
        # dispatcher: transcript_context present -> directive appended after it
        self.assertEqual(
            build_turn_final_context("TRANSCRIPT_CTX", directive),
            "TRANSCRIPT_CTX\n\nDIRECTIVE",
        )
        # legacy: no transcript_context -> directive alone
        self.assertEqual(build_turn_final_context("", directive), "DIRECTIVE")
        # no directive -> unchanged transcript_context
        self.assertEqual(build_turn_final_context("TRANSCRIPT_CTX", ""), "TRANSCRIPT_CTX")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m unittest tests.test_evidence_state -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'core.routing.evidence_state'`.

- [ ] **Step 3: Create the module**

Create `core/routing/evidence_state.py`:

```python
# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Evidence Precedence Steer — Slice 3a.

Pure, deterministic computation of whether the current turn is holding
real query evidence, plus the computed directive that tells the model to
answer from it. Substrate-side and brain-agnostic: no LLM, no I/O.

CRITICAL: callers MUST pass the RAW dispatcher `transcript`, never the
composed `transcript_context`. The composed value has the dispatcher
instruction block appended, and that block contains the marker strings as
documentation examples — scanning it would false-positive every turn.
"""

from __future__ import annotations

from dataclasses import dataclass

# Positive markers: the dispatcher only emits these with real content.
_POSITIVE_MARKERS: tuple[str, ...] = (
    "[memory evidence]",
    "[memory context]",
    "[fresh evidence]",
)
# The web_format empty form; its presence means "no usable results".
_WEB_NO_RESULTS = "No results found."


@dataclass(frozen=True)
class EvidenceState:
    evidence_present: bool
    marker_labels: tuple[str, ...] = ()
    descriptions: tuple[str, ...] = ()


def _first_line_after(text: str, marker: str) -> str:
    idx = text.find(marker)
    if idx < 0:
        return ""
    tail = text[idx + len(marker):].lstrip()
    lines = tail.splitlines()
    return lines[0][:120] if lines else ""


def turn_evidence_state(*, transcript: str, web_context: str) -> EvidenceState:
    transcript = transcript or ""
    web_context = web_context or ""
    labels: list[str] = []
    descriptions: list[str] = []

    for marker in _POSITIVE_MARKERS:
        if marker in transcript:
            labels.append(marker.strip("[]"))
            descriptions.append(_first_line_after(transcript, marker))

    web_present = bool(web_context.strip()) and _WEB_NO_RESULTS not in web_context
    if web_present:
        labels.append("web search results")
        head_lines = web_context.strip().splitlines()
        descriptions.append(head_lines[0][:120] if head_lines else "")

    return EvidenceState(
        evidence_present=bool(labels),
        marker_labels=tuple(labels),
        descriptions=tuple(descriptions),
    )


def build_evidence_precedence_directive(state: EvidenceState) -> str:
    lines = [
        "EVIDENCE PRESENT THIS TURN.",
        "You are holding real evidence for the owner's question right now:",
    ]
    for label, desc in zip(state.marker_labels, state.descriptions):
        if desc:
            lines.append(f"  - {label}: {desc}")
        else:
            lines.append(f"  - {label}")
    lines.append(
        "Answer from this evidence. If a live/fresh fetch failed but substrate "
        "evidence exists, say that distinction plainly."
    )
    lines.append(
        "You may NOT claim the relevant source is blocked, missing, unavailable, "
        "or not-wired this turn — the evidence above contradicts that."
    )
    return "\n".join(lines)


def build_turn_final_context(transcript_context: str, evidence_directive: str) -> str:
    transcript_context = transcript_context or ""
    evidence_directive = evidence_directive or ""
    if not evidence_directive:
        return transcript_context
    if transcript_context.strip():
        return f"{transcript_context}\n\n{evidence_directive}"
    return evidence_directive
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m unittest tests.test_evidence_state -v`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
git add core/routing/evidence_state.py tests/test_evidence_state.py
git commit -m "feat(routing): add evidence-state + precedence directive (pure)"
```

---

### Task 2: Wire the directive into handle_message

**Files:**
- Modify: `daemon/maez_daemon.py:3744-3769`

- [ ] **Step 1: Apply the wiring**

In `daemon/maez_daemon.py`, replace the block at `:3748-3769`:

```python
        if _premise_flag:
            messages.append({"role": "system", "content": _premise_flag})
            system_part_capture.append(("premise_flag", _premise_flag))
        if transcript_context:
            system_part_capture.append(("transcript_context", transcript_context))
        messages = _consolidate_system_messages(
            messages,
            final_system_part=transcript_context,
        )
        messages.append({"role": "user", "content": prompt})
        if transcript_context:
            _log_daemon_system_part_shape(
                surface=source,
                call_purpose="llm_synthesis",
                system_parts=system_part_capture,
            )
            _log_daemon_prompt_payload_shape(
                surface=source,
                call_purpose="llm_synthesis",
                messages=messages,
                transcript_context=transcript_context,
            )
```

with:

```python
        if _premise_flag:
            messages.append({"role": "system", "content": _premise_flag})
            system_part_capture.append(("premise_flag", _premise_flag))
        # Slice 3a — Evidence Precedence Steer. Compute the turn's evidence
        # state from the RAW transcript (never transcript_context, which has
        # the instruction block's marker examples appended) plus web_context.
        from core.routing.evidence_state import (
            build_evidence_precedence_directive,
            build_turn_final_context,
            turn_evidence_state,
        )

        _evidence_state = turn_evidence_state(
            transcript=transcript, web_context=web_context
        )
        evidence_directive = ""
        if _evidence_state.evidence_present:
            evidence_directive = build_evidence_precedence_directive(_evidence_state)
        if transcript_context:
            system_part_capture.append(("transcript_context", transcript_context))
        if evidence_directive:
            system_part_capture.append(
                ("evidence_precedence_directive", evidence_directive)
            )
        turn_final_context = build_turn_final_context(
            transcript_context, evidence_directive
        )
        messages = _consolidate_system_messages(
            messages,
            final_system_part=turn_final_context,
        )
        messages.append({"role": "user", "content": prompt})
        if transcript_context or evidence_directive:
            _log_daemon_system_part_shape(
                surface=source,
                call_purpose="llm_synthesis",
                system_parts=system_part_capture,
            )
            _log_daemon_prompt_payload_shape(
                surface=source,
                call_purpose="llm_synthesis",
                messages=messages,
                transcript_context=transcript_context,
                evidence_directive=evidence_directive,
            )
```

- [ ] **Step 2: Verify the module imports and daemon still loads**

Run: `.venv/bin/python -c "import daemon.maez_daemon"`
Expected: no error. (`_log_daemon_prompt_payload_shape` gets its new `evidence_directive` param in Task 3; if Task 3 is done after this, the call passes a kwarg the function doesn't yet accept — so do Task 3 Step 1 before running the daemon. For ordering safety, the kwarg is added to the function signature in Task 3. Run this verification after Task 3.)

- [ ] **Step 3: Commit (after Task 3 lands the signature)**

Defer the commit to the end of Task 3 so the new `evidence_directive` kwarg and its consumer land together.

---

### Task 3: Telemetry — `evidence_directive_is_suffix` + thread-through

**Files:**
- Modify: `daemon/maez_daemon.py` — `_summarize_daemon_prompt_messages` (`:1022-1066`) and `_log_daemon_prompt_payload_shape` (~`:1070`)
- Test: `tests/test_memory_integrity_invariant.py`

- [ ] **Step 1: Add `evidence_directive` param + field to the summarizer**

In `_summarize_daemon_prompt_messages`, change the signature:

```python
def _summarize_daemon_prompt_messages(
    messages: list[dict],
    *,
    transcript_context: str = "",
    evidence_directive: str = "",
) -> dict[str, object]:
```

and add to the `summary.update({...})` block (alongside `transcript_is_suffix`):

```python
            "transcript_is_suffix": bool(
                transcript_context
                and system_content.endswith(transcript_context)
            ),
            "evidence_directive_is_suffix": bool(
                evidence_directive
                and system_content.endswith(evidence_directive)
            ),
```

- [ ] **Step 2: Thread `evidence_directive` through the logger**

In `_log_daemon_prompt_payload_shape`, add `evidence_directive: str = ""` to its signature and pass it into the `_summarize_daemon_prompt_messages(...)` call inside it.

Run: `grep -n "def _log_daemon_prompt_payload_shape" daemon/maez_daemon.py` and add the param + pass-through.

- [ ] **Step 3: Write the telemetry tests**

Add to `tests/test_memory_integrity_invariant.py`:

```python
    def test_payload_shape_reports_evidence_directive_suffix(self):
        from daemon import maez_daemon

        transcript_context = "[fresh evidence] LIVE_REDDIT\n\ninstruction"
        directive = "EVIDENCE PRESENT THIS TURN.\n...\ncontradicts that."
        system_content = f"BASE\n\n{transcript_context}\n\n{directive}"
        messages = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": "u"},
        ]
        summary = maez_daemon._summarize_daemon_prompt_messages(
            messages,
            transcript_context=transcript_context,
            evidence_directive=directive,
        )
        self.assertFalse(summary["transcript_is_suffix"])
        self.assertTrue(summary["evidence_directive_is_suffix"])
```

- [ ] **Step 4: Run telemetry test + daemon import**

Run:
```bash
.venv/bin/python -c "import daemon.maez_daemon"
.venv/bin/python -m unittest tests.test_memory_integrity_invariant.MemoryIntegrityInvariantTests.test_payload_shape_reports_evidence_directive_suffix -v
```
(Use the actual test class name from the file; find it with `grep -n "class .*TestCase" tests/test_memory_integrity_invariant.py`.)
Expected: import OK, test PASS.

- [ ] **Step 5: Commit Tasks 2+3 together**

```bash
git add daemon/maez_daemon.py tests/test_memory_integrity_invariant.py
git commit -m "feat(daemon): inject evidence-precedence directive as final tail + telemetry"
```

---

### Task 4: Integration — injection, generality, no-evidence, call-site guard

**Files:**
- Test: `tests/test_memory_integrity_invariant.py` (reuse the mock harness from `test_handle_message_sends_one_system_message_with_dispatcher_suffix`, `:380-428`)

- [ ] **Step 1: Update the existing suffix test (`:430`) to the new tail**

The existing `test_handle_message_sends_one_system_message_with_dispatcher_suffix` calls `handle_message(transcript="[fresh evidence] LIVE_REDDIT: recent posts", ...)`. `[fresh evidence]` is a positive marker, so 3a now appends the directive. Replace its final assertion (`:439-446`):

```python
        from core.brain_loop import _instruction_block_for_transcript

        self.assertTrue(
            system_messages[0]["content"].endswith(
                "[fresh evidence] LIVE_REDDIT: recent posts\n\n"
                + _instruction_block_for_transcript(
                    "[fresh evidence] LIVE_REDDIT: recent posts"
                )
            )
        )
```

with:

```python
        # Slice 3a: the evidence directive is now the intentional tail, after
        # transcript_context. The transcript block is still present (not the
        # suffix); the directive's closing line is the suffix.
        self.assertIn(
            "[fresh evidence] LIVE_REDDIT: recent posts",
            system_messages[0]["content"],
        )
        self.assertIn("EVIDENCE PRESENT THIS TURN", system_messages[0]["content"])
        self.assertTrue(
            system_messages[0]["content"].rstrip().endswith(
                "the evidence above contradicts that."
            )
        )
```

- [ ] **Step 2: Run the updated suffix test**

Run: `.venv/bin/python -m unittest tests.test_memory_integrity_invariant.MemoryIntegrityInvariantTests.test_handle_message_sends_one_system_message_with_dispatcher_suffix -v`
Expected: PASS (proves injection works end-to-end through `handle_message`).

- [ ] **Step 3: Add the call-site raw-transcript guard test**

Add (reusing the same mock harness pattern as the suffix test — copy its `with mock.patch(...)` stack):

```python
    def test_handle_message_feeds_raw_transcript_to_detector(self):
        from daemon import maez_daemon

        seen = {}

        def _spy(*, transcript, web_context):
            seen["transcript"] = transcript
            seen["web_context"] = web_context
            from core.routing.evidence_state import EvidenceState
            return EvidenceState(evidence_present=False)

        daemon = self._build_daemon_for_handle_message()  # same fixture the suffix test uses
        with self._handle_message_mock_stack(), mock.patch(
            "core.routing.evidence_state.turn_evidence_state",
            side_effect=_spy,
        ):
            maez_daemon.MaezDaemon.handle_message(
                daemon,
                "Search r/LocalLLaMA right now",
                source="telegram_surface",
                transcript="[fresh evidence] LIVE_REDDIT: recent posts",
                chat_history=[{"content": "Rohit: earlier\nMaez: prior answer"}],
            )

        # The detector must receive the RAW transcript, never transcript_context
        # (which appends _DISPATCHER_INSTRUCTION_BLOCK, containing the marker
        # examples + the literal "HARD INSTRUCTION").
        self.assertEqual(seen["transcript"], "[fresh evidence] LIVE_REDDIT: recent posts")
        self.assertNotIn("HARD INSTRUCTION", seen["transcript"])
```

NOTE for implementer: the existing suffix test inlines its mock stack and daemon fixture at `:300-428`. If `_build_daemon_for_handle_message` / `_handle_message_mock_stack` helpers do not exist, extract them from the suffix test into reusable methods on the test class FIRST (a pure refactor — run the suffix test before and after to confirm it still passes), then use them here. Patch target is `core.routing.evidence_state.turn_evidence_state` (the name `handle_message` imports); if the import in Task 2 is `from core.routing.evidence_state import turn_evidence_state` at call scope, patch that module attribute.

- [ ] **Step 4: Add the legacy-generality test**

```python
    def test_directive_general_on_legacy_web_turn(self):
        # No dispatcher transcript; real web_context results -> directive is the
        # tail (proves generality + the widened seam guard path).
        from daemon import maez_daemon

        daemon = self._build_daemon_for_handle_message()
        with self._handle_message_mock_stack(
            web_context="[WEB SEARCH: 'local llm'] 2 results — 2026\n  1. Post\n     body",
            needs_web_search=True,
        ):
            captured = self._captured_messages_holder()
            maez_daemon.MaezDaemon.handle_message(
                daemon,
                "what's the latest on local llms",
                source="telegram_surface",
                transcript="",
            )
        system_messages = [m for m in captured["messages"] if m.get("role") == "system"]
        self.assertEqual(len(system_messages), 1)
        self.assertTrue(
            system_messages[0]["content"].rstrip().endswith(
                "the evidence above contradicts that."
            )
        )
```

NOTE for implementer: the legacy path needs `needs_web_search=True` and a non-empty `web_format(sr)`. The suffix test mocks `skills.web_search.needs_web_search` to `False`; here mock it `True` and mock `web_search`/`web_format` (or `skills.web_search.search` + `format_for_context`) to return the `web_context` string above. Mirror the Slice-2 daemon test (`tests/test_routing_observation.py`'s daemon test) for the exact web_search mock shape.

- [ ] **Step 5: Add the no-evidence non-behavioral test**

```python
    def test_no_directive_when_no_evidence(self):
        # No positive markers, no real web results -> no directive, no
        # evidence_precedence_directive capture entry.
        from daemon import maez_daemon

        daemon = self._build_daemon_for_handle_message()
        captured = self._captured_messages_holder()
        with self._handle_message_mock_stack(needs_web_search=False):
            maez_daemon.MaezDaemon.handle_message(
                daemon,
                "just chatting, nothing to look up",
                source="telegram_surface",
                transcript="",
            )
        system_messages = [m for m in captured["messages"] if m.get("role") == "system"]
        self.assertFalse(
            any("EVIDENCE PRESENT THIS TURN" in m["content"] for m in system_messages)
        )
```

- [ ] **Step 6: Run the integration tests**

Run: `.venv/bin/python -m unittest tests.test_memory_integrity_invariant -v`
Expected: all pass (including the refactored suffix test).

- [ ] **Step 7: Commit**

```bash
git add tests/test_memory_integrity_invariant.py
git commit -m "test(daemon): evidence-precedence injection, generality, raw-transcript guard"
```

---

### Task 5: Update the `:297` AST source-contract assertion

**Files:**
- Modify: `tests/test_memory_integrity_invariant.py:297`

- [ ] **Step 1: Run the test to confirm the expected breakage**

Run: find and run the test containing `final_system_part=transcript_context` (the one ending at `:297`).
`grep -n "final_system_part=transcript_context" tests/test_memory_integrity_invariant.py`
Run that test:
Expected: FAIL — `handle_message` source now contains `final_system_part=turn_final_context`, not `final_system_part=transcript_context`.

- [ ] **Step 2: Update the assertion**

Change `:297`:

```python
        self.assertIn("final_system_part=transcript_context", handle_src)
```

to:

```python
        self.assertIn("final_system_part=turn_final_context", handle_src)
```

(The isolated `_consolidate_system_messages` assertion at `:286` — `system_messages[0]["content"].endswith(transcript_context)` — is a direct call to the consolidator with hand-built input and stays unchanged.)

- [ ] **Step 3: Run the test to verify it passes**

Run: that test, `-v`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add tests/test_memory_integrity_invariant.py
git commit -m "test(daemon): update source-contract assertion to turn_final_context"
```

---

### Task 6: Full-suite verification

**Files:** none (verification only)

- [ ] **Step 1: Focused suites**

Run:
```bash
.venv/bin/python -m unittest tests.test_evidence_state tests.test_memory_integrity_invariant tests.test_routing_observation -v
```
Expected: all pass.

- [ ] **Step 2: ruff on touched files**

Run: `.venv/bin/ruff check core/routing/evidence_state.py daemon/maez_daemon.py tests/test_evidence_state.py tests/test_memory_integrity_invariant.py`
Expected: no errors.

- [ ] **Step 3: Broad suite — confirm the floor holds**

Run: `.venv/bin/python -m unittest discover -s tests -p 'test_*.py' 2>&1 | grep -E '^(Ran|OK|FAILED)'`
Expected: floor holds at **3-with-flake** (`FAILED (failures=2 or 3, skipped=3)`) — the two standing deterministic failures (`test_web_search_direct_caller_inventory_is_stable`, `test_owner_bridge_chat_uses_envelope_prompt_block_and_recall_cap`) plus the intermittent cloud-retirement flake. **No new failure.** If a 4th distinct failure appears, stop — it is a Slice 3a regression. (Environmental FD/async-teardown errors are not floor failures; classify per Obs-13 if they appear.)

---

## Self-Review

**1. Spec coverage:**
- `turn_evidence_state` deterministic, raw inputs, detection rules → Task 1 (tests 1-4). ✓
- Negative-only markers excluded, legacy web no-results excluded, background excluded → Task 1. ✓
- Computed directive naming present evidence + forbidding blocked-claim → Task 1 (`build_evidence_precedence_directive`). ✓
- `turn_final_context` as final tail, general both paths → Task 1 (`build_turn_final_context`) + Task 2 wiring + Task 4 (suffix + legacy tests). ✓
- `evidence_precedence_directive` capture label → Task 2 + covered by Task 4 no-evidence test (absence) and suffix test (presence). ✓
- Widened seam guard `if transcript_context or evidence_directive:` → Task 2. ✓
- `evidence_directive_is_suffix` telemetry → Task 3 + test. ✓
- Call-site raw-transcript guard (#5) → Task 4 Step 3. ✓
- Existing `:297` + `:430` updated → Task 5 + Task 4 Step 1. ✓
- `:479` untouched → not modified by any task. ✓
- No verifier/fallback/judge/soul-edit; `_DISPATCHER_INSTRUCTION_BLOCK` untouched → no task adds them. ✓

**2. Placeholder scan:** the Task 4 tests reference helper methods (`_build_daemon_for_handle_message`, `_handle_message_mock_stack`, `_captured_messages_holder`) that may need extracting from the existing suffix test — Task 4 Step 3 NOTE makes that an explicit refactor instruction, not a placeholder. Web-search mock shape is pinned by reference to the Slice-2 daemon test. No "TBD"/"handle edge cases".

**3. Type consistency:** `turn_evidence_state(*, transcript, web_context) -> EvidenceState`; `EvidenceState(evidence_present, marker_labels, descriptions)`; `build_evidence_precedence_directive(state)`; `build_turn_final_context(transcript_context, evidence_directive)`; `_summarize_daemon_prompt_messages(..., evidence_directive="")` — names consistent across Tasks 1-4. The directive's stable suffix `"the evidence above contradicts that."` is asserted identically in Task 1, Task 4 Steps 1/4. ✓

## Notes for the executor

- Cross-lane: Codex implements task-by-task; Claude verifies before merge (read source, run focused + broad independently, confirm RED on Task 1 Step 2, Task 4 Step 1, Task 5 Step 1).
- The single highest-risk requirement is Task 2 passing RAW `transcript` (not `transcript_context`) to `turn_evidence_state`, guarded by Task 4 Step 3. Do not "fix" a failing directive by feeding it `transcript_context`.
- After merge: Obs 14 (flag-ON short window) is the live witness — does the computed steer alone make the voice answer from the substrate post instead of "DuckDuckGo blocked"? Result decides whether Slice 3b (verifier) is needed.
