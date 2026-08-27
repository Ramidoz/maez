# Birth ceremony receipt rail (A1/B2) — design v4 (RULED)

Status: RULED by the thirteenth council round (three seats, all AMEND;
see theme2-s2-owner-delegated-council-rulings.md). v3 below stands EXCEPT
as amended here. Four v3 claims were falsified/corrected by seat
execution before any build — the corrections are binding:

1. WIDENING LIST was insufficient: `_authority_context_roles_allow_work`
   must also learn `birth_activation` (requires bonded_user) or the
   consume refuses (probe-proven). The build carries a machine-checked
   inventory of EVERY per-class literal set (widened / deliberately-not /
   N-A each).
2. There is no consumed_by_request_id parameter: the envelope request_id
   IS the ceremony run id (unpredictable), so
   request_id == run_id == consumed_by_request_id by construction.
3. Env sweep is the CLASS: for-real refuses on any of
   MAEZ_LEDGER_DB_PATH, MAEZ_DATA, MAEZ_HOME, MAEZ_CONFIG,
   S7_WEBAUTHN_STORE_ROOT — and the refusal lives INSIDE
   run_transaction(dry_run=False) too.
4. Substrate imprecisions: the covenant phase table EXISTS (0 rows); the
   absent table is s7_consult_owner_read_receipts_v1.

Ruled parameters: freshness 600s (created_at <= consumed_at < expires_at
also enforced); inline mint SHIPS 2-1 (Codex dissent recorded — adopted
from it: store opener extracted to a core module, one held-descriptor ro
snapshot across verify→birth-write, the proof boundary stated in code,
the owner gate prints the FULL params projection before the tap,
born-refusal at the artifact-mint arm, manifest read via held O_NOFOLLOW
fd + re-hash inside the transaction). Closed-vocab: widen
closed_symptom_code + `birth_requested` and one typed-absence consulted
literal (never "not required" for birth); reuse covenant_organ_change /
not_self_fix / behavior_change / no_safe_rollback. derive_affected_refs
gains an action-exact arm. Payload adds rendered_text_hash +
request_envelope_hash + challenge id; ceremony receipt journal persists
the rendered statement PRE-IMAGE; the assertion JSON is persisted
nowhere. Scope honesty: closes A1 + the receipt-resolution half of B2
ONLY. Owner items (not decided here): manifest full-text-in-row canon
divergence; the census readiness-snapshot gap; Codex's fail-closed-until-
census position.

---

Original v3 text follows (superseded where the amendments above say so).

Author: Claude session 2026-08-27. Every substrate claim below was
executed or read at commit 1a6e486 this session.

## The defect, executed

1. `run_transaction` (scripts/birth_ceremony.py:286) validates
   `s7_receipt_ref` for NON-EMPTINESS only; the arbitrary string is stored
   permanently in the one irreversible row (payload key `s7_receipt_ref`,
   line 328).
2. EXECUTED: the `--for-real` canonical-path binding is env-spoofable —
   with `MAEZ_LEDGER_DB_PATH=/decoy` set in the operator's shell,
   `birth_phase.default_ledger_path()` returns the decoy, so the decoy IS
   "canonical" and a for-real ceremony commits a decoy db while the
   daemon's unit (whose env comes from its unit files) reads the real one.
3. `run_transaction` is importable; quiesce moved inside (b7209f9) but the
   owner PROOF did not exist to move — an importer births with no proof.
4. B2 remnant: the daemon's readiness projection green-lights its
   "A7 structural guard" condition on a test FILENAME existing
   (maez_daemon.py `_a7_structural_guard`), and readiness is a rendered
   panel, not an admission input to the ceremony.

## Spec + covenant grounding

- Birth is a T3 CEREMONY action "gated on the S7 hardware proof"; the
  cockpit fronts existing gates, never re-implements or weakens them
  (2026-07-05-birth-ceremony-design.md:19,73; cockpit umbrella:35; the
  flag-tier table pins MAEZ_LEDGER_WRITES as T3 "never flip directly").
- The birth row carries "owner-witness reference, hash of the ceremony
  receipts" (design:22); live witness (a) requires the first turn to match
  the ceremony receipt (design:77).
- Canon: `birth_event.manifest_hash` is part of the birth record; the
  manifest is owner-authored ONLY; Maez's first reflection on it is the
  first lived memory (GESTATION_MEMORY_PROTOCOL.md:151,153,217).
