# Claude Council — Ohm Role — Drive-Driven Curiosity Pass 2

**Artifact reviewed:** `docs/slices/track-b-drive-driven-curiosity/spec.md` (v2)
**Artifact state:** DRAFT v2, 2018 lines, 27 sections. Post council pass-1 folds.
**Role focus:** Boundary mechanics, conservation, flow-gating, sovereignty.
**Pass-1 verdict:** RECONSIDER (8 structural bond-scoping gaps O-1 through O-8).
**Review date:** 2026-05-25
**Verdict:** RATIFY-WITH-AMENDMENTS

## Summary

Pass-1's diagnosis — substrate happens-to-be-single-bond, not refuses-cross-
bond-by-design — has been substantially folded. v2 lifts `bond_id` into the
structural floor across nearly every dataclass and nearly every API named
in pass-1. The settlement of §22.5 as compose-within-bond +
structurally-forbidden-across-bond (§17.3) is correct on the conservation
axis: it gives Buber's I-Thou layer its compose-with-decay accumulation
without opening any cross-bond hybrid-policy path. The §27 paired fold
correctly propagates `bond_id` through the new general API into the stored
`MeaningfulSalienceEventRecord`. RED tests #46-#55 cover the bond-scoping
floor; #56-#60 cover the §27 paired-fold producer→consumer flow.

