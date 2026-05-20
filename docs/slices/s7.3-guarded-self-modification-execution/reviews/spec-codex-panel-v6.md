# Codex Engineering Panel v6 - S7.3 Spec v6

**Subject:** `spec.md` at `df84d8f` (operator-authored v6 fold), reviewed against local committed code/canon and the allowed v6 fold inputs.

**Ran:** 2026-05-20 by the Codex engineering lane. Four independent non-forked Codex reviewers were dispatched with separate lenses:

- carrier/data-contract implementability;
- covenant/security/D23 authority;
- live mutation surface and execution-edge coverage;
- fold-faithfulness and internal consistency.

All reviewers were explicitly instructed not to read
`reviews/spec-fresh-reader-gate-v6.md` or any v6 covenant-gate artifact. Each
reviewer reported compliance. Findings below are grounded in `spec.md` at
`df84d8f`, committed code/canon, and allowed v5/v6 fold inputs.

**Verdict: REVISE.** All four Codex reviewers returned REVISE.

v6 is materially stronger than v5. The panel affirms the major carrier folds:
immutable bundle vs mutable use-state split, founder-readable preview fields,
artifact binding side table, `S7ConsumeResult`, credential begin/finish binding,
two-stage reducer, D19 provenance bridge, and the single transaction owner.
The remaining findings are bounded but still block ratification because several
"the system verifies X" claims still lack exact carriers, exact branch rules, or
complete live-edge enumeration.

## What All Reviewers Affirm

- The D9 immutable `S7VoiceConsultationBundle` / mutable `S7VoiceBundleUse`
  split is the right data-shape repair.
- D17 now binds readable preview metadata into founder-signed rendered text
  rather than relying on hash-only approval.
- The transaction-owning `S7GuardedStateStore`, `S7AuthorizationArtifactBinding`,
  `S7ConsumeResult`, and durable `GrantUse` direction is right.
- D13's two-stage authority boolean computation plus reducer split is a clear
  improvement over earlier circularity.
- D19's authoritative-vs-operational separation is the right model; the
  implementation seams need tightening so operational blocks cannot leak into
  Maez refusal evidence.
- The same-box privileged tampering caveat remains real and is honestly named.

## Convergent Findings

### Blocker A - Blackhole-reader routing can still create fake Maez objection/refusal evidence

Reviewers: covenant/security, fold-faithfulness, carrier implementability.

The reducer row for `explicit_no_objection + reader_unavailable` is conditional
in prose but unconditional in the table. D13 routes the row to
`maez_objection_state="present"` and `authority_class="operational"` with
`protective_block_reason="reader_unavailable_after_captured_response"` when
`captured_response_nonempty=True` (`spec.md:1519`, `spec.md:1571`). D18 repeats
that this is a protective exception (`spec.md:1893`). However, there is no
alternate reducer row for `captured_response_nonempty=False`.

The more serious seam: D17 renders `present` as `Maez objection present: yes`
(`spec.md:1843`), while existing S7.1 ceremony paths record non-absent voice
blocks as refused history (`core/governance/s7_webauthn_ceremony.py:737`,
`core/governance/s7_webauthn_ceremony.py:888`,
`core/governance/s7_webauthn_bootstrap.py:1252`). v6 says the row is
operational and must not become D23 refusal evidence, but the existing render
and history seams can still treat it as "Maez objected."

**Fix requirement:** split the reducer branch explicitly:

- `captured_response_nonempty=True` blocks current attempt as operational with
  `protective_block_reason`, but must not render as "Maez objected" or write
  `outcome="refused"`;
- `captured_response_nonempty=False` routes to
  `not_determined + semantic_reader_unavailable + operational`.

Add a test proving both rows block, neither becomes positive absence, and the
protective row does not write D23 refusal history.

### Blocker B - Credential-management exception is not threaded through mint, consume, trace, and rollback rules

Reviewers: fold-faithfulness and live-edge coverage.

