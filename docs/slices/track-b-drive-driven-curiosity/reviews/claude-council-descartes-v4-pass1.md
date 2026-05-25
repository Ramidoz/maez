# Claude Council Review -- Descartes -- Drive-Driven Curiosity v4 Pass 1

**Verdict:** RATIFY-WITH-AMENDMENTS

**Severity summary:** The v4 producer-layer reshape is mechanically
plausible against real substrate. `Temperament.record_event(...)` API,
`ALLOWED_SOURCES` frozenset, `SubjectiveDuration.record_salience_event(...)`
producer-snapshot path, `ProducerRef` enum, watchdog allowlist, and
`identity.user_profile_id()` all match v4's claims when checked against
parent `211ace6`. The seam-is-dependency stance is correct: Slice 1's
explicit-score refusal already lives in the live code path
(`subjective_duration.py:631-635`), so v4 inherits RED #40's invariant
honestly. However four real load-bearing problems must fold before Codex
panel: (D-1) the §23 RED-test table is the source of truth, but ~10
internal section citations point at the wrong test numbers, including
RED #2, #6, #29, #30, #31, #46, #47-48, #54; (D-2) `wonderings` real
schema has no `bond_id`, no `priority_class`, no `salience`, no
`subject_kind`, no `third_party_consent`, no `resolution_marker`, no
`resolved_at` timestamp, no `produced_via_subjective_duration_depth` --
the spec's "projection over an existing wondering row plus drive-layer
metadata" needs a named, mechanically-coherent place for that
drive-layer metadata to live (sidecar table contract is partial);
(D-3) §15.4 names `subjective_duration` as a consumer of saturation
that "Nudges `retrospective_density`" but the live module exposes no
public surface that could be nudged -- §22.3 names this as open but the
spec also names it as v1 in §15.4, contradicting itself; (D-4) RED #3
("timer-only producer rejected") needs a mechanically-checkable
definition because no current code distinguishes a "fake timer-only
producer" from a producer that happens to fire on a cycle tick. Several
minor textual folds round out the list. None of these require
architectural reshape; all are tractable fold-level corrections.

---

## Finding D-1 -- §23 RED-test table is canonical but inline citations diverge from it

**Severity:** Blocking (the spec cannot be implemented test-first when
the spec disagrees with itself about which test proves which property)