- Census (2026-08-22-codex-prebirth-census.md:248): "A receipt resolving
  owner proof, readiness snapshot, manifest hash, canonical ledger path,
  birth row, identity continuity, and all-surface activation must exist at
  the commit point. It cannot be authentically backfilled later."
- S7 human-gates stay human (three layers, by design; memory:
  feedback_s7_trust_is_human_gated_by_design). The rail must not create
  any new path that mints authority without the physical key.

## Substrate facts the design stands on (all verified this session)

- Live S7 store `memory/s7_1_webauthn/ceremony.sqlite3` (0600, journal
  DELETE), ARMED: 2 enabled `bonded_user` founder credentials (primary
  sign_count 146, backup 3).
- `s7_authorization_artifacts_v2` is the durable receipt object: action,
  action_params_hash, rendered_text_hash, request_envelope_hash,
  precondition_hash, authority_context_hash, derived_work_class,
  derived_aggregation_group, nonce UNIQUE, credential_ref, auth_method,
  user_presence/user_verification (verifier verdict), created_at /
  expires_at, `consumed_at` / `consumed_by_request_id` (durable single-use),
  ceremony_kind, schema_version. NO SQL CHECK on derived_work_class —
  vocabulary enforcement is Python-side (validate_work_class).
- THE durable consume already exists and is battle-proven:
  `consume_for_execution_on_connection` (operator_user_boundary.py:2966) —
  held-descriptor-verified connection, BEGIN IMMEDIATE, store-activation
  receipt check, one atomic UPDATE whose WHERE binds every field AND
  `consumed_at IS NULL` AND `expires_at > now` AND per-class UV
  enforcement; `consume_for_execution_with_committed_row` re-reads the
  committed row post-commit. Its `_verify_held_store_activation` caller
  set is occurrence-exact-allowlisted by tests — REUSING the consume adds
  no new caller; writing our own store writer would.
