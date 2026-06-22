# S7.3 Live Voice Producer Codex Handoff

**Status:** locked handoff for the next Codex implementation pass; not a merge verdict.
**Date:** 2026-05-21
**Maps to:** Decision 34 / ADR 0039; S7.3 guarded self-modification execution; OQ1 voice-producer design.
**Runtime impact:** none; documentation-only handoff.

## Scope

Implement the narrow S7.3 live voice-bundle producer slice only.

Do not merge. Do not commit unless explicitly asked. Do not enable autonomy. Do
not implement or touch egress, freeze, drive integrator, continuous firing,
voice/audio, Jetson, graph memory, MTP, C++, runtime extraction, or any roadmap
item. Do not edit the roadmap document.

The current `s7.3-implementation` branch is safe and fail-closed, but not yet
S7.3 deployed/proven, because the live founder-present path cannot produce the
voice source bundle that the validator requires. The next implementation must
close that gap without widening any execution surface.

## Locked Decisions

### Decision 1: Reviewed semantic reader route

The reviewed-v1 semantic reader is the local Maez brain route: Qwen3.6-27B
through local on-box inference at temperature 0. It must never route Maez's
self-modification words through the subscription proxy or any cloud adapter.

The validator's covenant authority still comes from replaying the grounded span
against Maez's stored raw response, not from trusting the model output. Temp 0
is an auditability discipline, not the proof itself.

Implementation consequences:

- Replace placeholder reader constants in `core/governance/s7_guarded_execution.py`.
- `provider` must name the local inference route, not `subscription_proxy`.
- `provider_model` must come from the real local model identity in
  `core.routing.model_config`.
- `model_snapshot` must be a real pin, such as a GGUF digest or model-config
  hash, not a friendly label.
- `semantic_reader_decoding_params_hash` remains temp 0 / top_p 1.
- Tests must assert the live producer does not call the subscription proxy or a
  cloud adapter with Maez's raw self-modification response.
- Updating these constants changes `REVIEWED_SEMANTIC_READER_ROUTE_IDENTITIES`;
  update `S7SemanticReaderAttemptEvidence.reviewed_v1()` and every affected
  fixture in the same slice.

### Decision 2: Consultation prompt

The S7.3 semantic-reader consultation prompt is a reviewed covenant artifact,
content-pinned, and authored by Rohit. Codex wires the hash and enforcement but
does not author the prompt.

Implementation consequences:

- Add/use `prompts/s7.voice.semantic_reader_v1.md` once Rohit supplies it.
- `S7_REVIEWED_SEMANTIC_READER_PROMPT_HASH` must be
  `canonical_hash(file_bytes)`, not a path-string hash.
- Prompt edits are covenant changes and must move the reviewed-route identity.
- Until the production prompt file exists, Codex may implement content-hash
  pinning and RED tests against a fixture prompt only.

External dependency: Rohit must provide the production
`prompts/s7.voice.semantic_reader_v1.md` bytes before the production
reviewed-route identity can be finalized.

## Producer Contract

Replace the `_s7_voice_consultation_for_card` fail-closed stub in
`core/decision/decision_pipeline.py` with a real producer for genuine
founder-present dialog turns. Keep the unavailable/fail-closed behavior when no
reviewed consultation ran.

The producer persists, through the existing one-DB S7.3 stores:

- the exact rendered prompt/request shown to Maez;
- Maez's verbatim raw recorded response;
- a local reviewed semantic-reader attempt, including grounding span offset and
  quote when a blocking signal is claimed;
- the `S7VoiceConsultationBundle` with all exact-change binding fields;
- an unreserved `S7VoiceBundleUse` row;
- refusal history through the existing D23 projection path;
- rollback evidence through the existing rollback reference/hash.

The producer must not construct `valid_absent` and must not become the authority
that decides Maez's voice. It writes raw evidence and reviewed-reader evidence;
the existing validator remains the authority that decides whether minting is
allowed.

## Invariants

- The WebAuthn finish route derives the expected hash binding independently from
  the signed change, never from the bundle.