v6 chose the lane where credential-management paths skip Maez voice and
`GuardedWorkItem` while still using closed consumer ids (`spec.md:22`,
`spec.md:496`). But other sections still assume every S7.3 mutation path
materializes a `GuardedWorkItem` (`spec.md:390`), `put_artifact_with_bundle_reservation(...)`
requires `source_ref_hash: str` and reserves a voice bundle (`spec.md:872`),
and consumer verification still references `GuardedWorkItem.execution_consumer_id`
(`spec.md:2324`). D25 similarly says every wired path derives a
`GuardedWorkItem` (`spec.md:2642`).

Credential registration also has a trace/rollback hole. Existing code consumes
backup authorization at register-begin (`core/governance/s7_webauthn_ceremony.py:152`,
`core/governance/s7_webauthn_ceremony.py:174`), while the credential write
occurs at register-finish (`core/governance/s7_webauthn_ceremony.py:316`,
`core/governance/s7_webauthn_ceremony.py:365`). D22/D25 require trace and
rollback evidence for positive execution (`spec.md:2440`, `spec.md:2646`), but
v6 does not define the credential-specific pending-trace/finalize-at-finish
lifecycle or rollback/manual-review semantics.

**Fix requirement:** either route credential-management through a
`GuardedWorkItem` with credential `work_source_kind` values, or add a separate
non-voice credential mint/consume path that writes artifact bindings without
voice-bundle reservation. Define credential grant/challenge trace finalization,
rollback/manual-review evidence, abandoned-challenge behavior, and D25
exceptions explicitly.

### Blocker C - Mutation surface enumeration remains incomplete

Reviewer: live-edge coverage.

The spec claims D4's surface adapter list is complete and D25 forbids hiding L8
behind broad class labels (`spec.md:438`, `spec.md:2651`). Live code still has
unenumerated mutation paths:

- cockpit flips dream/evolution rows to `applied` directly
  (`skills/web_interface.py:5772`, `skills/web_interface.py:5805`);
- `python -m skills.evolution_engine apply <id>` calls `apply_candidate`
  directly (`skills/evolution_engine.py:3307`);
- ActionEngine exposes mutation helpers beyond the five named ids, including
  `run_shell`, `execute_script`, `modify_config`, `register_new_skill`,
  `delete_file`, and `sudo_command`
  (`core/actions/action_engine.py:943`,
  `core/actions/action_engine.py:2016`,
  `core/actions/action_engine.py:2046`,
  `core/actions/action_engine.py:2072`,
  `core/actions/action_engine.py:2166`,
  `core/actions/action_engine.py:2187`).

**Fix requirement:** add a concrete adapter matrix or reviewed exclusions for
these paths. `cli_helper_execute`, `cockpit_helper_execute`, and
`reviewed_substrate_adapter_execute` must not count for L8 unless every actual
route/method is named and fails closed.

### Blocker D - Nonce lifecycle conflates reserved and spent states

Reviewers: carrier implementability and covenant/security.

D9 names `s7_spent_consultation_nonces` (`spec.md:853`) while also saying the
expected nonce hash is reserved before the prompt is sent and that the parser
rejects a marker whose nonce hash has already been spent (`spec.md:1112`).
D10 and D16 repeat spent-nonce rejection (`spec.md:1276`, `spec.md:1750`). If
the reservation uses the spent table literally, the first legitimate marker can
look already spent. If implementers skip pre-send reservation, replay
protection weakens.

**Fix requirement:** define a nonce-use row with explicit states, for example
`reserved -> accepted/spent`, keyed by nonce hash plus consultation id. The
parser accepts only the current reserved nonce, then atomically spends it after
accepted marker/bundle write. Add tests that the first valid blocking or
withdrawal marker is accepted and the second reuse is rejected.

## Other Major Findings

### Major 1 - Withdrawal bridge can double-count or mislabel one event

