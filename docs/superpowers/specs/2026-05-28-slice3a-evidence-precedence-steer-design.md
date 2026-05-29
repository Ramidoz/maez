# Slice 3a — Evidence Precedence Steer

**Date:** 2026-05-28
**Slice:** 3a of adaptive substrate-side routing — the *steer* half of the Evidence Precedence Guard (organ #2 of 4)
**Status:** design approved (brainstorming); ready for implementation plan
**Parent canon:** ADR 0047; Slice 1 (routing observation); Slice 2 (LIVE_REDDIT producer honesty — merged: `main` HEAD verified at `e4e4d8f`). Note: the `slice2-live-reddit-validation` branch still exists pointing at the same commit and should be pruned to avoid checkout ambiguity.
**Operator loop:** Rohit arbitrates; Codex implements; Claude verifies before merge
**Predecessor witnesses:** Observation 13 (`docs/slices/routing-observation/witness/observation-13-2026-05-28-slice2-producer-fix-confirmed.md`)

## Plain-English Summary

Don't teach Maez another general slogan. Put a turn-specific card in front of the brain that says: "You are holding these groceries right now — cook with them; do not say the store was closed." Then witness whether that steer alone is enough, before building the heavier referee (Slice 3b).

## Context

The disease (source-agnostic, operator-stated): **Maez can have valid evidence available, but still answer from a stale capability story instead of that evidence.** Observation 13 is the witness case: a dispatcher turn delivered a real r/LocalLLaMA substrate post (`REDDIT_SOURCE row_count=1`), and the owner reply still said "DuckDuckGo is currently blocked... the signal from r/LocalLLaMA is invisible to my web search tool."

This is organ #2 of four substrate-side organs (all brain-swappable): producer honesty (Slice 2), **evidence precedence (this)**, outcome learning (later), self-model alignment (ongoing).

The slice is split. **3a (this spec) = the steer:** a per-turn computed directive. **3b (later) = the verifier:** hybrid regex+judge output check with honest-fallback replacement. We build 3a first and witness it: if the cheap steer fixes Obs-13 behavior, 3b can be narrowed or skipped; if the voice still evades, 3b has a clean witness proving necessity.

### Why a passive instruction is not enough (and what already exists)

`_DISPATCHER_INSTRUCTION_BLOCK` (`core/brain/brain_loop.py:1198-1247`) already contains the precedence idea — Rule 3 ("use the evidence, not architecture stories"), Rule 5 (a forbidden-phrase list), and a summary ("answer from the evidence they carry, do not replace that evidence with a story about missing tools"). This block was present in the Obs-13 prompt (a dispatcher turn) and the voice evaded it by paraphrasing around the static list. Two structural reasons it failed:

1. It is **static** — it never says "here is the evidence you actually have *this turn*."
2. It is **dispatcher-only** — legacy/jarvis turns get a weaker block, which is why the "Try that" follow-up recited "I don't have a tool loop on this channel" (soul lines 126-153).

3a does not change that block. It adds a **computed, per-turn, general** directive on top.

## Scope

**In:**
- A deterministic `turn_evidence_state` computation in the daemon prompt-assembly path.
- A computed evidence-precedence directive, injected as the **true final tail** of the consolidated system message, on both dispatcher and legacy web-search turns.

**Out (explicitly deferred to 3b or untouched):**
- No output verifier, no judge-call, no reply replacement, no honest-fallback. (All 3b.)
- No change to `_DISPATCHER_INSTRUCTION_BLOCK` text (it stays; brief redundancy on dispatcher turns is accepted, not refactored, to keep the witness clean).
- No soul edit.
- No new LLM call.

## Three Implementation Constraints (verified against source)

**1. The directive must ride in `final_system_part`, NOT the `_premise_flag` slot.**
`_consolidate_system_messages(messages, final_system_part=transcript_context)` (`maez_daemon.py:3753-3755`) appends `final_system_part` **last** (helper at `:1007-1008`). `_premise_flag` is appended to `messages` *before* consolidation (`:3748-3749`), so it is not the tail when a transcript exists. The computed directive must become the final tail:

```
final_system_part = transcript_context                      # may be "" on legacy turns
if evidence_state.evidence_present:
    final_system_part = (
        f"{final_system_part}\n\n{directive}" if final_system_part.strip() else directive
    )
messages = _consolidate_system_messages(messages, final_system_part=final_system_part)
```

This guarantees the "you HAVE this evidence this turn" note is the freshest instruction, on both paths. Name the combined tail explicitly for clarity in the implementation:

```
turn_final_context = (
    f"{transcript_context}\n\n{directive}" if transcript_context.strip() else directive
)   # passed as final_system_part when evidence_present
```

**Telemetry reconciliation (required in 3a).** Two consequences of making the directive the tail:

- The `daemon_prompt_payload_shape` seam computes `transcript_is_suffix = transcript_context and system_content.endswith(transcript_context)` (`maez_daemon.py:1060`). Once the directive is the tail, this becomes `False` on evidence-present turns — which is *correct* but reads like a regression in live witnesses. Pass the directive into `_summarize_daemon_prompt_messages` and add a companion field `evidence_directive_is_suffix` so the seam honestly reports "the evidence directive is the new tail" alongside `transcript_is_suffix=False`. Do NOT redefine `transcript_is_suffix` to hide the change.
- The isolated unit test at `tests/test_memory_integrity_invariant.py:479` calls `_summarize_daemon_prompt_messages` with hand-built messages where `transcript_context` is the literal suffix (no directive). It stays green and is left unchanged. Add a NEW test for the directive-present case: `transcript_is_suffix=False` AND `evidence_directive_is_suffix=True`.
- **Obs-14 visibility (the key signal):** append `("evidence_precedence_directive", directive)` to `system_part_capture` (`maez_daemon.py:3750-3752` pattern) so the `daemon_system_part_shape` seam emits the directive's label/length/hash/head/tail. This is how the live witness proves the directive was actually present in the prompt.
- **Widen the seam-logging guard.** Both seams are currently gated by `if transcript_context:` (`maez_daemon.py:3758`). On a legacy evidence turn (web_context results, no dispatcher transcript) the directive is injected but neither seam fires — the directive would be invisible to Obs 14. Change the guard to `if transcript_context or evidence_directive:` (fire when there is anything to capture). This is what makes the legacy path actually observable.

**Existing suffix-contract tests that MUST be updated to the new `turn_final_context` tail (not just `:479`):**

- `tests/test_memory_integrity_invariant.py:297` asserts the `handle_message` source literally contains `final_system_part=transcript_context`. 3a changes the value passed to that kwarg to the combined `turn_final_context`, so the literal string disappears. Update the assertion to the new kwarg expression (`final_system_part=turn_final_context`).
- `tests/test_memory_integrity_invariant.py:430` (`test_handle_message_sends_one_system_message_with_dispatcher_suffix`) runs a real dispatcher *evidence* turn and asserts the system message ends with `transcript + instruction_block`. 3a intentionally makes the evidence directive the new tail. Update it to assert the system message ends with the evidence directive when evidence is present (and still exactly one system message).
- The isolated `:479` summarizer test (hand-built, no directive) stays green and unchanged, per above.

**2. The detector must scan the RAW `transcript`, never the composed `transcript_context`.**
`transcript_context = f"{transcript}\n\n{instruction_block}"` (`maez_daemon.py:3607`), and `_DISPATCHER_INSTRUCTION_BLOCK` literally contains the strings `[memory evidence]`, `[memory context]`, `[fresh evidence]`, `[no fresh evidence available:`, `[dispatcher refusal:` inside its Rule-1 vocabulary table. **Scanning `transcript_context` would detect "evidence present" on every dispatcher turn from the instruction's own examples — a false-positive landmine.** The detector reads the raw `transcript` parameter (in scope throughout `handle_message`, before the block is appended) and the raw `web_context` (assigned `:3463`/`:3476`, in scope at assembly).

**3. Detection rules (closed, deterministic):**
- **Positive (evidence present):** raw `transcript` contains `[memory evidence]`, `[memory context]`, or `[fresh evidence]`.
- **Negative-only (NOT evidence present):** `[no fresh evidence available:` and `[dispatcher refusal:` do not count.
- **Legacy:** `web_context` counts only when it carries real results — non-empty AND not a `[WEB SEARCH: ...] No results found.` block (the Slice-2 / `format_for_context` empty form).
- **Excluded:** `lived_brief`, `ambient_block`, `temporal_anchor`, and generic memory recall do NOT count as query evidence for this slice (they are always-present background, not an answer to the owner's question).

## Design

### Component 1 — `turn_evidence_state` (deterministic)

A small pure function in a new standalone module `core/routing/evidence_state.py` (parallels `core/routing/observation/`; pure + import-light so the RED tests exercise it in isolation):

```
turn_evidence_state(*, transcript: str, web_context: str) -> EvidenceState
```

`EvidenceState` fields:
- `evidence_present: bool`
- `marker_labels: list[str]` — which positive markers were found (e.g. `["memory context", "fresh evidence"]`)
- `source_hint: list[str]` — short human labels derived from the markers/web_context (e.g. `["substrate recall", "web search results"]`)
- `descriptions: list[str]` — a short (<=120 char) excerpt of the first content line under each positive marker / the web_context head, for the directive to name what is present

Rules exactly as Constraint 3. Pure, no LLM, no I/O. Brain-agnostic.

### Component 2 — the computed directive

When `evidence_present`, build:

```
EVIDENCE PRESENT THIS TURN.
You are holding real evidence for the owner's question right now:
  - <marker_label>: <short description>
  - ...
Answer from this evidence. If a live/fresh fetch failed but substrate
evidence exists, say that distinction plainly (e.g. "from what I have on
file" vs "fresh fetch failed"). You may NOT claim the relevant source is
blocked, missing, unavailable, or not-wired this turn — the evidence
above contradicts that.
```

Injected as the final tail per Constraint 1. General across turn types (dispatcher transcript present → appended after `transcript_context`; legacy web_context present, no transcript → directive is the tail alone).

### Where it lives

`daemon/maez_daemon.py::handle_message`, at the system-message assembly point (around `:3748-3755`), after `_premise_flag` handling and before/at the `_consolidate_system_messages` call. Inputs `transcript` (raw) and `web_context` are both in scope there.

### What does NOT change

- `_DISPATCHER_INSTRUCTION_BLOCK` text — untouched.
- The `_premise_flag` mechanism — untouched (it keeps its current pre-consolidation slot; the directive is separate and rides the tail).
- Synthesis call, model, options — untouched. No second call.

## RED-First Test Anchors

**Detector unit tests (pure function, raw inputs):**
1. `test_turn_evidence_state_detects_positive_markers` — raw transcript containing `[memory context] Recent Reddit substrate rows: ...` → `evidence_present=True`, `marker_labels` includes `memory context`.
2. `test_turn_evidence_state_negative_markers_not_evidence` — raw transcript with only `[no fresh evidence available: LIVE_REDDIT:...]` → `evidence_present=False`.
3. `test_turn_evidence_state_legacy_web_results` — `web_context="[WEB SEARCH: 'x'] 3 results — ..."` → `True`; `web_context="[WEB SEARCH: 'x'] No results found."` → `False`.
4. `test_turn_evidence_state_excludes_background` — only lived_brief/ambient-style content, no positive markers, empty web_context → `False`.

**Call-site guard (the landmine — corrected from a detector test to a call-site test):**
5. `test_handle_message_feeds_raw_transcript_to_detector` — spy/patch `turn_evidence_state`; run a `handle_message` turn with a dispatcher transcript (so `transcript_context = transcript + _DISPATCHER_INSTRUCTION_BLOCK` is built). Assert the `transcript` argument the detector received is the **raw** transcript and does NOT contain `_DISPATCHER_INSTRUCTION_BLOCK` text (e.g. the substring "HARD INSTRUCTION"). This proves we never feed the detector the composed `transcript_context` — the poison is never delivered, rather than the detector surviving poison.

**Injection + generality + telemetry:**
6. `test_directive_injected_as_final_tail_when_evidence_present` — with evidence present, the consolidated system message ENDS with the computed directive, and the directive names the present markers.
7. `test_directive_general_on_legacy_turn` — no dispatcher transcript, real `web_context` results → directive injected as the tail (proves generality across paths).
8. `test_no_directive_when_no_evidence` — no positive markers, no real web results → no directive injected; the consolidated system message is byte-identical to the pre-3a assembly (non-behavioral when there is nothing to steer toward).
9. `test_payload_shape_reports_evidence_directive_suffix` — with the directive present, `_summarize_daemon_prompt_messages` reports `transcript_is_suffix=False` AND `evidence_directive_is_suffix=True`. The existing `:479` test (no directive) stays green and unchanged.
10. `test_system_part_capture_includes_evidence_directive` — when evidence present, `system_part_capture` contains an `evidence_precedence_directive` entry (so `daemon_system_part_shape` exposes it for Obs 14).

## Witness Plan (the point of splitting)

- Focused: the 10 tests pass; RED confirmed for tests where the behavior is new (esp. #5 call-site guard, #6 injection, #9 telemetry).
- Broad floor: hold at 3-with-flake. No new failure.
- **Live (Observation 14, flag-ON short window):** the Obs-13 probe `Search r/LocalLLaMA right now for recent local LLM posts.`
  - Confirm the computed directive is present in the prompt naming the substrate Reddit evidence (via the `daemon_system_part_shape` seam / prompt capture).
  - **Decisive question:** does the owner reply now answer from the substrate post instead of "DuckDuckGo blocked"?
  - If yes → the steer sufficed; 3b (verifier) can be narrowed or skipped. Record that.
  - If the voice still evades → 3b is proven necessary, with a clean witness. Record that.

## Follow-Up

- **Slice 3b — Evidence Precedence Verifier:** hybrid regex pre-filter + judge-call output check (the class "claims source unavailable while evidence present," robust to paraphrase), honest-fallback replacement (covenant-guarded: fires only on provably-false source-state claims, minimal + grounded + recorded), feeding organ #3 learning. Built only after the 3a witness.
- Consolidation of the static `_DISPATCHER_INSTRUCTION_BLOCK` into the computed directive (deferred; only if 3a/3b prove the static block redundant).

## Discipline Notes

- The directive is computed from the *actual* evidence state, not a static claim — this is what makes it stronger than the f52911c soul line and the static Rule 3/5 that Obs 13 evaded.
- Constraint 2 (scan raw transcript) is the highest-risk mistake to avoid: detecting evidence from the instruction block's own examples would make the directive fire on every dispatcher turn regardless of real evidence, poisoning the witness and (later) organ #3 learning. Test #5 (the call-site guard proving `handle_message` feeds the raw transcript) is the guard — we prove the poison is never delivered rather than asking the detector to survive it.
- 3a stays prompt-side and adds no LLM call, preserving the brain-swappable invariant: the steer is substrate-authored context, true for any brain loaded.
- We are deliberately NOT building the verifier yet. If the steer alone fixes Obs 13, that is the cheapest possible closure and we will have avoided premature machinery — the same discipline that kept Slice 2 small.