**Surface:** §5.1 (cites #2), §6.2.1 (cites #46), §6.4 (cites #47-#48),
§7.5 (cites #6), §10.7 (cites #54), §14.3.3 (cites #29), §14.3.4 (cites
#30), §14.6 (cites #31). Cross-referenced against §23.1-§23.8 table.

**Issue:** The §23 table is the implementation gate (it names actual
pytest paths). When §5.1 says "RED test #2 asserts construction fails
for missing bond_id," but the table at #2 is
`test_no_drive_driven_curiosity_db_created`, a TDD-first implementer
either writes the wrong test or writes the right test under the wrong
filename, and the §23.9 discipline ("tests are written FIRST") is
broken at the seam between spec and gate. Walking the citations against
the table:

- §5.1 says #2 = missing-bond-id refusal. Table #2 = no-new-DB. The
  missing-bond-id test is actually #3 (`test_missing_bond_id_refused`).
- §7.5 says #6 = safety-misclassification blocked. Table #6 =
  `test_wondering_resolution_drives_curiosity_metadata`. The safety
  misclassification test is #8.
- §6.2.1 says #46 = producers fail closed on missing bond_id. Table
  #46 = `test_silence_escalation_composed_with_signal_quality`. There
  is no producer-side bond_id-refusal test in the table; either add one
  (e.g. #3 already covers the producer-layer boundary) or rewrite the
  inline citation.
- §6.4 says "#47-#48 cover both limits" for the recursion gate. Table
  #47 = `test_scope_owner_interrupting_only`, #48 =
  `test_contact_pressure_blocked`. No recursion-depth or recursion-
  dedupe tests appear anywhere in the table.
- §10.7 says #54 = OWNER_OBSERVED excludes suppression windows; table
  #54 = `test_autonomy_policy_for_bond_isolation`. Suppression-
  exclusion is actually #57 in the table.
- §14.3.3 says #29 = pathological-resolution daily-budget cap. Table
  #29 = `test_owner_identifying_tokens_removed`. Daily-budget cap is
  #35.
- §14.3.4 says #30 = first-observation NULL transition. Table #30 =
  `test_unsanitizable_blocks_external`. First-observation NULL is #36.
- §14.6 says #31 = cross-organ seam mechanical truth. Table #31 =
  `test_provenance_tag_required_at_egress`. Cross-organ seam is #38.
- §19 says "RED test #42 asserts the [six-question] checklist." Table
  #42 = `test_temperament_modulates_carrying_capacity`. The six-
  question meta-test is #52.

**Required fold:** Renumber all inline citations to match §23, OR
renumber the §23 table to match prose. Recommend the former (the table
already cross-cuts and renumbering it cascades through the test plan).
Specifically:
- §5.1: "#2" → "#3"
- §6.2.1: "#46" → "#3" (it's the same property) or add a separate
  per-producer test row and renumber.
- §6.4: "#47-#48" → add two new rows under §23.2 for recursion-depth
  + recursion-dedupe and cite their numbers, or drop the recursion gate
  to a follow-up slice with explicit deferral text.
- §7.5: "#6" → "#8"
- §10.7: "#54" → "#57"
- §14.3.3: "#29" → "#35"
- §14.3.4: "#30" → "#36"
- §14.6: "#31" → "#38"
- §19: "#42" → "#52"
- §14.7: §16.1 Test 7 names a "second-layer enforcement" on outbound
  text but cites only #50 (which is the static AST scan over source
  files). Either add a separate `test_outbound_text_emotion_mimicry`
  test row in §23 or expand #50's stated proof to cover both surfaces.

**8-step trace:**
1. **Dependency-map:** §1 charter language, §6.2.1 producer-layer
   floor, §10.7 anti-self-confirmation, §14 temperament-write ceremony,
   §16.1 extraction gates, §19 data-maximalism checklist all depend on
   the test numbering.
2. **Write-path:** N/A (this is a spec-internal coherence problem).
3. **Read-path:** Codex panel reads §23 to write tests RED-first; the
   inline citations are what the covenant council and other slices
   reference. Both must agree.
4. **Test-path:** §23 table itself is the test-path. Inline citations
   are pointers into it.
5. **Fold-summary:** Old citations become false; the §23 table becomes
   the single source of truth.
6. **Cross-reference:** Every "RED test #N" in the spec must be checked
   against §23. Total surface: ~20 citations across §5-§19.
7. **RED-test trace:** Test names in §23 remain the contract; only the
   inline numeric pointers update.
8. **Verify-before-declaring:**
   `grep -nE "RED test #?[0-9]+|test #[0-9]+|#[0-9]+ asserts" spec.md`
   should yield zero divergences from the §23 table.

**Codex overlap flag:** Codex engineering panel will independently
catch this when writing the RED suite. Flag for synthesis composition
not duplication.

---

## Finding D-2 -- "Projection over wonderings + drive-layer metadata" needs a named, schema-coherent metadata surface

**Severity:** Blocking (the producer ceremony in §14.3 cannot run
without somewhere to read `bond_id`, `priority_class`, `salience`,
`subject_kind`, `resolution_marker`, `produced_via_subjective_duration_depth`,
and `third_party_consent_allows_external_research` from)

**Surface:** §5.1 dataclass, §5.2 storage paragraph, §6.4 recursion-
gate fields, §13.2.1 `subject_kind` / `third_party_consent_allows...`
fields, §14.1 resolution markers, §14.5 eligibility classifier inputs.
Verified against `core/evolution/wonderings.py:174-269` (`_init_schema`).

**Issue:** Verified live schema at `211ace6`:

```
sqlite> PRAGMA table_info(wonderings);
0|id|INTEGER
1|created_at|REAL
2|question|TEXT
3|status|TEXT
4|advance_count|INTEGER
5|deferral_count|INTEGER
6|pending_card_id|INTEGER
7|last_advanced|REAL
8|source|TEXT
9|conclusion|TEXT
10|last_pursuit_at|REAL
11|pursuit_count|INTEGER
```

The real `wonderings` row has no `bond_id`, no `priority_class`, no
`salience`, no `subject_kind`, no `third_party_consent_allows_external_research`,
no `resolution_marker`, no `resolved_at` timestamp, no
`encounter_source`, no `encounter_ref_digest`,
no `produced_via_subjective_duration_depth`,
no `autonomy_lane_hints`. Section §5.1's `CuriosityObject` projection
needs every one of these for the rest of the spec to be runnable.

`Wonderings.resolve(wid, conclusion)` (line 607-616) only updates
`status='resolved'` and `conclusion`. It does NOT timestamp resolution,
which §5.3 decay math and §14.2 resolution-marker logic both require.

§5.2 names "an append-only drive-layer sidecar table only for fields
not already represented by `wonderings`, and that sidecar must key back
to the existing wondering id" -- but only defines `CuriosityStateTransition`,
which captures transitions, not the rest-of-life metadata the
projection reads. The implementation cannot project a row that doesn't
exist.

This is NOT a recommendation to create `memory/drive_driven_curiosity.db`
(per brief Out-of-Scope §3). The fix is to commit to an explicit
sidecar schema inside `memory/wonderings.db` (additional tables /
columns) so the projection is mechanically reconstructible. The choice
is reasonable; v4 is just silent on it.

**Required fold:** Either
- Add §5.2.1 ("Drive-layer sidecar table inside `memory/wonderings.db`")
  naming the additional table(s) -- e.g.,
  `wondering_drive_metadata(wondering_id PK, bond_id, encounter_source,
  encounter_ref_digest, priority_class, salience, autonomy_lane_hints,
  subject_kind, third_party_consent_allows_external_research,
  produced_via_subjective_duration_depth, resolution_marker_type,
  resolution_marker_utc)` with append-only / read-latest discipline; OR
- Extend `wonderings` itself via ALTER TABLE (matching the existing
  `last_pursuit_at`/`pursuit_count` migration pattern at lines 221-244)
  for the structurally-mandatory fields (bond_id, priority_class,
  salience, resolved_at), and a sidecar for the multi-row history
  (resolution markers, state transitions, recursion provenance); AND
- Add §5.4 noting `Wonderings.resolve(...)` must gain a
  `resolved_at` timestamp write (a single ALTER TABLE + one UPDATE
  fold). RED test #1 should assert the projection reads each field
  from the named source.

**8-step trace:**
1. **Dependency-map:** §5.1 projection, §5.3 decay math, §6.2.1 bond
   propagation, §6.4 recursion depth field, §7 priority class, §13.2.1
   subject-kind check, §14.1-§14.6 resolution-write ceremony, §15.1
   `compute_saturation` (reads bond_id of open objects), §20 diagnostic
   row digests (per-bond HMAC key derivation needs bond_id), and §23
   tests #1, #3, #4, #5, #6, #38, #55 all depend on the metadata
   surface being real.
2. **Write-path:** Producer (§6) is the writer. Without a defined
   table, "producer writes a curiosity-object" has no target.
3. **Read-path:** `Wonderings.list_open`, `pick_next`, and the proposed
   §13 query builder all need to read these fields.
4. **Test-path:** RED #1
   (`test_curiosity_projection_wraps_existing_wondering`), #3
   (`test_missing_bond_id_refused`), #4 (append-only lifecycle), #6
   (`test_wondering_resolution_drives_curiosity_metadata`) and #38
   (cross-organ seam) all need to bind to real columns.
5. **Fold-summary:** §5.2's "an append-only drive-layer sidecar table
   only for fields not already represented" becomes false-by-omission;
   the new §5.2.1 names the exact contract.
6. **Cross-reference:** §5.1, §5.2, §5.3, §6.2.1, §6.4, §13.2.1, §14.1,
   §14.3.4, §20.3, §23 RED #1/#3/#4/#5/#6/#38/#55.
7. **RED-test trace:** Add `test_drive_metadata_sidecar_schema_present`
   to §23.1 (asserts PRAGMA on the named sidecar table matches the
   spec). Strengthen #1 to bind to the real columns.
8. **Verify-before-declaring:** `sqlite3 memory/wonderings.db
   "PRAGMA table_info(<sidecar-table-name>);"` after migration returns
   the spec columns.

**Codex overlap flag:** Codex will almost certainly catch this when
attempting to write RED #1 against real schema. Flag for synthesis.

---

## Finding D-3 -- §15.4 names `subjective_duration` as a saturation consumer; live module has no public surface for that nudge

**Severity:** Major (the spec contradicts itself between §15.4 v1 claim
and §22.3 open question)

**Surface:** §15.4 table row "`subjective_duration` | `weighted_salience`
| Nudges `retrospective_density` ..." vs §22.3 open question.

**Issue:** Verified at `core/evolution/subjective_duration.py:855-879`:
`_retrospective_density` is a private method that computes from
temperament-engagement + residual-resonance + recent-meaningful-event-
count. There is no public setter, no kwarg on
`record_salience_event(...)` for an external "saturation press" input,
and no plumbing from a saturation register into the per-sample compute
path. To "nudge" `retrospective_density`, Slice 2 would either need to
modify Slice 1's seam internals (which contradicts §2.2 / §14.4 /
brief Out-of-Scope §2) OR define a new public hook on
`subjective_duration` (which contradicts §15.4 "v1" framing because
that hook would be Slice 1 surface work).

§22.3 itself names this as an open question; §15.4 lands it as a v1
consumer. Pick one.

**Required fold:** Either
- Drop the `subjective_duration` row from §15.4's v1 consumer table,
  defer to a follow-up slice, and update §22.3 accordingly; OR
- Specify the public hook
  (`SubjectiveDuration.observe_curiosity_press(bond_id, press, sampled_utc)`
  or similar) as an EXPLICIT Slice 1 surface-extension and add a RED
  test under §23.7 proving the hook is read into the density compute.
- The first option is cleaner given the brief's discipline of treating
  Slice 1 as a dependency, not a modification target.

**8-step trace:**
1. **Dependency-map:** §15.4 consumer list, §22.3 open question, §24
   implementation surface table, §27 fold trajectory.
2. **Write-path:** Saturation would need to write into subjective_duration.
3. **Read-path:** `_retrospective_density` would need to read it.
4. **Test-path:** §23 has no test for saturation-driven density nudge.
5. **Fold-summary:** Removing the row makes §22.3 the binding
   statement.
6. **Cross-reference:** §15.4, §22.3, §24 (no subjective_duration
   modification implied by removal), §27.
7. **RED-test trace:** None needed if deferred; add one (e.g. #43.5
   `test_saturation_press_observed_by_subjective_duration`) if kept.
8. **Verify-before-declaring:** `grep -n "observe_curiosity_press\|saturation_press"
   core/evolution/subjective_duration.py` returns nothing today; spec
   must either specify it or remove the claim.

**Codex overlap flag:** Codex panel will catch this when attempting to
wire saturation. Flag for synthesis.

---

## Finding D-4 -- RED #3 ("no timer-only producer") needs a mechanically-checkable definition

**Severity:** Major

**Surface:** §6.1, §23.2 row #7
(`test_encounter_producers.py::test_no_timer_only_producer`).

**Issue:** §6.1 says "A producer that fires on a timer alone (cron tick
with no input signal) is structurally forbidden... A test fixture
constructs a 'fake timer-only producer' and asserts the substrate
refuses the registration." But the substrate currently has no producer-
registration API. Every existing wondering-producer call site
(daemon/wondering_cycle.py) effectively fires on a cycle tick: the
distinguishing property between "fires on tick" and "fires on encounter"
is whether the producer's input is anchored to a real signal event with
a verifiable provenance pointer (e.g., a cognition_quality event id, a
private-thoughts entry id). Without naming the provenance-pointer
discipline, "no timer-only" reduces to "the producer must not be the
only producer in its module" -- which is not a structural property the
test can mechanically check.

**Required fold:** Add §6.1.1 ("Producer-registration contract") with:
- The producer registration function (e.g. `register_encounter_producer(
  source: EncounterSource, evidence_pointer_kind: str, ...)`).
- A mandatory `evidence_pointer_kind` field declaring the upstream
  event-id table the producer reads from.
- The runtime refusal: producers whose `evidence_pointer_kind` is one
  of `{"timer", "cron", "scheduler_tick"}` (closed-vocabulary refusal
  set) are rejected at registration.
- RED #7 becomes mechanically checkable: construct a fake producer
  with `evidence_pointer_kind="timer"` and assert registration raises.

**8-step trace:**
1. **Dependency-map:** §6.1, §6.2 producer enum, §6.5 multi-modal
   readiness, §23.2 RED #7.
2. **Write-path:** Producer registration is the write.
3. **Read-path:** Each producer's `create_curiosity_object` path reads
   the evidence pointer to construct `encounter_ref_digest`.
4. **Test-path:** RED #7 + new RED for evidence-pointer-kind discipline.
5. **Fold-summary:** §6.1's "structurally forbidden" gains its
   mechanism.
6. **Cross-reference:** §6.1, §6.1.1 (new), §6.2.1, §19 (data-maximalism
   checklist gains an evidence-pointer-kind question).
7. **RED-test trace:** Update #7 to bind to the registration API; add
   #7a if needed.
8. **Verify-before-declaring:** `grep -n "register_encounter_producer\|evidence_pointer_kind"`
   in implementation matches spec.

**Codex overlap flag:** Codex will independently raise this when
asked to make #7 mechanical. Flag for synthesis.

---

## Finding D-5 -- "Retire production MANUAL_TEST_PRODUCER" overstates the cleanup

**Severity:** Minor

**Surface:** §24 row "Live seam dependency" and §27 trajectory.

**Issue:** Verified search: `MANUAL_TEST_PRODUCER` appears in
`core/evolution/subjective_duration.py:96` (enum), three test files,
and `scripts/scratch_e2e_canary.py`. It does NOT appear in any
production daemon path, skill, or always-on script. "Retire production
`MANUAL_TEST_PRODUCER`" is technically vacuous (there is no production
use to retire) and risks Codex either dropping the enum entry (which
breaks tests and the canary) or removing the canary (which deletes
Slice 1's smoke-test). The accurate statement is closer to "Slice 2
will introduce `DRIVE_DRIVEN_CURIOSITY` as the first real production
producer; `MANUAL_TEST_PRODUCER` remains as the canary/test
discriminator and is excluded from production code paths by gate."

**Required fold:** Rewrite §24's "Live seam dependency" responsibility
to: "Add `ProducerRef.DRIVE_DRIVEN_CURIOSITY` to the
`ProducerRef` enum. The existing `MANUAL_TEST_PRODUCER` entry remains
for canary/test surfaces; production producer registration gates
explicitly exclude it." Match §27.

**8-step trace:** Not applicable, prose-only correction with no
mechanical change.

**Codex overlap flag:** Codex will flag this when reading the diff
target.

---

## Finding D-6 -- §14.7 emotion-mimicry static-AST scan includes prompt-assembly modules but doesn't account for runtime-templated string composition

**Severity:** Minor

**Surface:** §14.7 RED #50 module list (`daemon/maez_daemon.py`,
`skills/telegram_voice.py`, `skills/web_interface.py` prompt-assembly
paths).

