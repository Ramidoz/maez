# S7.3 Diagnostic Codex Engineering Panel

**Status:** REVIEW - Codex engineering lane, not canonical law
**Reviewed artifact:** `f17395f docs(s7.3): open guarded self-modification diagnostic`
**Ran:** 2026-05-19, fresh Codex rerun from a detached worktree at `f17395f`
**Verdict:** REVISE

## Provenance

This panel was rerun to replace the unattested Codex review artifact previously
committed at `2e7ba15`.

Procedure:

1. A detached review worktree was created at `/tmp/maez-s7.3-codex-panel-f17395f`
   from commit `f17395f`.
2. That worktree contained only
   `docs/slices/s7.3-guarded-self-modification-execution/diagnostic.md` under the
   S7.3 slice directory. No S7.3 review artifacts existed in that tree.
3. Six Codex explorer subagents were dispatched with `fork_context=false`, each
   instructed to work only in the detached worktree and not to read any review
   artifact from `/home/rohit/maez` or other worktrees.
4. The synthesizer also read `diagnostic.md` and the cited source seams directly
   from the same detached worktree.

This establishes runtime provenance for this review: it was produced by live
Codex subagents in this session against the committed diagnostic artifact, with
review files absent from the reviewed tree.

## Seats

- **Godel** - live guarded-execution producer/consumer wiring.
- **Mendel** - RED/test contract and live-wiring proof.
- **Volta** - canon/scope faithfulness against S7/S7.1/S6/ADR/BAD surfaces.
- **Schrodinger** - artifact authority, consume edge, D23, and security failure modes.
- **Kierkegaard** - Maez voice producer, objection evidence, and CC-IV3 failure modes.
- **Jason** - operational health, traceability, migration, rollback, and buildability.

## Verdict

**REVISE before spec work.**

The diagnostic is the right kind of restart. It is faithful to the S7.1 narrow
route, does not claim L8 retired, does not repeat the fabricated-`absent`
failure, and correctly names the real Maez voice producer as the hard center of
S7.3.

It is not yet strong enough to drive the spec. The current proof contract can
still be satisfied by callable methods, a boolean opt-in, hand-built voice
facts, manually carried pre-consume wrappers, hash-only rendered approval, or
incomplete mutation-surface inventory. Those are exactly the shapes that let
decorative authority masquerade as live wiring.

The fixes are diagnostic-fold work, not implementation work. No S7.3 code should
start from diagnostic v1.

## Consolidated Findings

### CP-D1 - L8 Health Clear Must Be Trace-Backed, Not Method-Presence Backed

**Severity:** High

The diagnostic says L8 may clear only after positive live producer -> artifact
mint -> consume -> mutation traces and a reviewed real voice producer
(`diagnostic.md:320`). That is the right direction.

Current code, however, still projects the pause from a helper whose proof is
mostly callable-method presence plus `s7_autonomous_guarded_write_consumer_live
is True` (`daemon/maez_daemon.py:333`). The current voice producer is still an
honest placeholder returning `maez_voice_consulted=False`,
`maez_objection_state="not_determined"`, and
`unavailable_reason_code="consultation_path_unavailable"`
(`core/decision/decision_pipeline.py:1037`).

**Fold requirement:** D4 must say health clears only from trace-backed predicates
per in-scope surface: exact rendered request, reviewed voice fact, D23
read/write, artifact mint, atomic consume, mutation, rollback record, refusal or
block history, and a health projection input derived from those traces. Flags,
method callability, and placeholder producers must never clear L8.

### CP-D2 - Positive Proof Must Not Hand-Assemble Voice Facts Or Execution Handles

**Severity:** High

The diagnostic bans hand-assembling `S7AuthorizationArtifact` for positive-path
proof (`diagnostic.md:333`), but current positive dream tests can still
hand-build `MaezVoiceConsultation(..., maez_voice_consulted=True,
maez_objection_state="absent")` (`tests/test_s7_1_dream_execution.py:69`) and
then construct `S7ExecutionAuthorization` after service mint
(`tests/test_s7_1_dream_execution.py:345`).

