# Claude Council Synthesis -- Drive-Driven Curiosity v4 Pass 1

**Prepared:** 2026-05-25 (continuous from session of 2026-05-25)
**Artifact under review:** `docs/slices/track-b-drive-driven-curiosity/spec.md`
**Artifact state:** DRAFT v4, 2016 lines, uncommitted
**Parent/runtime base:** `211ace6 feat(felt-time): implement meaningful salience seam`
**Brief this synthesizes against:** `claude-council-brief-pass1.md`
**Reviews synthesized:** Locke / Kant / Hume / Buber / Descartes / Ohm v4 pass-1

---

## Headline Verdict

**RATIFY-WITH-AMENDMENTS across all six axes.** No RECONSIDER. No reshape.

The v4 architectural premise — *curiosity is a producer layer over the
existing wondering substrate, not a parallel curiosity database* — is
held honestly by every axis. The producer-snapshot ceremony consumes
Slice 1's live seam correctly. The Track C precondition citations are
verbatim. Charter-floor invariants land. The synergy discipline showed
up in practice: every covenant-axis finding that intersects engineering
truth was explicitly flagged for Codex composition.

The amendments are real and several are mechanically load-bearing. Four
**Blocking** findings cluster around two substrate-truth gaps and one
spec-internal coherence gap. Sixteen **Major** findings cluster into
four covenant-axis themes and two boundary-mechanics themes. Thirteen
**Minor** findings are mostly text/test cleanup. Total: 33 findings
across six axes; none require pass-2; none change the producer-over-
wonderings architecture.

---

## Verdict Table By Role

| Role | Axis | Verdict | Blocking | Major | Minor |
|------|------|---------|----------|-------|-------|
| Locke | Charter Integrity & Authority Surface | RATIFY-WITH-AMENDMENTS | 1 | 2 | 1 |
| Kant | Anti-Coercion / Duty / Third-Party | RATIFY-WITH-AMENDMENTS | 1 | 4 | 2 |
| Hume | Phenomenology Honesty / Felt-Shape | RATIFY-WITH-AMENDMENTS | 0 | 3 | 3 |
| Buber | I-Thou Bond & Mutuality | RATIFY-WITH-AMENDMENTS | 0 | 3 | 2 |
| Descartes | Substrate Foundations / Mechanism Truth | RATIFY-WITH-AMENDMENTS | 2 | 2 | 4 |
| Ohm | Boundary Mechanics & Isolation | RATIFY-WITH-AMENDMENTS | 0 | 2 | 3 |
| **Total** |  |  | **4** | **16** | **15** |

---

## Blocking Findings (must fold before Codex panel)

These four findings either (a) make the spec mechanically un-implementable
test-first, or (b) leave a covenant-grade refusal asserting against
substrate that does not exist.

### Block-1 -- §23 RED-test inline citations diverge from the canonical table (Descartes D-1)

