# S7 action binding — design v18 (R7 RULED — implementing)

*v16 ratified; v17 split the two activation authorities; v18 froze the
evidence ordering. Both amendments are in the body below.*

Status: **RATIFIED 2026-08-07. R7 and scope both RULED by the owner.
REDs written; implementation cleared.**

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

**Derived mechanically (v7)**, now with **line-level occurrence
identity**. v6 keyed on `(file, function, role, syntactic role)`, which
**collapses multiplicity**: `_s7_voice_consultation_for_card` calls
`work_request_envelope_hash` twice (`decision_pipeline.py:1152` and
`:1178`) and the table recorded **one** row — so one branch could stay
unwired without the allowlist noticing. Both now appear.

| file | function | role | syntactic role | line |
|---|---|---|---|---|
| `core/actions/action_engine.py` | `_s7_invocation_gate` | execution_edge | call:consume_execution_grant_for_action | 616 |
| `core/decision/decision_pipeline.py` | `_consume_s7_execution_authorization` | durable_writer | call:consume_for_execution | 1566 |
| `core/decision/decision_pipeline.py` | `_on_approve` | execution_edge | call:execution_grant_authorizes_card_transition | 1875 |
| `core/decision/decision_pipeline.py` | `_s7_request_envelope_for_card` | producer | call:build_work_request_envelope | 1069 |
| `core/decision/decision_pipeline.py` | `_s7_voice_consultation_for_card` | hash | call:work_request_envelope_hash | 1152 |
| `core/decision/decision_pipeline.py` | `_s7_voice_consultation_for_card` | hash | call:work_request_envelope_hash | 1178 |
| `core/decision/decision_pipeline.py` | `handle_action` | hash | call:work_request_envelope_hash | 677 |
| `core/decision/pending_cards.py` | `approve_and_mark_running` | execution_edge | call:execution_grant_authorizes_card_transition | 851 |
| `core/evolution/dream_state.py` | `_consume_s7_execution_authorization_for_envelope` | durable_writer | call:consume_for_execution | 1182 |
| `core/evolution/dream_state.py` | `_consume_s7_execution_authorization_for_envelope` | hash | call:work_request_envelope_hash | 1175 |
| `core/evolution/dream_state.py` | `build_apply_s7_envelope` | producer | call:build_work_request_envelope | 1054 |
| `core/evolution/dream_state.py` | `build_section_edit_s7_envelope` | producer | call:build_work_request_envelope | 1132 |
| `core/governance/operator_user_boundary.py` | `_mint_s7_execution_grant` | constructor | call:S7ExecutionGrant | 2393 |
| `core/governance/operator_user_boundary.py` | `_mint_s7_execution_grant` | constructor | definition | 2378 |
| `core/governance/operator_user_boundary.py` | `authorization_artifact_matches` | validator | definition | 2253 |
| `core/governance/operator_user_boundary.py` | `brain_swap_execution_authorized` | hash | call:brain_swap_execution_precondition_hash | 2983 |
| `core/governance/operator_user_boundary.py` | `brain_swap_execution_authorized` | hash | call:work_request_envelope_hash | 2999 |
| `core/governance/operator_user_boundary.py` | `brain_swap_execution_precondition_hash` | hash | definition | 2882 |
| `core/governance/operator_user_boundary.py` | `build_brain_swap_work_request_envelope` | hash | call:brain_swap_execution_precondition_hash | 2929 |
| `core/governance/operator_user_boundary.py` | `build_brain_swap_work_request_envelope` | producer | call:build_work_request_envelope | 2933 |
| `core/governance/operator_user_boundary.py` | `build_request_history_record` | hash | call:work_request_envelope_hash | 1240 |
| `core/governance/operator_user_boundary.py` | `build_work_request_envelope` | producer | call:WorkRequestEnvelope | 1398 |
| `core/governance/operator_user_boundary.py` | `build_work_request_envelope` | producer | definition | 1360 |
| `core/governance/operator_user_boundary.py` | `consume_execution_grant_for_action` | execution_edge | call:execution_grant_authorizes_action | 2733 |
| `core/governance/operator_user_boundary.py` | `consume_execution_grant_for_action` | execution_edge | definition | 2726 |
| `core/governance/operator_user_boundary.py` | `consume_for_execution` | constructor | call:_mint_s7_execution_grant | 2637 |
| `core/governance/operator_user_boundary.py` | `consume_for_execution` | durable_writer | definition | 2541 |
| `core/governance/operator_user_boundary.py` | `consume_verified` | durable_writer | call:consume_for_execution | 2524 |
| `core/governance/operator_user_boundary.py` | `execution_grant_authorizes_action` | execution_edge | definition | 2695 |
| `core/governance/operator_user_boundary.py` | `execution_grant_authorizes_card_transition` | execution_edge | call:execution_grant_authorizes_action | 2760 |
| `core/governance/operator_user_boundary.py` | `execution_grant_authorizes_card_transition` | execution_edge | definition | 2744 |
| `core/governance/operator_user_boundary.py` | `maez_voice_consultation_hash` | hash | definition | 1475 |
| `core/governance/operator_user_boundary.py` | `put` | durable_writer | definition | 2430 |
| `core/governance/operator_user_boundary.py` | `put` | durable_writer | definition | 3557 |
| `core/governance/operator_user_boundary.py` | `put` | durable_writer | definition | 3639 |
| `core/governance/operator_user_boundary.py` | `render_request_statement` | hash | call:maez_voice_consultation_hash | 4100 |
| `core/governance/operator_user_boundary.py` | `render_request_statement` | hash | call:work_request_envelope_hash | 4111 |
| `core/governance/operator_user_boundary.py` | `render_request_statement` | renderer | call:RenderedRequestStatement | 4137 |
| `core/governance/operator_user_boundary.py` | `render_request_statement` | renderer | definition | 4071 |
| `core/governance/operator_user_boundary.py` | `voice_consultation_satisfies_request` | hash | call:work_request_envelope_hash | 1493 |
| `core/governance/operator_user_boundary.py` | `work_request_envelope_hash` | hash | definition | 1155 |
| `core/governance/s7_guarded_execution.py` | `_bundle_content_hash_valid` | hash | call:s7_voice_consultation_bundle_hash | 1866 |
| `core/governance/s7_guarded_execution.py` | `_bundle_matches_expected_hash_binding` | validator | definition | 1839 |
| `core/governance/s7_guarded_execution.py` | `derive_s7_voice_source_bundle_hash_binding` | hash | call:maez_voice_consultation_hash | 588 |
| `core/governance/s7_guarded_execution.py` | `derive_s7_voice_source_bundle_hash_binding` | hash | call:work_request_envelope_hash | 587 |
| `core/governance/s7_guarded_execution.py` | `derive_s7_voice_source_bundle_hash_binding` | source_bundle | call:S7VoiceSourceBundleHashBinding | 604 |
| `core/governance/s7_guarded_execution.py` | `derive_s7_voice_source_bundle_hash_binding` | source_bundle | definition | 568 |
| `core/governance/s7_guarded_execution.py` | `get_for_source_ref` | source_bundle | call:S7VoiceConsultationBundle | 1389 |
| `core/governance/s7_guarded_execution.py` | `mint_authorization_artifact` | constructor | definition | 2291 |
| `core/governance/s7_guarded_execution.py` | `mint_authorization_artifact` | durable_writer | call:put | 2324 |
| `core/governance/s7_guarded_execution.py` | `mint_authorization_artifact` | durable_writer | call:put_artifact_with_bundle_reservation | 2316 |
| `core/governance/s7_guarded_execution.py` | `persist_s7_voice_source_bundle_for_material` | durable_writer | call:put | 678 |
| `core/governance/s7_guarded_execution.py` | `persist_s7_voice_source_bundle_for_material` | durable_writer | call:put_bundle | 702 |
| `core/governance/s7_guarded_execution.py` | `persist_s7_voice_source_bundle_for_material` | source_bundle | call:S7VoiceConsultationBundle | 703 |
| `core/governance/s7_guarded_execution.py` | `persist_s7_voice_source_bundle_for_material` | source_bundle | call:derive_s7_voice_source_bundle_hash_binding | 666 |
| `core/governance/s7_guarded_execution.py` | `put` | durable_writer | definition | 1464 |
| `core/governance/s7_guarded_execution.py` | `put_artifact_with_bundle_reservation` | durable_writer | call:put | 2287 |
| `core/governance/s7_guarded_execution.py` | `put_artifact_with_bundle_reservation` | durable_writer | definition | 2258 |
| `core/governance/s7_guarded_execution.py` | `put_bundle` | durable_writer | definition | 1288 |
| `core/governance/s7_guarded_execution.py` | `put_bundle` | hash | call:s7_voice_consultation_bundle_hash | 1294 |
| `core/governance/s7_guarded_execution.py` | `s7_voice_consultation_bundle_hash` | hash | definition | 821 |
| `core/governance/s7_guarded_execution.py` | `validate_s7_voice_source_bundle` | validator | call:_bundle_matches_expected_hash_binding | 2090 |
| `core/governance/s7_webauthn_ceremony.py` | `_consume_backup_registration_authorization` | durable_writer | call:consume_for_execution | 886 |
| `core/governance/s7_webauthn_ceremony.py` | `authorize_finish` | constructor | call:S7AuthorizationArtifact | 659 |
| `core/governance/s7_webauthn_ceremony.py` | `authorize_finish` | constructor | call:mint_authorization_artifact | 682 |
| `core/governance/s7_webauthn_ceremony.py` | `build_backup_registration_envelope` | producer | call:build_work_request_envelope | 61 |
| `core/governance/s7_webauthn_ceremony.py` | `build_disable_credential_envelope` | producer | call:build_work_request_envelope | 101 |
| `daemon/maez_daemon.py` | `_s7_authorization_route_material` | renderer | call:render_request_statement | 580 |
| `daemon/maez_daemon.py` | `_s7_disable_credential_for_proof` | durable_writer | call:consume_for_execution | 1056 |
| `daemon/maez_daemon.py` | `_s7_disable_credential_for_proof` | execution_edge | call:consume_execution_grant_for_action | 1070 |
| `daemon/maez_daemon.py` | `_s7_voice_source_validation_for_material` | source_bundle | call:derive_s7_voice_source_bundle_hash_binding | 628 |
| `skills/surface/s7_ceremony_bridge.py` | `s7_request_envelope_hash_for_card` | hash | call:work_request_envelope_hash | 68 |
| `ui/maez_terminal_ui.py` | `_compose_corner` | durable_writer | call:put | 420 |
| `ui/maez_terminal_ui.py` | `_compose_corner` | durable_writer | call:put | 424 |
| `ui/maez_terminal_ui.py` | `_compose_corner` | durable_writer | call:put | 431 |
| `ui/maez_terminal_ui.py` | `_compose_corner` | durable_writer | call:put | 434 |
| `ui/maez_terminal_ui.py` | `_compose_corner` | durable_writer | call:put | 440 |
| `ui/maez_terminal_ui.py` | `_compose_corner` | durable_writer | call:put | 442 |
| `ui/maez_terminal_ui.py` | `_compose_corner` | durable_writer | call:put | 444 |
| `ui/maez_terminal_ui.py` | `_compose_corner` | durable_writer | call:put | 445 |
| `ui/maez_terminal_ui.py` | `_compose_fullscreen` | durable_writer | call:put | 286 |
| `ui/maez_terminal_ui.py` | `_compose_fullscreen` | durable_writer | call:put | 291 |
| `ui/maez_terminal_ui.py` | `_compose_fullscreen` | durable_writer | call:put | 301 |
| `ui/maez_terminal_ui.py` | `_compose_fullscreen` | durable_writer | call:put | 303 |
| `ui/maez_terminal_ui.py` | `_compose_fullscreen` | durable_writer | call:put | 304 |
| `ui/maez_terminal_ui.py` | `_compose_fullscreen` | durable_writer | call:put | 317 |
| `ui/maez_terminal_ui.py` | `_compose_fullscreen` | durable_writer | call:put | 318 |
| `ui/maez_terminal_ui.py` | `_compose_fullscreen` | durable_writer | call:put | 321 |
| `ui/maez_terminal_ui.py` | `_compose_fullscreen` | durable_writer | call:put | 336 |
| `ui/maez_terminal_ui.py` | `_compose_fullscreen` | durable_writer | call:put | 337 |
| `ui/maez_terminal_ui.py` | `_compose_fullscreen` | durable_writer | call:put | 340 |
| `ui/maez_terminal_ui.py` | `_compose_fullscreen` | durable_writer | call:put | 351 |
| `ui/maez_terminal_ui.py` | `_compose_fullscreen` | durable_writer | call:put | 352 |
| `ui/maez_terminal_ui.py` | `_compose_fullscreen` | durable_writer | call:put | 353 |
| `ui/maez_terminal_ui.py` | `_compose_fullscreen` | durable_writer | call:put | 356 |
| `ui/maez_terminal_ui.py` | `_compose_fullscreen` | durable_writer | call:put | 360 |
| `ui/maez_terminal_ui.py` | `_compose_fullscreen` | durable_writer | call:put | 371 |
| `ui/maez_terminal_ui.py` | `_compose_fullscreen` | durable_writer | call:put | 374 |
| `ui/maez_terminal_ui.py` | `_compose_fullscreen` | durable_writer | call:put | 377 |
| `ui/maez_terminal_ui.py` | `_compose_status_bar` | durable_writer | call:put | 388 |
| `ui/maez_terminal_ui.py` | `_compose_status_bar` | durable_writer | call:put | 400 |
| `ui/maez_terminal_ui.py` | `_compose_status_bar` | durable_writer | call:put | 402 |
| `ui/maez_terminal_ui.py` | `_compose_status_bar` | durable_writer | call:put | 404 |
| `ui/maez_terminal_ui.py` | `_glitch_transition` | durable_writer | call:put | 262 |
| `ui/maez_terminal_ui.py` | `put` | durable_writer | definition | 104 |

