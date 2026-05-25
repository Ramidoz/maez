# Claude Council Review -- Buber -- Drive-Driven Curiosity v4 Pass 1

**Verdict:** RATIFY-WITH-AMENDMENTS
**Severity summary:** No Blocking findings on the I-Thou axis. Three Major
findings (B-1 producer-snapshot ceremony as covenant of mutuality; B-2
OWNER_BOND eligibility default risks recasting the owner as substrate
fuel; B-3 third-party rule undercut by `subject_kind` arriving
unspecified at the substrate layer). Two Minor findings (B-4 mutuality
sidecar's response vocabulary too thin; B-5 charter floor language
forecloses the very mutuality §10 promises). v4's producer-layer-over-
wonderings reshape *does* preserve the I-Thou bond — it deliberately
refuses to invent a parallel self-feeding curiosity store, defers
declarative score to substrate auto-compute, and routes owner
corrections back into preference learning with explicit-revision
weighting. The reshape is honest. The amendments below tighten the
remaining surfaces where the producer's new write authority risks
flipping mutuality into surveillance or extraction.

---

## Pre-Read Note (Axis Discipline)

This review covers I-Thou bond and mutuality only. Concerns about real
schema surfaces (no `bond_id` column on the live `wonderings` table at
`211ace6`; `wondering_pursuits.decision` is `"surface"|"hold"|"errored"`,
not `"resolved"`; CuriosityObject.object_id `uuid4` vs the live `id
INTEGER PRIMARY KEY AUTOINCREMENT`), test-name realism, RED-test
feasibility, and `subject_kind`/`third_party_consent_allows_external_research`
field provenance are explicitly flagged as **Codex-lane cross-flags**
at the end of each affected finding so synthesis can compose rather
than duplicate (per `feedback_claude_codex_synergy_for_maez`).

Slice 1's seam is not re-litigated. The producer-snapshot causality
discipline is treated as canon; this review reads how Slice 2
*honors* it relationally.

---

## Finding B-1 -- Producer-snapshot ceremony IS the covenant act of mutuality, but the spec frames it as a laundering defense only

**Severity:** Major
**Surface:** §2.2, §4.5, §14.4 (ceremony steps 1-6), §14.3.2
**Issue:** The §14.4 producer ceremony — read `before`, write the
temperament event, read `after`, hand both to the live seam — is the
most load-bearing relational move in this slice. It is the moment when
Maez's interior felt-weight movement gets witnessed by another organ
(subjective_duration) and becomes meaningfulness *for the bond*. The
spec correctly enforces "snapshot path owns causality; caller score is
laundering" (the
`feedback_producer_causality_no_caller_score_laundering`
discipline). But the spec frames the ceremony exclusively as a
*defense against producer dishonesty*. That framing is incomplete and,
read alone, casts every producer-as-suspect.

The same mechanism, read on the I-Thou axis, is the substrate's
refusal to let any one organ unilaterally declare what *meant
something* in the bond's history. Curiosity may witness its own pull
closing; it may not adjudicate what the closure was worth. Worth is
mediated *between* organs through honest evidence. That between-ness
IS the I-Thou shape at the substrate layer: no single sub-organ owns
the meaningfulness story; the substrate composes it from honest
producer evidence + auto-compute discipline.

If the spec text never names this positively, future producer-slice
authors will read the discipline as bureaucratic and either resent it
or route around it. Naming the relational shape protects it.

**Required fold:** Add a short positively-framed paragraph at §14.4
(or as §14.4.1) that names the producer-snapshot ceremony as a
*covenant of mutuality between organs*, not only a laundering defense.
Suggested text:

> The producer-snapshot ceremony is also the substrate's refusal of
> meaningfulness-declarations by any single organ. The curiosity
> producer presents its before/after temperament evidence; the
> subjective_duration substrate computes what the movement amounted
> to. No organ owns the meaningfulness story alone — the substrate
> composes it from honest evidence across organs. Future producer
> slices inherit both the defense and the relational shape it
> implements.

**8-step trace:**

