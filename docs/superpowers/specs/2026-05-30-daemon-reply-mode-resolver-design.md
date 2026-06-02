# Daemon Reply-Mode Resolver — Design

> 2026-05-30. Re-architects `MaezDaemon.handle_message`'s reply-decision path into one declared-precedence
> resolver, after the switchboard found B2 and B4 — the *same* bug class (independent candidate flags whose
> precedence is emergent from flag-exclusions × `if/elif` order, which drift). Builds on the
> temporal-continuity v2 work (`temporal-continuity-precedence-v2`); subsumes the B4/B5 fixes.
> Brain-swap-safe, substrate-side. **Staged** delivery to de-risk the refactor.

**Goal.** Replace the scattered candidate flags + `if/elif` chain + early returns in `handle_message`
with a single pure `resolve_reply_mode(signals) -> ReplyDecision` carrying an explicit, total, ordered
precedence. Every turn maps to exactly one mode in one place; precedence becomes *declared*, not emergent;
new modes are a table entry, not a flag-plus-hope. B4/B5 fall out of the declared precedence.

**The pattern being fixed (verified, from the dispatch map).** Today the decision is split across:
independent booleans (`authoritative_tool_reply`, `_current_turn_echo_reply`, `_honest_empty_candidate`,
`_focused_candidate`), each hand-maintaining its own exclusion conditions; an `if/elif` chain whose order
is the *real* precedence; a `_focused_used` + `reply is None` state machine spanning the final `else`; a
fourth re-derivation `_legacy_call_purpose` for logging that can drift; and two early returns
(clinical-boundary, camera) that bypass the whole tail invisibly. Two of these already drifted:
- **B2** (fixed in v2): `_focused_candidate` forgot `date_addressed`.
- **B4** (open): `_honest_empty_candidate` forgot to exclude `date_addressed`, and sits *before* focused.
Same bug, different flag. Patching flags can't fix the structure.

## Mode inventory (the full decision path, current true precedence)
From the verified map of `handle_message` (3184–4498):
1. **CLINICAL** — clinical-boundary/crisis (early return ~3257; **skip_tail**: bypasses audit/memory/trace/ledger)
2. **CAMERA** — camera-presence direct answer (early return ~3263; **skip_tail**)
3. **TOOL** — `authoritative_tool_reply` (~3900)
4. **ECHO** — intra-turn echo (~3902)
5. **HONEST_EMPTY** — empty web search, no evidence/dialogue (~3903)
6. **FOCUSED** — focused cognition (~3944; with dated/legacy execution fallback)
7. **DATED_HONESTY** — deterministic dated-recall honesty (~4037; sub-state of FOCUSED fallback)
8. **LEGACY** — megaprompt LLM synthesis (~4044)
9. **BACKEND_ERROR** — owner-visible error (degenerate sub-mode of LEGACY ~4079)

## Architecture

**1. `ReplyDecisionSignals` (hoisted to the first behavior-preserving safe point).** A dataclass with every
decision input: `is_voice`, `authoritative_tool_reply`, `echo_reply`, `dialogue_needs` (needs_dialogue or
fail_safe_legacy), `date_addressed` (`absolute_recall_cue(text).is_address`), `evidence_present`,
`web_search_ran`, `web_search_empty`, `focused_enabled`, `clinical` (result/answer), `camera_answer`.
This hoist removes the mid-assembly scatter and the `_empty_web_search` conflation: today
`_empty_web_search` is False both when search never ran and when it ran-nonempty; we split into
`web_search_ran` + `web_search_empty` where **`web_search_empty` ≡ today's `_empty_web_search`**
(behaviorally identical, since empty implies ran) and `web_search_ran` is new clarity used only by Slice 2.

**Behavior-preservation constraint:** "hoisted" does **not** mean "compute every possible signal before the
early-return guards." Clinical and camera currently return before trace start, web search, ledger writes,
audit, memory store, and LLM synthesis. Slice 1 must preserve that. Implement signal collection in phases:
- **pre-tail signals:** subjective-duration owner-contact side-effect (already before the guards), clinical
  result, camera answer, and static source/text fields. Call `resolve_reply_mode` with these available; if it
  returns a `skip_tail` mode, emit that reply and return exactly as today.
