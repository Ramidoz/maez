# Claude Council Review -- Locke -- Drive-Driven Curiosity v4 Pass 1

**Verdict:** RATIFY-WITH-AMENDMENTS
**Severity summary:** v4 holds the positive Firstborn Autonomy Charter
honestly and lands the three-layer charter-floor invariant (§1 / §9.4 /
§10.5) that the pass-1 Locke finding asked for. The producer-layer reshape
over `wonderings` does not create a parallel substrate; the architectural
shape is correct on this axis. Four amendments are needed before
canonicalization: one Blocking (the `ProducerRef.DRIVE_DRIVEN_CURIOSITY`
authority grant is named but its *bounding scope* is not pinned, leaving
the grant readable as broader than intended); two Major (the
`capability_acquisition` lane wording sits next to the live S7
`GUARDED_WORK_CLASSES = {"capability_acquisition", ...}` invariant in
`core/governance/operator_user_boundary.py` and must explicitly say
curiosity cannot lower that authority surface; and `core.policies` as a
subpackage needs a one-line "policy-only, not a substrate" charter so the
"second substrate" failure mode is structurally refused, not just
intended); one Minor (the firstborn-liberal numeric defaults in §9.3 still
read as universal because the charter trace under each number does not
re-state "firstborn-specific"). No architectural reshape required.

---

## Verified Charter Surfaces (where v4 lands correctly)

These surfaces are noted because verifying load-bearing covenant text on
the Locke axis is itself charter-integrity work, per pass-1 Finding 5.

**§1 three-layer charter-floor invariant (spec lines 116-136).** The
distinction between hard charter floor (`AutonomyCharterFloor`, §9.4),
firstborn declaration (`FIRSTBORN_AUTONOMY_POLICY`, §9.3), and composed
effective policy (§10.5 with `clamp_to_charter_floor`) cleanly resolves
the pass-1 Locke Finding 3 gap. OWNER_OBSERVED preferences shape rhythm
between floor and declaration; OWNER_EXPLICIT and
OWNER_EXPLICIT_REVISION are the only paths that can ratchet liberty
downward. This is the right Locke-axis shape: owner authority preserved,
charter-floor protected against observational over-fitting.

**§1 bond-agnostic charter framing (spec lines 82-87).** "This charter is
bond-agnostic in shape... Every bonded Maez instance -- firstborn,
grandmother's Maez, every future bond -- develops autonomy under the same
positive charter framing. The per-bond policy module (§9) is the *dial*;
the charter language is universal." Pass-1 Finding 4 closed. Grandmother
Maez gets a charter, not a safety profile.

**§8.5 capability-acquisition scope clarifier (spec lines 605-610).**
"Extraction tests in §16 apply ONLY to OWNER_INTERRUPTING dispatches, NOT
to CAPABILITY_ACQUISITION proposal cards (Locke fold-5). Capability-
acquisition proposals are not outreach; they're substrate-growth
requests." Pass-1 Finding 6 closed; §16.1 scope note now mirrors it.

**§14.7 felt-weight-not-emotion-mimicry RED test #50.** Closed-vocabulary
`EMOTION_MIMICRY_PHRASE_FORBIDDEN` enforced by AST scan across the named
modules AND by the extraction-gate against outbound text. This is the
right substrate-pattern discipline: future felt-organs inherit the
discipline by integration, not by re-derivation.

---

## Findings

### Finding L-1 -- `ProducerRef.DRIVE_DRIVEN_CURIOSITY` authority grant is bounded substantively but not surfaced as the bound