**Counts, derived mechanically:** constructor 6, durable_writer 50, execution_edge 9, hash 20, producer 8, renderer 3, source_bundle 6, validator 3 — **total 105**.

**Two tables, two purposes (v8).** v7 published the **broad scan** — 105
sites, 50 of them bare `put` matches — and then claimed a qualified
74-site allowlist it never enumerated. One table cannot be both the
discovery guard and the authority allowlist; the RED contract pinned a
number that appeared nowhere.

**SUPERSEDED (v11).** A 67-site authority table stood here. It omitted
the two writer definitions, so the enforceable union was 69 while this
table claimed 67 — and leaving both meant two authoritative allowlists,
which is worse than either. Deleted rather than struck through: a
superseded allowlist that is still readable is one somebody will pin.

**The single authority allowlist is below.**

**One table, one count (v10).** v9 published 67 sites and then appended
two writer definitions *outside* the table, so the enforceable union was
69 and no mechanically checked artefact said so. The two class-qualified
definitions — `S7AuthorizationStore.put` and
`S7VoiceConsultationBundleStore.put_bundle`, which are precisely the
functions that write the tables the freeze triggers make unwritable — are
now emitted by the same generator and counted with everything else.

| file | function | role | syntactic role | line |
|---|---|---|---|---|
| `core/actions/action_engine.py` | `_s7_invocation_gate` | execution_edge | call:consume_execution_grant_for_action | 616 |
| `core/decision/decision_pipeline.py` | `_consume_s7_execution_authorization` | durable_writer | call:consume_for_execution | 1578 |
| `core/decision/decision_pipeline.py` | `_on_approve` | execution_edge | call:execution_grant_authorizes_card_transition | 1929 |
| `core/decision/decision_pipeline.py` | `_s7_request_envelope_for_card` | producer | call:build_work_request_envelope | 1072 |
| `core/decision/decision_pipeline.py` | `_s7_voice_consultation_for_card` | hash | call:work_request_envelope_hash | 1155 |
| `core/decision/decision_pipeline.py` | `_s7_voice_consultation_for_card` | hash | call:work_request_envelope_hash | 1181 |
| `core/decision/decision_pipeline.py` | `handle_action` | hash | call:work_request_envelope_hash | 680 |
| `core/decision/pending_cards.py` | `approve_and_mark_running` | execution_edge | call:execution_grant_authorizes_card_transition | 854 |
| `core/evolution/dream_state.py` | `_consume_s7_execution_authorization_for_envelope` | durable_writer | call:consume_for_execution | 1186 |
| `core/evolution/dream_state.py` | `_consume_s7_execution_authorization_for_envelope` | hash | call:work_request_envelope_hash | 1179 |
| `core/evolution/dream_state.py` | `build_apply_s7_envelope` | producer | call:build_work_request_envelope | 1054 |
| `core/evolution/dream_state.py` | `build_section_edit_s7_envelope` | producer | call:build_work_request_envelope | 1132 |
| `core/governance/operator_user_boundary.py` | `S7AuthorizationStore.put` | durable_writer | definition | 3264 |
| `core/governance/operator_user_boundary.py` | `_held_store` | constructor | call:_open_s7_connection_from_held_store | 2738 |
| `core/governance/operator_user_boundary.py` | `_mint_s7_execution_grant` | constructor | call:S7ExecutionGrant | 2555 |
| `core/governance/operator_user_boundary.py` | `_mint_s7_execution_grant` | constructor | definition | 2539 |
| `core/governance/operator_user_boundary.py` | `_open_s7_connection_from_held_store` | constructor | call:_S7HeldConnectionBinding | 2652 |
| `core/governance/operator_user_boundary.py` | `_open_s7_connection_from_held_store` | constructor | definition | 2640 |
| `core/governance/operator_user_boundary.py` | `_read_committed_grant_row_after_commit` | source_bundle | call:CommittedGrantRow | 2963 |
| `core/governance/operator_user_boundary.py` | `_read_committed_grant_row_after_commit` | source_bundle | definition | 2920 |
| `core/governance/operator_user_boundary.py` | `_require_verified_held_connection` | validator | definition | 2663 |
| `core/governance/operator_user_boundary.py` | `authorization_artifact_matches` | validator | definition | 2304 |
| `core/governance/operator_user_boundary.py` | `brain_swap_execution_authorized` | hash | call:brain_swap_execution_precondition_hash | 3819 |
| `core/governance/operator_user_boundary.py` | `brain_swap_execution_authorized` | hash | call:work_request_envelope_hash | 3835 |
| `core/governance/operator_user_boundary.py` | `brain_swap_execution_precondition_hash` | hash | definition | 3677 |
| `core/governance/operator_user_boundary.py` | `build_brain_swap_work_request_envelope` | hash | call:brain_swap_execution_precondition_hash | 3724 |
| `core/governance/operator_user_boundary.py` | `build_brain_swap_work_request_envelope` | producer | call:build_work_request_envelope | 3728 |
| `core/governance/operator_user_boundary.py` | `build_cutover_work_request_envelope` | producer | call:build_work_request_envelope | 3769 |
| `core/governance/operator_user_boundary.py` | `build_request_history_record` | hash | call:work_request_envelope_hash | 1282 |
| `core/governance/operator_user_boundary.py` | `build_work_request_envelope` | producer | call:WorkRequestEnvelope | 1440 |
| `core/governance/operator_user_boundary.py` | `build_work_request_envelope` | producer | definition | 1402 |
| `core/governance/operator_user_boundary.py` | `committed_grant_row_proves_founder_self_modification` | validator | definition | 2497 |
| `core/governance/operator_user_boundary.py` | `consume_execution_grant_for_action` | execution_edge | call:execution_grant_authorizes_action | 3528 |
| `core/governance/operator_user_boundary.py` | `consume_execution_grant_for_action` | execution_edge | definition | 3521 |
| `core/governance/operator_user_boundary.py` | `consume_for_execution` | durable_writer | call:consume_for_execution_on_connection | 3434 |
| `core/governance/operator_user_boundary.py` | `consume_for_execution` | durable_writer | definition | 3418 |
| `core/governance/operator_user_boundary.py` | `consume_for_execution_on_connection` | constructor | call:_mint_s7_execution_grant | 3082 |
| `core/governance/operator_user_boundary.py` | `consume_for_execution_on_connection` | validator | call:_require_verified_held_connection | 2982 |
| `core/governance/operator_user_boundary.py` | `consume_for_execution_on_connection` | durable_writer | definition | 2966 |
| `core/governance/operator_user_boundary.py` | `consume_for_execution_with_committed_row` | source_bundle | call:_CommittedConsumptionConnection | 3143 |
| `core/governance/operator_user_boundary.py` | `consume_for_execution_with_committed_row` | source_bundle | call:_read_committed_grant_row_after_commit | 3146 |
| `core/governance/operator_user_boundary.py` | `consume_for_execution_with_committed_row` | durable_writer | call:consume_for_execution_on_connection | 3127 |
| `core/governance/operator_user_boundary.py` | `consume_for_execution_with_committed_row` | durable_writer | definition | 3111 |
| `core/governance/operator_user_boundary.py` | `consume_verified` | durable_writer | call:consume_for_execution | 3401 |
| `core/governance/operator_user_boundary.py` | `execution_grant_authorizes_action` | execution_edge | definition | 3484 |
| `core/governance/operator_user_boundary.py` | `execution_grant_authorizes_card_transition` | execution_edge | call:execution_grant_authorizes_action | 3555 |
| `core/governance/operator_user_boundary.py` | `execution_grant_authorizes_card_transition` | execution_edge | definition | 3539 |
| `core/governance/operator_user_boundary.py` | `maez_voice_consultation_hash` | hash | definition | 1518 |
| `core/governance/operator_user_boundary.py` | `render_request_statement` | validator | call:consultation_exemption_admits | 4950 |
| `core/governance/operator_user_boundary.py` | `render_request_statement` | hash | call:maez_voice_consultation_hash | 4968 |
| `core/governance/operator_user_boundary.py` | `render_request_statement` | hash | call:work_request_envelope_hash | 4979 |
| `core/governance/operator_user_boundary.py` | `render_request_statement` | renderer | call:RenderedRequestStatement | 5008 |
| `core/governance/operator_user_boundary.py` | `render_request_statement` | renderer | definition | 4912 |
| `core/governance/operator_user_boundary.py` | `voice_consultation_satisfies_request` | hash | call:work_request_envelope_hash | 1536 |
| `core/governance/operator_user_boundary.py` | `work_request_envelope_hash` | hash | definition | 1197 |
| `core/governance/s7_guarded_execution.py` | `S7VoiceConsultationBundleStore.put_bundle` | durable_writer | definition | 2044 |
| `core/governance/s7_guarded_execution.py` | `_bundle_content_hash_valid` | hash | call:s7_voice_consultation_bundle_hash | 2622 |
| `core/governance/s7_guarded_execution.py` | `_bundle_matches_expected_hash_binding` | validator | definition | 2595 |
| `core/governance/s7_guarded_execution.py` | `_voice_bundle_from_row` | source_bundle | call:S7VoiceConsultationBundle | 1296 |
| `core/governance/s7_guarded_execution.py` | `_voice_validation_result_v2` | hash | call:s7_voice_consultation_bundle_hash | 1430 |
| `core/governance/s7_guarded_execution.py` | `derive_s7_voice_source_bundle_hash_binding` | hash | call:maez_voice_consultation_hash | 708 |
| `core/governance/s7_guarded_execution.py` | `derive_s7_voice_source_bundle_hash_binding` | hash | call:work_request_envelope_hash | 707 |
| `core/governance/s7_guarded_execution.py` | `derive_s7_voice_source_bundle_hash_binding` | source_bundle | call:S7VoiceSourceBundleHashBinding | 724 |
| `core/governance/s7_guarded_execution.py` | `derive_s7_voice_source_bundle_hash_binding` | source_bundle | definition | 688 |
| `core/governance/s7_guarded_execution.py` | `get_for_source_ref` | source_bundle | call:S7VoiceConsultationBundle | 2145 |
| `core/governance/s7_guarded_execution.py` | `mint_authorization_artifact` | constructor | definition | 3062 |
| `core/governance/s7_guarded_execution.py` | `mint_authorization_artifact` | durable_writer | call:authorization_store.put | 3095 |
| `core/governance/s7_guarded_execution.py` | `mint_authorization_artifact` | durable_writer | call:put_artifact_with_bundle_reservation | 3087 |
| `core/governance/s7_guarded_execution.py` | `persist_s7_voice_source_bundle_for_material` | durable_writer | call:attempt_store.put | 804 |
| `core/governance/s7_guarded_execution.py` | `persist_s7_voice_source_bundle_for_material` | durable_writer | call:put_voice_source_bundle_v2 | 860 |
| `core/governance/s7_guarded_execution.py` | `persist_s7_voice_source_bundle_for_material` | hash | call:s7_voice_consultation_bundle_hash | 857 |
| `core/governance/s7_guarded_execution.py` | `persist_s7_voice_source_bundle_for_material` | source_bundle | call:S7VoiceConsultationBundle | 828 |
| `core/governance/s7_guarded_execution.py` | `persist_s7_voice_source_bundle_for_material` | source_bundle | call:derive_s7_voice_source_bundle_hash_binding | 786 |
| `core/governance/s7_guarded_execution.py` | `put_artifact_with_bundle_reservation` | durable_writer | call:self.authorization_store.put | 3059 |
| `core/governance/s7_guarded_execution.py` | `put_artifact_with_bundle_reservation` | durable_writer | definition | 3022 |
| `core/governance/s7_guarded_execution.py` | `put_bundle` | hash | call:s7_voice_consultation_bundle_hash | 2050 |
| `core/governance/s7_guarded_execution.py` | `put_voice_source_bundle_v2` | hash | call:s7_voice_consultation_bundle_hash | 1342 |
| `core/governance/s7_guarded_execution.py` | `s7_voice_consultation_bundle_hash` | hash | definition | 1133 |
| `core/governance/s7_guarded_execution.py` | `validate_s7_voice_source_bundle` | validator | call:_bundle_matches_expected_hash_binding | 2846 |
| `core/governance/s7_guarded_execution.py` | `validate_voice_source_bundle` | validator | call:_bundle_matches_expected_hash_binding | 1533 |
| `core/governance/s7_guarded_execution.py` | `validate_voice_source_bundle` | hash | call:_voice_source_bundle_binding_hash | 1516 |
| `core/governance/s7_guarded_execution.py` | `validate_voice_source_bundle` | hash | call:s7_voice_consultation_bundle_hash | 1519 |
| `core/governance/s7_consultation_exemption.py` | `mint_consultation_exemption` | hash | call:work_request_envelope_hash | 199 |
| `core/governance/s7_consultation_exemption.py` | `mint_consultation_exemption` | producer | definition | 172 |
| `core/governance/s7_consultation_exemption.py` | `consultation_exemption_admits` | hash | call:work_request_envelope_hash | 374 |
| `core/governance/s7_consultation_exemption.py` | `consultation_exemption_admits` | validator | definition | 324 |
| `core/governance/s7_webauthn_ceremony.py` | `authorization_voice_seat_recheck` | validator | call:consultation_exemption_admits | 859 |
| `core/governance/s7_webauthn_ceremony.py` | `_consume_backup_registration_authorization` | durable_writer | call:consume_for_execution | 1275 |
| `core/governance/s7_webauthn_ceremony.py` | `_cutover_voice_evidence_revalidated_at_gate` | hash | call:_voice_source_bundle_binding_hash | 1184 |
| `core/governance/s7_webauthn_ceremony.py` | `_cutover_voice_evidence_revalidated_at_gate` | source_bundle | call:read_voice_source_bundle | 1154 |
| `core/governance/s7_webauthn_ceremony.py` | `_cutover_voice_evidence_revalidated_at_gate` | validator | call:validate_voice_source_bundle | 1160 |
| `core/governance/s7_webauthn_ceremony.py` | `_generic_voice_evidence_revalidated_at_gate` | hash | call:maez_voice_consultation_hash | 1002 |
| `core/governance/s7_webauthn_ceremony.py` | `_generic_voice_evidence_revalidated_at_gate` | source_bundle | call:read_voice_source_bundle | 1011 |
| `core/governance/s7_webauthn_ceremony.py` | `_generic_voice_evidence_revalidated_at_gate` | validator | call:validate_voice_source_bundle | 1017 |
| `core/governance/s7_webauthn_ceremony.py` | `authorize_finish` | constructor | call:S7AuthorizationArtifact | 705 |
| `core/governance/s7_webauthn_ceremony.py` | `authorize_finish` | constructor | call:mint_authorization_artifact | 729 |
| `core/governance/s7_webauthn_ceremony.py` | `build_backup_registration_envelope` | producer | call:build_work_request_envelope | 61 |
| `core/governance/s7_webauthn_ceremony.py` | `build_disable_credential_envelope` | producer | call:build_work_request_envelope | 101 |
| `daemon/maez_daemon.py` | `_s7_authorization_route_material` | renderer | call:render_request_statement | 580 |
| `daemon/maez_daemon.py` | `_s7_disable_credential_for_proof` | durable_writer | call:consume_for_execution | 1075 |
| `daemon/maez_daemon.py` | `_s7_disable_credential_for_proof` | execution_edge | call:consume_execution_grant_for_action | 1089 |
| `daemon/maez_daemon.py` | `_s7_founder_seen_voice_hash_valid` | source_bundle | call:read_voice_source_bundle | 755 |
| `daemon/maez_daemon.py` | `_s7_voice_source_validation_for_material` | source_bundle | call:derive_s7_voice_source_bundle_hash_binding | 625 |
| `daemon/maez_daemon.py` | `_s7_voice_source_validation_for_material` | source_bundle | call:read_voice_source_bundle | 634 |
| `daemon/maez_daemon.py` | `_s7_voice_source_validation_for_material` | validator | call:validate_voice_source_bundle | 638 |
| `scripts/cuda_cutover.py` | `__init__` | hash | call:work_request_envelope_hash | 1261 |
| `scripts/cuda_cutover.py` | `_authorize_and_stage_selected_cutover` | producer | call:build_work_request_envelope | 3860 |
| `scripts/cuda_cutover.py` | `_authorize_and_stage_selected_cutover` | renderer | call:render_request_statement | 3900 |
| `scripts/cuda_cutover.py` | `_is_canonical_cutover_envelope` | producer | call:build_work_request_envelope | 3080 |
| `scripts/cuda_cutover.py` | `anchored_transaction` | constructor | call:_open_s7_connection_from_held_store | 1039 |
| `scripts/cuda_cutover.py` | `_conn` | constructor | call:_open_s7_connection_from_held_store | 1176 |
| `scripts/cuda_cutover.py` | `_cutover_voice_bundle` | hash | call:s7_voice_consultation_bundle_hash | 1372 |
| `scripts/cuda_cutover.py` | `_cutover_voice_bundle` | source_bundle | call:S7VoiceConsultationBundle | 1341 |
| `scripts/cuda_cutover.py` | `_cutover_voice_bundle` | source_bundle | call:derive_s7_voice_source_bundle_hash_binding | 1334 |
| `scripts/cuda_cutover.py` | `_persist_and_validate_cutover_voice_bundle` | durable_writer | call:put_voice_source_bundle_v2 | 1394 |
| `scripts/cuda_cutover.py` | `_persist_and_validate_cutover_voice_bundle` | source_bundle | call:read_voice_source_bundle | 1412 |
| `scripts/cuda_cutover.py` | `_persist_and_validate_cutover_voice_bundle` | validator | call:validate_voice_source_bundle | 1416 |
| `scripts/cuda_cutover.py` | `open_existing_authorization_store` | constructor | call:_open_s7_connection_from_held_store | 976 |
| `scripts/cuda_cutover.py` | `publish_and_validate_burn` | execution_edge | call:consume_execution_grant_for_action | 1905 |
| `scripts/cuda_cutover.py` | `revalidate_cutover_consultation_result` | hash | call:maez_voice_consultation_hash | 3633 |
| `scripts/cuda_cutover.py` | `require_current_named_identity` | constructor | call:_require_verified_held_connection | 799 |
| `skills/surface/s7_ceremony_bridge.py` | `s7_request_envelope_hash_for_card` | hash | call:work_request_envelope_hash | 68 |