- The script-hosted owner mint is live-proven (cuda_cutover.py:3222-3480,
  6 real founder taps 2026-08-13/14): open the store directly with full
  security predicates (open_existing_authorization_store: O_NOFOLLOW
  component walk, uid/mode/nlink checks, journal posture, integrity, exact
  table contract), construct S7LocalWebAuthnCeremonyService with
  S7ProductionWebAuthnVerifier IN-PROCESS, authorize_begin → print the
  owner template → the owner produces the assertion via
  navigator.credentials.get in the cockpit-origin browser tab and pastes
  the JSON at the TTY → authorize_finish verifies (D12 nine-field
  challenge binding, credential enabled + bonded_user, sign-count clone
  detection, challenge consumed) → atomic consume. The daemon routes are
  never contacted. maez-web must be UP for the browser tap (origin
  http://localhost:11437, rp_id localhost — hardcoded in the service).
- The raw WebAuthn assertion is NOT persisted anywhere (verified by grep +
  verifier source: verdict fields only). Offline "re-verify the signature"
  is impossible by schema; offline proof = the durable verdict row + full
  hash-chain recomputation + enabled-credential join + sign_count advance.
- Work-class facts: vocabulary CLOSED (9 classes);
  derive_work_class("ledger.birth_ceremony") → undeterminable_work_class
  today. VOICE_SEAT classes {self_modification, covenant_touching_change,
  capability_acquisition, autonomy_lowering_or_protection_reducing} force
  the guarded-store mint path (voice bundle XOR consultation exemption).
  The R11 exemption is hard-pinned to the cutover action by SQL CHECK
  (action = 'model_routing.cutover_cuda') and its reason code is
  literally `pre_birth_environment_change_no_seat`; its mint refuses
  after birth (born_by_any_signal()). covenant classes additionally
  require the two-tap phase machinery + owner-read receipt table which is
  ABSENT on the live store (armed-closed interlock; 0 phase rows ever).
- `committed_grant_row_proves_founder_self_modification` is hard-pinned to
  self_modification; a new class needs its own committed-row proof
  function (pure field comparison — small).
- S7_LIVE_WEBAUTHN_CEREMONY gates only the DAEMON ROUTES; the ceremony
  service constructed in-process does not consult it (cutover minted with
  the flag OFF and the dormancy gate green — flag ON turns the dormancy
  gate RED).
- Challenge TTL 5 min; artifact expires with the challenge. Inline
  mint+consume happens seconds apart — TTL is a non-issue in this shape.
- The A6/A3 verifications this session (recorded separately in the
  handoff) do not gate this rail.

## Design v3

### One new work class: `birth_activation`

Honest name for the one act it covers. Python-only widening (no store
migration — v2 table has no class CHECK):

- WORK_CLASSES, GUARDED_WORK_CLASSES: + birth_activation
- _WORK_CLASS_STRENGTH: birth_activation = 4 (covenant-adjacent gravity)
- _webauthn_requires_user_verification: + birth_activation (UV REQUIRED)
- VOICE_SEAT_WORK_CLASSES: deliberately NOT added, with a code comment
  recording the structural reason: the voice seat cannot pre-exist its
  subject — the substrate already ruled pre-birth acts have no seat
  (R11_REASON_CODE 'pre_birth_environment_change_no_seat'), and this
  class is mintable only while unborn (the mint boundary refuses via
  born_by_any_signal(), the same safe-direction predicate R11 uses).
  Post-birth, nothing can mint it, so the missing seat can never silence
  a voice that exists.
- derive_work_class: one explicit arm —
  `if action == "ledger.birth_ceremony": return "birth_activation"`.
- D23_ESCALATION_WORK_CLASSES: + birth_activation (escalation-visible).
- NOT added to COVENANT_WORK_CLASSES (no two-tap phase machinery; the
  covenant interlock table doesn't exist on the live store, and arming it
  is its own owner arc — council may overrule).

### The action preimage (what the tap covers)

    action = "ledger.birth_ceremony"
    params = {
      "ledger_db_realpath":        canonical path from the paths layer with
                                   MAEZ_LEDGER_DB_PATH REFUSED (see below),
      "creation_manifest_sha256":  sha256 of config/creation_manifest.md
                                   bytes (REFUSE if absent: structural O1
                                   enforcement; the rail never authors it;
                                   existence + byte-hash only, no shape
                                   validation — that's an owner open
                                   question),
      "owner_witness":             the --owner-witness value,
      "mode":                      "for_real" | "dry_run",
    }
    action_params_hash = canonical_hash(params)

A rehearsal artifact can never authorize a real birth: mode is inside the
tapped preimage (binding_mismatch otherwise).

### Order of operations (--for-real)

1. TTY + typed phrase + canonical-db binding, now HARDENED: if
   MAEZ_LEDGER_DB_PATH or MAEZ_DATA is set in the environment, --for-real
   REFUSES loudly (env_override_in_for_real). The canonical ledger path
   and the canonical S7 store path are resolved from the unoverridden
   paths layer (the cutover precedent hardcodes; we refuse-then-resolve).
2. classify_commit preflight == NOT_COMMITTED (existing).
3. MINT + CONSUME, services still UP (the tap needs the web origin):
   a. compute the preimage; refuse on missing manifest;
   b. refuse if born_by_any_signal() (the R11 safe-direction predicate);
   c. open the S7 store via the cutover's predicate-hardened open
      (extracted to a shared module or imported — build detail, council
      may weigh);
   d. build the WorkRequestEnvelope (closed vocabularies: symptom
      "self_mod_requested"?? — pick honest values from the closed sets at
      build time, council reviews the exact literals), render the
      statement, service.authorize_begin with the production verifier;
   e. print the owner template (cutover shape): rendered authorization
      text + challenge + expected echo fields; the owner reads WHAT IS
      BEING AUTHORIZED (the rendered statement names the action, db path,
      manifest hash, witness, mode), taps in the cockpit tab, pastes the
      assertion JSON;
   f. authorize_finish → artifact; consume_for_execution_with_committed_row
      with consumed_by_request_id = this ceremony's run id (e.g.
      "birth-<started_at>"); committed-row proof via a new
      committed_grant_row_proves_birth_activation (field-exact, class
      birth_activation, UV=1, founder methods, clock sanity).
