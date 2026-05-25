# Codex Engineering Panel -- Drive-Driven Curiosity v4.1 Pass 1

**Verdict:** RATIFY-WITH-AMENDMENTS

**Severity summary:** v4.1 holds the producer-over-wonderings architecture and
does not need cross-lane RECONSIDER. The panel found foldable engineering gaps:
4 Blocking, 16 Major, and 8 Minor findings. The Blocking cluster is all
mechanical: preserve existing `Wonderings` callers, make the third-party
creation/egress boundary auditable, make `MANUAL_TEST_PRODUCER` exclusion a
real production gate, and restore canonical RED coverage for #46b/#46c.

## Finding 1 -- Preserve Existing Wonderings Callers

**Severity:** Blocking
**Axis:** 1 / 7 -- Real-surface verification; live API truth
**Surface:** §5.2; RED #3/#6;
`core/evolution/wonderings.py:272-285`, `:607-616`;
`cli/maez_chat.py:489-496`; `daemon/wondering_cycle.py:286-288`;
`tests/test_wonderings.py`; `tests/test_wondering_pursuit_history.py`

**Issue:** v4.1 says new rows use
`Wonderings.add(question, source, bond_id=...)`, but the live signature is
`add(question, source="manual")`. Existing CLI, daemon, and test callers omit
`bond_id`. Making `bond_id` required would break old wondering behavior;
defaulting old callers to a real bond would silently promote legacy/non-drive
rows into drive projection.

**Required engineering fold:** Specify a backward-compatible signature:
`add(question, source="manual", *, bond_id="_LEGACY")`. Drive-layer creation
must call with a real `bond_id` and fail before projection if missing. Keep
`resolve(wondering_id, conclusion, *, resolved_at=None,
resolution_marker_type=None, resolution_marker_utc=None)` optional, or put the
new marker behavior behind a drive-specific resolution wrapper.

**8-step trace:** Existing `/wonder` and tests call `add` without `bond_id`;
v4.1 introduces a required bond-bearing path; required would break callers;
real-bond default would launder old rows; `_LEGACY` default preserves behavior;
drive projection refuses `_LEGACY`; drive producers still require real bond at
their boundary; tests must assert both compatibility and refusal.

**Council-axis composition flag:** Y -- composes Ohm O1 / Descartes D-2 with
actual API compatibility.

## Finding 2 -- Use Wonderings' Race-Safe Migration Pattern

**Severity:** Major
**Axis:** 1 -- Real-surface verification
**Surface:** §5.2; `core/evolution/wonderings.py:174-270`;
`core/evolution/subjective_duration.py:334-357`

**Issue:** v4.1 cites the Slice 1 PRAGMA-then-ALTER migration shape, but the
target file already has a stronger cross-process duplicate-column guard.
Daemon, CLI, and web can race schema initialization.

**Required engineering fold:** §5.2 should require adding `bond_id` and
`resolved_at` inside `Wonderings._init_schema()` with the existing
`existing_cols` plus `try/except sqlite3.OperationalError` duplicate-column
pattern, followed by `CREATE TABLE IF NOT EXISTS` and
`CREATE INDEX IF NOT EXISTS`.

**8-step trace:** Required because this touches live schema migration. Use the
target file's proven write path, not only the analogous Slice 1 migration.

**Council-axis composition flag:** Y -- mechanical fold of Descartes D-2.

## Finding 3 -- RED #5b Must Verify FK, Indexes, And FK Enforcement

**Severity:** Major
**Axis:** 1 -- Real-surface verification
**Surface:** §5.2.1; RED #5b; `core/evolution/wonderings.py:164-172`

**Issue:** `PRAGMA table_info(wondering_drive_metadata)` proves columns only.
It does not prove the foreign key exists, the bond index exists, or SQLite FK
enforcement is active. Current `Wonderings._conn()` does not set
`PRAGMA foreign_keys=ON`.

