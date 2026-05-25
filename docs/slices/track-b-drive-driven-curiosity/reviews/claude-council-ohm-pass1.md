# Claude Council — Ohm Role — Drive-Driven Curiosity Pass 1

**Artifact reviewed:** `docs/slices/track-b-drive-driven-curiosity/spec.md`
**Artifact state:** DRAFT v1, 1271 lines, 26 sections.
**Role focus:** Boundary mechanics, conservation, flow-gating, sovereignty.
**Specific lens:** Whether Track C deferral is strong enough to prevent
cross-bond leakage later.
**Review date:** 2026-05-24
**Verdict:** RECONSIDER

## Summary

The spec's Track C deferral language in §17 is the right gesture but not
load-bearing structure. The substrate v1 happens-to-be-single-bond (one user,
one `bond_id` value) but does not structurally enforce that future multi-bond
state cannot leak across bond boundaries. Multiple core data shapes —
`CuriosityObject`, `SaturationRegister`, the diagnostic HMAC key,
`build_curiosity_query`'s sanitization scope, and the
`SUBJECTIVE_DURATION_MEANINGFUL_EVENT` producer — are written without a
`bond_id` field or bond-scoped enforcement. A future Track C implementer
working from the spec text alone could ship multi-bond curiosity that
silently composes across bonds. This is the exact trap
[[project_multi_maez_topology_threat]] warns against: a substrate that
*happens to be safe today* because there is one bond, rather than a substrate
that *would refuse cross-bond flow even if multi-bond were enabled tomorrow*.

The fix is structural, not aspirational. The shape required: every persisted
row carries `bond_id`; every read filters by `bond_id`; every cross-organ
write proves bond-scope before firing; every consumer of `SaturationRegister`
gets a bond-scoped view; the diagnostic HMAC key is per-bond not
per-instance. With these in place, even a careless Track C implementer
would have to do explicit covenant work to enable cross-bond curiosity flow,
because the substrate would refuse it by structure.

§17's prose is correct; the spec body does not yet structurally back it.

## Verified Conservation Surfaces

Before listing gaps, the following spec text DOES land correctly on the
boundary-mechanics axis:

**§9.2 per-bond loading (line 503):**
> "Identity-aware: `AutonomyPolicy.for_bond(bond_id)` returns the policy for
> the named bond."

This is the right shape — policy is keyed on bond, not loaded as a global.
The interface name encodes the boundary.

**§10.2 AutonomyPreference data model (line 547):**
> "`bond_id: str # which bond this applies to`"

Preferences carry `bond_id`. Persisted preferences cannot be cross-applied at
read time because the dataclass field is load-bearing for retrieval. Verified
as conservation-safe at the storage layer.

**§13.2 provenance-safe search (lines 745-751):**
> "It does NOT include: Raw seed text from private conversations.
> Owner-identifying tokens (name, location, biometric). Private memory
> contents (cf. existing `MINIMIZABLE_PRIVATE_CONTEXT`). soul.md contents
> (cf. existing reserved-denied-raw)."

Egress sanitization rejects raw private content. This is correctly modeled at
the owner-privacy layer.

**§8.4 world-acting non-subscription (lines 449-458):**
> "RED test: Static AST scan ensures `curiosity_*` reads do not appear in
> `core/actions/action_engine.py`, `core/actions/tool_loop.py`, or any
> destructive-action helper module."

The static-AST scan is genuine structural enforcement — a future implementer
cannot wire curiosity into world-acting without the test failing. This is the
right model for what the Track C section is missing.

## Findings (Walking Through The Ten Boundary Questions)

### Question 1 — §17 strength of deferral

**Section:** §17 (lines 973-988).