- **tail signals:** only after no skip-tail decision exists, compute/build the existing trace, web-search,
  transcript/evidence, echo, dialogue, date, focused, and tool signals at their current safe points.

The resolver still owns precedence; phased signal collection only preserves today's side-effect ordering.
Golden tests must pin that clinical/camera turns do **not** call trace/web/audit/memory/ledger/LLM.

**2. `ReplyMode` enum + `ReplyDecision`.** `ReplyDecision = {mode: ReplyMode, reply: str | None,
call_purpose: str, skip_tail: bool, skip_reason: str | None}`. `reply` is populated only for deterministic
modes (CLINICAL/CAMERA/ECHO/TOOL/DATED_HONESTY); generative modes (FOCUSED/HONEST_EMPTY/LEGACY) leave
`reply=None` and are executed by the dispatcher. `call_purpose` is the single source of the logging label
(kills the `_legacy_call_purpose` drift).

`DATED_HONESTY` and `BACKEND_ERROR` are **execution outcomes**, not initial resolver winners. The initial
resolver chooses `FOCUSED` or `LEGACY`; the focused executor may then return a final outcome of
`DATED_HONESTY` (deterministic no-dated-memory reply) or fall through to `LEGACY`, and the legacy executor
may end in `BACKEND_ERROR`. Tests should assert both the initial resolver mode and the final outcome where
that distinction matters. This avoids a second hidden resolver inside the focused branch.

`call_purpose` is used only where today's prompt-shape logging exists. Slice 1 must not create new prompt
logs for CLINICAL/CAMERA skip-tail turns; their `call_purpose` is structural metadata for the resolver and
future content-free breadcrumbs, not a new logging side-effect.

**3. `resolve_reply_mode(signals) -> ReplyDecision` — pure, total, one declared precedence:**
```
clinical.matched          → CLINICAL  (skip_tail=True, skip_reason="deterministic_policy_reply")
camera_answer is not None → CAMERA    (skip_tail=True, skip_reason="deterministic_policy_reply")
authoritative_tool_reply  → TOOL
echo_reply                → ECHO
focused_enabled and not is_voice and (date_addressed or evidence_present or dialogue_needs)
                          → FOCUSED
web_search_ran and web_search_empty and not date_addressed and not evidence_present and not dialogue_needs
                          → HONEST_EMPTY
otherwise                 → LEGACY
```
**Slice-1 parity note:** to be byte-identical to today, Slice 1 keeps today's *actual* order, which is
HONEST_EMPTY *before* FOCUSED and FOCUSED's condition *including* `date_addressed` (the B4 bug). The table
above is the **Slice-2 corrected** order (FOCUSED before HONEST_EMPTY; HONEST_EMPTY excludes
`date_addressed`). Slice 1 encodes the buggy order; Slice 2 flips exactly those lines.

**4. Execution dispatch.** A single `match mode:` executes the resolved mode and its side-effects
(telemetry, `record_focused_cognition_run`, etc., moved verbatim from their current branches). FOCUSED's
execution-time fallback is a **declared chain**, not a re-decision: try focused; if it yields a non-empty
reply → done; else if `date_addressed` → DATED_HONESTY; else → LEGACY. **B5 fix (Slice 2):** the
DATED_HONESTY fallback distinguishes *focused produced no `date_confirmed` item* (→ honest absence:
"I don't have a dated memory for that window") from *focused crashed with a `date_confirmed` item assembled*
(→ transport-failure: "I couldn't pull that up just now") — never a false absence claim.

