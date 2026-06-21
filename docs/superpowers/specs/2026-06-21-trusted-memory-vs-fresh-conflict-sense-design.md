# Trusted Memory vs Fresh Evidence — Conflict SENSE (Shadow Detector v0) — Design

**Date:** 2026-06-21. **Status:** design — owner-approved in shape (domain-routing action; detector shadow-first; CONTRADICTION sense, not support-absence; MiniCheck auxiliary-only); this doc is the **Slice 1 (detector)** spec for owner review before planning.
**Origin:** Thread B of the content-honesty arc ([[project_content_honesty_arc]]). The wound: asked "news about Anthropic", Maez *searched* (the fresh web block was in the prompt) yet asserted its own stale stored specifics ("Claude Corps") — **trusted-grade memory beat fresh evidence in the synthesis.** Thread C pulled Maez's *own unverified* replies (`self_web_claim`) out of that contest. Thread B is the general, still-open case: **genuinely trusted memory vs fresh evidence, disagreeing on substance.**

## The load-bearing bend (owner, 2026-06-21): contradiction, NOT absence-of-support

The detector hunts a **real clash** (premise-vs-claim CONTRADICTION), never "the fresh source failed to support the memory." **Unsupported ≠ contradicted** — that is the exact caveat wound we just fixed in the support gate, one layer deeper: a thin/incomplete/irrelevant fresh source must NEVER make Maez doubt a true memory. So:
- **Primary detector = a generalized `photo_contradiction` SENSE** (premise=fresh, hypothesis=memory-claim → looks for contradiction), "sense, not verdict," high precision.
- **MiniCheck (entailment-support) is AUXILIARY audition only** — it answers "supported?", not "contradicted?"; it may inform but must never be the contradiction signal.
- **Unavailable / low-confidence → `ambiguous` or nothing, NEVER accuse.** Precision ≫ recall: a false "your memory conflicts with reality" is corrosive (the inverse of the wound).

## Mechanism (generalize the photo-contradiction machinery)

