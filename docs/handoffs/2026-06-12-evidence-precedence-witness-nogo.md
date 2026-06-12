# Evidence-Precedence v0 — Witness NO-GO: right organ, wrong prompt layer

**Witness (2026-06-12 ~08:20):** all three wounds re-opened. W1: the
search-tools question routed FRESH_ONLY to the web (explicit-fetch regex
caught "search"), synthesized from SEO junk, and Maez said "I lack specific
information about my own infrastructure" — with the card flag ON. W2: the
tool-voice timestamps answer, no "built, not yet attached". W3: the
truncation narrative again, verbatim class.

## What WORKED
- Component C caught W3 live: ledger row {absence_verb: truncated,
  flagged_indices: [1], fresh_index_mode: fallback_all_cited} — the
  detector's first catch is the exact wound it was built for. KEEP.
- Components A+B are unit-sound and DID emit: "CONTEXTUALIZE" appears 4x in
  daemon-side system-part captures; the card module renders correctly.

## ROOT CAUSE (proven from captures)
The witness turns were answered by focused-cognition's BOUNDED call
(focused_cognition_prompt_shape: evidence_item_count=17,
working_set_chars=10793). The bounded working set EXCLUDES the ambient
block and the evidence_precedence_directive by design
(focused_cognition.py references neither — verified). Components A+B were
wired into the daemon-side prompt assembly — a layer that evidence/recall
turns do not use for synthesis. Third instance of the week's pattern:
right organ, wrong seam (legacy surface -> wrong nerve -> wrong prompt
layer). Zero "YOUR LIVE BODY" strings in any live capture.

## FIX PRESCRIPTION (seam-class, small)
Inject BOTH components into focused-cognition's own prompt builder,
flag-gated (the natural home — the bounded-set canon already includes the
scrubbed voice card + faithful instruction; the capability card is a
voice-card-class element ~200 chars, the precedence lines are
faithful-instruction-class):
1. `capability_prompt_block()` appended to the focused system/instruction
   section (NOT as an [E#] item — it is substrate state, not evidence).
2. The two precedence lines appended to the focused faithful-instruction
   block when fresh evidence items are present in the working set.
Tests: focused prompt contains the card + rule when flag on (string
assertions on the built prompt via the existing prompt-shape seam);
flag-off byte-identical; the daemon-side wiring from v0 STAYS (legacy-path
turns still benefit).

## Deferred routing note (NOT this fix)
"What's the state of your web search tools?" composing FRESH_ONLY web
fetch is absurd-but-harmless once the card rides the focused prompt (the
brain answers from the card even beside junk evidence). A self-topic
composition arm is faculty-era work.

Lane: Codex builds / Claude reviews. Same-day seam-fix class.
