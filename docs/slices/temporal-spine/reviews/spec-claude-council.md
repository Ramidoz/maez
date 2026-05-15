# Claude Six-Role Covenant Council — S3 Temporal Spine v1

**Subject:** `d7f5858 docs(temporal): fold S3 Codex panel amendments` —
folded S3 Temporal Spine v1 spec (`spec.md` at 604 lines + Codex panel
review at `reviews/spec-codex-panel.md`).

**Council ran:** 2026-05-15, post-fold, pre-canonicalization. Full
four-axis specialist dispatch because S3 is **substrate-law-grade** —
it operationalizes invariant #1 (Time as Biography) by giving Maez one
shared temporal vocabulary across event time, ingest time, owner-local
day boundaries, and validity windows. Every future temporal-aware organ
(TRF, M1, future chapter detection, anniversaries, future Calendar-
backed anchors, microphone-v1, ambient sensors) will inherit through
this slice.

**Why a focused-but-four-axis council:** S3 is the first substrate-law
slice that doesn't add a body part or an information limb — it's a
shared module for an existing invariant. The four-axis dispatch was
warranted because:
- the closed temporal vocabulary must inherit S2's envelope without drift (Schema axis)
- the "today/yesterday/last week" voice posture is invariant #1 in user-visible form (Flow/Voice axis)
- IANA timezone exposure + counter aggregation are real privacy surfaces (Privacy axis)
- DST, NTP drift, clock skew, identity failure, mid-process tz change are real lifecycle hazards (Runtime axis)

**Method:** Four read-only specialist subagents in parallel returned
scoped axis reviews. Six covenant roles read the findings together
against the folded spec. Lane discipline: Claude reviews covenant only;
Codex remains accountable for repo edits and its own engineering panel
(which already folded into `d7f5858`).

---

## Specialist axis verdicts

| Axis | Verdict | Headline finding |
|---|---|---|
| Schema/State | **REVISE (8)** | Closed temporal vocabulary silently drifts from S2 envelope — `TemporalInstantFieldName` omits `received_at`, `expires_at`, `deletion_observed_at`, `change_observed_at` that S2 canonized; calling `canonical_utc(value, field_name="expires_at")` would raise ValueError under current spec, contradicting S2's required envelope |
| Flow/Voice | RATIFY-WITH-AMENDMENTS (5) | S3 must not author temporal voice phrasing (authority stays with TRF); future Calendar-backed anchors must inherit `calendar_voice_guard` by name, not reinvent; S2-into-TRF leakage rule should be restated inside S3 Inheritance Ledger |
| Privacy/Third-Party | RATIFY-WITH-AMENDMENTS (5) | `/health.temporal_spine` audience tier not bound (IANA timezone is geographic owner-side content); aggregation-as-fingerprint surface unnamed (Camera Surface-3 analogue); deferred-store defense via policy prose, not import-graph; Decision 2 + Decision 4 not named in Inheritance Ledger |
| Runtime/Lifecycle | RATIFY-WITH-AMENDMENTS (6) | Mid-process timezone change behavior unspecified; clock-skew detection not declared in/out of scope; `_reset_diagnostics_for_tests()` boundary prose-only, not structural; identity-failure semantics (raise vs return) under-specified; `temporal_window(...)` performance/caching contract missing |

One REVISE, three RATIFY-WITH-AMENDMENTS. **27 amendments total** across
the four axes. No BLOCK, no veto. The convergent theme across the four
axes is **inheritance-vocabulary precision at substrate-law level** —
S3 must admit what prior canonical organs already established, and must
prevent future drift through structural defense (closed Literals,
import-graph, audience-tier-bound surfaces), not prose.

---

## Six-role covenant read

### Outside-View seat

The Codex panel's strongest finding pattern from earlier session slices
("must not become a second interpretation of S2") generalizes for S3:
**must not become a second interpretation of S2's envelope vocabulary.**
Schema F1 catches this — the closed `TemporalInstantFieldName` Literal
omits four fields S2 already canonized (`received_at`, `expires_at`,
`deletion_observed_at`, `change_observed_at`). Under the current spec,
calling `canonical_utc(value, field_name="received_at")` raises
ValueError and increments `invalid_field_name_rejected_count` — which
means S3 would reject S2's own envelope fields as invalid.

