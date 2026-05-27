# Recall-Axis Dispatcher — Codex Engineering Pass-2 Synthesis

**Prepared:** 2026-05-26
**Artifact reviewed:** `docs/slices/recall-axis-dispatcher/spec-brief.md` v1.2
**Dispatch brief:** `docs/slices/recall-axis-dispatcher/reviews/codex-engineering-pass2-brief.md`
**Review records:** `docs/slices/recall-axis-dispatcher/reviews/codex-*-pass2.md`

This document is derivative reconstruction. The six `codex-*-pass2.md` files are the witnessed review record.

---

## Verdict Summary

| Seat | Verdict |
| --- | --- |
| Peirce | STILL OPEN |
| Arendt | STILL OPEN |
| Huygens | STILL OPEN |
| Pauli | STILL OPEN |
| Ohm | STILL OPEN |
| Lovelace / Bernoulli | STILL OPEN |

Engineering pass-2 result: **STILL OPEN.**

v1.2 closed most of the pass-1 engineering trapdoors. The remaining findings are narrow and foldable. No reviewer raised a covenant-axis escalation.

---

## Per-Batch Closure Summary

| Batch | Closure Verdict | Seat Pattern |
| --- | --- | --- |
| 1. `CompositionSpec` availability state | CLOSED | 6 CLOSED |
| 2. Active vs reserved source state | CLOSED | 6 CLOSED |
| 3. JARVIS ingress exhaustiveness | CLOSED | 6 CLOSED |
| 4. Archetype scoring thresholds | STILL OPEN / split | 3 CLOSED, 3 STILL OPEN |
| 5. Archetype manifest and replay corpus | CLOSED | 6 CLOSED |
| 6. Shared MiniLM encoder | CLOSED | 6 CLOSED |
| 7. `InventorySummary` contract | CLOSED | 6 CLOSED |
| 8. Prompt assembly / audit ownership | STILL OPEN | 4 STILL OPEN, 2 CLOSED |
| 9. Refusal semantics | CLOSED | 6 CLOSED |
| 10. Repair FSM | STILL OPEN / split | 4 STILL OPEN, 2 CLOSED |
| 11. Fan-out result / timeout / merge | STILL OPEN / split | 3 STILL OPEN, 3 CLOSED |
| 12. External fetch owner / budget | CLOSED-with-split | 5 CLOSED, 1 STILL OPEN |
| 13. Module placement | CLOSED | 6 CLOSED |
| 14. Budget tests | STILL OPEN | 6 STILL OPEN |
| 15. Nits / cross-references | CLOSED | 6 CLOSED |

---

## Convergent Material Findings

### Batch 14 — Realistic Adapter-Budget Tests Still Missing

Seats: Peirce, Arendt, Huygens, Pauli, Ohm, Lovelace / Bernoulli.

All six reviewers agreed that v1.2 still does not close Batch 14. v1.2 defines warm/cold/prewarm budgets and adds full-manifest/source-count anchors, but the RED-suite split still describes integration tests around mock substrates. The pass-1 closure criterion required p95 adapter-budget tests against realistic local stores.

Current v1.2 evidence cited:

- `spec-brief.md:278`: warm/cold/prewarm Layer 0 budget.
- `spec-brief.md:314`: Layer 1 deadline / prompt budget.
- `spec-brief.md:684`, `spec-brief.md:698`, `spec-brief.md:701`: warm/cold, slow/error branch, and full-manifest test anchors.
- `spec-brief.md:703`: RED-suite split still framed around mock substrate integration.

Required v1.3 fold:

- Add a realistic-store adapter-budget test requirement.
- Require p95 assertions for representative local SQLite/WAL, Chroma, file-backed, and bounded-reader adapters.
- Distinguish pure unit mocks from adapter-budget fixtures.
- Add budget telemetry assertions for cold/prewarm, source-selection limits, slow-branch timeout/cancellation, full-manifest scoring, and total prompt-budget contribution.

### Batch 8 — Audit Metadata Contract Still Generic

Seats STILL OPEN: Peirce, Huygens, Pauli, Lovelace / Bernoulli.
Seats CLOSED: Arendt, Ohm.

The synthesis call is STILL OPEN. v1.2 names `core/dispatcher/provenance_renderer.py`, routes owner synthesis through it, and defines mismatch behavior. That closes module ownership. It does not define the concrete audit payload fields required by pass-2, and several reviewers flagged that `audit_assistant_text` is either omitted or only implicitly covered through `self_claim_audit`.

Current v1.2 evidence cited:

- `spec-brief.md:206-213`: provenance renderer ownership and generic audit metadata.
- `spec-brief.md:568-570`: owner synthesis path must route through renderer.
- `spec-brief.md:696`: `test_all_owner_synthesis_surfaces_route_through_provenance_renderer`.

Required v1.3 fold:

- Add a closed audit metadata contract.
- Name which fields go to `audit_assistant_text`, `core/safety/self_claim_audit.py`, or both.
- Required fields should include at least: `spec_digest`, schema version, `composition_hint`, `provenance_framing`, `substrate_sources`, `external_sources`, source role map, `inventory_witness`, `source_availability`, `availability_limitations`, rendered block roles, template id, template version/hash, mismatch/refusal reason if any, utterance digest, surface, timestamp, and no-raw-private-content rule.
- Add a RED anchor proving the audit envelope is emitted.