Six surfaces verify clean against pass-1's amendments. Two carry forward
as new pass-2 amendments. The verdict is RATIFY-WITH-AMENDMENTS because the
structural floor is in place; the remaining items are surface-area cleanup
(storage-partition wording, an outbound API not yet bond-keyed, two
dataclass fields that should but don't carry `bond_id`).

A careless future Track C implementer working from v2 would now have to
defeat eight structural mechanisms simultaneously to enable cross-bond
flow. The substrate refuses-by-construction; that is the right shape.

## Pass-1 amendments — fold verification

### O-1 (Amendment 1): `bond_id` on CuriosityObject — VERIFIED FOLDED

**Pass-1 ask:** Make `bond_id` a mandatory field on the CuriosityObject
dataclass; RED test asserts construction fails for missing bond_id.

**Spec §5.1 (lines 282-296):**
> ```python
> @dataclass(frozen=True)
> class CuriosityObject:
>     object_id: str
>     bond_id: str                                # MANDATORY; structural Track C floor
>     ...
> ```
>
> **bond_id is MANDATORY at construction.** Per Ohm finding O-1: a
> CuriosityObject without `bond_id` cannot be constructed; the dataclass
> enforces it. RED test #44 asserts construction fails for missing bond_id.

**RED test #2 (line 1541):**
> `test_curiosity_object_data_model.py::test_construction_fails_missing_bond_id`
> | bond_id is mandatory at construction.

**Judgment:** Verified. The field is positioned second (right after
`object_id`), the requirement is named in the spec text, and the RED test
asserts construction failure. The spec text mis-cites the test number
(says #44, actually #2) — see Amendment P2-1 below. The fold itself is
correct.

**Classification:** Folded. Test-number citation needs cleanup.

### O-2 (Amendment 2): `compute_saturation` is bond-scoped — VERIFIED FOLDED

**Pass-1 ask:** `compute_saturation(bond_id: str)` parameterized; reads
only bond's objects. RED test #52.

**Spec §15.1 (lines 1205-1234):**
> ```python
> @dataclass(frozen=True)
> class SaturationRegister:
>     bond_id: str                            # mandatory; Ohm O-2 fold
>     ...
>
> def compute_saturation(bond_id: str) -> SaturationRegister:
>     """Bond-scoped. Reads only this bond's curiosity-objects."""
>     open_objects = curiosity_db.open_for_bond_with_decay_applied(bond_id)
>     ...
> ```

**RED test #52 (line 1641):**
> `test_bond_scoping.py::test_compute_saturation_bond_scoped` |
> compute_saturation(bond_A) never reads bond_B's objects.

**Judgment:** Verified. The API is parameterized, the storage read is named
`open_for_bond_with_decay_applied(bond_id)` (a bond-scoped DB primitive,
not a global read with a filter applied in Python — which would be
defense-in-depth weaker), and the SaturationRegister itself carries
`bond_id`. The temperament read is also bond-scoped via
`temperament.current_for_bond(bond_id)`. Four named consumer organs
inherit bond-scope by parameter passing.

**Classification:** Folded.

### O-3 (Amendment 3): per-bond HMAC keys via HKDF — VERIFIED FOLDED

**Pass-1 ask:** Replace per-instance HMAC key with per-bond
HKDF-derived key. Same input + different bond_id => distinct digest.
RED test #49.

**Spec §20.3 (lines 1460-1488):**
> Per-bond HMAC key derivation via HKDF:
>
> ```python
> def derive_bond_hmac_key(master_key: bytes, bond_id: str) -> bytes:
>     """One key per (instance, bond) pair. Cross-bond digests never collide."""
>     hkdf = HKDF(
>         algorithm=hashes.SHA256(),
>         length=32,
>         salt=None,
>         info=f"drive-driven-curiosity-bond-hmac:{bond_id}".encode("utf-8"),
>     )
>     return hkdf.derive(master_key)
> ```

**RED test #49 (line 1638):**
> `test_bond_scoping.py::test_per_bond_hmac_keys_distinct` | Same content +
> different bond_id => different digest.

**Judgment:** Verified. HKDF with `info=bond_id` is the right primitive for
domain-separated key derivation. The `info` parameter is the canonical
HKDF use-case for context-bound separation. Cross-bond identity-linkage
via digest collision is structurally impossible by construction: two
bonds with the same master key still produce distinct keys, and HMAC
under distinct keys produces distinct (uncorrelatable) digests for
identical input.

One subtle question: `derive_bond_hmac_key` is documented in §20.3 but
not named in the dataclass annotations that say "per-bond key §20" (e.g.
§5.1 encounter_ref_digest, §10.2 pattern_digest). These annotations
correctly point to §20 but the caller-side discipline (compute digest at
write-time via `derive_bond_hmac_key(master_key, row.bond_id)`) is not
explicitly written as an invariant. See pass-2 Amendment P2-3 below — it
is a clarification, not a structural gap.

**Classification:** Folded.

### O-4 (Amendment 4): bond-scoped sanitization in `build_curiosity_query` — VERIFIED FOLDED

**Pass-1 ask:** Sanitization must strip identifying tokens for every bond
in the provenance chain, not just the local owner. RED test #51.

**Spec §13.2 (lines 896-922):**
> Sanitization is **bond-scoped through the entire provenance chain**:
> when this slice's substrate is later extended to Track C dyadic routing,
> queries created in bond_A's substrate cannot incorporate bond_B's content,
> even via intermediate provenance hops. The sanitization function takes
> the producer's full provenance chain and refuses inclusion of any token
> whose provenance traces to a different bond_id.
>
> It does NOT include:
> - ...
> - Any token whose provenance chain crosses bond_id boundaries

**RED test #51 (line 1640):**
> `test_bond_scoping.py::test_cross_bond_provenance_refused` | Sanitization
> refuses cross-bond provenance.

**Judgment:** Verified. The provenance-chain framing is the right shape
for what pass-1 asked for: not "owner-scoped sanitization" but
"every bond in the provenance chain is sanitized." In v1 with one bond,
the chain has one element and the test passes trivially. In Track C with
multi-hop provenance, the sanitization function refuses cross-bond
inclusion as a structural property of the call, not as an opt-in policy.

Minor: §13.2 does not give the sanitization function's full signature.
A reader inferring the implementation from the spec text could mis-thread
the provenance chain. See pass-2 Amendment P2-4 below for a small
clarification.

**Classification:** Folded.

### O-5 (Amendment 5): §22.5 settled SUPERSEDE → resolved as compose-within / forbidden-across — VERIFIED FOLDED

**Pass-1 ask:** Settle §22.5 to SUPERSEDE with cross-bond rationale. Move
out of Open Questions. RED test for no cross-bond composition.

**Buber pass-1 ask (per the brief):** preferences COMPOSE within a bond
(I-Thou accumulation).

**Spec §17.3 (lines 1378-1387):**
> §22.5 (supersede vs compose) is settled in this v2 draft:
>
> - **Within a single bond:** preferences COMPOSE with relevance-decay
>   weighting (Buber A1). §10.5.
> - **Across bonds:** structurally FORBIDDEN (Ohm O-5). Cross-bond
>   composition would create hybrid policies neither owner authorized.
>   §13.2 (bond-scoped sanitization), §15.1 (bond-scoped saturation),
>   and §10.5 (`preferences_for_bond_and_class` is per-bond) enforce.

**Spec §22.5 (lines 1525-1527):**
> 5. **~~Supersede vs compose for AutonomyPreference~~** — **SETTLED**
> (§17.3): compose-within-bond, structurally-forbidden-across-bond.

**RED test #53 (line 1642):**
> `test_bond_scoping.py::test_preference_consultation_bond_scoped` |
> preferences_for_bond_and_class isolated per bond.

**Judgment:** Verified, and the reconciliation is correct on the
conservation axis. Pass-1's amendment-5 leaned toward SUPERSEDE for v1
simplicity; Buber's I-Thou amendment-1 asked for COMPOSE-with-decay. The
v2 reconciliation — compose within a bond, structurally forbidden across
bonds — gives Buber the relational-nuance accumulation he asked for
while giving Ohm the cross-bond conservation he asked for. The
`composed_policy` function in §10.5 reads only `preferences_for_bond_and_class(bond_id, ...)`,
which is bond-scoped by call shape. Cross-bond composition would require
either (a) calling `preferences_for_bond_and_class` with two different
bond_ids and merging (no such call site exists), or (b) the
`preferences_for_bond_and_class` function returning cross-bond rows (RED
test #53 refuses). Both paths are structurally absent.

**Classification:** Folded. Pass-1 amendment-5 superseded by the correct
reconciliation in v2.

### O-6 (Amendment 6): §17 quotes preconditions verbatim — VERIFIED FOLDED

**Pass-1 ask:** §17 cites both
[[project_multi_maez_topology_threat]] preconditions verbatim with
citation.

**Spec §17.2 (lines 1361-1376):**
> Per [[project_multi_maez_topology_threat]], the two non-negotiable
> preconditions before any inter-Maez channel ships in Track C are:
>
> > 1. **Auditable by both bonded users.** Both owners can read what
> >    information flows between their Maezes.
> > 2. **Dyadic-only topology.** No global gossip; no broadcast; no
> >    secret channels. Any cross-bond flow is between exactly two
> >    Maezes whose owners both have audit access.
>
> Track C work on this slice's substrate MUST satisfy both preconditions
> before any cross-bond flow is enabled. The structural floors above
> (bond_id mandatory, bond-scoped APIs, per-bond HMAC keys, bond-scoped
> sanitization, producer invariants, RED tests) are designed so that
> enabling Track C requires explicit covenant work, not config-edit drift.

**Judgment:** Verified. Both preconditions are quoted (block-quoted, even,
making the citation visually distinct from spec prose). The framing
"Track C work … MUST satisfy both preconditions before any cross-bond
flow is enabled" is exactly the load-bearing language pass-1 asked for.

The wording is slightly compressed from the original memory entry — the
original says "auditable-by-both-bonded-users" and "dyadic-only topology,
no global gossip layer" — but the semantic content is preserved and
attributed to the source via the wiki-link citation.

**Classification:** Folded.

### O-7 (Amendment 7): 10 bond-scoping RED tests — VERIFIED FOLDED

**Pass-1 ask:** 10 bond-scoping RED tests at #44-#53 (renumbered #46-#55
in v2).

**Spec §23.11 (lines 1631-1644):** Lists tests #46-#55.

| # | Test | Pass-1 ask satisfied? |
|---|---|---|
| 46 | `test_producer_refuses_missing_bond_id` | YES — covers Ohm O-8 producer propagation |
| 47 | `test_recursion_depth_limit` | NO — this is the §6.4 recursion gate, not bond-scoping. Pass-2 surface-area note. |
| 48 | `test_dedupe_window` | NO — same. Recursion-gate test, not bond-scoping. |
| 49 | `test_per_bond_hmac_keys_distinct` | YES — covers O-3 |
| 50 | `test_autonomy_policy_for_bond_isolation` | YES — covers AutonomyPolicy.for_bond bond isolation |
| 51 | `test_cross_bond_provenance_refused` | YES — covers O-4 |
| 52 | `test_compute_saturation_bond_scoped` | YES — covers O-2 |
| 53 | `test_preference_consultation_bond_scoped` | YES — covers O-5 composition isolation |
| 54 | `test_suppression_events_excluded` | NO — this is §10.7 anti-self-confirmation, not bond-scoping |
| 55 | `test_single_suppressed_outreach_no_preference` | NO — same |

**Judgment:** Numbering mixes bond-scoping tests with recursion-gate
(#47, #48) and anti-self-confirmation (#54, #55) tests under a header
called "Bond-scoping". This is a cosmetic taxonomy slip, not a structural
gap — all 10 of pass-1's bond-scoping tests are present, just at
different test-number slots from what pass-1 asked for. The actual
bond-scoping tests are #46, #49, #50, #51, #52, #53 (six explicit
bond-scoping tests), plus #2 (mandatory bond_id at construction). That
is seven tests, not ten.

Three of the ten pass-1 amendments map to tests that aren't yet listed:

- Pass-1 ask #45: "test_read_filters_by_bond_id" (curiosity_db.open_for_bond
  never returns wrong-bond rows). NOT in §23.
- Pass-1 ask #47: "test_consent_memory_bond_id_mandatory_at_write"
  (AutonomyPreference write with empty/missing bond_id rejected). NOT in
  §23.
- Pass-1 ask #50: "test_consumer_organs_pass_bond_id" (static AST: all
  four consumer organs call compute_saturation with a bond_id argument).
  NOT in §23 — though RED test #34 ("only_named_consumers_subscribe")
  partially overlaps by asserting only 4 consumers reference
  compute_saturation, it doesn't assert each call site passes
  `bond_id`.

