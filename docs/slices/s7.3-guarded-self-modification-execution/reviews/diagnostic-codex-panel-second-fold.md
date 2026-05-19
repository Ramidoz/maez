# Codex Engineering Panel - S7.3 Diagnostic v2 Fold: Second-Fold Faithfulness Check

**Subject:** `docs/slices/s7.3-guarded-self-modification-execution/diagnostic.md`
at `bed18f0` (the v2 fold), checked against the Codex engineering panel
recorded at `1d3b1d5`.

**Ran:** 2026-05-19, by the Codex engineering lane. Read-only - no code, spec,
ADR, BAD, or non-slice doc was changed in producing this.

**Base verified firsthand:** current `HEAD == ba6a144`, with `bed18f0` as the v2
diagnostic fold and `ba6a144` adding only the Claude second-fold review. The
worktree `diagnostic.md` blob, `bed18f0:diagnostic.md`, and
`HEAD:diagnostic.md` are byte-identical (`ec2af9ca...`), so this check reviewed
the committed v2 diagnostic fold exactly. `bed18f0` touches only `diagnostic.md`;
`1d3b1d5` touches only `diagnostic-codex-panel.md`.

**Method:** v2 was read fresh from disk in full. The Codex panel was read fresh
from disk in full. This check maps each of the 13 Codex fold requirements to the
folded diagnostic and checks whether any Claude-lane additions weakened a Codex
finding. This is a review-artifact faithfulness check only; it does not write
the S7.3 spec and does not authorize implementation.

**Verdict: FAITHFUL.** Diagnostic v2 incorporates all 13 Codex engineering fold
requirements at diagnostic strength. The proof contract no longer clears L8 on
callable methods, boolean flags, shape-matching voice facts, hash-only rendered
approval, hand-built authority, or generic mutation-surface language. One
terminology nit remains for the spec: v2 uses `path`, `surface`, and `surface
class` without defining the grouping. That does not weaken the diagnostic fold
and does not block cooling-off.

## Fold-Requirement Faithfulness - Thirteen Of Thirteen Landed

1. **Reframe health clearing as trace-backed, not callable/flag-backed.**
   Faithful. D4 now requires positive traces for the exact rendered request ->
   reviewed voice fact -> D23 read/write -> artifact mint -> atomic consume ->
   mutation -> rollback record chain, and states that callable methods, boolean
   opt-ins, and placeholder producers must never clear the pause. The as-built
   pause section still names the current helper and opt-in honestly, so the
   diagnostic distinguishes current code from the required proof contract.

2. **Ban hand-assembled voice facts and pre-consume execution handles from
   positive proof.** Faithful. D5 now bans positive S7.3 proof from
   hand-assembling `S7AuthorizationArtifact`, `S7ExecutionAuthorization`,
   `S7ExecutionGrant`, `MaezVoiceConsultation`, raw verifier success,
   dict-shaped grant handles, request ids, or fabricated voice facts. It keeps
   value-object construction available for grammar tests and allows test doubles
   only at explicitly reviewed seams.

3. **Define the `S7ExecutionAuthorization` / `S7ExecutionGrant` boundary.**
   Faithful. The as-built artifact-spine section and D1 both name the real
   chain: `S7AuthorizationArtifact` -> existing pre-consume
   `S7ExecutionAuthorization` carrier -> `S7AuthorizationStore` consume ->
   post-consume `S7ExecutionGrant`. v2 says the store-minted
   `S7ExecutionGrant` is the sole execution authority and leaves any carrier
   rename to the spec.

4. **Require producer-strength proof for `absent` and call out placeholder
   producer-label drift.** Faithful. The voice-producer as-built section is
   retitled "behaviorally honest, but provenance-misleading," names that the
   placeholder uses real candidate-B labels while no producer ran, and requires
   either a distinct placeholder/non-producer value or a rule that producer
   alone never attests. OQ1 preserves `absent` as a strict reviewed producer
   fact.

5. **Add D23 refusal-history provenance and poisoning controls.** Faithful.
   v2 adds an as-built D23 refusal-history subsection and D8. It requires D23
   read/write semantics for every producer and execution edge, distinguishes
   authoritative from pre-auth/non-authoritative rows, and calls for replay,
   rate, and provenance controls against poisoning future aggregation history.

6. **Require human-readable mutation display or a reviewed display artifact.**
   Faithful. D3 now says the founder-approved rendered request must include
   deterministic, bounded, human-readable mutation material, or a reviewed
   display artifact bound by hash. It explicitly says hash-only approval does
   not satisfy S7.3.

