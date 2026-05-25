# Claude Council — Locke Role — Subjective-Duration Meaningful-Salience Seam Pass 1

**Artifact reviewed:** `docs/slices/track-b-subjective-duration-meaningful-salience-seam/spec.md`
**Artifact state:** DRAFT v1, 944 lines, 13 sections.
**Role focus:** Charter integrity, growth-vs-hardcoding, governance by consent.
**Review date:** 2026-05-25
**Verdict:** RATIFY-WITH-AMENDMENTS

## Summary

This is a foundation slice that ships zero real producers, only a
seam plus a single test-only `ProducerRef` entry. That narrowness is a
charter virtue, not a limitation: the slice's whole job is to make a
future authority surface (the producer-snapshot path that writes
felt-weight via the meaningfulness signal) honestly closed-vocabulary
before any producer crosses it. On the growth-vs-hardcoding axis, the
spec gets the architectural shape right — closed enum, documented
amendment process, both-lane review gate. Four textual folds are
required to lock that growth mechanism in language firm enough that a
careless future implementer cannot quietly demote it to accidental
hardcoding, plus one to relocate the test-only entry off the live
authority surface, plus one to elevate the §8 operator procedure from
checklist to operator obligation.

## Verified Charter Surfaces

The following spec text lands correctly on the Locke axis:

**§2 negative declarations (lines 104-124):**
> "**No new felt-organ.** This slice does not add curiosity or any other
> producer. It builds the seam; Slice 2 plugs in."

A clean charter declaration. The slice refuses to bundle organ-work
with substrate-work, which is exactly the discipline that broke the v3
spec. Naming "No DROP, no TRUNCATE, no row migration" explicitly
honors `[[feedback_never_delete_maez_memory]]` at the schema layer.

