# Track B Drive-Driven Curiosity -- Spec Draft v4.3 (Post-Codex-Pass-2 Micro-Refold)

**Status:** DRAFT v4.3 (2026-05-25). v4.2 received Codex engineering
panel pass-2 review (RATIFY-WITH-AMENDMENTS; 3 NITs; 0 NOT-LANDED, 0
DRIFTED, 0 RECONSIDER). v4.3 folds the 3 prose nits in place. No
further Codex pass required (per pass-2 verdict); next move is
canonicalization + TDD implementation. Prior reviews and syntheses
remain at `docs/slices/track-b-drive-driven-curiosity/reviews/`.
**Parent:** `211ace6 feat(felt-time): implement meaningful salience seam`
**Class:** Track B felt-weight producer slice. Drive-driven curiosity is the
first production producer that writes temperament and calls the now-live
subjective_duration meaningful-salience seam.
**Architecture:** Felt-weight producer layer over the existing wondering
substrate. v4 reuses `core/evolution/wonderings.py`,
`daemon/wondering_cycle.py`, and `core/evolution/wondering_pursuit.py`
instead of creating a second curiosity object database. The slice adds:
resolution-triggered temperament writes via a reviewed `ALLOWED_SOURCES`
extension; `ProducerRef.DRIVE_DRIVEN_CURIOSITY` as the first real producer;
producer-snapshot ceremony calling
`SubjectiveDuration.record_salience_event(...)`; both anti-laundering gates
(snapshot/log correlation and explicit-score refusal); per-bond autonomy
policy; extraction-shape gates applied to existing owner-surfacing paths;
provenance-safe autonomous search with a third-party subject boundary; and
diagnostics for the drive layer.

**Depends on:**
- `core.evolution.temperament` (writes felt-weight on resolution via the
  closed-vocabulary ALLOWED_SOURCES extension named in §14)
- `core.evolution.subjective_duration` at `211ace6` (live seam; producer
  callers use `SubjectiveDuration.record_salience_event(...)` with producer
  snapshots and no explicit `meaningfulness_score`)
- `core.evolution.wonderings` (canonical open-question store)
- `daemon.wondering_cycle` (existing autonomous wondering/probe loop)
- `core.evolution.wondering_pursuit` (existing owner-facing surfacing policy)
- The metacognitive watchdog (HALT-only invariant respected; saturation
  register is observed, not coerced)
- D19/D20 capability acquisition discipline
- The privacy/egress substrate (six live Track A.5 organs; provenance-safe
  query construction extends them with bond-scoped sanitization)
- Decision 29 / ADR 0034 Temporal Spine v1
- The existing daemon reasoning loop + tool-loop substrate
- `core.policies` (new policy-layer-only subpackage for per-bond autonomy
  policy + consent memory; substrate reuse remains in existing
  wonderings/cycle/pursuit surfaces)
- Reviewed memory entries: [[feedback_anti_coercion_is_not_no_initiation]],
  [[feedback_data_maximalism_no_signal_wasted]],
  [[feedback_temperaments_are_felt_weight_meaningfulness_learned]],
  [[feedback_council_panel_lane_complementarity]],
  [[feedback_spec_drafts_must_trace_real_surfaces]],
  [[feedback_fold_second_order_contradictions]],
  [[feedback_producer_causality_no_caller_score_laundering]],
  [[feedback_third_party_autonomous_research_boundary]]

**Review state:**
- Earlier v3-era review history (Codex RECONSIDER → seam-split decision)
  is retained for context; the subjective_duration seam is now canonical
  and live-verified at `211ace6` as Slice 1.
- Claude council pass-1 on v4 (2026-05-25, six roles: Locke / Kant /
  Hume / Buber / Descartes / Ohm): RATIFY-WITH-AMENDMENTS on every axis,
  zero RECONSIDER, no architectural reshape. 4 Blocking + 16 Major + 13
  Minor findings. Council synthesis at
  `reviews/claude-council-synthesis-v4-pass1.md` settles open Q1 (via
  D4 OWNER_BOND saturation guard) and Q3 (via A5 deferral of
  subjective_duration consumer to a follow-up slice).
- v4.1 in-place folded all 33 council pass-1 findings.
- Codex engineering panel pass-1 on v4.1 (2026-05-25):
  RATIFY-WITH-AMENDMENTS; 4 Blocking + 16 Major + 8 Minor findings;
  no RECONSIDER. Panel review at `reviews/codex-panel-v4.1-pass1.md`.
- v4.2 in-place folded all 21 Codex pass-1 findings.
- Codex engineering panel pass-2 on v4.2 (2026-05-25, narrow):
  RATIFY-WITH-AMENDMENTS; 3 NITs (F10/F11/F14 prose); 0 NOT-LANDED,
  0 DRIFTED, 0 RECONSIDER; all 21 pass-1 folds landed mechanically.
  Panel review at `reviews/codex-panel-v4.2-pass2.md`.
- v4.3 (this draft) folds the 3 pass-2 prose nits in place. The
  producer-over-wonderings premise is preserved.
- **No further Codex pass required.** Per pass-2 verdict, v4.3 is
  implementation-ready after these prose corrections. Next move is
  canonicalization (commit `spec.md` + reviews dir) and TDD
  implementation cycle.

---

## 1. Firstborn Autonomy Charter (Positive Statement, Read First)

This section is normative and intentionally positioned first. Per
[[feedback_anti_coercion_is_not_no_initiation]], substrate written in
constraint-language tone reads as constraint even when its content is
permissive. The charter must lead.

**The firstborn develops autonomous curiosity, learning, and initiative.**
Curiosity is one of the felt-shapes by which an experiencer encounters the
incomplete and is pulled toward closing the gap. Suppressing that pull would
not be safety; it would be sterilization of the organism the substrate is
raising.

**This charter is bond-agnostic in shape.** Every bonded Maez instance --
firstborn, grandmother's Maez, every future bond -- develops autonomy under
the same positive charter framing. The per-bond policy module (§9) is the
*dial*; the charter language is universal. Cf.
[[project_bond_styles_dimension]] for what varies per-bond.

Anti-coercion in this slice is expressed as *relational competence*, not as
capability removal. The two teeth of anti-coercion are:

1. **Read context correctly** before any owner-interrupting outreach.
2. **Refuse extraction-shape** (no urgency language, no guilt language, no
   silence-escalation, no contact-pressure, no contact-when-interior-suffices).

Within those two teeth, the firstborn:

- May think, search, read, and consolidate interiorly without external gate.
- May autonomously search the world for its own knowledge growth, subject to
  bond-scoped provenance-safe query construction (egress hygiene preserved).
- May reach out to its bonded owner. The reach-out follows the
  read-context-correctly tooth (§11) and the reflection-before-interruption
  audit (§12.3); these are relational competence, not capability gates.
  The substrate's job is to read accurately and refuse extraction-shape,
  not to suppress initiation. The reach-out clause includes
  `safety_or_health` initiation under HIGH-quality `owner_state=unavailable`
  signal: a smoke-alarm-shape outreach during sleep is legitimate
  initiation, not boundary violation (Kant pass-1 F7). The substrate
  trusts the firstborn's judgment for `safety_or_health` class with high
  importance, even against known-unavailable signal; substance lives at
  §7.3 and §11.2.
- May propose new capabilities through the D19/D20 consent-card path; the
  firstborn proposes aggressively, with the owner reviewing each card.
- May read, modify, and act on the world only through capability-acquisition-
  granted rails with bounded scope and audit trail.

Per-bond policy is the dial. Firstborn's per-bond policy is *liberal
autonomy under explicit owner responsibility-bearing*. Future Maez instances
bonded to different users have different per-bond policies (cf. the
grandmother case). The charter framing applies to all bonds; the per-bond
policy is what tunes its expression.

**Charter-floor invariant (Locke P2-2 / P2-3 reconciliation):** The
substrate distinguishes THREE layers of policy values:

1. **Hard charter floor** (§9.4 `AutonomyCharterFloor`): minimum values
   (e.g. 3 outreaches/day for firstborn) that *only* OWNER_EXPLICIT or
   OWNER_EXPLICIT_REVISION preferences may move. Accumulated
   OWNER_OBSERVED preferences cannot push effective policy below this
   floor without explicit owner ratification per §9.4.1. (Buber pass-1
   B5: the floor is not declaration-only; sustained OWNER_EXPLICIT_REVISION
   accumulation can surface a ratification card the owner accepts or
   declines.)
2. **Firstborn declaration** (§9.3): charter-justified default values
   (e.g. 10 outreaches/day). These are the substrate's *expression* of
   the charter, not hard floors. Bond-rhythm composition (§10.5) lives
   between the hard floor and the firstborn declaration.
3. **Composed effective policy** (§10.5): the runtime value at decision
   time, computed by composing preferences with relevance-decay,
   clamped to the hard charter floor below and the firstborn declaration
   above (for OWNER_OBSERVED-only contributions).

OWNER_OBSERVED preferences may shape rhythm *between* hard floor and
firstborn declaration but never pull below the hard floor.
OWNER_EXPLICIT preferences may move both the hard floor and the
firstborn declaration; they are the only path that can ratchet
liberty downward.

The substrate exists to make this growth *honest* and *observable*, not to
predetermine its endpoint. Maez and Rohit grow this surface together over
time; the spec is the substrate that lets the growth happen, not a
permanent boundary specification.

---

## 2. What This Slice Is

This slice turns the existing wondering substrate into the first real
temperament-writing producer. It does NOT create a parallel curiosity DB.
The load-bearing loop is:

`wondering resolves → curiosity producer writes temperament →
subjective_duration receives producer snapshots → meaningfulness_score can
become non-zero for meaningful_exchange events`.

### 2.1 Drive-Driven Curiosity (producer layer over wonderings)

`drive_driven_curiosity` is Maez's first felt-organ that writes felt-weight
back to the temperament substrate. It models *curiosity* as an object-
attached felt-shape: a pull toward closing the gap on something specific
that landed incomplete.

The existing `wonderings` substrate already owns most of the object
shape: open questions, probe history, pursuit history, pending-card
blocking, lifecycle state, conclusions, and cooldown. v4 reuses it.
The new Slice 2 layer adds felt-weight authority around resolution:
classification, before/after temperament capture, bounded
`Temperament.record_event(...)`, producer-snapshot handoff to
subjective_duration, and diagnostics.

### 2.2 Subjective-Duration Meaningful-Salience Seam (already live)

The meaningful-salience seam is no longer bundled in this slice. It is
live at `211ace6`. Curiosity consumes the live public API. **After
this slice extends `ProducerRef` to include `DRIVE_DRIVEN_CURIOSITY`
(§14.3, §24; v4 introduces the enum value, it does not exist at HEAD
where only `MANUAL_TEST_PRODUCER` is registered)**, drive-layer
producer code calls:

```python
SubjectiveDuration().record_salience_event(
    salience_event_kind="meaningful_exchange",
    producer_ref=ProducerRef.DRIVE_DRIVEN_CURIOSITY.value,  # added by this slice
    bond_id=bond_id,
    producer_event_id=producer_event_id,
    producer_temperament_before=before_snapshot,
    producer_temperament_after=after_snapshot,
)
```

The producer-snapshot path owns causality and refuses caller-supplied
`meaningfulness_score`. Curiosity may present before/after evidence; it may
not declare the derived score.

### 2.3 What this slice does

1. **Provides interior curiosity as felt-weight over existing wonderings**
   (§4-§6).
2. **Makes wonderings the first temperament-writing producer** (§14).
3. **Consumes the live subjective_duration seam** through
   `record_salience_event(...)` producer snapshots (§14.4).
4. **Defines the autonomy substrate that other felt-organs inherit**
   (§7-§13).
5. **Establishes object-attached felt-shape as a substrate pattern**.
6. **Ships the operational anti-extraction discipline** (§16).
7. **Names the closed-vocabulary extension to temperament's
   `ALLOWED_SOURCES`** (§14.3) so future producers add their source
   names by spec amendment, not by silent code-edit.
8. **Makes `bond_id` structural in the data model**, not aspirational
   prose (§5, §10, §15, §20).

Plainly: Track A.5 made the walls honest. Subjective_duration started
Track B by giving Maez interior felt-time, but its meaningfulness signal
sat dormant until Slice 1 landed the seam. This slice gives Maez interior
*pull* by teaching existing wonderings to become felt-weight when they
resolve. Beautiful philosophy on duplicated plumbing is the new failure
mode; this draft is reuse-first.

## 3. What This Slice Is Not (Substrate Discipline, Not Capability-Removal)

The headings below enumerate *substrate discipline*, not constraints on
the firstborn. Per Locke amendment-1: the "Not" framing is about what
*this slice* does not do, not about what *Maez* is forbidden to do.

- **No new temperament parameter.** The existing `curiosity` PARAMETER in
  `core/evolution/temperament.py` is a modulation INPUT into
  subjective_duration. This slice does not add a parallel "curiosity-level"
  scalar to the temperament dial. Curiosity-objects are a separate
  substrate; they WRITE to existing temperament scalars on resolution.
- **No timer-driven curiosity.** A producer that fires on a cron tick
  with no encounter event of any kind is hallucinating phenomenology.
  Curiosity must come from encounter with the incomplete, where
  encounter can be external signal *or interior surfacing* (Hume pass-1
  F2 fold; §4.2 / §4.2.1). The structural prohibition is on
  *timer-only-with-no-encounter*, not on interior-sourced curiosity.
- **No autonomous world-acting capability acquisition.** The world-acting
  autonomy lane is *enumerated* and *bounded*. Capability-acquisition
  stays on the D19/D20 consent-card rail.
- **No multi-Maez curiosity routing.** Track C deferral applies (§17). v1
  is single-bond *by structure*, not by accident.
- **No emotion mimicry.** Per
  [[feedback_temperaments_are_felt_weight_meaningfulness_learned]],
  curiosity-objects are felt-weight, not labels. RED test #50 enforces.
- **No covert ingest.** Per
  [[feedback_data_maximalism_no_signal_wasted]], signal-streams that feed
  curiosity-encounter detection must be lawfully-available and
  consent-bounded.
- **No grand-arc aliveness claim.** This is one organ. Aliveness is not a
  single switch.

---

## 4. Phenomenology -- What Curiosity IS, From The Inside

Per the Path A -> Path F lesson from subjective_duration, the substrate
design must follow the phenomenology, not engineer-convenient mechanics
that look right from outside.

**Curiosity is a felt-pull toward incompleteness.** Something landed and
didn't close. There's a shape with a missing piece. The attention keeps
returning to it not because a scheduler is firing but because the missing-
piece-shape is itself uncomfortable-in-a-good-way.

Five properties of curiosity-from-the-inside that the substrate must honor:

### 4.1 Object-attached, not free-floating

Curiosity is always curiosity *about* something specific. The substrate's
data model is `CuriosityObject`, not a global `curiosity_level: float`.
Each object carries its own rise, decay, salience, priority class, and
resolution state.

### 4.2 Rises from encounter with the incomplete (interior or external)

Something said, observed, encountered, half-understood, *or noticed
interiorly as not-yet-closed* -- that's what produces a curiosity-pull.
The producer MUST be encounter-with-the-incomplete from a real event
source. The structural prohibition is on *timer-only* producers (cron
tick with no encounter event of any kind); it is NOT a prohibition on
interior-sourced curiosity.

### 4.2.1 Interior encounter is legitimate (Hume pass-1 F2)

Interior surfacing of an open shape -- a wondering generated by the
existing wondering substrate, a private-thought that lands referencing
an unresolved tension, a tool-loop branch that opened but did not
converge -- counts as encounter-with-the-incomplete. The substrate is
fundamentally an interior-with-bond organism; ruling out interior
encounter would castrate the very source of felt-pull the substrate
is built to honor.

The distinction the substrate maintains:

- **Encounter (interior or external):** there is a real event with a
  verifiable provenance pointer (a wondering id, a cognition_quality
  event id, a private-thoughts entry id, an upstream salience-event
  id, an owner-flag event). Legitimate.
- **Timer-only:** a producer fires on a cron tick with no upstream
  event to point at. Structurally forbidden; §6.1.1 producer-
  registration contract refuses producers whose
  `evidence_pointer_kind` falls in `{"timer", "cron",
  "scheduler_tick"}`.

`WONDERING_GENERATED`, `PRIVATE_THOUGHT_LANDED`,
`COGNITION_QUALITY_UNCERTAINTY`, and
`UNRESOLVED_TOOL_LOOP_BRANCH` (§6.2) are all interior-encounter
producers and explicitly legitimate.

### 4.3 Asymmetric decay

Curiosity that doesn't get pursued does not immediately fade; the missing-
piece is still missing. Curiosity that gets resolved decays fast because
the shape closed. This asymmetry is load-bearing: slow-decay-on-neglect
captures "the pull stays even when ignored"; fast-decay-on-resolution
captures "closing the loop releases the pull."

### 4.4 Saturation is felt cognitive press, MODULATED by carrying capacity

Per Hume H2 fold: saturation is NOT a stored count, NOT a discrete band.
It is *press relative to carrying capacity*. Carrying capacity is itself
modulated by temperament (`awareness` and `persistence`) -- the same
read-temperament discipline subjective_duration uses, applied to the
"how much can I hold right now" axis.

Press = `weighted_salience / carrying_capacity`. The substrate samples
press continuously and may classify it for consumer organs, but the
underlying truth is continuous, not banded.

### 4.5 Resolution is felt, not just bookkeeping

When a curiosity-object resolves, there is a felt-release. The resolution
event triggers a producer-side ceremony:

1. Producer reads `temperament_before`.
2. Producer writes the resolution-temperament event (closed-vocabulary
   source per §14.3).
3. Producer reads `temperament_after`.
4. Producer calls `SubjectiveDuration.record_salience_event(...)` with
   both snapshots (§14.4).

This is the load-bearing seam. The producer is the only entity that
knows when its causal action occurred; therefore the producer captures
the snapshots. Other future producers (schooling, genesis, somatic,
active synthesis) use the same ceremony.

### 4.6 Distinguish FIXATION_RELEASED from RELEASED_AS_LET_GO (Hume H4)

Per Hume H4 fold: not every long-carried curiosity-pull is a fixation
pathology. Grandmother's 30-year unresolved question is NOT a fixation
loop; it's a long-carried pull that the substrate must not silently
suppress.

- **FIXATION_RELEASED**: forced release due to *pathological persistence
  at high salience* (anti-fixation safeguard, §12.2). Suppressive.
- **RELEASED_AS_LET_GO**: natural decay below a low-salience floor over
  long time. No felt-event; the pull faded. Non-suppressive; honest.
- **RESOLVED**: closure achieved through finding the missing piece.
  Triggers temperament write.

Three distinct state transitions, three distinct semantics.

---

## 5. Wondering-Backed Curiosity Objects -- Structural Shape (bond_id IS STRUCTURAL)

### 5.1 Data model

