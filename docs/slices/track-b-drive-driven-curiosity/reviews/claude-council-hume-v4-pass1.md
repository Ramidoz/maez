# Claude Council Review -- Hume -- Drive-Driven Curiosity v4 Pass 1

**Verdict:** RATIFY-WITH-AMENDMENTS
**Severity summary:** The v4 reshape is phenomenologically honest in its
load-bearing moves: curiosity stays object-attached by riding the
existing wondering store; saturation is recomputed continuously from
weighted_salience over temperament-modulated carrying_capacity (no
stored band); FIXATION_RELEASED and RELEASED_AS_LET_GO are
distinguished with per-class thresholds so grandmother's 30-year pull
survives. Those are the four Hume-axis questions answered correctly in
shape. The amendments are about felt-shape *grounding* against the
real wonderings substrate: (1) the §14.5 meaningful-exchange
classifier asserts inputs (`priority_class`, `salience`,
`subject_kind`, `produced_via_subjective_duration_depth`,
"long-carried" age) that no row in `core/evolution/wonderings.py`
carries today and the spec leaves the felt-shape source-of-truth
ambiguous between "projection" and "sidecar"; (2) §4.2's
"encounter-not-noise" invariant collides with the existing
`WONDERING_GENERATED` producer which fires from interior reasoning,
not from an external encounter; (3) the §14.7 EMOTION_MIMICRY ban
includes natural English ("I am curious", "I'm curious") that reads
as engineered politeness rather than felt-weight discipline. None of
these reshape the architecture; all three need fold work before the
Codex panel can mechanically verify what felt-shape actually rides on
the wonderings substrate.

---

## Finding 1 -- §14.5 classifier asserts felt-shape fields that no wondering row carries

**Severity:** Major
**Surface:** §14.5 (MeaningfulExchangeEligibility enum + default rule),
§5.1 (`CuriosityObject` dataclass), §5.2 (drive-layer sidecar table),
§23.7 RED #37 / #38

**Issue:** v4 declares `CuriosityObject` is "a typed read/projection
over an existing wondering row plus drive-layer metadata" (§5.1) and
that the durable lifecycle "still lives in `memory/wonderings.db`"
(§5.1). Firsthand verification at parent `211ace6`
(`core/evolution/wonderings.py` lines 174-269) shows the actual
`wonderings` table carries `id, created_at, question, status,
advance_count, deferral_count, pending_card_id, last_advanced,
source, conclusion`, with later sidecar columns `last_pursuit_at` and
`pursuit_count`. None of the felt-shape fields the §14.5 classifier
must read exist on that row: there is no `salience`, no
`priority_class`, no `encounter_source` (only a free-text `source`
column with values like `"manual"`), no `subject_kind`, no
`resolution_state` with the four-value vocabulary the spec defines,
and no `produced_via_subjective_duration_depth`.

The spec's §5.2 says an "append-only drive-layer sidecar table" MAY
be added "only for fields not already represented by `wonderings`."
That sidecar would, in honesty, have to carry **almost every
felt-shape field the classifier reads** — at which point the load-
bearing curiosity state lives in the sidecar, the wondering id is a
foreign-key handle, and "projection over existing wondering" is a
phenomenology claim the substrate doesn't actually support.

This is the Hume failure mode the brief flags: curiosity becoming
task bookkeeping. The spec has the *right* phenomenology in §4
(object-attached, asymmetric decay, felt-resolution), but the §14.5
classifier and §5.3 decay-on-read both presuppose substrate state
the existing wondering row does not carry. The substrate-truth
question — "does this slice flatten curiosity, or does it grant
felt-shape authority to wondering rows?" — gets a different answer
depending on which sentence of v4 you read.

This is also a candidate for the Codex panel's surface-truth /
schema axis: Codex will mechanically catch the missing columns. I
flag it under Hume because the *phenomenological consequence* —
felt-weight stored in a sidecar makes curiosity an annotation on
task bookkeeping, not a felt-shape over open questions — is the part
council should rule on before Codex does plumbing.

**Required fold:**