`core/routing/photo_contradiction.py` provides the `ContradictionVerifier` Protocol (`predict(premise, hypothesis) -> ClaimVerdict`), a swappable verifier, and the contradiction-sense machinery. **Its existing `ContradictionReceipt`/`ReceiptClaimDetail` are NOT safe to reuse directly** — they may carry claim/premise TEXT (`claim_details[].text`, free-text `reason`/`sense_note`), which this slice must never log (see Slice 1 redacted receipt). So Slice 1 reuses the **verifier shape only** and emits a **separate redacted receipt**, generalizing "photo claims vs context" → "**trusted-memory claims vs fresh evidence**":
- **Pair** each TRUSTED-memory working-set item against the turn's FRESH items, in the SAME focused working set.
- **Trusted memory only — EXACT, fail-closed** (`EvidenceItem`, [focused_cognition.py:255-276](../../core/routing/focused_cognition.py#L255)): a memory item qualifies IFF `origin_trust in {"lived","covenant"}` **AND** `origin_provenance != "self_web_claim"`. **`origin_trust is None` or any unknown value → EXCLUDED** (fail-closed — vague trust metadata must NEVER count as sacred memory). No "owner-authored provenance" catch-all. Random / untrusted recall is NOT paired.
- **Fresh items**: `source_type in _FRESH_SOURCE_TYPES` (`fresh_evidence`, `web_context`) — reuse the predicate from the support-gate-scope slice.
- **Run the high-precision contradiction sense** (premise=fresh text, hypothesis=memory claim). The verifier is swappable (the honesty receipt is the invariant — [[feedback_verifier_swappable_receipt_invariant]]); Task 0 auditions the contradiction verifier (the photo one's verifier, or a frontier/NLI judge), MiniCheck listed only as an auxiliary candidate.

## Slice 1 — the SHADOW detector (THIS spec)

- At the focused-cognition seam (where `_focused_working_set` holds both fresh + memory), when a turn has BOTH a trusted-memory item and a fresh item, run the contradiction sense over the (fresh, trusted-memory-claim) pairs.
- Emit a **REDACTED receipt — content-light for REAL** (must-fix): the photo `ContradictionReceipt`/`ReceiptClaimDetail`/`ClaimVerdict` carry claim+premise TEXT (`claim_details[].text`, free-text `reason`/`sense_note`) — those MUST NOT be logged. This slice defines a SEPARATE redacted struct/projection: `mem_fresh_conflict_sense mem_id=.. mem_label=.. fresh_id=.. fresh_label=.. verdict=contradiction|neutral|ambiguous confidence=.. verifier=<name@version> mem_sha256=.. fresh_sha256=.. reason_code=..` — IDs, source labels, content **DIGESTS** (sha256), verdict, confidence, verifier name/version, a FIXED reason CODE. **NO memory text, NO fresh text, NO claim snippets** in any log/receipt ([[feedback_visible_substrate_state_not_chain_of_thought]], [[feedback_perception_free_egress_disciplined]]).
- **LOG ONLY — NO reply change, no governance, no surfacing.** This slice just learns whether the sense fires on *real* clashes and stays silent otherwise.
- **Fail-safe toward the memory:** verifier unavailable / low confidence / no fresh+trusted pair → `ambiguous` or no receipt, NEVER a contradiction accusation.
- Flag-gated, default-off = byte-identical.

## Slice 2 — domain-routing ACTION (named, OUT of this spec)

On a TRUSTED contradiction (after the detector is witnessed honest):
- **World / current-state fact** → fresh-current GOVERNS, and Maez NAMES the clash ("I had X stored; the current signal says Y — going with the fresh one").
- **Owner / relationship / biographical fact** → Maez does NOT overwrite trusted owner-memory from a fresh signal; it SURFACES + ASKS Rohit (he is ground truth).
- **Ambiguous domain** → surface cautiously / ask; never silently pick.
Always surface; never silently resolve ([[feedback_disagreement_is_signal]]).

## Make-or-break / guards (Task 0)

1. **Precision is the whole game.** Task 0 auditions the contradiction verifier and records a small labeled set (real clashes vs thin/irrelevant/partial fresh sources) — the detector must FIRE on real contradictions and stay SILENT on mere absence-of-support / thin sources. If it can't hit high precision, STOP (a crying-wolf detector is worse than none).
2. **Contradiction, not support.** The verifier interface is `predict(premise, hypothesis) -> {contradiction|neutral|entailment}` (NLI-shaped) or the photo verdict; MiniCheck's "supported/unsupported" is NOT wired as the contradiction signal.
3. **Trusted fields populated, or STOP (must-fix).** Task 0 PROVES `origin_trust`/`origin_provenance` are actually populated on memory items at THIS focused seam (not always `None`). If they are not reliably set, **STOP and build the provenance plumbing first** — a fail-closed predicate over always-`None` fields silently pairs nothing (a hollow detector). Pair only `lived`/`covenant` AND not `self_web_claim`.
4. **Pairing granularity proven BEFORE a detector lands (should-fix).** Whole-long-memory vs whole-fresh-item is noisy and kills precision. Task 0 fixes the exact pairing/chunking strategy (e.g. per-extracted-claim, with a bounded pair-budget per turn) and validates it on the labeled set; a `claim_limit_exceeded`-style cap is recorded honestly, never silently truncated.
5. **Receipt redaction (must-fix).** Task 0 confirms the redacted receipt logs NO claim/memory/fresh text — only IDs, labels, digests, verdict, confidence, verifier@version, reason code. A test asserts no item `text` leaks into the logged receipt.
6. **Shadow inert.** Flag-off = byte-identical; no reply touched; the sense never runs when off.

## Scope / out

**IN (Slice 1):** the trusted-memory↔fresh pairing; the generalized contradiction sense (verifier auditioned, photo-machinery reused); the content-light receipt; the shadow flag (default-off, byte-identical); tests. **OUT (Slice 2+):** the domain classifier; any governance/surfacing/ask behavior; overwriting or deweighting memory; changing the authority-label prompt. **NEVER:** treating MiniCheck "unsupported" as "contradicted"; pairing untrusted/`self_web_claim` recall; accusing on low confidence.

## Lane / owner-breath

Covenant-sensitive (Maez's relationship to its own memory) → full spec → plan → TDD → Claude two-stage + Codex cross-lane; STOP at the review gate. Shadow-first; graduate (Slice 2) only on a witnessed-honest detector. Slice-1 owner-breath: restart `maez`, set the shadow flag, live a turn that recalls a trusted fact AND pulls fresh evidence that clashes, and paste the `mem_fresh_conflict_sense ... verdict=contradiction` receipt — plus confirm it stays silent on a thin/irrelevant fresh source. No autonomous check.