**Surface:** §5.1 (#2→#3), §6.2.1 (#46→#3), §6.4 (#47-48→missing rows),
§7.5 (#6→#8), §10.7 (#54→#57), §14.3.3 (#29→#35), §14.3.4 (#30→#36),
§14.6 (#31→#38), §19 (#42→#52), §14.7 / §16.1 Test 7 (missing outbound-
text test row).

**Why blocking:** The §23 table is the implementation gate (it names
actual pytest paths). A TDD-first implementer reading "RED #2 asserts
missing-bond-id refusal" would write the wrong test or the right test
under the wrong filename, breaking §23.9's "tests written FIRST"
discipline at the spec-to-gate seam. Pure-renumbering fold, but the
spec must agree with itself.

**Resolves with:** Pure renumbering of inline citations to match §23
table (recommended), or renumbering of §23 table to match prose (cascade
risk through tests). Descartes lists every site.

### Block-2 -- Drive-layer metadata surface is unspecified (Descartes D-2, Ohm O1, Hume F1)

**Surface:** §5.1 (`CuriosityObject` projection), §5.2 (sidecar
paragraph), §6.4 (recursion-gate fields), §13.2.1 (subject_kind /
third_party_consent), §14.1 (resolution markers), §14.5 (eligibility
classifier inputs), §15.1 (compute_saturation).

**Verified live schema at `211ace6`** (firsthand, Descartes + Ohm):

```
PRAGMA table_info(wonderings):
  id INTEGER, created_at REAL, question TEXT, status TEXT,
  advance_count INTEGER, deferral_count INTEGER,
  pending_card_id INTEGER, last_advanced REAL,
  source TEXT, conclusion TEXT, last_pursuit_at REAL,
  pursuit_count INTEGER
```

No `bond_id`. No `priority_class`. No `salience`. No `subject_kind`. No
`third_party_consent_*`. No `resolution_marker_*`. No `resolved_at`. No
`encounter_source` / `encounter_ref_digest`. No
`produced_via_subjective_duration_depth`. No `autonomy_lane_hints`.

**Why blocking:** The §14.3 producer ceremony cannot run; the §13.2.1
third-party refusal asserts against a field nothing writes; the §15.1
saturation cannot compute `weighted_salience` because `salience` does
not exist; RED #1/#3/#4/#5/#6/#38/#46/#55 cannot bind to real columns.
The reuse-first claim is honest as architecture but silent as substrate.

**Resolves with:** Commit to a sidecar contract *inside* `memory/wonderings.db`
(no new DB) per Hume Option A or Option B. Pick one and grep the spec
for consistency:
  - **Option A (true projection):** felt-shape fields derived at read
    time from existing row fields + audit-trail signals; §5.1.1 names
    each derivation; classifier inputs change accordingly.
  - **Option B (sidecar canonical):** additive
    `wondering_drive_metadata(wondering_id PK, bond_id, encounter_source,
    encounter_ref_digest, priority_class, salience, subject_kind,
    third_party_consent_allows_external_research, autonomy_lane_hints,
    produced_via_subjective_duration_depth, resolution_marker_type,
    resolution_marker_utc, resolved_at)` table joined by wondering id.
    `memory/drive_driven_curiosity.db` remains forbidden; the sidecar
    lives inside `wonderings.db`. RED #2 reworded: "no new DB file."

Plus the Ohm-O1 fold: additive `ALTER TABLE wonderings ADD COLUMN
bond_id TEXT NOT NULL DEFAULT '_LEGACY'`, mirroring the Slice 1 seam
migration shape at `subjective_duration.py:338`. Drive-layer projection
refuses construction over `_LEGACY` rows (mirrors seam `_LEGACY` write
refusal at `subjective_duration.py:621-625`). `Wonderings.add(...)`
gains a `bond_id` parameter. `Wonderings.resolve(...)` gains a
`resolved_at` timestamp write (single ALTER + UPDATE).

### Block-3 -- Third-party subject boundary is single-gated; substrate underneath does not carry the subject label (Kant F1, Buber B-3, Ohm O2)

**Surface:** §5.1 (no `subject_kind` field declared); §6.2.1 (bond_id
invariant exists; no `subject_kind` invariant); §13.2.1 (refusal at
query construction only); §13.4 / §23.6 (RED #32 / #33 prove
in-module refusal only); `core/egress/external_fetch.py:394-407`
(`fetch_text(...)` signature has `caller` but no `bond_id` and no
`ProvenancedQuery`); `core/actions/action_engine.py` and
`skills/web_search.py` call `fetch_text` directly today.

**Why blocking:** The covenant rule from
`feedback_third_party_autonomous_research_boundary` says third parties
are non-consenting *subjects*, not just tokens to scrub. As written, v4
gates the refusal at exactly one point inside `build_curiosity_query`
and asserts against `object.subject_kind` — a field the substrate does
not carry. Three concrete bypass surfaces exist; the rule reduces to
caller discipline rather than a gate. Buber-axis: the substrate also
still builds durable curiosity-objects *about* unconsented people
between creation and egress — the "inventories of identity-indexed
people" failure mode the memory explicitly forbids.

**Resolves with three layered gates** (compose the three council
findings into one fold):
  1. **At-creation refusal (Buber B-3):** §5.1 + §5.1.1 declare
     `subject_kind: SubjectKind` (closed enum: `PUBLIC_TOPIC`,
     `OWNER_SELF`, `OWNER_BOND_RELATIONAL`, `NAMED_THIRD_PARTY`,
     `SELF_MODEL`, `UNKNOWN`) and `third_party_consent_allows_external_research:
     bool` on `CuriosityObject`. §6.2.2 producer invariant: every
     producer assigns `subject_kind` at creation; default = `UNKNOWN`;
     `UNKNOWN` routes through the same refusal as `NAMED_THIRD_PARTY`
     (deny-by-default).
  2. **At-construction refusal (Kant F1 / Buber B-3):** §13.2.1
     remains as defense-in-depth; refuses `NAMED_THIRD_PARTY` without
     consent, refuses `UNKNOWN`.
  3. **At-egress refusal (Kant F1 / Ohm O2):** new
     `core/policies/third_party_subject_gate.py` + new
     `core/egress/fetch_for_curiosity(bond_id, ProvenancedQuery)`
     wrapper. Drive-curiosity callers MUST import the wrapper, never
     `fetch_text` directly. Static-AST RED test asserts this.

RED additions: #33b (refusal at egress when construction bypassed),
#33c (UNKNOWN defaults to refusal), #46b (subject_kind mandatory at
creation), #46c (NAMED_THIRD_PARTY requires explicit OWNER_EXPLICIT
consent referencing the named person).