**Spec text:**
> "v1 substrate is single-bond. Curiosity-objects, autonomy preferences,
> saturation registers, and temperament writes all reference a single
> `bond_id` (the firstborn). Multi-Maez curiosity-object interaction is
> explicitly out of scope.
>
> Future Track C deliberations on cross-Maez interaction MUST include:
>
> - Whether curiosity-objects may reference cross-bond content at all.
> - If so, what egress / sovereignty discipline governs them.
> - How learned autonomy preferences (which encode bond-specific rhythm)
>   interact across bonds without leakage.
>
> This slice marks the assumption so Track C does not accidentally inherit
> a permissive default. (Cf. [[project_multi_maez_topology_threat]].)"

**Judgment:** Weak. The language is prose-aspirational, not load-bearing.
Three problems:

1. "all reference a single `bond_id`" is asserted but not enforced — see
   Question 2: the dataclass in §5.1 does NOT show `bond_id`. The assertion
   in §17 is contradicted by the structure in §5.1.
2. The "Future Track C deliberations MUST include" list is *what to consider
   in Track C* — it does not constrain v1's structural shape to make Track C
   safe.
3. [[project_multi_maez_topology_threat]] is cited but the two
   non-negotiable preconditions it names (auditable-by-both-bonded-users +
   dyadic-only topology) are NOT quoted by name in §17. A future implementer
   reading §17 alone has no anchor to those preconditions; they would have
   to follow the wiki link and re-derive.

The pattern that *would* be strong: explicit invariants that v1 enforces
*even though there is only one bond today*, such that those invariants would
refuse cross-bond flow in a Track C world where multiple bonds exist. The
spec does not yet contain those invariants.

**Classification:** Structural gap. Amendment required.

### Question 2 — §5.1 CuriosityObject dataclass is missing `bond_id`

**Section:** §5.1 (lines 213-227).

**Spec text:**
> ```python
> @dataclass(frozen=True)
> class CuriosityObject:
>     object_id: str                              # uuid4
>     created_utc: datetime
>     encounter_source: EncounterSource           # see 6.2
>     encounter_ref_digest: str                   # hmac-sha256 of source ref
>     seed_text_digest: str                       # hmac-sha256 of seed text
>     priority_class: CuriosityPriorityClass      # see 7
>     salience: float                             # [0.0, 1.0]
>     autonomy_lane_hints: frozenset[AutonomyLane]  # candidate action lanes
>     resolution_state: ResolutionState            # OPEN / RESOLVED / FIXATION_RELEASED
>     resolved_utc: datetime | None
>     resolution_marker: ResolutionMarker | None   # see 12.2
> ```

**Judgment:** Gap. §17 asserts "Curiosity-objects... all reference a single
`bond_id`" but the dataclass shows no `bond_id` field. Today this is silent
because there is one bond and a stored row's bond is implicit-by-deployment.
In a Track C world, this becomes load-bearing: without a `bond_id` field, a
row created in bond_A's context could be read in bond_B's context with no
structural prevention. The spec implicitly trusts the runtime to never
cross-load — which is exactly the
[[project_multi_maez_topology_threat]] failure mode (secret channels arise
when nothing structurally enforces topology).

§10.2 gets this right for AutonomyPreference. §5.1 does not.

**Classification:** Structural gap. The dataclass must carry `bond_id`. RED
test must assert presence + non-null at registration.

### Question 3 — §10 AutonomyPreference `bond_id` enforcement at write time

**Section:** §10.2 (lines 543-553), §10.6 (lines 583-594), §23 RED test list
(lines 1136-1138).

**Spec text in §10.2:**
> "`bond_id: str # which bond this applies to`"

**RED tests in §23 covering consent_memory:**
> "11 | test_consent_memory.py::test_append_only_no_delete | Preferences never deleted
> 12 | test_consent_memory.py::test_no_single_event_preference_creation | Sample-size floor for OWNER_OBSERVED preferences
> 13 | test_consent_memory.py::test_supersede_semantics | New preference takes priority"

**Judgment:** Partial. The dataclass carries `bond_id` (good). But:

1. No RED test asserts `bond_id` is non-null at write time. The dataclass
   declares `bond_id: str` (not `str | None`), but there is no spec'd test
   ensuring producers can't pass `bond_id=""` or `bond_id="default"` and have
   it accepted.