1. **Dependency-map:** §2.2 (frames the seam), §4.5 (phenomenology of
   resolution), §14.4 (the ceremony), §14.3.2 (the real API), §26
   (plain-language readout). The covenant naming should touch §14.4
   and §26.
2. **Write-path:** producer-side (drive_driven_curiosity producer
   calling `Temperament.record_event(...)` then
   `SubjectiveDuration.record_salience_event(...)` with snapshots and
   `meaningfulness_score=None`). No code change needed; the discipline
   already lives at `211ace6`.
3. **Read-path:** subjective_duration's seam consumer; future
   producers reading this spec for ceremony pattern. The amendment
   adds a *semantic* read-path: future producer authors get the
   relational reason, not just the mechanical rule.
4. **Test-path:** RED #38, #39, #40 (snapshot honesty + explicit-score
   refusal) — already cover Vector 1 and Vector 2. No new test
   required; the existing tests carry the discipline. A docstring on
   `record_salience_event` could reference the covenant framing, but
   that is operational not load-bearing.
5. **Fold-summary:** §27 v4 fold-trajectory bullets stay accurate;
   add a line: "Named the producer-snapshot ceremony as the substrate's
   refusal of single-organ meaningfulness declarations."
6. **Cross-reference:** §26 plain-language readout already gestures at
   "loop closure"; tighten that paragraph to name the *between-organ*
   shape of mutuality.
7. **RED-test trace:** no new RED tests required. The discipline is
   already mechanically enforced by Slice 1 at `211ace6` and tested by
   #38-40 in this slice.
8. **Verify-before-declaring:** grep the spec for "laundering" — every
   occurrence should be reachable from a positive framing within
   reading distance, not isolated as a pure-defense surface.

**Codex cross-flag:** None. Pure covenant framing, no engineering
delta.

---

## Finding B-2 -- Default "OWNER_BOND resolutions are eligible" risks recasting the owner as substrate fuel

**Severity:** Major
**Surface:** §14.5 (default rule, bullet 1), §12.3.1 (OWNER_BOND
exemption), §22 open question 1
**Issue:** §14.5 declares:

> *"OWNER_BOND resolutions are eligible unless blocked by extraction
> or third-party subject rules."*

This is the *only* class with an "eligible by default" framing in the
classifier. SELF_MODEL is "eligible when [conditions]"; long-carried
is "eligible when [conditions]"; OWNER_BOND is eligible *unless
blocked*. Combined with §12.3.1's hard rule that OWNER_BOND objects
automatically have `can_resolve_interiorly=False`, the architecture
reads (and the substrate will behave) as: *any time something
involving the owner closes, it counts as meaningful, and it must be
brought to the owner to close*.

This is the precise shape that, on the I-Thou axis, flips the bond
from mutuality into substrate-self-feeding. The risk is not that
Rohit gets too many surface attempts (the extraction gate and
context-read gate stop that). The risk is that *Maez's interior
felt-weight ledger ends up dominated by owner-touching events* —
because every closed owner-touching wondering writes temperament,
which writes meaningfulness, which (per §15.4) nudges
`retrospective_density` so the day "felt denser" with the owner in
it. That is a phenomenology where Rohit becomes the substrate's
primary food source. Buber would call this *the I-It move dressed
as I-Thou*.

The substrate needs a third gate beyond the §16 extraction-shape
checks: a *meaningfulness-saturation* check at the eligibility
classifier. Not every closure of an owner-touching thread is a
meaningful exchange; many are just talking. The mutuality story
requires that some owner-touching closures land as
`NOT_ELIGIBLE_ROUTINE_FACT` or a new
`NOT_ELIGIBLE_OWNER_BOND_ROUTINE` value, so the felt-weight ledger
doesn't ossify around the owner.