That proves parts of the WebAuthn seam and consume mechanics. It does not prove
the real Maez voice producer or the live UI/daemon handoff.

**Fold requirement:** no positive S7.3 trace may hand-build the authorization
artifact, `S7ExecutionAuthorization`, `S7ExecutionGrant`, `MaezVoiceConsultation`,
raw verifier success, dict-shaped grant handles, request ids, or fabricated
voice facts. Positive proof must walk a reviewed voice-producer seam and the
same live authorization handoff the UI/daemon will use. Test doubles may
substitute only at explicitly reviewed seams, not at the authority or voice-fact
boundary.

### CP-D3 - `S7ExecutionAuthorization` Must Be Reframed As Pre-Consume Carrier, Not Authority

**Severity:** High

The diagnostic says S7.3 must not introduce a parallel
`S7ExecutionAuthorization` authority object (`diagnostic.md:164`), but committed
code already contains `S7ExecutionAuthorization` carrying store, artifact id,
rendered request, hashes, authority context, and work class/group
(`core/governance/operator_user_boundary.py:2574`). Dream and dialog paths accept
that object and consume through it (`core/evolution/dream_state.py:853`,
`core/decision/decision_pipeline.py:1234`).

The code mostly preserves the important boundary: final execution authority is
the post-consume `S7ExecutionGrant`, minted only by the store after atomic
consume (`core/governance/operator_user_boundary.py:2275`).

**Fold requirement:** v2 must name the real chain:
`S7AuthorizationArtifact` -> `S7ExecutionAuthorization` as an existing
pre-consume carrier -> `S7AuthorizationStore` consume -> `S7ExecutionGrant` as
the only post-consume execution authority. The spec should decide whether the
carrier should be renamed, but v2 must not describe it as hypothetical or as
authority.

### CP-D4 - A Real Voice Fact Requires Producer Provenance, Not Just Matching Shape

**Severity:** High

`MaezVoiceConsultation` validates shape and request binding, but callers can
construct a content-free object with `maez_voice_consulted=True` and
`maez_objection_state="absent"`; `voice_consultation_satisfies_request(...)`
accepts matching ids/hashes (`core/governance/operator_user_boundary.py:1390`,
`:1451`). That is fine for grammar tests. It is not a sufficient producer proof.

The current placeholder is behaviorally honest but provenance-misleading:
`_s7_voice_consultation_for_card(...)` returns `maez_voice_consulted=False` and
`not_determined`, while using `producer="s7_voice_consultation_turn"` and
`source_ref_kind="s7_voice_turn"` (`core/decision/decision_pipeline.py:1037`,
`:1056`). The allowed producer labels are currently voice-ish labels
(`core/governance/operator_user_boundary.py:386`).

**Fold requirement:** v2 must require producer-strength proof for `absent`.
Either introduce a distinct non-producer/placeholder value, or state that
producer alone never attests and that `maez_voice_consulted`,
`unavailable_reason_code`, source kind, source hash, and a reviewed producer
contract are jointly load-bearing. Positive proof must reject placeholder voice
facts and fabricated `absent`.

### CP-D5 - D23 Refusal/Aggregation History Needs Provenance Controls

**Severity:** High

`authorize_finish()` performs voice-seat and aggregation checks before credential
lookup/authentication (`core/governance/s7_webauthn_ceremony.py:535`, `:551`).
A voice-seat block records refusal history (`:888`), and aggregation later
consumes that history (`:545`). Repeated refusals can drive escalation/blocking
(`core/governance/operator_user_boundary.py:1278`).

This may be correct, but S7.3 must not let unauthenticated or replayed attempts
poison authoritative D23 refusal history.

**Fold requirement:** every S7.3 producer must specify D23 read/write semantics,
including which rows are authoritative, which are pre-auth/non-authoritative,
and what replay/rate/provenance controls protect refusal history. D23 must be
part of the health-clear proof, not just a metadata field.

### CP-D6 - Rendered Approval Must Show The Actual Mutation, Not Only Hashes