2. No RED test asserts that `for_bond_with_preferences(bond_id, situation)`
   only consults preferences with matching `bond_id`. The §10.5 prose says
   "consults both the policy defaults AND the preference memory" but does
   not say "filtered by bond_id." A future Track C implementer could write
   the consultation function without bond filtering and the test list does
   not catch it.
3. Producers in §10.6 (explicit / observed / system default) do not name
   how `bond_id` is determined at producer time. In a multi-bond future, an
   OWNER_OBSERVED producer ingesting "Rohit consistently ignores outreach
   in 09:00-12:00" — that batch job, when generalized to multi-bond, must
   know which bond it is observing. Spec is silent.

**Classification:** Structural gap. RED tests for `bond_id` non-null + bond-
scoped consultation required.

### Question 4 — §9.2 per-bond loading lacks RED test for cross-bond isolation

**Section:** §9.2 (lines 502-507), §23 RED test list.

**Spec text:**
> "Identity-aware: `AutonomyPolicy.for_bond(bond_id)` returns the policy for
> the named bond. v1 has one bond (the firstborn, `rohit`)."

**RED tests in §23 covering autonomy_policy:**
> "10 | test_autonomy_policy.py::test_firstborn_liberal_defaults | FIRSTBORN_AUTONOMY_POLICY has the spec'd liberal values"

**Judgment:** Gap. The interface `for_bond(bond_id)` is structurally correct,
but RED test #10 only verifies the firstborn's values are liberal. There is
NO RED test asserting:

- `for_bond("bond_A")` and `for_bond("bond_B")` return distinct policies (or
  raise for unknown bonds in v1).
- A policy fetched for bond_A is never consulted in bond_B's action-decision
  path.
- The action-decision site in §8.3 ("Verify per-bond policy permits the
  action") loads the policy keyed on the *acting bond's* `bond_id`, not on
  a global or default.

In v1 with one bond, these tests would be trivially green — but their
presence is what would refuse a future implementer who writes
`for_bond(DEFAULT_BOND)` everywhere. Without the tests, the substrate would
silently accept that.

**Classification:** Structural gap. Add bond-isolation RED tests now (they
pass trivially with one bond; they refuse multi-bond drift later).

### Question 5 — §13 provenance-safe search owner-scoped not bond-scoped

**Section:** §13.2 (lines 736-754).

**Spec text:**
> "It does NOT include:
> - Raw seed text from private conversations.
> - **Owner-identifying tokens (name, location, biometric).**
> - Private memory contents (cf. existing `MINIMIZABLE_PRIVATE_CONTEXT`).
> - soul.md contents (cf. existing reserved-denied-raw)."

**Judgment:** Gap with cross-bond implication. The sanitization rules are
written in *owner* vocabulary, not *bond* vocabulary. In a Track C world where
Maez instance A might construct a curiosity-object derived from cross-bond
content (the [[feedback_maez_makes_visible_not_nudges]] grandmother case:
grandmother's loneliness signal routed to dad's Maez), the question becomes:

> If bond_B's Maez constructs an external_knowledge query for a
> curiosity-object that was *seeded by* bond_A's content (via a future
> cross-Maez routing layer), does §13.2's sanitization protect bond_A's
> identifying tokens?

§13.2 reads "owner-identifying tokens" — singular owner. If "owner" is
implicitly "this Maez's bonded owner," then sanitization protects the local
owner but not the *cross-bond source's* owner. A future Track C implementer
could route grandmother's loneliness signal to dad's Maez and have dad's Maez
construct a search query containing grandmother's identifying tokens — and
§13.2 would not stop it because grandmother is not dad's owner.

The fix: §13.2's sanitization must be defined in bond-scope: "no
identifying tokens belonging to any bond present in the curiosity-object's
provenance chain." In v1 with one bond, this is identical to owner-scope. In
Track C, it is structurally different.