**Required engineering fold:** Extend RED #5b to assert
`PRAGMA foreign_key_list(wondering_drive_metadata)` points to `wonderings(id)`,
`PRAGMA index_list(...)` contains `idx_wondering_drive_metadata_bond`, and a
negative insert fails with FK enforcement enabled. Specify that write/migration
connections enable `PRAGMA foreign_keys=ON`.

**8-step trace:** Required because this is a schema-integrity gate.

**Council-axis composition flag:** Y -- makes the sidecar contract mechanical.

## Finding 4 -- Isolate `_LEGACY` Refusal To Drive Projection

**Severity:** Major
**Axis:** 1 -- Real-surface verification
**Surface:** §5.1, §5.2.1; `core/evolution/wonderings.py:295-306`, `:342-374`;
`daemon/maez_daemon.py:3636-3639`

**Issue:** Existing `list_open` and `pick_next` intentionally read all
open/active wonderings. Filtering `_LEGACY` there would alter the current
wondering loop and pursuit behavior. Raising during collection projection would
let one legacy row poison scans.

**Required engineering fold:** State that old `Wonderings` read paths remain
unchanged. `_LEGACY` refusal belongs in the new single-row drive
`CuriosityObject` projector; collection-level drive readers skip/refusal-log
legacy rows instead of breaking `list_open`, `pick_next`, or pursuit scans.

**8-step trace:** Required because it protects a live reused substrate.

**Council-axis composition flag:** Y -- preserves Ohm O1 without damaging old
wondering behavior.

## Finding 5 -- Emit `SUBJECT_BOUNDARY_REFUSED` Before Raising

**Severity:** Blocking
**Axis:** 2 -- Three-layer third-party gate
**Surface:** §13.6, §15.0, §20.1; RED #58b

**Issue:** §13.6 pseudocode raises `SubjectBoundaryRefused` for `UNKNOWN` and
unconsented `NAMED_THIRD_PARTY` directly. §15.0 requires a specific diagnostic
before any `BondIsolationViolation`-family raise.

**Required engineering fold:** Make
`third_party_subject_gate.enforce_subject_boundary(...)` emit
`SUBJECT_BOUNDARY_REFUSED` before each `SubjectBoundaryRefused` raise, with no
raw bond/person identifiers. RED #58b must assert ordering for both `UNKNOWN`
and unconsented `NAMED_THIRD_PARTY`.

**8-step trace:** A `ProvenancedQuery` reaches egress; construction-bypass tests
exercise the egress gate; `fetch_for_curiosity` calls the subject gate; the
subject gate detects a refused subject kind; current pseudocode raises
immediately; no audit row exists; swallowed exceptions lose evidence; #58b must
prove diagnostic-before-raise.

**Council-axis composition flag:** Y -- Kant F1 + Buber B-3 + Ohm O4.

## Finding 6 -- Define The Fetch Wrapper URL Contract

**Severity:** Major
**Axis:** 2 -- Three-layer third-party gate
**Surface:** §13.3, §13.5; `core/egress/external_fetch.py:394-407`

**Issue:** The wrapper can preserve `external_fetch.fetch_text(...)`, whose
signature has `fetch_type`, `url`, and `caller`. But §13.5 calls
`query.public_safe_url()` while `ProvenancedQuery` declares `query_text`,
`provider_hint`, and provenance fields, not a URL method or URL-construction
contract.

**Required engineering fold:** Either add a `public_safe_url()` method/field
contract to `ProvenancedQuery`, or have `fetch_for_curiosity` derive the URL
from `query_text` through a named provider helper. Keep `fetch_text` unchanged.

**8-step trace:** Required because this is the egress write/read path.

**Council-axis composition flag:** Y -- Ohm O2 engineering feasibility fold.

## Finding 7 -- Add A Single Creation Choke Point For Subject-Kind Enforcement

**Severity:** Major
**Axis:** 2 -- Three-layer third-party gate
**Surface:** §6.1.1, §6.2.2, §13.2.1; RED #46b/#46c

**Issue:** v4.1 states every producer assigns `subject_kind` or fails closed,
but it does not yet state that all producer outputs pass through one constructor
or registration wrapper that enforces the invariant.

