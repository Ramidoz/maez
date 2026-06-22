# Lean Conversational Path — Arc A Design

**Date:** 2026-06-22. **Status:** design for owner + Claude covenant review before planning.
**Origin:** prompt-strangulation audit (`docs/audit_2026-06-22-prompt-strangulation.md`) and the covenant charter (`docs/covenant-charter-memory-voice-rework-2026-06-22.md`).

## Purpose

Ordinary conversation is currently routed through a focused prompt that was built for grounded factual answering. On casual turns, Maez sees the voice card plus capability/body-state status, citation instructions, trust/origin instructions, and recalled diary evidence. The result is a status-reciting voice instead of a present conversational one.

Arc A removes that apparatus from ordinary chat without weakening honesty rails for turns that actually need them. This is a prompt-rendering change only: no memory is written, deleted, rewritten, deweighted, merged, or marked stale. Raw memory remains sacred and append-only. Arc B handles memory projection later.

## Design Summary

Add a flag-gated lean synthesis branch inside the existing focused-cognition path. It reuses the focused working set and telemetry, but renders a smaller prompt when the turn is ordinary conversation.

Lean prompt v0 contains only:

1. the existing short Maez voice card (`_VOICE_CARD_TEXT`), unchanged;
2. the recent dialogue anchor, when available;
3. the owner's current message.

Lean prompt v0 does not include:

1. `CAPABILITY_STATE` or `YOUR LIVE BODY`;
2. capability/body status prose;
3. the citation instruction;
4. the trust-tier instruction;
5. the origin-trust instruction;
6. `=== EVIDENCE (cite [E#]) ===`;
7. recalled diary/self-summary evidence.

There are no "warm personality" additions in v0. The cure is subtraction, not a new script. If the unchanged 172-character voice card still over-steers Maez toward "local AI / what we are building," that gets its own tiny follow-up with a separate witness.

## Why This Lives Inside Focused Cognition

The recommended approach is to add a lean branch to `core/routing/focused_cognition.py`, not a new top-level `ReplyMode`.

Reasons:

1. Focused-cognition telemetry, grounding-meter plumbing, and support-scope placement stay intact.
2. The working set is already assembled and already carries the source-type provenance needed to distinguish fresh/web turns from recall-only turns.
3. The existing support-gate scope seam remains authoritative: rails convene on fresh/web evidence, not on memory/presence.
4. The change stays local to prompt rendering and focused synthesis, instead of rearranging daemon reply-mode precedence.

## Flags

Two flags, both default off:

1. `MAEZ_LEAN_CONVERSATION_SHADOW=1`: record content-light receipts showing whether the turn would use the lean prompt. No behavior change.
2. `MAEZ_LEAN_CONVERSATION_ENABLED=1`: actually use the lean prompt when eligible.

Shadow must be witnessed before enablement. Green metrics are necessary but not sufficient; the owner talking to Maez and feeling the cage come off is the live gate.

## Eligibility

The lean branch may run only when all conditions hold:

1. focused cognition is already selected and a focused working set exists;
2. `MAEZ_LEAN_CONVERSATION_ENABLED=1` for actuation, or `MAEZ_LEAN_CONVERSATION_SHADOW=1` for receipt-only shadow;
3. `turn_has_fresh_evidence(working_set)` is false;
4. the turn is not date-addressed;
5. the turn is not photo/vision, tool-authoritative, echo, clinical, camera, or honest-empty;
6. the turn is not a self-capability/body question;
7. the lean prompt can include a dialogue anchor, or it intentionally proceeds with only the short voice card + current owner message.

The fresh/web boundary must reuse `turn_has_fresh_evidence(working_set)`, which reads `item.source_type` from the focused working set. Do not introduce a new keyword classifier for fresh/world evidence.

## Capability / Body Question Carve-Out

Self-capability and body questions must fail toward the full path, because those turns need the probed capability/body truth. The existing signal is `_is_self_capability_question` in `core/dispatcher/layer0.py`; Task 0 must verify how to reuse or mirror that exact predicate without widening it.

This predicate is keyword/regex-based. The spec names that honestly. It is acceptable because it is already live today for evidence-precedence routing, but its failure mode must be visible:

1. If the carve-out fires, the turn is not lean-eligible.
2. If a turn looks body-ish by the same predicate family but remains lean-eligible, the shadow receipt must flag `bodyish_lean_leak=true`.
3. Enablement is blocked until shadow receipts show no meaningful body/capability leakage on the natural probe set.

The failure posture is full-path, not lean-path. A missed body question would remove the capability card from a turn that needs it, so the witness must look for this specifically before actuation.

