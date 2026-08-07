# S7 action binding — design v5

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

## S2 — ENUMERATED, CORRECTED (v3)

**v2's "complete map" was not complete, and the way it failed matters
more than the misses.** I scanned `--include=*.py core/ scripts/`. The
**`daemon/` tree was never in scope** — and the daemon is the *live*
path. I then wrote "enumerated rather than promised" and called the
allowlist complete. That is the same error as the credential search that
misled the owner: a search whose scope excluded the answer, reported as a
finding.

**v4's inventory contradicted itself.** Its headings totalled 30, the
listed references exceeded that, and the RED contract still pinned 22 —
three different numbers for one map, because I hand-counted a list I had
hand-assembled. The RED contract also demanded five caller joins *after*
`consume_verified` had been correctly reclassified as a row ↔ rendered
join, so it required a proof the design had just removed.

**Derived mechanically (v5)** by AST walk over every tracked production
file, emitting exact `(file, function, role, syntactic role)` tuples.
Counts come from the table, not from me:

| file | function | role | syntactic role |
|---|---|---|---|
| `core/actions/action_engine.py` | `_s7_invocation_gate` | execution_edge | call:consume_execution_grant_for_action |
| `core/decision/decision_pipeline.py` | `_consume_s7_execution_authorization` | durable_writer | call:consume_for_execution |
| `core/decision/decision_pipeline.py` | `_on_approve` | execution_edge | call:execution_grant_authorizes_card_transition |
| `core/decision/decision_pipeline.py` | `_s7_request_envelope_for_card` | producer | call:build_work_request_envelope |
| `core/decision/pending_cards.py` | `approve_and_mark_running` | execution_edge | call:execution_grant_authorizes_card_transition |
| `core/evolution/dream_state.py` | `_consume_s7_execution_authorization_for_envelope` | durable_writer | call:consume_for_execution |
| `core/evolution/dream_state.py` | `build_apply_s7_envelope` | producer | call:build_work_request_envelope |
| `core/evolution/dream_state.py` | `build_section_edit_s7_envelope` | producer | call:build_work_request_envelope |
| `core/governance/operator_user_boundary.py` | `_mint_s7_execution_grant` | constructor | call:S7ExecutionGrant |
| `core/governance/operator_user_boundary.py` | `_mint_s7_execution_grant` | constructor | definition |
| `core/governance/operator_user_boundary.py` | `build_brain_swap_work_request_envelope` | producer | call:build_work_request_envelope |
| `core/governance/operator_user_boundary.py` | `build_work_request_envelope` | producer | definition |
| `core/governance/operator_user_boundary.py` | `consume_execution_grant_for_action` | execution_edge | call:execution_grant_authorizes_action |
| `core/governance/operator_user_boundary.py` | `consume_execution_grant_for_action` | execution_edge | definition |
| `core/governance/operator_user_boundary.py` | `consume_for_execution` | constructor | call:_mint_s7_execution_grant |
| `core/governance/operator_user_boundary.py` | `consume_for_execution` | durable_writer | definition |
| `core/governance/operator_user_boundary.py` | `consume_verified` | durable_writer | call:consume_for_execution |
| `core/governance/operator_user_boundary.py` | `execution_grant_authorizes_action` | execution_edge | definition |
| `core/governance/operator_user_boundary.py` | `execution_grant_authorizes_card_transition` | execution_edge | call:execution_grant_authorizes_action |
| `core/governance/operator_user_boundary.py` | `execution_grant_authorizes_card_transition` | execution_edge | definition |
| `core/governance/operator_user_boundary.py` | `render_request_statement` | renderer | call:RenderedRequestStatement |
| `core/governance/operator_user_boundary.py` | `render_request_statement` | renderer | definition |
| `core/governance/s7_guarded_execution.py` | `_bundle_matches_expected_hash_binding` | validator | definition |
| `core/governance/s7_guarded_execution.py` | `derive_s7_voice_source_bundle_hash_binding` | source_bundle | call:S7VoiceSourceBundleHashBinding |
| `core/governance/s7_guarded_execution.py` | `derive_s7_voice_source_bundle_hash_binding` | source_bundle | definition |
| `core/governance/s7_guarded_execution.py` | `get_for_source_ref` | source_bundle | call:S7VoiceConsultationBundle |
| `core/governance/s7_guarded_execution.py` | `mint_authorization_artifact` | constructor | definition |
| `core/governance/s7_guarded_execution.py` | `mint_authorization_artifact` | durable_writer | call:put_artifact_with_bundle_reservation |
| `core/governance/s7_guarded_execution.py` | `persist_s7_voice_source_bundle_for_material` | source_bundle | call:S7VoiceConsultationBundle |
| `core/governance/s7_guarded_execution.py` | `persist_s7_voice_source_bundle_for_material` | source_bundle | call:derive_s7_voice_source_bundle_hash_binding |
| `core/governance/s7_guarded_execution.py` | `put_artifact_with_bundle_reservation` | durable_writer | definition |
| `core/governance/s7_guarded_execution.py` | `validate_s7_voice_source_bundle` | validator | call:_bundle_matches_expected_hash_binding |
| `core/governance/s7_webauthn_ceremony.py` | `_consume_backup_registration_authorization` | durable_writer | call:consume_for_execution |
| `core/governance/s7_webauthn_ceremony.py` | `authorize_finish` | constructor | call:S7AuthorizationArtifact |
| `core/governance/s7_webauthn_ceremony.py` | `authorize_finish` | constructor | call:mint_authorization_artifact |
| `core/governance/s7_webauthn_ceremony.py` | `build_backup_registration_envelope` | producer | call:build_work_request_envelope |
| `core/governance/s7_webauthn_ceremony.py` | `build_disable_credential_envelope` | producer | call:build_work_request_envelope |
| `daemon/maez_daemon.py` | `_s7_authorization_route_material` | renderer | call:render_request_statement |
| `daemon/maez_daemon.py` | `_s7_disable_credential_for_proof` | durable_writer | call:consume_for_execution |
| `daemon/maez_daemon.py` | `_s7_disable_credential_for_proof` | execution_edge | call:consume_execution_grant_for_action |
| `daemon/maez_daemon.py` | `_s7_voice_source_validation_for_material` | source_bundle | call:derive_s7_voice_source_bundle_hash_binding |