**Issue:** A static AST scan over string literals catches phrases like
`"Maez feels curious"` if they appear verbatim. It does NOT catch
runtime composition (e.g. `f"Maez feels {state}"` with `state="curious"`,
or `template.format(adj=adj)` with `adj="curious"`). The forbidden-
phrase set itself contains relatively bare phrases (`"I'm curious"`)
that are also legitimate vocabulary in human-side conversation, so
the scan must distinguish source-defined strings from runtime composition.
The §16.1 Test 7 outbound-text scan partially addresses this (because
it scans the actual rendered text), but §14.7's source-scan is the
load-bearing static guard, and the spec doesn't say how it handles
templated composition.

**Required fold:** Either narrow §14.7 to "string literals in
prompt-template files only" + ensure §16.1 Test 7 has its own RED row
under §23.7 to catch runtime composition, OR add a runtime
emotion-mimicry sanitizer at the prompt-render boundary and cite both
gates explicitly.

**8-step trace:**
1. **Dependency-map:** §14.7, §16.1 Test 7, §23 #50.
2. **Write-path:** Prompt assembly composes the outbound text.
3. **Read-path:** Outbound channel renders to the owner.
4. **Test-path:** #50 source scan + (to-be-added) outbound-text test.
5. **Fold-summary:** §14.7's "RED test #50 asserts" gains "for source-
   literal occurrences" qualifier; §16.1 Test 7 gets its own RED
   number.