**Required engineering fold:** Add a named creation API, or make
`register_encounter_producer(...)` wrap callbacks so all producer outputs pass
through one validator. RED #46b/#46c should iterate every registered
`EncounterSource` path.

**8-step trace:** Required because this is the durable-object write path for
third-party boundary enforcement.

**Council-axis composition flag:** Y -- Buber B-3 + Kant F1.

## Finding 8 -- Specify Production Exclusion For `MANUAL_TEST_PRODUCER`

**Severity:** Blocking
**Axis:** 3 -- ProducerRef authority scope
**Surface:** §6.1.1, §24, §25 item 4;
`core/evolution/subjective_duration.py:93-96`, `:584-639`

**Issue:** v4.1 says `MANUAL_TEST_PRODUCER` remains the canary/test
discriminator and production gates exclude it, but the sketched producer
registration API has no `producer_ref` or canary/production discriminator. At
HEAD, `record_salience_event(...)` validates enum membership, not production
eligibility.

**Required engineering fold:** Add an explicit production producer registration
gate, for example `register_encounter_producer(..., producer_ref: ProducerRef,
canary: bool = False)`, where production registration refuses
`ProducerRef.MANUAL_TEST_PRODUCER`. Add a RED proving the manual producer is
accepted only for canary/manual seam tests and cannot register as a production
encounter producer.

**8-step trace:** §25 requires exclusion; §24 repeats it; §6.1.1 is the only
concrete registration API; that API lacks `producer_ref`; HEAD only validates
enum membership; `MANUAL_TEST_PRODUCER` is currently the only enum entry; no
production eligibility check exists; therefore the promised exclusion is not
mechanical.

**Council-axis composition flag:** Y -- Descartes D-5 correction made real.

## Finding 9 -- Pin The #40a/#40b AST Predicates

**Severity:** Major
**Axis:** 3 / 6 -- ProducerRef authority scope; static-AST coverage
**Surface:** §14.3.5, §23.7, §24; RED #40a/#40b

**Issue:** The authority bound is right, but the AST tests are generic. Calls
could evade the scan through constants, wrappers, `**kwargs`, or helper
functions.

**Required engineering fold:** Specify the predicates. For #40a, every drive
root call to `record_salience_event` using
`ProducerRef.DRIVE_DRIVEN_CURIOSITY` must include literal
`salience_event_kind="meaningful_exchange"` in the same call or in the single
approved ceremony wrapper. For #40b, every `Temperament.record_event` call with
`source="drive_driven_curiosity_resolution"` must include literal
`parameter="curiosity"`. Ban `**kwargs` at raw authority-bearing calls unless
routed through the audited wrapper. Keep runtime refusal tests as load-bearing.

**8-step trace:** Required because this guards the producer authority boundary.

**Council-axis composition flag:** Y -- Locke L-1.

## Finding 10 -- Add Canonical RED Rows For #46b/#46c

**Severity:** Blocking
**Axis:** 4 -- RED-test feasibility
**Surface:** §6.2.2, §13.2, §13.4, §23 canonical RED table

**Issue:** v4.1 references #46b/#46c as load-bearing creation-layer
third-party refusal tests, but §23 omits canonical rows for them. The
three-layer gate is covered at construction/egress but not at durable-object
creation.

**Required engineering fold:** Add canonical §23 rows:
`test_encounter_producers.py::test_subject_kind_omission_refused_at_creation`
and
`test_encounter_producers.py::test_named_third_party_without_matching_owner_explicit_consent_refused_at_creation`,
or retag them onto existing row numbers with exact names. Update the total test
count.

**8-step trace:** `CuriosityObject`, producer registry, `SubjectKind`, and
`ThirdPartyConsent` are dependencies; encounter producers write sidecar
metadata; projection/query/egress read the classification; tests must assert
refusal before persistence; the current table lacks the test path; inline refs
and §23 must agree before TDD starts.

**Council-axis composition flag:** Y -- Kant/Buber/Ohm third-party boundary.

## Finding 11 -- Make RED #58b Non-Vacuous

**Severity:** Major
**Axis:** 4 / 6 -- RED-test feasibility; static-AST coverage
**Surface:** §15.0; RED #58b