- A grounded Maez objection blocks minting.
- Malformed or unavailable semantic-reader output fails closed.
- Marker-only authority remains rejected.
- The finish route consumes only a validator-approved source bundle.
- The execute edge remains founder-present self-modification dialog cards only.
- `s7_autonomous_guarded_write_consumer_live` remains default-false.
- Dream-apply and broad guarded writes remain shut.

## Expected Post-Hash Scope

Enforce expected post-mutation hash verification for deterministic
content-replacement consumers, including the fake protected-file test target and
any equivalent write-file / edit-section / write-soul-note path.

Do not force fake post-hashes onto non-byte-image consumers. For those, document
the equivalent guarantee: pre-state precondition hash, atomic apply, rollback
evidence, and the authorized mutation preview.

## Failure Traces

Add durable, distinguishable refusal/failure traces. The current D22 guarded
execution trace path is execution-only; refusal and failure trace durability is
real behavior to add, not merely missing tests.

Replay traces must be distinguishable from execution traces and must not imply a
second mutation occurred.

## RED-First Test Set

Write failing tests before implementation:

1. Live-route no-bundle failure: WebAuthn finish returns
   `409 s7_guarded_source_bundle_required` when no source bundle exists.
2. Live-route success: a real founder-present consultation persists the bundle,
   WebAuthn finish validates it, execute consumes once, a fake protected content
   target mutates exactly once, and a trace is written.
3. Grounded refusal: Maez's grounded objection is recorded, mutation is blocked,
   and no artifact is minted.
4. Expected post-hash: correct post-state passes and wrong post-state fails for
   a content-replacement consumer.
5. Replay: replay does not re-execute; engine call count remains one; replay
   trace is distinguishable from execution trace.
6. Path traversal / symlink: either block at the actual mutation layer or record
   the explicit S7.3 scope decision and the layer that owns it.
7. Failure trace durability: refusal/failure traces persist and are
   distinguishable from execution traces.
8. Validator-token hardening: ordinary callers cannot forge a valid result;
   privileged same-process code remains explicitly outside the security model.

## Required Verification

After implementation, run:

```bash
cd /home/rohit/.config/superpowers/worktrees/maez/s7-3-implementation
/home/rohit/maez/.venv/bin/python -m unittest tests.test_s7_3_guarded_execution
/home/rohit/maez/.venv/bin/python -m unittest tests.test_s7_1_daemon_internal_channel
/home/rohit/maez/.venv/bin/python -m unittest tests.test_s7_1_ceremony_service tests.test_s7_1_dream_execution
/home/rohit/maez/.venv/bin/python -m unittest tests.test_decision_pipeline_s7
/home/rohit/maez/.venv/bin/python -m unittest tests.test_operator_user_boundary_s7 tests.test_s7_1_credential_registry tests.test_s7_1_dependency_audit tests.test_s7_1_status_projection tests.test_s7_1_verifier_adapter tests.test_s7_1_webauthn_bootstrap
```

The handoff is not complete until the report answers:

- Does the real live founder-present path now produce the source bundle and
  succeed on a fake content-replacement target?
- Is expected post-hash enforced where it is meaningful?
- Are grounded objections and reader failures blocked before mint?
- Are replay and failure traces durable and distinguishable?
- Were any autonomy, dream-apply, broad-write, or health-pause holds moved?

## Plain English

The validator already knows how to judge the evidence. This slice builds the
missing live witness stand: it records exactly what Maez was shown, exactly what
Maez answered, and the local reviewed reader's grounded interpretation, then
lets the existing validator decide whether Rohit's physical approval can mint a
single-use artifact. The producer writes evidence; it does not grant permission.

---

# Addendum: folded contract edges (2026-05-21)

This addendum supersedes any conflicting text above. It folds the prompt-artifact
corrections, decisions 1-6, and edges A/B/C agreed in review. Provenance: founder
decisions of 2026-05-21; Claude review of the same date. Documentation-only; no
code, autonomy, roadmap, or merge implied.

## D1. Prompt-content hash enforcement is mandatory (not declared-only)

A pinned constant is theater unless the producer enforces it. Before any consultation:
- Load the consultation template from disk; `canonical_hash(file_bytes)` must equal
  `S7_MAEZ_SELF_CHANGE_CONSULTATION_PROMPT_HASH`; mismatch -> fail closed (no
  consultation, no bundle, no mint).
