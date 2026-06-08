# Photo Honesty Receipt v0 — Design

**Date:** 2026-06-08 · **Lane:** Claude implements / Codex reviews (swapped) · **Branch:** `photo-honesty-receipt-v0`
**Slice:** Lane 1 of the two-lane plan. Lane 2 (judge bakeoff) is separate and later.

## Why (witnessed live)

Re-witness 2026-06-08 12:24: vision read the screen correctly ("WWDC 2026"), but
the focused synthesis replied "WWDC **2024**" and **cited none of its evidence**
(`cited=0`). The grounding judge that should have caught it **timed out** (CPU-only
4B, too slow — confirmed by Rohit; it timed out even at 20s), so the wrong answer
shipped *and* was stored in lived memory.

The principle ([[feedback_verifier_swappable_receipt_invariant]]): **the verifier
is replaceable; the honesty receipt is the invariant.** Don't architect around a
slow judge. Build a zero-model deterministic floor first, then audition faster
verifiers (Lane 2) behind the same contract.

`cited=0` is a deterministic, no-model signal that a photo reply *ignored its own
vision evidence*. That should never count as a trusted "I saw it" answer.

## Goal

A photo-focused reply that didn't ground itself in the photo evidence (`cited=0`)
**never reaches the user or memory as a trusted "I saw it" answer.** Zero model,
zero added latency on the good path, no memory-schema change.

## The rail — inside `synthesize_photo_turn` (`core/routing/focused_cognition.py`)

The function already does `reply = raw_reply or deterministic`, then computes
`cited_ids` from the reply text via `_CITE_RE`. The rail slots in right after:

**Valid photo citation** = `cited_ids == ["E1"]` (cites E1 and *only* E1). The
one-item photo working set contains exactly one evidence item, `E1`; `_CITE_RE`
extracts any `[E#]` label but does not know which labels exist. So a reply citing
`[E2]` or `[E1][E2]` is *fake grounding* — it confabulated a citation to a label
that isn't there — and must be treated as ungrounded, exactly like `cited=0`.
"Ungrounded" below means **not** a valid photo citation (`cited_ids != ["E1"]`).

1. **First call is a valid photo citation (`cited_ids == ["E1"]`):** accept.
   `receipt_reason = "cited_ok"`. *(Common path — no extra cost.)*
2. **First call ungrounded** (`cited_ids != ["E1"]` — empty, `[E2]`, `[E1][E2]`,
   etc.; and the reply was the brain's, not already the deterministic fallback):
   **retry once** with a forced-citation instruction
   (`_PHOTO_VISION_RETRY_INSTRUCTION`: "You did not cite the evidence. Every claim
   about the photo MUST cite [E1] (the only evidence) and no other label; if you
   cannot ground a claim in the analysis above, do not make it.").
   - Retry cites `[E1]` and no other evidence label (`cited_ids == ["E1"]`) →
     `receipt_reason = "retry_recovered"`, use the retry reply.
   - Retry still ungrounded → **deterministic fallback** (below).
3. **Brain returned empty on the first call** (`raw_reply == ""` → already the
   deterministic): straight to `deterministic_fallback`, no wasted retry.
4. **Retry raises / transport fails:** treat as ungrounded → `deterministic_fallback`.
   Never crash.

### Deterministic fallback (the floor)

```
reply = "Here's what I'm confident I saw [E1]: " + analysis_text
```

The `[E1]` marker is **in the text** (Rohit's tightening) so the reply, the
computed `cited_ids` (which will be `["E1"]`), the log, and any downstream citation
check all **agree**. `receipt_reason = "deterministic_fallback"` keeps it honest:
*we* forced the citation, the brain did not. The fallback is grounded by
construction — it is the vision analysis verbatim.

## The receipt (telemetry-only in v0, trace-linked)

- `FocusedResult` gains **`receipt_reason: str | None = None`** (frozen dataclass,
  default keeps every existing caller untouched / backward-compatible).
- The daemon photo branch (`daemon/maez_daemon.py` ~5984) already logs
  `photo_focused_synthesis ... cited=...`. It gains **`receipt=<reason>
  turn_id=<_user_msg_turn_id>`** — trace-linked, so "what happened to this photo
  reply?" is answerable by id.
- **No memory-schema change.** The reply stored is grounded by construction, so a
  separate stored "verified/unverified" stamp is not load-bearing yet. That
  structured, memory-stamped receipt is **Lane 2's** job, when the judge adds a
  dimension (`judge_passed | judge_unavailable | judge_failed`) that *cannot* be
  guaranteed by construction and so deserves to ride with memory.

## Data flow

photo turn → `synthesize_photo_turn` (cite → retry → deterministic) → grounded
reply + `receipt_reason` → daemon logs the receipt trace-linked to `turn_id` →
existing strip / audit / `store_telegram` / trace pipeline (the F1 fix) → memory
only ever stores a grounded photo reply.

## Error handling

- Retry brain call raises/times out → `deterministic_fallback` (honest, no crash).
- The retry's extra brain call costs latency **only on the `cited=0` path** (the
  failure case). `cited_ok` (the common path) has no extra cost.

## Honest scope limit

The cite rail catches *"ignored the evidence"* — exactly what `WWDC2024` was
(`cited=0`). It does **not** catch *"cited [E1] but still contradicts it"* — a reply
that cites yet lies. That second case is genuinely **Lane 2's** job (the judge),
because it cannot be guaranteed by construction. v0 is the floor, not the whole
house — and we say so rather than overclaiming.

## Testing (TDD)

1. `cited_ids == ["E1"]` on first try → no retry, `receipt_reason=cited_ok`.
2. Ungrounded first (`cited_ids != ["E1"]`), `cited_ids == ["E1"]` on retry →
   `retry_recovered`, retry reply used.
3. Ungrounded both times → `deterministic_fallback`; reply is the sight-report
   (contains `[E1]` + the analysis), **not** the wandering reply; `cited_ids==["E1"]`.
4. **Fake-citation case:** first reply cites `[E2]` (or `[E1][E2]`) — a label not
   in the one-item working set → treated as **ungrounded** → retry/fallback, never
   accepted as `cited_ok`.
5. **WWDC case:** a reply contradicting the evidence + `cited=0` → caught
   (deterministic fallback); the wandering "2024" reply is never returned.
6. Brain empty on first call → `deterministic_fallback` (no wasted retry).
7. Retry raises → `deterministic_fallback` (no crash).
8. Retry is invoked **at most once** (no infinite retry).
9. Daemon log carries `receipt=<reason>` and `turn_id=<...>` (trace-linked).
10. No memory-schema change (no new stored field).

## Out of scope (Lane 2)

The judge, `judge_passed | judge_unavailable | judge_failed`, the memory-stamped
receipt, and the verifier bakeoff (HHEM / MiniCheck / Qwen-reranker / LFM).

## Predicted effect

A photo reply that doesn't cite its vision evidence is retried once for a
citation; if it still won't, the user gets the deterministic "Here's what I'm
confident I saw [E1]: …" (grounded) instead of a wandering answer. The
`WWDC2024`-class hallucination is caught with **zero model latency on the common
path**. Memory only ever stores grounded photo replies. Trace-linked receipt logs
make "what happened to this photo reply?" answerable by turn id. Non-photo turns
and the `cited_ok` path are unchanged.