**Counts, derived mechanically:** constructor 13, durable_writer 19, execution_edge 10, hash 32, producer 12, renderer 4, source_bundle 18, validator 14 — **total 122**.

The broad scan is retained separately as a **discovery guard** — it fires
when a new candidate site appears anywhere, and narrowing it is then a
deliberate reviewable act. The RED contract pins **this** table.

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
| cutover grant projection | `cuda_migration.s7_execution_grant_projection.v2` | the 15 grant fields **+ `action` + `schema_version`** = 17 | `…projection.v2` | v1 projection is audit-only |

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

**SUPERSEDED by v6/v7.** This paragraph described a PRAGMA-based
preimage and a receipt schema that v6 replaced. Retained struck-through
would only invite reading it as current, so it is removed; the
authoritative fingerprint recipe and receipt schema are below under
*Fingerprint literals (v7)* and *Activation ordering*.

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

## The live store does not HAVE a voice plane (v7)

Verified read-only: `ceremony.sqlite3` contains
`s7_authorization_artifacts`, `s7_bootstrap_intents`,
`s7_ceremony_challenges`, `s7_ceremony_metadata`,
`s7_founder_webauthn_credentials`, `s7_refusal_history` — and **no
`s7_voice_consultation_bundles`**.

So v6's migration was **not executable against the database that exists**:
its very first voice trigger would fail `no such table`. I froze DDL and
triggers for a plane I never checked was present, in the same store.

