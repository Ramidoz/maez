# The bonded consultation organ — design v1

Status: **DESIGN, owner-approved 2026-08-12. Nothing built.** Written by
the gate lane (Claude) at the owner's direction to swap lanes: Claude
builds, Codex reviews.

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