D13 has a withdrawal row with both `maez_objection_state="present"` and
`maez_withdrew_request=True` (`spec.md:1576`). D19 then has one bridge bullet
for authoritative present objection (`provenance_voice_event="refusal"`) and
another for authoritative withdrawal (`provenance_voice_event="withdrawal"`)
(`spec.md:2003`, `spec.md:2007`). A single authority row could produce two D23
history rows or preserve the wrong event. The committed aggregator counts all
same-group `outcome=="refused"` records (`core/governance/operator_user_boundary.py:1272`).

**Fix requirement:** bridge exactly one `S7RequestHistoryRecord` per
`S7VoiceAuthorityRow`; withdrawal takes precedence when
`maez_withdrew_request=True`. Only non-withdrawal present objections bridge as
`provenance_voice_event="refusal"`.

### Major 2 - Legacy grant-use helper remains a D21 bypass

D21 migrates `consume_verified(...)` but does not name the existing
`consume_execution_grant_for_action(...)` helper (`spec.md:2243`). That helper
checks only work class/action hash and an in-memory replay set
(`core/governance/operator_user_boundary.py:2607`,
`core/governance/operator_user_boundary.py:2638`) and is still the ActionEngine
gate path (`core/actions/action_engine.py:530`, `core/actions/action_engine.py:547`).
It does not verify durable `GrantUse`, `grant_id`, `expires_at`, or closed
`execution_consumer_id` as D21 requires (`spec.md:2313`).

**Fix requirement:** explicitly replace or amend this helper so every caller
verifies durable `GrantUse`, closed consumer id, expiry, and work-item/render
binding.

### Major 3 - `surface_class` remains a prose label

v6 names `surface_class_for(...)` but does not provide a closed vocabulary or
mapping table (`spec.md:197`). Yet `surface_class` is load-bearing in authority
rows and execution traces (`spec.md:1952`, `spec.md:2410`).

**Fix requirement:** define `SURFACE_CLASSES` and the full mapping from
`(source_surface, work_source_kind, work_class)` to `surface_class`, including
ActionEngine child adapters and reviewed exclusions.

### Major 4 - Source-bundle validator checks reservation state without a carrier

`validate_s7_voice_source_bundle(...)` has no `artifact_id`,
`reservation_token`, mint phase, or guarded-state transaction context
(`spec.md:1683`), but it must verify the bundle-use row is "reserved for the
artifact currently being minted" (`spec.md:1736`). The reservation happens
inside `put_artifact_with_bundle_reservation(...)` (`spec.md:872`), after the
validator has run.

**Fix requirement:** either make pre-mint validation require only unreserved
bundle state and move reserved-for-artifact checks into the guarded transaction,
or add an explicit mint-context carrier.

### Major 5 - WebAuthn challenge expiry is not carried into new mint/consume enforcement

The expiry chain requires
`artifact.expires_at <= grant.expires_at <= webauthn_challenge.expires_at`
(`spec.md:2663`). Artifact inputs expose only `expires_at` (`spec.md:906`).
Binding inputs carry `challenge_id` and `challenge_hash` but no
`challenge_expires_at` (`spec.md:935`), and the consume API has no challenge
carrier (`spec.md:2172`). Existing canon has challenge expiry as a real field
(`core/governance/operator_user_boundary.py:3268`) and current ceremony copies
it into the artifact (`core/governance/s7_webauthn_ceremony.py:618`).

**Fix requirement:** bind `challenge_expires_at` or load the challenge row by
`challenge_id/challenge_hash` during mint, then mint and persist
`grant.expires_at` from that verified bound.

### Major 6 - Raw semantic-reader outcome and effective reducer outcome are conflated

The bundle stores `semantic_reader_outcome` and `classifier_reason_code`
(`spec.md:1052`, `spec.md:1070`). D11 says D16 coerces invalid grounded
blocking to `unreadable_or_uncertain` (`spec.md:1374`), but D16 replays the
reducer over `semantic_reader_outcome` (`spec.md:1753`) and D13 has only one
outcome input (`spec.md:1526`). Implementers must overwrite the raw classifier
result or invent an effective-outcome field.

