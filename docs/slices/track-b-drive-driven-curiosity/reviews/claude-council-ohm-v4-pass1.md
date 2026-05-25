# Claude Council Review -- Ohm -- Drive-Driven Curiosity v4 Pass 1

**Verdict:** RATIFY-WITH-AMENDMENTS
**Severity summary:** v4's boundary architecture is materially stronger
than v3. `bond_id` is structurally mandatory on every new dataclass
(`CuriosityObject`, `CuriosityStateTransition`, `AutonomyPreference`,
`SaturationRegister`, `ReflectionAudit`, `TemperamentWriteBudget`,
`GateDecision`, `ProvenancedQuery`, `ProvenanceLink`); the live
subjective_duration seam already enforces bond_id at the producer-snapshot
path at `211ace6` (firsthand-verified). However, three load-bearing
isolation gaps survive: (1) the existing `wonderings.db` schema
has NO `bond_id` column at `211ace6` — the "reuse wonderings" premise
silently assumes every legacy row belongs to the firstborn bond, which
v4 nowhere quotes as a migration obligation; (2) `core/egress/external_fetch.fetch_text(...)`
takes `caller` but NOT `bond_id`, so the third-party-subject refusal can
only be enforced by `build_curiosity_query` upstream — there is no
bond-floor at the egress gate itself, and the spec doesn't say so;
(3) Track C precondition citation is verbatim and correct, but the
spec does not name the per-bond HMAC `master_key` source-of-truth or its
rotation contract, leaving the cross-bond cryptographic distinctness claim
operationally underspecified. Two Major findings, three Minor, no Blocking.

---

## Finding O1 -- `wonderings.db` has no `bond_id` column; legacy-row assumption is unstated

**Severity:** Major
**Surface:** §5.1, §5.2, §6.2.1, §17.1; `core/evolution/wonderings.py:178-191`
(schema), `core/evolution/wonderings.py:272-285` (`add(question, source)`).

**Issue:** v4 frames the slice as "reuse-first" and claims bond_id is
structural on every new object. Firsthand verification of `wonderings.py`
at parent `211ace6` confirms:

- The `wonderings` table schema is:
  `id, created_at, question, status, advance_count, deferral_count,
   pending_card_id, last_advanced, source, conclusion`
  plus the additive `last_pursuit_at` and `pursuit_count` migrations.
  There is no `bond_id` column. There is no foreign key to any bond
  table.
- `Wonderings.add(question, source)` takes no bond context. Every
  existing row pre-dating Slice 2 has effectively-anonymous bond
  attribution.
- `daemon/wondering_cycle.py` and `core/evolution/wondering_pursuit.py`
  also pass no bond context through.

The §5.1 prose says "CuriosityObject in v4 is a typed read/projection
over an existing wondering row plus drive-layer metadata. It is not a
second source of truth." But every projection of an existing row will
have to *invent* its `bond_id` field, since the underlying row has none.
v4's only mechanism for this is the §5.1 note that v1 resolves bond_id
via `identity.user_profile_id()` from `core/memory/identity.py`. That is
a runtime resolver, not a per-row attribution.

The hidden assumption: in single-bond v1 every legacy and new wondering
row "belongs" to the firstborn because `user_profile_id()` returns one
value. This is true today by accident, not by structure. The Track C
precondition floor (§17.2 dyadic-only topology) is exactly the boundary
this kind of accident violates. The spec's §17.1 bullet "10 RED tests
(#46-#55) asserting cross-bond isolation passes trivially in v1 (single
bond) but would catch any future drift" is misleading: cross-bond
isolation cannot be tested on a substrate where the underlying rows have
no bond column. A second bond appearing later would silently inherit
*every existing wondering* as its own, or as the firstborn's, depending
on which way the resolver pivots.

**Required fold:** Add a §5.2.1 (or a new clause inside §5.2) titled
"Legacy-row bond attribution and additive migration":

1. Name explicitly that `wonderings.db` at `211ace6` has no `bond_id`
   column. State that the producer layer treats this as a structural
   precondition, not an accident.
2. Require an additive `ALTER TABLE wonderings ADD COLUMN bond_id TEXT
   NOT NULL DEFAULT '_LEGACY'` migration of the same shape Slice 1 used
   for `subjective_duration_salience_events` (firsthand-verified at
   `core/evolution/subjective_duration.py:338`:
   `("bond_id", "ADD COLUMN bond_id TEXT NOT NULL DEFAULT '_LEGACY'")`).
