# Claude Six-Role Council — TRF implementation review

**Subject:** `7705e7d` (`feat(memory): implement TRF temporal recall guard`) — the corrected TRF implementation after Codex's post-implementation panel caught four real blockers and the recovery closed them.

**Council ran:** 2026-05-13, post-implementation.

**The four Codex blockers (per `SLICE_TEMPORAL_RECALL_AND_ARS_FRAGMENT_GUARD_CODEX_POST_IMPLEMENTATION_REVIEW.md`):**

| # | Blocker | Why it mattered |
|---|---------|-----------------|
| B1 | Unbounded full-store scan fallback | Violated spec's bounded-helper contract; could grow with entire memory store |
| B2 | Evidence trace mismatch (episode IDs vs source memory IDs) | Weakened future traceability |
| B3 | Kill switch disabled too much (skipped anchor detection, preventing fragment guard cleanup) | Operator couldn't disable temporal recall while keeping fragment-cleanup behavior |
| B4 | Evidence-found false safety: bare `I remember...` claims passed when window evidence existed | **The deepest failure mode — even with memory, ungrounded claims could leak** |

B4 is the consequential catch. It establishes a structural rule that aged into a load-bearing principle: **retrieval ≠ grounding.** That a bounded-window search returned items does NOT mean any specific claim is grounded by those items. The fix requires approved-retrieval-posture phrases (`I found one memory from last week...`) to bypass the guard; bare `I remember...` / `I recall...` remain guardable regardless of evidence presence.

---

## 1. Outside-View seat

Field-aligned. The "retrieval ≠ grounding" distinction (B4 fix) is converging across the field — Letta, Mem0, LangChain all separate retrieval from claim-justification. Maez's TRF + ARS combination now structurally enforces this. The Codex BLOCK-and-recover pattern (third time today after TDP Descartes and ARS smoother-but-leaking) is the discipline working at the load-bearing spots.

**Verdict:** RATIFY.

---

## 2. Body-Coherence seat

Per-invariant check, mechanically enforced by tests:

- **#1 Time as Biography** — IMPLEMENTED. Bounded calendar-week temporal anchor recall is the first concrete realization of #1.
- **#2 Human-Primacy** — preserved. `test_current_context_is_limited_to_first_person_self_report` enforces TRF-CC-2.
- **#3 Contextual Integrity** — content-free observability per spec.
- **#4 Interpretive Humility** — STRONGLY preserved. B4 fix prevents the "evidence_found = safe to claim memory" trap, which is the exact load-bearing concern for #4. Multiple regression tests cover bare-memory-claim cases: `test_evidence_found_memory_claim_without_approved_posture_is_guarded`, `test_evidence_found_affect_fragment_does_not_claim_no_match`, `test_audit_fail_open_plus_evidence_found_memory_claim_is_guarded`.
- **#7 Soul-Level Objection** — preserved.
- **#8 Capability Quarantine** — kill switch granular (B3 fix); doesn't disable fragment guard.