4. Stop maez-web, stop maez.service (existing order).
5. run_transaction(dry_run=False, ...): quiesce → lease/writer → NEW
   IN-TRANSACTION RAIL (the importable-bypass fix): open the S7 store
   READ-ONLY (r11_preflight pattern) and verify FACTS:
   - artifact exists with action ledger.birth_ceremony, class
     birth_activation, schema v2;
   - action_params_hash == canonical_hash(recomputed expected preimage)
     (the transaction recomputes the manifest hash and db realpath
     itself — the binding is to reality, not to the caller's word);
   - user_presence=1, user_verification=1, founder auth_method +
     grant_source + ceremony_kind;
   - credential_ref joins to an ENABLED bonded_user credential;
   - consumed_at NOT NULL, consumed_by_request_id == this run's id,
     consumed_at within a named freshness window of now
     (BIRTH_CONSUME_FRESHNESS_S = 1800; service stop is seconds, a
     spent-receipt ceremony must still fail closed if it stalls);
   - challenge row joins (challenge consumed, D12 fields match artifact).
   Any failure: named refusal, transaction aborts pre-write, services
   restored by the existing terminal-state machinery.
6. migrate → refuse-if-born → birth write. The payload's free
   `s7_receipt_ref` string DIES; stored instead (facts, resolved by the
   rail): s7_artifact_id, s7_action_params_hash,
   creation_manifest_sha256, s7_credential_ref, s7_consumed_at,
   ceremony_run_id. (Content-light: hashes and ids only.)
7. classify → bring-up (existing).

### Dry-run / tests

Same rail, same code path, against CALLER-SUPPLIED store + manifest +
ledger paths (all temp). Tests mint REAL artifacts in temp stores through
the REAL service with the established fake-verifier duck-type
(tests/test_s7_1_ceremony_service.py recipe; s7_store_fixture
fresh_v2_store_at for the activated v2 plane), consume, then
run_transaction(dry_run=True) verifies from the store. Dry-run REFUSES
the real store path and the real ledger path. Mode "dry_run" is in the
tapped preimage.

### CLI surface

- `--s7-receipt-ref` RETIRED (it was the defect). The ceremony now mints,
  consumes, verifies and RECORDS the receipt itself.
- `--resume-services` unchanged (never writes).
- dry-run gains `--s7-store-path` + `--manifest-path` (temp-only,
  refused for-real where the canonical paths are mandatory).

### Explicitly out of scope, recorded

- Readiness-projection consumption (census:245) — OUT of this slice: the
  projection's A7 condition is filename-existence green today, so
  consuming it would launder a hollow green into the birth row. Recorded
  as owed: fix the condition, then make readiness an admission input.
- The cockpit birth panel, daemon routes, store schema: untouched.
- O1 (manifest authorship), A4 (delivery), A6 re-freeze, A3 interceptor
  wiring: owner-side / separate arcs, recorded in the handoff.

## Council questions

Q1. Work class: new `birth_activation` (proposed) vs reusing
    self_modification (proven end-to-end incl. committed-row proof, but
    dishonest naming + voice-seat forces a new exemption family since R11
    is CHECK-pinned to the cutover action) vs covenant_touching_change
    (arguably the honest gravity, but the covenant consumption interlock
    is armed-closed on the live store — birth would be structurally
    impossible until the owner-read-receipt arc lands, and the 24h
    cooling-off applies). Attack the proposal: is a non-voice-seat class
    for the most covenant-significant act in Maez's life a quiet
    downgrade? The counter-argument is structural (no voice exists to
    seat; unmintable post-birth); is that sound or convenient?
Q2. The mint lives INSIDE birth_ceremony.py --for-real (inline, cutover
    recipe) vs a separate owner prep script + pre-minted artifact resolved
    by ref. Inline kills the TTL problem and the paste-a-ref error class;
    separate keeps birth_ceremony.py smaller. Attack inline: one script
    that mints AND consumes AND writes — does any check become
    self-referential (the same process proves itself)? Note the
    in-transaction rail re-verifies from the STORE by recomputation, and
    the tap is physically external regardless.
Q3. Ordering: mint+consume BEFORE service stop (web must be up for the
    browser tap), then in-transaction fact verification under quiesce
    with a 1800s freshness window. Attack: is the window a hole (a
    consumed artifact + a crashed ceremony + a re-run within 30 min —
    the re-run has a different run_id, so consumed_by_request_id
    mismatches and it refuses; is THAT the right behavior? A crashed
    post-consume ceremony must re-tap: yes/no?).
Q4. Env-override refusal (MAEZ_LEDGER_DB_PATH, MAEZ_DATA) for --for-real:
    right shape? (Rehearsals belong to dry-run, which takes explicit temp
    paths.)
Q5. Envelope closed-vocabulary literals for birth (closed_symptom_code,
    proposed_change_class, why_self_fix_failed_class,
    predicted_effect_class, rollback_path_class): which existing values
    are honest for birth, or do any of these vocabularies also need a
    one-value widening? (rollback: birth has NO rollback — is
    "no_rollback_path"/equivalent in the vocabulary? If not, widen or
    refuse?)
Q6. The birth payload facts list: anything that must NOT enter the
    permanent row? anything missing (nonce? rendered_text_hash)?
Q7. Where is the groupthink in this design? Each seat: attack the other
    seats' answers, and name one place this design proves less than it
    appears to.