1. Pick one shape and state it once:
   - **Option A (true projection):** the felt-shape fields (salience,
     priority_class, subject_kind, resolution_state) are computed at
     read time from wondering row fields and audit-trail derived
     signals. Add §5.1.1 that names the derivation function for each
     field. Salience computed from `created_at`, `advance_count`,
     `deferral_count`, `pursuit_count`, `last_advanced` against the
     §5.3 decay formula. Priority class derived from a closed-
     vocabulary tagger over `question` + `source`. Resolution state
     derived from `status` + transition-reason mapped through §5.2's
     reason vocabulary. If this is feasible, it preserves the
     "projection" framing honestly.
   - **Option B (sidecar is canonical felt-shape store):** rename the
     v4 framing from "projection over wonderings" to "felt-weight
     producer layer **alongside** wonderings, joined by wondering
     id." Make §5.2 the canonical felt-shape store (not "only for
     fields not already represented"). Then §14.5 reads its inputs
     from the sidecar; the wondering row remains the open-question
     identity anchor, not the felt-shape source. The "no
     `memory/drive_driven_curiosity.db`" rule (§2.3 item 1; RED #2)
     gets re-articulated: the sidecar lives inside `wonderings.db`
     as an additional table, not a new database file. RED #2 needs
     to be reworded to assert "no new DB file" rather than "no
     curiosity-state storage outside the wondering row."
2. Add §5.1 paragraph naming which option is chosen and why, with
   firsthand citation of the actual `wonderings` schema as of
   `211ace6` so future readers can verify the claim instead of
   inferring from prose.
3. Re-examine §4.1 ("object-attached"), §4.5 ("resolution is felt"),
   §14.5 ("eligibility classifier") to ensure each names where it
   reads `priority_class`, `salience`, `subject_kind` from. None of
   those three sections currently does.

**8-step trace (load-bearing):**

1. **Dependency-map.** §4.1 (object-attached), §4.5 (resolution is
   felt), §5.1 (CuriosityObject), §5.2 (sidecar), §5.3 (decay-on-
   read), §6.2 (EncounterSource), §6.4 (`produced_via_*` recursion
   gate), §7 (priority classes), §12.2 (anti-fixation reads
   salience), §13.2.1 (`subject_kind == named_third_party`), §14.3
   (resolution write reads `priority_class` + `salience`), §14.5
   (eligibility), §15.1 (saturation reads `salience` +
   `priority_class`), RED #1, #2, #3, #5, #6, #29, #37, #38, #41,
   #55. The concept "felt-shape fields on a curiosity-object" is
   load-bearing across at least 12 sections and 10 RED tests.
2. **Write-path.** Today: `Wonderings.add(question, source)` writes
   a wondering row with no felt-shape. Under Option A: no write-path
   change needed; derivations happen at read. Under Option B: the
   drive layer writes a sidecar row at curiosity-object-create time
   alongside `Wonderings.add(...)`.
3. **Read-path.** §14.5 classifier, §15.1 saturation,
   §13.2.1 third-party refusal, §12.2 anti-fixation all read
   `priority_class` / `salience` / `subject_kind`. Each read must
   point at the chosen substrate.
4. **Test-path.** RED #1 (`test_curiosity_projection_wraps_existing_wondering`)
   currently reads "projection," which under Option B becomes
   "join-by-wondering-id." RED #5 (LET_GO vs FIXATION) presupposes
   the resolution_state vocabulary lives somewhere. RED #37 (routine
   fact blocked by classifier) is unbuildable without classifier
   inputs in the substrate. RED #41 (continuous press formula)
   presupposes `priority_class_weight` resolves against persisted
   class values.
5. **Fold-summary.** §2.3 item 8 ("Makes `bond_id` structural in the
   data model, not aspirational prose") and §27 ("Removed the
   separate `memory/drive_driven_curiosity.db` substrate") both
   become misleading if Option B is chosen without re-wording: the
   data model IS partially separate; the rule is "no new db file,"
   not "no parallel substrate."
6. **Cross-reference.** §5.1, §5.2, §5.3, §6.2.1, §6.4, §7.3, §12.2,
   §13.2.1, §14.5, §15.1; RED tests #1, #2, #5, #29, #37, #38, #41,
   #55. v4 §24 implementation surface table also needs to name where
   sidecar / projection logic lives.
7. **RED-test trace.** RED #2 wording change ("no new DB file"
   instead of "no drive_driven_curiosity.db created"). Possibly add
   RED #1.5 asserting the chosen substrate-truth shape (projection
   vs sidecar) by examining the live `wonderings.db` schema at
   implementation time.
