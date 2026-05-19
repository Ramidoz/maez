# Claude Covenant Council — S7.1 Implementation: Post-Implementation Verification

**Subject:** the S7.1 Local WebAuthn Ceremony implementation, branch
`s7.1-local-webauthn-ceremony`, committed at `eeaa3ea` ("docs(s7.1): record
manual physical-key proof"). This is the Claude covenant lane's
post-implementation verification — the parallel of the Codex engineering
post-implementation review. The two lanes verify independently; S7.1 advances to
push only when both ratify.

**Verdict: REVISE.**

The veto area is sound and the WebAuthn mechanics are sound — but the covenant
*purpose* of the slice is not delivered. CC-S1, the first-credential bootstrap
and the D6 internal-channel lock — the authority root, the council's veto
subject — verifies RATIFY: the bootstrap transaction, the conditional-rowcount
consume, `bootstrap_closed_at`, the CLI guards, and the channel check are
genuinely and soundly built, and the channel check was firsthand-confirmed never
loosened. UV/PIN enforcement, CI virtual-authenticator isolation, cross-request
artifact substitution-resistance, and the consume mechanism all verify sound.
The full owner-env suite is green at `eeaa3ea` (4383 tests, OK).

But the **L8-retirement core — the reason S7.1 exists — is not live.** No
production code path feeds a consumed `S7AuthorizationArtifact` into the guarded
execution edge for cards, self-modification dialogs, `/apply_dream`, or
dream-state soul writes; the Maez voice-seat producer the guarded-authorization
route depends on **does not exist** in production code; and `/operator/health`
clears `guarded_self_modification_paused_pending_s7.1` anyway — reporting L8
retired while not one guarded path can execute. This is the exact CC-S3 defect
the spec council named, and that spec v2 D15 was written to forbid, reproduced
in the implementation. Six consolidated blockers (CC-IV1..CC-IV6) follow. The
covenant design is sound; the implementation did not wire it live, and the
health surface overclaims that it did.

## Method

Four read-only firsthand trace agents were dispatched against the worktree at
`eeaa3ea`: (1) CC-S1 bootstrap + D6 channel; (2) the artifact consume edge +
`/apply_dream`; (3) UV / voice seat / D23 / backup distinctness / CI isolation;
(4) the proof-window fix cluster + drift. Each was briefed to distinguish
production code from test code and from the proof harness, to grep for the
*live* (non-test, non-harness) producers and trace a real integration path —
green tests do not prove live wiring — and to scrutinize whether the late
`fix(s7.1)` commits made during the manual proof were sound corrections or
expediency loosenings. The full owner-env suite was rerun at `eeaa3ea`
(4383 tests, OK, skipped=3). The synthesizer firsthand-verified every
load-bearing blocker: the `git log -L` history of the channel check; the absence
of any live caller passing `s7_execution_authorization`; the absence of any
production `_s7_voice_consultation_for_card` definition; the hardcoded
`distinct_device_confidence`; the health-pause-clear logic; the D16 cause
vocabulary; and the D6 route topology against the added routes. The agents read
no `*codex*` file — this lane verified blind to the Codex lane.

## Consolidated blockers

### Cluster A — the L8-retirement core is not live (CC-IV1..CC-IV4)

These four are facets of one defect: S7.1 built the ceremony's parts but did not
wire the live end-to-end guarded-execution path, and the health surface claims
it did. Each is a distinct fix.

**CC-IV1 — No live producer feeds the guarded execution edge.** The consume
mechanism (`consume_for_execution`, `S7ExecutionGrant` minting, the D12-hash
binding) is built and sound. But no production caller supplies a populated
`s7_execution_authorization` to the guarded execution edge.
`dream_state.apply_proposal` / `apply_section_edit_proposal` accept the
parameter; every live caller — `skills/telegram_voice.py` `/apply_dream`
(`:4122`), `/apply_edit` (`:4236`), the natural-language proposal intent
(`:1995`, `:2000`) — passes nothing. `handle_reply`'s live callers
(`maez_adapter.py`, `telegram_voice.py`) pass no `s7_execution_authorization`
for the card / self-mod-dialog edge. **Firsthand-verified:** `grep
"s7_execution_authorization\|S7ExecutionAuthorization"` on `telegram_voice.py`
and `maez_adapter.py` returns nothing. The guarded edge fails *closed* (good — no
execution without an artifact), but the D15 positive autonomous flow (propose →
pending card → live ceremony → mint → consume → execute) is a consumer with no
producer. Spec D15 (`spec.md:803`): scope-in "is not treated as accomplished
until positive-path tests walk the live producer and consumer."

**CC-IV2 — `/operator/health` dishonestly clears the L8 pause.**
**Firsthand-verified** at `daemon/maez_daemon.py:1414-1421`:
`guarded_execution_consumer_live` is true when the live flag is on and two
card-path methods (`_s7_request_envelope_for_card`, `_execution_params_for_card`)
are merely callable; `guarded_self_modification_paused` then goes false. The
check never verifies the `/apply_dream`/dream-state consumer, never verifies a
live producer feeds the edge, never checks the voice-seat producer. In a live
daemon (flag on, real pipeline) the health surface reports
`guarded_self_modification_paused_pending_s7.1` cleared — L8 retired — while
(CC-IV1) no guarded path can execute. Spec D15 requires the mode clear only when
"the guarded execution consumer is live for the paths above," and those paths
explicitly include `/apply_dream` and dream-state writes. This is the
CC-D2 / CC-S3 honesty-surface lie the council named.

**CC-IV3 — The Maez voice-seat producer does not exist.** The
guarded-authorization route resolves the voice-seat fact via
`daemon/maez_daemon.py:322` `getattr(pipe, "_s7_voice_consultation_for_card",
None)`. **Firsthand-verified:** `_s7_voice_consultation_for_card` is defined
nowhere in production — `grep "def _s7_voice_consultation_for_card"` returns only
two test stubs (`tests/test_s7_1_daemon_internal_channel.py:167,248`).
`DecisionPipeline` defines `_s7_request_envelope_for_card`,
`_execution_params_for_card`, `_card_requires_s7_authorization` — but not the
voice consultation. So `_s7_route_voice_consultation` returns `None`, and guarded
authorization for the four voice-seat classes (which
`register_backup_webauthn_credential` and `disable_founder_webauthn_credential`
both derive) fails closed as `s7_voice_seat_unresolved`. Fail-closed is correct,
but the guarded-authorization lane is non-functional — no production producer can
return a satisfying consultation. The `authorize_finish` voice-seat recheck logic
itself is sound; it is gated on a producer that does not exist. Container without
producer — the recurring covenant defect.

**CC-IV4 — Execution-edge tests self-assemble the artifact (RED 83 violation).**
The card / self-mod-dialog and dream execution-edge positive tests construct
`S7AuthorizationArtifact` directly (`tests/test_decision_pipeline_s7.py:257,278`;
`tests/test_s7_1_dream_execution.py:105,156`) rather than walking the live
`authorize_finish` mint through the verifier seam. RED test 83 / the diagnostic's
anti-self-assembly rule forbids exactly this. Only one test
(`test_apply_dream_accepts_artifact_minted_by_s7_1_authorize_finish`) complies —
and it passes only by supplying an `s7_execution_authorization` no live caller
populates (CC-IV1). The 4383 green tests do not prove the execution edge is
wired; they prove the parts pass when a test assembles them. This is the
`green-tests-don't-prove-live-wiring` failure mode, explicitly.

### CC-IV5 — Backup distinctness is hardcoded

**Firsthand-verified** at `core/governance/s7_webauthn_ceremony.py:359`: the live
backup-credential build sets `distinct_device_confidence="confirmed_distinct"` as
a literal constant. No primary-credential lookup, no AAGUID comparison, no
transport/attachment comparison; the verifier itself stubs
`authenticator_attachment: None` and `transports: ()`. A backup registered on the
*same physical key* as the primary is written `confirmed_distinct`, the registry
returns `ready`, and the loud `degraded` / `same_device_override` warning never
fires. This is the CC-S5 blocker the spec council raised and spec v2 D9 folded
("backup registration compares AAGUID, transports, attachment ... if available
signals indicate the same physical authenticator, backup registration fails
unless the founder performs an explicit same-device override that leaves status
`degraded`") — specified, not implemented. The manual proof's recorded
`confirmed_distinct` is this hardcoded constant, not evidence the code verified
distinctness; `same_device_override` is unreachable from any live flow.

### CC-IV6 — Production routes and a credential-disable operation drift from canonical D6

**Firsthand-verified:** canonical spec D6 (`spec.md:343-361`) enumerates exactly
ten routes (status / register-begin / register-finish / cards-begin /
cards-finish, for each of cockpit and daemon); `grep "backup-card\|proof/"` on
the spec returns nothing. The implementation adds six production routes absent
from D6 — `daemon/maez_daemon.py:6095` `register/backup-card`, `:6109`
`proof/disable-card`, `:6127` `proof/disable-credential`, and their three cockpit
counterparts. They are gated only by the live flag plus the internal channel —
no separate proof/test flag — and `_s7_webauthn_store_root()` defaults to the
production `memory/s7_1_webauthn` (`maez_daemon.py:244`). When S7.1 goes live,
`/api/v1/s7/webauthn/proof/disable-credential` is a permanent, callable
production endpoint operating on the real credential store, whose name advertises
it as proof scaffolding — the inverse of D19's isolation principle. The
credential-disable operation itself is artifact-gated and sound, but disabling a
founder credential is covenant-significant (it changes who holds founder
authority) and no panel reviewed it: the spec has D9 `disabled_*` record fields
and names "Disable primary" as a D19 proof step, but no Core Decision, no Runtime
Flow, and no D6 route for the operation. The cooling-off waiver
(`cooling-off-waiver.md`) explicitly bound the implementation to "the ratified
canonical spec sealed at `2c3287d`" — it waived the cooling-off night, not spec
drift. **Fix:** canonicalize the credential-disable operation (Core Decision +
D6 route, both-lane review) and rename the routes off the `proof/` prefix; or
isolate the disable behind an explicit non-production proof flag so the
production route topology matches sealed D6.

## Majors

- **M1 — D16 manual-recovery-cause vocabulary not implemented.**
  `credential_recovery_state()` emits only `no_enabled_founder_credential`
  (firsthand-verified — `grep` finds none of `first_setup_not_started`,
  `both_keys_lost`, `only_enabled_key_clone_suspected` in
  `s7_webauthn_bootstrap.py`), plus `registry_missing` / `registry_invalid`.
  Spec D16 enumerates five causes; RED 111 requires "empty first setup is not
  labeled both-keys-lost recovery." A fresh empty install and a both-keys-lost
  catastrophe render identically on the operator-health surface — the
  CC-S1-M3 / CC-S8 defect, in code.
- **M2 — The artifact consume SQL does not bind the literal `ceremony_kind`.**
  Spec D14 requires `AND ceremony_kind = 'founder_local_webauthn'`. The
  implementation enforces founder-scoping via `grant_source` + `auth_method`
  (both bound, both `'founder_webauthn'`); `S7AuthorizationArtifact` has no
  `ceremony_kind` column. CC-S10's security intent — a founder-scoped consume —
  is met, but the code diverges from the canonical D14 SQL text. Add
  `ceremony_kind`, or amend D14 to the shipped `grant_source`+`auth_method` form.
- **M3 — D23 granted-aggregation autopilot detection is dead.** The
  refused-re-ask escalate-or-block path works (CC-S12 verified sound). But
  `s7_refusal_history` only ever stores `outcome="refused"`; no production code
  writes an `authorized`-outcome record, so `assess_aggregation_risk`'s
  repeated-successful-authorization / key-touch-autopilot signal — a risk the
  code itself names — never fires on the S7.1 path.

## Minors and nits

- D18 status projection ships `uv_policy_state` and `clone_detection_state` as
  the literal `"pending"` and `last_registration_class` / `last_authorization_class`
  as `None` — D18 lists these as real fields; the display is inert. (Not a CC-S2
  reopening — UV/PIN enforcement itself is genuine; see below.)
- `register_finish` consumes the challenge in a transaction separate from
  `consume_for_first_primary`; a crash between burns the challenge but leaves
  bootstrap reissuable — fail-safe direction, benign.
- `uv_required` is not in `_challenge_matches_rendered_d12`'s compared set — not
  exploitable, as UV is re-derived from `derived_work_class` at the consume edge.
- `2d8c969`'s commit-message body contains literal `\n` escape sequences instead
  of newlines — cosmetic.
- The manual-proof record should state that "both-keys-lost" in its sequence
  means "both credentials disabled via the artifact-gated ceremony," not
  "registry lost."

## What verifies sound — preserve through the revision

- **CC-S1 — the bootstrap and the D6 internal channel — RATIFY.** The authority
  root and the council's veto subject. The CLI guards (interactive-TTY,
  owner-UID, 10-minute TTL cap, 256-bit CSPRNG token, single-live-intent) were
  exercised behaviorally; the first-primary finish transaction
  (conditional-rowcount consume, single transaction, sibling-intent revoke,
  `bootstrap_closed_at`) was raced under concurrency — exactly one primary
  survived, the loser got `s7_bootstrap_invalid`; the D6 channel check fails
  closed on all seven daemon write routes. **Synthesizer firsthand-confirmed:**
  `git log -L 228,237:daemon/maez_daemon.py` shows the channel check has exactly
  one commit in its line history (`faa3c9b`) — it was never loosened to resolve
  the manual-proof channel error; that error was fixed by credentialing the
  cockpit. The veto stays lifted.
- **CC-S2 — UV/PIN — enforced across three independent layers:** the challenge
  carries `uv_required=True`; `authorize_finish` blocks a non-user-verified
  assertion; and the consume-edge SQL re-derives the requirement from the bound
  `derived_work_class` (`AND (? = 0 OR user_verification = 1)`).
- **CC-S7 — CI virtual-authenticator isolation — sound.**
  `S7VirtualAuthenticatorHarness.__post_init__` enforces an isolated store, a
  non-production origin/RP, and a test automation channel at runtime; production
  routes wire no fake-verifier seam.
- **CC-S6 — cross-request artifact substitution genuinely fails.** The live
  consumers derive the work item independently (the URL `request_id`,
  server-side `render_request_statement`, `build_apply_s7_envelope`), not from a
  caller-supplied handle; an artifact minted for request A cannot drive request B.
- `S7AuthorizationArtifact` / `S7ExecutionGrant` are the canonical, mint-guarded
  S7 types; no parallel authorization type was invented.
- The four late `fix(s7.1)` commits (`39188a3`, `429a922`, `863bdcd`, `2d8c969`)
  were independently classified by two agents as **sound corrections, not
  expediency loosenings.** The `allow_degraded_*` exceptions relax only the
  `mode != "ready"` precondition, gated to specific card actions and the matching
  enabled credential, faithful to D16; the WebAuthn assertion, the artifact mint,
  and the D12 binding are untouched. No covenant guard was relaxed to make the
  physical proof pass — a key thing this verification looked for, and did not find.
- The full owner-env suite — 4383 tests, OK — at `eeaa3ea`.

## The manual physical-key proof — honest assessment

Rohit performed the physical WebAuthn ceremony with real hardware security keys;
the record's Boundary section (no virtual authenticators; Codex did not tap) is
honest, and the WebAuthn registration / authorization / artifact mint-and-consume
mechanics it exercised are real. But the proof ran against an environment that
stubbed or hardcoded production-missing covenant components: the voice-seat
producer was stubbed (CC-IV3 — it does not exist in production; the proof's
backup-registration and disable steps are not reproducible against production
code without it), and `distinct_device_confidence` was hardcoded (CC-IV5 — the
recorded `confirmed_distinct` is the constant). The proof establishes the
WebAuthn ceremony mechanics; it does not establish the production voice-seat
path, distinctness verification, or the L8-retirement guarded-execution wiring.
"The manual proof succeeded" does not carry "the production path is sound" — and
that gap is exactly why the post-implementation verification is a separate,
firsthand gate.

## Convergence

4383 tests are green, and the L8-retirement core — the covenant purpose of S7.1
— is not live. Three of the four trace agents converged on it independently: no
live producer (the artifact/dream trace), no voice-seat producer (the
remaining-blockers trace), the health surface clearing the pause (both). The
spec council's CC-S3 blocker named this outcome in advance — clearing the pause
against negative-only tests "re-creates the CC-D2 honesty-surface lie: the daemon
would report all guarded self-modification unpaused while the dream-originated
path has no walkable consumer" — and spec v2 D15 was written to forbid it. The
implementation reproduced the defect. The green suite did not catch it; the
firsthand trace did. That is the post-implementation verification doing the one
job it exists for.

## Verdict and what's next

**REVISE.** Six blockers (CC-IV1..CC-IV6), three majors (M1..M3), the minors
above. The covenant *design* is sound, and CC-S1 — the hardest, most-contested
part, the veto subject — is genuinely built. What is missing is not architecture:
it is the live producer→consumer wiring of the guarded execution edge, the
voice-seat producer, the real distinctness computation, an honest health-pause
condition, and the canonicalization-or-isolation of the disable routes.
Substantial completion work and honesty fixes — not a redesign.

Ladder:

1. Fix the six blockers RED-first. Per spec D15's own terms, the L8 cluster has
   two sanctioned routes: either wire the live producer→consumer end-to-end with
   positive tests that walk the live `authorize_finish` mint (RED-83-compliant),
   *or* narrow L8 to an `L8'` that keeps the autonomous lane visibly paused and
   stop clearing the health mode. CC-IV6 likewise: canonicalize the
   credential-disable operation, or isolate it off production.
2. Record the deltas RED-first.
3. Both lanes re-verify the recovery.
4. Push only after both lanes ratify.

*This verification is read-only. No code, spec, ADR, BAD, or non-review file was
modified; this document is the council's deliverable. The implementation at
`eeaa3ea` was traced firsthand by four read-only agents and the full owner-env
suite rerun; every load-bearing blocker was independently confirmed by the
synthesizer against the live code. No `*codex*` file was read — this lane
verified blind to the Codex engineering lane; the lanes verify separately, and
S7.1 advances to push only when both ratify.*