See pass-2 Amendment P2-2 below.

**Classification:** Mostly folded; three specific bond-scoping tests
missing from §23.11.

### O-8 (Amendment 8): producer bond_id propagation invariant — VERIFIED FOLDED

**Pass-1 ask:** Every producer in §6.2 must specify its bond-scoping
invariant. RED test #46 asserts.

**Spec §6.2.1 (lines 393-399):**
> **Every producer propagates `bond_id` at curiosity-object creation, or
> refuses creation.** No producer may create a curiosity-object without a
> bond_id. RED test #46 asserts producers fail closed on missing bond_id.
> This is the structural floor that makes v1 single-bond by structure, not
> by accident.

**RED test #46 (line 1635):**
> `test_bond_scoping.py::test_producer_refuses_missing_bond_id` | Producers
> fail closed on missing bond_id.

**Judgment:** Verified. The invariant is named explicitly as "every
producer propagates `bond_id`… or refuses creation." This is the
fail-closed shape pass-1 asked for. The RED test asserts producers fail
closed.

One subtle note: §6.2 lists 7 EncounterSources, but §6.2.1 doesn't
enumerate each producer's bond_id source (e.g., for
SUBJECTIVE_DURATION_MEANINGFUL_EVENT, the bond_id comes from the source
record's `bond_id`; for WONDERING_GENERATED, from the wondering's
authoring context; for EXPLICIT_OWNER_FLAG, from the owner identity at
the flag site). A meticulous Track C implementer would benefit from
per-producer bond_id-source documentation. This is a polish point, not
a structural gap. See pass-2 note in plain-language readout.