**5. `skip_tail` modes (declared, not hidden).** CLINICAL/CAMERA carry `skip_tail=True` +
`skip_reason="deterministic_policy_reply"`. The dispatcher, seeing `skip_tail`, emits the reply and skips
the tail (audit/memory/trace/ledger) **exactly as today's early returns do** — behavior preserved, but the
bypass is now an explicit property the one resolver owns. `skip_reason` is structured so a later slice can
add a content-free trace/ledger breadcrumb without touching decision logic (NOT this slice).

## Staged delivery
- **Slice 1 — behavior-preserving extraction.** Build `ReplyDecisionSignals` + `ReplyMode` +
  `resolve_reply_mode` (encoding today's *actual* precedence, B4 bug included) + the `match` dispatcher;
  rewire `handle_message` to use them. Prove via a **golden routing truth-table test**: for an exhaustive
  matrix of signal combinations, the resolved mode + `call_purpose` + `skip_tail` equal what today's
  `if/elif`/early-returns produce. Plus golden tests that each mode's reply + side-effects are unchanged.
  No behavior change. This is the risky refactor, verified inert.
- **Slice 2 — the B4/B5 fix.** Flip exactly the two precedence lines (FOCUSED above HONEST_EMPTY;
  HONEST_EMPTY excludes `date_addressed`) and add the DATED_HONESTY absence-vs-transport distinction.
  Tiny, isolated behavior change, proven by the B4/B5 targeted tests + the v2 temporal tests. A routing
  regression here is unambiguously distinguishable from the intended fix.

## Non-goals
- **No learned intent classifier** (Approach C) — the resolver is the deterministic on-ramp; a future
  classifier can *feed* signals, not replace the declared precedence.
- **No change to any mode's behavior in Slice 1** (byte-identical). No new flag.
- **The post-reply mutators stay the tail, unchanged** — leak-strip, wondering-pursuit, audit,
  fragment-guard, memory store, ledger, trace. They alter reply *text*, not mode; the resolver does not
  touch them (except that `skip_tail` modes skip them, as today).
- No change to the temporal-continuity v2 internals (temporal_cue, provenance, recall) — this consumes
  `date_addressed`/`evidence_present`, it does not redefine them.

## Sequencing vs v2
This builds on `temporal-continuity-precedence-v2` (it consumes `absolute_recall_cue`/`date_addressed`).
B4 only bites when focused cognition is enabled (only then is there a dated-FOCUSED path for HONEST_EMPTY
to pre-empt); v2 is flag-gated, so **B4 is inert flag-off**. Therefore v2's verified B1/B2/B3 may merge
flag-off independently, and this resolver redesign (Slice 1 then Slice 2) lands before any default-on
decision. Branch this work off v2 (or off main after v2 merges).

## Testing
- **Slice 1:** exhaustive golden routing truth-table (signal matrix → mode/call_purpose/skip_tail equals
  today, including today's B4 ordering); per-mode reply + side-effect golden tests; skip-tail no-tail-call
  sentinels for clinical/camera; full daemon/handle_message suites unchanged; the broad floor unchanged
  (only the 3 documented).
- **Slice 2:** B4 (dated + web-trigger → FOCUSED/dated, NOT honest_empty), B5 (focused-crash-with-confirmed
  → transport-failure not absence), + the v2 temporal battery; integration witness; triad re-witness.

## Self-review
- **Placeholders:** none — the precedence table, the signal struct, the FOCUSED fallback chain, skip_tail
  semantics, and the staged test contracts are concrete. **Consistency:** `ReplyDecision` fields used
  identically across resolver/dispatcher/tests; `web_search_empty ≡ _empty_web_search` parity stated;
  Slice-1-buggy-order vs Slice-2-corrected-order called out explicitly so they don't conflate.
  **Scope:** decision path only; post-reply mutators + mode behaviors out (Slice 1); B4/B5 the only
  behavior change (Slice 2); intent-learning out. **Ambiguity:** "behavior-preserving" defined as
  byte-identical mode+call_purpose+skip_tail+reply+side-effects via golden tests; "skip_tail" defined as
  emit-reply-and-skip-audit/memory/trace/ledger exactly as today's early returns.