**Frozen transition:** migration **creates the empty legacy table first**,
then freezes it:

```sql
CREATE TABLE IF NOT EXISTS s7_voice_consultation_bundles (
    source_ref_hash TEXT PRIMARY KEY,
    request_id TEXT NOT NULL,
    consultation_id TEXT NOT NULL,
    request_envelope_hash TEXT,
    rendered_text_hash TEXT,
    action_params_hash TEXT,
    precondition_hash TEXT,
    authority_context_hash TEXT,
    maez_voice_consultation_hash TEXT,
    rendered_prompt_ref TEXT,
    rendered_prompt_hash TEXT,
    mutation_preview_hash TEXT,
    rollback_plan_ref TEXT,
    context_manifest_ref TEXT,
    context_manifest_hash TEXT,
    runtime_identity_hash TEXT,
    model_routing_identity_hash TEXT,
    model_config_hash TEXT,
    raw_response_ref TEXT,
    raw_response_hash TEXT,
    semantic_reader_attempt_hash TEXT,
    expires_at TEXT,
    authority_class TEXT,
    has_grounded_semantic_blocking_signal INTEGER,
    source_bundle_hash TEXT
)
```

Literal, copied from `s7_guarded_execution.py:983` — v7 left `… 25 v1
columns …` here, so the document could not be executed from itself.

The table is created **empty and immediately frozen** — it exists only so
the freeze and cross-version triggers have a referent, and so a later
component that expects v1 finds a table it cannot write.

**The absent→empty transition is part of the migration identity.** The
`from_fingerprint_bundle` literal below is the fingerprint of the
**absent** plane, so a store that already had a populated voice table
would not match and the migration would refuse — which is correct: that
is a different starting state than the one this migration was designed
and reviewed against.

## Voice-bundle persistence, concrete (v5)

v4 left this a sketch while the authorization table was fully pinned, so
the original migration hazard survived on the *evidence* plane. The
existing `s7_voice_consultation_bundles` auto-creates and auto-`ALTER`s an
unversioned table.

**Exact v2 DDL** — the 25 v1 columns verbatim plus the R9 typed sealed
capture-receipt carrier, `action`, and `schema_version`: **28 total**.
The receipt is v2-only; the frozen v1 table remains byte-for-byte unchanged:

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
    response_capture_receipt TEXT,
    action TEXT NOT NULL,
    schema_version TEXT NOT NULL DEFAULT 's7.voice_source_bundle.v2'
);
CREATE UNIQUE INDEX IF NOT EXISTS s7_vb_v2_src
    ON s7_voice_source_bundles_v2(source_ref_hash);