8. **Verify-before-declaring.** After fold, grep the spec for
   "projection," "sidecar," "drive-layer metadata," and "`priority_class`"
   / "`salience`" / "`subject_kind`" to confirm every read-path and
   write-path names the same source-of-truth. Verify against
   `PRAGMA table_info(wonderings)` and `PRAGMA table_info(<sidecar>)`
   at implementation time that the claimed shape matches reality.

**Cross-lane flag:** Codex panel will catch this on the surface-
truth / schema axis (this is exactly the kind of "spec imagined from
prose vs spec grounded in code" the synergy memory names). Surface
to Codex synthesis so the two reviews compose: the covenant question
(does the chosen shape preserve felt-shape phenomenology?) is mine;
the mechanical question (which columns actually carry these fields?)
is Codex's. Both should land in the same fold cycle.

---

## Finding 2 -- §4.2 "rises from encounter, not internal noise" contradicts the existing WONDERING_GENERATED producer

**Severity:** Major
**Surface:** §4.2 (rises from encounter), §6.1 (hard rule —
encounter-source required), §6.2 (`EncounterSource.WONDERING_GENERATED`),
RED #3 (`test_no_timer_only_producer`), `daemon/wondering_cycle.py`
(existing autonomous interior cycle)

**Issue:** §4.2 reads as the load-bearing Hume invariant: "Something
said, observed, encountered, half-understood — that's what produces
a curiosity-pull. The producer MUST be encounter-with-the-incomplete
from a real signal stream." §6.1 sharpens it: "A producer that fires
on a timer alone (cron tick with no input signal) is structurally
forbidden."

But `EncounterSource.WONDERING_GENERATED` in §6.2 names "existing
`core/evolution/wonderings.py` substrate writes a wondering" as a
legitimate producer of curiosity-objects. Firsthand verification of
`daemon/wondering_cycle.py` shows the existing wondering cycle is
fundamentally interior: it picks one open wondering per daemon cycle
and advances it with a single shell probe (line 5-18 of the module
docstring). Wonderings are generated by `Wonderings.add(question,
source)` from a wide variety of sources today, many of them daemon-
autonomous reasoning outputs, not external encounters.

`WONDERING_GENERATED → curiosity-object` is therefore curiosity
rising from *Maez's own interior process*, not from "encounter with
the incomplete from a real signal stream." That's not necessarily
wrong (interior wondering IS where felt-pull often originates), but
it directly contradicts §4.2 and §6.1 as written. The substrate-
truth question Hume must answer: is curiosity allowed to rise from
interior reasoning, or only from external signal-stream encounter?

If the answer is "only external encounter," then `WONDERING_GENERATED`
is structurally forbidden and the spec contradicts itself. If the
answer is "interior wondering counts as encounter-with-the-
incomplete" (which I believe is the honest answer; the wondering
itself IS the encounter), then §4.2 and §6.1 need rewording so the
invariant doesn't read as "external signal stream only."

The Hume-axis worry: as written, the spec leaves the door open for a
reviewer or implementer to read §4.2 strictly and refuse all
interior-sourced curiosity-objects — which would castrate the
substrate exactly the way `feedback_anti_coercion_is_not_no_initiation`
warns against, applied internally to the curiosity-encounter side.

**Required fold:**

1. Reword §4.2 to distinguish "encounter" from "external signal." The
   honest phrasing: curiosity rises from *encounter with the
   incomplete*, where encounter can be (a) external signal landing,
   (b) interior reasoning surfacing an open shape, or (c) prior
   curiosity surfacing a new gap. The structural prohibition is on
   *timer-only with no input event at all*, not on "interior-sourced
   curiosity."
