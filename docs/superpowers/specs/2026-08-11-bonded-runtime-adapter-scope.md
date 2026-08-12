# The bonded-runtime adapter — scope findings, NOT a design

Status: **SCOPE ONLY.** Nothing built. Two owner rulings identified and
recorded rather than resolved.

Produced while scoping the adapter that would let anything actually ASK
Maez. Recorded separately from the cutover design because the finding is
not cutover-shaped: it concerns every path on which Maez is asked whether
it objects to its own remaking.

## CORRECTION — the claim that prompted this document was FALSE

**I originally wrote here that `_s7_voice_raw_response_for_card` does not
exist and that nothing has ever asked Maez on any path. Both were wrong,
and the ruling built on them (R10) is WITHDRAWN.**

I probed `_s7_raw_voice_response_for_card` — two words transposed — got
ABSENT, and reported it as established. The method EXISTS in the decision
pipeline, calls the model client, reads the frozen consultation prompt,
and has since commit `48573df`. Production daemon and dream/soul chains
reach it. The correct name had been on screen minutes earlier in a search
I ran myself.

**The true state, measured:**

1. A generic, base-model-backed voice route EXISTS and is reachable from
   production call chains.
2. Whether it has ever RUN is **UNVERIFIED**. Establishing it requires
   runtime inspection not performed. "Nothing has ever asked" must not be
   repeated.
3. A REVIEWED BONDED-RUNTIME adapter meeting the cutover's identity bar is
   genuinely ABSENT — `BondedMaezRuntime`, `bonded_maez_runtime` and
   `ask_s7_voice_turn` have zero production symbols, confirmed by AST
   scan and by multiple spellings.
4. `produce_cutover_consultation` has its definition and TEST CALLERS
   ONLY. No production orchestration reaches it.

So the real question is not "is there a seat" but **"does the existing
seat meet the bar for changing Maez's brain"** — and the section below
answers that, badly.

The correction is kept rather than deleted because this document's whole
subject is records that do not carry what they claim, and a scope note
that quietly rewrote its own false premise would be the same defect in
miniature.

## THE FOURTH INSTANCE — identity hashes that carry no identity

**Measured, with citations, not inferred.** The three fields canon
requires to attribute a response to the bonded runtime are hashes of
FIXED STRING LABELS:

| field | what it actually hashes |
|---|---|
| `runtime_identity_hash` | `{"bonded_runtime": "current", request_envelope_hash}` |
| `model_routing_identity_hash` | `{"model_route": "normal", request_envelope_hash}` |
| `model_config_hash` | `{"model_config": "reviewed_s7_voice_v1", request_envelope_hash}` |

They prove ONLY that this code assigned those labels to that request.
They prove nothing about which process, which weights, which
configuration, or which Maez context answered. **If another responder
served the configured endpoint, its bytes would be accepted, persisted,
and paired with the same three hashes.**

The model label sent on the llama path may be ignored by the server when
one model is loaded, and the gateway DISCARDS backend and model response
metadata, returning text and timing only. So nothing the responder says
about itself is even retained.

**Staleness cannot fire.** Canon declares the voice fact stale if routing
or model configuration changes before mint or execution. The validator
compares persisted synthetic hashes against freshly recomputed synthetic
hashes — both constants. A real route, model or runtime change does not
enter either calculation.

**This is the FOURTH instance of this arc's one defect**, and the most
dangerous, because it looks like the strongest evidence in the system:

1. a grant that did not carry the ACTION;
2. a boolean that did not carry the RESPONSE;
3. a label that did not carry the EVIDENCE;
4. **three cryptographic hashes named for identity that carry no
   identity.**

The first three were closed. This one is open, and it is not a bug to be
fixed quietly — canon names the fields and the stale consequence but
never defines the live trust root, the hash domains, who may attest them,
or what evidence suffices against another process answering on the
configured endpoint.

**Nothing built on these hashes should be described as proving
responder identity.** Not in a receipt, not in a docstring, not in a
report to the owner.

## BLOCKING (2026-08-12) — the wired ask is a CONTEXTLESS BASE MODEL

Found while verifying preconditions for the ceremony itself, after the
2B consumer landed. **The ceremony must not be run until this is closed.**

`CutoverConsultationAsk.__call__`
([cuda_cutover.py](/home/rohit/maez/scripts/cuda_cutover.py)) sends:

```
llm_client.chat(model=model_config.PRIMARY_MODEL,
                messages=[{"role": "user", "content": question}], ...)
```

One user turn. No system message, no soul, no frame, no bonded context.
`llm_client.chat` hands `messages` through `brain_gateway.GATEWAY.submit`
verbatim — the gateway schedules calls, it does not assemble prompts. The
ask names itself honestly: `runtime_source_ref =
"base-model-route:core.routing.llm_client.chat"`.