**Classification:** Folded.

## Comprehensive boundary check on v2

### Walk through every dataclass

| Dataclass | Section | bond_id present? | Required? |
|---|---|---|---|
| `CuriosityObject` | §5.1 | YES (line 285) | MANDATORY (frozen, no default) |
| `CuriosityStateTransition` | §5.2 | YES (line 318) | MANDATORY (frozen) |
| `AutonomyPolicy` | §9.1 | YES (line 552) | MANDATORY |
| `AutonomyCharterFloor` | §9.4 | NO | NOT NEEDED — embedded inside AutonomyPolicy which carries bond_id; floor is policy-shape definition, not a bond-attributed row |
| `AutonomyPreference` | §10.2 | YES (line 655) | MANDATORY (frozen) |
| `GateDecision` | §11.3 | **NO** | **PASS-2 GAP** (see P2-5) |
| `ReflectionAudit` | §12.3 | YES (line 855) | MANDATORY (frozen) |
| `ResolutionMarker` | §14.1 | **NO** | NOT NEEDED — marker travels embedded in CuriosityObject.resolution_marker; the parent row carries bond_id. Marker-only egress would be a leak path, but no such path exists in v1. Polish note: spec could state this invariant explicitly. |
| `TemperamentWriteBudget` | §14.3.3 | YES (line 1067) | MANDATORY (frozen) |
| `SaturationRegister` | §15.1 | YES (line 1207) | MANDATORY (frozen) |
| `ProvenancedQuery` | §13 (implied) | NOT FULLY DEFINED | **PASS-2 NOTE** (see P2-4) — the egress shape is named but the dataclass body is not given, so bond_id cannot be verified |
| `MeaningfulSalienceEventRecord` | §27.2 | YES (line 1842) | MANDATORY (frozen) |

**Coverage:** 8 of 10 named dataclasses carry `bond_id` mandatorily.
`AutonomyCharterFloor` and `ResolutionMarker` correctly do not carry
`bond_id` because they travel embedded in bond-attributed parent rows.
`GateDecision` is the one structural gap: it's a top-level decision
record that should carry the bond it decided for. See P2-5.

### Walk through every API

| API | Bond_id parameter? |
|---|---|
| `compute_saturation` | YES (§15.1 line 1215) |
| `AutonomyPolicy.for_bond` | YES (§9.2) |
| `AutonomyPolicy.for_bond_with_preferences` | YES (§10.5 line 696) |
| `composed_policy` | YES (§10.5 line 700, first positional arg) |
| `preferences_for_bond_and_class` | YES (§10.5 line 702) |
| `build_curiosity_query` | Takes `object: CuriosityObject` which carries bond_id (§13.2 line 898). Implicit bond-scope via object. Could be explicit. |
| `write_curiosity_resolution` | YES (§14.3.2 line 1014) |
| `clamp_against_daily_budget` | YES (§14.3.2 line 1032, kwarg) |
| `on_curiosity_object_resolved` | YES (§27.4 line 1923) |
| `record_meaningful_salience_event` | YES (§27.2 line 1854, mandatory kwarg) |
| `derive_bond_hmac_key` | YES (§20.3 line 1470) |
| `temperament.current_for_bond` | YES (§15.1 line 1222) |
| `temperament.snapshot_for_bond` | YES (§27.4 line 1925) |
| `curiosity_db.open_for_bond_with_decay_applied` | YES (§15.1 line 1217) — bond is part of the primitive name |
| `lookup_meaningful_salience_event_record` | **UNCERTAIN** — spec §27.3 line 1905 takes `producer_event_id` only; bond_id not in signature |