**Issue:** #58b can pass vacuously if no raise sites are found or if a new
raise site is missed by fixtures.

**Required engineering fold:** Amend #58b to require a non-empty discovered
raise-site set and name initial surfaces: `snapshot_temperament_for_bond`,
`third_party_subject_gate`, `fetch_for_curiosity`, and
`CuriosityObject`/producer creation refusal. Use static inventory plus dynamic
fixtures, or dynamic fixtures with an explicit discovered-surface assertion.

**8-step trace:** Required because this is the boundary-audit invariant.

**Council-axis composition flag:** Y -- Ohm O4.

## Finding 12 -- Settle Q2: Use `core/evolution/drive_driven_curiosity.py`

**Severity:** Major
**Axis:** 5 -- Open §22 engineering decisions
**Surface:** §22 Q2, §24, §24.1; `core/evolution/wonderings.py:155`,
`:272`, `:607`

**Issue:** The spec still leaves the adapter location open. `wonderings.py` is
the canonical open-question store; producer registration, eligibility,
temperament-write ceremony, subjective-duration seam calls, and diagnostics are
not storage responsibilities.

**Required engineering fold:** Decide Q2 in the spec:
`core/evolution/drive_driven_curiosity.py` is the drive adapter/producer module.
`core/evolution/wonderings.py` receives only additive migrations and minimal
sidecar read/write helpers. Remove the "or focused additions near
`wonderings.py`" parenthetical from §24. Add that future felt-organs inherit the
producer-registration/ceremony pattern from the adapter, not from the
`Wonderings` storage class.

**8-step trace:** Required because this determines module ownership and static
scan roots.

**Council-axis composition flag:** N -- Codex scope-realism decision.

## Finding 13 -- Settle Q4: Phase EncounterSources

**Severity:** Major
**Axis:** 5 -- Open §22 engineering decisions
**Surface:** §6.2, §22 Q4, RED #9

**Issue:** v4.1 names seven v1 sources, but four lack mature durable event IDs
or bond footing.

**Required engineering fold:** Replace "v1 producer list" with
"EncounterSource closed vocabulary" split into v1 wired and v1.1 deferred.
Land in v1: `WONDERING_GENERATED`, `EXPLICIT_OWNER_FLAG` only as an explicitly
flagged `Wonderings.add(..., source="explicit_owner_flag", bond_id=...)` path,
and recursion-gated `SUBJECTIVE_DURATION_MEANINGFUL_EVENT`. Defer to v1.1:
`COGNITION_QUALITY_UNCERTAINTY`, `UNRESOLVED_TOOL_LOOP_BRANCH`,
`PRIVATE_THOUGHT_LANDED`, and
`CONVERSATION_DECLARED_UNKNOWN_VIA_COGNITION_QUALITY`. Update RED #9 to assert
the three wired sources and `ProducerSourceDeferred` with explicit reason
strings for the four deferred sources.

**8-step trace:** Required because source phasing controls write paths.

**Council-axis composition flag:** N -- Codex scope-realism decision.

## Finding 14 -- Settle Q5: Defer Semantic Match Entirely

**Severity:** Major
**Axis:** 5 -- Open §22 engineering decisions
**Surface:** §14.1, §14.2, §14.5.2; RED #37

**Issue:** v4.1 says semantic markers are behind a default-off feature flag,
but no flag name, helper, flag-off identity test, no-production-path invariant,
or static prevention rule is specified.

**Required engineering fold:** Remove the semantic-match feature flag from this
slice. v1 `ResolutionMarkerType` should contain only
`EXPLICIT_OWNER_RESOLVED` and `EXPLICIT_SELF_RESOLVED`. §14.2 should say
semantic-match resolution is deferred to its own slice; no feature flag ships
in Slice 2 v1. Remove `NOT_ELIGIBLE_LOW_CONFIDENCE` from v1 tests or mark it
future-only.

**8-step trace:** Required because a vague flag creates hidden production
paths.

**Council-axis composition flag:** N -- Codex scope-realism decision.