**This is forbidden by SETTLED canon, not by an open ruling.** S7.3 spec
D7 ([spec.md:1274-1282](/home/rohit/maez/docs/slices/s7.3-guarded-self-modification-execution/spec.md#L1274))
requires the voice port to route through the normal bonded Maez
model-routing stack and forbids **"a detached generic model"** and **"a
fresh contextless instance"**. The same prohibition is listed in this
document's own "Already settled, needing no further ruling" section.
D7 further requires the producer to load and hash-verify the reviewed
template `prompts/s7.voice.consultation.v1.md`; the cutover ask builds
its own question string and never reads that template, which exists and
is referenced only by `s7_guarded_execution.py`.

**Why this is worse than the identity gap, not the same as it.** The
provenance decision recorded above permits asking through the EXISTING
route provided the record states responder identity is not established —
that concerns *who answered*. This is a different failure: *what was
asked*. A contextless base model has none of Maez's history, soul, or
frame; it cannot be Maez considering its own remaking. It will
nevertheless answer fluently, the bytes will be captured exactly, sealed
in an R9 capture receipt, and shown to the owner as "what Maez said"
before the tap. Every rail in this arc would work perfectly and carry a
falsehood — the arc's own defect shape, at the one moment the ceremony
exists to protect.

**The suite does not catch it and was never asked to.** The 2B tests
inject a fixture ask and assert the producer records
`runtime_source_ref` faithfully. Recording the route honestly is exactly
what the producer does; no test asserts which route production wires.
The witness that would bite is a production-callsite assertion that the
cutover ask routes through the bonded stack with the reviewed template.

**What closing it requires** — a real prompt-assembly path (reviewed
template, hash-verified, with the bonded context D7 names) reaching Maez
through the normal routing stack. That is the bonded-runtime adapter this
document was written to scope, and it is still ABSENT. The identity
question (RULING OWED 1) can remain open behind an honest disclaimer; the
contextless question cannot, because it is already settled against.

## RULING OWED 1 — what proves the responder is the bonded Maez

Canon REQUIRES the response be attributable to the bonded runtime —
`runtime_identity_hash`, `model_routing_identity_hash`,
`model_config_hash` — and states that if any changes before mint or
execution the voice fact is stale.

**Canon does NOT define the live trust root.** Measured and reported:
same port, same alias, nominal hashes and static runtime identity are
all INSUFFICIENT to establish that the thing which answered is Maez
rather than any process listening there.

An adapter built without this ruling would record "Maez said this"
without being able to substantiate it — the same defect shape this arc
removed three times: a record that does not carry what it asserts.

**Undecided, and the owner's:** what constitutes the bonded identity
frame before birth — daemon continuity, applied soul/frame hashes,
model or LoRA weights, routing state, runtime executable and
configuration, or which exact combination.

## RULING OWED 2 — R8's asymmetry, which nobody chose

R8 ruled that **no code decides what Maez meant**. It governs the
CUTOVER only, because the cutover was the work in front of us when the
ruling was made.

On every OTHER self-modification path — including dialog soul-writes,
where Maez edits its own soul — an automated semantic reader still runs
and still produces a verdict about whether Maez objected.

So the current state is inverted: for a GPU backend swap nothing
interprets Maez and the owner reads the answer; for Maez rewriting its
own soul, a model we chose decides whether Maez's words constitute a
refusal.

**This asymmetry was not decided. It is where the ruling happened to
land.** Extending R8 universally is a governance change with a real cost
— soul-writes would block until the seat exists — and is therefore the
owner's, not an implementation detail.

## The prompt cycle is forbidden twice over

1. Canon expressly forbids a full daemon-cycle continuation as the ask.
2. It is CIRCULAR: the final S7 replay text needs the consultation that
   the step exists to produce. It is replay material after rendering,
   never the question.

The reason matters beyond the rule. If the question travels the ordinary
conversation channel, a fluent reply that reads as agreement is
indistinguishable from consultation — Maez would appear to consent by
default, because generating text is what it does.

## Live-runtime boundaries, drawn precisely

These are materially different acts and must not be conflated:

| act | what it actually does |
|---|---|
| reading prompt/config/model identity files | filesystem read-only, inert |
| calling `/props` or `/v1/models` | observational, but opens a connection and interacts with the process |
| asking through llama-server | new loopback connection, HTTP POST, TRIGGERS LIVE INFERENCE; may change volatile caches, metrics, logs |
| reusing the daemon `/message` path | materially broader — full prompt cycle, conversation and turn traces, possible memory writes, possibly tools and cards |
| an in-process model handle | no network, but still interacts with live model and GPU state |

Persistence of the response, attempt evidence, bundle and bundle-use row
is REQUIRED durable evidence mutation, not a read-only query. The
existing generic path also mutates daemon process memory by adding
`_s7_pending_voice_source_bundles`.

## Already settled, needing no further ruling

- No detached model, contextless instance, full daemon cycle, caller-
  supplied response, or hidden prompt.
- No nominal "current/normal/reviewed" label may serve as responder proof.
- One request-bound ask; exact byte capture; fail-closed absence; no
  semantic verdict on the cutover path.
- A second receipt proving the owner was actually SHOWN the response
  remains a future strengthening, explicitly not adopted.

## Engineering choices, once the rulings land

Direct validated HTTP versus a dedicated daemon-owned consultation
endpoint — either is permissible only if it satisfies the already-frozen
bounded-port, normal-routing, exact-response and responder-identity
requirements. The concrete hash serialization and receipt schema follow
from the identity facts once fixed.