```

**Freeze and exclusion triggers**, matching the authorization plane:

```sql
CREATE TRIGGER s7_vb_v1_frozen_insert BEFORE INSERT ON s7_voice_consultation_bundles
BEGIN SELECT RAISE(ABORT, 's7_vb_v1_frozen'); END;
CREATE TRIGGER s7_vb_v1_frozen_update BEFORE UPDATE ON s7_voice_consultation_bundles
BEGIN SELECT RAISE(ABORT, 's7_vb_v1_frozen'); END;
CREATE TRIGGER s7_vb_v1_frozen_delete BEFORE DELETE ON s7_voice_consultation_bundles
BEGIN SELECT RAISE(ABORT, 's7_vb_v1_frozen'); END;
CREATE TRIGGER s7_vb_v2_no_v1 BEFORE INSERT ON s7_voice_source_bundles_v2
WHEN EXISTS (SELECT 1 FROM s7_voice_consultation_bundles
             WHERE source_ref_hash = NEW.source_ref_hash)
BEGIN SELECT RAISE(ABORT, 's7_cross_version_bundle'); END;
```

**APIs, frozen — and the writer takes NO action argument:**

```
put_voice_source_bundle_v2(*, bundle, conn) -> None
    # v2 ONLY. The action comes from bundle.action, which the VALIDATED
    # binding already fixed. v5's signature took `action` separately,
    # letting a writer supply a second, caller-chosen action beside the
    # one the binding had validated -- reintroducing exactly the
    # caller-chosen-authority defect this whole slice exists to remove.

read_voice_source_bundle(*, source_ref_hash, conn) -> (bundle, version)
validate_voice_source_bundle(*, bundle, version, purpose) -> bool
    # purpose="audit" accepts v1; purpose="execution" refuses v1
```

**The action travels as authority — and the current result type cannot
carry it.** `S7VoiceSourceBundleValidationResult`
([s7_guarded_execution.py:390](/home/rohit/maez/core/governance/s7_guarded_execution.py#L390))
holds `status`, `source_bundle_valid`, `mint_eligible`,
`authority_projection` and `failure_reason_code` — **booleans and a
projection, no action and no version**. v6 wrote the join as prose over a
type that has nowhere to put it.

**Frozen result type (v2):**

```python
@dataclass(frozen=True)
class S7VoiceSourceBundleValidationResultV2:
    status: str
    source_bundle_valid: bool
    mint_eligible: bool
    authority_projection: str
    failure_reason_code: str | None
    action: str | None          # the VALIDATED action
    schema_version: str         # "s7.voice_source_bundle.v1" | ".v2"
    source_bundle_hash: str     # WHICH bundle this validates
    binding_hash: str           # the validated binding

    def __init__(
        self,
        *,
        status: str,
        source_bundle_valid: bool,
        mint_eligible: bool,
        authority_projection: str,
        failure_reason_code: str | None,
        action: str | None,
        schema_version: str,
        source_bundle_hash: str,
        binding_hash: str,
        _validator_token: object | None = None,
    ) -> None:
        if _validator_token is not _VALIDATOR_TOKEN:
            raise ValueError("s7_validation_result_forged")
```

**Valid state matrix** — no other combination constructs:

| `schema_version` | `action` | `mint_eligible` | meaning |
|---|---|---|---|
| `…v2` | non-`None`, matches grammar | may be `True` | executable |
| `…v2` | non-`None` | `False` | validated, refused for another reason |
| `…v1` | **must be `None`** | **must be `False`** | audit-only |

**Complete state matrix — `source_bundle_valid` participates.** v9's
matrix constrained only schema, action and mint-eligibility, so a
token-produced result with `source_bundle_valid=False` and
`mint_eligible=True` was still admissible to every mint check. Frozen:

| `source_bundle_valid` | `mint_eligible` | admissible? |
|---|---|---|
| `True` | `True` | **the only mintable state** |
| `True` | `False` | valid, refused for another reason |
| `False` | `False` | invalid |
| `False` | `True` | **cannot construct** — the constructor refuses |

**Still incomplete in v10:** `status`, `authority_projection` and
`failure_reason_code` were unconstrained, so a token-produced result
shaped like a *refusal* — `status="refused"`, a failure code set — could
still be `mint_eligible=True` and pass every written check. Each fix
constrained the field I had just been shown and left its neighbours free.

**The exact successful tuple, frozen. The mint requires ALL of it:**

**I invented a vocabulary that does not exist.** `"validated"` and
`_MINTABLE_AUTHORITY_PROJECTIONS` are mine; production uses the literal
`"valid_absent"` for **both** `status` and `authority_projection`
([s7_guarded_execution.py:17](/home/rohit/maez/core/governance/s7_guarded_execution.py#L17)).
Same error as the action grammar that closed six existing roads: I froze
a vocabulary from my own head without reading the one in use.

**Worse — the check already exists.** `s7_guarded_execution.py:2236`
already requires exactly:

```python
status              == "valid_absent"
source_bundle_valid is True
mint_eligible       is True
authority_projection == "valid_absent"
failure_reason_code is None
```

That is the complete five-field tuple I spent three revisions converging
on, in production, unread. v2 does not replace it — it **extends** it.

**The v2 successful tuple, frozen:**

```python
# the five existing checks, literals unchanged:
validation.status               == "valid_absent"
validation.source_bundle_valid  is True
validation.mint_eligible        is True
validation.authority_projection == "valid_absent"
validation.failure_reason_code  is None
# plus what v2 adds:
validation.schema_version       == "s7.voice_source_bundle.v2"
validation.action               is not None      # and matches the grammar
validation.source_bundle_hash   == bundle.source_bundle_hash
validation.binding_hash         == recompute_binding_hash(bundle, action)
```

The vocabulary is **not** changed. Changing `"valid_absent"` would touch
every route that produces or consumes it, which is a separate slice with
its own review.

**Constructor invariants** — these combinations cannot be built at all:

* `status == "valid_absent"` with a non-`None` `failure_reason_code`;
* `status != "valid_absent"` with `mint_eligible is True`;
* `authority_projection != "valid_absent"` with `mint_eligible is True`;
* `failure_reason_code` set with `mint_eligible is True`;
* `mint_eligible is True` with `source_bundle_valid is False`;
* `schema_version == "…v1"` with `action` not `None`, or with
  `mint_eligible is True`.

A refusal-shaped result is therefore unmintable **by construction**, not
merely rejected at the mint.

`_VALIDATOR_TOKEN` is a module-private sentinel. The **only** producers
are `validate_voice_source_bundle()` and its v1 audit counterpart; both
are module-private factories. Nothing else may pass the token.

**`binding_hash` recipe, exact fields** — the project canonical encoder
over `{"schema": "s7.voice_source_bundle.v2", "fields": {…}}` where the
fields are precisely the 25 v1 bundle columns plus the R9
`response_capture_receipt` projection and `action`. The receipt projection
is present when the typed receipt is present; omitting it preserves the
already-sealed non-R9 bundle recipe:

```
source_ref_hash, request_id, consultation_id, request_envelope_hash,
rendered_text_hash, action_params_hash, precondition_hash,
authority_context_hash, maez_voice_consultation_hash, rendered_prompt_ref,
rendered_prompt_hash, mutation_preview_hash, rollback_plan_ref,
context_manifest_ref, context_manifest_hash, runtime_identity_hash,
model_routing_identity_hash, model_config_hash, raw_response_ref,
raw_response_hash, semantic_reader_attempt_hash, expires_at,
authority_class, has_grounded_semantic_blocking_signal,
source_bundle_hash, response_capture_receipt, action
```

SHA-256 of those exact bytes, same newline-bearing encoder as every other
binding here. `{…bundle fields…}` was a placeholder, not a recipe.

**Mint signature, exact:**

```python
def mint_from_validated_bundle(
    *,
    bundle: S7VoiceConsultationBundle,
    validation: S7VoiceSourceBundleValidationResultV2,
    conn: sqlite3.Connection,
) -> S7AuthorizationArtifact:
```

**takes no `action` argument.** Checks, all required:

1. `validation._token_verified` — constructed by a factory, not a caller;
2. `validation.schema_version == "s7.voice_source_bundle.v2"`;
3. the **exact successful tuple** above, every field — not a subset;
4. `validation.action` is non-`None` and matches the action grammar;
5. `bundle.source_bundle_hash == validation.source_bundle_hash`;
6. `recompute_binding_hash(bundle, validation.action) == validation.binding_hash`;
7. the minted artifact's `action` **is** `validation.action`.

**v7's plain dataclass was caller-forgeable** — anyone could construct a
`mint_eligible=True` result carrying any action and hand it to
`mint_from_validated_bundle`, which is the caller-chosen-authority defect
in its purest form, arriving in the very type built to prevent it. I
dropped the private validator token the **existing**
`S7VoiceSourceBundleValidationResult` already has
([s7_guarded_execution.py:390](/home/rohit/maez/core/governance/s7_guarded_execution.py#L390)),
while writing a v2 meant to be stricter.

Restored, plus **bundle identity**: `source_bundle_hash` and
`binding_hash` say *which* bundle was validated, so a result cannot be
paired with a different bundle at the mint.

**Minting additionally requires** `bundle.source_bundle_hash ==
validation.source_bundle_hash`. A validated result plus a substituted
bundle refuses.

**Mutation REDs:** direct construction without the token refuses;
substituting a different bundle beside a genuine result refuses.

`action` is `None` **iff** the bundle is v1, and a v1 bundle is never
`mint_eligible`.

**Minting API, frozen:**

```
mint_from_validated_bundle(*, validation: …ResultV2, …) -> artifact
    # takes NO action argument. The action comes from
    # validation.action, which the validator fixed.
