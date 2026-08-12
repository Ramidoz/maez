# The bonded consultation organ — design v2 (canonical shape)

Status: **DESIGN. Nothing built.** Supersedes
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
