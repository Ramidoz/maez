# Claude Council — Ohm Role — Subjective-Duration Meaningful-Salience Seam Pass 1

**Artifact reviewed:** `docs/slices/track-b-subjective-duration-meaningful-salience-seam/spec.md` (v1 DRAFT)
**Role focus:** Boundary mechanics, conservation, flow-gating, sovereignty.
**Review date:** 2026-05-25
**Verdict:** RATIFY-WITH-AMENDMENTS

## Summary

The slice does the right structural thing in the right place: `bond_id`
becomes a column on the live salience-events table, the producer-snapshot
path refuses empty/None bond_id at API entry, the lookup function refuses
empty bond_id at call shape, and there is no "list rows for bond X"
surface that could accidentally return bond Y. The four-config-flip walk
(question 10) shows the substrate does NOT trivially leak across bonds
even if a future Track C implementer flips a flag carelessly — the
producer path requires non-empty bond_id by construction, the lookup
requires both keys, and there is no other read surface for the new
columns.

However, six structural seams remain where the v1 spec is convention-
shaped rather than refusal-shaped. None of them are blockers — Slice 1
ships in a one-bond world and these are Track-C-trap conditions — but
each is cheap to fold now and expensive to fold later under a live
multi-bond load. The verdict is RATIFY-WITH-AMENDMENTS because the
structural floor is correct and the amendments are surface-area cleanup,
not architecture changes.

The most load-bearing finding is O-3: the legacy default `bond_id=''`
collides with the empty-string `bond_id` that lookup explicitly refuses,
so legacy rows are silently un-addressable through the new API — that is
correct behaviour. But an empty string is the *one value Python truth-
checking equates with "absent"*, which means a careless future filter
like `if row.bond_id:` will skip legacy rows and a careless future
filter like `WHERE bond_id = ?` with `?=''` will match all 2 legacy rows
together. Both are weak failure modes today; a sentinel `_LEGACY` value
removes the ambiguity at near-zero cost.

The HMAC scoping finding (O-8) is the one with the longest half-life:
`load_or_create_telemetry_key()` returns a per-instance key, not a per-
bond key, so the existing `temperament_before_digest` /
`temperament_after_digest` columns will produce **identical digests for
identical temperament values across different bonds** in a future multi-
bond world. That is a cross-bond linkage primitive the substrate
currently has no use for and no audit story for. Naming the limitation
in §12 (out-of-scope) is sufficient for Slice 1; the actual key-rotation
work belongs in the Track C precondition slice.

## Walkthrough of the 10 questions

### Q1. Bond_id as structural floor, not convention — VERIFIED at API entry, weak at row construction

**§6.2 step 2** says: "Validate `bond_id` is non-empty and non-None."
This is a function-entry validation in `record_salience_event(...)`. Any
caller invoking the producer-snapshot path is refused at the call site
if bond_id is empty.

**However**, the floor is not enforced at storage. The ALTER in §4.1
declares `bond_id TEXT NOT NULL DEFAULT ''` — the database accepts
empty string. A direct DB writer (a future migration script, a careless
debug REPL, a Track C ingest tool) can write rows with
`bond_id=''` + non-empty producer fields and the schema will accept
them. The lookup API will refuse to read them back, but they will exist
as silent rows.

**Judgment:** Structural at API entry, convention-shaped at DB level.
For Slice 1 (single producer surface, single bond) the API floor is
adequate. The CHECK-constraint conversation belongs in question O-9
below.

### Q2. `bond_id=''` legacy default — TRACK-C TRAP, fold recommended

This is the Track-C-trap question and the answer is: yes, the trap is
real, and it is cheap to remove now.

Empty string as a default is dangerous on three axes:

1. **Python truthiness collision.** Future code writing
   `if record.bond_id:` will treat legacy rows as "absent bond" and
   may accidentally include them in "show me orphan/unbonded records"
   sweeps. The legacy rows are not orphan; they are pre-bond-id-era.