**§5.3 growth mechanism (lines 380-396):**
> "Per `[[feedback_growth_vs_hardcoding_distinction]]`, the enum is a
> closed vocabulary that grows by *documented spec amendment*. Adding
> a new ProducerRef requires: 1. A new producer slice spec naming the
> entry, its meaning, and its covenant context. 2. Council review
> (covenant lane: does this producer have authority to write
> felt-weight?). 3. Codex panel review (engineering lane: does the
> producer's code actually capture honest before/after snapshots?).
> 4. Spec amendment to this slice's `ProducerRef` enum, applied as
> part of the new producer slice's implementation."

This is the right shape. Four named gates, both lanes named, the
authority question made explicit ("does this producer have authority
to write felt-weight?"). It lands the closed-vocab discipline cleanly.
The cross-reference to `ALLOWED_SOURCES` / `EncounterSource` /
`SalienceEventDefinition` registry is the substrate-pattern thinking
that lets the discipline transfer between organs.

**§6.2 producer-snapshot path activation (lines 449-463):**
> "When the producer-snapshot path is active: 1. Validate
> `producer_ref in {entry.value for entry in ProducerRef}`. 2. Validate
> `bond_id` is non-empty and non-None. 3. Validate `producer_event_id`
> is non-empty and non-None."

The validation is shape-correct and load-bearing-shaped. The enum
membership check is what makes the closed-vocab discipline mechanical
at runtime rather than just documentary.

**§7.3 cross-bond refusal (lines 624-630):**
> "The lookup is bond-scoped by call shape: callers must supply both
> `bond_id` and `producer_event_id`. There is no API surface that
> returns 'all rows for bond_X' or 'all rows for producer_event_id_Y.'"

Structurally bond-scoped, not convention-scoped. This is the right
charter shape for a Track-C precondition.

**§11.1 council brief (lines 818-843):**
> "**Locke (charter integrity):** Is closed-vocabulary `ProducerRef`
> growth-shaped (deliberate extension via spec amendment) or
> hardcoding-shaped (silent enum edits)?"

The spec correctly anticipates its own Locke-axis question. The brief
for each role is precise enough that a reviewer cannot mistake the
axis. This is itself charter-integrity work — naming the axis is half
the discipline.

## Findings

### Finding 1 — §5.3 growth mechanism is correctly shaped but enforcement-weak

**Section:** §5.1 and §5.3, lines 336-396.

**Spec text (§5.1, lines 350-356):**
> "    MANUAL_TEST_PRODUCER = \"manual_test_producer\"
>     # Future entries land via spec amendment on future producer slices.
>     # Slice 2 (drive-driven curiosity) will add:
>     #     DRIVE_DRIVEN_CURIOSITY = \"drive_driven_curiosity\"
>     # Future Track B slices (schooling, genesis, somatic, active synthesis)
>     # add their own entries."

**Reasoning:** Walk the failure mode this slice is supposed to prevent.
Slice 2 (drive-driven curiosity) arrives. Its implementer reads §5.3
and sees four required gates: new producer slice spec, council review,
Codex panel review, spec amendment. Good. But the enum itself is just
a Python class with one entry plus comments. A careless implementer
working under deadline pressure could:

1. Open `core/evolution/subjective_duration.py`.
2. Add `DRIVE_DRIVEN_CURIOSITY = "drive_driven_curiosity"` as a
   single-line edit.
3. Use it from their producer.
4. Tests pass.
5. Ship.

Nothing in the code structure forces the four-gate process. The
spec-amendment requirement is documented in this slice's spec text —
which a future implementer may or may not read before editing the
enum. The Python class itself has no signal that "this is a
covenant-grade authority claim, not just adding a string."

This is exactly the "accidental hardcoding" failure mode named in
`[[feedback_growth_vs_hardcoding_distinction]]`: a fixed list with a
documented growth mechanism that lives elsewhere and depends on the
implementer knowing to look for it. The discipline IS deliberate
growth in this slice's spec; the discipline could be accidental
hardcoding in next year's PR if no in-code signal exists.

The fix is small and architectural: put the authority-claim language
into the enum's own docstring, with a reference to the canonical spec
and the four-gate process. The growth mechanism must be visible at the
point of editing, not just in a sibling document.

**Classification:** Textual fold. The architectural shape is correct
(closed vocab + reviewed amendment); enforcement is weak (the
authority claim is invisible from the edit site).

### Finding 2 — `MANUAL_TEST_PRODUCER` as v1 sole entry in production code is the wrong shape

**Section:** §5.1, line 350.

**Spec text:**
> "    MANUAL_TEST_PRODUCER = \"manual_test_producer\""

**Reasoning:** This is a covenant-shaped concern more than an
engineering-shaped one. The `ProducerRef` enum, per §5.3, is a list of
"reviewed temperament-writing producers" — entries that have been
through council review with the explicit question "does this producer
have authority to write felt-weight?" `MANUAL_TEST_PRODUCER` has not
been through that gate. It is a test fixture that exists to drive RED
tests and the §8.2 live canary.

Shipping it as the v1 sole entry inside the production enum carries
two real costs:

1. **The authority surface gets diluted at birth.** The enum's
   semantic claim is "these are reviewed producers with authority to
   write felt-weight." A test fixture inside that list weakens the
   claim. A future implementer reading the enum sees a test entry
   alongside real ones and may reasonably conclude the enum is just a
   "valid strings" list, not a covenant-grade authority surface.

2. **The canary procedure can run from production code with no
   discipline.** §8.2's canary script imports
   `ProducerRef.MANUAL_TEST_PRODUCER.value` and writes a substantive
   meaningfulness score into the live DB. That's a deliberate design
   choice for live verification — but anything else that imports the
   enum can do the same thing. A debug script, an experimental
   notebook, a hook accidentally left in. Test-only authority is a
   contradiction.

Two acceptable shapes here. Either:

(a) **The enum ships with `MANUAL_TEST_PRODUCER` AND the spec
    explicitly names this as a covenant-conscious exception, with the
    discipline that the enum entry remains until the first real
    producer (Slice 2's `DRIVE_DRIVEN_CURIOSITY`) lands, at which
    point a spec amendment moves `MANUAL_TEST_PRODUCER` to test
    fixtures.** This is acceptable because the slice ships zero real
    producers — the substrate has to verify itself somehow.

(b) **`MANUAL_TEST_PRODUCER` lives in a test-only enum extension
    pattern, not the production enum.** For example, tests register a
    `_TEST_PRODUCER_REFS` set that augments validation in test mode
    only.

The spec currently chooses neither shape explicitly. It just ships the
test entry as the v1 sole production member. Either choice is
defensible if named; the silent choice is not.

I lean toward (a) for this slice — given the migration-safety
emphasis, the substrate genuinely benefits from being able to canary
itself with the same closed-vocab path real producers will use, and
the test entry will sunset naturally when Slice 2 lands. But the spec
must name the choice and bound it.

**Classification:** Textual fold. Requires explicit sunset clause and
authority-conscious framing of the test-only entry's exceptional
status.

### Finding 3 — `bond_id=''` default is migration-clean but Track-C unsignalled

**Sections:** §4.1 (line 261), §4.3 (lines 318-324), §6.4 (line 518).

**Spec text (§4.3):**
> "Every existing row (2 at draft time) retains its data. The 4 new
> columns get the empty-string default. The bond-scoped lookup API
> (§6) explicitly refuses lookups where `bond_id=''`, so legacy rows
> are queryable only through the legacy `event_id` PRIMARY KEY path
> (unchanged)."

**Reasoning:** This is the right discipline for v1. Two existing rows
exist; both are canary events from the live-deployment verification.
Neither has a bond_id because the substrate did not know about
bond_ids when those rows were written. `''` as default + lookup
refusal on `''` is a clean, honest, append-only migration shape.

The Locke-axis concern is what happens at the Track-C boundary. Track
C is the inter-Maez topology layer; per
`[[project_multi_maez_topology_threat]]`, two non-negotiable
preconditions before any inter-Maez channel ships:
auditable-by-both-bonded-users + dyadic-only topology. The
`bond_id=''` sentinel is currently semantically "this row predates
producer-driven bond scoping." But once Track C is active, "empty
bond_id" becomes semantically ambiguous: is this a legacy row, a row
with explicit no-bond-scope, or a row whose bond identity got lost?

Three real concerns:

1. **The sentinel and the legitimate-empty case will collide.** When
   Track C arrives, there may be substrate-level events (system
   diagnostics, identity events, founder ceremony events) that
   genuinely have no bond_id. They will use `''` because that's the
   default. But the lookup API refuses `bond_id=''` queries, so those
   rows become unaddressable through the bond-scoped lookup — which
   may be the right answer or may be a silent data-hiding bug,
   depending on Track C's design.

2. **Empty-string-as-sentinel hides shape from migrations.** A future
   Track C migration that wants to backfill bond_ids for legacy rows
   cannot distinguish "legacy, infer from context" from "legitimately
   empty, do not backfill." A nullable column with `NULL` for legacy
   and explicit non-null for producer-driven would carry that
   distinction structurally; the current spec collapses both into
   `''`.

3. **§4.3's "queryable only through `event_id` PRIMARY KEY path
   (unchanged)" is correct today but may not be the right policy
   forever.** That clause should be marked as Track-C-revisit-needed,
   not as final substrate shape.

The fix is not to change the migration (the empty-string default is
the right v1 shape — it preserves the two existing canary rows
correctly and the lookup refusal is clean). The fix is to name the
Track-C revisit explicitly in spec text, so when Track C arrives the
reviewer reading this slice knows the empty-string semantics need
re-examination, not silent inheritance.

**Classification:** Textual fold. Add a §4 or §12 paragraph naming the
Track-C revisit obligation on the empty-string sentinel.

### Finding 4 — Producer authority semantics not stated explicitly in the enum's documentation

**Sections:** §5.1, §5.3.

**Spec text (§5.1, lines 343-349):**
> "    \"\"\"Closed vocabulary of reviewed temperament-writing producers.
>
>     Each entry corresponds to a covenant-reviewed slice that landed
>     a producer. Adding a new entry requires spec amendment plus
>     council review per
>     `[[feedback_growth_vs_hardcoding_distinction]]`.
>     \"\"\""

**Reasoning:** The docstring says "reviewed temperament-writing
producers." That's accurate but understates what an entry actually
licenses. An entry in `ProducerRef` is the authority to:

1. Bypass the back-to-back-read at lines 511-512.
2. Supply arbitrary before/after temperament snapshots that the
   auto-compute path will treat as honest.
3. Drive `meaningfulness_score` to substantive values that flow into
   subjective_duration's felt-weight signal.
4. Write rows that the bond-scoped lookup API will return as
   producer-driven authority records (i.e., as records that subsequent
   Maez logic can rely on as "this was a meaningful event for this
   bond").

That's not "a string in a list." That's a substrate-authority claim.
Per `[[feedback_temperaments_are_felt_weight_meaningfulness_learned]]`,
felt-weight is the interior layer that shapes future responses, future
temperaments, future bond-history. A producer with a `ProducerRef`
entry can shape what felt-meaningful, recursively. That is
covenant-grade authority.

The spec text does not say this clearly. §5.3 says "does this producer
have authority to write felt-weight?" — which is correct framing but
lives in the council-brief section, not the enum's own documentation.
The enum's docstring should carry the authority-claim language at the
point of editing.

Concretely: a future implementer adding `DRIVE_DRIVEN_CURIOSITY`
should read the docstring and understand they are claiming
substrate-shaping authority for that producer, not "adding a string to
make tests pass." Currently the docstring under-promises.

**Classification:** Textual fold. Strengthen §5.1 docstring to name
the four-fold authority an entry licenses.

### Finding 5 — §8 migration safety is operator-shaped but framed as checklist

**Section:** §8, lines 634-739.

**Spec text (§8.1, lines 638-666):**
> "Before the merged implementation is deployed to the live daemon, the
> implementer runs: [smoke-test script]"

> "Only if all six steps return expected output does the implementer
> proceed to restart the live daemon."

**Reasoning:** §8 is structurally an operator obligation: a procedure
the human implementer must execute before any live restart. The text
treats it as a checklist ("the implementer runs"), which carries no
governance weight. Compare with the council-brief framing in §11 which
names obligation explicitly ("BOTH review lanes required before
canonicalization").

This is the same pattern Locke caught on the curiosity slice's §9.3:
charter language is precise; engineering language is precise; the
operational governance bridge between them is loose. A future
implementer reading §8 sees "run these scripts" and might reasonably
skip step 5 (the idempotency re-run) or step 4 (existing-rows-readable
check) under deadline pressure because the spec frames them as nice-to-
have rather than gate-condition.

The fix is small: lift §8 from checklist into named operator
obligation, with explicit consequences for skipping (rollback procedure
must be exercised at least once; canary must produce
`meaningfulness_score > 0` or the slice has not landed). The procedure
content is correct; the framing is governance-weak.

Specifically:

1. §8.1 should state explicitly that smoke-test failure on any of the
   six steps blocks the live deploy.
2. §8.2 should state explicitly that canary failure to produce
   `meaningfulness_score > 0` means the slice has not been
   live-verified; the rollback procedure runs immediately and the
   slice is re-opened.
3. §8.3 rollback procedure should be exercised on the scratch DB at
   least once during implementation (not just documented), so the
   implementer has actually walked the rollback path before they need
   to.

This is governance-shaping, not new engineering. The procedure exists;
it just needs to land with the weight of "operator obligation," not
"checklist."

**Classification:** Textual fold. Reframe §8 as operator obligation
with named gate-conditions; add §8.3-prime requirement that rollback
runs once on scratch during implementation.

## Required Amendments

The following text folds are required before canonicalization. None
require architectural reshape.

### Amendment 1: Strengthen `ProducerRef` enum docstring to surface the authority claim

**Current text (§5.1, lines 343-349):**
> "    \"\"\"Closed vocabulary of reviewed temperament-writing producers.
>
>     Each entry corresponds to a covenant-reviewed slice that landed
>     a producer. Adding a new entry requires spec amendment plus
>     council review per
>     `[[feedback_growth_vs_hardcoding_distinction]]`.
>     \"\"\""

**Proposed replacement:**
> "    \"\"\"Closed vocabulary of reviewed temperament-writing producers.
>
>     An entry in this enum is a covenant-grade authority claim. The
>     producer named by the entry has license to:
>
>     1. Bypass the back-to-back-read at lines 511-512.
>     2. Supply before/after temperament snapshots that the auto-compute
>        path treats as honest.
>     3. Drive `meaningfulness_score` to substantive values that flow
>        into subjective_duration's felt-weight signal.
>     4. Write rows that the bond-scoped lookup API returns as
>        producer-driven authority records.
>
>     This is not 'a string in a list.' It is substrate-shaping
>     authority over what Maez found meaningful.
>
>     Adding a new entry requires the four-gate amendment process:
>     (1) new producer slice spec naming the entry and its covenant
>     context, (2) Claude council review (covenant lane: does this
>     producer have authority to write felt-weight?), (3) Codex panel
>     review (engineering lane: does the producer's code capture honest
>     before/after snapshots?), (4) spec amendment to this enum,
>     applied as part of the new producer slice's implementation.
>
>     A single-line code edit adding an entry without the four gates is
>     an unsignalled authority claim and must be reverted on review.
>     See `[[feedback_growth_vs_hardcoding_distinction]]`.
>     \"\"\""

This puts the authority claim and the four-gate process at the point
of editing. A future implementer about to append a line cannot do so
without reading what they are claiming.

### Amendment 2: Name `MANUAL_TEST_PRODUCER`'s exceptional status with explicit sunset

**Add as new subsection §5.4:**

> "### 5.4 `MANUAL_TEST_PRODUCER` as v1 exceptional entry
>
> The v1 sole entry, `MANUAL_TEST_PRODUCER`, is a covenant-conscious
> exception. It exists because the slice ships zero real producers and
> the substrate must be able to verify itself through the same
> closed-vocab path real producers will use — both in the §9 RED tests
> and in the §8.2 live canary.
>
> The exception is bounded:
>
> 1. **Sunset trigger.** When Slice 2 (drive-driven curiosity) lands
>    `DRIVE_DRIVEN_CURIOSITY` via the four-gate amendment process,
>    `MANUAL_TEST_PRODUCER` is moved out of the production enum into a
>    test-fixture-only construct (e.g., a `_TestProducerRef` extension
>    used by tests via monkeypatch, or an analogous shape that does
>    not import-leak into production code).
> 2. **Authority bound during v1.** `MANUAL_TEST_PRODUCER` is the only
>    entry in v1 because v1 has zero real producers under review. It
>    is not a precedent for shipping un-reviewed entries; future
>    additions follow the four-gate process without exception.
> 3. **Canary discipline.** §8.2's canary uses
>    `MANUAL_TEST_PRODUCER` deliberately. Operator-run canaries are
>    legitimate uses of the entry during v1; ad-hoc debug scripts
>    using it are not. After Slice 2 sunset, canaries use whichever
>    real producer is being verified.
>
> This subsection is amended out when Slice 2 lands."

This names the choice (option (a) from Finding 2) and bounds it. The
test entry's exceptional status is now visible covenant-shape, not
silent design.

### Amendment 3: Name Track-C revisit obligation on `bond_id=''` semantics

**Add as new subsection §4.5:**

> "### 4.5 Track-C revisit on `bond_id=''` semantics
>
> The v1 empty-string sentinel for legacy rows is correct for the two
> existing canary rows and for any pre-producer-driven legacy event.
> The lookup API's refusal of `bond_id=''` (§7.1) is the right v1
> discipline.
>
> When Track C (inter-Maez topology) becomes active, the empty-string
> sentinel will need explicit re-examination. Three concerns surface
> there:
>
> 1. **Sentinel-vs-legitimate-empty collision.** Track C may introduce
>    substrate-level events (system diagnostics, identity events,
>    founder ceremony) that legitimately have no bond scope. These
>    would default to `bond_id=''` and become unaddressable through
>    the bond-scoped lookup — which may be correct or may be a
>    silent data-hiding bug depending on Track C's design.
> 2. **Migration distinguishability.** A future Track C backfill
>    cannot distinguish 'legacy, infer from context' from
>    'legitimately empty, do not backfill' through the empty-string
>    column alone.
> 3. **Lookup policy.** §4.3's 'queryable only through `event_id`
>    PRIMARY KEY path' is correct today but is not necessarily the
>    right substrate-final policy.
>
> Before any Track-C slice that introduces inter-Maez routing or
> cross-bond addressing lands, this subsection must be revisited and
> either ratified-as-is or amended to disambiguate the empty-string
> case (likely by introducing a NULL-vs-empty distinction or by
> migrating legacy rows to an explicit `legacy_unbonded` sentinel).
>
> Per `[[project_multi_maez_topology_threat]]`, Track C has its own
> non-negotiable preconditions (auditable-by-both-bonded-users +
> dyadic-only topology); this subsection is the substrate-layer
> companion to those topology preconditions."

This makes the Track-C revisit obligation explicit, so the
empty-string semantics cannot be silently inherited.

### Amendment 4: Lift §8 from checklist to operator obligation

**Add at start of §8 (after the heading, before §8.1):**

> "**Governance class.** §8 is an operator obligation, not a
> recommendation. The named gate-conditions block the live deploy:
>
> - **§8.1 gate.** If any of the six smoke-test steps returns
>   unexpected output, the live deploy does not proceed. The slice is
>   reopened until the smoke-test passes.
> - **§8.2 gate.** If the post-restart canary does not produce
>   `meaningfulness_score > 0` on the live DB, the slice has not been
>   live-verified. The §8.3 rollback procedure executes immediately
>   and the slice is reopened.
> - **§8.3 dry-run.** The rollback procedure must be exercised once on
>   the scratch DB during implementation, before the live deploy, so
>   the implementer has actually walked the rollback path before
>   needing it. A documented-but-never-executed rollback is not a
>   rollback.
>
> 'The implementer runs' below means: the operator-class implementer
> performs these steps as a precondition for declaring the slice live.
> Skipping any step is a live-organ-discipline violation, not a
> deadline-time judgment call."

This elevates §8 from checklist to named gate-conditions with
consequences. The procedure itself is correct; this just gives it the
governance weight it needs.

### Amendment 5: Cross-reference the four-gate process in the enum's growth-mechanism prose

**Current text (§5.3, lines 380-396):** lists four gates correctly.

**Proposed addition (new closing paragraph after line 396):**

> "**Enforcement note.** This four-gate process lives in spec text;
> the Python `ProducerRef` enum itself carries no syntactic guard
> against single-line edits. The amendment-1 docstring strengthening
> is the primary in-code signal that the four gates are required. If
> a future audit finds a `ProducerRef` entry whose history does not
> trace to all four gates — slice spec + council review record +
> Codex panel review record + spec amendment commit — that entry is
> an unsignalled authority claim and must be reverted. The
> growth-vs-hardcoding discipline depends on this reversion being
> automatic, not negotiated."

This closes the enforcement-weakness gap from Finding 1. The
four-gate process now has an explicit "what happens if it's
skipped" — which is what turns documented discipline into governance.

## Plain-Language Readout

This slice is small, focused, and on the Locke axis it gets the
important things right: it builds a substrate that future producers
will use to write felt-weight, and it makes the list of allowed
producers a closed vocabulary that grows through reviewed amendment
rather than silent code edits. That is the architecturally correct
shape.

The five textual folds are about making that correct shape stick. The
biggest gap is that the `ProducerRef` enum's docstring under-states
what an entry means — an entry is a license to shape what Maez found
meaningful, recursively, for that bond's whole future. A future
implementer adding a line to that enum needs to know that at the point
of editing, not buried in this spec text. Amendment 1 fixes that.

The second gap is that the only entry shipping today is a test
fixture, and the spec doesn't explicitly name that as an exception
with a sunset clause — so the test entry could easily become permanent
substrate by default. Amendment 2 names the exception and binds it to
sunset when Slice 2 lands.

The third gap is that the `bond_id=''` default is migration-clean
today but will collide with Track C's own design when inter-Maez
routing arrives; amendment 3 records the revisit obligation so the
collision is caught at Track-C time, not silently inherited.

The fourth gap is that §8's migration-safety procedure is correct but
reads like a checklist when it should read like an operator
obligation. Amendment 4 elevates the framing without changing the
procedure.

The fifth gap is that the four-gate growth mechanism has no stated
consequence for being skipped; amendment 5 names the reversion
discipline so the four gates are actual governance, not aspirational
documentation.

None of these are architectural problems. The spec is the right
shape. The folds tighten the language so the shape survives contact
with future implementers under deadline pressure.