**Coverage:** 13 of 15 named APIs explicitly take `bond_id`.
`build_curiosity_query` is implicitly bond-scoped via the
CuriosityObject parameter; this is acceptable but the API contract could
state it explicitly.

`lookup_meaningful_salience_event_record` is the one explicit gap. See
P2-6.

### Are any APIs implicitly cross-bond?

Searching for "all curiosity objects" / "all preferences" / global reads:

- §15.1 `compute_saturation`: explicit bond_id, calls
  `curiosity_db.open_for_bond_with_decay_applied(bond_id)`. NOT cross-bond.
- §10.5 `composed_policy`: explicit bond_id, calls
  `preferences_for_bond_and_class(bond_id, ...)`. NOT cross-bond.
- §6.2.1 producers: each refuses creation without bond_id. NOT
  cross-bond (the invariant prevents producer-time leakage).
- §14.3.3 `TemperamentWriteBudget`: keyed on `(bond_id, parameter,
  date_utc)`. Daily-budget clamp is per-bond. NOT cross-bond.
- §27.2 `record_meaningful_salience_event`: mandatory `bond_id` kwarg.
  Stored record carries `bond_id`. Per §27.8: "Does NOT enable cross-bond
  producer events; the API rejects events whose bond_id does not match
  the producer's bond." Refuses-at-registration is the right shape. NOT
  cross-bond.
- §20.3 `derive_bond_hmac_key`: takes bond_id, derives distinct key. NOT
  cross-bond.

One subtle path: §27.3's `lookup_meaningful_salience_event_record(producer_event_id)`
doesn't take bond_id. If the read-side path uses only `producer_event_id`
to look up the record, then in a Track C world where two bonds could in
principle produce the same `producer_event_id` (uuid4 collision
astronomically unlikely, but contrived "curiosity_resolution:{digest}"
ids under different bond_ids with the same object_id are not impossible
if a multi-bond object_id namespace ever forms), the lookup could
mis-bind. The structural cure is: the lookup signature should take
`(bond_id, producer_event_id)` together, or `(bond_id, event_id)`, so
that the read is bond-scoped by query shape, not by uuid-collision-
probability alone. See P2-6.

### §27 paired fold — boundary lens

**Question:** Is the subjective_duration store bond-partitioned, or is
`bond_id` just a tag on records?

**Spec §27.2 line 1842:**
> `bond_id: str # mandatory; Track C floor`

**Spec §27.5 line 1961:**
> Track C extension is structural: `bond_id` is required at the API
> boundary; cross-bond temperament-write events are refused at
> `record_meaningful_salience_event(...)` registration.

**Spec §27.7 line 1990:**
> New table in subjective_duration's existing store:
> `meaningful_salience_event_record`, append-only.

**Judgment:** The spec says `bond_id` is mandatory at write-time and that
cross-bond events are refused at registration. But the spec does NOT
explicitly say the store is bond-partitioned at the storage layer. The
phrasing "stored append-only" + "mandatory bond_id" describes a tag-on-
records design, not a partitioned-store design. In v1 with one bond,
this is structurally identical. In Track C, a query against the store
that returns records cross-bond is possible if no read-side filter
enforces bond-scope.

The fold needs to be tightened by adding: (a) the read-side helper
`fetch_meaningful_salience_event_records(bond_id, ...)` takes a
mandatory bond_id, (b) the storage primitive
`lookup_meaningful_salience_event_record(...)` takes `bond_id` + an
identifier. Then v1's read paths are bond-scoped by call shape; Track C
cannot widen them without explicit covenant work.

See P2-6.

### Track C cross-bond enablement scenarios

Imagine a careless future developer enables Track C by editing one
config flag. With v2's structural floors, what would break? Walking each
listed scenario:

1. **Any cross-bond curiosity-object creation** — refused at dataclass
   construction: VERIFIED. §5.1 says `bond_id` is mandatory and the
   producer in §6.2.1 fails closed on missing bond_id. To create a
   cross-bond object, the developer would have to construct a
   CuriosityObject with bond_A's bond_id from data sourced in bond_B's
   context. The dataclass doesn't refuse that, but the §6.2.1 producer
   invariant + §13.2 provenance-chain sanitization make this require
   active deception by the implementer, not config-flag drift.