6. **Cross-reference:** §14.7, §16.1, §23.
7. **RED-test trace:** Add e.g. `test_outbound_text_emotion_mimicry`
   under §23.7.
8. **Verify-before-declaring:** Run both scans against a fixture that
   includes runtime-composed forbidden phrases; both must fail RED
   before code lands.

**Codex overlap flag:** Likely.

---

## Finding D-7 -- §15.0 wrapper claim about old v2 references is fine, but assertion message embeds runtime values

**Severity:** Minor (defensive-coding concern, not architectural)

**Surface:** §15.0 `snapshot_temperament_for_bond` example body.

**Issue:** The `raise CrossBondAccessError(f"v1 single-bond;
bond_id={bond_id} != identity.user_profile_id()={identity.user_profile_id()}")`
leaks `identity.user_profile_id()` into the error message. v1 is
single-bond so this is benign today, but the wrapper is explicitly
named as a Track-C-precondition surface; baking the identity into the
exception message will become a (small) leak once multi-bond lands.

**Required fold:** Use a digest (HMAC-truncated) for both bond_ids in
the error message, or omit them entirely and reference the diagnostic
row id. Trivial.

**8-step trace:** Not applicable, pure code-hygiene fix.

**Codex overlap flag:** Possible.

---

## Finding D-8 -- §14.3 daily-budget clamp doesn't define what happens when prior is NULL AND budget is already exhausted

