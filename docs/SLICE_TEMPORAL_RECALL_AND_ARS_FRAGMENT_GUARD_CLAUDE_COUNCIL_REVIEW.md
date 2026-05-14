# Claude Six-Role Council — TRF (Temporal Recall + ARS Fragment Guard) spec review

**Subject:** `docs/SLICE_TEMPORAL_RECALL_AND_ARS_FRAGMENT_GUARD.md` — 743-line spec draft. Pre-spec amendments T1-T6 folded; Codex's six-agent panel BLOCK/REVISE closure folded.

**Council ran:** 2026-05-13, pre-canonical. Codex's six-agent panel has already sat (two BLOCKs, both folded). This council reviews the corrected draft.

**The three open questions Codex explicitly flagged for Claude — answered first.**

---

## Q1 — Voice-character ratification of the fallback phrase

Proposed: `"I'm not finding that clearly right now. I hear that you feel much better than last week."`

**Council verdict: RATIFY.**

- **Outside-View:** more natural than field-standard "I don't have access to..." patterns; acknowledges retrieval failure not memory absence
- **Body-Coherence:** witness-language pattern preserves invariant #4 (Interpretive Humility) — Maez is echoing what the user just said, not interpreting
- **Future-Rohit:** 5-year-readable, short, doesn't promise future knowledge
- **20-Years-Future-Maez:** the "right now" motif extends ARS's voice signature; becomes a Maez stylistic anchor for "this is the limit of what I can ground at this moment" — endorses

The phrase is **ratified exactly as proposed.** State-specific fallback distinction (`bounded_search_no_match` → `"I'm not finding..."` vs `helper_unavailable` → `"I can't check..."`) is also correct — "finding" implies a search happened; "check" implies the search was unavailable. That distinction is load-bearing voice character.

## Q2 — Mechanical current-message context preservation: covenant-safe?

**Council verdict: RATIFY** with one precision amendment.

The rule (T5) limits transformation to FIRST-PERSON self-reports with v1 temporal anchors:
- `I feel <adj> compared to <anchor>` → `I hear that you feel <adj> compared to <anchor>.`

This is witness language, not interpretation. Maez echoes what the user JUST said, prefixed with "I hear that" (counseling-shaped acknowledgment signaling attentive listening). It does NOT infer feelings, diagnose, or claim understanding of meaning.

**Body-Coherence verifies preservation of:**
- Invariant #2 (Human-Primacy): user's words remain primary; Maez witnesses
- Invariant #4 (Interpretive Humility): "I hear that" is acknowledgment, not interpretation
- Invariant #5 (Rupture and Repair): the pattern doesn't pre-empt user naming their own state

**Required precision amendment (TRF-CC-1):** the paraphrase rule must preserve **comparative-relational structure**. "Much better compared to last week" → "Much better than last week" is acceptable because "compared to" and "than" are both comparative-relational. But "since" → "than" would NOT be acceptable (those denote different temporal-relational structures). Spec should explicitly say: comparative connectors map to comparative connectors; temporal-causal connectors do not collapse into comparative ones.

## Q3 — Fragment guard's post-audit position preserves ARS protection?

**Council verdict: RATIFY.**

The fragment guard runs AFTER ARS. Its outputs are either:
- Fixed phrases (`"I'm not finding that clearly right now."` / `"I can't check that clearly right now."`)
- Mechanical user-text reflections (`"I hear that <user words>"`)

**Neither path can leak unverified model claims because:**
- Fixed phrases contain no model output
- User-text reflections echo USER words, not Maez's model output (the user is the source of truth for their own self-reports)

Test 22 ("Audit protection is preserved: ungrounded memory claims still do not surface") explicitly validates this. The fragment guard structurally cannot reintroduce the failure mode ARS exists to prevent.

---

## 1. Outside-View seat