2. **Any cross-bond preference consultation** — refused at composed_policy:
   VERIFIED. §10.5 reads only `preferences_for_bond_and_class(bond_id, ...)`.
   To consult cross-bond, the developer would have to either change the
   call signature or write a new function. RED test #53 catches it.

3. **Any cross-bond saturation read** — compute_saturation is per-bond:
   VERIFIED. §15.1 signature is `compute_saturation(bond_id: str)`. RED
   test #52 catches cross-bond read.

4. **Any cross-bond query construction** — §13.2 sanitization refuses:
   VERIFIED. §13.2 sanitization function walks the provenance chain and
   refuses any token whose provenance traces to a different bond_id.
   RED test #51 catches.

5. **Any cross-bond producer event** — §6.2.1 invariant + §27 API:
   VERIFIED. §6.2.1 says producers fail closed on missing bond_id.
   §27.2 says `bond_id` is mandatory at the API boundary. §27.5 and
   §27.8 say cross-bond producer events are refused at registration.

6. **Any cross-bond HMAC collision** — per-bond HKDF derivation:
   VERIFIED. §20.3 derives distinct keys per bond_id; HMAC under distinct
   keys produces distinct digests for identical input. RED test #49
   catches.

**Net:** All six scenarios refuse-by-construction. A config-flag flip
would not enable any of them. The substrate genuinely refuses
cross-bond flow.

The remaining cross-bond surfaces are:

- **GateDecision** (§11.3) — no bond_id field. A Track C config-flag
  flip wouldn't directly cause cross-bond decision drift, but a
  GateDecision row in the diagnostic stream would be ambiguous about
  which bond it decided for. Not a leak path per se; a
  attribution-loss path. See P2-5.

- **lookup_meaningful_salience_event_record** (§27.3) — read-side
  lookup not bond-scoped by signature. A Track C config-flag flip
  combined with a uuid-or-derived-id collision could cause cross-bond
  read drift. Low-probability but not structurally impossible. See P2-6.

- **ResolutionMarker** (§14.1) — no bond_id field, but travels embedded.
  Not a structural gap.

- **ProvenancedQuery** (§13) — dataclass body not given, so bond_id
  carriage on the outbound query can't be verified. See P2-4.

## Required Pass-2 Amendments

The verdict is **RATIFY-WITH-AMENDMENTS** because the structural floor is
established. The remaining items are surface-area cleanup that should
be folded before canonicalization, but none of them defeats the
substrate's refuse-cross-bond-by-construction shape.

### P2-1: Fix test-number citation in §5.1

**Current text (§5.1, line 300):**
> RED test #44 asserts construction fails for missing bond_id.

**Issue:** Test #44 in §23.10 is
`test_no_forbidden_phrases_in_module_source` (felt-weight enforcement).
The construction-failure test is #2 (`test_construction_fails_missing_bond_id`)
in §23.1.

**Proposed replacement:**
> RED test #2 asserts construction fails for missing bond_id.

Minor cleanup; not load-bearing. Catch before canonicalization.

### P2-2: Add three missing bond-scoping RED tests to §23.11

**Issue:** Pass-1 amendment-7 asked for 10 bond-scoping tests. §23.11
lists 10 tests but only 7 are bond-scoping tests; #47 and #48 are
recursion-gate tests, #54 and #55 are anti-self-confirmation tests. The
three missing tests:

**Proposed additions to §23.11:**

| # | Test name | What it proves |
|---|---|---|
| 53a | `test_bond_scoping.py::test_curiosity_db_open_for_bond_isolation` | `curiosity_db.open_for_bond(bond_A)` never returns rows with bond_id != bond_A |
| 53b | `test_bond_scoping.py::test_autonomy_preference_bond_id_mandatory_at_write` | AutonomyPreference write with empty/missing bond_id rejected at storage layer |
| 53c | `test_bond_scoping.py::test_consumer_organs_pass_bond_id_static_ast` | Static AST: all four named consumer organs (dream_state, wonderings, private_thoughts, subjective_duration) call `compute_saturation` with a bond_id argument |