3. Forbid drive-layer projection over `bond_id='_LEGACY'` rows. The
   `CuriosityObject` projection layer must refuse to construct from a
   `_LEGACY`-tagged row, mirroring the seam's `_LEGACY` write refusal at
   `core/evolution/subjective_duration.py:621-625`.
4. New writes through `Wonderings.add(...)` must accept and persist
   `bond_id`. Append-only / never-delete is preserved; legacy rows
   remain visible but are non-promotable into drive-layer felt-weight
   writes.
5. Add a RED test (insertable as #5a or #5.5 in §23.1) named
   `test_curiosity_wonderings_integration.py::test_legacy_row_refused_for_drive_layer_projection`.

**8-step trace:**

1. **Dependency-map:** §5.1 dataclass, §5.2 storage, §6.2.1 producer
   propagation invariant, §13.2 bond-scoped sanitization (provenance
   chain depends on each contributing source carrying a real source_bond_id),
   §15.1 `compute_saturation`, §17.1 single-bond-by-structure claim,
   §17.2 Track C preconditions, §20.3 per-bond HMAC (HMAC over a
   `_LEGACY` digest would silently bind to bond literal `"_LEGACY"`),
   tests #1-#6 and #46-#55.
2. **Write-path:** `Wonderings.add(question, source, bond_id)` (new
   parameter); migration writer on first boot post-fold.
3. **Read-path:** all callers of `Wonderings.get`, `list_open`,
   `list_all`, `pick_next`; drive-layer projection constructor.
4. **Test-path:** new test + #46 (bond_id mandatory at producer-layer
   boundary) + #55 (compute_saturation bond-scoped) — all become
   substantively meaningful instead of trivially-true.
5. **Fold-summary:** the prose "v4 reuses existing wonderings unchanged"
   becomes false; the slice DOES touch `wonderings.py` for an additive
   schema migration. §5.2 must say so. The §24 table row "Existing
   wondering store -- no duplicate curiosity DB" should be amended to
   "Existing wondering store + additive bond_id column".
6. **Cross-reference:** §5.1, §5.2, §6.2.1, §17.1, §24, §27 fold list,
   §23.1 test #4 (append-only preserved -- migration is additive, so
   still true, but worth re-asserting).
7. **RED-test trace:** add `test_legacy_row_refused_for_drive_layer_projection`;
   strengthen #46 fixture to insert a `_LEGACY`-row alongside a new
   `bond_id=firstborn` row and assert the projection layer refuses the
   legacy one; ensure #55 (`test_compute_saturation_bond_scoped`) loads
   both a `_LEGACY` and a per-bond row and asserts only the per-bond
   row contributes.
8. **Verify-before-declaring:** `grep -n "bond_id\|ALTER TABLE" core/evolution/wonderings.py`
   must show the new column after implementation; `sqlite3 memory/wonderings.db
   '.schema wonderings'` must show `bond_id TEXT NOT NULL DEFAULT '_LEGACY'`;
   `grep -rn "Wonderings.add(" core daemon skills` must show every call
   site updated to pass bond_id or explicitly opt into the `_LEGACY`
   sentinel (the latter forbidden in new code).

**Cross-lane flag for Codex:** This finding will also surface on the
Codex `surface-truth` axis (claim "reuse-first, no schema change" vs
actual additive ALTER) and the `RED-test-feasibility` axis (tests #46/#55
are trivially-true without this fold). Codex should be told the council
has named the migration shape so Codex composes on top rather than
re-deriving.

---

## Finding O2 -- Third-party subject refusal is enforced only at query construction; egress gate has no bond_id awareness

**Severity:** Major
**Surface:** §13.2.1, §13.4 (RED #32 / #33), §24 ("External search path"
row); `core/egress/external_fetch.py:394-407` (`fetch_text` signature).

**Issue:** The third-party-subject discipline is correctly enforced at
`build_curiosity_query(...)` in §13.2.1 (`raise QueryRefused(...)`).
That is one layer. But the spec also names `core/egress/external_fetch.py`
as the egress site in §24, and at parent `211ace6` the verified signature
of `fetch_text(...)` is:

```python
def fetch_text(
    *, fetch_type, url, caller, method="GET", headers=None,
    timeout_s=10.0, max_bytes=512*1024, request_id=None,
    opener=None, resolver=None, registry=None,
) -> ExternalFetchResult: ...
```