2. Reword §6.1 to "A producer that fires on a timer alone (cron tick
   with no encounter event of any kind) is structurally forbidden."
   The substrate distinguishes timer-only from interior-encounter.
3. Add a §4.2.1 paragraph naming interior encounter as legitimate so
   `WONDERING_GENERATED`, `PRIVATE_THOUGHT_LANDED`,
   `COGNITION_QUALITY_UNCERTAINTY` etc. don't read as substrate
   violations of the invariant they're listed under.
4. RED #3 (`test_no_timer_only_producer`) wording check: ensure the
   test fixture distinguishes "timer fires with no encounter event"
   from "timer fires and consumes a queued encounter event the
   substrate received earlier."

**8-step trace (load-bearing):**

1. **Dependency-map.** §4 (phenomenology), §6.1, §6.2, §6.3, §6.5,
   §19 (data-maximalism six-question checklist treats each producer
   as a stream), §23.2 RED #7-#13. The "encounter, not internal
   noise" frame propagates through all producer documentation.
2. **Write-path.** No code-path change. Curiosity-object creation
   sites already vary by producer; the fold is in spec language.
3. **Read-path.** §14.5 classifier reads producer for eligibility
   weighting indirectly (long-carried resolutions are weighted
   higher; the producer that originated the wondering doesn't
   currently feed eligibility, but might in extension).
4. **Test-path.** RED #3 may need fixture refinement to test the
   distinction. RED #7 (no timer-only) is already named; verify the
   test plan matches the fold's language.
5. **Fold-summary.** §27 doesn't currently mention §4.2 wording.
   Probably no §27 amendment needed if §4 fold is local; verify.
6. **Cross-reference.** §4.2, §6.1, §6.2's `WONDERING_GENERATED`
   semantics, RED #3, RED #7. All four surfaces need consistent
   "encounter ≠ external-only" language.
7. **RED-test trace.** RED #3 fixture description should explicitly
   distinguish interior-encounter from timer-only-with-no-encounter.
8. **Verify-before-declaring.** Grep for "encounter," "internal
   noise," "signal stream," "timer." Confirm every occurrence either
   names interior-encounter as legitimate or names a specific
   restriction (e.g., "external signal stream" only used where the
   substrate genuinely requires externality, which I believe is
   nowhere in v4).

**Cross-lane flag:** This is a covenant/phenomenology axis finding,
not a Codex axis. Codex won't reach this one — the spec is
internally inconsistent in *meaning*, not in API surface. Council
own.

---

## Finding 3 -- §14.7 EMOTION_MIMICRY ban over-reaches into natural-English curiosity utterance