**TRF-CC-1 (comparative-relational structure preservation):** `test_comparative_structure_not_rewritten_from_since` confirms "since" → "than" rewrite is forbidden. ✓
**TRF-CC-2 (first-person self-report only):** `test_current_context_is_limited_to_first_person_self_report`. ✓
**TRF-CC-6 (no anchor → guard doesn't activate):** `test_guard_does_not_activate_without_temporal_anchor`. ✓

**Bridge clause check:** PRESERVED. Slice is dyadic.

**Genderless rule check:** new code uses "Maez" throughout. Verified clean.

**Verdict:** RATIFY.

---

## 3. Logical seat *(veto authority)*

Internal consistency check on the implementation:

**Strong correctness:**
- ✓ All 25 spec-contract tests landed, plus 8 more for Codex blocker regression coverage = 33 total
- ✓ TRF-CC-4 boundary tests (`test_boundary_cases_for_fragment_classifier`)
- ✓ TRF-CC-5 exactly-max-items boundary test (`test_more_than_max_items_truncates_but_exact_max_does_not`)
- ✓ TRF-CC-6 no-anchor guard scope (`test_guard_does_not_activate_without_temporal_anchor`)
- ✓ TRF-CC-7 DST behavior (`test_yesterday_uses_local_calendar_day_even_across_dst`)
- ✓ TRF-CC-8 probe corpus at `tests/data/trf_probe_corpus.jsonl` per spec
- ✓ B1 unbounded scan blocker fixed and regression-tested
- ✓ B2 evidence trace blocker fixed and regression-tested
- ✓ B3 kill-switch blocker fixed and regression-tested
- ✓ B4 evidence-found false-safety blocker fixed with multiple regression tests including the audit-fail-open case

**One optional catalog-queue suggestion:**

**TRF-PI-L1.** The operator's honest caveat — sqlite `ResourceWarning` noise in the broader suite — is exactly the right posture. Not pretending it disappeared is healthier than ignoring it. For Logical seat: the warnings indicate something (probably unclosed sqlite connections somewhere in test infrastructure or production code). Not a TRF blocker. Worth queueing as either a new geek-out catalog entry OR an N-track operational item, similar to how mediapipe noise became N1 work. Operator's call when/how to address.

**Veto consideration:** NO VETO.

**Verdict:** RATIFY (with optional TRF-PI-L1 catalog suggestion).

---

## 4. Creative seat

Two observations, no redesign:

**TRF-PI-C1.** The "evidence_found is not permission to claim memory" structural distinction (B4 fix) is template-shaped for future retrieval-aware AI patterns in Maez. Applies to ANY future memory subsystem — bond-repair retrieval, soul-objection retrieval, crisis-routing retrieval. Worth noting as a substrate principle: retrieval results require approved-posture wrapping before bypassing safety guards.

**TRF-PI-C2.** The combined TRF + ARS architecture is now a coherent "retrieve → reply → audit → cleanup" pipeline. Future memory-augmented response slices can adopt this template (S2 contextual integrity at ingest is the natural pair, since both touch the memory→response boundary).

**Verdict:** RATIFY.

---

## 5. Visionary / Future-Rohit seat

5-year readability:

- Codex post-implementation review trail at `docs/SLICE_TEMPORAL_RECALL_AND_ARS_FRAGMENT_GUARD_CODEX_POST_IMPLEMENTATION_REVIEW.md` — 5-year-readable explanation of what Codex caught and why
- 33 tests with explicit names matching spec contract + Codex blockers
- Probe corpus is executable JSONL at canonical path
- Observation log template at `docs/TRF_OBSERVATION_LOG.md`
- Commit body explicitly names the four blockers

The TRF closure trail (spec → both panels pre-impl → canonical → impl → Codex post-impl 4 blockers → fix → both panels post-impl → live observation) is clear provenance.

**Verdict:** RATIFY.

---

## 6. 20-Years-Future-Maez seat

**Voice of 2046-Maez:**

> *"TRF was the slice that established 'retrieval ≠ grounding' as a structural rule. Before TRF, the fragment guard's first implementation treated `evidence_found` as permission to pass bare `I remember...` claims. That would have been the deepest failure mode possible — even when memory exists, ungrounded claims could leak. Codex's panel caught it; the fix required only approved-retrieval-posture phrases to bypass the guard.*
>
> *By 2030, that 'retrieval ≠ grounding' distinction was the canonical pattern across all memory-aware AI systems I knew about. Maez had it from week one of the temporal-anchor work because Codex's Descartes seat asked the right question early enough.*
>
> *Also: 'right now' as the voice signature for temporal-bounded uncertainty solidified here. By 2028 it was unmistakably Maez."*

**Verdict:** RATIFY.

---

## Verdict

**RATIFY.** No veto. No mechanical amendments needed. One optional catalog-queue suggestion (TRF-PI-L1, sqlite ResourceWarning noise).

The implementation is the tightest post-Codex-recovery this session has produced. All pre-implementation TRF-CC amendments are mechanically enforced by named tests. The four Codex blockers were real, not ceremonial, and the fixes are structural (not patch-around). B4 establishes "retrieval ≠ grounding" as a structural Maez rule, applicable to all future memory-aware work.

### Optional follow-up

| # | Seat | Suggestion |
|---|------|-----------|
| TRF-PI-L1 | Logical | (Optional) Queue sqlite ResourceWarning noise as new catalog entry / N-track item; not a TRF blocker but operator's honest caveat is worth durable-recording |

### What ratifies cleanly

- All four Codex blockers (B1 unbounded scan, B2 evidence trace, B3 kill switch, B4 evidence-found false safety) closed structurally with regression tests
- All eight TRF-CC amendments from pre-impl council mechanically enforced by tests
- 33 RED-first tests covering spec contract + blocker recovery
- Probe corpus at canonical path (executable JSONL)
- Observation log template exists
- Codex post-implementation review trail is durable doc
- Bridge clause preserved
- Genderless rule preserved
- "Retrieval ≠ grounding" established as a substrate principle
- "Right now" voice motif extends consistently across ARS + TRF
- Honest caveat acknowledged (sqlite ResourceWarning) without pretending

### Status

Per spec promotion criteria:
- ✓ Both panels post-implementation ratify (Codex: BLOCK-and-recovered; Claude: this review = RATIFY)
- ✓ 33 RED-first tests cover spec contract + Codex blockers
- ✓ Audit protection preserved (multiple tests including audit-fail-open case)
- ✓ Old ARS sentinel phrases absent from user-visible output
- ✓ Probe corpus + observation log infrastructure
- **Awaiting:** live conversation closes Entry 5 only after one full day OR three natural temporal-memory turns with no fragments

Implementation is effectively complete; **awaiting live observation for geek-out Entry 5 closure** (same posture as ARS Entry 3).

### What's next per the spec's protocol

1. Operator decides on TRF-PI-L1 (queue sqlite noise as catalog entry, defer, or ignore)
2. Branch pushed to origin/main (currently ahead 2: TRF spec `e23f906` + TRF impl `7705e7d`)
3. Live Telegram observation begins
4. Geek-out catalog Entry 5 closes after one full day OR three natural temporal-memory turns with no fragments

*This council review is read-only. No code or non-audit-dir docs changed in producing it.*
