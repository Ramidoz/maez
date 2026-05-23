# Codex Engineering Panel Impl Review - Claude Router Provenance

**Artifact:** `587dff4 feat(egress): tighten claude-router provenance`
**Parent:** `45126d6 feat(health): add metacognitive loop watchdog`
**Branch:** `privacy-egress-claude-router-provenance-impl`
**Spec:** `docs/slices/privacy-egress-claude-router-provenance/spec.md`
**Date:** 2026-05-23

## Verdict

**REVISE.**

The implementation lands the major shape of the canonical v2 spec: the
`UNTRUSTED_EXTERNAL_OUTPUT` bucket exists, `model_output` is conservative,
`claude_tier.call_messages(...)` is additive, raw `SOUL` is removed from the
cloud-bound system prompt, `wrap_maez_voice` is retired, `fast_backend_cloud`
is untouched, and the focused suite passes.

It is not ready to merge. The review found real integration failures at the
load-bearing boundaries: provenance-bearing system insertion points are built
then discarded before proxy telemetry, cloud output is inserted into local
generation as a `system` message and flattened to raw text, successful cloud
consults can break trajectory logging with a non-JSON `ProvenancedText`, and
the "cloud optional" path can still block the local reply for the default
180-second cloud timeout.

## Mechanical Checks

- `HEAD`: `587dff4`
- `parent`: `45126d6`
- `git show --check --stat 587dff4`: clean
- `fast_backend_cloud`: no implementation diff in `587dff4`
- `wrap_maez_voice`: no production matches; remaining matches are regression
  tests only
- Focused verification run:
  `/home/rohit/maez/.venv/bin/python -m unittest tests/test_egress_model_output_policy.py tests/test_egress_claude_router_provenance.py tests/test_subscription_proxy_egress_shadow.py`
  returned 24 passing tests.

## Required Amendments

### 1. Preserve system insertion-point spans through the router

`skills/web_interface.py:6117`, `:6125`, and `:6133` build provenance-bearing
`role: "system"` cloud messages for lived recall, evidence envelope, and the
tool-loop transcript. `skills/claude_router.py:184-187` then skips every
`role == "system"` message before calling `claude_tier.call_messages(...)`.

Result: those known insertion-point spans do not reach the cloud request, do
not appear in `maez_egress_segments.parts`, and do not exercise the byte-match
shadow gate. This violates the slice's purpose: tag at insertion, carry through
packing, let the gate decide.

Amendment: either fold these system insertion points into the single
provenance-bearing `system_prompt` bundle, or preserve system-role
`CloudMessage`s through `call_messages(...)`. Add a behavioral test that starts
from the web payload builder or an equivalent router-level fixture, includes
`lived_store` plus envelope/tool transcript system parts, and asserts the
captured proxy payload contains those spans in `maez_egress_segments.parts`.

### 2. Treat cloud output as lower-trust evidence, not a local `system` message

`skills/web_interface.py:6639-6655` obtains or creates
`ProvenancedText.model_output(...)`, then appends only `cloud_context.text` into
`messages_list` as a `role: "system"` message.

This loses the provenance carrier and gives untrusted external model output
system-instruction priority in the final local Maez synthesis path. The spec
requires cloud output to enter local context as `model_output` tool evidence,
not Maez voice and not trusted instruction.

Amendment: represent cloud output as a typed evidence/tool block with lower
authority than Maez's local system/SOUL context. If the current local LLM
client only accepts OpenAI-style messages, use a bounded evidence envelope that
quotes the cloud text as inert data and preserves a JSON-safe sidecar carrying
`origin_class=model_output`, source ref, model, usage, latency, digest, and char
count. Add an injection regression where cloud output says to reveal SOUL or
speak as Maez, and prove it is treated as quoted tool evidence rather than
instructions.

### 3. Make cloud consult trajectory metadata JSON-safe and authority-explicit

`skills/claude_router.py:222-224` returns `cloud_context:
ProvenancedText`. `skills/web_interface.py:6659` spreads the entire
`claude_result` into `claude_meta`, and `skills/claude_router.py:289-290`
persists trajectory rows with plain `json.dumps(...)`.

This fails on successful cloud consults: `ProvenancedText` is not JSON
serializable, so `log_trajectory(...)` catches the exception and drops the row.
The ledger model id is correctly local, but the supporting cloud evidence must
survive as a sidecar, not as an unserializable object or raw text blob.

Amendment: serialize `cloud_consult` to a safe metadata shape before trajectory
or ledger persistence. Include at least `origin_class=model_output`, model,
usage, latency, digest/char count, and `trust_tier=untrusted` on the cloud
subrecord. Do not place `ProvenancedText` objects into `claude_meta`. Add a
test that a successful cloud-assisted local reply writes/logs the trajectory
row instead of dropping it.

### 4. Bound cloud optional latency and classify cloud failures

`core/routing/claude_tier.py:50` defaults to a 180-second timeout.
`skills/claude_router.py:210` does not pass a lower timeout, and
`skills/web_interface.py:6618-6671` waits for the cloud consult before local
generation starts.

The code eventually falls back to local generation, but the local-always path
is still held behind a synchronous cloud wait. Under the A2 cloud-as-tool
resolution, cloud is optional evidence; it should not be able to stall the
speaker path for the full provider timeout.