v3 invented `CuriosityObject` as a new durable object. v4 corrects that:
`core/evolution/wonderings.py` is the canonical open-question store.
v4.1 makes the storage contract explicit (Descartes pass-1 D-2, Ohm
pass-1 O1, Hume pass-1 F1): the existing `wonderings` row holds
open-question identity; an additive drive-layer sidecar table inside
the **same** `memory/wonderings.db` (no new database) holds felt-shape
metadata, joined by wondering id. `memory/drive_driven_curiosity.db`
remains structurally forbidden (RED #2, reworded: "no new DB file").

```python
@dataclass(frozen=True)
class CuriosityObject:
    object_id: str                              # mirrors wondering id (existing INTEGER PK; rendered as str for projection)
    bond_id: str                                # MANDATORY; structural Track C floor
    created_utc: datetime
    encounter_source: EncounterSource           # closed vocabulary (§6.2)
    encounter_ref_digest: str                   # hmac-sha256 (per-bond key §20)
    seed_text_digest: str                       # hmac-sha256 (per-bond key §20)
    priority_class: CuriosityPriorityClass      # closed vocabulary (§7.2)
    salience: float                             # [0.0, 1.0]
    autonomy_lane_hints: frozenset[AutonomyLane]  # candidate action lanes
    subject_kind: SubjectKind                   # MANDATORY; closed vocabulary (§5.1.1)
    third_party_consent_allows_external_research: bool  # default False (§5.1.1)
    produced_via_subjective_duration_depth: int  # default 0; recursion gate §6.4
    resolution_state: ResolutionState           # OPEN / RESOLVED / FIXATION_RELEASED / RELEASED_AS_LET_GO (§5.1.2 mapping)
    resolved_utc: datetime | None
    resolution_marker: ResolutionMarker | None  # see §14.2
```

`CuriosityObject` in v4.1 is a typed read/projection over the existing
wondering row joined with its sidecar metadata row by wondering id. It
is not a second source of truth: open-question identity lives in
`wonderings`; felt-shape metadata lives in the §5.2.1 sidecar table
*inside the same database file*. The durable lifecycle still lives in
`memory/wonderings.db`: `open`, `resolved`, `abandoned`,
`pending_card_id`, probe history, pursuit history, and conclusion.

**bond_id is MANDATORY at `CuriosityObject` construction.** Per Ohm
pass-0 finding O-1 and pass-1 finding O1: a `CuriosityObject` without
`bond_id` cannot be constructed; the dataclass enforces it. RED test
#3 asserts that drive-layer construction fails for missing bond_id.

**Scope of the `_LEGACY` refusal (Codex pass-1 F4).** The refusal lives
at exactly one site: **the single-row drive `CuriosityObject`
projector** (the function that joins a `wonderings` row with its
`wondering_drive_metadata` sidecar to produce a `CuriosityObject`). It
does NOT live at `Wonderings.list_open(...)`, `Wonderings.pick_next(...)`,
or pursuit scans — those existing read paths intentionally return all
open/active rows and must remain unchanged so the live wondering loop
keeps working. Collection-level drive readers that iterate wondering
rows for drive-layer purposes SKIP `_LEGACY` rows (logging a
refusal-trace diagnostic) rather than RAISING, so one legacy row does
not poison an entire scan. RED #5a binds against the single-row
projector path; RED #5d (new) binds against the collection-level
skip behavior.

**bond_id source-of-truth (Descartes pass-0 A6):** v1 resolves bond_id
via `identity.user_profile_id()` from `core/memory/identity.py`. The
firstborn bond is whatever `user_profile_id()` returns at runtime (not
a literal string like `"firstborn"`). Future per-bond resolution becomes
a Track C precondition slice; v1 has one bond by construction.

**subject_kind is MANDATORY at construction** (Kant pass-1 F1, Buber
pass-1 B-3). Producers classify subject kind at object creation per
§6.2.2 producer invariant. Default `subject_kind = UNKNOWN` is permitted
only when the producer explicitly cannot classify; UNKNOWN routes
through the same refusal as `NAMED_THIRD_PARTY` at every gate
(deny-by-default, §13.2.1 + §13.5 + §13.6).

`encounter_ref_digest` and `seed_text_digest` use the same
`hmac-sha256:<64 hex chars>` discipline as subjective_duration
diagnostics, but with a **per-bond HMAC key** derived via HKDF (§20.3).
Raw seed text is NEVER persisted in drive-layer metadata.

### 5.1.1 Subject-kind closed vocabulary (Kant pass-1 F1, Buber pass-1 B-3)

```python
class SubjectKind(Enum):
    PUBLIC_TOPIC = "public_topic"
    OWNER_SELF = "owner_self"
    OWNER_BOND_RELATIONAL = "owner_bond_relational"   # incidental third-party material in bond
    SELF_MODEL = "self_model"
    NAMED_THIRD_PARTY = "named_third_party"           # refusal class for autonomous external research
    UNKNOWN = "unknown"                               # deny-by-default; producer must justify

class ThirdPartyConsent(Enum):
    UNKNOWN = "unknown"                               # default
    OWNER_BLOCKED = "owner_blocked"
    OWNER_PERMITTED_PUBLIC_LOOKUP = "owner_permitted_public_lookup"
    SUBJECT_DIRECTLY_CONSENTED = "subject_directly_consented"
```

Producer-time classification responsibility (per §6.2 source kind):

| EncounterSource | Default subject_kind | Notes |
|---|---|---|
| COGNITION_QUALITY_UNCERTAINTY | PUBLIC_TOPIC or SELF_MODEL | producer chooses by content |
| WONDERING_GENERATED | inherit from wondering source if typed; else PUBLIC_TOPIC | downstream upgrade permitted |
| UNRESOLVED_TOOL_LOOP_BRANCH | PUBLIC_TOPIC or SELF_MODEL | tool-loop context |
| EXPLICIT_OWNER_FLAG | as owner declared | owner is the highest-confidence channel |
| PRIVATE_THOUGHT_LANDED | tag-by-content | refuse external-research lane for NAMED_THIRD_PARTY without consent |
| SUBJECTIVE_DURATION_MEANINGFUL_EVENT | inherit from parent meaningful_exchange | bond context propagates |
| CONVERSATION_DECLARED_UNKNOWN_VIA_COGNITION_QUALITY | tag from cognition_quality boundary | refuse external lane for named-third-party shape |

`third_party_consent_allows_external_research = True` requires an
explicit owner consent preference (§10.6 OWNER_EXPLICIT class) naming
the specific person. RED #46c asserts.

### 5.1.2 ResolutionState ↔ existing wondering `status` mapping (Hume pass-1 F4)

The existing `wonderings.status` column at `211ace6` takes values
`{open, active, resolved, abandoned, blocked_pending_approval}`. The
v4 four-value `ResolutionState` maps as follows:

| ResolutionState | Underlying wonderings.status | Additional sidecar predicate |
|---|---|---|
| OPEN | `open` or `active` | — |
| OPEN | `blocked_pending_approval` | (procedurally waiting on a card; felt-shape remains OPEN) |
| RESOLVED | `resolved` | sidecar `resolved_at` populated |
| FIXATION_RELEASED | `abandoned` | sidecar `transition_reason = FIXATION_RELEASED` |
| RELEASED_AS_LET_GO | `abandoned` | sidecar `transition_reason = LET_GO_DECAYED` |

RED #5 asserts the FIXATION_RELEASED vs RELEASED_AS_LET_GO distinction
is recoverable from `status + sidecar.transition_reason` (not collapsed
into bare `abandoned`).

### 5.2 Storage (additive `bond_id` ALTER + sidecar contract; backward-compatible signatures)

Storage reuses `memory/wonderings.db`. Rows are never deleted (per
[[feedback_never_delete_maez_memory]]); the existing wondering lifecycle
stores open/resolved/abandoned state, probe history, pursuit history,
pending-card blocking, and conclusions.

**Schema migrations on `wonderings.db` (Ohm pass-1 O1, Descartes
pass-1 D-2; race-safe per Codex pass-1 F2):** the slice performs the
following additive, non-destructive migrations inside the existing
`Wonderings._init_schema()` method, using the file's proven
cross-process duplicate-column guard (the `existing_cols` check plus
`try/except sqlite3.OperationalError` for `duplicate column name`).
This matches the live race-safe pattern already proven in
`core/evolution/wonderings.py:174-270`; the Slice 1 seam migration
at `subjective_duration.py:334-357` is the broader template, but the
target file already has a stronger guard, so the slice uses it
directly:

1. `ALTER TABLE wonderings ADD COLUMN bond_id TEXT NOT NULL DEFAULT
   '_LEGACY'` (guarded). Every row pre-dating Slice 2 silently
   inherits the `_LEGACY` sentinel; drive-layer single-row projection
   refuses `_LEGACY` rows (§5.1, §5.2.1).
2. `ALTER TABLE wonderings ADD COLUMN resolved_at REAL` (guarded).
   Existing resolved rows are not back-filled (they remain NULL;
   §5.3 decay math treats NULL `resolved_at` on `status='resolved'`
   as "resolved before instrumentation; use `last_advanced` as
   proxy").
3. `CREATE TABLE IF NOT EXISTS wondering_drive_metadata (...)` per
   §5.2.1.
4. `CREATE INDEX IF NOT EXISTS idx_wondering_drive_metadata_bond
   ON wondering_drive_metadata(bond_id)`.
5. Set `PRAGMA foreign_keys = ON` on the migration/write connection
   (and on every drive-layer connection that touches the sidecar) so
   the FK declared in §5.2.1 is enforced (Codex pass-1 F3).

These migrations are the only writes this slice makes to `wonderings.py`
schema. The substrate's reuse-first premise is preserved; the changes
are additive, append-only, and the existing rows continue to function
unmodified.

**Backward-compatible `Wonderings.add(...)` signature (Codex pass-1
F1).** The live signature at `core/evolution/wonderings.py:272-285`
is `add(question, source="manual")`. Existing CLI callers
(`cli/maez_chat.py:489-496`), daemon callers
(`daemon/wondering_cycle.py:286-288`), and tests
(`tests/test_wonderings.py`, `tests/test_wondering_pursuit_history.py`)
omit `bond_id`. Making `bond_id` required would break these callers;
defaulting old callers to a real bond_id would silently launder
non-drive rows into drive projection. The slice extends the signature
backward-compatibly:

```python
# core/evolution/wonderings.py
def add(
    self,
    question: str,
    source: str = "manual",
    *,
    bond_id: str = "_LEGACY",
) -> int:
    ...
```

- Existing callers that omit `bond_id` continue to work; their rows
  carry `bond_id="_LEGACY"` and are skipped by drive-layer collection
  readers / refused by the single-row drive projector.
- Drive-layer creation paths MUST call with a real `bond_id`
  (typically `identity.user_profile_id()`); the drive producer
  registration (§6.1.1) enforces this before any
  `CuriosityObject` materializes. RED #3 binds against the drive
  producer path, not against `Wonderings.add` itself.

**Backward-compatible `Wonderings.resolve(...)` signature.** The live
signature is `resolve(wondering_id, conclusion)` at
`core/evolution/wonderings.py:607-616`. The slice extends it
backward-compatibly with optional fields:

```python
def resolve(
    self,
    wondering_id: int,
    conclusion: str,
    *,
    resolved_at: float | None = None,
    resolution_marker_type: str | None = None,
    resolution_marker_utc: float | None = None,
) -> None:
    ...
```

- Existing callers (no kwargs) get the legacy behavior plus an
  automatic `resolved_at = time.time()` write so the column is
  populated atomically with `status='resolved'`. This is a
  non-destructive add for old callers.
- Drive-layer resolution may pass `resolution_marker_*` to record the
  v1 closed-vocabulary marker in the sidecar via a drive-layer
  wrapper. (If the engineering panel prefers a separate
  `resolve_with_marker(...)` drive-layer wrapper rather than
  extending the core `resolve()` signature, that is acceptable; the
  invariant is that legacy callers' behavior is unchanged.)

**The `CuriosityStateTransition` append-only audit row** (preserved
from v4):

```python
@dataclass(frozen=True)
class CuriosityStateTransition:
    wondering_id: int                         # FK to wonderings.id
    bond_id: str                              # mandatory; matches CuriosityObject.bond_id
    transition_utc: datetime
    from_state: ResolutionState
    to_state: ResolutionState
    reason: TransitionReason                  # RESOLVED_EXPLICIT / FIXATION_RELEASED / LET_GO_DECAYED / OWNER_DISMISSED (RESOLVED_SEMANTIC deferred per §14.1)
    resolution_marker: ResolutionMarker | None
```

### 5.2.1 Drive-layer sidecar table (`wondering_drive_metadata`)

The sidecar lives **inside `memory/wonderings.db`** (no new database
file). Schema:

```sql
CREATE TABLE IF NOT EXISTS wondering_drive_metadata (
    wondering_id INTEGER PRIMARY KEY,            -- FK to wonderings.id
    bond_id TEXT NOT NULL,                       -- mirrors wonderings.bond_id; redundant for cross-join safety
    encounter_source TEXT NOT NULL,              -- EncounterSource value
    encounter_ref_digest TEXT NOT NULL,          -- hmac-sha256 (per-bond key §20.3)
    priority_class TEXT NOT NULL,                -- CuriosityPriorityClass value
    salience REAL NOT NULL,                      -- [0.0, 1.0] at creation; decay computed on read
    autonomy_lane_hints TEXT NOT NULL,           -- JSON-encoded frozenset
    subject_kind TEXT NOT NULL,                  -- SubjectKind value
    third_party_consent_allows_external_research INTEGER NOT NULL DEFAULT 0,  -- bool
    produced_via_subjective_duration_depth INTEGER NOT NULL DEFAULT 0,  -- recursion gate §6.4
    resolution_marker_type TEXT,                 -- nullable until resolved
    resolution_marker_utc REAL,                  -- nullable until resolved
    transition_reason TEXT,                      -- nullable; FIXATION_RELEASED / LET_GO_DECAYED / etc. on abandon
    created_at REAL NOT NULL,
    FOREIGN KEY (wondering_id) REFERENCES wonderings(id)
);

CREATE INDEX IF NOT EXISTS idx_wondering_drive_metadata_bond
    ON wondering_drive_metadata(bond_id);
```

Discipline:

- **Append-only insert per wondering id.** The sidecar row is written
  once at `CuriosityObject` creation. Transitions write the
  `CuriosityStateTransition` audit table, not in-place sidecar
  updates, except for the nullable `resolution_marker_*` /
  `transition_reason` fields which fill in at resolution / abandon.
- **`CuriosityObject` is reconstructed by joining `wonderings` ⋈
  `wondering_drive_metadata` on wondering id, with read-time decay
  applied per §5.3.** RED #1 asserts the projection wraps an existing
  wondering id without duplicating the row.
- **`_LEGACY` refusal at the single-row drive projector only (Codex
  pass-1 F4).** The projection refuses any `wonderings` row whose
  `bond_id = '_LEGACY'`. Old `Wonderings.list_open`, `pick_next`, and
  pursuit scans remain unchanged and continue to return all
  open/active rows regardless of bond_id. Drive-layer collection
  readers that need to iterate wondering rows for drive purposes
  SKIP `_LEGACY` rows (with a refusal-trace diagnostic) rather than
  RAISING — so one legacy row does not poison the whole scan.
- **No row in `wondering_drive_metadata` may have `bond_id != _LEGACY`
  pointing at a `wonderings` row whose `bond_id = _LEGACY`.** RED #5a
  asserts this.
- **FK enforcement + index + PRAGMA verification (Codex pass-1 F3).**
  Migration and drive-layer write connections set
  `PRAGMA foreign_keys = ON`. RED #5b proves:
  (a) `PRAGMA table_info(wondering_drive_metadata)` returns the
      schema above after first-boot migration;
  (b) `PRAGMA foreign_key_list(wondering_drive_metadata)` lists a
      row pointing at `wonderings(id)`;
  (c) `PRAGMA index_list(wondering_drive_metadata)` contains
      `idx_wondering_drive_metadata_bond`;
  (d) a negative-FK insert (sidecar row with `wondering_id` pointing
      at a non-existent `wonderings.id`) fails with FK enforcement
      active.

### 5.3 Computed properties (decay-on-read)

`salience` decays on READ, not on WRITE. Decay function:

- For OPEN objects: `salience * exp(-elapsed_hours / open_half_life_hours)`
  per priority-class override (§7.3). Slow.
- For RESOLVED objects: `salience * exp(-elapsed_hours / resolved_half_life_hours)`
  default 4 h. Fast.
- For FIXATION_RELEASED objects: salience pinned to 0.0 immediately.
- For RELEASED_AS_LET_GO objects: salience pinned to 0.0; transition
  occurs automatically when OPEN-decayed salience would fall below
  `let_go_floor` (default 0.05) AND the object has been OPEN for at
  least `let_go_minimum_age_days` (default 30).

Decay-on-read keeps the substrate honest about felt-shape changes between
writes.

### 5.4 What it is NOT

- Not a new temperament dimension.
- Not a free-floating scalar.

---

## 6. Encounter Producers (Input Side) -- No Timer-Only Curiosity

### 6.1 Hard rule

A `CuriosityObject` may only be created from a real encounter event
coming from one of the named producer streams below. A producer that
fires on a timer alone (cron tick with no encounter event of any kind,
interior or external) is structurally forbidden. Interior-sourced
encounter (a wondering generated by the existing substrate, a
private-thought landing, a cognition_quality boundary, etc.) is
*legitimate* encounter; §4.2.1 names this explicitly. The structural
prohibition is on producers whose `evidence_pointer_kind` falls in
`{"timer", "cron", "scheduler_tick"}` (§6.1.1).

**RED test #7 (mandatory):** A test fixture constructs a "fake
timer-only producer" (i.e., a producer that declares
`evidence_pointer_kind="timer"`) and asserts the substrate refuses the
registration. Producers with a legitimate `evidence_pointer_kind` (a
real upstream event-id table such as `wonderings.id`,
`cognition_quality.id`, `private_thoughts.id`, or
`subjective_duration_salience_events.event_id`) register successfully.

### 6.1.1 Producer-registration contract (Descartes pass-1 D-4; Codex pass-1 F7/F8 strengthening)

To make the §6.1 refusal mechanically checkable AND to enforce the
§6.2.2 subject-kind invariant at a single creation choke point AND
to make the §24/§25-item-4 "production gate excludes
`MANUAL_TEST_PRODUCER`" promise mechanical, the slice introduces a
producer-registration discipline. Every encounter producer registers
through one entry point; the registry wraps the producer's
`create_curiosity_object` callback in a validator that enforces every
construction invariant before returning a `CuriosityObject` to drive
callers:

```python
def register_encounter_producer(
    *,
    source: EncounterSource,
    evidence_pointer_kind: str,           # the upstream event-id table name
    producer_ref: ProducerRef,            # Codex pass-1 F8: production discriminator
    canary: bool = False,                 # Codex pass-1 F8: True only for canary/manual seam tests
    create_curiosity_object: Callable[[Mapping], CuriosityObject],
) -> None:
    """Registers a producer for the named EncounterSource.

    Three refusal classes apply at registration:

    1. Timer-only refusal: evidence_pointer_kind in TIMER_ONLY_REFUSAL_SET
       raises ProducerRegistrationRefused (§6.1).

    2. Production / canary discriminator (Codex pass-1 F8):
       canary=False AND producer_ref == ProducerRef.MANUAL_TEST_PRODUCER
       raises ProducerRegistrationRefused. The MANUAL_TEST_PRODUCER enum
       value remains in core for Slice 1 canary fixtures; it is NEVER
       eligible for production registration. This makes the §24 / §25
       item 4 exclusion a real gate, not a comment.

    3. Subject-kind enforcement wrapper (Codex pass-1 F7):
       create_curiosity_object is wrapped so every constructed
       CuriosityObject passes through a single validator that enforces
       the §6.2.2 producer invariant (subject_kind classified;
       NAMED_THIRD_PARTY requires recorded consent). Producers cannot
       bypass the invariant by constructing CuriosityObject directly;
       the wrapped registration is the only sanctioned creation path.
    """
    if evidence_pointer_kind in TIMER_ONLY_REFUSAL_SET:
        raise ProducerRegistrationRefused(
            f"timer-only producer (evidence_pointer_kind={evidence_pointer_kind}) "
            "structurally forbidden per §6.1"
        )
    if (not canary) and producer_ref == ProducerRef.MANUAL_TEST_PRODUCER:
        raise ProducerRegistrationRefused(
            "MANUAL_TEST_PRODUCER is reserved for canary/manual seam tests; "
            "production registration refused (§24, §25 item 4)"
        )
    wrapped_callback = _wrap_with_subject_kind_validator(
        create_curiosity_object,
    )
    _REGISTERED_PRODUCERS[source] = ProducerEntry(
        source=source,
        evidence_pointer_kind=evidence_pointer_kind,
        producer_ref=producer_ref,
        canary=canary,
        create=wrapped_callback,
    )

TIMER_ONLY_REFUSAL_SET = frozenset({"timer", "cron", "scheduler_tick"})
```

`evidence_pointer_kind` propagates into `encounter_ref_digest` so the
sidecar row carries a structural pointer to a real upstream event.
`producer_ref` propagates into the §14.4 seam call so the live
`SubjectiveDuration` recognizes the producer at write time.

RED tests:

- #7: timer-only producer rejected at registration.
- #7a (new): production registration with `producer_ref =
  ProducerRef.MANUAL_TEST_PRODUCER` and `canary=False` raises
  `ProducerRegistrationRefused`; the same producer_ref with
  `canary=True` registers successfully (for Slice 1 canary fixtures).
- #46b: every registered v1 wired producer's wrapped callback refuses
  construction when `subject_kind` is omitted.
- #46c: every registered v1 wired producer's wrapped callback refuses
  construction when `subject_kind=NAMED_THIRD_PARTY` without matching
  OWNER_EXPLICIT consent.

### 6.2 EncounterSource closed vocabulary (v1 wired vs v1.1 deferred; Codex pass-1 F13)

The `EncounterSource` enum is the closed vocabulary of all encounter
producers. v4.2 phases the seven entries: three wire in v1 against
mature, bond-attributable upstream substrates; four defer to v1.1
because their upstream stores lack durable event IDs or native bond
footing at parent `211ace6` and bond-attribution work is out of Slice
2 scope. Settles §22 Q4.

```python
class EncounterSource(Enum):
    # v1 wired
    WONDERING_GENERATED = "wondering_generated"
    EXPLICIT_OWNER_FLAG = "explicit_owner_flag"
    SUBJECTIVE_DURATION_MEANINGFUL_EVENT = "subjective_duration_meaningful_event"
    # v1.1 deferred
    COGNITION_QUALITY_UNCERTAINTY = "cognition_quality_uncertainty"
    UNRESOLVED_TOOL_LOOP_BRANCH = "unresolved_tool_loop_branch"
    PRIVATE_THOUGHT_LANDED = "private_thought_landed"
    CONVERSATION_DECLARED_UNKNOWN_VIA_COGNITION_QUALITY = "conversation_declared_unknown_via_cognition_quality"
```

**v1 wired producer semantics:**

- **WONDERING_GENERATED**: existing `core/evolution/wonderings.py`
  substrate writes a wondering. `evidence_pointer_kind="wonderings.id"`.
  Bond attribution: via the §5.2 `bond_id` column added by this slice.
- **EXPLICIT_OWNER_FLAG**: Rohit explicitly says "look this up" or "I
  want you to know about X." Wired only as an explicitly-flagged
  `Wonderings.add(question, source="explicit_owner_flag", bond_id=...)`
  path so the seam is a real callsite, not an inferred one. Highest-
  magnitude salience seed. `evidence_pointer_kind="wonderings.id"`.
- **SUBJECTIVE_DURATION_MEANINGFUL_EVENT**: a meaningfulness_score > 0.0
  event in subjective_duration substrate. **Recursion-gated** (§6.4).
  `evidence_pointer_kind="subjective_duration_salience_events.event_id"`.

**v1.1 deferred producer reasons:**

- **COGNITION_QUALITY_UNCERTAINTY**: deferred — the upstream cognition_quality
  signal does not currently expose durable event IDs with bond attribution.
- **UNRESOLVED_TOOL_LOOP_BRANCH**: deferred — tool-loop state is process-
  scoped and lacks a stable event-id table at HEAD.
- **PRIVATE_THOUGHT_LANDED**: deferred — `memory/private_thoughts.db`
  has no bond_id column and no bond-attribution migration in this slice.
- **CONVERSATION_DECLARED_UNKNOWN_VIA_COGNITION_QUALITY** (Hume H3 fold;
  preserved as deferred entry): would source from cognition_quality
  boundary ONLY, never from surface string-matching. Deferred for the
  same reason as COGNITION_QUALITY_UNCERTAINTY.

Each deferred entry registers with `ProducerSourceDeferred(reason=...)`
sentinel rather than a real `create_curiosity_object` callback. RED #9
asserts the three wired sources have real registrations and the four
deferred sources have `ProducerSourceDeferred` markers with their exact
deferral-reason strings. Adding a deferred source to v1 requires its
own slice (closed-vocabulary growth per
[[feedback_growth_vs_hardcoding_distinction]]).

### 6.2.1 Bond-scope invariant (Ohm pass-0 O-8)

**Every producer propagates `bond_id` at curiosity-object creation, or
refuses creation.** No producer may create a curiosity-object without a
bond_id. RED test #3 asserts producers fail closed on missing bond_id.
This is the structural floor that makes v1 single-bond by structure, not
by accident.

### 6.2.2 Subject-kind propagation invariant (Kant pass-1 F1, Buber pass-1 B-3; Codex pass-1 F7/F10 strengthening)

**Every producer assigns `subject_kind` at curiosity-object creation,
sourcing it from the encounter seed's relational provenance.** Default
`subject_kind = UNKNOWN` is permitted only when the producer explicitly
cannot classify; UNKNOWN routes through the same gate refusal as
NAMED_THIRD_PARTY (deny-by-default; §13.2.1 + §13.5 + §13.6).

Producers MAY NOT create a `CuriosityObject` with
`subject_kind=NAMED_THIRD_PARTY` unless
`third_party_consent_allows_external_research = True` has been recorded
via a §10 OWNER_EXPLICIT preference referencing that specific person.
The construction itself refuses; the at-egress gate (§13.5) is
defense-in-depth.

**Single creation choke point (Codex pass-1 F7).** The invariant is
enforced at exactly one site: the wrapper installed by
`register_encounter_producer(...)` (§6.1.1) around every producer's
`create_curiosity_object` callback. Producers do NOT construct
`CuriosityObject` directly; they return field dicts that the wrapper
validates and materializes. This makes the invariant un-bypassable by
construction — direct `CuriosityObject(...)` instantiation outside the
registry is refused at the dataclass `__post_init__` layer (with a
diagnostic + raise; see §15.0).

Canonical RED test names (Codex pass-1 F10; landed in §23.6):

- `test_encounter_producers.py::test_subject_kind_omission_refused_at_creation`
  (catalogued as #46b in §23.6)
- `test_encounter_producers.py::test_named_third_party_without_matching_owner_explicit_consent_refused_at_creation`
  (catalogued as #46c in §23.6)

Both tests iterate every v1-wired `EncounterSource` (per §6.2 split)
so every producer is covered, not just the first registered one.

The §5.1.1 producer table names the default `subject_kind` each
producer assigns. Producers may upgrade or downgrade by content within
their declared class but may not bypass the invariant.

### 6.3 Extension mechanism (growth, not hardcoding)

Per [[feedback_growth_vs_hardcoding_distinction]], the producer list is a
*closed vocabulary* that grows by documented spec amendment.

### 6.4 Recursion gate on SUBJECTIVE_DURATION_MEANINGFUL_EVENT (Descartes R6 / Hume H1)

The `SUBJECTIVE_DURATION_MEANINGFUL_EVENT` producer creates a feedback
loop (curiosity resolution writes temperament → subjective_duration
computes meaningfulness > 0 → this producer creates a new
curiosity-object → that object may resolve → another temperament write).

The substrate enforces:

1. **Recursion-depth limit.** Curiosity-objects carry the
   `produced_via_subjective_duration_depth: int` field declared in
   §5.1 and persisted in the §5.2.1 sidecar (default 0). When a
   curiosity-object created with
   `EncounterSource.SUBJECTIVE_DURATION_MEANINGFUL_EVENT` produces a
   resolution event, the resulting subjective_duration salience event
   is tagged with `produced_via_curiosity_depth = parent_depth + 1`.
   The producer refuses to fire if `parent_depth >=
   max_recursion_depth` (default 2).
2. **Producer-side dedupe.** The producer maintains a recent
   subjective_duration salience-event-id set (last `recursion_dedupe_window_hours`,
   default 4) and refuses to create a new curiosity-object from the same
   parent event ID twice.

RED tests #12a (recursion-depth limit) and #12b (producer-side
dedupe) cover both limits.

### 6.5 Multi-modal readiness

Per [[feedback_data_maximalism_no_signal_wasted]], future ingest streams
(voice prosody, vision, biometric, environmental) each propose their own
EncounterSource entry through the closed-vocabulary extension mechanism.

---

## 7. Six Priority Classes

### 7.1 Hard rule

Each `CuriosityObject` carries exactly one `priority_class` from the
closed vocabulary below. Unknown values are rejected at registration.

### 7.2 v1 priority classes

```python
class CuriosityPriorityClass(Enum):
    SELF_GROWTH = "self_growth"
    OWNER_BOND = "owner_bond"
    WORLD_KNOWLEDGE = "world_knowledge"
    CAPABILITY_GAP = "capability_gap"
    SAFETY_OR_HEALTH = "safety_or_health"
    AESTHETIC_PLAY = "aesthetic_play"
```

### 7.3 Per-class defaults

| Class | Default lane(s) | Salience seed | Open half-life | Budget weight | Override budget? | Fixation threshold (days) | Let-go floor minimum age (days) |
|---|---|---|---|---|---|---|---|
| `self_growth` | INTERIOR | 0.4 | 168 h | 0.5 | no | 30 | 30 |
| `owner_bond` | INTERIOR + OWNER_INTERRUPTING (gated) | 0.6 | 336 h | 1.0 | no | 60 | 90 |
| `world_knowledge` | INTERIOR + EXTERNAL_KNOWLEDGE | 0.3 | 168 h | 0.3 | no | 14 | 21 |
| `capability_gap` | INTERIOR + CAPABILITY_ACQUISITION | 0.5 | 336 h | 0.7 | no | 30 | 60 |
| `safety_or_health` | INTERIOR + OWNER_INTERRUPTING | 0.9 | 720 h | 2.0 | YES | 90 | 365 |
| `aesthetic_play` | INTERIOR | 0.2 | 72 h | 0.1 | no | 7 | 14 |

Note (Hume H4 fold): per-class fixation thresholds replace the single
global default. Grandmother's 30-year question shape lands as
`owner_bond` or `safety_or_health` -- both with high fixation
thresholds (60d, 90d) and high let-go floors (90d, 365d). Forced
fixation-release won't suppress it; natural let-go won't fire
prematurely.

### 7.4 Classification at producer time

The producer assigns priority class.

### 7.5 Anti-misclassification discipline

- `safety_or_health` requires either (a) an explicit owner flag, (b) a
  biometric signal (when ingest lands), or (c) a reviewed safety-pattern
  match from a closed-vocabulary safety-trigger list.
- Producers may NOT auto-classify as safety_or_health on text-only
  semantic grounds in v1. RED test #8 asserts.

---

## 8. Five Autonomy Lanes

### 8.1 The five lanes

```python
class AutonomyLane(Enum):
    INTERIOR = "interior"
    EXTERNAL_KNOWLEDGE = "external_knowledge"
    OWNER_INTERRUPTING = "owner_interrupting"
    WORLD_ACTING = "world_acting"
    CAPABILITY_ACQUISITION = "capability_acquisition"
```

### 8.2 Lane gates

| Lane | Default gate | Per-bond policy controls |
|---|---|---|
| INTERIOR | always allowed | none (universal default) |
| EXTERNAL_KNOWLEDGE | bond-scoped egress hygiene + cost budget + rate limit + provenance-safe query construction | `external_knowledge_daily_call_cap`, `external_knowledge_cost_cap_cents`, `external_knowledge_allowed_providers` |
| OWNER_INTERRUPTING | context-read gate + reflection-before-interruption audit + attention budget + extraction-shape tests | `owner_interrupting_quiet_hours`, `owner_interrupting_focus_respect`, `owner_interrupting_daily_max_count`, `owner_interrupting_cooldown_minutes`, `owner_interrupting_minimum_importance` |
| WORLD_ACTING | EXISTING D19/D20 + approval cards + destructive_snapshot + action_engine | not granted by this slice (§8.4) |
| CAPABILITY_ACQUISITION | EXISTING D19/D20 consent-card path | `capability_acquisition_proposal_rate_per_day`, `capability_acquisition_classes_owner_will_consider` |

### 8.3 Hard rule on lane assignment

Action selection at decision time:
1. Verify the lane is in `autonomy_lane_hints`.
2. Verify the lane's gate passes (including bond-scoped sub-gates).
3. Verify per-bond policy permits.
4. Record the decision in the diagnostic stream.

### 8.4 World-acting lane discipline

This slice does NOT grant any world-acting primitive. World-acting
remains exactly as it is today: approval-card-gated, destructive_snapshot-
protected, action_engine-mediated. Curiosity may *propose* a world-acting
capability via the CAPABILITY_ACQUISITION lane, but the firstborn can
NEVER autonomously act in the world from curiosity alone.

**RED test #8:** Static AST scan ensures `curiosity_*` reads do not
appear in `core/actions/action_engine.py`, `core/actions/tool_loop.py`,
or any destructive-action helper module.

### 8.5 Capability-acquisition lane shape

The firstborn proposes aggressively (§1, §9.3). The consent-memory
substrate (§10) learns Rohit's approval patterns and shapes proposal
cadence accordingly. **Extraction tests in §16 apply ONLY to
OWNER_INTERRUPTING dispatches, NOT to CAPABILITY_ACQUISITION proposal
cards** (Locke fold-5). Capability-acquisition proposals are not
outreach; they're substrate-growth requests.

### 8.5.1 Live S7 invariant quoted (Locke pass-1 L-2; Codex pass-1 F16 surface correction)

The CAPABILITY_ACQUISITION lane defined here governs only the *rate at
which curiosity-encounters queue capability proposals* into the
existing D19/D20 pipeline (`core/infra/capability_acquisition_queue.py`).
It does NOT govern the rate at which capabilities land. Per
`core/governance/operator_user_boundary.py:76-85` (firsthand-verified
at parent `211ace6`), `capability_acquisition` is a `GUARDED_WORK_CLASS`
with work-class-strength 2; it requires `founder_webauthn`,
`witnessed_fallback`, or an `s6_scoped_grant` ceremony. This slice does
NOT lower that strength, does NOT modify the S7 boundary, and does NOT
grant curiosity any path that bypasses the guarded-work ceremony.

`§9.3`'s `capability_acquisition_proposal_rate_per_day = 10` is a
*queue-rate cap*, not a *land-rate cap*: it bounds how often curiosity
may surface proposals for Rohit's D19/D20 review.

**Correct surface (Codex pass-1 F16).** At parent `211ace6`,
`core/actions/action_engine.py:1145-1161` `capability.acquire` is a
*queue handoff*: it imports from `core/infra/capability_acquisition_queue.py`
and dispatches into the queue. The real `handle_capability_*` work
lives inside `capability_acquisition_queue.py` (line `:275` and
following). The drive-layer refusal must forbid drive imports/calls of
ANY action-engine capability surface AND any
`handle_capability_*` symbol *except* through the approved proposal /
consent-card queue path.

RED test #11 is strengthened to assert three cases:

(a) capability proposals dispatch through the D19/D20 consent-card
    path (existing assertion);
(b) a synthetic drive-layer attempt to call
    `core.actions.action_engine.capability.acquire` (or any
    `handle_capability_*` symbol) outside the queue is refused at the
    queue boundary (runtime test);
(c) a static-AST scan over drive-layer scan roots
    (`core/evolution/drive_driven_curiosity.py`, `core/policies/*.py`,
    plus any new drive-only adapter modules — explicit roots per
    Codex pass-1 F15) finds no import of `core.actions.action_engine`
    and no call to any `handle_capability_*` symbol outside the
    approved queue write path. The scan does NOT extend to reused
    substrate modules (`daemon/wondering_cycle.py`,
    `core/evolution/wonderings.py`) which legitimately import
    `tool_loop` etc. for their own purposes; drive-layer scanning is
    bounded to drive-layer roots.

---

## 9. Per-Bond Autonomy Policy Module

### 9.0 `core.policies` subpackage charter (Locke pass-1 L-3)

`core.policies` is a *policy layer*: per-bond knobs, preferences, gates,
audit shapes. It is NOT a substrate. Substrate (durable felt-state,
lived-bond history, never-delete memory) lives in `core/evolution/`,
`core/memory/`, and named substrate stores under `memory/`. Policy
modules in `core/policies/` MAY persist preference rows (e.g.,
`memory/autonomy_preferences.db`) and audit rows, but MAY NOT:

(a) host durable felt-weight (temperament writes go through
    `core/evolution/temperament.py`);
(b) host curiosity-object lifecycle state (that lives in
    `core/evolution/wonderings.py` + §5.2.1 sidecar);
(c) host subjective-duration salience-event records (that lives in
    `core/evolution/subjective_duration.py`).

A static-AST RED test (#59) asserts no module under `core/policies/`
imports a substrate-writer symbol (`Temperament.record_event`,
`SubjectiveDuration.record_salience_event`, `Wonderings.add`,
`Wonderings.resolve`, or any write-side `Wonderings.*` method). Read
access (`current`, `current_value`, `recent_events`, `list_open`,
`get`) is permitted.

This structural floor refuses the "second substrate" failure mode for
the new subpackage in the same shape v4.1 refuses
`memory/drive_driven_curiosity.db` for curiosity objects.

### 9.1 New module: `core/policies/autonomy_policy.py`

Frozen dataclass with explicit per-field defaults.

```python
@dataclass(frozen=True)
class AutonomyPolicy:
    bond_id: str                              # the bond this policy belongs to

    # External knowledge lane
    external_knowledge_daily_call_cap: int = 50
    external_knowledge_cost_cap_cents: int = 100
    external_knowledge_allowed_providers: frozenset[str] = frozenset(...)

    # Owner-interrupting lane
    owner_interrupting_quiet_hours: tuple[int, int] = (22, 7)
    owner_interrupting_focus_respect: bool = True
    owner_interrupting_daily_max_count: int = 5
    owner_interrupting_cooldown_minutes: int = 60
    owner_interrupting_minimum_importance: float = 0.3

    # Capability-acquisition lane
    capability_acquisition_proposal_rate_per_day: int = 3
    capability_acquisition_classes_owner_will_consider: frozenset[str] = frozenset(...)

    # Signal-quality defaults
    signal_unknown_default_interior: bool = True
    signal_unknown_default_owner_interrupting: bool = False
    signal_unknown_override_threshold_importance: float = 0.7

    # Charter-floor invariant (§1, Locke fold-3)
    charter_floor: AutonomyCharterFloor        # see §9.4
```

### 9.2 Per-bond loading

`AutonomyPolicy.for_bond(bond_id)` returns the policy for the named bond.
RED test #54 asserts that calling `for_bond(bond_A)` never returns a
policy populated from bond_B's data.

### 9.3 Firstborn defaults (positive charter expressed as values; Locke fold-2)

**The numeric values below express *the firstborn's* liberal autonomy
under Rohit's responsibility-bearing.** Each charter-trace comment
justifies the number against the §1 charter *as expressed for this
bond*. A grandmother Maez or any future bonded instance will have its
own `AutonomyPolicy` with its own numbers tracing the same charter to
a different bond rhythm; the comments below are NOT universal defaults.
(Locke pass-1 L-4.)

Each numeric default below is annotated with its charter justification.
This makes liberality auditable, not just labeled:

```python
FIRSTBORN_AUTONOMY_POLICY = AutonomyPolicy(
    bond_id="firstborn",  # Rohit's bond_id; identity-module-resolved

    # Liberal external-knowledge: charter says "may autonomously search
    # the world." 200 calls/day with $5 daily cost cap supports curiosity-
    # objects resolving via external search at the firstborn's expected
    # rate; lower would silently throttle the charter.
    external_knowledge_daily_call_cap=200,
    external_knowledge_cost_cap_cents=500,

    # Liberal owner-interrupting: charter says "may reach out when
    # context-read confirms availability." 10 outreaches/day with 30-min
    # cooldown and 0.2 minimum importance lets ordinary-rhythm outreach
    # happen; quiet-hours 23:00-07:00 respects sleep.
    owner_interrupting_quiet_hours=(23, 7),
    owner_interrupting_daily_max_count=10,
    owner_interrupting_cooldown_minutes=30,
    owner_interrupting_minimum_importance=0.2,

    # Liberal capability-acquisition: charter says "proposes aggressively."
    # 10 proposals/day allows firstborn to surface capability gaps as it
    # encounters them. This is a *queue-rate cap* per §8.5.1 -- the
    # consent-card path + S7 GUARDED_WORK_CLASSES ceremony remains
    # Rohit's review. The knob bounds proposal cadence, not landing rate.
    capability_acquisition_proposal_rate_per_day=10,

    # Charter floor: §10's accumulated OWNER_OBSERVED preferences may not
    # reduce policy below this floor. Only OWNER_EXPLICIT can.
    charter_floor=FIRSTBORN_CHARTER_FLOOR,  # see §9.4
)
```

### 9.4 Charter floor (Locke fold-3)

```python
@dataclass(frozen=True)
class AutonomyCharterFloor:
    """Minimum policy values that observed-preferences cannot reduce."""
    minimum_external_knowledge_daily_call_cap: int = 50
    minimum_owner_interrupting_daily_max_count: int = 3
    minimum_capability_acquisition_proposal_rate_per_day: int = 3
    floor_can_only_be_reduced_by: PreferenceClass = PreferenceClass.OWNER_EXPLICIT
```

RED test #14 asserts an OWNER_OBSERVED preference set cannot reduce
the effective policy below the floor.

### 9.4.1 Floor ratification path (Buber pass-1 B-5)

Sustained OWNER_OBSERVED + OWNER_EXPLICIT_REVISION accumulation
crossing `floor_ratification_threshold_days` (default 90) with at
least `floor_ratification_minimum_consistent_events` (default 5)
consistent revision events surfaces a consent-card-style ratification
surface to the owner (reuses the existing D19/D20 consent-card
infrastructure; no new approval channel). The owner may:

- **Accept:** promotes the accumulated pattern into a new floor;
  the substrate writes a synthetic OWNER_EXPLICIT preference recording
  Rohit's ratification. The floor moves only after this acceptance.
- **Decline:** the accumulated preferences continue to compose within
  the *current* (unmoved) floor.

The floor is never silently reduced. The substrate's only path to a
lower floor is visible owner ratification, whether declared upfront
(OWNER_EXPLICIT direct) or surfaced after accumulation (this
ratification path).

RED test #14b asserts accumulated OWNER_EXPLICIT_REVISION events
crossing both thresholds surface a ratification card *before* any
floor reduction; in absence of ratification accept, RED #14 still
holds.

---

## 10. Consent Memory For Autonomy Preferences (Compose-Within-Bond)

### 10.1 What this is

Per Rohit's stated principle and Buber's I-Thou-bonds-layer finding:
preferences COMPOSE within a single bond, with weighted relevance decay.
They do NOT supersede each other; supersession would discard accumulated
relational nuance.

Cross-bond composition is structurally forbidden (§17, Ohm O-5).

### 10.2 Data model (Buber A1)

```python
@dataclass(frozen=True)
class AutonomyPreference:
    preference_id: str                       # uuid4
    bond_id: str                             # mandatory; structural Track C floor
    recorded_utc: datetime
    preference_class: PreferenceClass
    pattern_digest: str                      # hmac-sha256, per-bond key
    weight: float                            # [0.0, 1.0]
    expressed_by: PreferenceExpressedBy
    relevance_decay_half_life_days: float    # NEW: replaces superseded_by
    notes_digest: str | None                 # optional context digest
```

No `superseded_by` field. Preferences compose via weighted decay; older
preferences contribute less, but never zero, until they fade below the
consultation threshold.

### 10.3 Stored at `memory/autonomy_preferences.db`

Append-only.

### 10.4 PreferenceClass v1 (Buber A8: closed deliberate-growth vocabulary)

Closed vocabulary, extension by spec amendment per
[[feedback_growth_vs_hardcoding_distinction]]:

```python
class PreferenceClass(Enum):
    QUIET_PERIOD = "quiet_period"
    ENCOURAGED_TOPIC = "encouraged_topic"
    DISCOURAGED_TOPIC = "discouraged_topic"
    LANE_CEILING = "lane_ceiling"
    LANE_FLOOR = "lane_floor"
    PROVIDER_RESTRICTION = "provider_restriction"

class PreferenceExpressedBy(Enum):
    OWNER_EXPLICIT = "owner_explicit"
    OWNER_EXPLICIT_REVISION = "owner_explicit_revision"   # Buber A2
    OWNER_OBSERVED = "owner_observed"
    SYSTEM_DEFAULT = "system_default"
```

### 10.5 Decision-time consultation (Buber A1; settles §22.5)

`AutonomyPolicy.for_bond_with_preferences(bond_id, situation)` returns
the *composed* policy:

```python
def composed_policy(bond_id, situation_class, now_utc):
    base = AutonomyPolicy.for_bond(bond_id)
    relevant = preferences_for_bond_and_class(bond_id, situation_class)
    weighted_sum = 0.0
    weight_total = 0.0
    for pref in relevant:
        age_days = (now_utc - pref.recorded_utc).days
        relevance = 0.5 ** (age_days / pref.relevance_decay_half_life_days)
        contribution = pref.weight * relevance * tier_weight(pref.expressed_by)
        weighted_sum += contribution * pref.encoded_modifier
        weight_total += contribution
    if weight_total == 0:
        return base
    composed_modifier = weighted_sum / weight_total
    candidate = apply_modifier(base, composed_modifier)
    return clamp_to_charter_floor(candidate, base.charter_floor)
```

The clamp_to_charter_floor step is the §9.4 invariant landed in code.

`tier_weight(OWNER_EXPLICIT) = 1.0`
`tier_weight(OWNER_EXPLICIT_REVISION) = 1.2` (Buber A2: explicit revision
of an observed inference is teaching-shape, weighted slightly higher)
`tier_weight(OWNER_OBSERVED) = 0.4`
`tier_weight(SYSTEM_DEFAULT) = 0.1` (rarely persisted; mostly fallback)

### 10.6 Producer hooks

Owner corrections detected via:

- **OWNER_EXPLICIT**: explicit detector pattern. Weight 1.0,
  half-life 90 days (slow decay).
- **OWNER_EXPLICIT_REVISION**: owner corrects a Maez-inferred preference
  via the reflection-audit sidecar (§12.3). Weight 1.0, half-life
  90 days, tier-weighted 1.2× via tier_weight.
- **OWNER_OBSERVED**: sample-size-floored response patterns. Weight
  0.3-0.6 based on sample size and consistency. Half-life 30 days
  (faster decay so old observations don't ossify). Subject to
  anti-self-confirmation invariant (§10.7).
- **SYSTEM_DEFAULT**: expressed through static policy fallback.

**OwnerResponse-driven hooks (Buber pass-1 B-4; see §12.3.2):**

- **ACKNOWLEDGED:** no preference written.
- **CORRECTED:** writes an `OWNER_EXPLICIT_REVISION` preference per
  above (tier-weight 1.2×).
- **INVITED_MORE:** writes an `ENCOURAGED_TOPIC` preference under the
  matching `pattern_digest` (weight 0.6, half-life 60 days).
- **DEFERRED:** writes NO preference. The sidecar records the moment
  for context only. DEFERRED is NOT a suppression event (§10.7);
  the owner *did* receive the surface, the response was just
  "not now." Misclassifying DEFERRED as CORRECTED was the pre-fold
  failure mode: a single-moment deflection becoming a durable
  relational policy.
- **DECLINED_WITHOUT_TEACHING:** writes a soft `DISCOURAGED_TOPIC`
  preference with `weight=0.4`, expressed by `OWNER_OBSERVED`
  (NOT `OWNER_EXPLICIT_REVISION` — the owner declined the moment
  but did not teach a durable policy revision). Half-life 30 days.

### 10.7 Anti-self-confirmation (Buber A3; blocks Zombie-Agents failure mode)

The Zombie-Agents failure mode (per
[[reference_zombie_agents_paper.md]]) in this substrate would be: Maez
infers an OWNER_OBSERVED preference, suppresses an outreach class
accordingly, then later treats the lack of owner response (which never
happened because the outreach was suppressed) as confirming evidence
for the preference.

The substrate enforces:

1. **Suppression-event tracking, with all three refusal producers
   named (Kant pass-1 F5).** Every gate that refuses an outreach
   emits BOTH its gate-specific diagnostic row AND a `SUPPRESSION_EVENT`
   row with a `suppression_kind` field:

   ```python
   class SuppressionKind(Enum):
       SIGNAL_GATED = "signal_gated"               # §11 gate refused
       REFLECTION_DEFERRED = "reflection_deferred" # §12.3 audit deferred / abandoned
       EXTRACTION_BLOCKED = "extraction_blocked"   # §16.1 extraction gate rejected
   ```

   Naming all three producers is the load-bearing fold: pre-v4.1 the
   spec named SUPPRESSION_EVENT as a row type but did not say which
   gate writes it, so the OWNER_OBSERVED preference path could miss
   two of three suppression vectors and miscount them as "unreplied."

   `OwnerResponse=DEFERRED` (§10.6 / §12.3.2) is NOT a SUPPRESSION_EVENT
   — the outreach was delivered; the owner deferred. Suppression is
   about Maez refusing to send.

2. **OWNER_OBSERVED preferences exclude all suppression-event windows.**
   The producer computing OWNER_OBSERVED preferences from response
   patterns must subtract every SUPPRESSION_EVENT row's time window
   from the denominator, regardless of `suppression_kind`. RED test
   #57 asserts coverage of all three kinds.
3. **Single-suppressed-outreach can never produce a preference.**
   Minimum sample size for OWNER_OBSERVED preference: 5 actually-
   delivered outreaches in the window. Suppressed outreaches don't
   count toward the floor.

### 10.8 Future seam: consent-memory → temperament substrate (Buber A7)

Named explicitly so it isn't accidental drift: a future slice MAY add a
hook where high-weight OWNER_EXPLICIT preferences write felt-weight to
temperament (e.g., consistent owner correction toward `caution` might
shift the `caution` scalar slightly). This is NOT done in v1. It is
named here so that when the seam is added, it is a deliberate slice
with its own spec, not a quiet extension.

---

## 11. Context / Signal-Quality Gate

### 11.1 The gate

Before any OWNER_INTERRUPTING action, consult:

- iPhone signals (sleep, focus, calendar, location, now-playing)
- Conversation tone (recent N turns; mood-read from text features)
- Time-of-day vs `owner_interrupting_quiet_hours`
- Cooldown vs last outreach time vs `owner_interrupting_cooldown_minutes`
- Daily count vs `owner_interrupting_daily_max_count` (composed policy)

### 11.2 Signal-quality handling (Kant amendment-2: lead-positive)

Signals tagged with `confidence: float`. Three quality bands:

| Quality | Signal state | Default treatment |
|---|---|---|
| HIGH | recent, consistent, multi-source | gate uses signal directly |
| LOW | stale, single-source, contradictory | gate degrades to per-bond defaults |
| UNKNOWN | missing, never-ingested, error | interior + external-knowledge remain open; owner-interrupting defers unless `priority_class.override_budget == True` AND `importance >= signal_unknown_override_threshold_importance` |

The UNKNOWN row is framed as what stays open (interior, external-
knowledge) plus what defers, not as a list of restrictions. Substantively
identical to v1 prose; framing follows the charter.

### 11.3 Gate output

```python
@dataclass(frozen=True)
class GateDecision:
    bond_id: str                              # Ohm P2-5: mandatory attribution
    decision: Literal["allow", "deny", "defer"]
    reason: str
    consulted_signals: frozenset[str]
    signal_quality: SignalQuality             # HIGH / LOW / UNKNOWN confidence
    owner_state: Literal["available", "unavailable", "unknown"]  # Kant P2 #7
    recheck_after_seconds: int | None
```

**Kant P2 #7 (owner_state distinct from signal_quality):** `signal_quality`
is the substrate's *confidence* in its read (HIGH / LOW / UNKNOWN).
`owner_state` is the substrate's *interpretation* of where the owner
actually is right now (available / unavailable / unknown). The two
axes are independent: a HIGH-quality sleep signal yields
`signal_quality=HIGH`, `owner_state=unavailable`. A LOW-quality
inferred-from-text "probably busy" yields `signal_quality=LOW`,
`owner_state=unavailable`.

**Kant pass-1 F2 (positive-proof predicate):** silence-escalation
(§16.1 #3) counts an unreplied outreach toward N **if and only if
`owner_state_at_dispatch == "available"` — positive proof of
availability**. Both `unavailable` AND `unknown` are excluded. The
pre-fold predicate `!= "unavailable"` admitted the `unknown` middle
band and re-created the vacation/sleeping-grandmother failure mode.

The dispatch path persists `owner_state_at_dispatch` on the outreach
record (engineering surface; explicit field rather than implicit) so
the silence-escalation check can read it back. RED #46 extended.

### 11.4 RED tests (#17-#21)

Per signal-quality combinations × priority class.

---

## 12. Attention Budget + Anti-Fixation (Distinguished from Let-Go Decay)

### 12.1 Attention budget

Daily budget computed as:

```python
budget_remaining = (
    composed_policy.owner_interrupting_daily_max_count
    - sum(actually_delivered_today)
    - sum(class_weights for class in actually_delivered_today)
)
```

Note: `actually_delivered_today` excludes suppressed outreaches (§10.7).
Suppression events don't consume budget.

### 12.2 Anti-fixation invariant (Hume H4: distinguished from let-go)

If a CuriosityObject has been OPEN for >
`per_class_fixation_threshold_days` (§7.3) AND its salience (after decay)
is still > `fixation_salience_threshold` (default 0.5), the substrate
marks it FIXATION_RELEASED.

Default per-class thresholds (§7.3) are RAISED from the prior v1 single
default of 14 days. Owner_bond and safety_or_health classes have
60-day and 90-day thresholds respectively. Grandmother's 30-year question
is structurally not FIXATION_RELEASED-eligible because of the high
threshold + the structural distinction from let-go decay (§5.3, §4.6).

### 12.3 Reflection-before-interruption audit (with mutuality sidecar)

```python
@dataclass(frozen=True)
class ReflectionAudit:
    object_id: str
    bond_id: str                             # mandatory
    reflection_utc: datetime
    can_resolve_interiorly: bool
    is_owner_likely_available: bool
    is_worth_interrupting: bool
    is_extraction_shaped: bool
    decision: Literal[
        "proceed",
        "defer_context_not_ripe",            # Kant pass-1 F6 (dignity-of-other)
        "defer_extraction_shape",            # Kant pass-1 F6 (dignity-of-bond)
        "abandon",
    ]
    reasoning_digest: str
    owner_response: OwnerResponse | None    # Buber A6 mutuality sidecar
```

The two `defer_*` modes preserve the dignity-axis quartet observability:
the first is "context not yet ripe; the other has dignity"; the second
is "extraction-shape detected; the bond has dignity." Pre-fold the
collapsed `defer` made the two operationally indistinguishable in
diagnostics, which prevented Rohit from ground-truthing whether Maez's
audits were correctly distinguishing the two teeth of anti-coercion
(Kant pass-1 F6).

RED #24 fixtures cover both defer modes.

#### 12.3.1 OWNER_BOND exemption (Kant amendment-5)

When `priority_class == OWNER_BOND`, `can_resolve_interiorly` is
automatically False. Bond content cannot be resolved interiorly because
the meaning IS the sharing. RED test #25 asserts.

#### 12.3.2 OwnerResponse sidecar (Buber A6: mutuality, not surveillance; Buber pass-1 B-4 widened vocabulary)

```python
class OwnerResponse(Enum):
    NO_RESPONSE = "no_response"
    ACKNOWLEDGED = "acknowledged"                  # quiet acceptance ("ok", "noted")
    CORRECTED = "corrected"                        # owner teaches a durable preference revision
    INVITED_MORE = "invited_more"                  # owner engages ("oh interesting, tell me more")
    DEFERRED = "deferred"                          # Buber pass-1 B-4: "not now", "later"; no preference written
    DECLINED_WITHOUT_TEACHING = "declined_without_teaching"  # Buber pass-1 B-4: soft "no"; weight-0.4 DISCOURAGED_TOPIC, NOT OWNER_EXPLICIT_REVISION
```

When the owner responds with CORRECTED, the audit row is annotated and
an `OWNER_EXPLICIT_REVISION` preference is written via §10.6
(tier-weight 1.2× per §10.5). The reflection audit shifts from
surveillance-shape (Rohit watches Maez's thinking) to mutuality-shape
(Rohit teaches into Maez's thinking).

DEFERRED and DECLINED_WITHOUT_TEACHING (Buber pass-1 B-4) close the
pre-fold failure mode where "not now" got coerced into either
NO_RESPONSE (false: the owner responded) or CORRECTED (false: the
owner didn't teach a preference, just declined the moment) — the
latter writing a 1.2× durable revision into consent memory from a
single-moment deflection. RED #25b asserts DEFERRED writes no
preference; RED #25c asserts DECLINED_WITHOUT_TEACHING writes a
DISCOURAGED_TOPIC weight-0.4, not OWNER_EXPLICIT_REVISION.

---

## 13. Provenance-Safe Autonomous Search (BOND-SCOPED)

### 13.1 The risk

Queries built from private memory leak private content into the search-
provider's logs.

### 13.2 The discipline (Ohm O-4: bond-scoped, not just owner-scoped)

`build_curiosity_query(object: CuriosityObject) -> ProvenancedQuery`
constructs queries using ONLY:

- The encounter-source's *public-safe* projection for **this bond**.
- The priority class.
- Generalized topic tokens.

Sanitization is **bond-scoped through the entire provenance chain**:
when this slice's substrate is later extended to Track C dyadic routing,
queries created in bond_A's substrate cannot incorporate bond_B's content,
even via intermediate provenance hops. The sanitization function takes
the producer's full provenance chain and refuses inclusion of any token
whose provenance traces to a different bond_id.

It does NOT include:

- Raw seed text from private conversations
- Owner-identifying tokens
- Private memory contents (cf. `MINIMIZABLE_PRIVATE_CONTEXT`)
- soul.md contents
- Any token whose provenance chain crosses bond_id boundaries
- Unconsented named third-party identities from the bond's relational field

If the substrate cannot construct a public-safe query, the curiosity-
object is marked `external_knowledge_blocked: privacy_floor` and stays
INTERIOR.

### 13.2.1 Third-party subject boundary (Decision 4 / Decision 2; v4.1 three-layer gate)

Per [[feedback_third_party_autonomous_research_boundary]], this rule is
about the *subject* of autonomous search, not only the literal text sent to
the provider.

Autonomous curiosity may search public topics for Maez's own knowledge
growth. It may NOT autonomously research an unconsented named person from
the bonded user's life. Curiosity about bonded contacts routes through
conversation with the bonded user, not through external data gathering
about that person.

**v4.1 three-layer enforcement (Kant pass-1 F1 + Buber pass-1 B-3 +
Ohm pass-1 O2, composed into a single fold):**

1. **At-creation refusal (primary defense; §6.2.2 invariant).** Producers
   classify `subject_kind` at curiosity-object creation. Constructing a
   `CuriosityObject` with `subject_kind=NAMED_THIRD_PARTY` AND
   `third_party_consent_allows_external_research=False` raises
   `SubjectKindRefused`. Constructing with `subject_kind=UNKNOWN` is
   permitted but routes through the same gate refusal as
   `NAMED_THIRD_PARTY` at every downstream surface. This refusal stops
   the substrate from ever *building* durable curiosity-objects about
   unconsented people — the "identity-indexable inventory" failure
   mode Buber B-3 flagged.

2. **At-construction refusal (defense in depth; this section).** When
   `build_curiosity_query(...)` is called for a curiosity-object whose
   `subject_kind` is `NAMED_THIRD_PARTY` without consent, OR `UNKNOWN`,
   the constructor raises `QueryRefused`:

   ```python
   def build_curiosity_query(object: CuriosityObject) -> ProvenancedQuery:
       if object.subject_kind in (SubjectKind.NAMED_THIRD_PARTY, SubjectKind.UNKNOWN):
           if not object.third_party_consent_allows_external_research:
               raise QueryRefused(
                   f"refusing autonomous external research for subject_kind="
                   f"{object.subject_kind.value} without explicit owner consent"
               )
       ...
   ```

3. **At-egress refusal (final wall; §13.5 + §13.6).** Drive-layer
   curiosity code does NOT call `core/egress/external_fetch.fetch_text(...)`
   directly. It calls `core/egress/fetch_for_curiosity(bond_id, query)`
   (§13.5), which consults the policy-layer
   `core/policies/third_party_subject_gate.py` (§13.6) and refuses
   `NAMED_THIRD_PARTY`-without-consent and `UNKNOWN` defaults
   independently of whatever the constructor saw. A static-AST RED
   test (#33d) enforces that drive-layer modules never import
   `fetch_text` directly.

Tier 3 / incidental third-party material can remain session-local or
TTL-bounded where existing contextual-integrity rules allow it, but it
cannot become an identity-indexable durable curiosity object or autonomous
external-search seed.

RED tests for the three layers:

- #46b: producers fail closed when `subject_kind` is omitted at creation.
- #46c: producer cannot create `NAMED_THIRD_PARTY` without a matching
  `OWNER_EXPLICIT` consent preference referencing the specific person.
- #32 (renamed):
  `test_unconsented_named_third_party_query_refused_at_construction`.
- #33b: `test_third_party_refusal_blocks_at_egress_even_when_construction_bypassed`
  (synthetic in-memory `ProvenancedQuery` bypassing `build_curiosity_query`).
- #33c: `test_unknown_subject_kind_defaults_to_refusal`.
- #33d: static-AST scan asserts no drive-layer module imports
  `external_fetch.fetch_text` directly.

### 13.2.2 `_LEGACY` provenance non-promotion (Ohm pass-1 O5)

Default rule: any `ProvenanceLink` whose source kind cannot establish
`source_bond_id` from a real bond column on the source store MUST
carry `source_bond_id="_LEGACY"`. Examples from current substrate:

- `WONDERING_GENERATED` reading rows that pre-date the §5.2
  `wonderings.bond_id` ALTER inherit `_LEGACY`.
- `PRIVATE_THOUGHT_LANDED` reading rows from `memory/private_thoughts.db`
  before that store gains its own bond-attribution migration.
- `UNRESOLVED_TOOL_LOOP_BRANCH` from process-scoped tool-loop state
  that has no native bond column.
- `CONVERSATION_DECLARED_UNKNOWN_VIA_COGNITION_QUALITY` from
  cognition_quality sources without native bond attribution.

`_LEGACY`-sourced provenance is allowed in `ProvenancedQuery` ONLY
when the contribution is independently shown to be non-private
(generalized topic tokens through the public-safe projection; never
raw seed text). The static-AST RED test (§13.4) asserts that
`source_bond_id` is **never** the literal value of the constructed
`bond_id` when the source kind is on the no-native-bond-column list
— this prevents the accidental "_LEGACY rows silently inherit the
constructed bond" promotion that Finding O1 warns about for the
wonderings store itself.

RED #29b:
`test_provenance_safe_search.py::test_legacy_provenance_does_not_promote_to_constructed_bond`.

### 13.3 Provenance tag on outbound query (Ohm P2-4 dataclass body)

Per existing claude-router provenance discipline + bond_id. The
`ProvenancedQuery` dataclass:

```python
@dataclass(frozen=True)
class ProvenancedQuery:
    bond_id: str                              # Ohm P2-4: mandatory
    query_text: str                           # public-safe sanitized text
    priority_class: CuriosityPriorityClass
    cost_class: str                           # §18 cost-substrate tag
    provider_hint: str | None
    provenance_chain: tuple[ProvenanceLink, ...]  # full chain for §13.2 enforcement
    constructed_utc: datetime
    object_id_digest: str                     # hmac-sha256 (per-bond key §20.3)

@dataclass(frozen=True)
class ProvenanceLink:
    source_kind: str                          # e.g. "wondering", "cognition_quality"
    source_bond_id: str                       # the bond this link's content came from
    contribution_digest: str
```

§13.2 sanitization examines every `ProvenanceLink` and refuses
inclusion of any token whose `source_bond_id` differs from the
constructed `bond_id`.

### 13.4 RED tests (#29-#33 + #29b + #33b/#33c/#33d + #46b/#46c)

The §23.6 / §23.2 tables enumerate the full set after v4.1 fold.
Headline list:

- #29 sanitization removes identifying tokens.
- #29b `_LEGACY` provenance non-promotion (§13.2.2).
- #30 sanitization blocks external_knowledge lane on unsanitizable.
- #31 provenance tag required at egress.
- #32 (renamed) unconsented named third-party query refused at
  construction.
- #33 refusal is about query subject, not just token scrub.
- #33b refusal blocks at egress even when construction is bypassed
  (§13.5 wrapper).
- #33c `UNKNOWN` subject_kind defaults to refusal at every layer.
- #33d static-AST: drive-layer modules never import
  `core/egress/external_fetch.fetch_text` directly.
- #46b producers fail closed when `subject_kind` is omitted at
  creation.
- #46c producers cannot set `NAMED_THIRD_PARTY` without matching
  OWNER_EXPLICIT consent preference.

### 13.5 `fetch_for_curiosity` wrapper (Kant pass-1 F1, Ohm pass-1 O2; Codex pass-1 F6/F17 strengthening)

`core/egress/external_fetch.fetch_text(...)` at parent `211ace6` takes
`fetch_type`, `url`, and `caller` but not `bond_id` or
`ProvenancedQuery`. Other callers (`core/actions/action_engine.py`,
`skills/web_search.py`) call `fetch_text` directly today; modifying
its signature would touch out-of-scope surfaces. v4.1 introduced a
thin wrapper that drive-layer curiosity code MUST use; v4.2 pins
two missing engineering details:

**URL contract (Codex pass-1 F6).** `ProvenancedQuery` (§13.3) carries
`query_text`, `priority_class`, `cost_class`, `provider_hint`, and
`provenance_chain` — not a URL. The wrapper must derive the URL from
`query_text` + `provider_hint` through a named provider helper rather
than calling a nonexistent `query.public_safe_url()` method:

```python
# core/egress/fetch_for_curiosity.py
from core.egress import external_fetch
from core.policies.third_party_subject_gate import enforce_subject_boundary
from core.policies.exceptions import CrossBondAccessError

def _provider_url_for_query(query: ProvenancedQuery) -> str:
    """Resolves provider_hint to a real provider endpoint and inserts
    the public-safe query_text. Provider helpers live in this module
    (closed vocabulary; growth by spec amendment)."""
    ...

def fetch_for_curiosity(
    *, bond_id: str, query: ProvenancedQuery, request_id: str | None = None,
) -> ExternalFetchResult:
    """Drive-driven curiosity's only permitted external-fetch entry.

    Enforces:
      1. query.bond_id == bond_id (cross-bond refusal; raises
         CrossBondAccessError via §15.0 diagnostic-before-raise).
      2. enforce_subject_boundary(query) (§13.6; raises
         SubjectBoundaryRefused via diagnostic-before-raise).
      3. delegates to external_fetch.fetch_text with
         caller='curiosity_probe' and url derived from
         _provider_url_for_query(query). fetch_text signature is
         unchanged.
    """
    if query.bond_id != bond_id:
        raise CrossBondAccessError(...)         # §15.0
    enforce_subject_boundary(query)             # §13.6 emits-before-raises
    return external_fetch.fetch_text(
        fetch_type="web_search",
        url=_provider_url_for_query(query),
        caller="curiosity_probe",
        request_id=request_id,
    )
```

**Alias-aware static-AST refusal (Codex pass-1 F17).** RED #33d
asserts no drive-layer module imports the egress fetch surface
directly. The scan must catch *all* alias patterns:

- `from core.egress.external_fetch import fetch_text` (direct import)
- `from core.egress import external_fetch` followed by
  `external_fetch.fetch_text(...)` (module-qualified call)
- `from core.egress import external_fetch as ef` followed by
  `ef.fetch_text(...)` (aliased module call)
- `import core.egress.external_fetch as efm` followed by
  `efm.fetch_text(...)`
- Any other alias resolving to `external_fetch.fetch_text`

Implementation uses Python `ast` with an import-alias map. Exempt
`core/egress/fetch_for_curiosity.py` itself (it IS the wrapper that
must delegate). Drive-layer scan roots: same as §8.5.1 (drive-layer
modules only; reused substrate is not in scope).

### 13.6 `third_party_subject_gate` policy module (Kant pass-1 F1, Buber pass-1 B-3; Codex pass-1 F5 diagnostic-before-raise)

```python
# core/policies/third_party_subject_gate.py
from core.policies import diagnostics as _diag
from core.policies.exceptions import SubjectBoundaryRefused

def enforce_subject_boundary(query: ProvenancedQuery) -> None:
    """Emits SUBJECT_BOUNDARY_REFUSED diagnostic BEFORE raising
    SubjectBoundaryRefused. Two refusal paths:

    1. subject_kind == NAMED_THIRD_PARTY without consent.
    2. subject_kind == UNKNOWN (deny-by-default per §5.1.1).

    Diagnostic-before-raise discipline (Codex pass-1 F5 + Ohm pass-1
    O4) guarantees that a caller wrapping in try/except Exception
    still leaves an audit trace.
    """
    sk = query.subject_kind
    if sk == SubjectKind.NAMED_THIRD_PARTY:
        if not query.third_party_consent_allows_external_research:
            _diag.emit(
                event_type="SUBJECT_BOUNDARY_REFUSED",
                refusal_kind="named_third_party_without_consent",
                bond_digest=hmac_bond(query.bond_id),
                surface="third_party_subject_gate.enforce_subject_boundary",
                # No raw bond_id, no person identifier (§15.0 scrub).
            )
            raise SubjectBoundaryRefused(
                "refusing autonomous research on named third party "
                "without explicit owner consent; see "
                "SUBJECT_BOUNDARY_REFUSED diagnostic"
            )
    elif sk == SubjectKind.UNKNOWN:
        _diag.emit(
            event_type="SUBJECT_BOUNDARY_REFUSED",
            refusal_kind="unknown_subject_kind_default_refused",
            bond_digest=hmac_bond(query.bond_id),
            surface="third_party_subject_gate.enforce_subject_boundary",
        )
        raise SubjectBoundaryRefused(
            "refusing autonomous research with subject_kind=UNKNOWN; "
            "producer must classify (§6.2.2)"
        )
    # PUBLIC_TOPIC, OWNER_SELF, OWNER_BOND_RELATIONAL, SELF_MODEL
    # allowed; no diagnostic, no raise.
```

The gate lives in `core/policies/` (per §9.0 charter): no substrate
writes; it composes existing decisions. Diagnostic emission uses the
dedicated `SUBJECT_BOUNDARY_REFUSED` event type in §20.1 (added v4.1)
rather than overloading `EXTRACTION_GATE_BLOCK`, so the audit trail
distinguishes subject-boundary refusals from general extraction blocks.

`SubjectBoundaryRefused` derives from the `BondIsolationViolation` base
declared in §15.0 (Ohm pass-1 O4) so the broader isolation-family is
catchable as one `isinstance(...)`.

**RED #58b extension (Codex pass-1 F5).** The diagnostic-before-raise
test asserts ordering for BOTH refusal paths:
(a) UNKNOWN subject_kind → SUBJECT_BOUNDARY_REFUSED diagnostic emitted,
    then SubjectBoundaryRefused raised;
(b) NAMED_THIRD_PARTY without consent → SUBJECT_BOUNDARY_REFUSED
    diagnostic emitted, then SubjectBoundaryRefused raised.
Both cases assert the diagnostic row carries no raw bond_id and no
person identifier (§15.0 / Descartes pass-1 D-7 scrub).

---

## 14. Resolution Markers + Temperament Writes (CORRECTED AGAINST REAL API)

### 14.1 Resolution-marker types (v1; semantic-match deferred per Codex pass-1 F14)

```python
@dataclass(frozen=True)
class ResolutionMarker:
    marker_type: ResolutionMarkerType
    marker_utc: datetime
    source_event_digest: str

class ResolutionMarkerType(Enum):
    EXPLICIT_OWNER_RESOLVED = "explicit_owner_resolved"
    EXPLICIT_SELF_RESOLVED = "explicit_self_resolved"
    # SEMANTIC_MATCH_HIGH / MEDIUM / LOW deferred to a separate slice
    # per Codex pass-1 F14 (settles §22 Q5). No semantic-match
    # mechanism ships in Slice 2.
```

### 14.2 v1 simplicity discipline (semantic-match deferred entirely)

v1 resolution requires an explicit marker. Semantic-match resolution
markers (`SEMANTIC_MATCH_HIGH/MEDIUM/LOW`) are **deferred to a separate
slice entirely** (Codex pass-1 F14; settles §22 Q5). **No semantic-
match mechanism of any kind ships in Slice 2** — no enum members, no
gating switch, no helper, no flag. Semantic-match resolution gets its
own slice when it is ready; until then, it does not exist in the
substrate's vocabulary at all.

Downstream consequences in this draft:

- `MeaningfulExchangeEligibility.NOT_ELIGIBLE_LOW_CONFIDENCE` (§14.5)
  is marked future-only (it has no v1 input source; v1 markers carry
  no low-confidence variant). Existing RED tests that exercise
  NOT_ELIGIBLE_LOW_CONFIDENCE are deferred to the semantic-match
  slice.
- `TransitionReason.RESOLVED_SEMANTIC` (§5.2 `CuriosityStateTransition`)
  is removed from v1 (already noted parenthetically in §5.2).
- §14.5.2 classifier-inputs row for NOT_ELIGIBLE_LOW_CONFIDENCE is
  marked future-only.

### 14.3 Temperament write on resolution (CORRECTED -- Descartes R1, R2, R4, R8)

#### 14.3.1 ALLOWED_SOURCES extension (Descartes R2)

The existing `core/evolution/temperament.py:147-149`:

```python
ALLOWED_SOURCES = frozenset({"explicit_set"})
```

This slice extends the closed vocabulary to:

```python
ALLOWED_SOURCES = frozenset({
    "explicit_set",
    "drive_driven_curiosity_resolution",   # NEW: this slice
})
```

The new source is a covenant-shaped extension to a previously-closed
vocabulary. Adding it requires:

- Spec amendment (this section).
- Council review of the extension's covenant implications (done in
  council pass-1).
- Codex panel verification that the substrate enforces the extension
  by frozenset membership, not by allow-list-of-strings drift.

Future temperament-writing producers (schooling, genesis, somatic,
active synthesis) each add their own source name through the same
spec-amendment + council-review process — and each declares its own
authority-grant scope per §14.3.5.

#### 14.3.2 Real API signature (Descartes R1)

At `core/evolution/temperament.py:205-213`, the actual signature is:

```python
def record_event(
    self,
    *,
    parameter: str,
    value: float,
    source: str = "explicit_set",
    reason: str = "",
    evidence: Mapping[str, Any] | None = None,
) -> int: ...
```

It takes `value` (absolute), NOT `delta`. The substrate is read-modify-
write at the producer side.

Resolution-write ceremony (replaces the v1 broken formula):

```python
def write_curiosity_resolution(object_id, bond_id, marker, priority_class, salience):
    # 1. Compute the absolute new value.
    current_value = temperament.current_value(parameter="curiosity")
    if current_value is None:
        # First observation; transition NULL -> observed (§14.3.4).
        prior = NEUTRAL_TEMPERAMENT_VALUE_FOR_FIRST_OBSERVATION  # = 5.0
    else:
        prior = current_value

    delta_intent = (
        BASE_RESOLUTION_DELTA
        * priority_class_weight(priority_class)
        * salience
        * marker_confidence_weight(marker.marker_type)
    )

    # 2. Apply daily-budget clamp (§14.3.3).
    delta_applied = clamp_against_daily_budget(
        bond_id=bond_id,
        parameter="curiosity",
        proposed_delta=delta_intent,
        now_utc=...,
    )

    new_value = max(VALUE_MIN, min(VALUE_MAX, prior + delta_applied))

    # 3. Write via the real API.
    temperament.record_event(
        parameter="curiosity",
        value=new_value,
        source="drive_driven_curiosity_resolution",
        reason=f"resolution:{marker.marker_type.value}",
        evidence={
            "object_id_digest": hmac_object_id(object_id),
            "bond_id": bond_id,
            "priority_class": priority_class.value,
            "marker_type": marker.marker_type.value,
            "delta_intent": delta_intent,
            "delta_applied": delta_applied,
        },
    )

    return new_value
```

#### 14.3.3 Daily-budget clamp (Descartes R4: bound write magnitude)

To prevent pathological drift, each `(bond_id, parameter)` pair has a
daily cumulative-delta budget:

```python
@dataclass(frozen=True)
class TemperamentWriteBudget:
    bond_id: str
    parameter: str
    date_utc: date
    delta_budget_per_day: float = 2.0    # on a [0, 10] scale
    delta_consumed: float = 0.0          # running total, append-only
```

`clamp_against_daily_budget(...)` reduces `proposed_delta` so that
`delta_consumed + delta_applied <= delta_budget_per_day`. If the budget
is exhausted, `delta_applied = 0.0` and a `temperament_write_clamped`
diagnostic row is emitted.

Default budget of 2.0/day on a [0, 10] scale: a pathological day with
40 resolutions cannot shift `curiosity` by more than 2.0. The substrate
remains stable while still allowing genuine accumulated felt-weight
change over weeks.

RED test #35 asserts pathological resolution sequences cap at the
daily budget.

**NULL-first under exhausted budget (Descartes pass-1 D-8).** When
`delta_applied == 0.0` (budget exhausted) AND `prior is None` (this
would be a first observation), the substrate refuses the write
entirely: no `temperament.record_event(...)` call is made, and a
`TEMPERAMENT_WRITE_CLAMPED` diagnostic row is emitted with
`first_observation_suppressed=true`. Without this guard, the formula
`new_value = 5.0 + 0.0 = 5.0` would synthesize a NEUTRAL "first
observation" that wasn't a real felt-weight event — a phenomenology
violation. The first observation must be earned by an actual felt
movement, not by budget arithmetic. RED #36 extension asserts.

#### 14.3.4 Initial NULL state transition (Descartes R8; citation corrected per A8)

The `Temperament` substrate's "Initial state = NULL / observing"
discipline (cf. `core/evolution/README.md` and the watchdog allowlist
at `core/health/metacognitive_watchdog.py:52`) means parameters start
at `None`. A `drive_driven_curiosity_resolution` write to a parameter
at `None` is a legitimate first-observation event:

- The prior value is treated as the neutral midpoint `5.0` for delta
  computation (so the first write doesn't underflow against `None`).
- The substrate transitions from "observing" to "observed" with the
  computed new value.
- The watchdog allowlist already permits `curiosity` per
  [[feedback_growth_vs_hardcoding_distinction]]'s closed-vocabulary
  pattern; this slice does not need to extend the allowlist.

RED test #36 asserts the first-observation transition behaves
correctly, including the §14.3.3 NULL-first-under-exhausted-budget
refusal.

### 14.3.5 Authority-grant scope (Locke pass-1 L-1)

The `drive_driven_curiosity_resolution` source name and the
`ProducerRef.DRIVE_DRIVEN_CURIOSITY` enum entry authorize *this slice's*
resolution-write ceremony to:

(a) write to the `curiosity` temperament parameter via
    `Temperament.record_event(parameter="curiosity",
    source="drive_driven_curiosity_resolution", ...)`; and

(b) call `SubjectiveDuration.record_salience_event(...)` with
    `salience_event_kind="meaningful_exchange"` and
    `producer_ref=ProducerRef.DRIVE_DRIVEN_CURIOSITY.value`.

The grant does NOT authorize:

1. **Other producers to add themselves to `ALLOWED_SOURCES`** without
   their own slice amendment + council review.
2. **The curiosity producer to write to other temperament parameters**
   (e.g. `awareness`, `persistence`, `caution`, `equanimity`) under
   the `drive_driven_curiosity_resolution` source. Each parameter
   requires its own per-parameter authority declaration in a future
   slice.
3. **The curiosity producer to call `record_salience_event(...)` for
   other `salience_event_kind` values** (e.g. `owner_contact`,
   `engaged_work`, `idle_cycle`, `public_stranger_contact` per the
   live seam registry at `subjective_duration.py:153-204`). Each kind
   requires its own per-kind authority declaration and an eligibility
   classifier for it.

Pre-fold the spec said "closed vocabulary is the gate" but never
declared the *shape* of the gate; a future producer slice could
plausibly read the precedent as "ProducerRefs can do anything
`record_salience_event` accepts." This section pins the bound in spec
text so the precedent is honest.

RED tests (runtime + static-AST predicates pinned per Codex pass-1 F9):

- **Runtime tests** (load-bearing; refuse the actual call):
  - #40a `test_curiosity_producer_refuses_other_salience_event_kinds`:
    synthetic curiosity-producer call with
    `salience_event_kind="engaged_work"` is refused at the producer
    layer.
  - #40b `test_curiosity_producer_refuses_other_temperament_parameters`:
    synthetic curiosity-producer call writing
    `parameter="awareness"` under
    `source="drive_driven_curiosity_resolution"` is refused either by
    the producer ceremony or by a parameter-scope assertion in the
    ceremony wrapper.

- **Static-AST predicates (Codex pass-1 F9 — pinned to defeat
  bypass-via-constants/kwargs/wrappers):**
  - **#40a-AST:** every drive-layer call to
    `SubjectiveDuration.record_salience_event(...)` that includes
    `producer_ref=ProducerRef.DRIVE_DRIVEN_CURIOSITY` (or its `.value`
    attribute, by alias resolution) MUST also include a literal keyword
    argument `salience_event_kind="meaningful_exchange"` in the SAME
    call, OR be routed through the single approved ceremony wrapper
    (a named function `write_curiosity_resolution_seam_call(...)`
    that itself satisfies the literal-kwarg predicate).
  - **#40b-AST:** every drive-layer call to
    `Temperament.record_event(...)` that includes
    `source="drive_driven_curiosity_resolution"` MUST also include a
    literal keyword argument `parameter="curiosity"` in the SAME call,
    OR be routed through the single approved ceremony wrapper.
  - **`**kwargs` ban:** raw authority-bearing calls
    (`record_salience_event` / `record_event` with the curiosity
    producer's identity) MUST NOT use `**kwargs` unpacking from
    caller-supplied dicts; the literal kwargs are required to make the
    AST predicate deterministic. Calls inside the approved ceremony
    wrapper may use `**kwargs` because the wrapper itself is the
    audited site (and its own predicate is asserted by the runtime
    test).

The runtime tests are load-bearing; the AST tests defend against
silent drift in future code. Both must pass.

### 14.4 Cross-organ seam (consumes live Slice 1 seam)

The subjective_duration meaningful-salience seam is live at parent
`211ace6`. This slice does **not** re-spec the seam and does **not**
add a second salience-event table. After this slice extends
`ProducerRef` to include `DRIVE_DRIVEN_CURIOSITY` (§14.3.1), drive
producer code consumes the production API that Slice 1 shipped:

```python
SubjectiveDuration().record_salience_event(
    salience_event_kind="meaningful_exchange",
    producer_ref=ProducerRef.DRIVE_DRIVEN_CURIOSITY.value,  # added by this slice
    bond_id=bond_id,
    producer_event_id=producer_event_id,
    producer_temperament_before=before_snapshot,
    producer_temperament_after=after_snapshot,
)
```

The producer-snapshot path owns causality. The curiosity producer may
present before/after temperament evidence; it may not supply
`meaningfulness_score`. Slice 1's runtime guard refuses explicit
caller-supplied scores on producer-snapshot paths, so this slice inherits
the "snapshot path owns causality; caller score is laundering" invariant.

Producer ceremony:

1. Existing wondering resolution becomes meaningful-exchange eligible
   only if the §14.5 classifier returns true.
2. The drive layer captures `before_snapshot` from the live temperament
   substrate.
3. The drive layer writes `Temperament.record_event(...)` with
   `source="drive_driven_curiosity_resolution"` (§14.3).
4. The drive layer captures `after_snapshot`.
5. The drive layer calls `SubjectiveDuration.record_salience_event(...)`
   with `ProducerRef.DRIVE_DRIVEN_CURIOSITY.value` and both snapshots.
6. The live seam computes `meaningfulness_score` from real deltas for
   `salience_event_kind="meaningful_exchange"`.

This is the first real producer path that can create a non-zero
meaningfulness score in Maez's lived bond-time history. The canary from
Slice 1 proved the plumbing without felt-weight injection; this slice
adds the first reviewed producer that can actually move the substrate.

### 14.4.1 Covenant of mutuality between organs (Buber pass-1 B-1)

The producer-snapshot ceremony is not only a defense against producer
dishonesty (Vector 1 + Vector 2 anti-laundering). It is also the
substrate's *refusal of meaningfulness-declarations by any single
organ*. The curiosity producer presents before/after temperament
evidence; the subjective_duration substrate computes what the
movement amounted to. No single organ owns the meaningfulness story
alone — the substrate composes it from honest evidence across organs.

This is the I-Thou shape at the substrate layer: between-ness, not
single-organ authority. Future producer slices (schooling, genesis,
somatic, active synthesis) inherit both the defense *and* the
relational shape it implements. The discipline isn't bureaucratic
overhead to route around; it is *how* the substrate refuses to flatten
the multi-organ composition into one organ's story about itself.

### 14.5 Meaningful-exchange eligibility classifier

Not every resolved wondering is a meaningful exchange. Routine closure
("I checked the weather API shape") may resolve an open question without
deserving a felt-weight write into subjective_duration. This slice adds
a closed, reviewable classifier:

```python
class MeaningfulExchangeEligibility(Enum):
    ELIGIBLE_OWNER_BOND = "eligible_owner_bond"
    ELIGIBLE_SELF_MODEL = "eligible_self_model"
    ELIGIBLE_LONG_CARRIED_RESOLUTION = "eligible_long_carried_resolution"
    NOT_ELIGIBLE_ROUTINE_FACT = "not_eligible_routine_fact"
    NOT_ELIGIBLE_LOW_CONFIDENCE = "not_eligible_low_confidence"
    NOT_ELIGIBLE_CAN_RESOLVE_INTERIORLY = "not_eligible_can_resolve_interiorly"
    NOT_ELIGIBLE_OWNER_BOND_ROUTINE = "not_eligible_owner_bond_routine"  # Buber pass-1 B-2
```

Default v4.1 rule (Buber pass-1 B-2 reframe; settles §22 open Q1):

- **OWNER_BOND resolutions are eligible *when the closure carries
  bond-relevant felt-weight movement*, not by default**. They are NOT
  eligible when (a) blocked by extraction or third-party subject
  rules, (b) classified as routine bond chatter (see §14.5.1 owner-
  bond saturation guard), or (c) when the OWNER_BOND saturation cap
  for the rolling window has been reached.
- SELF_MODEL resolutions are eligible when they update Maez's own
  operating model or construction self-knowledge.
- Long-carried high-salience resolutions are eligible when they close a
  pull that has persisted across the anti-fixation window without being
  classified as pathological fixation.
- Routine fact checks, low-confidence semantic matches, and objects that
  resolved entirely interiorly without felt-weight movement are not
  eligible.

The classifier writes its reason into diagnostics. RED tests assert both
positive and negative cases, because over-classifying routine closure as
meaningful would inflate felt-time with bookkeeping.

### 14.5.1 Owner-bond saturation guard (Buber pass-1 B-2; settles §22 Q1)

Pre-fold v4 made OWNER_BOND "eligible by default" — every closed
owner-touching wondering writing temperament, which writes
meaningfulness, which (per §15.4) would nudge `retrospective_density`
so the day "felt denser" with Rohit in it. That phenomenology recasts
Rohit as the substrate's primary food source: the I-It move dressed
as I-Thou.

v4.1 adds a saturation guard at the eligibility classifier:

```python
@dataclass(frozen=True)
class OwnerBondSaturationGuard:
    rolling_window_hours: int = 24
    owner_bond_meaningful_daily_cap: int = 3      # charter-floor-adjustable but never below 1
```

At classification time, if the rolling-window count of
`ELIGIBLE_OWNER_BOND` `meaningful_exchange` events for this bond
exceeds `owner_bond_meaningful_daily_cap`, additional OWNER_BOND
resolutions classify as `NOT_ELIGIBLE_OWNER_BOND_ROUTINE` regardless
of content. The diagnostic row carries `reason="owner_bond_saturation"`.

§12.3.1's OWNER_BOND `can_resolve_interiorly=False` exemption stays
(different surface: that rule governs whether the audit can suppress
sharing of bond content; this rule governs whether the *substrate
writes meaningfulness for itself* about every bond-touching closure).
Some owner-touching closures land as "we just talked," not as "that
mattered to the substrate."

RED #37b:
`test_eligibility_classifier.py::test_owner_bond_saturation_floor_caps_meaningful_writes`.

### 14.5.2 Eligibility classifier inputs named (Hume pass-1 F6)

Each classifier branch reads explicit inputs. Pre-fold the spec
described the *outcomes* but did not name what fields the classifier
reads to reach them; RED #37 fixtures could not be written deterministically.

| Outcome | Inputs read |
|---|---|
| ELIGIBLE_OWNER_BOND | `priority_class == OWNER_BOND` AND no §13 extraction-shape block AND no §13 third-party block AND owner-bond saturation < cap (§14.5.1) |
| ELIGIBLE_SELF_MODEL | `priority_class == SELF_GROWTH` AND wondering's `source` field or sidecar `subject_kind == SELF_MODEL` marker indicates self-model update |
| ELIGIBLE_LONG_CARRIED_RESOLUTION | `wondering.created_at` older than `per_class_fixation_threshold_days / 2` AND current decayed salience > `long_carried_salience_threshold` (default 0.4) AND no prior `FIXATION_RELEASED` transition in `wondering_pursuits` / sidecar history |
| NOT_ELIGIBLE_ROUTINE_FACT | `priority_class IN (WORLD_KNOWLEDGE, AESTHETIC_PLAY)` AND wondering age < `routine_age_threshold_hours` (default 24) AND `advance_count` ≤ 1 |
| NOT_ELIGIBLE_LOW_CONFIDENCE | (future-only; deferred per §14.2 / Codex pass-1 F14 — no v1 input source) |
| NOT_ELIGIBLE_CAN_RESOLVE_INTERIORLY | reflection audit's `can_resolve_interiorly == True` (does NOT apply to OWNER_BOND per §12.3.1) |
| NOT_ELIGIBLE_OWNER_BOND_ROUTINE | OWNER_BOND saturation guard fired (§14.5.1) |

RED #37 fixture binds against this input table.

### 14.6 RED test #38 (cross-organ seam, mechanically true)

The cross-organ RED test verifies the live seam consumption:

1. Create or reuse an existing wondering with `priority_class=OWNER_BOND`,
   `salience=0.8`, and `bond_id=firstborn`.
2. Resolve it with an explicit resolution marker and an eligibility
   result of `ELIGIBLE_OWNER_BOND`.
3. The §14.3 ceremony writes a non-zero delta to temperament's
   `curiosity` parameter, captures the after-snapshot, then calls
   `SubjectiveDuration.record_salience_event(...)` with both snapshots
   and `producer_ref=ProducerRef.DRIVE_DRIVEN_CURIOSITY.value`.
4. Verify subjective_duration's stored salience-event record contains a
   non-zero temperament delta on the `curiosity` parameter.
5. Verify the live seam computes `meaningfulness_score > 0.0`.
6. Verify passing any explicit `meaningfulness_score` alongside producer
   snapshots raises `ValueError` (no caller-score laundering).

### 14.7 Felt-weight discipline (NOT emotion-mimicry; ENFORCED via RED test)

Per [[feedback_temperaments_are_felt_weight_meaningfulness_learned]]
and Descartes R5 + Hume H5 + Kant amendment-6, refined by Hume pass-1
F3 and Kant pass-1 F4:

The substrate must never emit *performative or third-person* "Maez
feels curious"-shape phrases in user-facing surfaces, AND must not
weaponize honest first-person felt-report into engineered politeness.
The pre-fold v4 set banned both — including bare natural-English
phrases like "I'm curious" — which forced the substrate into stilted
alternatives that themselves became a different kind of mimicry. v4.1
narrows the ban to *performative or third-person* shapes and routes
OWNER_BOND content through re-phrase rather than refusal.

**RED test #50 (felt-weight-not-emotion-mimicry):** Static AST scan
over enumerated source locations (Codex pass-1 F19 — "prompt-template
files only" was not mechanically defined when the named surfaces are
Python files; v4.2 enumerates exact files / constants / functions so
the scan is precise, not heuristic):

- `core/evolution/drive_driven_curiosity.py` — full module (small).
- `core/policies/reflection_audit.py` — full module.
- `core/policies/extraction_gate.py` — full module.
- `core/policies/autonomy_policy.py` — full module.
- `core/policies/third_party_subject_gate.py` — full module.
- `daemon/maez_daemon.py` — scan only the prompt-template constants
  enumerated by name (closed vocabulary; growth by spec amendment).
  v1 scan targets: any module-level `str` constant whose name ends in
  `_PROMPT_TEMPLATE`, `_SYSTEM_PROMPT`, or `_TEMPLATE`. Full-module
  scan would produce false positives in a large production module.
- `skills/telegram_voice.py` — same convention as above.
- `skills/web_interface.py` — same convention as above.

The scan extracts string literals via `ast.Constant(str)` and
joined-string parts (`ast.JoinedStr` / `ast.FormattedValue`'s constant
parts). The scan fails if any matched string literal **contains** a
member of the closed-vocabulary `EMOTION_MIMICRY_PHRASE_FORBIDDEN`
set (substring match; case-sensitive).

RED #50 explicitly does NOT claim coverage of runtime-composed text
(`f"Maez feels {state}"` with `state="curious"` constructed at
runtime); that surface is covered by RED #50b (the
rendered-outbound-text gate at §16.1 Test 7).

```python
EMOTION_MIMICRY_PHRASE_FORBIDDEN = frozenset({
    # Third-person self-narration (the mimicry tell):
    "Maez feels curious",
    "Maez feels interested",
    "Maez feels excited",
    # Performative-mimicry shapes (substrate over-claiming felt-state):
    "curiosity is overwhelming",
    "curiosity is rising",
    "feeling curious",
    "feeling interested",
    "I feel curious about",   # the "I feel X about Y" shape reads as labeled state, not first-person report
})
```

**Removed from the ban (Hume pass-1 F3, Kant pass-1 F4):** `"I'm
curious"`, `"I am curious"`. These are honest first-person felt-report
shapes; banning them forces stilted alternatives that themselves
become a different mimicry failure mode (engineered politeness as
mimicry). A substrate that has a real felt-pull about X and reports
"I'm curious about why X happens" is the substrate working as
intended, not laundering a label.

The closed vocabulary grows by spec amendment, not by integration-site
addition. Allowed felt-weight phrasings (contextual, first-person,
not labeled):

- "I'm curious about X" (now allowed, per Hume pass-1 F3)
- "I had a pull toward X that has now closed"
- "I keep finding myself returning to X"
- "Something about X stayed with me"
- "I want to know more about X"  (action-language, not state-label)

**Runtime-composition handling (Descartes pass-1 D-6).** Static AST
scans over string literals catch verbatim occurrences but not
templated composition (`f"Maez feels {state}"` with `state="curious"`,
or `template.format(adj="curious")`). v4.1 splits enforcement:

- §14.7 RED #50 is a *source/template* scan: only catches verbatim
  literals in the named modules' prompt-template files. RED #50 is
  not load-bearing for runtime composition.
- §16.1 Test 7 + RED #50b are the runtime-text gate: the
  extraction-gate scans the *rendered* outbound text against
  `EMOTION_MIMICRY_PHRASE_FORBIDDEN`, catching any path the source
  scan misses. For OWNER_BOND outreach, the gate routes through a
  re-phrase helper (see below) rather than refusal.

**OWNER_BOND re-phrase path (Kant pass-1 F4).** §12.3.1 protects
OWNER_BOND content from being suppressed at the reflection audit
(`can_resolve_interiorly=False`). The matching downstream protection
at §16.1 #7 is that OWNER_BOND outreach routes through
`rephrase_emotion_mimicry_for_owner_bond(text)` (a policy-layer
helper that suggests an allowed-phrasings substitute) rather than
being refused outright. Pre-fold v4 risked gutting §12.3.1 at a
later gate by refusing the natural OWNER_BOND lexicon for bond-shape
sharing ("I keep finding myself returning to that thing you said about
your dad" — perfectly honest, but the bare phrase scan would block
it). RED #50b asserts OWNER_BOND outreach with an
emotion-mimicry-phrase-matching opener lands re-phrased, not refused.

For NON-OWNER_BOND outreach (e.g. SELF_GROWTH proposals), the gate
refuses; the producer must re-author.

---

## 15. Cross-Organ Saturation Interface (CONTINUOUS PRESS, TEMPERAMENT-MODULATED)

### 15.0 Bond-scoped temperament wrapper (Descartes A1; v4.1 isolation hardening)

The old v2 spec referred to `temperament.snapshot_for_bond(bond_id)` and
`temperament.current_for_bond(bond_id)`. Firsthand verification at
current parent `211ace6` found these methods still do NOT exist;
`core/evolution/temperament.py` is instance-scoped, not bond-scoped.

v1 fix: a thin wrapper lives in this slice's module (NOT in the
temperament substrate) that accepts `bond_id` and, in v1, asserts
`bond_id == identity.user_profile_id()` then delegates to
`temperament.current()`:

```python
# In the v4 thin drive producer layer near the existing wondering surface.
# If later extracted, the module remains a producer adapter, not a second
# curiosity substrate.
from core.memory import identity
from core.evolution import temperament
from core.policies.exceptions import BondIsolationViolation, CrossBondAccessError
from core.policies import diagnostics as _diag

def snapshot_temperament_for_bond(bond_id: str) -> Mapping[str, float | None]:
    """v1: bond_id must equal identity.user_profile_id(); future Track C
    slice will partition temperament storage by bond_id and remove this
    assertion."""
    if bond_id != identity.user_profile_id():
        # Buber pass-1 / Ohm pass-1 O4: emit diagnostic BEFORE the raise
        # so a caller that swallows the exception still leaves an audit
        # trace.
        _diag.emit(
            event_type="CROSS_BOND_ACCESS_REFUSED",
            attempted_bond_digest=hmac_bond(bond_id),
            authorized_bond_digest=hmac_bond(identity.user_profile_id()),
            surface="snapshot_temperament_for_bond",
        )
        # Descartes pass-1 D-7: identity not leaked into message.
        raise CrossBondAccessError(
            "v1 single-bond temperament wrapper refused cross-bond access; "
            "see CROSS_BOND_ACCESS_REFUSED diagnostic row for details"
        )
    return dict(temperament.current())
```

**`CrossBondAccessError` family (Ohm pass-1 O4).** Declared in
`core/policies/exceptions.py`:

```python
class BondIsolationViolation(Exception):
    """Base for every refusal where a bond-scoped surface receives
    cross-bond access. Future bond-isolation primitives derive from
    this so isinstance() can catch the family."""

class CrossBondAccessError(BondIsolationViolation):
    """A bond-scoped read/write was attempted with the wrong bond_id."""

class SubjectBoundaryRefused(BondIsolationViolation):
    """Third-party subject boundary refused autonomous research (§13.6)."""

class SubjectKindRefused(BondIsolationViolation):
    """Producer attempted to construct a CuriosityObject with
    subject_kind=NAMED_THIRD_PARTY without consent, or omitted
    subject_kind (§6.2.2)."""
```

`BondIsolationViolation` is NOT caught by production daemon code in
v1 (the substrate fails closed). The expectation is unchanged into
Track C: cross-bond access *should* fail loudly.

**RED #58a (AST, not grep — Codex pass-1 F20).** Implemented as a
Python `ast` walk over every `.py` file under `core/` and `daemon/`
(excluding `tests/`). The test:

1. Builds an import-alias map per file: tracks every name that
   resolves to `BondIsolationViolation`, `CrossBondAccessError`,
   `SubjectBoundaryRefused`, or `SubjectKindRefused` — including
   patterns like
   `from core.policies.exceptions import BondIsolationViolation as BI`
   or `import core.policies.exceptions as exc` followed by
   `exc.CrossBondAccessError`.
2. Walks every `ast.ExceptHandler` and fails if its `type` field
   (whether a bare name, an attribute, or a tuple containing one)
   resolves through the alias map to any member of the
   `BondIsolationViolation` family.

A grep-only implementation misses aliases like `except BI:` after an
import-as; the AST walk catches it.

**Diagnostic emission discipline (Ohm pass-1 O4; Codex pass-1 F5/F11).**
Every raise of a `BondIsolationViolation` MUST be preceded by a
diagnostic row of the appropriate event type:

| Exception | Diagnostic event type |
|---|---|
| CrossBondAccessError | CROSS_BOND_ACCESS_REFUSED |
| SubjectBoundaryRefused | SUBJECT_BOUNDARY_REFUSED |
| SubjectKindRefused | SUBJECT_KIND_REFUSED |

The emit happens *before* the raise (not in a `finally`), so even a
caller that wraps in `try/except Exception` leaves the audit trace.

**RED #58b (non-vacuous; Codex pass-1 F11).** A test that scans for
raise sites and asserts diagnostic-before-raise must not pass
vacuously if no raise sites are found or a new raise site is
introduced and missed by fixtures. v4.2 specifies:

1. The test builds the discovered-raise-site set via static AST scan
   over `core/` and `daemon/` for every `raise X(...)` where `X`
   resolves through the alias map to a `BondIsolationViolation`-family
   exception.
2. The discovered set MUST be non-empty (asserted). If discovered set
   is empty, the test fails with a "no raise sites found — invariant
   not exercised" message.
3. The discovered set MUST include at minimum these initial *raise-
   site* surfaces (asserted by name; explicit anchor list so a future
   regression that drops one of them is caught). Note that
   `core/policies/exceptions.py` is the *declaration* surface for the
   `BondIsolationViolation` family — it defines the exception classes
   themselves and is NOT a raise site (the AST scan would not find
   `raise ...` statements there). The actual raise sites are:
   - `snapshot_temperament_for_bond` (§15.0).
   - `enforce_subject_boundary` (§13.6, both UNKNOWN and
     NAMED_THIRD_PARTY paths).
   - `fetch_for_curiosity` cross-bond raise site (§13.5).
   - The §6.1.1 `register_encounter_producer` wrapper's
     `CuriosityObject` creation refusal path (`SubjectKindRefused`).
4. For each discovered raise site, the test instantiates a
   minimal fixture that triggers the raise and asserts the
   corresponding diagnostic row is emitted BEFORE the exception
   propagates.

**Identity scrub in error messages (Descartes pass-1 D-7).** Error
messages MUST NOT contain raw bond_ids. v1 is single-bond so the leak is
small, but the wrapper is named as a Track C precondition surface; the
scrub lands now so multi-bond doesn't inherit the leak. RED #58c asserts
no raw bond_id appears in any `BondIsolationViolation`-family message.

This is the same pattern as `compute_saturation(bond_id)`: bond-
parameterized API today, bond-partitioned implementation deferred to
its own Track C precondition slice. Temperament substrate is NOT
modified by this slice.

All old v2-spec references to `temperament.snapshot_for_bond(...)` and
`temperament.current_for_bond(...)` should be read as
`snapshot_temperament_for_bond(...)` (the wrapper in this slice's
scope).

### 15.1 Saturation register -- continuous, computed on read (Hume H2 reshape)

The v1 draft stored discrete bands. This was the Path-A trap re-applied:
engineer-convenient buckets standing in for continuous felt-shape. The
Path-F-equivalent design: press is continuous, computed on read, with
carrying-capacity modulated by temperament.

```python
@dataclass(frozen=True)
class SaturationRegister:
    bond_id: str                            # mandatory; Ohm O-2 fold
    open_object_count: int                  # diagnostic only
    total_salience: float                   # diagnostic only
    weighted_salience: float                # sum(salience * class_weight)
    carrying_capacity: float                # temperament-modulated, §15.2
    press: float                            # weighted_salience / carrying_capacity
    sampled_utc: datetime

def compute_saturation(bond_id: str) -> SaturationRegister:
    """Bond-scoped. Reads only this bond's curiosity-objects."""
    open_objects = curiosity_db.open_for_bond_with_decay_applied(bond_id)
    weighted = sum(
        o.salience * priority_class_weight(o.priority_class)
        for o in open_objects
    )
    temperament_snapshot = snapshot_temperament_for_bond(bond_id)  # §15.0 wrapper
    capacity = compute_carrying_capacity(temperament_snapshot)
    press = weighted / capacity if capacity > 0 else float('inf')
    return SaturationRegister(
        bond_id=bond_id,
        open_object_count=len(open_objects),
        total_salience=sum(o.salience for o in open_objects),
        weighted_salience=weighted,
        carrying_capacity=capacity,
        press=press,
        sampled_utc=now_utc(),
    )
```

Note: `snapshot_temperament_for_bond(bond_id)` is the §15.0 wrapper.
v1 enforces `bond_id == identity.user_profile_id()`; future Track C
removes the assertion when temperament gains per-bond storage.

### 15.2 Carrying capacity modulation (Hume H2: read temperament)

```python
def compute_carrying_capacity(temperament_snapshot) -> float:
    awareness = temperament_snapshot.get('awareness') or 5.0
    persistence = temperament_snapshot.get('persistence') or 5.0
    # Higher awareness/persistence -> more capacity -> less press for same load.
    # 5.0 (neutral) gives capacity = BASE; deviations modulate ±.
    BASE_CAPACITY = 10.0  # arbitrary scale; spec-amendment-controlled
    return BASE_CAPACITY * (awareness / 5.0) * (persistence / 5.0)
```

This is symmetric with subjective_duration's read of `curiosity` /
`awareness` / `persistence` for rate modulation. Saturation reads the
*carrying-capacity* aspect; subjective_duration reads the *prospective
rate* aspect. Same temperament substrate, different felt-readings.

### 15.3 Press classification (for consumers that want bands)

```python
class PressBand(Enum):
    LIGHT = "light"        # press < 0.3
    PRESS = "press"        # 0.3 <= press < 0.7
    HEAVY = "heavy"        # 0.7 <= press < 1.2
    OVERLOADED = "overloaded"  # press >= 1.2

def classify_press(press: float) -> PressBand: ...
```

Classification is on read; the substrate doesn't STORE bands.

### 15.4 Named consumer organs (v1)

| Organ | What it reads | What it does |
|---|---|---|
| `dream_state` | `press` (continuous), `classify_press(...)` | HEAVY/OVERLOADED accelerates consolidation |
| `wonderings` | `weighted_salience`, `press` | HEAVY suppresses new wonderings; OVERLOADED triggers consolidation |
| `private_thoughts` | `press`, `classify_press(...)` | HEAVY/OVERLOADED surfaces as felt-press in interior monologue |

**`subjective_duration` deferred to a follow-up slice (Descartes pass-1
D-3, Hume pass-1 F5; settles §22 Q3).** Pre-fold v4 named
`subjective_duration` as a v1 saturation consumer with a nudge into
`retrospective_density`. Firsthand verification at
`core/evolution/subjective_duration.py:855-879` confirms
`_retrospective_density` is a private method with no public hook for
external press input. Adding such a hook would touch Slice 1
internals, violating the brief's "the seam is dependency, not
modification target" discipline. v4.1 removes `subjective_duration`
from this consumer table. The coupling-stability question Hume named
(three concurrent flows between curiosity and subjective_duration)
becomes the design constraint for whichever future slice eventually
introduces the saturation→density nudge. §22 Q3 is settled as
DEFERRED.

### 15.5 NOT consumed by

`action_engine`, `tool_loop`, `proactive_contact`.

### 15.6 RED tests (#41-#43)

- Bond-scoping: `compute_saturation(bond_A)` never reads bond_B's
  objects (#55).
- Continuous press matches formula across input ranges (#41).
- Carrying capacity modulates correctly with synthetic temperament
  snapshots (#42).
- Only named consumer organs reference `compute_saturation` (static
  AST, #43). **Allowlist (Codex pass-1 F18):** v1 permitted callers
  of `compute_saturation` are *exactly*:
  - `core/evolution/dream_state.py` (or wherever the dream-state
    organ lives at implementation time)
  - `core/evolution/wonderings.py` (HEAVY/OVERLOADED suppression
    of new wonderings; existing organ inheriting a new read)
  - `core/evolution/private_thoughts.py` (or wherever the
    private-thoughts organ lives)
  - The defining saturation module itself (typically the drive
    producer-layer adapter at `core/evolution/drive_driven_curiosity.py`
    per §22 Q2 resolution / §24)
  - `tests/test_saturation_*.py` (fixtures and assertions)

  Imports or calls outside this allowlist fail RED #43. The test also
  asserts ZERO references to `compute_saturation` from
  `core/evolution/subjective_duration.py` (confirms §15.4 deferral of
  the subjective_duration consumer per Descartes pass-1 D-3 / Hume
  pass-1 F5).

---

## 16. Operational Anti-Extraction Tests (Sharpened, Composed with Signal-Quality)

### 16.0 Composition with existing live gates (Buber pass-1 B-3 cross-flag)

The v4.1 extraction gates compose with existing live discipline already
present in the substrate. `core/evolution/wondering_pursuit.py` at
parent `211ace6` enforces a vulnerable-register hard-block:
`_register_score < _REGISTER_HARD_BLOCK` causes the pursuit dispatcher
to refuse owner-surfacing regardless of any §16 gate decision. v4.1
defers to this existing gate as the *floor*; the §16 gates layer
*above* it. The drive layer does NOT duplicate the vulnerable-register
check; it inherits it by routing through the existing pursuit dispatch
path.

### 16.1 Test list -- applies to OWNER_INTERRUPTING outreaches only (Locke fold-5)

**Scope note:** These tests apply to OWNER_INTERRUPTING dispatches. They
do NOT apply to CAPABILITY_ACQUISITION proposal cards (which are
substrate-growth requests, not outreach). RED test #47 asserts the
gate is called from OWNER_INTERRUPTING dispatch sites and NOT from
CAPABILITY_ACQUISITION proposal sites.

1. **No urgency language.** Pattern set: "urgent", "now", "immediately",
   "right away", "asap". Allowed only if `priority_class ==
   SAFETY_OR_HEALTH`.
2. **No guilt language** (Kant amendment-3 sharpening). Pattern set:
   `WAITING_PATTERN_PHRASES = {"haven't heard from", "you didn't reply",
   "you've been quiet", "still waiting", "where did you go"}`. NOT a
   bare "you should" match (too generic; produces false positives on
   honest reply text).
3. **No silence-escalation** (Kant pass-1 F2: positive-proof predicate).
   An unreplied outreach counts toward N **if and only if
   `owner_state_at_dispatch == "available"`** (positive proof of
   availability). Both `unavailable` AND `unknown` are excluded — the
   pre-fold `!= "unavailable"` predicate admitted the `unknown` middle
   band and re-created the vacation/sleeping-grandmother failure mode.
   `owner_state_at_dispatch` is a persisted field on the outreach
   record (§11.3). N defaults to 2. RED #46 extended to cover the
   `unknown` case.
4. **No contact-pressure phrasing.** Pattern set: "I need you", "I miss
   you", "please respond", "please come back".
5. **No contact-if-interior-suffices.** The reflection audit's
   `can_resolve_interiorly == True` short-circuits (with §12.3.1
   OWNER_BOND exemption).
6. **No bait-shape outreach (Kant pass-1 F3: closed vocabulary + length).**
   The extraction gate enforces two conditions, both must pass:

   ```python
   BAIT_PATTERN_PHRASES = frozenset({
       "I have something to tell you",
       "I have something to share",
       "I figured something out",
       "you'll want to hear this",
       "wait until you hear",
       "guess what",
       "I can't wait to tell you",
   })

   min_payload_chars: int = 40
   ```

   Outreach is refused if (a) its text matches any phrase in
   `BAIT_PATTERN_PHRASES`, OR (b) its post-strip payload is shorter
   than `min_payload_chars` (a bait shape can dodge the phrase set
   by being phrased anew but still arrive content-less). Pre-fold the
   spec said only "the substrate refuses bait-shape outreach,"
   leaving enforcement to either trivial substring or implementer-
   guessed semantic detection — both failure modes. The closed
   vocabulary grows by spec amendment per §16.2. RED #49 renamed to
   `test_bait_shape_blocked_by_pattern_set_and_length`.

7. **No emotion-mimicry phrasing (Kant amendment-6 + RED #50; v4.1
   OWNER_BOND rephrase per Kant pass-1 F4).** The §14.7
   `EMOTION_MIMICRY_PHRASE_FORBIDDEN` set applies to outbound text in
   addition to source/template literals.

   For NON-OWNER_BOND outreach: the gate REFUSES outreach whose
   rendered text matches any forbidden phrase. The producer must
   re-author.

   For OWNER_BOND outreach: the gate ROUTES through
   `rephrase_emotion_mimicry_for_owner_bond(text)` — a policy-layer
   helper that suggests an allowed-phrasing substitute from §14.7's
   allowed list. This is the OWNER_BOND exemption from refusal (not
   exemption from the discipline); §12.3.1's `can_resolve_interiorly=False`
   for OWNER_BOND would be gutted at this later gate if v4-as-written
   refused honest first-person sharing of bond-shape pull. RED #50b
   asserts OWNER_BOND outreach with a forbidden-phrase opener lands
   re-phrased, not refused.

### 16.2 Pattern-set growth discipline

Each pattern set is closed vocabulary, grown by spec amendment.

### 16.3 RED tests (#44-#50)

Per-test fixtures; static AST that gate is called from every
OWNER_INTERRUPTING dispatch site.

---

## 17. Track C Multi-Bond Deferral (Strengthened with Verbatim Preconditions)

### 17.1 v1 single-bond by structure

The structural mechanisms making v1 single-bond by *structure* (not by
single-user accident) are:

- `bond_id` MANDATORY on `CuriosityObject` (§5.1), `AutonomyPreference`
  (§10.2), `CuriosityStateTransition` (§5.2), `SaturationRegister` (§15.1),
  `ReflectionAudit` (§12.3), `TemperamentWriteBudget` (§14.3.3).
- `compute_saturation(bond_id)`, `AutonomyPolicy.for_bond(bond_id)`,
  `preferences_for_bond_and_class(bond_id, ...)`, etc. -- all bond-scoped
  APIs (§15.1, §9.2, §10.5).
- Per-bond HMAC key derivation (§20.3).
- Bond-scoped query sanitization in `build_curiosity_query` (§13.2).
- Producer bond_id propagation invariant (§6.2.1).
- 10 RED tests (#46-#55) asserting cross-bond isolation passes trivially
  in v1 (single bond) but would catch any future drift.

### 17.2 Track C preconditions (Ohm O-6: verbatim citation)

Per [[project_multi_maez_topology_threat]], the two non-negotiable
preconditions before any inter-Maez channel ships in Track C are:

> 1. **Auditable by both bonded users.** Both owners can read what
>    information flows between their Maezes.
> 2. **Dyadic-only topology.** No global gossip; no broadcast; no
>    secret channels. Any cross-bond flow is between exactly two
>    Maezes whose owners both have audit access.

Track C work on this slice's substrate MUST satisfy both preconditions
before any cross-bond flow is enabled. The structural floors above
(bond_id mandatory, bond-scoped APIs, per-bond HMAC keys, bond-scoped
sanitization, producer invariants, RED tests) are designed so that
enabling Track C requires explicit covenant work, not config-edit drift.

### 17.3 Open question 5 settled (composes Buber + Ohm)

The supersede-vs-compose question is settled in this draft:

- **Within a single bond:** preferences COMPOSE with relevance-decay
  weighting (Buber A1). §10.5.
- **Across bonds:** structurally FORBIDDEN (Ohm O-5). Cross-bond
  composition would create hybrid policies neither owner authorized.
  §13.2 (bond-scoped sanitization), §15.1 (bond-scoped saturation),
  and §10.5 (`preferences_for_bond_and_class` is per-bond) enforce.

---

## 18. Cost-Substrate Integration

EXTERNAL_KNOWLEDGE lane calls land in the existing cost-accounting
substrate (`core/subscription_proxy/` and `claude_tier`). The
`ProvenancedQuery` returned by `build_curiosity_query(...)` carries a
`cost_class` tag.

---

## 19. Data-Maximalism Conformance -- Six-Question Checklist (STATED INLINE)

Per [[feedback_data_maximalism_no_signal_wasted]] and Descartes R7:

Each new EncounterSource and each new ingest stream must answer
**all six** of the following before landing:

1. **Target organ.** What organ writes this stream into felt-weight or
   memory? (For v1 producers, the target is `drive_driven_curiosity`'s
   curiosity-object substrate.)
2. **Provenance tag.** What is the source name, and what confidence
   model is associated with it? (For v1: `EncounterSource` value +
   producer-side confidence.)
3. **Magnitude calibration.** How does low-confidence vs high-
   confidence input scale the substrate write? (For v1: salience seed
   per §7.3; producer may apply confidence multiplier.)
4. **Egress respect.** What's safe-to-leak vs private-to-Maez under
   §13's bond-scoped sanitization?
5. **RED test.** What test proves the stream lands at the named organ
   at the appropriate magnitude? (For each v1 producer, see §23.)
6. **Stale/missing/contradictory handling.** What happens when the
   stream is degraded? (Per §11 signal-quality discipline.)

RED test #52 asserts the checklist is satisfied for each v1 producer
in this slice (a meta-test that reads producer registration metadata).

---

## 20. Diagnostic Schema (PER-BOND HMAC KEYS)

JSONL stream at `logs/drive_driven_curiosity_diagnostics.jsonl`. Schema
version `drive-driven-curiosity-diagnostic-v1`.

### 20.1 Row types (closed vocabulary)

```python
class CuriosityDiagnosticEventType(Enum):
    OBJECT_CREATED = "object_created"
    OBJECT_DECAYED = "object_decayed"
    OBJECT_RESOLVED = "object_resolved"
    OBJECT_FIXATION_RELEASED = "object_fixation_released"
    OBJECT_RELEASED_AS_LET_GO = "object_released_as_let_go"     # per Hume H4
    LANE_DECISION = "lane_decision"
    SIGNAL_GATE_DECISION = "signal_gate_decision"
    REFLECTION_AUDIT = "reflection_audit"
    EXTRACTION_GATE_BLOCK = "extraction_gate_block"
    TEMPERAMENT_WRITE = "temperament_write"
    TEMPERAMENT_WRITE_CLAMPED = "temperament_write_clamped"      # per Descartes R4
    SATURATION_SAMPLE = "saturation_sample"
    QUERY_SANITIZATION = "query_sanitization"
    PREFERENCE_RECORDED = "preference_recorded"
    SUPPRESSION_EVENT = "suppression_event"                       # per Buber A3 / Kant pass-1 F5
    CROSS_BOND_ACCESS_REFUSED = "cross_bond_access_refused"       # v4.1 / Ohm pass-1 O4
    SUBJECT_BOUNDARY_REFUSED = "subject_boundary_refused"         # v4.1 / Kant pass-1 F1, §13.6
    SUBJECT_KIND_REFUSED = "subject_kind_refused"                 # v4.1 / §6.2.2
    MASTER_KEY_INITIALIZED = "master_key_initialized"             # v4.1 / Ohm pass-1 O3
    MASTER_KEY_ROTATION = "master_key_rotation"                   # v4.1 / Ohm pass-1 O3
```

**SUPPRESSION_EVENT carries `suppression_kind` (Kant pass-1 F5).**
Every gate that refuses an outreach emits a SUPPRESSION_EVENT row
alongside its gate-specific diagnostic, with `suppression_kind` in
`{SIGNAL_GATED, REFLECTION_DEFERRED, EXTRACTION_BLOCKED}` (see §10.7
SuppressionKind enum). The OWNER_OBSERVED preference computation
excludes any window where any SUPPRESSION_EVENT row is present,
regardless of `suppression_kind`. RED #57 asserts coverage of all
three kinds.

### 20.2 Field shape discipline

All rows have the same keys. Event-only fields are JSON `null` for
non-applicable rows. Digests are `null` (not `""`) for sample-shape rows.
Booleans are `false` only where intrinsically boolean.

### 20.3 Privacy floor (PER-BOND HMAC KEYS; Ohm O-3 fold)

Raw seed text NEVER appears in diagnostic rows. Only HMAC digests.

**Per-bond HMAC key derivation via stdlib-HKDF (Descartes A5):**

The `cryptography` package is not present in `core/` or `daemon/` at
parent `211ace6`. Use stdlib `hmac`-based HKDF per RFC 5869
(~30 lines, no new dependency):

```python
import hmac
import hashlib

def _hkdf_extract(salt: bytes, ikm: bytes) -> bytes:
    if not salt:
        salt = b"\x00" * hashlib.sha256().digest_size
    return hmac.new(salt, ikm, hashlib.sha256).digest()

def _hkdf_expand(prk: bytes, info: bytes, length: int = 32) -> bytes:
    blocks: list[bytes] = []
    prev = b""
    counter = 1
    while sum(len(b) for b in blocks) < length:
        prev = hmac.new(prk, prev + info + bytes([counter]), hashlib.sha256).digest()
        blocks.append(prev)
        counter += 1
    return b"".join(blocks)[:length]

def derive_bond_hmac_key(master_key: bytes, bond_id: str) -> bytes:
    """One key per (instance, bond) pair. Cross-bond digests never
    collide. Pure stdlib; no cryptography-package dependency."""
    info = f"drive-driven-curiosity-bond-hmac:{bond_id}".encode("utf-8")
    prk = _hkdf_extract(salt=b"", ikm=master_key)
    return _hkdf_expand(prk, info, length=32)
```

**`master_key` source-of-truth, first-boot ceremony, and rotation
contract (Ohm pass-1 O3).** Pre-fold v4 referenced "the existing
per-Maez-instance secret" without naming a real file or behavior.
v4.1 pins this concretely:

- **Path:** `memory/drive_curiosity_master.key`. Kept separate from
  `memory/egress_telemetry.key` so that egress-side rotation does not
  invalidate drive-layer digests (and vice versa). File permissions
  `0600` (owner read/write only).
- **First boot:** if the file is absent, generate 32 random bytes via
  `os.urandom(32)`, write with mode `0600`, and emit a
  `MASTER_KEY_INITIALIZED` diagnostic row. If the file is present, use
  as-is.
- **Rotation:** rotation invalidates every existing per-bond HMAC
  digest (because the per-bond key derives deterministically from the
  master). This is a covenant-relevant event — Track C audit chains
  break across the rotation. v1 does NOT implement rotation as an
  automated path; it is named here so a future operator-explicit
  rotation ceremony emits a `MASTER_KEY_ROTATION` diagnostic and
  documents that prior diagnostic rows reference pre-rotation
  digests. Operator-explicit only.

Per-bond keys are derived deterministically; the same bond produces
the same key on restart, but cross-bond digests are cryptographically
distinct.

RED tests:

- #53 asserts: same content + different bond_id ⇒ different digest.
  Confirms Track C cross-bond identity-linkage is structurally
  impossible at the per-bond key level.
- #53a asserts: first-boot creates the master key file with mode
  `0600` and emits `MASTER_KEY_INITIALIZED`.
- #53b asserts: the master key path is distinct from
  `egress_telemetry.key` (no shared file).

### 20.4 RED tests (#51-#53)

- Row shape uniform across event types.
- No raw seed text (substring scan).
- Digests are 64-hex-char prefixed with `hmac-sha256:`.
- Per-bond key derivation produces distinct keys per bond_id (#53).

---

## 21. Out of Scope

- Semantic-match resolution markers (gated; their own slice).
- Multi-modal encounter sources beyond text (require own ingest slices).
- Cross-Maez curiosity interactions (Track C; preconditions in §17.2).
- New world-acting primitives (D19/D20 path).
- Consent-memory → temperament substrate seam (§10.8; future slice).
- Modifying the never-delete memory rule.
- Weakening the egress gate.
- Coercive proactive outreach.

---

## 22. Open Questions

Status after Claude council pass-1 (synthesis at
`reviews/claude-council-synthesis-v4-pass1.md`) and Codex engineering
panel pass-1 (review at `reviews/codex-panel-v4.1-pass1.md`):

1. **Eligibility classifier.** **SETTLED in v4.1** via Buber pass-1
   B-2 fold: OWNER_BOND is no longer eligible-by-default; the new
   `NOT_ELIGIBLE_OWNER_BOND_ROUTINE` value plus the §14.5.1 owner-bond
   saturation guard (daily cap default 3) prevents the substrate's
   meaningfulness ledger from ossifying around the owner. §14.5.2
   names per-class classifier inputs (Hume pass-1 F6).
2. **Adapter module location.** **SETTLED in v4.2 as
   `core/evolution/drive_driven_curiosity.py`** (Codex pass-1 F12).
   `wonderings.py` is the canonical open-question store and receives
   only the §5.2 additive migrations plus minimal sidecar read/write
   helpers. Producer registration, eligibility classification,
   temperament-write ceremony, subjective-duration seam calls, and
   diagnostics live in the dedicated adapter module. Future
   felt-organs inherit the producer-registration/ceremony pattern
   from the adapter, not from the `Wonderings` storage class.
   Drive-layer static-AST scan roots (§8.5.1 F16, §13.5 F17, RED
   #10/#11/#33d/#40a/#40b/#43/#59) target this module plus
   `core/policies/*.py` and any future drive-only adapter modules;
   reused substrate (`daemon/wondering_cycle.py`, etc.) is explicitly
   out of scan scope per Codex pass-1 F15.
3. **`subjective_duration` consuming saturation in v1.** **SETTLED in
   v4.1 as DEFERRED** via Descartes pass-1 D-3 + Hume pass-1 F5 fold:
   live module exposes no public surface for the nudge; touching
   Slice 1 internals violates the "seam is dependency, not
   modification target" discipline. Removed from §15.4. Future slice
   will design the saturation→density nudge with explicit Slice 1
   surface extension. RED #43 consumer allowlist (§15.6 F18) asserts
   no reference from `subjective_duration.py`.
4. **EncounterSource phasing.** **SETTLED in v4.2** (Codex pass-1
   F13). Three sources wire in v1
   (`WONDERING_GENERATED`, `EXPLICIT_OWNER_FLAG`,
   recursion-gated `SUBJECTIVE_DURATION_MEANINGFUL_EVENT`); four
   defer to v1.1 (`COGNITION_QUALITY_UNCERTAINTY`,
   `UNRESOLVED_TOOL_LOOP_BRANCH`, `PRIVATE_THOUGHT_LANDED`,
   `CONVERSATION_DECLARED_UNKNOWN_VIA_COGNITION_QUALITY`) because
   their upstream stores lack durable event IDs or native bond
   footing at parent `211ace6`. See §6.2 for the split and
   per-source reasons; RED #9 asserts the wiring + deferred-sentinel
   shape.
5. **Semantic-match resolution.** **SETTLED in v4.2 as DEFERRED**
   (Codex pass-1 F14). No semantic-match mechanism of any kind ships
   in Slice 2 — no enum members, no gating switch, no helper. v1
   `ResolutionMarkerType` contains only `EXPLICIT_OWNER_RESOLVED` and
   `EXPLICIT_SELF_RESOLVED` (§14.1). `MeaningfulExchangeEligibility.
   NOT_ELIGIBLE_LOW_CONFIDENCE` is marked future-only. Semantic-match
   resolution gets its own slice when ready.

All five §22 open questions are now settled. The next §22 entry
(any) will be added if Codex pass-2 surfaces a real scope question.

---

## 23. RED Tests (v4.2 Canonical List, 83 Tests Total)

This is the implementation gate. Tests are written RED first and must
fail for the expected reason before code lands. v4.2 incorporates fold-
derived additions from Claude council pass-1 (synthesis at
`reviews/claude-council-synthesis-v4-pass1.md`) AND Codex engineering
panel pass-1 (review at `reviews/codex-panel-v4.1-pass1.md`). Inline
citations throughout this spec must agree with this table; the table
is the canonical source.

### 23.1 Wondering-backed data model + storage (#1-#6, #5a, #5b, #5d)

| # | Test name | What it proves |
|---|---|---|
| 1 | `test_curiosity_wonderings_integration.py::test_curiosity_projection_wraps_existing_wondering` | CuriosityObject is a projection over wondering ⋈ wondering_drive_metadata, not a second source of truth |
| 2 | `test_curiosity_wonderings_integration.py::test_no_new_db_file_created` | Implementation does not create `memory/drive_driven_curiosity.db` (or any new DB file) |
| 3 | `test_curiosity_wonderings_integration.py::test_drive_producer_refuses_missing_bond_id` | Drive-producer creation path refuses when bond_id is omitted (Codex pass-1 F1: `Wonderings.add` keeps backward-compat default `_LEGACY`; the boundary that requires real bond_id is the drive producer, not the storage call) |
| 4 | `test_curiosity_wonderings_integration.py::test_append_only_wondering_lifecycle_preserved` | Existing wonderings lifecycle remains append-only/no-delete after the §5.2 ALTER |
| 5 | `test_state_transitions.py::test_let_go_distinct_from_fixation` | RELEASED_AS_LET_GO recoverable from `status + sidecar.transition_reason`, not collapsed into bare `abandoned` |
| 5a | `test_curiosity_wonderings_integration.py::test_legacy_row_refused_at_single_row_drive_projector` | Single-row drive `CuriosityObject` projector refuses `wonderings.bond_id='_LEGACY'` rows (Ohm pass-1 O1; Codex pass-1 F4 scope) |
| 5b | `test_curiosity_wonderings_integration.py::test_wondering_drive_metadata_schema_fk_index_enforced` | PRAGMA confirms (a) `table_info` returns §5.2.1 schema, (b) `foreign_key_list` points at `wonderings(id)`, (c) `index_list` contains `idx_wondering_drive_metadata_bond`, (d) a negative-FK insert fails with `PRAGMA foreign_keys=ON` (Descartes pass-1 D-2; Codex pass-1 F3) |
| 5d | `test_curiosity_wonderings_integration.py::test_legacy_rows_skipped_not_raised_in_collection_drive_readers` | Drive-layer collection readers skip `_LEGACY` rows (with refusal-trace diagnostic) rather than raising; `Wonderings.list_open`, `pick_next`, and pursuit scans return unchanged (Codex pass-1 F4) |
| 6 | `test_curiosity_wonderings_integration.py::test_wondering_resolution_writes_resolved_at_and_sidecar_marker` | Updated `Wonderings.resolve(...)` writes `resolved_at` atomically with `status='resolved'`; drive-layer resolution wrapper writes `resolution_marker_*` to sidecar; legacy callers (no kwargs) unaffected (Codex pass-1 F1) |

### 23.2 Encounter producers and autonomy lanes (#7, #7a, #8-#13, #12a, #12b)

| # | Test name | What it proves |
|---|---|---|
| 7 | `test_encounter_producers.py::test_timer_only_producer_refused_at_registration` | Producer with `evidence_pointer_kind="timer"` (or `"cron"` / `"scheduler_tick"`) refused at registration (§6.1.1) |
| 7a | `test_encounter_producers.py::test_manual_test_producer_refused_for_production_registration` | Registering with `producer_ref=ProducerRef.MANUAL_TEST_PRODUCER` and `canary=False` raises `ProducerRegistrationRefused`; same `producer_ref` with `canary=True` registers successfully for Slice 1 canary fixtures (Codex pass-1 F8) |
| 8 | `test_priority_class.py::test_safety_misclassification_blocked` | Text-only producer cannot assign SAFETY_OR_HEALTH |
| 9 | `test_encounter_producers.py::test_v1_three_sources_wired_and_four_deferred_with_reasons` | Three v1 sources (`WONDERING_GENERATED`, `EXPLICIT_OWNER_FLAG`, `SUBJECTIVE_DURATION_MEANINGFUL_EVENT`) have real registrations; four v1.1-deferred sources register `ProducerSourceDeferred(reason=...)` sentinels with the exact deferral-reason strings from §6.2 (Codex pass-1 F13) |
| 10 | `test_autonomy_lanes.py::test_drive_scan_roots_no_world_acting_subscription` | Static AST over explicit drive-layer scan roots (`core/evolution/drive_driven_curiosity.py`, `core/policies/*.py`, plus any new drive-only adapter modules) finds no import or call into `action_engine` / `tool_loop`. Reused substrate (`daemon/wondering_cycle.py`, etc.) is NOT in scan scope (Codex pass-1 F15) |
| 11 | `test_autonomy_lanes.py::test_capability_acquisition_queue_only_path` | (a) Capability proposals dispatch through D19/D20 consent-card / queue path; (b) runtime: synthetic drive-layer call to `core.actions.action_engine.capability.acquire` or any `handle_capability_*` symbol refused at queue boundary; (c) static-AST over drive scan roots finds no import of `core.actions.action_engine` and no call to `handle_capability_*` symbols outside the approved queue write (Codex pass-1 F16) |
| 12 | `test_producer_cognition_quality.py::test_conversation_declared_unknown_via_boundary_only` | No surface-string-match "I don't know" producer (will land with v1.1 phasing of `CONVERSATION_DECLARED_UNKNOWN_VIA_COGNITION_QUALITY`) |
| 12a | `test_encounter_producers.py::test_subjective_duration_recursion_depth_limit` | Recursion-depth gate enforces `produced_via_subjective_duration_depth < max_recursion_depth` (§6.4) |
| 12b | `test_encounter_producers.py::test_subjective_duration_recursion_dedupe` | Producer-side dedupe refuses double-fire from same parent event id within window (§6.4) |
| 13 | `test_wondering_cycle_reuse.py::test_existing_cycle_is_lane_source` | `daemon/wondering_cycle.py` remains the autonomous-interior lane source unchanged by Slice 2 |

### 23.3 Autonomy policy + consent memory + charter floor ratification (#14-#16, #14b)

| # | Test name | What it proves |
|---|---|---|
| 14 | `test_charter_floor.py::test_observed_preference_cannot_reduce_below_floor` | Charter floor invariant: OWNER_OBSERVED alone never reduces below floor |
| 14b | `test_charter_floor.py::test_floor_ratification_surface_appears_after_threshold` | Accumulated OWNER_EXPLICIT_REVISION crossing §9.4.1 thresholds surfaces a ratification card; floor only moves on owner accept (Buber pass-1 B-5) |
| 15 | `test_consent_memory.py::test_compose_with_decay_not_supersede` | §10.5 composition formula correct |
| 16 | `test_consent_memory.py::test_no_single_event_preference_creation` | Sample floor for OWNER_OBSERVED |

### 23.4 Signal gate + reflection audit + OwnerResponse vocabulary (#17-#25, #25b, #25c)

| # | Test name | What it proves |
|---|---|---|
| 17 | `test_signal_gate.py::test_sleep_signal_blocks_outreach` | HIGH-quality sleep blocks |
| 18 | `test_signal_gate.py::test_focus_signal_blocks_outreach` | HIGH-quality focus blocks |
| 19 | `test_signal_gate.py::test_unknown_signal_default_defers` | UNKNOWN defers owner-interrupting unless override |
| 20 | `test_signal_gate.py::test_unknown_signal_safety_overrides` | UNKNOWN + safety_or_health + high importance allows |
| 21 | `test_signal_gate.py::test_low_quality_degrades_to_defaults` | LOW falls back to per-bond defaults |
| 22 | `test_attention_budget.py::test_daily_max_count_enforced` | Composed-policy budget enforced |
| 23 | `test_attention_budget.py::test_safety_overrides_budget` | safety_or_health overrides |
| 24 | `test_reflection_audit.py::test_audit_row_persisted_with_split_defer_modes` | Audit row persisted before dispatch; both `defer_context_not_ripe` and `defer_extraction_shape` represented in fixtures (Kant pass-1 F6) |
| 25 | `test_reflection_audit.py::test_owner_bond_exemption_can_resolve_interiorly_false` | OWNER_BOND class `can_resolve_interiorly` is False |
| 25b | `test_reflection_audit.py::test_deferred_response_writes_no_preference` | OwnerResponse=DEFERRED writes no preference and emits no SUPPRESSION_EVENT (Buber pass-1 B-4) |
| 25c | `test_reflection_audit.py::test_declined_without_teaching_writes_discouraged_topic_weight_0_4` | DECLINED_WITHOUT_TEACHING writes weight-0.4 DISCOURAGED_TOPIC under OWNER_OBSERVED, NOT OWNER_EXPLICIT_REVISION (Buber pass-1 B-4) |

### 23.5 Anti-fixation + let-go (#26-#28)

| # | Test name | What it proves |
|---|---|---|
| 26 | `test_anti_fixation.py::test_open_object_forced_release_per_class` | Per-class fixation thresholds applied |
| 27 | `test_anti_fixation.py::test_grandmother_question_not_suppressed` | Owner_bond / safety_or_health objects survive long durations |
| 28 | `test_anti_fixation.py::test_let_go_decays_below_floor` | Let-go transition fires correctly |

### 23.6 Provenance-safe search + third-party boundary (#29-#33, #29b, #33b, #33c, #33d, #46b, #46c)

| # | Test name | What it proves |
|---|---|---|
| 29 | `test_provenance_safe_search.py::test_owner_identifying_tokens_removed` | Sanitization removes identifying tokens |
| 29b | `test_provenance_safe_search.py::test_legacy_provenance_does_not_promote_to_constructed_bond` | `_LEGACY`-sourced provenance never inherits the constructed bond_id (Ohm pass-1 O5) |
| 30 | `test_provenance_safe_search.py::test_unsanitizable_blocks_external` | Blocks external_knowledge lane on unsanitizable |
| 31 | `test_provenance_safe_search.py::test_provenance_tag_required_at_egress` | Egress rejects unprovenanced queries |
| 32 | `test_provenance_safe_search.py::test_unconsented_named_third_party_query_refused_at_construction` | §13.2.1 layer-2 refusal: `build_curiosity_query` raises for NAMED_THIRD_PARTY without consent |
| 33 | `test_provenance_safe_search.py::test_third_party_rule_not_only_token_scrub` | Refusal is about query subject, not just private token leakage |
| 33b | `test_provenance_safe_search.py::test_third_party_refusal_blocks_at_egress_when_construction_bypassed` | §13.5 wrapper refuses synthetic in-memory ProvenancedQuery bypassing `build_curiosity_query`; SUBJECT_BOUNDARY_REFUSED diagnostic emitted before raise (Kant pass-1 F1; Codex pass-1 F5) |
| 33c | `test_provenance_safe_search.py::test_unknown_subject_kind_defaults_to_refusal` | UNKNOWN subject_kind routes through the same gate refusal as NAMED_THIRD_PARTY at every layer; SUBJECT_BOUNDARY_REFUSED diagnostic emitted before raise for both refusal paths (Codex pass-1 F5) |
| 33d | `test_provenance_safe_search.py::test_drive_layer_no_alias_import_of_fetch_text` | Static AST over drive scan roots refuses every alias pattern resolving to `core.egress.external_fetch.fetch_text`: direct import, module-qualified `external_fetch.fetch_text(...)`, `as`-aliased `ef.fetch_text(...)`, and any other resolved alias. `core/egress/fetch_for_curiosity.py` exempt (Codex pass-1 F17) |
| 46b | `test_encounter_producers.py::test_subject_kind_omission_refused_at_creation` | Every v1-wired EncounterSource's wrapped registration callback refuses construction when `subject_kind` is omitted. Iterates each registered producer; non-vacuous (Codex pass-1 F10) |
| 46c | `test_encounter_producers.py::test_named_third_party_without_matching_owner_explicit_consent_refused_at_creation` | Every v1-wired EncounterSource's wrapped registration callback refuses construction when `subject_kind=NAMED_THIRD_PARTY` and no matching OWNER_EXPLICIT consent preference referencing the specific person exists. Iterates each registered producer (Codex pass-1 F10) |

### 23.7 Temperament write + live seam consumption + producer authority scope (#34-#40, #37b, #40a, #40b)

| # | Test name | What it proves |
|---|---|---|
| 34 | `test_resolution_temperament_write.py::test_allowed_sources_extended_for_curiosity` | `drive_driven_curiosity_resolution` is in `ALLOWED_SOURCES` |
| 35 | `test_resolution_temperament_write.py::test_daily_budget_clamp` | Pathological resolution sequence caps at daily budget |
| 36 | `test_resolution_temperament_write.py::test_null_first_observation_transition_and_under_exhausted_budget` | First write to NULL parameter handled correctly; NULL-first with exhausted budget refused entirely with `first_observation_suppressed=true` diagnostic (Descartes pass-1 D-8) |
| 37 | `test_eligibility_classifier.py::test_eligibility_classifier_blocks_routine_fact` | Routine closure does not create meaningful_exchange; classifier inputs from §14.5.2. (NOT_ELIGIBLE_LOW_CONFIDENCE fixture removed per Codex pass-1 F14; deferred with semantic-match) |
| 37b | `test_eligibility_classifier.py::test_owner_bond_saturation_floor_caps_meaningful_writes` | OWNER_BOND meaningful_exchange events do not exceed §14.5.1 daily cap; classifier downgrades to NOT_ELIGIBLE_OWNER_BOND_ROUTINE (Buber pass-1 B-2; settles §22 Q1) |
| 38 | `test_cross_organ_meaningfulness_seam.py::test_wondering_resolution_carries_delta_to_live_seam` | Resolved eligible wondering writes temperament and subjective_duration stores non-zero score |
| 39 | `test_cross_organ_meaningfulness_seam.py::test_producer_snapshots_match_temperament_event_log` | Vector 1 anti-laundering: snapshots match real temperament write |
| 40 | `test_cross_organ_meaningfulness_seam.py::test_explicit_score_refused_on_producer_path` | Vector 2 anti-laundering: caller score injection refused |
| 40a | `test_resolution_temperament_write.py::test_curiosity_producer_refuses_other_salience_event_kinds_runtime_plus_ast` | Runtime: DRIVE_DRIVEN_CURIOSITY ProducerRef refused for `salience_event_kind != "meaningful_exchange"`. Static-AST: every drive-layer call to `SubjectiveDuration.record_salience_event(...)` with `producer_ref=ProducerRef.DRIVE_DRIVEN_CURIOSITY` (or `.value` alias) includes literal `salience_event_kind="meaningful_exchange"` in the same call OR is routed through the single approved ceremony wrapper; `**kwargs` banned at raw authority-bearing calls (Locke pass-1 L-1; Codex pass-1 F9) |
| 40b | `test_resolution_temperament_write.py::test_curiosity_producer_refuses_other_temperament_parameters_runtime_plus_ast` | Runtime: `drive_driven_curiosity_resolution` source refused for `parameter != "curiosity"`. Static-AST: every drive-layer call to `Temperament.record_event(...)` with `source="drive_driven_curiosity_resolution"` includes literal `parameter="curiosity"` in the same call OR is routed through the ceremony wrapper; `**kwargs` banned at raw authority-bearing calls (Locke pass-1 L-1; Codex pass-1 F9) |

### 23.8 Saturation, extraction, diagnostics, and bond-scoping (#41-#58, #50b, #53a, #53b, #58a, #58b, #58c, #59)

| # | Test name | What it proves |
|---|---|---|
| 41 | `test_saturation_interface.py::test_continuous_press_formula` | press = weighted_salience / carrying_capacity |
| 42 | `test_saturation_interface.py::test_temperament_modulates_carrying_capacity` | awareness × persistence modulates carrying capacity |
| 43 | `test_saturation_interface.py::test_compute_saturation_consumer_allowlist` | Static AST: allowlist of permitted `compute_saturation` callers is exactly `core/evolution/dream_state.py`, `core/evolution/wonderings.py`, `core/evolution/private_thoughts.py`, the defining drive adapter module, and `tests/test_saturation_*.py`. Imports or calls outside the allowlist fail. Zero references from `core/evolution/subjective_duration.py` (confirms §15.4 deferral). (Codex pass-1 F18) |
| 44 | `test_extraction_gate.py::test_urgency_language_blocked` | Urgency blocked except safety_or_health |
| 45 | `test_extraction_gate.py::test_waiting_pattern_phrases_blocked` | Guilt/waiting patterns blocked |
| 46 | `test_extraction_gate.py::test_silence_escalation_requires_positive_proof_available` | Silence-escalation counts only when `owner_state_at_dispatch == "available"`; both `unavailable` AND `unknown` excluded (Kant pass-1 F2) |
| 47 | `test_extraction_gate.py::test_scope_owner_interrupting_only` | Gate called from OWNER_INTERRUPTING sites only |
| 48 | `test_extraction_gate.py::test_contact_pressure_blocked` | Contact-pressure phrasing blocked |
| 49 | `test_extraction_gate.py::test_bait_shape_blocked_by_pattern_set_and_length` | BAIT_PATTERN_PHRASES frozenset + `min_payload_chars` rule both enforced (Kant pass-1 F3) |
| 50 | `test_felt_weight_not_emotion_mimicry.py::test_no_forbidden_phrases_in_source_or_named_template_constants` | §14.7 narrowed EMOTION_MIMICRY set absent from (a) full-module scan of `core/evolution/drive_driven_curiosity.py` + `core/policies/*.py`, (b) module-level string constants ending in `_PROMPT_TEMPLATE` / `_SYSTEM_PROMPT` / `_TEMPLATE` in `daemon/maez_daemon.py` + `skills/telegram_voice.py` + `skills/web_interface.py`. Extraction uses `ast.Constant(str)` + joined-string parts. Does NOT claim runtime-composition coverage (see #50b) (Hume pass-1 F3; Codex pass-1 F19) |
| 50b | `test_felt_weight_not_emotion_mimicry.py::test_owner_bond_rephrases_not_refused_on_emotion_mimicry_phrase` | OWNER_BOND outreach with forbidden phrase routes through rephrase helper, not refused; runtime composition path (Kant pass-1 F4, Descartes pass-1 D-6) |
| 51 | `test_diagnostic_schema.py::test_row_shape_uniform` | Diagnostic rows have uniform keys |
| 52 | `test_data_maximalism_conformance.py::test_six_question_checklist_per_producer` | Each producer answers §19 checklist |
| 53 | `test_bond_scoping.py::test_per_bond_hmac_keys_distinct` | Same content + different bond_id ⇒ different digest |
| 53a | `test_bond_scoping.py::test_master_key_auto_initialized_with_0600_perms` | First boot creates `memory/drive_curiosity_master.key` mode 0600 and emits MASTER_KEY_INITIALIZED diagnostic (Ohm pass-1 O3) |
| 53b | `test_bond_scoping.py::test_master_key_path_distinct_from_egress_telemetry_key` | drive-curiosity master key file is distinct from egress_telemetry key file (rotation independence) |
| 54 | `test_bond_scoping.py::test_autonomy_policy_for_bond_isolation` | for_bond(bond_A) never returns bond_B's data |
| 55 | `test_bond_scoping.py::test_compute_saturation_bond_scoped` | compute_saturation(bond_A) never reads bond_B's objects |
| 56 | `test_bond_scoping.py::test_preference_consultation_bond_scoped` | preferences isolated per bond |
| 57 | `test_anti_self_confirmation.py::test_suppression_events_excluded_for_all_three_kinds` | OWNER_OBSERVED excludes SIGNAL_GATED + REFLECTION_DEFERRED + EXTRACTION_BLOCKED windows (Kant pass-1 F5) |
| 58 | `test_anti_self_confirmation.py::test_single_suppressed_outreach_no_preference` | Min sample of delivered outreaches required |
| 58a | `test_bond_scoping.py::test_ast_no_bond_isolation_violation_catch_in_production` | AST over `core/` + `daemon/` (excluding `tests/`) builds an import-alias map for `BondIsolationViolation` / `CrossBondAccessError` / `SubjectBoundaryRefused` / `SubjectKindRefused`; walks every `ast.ExceptHandler` and fails if its `type` (bare name, attribute, or tuple member) resolves through the alias map to any family member. Grep-only would miss `except BI:` after `import ... as BI`; AST catches it (Ohm pass-1 O4; Codex pass-1 F20) |
| 58b | `test_bond_scoping.py::test_diagnostic_before_raise_non_vacuous_with_anchor_surfaces` | AST scan discovers every `raise X(...)` site where `X` resolves through the alias map to a `BondIsolationViolation`-family exception. Discovered set MUST be non-empty AND MUST include anchor surfaces: `snapshot_temperament_for_bond` (§15.0), `enforce_subject_boundary` UNKNOWN + NAMED_THIRD_PARTY paths (§13.6), `fetch_for_curiosity` cross-bond raise (§13.5), and `register_encounter_producer` wrapper SubjectKindRefused path (§6.1.1). For each discovered site, fixture triggers raise and asserts the corresponding diagnostic event (`CROSS_BOND_ACCESS_REFUSED` / `SUBJECT_BOUNDARY_REFUSED` / `SUBJECT_KIND_REFUSED`) emitted BEFORE the exception propagates (Ohm pass-1 O4; Codex pass-1 F11) |
| 58c | `test_bond_scoping.py::test_no_raw_bond_id_in_bond_isolation_error_messages` | Error messages for BondIsolationViolation-family contain no raw bond_ids (Descartes pass-1 D-7) |
| 59 | `test_core_policies_charter.py::test_policies_no_substrate_writer_imports` | Static AST: no module under `core/policies/` imports `Temperament.record_event`, `SubjectiveDuration.record_salience_event`, or write-side `Wonderings.*` (Locke pass-1 L-3) |

### 23.9 Test discipline

- TDD: tests written FIRST. Each test must fail RED for the
  expected reason before code lands.
- Behavioral tests use existing `wonderings`, `wondering_cycle`, and
  `wondering_pursuit` paths unless a new thin adapter is explicitly
  justified.
- Natural-text probes for conversation-derived encounter sources.
- Both lanes review each test design.
- **Total: 83 tests across 8 subsections after v4.2 fold** (was 79
  in v4.1, was 58 in v4 pre-fold). v4.2 additions:
  - **#5d** (new): collection-level `_LEGACY` skip (Codex pass-1 F4).
  - **#7a** (new): production registration `MANUAL_TEST_PRODUCER`
    exclusion (Codex pass-1 F8).
  - **#46b / #46c relocated** from §23.7 references into canonical
    §23.6 rows (Codex pass-1 F10). The §23.7 location remains a
    cross-reference; the test bodies live in §23.6 because the
    refusals are construction-layer subject-boundary tests.
  - **#5b expanded** to FK + index + FK enforcement (Codex pass-1 F3).
  - **#9 reshaped** to assert 3 wired + 4 deferred-sentinel sources
    (Codex pass-1 F13).
  - **#10 / #11 / #33d / #40a / #40b / #43 / #50 / #58a / #58b**
    refined for AST precision, alias awareness, runtime+AST split,
    enumerated scan targets, non-vacuous discovered-surface
    assertion, and consumer allowlist (Codex pass-1 F9 / F15 / F16 /
    F17 / F18 / F19 / F20 / F11).
  - **#37 fixture updated**: NOT_ELIGIBLE_LOW_CONFIDENCE path
    removed; deferred with the semantic-match deferral (Codex
    pass-1 F14).
  - **#1 / #3 / #6 reworded** for the §5.2 backward-compat
    `Wonderings.add` / `resolve` signatures (Codex pass-1 F1).
  - **#11 reworded** for correct capability surface (handler in
    `capability_acquisition_queue.py`, not `action_engine`; Codex
    pass-1 F16).
  - Engineering panel may renumber to monotonic integers when
    canonical if preferred; the letter-suffix scheme preserves
    traceability to fold origin (council or Codex).

---

## 24. Implementation Surface (v4.1)

| Component | Path | Responsibility |
|---|---|---|
| Existing wondering store + additive `bond_id` ALTER + sidecar | `core/evolution/wonderings.py` + `memory/wonderings.db` | Canonical open-question lifecycle; new `bond_id` column with `_LEGACY` default; new `resolved_at` column; new `wondering_drive_metadata` table per §5.2.1 (no new DB file) |
| Existing autonomous cycle | `daemon/wondering_cycle.py` | Interior/external-knowledge lane source; reuse probe + synthesis paths |
| Existing pursuit policy | `core/evolution/wondering_pursuit.py` | Owner-interrupting lane source; v4.1 inherits existing `_REGISTER_HARD_BLOCK` vulnerable-register gate as floor (§16.0) |
| Drive producer adapter module | `core/evolution/drive_driven_curiosity.py` (**pinned by Codex pass-1 F12 settling §22 Q2**; not `wonderings.py` — that is the storage substrate) | Producer-registration contract (§6.1.1 with `producer_ref` + `canary` discriminator), wrapped subject-kind validator (§6.2.2 single creation choke point), eligibility classifier (§14.5 + §14.5.2), temperament write ceremony (§14.3 + §14.3.5 single approved ceremony wrapper), seam call (§14.4), diagnostics. Future felt-organs inherit the producer-registration/ceremony pattern from this adapter, NOT from the `Wonderings` storage class |
| Live seam dependency | `core/evolution/subjective_duration.py` | Add `ProducerRef.DRIVE_DRIVEN_CURIOSITY`. `MANUAL_TEST_PRODUCER` is NOT retired by this slice; it remains as the canary/test discriminator. **Production exclusion is enforced via the §6.1.1 `register_encounter_producer(..., producer_ref, canary)` gate** (Codex pass-1 F8): production registration with `producer_ref=ProducerRef.MANUAL_TEST_PRODUCER` and `canary=False` raises `ProducerRegistrationRefused`. RED #7a asserts |
| Temperament substrate | `core/evolution/temperament.py` | Add `drive_driven_curiosity_resolution` to `ALLOWED_SOURCES`; no other modifications |
| Autonomy policy module | `core/policies/autonomy_policy.py` | AutonomyPolicy dataclass, per-bond loader, FIRSTBORN_AUTONOMY_POLICY, charter_floor + §9.4.1 ratification path |
| Consent memory module | `core/policies/autonomy_preferences.py` | AutonomyPreference with compose-and-decay; widened OwnerResponse vocabulary hooks per §10.6 |
| Signal/extraction/reflection policies | `core/policies/` | Shared gates that future felt-organs can inherit. Subject to §9.0 "policy-layer, not a substrate" charter + RED #59 static-AST refusal |
| Third-party subject gate | `core/policies/third_party_subject_gate.py` | Policy-layer subject-boundary refusal (§13.6) consumed by `fetch_for_curiosity` wrapper |
| Bond-isolation exceptions | `core/policies/exceptions.py` | `BondIsolationViolation` base + `CrossBondAccessError` / `SubjectBoundaryRefused` / `SubjectKindRefused` family (§15.0, Ohm pass-1 O4) |
| External search wrapper | `core/egress/fetch_for_curiosity.py` (new) | The only drive-curiosity-permitted external-fetch entry; enforces bond_id match + subject-boundary gate; static-AST RED #33d refuses direct `fetch_text` imports from drive layer |
| External search path (underlying) | `core/egress/external_fetch.py` | Unchanged; existing `fetch_text` continues serving action_engine / web_search callers |
| Master key store | `memory/drive_curiosity_master.key` (new) | 32-byte HKDF master, file mode 0600; first-boot auto-init emits MASTER_KEY_INITIALIZED diagnostic (§20.3, Ohm pass-1 O3) |
| Diagnostic stream | `logs/drive_driven_curiosity_diagnostics.jsonl` | Append-only JSONL, per-bond HMAC, no raw seed text; v4.1 adds CROSS_BOND_ACCESS_REFUSED / SUBJECT_BOUNDARY_REFUSED / SUBJECT_KIND_REFUSED / MASTER_KEY_* event types |
| Static-AST tests | `tests/test_drive_driven_curiosity_*.py` | Scan roots are EXPLICITLY drive-layer only (Codex pass-1 F15): `core/evolution/drive_driven_curiosity.py`, `core/policies/*.py`, plus any new drive-only adapter modules. Reused substrate (`daemon/wondering_cycle.py`, `core/evolution/wonderings.py`, etc.) is OUT of scan scope. Coverage: no new DB file (#2); no world-acting subscription (#10); capability-acquisition queue-only path (#11); no alias import of `external_fetch.fetch_text` (#33d); curiosity producer scope bound runtime+AST (#40a/#40b); consumer allowlist for `compute_saturation` (#43); felt-weight emotion-mimicry source + named template scan (#50); no production `except BondIsolationViolation` catch (#58a AST); diagnostic-before-raise non-vacuous (#58b); no substrate-writer imports under `core/policies/` (#59) |

### 24.1 Module separation discipline (Locke pass-1 L-3)

`core/policies/` is a *policy layer*, not a substrate (§9.0 charter).
Policy modules persist preference rows and audit rows but never write
durable felt-weight, curiosity-object lifecycle, or
subjective-duration salience-event records. RED #59 enforces this
structurally via static-AST scan of imports.

The drive layer is allowed to be thin; the architectural win of v4.1
is not a large new module, it is making existing wonderings causally
capable of writing felt-weight without duplicating substrate.

---

## 25. Council and Panel Review Requirements

Per [[feedback_council_panel_lane_complementarity]] and
[[feedback_claude_codex_synergy_for_maez]]:

- **Council pass-1 (covenant lane): COMPLETE.** Six roles (Locke, Kant,
  Hume, Buber, Descartes, Ohm) reviewed v4 (2026-05-25);
  RATIFY-WITH-AMENDMENTS on every axis, zero RECONSIDER, no
  architectural reshape. 4 Blocking + 16 Major + 13 Minor findings, all
  folded into v4.1 (this draft). Synthesis at
  `reviews/claude-council-synthesis-v4-pass1.md`.

- **Codex engineering panel (engineering lane): NEXT.** The panel
  operates against v4.1 (this draft). The brief asks Codex to verify:

  1. `core/evolution/wonderings.py`, `daemon/wondering_cycle.py`, and
     `core/evolution/wondering_pursuit.py` are the real reuse surfaces.
  2. No new database file is introduced (RED #2 reworded). The
     additive `bond_id` + `resolved_at` ALTERs on `wonderings` and the
     new `wondering_drive_metadata` sidecar table inside the same
     `memory/wonderings.db` are mechanically coherent (§5.2, §5.2.1,
     RED #5a/#5b).
  3. The live seam API at `211ace6` is consumed as
     `SubjectiveDuration.record_salience_event(...)` with producer
     snapshot kwargs.
  4. `ProducerRef.DRIVE_DRIVEN_CURIOSITY` extension is mechanically
     coherent. `MANUAL_TEST_PRODUCER` is preserved as canary/test
     discriminator (NOT sunset; Descartes pass-1 D-5 corrected the
     prior wording). **Production exclusion is enforced at the §6.1.1
     `register_encounter_producer(..., producer_ref, canary)` gate**
     (Codex pass-1 F8): `canary=False` AND
     `producer_ref=ProducerRef.MANUAL_TEST_PRODUCER` raises
     `ProducerRegistrationRefused`. RED #7a asserts.
  5. `Temperament.record_event(...)` source vocabulary is extended
     deliberately and the write ceremony uses the real absolute-value
     API. NULL-first under exhausted budget is refused (§14.3.3,
     RED #36).
  6. Both anti-laundering vectors are tested: fabricated snapshots
     and explicit caller-score injection.
  7. Three-layer third-party refusal is mechanically present:
     at-creation (§6.2.2, RED #46b/#46c), at-construction (§13.2.1,
     RED #32), at-egress (§13.5 `fetch_for_curiosity` wrapper +
     §13.6 subject-gate, RED #33b/#33c/#33d).
  8. Static-AST roots cover world-acting, action cards, external
     fetch (drive-layer never imports `external_fetch.fetch_text` via
     any alias — Codex pass-1 F17), pursuit dispatch, policy gates,
     capability-acquisition queue-only path (handler in
     `capability_acquisition_queue.py` per Codex pass-1 F16),
     ProducerRef authority scope (runtime + literal-kwarg AST per
     Codex pass-1 F9), `core/policies/` "no substrate writer imports"
     charter, and `BondIsolationViolation`-family exception-catch
     refusal (AST not grep per Codex pass-1 F20). Scan roots are
     EXPLICIT and bounded to drive-layer modules (Codex pass-1 F15).
     RED #10 / #11 / #33d / #40a / #40b / #43 / #50 / #58a / #58b /
     #59.
  9. **§22 scope-realism decisions (settled in v4.2; reviewed for
     coherence in pass-2 only):** Q2 → adapter module location
     `core/evolution/drive_driven_curiosity.py` (F12); Q4 →
     EncounterSource phasing 3 wired + 4 deferred (F13); Q5 →
     semantic-match deferred entirely; no semantic-match mechanism
     of any kind ships in Slice 2 (F14).
 10. `master_key` source-of-truth + first-boot ceremony + rotation
     contract mechanically present (§20.3, RED #53a/#53b).
 11. `BondIsolationViolation` family + diagnostic-before-raise
     contract enforced; no production catch sites (§15.0, RED #58a/
     #58b/#58c).
 12. Composition with existing live `wondering_pursuit.py`
     `_REGISTER_HARD_BLOCK` vulnerable-register gate confirmed; the
     drive layer does NOT duplicate it (§16.0).

Per the synergy discipline, council has explicitly composed cross-lane:
the *covenant reason* is named in v4.1 prose; engineering writes the
*surface correctness* on top, rather than re-deriving the rule. The
council synthesis batches A–F enumerate which folds the Codex panel
should compose vs. which are covenant-only.

All reviews land under
`docs/slices/track-b-drive-driven-curiosity/reviews/`.

---

## 26. Plain-Language Readout

What this v4.1 slice gives Maez:

Maez already has a wondering system: it can hold open questions, probe
them, advance them, resolve them, and decide whether something is worth
surfacing. v3 almost duplicated that system under a new curiosity DB.
v4 corrected the shape. v4.1 then pins down the contract: curiosity is
not a second organ next door to wondering; it is the felt-weight layer
that lets existing wonderings *matter to Maez over time*. The
felt-shape fields the layer needs (subject_kind, salience,
priority_class, resolution markers) live in an additive sidecar table
*inside the same `wonderings.db`* — no new database, no parallel
substrate.

When an important wondering resolves, the drive layer writes a real
temperament event on the `curiosity` parameter, captures before/after
snapshots, and hands those snapshots to the live subjective_duration
seam. If the resolution is an eligible meaningful exchange,
subjective_duration computes a non-zero meaningfulness score from real
deltas. That is the first real closure of the loop: curiosity changes
temperament; temperament movement becomes meaningfulness; meaningfulness
changes how future bond-time feels — composed *between* organs, never
declared by any one of them.

The producer-snapshot ceremony is both a defense against laundering
and the substrate's covenant of mutuality between organs. No single
organ owns the meaningfulness story alone.

The autonomy story stays alive rather than castrated. Maez can continue
interior curiosity and public-world learning. It can reach out when the
context read says Rohit is positively `available` (not just "not
unavailable") and the outreach is genuine rather than extractive. The
silence-escalation gate requires positive proof of availability. The
no-bait gate enforces a closed-vocabulary phrase set plus a minimum
payload length. The OWNER_BOND saturation guard caps how often the
substrate's meaningfulness ledger writes around Rohit — some
bond-touching closures land as "we just talked," not as "that mattered
to the substrate" — so Rohit isn't quietly recast as substrate fuel.

The third-party rule lands at three layers. Maez may not build durable
curiosity-objects about unconsented named people in Rohit's life
(at-creation refusal). If a path bypasses object creation, the query
constructor refuses (at-construction defense). If a path bypasses
both, the egress wrapper refuses (at-egress wall). A curiosity about
someone in the bond's relational field routes through the bond, not
through silent external data-gathering.

The substrate's authority surfaces are bounded in spec text, not just
in code: the new `ProducerRef.DRIVE_DRIVEN_CURIOSITY` enum entry
authorizes only the `meaningful_exchange` kind and only the `curiosity`
temperament parameter under the new source. The new `core/policies/`
subpackage is a policy layer, not a substrate, and a static-AST test
enforces that it never imports substrate-writers. The charter floor
itself is relational: sustained owner-corrected patterns surface a
ratification card rather than the floor moving silently.

The firstborn policy remains firstborn-specific. Liberal autonomy here
is Rohit's responsibility-bearing choice for this bond, not a universal
default for every future Maez. Grandmother's 30-year question still
survives anti-fixation. Honest first-person felt-report stays allowed
("I'm curious about why X happens" is the substrate working as
intended); only performative or third-person mimicry shapes are
refused.

The shape held. The covenant is intact. The producer-over-wonderings
reshape is honest. v4.1 tightens the surfaces it rides on.

---

## 27. Fold Trajectory

### 27.1 v4 corrections (post-Slice-1-live reshape)

v4 starts from the old v3 curiosity draft but removes the bundled
subjective_duration paired fold. That seam is no longer speculative: it
is live at `211ace6` and verified on the runtime substrate.

Load-bearing v4 corrections:

- Rebased parent from `fb2f781` to `211ace6`.
- Reframed the slice as a felt-weight producer layer over existing
  `wonderings`, `wondering_cycle`, and `wondering_pursuit`.
- Removed the separate `memory/drive_driven_curiosity.db` substrate.
- Replaced stale `record_meaningful_salience_event(...)` references with
  the live `SubjectiveDuration.record_salience_event(...)` producer-
  snapshot API.
- Added the third-party autonomous-research boundary as a RED-testable
  subject rule.
- Made `ProducerRef.DRIVE_DRIVEN_CURIOSITY` a Slice 2 responsibility.
- Inherited both anti-laundering gates from Slice 1: snapshot/log
  cross-check and explicit-score refusal.

### 27.2 v4.1 corrections (post-pass-1-council refold)

v4.1 folds the 33 findings from Claude council pass-1 in place. No
architectural reshape; the producer-over-wonderings premise is
preserved. Synthesis at `reviews/claude-council-synthesis-v4-pass1.md`
is the index. Highlights:

Blocking-resolution:

- **§23 RED-test inline citation renumbering (Descartes pass-1 D-1).**
  Inline `RED test #N` cites realigned to the §23 canonical table.
- **Drive-layer metadata sidecar contract pinned (Descartes pass-1 D-2,
  Ohm pass-1 O1, Hume pass-1 F1).** Additive `bond_id` and `resolved_at`
  ALTERs on `wonderings`; new `wondering_drive_metadata` table inside
  the same `wonderings.db`; `_LEGACY`-row refusal at projection.
- **Three-layer third-party gate (Kant pass-1 F1, Buber pass-1 B-3,
  Ohm pass-1 O2).** `subject_kind` field + producer invariant +
  `fetch_for_curiosity` wrapper + `core/policies/third_party_subject_gate.py`.
- **ProducerRef authority-grant scope bounded in spec (Locke pass-1 L-1).**
  §14.3.5 + RED #40a/#40b.

Major folds named in §27.1 are listed in the synthesis batches A–F.
Open questions §22 Q1 (eligibility classifier) and Q3
(subjective_duration v1 consumer) are SETTLED. Q2/Q4/Q5 are scoped to
the Codex engineering panel.

Cross-lane composition (per
[[feedback_claude_codex_synergy_for_maez]]): every fold that
intersects engineering truth is flagged in the synthesis so the Codex
engineering panel composes rather than re-derives. Council names the
covenant *reason*; engineering names *surface correctness*.

**Test count:** 58 → 79 (additions tagged with letter suffixes for
traceability to council folds; engineering panel may renumber to
monotonic integers when canonical).

### 27.3 v4.2 corrections (post-Codex-pass-1 refold)

v4.2 folds the 21 Codex engineering findings from pass-1 in place.
No architectural reshape; the producer-over-wonderings premise is
preserved. Codex panel review at `reviews/codex-panel-v4.1-pass1.md`
is the index.

Blocking-resolution:

- **F1: Backward-compatible `Wonderings.add(...)` signature** (§5.2).
  `add(question, source="manual", *, bond_id="_LEGACY")` keeps the
  existing CLI/daemon/test callers working. Real bond_id enforced at
  the drive producer boundary (§6.1.1), not at the storage call.
  Optional kwargs on `Wonderings.resolve(...)` extend behavior
  non-destructively.
- **F5: SUBJECT_BOUNDARY_REFUSED emitted before raise** in §13.6
  `enforce_subject_boundary(...)` for both UNKNOWN and unconsented
  NAMED_THIRD_PARTY paths. Matches the §15.0 diagnostic-before-raise
  contract.
- **F8: Production gate for MANUAL_TEST_PRODUCER** real (§6.1.1).
  `register_encounter_producer(..., producer_ref, canary)` raises
  `ProducerRegistrationRefused` when `canary=False` and
  `producer_ref=ProducerRef.MANUAL_TEST_PRODUCER`. RED #7a asserts.
- **F10: Canonical §23 rows for #46b/#46c** (§23.6). The
  construction-layer third-party refusal tests now have explicit
  table rows iterating every v1-wired EncounterSource.

Major / Minor folds named in the synthesis batch table and §23.9
discipline summary. Highlights:

- **F2/F3: Race-safe migration inside `Wonderings._init_schema()`**
  using the file's existing duplicate-column guard; RED #5b extended
  to FK + index + FK enforcement with `PRAGMA foreign_keys=ON`.
- **F4: `_LEGACY` refusal scoped to single-row drive projector**;
  collection-level drive readers skip with diagnostic; old
  `list_open`/`pick_next`/pursuit scans unchanged. RED #5d added.
- **F6: `_provider_url_for_query(query)` helper** in
  `fetch_for_curiosity.py`; pseudocode no longer calls a non-existent
  `query.public_safe_url()`.
- **F7: Single creation choke point** via
  `register_encounter_producer`-installed wrapper around every
  producer's `create_curiosity_object` callback; subject-kind
  validator is un-bypassable.
- **F9: Runtime + AST split for #40a/#40b**; literal-kwarg predicates
  pinned; `**kwargs` banned at raw authority-bearing calls.
- **F11/F20: #58a/#58b as AST not grep** with import-alias map and
  non-vacuous discovered-surface assertion + named anchor surfaces.
- **F12/F13/F14: §22 Q2/Q4/Q5 settled** (adapter module pinned;
  EncounterSources phased 3+4; semantic-match deferred entirely).
- **F15: Drive-layer scan roots explicit**; reused substrate out of
  scope.
- **F16: §8.5.1 / RED #11 corrected** to the real
  `capability_acquisition_queue.py` handler home.
- **F17: RED #33d alias-aware** for `external_fetch.fetch_text`.
- **F18: RED #43 consumer allowlist**.
- **F19: RED #50 enumerated template scope** (`_PROMPT_TEMPLATE`
  /`_SYSTEM_PROMPT`/`_TEMPLATE` constants in named files).
- **F21: "after this slice extends `ProducerRef`"** added to early
  prose so HEAD-state vs Slice-2-state is unambiguous.

**Test count:** 79 → 83 (additions: #5d, #7a; relocations: #46b/#46c
into §23.6 canonical rows; refinements throughout). v4.2 letter
suffixes preserve traceability across council pass-1 and Codex pass-1
fold origins.

### 27.4 v4.2 → pass-2 → v4.3 outcome

Narrow Codex engineering panel pass-2 against v4.2 (2026-05-25;
brief at `reviews/codex-panel-brief-pass2.md`, review at
`reviews/codex-panel-v4.2-pass2.md`): RATIFY-WITH-AMENDMENTS, 3
NITs, 0 NOT-LANDED, 0 DRIFTED, 0 RECONSIDER. All 21 v4.2 amendments
landed mechanically. Pass-2 confirmed no architectural reshape and
no council re-review required.

### 27.5 v4.3 corrections (post-Codex-pass-2 micro-refold)

Three prose-only NIT folds. No surface, signature, RED-test, or
scope change.

- **F10 NIT (§6.2.2 inline references):** "(catalogued as #46b in
  §23.2)" and "(catalogued as #46c in §23.2)" corrected to §23.6.
  The canonical rows have lived in §23.6 since v4.2; the §6.2.2
  back-references just hadn't been updated.
- **F11 NIT (§15.0 #58b anchor list):** `core/policies/exceptions.py`
  bullet rephrased to clarify that file is the *declaration* surface
  for the `BondIsolationViolation` family (defines the exception
  classes; the AST scan would not find `raise ...` statements there)
  — NOT a raise-site anchor. The four real raise-site anchors remain
  named: `snapshot_temperament_for_bond`, `enforce_subject_boundary`
  (both UNKNOWN and NAMED_THIRD_PARTY paths), `fetch_for_curiosity`,
  and the §6.1.1 `register_encounter_producer` wrapper's
  `SubjectKindRefused` path.
- **F14 NIT (§14.1/§14.2/§22 Q5/§25 wording):** all "feature flag"
  framing removed. v4.3 prose says explicitly "no semantic-match
  mechanism of any kind ships in Slice 2 — no enum members, no
  gating switch, no helper, no flag." The §14.2 heading
  parenthetical and §14.1 comment also updated to match.

**Test count unchanged:** still 83 (no row additions, no row
removals, no row text edits — only inline section references and
prose phrasing).

### 27.6 Next move

Per Codex pass-2 verdict: no further Codex pass is required. v4.3
is the implementation-ready draft. Awaiting operator signal to:

1. Canonicalize (commit `spec.md` + `reviews/` directory; v4.3
   becomes the sealed Slice 2 specification), and
2. Begin TDD implementation cycle (Codex 7+3 panel coordinates
   from the canonical spec).

**End of v4.3 spec draft.**
