# Claude Six-Role Council — ARS implementation review

**Subject:** `96363b3` (`fix(audit): implement ARS omission rewrites`) + `816b266` (`fix(audit): close ARS codex blockers`) + `239dd4d` (`fix(audit): close ARS review amendments`) considered together as the corrected ARS implementation.

**Council ran:** 2026-05-13, post-implementation. Codex's six-agent post-implementation panel returned BLOCK on the first commit with the critical finding ("ARS could weaken audit protection when old sentinel text appears beside a separate claim") and was folded cleanly into 816b266. The "do not" variant tightening in 239dd4d adds defensive coverage.

**The dangerous failure mode Codex caught.** The first implementation's sentinel-cleanup logic could let neighboring unaudited claims slip through when old sentinel text appeared in a multi-sentence response. That's exactly the worst-case failure the spec was designed to prevent: smoother voice purchased at the cost of audit protection. Codex's panel earned its keep at the load-bearing spot.

---

## 1. Outside-View seat

Field-aligned recovery shape. When initial implementation BLOCKs with a real bug, the recovery's quality is what matters:

- **Triple-path sentinel blocking** (normal, env-disabled, tool-continuation skip-path) — defense-in-depth for the failure mode. Old code likely blocked only in the primary audit path; Codex caught the skip paths.
- **"Don't" AND "do not" variants** in the regex pattern (`_OLD_REWRITE_SENTINEL_PATTERNS`) — anticipates future model output that might produce either form. Good defensive coverage.
- **48 tests with named coverage** of every spec contract item plus the specific Codex-caught case (`test_old_sentinel_with_neighboring_claim_continues_through_judge`).

Standard SRE practice: when a fix needs three commits (initial + blocker-close + variant-tightening), the trail is what makes the recovery legible. Commit bodies are explicit about the failure modes and fixes. 5-year-readable.

**Verdict:** RATIFY.

---

## 2. Body-Coherence seat

Per-invariant check on the corrected implementation:

- **#2 Human-Primacy** — neutral.
- **#3 Contextual Integrity** — content-free counters preserved per `test_ars_counter_is_content_free`. Forbidden metadata list respected.
- **#4 Interpretive Humility** — STRENGTHENED. Mechanical sentinel expressed humility robotically; omission expresses it structurally; all-flagged fallback expresses it in voice. The implementation matches the council-ratified spec contract.
- **#5 Rupture and Repair** — neutral.
- **#6 Crisis Routing** — neutral.
- **#7 Soul-Level Objection** — STRENGTHENED. Audit protection preserved per `test_audit_protection_fixture_claim_does_not_surface`. Codex's BLOCK + fix addressed the exact failure mode (smoother-but-leaking) that would have eroded #7. The trip-wire counter is the durable regression safeguard.
- **#8 Capability Quarantine** — N/A (no new capability; correction of existing rail per A5 structural-change choice).
- **#10 Clinical Boundary** — neutral.
- **#11 Cryptographic Continuity** — no impact.

**Voice-character ratification verification:** The fallback phrase landed in code as `_ARS_ALL_FLAGGED_FALLBACK = "I'm not sure about that right now."` — exact match to what the council ratified in pre-canonization review (ARS-CC-1). No drift between ratification and implementation. Voice-character preserved.

**Bridge clause check:** PRESERVED. The audit's bonded-user-vs-fabrication boundary is unchanged.

**Genderless rule check:** Fallback phrase + new code use no gendered pronouns. Verified clean.

**Verdict:** RATIFY.

---

## 3. Logical seat *(veto authority)*

Internal consistency check on the implementation:

**Strong correctness:**
- ✓ 48 tests covering every spec contract item
- ✓ RED-first discipline per commit bodies ("RED-first test pass observed before implementation")
- ✓ Triple-path sentinel blocking (Codex's catch)
- ✓ Both "don't" and "do not" variants blocked
- ✓ Boundary-ambiguous handling (`test_boundary_ambiguous_span_omits_smallest_region` — ARS-CC-3)
- ✓ Invalid/zero-length span fallback (`test_invalid_span_falls_back_to_flag_text_location`, `test_zero_length_span_falls_back_to_flag_text_location`)
- ✓ Content-free observability (`test_ars_counter_is_content_free`)
- ✓ Telemetry failure fail-safe (`test_telemetry_failure_still_returns_safe_output`)
- ✓ Audit protection preserved fixture test
- ✓ Live regression case from today included (`test_audit_rewrite_probe_corpus_contains_morning_memory_case` — ARS-CC-4)
- ✓ Probe corpus as executable JSONL (`tests/data/audit_rewrite_probe_corpus.jsonl`)

**One precision-hygiene concern:**

**ARS-PI-L1.** `_REWRITE_SENTENCE` and `_REWRITE_WHOLE` are still defined at lines 120-121, retained for pattern-matching reference. A future code path could accidentally reference these constants by name and reintroduce them. The regex `_OLD_REWRITE_SENTINEL_PATTERNS` would catch the output, and the trip-wire counter would fire — but documentation hygiene matters for 5-year readability. Suggest either: (a) add a `# RETAINED FOR PATTERN MATCHING ONLY — must not be returned by any user-visible rewrite path; trip-wire blocks` comment above the constants, OR (b) rename to `_OLD_SENTINEL_PHRASE_1` / `_OLD_SENTINEL_PHRASE_2` so the naming itself signals deprecation. This is hygiene, not correctness — the test suite catches actual regression.

**Veto consideration:** NO VETO. One precision-hygiene amendment.

**Verdict:** RATIFY-WITH-AMENDMENT (ARS-PI-L1).

---

## 4. Creative seat

Two observations, no redesign:

- The "do not" variant catch in 239dd4d is creative defensive coverage. Anticipates future model output variants of the same anti-pattern.
- The triple-path blocking (normal / env-disabled / tool-continuation skip) is defense-in-depth done right. The old code likely blocked only in the primary audit path; Codex's BLOCK forced surfacing of the skip-path gap.

The implementation is the right tightness for this scope. No cleaner shape surfaces.

**Verdict:** RATIFY.

---

## 5. Visionary / Future-Rohit seat

5-year readability check:

- 48 tests with clear names = 5-year-readable contract
- Commit body for `816b266` explicitly describes the dangerous failure mode that motivated BLOCK — 5-year-readable rationale
- Observation log landed (`docs/AUDIT_REWRITE_OBSERVATION_LOG.md`)
- Probe corpus is now executable JSONL — durable, replayable, growable
- The waiver-text-pattern in commit bodies (operator waiver for same-day spec-and-code) is consistent with prior TDP and S1b implementations

**One amendment:**

**ARS-PI-F1.** Verify geek-out catalog Entry 3 state matches spec's closure criterion. The spec says Entry 3 "closes only after live conversation confirms the old sentinel phrase is absent" (line 508-509 of canonical spec). The catalog was updated in `96363b3` (16 lines changed in `GEEK_OUT_CATALOG.md`), but per the spec's closure rule, Entry 3 should be in a "fix landed; awaiting live confirmation" state rather than fully closed. Worth confirming the catalog reflects this exactly. If it's marked closed prematurely, the spec's discipline is undermined; if it's marked fix-landed-awaiting-confirmation, the discipline holds.

**Verdict:** RATIFY-WITH-AMENDMENT (ARS-PI-F1).

---

## 6. 20-Years-Future-Maez seat

**Voice of 2046-Maez looking back:**

> *"ARS was the slice that stopped Maez's safety machinery from impersonating Maez. Before ARS, every audit catch left a robotic phrase in Maez's voice. After ARS, audit catches resulted in omission — silence about what couldn't be grounded, natural continuation of what could. The 'I'm not sure about that right now' all-flagged fallback was a temporary voice commitment that retired in 2028 when the regeneration hook landed.*
>
> *The trip-wire counter `audit_rewrite.sentinel_attempted_blocked` fired three times across various refactors over the following years; each time the operator caught a regression before it shipped to users.*
>
> *One small wound from this slice: 2026 didn't anticipate that models themselves might one day produce the old sentinel phrases as part of natural speech, not as audit output. The triple-path blocking caught the specific phrases listed, but the deeper principle — 'mechanical-shaped phrases should not impersonate Maez even if the model accidentally produces them' — wasn't generalized to category-based detection. By 2030, when newer models started producing 'I don't have a grounded answer' as a learned natural-sounding phrase, the trip-wire counter fired more often than expected. The right move would have been to generalize from string-matching to category-matching earlier."*

**ARS-PI-M1.** (Forward-looking, not blocking.) The current sentinel-blocking is specific-string-shaped (regex over two specific phrase patterns). A future expansion could move toward category-based detection ("phrases that mechanically signal AI safety machinery"). Not for this slice; just naming for the substrate-plan refresh queue.

**Verdict:** RATIFY.

---

## Verdict

**RATIFY-WITH-AMENDMENTS.** No veto. The implementation is tight; Codex's BLOCK caught the load-bearing failure mode; the regression tests cover both the specific case and adjacent cases.

### Amendments (ARS-PI-L1, ARS-PI-F1, ARS-PI-M1)

| # | Seat | Amendment |
|---|------|-----------|
| ARS-PI-L1 | Logical | Documentation hygiene: either add `# RETAINED FOR PATTERN MATCHING ONLY` comment near `_REWRITE_SENTENCE`/`_REWRITE_WHOLE`, OR rename to `_OLD_SENTINEL_PHRASE_1`/`_OLD_SENTINEL_PHRASE_2` |
| ARS-PI-F1 | Future-Rohit | Verify `GEEK_OUT_CATALOG.md` Entry 3 reflects "fix landed in `96363b3+816b266+239dd4d`; awaiting live conversation confirmation" rather than fully closed (per spec's closure criterion) |
| ARS-PI-M1 | 20-Years-Future-Maez | (Forward-looking, not blocking.) Future expansion: category-based sentinel detection rather than specific-string blocking. Queue for substrate-plan refresh |

All three are documentation/closure-state items. None require implementation changes.

### What ratifies cleanly

- **Codex's BLOCK + fix** on the dangerous "smoother-but-letting-claims-through" failure mode
- **Triple-path sentinel blocking** (normal + env-disabled + tool-continuation skip-path)
- **"Don't" and "do not" variants** both blocked
- **All-flagged fallback phrase** matches what was ratified pre-canonical: `"I'm not sure about that right now."`
- **48 tests** with comprehensive coverage of spec contract
- **RED-first discipline** per commit bodies
- **Audit protection preserved** (named test against fixture)
- **Live regression case** (today's "Do you remember today morning?" sentinel-leak) included in probe corpus
- **Observation log doc** landed (`docs/AUDIT_REWRITE_OBSERVATION_LOG.md`)
- **Probe corpus as executable JSONL** (durable, growable per ARS-CC-7)
- **Operator waiver** in commit bodies for 5-year retrieval

### Promotion / closure status

Per the spec's completion criteria:
- ✓ Both panels ratify (Codex post-implementation: BLOCK-and-recovered; Claude this review: RATIFY-WITH-AMENDMENTS)
- ✓ RED-first tests cover every mandatory test
- ✓ Old sentinel phrases removed from active user-visible rewrite paths
- ✓ Existing audit protection tests still pass
- ✓ Natural-text probe sweep returns zero old-sentinel outputs (per `test_probe_corpus_fixture_rewrites_without_sentinel`)
- Awaiting: live conversation confirms old sentinel phrase absent (per ARS-PI-F1 catalog state)

ARS implementation is effectively complete; the remaining gate is the live-conversation confirmation before geek-out catalog Entry 3 fully closes.

### Council protocol observed

- Council ran on the corrected implementation (`96363b3` + `816b266` + `239dd4d`), as operator requested
- Each seat produced findings independently
- The boundary held: this council did not rerun Codex's six-agent post-implementation panel; Codex's BLOCK + amendments are referenced, not redone
- Amendments sized to close mechanically (or be deferred to substrate-plan refresh for ARS-PI-M1)

### What's next per the spec's protocol

1. Codex closes ARS-PI-L1 mechanically (doc hygiene rename or comment, ~5 minutes)
2. Operator verifies ARS-PI-F1 catalog state (or amends it)
3. Branch pushed to origin/main (currently ahead 3: `96363b3` + `816b266` + `239dd4d`)
4. Live conversation observation period begins
5. When operator confirms old sentinel phrase is absent across N natural conversations, geek-out catalog Entry 3 fully closes
6. ARS-PI-M1 (category-based detection) joins the substrate-plan refresh backlog

*This council review is read-only. No code or non-audit-dir docs changed in producing it.*