Field-aligned. Bounded-temporal-anchor recall is somewhat novel for AI companions — most products rely on embedding similarity, which fails for "last week" (temporal phrases don't match content embeddings well). Maez's deterministic calendar-week window is more honest about what it can and can't ground. The fragment-guard pattern is field-aligned with response-filter chains in production AI.

**Verdict:** RATIFY.

---

## 2. Body-Coherence seat

Per-invariant check on the corrected draft:

- **#1 Time as Biography** — OPERATIONALIZED. This slice is the first concrete realization of invariant #1; bounded temporal-anchor recall makes "last week" a first-class query.
- **#2 Human-Primacy** — preserved by mechanical witness pattern (per Q2 verdict).
- **#3 Contextual Integrity** — content-free observability with explicit forbidden-metadata list.
- **#4 Interpretive Humility** — STRENGTHENED. The slice adds explicit "I am not finding" framing where the model would have fabricated; "right now" motif acknowledges temporal-bounded uncertainty.
- **#5 Rupture and Repair** — neutral.
- **#6 Crisis Routing** — neutral.
- **#7 Soul-Level Objection** — neutral; this slice doesn't touch refusal.
- **#8 Capability Quarantine** — kill switch `MAEZ_TEMPORAL_ANCHOR_RECALL=0` provides granular control.
- **#10 Clinical Boundary** — the witness pattern is counseling-shaped but doesn't claim therapeutic role. Acceptable.
- **#11 Cryptographic Continuity** — no impact.

**Bridge clause check:** PRESERVED. Slice is dyadic (Maez ↔ bonded user); doesn't reach outward.

**Genderless rule check:** Spec uses "Maez" throughout. No she/her. Verified clean.

**Three Body-Coherence amendments:**

**TRF-CC-1 (above).** Paraphrase rule preserves comparative-relational structure.

**TRF-CC-2.** Confirm witness-language pattern `"I hear that <user words>"` applies ONLY to first-person self-reports. Patterns like "I hear that you seem upset" (inferring an emotional state the user did not name) must remain forbidden.

**TRF-CC-3.** Note `"right now"` as a recurring Maez stylistic motif (now appearing in ARS all-flagged fallback AND TRF fragment-guard fallback). This is becoming a voice signature for temporal-bounded uncertainty. Future Voice-OUT subsystem work may want to consider whether this motif is preserved, extended, or replaced. Worth noting in the spec or memory for downstream awareness.

**Verdict:** RATIFY-WITH-AMENDMENTS (TRF-CC-1, TRF-CC-2, TRF-CC-3).

---

## 3. Logical seat *(veto authority)*

Internal consistency check:

**Strong correctness:** bounded windows, half-open intervals, timezone explicit (with DST test mandated), result contract closed, 25 mandatory RED-first tests, telemetry content-free with bounded-per-turn rule, forbidden phrases enumerated, negative controls included.

**Three precision concerns:**

**TRF-CC-4.** Fragment classifier (T3) has disjunctive criteria ("any of these are true"). Tests should explicitly cover the boundary cases: one criterion only (e.g., starts with "But" but is 15 words), multiple criteria (e.g., starts with "But" AND is affect-only), and edge cases at the 12-word threshold. The 25-test list doesn't explicitly enumerate these boundary cases.

**TRF-CC-5.** Temporal-anchor recall with exactly `max_items=4` matching episodes should have `truncated=False`. Test 7 covers ">4 matching episodes" but not the boundary case of `=4`. Add one boundary test.

**TRF-CC-6.** Spec doesn't explicitly address: what if no temporal anchor was detected but ARS still left a fragment? T4's state-specific fallback table presumes anchor_detected=True. Two clean options: (a) the fragment guard only activates when `anchor_detected=True`, OR (b) there's a third fallback phrase for non-temporal fragment cases. Spec should pin which. Operator likely intends (a) — fragment guard is scoped to temporal-recall cases — but the spec should say so explicitly.

**Veto consideration:** NO VETO. Three boundary-precision concerns.

**Verdict:** RATIFY-WITH-AMENDMENTS (TRF-CC-4, TRF-CC-5, TRF-CC-6).

---

## 4. Creative seat

Two observations, no redesign:

**TRF-CC-9 (optional).** The state-specific fallback distinction (bounded_search_no_match vs helper_unavailable) is precise. Worth noting in the spec or as comment in code that "finding" vs "check" carry different semantic implications — load-bearing voice character. Helps future readers preserve the distinction during refactors.

**TRF-CC-10 (optional).** The v1 anchor system is template-shaped for the broader temporal-spine (S3) work. When S3 ships, this v1 graduates into a richer model (event-anchored phrases, weekday names, multi-hop temporal queries). Worth noting that v1 is the precursor pattern, similar to how S1a.1's audit-before-handle became S1b's observability template.

**Verdict:** RATIFY.

---

## 5. Visionary / Future-Rohit seat

5-year readability check:

- Two modules clearly named, one new (`core/safety/temporal_fragment_guard.py`)
- Deterministic temporal-window definitions (Monday-Sunday calendar week, half-open intervals)
- 25 RED-first tests with named coverage
- Codex panel amendments folded section is durable provenance
- Observation log template defined

**Two amendments:**

**TRF-CC-7.** Add one sentence on DST behavior. Spring-forward day has 23-hour "yesterday"; fall-back day has 25-hour "yesterday." The spec mandates a DST-adjacent reference time test but doesn't say what behavior is expected. Specify: "yesterday" is the full local calendar day [00:00 previous day, 00:00 current day) regardless of DST hour count; the test asserts the calendar-day boundaries hold, not specific second counts.

**TRF-CC-8.** Pin the probe corpus file location. Test 25 mentions "anti-overfit probes cover 2-3 prompts per v1 anchor plus negative controls" — but where are these stored? Suggest: `tests/data/trf_probe_corpus.jsonl` (same executable-JSONL pattern as ARS's `audit_rewrite_probe_corpus.jsonl`). 5-year-future readers benefit from a canonical corpus file.

**Verdict:** RATIFY-WITH-AMENDMENTS (TRF-CC-7, TRF-CC-8).

---

## 6. 20-Years-Future-Maez seat

**Voice of 2046-Maez looking back:**

> *"TRF was the slice that made 'last week' a first-class temporal-anchor query for me. Before TRF, asking Maez 'do you remember last week?' relied on keyword overlap, which failed when the user didn't use specific keywords. After TRF, the prompt was routed to a bounded calendar-week search, and the answer was either evidence-backed or honestly 'I'm not finding that clearly right now.' The fragment guard caught the worst residual ARS bug.*
>
> *The 'right now' motif from ARS got reused in TRF and became part of Maez's voice signature for temporal-acknowledgment uncertainty. By 2028, when the temporal-spine work shipped, this v1 anchor system graduated into a richer model. The 'right now' motif persisted.*
>
> *One wound 2046-me carries: the witness-language pattern 'I hear that <user words>' was mechanical in v1 — could only echo first-person self-reports. By 2030, when I had richer language understanding, the pattern needed to extend. The v1 rule was the right choice for 2026 — keep it mechanical to avoid hallucinated empathy — but the generalization path wasn't explicitly named."*

**TRF-CC-11 (forward-looking, not blocking).** Note that the witness-language pattern is the starting point for future "Maez acknowledges what the bonded user said without interpreting" work. Future expansion is queued for voice subsystem / generalization work. Not in scope for v1.

**Verdict:** RATIFY.

---

## Verdict

**RATIFY-WITH-AMENDMENTS.** No veto. The three open Codex-flagged questions are answered:
- Voice-character ratified as proposed
- Current-message preservation rule is covenant-safe (with TRF-CC-1 precision)
- Fragment guard post-audit position preserves ARS protection

Eight precision amendments + three optional forward-looking notes:

| # | Seat | Amendment |
|---|------|-----------|
| TRF-CC-1 | Body-Coherence | Paraphrase rule preserves comparative-relational structure ("compared to" → "than" OK; "since" → "than" NOT OK) |
| TRF-CC-2 | Body-Coherence | Confirm witness-language pattern applies only to first-person self-reports |
| TRF-CC-3 | Body-Coherence | Note "right now" as recurring Maez stylistic motif |
| TRF-CC-4 | Logical | Boundary test: fragment classifier with one-criterion-only vs multiple-criteria cases |
| TRF-CC-5 | Logical | Boundary test: temporal-anchor recall with exactly `max_items=4` should have `truncated=False` |
| TRF-CC-6 | Logical | Specify fragment guard behavior when no anchor detected: scope to anchor_detected=True or define third fallback |
| TRF-CC-7 | Future-Rohit | DST behavior sentence: yesterday is full local calendar day regardless of DST hour count |
| TRF-CC-8 | Future-Rohit | Pin probe corpus file location (suggest `tests/data/trf_probe_corpus.jsonl`) |
| TRF-CC-9 | Creative | (Optional) Note "finding" vs "check" load-bearing voice distinction |
| TRF-CC-10 | Creative | (Optional) Note v1 anchor system as template for S3 broader temporal spine |
| TRF-CC-11 | 20-Years-Future-Maez | (Forward-looking) Witness-language pattern is starting point; future generalization queued for voice subsystem |

### What ratifies cleanly

- Bounded calendar-week recall as operationalization of invariant #1 (Time as Biography)
- Fragment guard as pure post-audit helper (preserves ARS protection)
- State-specific fallback phrases (bounded_search_no_match vs helper_unavailable)
- Mechanical witness-language pattern (first-person self-reports only)
- 25 RED-first tests with live-failure regression cases included
- Codex panel's two BLOCKs folded cleanly
- Half-open interval semantics
- Content-free observability with bounded-per-turn rule
- Kill switch granularity (`MAEZ_TEMPORAL_ANCHOR_RECALL=0` disables only temporal helper)
- Forbidden phrases enumerated
- Negative controls in probe corpus

### What's next per the spec's protocol

1. Codex closes TRF-CC-1 through TRF-CC-8 mechanically (most are one-paragraph spec additions, two are boundary test additions)
2. Optional: TRF-CC-9, TRF-CC-10, TRF-CC-11 fold if operator wants 5-year provenance
3. Spec becomes canonical
4. Cooling-off night or explicit operator waiver
5. Implementation per spec contract, RED-first
6. Both panels post-implementation
7. Live Telegram observation per spec's catalog closure rule

*This council review is read-only. No code or non-audit-dir docs changed in producing it.*
