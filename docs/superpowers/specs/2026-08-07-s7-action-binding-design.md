# S7 action binding — design v4

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

Re-scanned repo-wide, and **separated by ROLE** — v3 mixed definitions,
constructors and callers in one list, which is why it read as complete
while missing bridges.

**Producers — build the envelope (6)**
`dream_state.py:1054`, `:1132`; `s7_webauthn_ceremony.py:61`, `:101`;
`operator_user_boundary.py:2933`; `decision_pipeline.py:1069`.

**Renderers (2)**
`operator_user_boundary.py:4071` (definition, `:4137` construction);
`daemon/maez_daemon.py:580`.

**Constructors — mint artifact/grant (5)**
`s7_guarded_execution.py:2291`; `s7_webauthn_ceremony.py:659`, `:682`;
`operator_user_boundary.py:2393` (`S7ExecutionGrant(`);
**`operator_user_boundary.py:2637`** ← the actual mint CALL
(`_mint_s7_execution_grant`), missed by v3 which listed only the class
construction.

**Source-bundle construction / round-trip (5)** — v3 listed none of these
`s7_guarded_execution.py:604` (`S7VoiceSourceBundleHashBinding(`),
`:666` (`derive_…_hash_binding`), `:703`, `:1389`
(`S7VoiceConsultationBundle(`);
`daemon/maez_daemon.py:628`; `decision_pipeline.py:1211`.

**Validators (1)**
**`s7_guarded_execution.py:1839`** (`_bundle_matches_expected_hash_binding`)
← the source-bundle validation join, missed by v3.

**Durable writers / consumers (5)**
`dream_state.py:1182`; `s7_webauthn_ceremony.py:886`;
`operator_user_boundary.py:2524`, `:2541`; `decision_pipeline.py:1566`;
`daemon/maez_daemon.py:1056`.

**Execution edges (4)**
`operator_user_boundary.py:2695`, `:2726`, `:2744` (definitions);
`action_engine.py:616`; `daemon/maez_daemon.py:1070`.

**Card-transition callers (2)**
`decision_pipeline.py:1875`; `pending_cards.py:851`.

Each role gets its **own** structural allowlist. A site added to any role
without being pinned fails.

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

**Deployment ordering:** an old daemon must not continue writing v1
during activation. The migration command refuses while any process holds
the store, and the daemon refuses to serve guarded paths once the receipt
exists but its own build predates v2. Two writers of different vintages
is the one failure this design cannot detect after the fact.

## Voice-bundle persistence (v4)

Its store has the **same defect**: it auto-creates and auto-`ALTER`s an
unversioned table. Frozen on the same pattern:

* separate physical storage — `s7_voice_source_bundles_v2`;
* v1 rows **audit-readable**, structurally unable to mint v2 authority;
* **writer** routes only to v2; **decoder** reads both and tags the
  version; **validator** accepts v1 for audit and refuses it for
  execution;
* its own fingerprint and its own entry in the migration receipt;
* the same never-backfill and never-migrate-on-open rules.

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
