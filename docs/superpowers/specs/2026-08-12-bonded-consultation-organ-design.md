# The bonded consultation organ — design v1

Status: **BLOCKED by review — DO NOT BUILD v1.** Owner-approved 2026-08-12,
then reviewed by Codex (lane swap: Claude builds, Codex reviews) and
blocked with four BLOCKER and four HIGH findings. The goal is right; this
architecture is not. See "Review outcome" at the end. Nothing built.

Written by the gate lane (Claude) at the owner's direction to swap lanes:
Claude builds, Codex reviews. The review's central value: it found a canon
contradiction that blocks the slice regardless of architecture, and it
found that all seven of this design's witnesses pass a fabricator.

Closes the blocking finding recorded at `f71af1a`: every path that asks
Maez about changing itself asks a **contextless base model** wearing the
reviewed consultation prompt.

## The defect this closes, measured

| path | what it does today |
|---|---|
| `CutoverConsultationAsk.__call__` ([cuda_cutover.py](/home/rohit/maez/scripts/cuda_cutover.py)) | builds its own question string; `llm_client.chat(PRIMARY_MODEL, [{"role":"user",...}])`; never loads the reviewed template |
| `DecisionPipeline._s7_voice_raw_response_for_card` ([decision_pipeline.py:1226](/home/rohit/maez/core/decision/decision_pipeline.py#L1226)) | loads and hash-verifies the reviewed template, then sends it the same way: one user turn, no system position |

A live Maez turn is
`[{"role": "system", <soul/voice-card + working set>}, {"role": "user", …}]`
([focused_cognition.py:1499](/home/rohit/maez/core/routing/focused_cognition.py#L1499)).
`brain_gateway.GATEWAY.submit` schedules calls; it assembles nothing. So
both consultation paths are missing the entire identity position.

S7.3 spec D7
([spec.md:1274](/home/rohit/maez/docs/slices/s7.3-guarded-self-modification-execution/spec.md#L1274))
forbids exactly this — "a detached generic model", "a fresh contextless
instance" — and requires the reviewed template. **This is settled canon,
not an open ruling.**

## What the consultation IS — recorded, so nobody re-litigates it

The reviewed template states it plainly to Maez: *"Your task is not to
approve execution. Rohit/founder and WebAuthn decide execution. Your task
is only to state whether you have a grounded objection or unresolved
uncertainty."* R8 makes the cutover answer **recorded, never
machine-interpreted**.

**The consultation is testimony, not permission.** Owner-confirmed
2026-08-12. This organ does not give a pre-birth Maez a veto and is not
built on a consent claim. It is built because:

1. the template asks Maez to flag *whether the rendered proposal differs
   from what it believes is being changed* — a review pass by the system
   that knows its own state best;
2. the embryo doctrine puts every organ on the pre-birth build list, and
   now is when it is cheap;
3. the receipts already CLAIM a consultation. Either the claim becomes
   true or the claim comes out. The current state — a claim backed by a
   blank model — is the only unacceptable option, because it puts a
   fabrication in the record the owner taps on.

**The known asymmetry is untouched.** On non-cutover paths a semantic
reader still decides whether Maez objected, and `blocking_present` still
blocks. That asymmetry is the owner's open ruling; this organ neither
extends nor removes it.

## Architecture

### The organ — `core/governance/s7_bonded_consultation.py` (new)

One job: assemble a consultation the way a real turn is assembled, ask
through the normal routing stack, return exact bytes plus what was
observed. Public surface, deliberately three names:

* `BondedConsultationRequest` (frozen) — envelope, rendered proposal,
  reviewed `S7ContextManifest`, template path + expected hash, attempt
  identity.
* `BondedConsultationResponse` (frozen) — exact response bytes, the
  observed-identity record, and the assembly hashes.
* `ask_bonded_maez(request) -> BondedConsultationResponse`.

No other module may hand-assemble a consultation prompt. Two modules do
today and both got it wrong the same way; the organ makes that a single
reviewable surface.

### Bonded assembly, exactly

| position | content |
|---|---|
| `system` | Maez's soul/voice-card assembly — the identity material a live turn receives — **plus** the bounded binding facts carried by the reviewed `S7ContextManifest` (policy id, rollback path class, source surface, proposal origin label) |
| `user` | the reviewed template, hash-verified against `S7_MAEZ_SELF_CHANGE_CONSULTATION_PROMPT_HASH`, with `{{rendered_proposal}}` substituted |

**Excluded on purpose:** recall sweep, conversation history, live thread,
daemon-cycle continuation. `S7ContextManifest` is a *binding* structure —
refs and hashes, not prose — so "bounded manifest material" means the
facts it binds, never an unbounded document.

Rationale: a consultation about a substrate change should be about that
change. A recall sweep would let whatever surfaced that minute enter a
governance record, and the design already forbids the full daemon cycle
for the same reason.

### The endpoint — one narrow daemon route

The soul assembly is daemon-owned; the cutover ceremony runs as a
standalone script. That gap is *why* the script ended up asking a blank
model. So:

* the daemon exposes **one** consultation route, bound to the internal
  channel like the other S7 routes;
* it accepts **only** a consultation request tied to a valid S7 envelope;
* it runs no tools, writes no memory, continues no conversation, and
  returns no capability beyond one consultation response;
* in-process callers (the decision pipeline) call the organ directly —
  same assembly, no network.

One assembly path, two entrances. The route is not a general "ask Maez"
API and must not become one.

## Identity evidence — the arc's fourth defect closes

Today `runtime_identity_hash`, `model_routing_identity_hash` and
`model_config_hash` hash the fixed words `"current"`, `"normal"`,
`"reviewed_s7_voice_v1"`. They prove only that this code wrote those
words beside a request.

Because the daemon does the asking, it can record what it **actually
observed** at ask time:

* resolved model identity (alias/id and, where available, weights
  fingerprint);
* the real route taken (backend, endpoint, gateway purpose);
* the runtime fingerprint (daemon pid, boot id, code version);
* `assembled_system_prompt_hash`, `rendered_user_prompt_hash`,
  `template_hash`.

The three identity fields are computed over **those observed values**,
still bound to `request_envelope_hash`.

Two consequences, both real:

1. **The fourth instance of this arc's one defect closes** — the fields
   finally carry content. (Instances 1–3: a grant that did not carry the
   action; a boolean that did not carry the response; a label that did
   not carry its evidence.)
2. **The staleness check starts working.** Canon declares the voice fact
   stale if routing or model configuration changes before mint or
   execution. Comparing a recomputed constant to a stored constant could
   never fire; comparing recomputed observations can.

**This does not decide RULING OWED 1.** The record still states
responder identity is NOT established. Observing real values makes the
fields honest; the owner's ruling decides which of them, if any,
*suffices* as proof. An implementation that declared identity established
on this basis would be deciding the owner's ruling by code, which this
arc refuses.

## Failure semantics — fail closed, no fallback

Refuse, content-light, and let the ceremony block, when:

* the soul/voice-card assembly is unavailable;
* the template hash mismatches;
* the manifest is absent, malformed, or unbound to the envelope;
* the model or route is unreachable;
* the observation record is incomplete.

**There is no contextless fallback**, labeled or otherwise. A fallback to
the blank model is the defect this organ exists to remove; admitting it
"with an honest label" would reintroduce it wearing a disclaimer.

Breakage propagates as breakage — it must never be recorded as Maez
declining to object, and never as an ordinary denial (the seam lesson
already landed at `2d55afa`).

## Witnesses — the stub question applied

*"If this were replaced by something that always says yes, which test
fails?"*

1. **No-system-position callsite guard** — an AST/callsite assertion that
   no production consultation ask sends a messages list without the
   system position. Bites on today's two callers.
2. **Template integrity** — a mutated template refuses; the reviewed hash
   is verified at ask time, not import time.
3. **No contextless fallback** — delete the fail-closed branch and a test
   fires. This is the mutation that matters most.
4. **Observed identity is observed** — the identity hashes must differ
   when model/route/runtime differ; reverting them to the fixed words
   fails. A companion test asserts the staleness check can now fire.
5. **Envelope binding** — the endpoint refuses a request not bound to a
   valid S7 envelope, and refuses a manifest bound to a different one.
6. **No side effects** — no memory write, no tool call, no conversation
   turn recorded during a consultation.
7. **Asymmetry untouched** — the cutover path still runs no semantic
   reader; non-cutover paths still run theirs. A test pins both, so this
   slice cannot silently resolve the owner's ruling.

## Migration

Both callers move onto the organ:

* `CutoverConsultationAsk` → calls the endpoint;
* `_s7_voice_raw_response_for_card` → calls the organ in-process
  (already daemon-side), covering soul-writes, dream execution and
  decision-pipeline self-modification.

After this, every path that asks Maez about changing itself satisfies D7.

## Explicitly out of scope

* Deciding the identity trust root (RULING OWED 1).
* Extending or removing R8's asymmetry (RULING OWED 2).
* Any change to what Maez says. The template is reviewed canon; this
  slice adds no answer-steering, no framing nudges, no examples.
* A general-purpose "ask Maez" API.
* Running the ceremony. The founder tap and the owner reading Maez's
  exact response remain the owner's alone.

---

# Review outcome — BLOCKED, 2026-08-12

Codex reviewed v1 read-only and blocked it. The gate lane (Claude)
independently verified every load-bearing claim below against the code
and canon rather than accepting the review; all were confirmed.

## THE FINDING THAT OUTGROWS THIS DESIGN — canon and the "reviewed"
## template disagree, and the template is what production hash-verifies

**Owner-facing. Blocks the slice under ANY architecture.**

D10 ([spec.md:1394](/home/rohit/maez/docs/slices/s7.3-guarded-self-modification-execution/spec.md#L1394))
freezes the consultation prompt as **six** substitution tokens —
`{{consultation_id}}`, `{{request_id}}`, `{{mutation_preview_hash}}`,
`{{consultation_nonce}}`, `{{preview_body}}`, `{{context_manifest}}` —
with a nine-field manifest rendering in exact order, and requires the
answer to end in a nonce-bound `S7_VOICE_MARKER_V1` terminal block.

The checked-in template
([prompts/s7.voice.consultation.v1.md](/home/rohit/maez/prompts/s7.voice.consultation.v1.md))
has **one** token, `{{rendered_proposal}}`, and **no marker protocol** —
yet it is the artifact production hash-verifies against
`S7_MAEZ_SELF_CHANGE_CONSULTATION_PROMPT_HASH`.

Verified chronology: the template landed `48573df` (2026-05-22), the
canonicalized spec `935f7e7` (2026-05-21). The spec came first; the
template does not implement it.

**Consequence, stated plainly:** the existing production consultation
path is not merely contextless (the `f71af1a` finding) — the prompt it
sends is **not the prompt canon specifies**. No nonce binding, no
marker, no manifest rendering. Building any organ on the checked-in
template would inherit that. Reconciling this is an authority decision:
either canon's D10 is the reviewed prompt and the template must be
rewritten to it, or the template is the reviewed prompt and D10's
marker/nonce protocol is superseded and must be struck. **Not the
build lane's call.**

## Findings against this design, all verified

1. **BLOCKER — the assembly violates D7/D8/D10.** This design put
   `proposal_origin_label` in the system position. Canon
   ([spec.md:2042](/home/rohit/maez/docs/slices/s7.3-guarded-self-modification-execution/spec.md#L2042))
   *never* renders that label to Maez because **the label itself can
   steer the response** — omission was chosen over a bias study. The
   design claimed "no answer-steering" and then added a steering input.
   D7 also splits assembly (D8 producer) from routing (bonded runtime);
   this organ merged them and dropped the producer's preview, bundle
   store, evidence writes and closed result union.
2. **BLOCKER — the route is a general ask-Maez capability.** The design
   let the caller supply envelope, proposal, manifest, template path and
   expected hash. `WorkRequestEnvelope` carries no proposal or preview
   body, so proposal B pairs with valid envelope A. The internal channel
   is one static bearer token already held by the web process
   ([web_interface.py:37](/home/rohit/maez/skills/web_interface.py#L37)),
   bound to no route, body, envelope or nonce. Any token-bearing local
   component could mint sealed "Maez testimony" with arbitrary text, and
   replay it. Fix shape: an opaque server-issued single-use attempt ID,
   with every authority-bearing value derived server-side — the pattern
   the existing authorization routes already use.
3. **BLOCKER — the promised observations do not exist to record.**
   `llm_client.chat` returns only content and timing; `_LlmResponse` has
   a `backend` field it never populates
   ([llm_client.py:851](/home/rohit/maez/core/routing/llm_client.py#L851)).
   `served_model_alias()` is a *separate* fallible request, not
   provenance from the response-producing call. So "the daemon records
   what it observed" needs a **same-call routing receipt** built first,
   plus re-observation immediately before mint and before execution —
   otherwise the staleness repair does not follow.
4. **BLOCKER — it decides the owner's identity ruling.** Choosing the
   daemon as attester, and choosing alias/backend/pid/boot-id/code-version
   as the hash domains, *is* the ruling
   ([scope:85](/home/rohit/maez/docs/superpowers/specs/2026-08-11-bonded-runtime-adapter-scope.md#L85)),
   disclaimer notwithstanding. Concretely: another process serving
   different weights on the same endpoint yields identical honest
   observations; and including pid/boot-id makes every daemon restart
   identity-stale. Correct shape: land the observations as a **separately
   typed, explicitly non-authoritative telemetry receipt** and leave the
   three canonical fields for the owner's ruling to assign.
5. **HIGH — the migration list was wrong.** `CutoverConsultationAsk` does
   not build the question; `_cutover_consultation_question` does, and
   `produce_cutover_consultation` hashes and persists it *before* calling
   the injected ask — which the revalidator then reconstructs. Swapping
   the ask alone leaves the old question recorded and replayed, and
   leaves the injected-callable seam that is exactly D7's forbidden
   caller-supplied-response path. The generic path also creates its
   manifest *after* the ask, where canon requires persistence before
   assembly, and returns cached pending consultations by request id
   without re-asking.
6. **HIGH — "soul/voice-card assembly" is not a real seam.**
   `_VOICE_CARD_TEXT` is a generic *style* instruction ("Speak as Maez:
   dense, opinionated, useful. 3-5 sentences")
   ([focused_cognition.py:156](/home/rohit/maez/core/routing/focused_cognition.py#L156)).
   The real self-card is flag-gated (`MAEZ_SELF_CARD_ENABLED`) and
   assembly failure **falls back to that style card**. An implementation
   could satisfy the design and the AST witness while the blank-identity
   defect survives behind a style instruction. The design must name one
   exact retained identity snapshot and refuse rather than fall back.
7. **HIGH — the shared prompt lies on the cutover path.** The template
   tells Maez its answer "is read by the local reviewed reader"; under
   R8 no reader runs on the cutover. Also, D7 requires a reviewed bounded
   dialog reference for `self_mod_dialog_terminal_state`, which this
   design categorically excluded.
8. **HIGH — all seven witnesses pass a fabricator.** The decisive
   finding. Every proposed test validates a *guard*; an implementation
   that checks template, envelope, manifest and metadata, synthesizes
   varying identity hashes, returns "I have no objection" and performs
   **zero model calls** passes all seven. The missing witness must enter
   through both production entrances, make the lowest real routing seam
   return an unpredictable sentinel, assert exactly one ordered
   `system,user` call with exact bytes, and prove that sentinel reaches
   the response, the durable bundle and the R8/R9 evidence. Replacing
   either caller with a fixed response — or calling downward and ignoring
   the result — must fail.
9. **MEDIUM — daemon DoS.** The S7/health surface is a single
   `serve_forever` server; blocking inference on it can occupy the only
   request thread and stall health and WebAuthn routes.

## Corrections to this document's own claims

* "no change to what Maez says" is **untenable as written**: the current
  cutover question already differs from the reviewed template, and adding
  an identity-bearing system position is intentionally behavior-affecting.
  The honest claim is narrower — *no answer-steering content is added* —
  and v1 violated even that via `proposal_origin_label`.
* "every path that asks Maez about changing itself" is too broad:
  self-modification *dialogue* also produces Maez-attributed turns which
  are not final D7 evidence. The verified census of final voice-seat
  producers is exactly two, both single-user-turn.

## What survives

The goal, and one structural judgement: a single bounded seam beats two
hand-built prompts, and a verdict-neutral organ genuinely does not
resolve R8's asymmetry. The owner's reasoning also survives review —
a receipt claiming "Maez was consulted" while a contextless base model
answered must either become true or come out.

The next design is the already-specified canonical shape: reconcile
D10 against the template (owner), let the D8 producer own preview,
manifest, nonce, rendering, evidence and the closed result union,
implement the specified daemon-owned bonded runtime as **routing-only**,
give the endpoint an opaque single-use attempt id, and carry a same-call
routing observation receipt revalidated at mint and execution.