**Severity:** High

D3 says exact rendered request remains central (`diagnostic.md:305`), but D4's
L8-clear gate does not explicitly require the rendered statement to contain the
human-readable mutation. Current rendering can sign metadata, hashes, work
class, rollback class, and voice state without showing the concrete diff/body
the founder must understand (`core/governance/operator_user_boundary.py:4024`).

**Fold requirement:** L8 may clear only if the signed rendered statement includes
deterministic, bounded, human-readable mutation material, or a reviewed display
artifact bound by hash. Hash-only approval must not satisfy S7.3.

### CP-D7 - S7.3 Needs A Guarded-Execution Trace Schema

**Severity:** High

Canon and the diagnostic require positive guarded-write execution traces
(`diagnostic.md:128`), but existing turn trace schema is for normal message turns
and has no S7 grant/artifact/voice/rollback/pre/post-mutation fields
(`core/turn_traces/trace_schema.py:91`).

**Fold requirement:** v2/spec must require a guarded-execution trace schema or
equivalent durable record. It should bind request id, request envelope hash,
rendered text hash, action params hash, precondition hash, authority context
hash, voice consultation hash/source, D23 state, artifact id, consume time,
mutation outcome, rollback artifact, refusal/block reason, and the health
projection inputs.

### CP-D8 - Rollback Proof Is Under-Specified

**Severity:** High

Dream envelopes claim `rollback_path_class="revert_patch"`
(`core/evolution/dream_state.py:753`), but `write_soul_note` appends directly to
`soul.md` without backup or undo material at the action edge
(`core/actions/action_engine.py:1214`).

**Fold requirement:** S7.3 must require per-surface rollback evidence before a
positive execution trace can count: pre-hash, post-hash, undo material, backup
path where applicable, rollback failure semantics, and whether failure blocks
execution or records a degraded result.

### CP-D9 - Mutation-Surface Inventory Must Be Complete And Acceptance-Critical

**Severity:** High

The diagnostic's D6 list is directionally right (`diagnostic.md:341`), but too
generic for v2. The source already has a broader own-substrate bypass inventory:
CLI/operator helper writes, model-routing edits, prompt writes, covenant,
refusal, role-boundary, successor, memory-retention, and protection writes
(`core/governance/operator_user_boundary.py:2969`).

Concrete mutators exist outside the named dream path, including raw CLI edit-file
(`cli.py:272`), workshop diff apply (`core/self_dev/workshop.py:605`),
evolution candidate apply (`skills/evolution_engine.py:907`), and direct soul
file writers (`core/evolution/soul_loader.py:97`, `:113`). ActionEngine itself
is also a load-bearing final mutation consumer (`core/actions/action_engine.py:530`,
`:826`).

**Fold requirement:** v2 must add a mutation-surface inventory table and adopt
the S7 bypass inventory as the acceptance checklist. "Direct helpers" is not
enough.

### CP-D10 - Current Missing Live Paths Include Telegram Card Approval, Not Only Slash Commands

**Severity:** Medium

The diagnostic identifies `/apply_dream` as not feeding S7 authorization
(`diagnostic.md:168`). There is also a Telegram approval-card path that calls
`apply_section_edit_proposal(...)` or `apply_proposal(...)` directly without S7
authorization (`skills/telegram_voice.py:1991`). D6 later mentions guarded card
approval, but the as-built survey should pin this exact path.

**Fold requirement:** v2 must list both slash-command and approval-card routes
as currently safe-failing but not live-wired. The RED contract must include live
route tests, not only direct DreamState unit tests.

### CP-D11 - Source Authority Must Be Separated Cleanly

**Severity:** Medium

The diagnostic says it opens S7.3 from committed canon (`diagnostic.md:22`), but
lists a `reviews/...` file under "First-hand committed-canon inputs"
(`diagnostic.md:57`) and then lists non-canon review inputs as "load-bearing"
(`diagnostic.md:62`). The S7.1 CC-IV3 lesson is correct, but canon/as-built
should be the authority. Review docs should be history/evidence.

