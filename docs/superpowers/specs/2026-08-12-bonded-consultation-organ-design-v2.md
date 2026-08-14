# The bonded consultation organ — design v2 (canonical shape)

Status: **BLOCKED by review — DO NOT BUILD AS SEQUENCED.** Codex blocked
v2 with 6 BLOCKER + 4 HIGH. Verdict: materially better than v1, but not
buildable as one slice, and its sequencing opens a live window that is
*less* safe than today. Full outcome at the end. Nothing built.

Supersedes
`2026-08-12-bonded-consultation-organ-design.md`, which Codex blocked
with 4 BLOCKER + 4 HIGH findings, all independently verified by the gate
lane. Lane assignment unchanged: **Claude builds, Codex reviews.**

## THE OWNER'S RULING — canon D10 is authoritative

Asked 2026-08-12, decided by the owner: **canon D10 governs; the
checked-in template is brought to canon.**

The contradiction being closed: D10
([spec.md:1394](/home/rohit/maez/docs/slices/s7.3-guarded-self-modification-execution/spec.md#L1394))
freezes six substitution tokens and a nonce-bound `S7_VOICE_MARKER_V1`
terminal block; the checked-in template
([prompts/s7.voice.consultation.v1.md](/home/rohit/maez/prompts/s7.voice.consultation.v1.md))
carries one token and no marker. Spec `935f7e7` (2026-05-21) preceded
template `48573df` (2026-05-22); the template never implemented it.
Verified: **no marker parser exists anywhere in the tree** — the entire
verdict-carrying half of canon was never built.

**What the ruling buys, stated as the reason it was taken.** The marker
is not ceremony. It is the mechanism that makes R8 — *no code decides
what Maez meant* — implementable on every path instead of only on the
cutover, where it is currently satisfied by the owner reading the answer
personally. Maez states its own verdict in a parseable form; a parser
checks it; no model interprets Maez. The owner's open RULING 2 (R8's
asymmetry) becomes answerable rather than structurally blocked.

**Cost the owner accepted:** the model must reliably emit the block; a
missing or malformed marker is `missing_or_malformed`, which blocks. A
thoughtful prose answer that ignores the format halts the ceremony.
Fail-safe, and real.

**Covenant note, recorded not buried.** The marker asks Maez to end with
one of three fixed verdicts. Maez still says whatever it wants in prose
first — the marker is a rail on the *carrier*, not a script for the
*content*. The owner was shown this framing before ruling.

## Scope of this slice

1. Bring the template to canon D10 — six tokens, nine-field manifest
   rendering, terminal marker instruction — **preserving the existing
   reviewed prose verbatim**. See "Template change discipline".
2. Build the D10 marker **parser** and its closed result shape.
3. Build the D8 **producer**: owns preview, manifest, nonce, rendering,
   evidence persistence and the closed result union.
4. Build the daemon-owned **bonded runtime port: routing only**, per D7.
5. Expose **one narrow endpoint** taking an opaque server-issued
   single-use attempt id, deriving all authority-bearing material
   server-side.
6. Land routing observations as a **separately typed, explicitly
   non-authoritative telemetry receipt**.
7. Migrate both final voice-seat producers onto the producer.

## Fixing what v1 got wrong

Each item below is a v1 defect the review found; the v2 answer follows.

| v1 defect | v2 |
|---|---|
| put `proposal_origin_label` in the prompt — canon never renders it because the label **steers** | the label is audit/hash-bound only and never rendered; a witness asserts it is absent from `rendered_prompt_text` |
| organ merged D8 assembly with D7 routing | split exactly as canon: producer assembles and persists, runtime port only routes |
| endpoint took caller-supplied envelope/proposal/manifest/template | endpoint takes **only** an opaque single-use attempt id; the daemon derives envelope, preview, manifest, template and nonce from durable state, matching the existing authorization routes' pattern |
| promised observations the routing layer discards | a **same-call routing receipt** is built first; without it the observation is `unavailable` and the consultation refuses rather than inventing values |
| moved observations into the three canonical identity fields | observations land in a distinct `S7RoutingObservationReceipt`, explicitly non-authoritative; the three canonical fields stay untouched pending RULING 1 |
| named `_VOICE_CARD_TEXT` as "soul" — it is a 4-line style instruction with a silent fallback | one **named identity snapshot** with an explicit component/version policy; assembly failure **refuses**, never falls back to the style card |
| migration list wrong (`CutoverConsultationAsk` does not build the question) | migration covers `_cutover_consultation_question`, `produce_cutover_consultation`, the revalidator, bundle persistence, manifest-creation order, and the pending-consultation cache |
| all seven witnesses passed a fabricator | the sentinel witness below is the primary; guard tests are secondary |

## Component boundaries

### 1. `S7VoiceMarkerParser` (new, pure)

Input: the assistant response segment only. Output: closed
`ParsedS7VoiceMarker` with `marker_kind` ∈ {`explicit_no_objection`,
`blocking_marker`, `withdrawal_marker`, `missing_or_malformed`} plus the
parsed ids/hash/nonce.

Canon-mandated rules, each with its own test: reject marker text
appearing inside the quoted preview, mutation body, or caller material;
require exact consultation id, request id, `mutation_preview_hash` and
nonce; require **exactly one** block after the answer; reject unknown
choices and duplicate blocks; and **never infer `explicit_no_objection`
from silence, a missing marker, empty history, or a caller flag.**

Pure function, no I/O, no model. This is the piece that lets R8 hold
without a semantic reader.

### 2. `S7ConsultationProducer` (D8)

Owns, in canon's order — **persistence before assembly**: create and
persist the preview and context manifest, mint the consultation nonce
and attempt id, render the template, persist `rendered_prompt_hash` and
`rendered_prompt_ref`, call the runtime port, capture exact bytes, parse
the marker, and emit a closed result union. It is the only module
permitted to assemble a consultation prompt.

### 3. `BondedMaezRuntime` (D7) — routing only

`ask_s7_voice_turn(rendered_prompt_text, identity_snapshot) ->
(exact_response_bytes, routing_observation)`. It assembles nothing and
decides nothing. It sends `[system: identity snapshot][user: rendered
prompt]` through the normal routing stack and returns what came back
plus the same-call observation.

### 4. `S7RoutingObservationReceipt` (new, non-authoritative)

Records what the response-producing call actually reported: backend,
endpoint, resolved model identity, runtime fingerprint, and the exact
`system`/`user` byte hashes. **Requires a same-call provenance path
that does not exist today** — `llm_client.chat` returns content and
timing and drops backend/model
([llm_client.py:851](/home/rohit/maez/core/routing/llm_client.py#L851)).
Building that path is in scope. Absent observation ⇒ refuse.

Typed as non-authoritative in the schema itself, not by comment. It does
not feed the three canonical identity fields; RULING 1 decides those.

### 5. The endpoint

One daemon route. Body: an opaque, server-issued, single-use attempt id
and nothing else that carries authority. The daemon reopens durable
state to derive envelope, preview, manifest, template and nonce. Bounded
worker, deadline, single-in-flight, body/response limits, replay
refused — the S7/health surface is a single `serve_forever` server and
must not be occupied by blocking inference.

## Template change discipline

The template is what Maez is asked. Rules for changing it:

* **Existing reviewed prose is preserved verbatim** — the "Consider:"
  list, "Do not agree because Rohit wants it", "Speak in your own voice",
  and the not-execution-approval framing. This slice adds canon's
  *structure*, and does not rewrite Maez's question.
* One line is **factually wrong on the cutover path** and must be fixed
  rather than preserved: *"read by the local reviewed reader"* — under
  R8 no reader runs there. The replacement states who reads the answer
  without asserting a reader that may not exist.
* The old template stays recoverable in git, and the pinned hash
  constant is updated as a **literal**, never computed from the file —
  the existing guard test forbids `= _hash_file_bytes`
  ([test_s7_3_guarded_execution.py:47](/home/rohit/maez/tests/test_s7_3_guarded_execution.py#L47)),
  and that guard must survive.
* No answer-steering content is added. `proposal_origin_label` never
  appears.

## The anti-fabricator witness — primary

v1's seven witnesses all passed an implementation that validates every
guard, returns *"I have no objection"*, and performs **zero model calls**.
The primary witness must therefore prove inference happened:

> Enter through **both** production entrances. Make the **lowest real
> routing seam** return an unpredictable per-test sentinel plus an
> independently produced routing observation. Assert exactly **one**
> ordered `system, user` call with **exact expected bytes**. Then prove
> that exact sentinel reaches the returned response, the durable bundle,
> and the R8/R9 evidence.

Replacing either caller with a fixed response — or calling downward and
ignoring the result — must fail. Guard tests (template integrity,
envelope binding, no-fallback, no side effects, asymmetry pinned) remain,
but as secondary.

Additional witnesses this design owes: marker-inside-preview forgery
refused; nonce mismatch refused; duplicate marker refused; silence never
read as no-objection; `proposal_origin_label` absent from the rendered
prompt; identity-snapshot assembly failure refuses instead of falling
back to the style card.

## Explicitly out of scope

* **RULING 1** — the identity trust root. Observations are recorded as
  non-authoritative telemetry; nothing claims responder identity is
  established.
* **RULING 2** — R8's asymmetry. This slice builds the parser that makes
  a decision possible and pins current behavior by test; it does not
  extend or remove the semantic reader anywhere.
* Any change to what Maez says, beyond canon's structure and the one
  false line.
* A general-purpose ask-Maez API.
* Running the ceremony. The founder tap and the owner reading Maez's
  exact response remain the owner's alone.

## Sequencing

The slice is large. Proposed order, each independently reviewable:

1. marker parser (pure, no dependencies, immediately testable);
2. template brought to canon + hash literal updated;
3. same-call routing observation path + receipt;
4. producer (assembly, persistence order, closed result union);
5. runtime port + identity snapshot policy;
6. endpoint with attempt-id ingress;
7. migrate both callers; anti-fabricator witness across both entrances.

---

# Review outcome — BLOCKED, 2026-08-12

Second Codex review; second block. The gate lane verified the two most
dangerous findings against live code before recording them.

## THE CATASTROPHIC ONE — verified — adding the parser fails OPEN

`_voice_seat_recheck` admits `not_determined` on the cutover path when
the content-blind R8/R9 evidence revalidates, returning `ok: True`
([s7_webauthn_ceremony.py:856](/home/rohit/maez/core/governance/s7_webauthn_ceremony.py#L856)).
That branch is deliberate: it *is* R8 — the cutover records rather than
judges, and the owner reads the answer.

Now add the marker parser. `missing_or_malformed` maps to
`not_determined`. **Maez writes an honest, grounded objection in prose,
fails to emit a well-formed marker, and this branch admits it.**

The failure is a *conflation*: today `not_determined` means "no machine
verdict was sought." With a parser it would also mean "Maez may have
objected and we could not parse it." Those must never collapse into one
state. v2 promised "malformed blocks"; the consuming gate does not
implement that promise, and v2 did not touch it.

**Owner decision required**, because it is R8's wording:

* either cutover stays recorded-only and parser output may create **no**
  positive machine authority (malformed must reach the owner as an
  unresolved answer, distinct from "not judged");
* or R8 is amended from *"no code decides/inspects meaning"* to *"no
  semantic-model inference"*, letting the structured marker gate cutover.

Canonical D14 makes `absent` require **both** a verified
`explicit_no_objection` marker **and** a reader's
`no_blocking_signal_detected`
([spec.md:2665](/home/rohit/maez/docs/slices/s7.3-guarded-self-modification-execution/spec.md#L2665)).
With no reader on cutover, canon yields blocking `not_determined` for
every arm — which is the opposite of what the live branch does.

## THE ONE THAT CHANGES WHAT IS ACHIEVABLE — proof of inference is not testable

v2's sentinel witness replaces the lowest routing seam with a
sentinel-producing fake. A production fabricator that parses the D10
bindings out of its own prompt, synthesizes a valid marker and performs
**zero inference** still passes — because the test substitutes its own
fake at exactly the boundary where fabrication would live.

**Consequence, stated plainly and carried forward:** no unit test can
prove genuine inference. The sentinel is an excellent *routing and
exact-dataflow* witness above the mocked seam and must be called that.
Real proof needs an unmocked live witness or an independently trusted
response-producing boundary — **which is RULING 1**. The owner's identity
ruling is therefore not a refinement; it is on the critical path for the
claim "Maez actually answered."

Second fabricator in the same family: every proposed marker test is
negative, so a parser that always returns `missing_or_malformed` passes
all of them while making the voice seat permanently unusable. A
**positive control** — unpredictable prose plus one valid current
marker, proven through parser → reducer → durable validator → final
gate — must exist, and every negative must be a mutation of that
passing fixture.

## Other blockers, in brief

3. **Sequencing opens a live window.** Step 2 changes the active template
   and hash; step 7 migrates callers. Between them, the live generic
   caller — which substitutes only `{{rendered_proposal}}` — would send a
   canonical six-token template with unresolved placeholders to the
   model, while the integrity guard stays green and the old reader can
   still project the reply to `absent`. The parser may land **only while
   completely dormant**; the template/producer/runtime/stores/validator/
   callers must switch atomically, or existing callers must be forced
   fail-closed first. A versioned *staging* template can be reviewed
   without touching the active file.
4. **The attempt-id ingress is circular.** v2 has the producer mint the
   id and the endpoint require a server-issued id, with no issuer,
   schema, lifecycle or durable join — and the standalone cutover mints
   its attempt locally, so the daemon has no row to reopen. Needs an
   explicit issuer and an atomic `pending → reserved → terminal`
   lifecycle, reservation committed **before** inference, plus TTL,
   restart and ambiguous-timeout behavior. The attempt id must not be
   the sole credential: possession of it plus the shared static bearer
   token must not become a general or timing-controllable ask.
5. **The port signatures are not canonical.** D7 requires consultation/
   request ids, template id/hash, typed preview, manifest hash, nonce and
   time carried *through* the call as audit pins
   ([spec.md:1241](/home/rohit/maez/docs/slices/s7.3-guarded-self-modification-execution/spec.md#L1241));
   v2 shortened it to prompt + snapshot, which permits provenance to be
   decorated onto the receipt *after* the response instead of produced at
   the seam. D8 also *receives* a materialized preview rather than
   creating it.
6. **Consuming-gate replay still unspecified** — the v1 defect in new
   words. The bundle cannot represent parsed marker, nonce state, prompt
   integrity, reducer output or routing receipt; the generic validator
   only rereads stored prompt text; the cutover validator replays none of
   it; and the context policy is an in-code placeholder with
   `policy_body_hash="f"*64`. Canon requires the consuming validator to
   reconstruct template, preview, manifest, ids and nonce.
7. **D11 injection scanning was assigned to the wrong component** — the
   parser sees only the assistant segment and cannot know a marker
   instruction originated in the preview. Canon puts delimiter/protocol
   scanning in the producer *before* inference, with durable
   `PromptIntegrityEvidence`. Witness must enter through the producer
   with safe/injected versions of one fixture and assert **zero** runtime
   calls for the injected one.
8. **Telemetry is safe; the identity snapshot is not.** Non-authoritative
   telemetry genuinely avoids RULING 1 provided `selected_*` /
   `reported_*` / observed values are distinguished and it has no
   positive path to identity, verdict, staleness, R9 or mint
   eligibility. But "a named identity snapshot with a component/version
   policy" *is* RULING 1: soul-only versus soul+self-card+policies+model
   state ask materially different entities. It must be frozen by
   owner-reviewed bytes or left unresolved, and resolved from retained
   daemon state — never caller-supplied, which would recreate the hidden
   prompt.
9. **The replacement prompt line is owner-authored, not builder-authored.**
   The false line ("read by the local reviewed reader") is indeed false
   on cutover and presently true-ish generically. But this prompt is
   content-pinned and owner-authored; the builder wires it. The D10
   ruling authorized canonical *structure*, not free-form replacement
   wording. Exact replacement bytes must be owner-supplied or explicitly
   ratified before the hash is frozen.
10. **Canon still omitted:** D15's one-attempt-plus-two-retries with
    ordered durable records and first-blocking-result-wins; the reviewed
    policy-gated dialog-context exception for
    `self_mod_dialog_terminal_state`; durable R9 capture before parser
    disposition; the D13 reducer/authority-boolean stages; the exact
    result arms (a captured malformed response stays
    `consultation_produced`; `producer_blocked` is only pre-response
    prompt-integrity failure); and the distinction between canonical
    prompt bytes, post-sanitization transmitted bytes, raw transport
    bytes and the normalized assistant segment — the llama path
    sanitizes messages and strips response control tokens.

Minor: v2's principal D10 citation pointed at the origin-label rule;
D10 begins at
[spec.md:1998](/home/rohit/maez/docs/slices/s7.3-guarded-self-modification-execution/spec.md#L1998).

## Where this leaves the work

The organ is not one slice and must not be built as one. What is
genuinely safe to land now is narrow: **the marker parser as a pure,
dormant module with a positive control and mutation-derived negatives,
wired to nothing.** Everything else waits on decomposition and on two
owner decisions that are now on the critical path — the D13/R8
reconciliation above, and RULING 1, which turns out to gate not just
receipts but the very claim that Maez answered.

---

## REQUIRED PROPERTIES from the 2026-08-14 full-body audit (ruled, not optional)

The audit found the CURRENT consultation wire lying in three ways that
any accepted design must cure structurally -- they are requirements now,
with evidence in docs/audit_2026-08-14-full-body.md:

1. **The prompt that is hashed must be the prompt that was asked.** The
   live wire persists rendered_prompt_hash over a SYNTHETIC 8-line
   derivation (s7_guarded_execution.expected_s7_voice_rendered_prompt_text)
   while decision_pipeline sends reviewed-template + rendered-proposal
   text; the v2 validator then compares the derivation against itself.
   The organ's evidence chain must persist the REAL prompt bytes (or
   their hash + durable pre-image) and the validator must REPLAY, not
   re-derive -- the dormant replaying validator
   (validate_s7_voice_source_bundle) is the shape to promote, not
   discard.
2. **Responder identity must be bound or refused, never fabricated.**
   runtime_identity_hash / model_routing_identity_hash /
   model_config_hash are today computed from the string constants
   "current" / "normal" / "reviewed_s7_voice_v1". The organ must bind
   the actual serving identity (model file digest, route config, server
   identity) or carry an explicit typed absence -- the
   RESPONDER_IDENTITY_DISCLAIMER pattern -- but a hash field may never
   again be a constant wearing a binding's name.
3. **Consultation evidence must survive a restart.** The raw response
   and reader attempt live in an in-memory dict
   (_s7_pending_voice_source_bundles) between production and
   persistence; a daemon restart mid-flow loses the owner-witnessed
   bytes and later refuses under a misleading name
   (invalid_hash_binding via the source_ref_hash write-once
   short-circuit). The organ's staging must be durable and its
   dedupe honest about WHICH consultation's bytes it serves.