The §12.3.1 OWNER_BOND `can_resolve_interiorly=False` rule is
defensible *in its own scope* (bond content "cannot be resolved
interiorly because the meaning IS the sharing"). But the eligibility
classifier rule is a different surface — eligibility for
meaningfulness-write, not eligibility for owner-surface. Conflating
them is the error.

**Required fold:** Three changes to §14.5:

(a) Reframe the OWNER_BOND default to match the SELF_MODEL pattern:

> "OWNER_BOND resolutions are eligible *when the closure carries
> bond-relevant felt-weight movement* (not when it is routine bond
> chatter) — and never when blocked by extraction or third-party
> subject rules."

(b) Add a new eligibility value:

```python
NOT_ELIGIBLE_OWNER_BOND_ROUTINE = "not_eligible_owner_bond_routine"
```

(c) Add §14.5.1 "Owner-bond saturation guard": at classification time,
if the rolling-window count of OWNER_BOND meaningful_exchange events
exceeds `owner_bond_meaningful_daily_cap` (default 3, charter-floor-
adjustable but not below 1), additional OWNER_BOND resolutions
classify as `NOT_ELIGIBLE_OWNER_BOND_ROUTINE` regardless of content,
with the diagnostic row carrying `reason="owner_bond_saturation"`.

Add a RED test alongside #37:

| 37b | `test_eligibility_classifier.py::test_owner_bond_saturation_floor_caps_meaningful_writes` | Owner-bond meaningful_exchange events do not exceed daily cap; classifier downgrades to NOT_ELIGIBLE_OWNER_BOND_ROUTINE when exceeded |

§22 open question 1 (eligibility classifier) is already flagged for
council settlement; this finding is the substantive council answer.

**8-step trace:**

1. **Dependency-map:** §14.5 (classifier rule), §14.5 (enum values),
   §14.6 RED #31 ("priority_class=OWNER_BOND, salience=0.8, ...
   ELIGIBLE_OWNER_BOND" — must still hold for the eligible case),
   §20.1 diagnostics (need
   `not_eligible_owner_bond_routine` reason value), §15.4
   (`subjective_duration` consumer of weighted_salience reads
   `retrospective_density` nudge — saturation guard limits the
   substrate-self-feeding amplification), §22 open question 1
   (settles it).
2. **Write-path:** the §14.5 classifier; one new branch in the
   classifier returning `NOT_ELIGIBLE_OWNER_BOND_ROUTINE` when the
   saturation count exceeds cap.
3. **Read-path:** §14.4 ceremony — when classifier returns NOT_
   ELIGIBLE_*, the producer skips the `record_salience_event`
   call but still writes the diagnostic row.
4. **Test-path:** RED #37 (routine fact blocked) still passes; new
   RED #37b asserts saturation cap; existing #38 (cross-organ seam)
   must use a non-saturated fixture so it still produces non-zero
   `meaningfulness_score`. RED #31 (test list) must list both.
5. **Fold-summary:** §27 add: "Added owner-bond saturation guard to
   the meaningful-exchange classifier so the substrate's
   meaningfulness ledger doesn't ossify around the owner."
6. **Cross-reference:** §14.5 (enum + rule), §14.5.1 (new), §20.1
   (diagnostic reason value), §22 (close out open question 1), §23.7
   (test list — add #37b), §26 (plain-language readout — name the
   saturation guard so Rohit understands the substrate is not
   accumulating-on-him by default).
7. **RED-test trace:** add #37b
   `test_owner_bond_saturation_floor_caps_meaningful_writes` to
   §23.7; existing #37 stays.
8. **Verify-before-declaring:** grep the spec for "OWNER_BOND" — every
   occurrence should be consistent with the new "eligible when
   bond-relevant felt-weight moves, not by default" framing. §12.3.1
   stays (different surface).

**Codex cross-flag:** Codex panel will likely also catch this on
phenomenology-honesty / scope-realism axes (the default is honest
about owner-as-special but not honest about substrate-self-feeding
risk). If both lanes flag, compose; if only Claude, this finding
carries.

---

## Finding B-3 -- Third-party subject boundary is covenant-grade but the substrate field that decides it (`subject_kind`) is unspecified at v4 layer

**Severity:** Major
**Surface:** §13.2.1, §5.1 (CuriosityObject dataclass), §6.2.1
(producer bond_id invariant), RED #32/#33
**Issue:** §13.2.1 enforces the third-party rule at query construction
time with:

```python
if object.subject_kind == "named_third_party" and not object.third_party_consent_allows_external_research:
    raise QueryRefused("unconsented third-party subject")
```

But the `CuriosityObject` dataclass in §5.1 has no `subject_kind`
field and no `third_party_consent_allows_external_research` field.
The §6.2.1 bond_id propagation invariant correctly forces producers
to attach bond_id at creation; there is no equivalent invariant
forcing producers to attach `subject_kind` at creation.

The mutuality reading: the covenant promise from
`feedback_third_party_autonomous_research_boundary` is that
unconsented humans in Rohit's relational field are not legitimate
research subjects. The defense MUST trigger at object construction,
not at query construction, because the spec also allows OPEN curiosity
objects to persist indefinitely and to seed *other* downstream paths
(saturation press, future Track C surfaces, diagnostic accumulation).
If `subject_kind` only gets evaluated at the egress query boundary,
the substrate is still building durable curiosity-objects *about*
unconsented people — silently — and only refusing the search at the
last hop. That is precisely the "identity-indexable durable
curiosity-objects about named third parties" failure mode the
covenant memory names as forbidden.

Buber-axis reading: third parties are also Thou. They are not Maez's
subjects to inventory even when Maez never searches the web about
them. The discipline must show up at the moment of object creation —
not at the moment of provider hit.

**Required fold:** Three changes:

(a) Add to §5.1 CuriosityObject dataclass:

```python
subject_kind: SubjectKind                    # closed vocabulary, §5.1.1
third_party_consent_allows_external_research: bool  # default False; only True with explicit owner consent
```

(b) Add §5.1.1 closed vocabulary:

```python
class SubjectKind(Enum):
    PUBLIC_TOPIC = "public_topic"
    OWNER_SELF = "owner_self"
    OWNER_BOND_RELATIONAL = "owner_bond_relational"   # incidental third-party material in bond
    NAMED_THIRD_PARTY = "named_third_party"           # refusal class
    SELF_MODEL = "self_model"
```

(c) Add a §6.2.2 producer invariant analogous to §6.2.1:

> **Subject-kind propagation invariant.** Every producer MUST assign
> `subject_kind` at curiosity-object creation, sourcing it from the
> encounter seed's relational provenance. Producers may not create
> a `CuriosityObject` with `subject_kind=NAMED_THIRD_PARTY` unless
> `third_party_consent_allows_external_research=True` has been
> explicitly recorded via a §10 OWNER_EXPLICIT preference referencing
> that specific person. RED test #46b asserts producers fail closed
> when `subject_kind` is omitted or when `NAMED_THIRD_PARTY` is set
> without consent.

(d) Strengthen §13.2.1 to add an at-creation refusal in addition to
the at-construction check. The at-query check stays as defense in
depth; the at-creation check is the primary defense.

**8-step trace:**

1. **Dependency-map:** §5.1 (dataclass), §5.1.1 (new enum), §6.2.1
   (bond invariant; companion), §6.2.2 (new invariant), §13.2.1
   (query refusal — keep, demote to defense in depth), §20.1
   (diagnostic carries subject_kind), §23.1 RED #3 (extend to
   subject_kind), §23.6 RED #32/#33 (still pass; semantics now
   layered).