## Finding 15 -- Declare Static Scan Roots For World-Acting Tests

**Severity:** Major
**Axis:** 6 -- Static-AST coverage
**Surface:** §8.4, §23 RED #10/#11, §24;
`daemon/wondering_cycle.py:25-27`, `:310`, `:355-356`

**Issue:** Existing `daemon/wondering_cycle.py` imports and calls `tool_loop`.
A broad scan over reused wondering substrate would fail before Slice 2 exists.

**Required engineering fold:** Declare explicit scan roots for #10/#11:
`core/evolution/drive_driven_curiosity.py`, new `core/policies/*.py`, and any
new drive-only adapter modules. Treat `daemon/wondering_cycle.py` as reused
substrate unless Slice 2 edits it with new drive dispatch. Fail imports/calls
to action-engine/tool-loop symbols inside drive roots.

**8-step trace:** v4.1 reuses the existing wondering cycle; the new write path
is the drive adapter; the old read path may remain; RED #10 scans drive roots;
synthetic bad drive modules prove failure; import smoke verifies real roots.

**Council-axis composition flag:** Y -- Locke L-2/L-3.

## Finding 16 -- Correct RED #11's Capability Surface

**Severity:** Major
**Axis:** 6 -- Static-AST coverage
**Surface:** §8.5.1, RED #11;
`core/governance/operator_user_boundary.py:76-85`, `:99-109`;
`core/infra/capability_acquisition_queue.py:275`;
`core/actions/action_engine.py:1145-1161`

**Issue:** The guarded-work invariant is true, but the spec phrase
`core/actions/action_engine.handle_capability_acquire` does not match the live
shape. The handler lives in `core/infra/capability_acquisition_queue.py`;
`action_engine` imports it as a queue handoff.

**Required engineering fold:** Reword #11 to forbid drive-layer imports/calls
of action-engine modules and any `handle_capability_*` symbol except through
the approved proposal/card queue surface. Pair static scan with a runtime test
that bypass attempts reach refusal/queue-only behavior.

**8-step trace:** Required because this protects the D19/D20 capability
boundary.

**Council-axis composition flag:** Y -- Locke L-2.

## Finding 17 -- Make #33d Alias-Aware

**Severity:** Minor
**Axis:** 6 -- Static-AST coverage
**Surface:** §13.5; RED #33d; `core/egress/external_fetch.py:394-407`

**Issue:** "Never import `fetch_text` directly" misses alias patterns such as
`from core.egress import external_fetch` followed by
`external_fetch.fetch_text(...)`.

**Required engineering fold:** #33d should fail on direct `fetch_text` imports,
`external_fetch` imports inside drive roots, and calls resolving to `fetch_text`
or `<alias>.fetch_text`. Exempt `core/egress/fetch_for_curiosity.py`, which is
the wrapper that must delegate.

**8-step trace:** Not applicable; static-test precision note.

**Council-axis composition flag:** Y -- Kant/Ohm egress boundary.

## Finding 18 -- Add A Consumer Allowlist For #43

**Severity:** Minor
**Axis:** 6 -- Static-AST coverage
**Surface:** §15.4, §15.6; RED #43;
`core/evolution/subjective_duration.py:855-879`

**Issue:** The subjective-duration deferral is mechanically correct, but #43
needs an explicit allowlist to avoid future ambiguity.

**Required engineering fold:** Define v1 allowed consumers of
`compute_saturation` as exactly `dream_state`, `wonderings`,
`private_thoughts`, the defining saturation module, and tests. Fail imports or
calls outside that allowlist, and confirm no reference from
`core/evolution/subjective_duration.py`.

**8-step trace:** Not applicable; static-test precision note.

**Council-axis composition flag:** Y -- Descartes/Hume A5.

## Finding 19 -- Enumerate RED #50 Template Scope

**Severity:** Major
**Axis:** 6 -- Static-AST coverage
**Surface:** §14.7, §16.1; RED #50/#50b