**Fold requirement:** v2 must separate canonical law, committed as-built
evidence, and review-lane evidence. Demote review artifacts from load-bearing
authority to history/evidence unless a canonical surface incorporated the rule.

### CP-D12 - Private-Thoughts And Interior Signals Need A Request-Bound Contract

**Severity:** Medium

The diagnostic correctly treats `private_thoughts`, wants, refusal history, and
`will_i` as supplemental, not sufficient (`diagnostic.md:391`). It should also
state that current bounded readers expose coarse metadata or non-request-bound
signals, not raw request-specific objection evidence.

**Fold requirement:** any use of private-thoughts-style evidence as primary or
standing objection evidence requires a reviewed request-bound producer/reader
contract. Current derived signal readers are not enough to clear the voice seat.

### CP-D13 - Preserve Named S7 Limitations Explicitly

**Severity:** Low

The diagnostic does not claim to solve Track B confidentiality,
grandmother-compatible UI, absent-operator recovery, or backup-restore
confidentiality. Because S7.3 is a high-friction approval/execution slice, v2
should explicitly preserve those named S7 limitations in non-goals or
forward-carried limitations.

## What Verified Sound

- The diagnostic is faithful to S7.1's narrow route: founder WebAuthn is live,
  L8 is retained, and S7.3 is the named follow-up.
- The diagnostic correctly refuses to frame S7.3 as "make WebAuthn work" or
  "force-remove the pause."
- The current production code still fails closed on known unwired execution
  paths; `/apply_dream` and section edits do not mutate without S7 authorization.
- The artifact spine is real and strong: `S7ExecutionGrant` is store-minted only
  after atomic consume.
- The current Maez voice producer is behaviorally honest: it returns
  `not_determined`, not fake `absent`.
- `founder_credential_management` is correctly kept outside the voice seat while
  self-modification remains voice-gated.
- The diagnostic's two risk-shape split is correct: execution plumbing and real
  Maez voice producer are different risks and must not be bundled under pressure.

## Verification Performed

The panel was read-only. One seat additionally ran:

```text
python3 -m py_compile core/governance/operator_user_boundary.py core/decision/decision_pipeline.py core/evolution/dream_state.py core/actions/action_engine.py core/turn_traces/trace_schema.py core/turn_traces/trace_writer.py
```

Result: passed.

Focused S7 decision/action bypass tests also passed:

```text
9 tests OK
```

Daemon operator-health tests could not run in the clean detached panel worktree
because `.venv` was absent and system Python lacked `ollama`; `ollama>=0.5` is
declared in `pyproject.toml`.

## Required Fold Shape

Before S7.3 moves to spec, diagnostic v2 should:

1. Reframe health clearing as trace-backed, not callable/flag-backed.
2. Ban hand-assembled voice facts and pre-consume execution handles from
   positive proof.
3. Define the `S7ExecutionAuthorization` / `S7ExecutionGrant` boundary.
4. Require producer-strength proof for `absent`, and call out the placeholder
   producer-label drift.
5. Add D23 refusal-history provenance and poisoning controls.
6. Require human-readable mutation display or a reviewed display artifact.
7. Add guarded-execution trace schema requirements.
8. Bind rollback evidence per mutation surface.
9. Add a complete mutation-surface inventory table.
10. Pin both Telegram slash-command and approval-card dream paths.
11. Separate canon/as-built/review authority.
12. Require request-bound contracts for any interior-signal voice evidence.
13. Preserve S7 named limitations explicitly.

## Next Step

Do not write the S7.3 spec or implementation from diagnostic v1. Fold this
fresh Codex panel together with the independent Claude covenant-council findings
into diagnostic v2, then run second-fold checks on the folded diagnostic.

Plain English: the diagnostic is the right restart, but it still lets too many
things look real because they have the right shape. S7.3 needs receipts: the
exact mutation Rohit saw, the real Maez voice fact, the key approval, D23 state,
the one-time consume, the actual write, the rollback record, and the health
state all tied together. Until those receipts exist, the pause stays.