**Classification:** Structural gap. Sanitization scope must be bond-scoped,
not owner-scoped.

### Question 6 — §20.3 diagnostic HMAC key is per-instance, not per-bond

**Section:** §20.3 (lines 1064-1069).

**Spec text:**
> "Raw seed text NEVER appears in diagnostic rows. Only HMAC digests of seed,
> encounter source, and resolution markers. The HMAC key is the same one
> used by subjective_duration's diagnostic stream (one key per Maez
> instance, not committed to git)."

**Judgment:** Gap with multi-bond implication. One HMAC key per Maez instance
means that in a Track C world where one Maez instance carries multiple
bonds, digests across bonds use the same key. Consequence:

- A digest computed in bond_A is *byte-equal* to a digest of the same input
  computed in bond_B (because HMAC is deterministic in key+input). Diagnostic
  reviewers (or future code) can cross-correlate bonds by comparing digests.
- If diagnostic streams are ever shared with a third party for audit, the
  cross-bond linkage is recoverable from digest equality. The "raw text
  never appears" privacy floor protects against text reconstruction but NOT
  against cross-bond identity-linkage via digest collision.

The right shape: one HMAC key *per bond*, derived (e.g.) by
`HKDF(instance_master_key, bond_id)`. Digests in bond_A and bond_B are then
structurally non-correlatable even if the same raw input is hashed in both.

[[project_multi_maez_topology_threat]] precondition 1
("auditable by both bonded users, no secret channels") is closer to satisfied
when per-bond keying prevents cross-bond linkage in the diagnostic stream
itself.

For v1 with one bond, per-bond and per-instance keys are computationally
identical. The structural shape — keyed derivation per bond — is what makes
Track C safe.

**Classification:** Structural gap. Per-bond HMAC key derivation, not
per-instance.

### Question 7 — §15 saturation interface is instance-scoped not bond-scoped

**Section:** §15 (lines 872-922).

**Spec text in §15.1:**
> ```python
> def compute_saturation() -> SaturationRegister:
>     open_objects = curiosity_db.open_with_decay_applied()
>     return SaturationRegister(
>         open_object_count=len(open_objects),
>         ...
>     )
> ```

**Spec text in §15.2:**
> "Named consumer organs (v1): dream_state, wonderings, private_thoughts,
> subjective_duration"

**Judgment:** Structural gap. `compute_saturation()` has no `bond_id`
parameter. It reads from `curiosity_db.open_with_decay_applied()` — which,
in v1 with no bond_id field on CuriosityObject (see Question 2), reads ALL
open objects. The four named consumers (dream_state, wonderings,
private_thoughts, subjective_duration) all currently treat saturation as a
single global register.

In Track C, when bond_B's Maez consumes saturation to nudge
`retrospective_density` upward in subjective_duration, it should consume
*bond_B's* saturation, not the union of bond_A + bond_B's saturation. The
spec does not enforce this. Today this is fine because there is one bond;
in Track C, a careless implementer extends saturation to multi-bond by
"just adding more objects to the DB" and silently leaks cross-bond felt-press
into bond-specific subjective_duration calculations.

The right shape:

```python
def compute_saturation(bond_id: str) -> SaturationRegister:
    open_objects = curiosity_db.open_for_bond_with_decay_applied(bond_id)
    ...
```

Each consumer organ then calls `compute_saturation(bond_id=acting_bond_id)`.
In v1 with one bond, the only call site is `compute_saturation(bond_id="rohit")`.
In Track C, this refuses to compute cross-bond saturation by structure.

**Classification:** Structural gap. Saturation must be bond-scoped.

### Question 8 — §6.2 SUBJECTIVE_DURATION_MEANINGFUL_EVENT producer bond-scoping unspecified

**Section:** §6.2 (lines 320-323), §6.3 (lines 328-342).