**Severity:** Minor

**Surface:** §14.3.2 ceremony body + §14.3.3 clamp + §14.3.4 NULL-first
transition.

**Issue:** §14.3.4 says first-observation transitions use `prior = 5.0`
(`NEUTRAL_TEMPERAMENT_VALUE_FOR_FIRST_OBSERVATION`). §14.3.3 says
exhausted budget yields `delta_applied = 0.0`. In the edge case where
the *first* curiosity resolution of the day fires *after* the budget is
already exhausted by some other producer (none today, but the spec
opens this door), the formula gives `new_value = 5.0 + 0.0 = 5.0`,
which writes a synthetic "neutral" first observation that wasn't a real
felt-weight event. The substrate would then record a NEUTRAL
first-observation triggered by budget exhaustion rather than by
encounter shape -- the exact phenomenology violation §4 warns against.

**Required fold:** Either
- When `delta_applied == 0.0` AND `prior is None`, refuse to write the
  event entirely (return early, no `temperament.record_event(...)`
  call). Emit a `temperament_write_clamped` diagnostic with
  `first_observation_suppressed=true`; OR
- Document the rule explicitly that the first observation is exempt
  from the daily budget (with rationale: the substrate cannot lose its
  first-observation event to a budget that was meant to bound drift, not
  bound transitions).