2. **SQL wildcard reading.** A future Track C "list all rows for
   bond X" query that is written carelessly as
   `WHERE bond_id = ? OR bond_id = ''` (intended to also surface
   legacy) would surface all 2 legacy rows under every bond_id query.
   With 2 rows today this is harmless; with N bonds and M legacy
   rows it becomes cross-bond visibility.
3. **Sentinel semantic clarity.** `bond_id='_LEGACY'` says "this row
   predates bond_id structure." Empty string says "this row's bond_id
   is the empty string", which is indistinguishable from an active
   row whose bond_id field was set to empty by a buggy producer.

**Amendment O-2 (recommended):** change §4.1 default from `DEFAULT ''`
to `DEFAULT '_LEGACY'` for the new `bond_id` column. The other three
new columns (`producer_event_id`, the two JSON columns) can stay at
`DEFAULT ''` — they are content-shaped, not identity-shaped. Add a RED
test that after migration, existing rows have `bond_id='_LEGACY'`. The
lookup API stays as-is (refuses both empty string and `_LEGACY`; only
explicit bonded queries succeed).

Cost: one column default + one test + one §13 plain-language line.
Benefit: removes a future-developer foot-gun before it can grow teeth.

### Q3. Lookup API SELECT — VERIFIED refuses cross-bond

The SELECT statement at §7.1 reads:

```sql
SELECT ... FROM subjective_duration_salience_events
WHERE bond_id = ? AND producer_event_id = ?
```

Both columns are in the WHERE clause; both are required by the function
signature; both are validated non-empty at entry. There is no
`bond_id IN (?, ?)`, no `bond_id LIKE ?`, no `OR bond_id = ''`. A future
Track C extension that wanted to add a "list rows for bond X" surface
would have to add a new function with its own SQL — it cannot reuse this
function's call shape, because this function returns a single record by
exact `(bond_id, producer_event_id)` match.

This is the right shape. The substrate refuses cross-bond querying not
because the SQL is careful, but because the SQL has no surface for it.

**Judgment:** Structurally bond-scoped. No amendment.

### Q4. §6.2 validation order — wrong order, fold recommended