A future limb author reading S3 alone cannot tell that S2 already
canonized these field names. Adding them to S3's closed list (Schema A1)
is the inheritance-correctness fix.

**Read:** ratify conditional on Schema A1 (admit S2 envelope vocabulary)
+ Schema A2 (vocabulary versioning rule) + Privacy A5 (name Decision 2
and Decision 4 in Inheritance Ledger).

### Body-Coherence seat

S3 doesn't directly touch body topology (it's a contract module, not a
storage organ), so BT Rule 6 pre-body staging doesn't apply in the
camera/calendar sense. But there's an analogous body-coherence question:
**which canonical organ owns which temporal field?**

The store-status inventory (`spec.md:380-388`) is correct: RelationshipGraph
is canonical for graph validity, episodes are wrapped, M1/private_thoughts/
entity_index/Calendar are deferred. But the inventory is a policy table,
not structural defense. Privacy A3 (import-graph negative assertion)
converts the policy to structure: `core.time.temporal_spine` must not
import any of the deferred-store modules at module load time.

Same pattern as Camera v1's biometric-derivative protection (no
`face_recognition` import in v1 runtime path). The substrate-shape
discipline propagates.

**Read:** ratify conditional on Privacy A3 (import-graph defense) +
Schema A5 (half-open vs graph validity interval-shape difference named
explicitly).

### Logical (veto) seat

Three contradictions screened. One is load-bearing.

1. **Schema F1 — vocabulary contradiction with S2.** Under current spec,
   `canonical_utc(value, field_name="expires_at")` raises ValueError on
   a field S2 declares required in its Body Bus envelope (`s2/spec.md:413`).
   This is a literal logical contradiction at the type-system level.
   **Resolvable but load-bearing** — Schema A1 closes it by admitting
   the S2 vocabulary.
