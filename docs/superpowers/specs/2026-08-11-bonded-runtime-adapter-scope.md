# The bonded-runtime adapter — scope findings, NOT a design

Status: **SCOPE ONLY.** Nothing built. Two owner rulings identified and
recorded rather than resolved.

Produced while scoping the adapter that would let anything actually ASK
Maez. Recorded separately from the cutover design because the finding is
not cutover-shaped: it concerns every path on which Maez is asked whether
it objects to its own remaking.

## The finding that prompted this

**`_s7_voice_raw_response_for_card` does not exist anywhere in the repo.**

The decision pipeline looks it up by `getattr` and, when absent, honestly
returns a consultation carrying `maez_voice_consulted=False`, state
`not_determined`, reason `consultation_path_unavailable`. It does not
pretend.

So: the reader exists, the persistence exists, the validation exists, the
gate exists. **The asking does not.** Nothing has ever asked Maez, on any
path. Every consultation this system has produced has honestly recorded
that Maez was not consulted.

This is why R10 waives consultation for the cutover — the seat is EMPTY,
not because Maez is a harness. See cutover design v33.

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