### Batch 10 — Cross-Surface Repair Isolation Test Missing

Seats STILL OPEN: Arendt, Huygens, Pauli, Lovelace / Bernoulli.
Seats CLOSED: Peirce, Ohm.

The synthesis call is STILL OPEN. v1.2 defines Layer 2 as a modifier, removes repair inheritance from `CompositionHint`, defines FSM states, and gives a cache key with bond/surface/conversation/turn. The remaining gap is test specificity: the RED anchors do not explicitly prove simultaneous Telegram/web or multi-surface repair turns cannot inherit each other's prior specs. Arendt also flags timestamp/TTL keying as under-specified relative to the pass-2 closure checklist.

Current v1.2 evidence cited:

- `spec-brief.md:356-373`: repair FSM and prior-spec storage.
- `spec-brief.md:426-436`: repair inheritance not a `CompositionHint`.
- `spec-brief.md:677-678`: repair RED anchors.

Required v1.3 fold:

- Add a RED anchor such as `test_repair_fsm_does_not_cross_inherit_between_concurrent_surfaces`.
- Explicitly prove two simultaneous conversations/surfaces under the same bond cannot inherit each other's prior spec.
- Add a RED anchor for post-repair construction validation/refusal of the modified `CompositionSpec`.
- Clarify whether timestamp/TTL are part of storage identity or define an equivalent collision-proof freshness model.

### Batch 11 — Fan-Out Cancellation Semantics Split

Seats STILL OPEN: Arendt, Ohm, Lovelace / Bernoulli.
Seats CLOSED: Peirce, Huygens, Pauli.

The synthesis call is STILL OPEN because half the panel found the same material gap: v1.2 defines result states, deadlines, max parallel branches, merge order, and prompt budget, but does not explicitly say what happens to in-flight branches after per-branch timeout or global deadline. Without that, late branch results could mutate or confuse prompt fallback behavior unless implementation guesses correctly.

Current v1.2 evidence cited:

- `spec-brief.md:303-314`: fan-out result states, deadlines, merge, prompt budget.
- `spec-brief.md:606-608`: D12 concurrent fan-out.
- `spec-brief.md:698`: slow/error branch test.

Required v1.3 fold:

- Define cancellation behavior at per-branch timeout and global deadline.
- State whether slow branches are cancelled, abandoned, drained with bounded grace, quarantined, or ignored by generation id.
- Require no late branch can mutate the merged recall after prompt fallback.
- Add cancellation telemetry/audit expectations and a RED anchor proving the behavior.

---

## Split / Borderline Findings

### Batch 4 — Tie Handling and No-Match Source Selection

Seats STILL OPEN: Pauli, Ohm, Lovelace / Bernoulli.
Seats CLOSED: Peirce, Arendt, Huygens.

v1.2 declares thresholds and says tie handling is deterministic. The split is whether that is enough. Three seats want the exact tie rule and no-match source-selection behavior made executable before canonicalization.

Synthesis call:

Fold into v1.3. It is small and prevents implementation-local constants from returning through a side door. v1.3 should define:

- exact tie ordering or multi-match behavior when scores fall within `multi_match_delta`;
- how ties affect emitted `CompositionHint`, `ProvenanceFraming`, and source set;
- no-match `substrate_sources` and `external_sources` for `PRESENT`, `UNKNOWN`, `ABSENT`, and reserved-source cases;
- deterministic ordering for fallback-selected sources.

### Batch 12 — External Error Mapping Specificity

Seat STILL OPEN: Ohm.
Seats CLOSED: Peirce, Arendt, Huygens, Pauli, Lovelace / Bernoulli.

Ohm found that v1.2 gives budgets and generic failure mapping but only explicitly names Reddit bot-block. The majority marked Batch 12 closed, but the requested fold is cheap and aligns with Ohm's cost/surface lane.

Synthesis call:

Fold into v1.3 as a low-cost material clarification:

- enumerate failure classes for `WEB_SEARCH`, `LIVE_REDDIT`, `FETCH_URL`, `ARXIV_OR_PAPERCLIP`, and `FRONTIER_CONSULT`;
- map each to `FRESH_ATTEMPT_FAILED`, `FETCH_BUDGET_EXHAUSTED`, `SOURCE_TIMEOUT`, or `RESERVED_SOURCE_UNAVAILABLE`;
- define stop conditions for timeout, max attempts, global deadline, empty result, and reserved source.

---

## Material Outcome

v1.2 should not proceed to canonicalization yet.

The v1.3 fold is narrow:

1. Add realistic-store p95 adapter-budget requirements and telemetry anchors.
2. Define the audit metadata payload for provenance rendering and self-claim/fabrication audit.
3. Add cross-surface repair isolation and post-repair validation anchors; clarify timestamp/TTL freshness model.
4. Define fan-out cancellation / late-result behavior.
5. Define tie/no-match source-selection rules.
6. Add external-source error-class mapping and stop conditions.

No council pass-2 is indicated. No covenant-axis escalation surfaced.

---

## Recommended Next Step

Fold `spec-brief.md` from v1.2 to v1.3 using the narrow list above, then dispatch Codex pass-3 as a closure-only check against the v1.3 deltas.

If pass-3 returns CLOSED / NIT-only, canonicalize as Decision 42 / ADR 0047.
