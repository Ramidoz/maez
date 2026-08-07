# S7 action binding — design v2

Status: **DRAFT — awaiting ratification. No REDs, no code until ratified.**

Origin: the CUDA cutover slice needed a tap that authorizes *this exact
operation*. It discovered that S7 does not bind the action at all. The
owner ruled the substrate be fixed rather than compensated around, which
is right — this is S7's core job, not cutover polish.

---

## The defect

`execution_grant_authorizes_action`
([operator_user_boundary.py:2695](/home/rohit/maez/core/governance/operator_user_boundary.py#L2695))
compares exactly two things:

```python
grant.derived_work_class == derived
and grant.action_params_hash == canonical_hash(params or {})
```

**Neither carries the action.** Reproduced:

| action | derived class | params hash |
|---|---|---|
| `model_routing.cutover_cuda` | `self_modification` | identical |
| `model_routing.wipe_and_replace` | `self_modification` | identical |

So one grant authorizes **every sibling operation of the same class with
the same params**. Nothing in `WorkRequestEnvelope`,
`RenderedRequestStatement`, `S7AuthorizationArtifact`, the durable row,
or `S7ExecutionGrant` records which action was signed.

**What this means in the owner's terms:** a tap for *"switch to CUDA"* is
a tap for *"some self-modification with these arguments."* BAD promises
*exact-request authorization grammar*
([BETA_ARCHITECTURE_DECISIONS.md:2780](/home/rohit/maez/docs/governance/BETA_ARCHITECTURE_DECISIONS.md#L2780));
this does not meet that promise.

## The ruling

**Option 1: versioned, first-class action binding.** Not a new opaque
hash (option 2 — smaller but weaker for *what you see is what you sign*),
and not cutover-only compensation (option 3 — rejected for this
ceremony).

## What the action must traverse

The exact action string travels, end to end, with no inference anywhere:

| carrier | change |
|---|---|
| `WorkRequestEnvelope` | carries `action` (it already receives one; it must **retain** it) |
| rendered signed text | the action is **visible**, not merely hashed |
| `S7AuthorizationArtifact` | new `action` field |
| durable row | new `action` column |
| `S7ExecutionGrant` | new `action` field |
| source-bundle binding | includes the action |
| grant projection | includes the action |

**Visibility is a requirement, not a nicety.** A hash alone cannot
satisfy *what you see is what you sign*: the human tapping the key must
be able to read which operation they are authorizing.

## The edge

```python
grant.action == action
and grant.derived_work_class == derived
and grant.action_params_hash == canonical_hash(params or {})
```

Exact string equality, added to — never replacing — the existing two.

**Binding RED (generic, not cutover-specific):** a grant minted for
`model_routing.cutover_cuda` **refuses** every sibling `model_routing.*`
action with identical params, at the generic S7 execution edge.

## Versioning, explicitly

* the artifact/grant schema **version bumps**; the change is never
  silent;
* `action_params_hash` is **not** reinterpreted — its meaning is
  unchanged, and the action is bound separately;
* historical rows are **never overwritten** and never backfilled.

### Historical artifacts

Verified read-only: the live store holds **four** artifact rows, all
`founder_credential_management`, all expired between 2026-07-08T02:10 and
14:27, three consumed and one unconsumed-but-expired. **No current
authorization needs preserving.**

Rules:

* v1 rows remain **readable and auditable**;
* a missing action is **never inferred or backfilled** — absence is a
  fact about the record, and manufacturing one would be the fabrication
  this project refuses;
* a v1 row **cannot authorize new guarded execution**. It fails closed at
  the edge because it cannot satisfy exact action equality.

*(Note: `ceremony.sqlite3.pre-backfill.bak` exists beside the live store,
so a backfill has happened here before. That is a further reason to state
the no-backfill rule explicitly rather than assume it.)*

## Safety of the build

* build and migration tests run against **store copies**;
* **the live S7 store is untouched** until this slice is separately
  reviewed and authorized;
* no credential is enrolled, disabled, or re-enabled by this work.

## What remains in the cutover afterwards

The cutover-local `cutover_action` params check **stays**, as a second
rail. It is no longer the source of authority — S7 is — and the design
must describe it that way.

## Sequence

1. this design + ADR/BAD amendment (**here**);
2. RED the generic sibling-action bypass at the S7 edge;
3. implement and gate the versioned change across **every** mint and
   consume path;
4. return to cutover 2B and update its receipt projection from the final
   grant shape;
5. complete 2B RED gaps 2–5 before any consumer implementation.

---

## Frozen schema identities (v2)

"Schema version bumps" was not implementable: `WorkRequestEnvelope` uses
the shared `s7.v1`, the artifact and grant carry **no version field at
all**, and the renderer is `s7.rendered_request.v1`. Frozen:

| carrier | v1 identity | v2 identity | v2 adds |
|---|---|---|---|
| envelope | `s7.v1` (shared) | `s7.work_request_envelope.v2` | `action` retained, not discarded |
| rendered statement | `s7.rendered_request.v1` | `s7.rendered_request.v2` | visible `Action:` line |
| authorization artifact | *(unversioned)* | `s7.authorization_artifact.v2` | `action` field + explicit version |
| durable row | *(unversioned)* | `s7_authorization_artifacts_v2` | `action` column + `schema_version` |
| execution grant | *(unversioned)* | `s7.execution_grant.v2` | `action` field + explicit version |
| voice source bundle | current binding | v2 binding | action in the bound preimage |
| cutover grant projection | `…grant_projection.v1` | `…grant_projection.v2` | `action` in the projected fields |

v1 records stay decodable **for audit** and are structurally unable to
authorize: they have no action to satisfy exact equality with, and the
absence is never filled in.

## The database transition

`S7AuthorizationStore.__init__` creates directories, runs `executescript`,
`ALTER TABLE`s and commits
([operator_user_boundary.py:2413](/home/rohit/maez/core/governance/operator_user_boundary.py#L2413)).
**Putting a v2 migration there would rewrite the live store merely by
opening it** — precisely what this design forbids elsewhere.

Frozen: a **separate v2 table**, `s7_authorization_artifacts_v2`, not an
in-place alter. Coexistence is by distinct table, which is auditable
without tagging every row.

**Migration is a separately owner-authorized entrypoint**, never a
side effect of construction:

* **idempotent** — re-running changes nothing;
* **transactional** — any failure rolls back whole; no partial table;
* **refuses a partial or future schema** rather than repairing it;
* **cross-version nonce collisions refuse** — a nonce present in v1 may
  not be reused in v2;
* **no historical-row backfill**, ever. The `ceremony.sqlite3.pre-backfill.bak`
  beside the live store proves a backfill has happened here before, which
  is why this is a rule and not an assumption.

## The complete authority join

```
envelope.action
  == rendered.action
  == artifact.action
  == committed row.action
  == grant.action
  == runtime action
```

Two further requirements, because equality alone is not enough:

* **consumption matches the stored action in its atomic SQL**, and mints
  the grant **from the matched row** — never from an unchecked caller
  value. A grant whose action came from the caller would bind nothing.
* the **source bundle binds the same action**.

Each link carries its own mutation-killing RED.

## S1 — RULED: where the action renders

An exact metadata line, **after `Request id` and before `Work class`**:

```
Action: model_routing.cutover_cuda
```

Exact literal, no truncation, no summarising. The renderer version bumps
with it.

## S2 — ENUMERATED (not promised)

Scanned rather than assumed. Every site that must pass the action
through, and structurally pin it:

**Envelope producers (6)**
`core/evolution/dream_state.py:1054`, `:1132`;
`core/governance/s7_webauthn_ceremony.py:61`, `:101`;
`core/governance/operator_user_boundary.py:2933`;
`core/decision/decision_pipeline.py:1069`.

**Artifact / grant mints (4)**
`s7_guarded_execution.py:2291` (`mint_authorization_artifact`);
`s7_webauthn_ceremony.py:659` (`S7AuthorizationArtifact(`), `:682`;
`operator_user_boundary.py:2393` (`S7ExecutionGrant(`).

**Consumption / action edges (7)**
`s7_webauthn_ceremony.py:886`;
`operator_user_boundary.py:2524`, `:2541` (`consume_for_execution`),
`:2695` (`execution_grant_authorizes_action`),
`:2726` (`consume_execution_grant_for_action`),
`:2744` (`execution_grant_authorizes_card_transition`);
`dream_state.py:1182`; `decision_pipeline.py:1566`.

**The finding this enumeration produced:** `consume_for_execution` has
**four** callers and mints grants **without** consulting the action
helper, and `execution_grant_authorizes_card_transition` is a **second**
edge. Changing only `execution_grant_authorizes_action` — the obvious
single-site fix — would have left both bypasses open.

## RED contract

* a **v1 record refuses** new guarded execution (audit-only);
* a **v2 grant refuses every sibling** `model_routing.*` action with
  identical params, **at the generic edge**;
* the action is **visible** in the rendered statement, exact and
  untruncated;
* **malformed or missing** action refuses, never defaults;
* migration is **idempotent** and **rolls back** whole on failure;
* the **live store is byte- and metadata-identical** throughout testing —
  asserted, not assumed.

## Carried

* **S3** — `consume_for_execution`'s four callers each need the action
  threaded from their own authority material. Whether they all *have* an
  action to thread is not yet established, and assuming they do is how
  this class of bug started.
