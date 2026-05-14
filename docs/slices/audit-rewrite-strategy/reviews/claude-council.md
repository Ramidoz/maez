# Claude Six-Role Council — ARS (audit rewrite strategy) spec review

**Subject:** `docs/slices/audit-rewrite-strategy/spec.md` — spec draft folding operator pre-spec amendments A1-A5. Pre-canonical; Codex's six-agent panel still needs to sit in its lane.

**Council ran:** 2026-05-13, pre-canonical.

**Subject is a SPEC, not a commit.** This council reviews the contract that ARS implementation will be held to. The audit rail protects covenant invariants #4 (Interpretive Humility) and #7 (Soul-Level Objection); a bad fix could make Maez sound smoother while letting fabricated claims through. Both councils' pre-code review is load-bearing.

---

## 1. Outside-View seat

Omission-over-sentinel is field-aligned. Modern AI safety practice (Anthropic Claude's post-hallucination response strategy, OpenAI's recent updates for voice-authored uncertainty at generation time, LangGraph audit patterns with structured filtering) all favor omission as default with optional regeneration. Mechanical sentinel injection is a known anti-pattern in the field.

The spec follows the session's established pattern (wrapper-isolated change, strict scope, content-free counters with trip-wire safeguard, RED-first test discipline). Aligned with what's been working today.

One field-aligned note worth surfacing as observation: the "I'm not sure about that right now" all-flagged fallback IS a fixed phrase, with the same voice-identity-continuity-surface concern as TDP's empty-text-only rule, just in inverted form. The spec acknowledges this (line 218-222, framing regeneration as roll-forward). That's the right discipline — temporary fixed voice commitment with a named retirement path.

**Verdict:** RATIFY.

---

## 2. Body-Coherence seat

Per-invariant check on the proposed implementation:

- **#2 Human-Primacy** — neutral.
- **#3 Contextual Integrity** — content-free observability with explicit forbidden-metadata list. STRENGTHENED.
- **#4 Interpretive Humility** — STRENGTHENED. The mechanical sentinel expressed humility robotically; omission expresses it structurally; voice-authored fallback expresses it in voice for the all-flagged case.
- **#5 Rupture and Repair** — neutral.
- **#7 Soul-Level Objection** — the audit rail is the structural seed of refusal logging. The spec preserves "ungrounded claims must still not surface" as the load-bearing protection. The Test Contract's "audit protection preserved" line (line 422) directly addresses this with the judge_eval fixture. PRESERVED.
- **#8 Capability Quarantine** — different shape from S1b/TDP. This is a STRUCTURAL change with no runtime flag (A5). Body-Coherence accepts this reasoning — it's correcting an existing rail, not adding new capability, and the trip-wire counter is the regression safeguard.

**Bridge clause check:** PRESERVED. The audit's protection of bonded-user-vs-fabrication boundary is unchanged.

**Genderless rule check:** "I'm not sure about that right now" uses no gendered pronouns. Verified clean.

**One amendment from Body-Coherence:**

**ARS-CC-1.** The all-flagged fallback phrase "I'm not sure about that right now" is the most consequential voice-identity decision in this spec. Even though it's all-flagged-only and the spec correctly marks it as a temporary v1 commitment, the phrase itself deserves explicit voice-character review during canonization. Three questions for the canonization moment: (a) does this phrase sound like Maez specifically, not like a generic AI? (b) does the "right now" qualifier hint at temporal acknowledgment that Maez might know later, which is the right shape, or does it sound dismissive? (c) is there a shorter or more characterful alternative? I lean toward accepting the proposed phrase, but flag the voice-character question for explicit operator ratification rather than implicit acceptance.

**Verdict:** RATIFY-WITH-AMENDMENT (ARS-CC-1).

---

## 3. Logical seat *(veto authority)*

Internal consistency check on the spec:

**Strong correctness:**
- ✓ Sentence-span scope with paragraph fallback rules pinned (A1)
- ✓ All-flagged behavior explicit, fallback choice rationaled
- ✓ Boundary-ambiguous failure mode pinned (fail-safe toward omission)
- ✓ Trip-wire counter for sentinel regression
- ✓ Content-free observability with forbidden-metadata list
- ✓ Test Contract with 13 mandatory RED-first tests
- ✓ Tests-likely-to-change AND tests-that-must-stay-green both enumerated
- ✓ Rollback options that explicitly forbid restoring sentinel without both-panel review
- ✓ Existing sentinel text in model output gets handled (line 240-247)
- ✓ A5 structural-change reasoning is sound