**Counts, derived mechanically:** constructor 6, durable_writer 8, execution_edge 9, producer 7, renderer 3, source_bundle 6, validator 2 — **total 41**.

**Four caller joins**, not five: `consume_verified` is the row ↔ rendered
join and is counted there, not among the callers.

**A further finding from the corrected scan:**
`daemon/maez_daemon.py:1056` constructs
`s7.S7AuthorizationStore(store.db_path)` **inline, on the live request
path** — and that constructor creates, `ALTER`s and commits. The live
daemon therefore already migrates the store merely by handling a request.
Any v2 migration placed in that constructor would run **from the
daemon**, unauthorized. This is why "normal opening is verification-only"
must be enforced, not merely stated.

## S3 — ANSWERED (v3), not carried

Each consumer has an authoritative action; none needs inventing:

| consumer | authoritative action |
|---|---|
| decision pipeline | `card.action` |
| dream state | reconstructed `envelope.action` |
| backup registration | fixed `register_backup_webauthn_credential` |
| credential disable | fixed `disable_founder_webauthn_credential` |
| `consume_verified` | **stored-row action ↔ `rendered.action`** — see below |

**`consume_verified` is NOT a caller join.** v3 listed its caller action
as `rendered.action` and its rendered action as `rendered.action` — a
tautology proving nothing. It is correctly classified as a **stored-row ↔
rendered** join: the committed row's action must equal the rendered
statement's, and neither is supplied by the caller. Reclassified rather
than dressed up.

**Frozen join per caller:** caller-action **==** rendered-action, each
with its own mutation-killing RED. Carrying S3 into implementation would
have meant deciding this while writing code, which is how the original
defect arrived.

## Action grammar

`Action: <literal>` raw is unsafe: a newline or control character in the
literal injects metadata into the signed statement the human reads.

**v3's grammar closed four roads already in use** — worse than reported,
it also refused `run_shell` and `backup_status`. I froze a dotted-suffix
form from the single action I cared about and never tested it against the
actions S7 already carries:

| action | v3 grammar |
|---|---|
| `write_soul_note` | **REFUSED** |
| `edit_soul_section` | **REFUSED** |
| `register_backup_webauthn_credential` | **REFUSED** |
| `disable_founder_webauthn_credential` | **REFUSED** |
| `run_shell` | **REFUSED** |
| `backup_status` | **REFUSED** |
| `model_routing.cutover_cuda` | pass |