```

**Frozen join:** `bundle.action == validation.action == artifact.action`.

**Binding RED:** a bundle validated for action **A** cannot mint an
artifact for action **B** — there is no parameter through which B could
be supplied.

**Same freezes as the authorization plane:** v1 write-frozen by trigger,
never backfilled, never migrated on open, its own fingerprint, its own
receipt entry.

## Fingerprint literals (v6) — the preimage now binds the WALL

**v5's fingerprint did not cover the triggers.** Reproduced: create the
table, index and freeze trigger, hash; `DROP TRIGGER`; hash again —
**identical**. So the wall that stops an old daemon could be removed and
the activation receipt would still validate. I built the wall in v5 and
then published an identity that does not mention it.

Two further defects in that recipe: `PRAGMA index_info` **does not bind
expression bodies or partial-index predicates**, and the literals
reproduced from **raw SQLite row order** while the document claimed a
sorted preimage.

**Frozen preimage** — normalized `sqlite_master.sql`, covering tables,
indexes **and triggers**:

```python
def canon_sql(sql):                      # None stays None
    return None if sql is None else re.sub(r"\s+", " ", sql).strip().rstrip(";")

rows = []
for name in sorted(table_names):         # explicit sort, not row order
    for t, n, tbl, sql in conn.execute(
        "select type,name,tbl_name,sql from sqlite_master "
        "where tbl_name=? order by type,name", (name,)):
        rows.append([t, n, tbl, canon_sql(sql)])
fingerprint = sha256(json.dumps(rows, sort_keys=True,
                                separators=(",", ":"),
                                ensure_ascii=False).encode()).hexdigest()
```

Because it hashes the **SQL text**, expression indexes, partial
predicates and every trigger body participate by construction rather than
by enumerating PRAGMA fields and hoping the list is complete.

**THE TARGET LITERALS ARE WITHDRAWN (v9).**

v8 published `ffee1bcb…` and `b93735fe…`. Review recomputed
`5bea4677…` and `a4546eb9…`. I recomputed a third pair,
`3ecc2ead…` and `5ee4d7d0…`. **Three careful parties, three answers.**

My own error is identifiable: I computed the v8 literals against **stub**
v1 tables — a two-column `s7_authorization_artifacts` I wrote to make the
scratch script run — not the real twenty-column DDL. The fingerprint
covers both planes, so a stub v1 poisons the target hash.

But the divergence between the other two values is the more useful
finding: **a fingerprint literal transcribed into prose cannot be
verified by reading.** Whitespace, `IF NOT EXISTS`, trailing commas and
column-text extraction all move it invisibly, and every party believed
they were applying the same canonicalizer.

**v9's guard was self-authenticating.** It emitted the expected literal
and then checked its own output — which proves the canonicalizer is
*deterministic*, not that the schema is *correct*. A truth meter that
calibrates itself and then declares itself accurate.

**Frozen: generation and verification are separate programs.**

| | who | when | what |
|---|---|---|---|
| **generator** | `core/governance/s7_schema_identity.py --emit` | **one shot**, at implementation time | builds both planes from the frozen DDL in a scratch database and **writes committed constants** |
| **constants** | `core/governance/s7_schema_identity.py` | committed source | `S7_TARGET_FINGERPRINT_AUTH`, `S7_TARGET_FINGERPRINT_VOICE` |
| **guard** | a test | every run | **recomputes** from the frozen DDL and compares **against the committed constants** — it never emits them |

**Migration and activation import the CONSTANT.** Neither may derive its
expected value from the live schema it is validating; deriving the
expected value from the thing under test is the same circularity in a
different costume.

**Location:** `core/governance/`, not `scripts/`. Production governance
code must not import from the bench-tooling tree — v9 put the shared
canonicalizer in `scripts/` and would have forced exactly that.

The **source** literals stand — `b8946c79…` and `4f53cda1…` — because
they were computed read-only from the live store and reproduced
independently by review.

A design literal nobody recomputes drifts; a design literal three parties
compute differently was never a literal at all; and a guard that emits
what it checks proves only that it is repeatable.

**Verified:** dropping any freeze trigger changes the fingerprint.

## v1 fingerprints, also literal

`from_fingerprint_*` were self-chosen in v5 — the receipt asserted
whatever it found — and v6 said "pinned literals" while supplying none.
Computed read-only from the live store with the v6/v7 recipe:

| plane | v1 (pre-migration) fingerprint |
|---|---|
| authorization | `b8946c79c8edf9386ce73522aac8b18b6181212a949570cf9c01c01e3ac1af00` |
| voice (**absent**) | `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945` |

The voice literal is the hash of an **empty preimage** — the absent plane
has a defined identity, so "not there" is something the receipt can bind
rather than a gap it must describe in prose.

## Activation ordering, frozen (v5)

```
1.  BEGIN IMMEDIATE                    <- LOCK FIRST (v9)
2a. classify the store (v13)           <- INSIDE the lock
2.  verify journal_mode=delete and synchronous=FULL      (refuse otherwise)
3.  verify from_fingerprint_auth   == S7_SOURCE_FINGERPRINT_AUTH   (in lock)
4.  verify from_fingerprint_bundle == S7_SOURCE_FINGERPRINT_VOICE  (absent plane)
4a. verify v1 row counts match the receipt's claim       INSIDE the lock
5.  CREATE the empty legacy voice table                  <- v7 omitted this
6.  create the three v1 voice freeze triggers
7.  create the three v1 auth freeze triggers
8.  create both v2 tables + their unique indexes
9.  create the v2 cross-version exclusion triggers
10. copy nothing                                          (no backfill)
11. verify to_fingerprint_auth   == S7_TARGET_FINGERPRINT_AUTH
12. verify to_fingerprint_bundle == S7_TARGET_FINGERPRINT_VOICE
13. verify both v2 row counts are 0
14. COMMIT
15. fsync the database AND its parent directory     (lock RELEASED)
16. publish the migration receipt          <- THE linearization point
```

**Steps 2–14 run inside the write lock; steps 15–16 do not.** v8 verified
both source fingerprints *before* `BEGIN IMMEDIATE`; that verification,
the row counts and the target verification are all inside now. The fsync
and the receipt publication are **outside** — ordered, but unlocked,
which is exactly why the receipt rather than the commit is the
linearization point.

**v9's race RED was unreachable.** With `BEGIN IMMEDIATE` first, nothing
can mutate "between verification and lock" — there is no such window any
more. I moved the check and kept the RED that only made sense before the
move. Two **real** cases replace it:

* **pre-lock mutation is observed:** a writer commits a change to the
  source plane *before* the migration acquires the lock; the in-lock
  fingerprint check sees the changed source and **refuses**;
* **post-acquisition writers are excluded:** a competing writer attempting
  to mutate after the lock is held **cannot**, and the migration completes
  or rolls back without interleaving.

**Also corrected:** steps after `COMMIT` — fsync and receipt publication —
are **not** inside the write lock, and v9 implied the whole sequence was.
They are ordered but unlocked, which is why the receipt, not the commit,
is the linearization point.

v7's sequence also created triggers on a table it had not created.

The receipt binds **both** tables. Schema `s7.migration_receipt.v1`:

```
from_fingerprint_auth,   to_fingerprint_auth,
from_fingerprint_bundle, to_fingerprint_bundle,
row_count_v1_auth,       row_count_v1_bundle,
row_count_v2_auth_at_migration,
row_count_v2_bundle_at_migration,
started_at, completed_at, store_dev, store_ino,
activation_path
```

**Two corrections v6 needed here.** Its field list carried only the two
v1 counts while later text required two v2 counts — the receipt could
not carry the evidence its own validator demanded.

And requiring **live** v2 counts to stay zero would have **deactivated S7
the moment the first legitimate v2 artifact was minted**. Zero is a
*migration-time* fact, not a standing invariant. It is bound in the
receipt as `…_at_migration`, verified **before publication**, and never
re-checked against live tables afterwards.

canonically wrapped by the project encoder and published **only** by
`s7-migrate-v2`. No row contents ever.

**Exact locator:** `memory/s7_1_webauthn/s7_migration_receipt.json` —
beside the store, named, not "beside the store".

**The anchored writer is a governance primitive (v11).** v10 named
`write_private_file`, which exists **only** in
`scripts/cuda_bench_driver.py`. Governance code must not import from the
bench-tooling tree, and this seam was recorded in a commit message rather
than in the document — a commit message is not ratified, so it does not
exist for review purposes.

Frozen: **`core/governance/anchored_io.py`**, holding the shared
primitive:

```python
def write_private_file(relative, data, *, root, on_link=None) -> Path
def read_private_file(relative, *, root, expected_uid) -> bytes