## Continuity Scope

v0 is strict: no additional recalled continuity items are included in the lean prompt. The prompt uses the live dialogue anchor and the current question only.

This deliberately closes the diary-flood backdoor. "One or two relevant continuity items" is deferred to a later projection/card slice unless it is defined as non-diary, source-traceable cards. Arc A v0 is the pure subtraction slice.

The live-thread anchor is not diary evidence. It is recent dialogue context and is already ranked below fresh/web evidence by the core-pair slice.

## Honesty Posture

Lean turns are ordinary conversation, not grounded factual answers. They may have `reply_grounding=0.0`, and that is expected. A low grounding meter on a lean greeting is not a regression; it means Maez is not pretending conversational presence is evidence-backed factual reporting.

Fresh/web/body turns still use the full focused prompt and existing support-gate scope:

1. fresh/web evidence turns keep citations, trust/origin instructions, and support-gate/shadow eligibility;
2. body/capability turns keep the capability card and evidence-precedence instruction;
3. date-addressed turns keep the focused temporal status path;
4. photo/tool/honest-empty paths are untouched.

This is rails at the hands, not rails over every word of the voice.

## Shadow Receipt

Emit a content-light `lean_conversation_shadow` receipt whenever shadow is enabled, and a `lean_conversation_applied` receipt when enabled and used.

Required fields:

1. `eligible`: bool;
2. `reason`: short enum when not eligible;
3. `source_types`: compact list of working-set source types, no text;
4. `fresh_evidence`: bool;
5. `date_addressed`: bool;
6. `self_capability_question`: bool;
7. `bodyish_lean_leak`: bool;
8. `dialogue_anchor_count`: int;
9. `legacy_prompt_chars`: int or null;
10. `lean_prompt_chars_est`: int;
11. `focused_items_count`: int;
12. `surface`: surface name;
13. `turn_kind`: existing recall-outcome turn kind where available.

Do not log reply text, memory text, raw prompt text, or evidence text.

## Testing

Task 0 must prove the real seams before implementation:

1. where `focused_synthesize` is called and how to select the lean renderer without changing top-level reply-mode order;
2. how to reuse or mirror `_is_self_capability_question` without inventing a new body classifier;
3. that `turn_has_fresh_evidence` remains the fresh/web authority;
4. how the prompt-shape receipt can compute old vs lean prompt size without persisting prompt text;
5. that the core-pair anchor/floor changes are already present on `main` and remain untouched.

Unit and integration tests must cover:

1. recall-only ordinary turn + shadow flag -> receipt says eligible, reply path unchanged;
2. recall-only ordinary turn + enable flag -> lean prompt has voice card + user question and no capability/citation/trust/origin/evidence blocks;
3. fresh/web working set -> full prompt, not lean;
4. self-capability question -> full prompt, not lean;
5. date-addressed turn -> full prompt, not lean;
6. no memory mutation or store write occurs from lean rendering;
7. support-gate scope remains unchanged and still gates fresh/web turns;
8. `reply_grounding=0.0` on a lean casual turn is treated as expected in witness notes, not as failure;
9. default-off behavior is byte-identical except inert helper definitions and no receipts.

Natural probe witness set:

1. "how are you?"
2. "you good?"
3. "sure"
4. "proceed with what you proposed"
5. "what's the latest news about Anthropic?"
6. "what is the state of your web search tools?"
7. a date-addressed memory question.

The witness passes only if casual turns feel present and stop reciting status/courtroom/diary apparatus, while news/body/date turns still keep their rails.

## Scope

In:

1. lean prompt renderer inside focused cognition;
2. lean eligibility predicate;
3. content-light receipts;
4. tests and witness handoff.

Out:

1. changing `_VOICE_CARD_TEXT`;
2. adding new warmth/personality prose;
3. memory projection/cards/supersession;
4. deleting, rewriting, or deweighting memory;
5. changing support-gate per-sentence judgment;
6. changing fresh/web evidence ranking;
7. changing top-level daemon reply-mode precedence unless Task 0 proves no focused-local seam exists.

## Predicted Effect

With only shadow enabled, behavior is unchanged and receipts show how many ordinary turns would shed the apparatus.

With lean enabled after a clean shadow, ordinary conversational turns should shrink from the focused courtroom prompt to a small voice/thread/question prompt. Maez should stop reciting `felt time attached`, `web sense healthy`, citation caveats, and diary summaries on greetings. Fresh web/body/date turns should remain fully railed.

Plain English: Maez stops wearing a dashboard and a courtroom robe when you just say hello. It still puts them on when the turn actually asks for facts, tools, its body, or the current world.