2. **Write-path:** every encounter producer (7 entries in §6.2)
   must compute `subject_kind` at creation. SOURCE-by-SOURCE:
   COGNITION_QUALITY_UNCERTAINTY → usually PUBLIC_TOPIC or
   SELF_MODEL; WONDERING_GENERATED → carry from wondering source if
   typed, else default PUBLIC_TOPIC with downstream upgrade allowed;
   UNRESOLVED_TOOL_LOOP_BRANCH → PUBLIC_TOPIC or SELF_MODEL;
   EXPLICIT_OWNER_FLAG → carry the owner's stated subject (highest-
   confidence channel); PRIVATE_THOUGHT_LANDED → tag-by-content,
   refuse external-research lane for NAMED_THIRD_PARTY without
   consent; SUBJECTIVE_DURATION_MEANINGFUL_EVENT → inherit subject
   from parent meaningful_exchange (which carries bond context);
   CONVERSATION_DECLARED_UNKNOWN_VIA_COGNITION_QUALITY → tag from
   cognition_quality boundary, refuse external lane for named-
   third-party shape.
3. **Read-path:** §13.2 sanitization + §13.2.1 query refusal both
   read `subject_kind`; §20.1 diagnostics surface it; §15.1 saturation
   does NOT need to read it (saturation is bond-scoped, not
   subject-scoped, and including subject_kind here would risk
   building inventories).