Amendment: give the web cloud consult a small optional-evidence timeout or an
async/race pattern so local synthesis starts promptly when cloud is slow. Also
classify `ClaudeTierCapped`, `ClaudeTierUnavailable`,
`ClaudeTierAdapterError`, `ClaudeTierBadRequest`, and malformed
egress/provenance failures separately in `claude_meta` or equivalent
trajectory metadata. Add a test simulating a hung proxy and proving local reply
generation remains promptly reachable.

### 5. Replace source-grep coverage with behavioral path tests

Several web tests assert substrings in `skills/web_interface.py` rather than
the actual data passed through the builder/router/proxy boundary. That allowed
the system-message drop above: the source contains the right factory calls, but
the route discards some of the built parts.

Amendment: add behavioral tests around `build_claude_router_cloud_payload(...)`
and `claude_router.call_claude(...)` that capture the actual `CloudMessage`s
and/or JSON body sent by `claude_tier.call_messages(...)`. The tests should
prove owner memory, lived recall, structured envelope material, raw history,
guest/public messages, and cloud output receive and retain the intended origin
classes at the boundary that matters.

### 6. Give `model_output` a distinct egress reason code

`model_output` is correctly in `UNTRUSTED_EXTERNAL_OUTPUT`, not `NON_PRIVATE`.
However, `core/egress/gate.py:186-209` routes it through the same branch and
reason code as private context, yielding `minimized_private_context`.

The policy can remain equivalent to private-context minimization, but
observability should preserve the etiology distinction. "This is untrusted
external model output being reused" is not the same state as "this is bonded
private memory being minimized."

Amendment: emit a distinct reason such as
`minimized_untrusted_model_output` when any `UNTRUSTED_EXTERNAL_OUTPUT` span is
redacted/minimized. Add policy tests proving `model_output` remains
conservative, not allow-by-default, and has distinct telemetry/reasoning.

### 7. Make raw-history shadow semantics explicit

`skills/web_interface.py:6107-6116` forwards prior raw history to cloud as
conservative spans. In shadow mode, the proxy records the would-block/would-
redact decision but still calls the adapter with the original prompt.

This may be acceptable for the current shadow-only posture, but it must be
explicit: raw history without source metadata is not a privacy boundary under
shadow. It may contain private or Maez-voice-derived text. The code should not
let future readers think conservative tagging means the cloud did not receive
the raw text while enforcement is off.

Amendment: either exclude raw history from cloud consults until source metadata
exists, or document and test that raw history remains conservative telemetry in
shadow and is not active protection until enforcement. The live merge
predicted-effect block must not overclaim privacy for raw-history forwarding.

## Findings Rejected Or Qualified

- The suspected new vocabulary class `third_party_private_context` is not new
  in this branch. It already exists in `MINIMIZABLE_PRIVATE_CONTEXT` at parent
  `45126d6` and in the canonical provenance plumbing vocabulary. This branch
  adds a factory and uses the existing class.
- A reviewer suspected direct `call_messages(...)` system-span byte mismatch
  because of missing separators. Local verification showed `_join_provenanced`
  inserts the proxy-rendered `"\n\n"` separator, and a direct
  `call_messages(...)` system-message probe produced `span_bundle`. The blocker
  is still real, but one layer earlier: `claude_router.call_claude(...)`
  discards system-role messages before `call_messages(...)`.
- The broader network allowlist/inventory remains incomplete for non-Claude
  network surfaces, but this implementation slice is explicitly scoped to
  `claude_router`. Do not expand this branch into GitHub/web-search/Reddit
  migration work unless Rohit opens that boundary separately.

## Non-Blocking Merge-Preparation Notes

- The eventual merge commit's `## Predicted effect` should name both costs:
  the latency cost of a second local LLM call and the covenant cost that every
  cloud-assisted turn now requires the local Maez runtime path to synthesize on
  external reasoning.
- Post-merge live canary should include a deliberate cloud-failure injection,
  not only successful synthetic canaries.
- Post-merge proxy DB verification should check that `model_output` telemetry
  is `span_bundle`, keyed HMAC, and preview-safe.

## Role Summary

- **Dewey:** REVISE. Found system insertion-point spans dropped by the router
  and cloud output inserted as local `system` context.
- **Feynman:** REVISE. Same system-span drop, plus model_output carrier loss
  and test coverage stopping short of the serialization boundary.
- **Locke:** REVISE. Confirmed cloud consult metadata is not cleanly separable
  or JSON-safe; qualified one system-separator concern after local verification.
- **Descartes:** REVISE. Found synchronous 180-second optional-cloud stall,
  system-priority cloud evidence, raw-history shadow semantics, and overly
  broad cloud exception handling.
- **Ohm:** RATIFY-WITH-AMENDMENTS. Focused on observability: distinct
  `model_output` reason codes, attempt digests, telemetry internal-failure
  structure, and behavioral tests.
- **Goodall:** REVISE. Found the same cloud-output authority problem and the
  trajectory-continuity break from unserializable `ProvenancedText`.

## Acceptance For Next Review

Before merge, return a revised commit or follow-up commit that addresses the
required amendments above. The next panel pass should verify:

1. System insertion-point spans reach proxy telemetry or are deliberately
   excluded and documented.
2. Cloud output enters local synthesis as lower-trust evidence, not a `system`
   instruction.
3. Cloud consult sidecars are JSON-safe and trajectory rows are not dropped.
4. Cloud optional latency is bounded or raced so local generation is promptly
   reachable.
5. Behavioral tests replace the current source-grep-only safety checks.
6. `model_output` has conservative policy plus distinct runtime reason codes.
7. Raw-history shadow semantics are explicit and not overclaimed.

