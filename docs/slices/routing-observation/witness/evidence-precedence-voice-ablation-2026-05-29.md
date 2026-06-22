# Voice Ablation — B′ (Single Voiced Clean Call) Confirmed

**Date:** 2026-05-29
**Question:** Can Maez's voice be restored over the clean evidence answer WITHOUT re-introducing the knowledge-conflict ("blocked") prior — and in one call or two?
**Method:** A/B/B′/C ablation against the live model (`qwen36-27b`), read-only. Same evidence + probe as the diagnostic.
**Harness:** `scripts/validate/evidence_precedence_voice_ablation.py`
**Raw:** `docs/slices/routing-observation/witness/evidence-precedence-voice-ablation-raw.json`
**Predecessor:** `evidence-precedence-diagnostic-2026-05-29.md` (proved clean→used, megaprompt→evades)

## Arms & Results (2 samples each)

| Arm | Shape | Verdict | Faithful |
|---|---|---|---|
| A CLEAN_FACTUAL | clean evidence call, faithful instruction, **no voice card** | MIXED, MIXED | 2/2 |
| B TWO_CALL | call1 factual → call2 voice render (scrubbed card) | EVIDENCE_USED, EVIDENCE_USED | 2/2 |
| **B′ SINGLE_VOICED** | **one call: evidence + question + scrubbed voice card + faithful instruction** | **EVIDENCE_USED, EVIDENCE_USED** | **2/2** |
| C TAIL_DUP | full megaprompt + evidence duplicated at the tail | HEDGED, MIXED | **1/2** |

## Verdict

**B′ confirmed as the architecture.** One clean call with selected evidence + owner question + scrubbed voice card + context-faithful instruction produced faithful, evidence-grounded answers in Maez's own voice, connected to the owner's world ("…the edge-AI direction we need to push"), with zero re-introduction of the "blocked" prior — 2/2.

## What each arm establishes

- **B′ (winner):** facts + voice + owner-relevance in ONE coherent call. The **scrubbed voice card works** — restoring voice did NOT bring back the knowledge-conflict ("blocked/can't search") prior. Validates the design's highest-risk detail (voice card must carry no capability/source-status vocabulary).
- **B (not broken, just heavier):** the two-call render also stayed faithful + voiced (the feared fragmentation/drift did not appear in these samples). But it costs two calls and a render surface for no quality gain over B′. Per the Cognition/Anthropic coherence finding, single-call is preferred for a coherence-critical single answer. **B′ wins on parsimony, not because B failed.**
- **A (voice card matters):** clean facts but mechanical/listy ("here are the recent posts: …") and slightly hedged (tripped an evasion token → MIXED). Confirms brevity alone yields a flat answer; the voice card does real work.
- **C (focused call is necessary):** duplicating evidence at the tail of the megaprompt was unreliable — one sample **fabricated a fake live search** ("Triggering a live search now…"), one hedged ("from my substrate cache"). You cannot cheaply patch the megaprompt; the focused call is required.

## Design nuance surfaced

The bare context-faithful instruction (arm A: "answer only from the evidence; if it doesn't cover, say so") slightly **over-hedged** — the caution framing induced a defensive tone. B′'s voice card ("give your read, opinionated, connect to the owner's world") counteracts it. **Recipe: faithful instruction + synthesize-and-opine voice card together** — faithfulness framing alone is too timid; voice card alone (without faithfulness) was never tested but risks drift. The pair is the balance.

## Confirmed Architecture (B′) — to spec

A general **Focused Cognition** organ (Reddit is just the first source):
1. **Working-set assembler** selects the turn's evidence (source-priority scored), excluding soul/ambient/history bulk.
2. **Ordering:** strongest evidence first, lightly repeated at the tail (U-curve, Lost-in-the-Middle).
3. **One B′ call:** selected evidence + owner question + scrubbed voice card + context-faithful instruction + inline citation requirement.
4. **Trace row:** evidence IDs, source types, prompt size, citations used, groundedness verdict (extends the Slice-1 flight recorder).
5. **Later:** router learns which working-set patterns work best (organ #3 / DSPy-style).

**Explicitly NOT:** IRCAN-style neuron reweighting (real research, but requires gradient/activation access llama.cpp/GGUF does not expose, binds the fix to Qwen internals → violates brain-swappability, and is unnecessary since the clean call already achieves faithfulness). No referee/replacement as the primary fix (the light groundedness verdict in the trace row is a monitor, not a fixer).

## Discipline Note

Three independent analyses (Codex, Claude, Grok) converged on B′ — but convergence is not a witness. The ablation was run anyway and it is what confirms B′ (and kills the cheap C hack, and shows the voice card both matters and is safe). Per Rohit: "Three AIs agreeing is not a witness. The witness decides." It did.

## Service Posture

Read-only diagnostic; no daemon changes, no maez state writes, flag untouched. Live daemon remains flag-absent on `e26938f`.