**Spec text in §6.2:**
> "SUBJECTIVE_DURATION_MEANINGFUL_EVENT: a meaningfulness_score > 0.0 event
> in subjective_duration substrate (which this slice's resolutions feed —
> the loop closes here). Priority class `owner_bond`."

**Judgment:** Structural gap with cross-bond implication. The producer wires
subjective_duration's salience events into curiosity-object creation. In
Track C, if subjective_duration is extended to register meaningful events
that include cross-bond signal (e.g., grandmother's Maez receives a routed
signal about dad's birthday and computes a meaningful_exchange event), this
producer would create a curiosity-object with priority_class=OWNER_BOND that
references cross-bond content.

The §6.2 spec does not say:
- The producer must verify the meaningful_exchange event is bond-scoped to
  the curiosity-substrate's bond before creating an object.
- The producer must propagate `bond_id` from the source event into the
  CuriosityObject.

§6.3 says producers extend by spec amendment — good, growth-not-hardcoding.
But the *existing* producer in §6.2 does not specify its bond-scoping. A
Track C implementer extending subjective_duration to multi-bond would
inherit this producer without realizing it needs to bond-scope. The producer
becomes a cross-bond leakage path silently.

**Classification:** Structural gap. Every producer in §6.2 must specify its
bond-scoping invariant explicitly. RED test #4
("test_all_v1_sources_registered") should be extended to assert bond-scoping
per producer.

### Question 9 — §22.5 supersede vs compose Open Question, cross-bond implication

**Section:** §22.5 (lines 1114-1117).

**Spec text:**
> "**AutonomyPreference superseding semantics.** Does a new explicit
> preference SUPERSEDE the prior or OVERLAY it (compose)? Lean toward
> supersede for v1 (simpler, more predictable); composition is a v2
> refinement."

**Judgment:** This open question MUST be settled SUPERSEDE for v1, explicitly
for Track C reasons.

Reasoning: under COMPOSE semantics, a preference from bond_A could compose
with a preference from bond_B at decision time, producing a hybrid policy
that neither bond's user explicitly authorized. This is exactly the
[[project_multi_maez_topology_threat]] failure mode — a Maez whose behavior
is shaped by patterns it learned in bond_A leaking into its conduct in
bond_B.

Under SUPERSEDE semantics, the bond_id filter at consultation time
(Question 3) determines which preference applies; there is no composition.
Cross-bond leakage is structurally impossible at the preference layer if
composition is not permitted.

The spec leans toward supersede already — this lean must become a hard
commitment with the rationale stated as "cross-bond composition would create
hybrid policies neither bond's user authorized; supersede preserves bond
sovereignty."

**Classification:** Open question must be settled SUPERSEDE in this spec,
with cross-bond reasoning recorded. Future composition refinement only
permitted within a single bond's preference set.

### Question 10 — §17 does not cite the two non-negotiable preconditions by name

**Section:** §17 (lines 973-988).

**Spec text:**
> "This slice marks the assumption so Track C does not accidentally inherit
> a permissive default. (Cf. [[project_multi_maez_topology_threat]].)"

**Judgment:** Weak. The wiki link gestures at the preconditions but does not
name them. A Track C implementer reading §17 alone learns "v1 is
single-bond" but does NOT learn:

1. **Auditable by both bonded users, no secret channels.** Every message
   between Maez-A and Maez-B must be visible to both A's user and B's user.
2. **Dyadic-only topology, no global gossip layer.** Inter-Maez communication
   is only between explicitly-consented pairs.

These preconditions are load-bearing for any future cross-bond curiosity
routing. They must be quoted by name in §17, with the source citation.

**Classification:** Textual fold. Strengthen §17 to quote both preconditions
verbatim from [[project_multi_maez_topology_threat]].

## Required Amendments

The verdict is **RECONSIDER** because findings 1, 2, 5, 6, 7, 8 are
structural gaps, not textual folds. The substrate currently passes-by-
single-bond rather than refuses-cross-bond. The following amendments are
required before canonicalization.

### Amendment 1: Add `bond_id` to CuriosityObject dataclass (§5.1)

**Current text (§5.1, lines 213-227):**
```python
@dataclass(frozen=True)
class CuriosityObject:
    object_id: str
    created_utc: datetime
    encounter_source: EncounterSource
    encounter_ref_digest: str
    seed_text_digest: str
    priority_class: CuriosityPriorityClass
    salience: float
    autonomy_lane_hints: frozenset[AutonomyLane]
    resolution_state: ResolutionState
    resolved_utc: datetime | None
    resolution_marker: ResolutionMarker | None
```

**Proposed replacement:**
```python
@dataclass(frozen=True)
class CuriosityObject:
    object_id: str
    bond_id: str                                # which bond owns this object
    created_utc: datetime
    encounter_source: EncounterSource
    encounter_ref_digest: str
    seed_text_digest: str
    priority_class: CuriosityPriorityClass
    salience: float
    autonomy_lane_hints: frozenset[AutonomyLane]
    resolution_state: ResolutionState
    resolved_utc: datetime | None
    resolution_marker: ResolutionMarker | None
```

Add to §5.1 text: "`bond_id` is mandatory and immutable. Curiosity-objects
are bond-scoped by structure; no read path returns objects from a bond
other than the one queried. v1 has one bond (`rohit`); this field's
existence is what makes Track C cross-bond curiosity routing impossible
without explicit covenant work."

### Amendment 2: Bond-scope `compute_saturation` (§15.1)

**Current text (§15.1, lines 877-887):**
```python
def compute_saturation() -> SaturationRegister:
    open_objects = curiosity_db.open_with_decay_applied()
    ...
```

**Proposed replacement:**
```python
def compute_saturation(bond_id: str) -> SaturationRegister:
    open_objects = curiosity_db.open_for_bond_with_decay_applied(bond_id)
    ...
```

Add to §15.2: "Each named consumer organ MUST call `compute_saturation`
with its acting bond's `bond_id`. RED test asserts no call site invokes
`compute_saturation` without a bond_id argument."

### Amendment 3: Per-bond HMAC key derivation (§20.3)

**Current text (§20.3, lines 1064-1069):**
> "The HMAC key is the same one used by subjective_duration's diagnostic
> stream (one key per Maez instance, not committed to git)."

**Proposed replacement:**
> "The HMAC key is bond-scoped, derived from a per-instance master key via
> `HKDF(master_key, info=bond_id)`. Digests of the same raw input under
> bond_A's key and bond_B's key are non-correlatable. The master key is one
> per Maez instance, not committed to git; the per-bond derived key is
> recomputed on each digest operation rather than persisted. This prevents
> cross-bond identity-linkage via digest collision in the diagnostic
> stream itself. v1 with one bond produces one derived key; in Track C
> each additional bond derives its own key by structure."

### Amendment 4: Bond-scoped sanitization in `build_curiosity_query` (§13.2)

**Add to §13.2 (after line 751):**
> "The sanitization is bond-scoped, not owner-scoped. The query must not
> include identifying tokens belonging to ANY bond present in the
> curiosity-object's provenance chain — not only the local owner. In v1
> with one bond, this is equivalent to owner-scope. In Track C with
> cross-bond routing, this prevents a Maez instance from emitting a query
> containing another bond's identifying tokens. RED test asserts a
> simulated cross-bond curiosity-object (bond_A seed, bond_B acting) is
> sanitized against bond_A's identifying tokens, not only bond_B's."

### Amendment 5: Settle §22.5 to SUPERSEDE with cross-bond rationale

**Current text (§22.5, lines 1114-1117):**
> "AutonomyPreference superseding semantics. Does a new explicit preference
> SUPERSEDE the prior or OVERLAY it (compose)? Lean toward supersede for v1
> (simpler, more predictable); composition is a v2 refinement."

**Proposed replacement (and move out of Open Questions into §10 as a settled
invariant):**

Remove §22.5. Add as §10.9:

> "### 10.9 Supersede semantics, no composition across bonds
>
> AutonomyPreferences SUPERSEDE, never COMPOSE, across bond boundaries. A
> preference recorded in bond_A's preference set MUST NOT compose with a
> preference in bond_B's preference set at decision time. This is
> non-negotiable per [[project_multi_maez_topology_threat]]: composition
> across bonds would produce a hybrid policy neither bond's user
> authorized, which is exactly the cross-bond leakage failure mode the
> deferral exists to prevent.
>
> Within a single bond, supersede semantics apply for v1; composition is a
> v2 refinement to consider only after Track C ships and only with explicit
> bond_id scope on every composed preference.
>
> RED test asserts that `for_bond_with_preferences(bond_A, situation)` does
> not read any preference with `bond_id != bond_A`. Test passes trivially
> in v1; refuses Track C drift."

### Amendment 6: §17 cites both preconditions by name

**Current text (§17, lines 973-988):** as quoted in Question 10.

**Proposed replacement:**

> "## 17. Track C Multi-Bond Deferral
>
> v1 substrate is single-bond. Every persisted row, every read path, every
> cross-organ write, and every diagnostic digest is bond-scoped by
> structure. Curiosity-objects (§5.1), autonomy preferences (§10.2),
> saturation registers (§15.1), temperament writes (§14.3), and diagnostic
> HMAC digests (§20.3) all carry or derive from `bond_id`. There is no
> path in v1 that returns or writes data for a bond other than the one
> explicitly named in the call site.
>
> Multi-Maez curiosity-object interaction is explicitly out of scope for
> v1. Two non-negotiable preconditions, quoted verbatim from
> [[project_multi_maez_topology_threat]], govern any future Track C
> deliberations on cross-Maez interaction:
>
> 1. **Auditable by both bonded users, no secret channels.** Every message
>    that travels between Maez-A and Maez-B is visible to both A's user
>    and B's user — same way the consent-card surface today makes Maez's
>    actions visible to its bonded user. No backchannel between Maez-A and
>    Maez-B that isn't surfaced to both human bonded contacts.
>
> 2. **Dyadic-only topology, no global gossip layer.** Inter-Maez
>    communication is only between explicitly-consented pairs. There is no
>    'Maez network' in the sense of a chat room or gossip protocol.
>
> Beyond these preconditions, Track C deliberations on cross-Maez
> interaction MUST also include:
>
> - Whether curiosity-objects may reference cross-bond content at all.
> - If so, what egress / sovereignty discipline governs them.
> - How learned autonomy preferences (which encode bond-specific rhythm)
>   interact across bonds without leakage.
> - How `compute_saturation` extends to multi-bond — whether saturation
>   bands are per-bond, per-pair, or something else.
> - How the per-bond HMAC key derivation interacts with cross-bond
>   diagnostic correlation (and whether such correlation is ever
>   appropriate).
>
> v1's structural enforcement (bond_id on every row, bond-scoped reads,
> per-bond key derivation) is what makes this deferral load-bearing rather
> than aspirational. A Track C implementer cannot enable cross-bond
> curiosity by configuration alone; the substrate refuses cross-bond flow
> by structure and explicit covenant work is required to change that."