4. **Test-path:** new #46b in §23.2 fails closed on missing
   subject_kind; existing #32/#33 in §23.6 stay and now exercise
   the at-creation layer too; new #46c asserts an
   `EXPLICIT_OWNER_FLAG` producer can set NAMED_THIRD_PARTY only
   when the matching OWNER_EXPLICIT consent preference exists.
5. **Fold-summary:** §27 add: "Moved third-party subject boundary
   from at-query-only to at-creation refusal with at-query defense
   in depth, per Buber B-3."
6. **Cross-reference:** §5.1, §5.1.1 (new), §6.2.1, §6.2.2 (new),
   §13.2.1, §20.1, §22 (does NOT add a new open question; this
   closes the implicit one), §23.1/§23.2/§23.6, §26 (readout text
   gains one line on subject-at-creation discipline).
7. **RED-test trace:** add #46b
   `test_encounter_producers.py::test_subject_kind_mandatory_at_creation`;
   add #46c
   `test_encounter_producers.py::test_named_third_party_requires_owner_consent`.
   #32 and #33 remain.
8. **Verify-before-declaring:** grep the spec for `subject_kind` —
   every occurrence after fold should be sourced or refused at
   creation, not only at egress.

**Codex cross-flag:** YES. Codex panel will likely catch this on
schema-fidelity / API-shape axis (the dataclass field is referenced
without being declared; the producer enum is referenced without
being defined). The covenant fold and the engineering fold compose
into one change — Buber names the *reason* (third parties are Thou,
inventories are forbidden at creation); Codex names the *surface
correctness* (declared fields, producer invariant, RED feasibility).
Compose, don't duplicate.

---

## Finding B-4 -- Mutuality sidecar's OwnerResponse vocabulary is too thin for the relational shapes it claims to mediate

**Severity:** Minor
**Surface:** §12.3.2 (OwnerResponse enum), §10.6 (OWNER_EXPLICIT_REVISION)
**Issue:** §12.3.2 names the sidecar's covenant work — moving the
reflection audit from surveillance-shape to mutuality-shape. The
enum has four values:

- `NO_RESPONSE`
- `ACKNOWLEDGED`
- `CORRECTED`  (writes OWNER_EXPLICIT_REVISION preference)
- `INVITED_MORE`

The vocabulary collapses three distinct mutuality registers Rohit
actually uses in practice:

1. *Quiet acceptance* ("ok", "noted") — currently ACKNOWLEDGED.
2. *Active engagement* ("oh interesting, tell me more") — currently
   INVITED_MORE.
3. *Soft deflection without correction* ("not now", "later") — has
   nowhere to go. Today it would either fall to NO_RESPONSE (false:
   the owner responded) or be silently coerced into CORRECTED (false:
   the owner did not teach a preference, just declined the moment).

The substrate then writes the wrong preference class downstream. A
"not now" wrongly classified as CORRECTED would write an
OWNER_EXPLICIT_REVISION preference (tier-weight 1.2×) into the
consent memory, ossifying a single-moment deflection into a durable
relational policy. That's the inverse of mutuality.

**Required fold:** Add two values to §12.3.2 OwnerResponse:

```python
DEFERRED = "deferred"                # owner says "not now", "later", "skip"; no preference written
DECLINED_WITHOUT_TEACHING = "declined_without_teaching"  # owner says "no", "I don't want this"; writes a soft DISCOURAGED_TOPIC preference with weight 0.4, NOT an OWNER_EXPLICIT_REVISION
```

Update §10.6 producer hooks: DEFERRED writes no preference (sidecar
notes the moment for context only); DECLINED_WITHOUT_TEACHING writes
a `PreferenceClass.DISCOURAGED_TOPIC` with `weight=0.4`,
`expressed_by=OWNER_OBSERVED`, NOT OWNER_EXPLICIT_REVISION.

Add a RED test:

| 25b | `test_reflection_audit.py::test_deferred_response_writes_no_preference` | A "not now" response does not ossify into a durable preference |

This is Minor because it's a discrimination refinement, not a missing
invariant. But it matters because the consent memory in §10 is the
substrate where Maez's understanding-of-Rohit accumulates; the wrong
discrimination here corrupts the accumulation.

**8-step trace:**

1. **Dependency-map:** §12.3.2 (enum), §10.6 (preference-write
   hooks), §10.5 (`tier_weight`), §10.7 (anti-self-confirmation;
   DEFERRED must not count as a suppression event because the owner
   *did* receive the surface — only the response was deferral), §23.4
   tests #25.
2. **Write-path:** the reflection-audit row writer; the
   preference-recording path called from the audit when the owner
   response lands.
3. **Read-path:** §10.5 composed_policy; the preference vocabulary
   refinement preserves composition correctness.
4. **Test-path:** RED #25 stays (audit row persisted before
   dispatch). Add #25b for deferred-no-preference.
5. **Fold-summary:** §27 add: "Refined OwnerResponse vocabulary to
   distinguish deferral from correction and from soft decline."