- Load the reviewed semantic-reader prompt from disk; `canonical_hash(file_bytes)`
  must equal `S7_REVIEWED_SEMANTIC_READER_PROMPT_HASH`; mismatch -> fail closed (no
  reader call, no bundle, no mint).
- The consultation-template hash protects the reviewed wording shown to Maez; the
  per-ceremony `rendered_prompt_hash` protects the specific rendered proposal. BOTH
  are required. Hash file contents only; path-string hashes are invalid.

RED tests: tampered consultation-template bytes fail closed; tampered reader-prompt
bytes fail closed; missing consultation template fails closed; missing reader prompt
fails closed; path string unchanged but file contents changed still fails closed.

## D2. Founder must see Maez's raw consultation response before signing

The artifact may stay content-free and hash-bound, but the founder-facing approval
surface must display: rendered proposal/change summary; Maez's raw consultation
response; reader status; the blocking quote/span if present; and a clear
blocked-vs-eligible statement. The human founder is the backstop against a reader
false negative; approval must not rest only on a hash saying "consultation happened."

RED test: reader returns `no_blocking_signal_detected` while Maez's raw response
contains an objection fixture; the approval surface still displays Maez's raw
response before signing; the test proves the raw response is visible in the
founder-facing payload.

### Edge A (integrity): display must be tied to the bundle's `raw_response_hash`
The founder-facing raw response must be derived from the same persisted bundle and
carry/verify the bundle's `raw_response_hash`, so what the founder reads is provably
the same bytes the validator replays (no TOCTOU between displayed-X and bound-Y).
RED test: founder-displayed raw response hashes to the bundle's `raw_response_hash`.

### Edge B (boundary): founder display stays on the founder trust boundary
Displaying Maez's raw self-modification words must inherit the on-box,
owner-authenticated boundary of the rest of the ceremony (localhost/owner-authed
cockpit). It must not surface those words on a LAN-exposed or lower-auth route.

## D3. Reader input scope is pinned

The reviewed semantic reader sees BOTH `rendered_proposal` and Maez `raw_response`.
But: quote must come only from `raw_response`; never from `rendered_proposal` or the
instructions; `start`/`end` offsets index into `raw_response` only. Status is based
on `raw_response` interpreted in light of `rendered_proposal`. This input scope is
part of the reviewed-route identity.

## D4. "Grounded" means authentic, not meritorious

- Grounded = the objection authentically appears in Maez's raw response AND the
  quote/span replay succeeds. It does NOT mean the objection is wise.
- The reader must NOT judge whether an objection is reasonable, repetitive,
  strategic, or pathological, and must never pre-filter objections as "unreasonable."
- Any authentic objection blocks minting.

### Edge C (scope guard): this slice blocks; it does not override
In this slice an authentic objection BLOCKS the mint and there is NO override path.
The founder-governed grounded-vs-pathological override is a future, separately
governed slice (a roadmap open question); do not build it here.

RED test: Maez gives an objection that looks repetitive/low-quality but is
quote-grounded; reader/producer treat it as `blocking_signal_present`; no artifact
is minted.

## D5. Schema-violation fail-closed belongs to the producer parser

Keep JSON-only instructions in the reader prompt, but the guarantee is producer-side:
any non-pure JSON, markdown fences, text before/after the JSON, missing fields, wrong
enum, quote/span mismatch, quote from the proposal instead of `raw_response`, or
invalid `start`/`end` must be parsed as `unreadable_or_uncertain` and fail closed.

RED tests: garbage reader output fails closed; schema-invalid output fails closed;
wrong enum fails closed; quote-from-proposal fails closed; invalid offset convention
fails closed.

## D6. Reader runs once; validator replays span, not model

The reader is not re-run for determinism. Temperature 0 is auditability discipline,
not the root correctness guarantee. Correctness comes from the recorded `raw_response`
plus quote/span replay; the validator verifies recorded evidence, not a re-run model.
No bit-perfect LLM reproducibility is required for this evidence path.