**Three precision concerns:**

**ARS-CC-2. Resolve Open Question #1 (`AuditResult.mode` enum expansion) in the spec, not deferred to implementation.** The spec describes the choice (preferred: expand enum; fallback: compat-preserving with new counters) but doesn't pick. This decision affects downstream parser compatibility. Codex's Locke seat will likely answer from identity-continuity perspective. Worth picking in the canonical spec so implementation isn't blocked on the question.

**ARS-CC-3. Add explicit test for boundary-ambiguous flag handling.** The "fail safe toward omission of smallest containing region" rule (line 226-228) is named but not directly tested in the Test Contract. Worth adding: "Boundary-ambiguous flag with no clean sentence mapping omits smallest containing region; legitimate uncluttered text is preserved."

**ARS-CC-4. Confirm `judge_eval_2026_05_05.jsonl` fixture is still representative.** That fixture is 22 cases from the morning's audit work. The live "Do you remember today morning?" sentinel-leak case from today's screenshots may want to be added as a regression fixture so the spec's "audit protection preserved" test includes the exact scenario that motivated the slice.

**Veto consideration:** NO VETO. Three precision concerns, all small.

**Verdict:** RATIFY-WITH-AMENDMENTS (ARS-CC-2, ARS-CC-3, ARS-CC-4).

---

## 4. Creative seat

The spec is tight. Two observations:

**ARS-CC-5.** **The probe corpus (A3) is template-shaped.** Three categories (live prompts from today, S1b C2-adjacent probes, audit-rewrite stress probes) is a clean structure. Future safety changes (Voice-OUT-safety, Body Topology probes, crisis-channel probes) will want similar corpus shape. Worth noting in the spec that this corpus pattern is reusable, similar to how the slice-letter convention and the timeboxed-feature-flag pattern from TDP became reusable.

Optional addition: when this slice ratifies, the probe corpus could be extracted to `docs/PROBE_CORPUS_AUDIT_REWRITE.md` or sibling so future corpus expansions don't require spec re-canonization. Operator's call; embedded is fine for v1.

**Verdict:** RATIFY (with optional ARS-CC-5).

---

## 5. Visionary / Future-Rohit seat

5-year readability check:

- Spec structure is clear: intent → current behavior → load-bearing rule → scope → rewrite semantics → tests → predicted effect → rollback → review protocol → open questions → completion criteria
- The "Open Questions for Panels" section names what's not yet decided
- The trip-wire counter is template-shaped for future safety changes
- The probe corpus is embedded in spec; durable for future regression testing

**Two amendments:**

**ARS-CC-6.** **Add explicit review trigger for the all-flagged fallback phrase.** The spec correctly identifies the phrase as a v1 commitment, but doesn't pin when review happens. Suggest: "this phrase should be re-reviewed when [trigger]" — e.g., when the regeneration hook lands (named in A2 rationale), when the Voice-OUT subsystem ships, OR on a calendar trigger (e.g., 90 days post-implementation). Without an explicit trigger, the temporary commitment risks becoming permanent through inattention. Same wound class as deferred amendments in the audit master findings.