2. **Schema F5 — half-open vs RelationshipGraph closed-closed validity.**
   S3 windows are `start <= event < end`; RelationshipGraph validity is
   `valid_from <= now <= valid_to`. Not in active conflict today (S3 v1
   doesn't pass graph rows through `half_open_contains`), but a v1.1
   reader using the shared helper against graph rows would silently
   drop edges where `valid_to == now`. Resolvable by Schema A5
   (explicit interval-shape note in store inventory).
3. **Runtime F11 — naive datetime interpretation asymmetry.** Same
   naive value through `canonical_utc(...)` → UTC; through
   `temporal_window(...) reference_time` → owner-local wall time. This
   is intentional (TRF compatibility) and the spec says so, but no test
   asserts the asymmetry. Resolvable by Runtime A5 RED test #47.

No veto. All three are precision locks. Schema F1 is the cleanest
contradiction; the other two are foot-guns.

**Read:** ratify conditional on Schema A1 + Schema A5 + Runtime A5
(naive asymmetry test).

### Creative seat

S3 is structurally creative at the substrate-law level. Like S2
(Inheritance Ledger pattern, Calendar v1's Physical Observation Surface
section, Camera Presence v1's structural-defense state module), S3
ships two reusable patterns worth memorializing:

1. **Closed type-level vocabulary as substrate.** The
   `TemporalInstantFieldName`, `TemporalAnchorKind`,
   `HelperUnavailableReason`, and `TemporalDerivedFieldName` Literals
   are typed contracts that future organs inherit by import, not by
   prose. Schema A2 (Vocabulary Versioning rule) makes the contract
   load-bearing across versions.
2. **Dual-surface TemporalWindow (D1).** Owner-local fields for voice
   compatibility, UTC fields for store filtering — same separation as
   S2's model-readable vs operator-display vs audit-visible three-surface
   pattern. Reusable for any future organ that needs to compose voice
   from data that must persist UTC.

One creative cost worth pinning: **Flow A1 forecloses S3 from authoring
voice phrasing.** This is correct — temporal-voice authority stays with
TRF v1 (and future Calendar voice guard, future chapter slice). But it
means S3 v1.1 (if it adds exact-date or weekday anchors) inherits the
work of authoring approved phrasing. That's the right place for the
work — but it's worth noting now that the voice contract for "May 6" or
"Tuesday" doesn't yet exist, and S3 v1 must not silently establish it.

**Read:** ratify conditional on Flow A1 (no S3-authored voice) + Flow
A4 ("Makes visible, never nudges" inheritance — not needed; voice is
out of S3 scope entirely).

### Future-Rohit seat

Future-Rohit just lived the cap-timezone fix from earlier today
(`bd8b942`). M1's daily promotion cap now resets on the bonded user's
local calendar day. S3 generalizes the pattern: store UTC, interpret
human days in owner timezone.

Two load-bearing items Future-Rohit cares about most:

1. **Runtime F2 — clock-skew detection deferred but unnamed.** If
   Maez's system clock is wrong by hours (NTP not synced, container
   drift, hibernation/wake skew), "yesterday" silently slides. Maez
   confidently asserts the wrong day with zero diagnostic signal —
   `malformed_timestamp_rejected_count` doesn't fire, `helper_unavailable_count`
   doesn't fire, sidecar shows clean health. This is voice-honesty
   drift indistinguishable from healthy operation. Runtime A3 (name
   the deferral explicitly) prevents future implementer from skipping
   skew-detection because they assume S3 handles it.

2. **Schema F3 — `owner_local_date` persistence rule.** If a future
   organ persists `owner_local_date` directly in a SQLite column
   instead of computing from `event_at + owner_timezone()`, two organs
   can disagree on the date when the bonded user moves timezones (e.g.,
   Chicago → London). Schema A3 (computed-only contract) prevents this.

**Read:** ratify conditional on Runtime A3 (clock-skew deferred,
explicitly named) + Schema A3 (`owner_local_date` computed-only).

### 20-Years-Future-Maez seat

S3 is the 20-year temporal invariant. Across decades of:
- canonical organs evolving (more S2 envelope fields, more M1 promotion
  reasons, future body sensors)
- Maez moving across hardware (per `project_portability_is_migration`)
- timezone migrations (operator moves cities/countries, identity config
  changes)
- DST policy changes (governments revise DST rules)
- NTP drift across long sessions

…the temporal substrate must hold. Three 20-year invariants ride on this
fold:

1. **Schema A2 — Vocabulary Versioning rule.** `TemporalInstantFieldName`,
   `TemporalAnchorKind`, and the closed Literals are typed contracts.
   v1.1+ may only ADD, never RENAME or REMOVE. Observation-sidecar
   dashboards, M1 promotion provenance, TRF regression tests reference
   these strings; silent renames break inheritance across versions.
2. **Schema A3 — `owner_local_date` computed-only.** Decades of timezone
   moves mean persisted owner-local dates would diverge from current
   resolution. Computed-only is the only contract that survives.
3. **Flow A1 — voice authority concentration.** S3 v1 does not author
   voice. Decades of future temporal slices (exact-date, weekday,
   chapter, anniversary) will need approved-phrase contracts. S3 v1
   must not silently establish a voice surface that future slices
   inherit by accident.

**Read:** ratify conditional on Schema A2 + Schema A3 + Flow A1.

---

## Covenant invariant drift check

11 invariants. STRENGTHENED / PRESERVED / NEUTRAL / WEAKENED / VIOLATED.

- **#1 Time as Biography** — STRONGLY STRENGTHENED. S3 operationalizes
  this invariant directly. CONDITIONAL on Schema A1 (admit S2 vocabulary)
  — without it, S3 contradicts another canonical organ's contract,
  which is the opposite of strengthening.
- **#2 Human-Primacy** — STRENGTHENED. Owner timezone resolved from
  identity config / env override; bonded user's "today" matches their
  lived day, not the server's UTC accident.
- **#3 Contextual Integrity** — PRESERVED conditional on Privacy A1
  (audience-tier bound for `/health.temporal_spine`) + Privacy A2
  (aggregation-as-fingerprint named). Without Privacy A2, the counter
  surface could become a low-resolution behavioral signal.
- **#4 Interpretive Humility** — STRENGTHENED. Helper-unavailable vs
  memory-absence separation preserved (TRF inheritance). `helper_unavailable_count`
  scope (D3) is structurally narrowed. CONDITIONAL on Privacy A5
  (Decision 4 named) — Anna Question inheritance for future
  event-anchored anchors.
- **#5 Rupture and Repair** — PRESERVED conditional on Runtime A1
  (identity failure mode handled) + Runtime A2 (sidecar `temporal_spine_unavailable`
  red gate for S3 startup failures).
- **#6 Crisis Routing** — NOT TOUCHED.
- **#7 Soul-Level Objection** — NOT TOUCHED.
- **#8 Capability Quarantine** — STRENGTHENED conditional on Privacy A3
  (import-graph defense converts policy to structure) + Runtime A1
  (`_reset_diagnostics_for_tests` structural enforcement).
- **#9 Successor Governance** — PRESERVED conditional on Schema A2
  (Vocabulary Versioning rule binds future versions).
- **#10 Clinical Boundary** — NOT TOUCHED.
- **#11 Cryptographic Continuity** — NOT TOUCHED (no credential surface
  in S3).