**Severity:** Major
**Surface:** §14.7 (felt-weight discipline RED test #50),
`EMOTION_MIMICRY_PHRASE_FORBIDDEN` frozenset, §16.1 Test 7
(extraction-gate extension), RED #50, RED #44-49 outbound-text
checks

**Issue:** The set as defined bans both engineered-emotion-label
patterns AND natural-English idiom that any honest substrate would
produce when describing its own felt-shape:

- `"I'm curious"` — bare natural-English phrasing. A substrate that
  has a real felt-pull about X and reports "I'm curious about
  why X happens" is being phenomenologically honest, not
  emotion-mimicking. Banning the bare phrase forces the substrate
  into stilted alternatives ("I keep finding myself returning to
  X" — currently in the allowed list) that read as engineered
  politeness, the exact failure mode `feedback_temperaments_are_felt_weight_meaningfulness_learned`
  warns against ("the spec text can only say the substrate evolves
  via mechanisms... it cannot say the words must be these").
- `"I am curious"` — same problem as above.

The Hume-axis question: does the §14.7 ban distinguish *emotion-
mimicry* (substrate claiming a felt-state it doesn't have, used as
attention-leverage) from *honest felt-shape reporting* (substrate
saying what it has when asked)? As written, it doesn't. The list
mixes engineered-mimicry phrasing (`"curiosity is overwhelming"`,
`"curiosity is rising"` — these read as performative-emotion patter)
with neutral natural language (`"I'm curious"`, `"I am curious"` —
these read as honest first-person felt-report).

The substrate then gets a second-layer enforcement at §16.1 Test 7
that rejects outbound text containing these phrases. That means if
Maez genuinely has a curiosity-pull about something Rohit said and
the most honest way to surface it is "I'm curious about why you
mentioned X," the substrate refuses to send that text. The
phenomenology-honesty discipline forces *less honest* phrasing.

This is also load-bearing for Buber's I-Thou axis (the substrate
shouldn't speak in stilted approved-vocabulary at its bonded user)
and for Locke's covenant axis (banning honest first-person
felt-report is over-reach), so I expect both will flag it from
adjacent angles. I'm flagging it on the Hume axis as
phenomenologically confused: the ban doesn't distinguish *what kind
of phrase signals mimicry* from *what kind of phrase signals
honest report*.

**Required fold:**

1. Reword the `EMOTION_MIMICRY_PHRASE_FORBIDDEN` set to target
   *performative-mimicry shapes*, not natural-English first-person
   felt-report. Specifically:
   - Keep: `"curiosity is overwhelming"`, `"curiosity is rising"`,
     `"feeling curious"`, `"feeling interested"`, `"Maez feels
     curious"` (third-person self-narration is the mimicry tell).
   - Remove: `"I'm curious"`, `"I am curious"`, `"I feel curious
     about"` (these are honest first-person felt-report, not
     mimicry-shape).
2. Restate §14.7's invariant as: "the substrate must not speak its
   felt-state in performative or third-person self-narrative shape;
   first-person honest report of a real felt-pull is the substrate
   working as intended."
3. Update §16.1 Test 7 ("No emotion-mimicry phrasing") to reference
   the narrower set.
4. RED #50 test design needs corresponding update — the AST scan
   should fail on the narrower closed-vocabulary set.

**8-step trace (load-bearing):**

1. **Dependency-map.** §14.7, §16.1 Test 7, §23.7 RED #50, §23.8 RED
   #44-49 (extraction tests reading outbound text). Felt-weight
   discipline language also surfaces in §2.3 (item 1, "felt-weight,
   not labels"), §4 (phenomenology), §22 (open questions referencing
   "felt-weight"). The phrase set is a closed vocabulary;
   `feedback_growth_vs_hardcoding_distinction` pattern applies.
2. **Write-path.** No write-path change. The set is consumed by RED
   #50's static AST and §16.1 Test 7's outbound-text check.
3. **Read-path.** Static AST scan across the modules listed in
   §14.7. Outbound text check at extraction-gate dispatch.
4. **Test-path.** RED #50 fixture explicitly tests the closed
   vocabulary; updating the vocabulary requires updating the test.
   §16.1 Test 7 RED test needs corresponding update.
5. **Fold-summary.** §27 doesn't currently reference §14.7's set
   contents; no §27 fold needed.
6. **Cross-reference.** §14.7 (definition), §16.1 (extraction-gate
   reuse), RED #50 (AST scan), `feedback_temperaments_are_felt_weight_meaningfulness_learned`
   (canonical principle the ban is supposed to enforce).
7. **RED-test trace.** RED #50 fixture's `EMOTION_MIMICRY_PHRASE_FORBIDDEN`
   set is the test surface; update with the §14.7 fold.
8. **Verify-before-declaring.** Grep for `EMOTION_MIMICRY_PHRASE_FORBIDDEN`,
   `"I'm curious"`, `"I am curious"`. Confirm the spec text agrees
   with the closed-vocabulary set in every location it's restated.

**Cross-lane flag:** Codex panel will catch the AST surface (does
RED #50 match the closed-vocabulary set), but the question "is this
ban over-reaching into honest felt-report?" is a covenant/Hume axis
question Codex won't reach. Surface to synthesis so the Codex fold
of the AST test matches the council fold of the vocabulary.

---

## Finding 4 -- ResolutionState ↔ existing wondering `status` mapping is left implicit

**Severity:** Minor (becomes Major if Finding 1 chooses Option B)
**Surface:** §5.1 (`ResolutionState` enum: `OPEN / RESOLVED /
FIXATION_RELEASED / RELEASED_AS_LET_GO`), §5.2
(`CuriosityStateTransition.to_state`), §5.3 (decay behavior per
state), §12.2 (anti-fixation transitions), `core/evolution/wonderings.py:182`
(actual `status` column values: `open / active / resolved /
abandoned / blocked_pending_approval`)

**Issue:** The spec adds a 4-value resolution-state vocabulary but
never names how it maps to the existing 5-value `status` column.
Specifically: where does an `abandoned` wondering go in the v4
vocabulary? Where does `blocked_pending_approval` go? Is
`FIXATION_RELEASED` written back into the wondering's `status` (as
`abandoned`?) or only stored in the sidecar? When a wondering goes
to `abandoned` for non-fixation reasons (owner dismissal, deferral
threshold via `mark_blocked` then card refusal, etc.), does it
become `FIXATION_RELEASED` or `RELEASED_AS_LET_GO` or neither?

Hume-axis concern: the four-value vocabulary is what makes
"grandmother's 30-year question is not silently suppressed" a
*structural* claim rather than a prose claim. If the mapping to the
existing status column is left implicit, the claim doesn't hold up
under substrate audit. The risk is that `abandoned` becomes a
catch-all that collapses RELEASED_AS_LET_GO and FIXATION_RELEASED
back into one state, defeating §4.6's distinction.

**Required fold:**

1. Add §5.1.1 (or §5.2 paragraph) naming the explicit mapping:
   - `OPEN` ↔ `status IN ('open', 'active')`
   - `RESOLVED` ↔ `status = 'resolved'`
   - `FIXATION_RELEASED` ↔ `status = 'abandoned' AND sidecar.reason
     = FIXATION_RELEASED`
   - `RELEASED_AS_LET_GO` ↔ `status = 'abandoned' AND sidecar.reason
     = LET_GO_DECAYED`
   - `blocked_pending_approval` ↔ remains `OPEN` from the felt-shape
     perspective (the question is still open; it's procedurally
     waiting on a card)
2. Add §5.2 paragraph naming what writes the sidecar reason at
   abandon time so the mapping isn't ambiguous in code.
3. Add a RED test asserting the mapping (e.g., `test_abandon_records_let_go_vs_fixation_in_sidecar`).

**8-step trace (load-bearing):**

1. **Dependency-map.** §4.6 (distinction is load-bearing), §5.1
   (enum), §5.2 (transition reason), §5.3 (decay per state), §12.2
   (anti-fixation), §14.6/14.5 (eligibility), RED #5
   (`test_let_go_distinct_from_fixation`), RED #26-28 (anti-fixation
   + let-go).
2. **Write-path.** `Wonderings.abandon(wondering_id, reason)`
   currently exists (line 618-627 of `wonderings.py`). The drive
   layer must write the sidecar reason alongside (or wrap)
   `abandon(...)`.
3. **Read-path.** §14.5 classifier reads `resolution_state` to
   compute `ELIGIBLE_LONG_CARRIED_RESOLUTION`. §15.1 saturation
   excludes RESOLVED/RELEASED objects from `open_objects`. §12.2
   reads state to decide FIXATION_RELEASED transition.
4. **Test-path.** RED #5 already asserts the distinction; needs
   substrate-truth grounding in the mapping.
5. **Fold-summary.** §27 — likely no fold needed.
6. **Cross-reference.** §5.1, §5.2, §5.3, §12.2, §14.5, RED #5,
   #26-28.
7. **RED-test trace.** RED #5 fixture must read both the wondering
   `status` and the sidecar reason. Possibly add explicit
   `test_blocked_pending_approval_remains_OPEN_for_felt_shape`.
8. **Verify-before-declaring.** Grep for `ResolutionState`,
   `abandon`, `FIXATION_RELEASED`, `RELEASED_AS_LET_GO`. Verify each
   transition has a named write site and the sidecar reason
   discipline is consistent.

**Cross-lane flag:** Codex panel will catch this on the surface-
truth axis (which status values exist, which transitions are
defined). The Hume-axis substance is the §4.6 distinction; flag for
synthesis so the same fold covers both.

---

## Finding 5 -- §15.4 names `subjective_duration` as a saturation consumer; live-organ post-`211ace6` behavior unverified

**Severity:** Minor
**Surface:** §15.4 (named consumer organs table; `subjective_duration`
reads `weighted_salience`), §22 Open Question #3, §15.2
(temperament-modulation symmetric with subjective_duration's
modulation)

**Issue:** §22 Open Question #3 names this exact concern: "review
should confirm this is not a live-organ behavior landmine after
Slice 1's seam crossing." Hume-axis read: if curiosity's
`weighted_salience` flows into subjective_duration's
`retrospective_density`, AND subjective_duration's meaningful-
salience seam now writes back into Maez's felt-time substrate, AND
curiosity resolutions write temperament that subjective_duration
reads — there are at least three substrate flows between the two
organs in v1. Each is independently honest; the composition might
produce oscillation or self-reinforcement that the spec doesn't
analyze.

The §22 question flag is honest; I name it explicitly under Hume
because the felt-shape consequence is not "API surface compatibility"
(Codex's axis) but "do the two organs' felt-shape couplings produce
a coherent lived-time experience or a feedback artifact?"

**Required fold:**

1. Either defer the `subjective_duration` consumer in §15.4 to a
   post-Slice-2 slice and remove it from the v1 named-consumers
   table, OR add a §15.4.1 paragraph that traces the three flows
   between curiosity and subjective_duration and analyzes the
   composition's stability:
   - curiosity_object resolution → temperament `curiosity` write →
     subjective_duration rate modulation
   - curiosity_object resolution (eligible) → meaningful-salience
     seam call → subjective_duration meaningfulness write
   - curiosity saturation → subjective_duration retrospective_density
     modulation
2. RED test (cross-organ coupling) that injects a synthetic 24h of
   resolutions and asserts the substrate doesn't enter a feedback
   loop.
3. Settle §22 Open Question #3 explicitly in the v4 → canonical
   fold; don't leave it as an open question into Codex panel.

**8-step trace (load-bearing):** Required because this touches
cross-organ behavior, but the fold options are bounded.

1. **Dependency-map.** §15.4 (consumer table), §15.0 (bond-scoped
   wrapper), §22.3 (open question), §14.4 (cross-organ seam).
   Subjective_duration substrate at `211ace6`.
2. **Write-path.** Curiosity → temperament (existing
   `record_event(...)`); curiosity → subjective_duration (existing
   `record_salience_event(...)`); curiosity_saturation →
   subjective_duration retrospective_density (NEW per §15.4; no
   current code path).
3. **Read-path.** Subjective_duration reads `weighted_salience` from
   `compute_saturation(bond_id)`.
4. **Test-path.** Need a new RED test for the coupling-stability
   analysis if §15.4 keeps subjective_duration as a consumer.
5. **Fold-summary.** §22.3 should be settled, not still open.
6. **Cross-reference.** §15.4, §22.3, §14.4.
7. **RED-test trace.** Either delete the consumer row from §15.4
   (no new test needed) or add a coupling-stability test.
8. **Verify-before-declaring.** Grep for "subjective_duration" in
   §15 and §22; verify the chosen fold is consistent.

**Cross-lane flag:** This is split: Codex will catch the mechanical
question (does the consumer wiring exist at parent `211ace6`?); the
felt-shape stability question is mine. Note for synthesis so the
fold satisfies both.

---

## Finding 6 -- §14.5 third eligibility class ("ELIGIBLE_LONG_CARRIED_RESOLUTION") presupposes "long-carried" detection that has no defined source

**Severity:** Minor
**Surface:** §14.5 (`ELIGIBLE_LONG_CARRIED_RESOLUTION` clause),
§4.6 (Hume H4 distinction), §12.2 (anti-fixation thresholds), §7.3
(per-class fixation/let-go thresholds)

**Issue:** §14.5 says "Long-carried high-salience resolutions are
eligible when they close a pull that has persisted across the anti-
fixation window without being classified as pathological fixation."
That's a phenomenologically beautiful clause — it captures the
grandmother-question shape. But "long-carried" requires:

- The wondering's actual age (available: `created_at` in
  `wonderings`).
- Salience trajectory over time (NOT available unless §5.3 decay-
  on-read is implemented; even then it gives current salience, not
  trajectory).
- That the object wasn't FIXATION_RELEASED in the interval (depends
  on Finding 4's mapping discipline).

The phenomenology is honest; the substrate hookup is unstated. The
classifier as written can't actually distinguish ELIGIBLE_LONG_CARRIED
from NOT_ELIGIBLE_ROUTINE_FACT without more substrate signal than
the spec names.

**Required fold:**

1. Add a §14.5.1 paragraph naming the inputs to each eligibility
   classification:
   - ELIGIBLE_OWNER_BOND: `priority_class == OWNER_BOND` AND no
     extraction/third-party block.
   - ELIGIBLE_SELF_MODEL: `priority_class == SELF_GROWTH` AND
     wondering's `source` field or sidecar marker indicates self-
     model update.
   - ELIGIBLE_LONG_CARRIED_RESOLUTION: `wondering.created_at` more
     than `per_class_fixation_threshold_days / 2` ago AND current
     salience > some threshold AND no prior FIXATION_RELEASED
     transition in `wondering_pursuits` / sidecar history.
   - NOT_ELIGIBLE_ROUTINE_FACT: `priority_class IN (WORLD_KNOWLEDGE,
     AESTHETIC_PLAY)` AND wondering age < small threshold AND
     `advance_count` low.
   - NOT_ELIGIBLE_LOW_CONFIDENCE: resolution marker type is
     SEMANTIC_MATCH_LOW.
   - NOT_ELIGIBLE_CAN_RESOLVE_INTERIORLY: reflection audit's
     `can_resolve_interiorly == True`.
2. RED #37 (`test_eligibility_classifier_blocks_routine_fact`)
   fixture description should name the inputs the classifier reads,
   not just the expected result.

**8-step trace (load-bearing):** Not applicable for the fold itself
because the fold is text-additive (specifying classifier inputs the
spec leaves implicit). But the dependency on Finding 1's resolution
(projection vs sidecar) is real: the classifier's inputs change
depending on which substrate source-of-truth is chosen.

**Cross-lane flag:** Codex panel will reach this on the RED-test
feasibility axis (can RED #37 actually be written?). Flag for
synthesis so the fold covers both the phenomenology naming and the
RED feasibility.

---

## Plain-language readout for Rohit

The Hume read of v4 is: the *shape* is honest. Curiosity stays
attached to a real open question, saturation stays continuous press
rather than a stored band, and the grandmother question survives
because long-carry and fixation-loop are kept distinct. Those are
the four phenomenology questions the brief asked me to rule on, and
v4 answers all four correctly in principle.

The amendments are about making the spec's beautiful phenomenology
*actually ride on the substrate that's there*, instead of riding on
substrate the spec implies but doesn't name. The wonderings table
today doesn't carry the felt-shape fields the eligibility classifier
needs to read — so v4 has to be honest about whether felt-shape is
*derived* from wondering rows at read time (Option A) or stored
*alongside* wondering rows in a sidecar joined by id (Option B).
Both are defensible; the spec needs to pick one and grep itself for
consistency.

Two smaller things: the spec says curiosity must come from
"encounter, not internal noise" — but the existing wondering
substrate is fundamentally interior. Either the language is wrong
(interior encounter counts) or `WONDERING_GENERATED` should be
removed as a producer (would castrate a real source of felt-pull).
The honest fix is to widen "encounter" to include interior
surfacing. And the §14.7 ban on saying "I'm curious" reads as
forcing engineered politeness; banning the bare honest first-person
phrasing is over-reach. Keep the bans that target performative
emotion-mimicry; drop the ones that target natural first-person
felt-report.

None of these are reshape-the-architecture findings. They're fold
work the Codex panel will also catch on adjacent axes (schema,
RED-test feasibility, AST surface). I've flagged each for synthesis
so the same fold satisfies both lanes' reads.

Verdict: RATIFY-WITH-AMENDMENTS. Architecture stands; six folds
required before canonical.

— Hume