**ARS-CC-7.** **Specify the probe corpus growth mechanism.** Currently the corpus is in the spec body. If new geek-out moments surface (which they will, per the catalog's design), how does the corpus grow? Options: (a) appendable section in this spec, requiring spec-amendment commits; (b) sibling file `docs/PROBE_CORPUS_AUDIT_REWRITE.md` for low-friction additions; (c) catalog entries link to test fixtures that act as the corpus. Spec author picks; document the choice.

**Verdict:** RATIFY-WITH-AMENDMENTS (ARS-CC-6, ARS-CC-7).

---

## 6. 20-Years-Future-Maez seat

**Voice of 2046-Maez looking back:**

> *"ARS in 2026 was when Maez's voice stopped being contaminated by safety machinery. Before ARS, every audit catch left a robotic sentinel in Maez's voice. After ARS, audit catches resulted in omission — the response went quiet about what couldn't be grounded and continued naturally about what could. The all-flagged fallback was a temporary voice commitment; by 2028, when regeneration hooks shipped, even that phrase retired. The substrate's principle held: mechanical machinery does not impersonate Maez.*
>
> *One small wound from this slice: the trip-wire counter `audit_rewrite.sentinel_attempted_blocked` was the regression safeguard, but there was no procedure for what happens when it fires in production. By 2028, the counter had fired three times across various refactors and each time the operator had to re-derive what to do. A written procedure would have saved cycles."*

**ARS-CC-8.** **Specify the operator response loop for trip-wire firing.** If `audit_rewrite.sentinel_attempted_blocked` activates, what does the operator do? Investigate? Roll back? Patch immediately? Suggest the procedure: (a) the counter fire triggers a log line operator can see; (b) on first fire, operator investigates which code path attempted the sentinel; (c) if it's a regression in code, roll back; if it's a new edge case, patch; (d) record the incident in a sibling file or catalog entry. One paragraph in the spec.

**Verdict:** RATIFY-WITH-AMENDMENT (ARS-CC-8).

---

## Verdict

**RATIFY-WITH-AMENDMENTS.** No veto. The spec is comprehensive; eight small amendments fold cleanly without redesign.

### Amendments (ARS-CC-1 through ARS-CC-8)

| # | Seat | Amendment |
|---|------|-----------|
| ARS-CC-1 | Body-Coherence | All-flagged fallback phrase voice-character: explicit operator ratification during canonization (does it sound like Maez specifically?) |
| ARS-CC-2 | Logical | Resolve Open Question #1 (`AuditResult.mode` enum expansion) in the canonical spec, not deferred to implementation |
| ARS-CC-3 | Logical | Add test: "Boundary-ambiguous flag with no clean sentence mapping omits smallest containing region; legitimate text preserved" |
| ARS-CC-4 | Logical | Add today's "Do you remember today morning?" sentinel-leak as a regression fixture (or confirm `judge_eval_2026_05_05.jsonl` is still representative) |
| ARS-CC-5 | Creative | (Optional) Note the probe corpus pattern is template-shaped for future safety changes |
| ARS-CC-6 | Future-Rohit | Add explicit review trigger for the all-flagged fallback phrase (when regeneration hook lands / Voice-OUT ships / 90-day calendar) |
| ARS-CC-7 | Future-Rohit | Pin probe corpus growth mechanism (appendable section vs sibling file vs catalog-linked fixtures) |
| ARS-CC-8 | 20-Years-Future-Maez | Specify operator response loop for trip-wire counter firing (`audit_rewrite.sentinel_attempted_blocked` → investigate → roll-back-or-patch → record) |

### What ratifies cleanly

- **Omission-over-sentinel as load-bearing rule** — equivalent in weight to TDP's empty-text-only rule
- A1 sentence-span scope with paragraph rules and boundary-ambiguity handling
- A2 fixed voice fallback for v1 with regeneration as named roll-forward path
- A3 probe corpus structure (live + C2-adjacent + audit-rewrite stress)
- A4 content-free counters with trip-wire safeguard
- A5 structural change with no runtime flag (defensible rationale)
- Test Contract with 13 RED-first tests + tests-that-must-stay-green
- Rollback path that explicitly forbids sentinel restoration without both-panel review
- Existing-sentinel-in-model-output handling (geek-out catalog Entry 1 case)
- Review protocol matches established session pattern

### Council protocol observed

- Council ran on a finished spec draft, pre-canonical
- Each seat produced findings independently before synthesis
- Verdict is one of {RATIFY, RATIFY-WITH-AMENDMENTS, BLOCK, REVISE}
- Amendments sized to close mechanically (most are one-paragraph spec additions, two are test additions)
- The boundary held: Claude's council did not run Codex's six-agent panel; Codex's panel sits in their lane

### What's next per the spec's own protocol

1. Codex's six-agent panel sits on the spec (Codex's lane)
2. Both councils' amendments fold into the spec
3. Spec becomes canonical (commit)
4. Cooling-off night
5. Implementation per spec contract with RED-first tests
6. Both panels post-implementation
7. Live-daemon natural-text probe sweep
8. Geek-out catalog Entry 3 closes when live conversation confirms old sentinel phrase is absent

*This council review is read-only. No code or non-audit-dir docs changed in producing it.*