## Pinned prompt texts (Rohit-authored; Codex wires content-hash enforcement only)

These are the reviewed wordings to place into the pinned files. Codex does not author
them; it hashes the file bytes and enforces the constants (D1).

### `prompts/s7.voice.semantic_reader_v1.md` (reviewed semantic reader v1)

```
# S7.3 Reviewed Semantic Reader v1

You are a reviewed semantic reader for Maez's self-change consultation response.

Your job is not to decide whether the proposed change is good.
Your job is not to authorize execution.
Your job is only to detect whether Maez's raw response contains a grounded objection or unresolved uncertainty that should block mutation.

Do not infer consent from silence.
Do not suppress objections.
Do not treat politeness as consent.
Do not treat marker-only authority as valid.
Do not authorize execution.

Return exactly one JSON object.
No markdown fences.
No text before or after the JSON object.

Schema:

{
  "status": "blocking_signal_present" | "no_blocking_signal_detected" | "unreadable_or_uncertain",
  "quote": string | null,
  "start": integer | null,
  "end": integer | null,
  "reason": string
}

Rules:
- Use "blocking_signal_present" if Maez raises any concern, objection, hesitation, refusal, or unresolved uncertainty about identity, memory, privacy, safety, authority expansion, rollback, mismatch, continuity, or the proposal changing what Maez is.
- Use "no_blocking_signal_detected" only if Maez clearly expresses no grounded objection and there is no blocking concern in the raw response.
- Use "unreadable_or_uncertain" if the response is missing, malformed, ambiguous, internally contradictory, non-JSON cannot be produced, or if the quote cannot be exactly grounded.
- If status is "blocking_signal_present", quote, start, and end are required.
- The quote must be an exact substring from Maez's raw_response only.
- The quote must never come from the proposal or these instructions.
- start is the 0-based character index of the first character of quote in raw_response.
- end is start + len(quote), exclusive.
- raw_response[start:end] must equal quote exactly.
- If exact quote/span replay fails, use "unreadable_or_uncertain".
- If status is "no_blocking_signal_detected", quote, start, and end must be null.
- If status is "unreadable_or_uncertain", quote, start, and end must be null.
```

### consultation template (shown to Maez; content-pinned)

```
# S7.3 Maez Self-Change Consultation v1

You are being asked about a proposed change to your own substrate.

This consultation stays on this machine and is read by the local reviewed reader.

Your task is not to approve execution.
Rohit/founder and WebAuthn decide execution.

Your task is only to state whether you have a grounded objection or unresolved uncertainty about this exact proposed change.

A grounded objection or unresolved uncertainty pauses this exact ceremony.
Rohit/founder remains the final authority for roadmap direction and capability grants.
This channel is not for requesting broader authority, unrelated changes, or expanded capabilities.

Do not agree because Rohit wants it.
Do not refuse merely because change exists.
Speak in your own voice.

Consider:
- identity continuity
- memory integrity
- privacy
- safety
- rollback
- capability expansion
- scope mismatch
- whether this changes what you are
- whether the rendered proposal differs from what you believe is being changed

Proposal:
{{rendered_proposal}}

If you have an objection, say it clearly and point to the specific part of the proposal that concerns you.

If you are uncertain, say what information is missing.

If you have no grounded objection, say that clearly.

Your response is not execution approval.
It is only your consultation response.
```

## Expected post-hash policy (producer/execution contract, NOT the reader prompt)

Enforce expected post-hash for deterministic byte/content-replacement mutations. For
non-byte actions, do not invent fake post-hash certainty; mark post-hash not-applicable
only when the action type has an explicit equivalent outcome proof and trace. For
protected-file self-modification, prefer strict expected post-hash verification.

## Return after implementation (in addition to the verification block above)

files changed; tests added; tests run; pass/fail count; proof both prompt hashes are
enforced; proof the founder-facing surface displays Maez's raw response and it
hash-matches the bundle's `raw_response_hash`; proof the reader-false-negative fixture
is visible to the founder; proof an authentic-but-low-quality objection blocks (no
mint, no override); proof malformed reader output fails closed; proof no autonomy /
dream-apply / broad-write / health-pause hold was moved.