**Issue:** "daemon/maez_daemon.py prompt-template files only" is not
mechanically defined when the named surfaces are Python files. A full literal
scan of huge production modules risks false positives; a vague scan risks
missing the intended templates.

**Required engineering fold:** Enumerate exact files, constants, or functions
to scan for RED #50. Use `ast.Constant(str)` and joined-string extraction for
Python sources plus text scan for explicit template files. Keep #50b as the
runtime rendered-text gate; #50 should not claim runtime composition coverage.

**8-step trace:** Source/template literals and runtime outbound gate are
dependencies; prompt text is the write path; owner outbound text is the read
path; #50 scans literals, #50b scans rendered output; forbidden literals in
named templates fail; rendered forbidden phrases are rephrased/refused by class.

**Council-axis composition flag:** Y -- Hume F3 + Descartes D-6.

## Finding 20 -- Implement #58a As AST, Not Grep

**Severity:** Minor
**Axis:** 6 -- Static-AST coverage
**Surface:** §15.0; RED #58a

**Issue:** The invariant is feasible, but grep misses aliases such as
`except BI:` after importing `BondIsolationViolation as BI`.

**Required engineering fold:** Implement #58a as AST over `core/` and
`daemon/`, excluding tests. Build an import-alias map for
`BondIsolationViolation` and `CrossBondAccessError`; fail any `ExceptHandler`
catching those names, attributes, or tuples containing them.

**8-step trace:** Not applicable; static-test precision note.

**Council-axis composition flag:** Y -- Ohm O4.

## Finding 21 -- Clarify Planned ProducerRef Extension In Early Prose

**Severity:** Minor
**Axis:** 7 -- Live code/schema/API truth
**Surface:** §2.2, §14.4, §24; `core/evolution/subjective_duration.py:93-96`

**Issue:** Later v4.1 correctly says Slice 2 adds
`ProducerRef.DRIVE_DRIVEN_CURIOSITY`, but early sample code can read as if the
enum value already exists at HEAD. Current live enum has only
`MANUAL_TEST_PRODUCER`.

**Required engineering fold:** Add "after this slice extends `ProducerRef`" to
the early seam-consumption prose and examples.

**8-step trace:** Not applicable; wording-to-surface precision note.

**Council-axis composition flag:** N.

## Verified Accurate Surfaces

- `wonderings.py` currently lacks `bond_id`, `resolved_at`, and the drive
  sidecar; v4.1 correctly treats them as additive changes.
- `Temperament.ALLOWED_SOURCES` currently contains only `explicit_set`, and
  `record_event(...)` writes absolute values, not deltas; v4.1 matches this.
- `SubjectiveDuration.record_salience_event(...)` has producer-snapshot kwargs,
  refuses `_LEGACY` producer writes, and refuses explicit score injection on
  producer-snapshot path; v4.1 inherits the Slice 1 anti-laundering gates.
- `external_fetch.fetch_text(...)` has `caller` but no `bond_id` or
  `ProvenancedQuery`; a wrapper is the correct shape.
- `identity.user_profile_id()` exists and is the v1 bond source of truth.
- The watchdog allows the temperament parameter set, so `curiosity` can be
  governed by existing parameter allowlist discipline.
- `wondering_pursuit` has the vulnerable-register hard block v4.1 cites.
- `capability.acquire` routes to the capability-acquisition queue; it does not
  directly install or fetch code.
- `capability_acquisition` is a guarded work class with strength 2.
- Python `ast` is sufficient for the named static scans if roots and predicates
  are pinned; no specialized analyzer is required.

## Panel Bottom Line

v4.1 is structurally sound but not implementation-ready. The panel does not
ask for architecture reshape: producer-over-wonderings holds, Slice 1 stays
out of scope, and the council's covenant findings remain load-bearing. The
next move is a small v4.2 refold that turns these surface-truth gaps into exact
spec language and canonical RED rows. After that, a narrow Codex pass-2 should
verify only the amended surfaces, not re-litigate the whole slice.

Plain language: the blueprint is the right building, but several doorways are
still drawn as intentions instead of hinges. Fold those hinges into the spec
before TDD starts, and the implementation path should be much cleaner.