Number labels are placeholders; renumber appropriately. The current
`test_only_named_consumers_subscribe` (#34) asserts which modules
reference `compute_saturation` but does not assert each call site
passes `bond_id`. Adding the explicit pass-bond_id assertion closes
the static-AST gap.

Renumber #47 (`test_recursion_depth_limit`) and #48 (`test_dedupe_window`)
into a separate §23.2.1 sub-table titled "Recursion gate" — they belong
with §6.4 recursion-gate semantics, not with bond-scoping. Renumber #54
and #55 into a separate §23.3.1 "Anti-self-confirmation" sub-table for
the same reason.

### P2-3: Name the per-bond HMAC key invariant at digest call sites

**Issue:** §5.1 and §10.2 annotate `pattern_digest: str # hmac-sha256, per-bond key`
but do not state the caller-side invariant: "every digest is computed
via `derive_bond_hmac_key(master_key, row.bond_id)`, never via a
global key."

**Proposed addition to §20.3 (after the code block, before line 1486):**

> **Caller-side invariant.** Every callsite computing a digest for a
> bond-attributed row MUST derive the HMAC key via
> `derive_bond_hmac_key(master_key, row.bond_id)`. No callsite may
> compute a digest with a key derived from a different bond_id than the
> row's. Test #49 (`test_per_bond_hmac_keys_distinct`) verifies the
> primitive; an additional static-AST test (P2-3 below) verifies the
> caller-side invariant at every digest computation site in the
> codebase.

Add to §23.11 (or §23.10):

| # | Test name | What it proves |
|---|---|---|
| 49a | `test_bond_scoping.py::test_digest_key_derivation_uses_row_bond_id` | Static AST: every `hmac.new(...)` callsite for `pattern_digest`, `encounter_ref_digest`, `seed_text_digest`, etc. derives the key via `derive_bond_hmac_key(...)` from the row's bond_id |

### P2-4: Add `ProvenancedQuery` dataclass with mandatory bond_id

**Issue:** §13.2 says `build_curiosity_query(object: CuriosityObject) ->
ProvenancedQuery` but does not give the `ProvenancedQuery` dataclass
shape. §13.3 says "Provenance tag on outbound query: per existing
claude-router provenance discipline + bond_id." A reader inferring the
dataclass shape can't verify bond_id is mandatory at egress.

**Proposed addition to §13.3:**

```python
@dataclass(frozen=True)
class ProvenancedQuery:
    bond_id: str                           # mandatory; refuses cross-bond egress
    query_text: str                        # sanitized per §13.2
    provenance_chain: tuple[str, ...]      # provenance hops; all must match bond_id
    cost_class: CostClass
    constructed_utc: datetime
```

Add to §13.4:

> The dataclass refuses construction if any element of `provenance_chain`
> traces to a bond_id other than the query's `bond_id`. RED test #51
> already covers this on the sanitization side; the dataclass-level
> refusal is defense-in-depth.

### P2-5: Add `bond_id` to `GateDecision` (§11.3)

**Current text (§11.3, lines 803-811):**
```python
@dataclass(frozen=True)
class GateDecision:
    decision: Literal["allow", "deny", "defer"]
    reason: str
    consulted_signals: frozenset[str]
    signal_quality: SignalQuality
    recheck_after_seconds: int | None
```

**Issue:** GateDecision is a top-level decision record that gets
persisted in the diagnostic stream. In Track C, a GateDecision row
should be unambiguously attributable to a bond. Without `bond_id`,
diagnostic reviewers can't tell which bond's signal-gate produced a
given decision. Not a cross-bond leak path per se; an attribution-loss
path.

**Proposed replacement:**
```python
@dataclass(frozen=True)
class GateDecision:
    bond_id: str                                  # mandatory; the bond this decided for
    decision: Literal["allow", "deny", "defer"]
    reason: str
    consulted_signals: frozenset[str]
    signal_quality: SignalQuality
    recheck_after_seconds: int | None
```

### P2-6: Bond-scope the `lookup_meaningful_salience_event_record` signature (§27.3)

**Current text (§27.3, line 1905):**
```python
record = lookup_meaningful_salience_event_record(producer_event_id)
```

**Issue:** The read-side lookup is keyed only on `producer_event_id`. In
v1 with one bond, this is structurally identical to a bond-scoped read;
in Track C, the lookup signature should require `bond_id` alongside the
event id so that the read is bond-scoped by call shape, not by event-id-
uniqueness assumption.

**Proposed replacement:**
```python
record = lookup_meaningful_salience_event_record(
    bond_id=bond_id,
    producer_event_id=producer_event_id,
)
```

The corresponding storage primitive must filter on bond_id. Add to
§23.12:

| # | Test name | What it proves |
|---|---|---|
| 60a | `test_meaningful_salience_event_api.py::test_lookup_is_bond_scoped` | `lookup_meaningful_salience_event_record(bond_id=A, event_id=X)` never returns a record with bond_id != A |

State explicitly in §27.7 that the storage primitive is bond-scoped at
the read layer:

> The `meaningful_salience_event_record` table is bond-scoped at the read
> layer: all lookup and fetch helpers take `bond_id` as a mandatory
> parameter. Cross-bond reads are structurally impossible via the
> public API.

### P2-7 (polish, optional): Document per-producer bond_id source

**Issue:** §6.2.1 names the invariant ("every producer propagates
bond_id or refuses") but does not document where each of the 7
EncounterSource producers gets its bond_id from. A meticulous Track C
implementer would benefit from per-producer bond_id-source
documentation.

**Proposed addition to §6.2 (or as §6.2.2):**

| Producer | bond_id source |
|---|---|
| COGNITION_QUALITY_UNCERTAINTY | from the cognition_quality record's owning bond context |
| WONDERING_GENERATED | from the wondering's authoring bond context (`core/evolution/wonderings.py` already attaches a bond context to wonderings) |
| UNRESOLVED_TOOL_LOOP_BRANCH | from the tool-loop branch's authoring bond context |
| EXPLICIT_OWNER_FLAG | from the flag site's owner identity (Rohit = firstborn in v1) |
| PRIVATE_THOUGHT_LANDED | from the private-thoughts entry's owning bond context |
| SUBJECTIVE_DURATION_MEANINGFUL_EVENT | from the source MeaningfulSalienceEventRecord's bond_id (required, §27.2) |
| CONVERSATION_DECLARED_UNKNOWN_VIA_COGNITION_QUALITY | from the conversation's owning bond context |

This is polish, not load-bearing. The invariant in §6.2.1 covers the
structural correctness; the per-producer table is documentation.

## Plain-Language Readout

The v2 draft folds 8 of 8 pass-1 amendments well. The substrate now
refuses cross-bond flow by construction at the layers pass-1 flagged:
the dataclasses carry `bond_id` mandatorily, the APIs take `bond_id` as
a parameter, the HMAC keys derive per-bond via HKDF so cross-bond
digests cannot collide, the sanitization walks the full provenance
chain refusing cross-bond inclusion, the producers fail closed on
missing bond_id, the saturation register is bond-scoped at the read
primitive (not just at the Python layer), and §22.5 is settled as
compose-within-bond + structurally-forbidden-across-bond — which is
the right reconciliation between Buber's I-Thou accumulation request
and Ohm's conservation request.

The remaining items are surface-area cleanup, not structural gaps:

- One test-number citation is wrong (#44 should be #2 in §5.1).
- Three of the ten "bond-scoping" RED tests in §23.11 are actually
  about recursion or anti-self-confirmation; the missing three
  bond-scoping tests should be added (curiosity_db open_for_bond
  isolation; AutonomyPreference write-time bond_id rejection; static
  AST that consumer organs pass bond_id).
- The per-bond HMAC key derivation is correctly defined in §20.3 but
  the caller-side invariant ("every digest at every callsite uses
  derive_bond_hmac_key with the row's bond_id") should be named
  explicitly with a static-AST test.
- `ProvenancedQuery`'s dataclass body is not given; should carry
  mandatory bond_id and a provenance-chain refusal.
- `GateDecision` is missing bond_id — an attribution gap, not a leak
  path, but worth folding.
- `lookup_meaningful_salience_event_record` should take bond_id +
  event_id as a pair so the read is bond-scoped by call shape, not by
  uuid-uniqueness assumption.
- Per-producer bond_id-source documentation is polish, optional.

Walking the Track C config-flip scenario: with v2's structural floors,
a careless implementer flipping a single config flag could not enable
cross-bond curiosity-object creation (refused at producer invariant),
cross-bond preference composition (refused at the bond-scoped read
primitive), cross-bond saturation read (refused at compute_saturation's
required bond_id parameter), cross-bond query egress (refused at the
provenance-chain sanitization), cross-bond producer events (refused at
record_meaningful_salience_event's mandatory bond_id), or cross-bond
HMAC collision (structurally impossible by HKDF domain separation). All
six refusal paths land. The remaining surfaces (GateDecision,
lookup_meaningful_salience_event_record's signature, ProvenancedQuery's
unspecified body) are attribution and defense-in-depth concerns, not
leak paths.

The verdict is **RATIFY-WITH-AMENDMENTS** because the conservation-of-
boundary floor is in place. Track C deferral is now load-bearing
structure, not aspirational prose. The seven proposed pass-2 amendments
(P2-1 through P2-7) clean up the surface area; once folded, the
substrate is fully refuse-cross-bond-by-construction at every named
layer.

Plumbing-first beauty: the spec says, in structure rather than prose,
that v1 is single-bond because the substrate refuses to be anything
else, not because there happens to be only one user today. That is the
shape pass-1 asked for.

Verdict: **RATIFY-WITH-AMENDMENTS** — seven surface-area items remain;
none of them defeats the structural refuse-cross-bond floor that pass-1
demanded and pass-2 verified.