Frozen instead — dotted segments **optional**, so established undotted
actions remain valid:

```
^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)*$
```

* length bounded at 128 bytes UTF-8;
* anything else **refuses at construction** — never escaped, never
  truncated, never rendered. An escaped action is still one the human
  must decode, and *what you see is what you sign* requires they not
  have to.

**Boundary REDs:** every action literal S7 currently uses passes; a
newline, a control character, a leading dot, a trailing dot, a double
dot, an empty segment, uppercase, and a 129-byte literal each refuse.

Refusing beats escaping here: an escaped action is still an action the
human must decode, and *what you see is what you sign* requires that they
not have to.

## Voice bundle and projection identities (v3)

v2 wrote "current binding → v2 binding", which is a placeholder. Frozen:

| carrier | identity | fields | hash domain | decoder routing |
|---|---|---|---|---|
| voice source bundle | `s7.voice_source_bundle.v2` | v1 fields **+ `action`** | `s7.voice_source_bundle.v2` | v1 decodes audit-only; v2 required for execution |
| cutover grant projection | `cuda_migration.s7_execution_grant_projection.v2` | the 15 grant fields **+ `action`** = 16 | `…projection.v2` | v1 projection is audit-only |

## The database transition, concrete (v3)

**Exact v2 DDL** — literal, no placeholder:

```sql
CREATE TABLE IF NOT EXISTS s7_authorization_artifacts_v2 (
    artifact_id TEXT PRIMARY KEY,
    request_id TEXT NOT NULL,
    request_envelope_hash TEXT NOT NULL,
    rendered_text_hash TEXT NOT NULL,
    action_params_hash TEXT NOT NULL,
    precondition_hash TEXT NOT NULL,
    authority_context_hash TEXT NOT NULL,
    derived_work_class TEXT NOT NULL,
    derived_aggregation_group TEXT NOT NULL,
    nonce TEXT NOT NULL UNIQUE,
    credential_ref TEXT NOT NULL,
    auth_method TEXT NOT NULL,
    grant_source TEXT NOT NULL,
    user_presence INTEGER NOT NULL,
    user_verification INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    consumed_at TEXT,
    consumed_by_request_id TEXT,
    ceremony_kind TEXT NOT NULL DEFAULT 'founder_local_webauthn',
    action TEXT NOT NULL,
    schema_version TEXT NOT NULL DEFAULT 's7.authorization_artifact.v2'
);
CREATE UNIQUE INDEX IF NOT EXISTS s7_v2_nonce
    ON s7_authorization_artifacts_v2(nonce);
```

The first twenty columns are the v1 definitions verbatim, read from the
live store's `sqlite_master` rather than transcribed from memory.

**Fingerprint preimage:** canonical JSON of
`[(cid, name, type, notnull, dflt_value, pk) …]` from
`PRAGMA table_info(s7_authorization_artifacts_v2)` plus
`[(name, unique, origin) …]` from `PRAGMA index_list(…)`, both sorted by
name, hashed with the project canonical encoder. The resulting literal is
pinned once the table exists; drift refuses.

**Migration receipt** — schema `s7.migration_receipt.v1`, fields:
`from_fingerprint`, `to_fingerprint`, `row_count_v1`, `row_count_v2`,
`started_at`, `completed_at`, `store_dev`, `store_ino`. Bound by the
project canonical wrapper. **Published by the `s7-migrate-v2` command
only**, durably beside the store as `s7_migration_receipt.json`, written
through the anchored `write_private_file` primitive. No row contents ever
appear in it.

**Schema fingerprint:** canonical hash over `PRAGMA table_info` +
`PRAGMA index_list` for the v2 table, pinned as a literal; drift refuses.

**Routing:** v1 table is **audit-only** — readable, never written, never
consumable. v2 is the only writable and consumable table.

**Migration is an owner-authorized command**, `s7-migrate-v2`, which:

* mints a **durable migration receipt** (from/to fingerprints, row
  counts, timestamp, no row contents);
* is **idempotent** — a second run is a no-op and says so;
* is **transactional** — any failure rolls back whole, leaving no partial
  table;
* **refuses** a partial or future schema rather than repairing it;
* **rejects atomically** on cross-table collision of **either** `nonce`
  **or** `artifact_id`;
* **never backfills** a historical row.

**Before activation:** if the v2 table is **absent**, every guarded
execution path **refuses** — it does not silently fall back to v1. Absent
is not permission.