The first option preserves both invariants.

**8-step trace:**
1. **Dependency-map:** §14.3.2, §14.3.3, §14.3.4, §20.1
   `TEMPERAMENT_WRITE_CLAMPED` event type, §23 RED #35, #36.
2. **Write-path:** `temperament.record_event(...)`.
3. **Read-path:** §15.2 `compute_carrying_capacity` reads
   awareness/persistence; first-observation values matter for the curve
   used by saturation.
4. **Test-path:** RED #36 (NULL first-observation transition) must
   distinguish "clean first observation" from "budget-suppressed first
   observation."
5. **Fold-summary:** §14.3.3's "exhausted budget yields delta_applied
   = 0.0" gains the `prior is None` sub-rule.
6. **Cross-reference:** §14.3.2, §14.3.3, §14.3.4, §20.1, §23 #35/#36.
7. **RED-test trace:** Add (or extend #36) `test_null_first_observation_under_exhausted_budget`.
8. **Verify-before-declaring:** Run the new test against a temperament
   ledger with no `curiosity` rows and a budget pre-consumed by a
   sibling producer; expect no write.

**Codex overlap flag:** Likely.

---

## Plain-language readout for Rohit

v4 mostly checks out against the real substrate. The temperament API,
the live seam, the watchdog allowlist, the producer-snapshot path's
explicit-score refusal, the identity module, and the wondering store all
exist in the shape v4 claims, and the "producer over existing wonderings"
reframe is mechanically plausible — no architectural rewrite needed.

Four real things have to be fixed before Codex picks this up:

1. The §23 RED test table is the source of truth, but about ten places
   in the spec point to the wrong test number. A first-pass test-driven
   implementer would write the wrong tests or write the right tests with
   the wrong names; either way the TDD discipline breaks at the spec-to-
   gate seam. Pure renumbering fold, but blocking.

2. The spec says CuriosityObject is "a projection over an existing
   wondering row plus drive-layer metadata," but the real `wonderings`
   table has none of the metadata (bond_id, priority_class, salience,
   subject_kind, third-party-consent, resolution markers, resolved_at).
   The slice has to commit to where that metadata lives — either ALTER
   the wonderings table or add a named sidecar table inside the same
   database. The fix is small and lives inside `memory/wonderings.db` (no
   new DB), but right now nothing in the spec says exactly how the
   producer reads or writes those fields.

3. §15.4 says subjective_duration consumes saturation in v1, but the
   real subjective_duration module has no public surface for that nudge
   to land on. §22.3 calls this an open question; §15.4 calls it shipped.
   Pick one. Cleaner answer: defer it, since touching subjective_duration
   internals would violate the brief's "seam is dependency, not modify
   target" rule.

4. RED #3 says "timer-only producers are refused at registration," but
   the substrate has no producer-registration API today and the spec
   doesn't define how the test mechanically distinguishes a timer-only
   producer from a producer that happens to fire on a cycle tick. Adding
   an `evidence_pointer_kind` field to producer registration makes the
   test runnable.

The other findings (MANUAL_TEST_PRODUCER cleanup overstatement,
emotion-mimicry scan template handling, exception-message leak in §15.0,
NULL-first under exhausted budget) are minor — folds, not reshapes.

Codex will independently reach most of these when writing the RED suite
and the schema migration. Flagged each cross-lane concern so synthesis
composes the two lanes' findings rather than duplicating them.

**End of Descartes review.**