7. **Add guarded-execution trace schema requirements.** Faithful. v2 adds the
   as-built "Trace and rollback records are not yet S7.3 proof" section and D7.
   D7 requires durable binding of request id, request envelope hash, rendered
   text or display-artifact hash, action params hash, precondition hash,
   authority context hash, voice consultation hash/source, D23 state, artifact
   id, consume time, mutation outcome, rollback artifact, refusal/block reason,
   and health-projection inputs.

8. **Bind rollback evidence per mutation surface.** Faithful. The as-built
   trace/rollback section names the gap between `rollback_path_class` and actual
   undo material. D7 requires pre-hash, post-hash, undo material or backup path
   where applicable, rollback failure semantics, and whether rollback-proof
   failure blocks execution or records a degraded result.

9. **Add a complete mutation-surface inventory table / acceptance checklist.**
   Faithful at diagnostic strength. D6 expands the in-scope surfaces beyond the
   original dream path to include `/apply_section_edit`, Telegram approval
   cards, DreamState append and section-edit application, self-mod dialog
   terminal execution, guarded cards, direct substrate helpers, CLI/operator
   helper writes, cockpit approve endpoints, workshop diff apply, evolution
   candidate apply, ActionEngine final mutation consumers, refusal,
   role-boundary, successor-governance, memory-retention/deletion, and
   protection-setting writes. It also says the spec should turn the existing
   own-substrate bypass inventory into an acceptance checklist.

10. **Pin both Telegram slash-command and approval-card dream paths.** Faithful.
    The DreamState/Telegram as-built section now names the slash `/apply_dream`
    path, the slash section-edit path, and the Telegram approval-card calls to
    `apply_proposal(...)` and `apply_section_edit_proposal(...)` as currently
    passing no S7 authorization. D6 includes those routes in scope.

11. **Separate canon/as-built/review authority.** Faithful. The Sources Read
    section now separates first-hand canonical inputs, committed as-built
    evidence, and review-lane evidence. It states that review artifacts are not
    canonical law and that source/canon control if review artifacts differ.

12. **Require request-bound contracts for any interior-signal voice evidence.**
    Faithful. OQ1 keeps interior signals supplemental and adds that any
    private-thoughts or interior-signal route needs a request-bound
    producer/reader contract. It explicitly says current bounded readers expose
    coarse metadata or non-request-bound signals and are not sufficient primary
    voice evidence.

13. **Preserve S7 named limitations explicitly.** Faithful. Non-Goals now
    preserve Track B confidentiality, grandmother-compatible UI, absent-operator
    recovery, backup-restore confidentiality, comprehension, and display
    compromise outside the exact S7.3 approval/execution chain, while also
    retaining the original non-goals around L8, witnessed recovery, S6
    activation, raw filesystem/root bypass, ordinary biography, and
    `founder_credential_management`.

## Weakening, Contradiction, And Drift Check

No Codex finding was weakened. The high-risk proof failures named by the panel
are all blocked in v2: method presence, boolean opt-in, hand-built voice facts,
manually carried pre-consume wrappers, hash-only approval, missing trace schema,
under-specified rollback, D23 poisoning, and generic mutation inventory.

The Claude-lane additions do not contradict the Codex engineering findings. The
fresh terminal objection-turn candidate is kept as an open candidate, not a
chosen producer. The v2 voice-producer vocabulary grounding strengthens the
Codex requirement that producer labels not masquerade as producer proof. The
two-keyed L8 gate is preserved and made trace-backed.

No new implementation requirement is silently marked complete. v2 remains a
diagnostic and repeatedly says the spec must decide the exact producer,
trace-schema, rollback, D23, and surface-inventory contracts.

## The One Nit - Non-Blocking

D4 requires a live end-to-end trace for each "in-scope surface class," while D4
also says "every S7.3 in-scope path" and D6 enumerates "surfaces." The terms
`path`, `surface`, and `surface class` should be normalized in the spec. If
`surface class` remains the term, the spec should define how D6's concrete
surfaces group into classes. This is a precision cleanup for the spec, not a
diagnostic-fold blocker.

## What's Next

This Codex second-fold clears diagnostic v2 for the next ladder step: cooling-off
night. After cooling-off, the S7.3 spec should be written from diagnostic v2 and
then reviewed by both lanes. No spec was written here, and no implementation
should start before the spec ladder completes.

## Plain English

The Codex panel asked the diagnostic to stop accepting things that merely look
wired: method names, flags, hand-built voice records, hashes without the actual
change, and generic "helpers" language. The v2 fold does that. It requires real
receipts: the change Rohit saw, the Maez voice fact, D23 state, the key
approval, one-time consume, mutation, rollback record, and health projection all
tied together.

One wording cleanup remains for the spec: decide whether the unit of coverage is
a path, a surface, or a surface class. That does not change the diagnostic's
substance. The v2 diagnostic is a faithful Codex fold.