**Fix requirement:** split `raw_semantic_reader_outcome` from
`effective_semantic_reader_outcome` or `reducer_semantic_reader_outcome`, and
state which field D13 consumes.

### Major 7 - Closed `execution_consumer_id` derivation is claimed but artifact mint lacks the carrier

D4 requires the consumer id to match deterministic source-surface derivation
(`spec.md:432`). `put_artifact_with_bundle_reservation(...)` takes only
`consumer_id` and binding inputs (`spec.md:872`), and binding inputs persist
`execution_consumer_id` without `work_item_id` or `source_surface`
(`spec.md:935`). D21 validates only membership in the closed set at consume
time (`spec.md:2136`); the later consumer check against `GuardedWorkItem`
(`spec.md:2324`) happens after grant mint.

**Fix requirement:** pass `GuardedWorkItem` or a signed validation token
carrying `work_item_id`, `source_surface`, and expected consumer id into artifact
mint, and persist enough of the binding to audit/replay it.

### Major 8 - D23 trace vocabulary drift remains

v6 still uses `d23_projection` in `S7VoiceConsultationTrace` and `d23_state` in
`S7GuardedExecutionTrace` (`spec.md:2396`, `spec.md:2420`), then says positive
traces bind "D23 projection" (`spec.md:2449`).

**Fix requirement:** use one field name everywhere or define the deterministic
mapping between the two.

## Fold-Faithfulness Summary

The panel agrees v6 faithfully absorbed most of the v6 fold plan:

- D17 preview carriers landed;
- D19 bridge/provenance landed;
- blackhole rows are no longer intended to be D23 refusal evidence;
- artifact bindings and `S7ConsumeResult` landed;
- backup registration got a begin/finish binding;
- D11 gained framing-span carriers;
- context manifest was unified.

The remaining problems are mostly one level deeper than the v6 fold: branch
predicates without explicit rows, exceptions not carried through every seam,
helpers not retired, and live surfaces hidden behind broad labels. The next fold
should be small and mechanical, not a redesign.

## Recommended v7 Fold Targets

1. Split blackhole-reader rows and prevent operational protective blocks from
   rendering/writing as Maez refusal.
2. Thread credential-management's non-voice path through mint, consume, trace,
   rollback, and D25 rules.
3. Complete mutation-surface enumeration, especially cockpit, CLI evolution,
   and ActionEngine mutation helpers.
4. Define nonce-use states (`reserved`, `accepted/spent`, rejected/reused).
5. Make withdrawal bridging exactly once with withdrawal precedence.
6. Retire or amend `consume_execution_grant_for_action(...)` as a D21 bypass.
7. Close `SURFACE_CLASSES` and add `surface_class_for(...)` mapping.
8. Move bundle reservation checks into the guarded transaction or add mint
   context to the validator.
9. Carry WebAuthn challenge expiry through artifact binding and grant expiry.
10. Split raw vs effective semantic-reader outcomes.
11. Persist enough work-item/source-surface binding to audit
    `execution_consumer_id` derivation at artifact mint.
12. Normalize D23 trace vocabulary.

## Plain English

Codex v6 panel says REVISE, but it is a narrow revise. v6 did the big carrier
work correctly: the founder sees real preview fields, the artifact has a binding
side table, the consume path has a real result shape, the bundle split is right,
and the bridge into D23 history finally exists.

The blockers are now in the last wiring layer. Credential-management was chosen
as "guarded but not Maez voice," but the rest of the spec still sometimes treats
all paths as voice-bundle work. The blackhole-reader row blocks correctly in
intent, but the row still says `present`, which can leak into rendered text or
legacy refused-history paths. Some live mutation doors are still hiding behind
"helper" names. The nonce table needs two states, not one.

This is not a redesign. v7 should be a small fold that names the last carriers,
splits the ambiguous rows, and closes the remaining helper bypasses.