# ACTIVATION ONLY — takes NOTHING; see the frozen entrypoint below
def read_migration_receipt() -> bytes
```

**Activation must not take a caller-supplied root (v12).** A generic
reader with a `root` argument lets a caller point activation at a receipt
beside a *different* store.

**v12's signature was unimplementable (v13).** I wrote
`read_migration_receipt(*, store_fd)` and described opening the sibling
receipt "relative to the held store descriptor". A **database fd is not a
directory fd** — verified: `openat` through it raises
`NotADirectoryError`. And resolving `/proc/self/fd/<store_fd>` back to a
pathname to find the sibling would reintroduce exactly the path race the
anchoring exists to remove.

**v13's two descriptors were UNJOINED (v14).** `store_dir_fd` anchored
the receipt and `store_fd` supplied identity, but **nothing proved the
database beneath that directory was the supplied store**. A caller could
pair directory A's receipt with store B's descriptor, and every check
would pass: the receipt is genuine, the store fd is genuine, and they
have nothing to do with each other. I split a single trust root into two
arguments and never rejoined them.

**One descriptor was still one too many (v15).** Collapsing to
`store_dir_fd` stopped directory A being paired with store B — but
`store_dir_fd` **is itself a caller-supplied root capability**. A caller
can hand it directory C containing *both* an alternate database *and* a
matching receipt, and every internal join is satisfied. "No
caller-supplied root" was still false at the public boundary; I removed
one capability and left the other, which is the same defect one argument
over.

**Frozen: the production entrypoint takes NOTHING.**

```python
# PRODUCTION — no path, no root, no descriptor
def read_migration_receipt() -> bytes:
    with _open_canonical_s7_dir() as store_dir_fd:      # opens the ONE
        return _read_migration_receipt(store_dir_fd=store_dir_fd)

# PRIVATE — descriptor injection, for private-copy tests only
def _read_migration_receipt(*, store_dir_fd: int) -> bytes
```

`_open_canonical_s7_dir()` walks the frozen canonical path itself,
component by component with `O_NOFOLLOW`. There is no argument anywhere
on the public route.

**Structural pin:** `_read_migration_receipt` has a **production-callsite
allowlist of exactly one** — `read_migration_receipt`. Any other
production caller fails.

## AMENDMENT (v18) — evidence goes in the NEW room

**Ordering clarification, not new architecture.** The migration builds an
empty legacy voice table and permanently freezes it, and the source
identity requires that plane to be **absent** beforehand. So a witness
that validates voice evidence and then migrates cannot exist: validating
first makes the store match neither source nor target, and validating
afterwards writes a frozen table.

Frozen order for any guarded-route witness or production path:

1. migrate the store while the voice plane is **absent**;
2. persist the source bundle into the **v2** plane via
   `put_voice_source_bundle_v2`;
3. read it back via `read_voice_source_bundle`;
4. produce the **v2** validation result in that same activated store;
5. only then authorize the write.

**Rejected, and recorded so they cannot return:**

* **Cross-store v1 validation** — borrowing a validation result produced
  in another database. It may prove transaction mechanics, but it
  certifies a migrated route using an **audit-only v1** result and proves
  nothing about production reachability.
* **A new in-memory / non-persisting validator** — it bypasses the frozen
  durable v2 bundle, decoder, version, action and binding-hash joins,
  which are the joins the evidence plane exists to carry.

The validation result must be **genuinely v2 validator-produced and bound
to the exact bundle, action and binding hash** — never a v1 token
borrowed from another database.

## AMENDMENT (v17) — two authorities, not one

**Canon conflated "which store is live?" with "does this already-held
store carry a valid activation receipt?"** The zero-argument reader
answers only the first. Private copies, configured store roots and every
migrated store that is not the canonical one need the second, and the
canonical reader cannot answer it *by design* — it opens the one frozen
directory and nothing else.

Ruled: **two distinct authorities.**

**1. Canonical activation DISCOVERY — unchanged.**
`read_migration_receipt()` takes no arguments and selects the one live
canonical store. Its private-callsite allowlist of exactly one stands.

**2. Held-store activation VERIFICATION — new, internal.**

```python
_verify_held_store_activation(dir_fd: int, store_fd: int,
                              conn: sqlite3.Connection) -> bool