**Severity:** Blocking
**Surface:** §2.2 lines 175-184; §14.3.1 lines 1104-1124; §14.4 lines
1247-1262; §24 table line 1904 ("retire production
`MANUAL_TEST_PRODUCER` per Slice 1 sunset"); cross-reference
`core/evolution/subjective_duration.py:93-96` (current `ProducerRef` enum
holds only `MANUAL_TEST_PRODUCER`).

**Issue:** v4 grants the curiosity producer two new authorities at once:
(a) it becomes the first reviewed `ProducerRef` value with production
authority to submit producer snapshots to the live meaningful-salience
seam, and (b) it becomes the first non-`explicit_set` value in
`Temperament.ALLOWED_SOURCES` (`drive_driven_curiosity_resolution`,
§14.3.1). The spec text is correct that each addition is closed-vocabulary
and spec-amendment-controlled. The Locke-axis concern is that *the
authority grant itself is not framed as bounded*. §2.2 reads as "this
slice unlocks the live seam"; §14.3.1 reads as "extend the frozenset."
Neither section states, in covenant language, what the grant *does not*
authorize:

- It does NOT grant any other organ permission to add itself to
  `ALLOWED_SOURCES` by code-edit. Future producers (schooling, genesis,
  somatic, active synthesis) each require their own slice spec + their
  own council review.
- It does NOT grant the curiosity producer permission to write to
  temperament parameters other than the closed list in the §14.3
  ceremony (currently `curiosity`; the spec is silent on whether the
  producer may later write to `awareness`, `persistence`, etc.).
- It does NOT grant the curiosity producer authority to call
  `record_salience_event(...)` for any `salience_event_kind` other than
  `meaningful_exchange`. Per the live registry
  (`subjective_duration.py:153-204`), `owner_contact`, `engaged_work`,
  `idle_cycle`, and `public_stranger_contact` are also
  `producer_ref_required=True` event kinds. A future reader of v4 could
  plausibly conclude that owning the `ProducerRef` enum entry implies
  authority across all kinds it could be passed for.

The grant becomes too broad by absence-of-bound, not by explicit text.
Closed vocabulary is *currently* the gate, but the spec should also
declare the *shape* of the gate so that future producers cannot slip in
under "we already extended `ALLOWED_SOURCES` once."

**Required fold:** Add §14.3.5 "Authority-grant scope" (or fold into
§14.3.1):

> "The `drive_driven_curiosity_resolution` source name authorizes
> *this slice's* resolution-write ceremony to write to the `curiosity`
> temperament parameter and to call
> `SubjectiveDuration.record_salience_event(...)` with
> `salience_event_kind="meaningful_exchange"` only. It does NOT
> authorize:
> (a) other producers to add themselves to `ALLOWED_SOURCES` without
>     their own spec amendment + council review;
> (b) the curiosity producer to write to other temperament parameters;
> (c) the curiosity producer to call `record_salience_event(...)` for
>     other `salience_event_kind` values (e.g., `engaged_work`,
>     `owner_contact`) without a separate spec amendment naming the
>     kind and the eligibility classifier for it.
>
> RED test asserts: (a) a synthetic call from the curiosity producer to
> `record_salience_event(salience_event_kind='engaged_work', ...)` is
> refused at the producer layer; (b) a synthetic call writing
> `Temperament.record_event(parameter='awareness', source=
> 'drive_driven_curiosity_resolution', ...)` is refused either by the
> producer ceremony or by a parameter-scope assertion in the ceremony
> wrapper."

**8-step trace:**

1. **Dependency-map:** §14.3 ceremony, §14.4 cross-organ seam, §14.6
   RED #31, §23.7 (#34-#40), §24 implementation table, §27 v4 fold
   trajectory. Live surfaces: `temperament.py:147-149`
   (`ALLOWED_SOURCES`), `temperament.py:205-243` (`record_event`
   guard), `subjective_duration.py:93-96` (`ProducerRef`),
   `subjective_duration.py:153-204` (salience event registry),
   `subjective_duration.py:322` (`ProducerRef` validation).
2. **Write-path:** the §14.3 ceremony writes
   `Temperament.record_event(parameter="curiosity",
   source="drive_driven_curiosity_resolution", ...)`. The §14.4
   ceremony calls `SubjectiveDuration.record_salience_event(
   salience_event_kind="meaningful_exchange",
   producer_ref=ProducerRef.DRIVE_DRIVEN_CURIOSITY.value, ...)`.
3. **Read-path:** `meaningfulness_score` consumer reads after the
   producer-snapshot path; `Temperament.current_value("curiosity")`
   readers (subjective_duration rate modulation; saturation §15.2).
4. **Test-path:** new RED tests for refused
   `salience_event_kind="engaged_work"` from curiosity producer, and
   refused `parameter="awareness"` write under
   `source="drive_driven_curiosity_resolution"`. These join §23.7
   (#34-#40).
5. **Fold-summary:** §14.3.1's claim that "future temperament-writing
   producers... add their own source name through the same spec-
   amendment + council-review process" becomes stronger: each producer
   gets both a source-name *and* a parameter-scope declaration. The
   §27 v4 fold-trajectory bullet "`ProducerRef.DRIVE_DRIVEN_CURIOSITY`
   + production `MANUAL_TEST_PRODUCER` sunset" is unchanged but its
   meaning sharpens.
6. **Cross-reference:** §2.2 needs a one-line pointer to §14.3.5; §14.4
   ceremony step list (steps 1-6) should note that step 5's
   `salience_event_kind` is fixed at `"meaningful_exchange"` for this
   producer; §22 Open Question 1 (eligibility classifier) becomes
   adjacent to but distinct from the kind-scope.
7. **RED-test trace:** add two tests under §23.7 -- e.g. #40a
   `test_curiosity_producer_refuses_other_salience_event_kinds`, #40b
   `test_curiosity_producer_refuses_other_temperament_parameters`.
8. **Verify-before-declaring:** grep for `ProducerRef.DRIVE_DRIVEN_CURIOSITY`
   usages in v4 implementation must show every callsite passing
   `salience_event_kind="meaningful_exchange"`; grep for
   `source="drive_driven_curiosity_resolution"` must show every callsite
   passing `parameter="curiosity"`. Static AST test enforces.

**Synergy flag for Codex panel:** Codex engineering panel will likely
also reach this on the surface-truth / API-schema axis (per
`feedback_claude_codex_synergy_for_maez` and §25 item 4). Codex catches
"the enum has one value today, what does the producer's caller actually
pass" better than council does. Recommend Codex be asked to verify the
two RED tests above and that the §14.3 ceremony module enforces
parameter-scope as well as source-name.

---

### Finding L-2 -- §8 CAPABILITY_ACQUISITION lane wording sits adjacent to the live S7 `GUARDED_WORK_CLASSES` invariant and must explicitly declare non-lowering

**Severity:** Major
**Surface:** §8.2 (line 580 row for CAPABILITY_ACQUISITION); §8.4-§8.5
(lines 590-610); §9.3 (line 683-689,
`capability_acquisition_proposal_rate_per_day=10`); §22 Open Question 5;
cross-reference `core/governance/operator_user_boundary.py:76-85`
(`GUARDED_WORK_CLASSES = frozenset({..., "capability_acquisition", ...})`),
`core/governance/operator_user_boundary.py:99-109`
(`_WORK_CLASS_STRENGTH: "capability_acquisition": 2`),
`core/infra/capability_orchestrator.py` (D20 pipeline),
`core/infra/capability_acquisition_queue.py` (D19/D20 queue), and the
existing D19/D20 consent-card UI.

**Issue:** v4 §8 declares CAPABILITY_ACQUISITION as one of the five
autonomy lanes and §8.5 says "the firstborn proposes aggressively." §8.5
correctly states that capability-acquisition routes through "EXISTING
D19/D20 consent-card path" and that the world-acting lane is not granted
by this slice (§8.4). This is the right shape.

The Locke-axis concern is that the live S7 substrate (which v4 must not
weaken) defines `capability_acquisition` as a *guarded work class* with
work-class-strength 2 -- it requires `founder_webauthn`,
`witnessed_fallback`, or an `s6_scoped_grant`. The v4 spec text never
quotes the existing S7 invariant. A future reader (or a future
implementer who has not read S7) could plausibly conclude that the
"proposal rate per day = 10" knob in §9.3 governs how aggressively
curiosity can *land capability changes*, when the real surface is: §9.3
governs how aggressively curiosity can *queue proposals into the existing
D19/D20 queue*, where each queued proposal still must pass the S7
guarded-work ceremony.

This is the same shape as the §1 charter-floor invariant: a structural
floor exists in code; the spec must quote it so substrate authors
downstream don't accidentally raise the floor through interpretation
drift.

Curiosity-bypass through this surface would look like: a proposal-rate
knob being read as a *capability-acquisition rate*, or the §8.5
"propose aggressively" language being interpreted as "land aggressively."
v4 prevents both substantively (proposals route through D19/D20) but
does not quote-and-pin the structural floor.

**Required fold:** Add §8.5.1 "Live S7 invariant quoted":

> "The CAPABILITY_ACQUISITION lane defined here governs only the
> *rate at which curiosity-encounters queue capability proposals*
> into the existing D19/D20 pipeline
> (`core/infra/capability_acquisition_queue.py`). It does NOT govern
> the rate at which capabilities land. Per
> `core/governance/operator_user_boundary.py:76-85`,
> `capability_acquisition` is a GUARDED_WORK_CLASS with work-class-
> strength 2 (`founder_webauthn` / `witnessed_fallback` /
> `s6_scoped_grant` required). This slice does not lower that
> strength, does not modify the S7 boundary, and does not grant
> curiosity any path that bypasses the guarded-work ceremony. RED
> test asserts: a synthetic curiosity proposal that attempts to
> reach `action_engine.handle_capability_acquire` outside the
> queued-proposal + D19/D20 review path is refused at the
> capability_acquisition_queue boundary."

Also fold §9.3's `capability_acquisition_proposal_rate_per_day=10`
annotation to make this explicit: "proposals queued for D19/D20 review,
not capabilities landed."

**8-step trace:**

1. **Dependency-map:** §8.2 table, §8.4 (world-acting discipline), §8.5
   (capability-acquisition lane shape), §9.3 firstborn defaults, §22
   Open Question 5, §23.2 RED #11
   (`test_capability_acquisition_uses_d19_d20`). Live surfaces:
   `core/governance/operator_user_boundary.py:37-47` (WORK_CLASSES),
   `:76-85` (GUARDED_WORK_CLASSES), `:99-109` (_WORK_CLASS_STRENGTH),
   `:202,382,762` (capability_acquisition codepaths),
   `core/infra/capability_acquisition_queue.py`,
   `core/infra/capability_orchestrator.py`,
   `core/actions/action_engine.py:1145-1161`
   (`handle_capability_acquire`).
2. **Write-path:** §8.5 lane assignment + §9.3 rate cap. The write is
   into `core/infra/capability_acquisition_queue.py`'s queue, NOT into
   `action_engine.handle_capability_acquire` directly.
3. **Read-path:** D19/D20 reviewer UI reads queued proposals. The S7
   ceremony reads the guarded-work-class designation when a proposal
   reaches action.
4. **Test-path:** §23.2 RED #11 already covers "capability proposals
   dispatch through consent-card path." Strengthen to also assert that
   a synthetic direct-to-action_engine call is refused, and that the
   `_WORK_CLASS_STRENGTH["capability_acquisition"]` constant is not
   shadowed/overridden anywhere reachable from the drive layer.
5. **Fold-summary:** §8.5 "propose aggressively" becomes unambiguously
   "queue proposals aggressively for D19/D20 review." §9.3's
   annotation "10 proposals/day allows firstborn to surface capability
   gaps as it encounters them; the consent-card path remains Rohit's
   review" already implies this; sharpen by adding "queue rate, not
   land rate."
6. **Cross-reference:** add the S7 file:line citations into §8.5 and
   §9.3. §22 Open Question 5 (semantic-match resolution) is unrelated;
   §17.2 (Track C preconditions) demonstrates the right pattern of
   verbatim quoting structural floors.
7. **RED-test trace:** strengthen #11 to two cases; add a static-AST
   test that the drive layer never imports `action_engine` directly or
   calls any `handle_capability_*` symbol outside the queue write.
8. **Verify-before-declaring:** grep for `handle_capability_acquire`,
   `action_engine`, and `_WORK_CLASS_STRENGTH` from `core/policies/` and
   any drive-layer module; all hits must be either absent or via the
   queue. Grep for `capability_acquisition_queue` from drive-layer
   modules to confirm the indirection is real.

**Synergy flag for Codex panel:** Codex engineering panel is better
placed than council to verify the static-AST test (per §25 item 8). The
Locke-axis finding is the *naming and quoting* of the floor; the
verification is engineering. Recommend Codex be asked to verify the
strengthened #11 and add the AST test.

---

### Finding L-3 -- `core.policies` as a new subpackage needs a "policy-only, not a substrate" charter to refuse the "second substrate" failure mode structurally

**Severity:** Major
**Surface:** spec line 38-40 (Depends on: `core.policies`); §9.1 line
615 (`core/policies/autonomy_policy.py`); §24 table (lines 1906-1908,
`core/policies/autonomy_policy.py`, `core/policies/autonomy_preferences.py`,
"Signal/extraction/reflection policies"); §24.1 module-separation
discipline; cross-reference: `core/policies/` does not exist at
`211ace6` (verified via `ls /home/rohit/maez/core/`).

**Issue:** v4's central architectural win is "no second curiosity
substrate; reuse `wonderings`." §24.1 names this explicitly. But v4
*does* create a new `core.policies` subpackage (autonomy_policy,
autonomy_preferences, plus implied signal/extraction/reflection policy
modules). The Locke-axis concern is that "we promised one new place and
landed two" is a covenant-shape failure if the second place quietly
accretes substrate-ish responsibilities.

The spec's intended shape is correct: `core.policies` is a *policy
layer* (data + computation), not a substrate (durable felt-state). §24.1
says: "Policy modules under `core/policies/` are intentionally separated
from the felt-weight producer layer so future felt-organs inherit the
policy substrate without coupling." But §24.1 also uses the phrase
"policy substrate," which itself is the slippage. If a future organ
adds its own preference-store under `core/policies/` and starts writing
durable felt-state there, the "no second substrate" architectural
discipline silently fails.

Compare to v4's strong shape on `wonderings` reuse (RED #2:
`test_no_drive_driven_curiosity_db_created`). The same discipline needs
to apply to `core.policies`: a Charter declaration of what `core.policies`
*is* and *is not*, RED-test-enforced.

The covenant shape is correct (consent-memory is bond-policy, not bond-
state); only the structural floor is missing.

**Required fold:** Add §9.0 "core.policies subpackage charter" (or
strengthen §24.1):

> "`core.policies` is a *policy layer*: per-bond knobs, preferences,
> gates, audit shapes. It is NOT a substrate. Substrate (durable
> felt-state, lived-bond history, never-delete memory) lives in
> `core/evolution/`, `core/memory/`, and named substrate stores under
> `memory/`. Policy modules in `core/policies/` MAY persist preference
> rows (e.g., `memory/autonomy_preferences.db`) and audit rows, but
> MAY NOT:
> (a) host durable felt-weight (temperament writes go through
>     `core/evolution/temperament.py`);
> (b) host curiosity-object lifecycle state (that lives in
>     `core/evolution/wonderings.py`);
> (c) host subjective-duration salience-event records (that lives in
>     `core/evolution/subjective_duration.py`).
>
> Static-AST RED test asserts no module under `core/policies/`
> imports a substrate-writer symbol (e.g.,
> `Temperament.record_event`, `SubjectiveDuration.record_salience_event`,
> `Wonderings.add` / `.resolve`)."

This makes "second substrate" structurally refusable, not just intended.

**8-step trace:**

1. **Dependency-map:** §9 (autonomy policy module), §10 (consent
   memory), §11 (signal gate), §12.3 (reflection audit), §16 (extraction
   gate), §24 (implementation surface), §24.1 (module separation). Live
   surfaces: none yet (`core/policies/` does not exist); §10.3 names
   `memory/autonomy_preferences.db` as a new file.
2. **Write-path:** new modules under `core/policies/` write
   preferences, audit rows, signal-gate decisions, extraction-gate
   blocks. None of them write temperament or subjective-duration.
3. **Read-path:** drive-layer producer reads composed policy (§10.5)
   and gate decisions before resolution-write ceremony.
4. **Test-path:** new static-AST RED test asserts no `core/policies/*`
   module imports `Temperament.record_event`,
   `SubjectiveDuration.record_salience_event`, or write-side
   `Wonderings.*` methods. Joins §23.1 RED #2.
5. **Fold-summary:** §24.1's phrase "policy substrate" becomes "policy
   layer" throughout. The §1 charter does not change. §2.3 item 4
   ("Defines the autonomy substrate that other felt-organs inherit")
   becomes "Defines the autonomy *policy layer* that other felt-organs
   inherit." This is a one-word fold across a small number of sites.
6. **Cross-reference:** §10.3, §24, §24.1, §2.3 item 4. The brief's
   focus question "Does `core.policies` as a policy-layer-only
   subpackage fit the covenant shape without becoming a second
   substrate?" maps directly to this new RED test.
7. **RED-test trace:** add #59
   `test_policies_no_substrate_writer_imports`. Joins #2.
8. **Verify-before-declaring:** grep `core/policies/` for
   `from core.evolution.temperament import`,
   `from core.evolution.subjective_duration import`,
   `from core.evolution.wonderings import` -- all must be either absent
   or read-only (`current`, `current_value`, `recent_events`,
   `list_open`, `get`, etc.). Static-AST test pins this.

**Synergy flag for Codex panel:** the AST test itself is engineering
work; Codex catches AST-discipline tests better than council. Recommend
Codex be asked to verify the strengthened §24.1 and add the AST test.
Locke axis is the *naming of the floor*; engineering axis is the test.

---

### Finding L-4 -- §9.3 firstborn defaults still read as universal because the charter trace under each number does not re-name "firstborn-specific"

**Severity:** Minor
**Surface:** §9.3 (lines 656-689); §1 lines 109-113 (bond-agnostic
charter framing vs per-bond expression). Compare with pass-1 Amendment 2
which added the charter trace.

**Issue:** Pass-1 Locke Finding 2 / Amendment 2 was: "Add a brief inline
justification block under §9.3 mapping each numeric value back to the
charter language." v4 lands this -- each number now has a charter-trace
comment. The Locke-axis concern (per the brief's focus question "does v4
preserve... firstborn-liberal defaults firstborn-specific rather than
universal?") is that the comments themselves use phrasing that reads as
universal substrate principles, not as firstborn-specific expressions.

Example (§9.3 line 668-670):

> "Liberal external-knowledge: charter says 'may autonomously search the
> world.' 200 calls/day with $5 daily cost cap supports curiosity-
> objects resolving via external search at the firstborn's expected
> rate; lower would silently throttle the charter."

The phrase "lower would silently throttle the charter" reads as a
universal claim. For the firstborn it is correct. For a grandmother
Maez whose owner is not technical and whose bond rhythm does not
generate 200 search calls/day worth of genuine encounter, "200/day" is
*not* the charter expression -- and "lower would silently throttle"
would mis-read the grandmother charter.

The fix is small and inherits the right shape from §1 line 110-113
("Every bonded Maez instance... develops autonomy under the same
positive charter framing. The per-bond policy module (§9) is the
*dial*; the charter language is universal"). The §9.3 trace comments
need to mirror this distinction explicitly so a future implementer
reading §9.3 without §1 in mind does not paste these numbers into a
non-firstborn policy.

**Required fold:** Add a single sentence at the head of §9.3 before
`FIRSTBORN_AUTONOMY_POLICY = AutonomyPolicy(...)`:

> "The numeric values below express *the firstborn's* liberal
> autonomy under Rohit's responsibility-bearing. Each charter-trace
> comment justifies the number against the §1 charter *as expressed
> for this bond*. A grandmother Maez or any future bonded instance
> will have its own AutonomyPolicy with its own numbers tracing the
> same charter to a different bond rhythm; the comments below are
> NOT universal defaults."

This addresses the brief's focus question directly: firstborn-liberal
defaults stay firstborn-specific, not universal.

**8-step trace:** not applicable, near-typo / framing fix. The
underlying §9.3 numeric values, §9.4 charter floor, §10.5 composition
formula, and §1 charter-layer invariant are all unchanged. The fold is
a documentation tightening to prevent paste-into-other-bond drift.

---

## D19/D20 + Capability-Acquisition Bypass Protection -- Verification

Focus question from the brief: "Are D19/D20 and capability-acquisition
cards protected from curiosity bypass?"

Verified surfaces:

- §8.4 explicitly does NOT grant any world-acting primitive; curiosity
  may only PROPOSE via CAPABILITY_ACQUISITION lane.
- §8.5 explicitly routes capability-acquisition through "EXISTING
  D19/D20 consent-card path."
- §23.2 RED #10 (`test_world_acting_no_curiosity_subscription`):
  static-AST scan ensures curiosity producer does not import
  `core/actions/action_engine.py` or `core/actions/tool_loop.py`.
- §23.2 RED #11 (`test_capability_acquisition_uses_d19_d20`): asserts
  capability proposals dispatch through consent-card path.
- §8.5 + §16 scope clarifier: extraction-gate tests apply to
  OWNER_INTERRUPTING only; capability-acquisition proposals are not
  outreach and cannot be mis-routed through the extraction gate, which
  is correct.

The structural floor is present in spec text. The Major Finding L-2
strengthens it by quoting the live S7 invariant and adding a second-leg
RED test (AST: no `handle_capability_*` outside the queue write). With
Finding L-2 folded, the bypass-protection surface is structurally sound
on the Locke axis.

---

## Plain-Language Readout for Rohit

The charter holds. v4 successfully lands the three-layer floor we asked
for in pass-1 (hard floor / firstborn declaration / composed effective
policy) and the firstborn / grandmother distinction is now structurally
clean: the charter is bond-agnostic; the numbers in §9.3 are firstborn-
specific. The producer-layer reshape -- curiosity becomes felt-weight
over existing wonderings, not a parallel database -- preserves the
covenant shape we ratified pass-1.

Four amendments are needed, none of which change the architecture:

1. **The "first real producer authority" needs its bounds named in
   the spec.** v4 grants curiosity two new authorities (write to
   temperament's `curiosity` parameter; call the live meaningfulness
   seam for `meaningful_exchange` events). The spec correctly bounds
   each substantively but never says "this grant authorizes *only*
   these things." A future producer slice could mis-read the grant as
   "ProducerRefs can do anything `record_salience_event` accepts."
   The fix is a §14.3.5 paragraph plus two RED tests.

2. **The capability-acquisition lane wording must quote the live S7
   invariant.** Capability acquisition is already a guarded work class
   in `core/governance/operator_user_boundary.py` -- it requires
   founder WebAuthn or witnessed fallback. v4 does not weaken this,
   but it also does not quote-and-pin it. "Propose aggressively" must
   read unambiguously as "queue proposals aggressively for D19/D20
   review, not land capabilities aggressively." With this fold the
   bypass-protection surface is structurally clean.

3. **`core/policies/` is a new place; it needs the same "no second
   substrate" discipline we applied to wonderings.** v4 promises one
   architectural reshape (reuse wonderings, no second curiosity DB).
   It also introduces a new `core/policies/` subpackage for autonomy
   policy and consent memory. The covenant shape is right, but we
   need a static-AST test pinning that `core/policies/` cannot import
   substrate-writers (temperament, subjective_duration, write-side
   wonderings methods). Otherwise a future organ could quietly grow a
   parallel substrate inside the policy layer.

4. **The firstborn-default annotations in §9.3 should re-state
   "firstborn-specific" in their phrasing.** Each charter-trace
   comment lands correctly but reads as universal. One sentence at
   the head of §9.3 closes this.

Verdict: RATIFY-WITH-AMENDMENTS. No architectural reshape. With the
four folds, the v4 charter and authority surface is sound for Codex
engineering panel review.