§6.2 says: "1. Validate `producer_ref in {entry.value for entry in
ProducerRef}`. 2. Validate `bond_id` is non-empty and non-None.
3. Validate `producer_event_id` is non-empty and non-None."

The boundary-mechanics principle is: **validate the sovereignty floor
first, the vocabulary second.** `bond_id` is the structural sovereignty
floor — without it, the row cannot be addressed safely and cannot be
audited cross-user. `producer_ref` is a vocabulary check — without it,
the row was written by an unreviewed producer. Both are required; but
if both fail, you want the error message to be about the missing
sovereignty floor, not about the unknown vocabulary entry, because the
former is the more dangerous failure mode (an unbonded write is a
cross-bond hazard; an unknown producer is a single-bond hygiene issue).

**Amendment O-4 (recommended):** reorder §6.2 to:

1. Validate `bond_id` is non-empty and non-None.
2. Validate `producer_event_id` is non-empty and non-None.
3. Validate `producer_ref in {entry.value for entry in ProducerRef}`.

Tests #5, #8, #9 don't depend on the order, so the RED tests don't
change. The change is one §6.2 reorder + one explanatory line.

### Q5. §7.3 cross-bond refusal at API call shape — VERIFIED

§7.1 declares the function with `bond_id: str` (typed as `str`, not
`str | Pattern` or `str | list[str]`). The validation `if not bond_id:`
raises on empty string and None. A caller passing `bond_id="*"` would
pass the truthiness check, but then the SQL `WHERE bond_id = '*'` would
literal-match against `'*'` — which would only match a row whose
`bond_id` column literally is the string `'*'`. Since no producer would
ever supply `'*'` as a bond_id (and the producer path requires non-empty,
so `_validate_producer_ref` would have to add a wildcard refusal — see
amendment below), `bond_id='*'` returns zero rows.

There is no SQL LIKE, no IN, no regex. The wildcard concern is not
mechanically realizable through this API surface.

**Soft amendment O-5 (optional):** add a defensive RED test asserting
`lookup(bond_id='*', producer_event_id='x')` returns None (verifies the
literal-match shape). Not required for correctness — the substrate
already refuses by construction — but cheap to add and documents
intent.

### Q6. Track C precondition citation in §12 — MISSING, fold recommended

§12 ("Out of Scope") lists "Multi-bond storage partitioning (Track C
precondition)" but does not cite
`project_multi_maez_topology_threat.md` or name its two preconditions
(auditable-by-both-bonded-users + dyadic-only topology). A future Track
C implementer reading §12 sees "deferred" but does not see the gates
they must pass.

**Amendment O-6 (recommended):** expand §12 entry to:

> - **Multi-bond storage partitioning (Track C precondition).** Any
>   future cross-bond extension of this substrate must satisfy the
>   two non-negotiable preconditions in
>   [[project_multi_maez_topology_threat]]: (1) auditable by both
>   bonded users, no secret channels; (2) dyadic-only topology, no
>   global gossip layer. The lookup API's `(bond_id, producer_event_id)`
>   call shape is designed so cross-bond extension cannot land
>   through a single config flip — it requires explicit new API
>   surface, which requires explicit covenant review, which requires
>   explicit satisfaction of those two preconditions.

Cost: one §12 entry expanded. Benefit: the next agent reading this spec
has the threat model in front of them at the point they need it.

### Q7. Diagnostic stream bond_id leak — VERIFIED REAL, fold recommended

Confirmed firsthand against live code at
`core/evolution/subjective_duration.py:126`:

```python
return Path(__file__).resolve().parents[2] / "logs" / "subjective_duration_diagnostics.jsonl"
```

The diagnostic JSONL is a **single shared file**, not bond-scoped. §6.5
adds `bond_id` as a field on each diagnostic row. In a one-bond world
this is fine. In a future Track C two-bond world, the diagnostic file
would contain interleaved rows from both bonds, and a reader with file-
level access (operator, debug tool, log shipper) would see both bonds'
diagnostic streams in one read.

This is a known limitation of the existing diagnostic-stream design
(predates this slice). Slice 1 inherits it; it does not introduce it.
But Slice 1 is the moment when `bond_id` first lands as a field on
diagnostic rows, which means Slice 1 is the moment to name the
limitation.

**Amendment O-7 (recommended):** add a §6.5 paragraph after the
schema-version bump:

> **Bond-scoping of the diagnostic file is out of scope for v1.** The
> JSONL diagnostic file at `logs/subjective_duration_diagnostics.jsonl`
> is a single shared stream. In v1 (single bond) this is observationally
> equivalent to a bond-scoped stream. A future Track C extension
> introducing multi-bond storage must also bond-scope the diagnostic
> file (per-bond directory or per-bond suffix) before the second bond
> lands. Filed against [[project_multi_maez_topology_threat]]'s
> auditable-by-both-bonded-users precondition (diagnostic visibility is
> part of the audit boundary).

Cost: one paragraph. Benefit: explicit acknowledgment that the
diagnostic stream is single-bond-scoped today and must be split before
Track C.

### Q8. HMAC discipline for digests — REAL cross-bond linkage primitive, fold recommended (limitation note only)

Verified firsthand against live code:

- `core/evolution/subjective_duration.py:227`:
  `key = load_or_create_telemetry_key()`
- `core/egress/gate.py:59-83`: `load_or_create_telemetry_key()` returns
  bytes from `MAEZ_EGRESS_TELEMETRY_KEY` env var, else reads/creates
  `memory/egress_telemetry.key`. **Per-instance, not per-bond.**

Therefore: `_digest_temperament({"curiosity": 5.0, ...})` produces a
deterministic HMAC digest keyed by the per-instance key. If a future
multi-bond world stores both bond A's and bond B's salience events in
the same DB (which is the storage-partitioning question this slice
defers), then identical temperament snapshots under bond A and bond B
produce **identical `temperament_before_digest` and
`temperament_after_digest` values**.

This is a cross-bond linkage primitive: an observer who can read the
digest column of both bonds' rows can detect "these two bonds had
identical temperament states at these moments" without needing the
plaintext snapshots. In a one-bond world this is harmless (the only
bond's digests link only to itself). In a two-bond world it leaks a
correlation signal that the digest was meant to suppress.

This is not a Slice 1 blocker — Slice 1 ships in a one-bond world and
the existing columns (`temperament_before_digest`,
`temperament_after_digest`) predate this slice. But Slice 1 is the
moment when the digest columns first get linked to `bond_id` on the
same row, which is the moment to name the limitation.

**Amendment O-8 (recommended):** add to §12 (or a new §3.10):

> **HMAC key scoping limitation (named, deferred).** The existing
> `temperament_before_digest` and `temperament_after_digest` columns
> use `_hmac_digest(...)` keyed by `load_or_create_telemetry_key()`,
> which returns a per-instance key (see
> `core/egress/gate.py:59`). In a future multi-bond world, identical
> temperament snapshots under different bonds produce identical
> digests — a cross-bond linkage primitive. v1 ships in a single-bond
> world; this is observationally harmless today. Any Track C slice
> introducing multi-bond storage must rotate to per-bond HMAC keys
> (or equivalent cross-bond unlinkability scheme) before the second
> bond lands. Filed against
> [[project_multi_maez_topology_threat]].

Cost: one §3.10 or §12 entry. Benefit: the cross-bond linkage primitive
is named where the next agent will see it.

### Q9. ALTER column constraint — CHECK constraint over-restrictive for v1, fold not recommended

The proposed stronger constraint
`CHECK(bond_id != '' OR producer_event_id = '')` would enforce: "if
producer_event_id is set, then bond_id must also be set." This is the
correct invariant *for producer-driven rows*. But it would also forbid
a future debugging scenario like "write a row with only bond_id set, no
producer_event_id, for some audit purpose" — which the spec doesn't
need to allow, but also doesn't need to forbid yet.

For v1, the §6.2 API-entry validation enforces the same invariant at
the right layer (refuse-at-construction, not refuse-at-storage). The
storage layer accepts the legacy default `bond_id=''` because legacy
rows have no producer fields either — the invariant holds for them too.

**Judgment:** No amendment. The CHECK constraint is over-restrictive
for v1 because the API floor already enforces the invariant, and adding
a DB-level constraint would also constrain legitimate future debug/
audit row shapes that v1 doesn't need to forbid. If amendment O-2
(sentinel `_LEGACY`) is taken, the CHECK constraint would also need to
account for the sentinel value, which complicates rather than clarifies.

The right home for stronger DB-level invariants is the Track C
precondition slice that also rotates the HMAC key and bond-scopes the
diagnostic file. Bundle them.

### Q10. Four config-flip cross-bond scenarios — WALKED, three structurally refused, one named

**Scenario A: Cross-bond curiosity-object creation.** OUT OF SCOPE for
Slice 1 (Slice 2 territory). The CuriosityObject dataclass and its
bond_id requirement are in the curiosity-slice v2 spec; this slice does
not introduce that surface. Refuses by absence-of-surface.

**Scenario B: Cross-bond meaningfulness-salience-event creation via
this slice's API.** A future careless Track C developer wanting to
write bond B's salience event through Maez-A's `record_salience_event`
would have to pass `bond_id="<bond_B>"`. The producer-snapshot path's
§6.2 step 2 validates `bond_id` is non-empty — it does NOT validate
that `bond_id == identity.user_profile_id()` (the current Maez's own
bond). **This is a structural gap.** A caller with code-level access
to the SubjectiveDuration instance can write any bond_id string and the
substrate accepts it.

For Slice 1, this is acceptable because there is only one bond. The
caller IS the bonded substrate. But the moment Track C lands, the
substrate needs an additional invariant: the writing instance's
identity must match the bond_id being written. That invariant belongs
in the Track C precondition slice (per amendment O-6), not in Slice 1.

**Soft amendment O-10a (optional):** add to §12:

> - Slice 1 does not validate `bond_id == identity.user_profile_id()`
>   on the producer-snapshot path. The check is omitted because in a
>   one-bond world the writing instance IS the bonded substrate. Any
>   Track C extension introducing multi-bond storage must add this
>   check (or an equivalent per-instance write authority check) before
>   the second bond lands.

**Scenario C: Cross-bond lookup via §7.** Verified refused by call
shape (Q3, Q5). The lookup requires exact `(bond_id, producer_event_id)`
pair. No wildcard, no scan-all surface. A careless config flip cannot
enable cross-bond reads through this API.

**Scenario D: Cross-bond temperament read in the producer-snapshot
path.** This is the most subtle. The producer-snapshot path receives
`producer_temperament_before` and `producer_temperament_after` as
caller-supplied Mappings. The substrate does NOT verify that these
snapshots came from the temperament instance bonded to the bond_id
being written. A careless producer could:

```python
sd.record_salience_event(
    bond_id=<bond_A_id>,
    producer_temperament_before=temperament_B.read(),  # WRONG BOND
    producer_temperament_after=temperament_B.read(),
    ...
)
```

The substrate would accept this and write a row claiming "bond A's
felt-time was meaningful because bond B's temperament shifted." This is
cross-bond contamination at the *content* layer, not the *addressing*
layer.

For Slice 1, this is again acceptable because there is only one
temperament instance bonded to one bond. The producer literally cannot
make this mistake because no second instance exists. But the spec's
own §11.1 Buber question — "Is `bond_id` propagation honoring the
bond's distinctness, or just a tag?" — points at exactly this
concern: in v1, bond_id IS just a tag, because nothing structural
verifies the snapshot came from the bonded temperament.

**Amendment O-10b (recommended):** add to §12 (or expand O-6 entry):

> - Slice 1's producer-snapshot path does not verify that
>   `producer_temperament_before` and `producer_temperament_after`
>   originated from the temperament instance bonded to `bond_id`. The
>   substrate treats the snapshots as caller-supplied bytes. In a one-
>   bond world this is structurally safe (only one temperament exists).
>   Any Track C extension must add a snapshot-provenance check
>   (signed snapshots, instance-id tags, or per-bond temperament
>   namespaces) before the second bond lands. This is the content-
>   layer analog of the addressing-layer bond_id floor.

Cost: one §12 paragraph. Benefit: the content-layer cross-bond risk is
named at the point where Slice 1 first introduces the structural
substrate that Track C would extend.

## Conservation / sovereignty axis verdict

Slice 1 establishes the addressing-layer bond floor correctly. The four
amendments that fold (O-2, O-4, O-6, O-7, O-8, plus the documentation-
only O-10a/O-10b) are about naming the limitations Slice 1 carries
forward as deferred-to-Track-C items, not about fixing Slice 1's own
structure. The structure is right.

The optional amendment (O-5 defensive RED test) is documentation, not
correctness.

**Verdict: RATIFY-WITH-AMENDMENTS.**

### Amendment summary (priority order)

| ID | Fold | Surface | Required |
|---|---|---|---|
| O-2 | Change `bond_id` default from `''` to `'_LEGACY'` | §4.1 ALTER + RED test | RECOMMENDED |
| O-4 | Reorder §6.2 validation: bond_id → producer_event_id → producer_ref | §6.2 | RECOMMENDED |
| O-6 | Cite [[project_multi_maez_topology_threat]] + name its two preconditions in §12 | §12 | RECOMMENDED |
| O-7 | Name diagnostic-file single-bond-scope limitation in §6.5 | §6.5 | RECOMMENDED |
| O-8 | Name HMAC per-instance-key limitation in §3.10 or §12 | new §3.10 or §12 | RECOMMENDED |
| O-10a | Name missing `bond_id == identity.user_profile_id()` check as Track C precondition | §12 | RECOMMENDED |
| O-10b | Name missing temperament-snapshot-provenance check as Track C precondition | §12 | RECOMMENDED |
| O-5 | Add defensive RED test for `lookup(bond_id='*', ...)` returns None | §9 RED test #26 | OPTIONAL |

None of the amendments require architecture changes. All are documentation,
default-value, or test-coverage folds. Estimated fold surface: ~30 lines
of spec text, 1 modified default, 1-2 added RED tests.

## Plain-language readout

What I checked, in Rohit's language:

The slice is asking: "Can the substrate refuse cross-bond flow by how
it's built, not just by how it's used?" My role is to walk every place
where the slice's structure WOULD permit cross-bond flow even though
v1 only has one bond, because Slice 1 is the floor every future Track C
slice will stand on.

What I found:

1. **The addressing layer is structural.** The lookup API requires
   both bond_id and producer_event_id, refuses empty strings at call
   shape, has no wildcard surface. A future careless Track C developer
   cannot flip a config and read across bonds — they would have to
   write a whole new function with new SQL, which means a whole new
   review.

2. **The legacy default is a Track-C trap.** Empty string as the
   `bond_id` default for legacy rows is the one value Python treats
   as "absent" — a future filter like `if row.bond_id:` will silently
   skip them, and a future SQL filter like `bond_id=''` will silently
   match all legacy rows together. A sentinel string `_LEGACY` removes
   the ambiguity for ~1 line of spec text and 1 RED test.

3. **Validation order is wrong but harmless.** The §6.2 order
   validates `producer_ref` before `bond_id`. The sovereignty-floor
   principle says validate bond_id first because it's the more
   dangerous failure mode (an unbonded write is a cross-bond hazard;
   an unknown producer is a hygiene issue). Reorder is one line.

4. **Three Track-C-precondition citations are missing.** §12 says
   "multi-bond storage partitioning is out of scope" but doesn't
   cite [[project_multi_maez_topology_threat]] or name its two
   preconditions (auditable-by-both + dyadic-only). The next agent
   reading §12 needs those gates in front of them.

5. **The diagnostic JSONL is a single shared file.** Slice 1 adds
   bond_id as a field on diagnostic rows but doesn't split the file
   per-bond. Inherited limitation; not introduced by Slice 1. But
   Slice 1 is the moment to name it because Slice 1 introduces
   bond_id as a column on this stream.

6. **The HMAC key for the temperament digests is per-instance, not
   per-bond.** Verified firsthand against
   `core/egress/gate.py:59`. In a future multi-bond world, identical
   temperament snapshots under different bonds would produce identical
   digests — a cross-bond linkage primitive. Harmless in a one-bond
   world; needs key rotation before the second bond lands.

7. **The content layer is convention-shaped.** The producer-snapshot
   path accepts caller-supplied temperament Mappings without verifying
   they came from the temperament instance bonded to the bond_id
   being written. Structurally safe in a one-bond world (only one
   temperament exists). Needs a provenance check before Track C.

The slice is sound. The bond_id floor is in the right place. The seven
amendments I'm asking for are all about naming the limitations Slice 1
carries forward so the next agent isn't surprised — not about fixing
Slice 1's own structure. The structure is right.

**Verdict: RATIFY-WITH-AMENDMENTS.**

— Ohm