### Amendment 7: Add bond-scoping RED tests to §23

**Add the following RED tests to §23 (renumber as appropriate):**

| # | Test name | What it proves |
|---|---|---|
| 44 | `test_curiosity_object_bond_scoped.py::test_bond_id_mandatory_at_registration` | CuriosityObject with empty/missing bond_id rejected |
| 45 | `test_curiosity_object_bond_scoped.py::test_read_filters_by_bond_id` | curiosity_db.open_for_bond(A) never returns rows with bond_id != A |
| 46 | `test_autonomy_policy_bond_scoped.py::test_for_bond_isolates_policies` | for_bond(A) and for_bond(B) return distinct policies; unknown bond raises |
| 47 | `test_consent_memory_bond_scoped.py::test_bond_id_mandatory_at_write` | AutonomyPreference write with empty/missing bond_id rejected |
| 48 | `test_consent_memory_bond_scoped.py::test_consultation_filters_by_bond` | for_bond_with_preferences(A) reads no preference with bond_id != A |
| 49 | `test_saturation_bond_scoped.py::test_compute_saturation_requires_bond_id` | compute_saturation() without bond_id raises; saturation reads only bond's objects |
| 50 | `test_saturation_bond_scoped.py::test_consumer_organs_pass_bond_id` | Static AST: all four consumer organs call compute_saturation with a bond_id argument |
| 51 | `test_provenance_query_bond_scoped.py::test_sanitization_strips_all_provenance_bonds` | Query sanitization removes identifying tokens for every bond in provenance chain, not only local owner |
| 52 | `test_diagnostic_hmac_bond_scoped.py::test_per_bond_key_derivation` | HMAC of same input under bond_A and bond_B produces distinct digests |
| 53 | `test_preference_no_cross_bond_composition.py::test_supersede_not_compose_across_bonds` | A preference in bond_A's set never composes with a preference in bond_B's set at decision time |