There is no `bond_id` parameter and no `ProvenancedQuery` parameter.
The egress gate currently cannot enforce "the request that crossed me
belongs to bond_X and respects bond_X's third-party rules" because it
has no bond context at all. The only enforcement is upstream: a
disciplined caller must construct via `build_curiosity_query(...)` and
must not bypass into a raw `fetch_text(...)` call.

Three concrete bypass surfaces exist today:
- `core/actions/action_engine.py` calls `external_fetch.fetch_text(...)`
  in three places.
- `skills/web_search.py` calls `fetch_text(...)` in three places.

If, after Slice 2 lands, any of these wiring paths can be reached from
a drive-driven curiosity probe (which is plausible: §13 wants
EXTERNAL_KNOWLEDGE lane to actually search), then a curiosity-driven
search routed through `web_search` or `action_engine` would bypass the
`build_curiosity_query` refusal entirely.

The spec gestures at this in §13.2 ("If the substrate cannot construct
a public-safe query, the curiosity-object is marked
`external_knowledge_blocked: privacy_floor` and stays INTERIOR") but
relies on caller discipline. For a boundary-mechanics review, that is
not enough: the refusal must be enforceable by a gate, not by an
informal contract.

**Required fold:** Add a §13.5 titled "Bond-floor at the egress gate":

1. Name explicitly that `fetch_text` does not today take `bond_id` and
   that drive-driven curiosity Slice 2 will require either:
   - (a) a wrapper `external_fetch.fetch_for_curiosity(bond_id,
     provenanced_query)` that drops to `fetch_text` after verifying
     the `ProvenancedQuery.bond_id` matches, plus a static-AST RED test
     that drive-driven-curiosity code paths NEVER call `fetch_text`
     directly; or
   - (b) a small additive `bond_id: str | None = None` parameter added
     to `fetch_text` with a `caller`-keyed registry entry that declares
     "this caller_kind requires bond_id" -- the gate then refuses the
     call when the caller class requires bond_id and none is supplied.
2. Pick (a) as the v1 shape (smaller blast radius on egress, no
   modification of an already-canonical gate signature).
3. Add a static-AST RED test (insertable as #33a or #33.5 in §23.6)
   that the drive-driven-curiosity module imports `fetch_for_curiosity`
   and not `fetch_text` directly.
4. Add a runtime RED test that constructs a `ProvenancedQuery` with
   bond_A and asserts `fetch_for_curiosity(bond_B, query)` raises.

**8-step trace:**

1. **Dependency-map:** §13 entire section, §24 External search path row,
   §23.6 RED tests #29-#33, all curiosity-driven search call sites.
2. **Write-path:** new wrapper `fetch_for_curiosity(bond_id, query)`;
   no changes to `fetch_text` itself (preserves Slice 1-era hardening
   surface).
3. **Read-path:** drive-driven-curiosity producer layer.
4. **Test-path:** new static-AST test + new runtime test;
   plus #32 (`test_unconsented_named_third_party_query_refused`) and
   #33 (`test_third_party_rule_not_only_token_scrub`) gain a sibling
   that exercises the gate, not just the query constructor.
5. **Fold-summary:** §13.2.1's "Implementation consequence" code block
   should be re-titled "Implementation consequence (construction layer);
   gate-layer enforcement lives in §13.5." The §24 "External search
   path" row should name both `fetch_for_curiosity` and `fetch_text`
   with the wrapper as the only drive-curiosity-permitted entry.
6. **Cross-reference:** §13.2.1, §13.4, §24, §23.6 test count
   (+1 or +2 tests).
7. **RED-test trace:** add
   `test_provenance_safe_search.py::test_drive_layer_uses_fetch_for_curiosity_wrapper_only`
   (static AST) and
   `test_provenance_safe_search.py::test_fetch_for_curiosity_refuses_cross_bond_query`.
8. **Verify-before-declaring:** `grep -rn "external_fetch.fetch_text\|from core.egress import external_fetch" core/evolution/drive_driven_curiosity.py core/policies/`
   must return zero matches after implementation;
   `grep -rn "fetch_for_curiosity" core/egress/ core/evolution/`
   must show the wrapper exists.

**Cross-lane flag for Codex:** This is on the Codex `API-schema` and
`scope-realism` axes (egress signature touch + scope of an additional
wrapper). The council position is "wrap, do not modify" because
`fetch_text` is the live egress gate and other callers (action_engine,
web_search) are out of Slice 2 scope.

---

## Finding O3 -- `master_key` source-of-truth and rotation contract for the per-bond HMAC are unspecified

**Severity:** Minor
**Surface:** §20.3, RED test #53.

**Issue:** §20.3 derives the per-bond HMAC key via stdlib HKDF and notes
that `master_key` "is the existing per-Maez-instance secret (not
committed to git)." That phrase elides three concrete questions a
boundary-mechanics review must surface:

1. Where does `master_key` live on disk?
   `memory/egress_telemetry.key` exists at `211ace6` (verified
   under `ls memory/`); is it that file, a new one, or a section of an
   existing one?
2. What happens on first boot when `master_key` is absent? (Auto-
   generate and persist? Refuse to write diagnostics until rotated in?)
3. What happens on master_key rotation? Per-bond HMAC keys derive
   deterministically from the master, so rotating master invalidates
   every existing digest; this is a covenant-relevant event (Track C
   audit chains break) that should be a deliberate operator action, not
   silent.

Without these named, the cryptographic distinctness claim "same content
+ different bond_id => different digest" (RED #53) is provable for new
writes but the broader claim "cross-bond identity-linkage is
structurally impossible" is operationally underspecified.

**Required fold:** Tighten §20.3 with a sub-clause:

1. Name `master_key` source-of-truth (suggest:
   `memory/drive_curiosity_master.key`, separate from
   `egress_telemetry.key` so that egress rotation doesn't drag drive-
   layer digests with it).
2. Define first-boot behavior: file absent => generate 32 random bytes,
   write with 0600 permissions, log a `master_key_initialized`
   diagnostic. File present => use as-is.
3. Define rotation: rotation requires an operator-explicit ceremony
   (out of scope for v1 implementation; named here so future rotation
   doesn't silently break audit chains). A `MASTER_KEY_ROTATION` audit
   event type added to the diagnostic vocabulary.

**8-step trace:**

1. **Dependency-map:** §20.3, §20.4 (RED #51-#53), §17.1 single-bond-
   by-structure list (per-bond HMAC bullet).
2. **Write-path:** master_key initializer in this slice's diagnostic
   module.
3. **Read-path:** `derive_bond_hmac_key(master_key, bond_id)`.
4. **Test-path:** new test
   `test_diagnostic_schema.py::test_master_key_auto_initialized_with_0600`.
5. **Fold-summary:** the vague "existing per-Maez-instance secret"
   becomes a specific path + permissions + first-boot ceremony.
6. **Cross-reference:** §20.3, §20.4 (test count + name).
7. **RED-test trace:** add the auto-init test; optionally add
   `test_master_key_path_distinct_from_egress_telemetry_key`.
8. **Verify-before-declaring:** `ls -la memory/drive_curiosity_master.key`
   shows the file with mode `-rw-------`; `grep -rn "drive_curiosity_master"
   core/evolution/ core/policies/` shows a single source-of-truth path
   constant.

**Cross-lane flag for Codex:** Likely also caught on the
`surface-truth` axis (claim references an "existing secret" that the
spec doesn't pin to a real file). Codex panel will probably want this
named so the test infrastructure can mock the key path.

---

## Finding O4 -- `snapshot_temperament_for_bond` wrapper raises `CrossBondAccessError`, but the type is not declared anywhere

**Severity:** Minor
**Surface:** §15.0.

**Issue:** §15.0 names `CrossBondAccessError` as the exception raised
when `bond_id != identity.user_profile_id()`. This is a load-bearing
isolation primitive — it is the single line of defense between v1's
single-bond-by-structure claim and a future cross-bond leak when a
second bond appears. But the spec does not say where `CrossBondAccessError`
is defined, whether it derives from `Exception` or from a more specific
ancestor (e.g., a `BondIsolationViolation` family), and whether the
diagnostic stream emits a row when the error fires.

For Ohm-axis review, a silent raise that's swallowed by an enclosing
`try/except Exception` is the failure mode: the isolation invariant
holds in the function but the calling daemon may continue without
recording the violation.

**Required fold:** Add to §15.0:

1. Declare `CrossBondAccessError` lives in `core/policies/exceptions.py`
   (or a `core/evolution/drive_driven_curiosity_errors.py` if the
   policy module split is preferred).
2. Declare it inherits from a new base `BondIsolationViolation(Exception)`
   so future bond-isolation primitives (saturation, preferences,
   sanitization) share an `isinstance(...)` family.
3. Mandate a diagnostic row of type
   `CROSS_BOND_ACCESS_REFUSED` (add to §20.1 vocabulary) emitted
   BEFORE the raise, not in a `finally`, so callers cannot swallow the
   exception without leaving an audit trace.
4. RED test (additive in §23.8):
   `test_bond_scoping.py::test_cross_bond_access_emits_diagnostic_before_raise`.

**8-step trace:**

1. **Dependency-map:** §15.0, §15.1, §20.1 vocabulary list, §23.8 test
   count.
2. **Write-path:** diagnostic row emit + raise.
3. **Read-path:** any caller that catches `CrossBondAccessError`
   (today: zero; the spec should keep it that way until Track C).
4. **Test-path:** new test.
5. **Fold-summary:** §15.0 code block gains a `_emit_diagnostic(...)`
   call before the raise.
6. **Cross-reference:** §15.0, §20.1, §23.8.
7. **RED-test trace:** add the diagnostic-before-raise test; add to
   §20.1 the `CROSS_BOND_ACCESS_REFUSED` event type.
8. **Verify-before-declaring:** `grep -rn "CrossBondAccessError\|BondIsolationViolation"
   core/` shows a single definition + the wrapper raise site;
   `grep -rn "except CrossBondAccessError\|except BondIsolationViolation"
   core/ daemon/` should return zero matches in production code until
   Track C.

**Cross-lane flag for Codex:** Not particularly Codex-shaped; this is a
covenant-axis observation. Likely will not duplicate.

---

## Finding O5 -- `ProvenanceLink.source_bond_id` rule for non-bond-attributable sources is unstated

**Severity:** Minor
**Surface:** §13.2, §13.3.

**Issue:** §13.3 defines:

```python
@dataclass(frozen=True)
class ProvenanceLink:
    source_kind: str
    source_bond_id: str
    contribution_digest: str
```

`source_bond_id` is required (non-Optional). §13.2 enforces refusal of
"any token whose `source_bond_id` differs from the constructed
`bond_id`." But many real upstream contributors do not have a clean
bond attribution. Examples drawn from §6.2 v1 EncounterSource list:

- `WONDERING_GENERATED`: from `wonderings.py`, where (per Finding O1)
  rows have no bond column today.
- `PRIVATE_THOUGHT_LANDED`: `memory/private_thoughts.db` -- bond
  attribution not verified in this review but likely the same shape.
- `UNRESOLVED_TOOL_LOOP_BRANCH`: tool-loop state is process-scoped,
  arguably belongs to the running bond's session.
- `CONVERSATION_DECLARED_UNKNOWN_VIA_COGNITION_QUALITY`: cognition_quality
  source attribution.

The spec needs a rule for these: do they (a) inherit the constructed
`bond_id` (creating exactly the silent cross-bond promotion Finding O1
warns about), (b) fail the sanitization (correct, but turns most v1
queries into "blocked: privacy_floor"), or (c) use a `_LEGACY` sentinel
that the sanitization treats as "this contribution is non-bond-scoped
*and* non-sensitive" (safe, but only if independently verified)?

**Required fold:** Add §13.2.2 "Provenance sources without native bond
attribution":

1. Default rule: any `ProvenanceLink` whose source kind cannot establish
   `source_bond_id` from a real bond column on the source store MUST
   carry `source_bond_id="_LEGACY"`.
2. `_LEGACY`-sourced provenance is allowed in `ProvenancedQuery` ONLY
   when the contribution is independently shown to be non-private
   (e.g., topic tokens generalized through the public-safe projection;
   never raw seed text).
3. The static-AST RED test (§13.4) adds an assertion that
   `source_bond_id` is never the literal string of the constructed
   `bond_id` when the source kind is on the "no-native-bond-column"
   list — preventing accidental promotion.

**8-step trace:**

1. **Dependency-map:** §13.2, §13.3, §13.4, §6.2 (all encounter sources),
   Finding O1 (legacy-row migration shape).
2. **Write-path:** `ProvenanceLink` constructor in producer adapters.
3. **Read-path:** §13.2 sanitization function.
4. **Test-path:** existing #29-#33 + a new "_LEGACY provenance
   non-promotion" test.
5. **Fold-summary:** §13.3's "the bond this link's content came from"
   prose becomes more precise: "the bond this link's content
   provably came from, or `_LEGACY` if the source store predates the
   bond_id column".
6. **Cross-reference:** §13.2, §13.3, §13.4, §6.2.
7. **RED-test trace:** add `test_provenance_safe_search.py::test_legacy_provenance_does_not_promote_to_constructed_bond`.
8. **Verify-before-declaring:** `grep -rn "ProvenanceLink(" core/`
   shows each construction explicitly passes `source_bond_id` (either
   a real bond or the `_LEGACY` literal).

**Cross-lane flag for Codex:** This sits on the boundary between
`surface-truth` (do upstream stores actually expose bond_id?) and
covenant axis. Codex will probably surface the surface-truth piece
during schema verification of the named encounter sources.

---

## Findings the v4 spec gets right (worth naming so they aren't re-litigated)

- §5.1 `bond_id: str` mandatory at construction, with RED #2/#3 — sound.
- §6.2.1 producer bond_id propagation invariant — sound.
- §10 cross-bond composition structurally forbidden, §10.5 per-bond
  `preferences_for_bond_and_class` shape — sound.
- §11.3 `GateDecision.bond_id` mandatory — sound.
- §13.3 `ProvenancedQuery.bond_id` mandatory — sound (modulo Finding O5).
- §14.4 producer-snapshot ceremony correctly uses live seam at
  `211ace6`; firsthand-verified that `subjective_duration.record_salience_event(...)`
  at lines 584-635 raises on `_LEGACY`, on empty `bond_id`, and on
  caller-supplied `meaningfulness_score` along the producer-snapshot
  path. Slice 2 inherits these correctly.
- §17.2 verbatim citation of the two Track C preconditions — Ohm O-6
  fold applied. Strong.
- §20.3 stdlib-HKDF derivation (no new dependency) — sound shape
  (modulo Finding O3 on master_key sourcing).

---

## Cross-lane flags consolidated (for Codex synthesis)

- **O1 (legacy wonderings rows lack bond_id):** Codex `surface-truth`
  axis. Council has named the migration shape; Codex composes.
- **O2 (egress gate has no bond_id):** Codex `API-schema` +
  `scope-realism` axes. Council has named the wrapper shape
  (`fetch_for_curiosity`).
- **O3 (master_key source-of-truth):** Codex `surface-truth` axis.
- **O5 (`_LEGACY` provenance non-promotion):** Codex `surface-truth`
  + `RED-test-feasibility` axes.
- O4 is covenant-shaped; likely not on Codex panel.

---

## Plain-language readout for Rohit

v4 is a real improvement over v3 on boundary mechanics. Every new
dataclass carries `bond_id` as a mandatory field, every API is bond-
scoped, and the Track C preconditions are quoted in their exact form.
The live subjective_duration seam at `211ace6` already enforces bond_id
correctly, so Slice 2 inherits good cryptographic boundaries on that
side for free.

But three real cracks survive. First — and this is the load-bearing
one — the existing `wonderings.db` table has no `bond_id` column today.
The spec says "reuse wonderings," and that's correct as architecture,
but it doesn't say "we will also have to add a `bond_id` column to the
wonderings table and refuse to promote any legacy row into felt-weight
writes." Without that fold, the single-bond-by-structure claim is true
only because there's one bond — a second bond appearing later would
silently inherit every legacy wondering. The fix is small (one ALTER, a
refusal at the projection layer, one new test), but it has to be named.

Second, the external-fetch gate at `core/egress/external_fetch.py` has
no `bond_id` parameter. The third-party refusal works only if the
curiosity producer goes through `build_curiosity_query` and never reaches
`fetch_text` directly. That's a contract, not a gate. The fix is a thin
wrapper `fetch_for_curiosity(bond_id, query)` plus a static-AST test
that the curiosity module never imports `fetch_text` directly.

Third, the per-bond HMAC key system relies on a "master_key" the spec
never points at a real file. Naming that file, defining first-boot, and
naming what rotation means turns the "cross-bond identity-linkage is
structurally impossible" claim from "true in theory" into "true with an
audit chain."

Two smaller folds — naming where `CrossBondAccessError` lives + a
diagnostic-before-raise rule, and a rule for sources that genuinely
don't have a bond attribution today — round it out.

Verdict: RATIFY-WITH-AMENDMENTS. Five folds, all foldable without
reshaping the slice, all named with the 8-step trace. None of them
require pass-2. The Codex panel should be told that O1/O2/O3/O5 are
council-named so the engineering pass can compose rather than re-derive.