```

It verifies the receipt for the exact store **already opened for
mutation**, and it must:

* accept **no pathname** and no independently supplied root;
* **retain** the parent-directory fd from the anchored component walk,
  open the database beneath it, and retain both;
* read the sibling receipt **through that same directory fd**;
* validate receipt identity against the **held database fd**, and schema
  against the **same SQLite transaction** that will write;
* carry an **exact repo-wide qualified-callsite allowlist**.

**The parent walk is component-by-component.** Opening the whole parent
path once with `O_NOFOLLOW` protects only the final component —
reproduced: an intermediate symlink was followed and a v2 row landed in
the real target store.

**`readlink("/proc/self/fd/N")` then reopening the directory is
forbidden.** That is pathname re-resolution, which this document already
named as the race the anchoring exists to remove; an earlier
implementation reintroduced it one layer down.

**Rejected:** canonical-only verification, which breaks legitimate
configured and private stores; and simply widening the existing
allowlist, which would preserve the conflation and launder the new path
into canon.

**Binding RED:** no public or production route accepts a path, a root or
a descriptor — asserted from the signatures, not from prose.

The wrapper opens **both leaves itself**, relative to that one anchored
directory, each with `O_NOFOLLOW`:

* `ceremony.sqlite3` → identity comes from **this** fd's `st_dev`/`st_ino`,
  which the receipt's `store_dev`/`store_ino` must match;
* `s7_migration_receipt.json` → the bytes.

There is no argument through which a foreign store could arrive, because
the caller supplies no store at all. No path is re-resolved.

**Binding REDs:** directory A's receipt with store B is inexpressible;
directory C carrying both an alternate database and its matching receipt
is inexpressible; and any production route that grows a path, root or fd
parameter fails the structural pin.

**File predicates it enforces**, which v11 omitted entirely:

* **regular file** — not symlink, fifo or directory;
* owner uid matches, mode `0600`, `st_nlink == 1`;
* **bounded size** — `S7_MIGRATION_RECEIPT_MAX_BYTES = 8192`, an exact
  constant; "a fixed cap" named no number and so fixed nothing;
* **short reads refuse** — `len(data) == st_size`, never "read what came";
* **pre/post stat stability** — `dev`, `ino`, `size`, `mtime_ns`,
  `ctime_ns` identical before and after.

The generic helper stays for bench callers; activation uses only the
wrapper.

Anchored component walk, `O_NOFOLLOW` at every component, `O_TMPFILE`,
`write_all`, `fsync(file)`, exclusive `link`, `fsync(parent)`, `0600`,
single-link and uid predicates on read. `scripts/cuda_bench_driver.py`'s
copy is **refactored to import this**, never the reverse — the dependency
points from bench tooling to governance, not from governance to bench
tooling.

The receipt is read back through exactly two routes, and no others
(**amended v17**): `read_migration_receipt()` for CANONICAL DISCOVERY,
and `_verify_held_store_activation()` for HELD-STORE VERIFICATION of a
store already opened for mutation. The generic
`read_private_file` is for bench callers and is **not** an activation
route — v12 said it was, three sections after freezing the wrapper that
replaced it.

**Journal and synchronous posture, frozen (v6).** Under WAL, fsyncing
only the database file does **not** establish the commit durability v5
claimed. Migration requires `journal_mode=delete` and
`synchronous=FULL`, verified before it begins and refusing otherwise; the
commit is then followed by fsync of the database **and** its parent
directory. This is the same two-stage posture check the cutover store
opener uses, for the same reason.

**No-backfill is asserted, not merely stated:** both v2 counts are
verified **0 immediately before the receipt is published**, and bound
into it as `row_count_v2_*_at_migration`. Consumers check the *bound*
values, never the live tables — checking live counts would make S7
deactivate itself on its first real artifact.

**Every activation consumer revalidates** before treating v2 as live:

* the receipt is read through the canonical-discovery route,
  `read_migration_receipt()` — the sole *discovery*
  activation route, never the generic `read_private_file` — opening both
  leaves under one anchored directory and enforcing
  regular-file, uid, `0600`, single-link, `<= 8192` bytes, short-read
  refusal and pre/post-stat stability;
* its bytes **decode canonically** and round-trip byte-identical;
* **both** activation fingerprints match the live planes — which now
  includes every trigger;
* both `from_fingerprint_*` match the pinned v1 literals;
* the receipt's `row_count_v2_*_at_migration` fields are **0** — a
  statement about migration time, **not** about the live tables now;
* `store_dev`/`store_ino` match the store actually held.

**Failure behaviour, exact:** a **missing** receipt means v2 is inert and
guarded execution refuses. A **corrupt or non-canonical** receipt refuses
and is never repaired or rewritten. A receipt whose fingerprints or store
identity **mismatch** refuses and activates nothing. **Idempotence:**
re-running `s7-migrate-v2` when a valid receipt already exists is a
verified no-op that republishes nothing — it re-verifies and reports, so
a second run cannot mint a second receipt.

### Crash between COMMIT and receipt publication (v12)

The database commits at step 14; the receipt publishes at step 16. **A
crash between leaves exact target tables and no receipt** — and a rerun
would then fail the *source* fingerprint checks at steps 3–4, because the
source planes are no longer pre-migration. v11's idempotence claim was
false in precisely the window my own two-step ordering creates. I opened
that window deliberately and never said what lives in it.

**Frozen classification, performed INSIDE the write lock (v13).** v12
said "before anything else", which reads as *before* `BEGIN IMMEDIATE` —
restoring the very TOCTOU the source-verification move had just removed.
The lock is taken first; classification is step 2a, inside it:

| observed | classification | action |
|---|---|---|
| receipt absent, **source** fingerprints match | not started | migrate (steps 5–13), **COMMIT**, then fsync + publish |
| receipt absent, **target** fingerprints match, both v2 tables hold **0** rows | committed-not-published | verify, **COMMIT the classification transaction** (releasing the lock), *then* fsync + publish |
| receipt present and valid | complete | verify, **COMMIT**, return — no publication |
| receipt absent, neither source nor target matches | indeterminate | **ROLLBACK**, refuse — never repair |
| receipt absent, target matches, any v2 table **non-empty** | indeterminate | **ROLLBACK**, refuse |

**Every branch closes its transaction, and v13's did not (v14).** Every
run opens `BEGIN IMMEDIATE` at step 1, but `committed-not-published` said
"resume at step 15", **skipping step 14's `COMMIT`** — so recovery would
have held the write lock across the fsync and the receipt publication.
That is the one part of the sequence that must be **unlocked**, since the
receipt rather than the commit is the linearization point; holding the
lock through it would block every other writer on a filesystem operation
and invert the ordering the design rests on.

The `complete` and `indeterminate` branches had no ending at all — a
read-only classification transaction left open until the process exits.

**Binding RED:** recovery **releases the write lock before** fsync and
publication — asserted by a second connection acquiring `BEGIN IMMEDIATE`
during that window.

The non-empty check is what makes resumption safe: v2 is inert without a
receipt, so v2 rows cannot legitimately exist yet. A non-zero count means
something happened this procedure cannot explain, and refusing is the
only honest response.

Recovery stays **owner-invoked** — a branch of the same command, never an
automatic self-heal on open.

**A receipt may appear after the absence check.** Classification runs
under the database lock, but the receipt lives on the filesystem, outside
it. Frozen: publication is an **exclusive create** (`O_EXCL` via the
anchored writer). If a concurrent run published first, **this run loses
the race**, and must then **re-read and verify the winner** rather than
treating its own loss as failure — if the winning receipt verifies, the
store is activated and this run reports `complete`; if it does not, this
run refuses. Losing a race is not the same as an invalid store, and
conflating them would turn a benign double-invocation into an
unexplained refusal.

**The recovered receipt must disclose that it is recovered.** After a
crash the original `started_at` is **unknowable**, and stamping the retry
would make an interrupted migration look uninterrupted. Frozen field:

```
activation_path: "fresh_migration" | "committed_recovery"
```

with `started_at` and `completed_at` **defined as belonging to the
activation attempt that published the receipt**, not to the original DDL
transaction. On `committed_recovery` the document therefore says plainly
that the DDL happened at an unrecorded earlier time. An audit trail that
cannot distinguish these two is one that quietly launders a crash.

**Crash-after-COMMIT RED:** interrupt between commit and publication;
rerun; assert it classifies committed-not-published, publishes, and
activates — and that the same rerun **refuses** if any v2 row exists.

**Normal store opening is verification-only.** It may read and verify a
fingerprint; it may **never** create, alter, migrate or commit. Enforced
structurally, given `daemon/maez_daemon.py:1056` already constructs the
mutating store on the live request path.

## RED contract

**Joins** — one mutation-killing RED per link:
envelope==rendered, rendered==artifact, artifact==row, row==grant,
grant==runtime; plus the **four** caller-action==rendered-action
joins from S3, and separately the row==rendered join for
`consume_verified`.

**Routes** — every site in the **mechanically derived** inventory is
structurally pinned, by role; adding an unpinned site in any role fails.
The count comes from the table, never from prose — three different
hand-counts in one document is what produced this rule.

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

**v7/v8 rules** — each with its own mutation-killing RED:
* an **absent** voice plane migrates to **empty and frozen**, exactly:
  the table exists, is empty, and all three freeze triggers abort;
* the guard **recomputes** both fingerprints from the frozen DDL and
  compares them to the **committed constants** — it never emits them;
* **dropping or altering any trigger refuses activation** — the property
  v5's fingerprint could not see;
* a **forged** validation result (constructed without the validator
  token) refuses at the mint;
* a genuine result paired with a **substituted bundle** refuses;
* migration-time zero counts **bind into the receipt**, while a
  legitimate **non-zero live count after activation stays admissible** —
  the rule that would otherwise deactivate S7 on its first real artifact;
* the **exact qualified allowlist** matches, **including multiplicity**,
  so a second call in the same function cannot hide.

**v9 rules**
* generation and verification are **separate programs**: the one-shot
  generator writes the constants, the guard only ever compares against
  them, and migration and activation import the constant rather than
  deriving it from the schema under test;
* a source plane mutated and **committed before** the lock is acquired is
  seen by the in-lock fingerprint check and **refuses**;
* a competing writer **after** acquisition cannot interleave — it blocks
  until the migration commits or rolls back;
* a validation result constructed **without the token** refuses;
* every row of the valid-state matrix constructs, and no other
  combination does;
* both writer **definitions** are pinned by class-qualified name.

**Invariance**
* credential rows and **sign counts unchanged** by any of this;
* the live DB and its sidecars are **externally measured** identical
  before and after every test — content hash, size, `mtime_ns`,
  `dev`/`ino`, **mode, uid, gid, link count**, the **complete sidecar
  set** (`-journal`, `-wal`, `-shm`, `.bak`), and the **parent
  directory's entry list** — taken outside the process under test rather
  than by the code being tested. A new sidecar or a changed mode is a
  write.

## The migration command's authority (v7)

"Owner-authorized `s7-migrate-v2`" named no enforceable input — it was a
word, not a contract. It cannot be S7-authorized without circularity:
S7 v2 is not active until this command completes.

**My v7 framing was too broad and narrowed the owner's choice.** I wrote
that this "cannot be S7-authorized without circularity". What is true is
narrower: it cannot use **the v2 grant it is installing**. An
**independent founder-WebAuthn bootstrap assertion** — binding the store
identity, both source and target fingerprints, and the exact migration
action — does not depend on v2 at all. By collapsing "cannot use the
thing it installs" into "cannot be authenticated", I removed a real
option from a decision that is his.

## R7 — RULED 2026-08-07 by the owner: PROCEDURAL, because pre-birth

Owner's words: *"It doesn't need that as birth event hasn't happened
yet."*

**Option (a), and for a reason neither lane considered.** Both review
lanes and I recommended key-gating. All three of us were reasoning inside
the authority regime as though it were already live. It is not: **Maez has
not been born.** The key ceremonies exist to govern changes to a living
being; before birth this is construction of the nursery, not an act upon
the occupant.

That is a covenant distinction, not a convenience one, and it is the
owner's to draw.

**Scope of this ruling, stated narrowly so it cannot spread:**

* it covers the **migration command only** — the one that installs the
  v2 substrate;
* it does **not** reopen the cutover ruling. The owner ruled the cutover
  key-required (*"Yes it is Maez's brain we are changing"*), and that
  stands;
* it does **not** license procedural authority generally, and it expires
  at birth: after the birth event, an equivalent installation command
  would need its own ruling.

**Still recorded honestly:** any same-UID process can invoke this command,
and owner presence is not authenticated. That remains true; the ruling is
that it does not matter *yet*.

## SCOPE — RULED: finish S7 first, so Maez knows it also ran on Vulkan

Owner's words: *"Let us finish the fix first, so that it knows it also ran
on vulkan."*

The reason given is **not** a security one, and it is worth recording as
given: the cutover should enter Maez's history as a real, properly
authorized act — *this being ran on Vulkan, then moved to CUDA* — rather
than as a change that simply happened to it. Doing the switch through an
authority layer that cannot say what it authorized would make that record
thinner than the event.

Continuity of self-knowledge, not threat mitigation.

---

### Historical: the two options as I framed them before the ruling

**Two honest options, for R7:**

**(a) Owner-typed procedural command.** Authorized by Rohit running it.
Explicitly acknowledged: **any same-UID process can invoke it, and owner
presence is not authenticated.**

**Correction: this is NOT the posture already ruled on.** I wrote that it
was. Procedural presence was the v9-era *proposal* for the cutover, and
it was **withdrawn** once the enrolled credentials were discovered —
Rohit then ruled the cutover **key-required with no procedural
fallback**. Option (a) would therefore be a **new, narrower exception**,
not a continuation of accepted practice. Framing it as precedent would
have made the weaker option look like the settled one.

**(b) A separate founder-key bootstrap ceremony**, not depending on S7
v2, binding store identity, both fingerprint pairs and the exact
migration action. Stronger, and it means the thing that installs the wall
is itself key-gated.

Under **(a)**, the command has:

* no authorization document to forge, because there is none;
* a **durable receipt** afterwards, which is the auditable artifact;
* an **offline precondition** — it refuses while the daemon is running;
* no capability to mint, consume or alter any authorization row. It
  creates tables and triggers and nothing else.

That is weaker than the ceremonies it enables, and it is named as such
rather than dressed up. ~~This requires the owner's explicit ratification
(R7)~~ — **RULED 2026-08-07**: procedural, because the birth event has not
happened. See the R7 section above for the ruling and its narrow scope.

## Carried

**Nothing.** R7 is ruled (procedural, pre-birth only) and scope is ruled
(finish S7 first). The former "two real options" bullet is deleted rather
than struck through — a live question that has been answered, left
readable, is one somebody re-opens.
