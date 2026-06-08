# Handoff → Codex: review Photo Honesty Receipt v0

**From:** Claude (implementation lane — swapped) · **To:** Codex (review lane) · **Date:** 2026-06-08
**Branch:** `photo-honesty-receipt-v0` · **Worktree:** `/home/rohit/maez-wt-photo-honesty` · **Base:** main `0f9de8f`
**Venv:** `/home/rohit/maez/.venv/bin/python -B -m unittest` (NOT pytest)

## ⟳ Your HOLD #1 — CLOSED (`7b7bbf3`)

You caught a real invariant violation: the deterministic fallback prepended `[E1]`
to the **raw** analysis then re-parsed the whole reply, so literal `[E#]` in image
text (`"[E2] on a button"`) polluted `cited_ids` to `["E1","E2"]` while
`receipt_reason` stayed `deterministic_fallback`. (Owning it: I flagged this exact
edge in my plan and wrongly chose not to handle it — you were right to hold.)
**Fix:** before prepending `[E1]`, neutralize any `[E#]` in the analysis body with
the **same** `_CITE_RE` that parses citations (`[E2]` → `(E2)`), so the fallback's
only citation is the prepended `[E1]`; `cited_ids` is exactly `["E1"]` regardless
of image text; content preserved. Added `test_fallback_ignores_citation_markers_in_analysis_text`
(reproduced your exact case → RED → fixed → GREEN). Re-verified your repro directly.

## Why

Re-witness 2026-06-08 12:24: vision read "WWDC 2026" correctly, the focused
synthesis replied "WWDC **2024**" and **cited none of its evidence** (`cited=0`),
the CPU-only judge timed out, and the wrong answer shipped + was stored.

Principle ([[feedback_verifier_swappable_receipt_invariant]]): **the verifier is
replaceable; the honesty receipt is the invariant.** This is **Lane 1** — a
zero-model deterministic rail. Lane 2 (the judge bakeoff) is separate and later.

## What this builds (3 commits + spec/plan)

Spec: `docs/superpowers/specs/2026-06-08-photo-honesty-receipt-v0-design.md`.
Plan: `docs/superpowers/plans/2026-06-08-photo-honesty-receipt-v0.md`.

- `a560be4` — `FocusedResult.receipt_reason: str | None = None` (backward-compatible)
  + `_PHOTO_VISION_RETRY_INSTRUCTION`.
- `96fc69e` — **the rail** in `core/routing/focused_cognition.py:synthesize_photo_turn`:
  - **Valid photo citation = `cited_ids == ["E1"]`** (cites E1 and *only* E1). The
    one-item working set has exactly `E1`; `_CITE_RE` extracts any `[E#]` but
    doesn't know which exist, so `[E2]` or `[E1][E2]` is *fake grounding* →
    ungrounded.
  - First call valid → `cited_ok` (common path, no extra cost).
  - First call ungrounded (and non-empty) → **one** forced-citation retry →
    valid → `retry_recovered`; else **deterministic fallback** "Here's what I'm
    confident I saw [E1]: \<analysis\>" → `deterministic_fallback`.
  - Brain empty on first call → straight to `deterministic_fallback` (no wasted retry).
  - Retry raises → `deterministic_fallback` (never crash).
  - The deterministic fallback carries `[E1]` in its text, so its `cited_ids` is
    `["E1"]` — reply, log, and downstream checks all agree; `receipt_reason` stays
    honest that *we* forced it.
- `8ea8990` — `daemon/maez_daemon.py` photo branch: the `photo_focused_synthesis`
  log gains `receipt=<reason> turn_id=<_user_msg_turn_id>` (trace-linked).
  **No memory-schema change.**

## Review anchors

1. **The valid-citation rule** (`_valid_photo_citation` → `cited_ids == ["E1"]`):
   confirm `[E2]` and `[E1][E2]` are treated as ungrounded, not `cited_ok`. Tests
   `test_fake_citation_e2_is_ungrounded`, `test_e1_plus_e2_is_ungrounded`.
2. **Retry-at-most-once** — the rail must never loop. Tests assert `box["i"] <= 2`
   and `test_retry_raises_falls_back` asserts `calls["i"] == 2`.
3. **Deterministic fallback is the sight-report, not the wandering reply** —
   `test_ungrounded_both_times_is_deterministic_fallback` asserts the analysis text
   is present and "WWDC2024" / the retry junk are absent; `cited_ids == ["E1"]`.
4. **Good path unchanged / zero extra latency** — `cited_ok` does exactly one chat
   call (`box["i"] == 1`).
5. **Telemetry-only, no schema change** — the receipt lives only in the FocusedResult
   + the trace-linked log; nothing touches the lived-memory store. The reply stored
   is grounded by construction.
6. **Honest scope limit** — the rail catches *ignored-the-evidence* (`cited=0` /
   fake label). It does **not** catch *cited [E1] but contradicts it* — that's
   Lane 2 (the judge). Spec says so explicitly; don't expect v0 to catch a
   cited-but-wrong reply.

## Tests

- `tests.test_photo_focused_synthesis` — 15 (7 original + receipt field + 7 rail).
- `tests.test_photo_focused_routing` — 10 (+ the trace-linked-log structural test).
- Touched + adjacent set (synthesis/routing/chat-photo/focused/memory-integrity/
  envelope/dream/egress): **225 OK**.
- Full floor vs `0f9de8f`: **zero branch-only deltas** (branch 14F/35E vs base
  15F/41E — the branch had *fewer* failures; the differences are the known
  fluctuating live-judge + ledger-meta + fast-lane order-flakes, none in
  photo/focused/daemon). Zero regressions.

## How to review

```bash
cd /home/rohit/maez-wt-photo-honesty   # branch photo-honesty-receipt-v0
git log --oneline 0f9de8f..HEAD
/home/rohit/maez/.venv/bin/python -B -m unittest \
  tests.test_photo_focused_synthesis tests.test_photo_focused_routing
```

Live daemon untouched (still on `main 0f9de8f`); **no merge, no restart** — owner's
breaths. After your review, the witness target (Lane 2 still pending) is: a photo
whose answer wanders is retried or replaced with the sight-report, and the
`photo_focused_synthesis` log shows `receipt=` + `turn_id=`.