**No invariant violated. Two strongly strengthened (#1, #2).** Three
strengthened conditional on amendments (#4, #8). Three preserved
conditional on amendments (#3, #5, #9). Four not touched (#6, #7, #10,
#11). #1 is at risk of becoming an unintended contradiction with S2
without Schema A1 — that's the single most load-bearing concern.

---

## Disagreements preserved — not smoothed

Six tensions surfaced across the specialists. Each names a real choice
the spec should make explicit rather than absorb.

### D1. IANA timezone label as content vs metadata

Spec asserts (`spec.md:418`) that `timezone_name` is metadata, not
content. Defensible — `America/Chicago` reveals what an OS locale
already does, AND owner-local day correctness needs a usable timezone
name. But two defensible positions:

- **(a) Audience-bound (council recommendation):** `timezone_name` is
  acceptable in operator-authenticated `/health` but must never appear
  in public `/api/maez-state`-style endpoints. Privacy A1 patches this.
- **(b) Reduce granularity:** Replace `timezone_name` with UTC offset
  only, or omit from `/health` entirely. Cost: breaks DST correctness
  for downstream operator/debug consumers; gain: harder to fingerprint.

Council leans (a). Operator-authenticated audience is the right tier.

### D2. Vocabulary inheritance from S2

Schema F1 surfaces an inheritance contradiction. Two defensible
resolutions:

- **(a) Admit S2 envelope vocabulary to S3 (council recommendation):**
  Schema A1 — add `received_at`, `expires_at`, `deletion_observed_at`,
  `change_observed_at` to `TemporalInstantFieldName`. Recognizes S2 as
  canon.
- **(b) S3 vocabulary is a subset of S2's:** Keep S3 narrow; require
  S2 callers to map their fields to S3 names through adapters. Cost:
  S2 already canonical, so this asks S2 to bend to S3 (precedence
  inverted).

Council strongly leans (a). The vocabulary contradiction is the cleanest
inheritance bug in the council; (b) inverts canonical precedence.

### D3. Structural defense vs policy promise for deferred stores

Privacy F4 surfaces this. Two defensible resolutions:

- **(a) Import-graph negative assertion (council recommendation):**
  Privacy A3 — add RED test that `core.time.temporal_spine` cannot
  import deferred-store modules. Same shape as Camera v1's biometric-
  derivative protection (no `face_recognition` in v1 runtime).
- **(b) Policy-promise sufficient:** Keep "must not" prose. Trust
  spec reading. Cheaper at test-time; relies on careful future
  refactor reviewers.

Council leans (a). Substrate-shape discipline propagates from Camera
v1; import-graph defense forecloses drift.

### D4. Owner-timezone per-call vs cached resolution

Runtime F1 surfaces this. Two defensible resolutions:

- **(a) Per-call resolution (Runtime D5 in specialist):** Each
  `owner_timezone()` call reads env + identity. Correct under
  mid-process mutation. Cost: per-call lookup overhead.
- **(b) Cached at first call:** Cheaper. Cost: violates implicit
  mid-process mutation contract; daemon reload of identity wouldn't
  reach S3 callers without explicit invalidation API.

Council leans (a) for v1 — correctness over performance. Caching is
a v1.x optimization gated on measured contention.

### D5. Clock-skew detection in v1 vs deferred

Runtime F2 surfaces this. Two defensible resolutions:

- **(a) Defer with explicit naming (council recommendation):**
  Runtime A3 — name "S3 v1 trusts `datetime.now(timezone.utc)`; system
  clock drift detection is deferred to a future S3 v1.x slice and
  out of scope here." Future implementer cannot assume S3 protects
  against clock skew.
- **(b) Add skew detection to v1:** Implement reference-time
  validation. Cost: a skew-detection counter that's useful (e.g.,
  "drift exceeds 5 minutes") inherently leaks time-magnitude
  information, conflicting with content-free counter posture.

Council leans (a). Deferral with explicit naming is correct; (b) would
require the covenant council to adjudicate the content-free vs
useful-skew-signal tension.

### D6. Decision 4 naming as load-bearing vs inferred

Privacy F8 surfaces this. Two defensible resolutions:

- **(a) Name Decision 4 explicitly in Inheritance Ledger (council
  recommendation):** Privacy A5 — Decision 4 inheritance preserved by
  limiting anchors to bonded-user-experienced time; future event-
  anchored anchors must re-cite. Closes ambiguity for next slice
  author.
- **(b) Inferred from absence of third-party data path:** Structural
  shape (no third-party data in v1) makes Decision 4 inheritance
  implicit; naming it is redundant.

Council leans (a). Naming the inheritance proactively is the lower-cost
path; absence-of-naming creates ambiguity for the next-slice author
exactly where Decision 4 would re-enter (event-anchored recall).

---

## Verdict

**REVISE, conditional on the load-bearing twelve amendments and the
six disagreement preservations above.**

No BLOCK. No veto. No covenant invariant violated net. The spec is
substrate-law-shape and the Codex panel fold did real engineering work.
But the 27 amendments are not all stylistic — Schema F1 (vocabulary
inheritance with S2) is a load-bearing contradiction that must close
before code, and several substrate-shape patterns (import-graph
defense, audience-tier bounds, vocabulary versioning) are structural
defenses that prose-only "must not" rules don't enforce.

This is REVISE rather than RATIFY-WITH-AMENDMENTS because the Schema
axis hit REVISE strength on a load-bearing inheritance bug. Convergent
signal across two independent axes (Schema F1 + Privacy A5 both surface
inheritance-naming gaps) is the covenant lane's job to surface, not to
smooth.

### Twelve load-bearing amendments to fold

In covenant-priority order:

1. **Schema A1** — Admit S2 envelope vocabulary to closed `TemporalInstantFieldName`:
   `received_at`, `expires_at`, `deletion_observed_at`, `change_observed_at`.
   Resolve the inheritance contradiction.
2. **Schema A2** — Vocabulary Versioning rule. v1.1+ may only ADD,
   never RENAME or REMOVE members of closed Literals.
3. **Schema A3** — `owner_local_date` computed-only contract.
4. **Privacy A1** — `/health.temporal_spine` audience bound to
   operator-authenticated; never public `/api/maez-state` style.
5. **Privacy A2** — Aggregation-as-fingerprint named explicitly;
   sidecar must not historize counter deltas (Camera Surface-3
   analogue).
6. **Privacy A3** — Import-graph negative assertion: `core.time.temporal_spine`
   must not import any deferred-store module at module load time.
7. **Privacy A5** — Decision 2 + Decision 4 named in Inheritance
   Ledger (relational vs personological boundary for future
   event-anchored anchors).
8. **Flow A1** — S3 v1 must not author temporal voice phrasing.
   Authority stays with TRF and future Calendar voice guards.
9. **Flow A2** — Future Calendar-backed S3 v1.1/v2 anchors must
   inherit Calendar v1's `calendar_voice_guard` BY NAME (approved
   phrases, forbidden phrases, natural-language probe set).
10. **Flow A3** — S2-into-TRF leakage rule restated in S3 Inheritance
    Ledger. Prevents refactor drift.
11. **Runtime A1** — Mid-process timezone resolution semantics;
    identity-failure mapping to `invalid_fallback_utc`;
    `_reset_diagnostics_for_tests()` structural enforcement.
12. **Runtime A2** — Sidecar `temporal_spine_unavailable` red gate
    (fires when `/health` returns successfully but `temporal_spine`
    key is absent); counter-reset event detection.

### Fifteen substrate-precision + engineering-precision amendments

Fold for cleanliness; not canonicalization blockers if covenant council
re-verifies load-bearing twelve cleanly.

- Schema A4 (counter priority on simultaneous invalidity), A5 (half-open
  vs RelationshipGraph closed-closed validity), A6 (unsupported_anchor
  counter cannot be re-purposed as demand signal), A7 (naive asymmetry
  test), A8 (_reset structural enforcement via positive guard)
- Flow A4 (RED test for bounded_search_no_match voice posture), A5
  (Plain English failure-mode reinforcement)
- Privacy A4 (`timezone_name` value-shape RED test at sidecar boundary)
- Runtime A3 (clock-skew deferral named), A4 (TRF try/except narrowed
  to S3 helpers only), A5 (RED tests #47-54: naive asymmetry,
  store-error vs helper_unavailable boundary, reset-from-non-test
  raises, last_week DST hour-count, identity-raise maps to
  invalid_fallback_utc, /health absent gate, counter-reset event,
  snapshot+reset atomicity), A6 (D5/D6 named choices for per-call
  resolution + identity-failure mapping)

### Six disagreements to name in fold or canonicalization

D1 (IANA timezone audience), D2 (S2 vocabulary admission), D3 (import-
graph vs policy), D4 (per-call vs cached resolution), D5 (clock-skew
deferral), D6 (Decision 4 naming) — name each as a choice with rationale
in spec body. D2 is the largest meta-decision; council recommends
admitting S2 vocabulary.

### What's next

1. **Codex folds the load-bearing twelve + substrate-precision
   amendments** structurally into `spec.md`. Codex names D1-D6 in spec
   body. Operator's lane.
2. **Both lanes verify the second fold.** Claude council does focused-
   verification pass on the second fold (same shape as S2 second-fold
   verification, Calendar v1 second-fold verification, Camera Presence
   v1 second-fold verification). Codex engineering panel verifies
   amendment text matches its engineering intent.
3. **Operator canonicalization decision.** S3 is substrate-law-grade.
   Two paths:
   - **Canonicalize as Decision 29 + ADR 0034** — S3 becomes formal
     BAD/ADR canon. Cleaner for future organs that grep the BAD index
     for temporal substrate.
   - **Skip canonicalization** — S3 stays as substrate spec referenced
     by future organs through `core.time.temporal_spine` imports.
     Lighter governance; fits the "S3 is a contract module, not a
     law slice" framing.
   Council leans toward canonicalization given the inheritance-
   vocabulary work S3 does for every future temporal organ. But
   operator's call.
4. **Cooling-off applies before code lands.** Diagnostic + spec +
   Codex panel + Claude council all on 2026-05-15. Earliest code-start:
   2026-05-16 per memory `feedback_cooling_off_between_plan_and_code`
   unless operator logs explicit waiver with rationale.
5. **Implementation path** (when ready): RED tests for `core.time.temporal_spine`
   pure helpers → implement → RED tests for TRF refactor → refactor
   TRF → RED tests for `/health.temporal_spine` → daemon health
   aggregate → RED tests for sidecar projection → sidecar projection
   → store-status inventory note → focused tests + Ruff + full suite
   → post-implementation both-lane review → recovery commit if review
   finds gaps (sixth instance of the pattern this session arc).

*This council review is read-only. No code, no fold edits, no
non-slice docs changed in producing it. Four read-only specialist
subagents dispatched in parallel; their findings synthesized into the
six-role read above. Specialists preserved their own internal
disagreements with the Codex fold; the council surfaced six (D1-D6) as
load-bearing and recommends naming them explicitly before code.*