**Activation has ONE durable linearization point: the migration
receipt.** Creating the table does **not** activate v2. Until the receipt
exists and verifies, v2 is inert and guarded execution refuses. Otherwise
a half-finished migration — table present, rows not moved — would look
like an activated system.

**Cross-version collision rejection applies to EVERY v2 insert**, not
only to migration. A nonce or `artifact_id` present in the v1 table may
never be written to v2, at any time, by any path. Restricting the check
to migration would leave the collision reachable the moment normal
minting resumed.

**Legacy writes are stopped IN THE DATABASE, not by policy (v5).**

v4 said an old daemon "must not" continue writing v1, enforced by the
migration command refusing while the store is held and by the daemon
declining once a receipt exists. **Both are unenforceable.** A pre-v2
daemon cannot know a v2 receipt exists — it has no code that looks — and
merely having SQLite open does not necessarily hold a detectable lock. I
recorded that as an accepted residual; it is not acceptable for the layer
that authorizes changing Maez's brain.

Frozen: **migration installs triggers that make every legacy v1 write
fail**, so an old daemon fails loudly at the database rather than
silently continuing:

```sql
CREATE TRIGGER s7_v1_frozen_insert BEFORE INSERT ON s7_authorization_artifacts
BEGIN SELECT RAISE(ABORT, 's7_v1_frozen'); END;
CREATE TRIGGER s7_v1_frozen_update BEFORE UPDATE ON s7_authorization_artifacts
BEGIN SELECT RAISE(ABORT, 's7_v1_frozen'); END;
CREATE TRIGGER s7_v1_frozen_delete BEFORE DELETE ON s7_authorization_artifacts
BEGIN SELECT RAISE(ABORT, 's7_v1_frozen'); END;
```

v1 stays **readable** for audit and becomes **unwritable** for everyone,
including code that has never heard of v2. The offline
stop/witness/deploy/restart ceremony remains the operational procedure,
but it is no longer what the guarantee rests on.

**Cross-version exclusion is atomic, not check-then-insert (v5).** A
`SELECT`-then-`INSERT` is raceable. Frozen as triggers on the v2 table,
evaluated inside the insert's own transaction:

```sql
CREATE TRIGGER s7_v2_no_v1_nonce BEFORE INSERT ON s7_authorization_artifacts_v2
WHEN EXISTS (SELECT 1 FROM s7_authorization_artifacts WHERE nonce = NEW.nonce)
BEGIN SELECT RAISE(ABORT, 's7_cross_version_nonce'); END;
CREATE TRIGGER s7_v2_no_v1_artifact BEFORE INSERT ON s7_authorization_artifacts_v2
WHEN EXISTS (SELECT 1 FROM s7_authorization_artifacts WHERE artifact_id = NEW.artifact_id)
BEGIN SELECT RAISE(ABORT, 's7_cross_version_artifact'); END;
```

Migration itself runs in a single `BEGIN IMMEDIATE` transaction.

## Voice-bundle persistence, concrete (v5)

v4 left this a sketch while the authorization table was fully pinned, so
the original migration hazard survived on the *evidence* plane. The
existing `s7_voice_consultation_bundles` auto-creates and auto-`ALTER`s an
unversioned table.

**Exact v2 DDL** — the 25 v1 columns verbatim (read from
`s7_guarded_execution.py:983`) plus two, **27 total**:

```sql
CREATE TABLE IF NOT EXISTS s7_voice_source_bundles_v2 (
    source_ref_hash TEXT PRIMARY KEY,
    request_id TEXT NOT NULL, consultation_id TEXT NOT NULL,
    request_envelope_hash TEXT, rendered_text_hash TEXT,
    action_params_hash TEXT, precondition_hash TEXT,
    authority_context_hash TEXT, maez_voice_consultation_hash TEXT,
    rendered_prompt_ref TEXT, rendered_prompt_hash TEXT,
    mutation_preview_hash TEXT, rollback_plan_ref TEXT,
    context_manifest_ref TEXT, context_manifest_hash TEXT,
    runtime_identity_hash TEXT, model_routing_identity_hash TEXT,
    model_config_hash TEXT, raw_response_ref TEXT, raw_response_hash TEXT,
    semantic_reader_attempt_hash TEXT, expires_at TEXT,
    authority_class TEXT, has_grounded_semantic_blocking_signal INTEGER,
    source_bundle_hash TEXT,
    action TEXT NOT NULL,
    schema_version TEXT NOT NULL DEFAULT 's7.voice_source_bundle.v2'
);
CREATE UNIQUE INDEX IF NOT EXISTS s7_vb_v2_src
    ON s7_voice_source_bundles_v2(source_ref_hash);
```