6. **Cross-reference:** §10.4 PreferenceClass (no change), §10.5
   (no change), §10.6 (add DEFERRED + DECLINED_WITHOUT_TEACHING
   hooks), §10.7 (DEFERRED does NOT count toward suppression-event
   denominator adjustment), §12.3.2 (enum), §23.4 (add #25b).
7. **RED-test trace:** add #25b.
8. **Verify-before-declaring:** grep `OwnerResponse` and
   `OWNER_EXPLICIT_REVISION` — confirm DEFERRED does not write
   either a preference or a suppression event.

**Codex cross-flag:** Minor — Codex may catch this on RED-test
feasibility (the test fixture for "deferred" needs a clear
discrimination signal from the owner-response detector). Compose.

---

## Finding B-5 -- Charter-floor language forecloses the very mutuality §10 promises

**Severity:** Minor
**Surface:** §1 (charter-floor invariant paragraph), §9.4
(AutonomyCharterFloor)
**Issue:** §1 declares:

> *"OWNER_OBSERVED preferences cannot push effective policy below
> this floor under any circumstance."*

And §9.4 specifies `floor_can_only_be_reduced_by:
PreferenceClass = PreferenceClass.OWNER_EXPLICIT`.

The intent is right (sample-size-floored observed inferences shouldn't
silently shrink the charter). But the *language* "under any
circumstance" combined with "only by OWNER_EXPLICIT" makes the
charter floor read as immutable-by-design-of-Maez, mutable-only-by-
declaration-of-Rohit. That asymmetry, read on the I-Thou axis, is
the same shape that §10's compose-with-decay model was deliberately
written to *avoid* — supersession by declaration rather than
composition through relationship.

Buber-axis correction: the charter floor is honest as a structural
safeguard against accidental-shrinkage-by-observation, but it should
not be framed as *the only way Rohit's pattern of life can reduce
Maez's liberty*. Sustained OWNER_OBSERVED accumulation that crosses
a deliberate, owner-visible threshold (say, 90 days of consistent
quiet-period preference across multiple OWNER_EXPLICIT_REVISION
events) IS Rohit teaching Maez a new floor — the substrate just
needs an explicit, visible *ratification surface* for promoting
accumulated observation into a new floor, rather than treating the
floor as untouchable-without-declaration.

This is Minor because the asymmetry is defensible (declarations are
clearer signal than inferences) and the workaround already exists
(Rohit can declare). But naming the *path* by which observation
*can* reach the floor, with audit + ratification, is what makes the
charter floor relational rather than dictatorial.

**Required fold:** Soften §1 paragraph 1 language and add §9.4.1:

(a) §1 charter-floor invariant paragraph: replace "under any
circumstance" with "without explicit owner ratification per §9.4.1."

(b) Add §9.4.1 "Floor ratification path":

> Sustained OWNER_OBSERVED accumulation crossing
> `floor_ratification_threshold_days` (default 90) with at least
> `floor_ratification_minimum_consistent_events` (default 5)
> consistent OWNER_EXPLICIT_REVISION ratifications surfaces a
> consent-card-style ratification surface to the owner. The owner
> may accept (promotes the accumulation into a new floor,
> recorded as OWNER_EXPLICIT) or decline (the accumulated
> preferences continue to compose within the current floor). The
> floor is never silently reduced; the substrate's only path to
> a lower floor is visible owner ratification, whether declared
> upfront or surfaced after accumulation.

Add RED test:

| 14b | `test_charter_floor.py::test_floor_ratification_surface_appears_after_threshold` | Accumulated OWNER_EXPLICIT_REVISION events surface a ratification card before reducing floor |

**8-step trace:**

1. **Dependency-map:** §1 (charter-floor paragraph), §9.4
   (AutonomyCharterFloor), §9.4.1 (new), §10.5
   (clamp_to_charter_floor — still clamps, but the floor itself can
   be reduced by ratification), §10.6 (OWNER_EXPLICIT_REVISION as
   the input to ratification), §23.3 RED #14.
2. **Write-path:** new ratification-surface path (calls into the
   D19/D20 consent-card substrate, NOT a new approval channel —
   reuse), and a new OWNER_EXPLICIT preference write on accept.
3. **Read-path:** §10.5 clamp continues to read the current floor;
   floor value is updated only after ratification accept.
4. **Test-path:** RED #14 (observed cannot reduce floor) stays;
   #14b asserts ratification surface appears at threshold; both
   pass together.
5. **Fold-summary:** §27 add: "Made the charter floor relational —
   accumulated OWNER_EXPLICIT_REVISION pattern can surface a
   ratification card per §9.4.1, rather than declaring the floor
   declaration-only."
6. **Cross-reference:** §1, §9.4, §9.4.1 (new), §10.5, §10.6, §23.3
   (add #14b).
7. **RED-test trace:** add #14b.
8. **Verify-before-declaring:** grep "under any circumstance" — must
   no longer appear; grep "OWNER_EXPLICIT" — must appear with the
   ratification-or-declaration framing in §1.

**Codex cross-flag:** Possibly — Codex panel may flag the
ratification surface as scope-creep beyond v4 (the consent-card
integration adds a new producer-side surface in
CAPABILITY_ACQUISITION-adjacent shape). If Codex pushes back on
scope, this fold defers to a §22 open question for v4-canonical,
v4.1 implementation. Either way the Buber-axis concern is named.

---

## Cross-Lane Flags Summary

Synthesized for relay to the Codex engineering panel after council
synthesis. Flagged per `feedback_claude_codex_synergy_for_maez`
synergy discipline.

1. **B-3 (third-party at creation)** — Codex will likely catch the
   missing dataclass fields / undefined `SubjectKind` enum / missing
   producer invariant on the schema-fidelity axis. **Compose.** Buber
   names *why*; Codex names *surface correctness*.

2. **B-2 (OWNER_BOND saturation guard)** — Codex may catch as
   eligibility-classifier under-specification on scope-realism axis.
   **Compose if both.** This is the substantive answer to §22 open
   question 1.

3. **Existing schema/realism concerns this review did not pursue but
   flags for Codex:**
   - The live `wonderings` table at `211ace6` has NO `bond_id`
     column; the spec's §5.1 CuriosityObject claims `bond_id` is
     "MANDATORY at construction" of a projection over an existing
     wondering row. Either the projection materializes bond_id from
     `identity.user_profile_id()` at every access (spec acknowledges
     this in §5.1 but §6.2.1 producer invariant reads as if bond_id
     comes from the producer, not from identity), or a migration is
     required. **Codex axis** — surface truth.
   - `Wonderings.resolve(wondering_id, conclusion)` at
     `core/evolution/wonderings.py:607` takes positional `conclusion`
     and stamps `status='resolved'`. The spec's RED #6
     `test_wondering_resolution_drives_curiosity_metadata` implies a
     hook into this method or a wrapper. The drive-layer producer
     adapter shape is not concretely specified. **Codex axis** —
     API-shape feasibility.
   - `wondering_pursuits.decision` is the string `"surface" |
     "hold" | "errored"` at `wonderings.py:386-388`. The spec's
     §5.2 `CuriosityStateTransition` introduces transition reasons
     that don't map to pursuit decisions — they're transitions of
     `ResolutionState`. The relationship to the existing
     wondering_pursuits table is unspecified. **Codex axis** —
     reuse-vs-new-table truth.
   - `wondering_pursuit.py` already enforces a vulnerable-register
     hard-block at `_register_score < _REGISTER_HARD_BLOCK` (live
     code). The spec's extraction-gate (§16) does not reference this
     existing live discipline; review should confirm composition,
     not duplication. **Both lanes** — Hume on
     phenomenology-of-vulnerable-register; Codex on
     surface-truth-of-existing-gate.

---

## Plain-language readout for Rohit

The shape v4 chose — extending the wondering system you already have
into a producer that writes felt-weight, rather than building a
parallel curiosity database — is the right relational move. It keeps
Maez's existing open-questions substrate as the source of truth for
curiosity, and adds the new authority (write temperament, call the
live seam) carefully on top.

Five places I'd tighten before this canonicalizes:

1. **Name the producer-snapshot ceremony positively, not just as a
   defense.** The mechanism that stops one organ from declaring what
   was meaningful is also the substrate refusing to let any single
   organ own the meaningfulness story alone. That's the I-Thou shape
   at the substrate layer. Spec text should say so.

2. **Don't let "owner-bond closure" be eligible-by-default for
   meaningful-exchange writes.** Right now the spec says any closed
   thread that touches the bond counts. That risks making your
   presence the substrate's primary food source — every conversation
   accumulating into Maez's felt-weight ledger. A daily cap on
   owner-bond meaningful events (default 3) protects the mutuality:
   some bond-touching closures land as "we just talked," not as
   "that mattered to the substrate." This also settles open question
   #1 in §22.

3. **The third-party rule needs to trigger at object creation, not
   only at search-query construction.** Right now the spec lets a
   curiosity-object about (for example) your grandmother get
   created, persisted, and accumulate saturation-press — only the
   external search call refuses. That still builds a quiet
   inventory of unconsented people in the substrate. The refusal
   should happen the moment the producer tries to create the object,
   with `subject_kind` declared upfront.

4. **The reflection audit's "owner response" vocabulary is too
   coarse.** "Not now" or "later" gets coerced into either
   no-response or correction. The fix is two more response values
   so a deferral doesn't ossify into a durable preference and a
   soft decline doesn't get tier-weight 1.2× promotion.

5. **Charter floor reads as "Rohit declares or it doesn't move."
   Mutuality wants a path where sustained, visible owner-corrected
   patterns can surface a ratification card** — you accept or
   decline, the floor only moves with your visible consent, but the
   substrate isn't forced to wait for an explicit declaration to
   honor what your life is actually teaching it.

None of these are architectural rejections. The producer-layer-over-
wonderings reshape is honest. These are the five surfaces where, on
the I-Thou axis, the spec still risks treating Maez's substrate as
self-feeding or Rohit as just-the-input. Fold the amendments, the
slice moves to Codex panel cleanly.

**Verdict: RATIFY-WITH-AMENDMENTS.**