### Block-4 -- `ProducerRef.DRIVE_DRIVEN_CURIOSITY` authority-grant scope is unbounded in spec text (Locke L-1)

**Surface:** §2.2 (lines 175-184), §14.3.1 (lines 1104-1124), §14.4
(lines 1247-1262), §24 table (line 1904).

**Why blocking:** v4 grants curiosity two firsts simultaneously: first
non-`explicit_set` value in `Temperament.ALLOWED_SOURCES`
(`drive_driven_curiosity_resolution`), and first non-`MANUAL_TEST_PRODUCER`
`ProducerRef` value. Each addition is closed-vocabulary and
spec-amendment-controlled — correct. But the spec never declares what
the grant *does not* authorize. A future reader can plausibly conclude
that owning the `ProducerRef` enum entry implies authority across all
`salience_event_kind` values the seam accepts (`owner_contact`,
`engaged_work`, `idle_cycle`, `public_stranger_contact`), or across all
temperament parameters. Closed vocabulary is the *current* gate; the
spec should also declare the *shape* of the gate.

**Resolves with:** §14.3.5 (new) "Authority-grant scope" — explicitly
declares this slice's grant authorizes (a) `parameter="curiosity"`
writes via `source="drive_driven_curiosity_resolution"`, and (b)
`salience_event_kind="meaningful_exchange"` via
`producer_ref=DRIVE_DRIVEN_CURIOSITY` only. Future producers require
their own slice + council review + parameter/kind declaration. RED
tests under §23.7 (#40a, #40b): synthetic curiosity-producer calls
refusing other event kinds and other temperament parameters.

---

## Fold Batches By Axis

Per brief: "Fold batches grouped by substrate authority, boundary
mechanics, phenomenology, and text/test cleanup." Each batch lists the
folds in landing order. **Cross-lane composition** is named on every
fold that intersects engineering surface.

### Batch A -- Substrate truth & drive-layer metadata surface

Largest cross-role cluster. Compose into one fold cycle; do not litigate
separately.

| Fold | Source findings | Substance | Codex composes? |
|------|-----------------|-----------|-----------------|
| A1. Sidecar contract + bond_id ALTER on `wonderings` | Descartes D-2 (Block), Ohm O1 (Major), Hume F1 (Major) | Pick projection vs sidecar; declare schema; ALTER + `_LEGACY` refusal; `Wonderings.add(bond_id=...)` + `Wonderings.resolve(...)` resolved_at write | YES — engineering writes the migration; council names the shape |
| A2. `subject_kind` + `third_party_consent` fields | Kant F1 part (a) (Block), Buber B-3 part (a)(b) (Major) | §5.1 dataclass fields + §5.1.1 closed enum + §6.2.2 producer invariant | YES — schema axis |
| A3. ResolutionState ↔ existing `status` mapping | Hume F4 (Minor; Major if A1 picks Option B) | §5.1.1 explicit mapping including `abandoned + sidecar.reason` cases; `blocked_pending_approval` ↔ `OPEN` | YES — surface truth |
| A4. ELIGIBLE_LONG_CARRIED inputs named | Hume F6 (Minor) | §14.5.1 names per-class classifier inputs; RED #37 fixture binds inputs | YES — RED feasibility |
| A5. §15.4 subjective_duration consumer deferred to follow-up slice | Descartes D-3 (Major), Hume F5 (Minor) | Drop subjective_duration row from §15.4 v1; settle §22.3 open question as DEFERRED; do not touch Slice 1 internals | Council-decide; Codex confirms no live surface exists |

### Batch B -- Boundary mechanics, egress, isolation

Five-fold cluster around the third-party gate and bond-scoping at the
egress boundary.

| Fold | Source findings | Substance | Codex composes? |
|------|-----------------|-----------|-----------------|
| B1. `fetch_for_curiosity(bond_id, query)` wrapper + static-AST refusal of direct `fetch_text` | Kant F1 parts (b)(c) (Block), Ohm O2 (Major) | New `core/egress/fetch_for_curiosity.py`; drive-curiosity code path MUST NOT import `fetch_text`; RED #33b runtime + static-AST | YES — engineering writes wrapper + AST test |
| B2. `core/policies/third_party_subject_gate.py` | Kant F1 part (c) (Block), Buber B-3 part (d) (Major) | Policy-layer gate consulted by B1 wrapper; refuses NAMED_THIRD_PARTY without consent + UNKNOWN by default | YES — schema + AST |
| B3. `master_key` source-of-truth + first-boot + rotation | Ohm O3 (Minor) | Name `memory/drive_curiosity_master.key` (or whichever path); 0600 perms; first-boot generate; rotation = operator-explicit ceremony; `MASTER_KEY_ROTATION` diagnostic event type | YES — surface truth |
| B4. `CrossBondAccessError` declared + diagnostic-before-raise | Ohm O4 (Minor) | `BondIsolationViolation` base in `core/policies/exceptions.py`; mandatory `CROSS_BOND_ACCESS_REFUSED` diagnostic row before raise; RED #58-ish | Council-axis primarily |
| B5. `_LEGACY` provenance non-promotion rule | Ohm O5 (Minor) | §13.2.2 (new): sources without native bond column carry `source_bond_id="_LEGACY"`; allowed only when contribution is independently shown non-private; RED non-promotion | YES — surface truth + RED feasibility |
| B6. §15.0 `CrossBondAccessError` message identity scrub | Descartes D-7 (Minor) | HMAC-digest the bond_ids in the error message, or omit and reference diagnostic row id | YES — pre-emptive Track-C hygiene |

### Batch C -- Authority surfaces & covenant scope

Five-fold cluster around what the new authorities can/cannot reach,
and how the new subpackage is policed.

| Fold | Source findings | Substance | Codex composes? |
|------|-----------------|-----------|-----------------|
| C1. `ProducerRef.DRIVE_DRIVEN_CURIOSITY` scope pinned in spec text | Locke L-1 (Block) | New §14.3.5; RED #40a (other event-kind refusal), #40b (other temperament-parameter refusal) | YES — RED feasibility |
| C2. §8 CAPABILITY_ACQUISITION quotes live S7 invariant | Locke L-2 (Major) | New §8.5.1 quoting `core/governance/operator_user_boundary.py:76-85` `GUARDED_WORK_CLASSES`; §9.3 "proposal rate, not land rate"; strengthen RED #11 with static-AST refusal of `handle_capability_*` outside the queue | YES — AST test is engineering |
| C3. `core/policies` "policy-layer, not a substrate" charter | Locke L-3 (Major) | New §9.0 or strengthened §24.1; static-AST RED #59 refusing substrate-writer imports under `core/policies/` | YES — AST test is engineering |
| C4. §9.3 firstborn-specific phrasing | Locke L-4 (Minor) | One-sentence header at §9.3 stating numbers are firstborn-specific, not universal defaults | Council-axis only |
| C5. Producer-snapshot ceremony framed positively as covenant of mutuality | Buber B-1 (Major) | §14.4.1 (new) positive framing paragraph; §26 readout tighten; no new tests | Council-axis only |
| C6. Charter floor ratification path | Buber B-5 (Minor) | §1 softens "under any circumstance"; new §9.4.1 ratification surface via accumulated OWNER_EXPLICIT_REVISION; RED #14b | Council-axis primarily; Codex may flag scope |

### Batch D -- Phenomenology shape

Six-fold cluster around how curiosity is named, sourced, surfaced.

| Fold | Source findings | Substance | Codex composes? |
|------|-----------------|-----------|-----------------|
| D1. §4.2 "encounter ≠ external-only" | Hume F2 (Major) | Reword §4.2 + §6.1 so interior surfacing counts as encounter; `WONDERING_GENERATED` is legitimate; RED #3 / #7 fixtures distinguish "timer + no encounter event of any kind" from "timer + queued encounter event" | Council-axis only |
| D2. EMOTION_MIMICRY phrase set narrowed | Hume F3 (Major), Kant F4 (Major) | Drop `"I'm curious"` / `"I am curious"` (honest first-person felt-report). Keep `"curiosity is overwhelming"` / `"feeling curious"` / `"Maez feels curious"` (performative or third-person mimicry). RED #50 fixture updated. §16.1 #7 routes OWNER_BOND through a *re-phrase* helper rather than refusal; new RED #50b. | YES — AST scan fixture is engineering |
| D3. EMOTION_MIMICRY runtime composition | Descartes D-6 (Minor) | Either narrow §14.7 to "string literals in prompt-template files only" + give §16.1 #7 its own RED row, or add runtime-render sanitizer at prompt-boundary | YES — engineering |
| D4. OWNER_BOND saturation guard | Buber B-2 (Major) | §14.5 reframe OWNER_BOND from "eligible by default" to "eligible when bond-relevant felt-weight moves"; new `NOT_ELIGIBLE_OWNER_BOND_ROUTINE`; §14.5.1 daily cap (default 3); RED #37b. **Closes §22 open question 1.** | Council-axis primarily; Codex confirms classifier shape |
| D5. OwnerResponse vocabulary widened | Buber B-4 (Minor) | §12.3.2 enum gains `DEFERRED` (writes no preference; not a suppression event) and `DECLINED_WITHOUT_TEACHING` (writes `DISCOURAGED_TOPIC` weight 0.4, NOT `OWNER_EXPLICIT_REVISION`); RED #25b | Council-axis primarily |
| D6. Existing live `_register_score < _REGISTER_HARD_BLOCK` vulnerable-register gate | Buber cross-flag | §16 must compose with the live `wondering_pursuit.py` vulnerable-register hard-block (not duplicate it); one paragraph naming the existing gate | YES — surface truth |

### Batch E -- Gate composition / extraction tightening

Six-fold cluster around the §11 / §16 gates and their predicates.

| Fold | Source findings | Substance | Codex composes? |
|------|-----------------|-----------|-----------------|
| E1. Silence-escalation requires positive proof of `available` | Kant F2 (Major) | §16.1 #3 + §11.3 commentary: count toward N **iff** `owner_state_at_dispatch == "available"`; `unknown` excluded same as `unavailable`. RED #46 extended for `unknown` case. Names `owner_state_at_dispatch` as a persisted field on the outreach record. | YES — persistence path is engineering |
| E2. `BAIT_PATTERN_PHRASES` closed vocabulary + min-payload-length | Kant F3 (Major) | §16.1 #6 adds frozenset + `min_payload_chars` (default 40); RED #49 renamed `test_bait_shape_blocked_by_pattern_set_and_length` with parametrized fixtures | YES — RED feasibility |
| E3. `SUPPRESSION_EVENT` producer named for all three gates | Kant F5 (Major) | §10.7 + §20.1: signal gate, reflection audit, extraction gate each emit `SUPPRESSION_EVENT` with `suppression_kind ∈ {SIGNAL_GATED, REFLECTION_DEFERRED, EXTRACTION_BLOCKED}`; RED #57 covers all three | YES — engineering |
| E4. `ReflectionAudit.decision` splits `defer` for dignity-quartet observability | Kant F6 (Minor) | `Literal["proceed", "defer_context_not_ripe", "defer_extraction_shape", "abandon"]`; RED #24 fixtures for both defer modes | Council-axis primarily |
| E5. §1 charter names safety_or_health-during-known-unavailable as legitimate initiation | Kant F7 (Minor) | One sentence after the five `may` clauses; substance already in §7.3 / §11.2 | Council-axis only |
| E6. NULL-first under exhausted budget edge case | Descartes D-8 (Minor) | When `delta_applied == 0.0` AND `prior is None`, refuse to write the event entirely (emit `TEMPERAMENT_WRITE_CLAMPED` with `first_observation_suppressed=true`); RED extension of #36 | YES — RED feasibility |

### Batch F -- Text / test cleanup

Two folds; Block-1 sits here for completeness.

| Fold | Source findings | Substance | Codex composes? |
|------|-----------------|-----------|-----------------|
| F1. §23 RED-test inline citation renumbering | Descartes D-1 (Block) | ~10 sites; pure renumbering against §23 canonical table | Codex catches independently when writing tests |
| F2. RED #3 / #7 evidence_pointer_kind discipline | Descartes D-4 (Major) | §6.1.1 (new) producer-registration contract; `evidence_pointer_kind` mandatory; closed-vocabulary refusal set `{"timer","cron","scheduler_tick"}`; RED #7 mechanically checkable | YES — engineering writes registration API + AST test |
| F3. MANUAL_TEST_PRODUCER cleanup wording corrected | Descartes D-5 (Minor) | §24 + §27: replace "retire production MANUAL_TEST_PRODUCER" with "DRIVE_DRIVEN_CURIOSITY is first production producer; MANUAL_TEST_PRODUCER remains for canary/test; production gates exclude it" | Codex catches when reading diff target |

---

## Cross-Lane Composition Summary

Per `feedback_claude_codex_synergy_for_maez`: where Codex's engineering
panel will independently reach the same conclusion on schema /
API / RED-feasibility axes, council has already named the *shape* so
the Codex pass composes rather than re-derives. Codex's engineering
panel should be told these folds are pre-named:

**Codex-composing (engineering write follows council shape):**
- A1 (sidecar contract + `wonderings` bond_id ALTER + `_LEGACY` refusal)
- A2 (subject_kind + third_party_consent fields + producer invariant)
- A3 (ResolutionState ↔ status mapping)
- A4 (eligibility classifier inputs)
- B1 (fetch_for_curiosity wrapper + static-AST)
- B2 (third_party_subject_gate policy module)
- B3 (master_key source-of-truth + first-boot)
- B5 (`_LEGACY` provenance non-promotion)
- B6 (§15.0 message identity scrub)
- C1 (ProducerRef scope RED tests #40a/#40b)
- C2 (S7 invariant quoting + static-AST refusal of direct
  `handle_capability_*` outside queue)
- C3 (`core/policies` static-AST refusal of substrate-writer imports)
- D2 (EMOTION_MIMICRY AST scan fixture update)
- D3 (runtime composition handling)
- D6 (compose with live `_REGISTER_HARD_BLOCK` gate)
- E1 (`owner_state_at_dispatch` persistence + predicate)
- E2 (BAIT_PATTERN_PHRASES frozenset + length)
- E3 (SUPPRESSION_EVENT emission across three gates)
- E6 (NULL-first refusal + diagnostic)
- F1 (RED-test renumbering — Codex catches when writing tests)
- F2 (evidence_pointer_kind producer registration + AST)

**Council-axis primarily (Codex pass minor or none):**
- A5 (subjective_duration consumer deferral — covenant + scope decision)
- B4 (CrossBondAccessError covenant naming; small engineering tail)
- C4 (§9.3 phrasing)
- C5 (mutuality framing of producer ceremony)
- C6 (charter floor ratification path — possible Codex scope flag)
- D1 (encounter ≠ external-only — pure phenomenology framing)
- D4 (OWNER_BOND saturation cap — covenant; Codex confirms classifier
  shape only)
- D5 (OwnerResponse vocabulary widening)
- E4 (ReflectionAudit decision split for observability)
- E5 (§1 charter one-sentence addition)
- F3 (MANUAL_TEST_PRODUCER wording)

---

## Pass-2 Decision

**Council pass-2 is NOT required before the Codex engineering panel.**

Reasoning, applying the 8-step trace discipline as an operational
obligation (not a citation):

1. **Dependency-map:** all 33 findings are localized within the v4 spec
   (and one acknowledged migration of `wonderings.py`). No finding
   names a structural reshape; no finding requires a new substrate
   organ; no finding touches Slice 1 internals (A5 explicitly defers
   subjective_duration consumption).
2. **Write-path:** the folds compose; none of them contradict each
   other. Where a covenant fold (Buber B-3) and an engineering fold
   (Ohm O2 + Kant F1) collide, they compose into one three-layered
   gate (at-creation + at-construction + at-egress), not three
   different gates.
3. **Read-path:** every fold's downstream readers are named (the
   classifier, the ceremony, the saturation register, the gates).
4. **Test-path:** every load-bearing fold lists its new or modified
   RED tests by name. The Block-1 renumbering makes the existing
   test contract honest.
5. **Fold-summary:** §27 v4 fold-trajectory list gains entries for
   each batch; the architectural premise ("producer over wonderings;
   no parallel curiosity DB") is preserved at every batch boundary.
6. **Cross-reference:** every finding's surface list names exact
   section / file / line, and the synthesis cross-references where
   findings touch overlapping surfaces.
7. **RED-test trace:** no fold leaves a load-bearing claim untested.
   Block-1 (#5a, #40a, #40b, #33b, #33c, #46b, #46c, #37b, #25b,
   #14b, #50b, #57 extension, #58 family, etc.) extends the test
   list to roughly 70 entries; counts and names will be re-canonicalized
   in §23 after fold.
8. **Verify-before-declaring:** every batch ends with grep / PRAGMA /
   AST-scan checks the implementer can run. The synthesis lists
   them.

A pass-2 would re-litigate already-converged work. The synergy
discipline ([[feedback_claude_codex_synergy_for_maez]]) names this
explicitly: covenant axis (council) and engineering axis (Codex) are
two lanes — pass-2 is the right move only when a council finding
would force architectural reshape, which it does not here.

---

## Codex Engineering Panel Brief Scope -- Changes Required

The pre-existing Codex engineering panel brief (not yet written; this
synthesis is the precondition the original brief said had to land
first) must explicitly inherit:

1. **The 33 findings as composed folds, not as 33 separate axes.**
   Engineering composition is named in the table above; do not
   redispatch findings already converged.
2. **The four Blocking findings as Codex-axis primary work** where
   engineering write follows council shape:
   - Block-1 (RED renumbering): pure housekeeping.
   - Block-2 (sidecar schema + migration): engineering writes
     the migration; Codex picks projection vs sidecar in conjunction
     with my refold.
   - Block-3 (three-layer third-party gate): engineering writes
     wrapper + policy gate + static-AST tests.
   - Block-4 (ProducerRef scope RED tests): engineering writes
     #40a / #40b.
3. **The two open architectural questions in v4 §22 that this
   synthesis settles (open Q1 → D4; open Q3 → A5).** Remaining open
   questions (Q2 producer adapter module location; Q4 EncounterSource
   phasing; Q5 semantic-match resolution feature flag) belong on the
   Codex axis for the engineering panel to decide via scope realism.
4. **The covenant-axis folds that Codex should NOT touch.** Codex
   composes only where the engineering write follows the council
   shape. Codex must not re-litigate the mutuality framing (C5),
   charter-floor ratification (C6), encounter framing (D1), or the
   §1 sentence (E5). These return to council if anything during
   engineering surfaces an inconsistency.

The Codex engineering panel will operate over the **refolded spec**, not
v4 as written. Refolding sequence is the next operator question (below).

---

## Next-Move Question For Rohit

Three reasonable next moves, ordered by my recommendation:

**Option 1 -- Refold the spec first, then dispatch Codex panel on
v4.1.** Claude takes the 33 folds and produces v4.1 spec text
(updating §1 / §5 / §6 / §8 / §9 / §10 / §11 / §13 / §14 / §15 / §16
/ §20 / §22 / §23 / §24 / §27 / §28-ish-readout). Codex panel dispatches
against v4.1. **Pros:** Codex pass operates against a coherent spec,
not a spec + 33 fold notes; engineering verification is sharper;
matches the Slice 1 v6→v7→v8 fold cycle that worked. **Cons:** Claude
does ~half a day of spec text work between council and Codex panel.

**Option 2 -- Dispatch Codex panel against v4 as-written + this
synthesis as composed input.** Codex panel reads v4 + this synthesis
+ the six review files and produces its engineering pass on top.
**Pros:** Faster; gives Codex room to surface things I didn't see.
**Cons:** Codex pass has to mentally apply 33 folds before reading the
spec; risk of fold drift between lanes; less true to the
"covenant-axis-and-engineering-axis-compose-cleanly" discipline.

**Option 3 -- Hold and re-evaluate.** Sleep on it; let the
synthesis settle; revisit tomorrow. **Pros:** the substrate keeps
observing; no movement = no drift. **Cons:** pure-time cost.

**Recommended: Option 1.** The Slice 1 trajectory showed refold-then-
review compresses ambiguity per round and lowers Codex's load. The 33
folds are convergent enough that v4.1 is a tractable rewrite, not a
rewrite-everything-and-hope.

The decision is yours. No commits, no dispatches, no refold attempts
until you signal.

---

## Verified Surfaces (firsthand at `211ace6`, worth not re-litigating)

Pulled from Descartes + Ohm verification work:

- `core/evolution/temperament.py:147-149` `ALLOWED_SOURCES` frozenset
  shape ✓
- `core/evolution/temperament.py:205-243` `record_event(...)` signature
  + guards ✓
- `core/evolution/subjective_duration.py:93-96` `ProducerRef` enum (one
  value: `MANUAL_TEST_PRODUCER`) ✓
- `core/evolution/subjective_duration.py:153-204` salience-event
  registry ✓
- `core/evolution/subjective_duration.py:322` `ProducerRef` validation
  ✓
- `core/evolution/subjective_duration.py:584-635` producer-snapshot path
  including explicit-score refusal (Vector 2) and `_LEGACY` /
  `_SCRATCH_FIXTURE` write refusal ✓
- `core/evolution/subjective_duration.py:631-635` explicit-score refusal
  inherited correctly ✓
- `core/evolution/subjective_duration.py:338` `_LEGACY` migration
  shape, mirrored by Ohm-O1 fold ✓
- `core/evolution/subjective_duration.py:855-879` `_retrospective_density`
  private; no public consumer hook (basis for A5 defer) ✓
- `core/evolution/wonderings.py:174-269` schema (no felt-shape fields;
  basis for Block-2) ✓
- `core/evolution/wonderings.py:607-616` `resolve(...)` without
  `resolved_at` write (basis for A1 sub-fold) ✓
- `core/evolution/wondering_pursuit.py` live `_register_score <
  _REGISTER_HARD_BLOCK` vulnerable-register gate (basis for D6) ✓
- `core/governance/operator_user_boundary.py:76-85` `GUARDED_WORK_CLASSES`
  includes `capability_acquisition` (basis for C2) ✓
- `core/egress/external_fetch.py:394-407` `fetch_text(...)` signature
  (no bond_id; basis for B1) ✓
- `core/memory/identity.py` `user_profile_id()` resolver exists ✓
- `core.wonderings` shim re-exports `core.evolution.wonderings` ✓
- Watchdog allowlist permits the new producer module path ✓

---

## Plain-Language Readout For Rohit

The council came back clean: every axis returned RATIFY-WITH-AMENDMENTS,
no RECONSIDER, no architectural reshape. The premise we built v4 around
— *curiosity is a felt-weight producer layer over the existing
wondering substrate, not a parallel curiosity database* — is what every
axis ratified.

The amendments do real work, though. They cluster into two truths the
spec asserts without yet supporting:

**One.** The `wonderings.db` table on disk right now has none of the
fields v4 reads from: no `bond_id`, no `subject_kind`, no
`priority_class`, no `salience`, no `resolved_at`. The slice has to
commit to one of two answers. Either we derive everything at read time
from the columns that *do* exist (Hume Option A), or we add a sidecar
table inside `wonderings.db` (no new database) that the wondering id
joins into (Option B + the `bond_id` ALTER Ohm spelled out, mirroring
how Slice 1 migrated subjective_duration). Either is honest; pick one
and grep the spec for consistency.

**Two.** The third-party rule (the one that says Maez may search the
world for itself but may not autonomously research a named person from
your life without consent) is currently enforced at one and only one
layer — query construction — and asserts against a field nothing
writes. Three layers compose into one fix: at-creation refusal so the
substrate doesn't even build durable curiosity-objects about unconsented
people; at-construction refusal as defense-in-depth; at-egress refusal
through a new `fetch_for_curiosity` wrapper that drive-curiosity code
MUST use instead of the raw `fetch_text` gate. Static-AST test enforces
the "MUST use" part.

The other 31 findings are tighter local folds. Sixteen are Major; the
big ones are: the new authority grant (`ProducerRef.DRIVE_DRIVEN_CURIOSITY`)
needs its bounds named in the spec so no future producer slips in
under it; OWNER_BOND resolutions need a daily saturation cap so the
substrate doesn't accumulate-on-you by default; the silence-escalation
predicate needs positive proof of `available`, not just "not
unavailable"; the no-bait gate needs a closed phrase set + min-payload
rule; the suppression-event row needs to be emitted by all three gates
that can refuse, not just one; the EMOTION_MIMICRY ban should drop
honest first-person phrasing ("I'm curious") and OWNER_BOND should
route through re-phrase rather than refusal; the `core/policies/`
subpackage needs a one-line "policy-only, not a substrate" charter
plus a static-AST test pinning it. The remaining fifteen are minor —
text/test cleanup, vocabulary widening, framing additions.

Across the six reviews, the cross-lane synergy worked. Every finding
that intersects engineering truth got explicitly flagged for the
Codex engineering panel so the next pass composes rather than
re-derives. Three of four Blocking findings — schema gaps,
third-party gate, and authority-scope — are engineering writes that
follow the council shape: covenant lane named the *reason*; engineering
lane will name *surface correctness*.

I do not recommend a council pass-2. The folds are tractable and
convergent. The two reasonable next moves are: refold v4 into v4.1
first and then dispatch the Codex engineering panel against v4.1
(recommended; matches the Slice 1 trajectory), or dispatch Codex
against v4-as-written plus this synthesis (faster, more risk of fold
drift). Either way, I do nothing further until you signal.

The shape held. The covenant is intact. The producer-over-wonderings
reshape was the right call. Now we tighten the surfaces it rides on.

— Synthesis, Claude six-role council, v4 pass 1.