**APIs, frozen:**

```
put_voice_source_bundle_v2(*, bundle, action, conn) -> None   # v2 ONLY
read_voice_source_bundle(*, source_ref_hash, conn)
    -> (bundle, version)        # reads BOTH, tags the version
validate_voice_source_bundle(*, bundle, version, purpose)
    -> bool                     # purpose="audit" accepts v1;
                                # purpose="execution" refuses v1
```

**Same freezes as the authorization plane:** v1 write-frozen by trigger,
never backfilled, never migrated on open, its own fingerprint, its own
receipt entry.

## Fingerprint literals (v5)

v4 gave a recipe and no value. Computed deterministically from the frozen
DDL above — preimage is canonical JSON of `PRAGMA table_info`,
`PRAGMA index_list`, **and `PRAGMA index_info` per index** (so index
columns, expressions and partial predicates participate; v4's preimage
omitted them), sorted, hashed with SHA-256:

| table | fingerprint |
|---|---|
| `s7_authorization_artifacts_v2` | `0c2c2268087736a00e32ded1165f82ed16d83e119ed3de2cc533f9e5d9ebc614` |
| `s7_voice_source_bundles_v2` | `45b8e1778692f5297d4d6ad64cf888e86f267ac0877562db05336a1ee0dc0b9b` |

Either differing refuses.

## Activation ordering, frozen (v5)

```
1. BEGIN IMMEDIATE
2. create both v2 tables + indexes + all triggers
3. copy nothing  (no backfill)
4. COMMIT
5. fsync the database AND its parent directory
6. publish the migration receipt          <- THE linearization point
```

The receipt binds **both** tables. Schema `s7.migration_receipt.v1`:

```
from_fingerprint_auth, to_fingerprint_auth,
from_fingerprint_bundle, to_fingerprint_bundle,
row_count_v1_auth, row_count_v1_bundle,
started_at, completed_at, store_dev, store_ino
```

canonically wrapped by the project encoder, published only by
`s7-migrate-v2` through `write_private_file`. No row contents ever.

**Every activation consumer revalidates** before treating v2 as live:
the receipt's bytes decode canonically, **both** fingerprints match the
live tables, and `store_dev`/`store_ino` match the store it is actually
holding. A receipt naming a different store activates nothing.

**Normal store opening is verification-only.** It may read and verify a
fingerprint; it may **never** create, alter, migrate or commit. Enforced
structurally, given `daemon/maez_daemon.py:1056` already constructs the
mutating store on the live request path.

## RED contract

**Joins** — one mutation-killing RED per link:
envelope==rendered, rendered==artifact, artifact==row, row==grant,
grant==runtime; plus each of the five caller-action==rendered-action
joins from S3.

**Routes** — every one of the 22 enumerated sites is structurally pinned;
adding a 23rd unpinned site fails.

**Refusals**
* an **unexpired v1** record still refuses new guarded execution — not
  merely an expired one, which would pass for the wrong reason;
* a v2 grant **refuses every sibling** `model_routing.*` action with
  identical params, at the **generic** edge;
* **malformed or missing** action refuses, never defaults;
* an action failing the grammar refuses **at construction**;
* the v2 table **absent** refuses; no fallback to v1.

**Migration**
* idempotent; a fault **injected mid-migration rolls back whole**;
* partial and future schemas refuse;
* cross-version **nonce** and **artifact_id** collisions both refuse
  atomically.

**Invariance**
* credential rows and **sign counts unchanged** by any of this;
* the live DB and its sidecars are **externally measured** identical
  before and after every test — content hash, size, `mtime_ns`,
  `dev`/`ino`, **mode, uid, gid, link count**, the **complete sidecar
  set** (`-journal`, `-wal`, `-shm`, `.bak`), and the **parent
  directory's entry list** — taken outside the process under test rather
  than by the code being tested. A new sidecar or a changed mode is a
  write.

## Carried

Nothing. S1, S2 and S3 are all ruled or enumerated. The remaining work is
REDs, then implementation.