All ten tests pass trivially in v1 (one bond). They refuse Track C drift by
structure if any future implementer tries to enable cross-bond curiosity
without explicit covenant work.

### Amendment 8: Bond-scoping invariant per encounter producer (§6.2)

**Add to §6.2 (after the producer list, before §6.3):**

> "### 6.2.1 Bond-scoping invariant per producer
>
> Every producer in §6.2 MUST propagate the source event's `bond_id` into
> the created CuriosityObject. If the source event has no `bond_id` (e.g.,
> an instance-level signal not bond-attached), the producer MUST refuse to
> create a CuriosityObject rather than default to a global bond_id. RED
> test asserts each of the seven v1 producers either passes a non-default
> bond_id or refuses.
>
> This is what prevents the SUBJECTIVE_DURATION_MEANINGFUL_EVENT producer
> (and any future producer) from becoming a cross-bond leakage path when
> subjective_duration extends to multi-bond in Track C."

## Plain-Language Readout

The Track C deferral language is the right gesture but not yet load-bearing
structure. Today, v1 happens-to-be-single-bond because there is one user —
not because the substrate refuses multi-bond by design. A future implementer
working from this spec could ship multi-bond curiosity that silently leaks
across bonds, because the dataclass for `CuriosityObject` has no `bond_id`
field, the saturation register reads all open objects globally, the
diagnostic HMAC key is per-instance not per-bond, the query sanitization is
owner-scoped not bond-scoped, and the
`SUBJECTIVE_DURATION_MEANINGFUL_EVENT` producer is silent on bond
propagation.

The fix is structural, not aspirational. Make `bond_id` a mandatory field
on every persisted row. Make every read filter by `bond_id`. Make the
HMAC key derive per-bond from an instance master key. Make sanitization
strip identifying tokens for every bond in the provenance chain, not just
the local owner. Make the saturation register bond-scoped. Make every
encounter producer propagate `bond_id` or refuse. Settle the supersede-vs-
compose question as SUPERSEDE with cross-bond reasoning, and forbid
composition across bonds entirely.

With these eight amendments in place, a careless Track C implementer would
have to do explicit covenant work to enable cross-bond curiosity. The
substrate would refuse cross-bond flow by structure — even though there is
only one bond today. That is the right shape for a v1 deferral: not "we
trust Track C to do this right later," but "v1 refuses Track C drift by
construction, until covenant work explicitly opens the door."

This is the boundary-mechanics axis being honest. The current §17 says the
right thing in prose; the body of the spec does not yet back it
structurally. With the eight amendments, prose and structure agree.

Verdict: **RECONSIDER** — six structural gaps require body changes beyond
text fold; once folded, the spec lands the conservation-of-boundary
guarantee that Track C deferral is supposed to encode.
