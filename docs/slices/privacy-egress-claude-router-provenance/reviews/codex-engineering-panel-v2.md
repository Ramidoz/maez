# Codex Engineering Panel -- Claude Router Provenance Spec v2

**Reviewed artifact:** `docs/slices/privacy-egress-claude-router-provenance/spec.md`
**Review date:** 2026-05-22
**Base:** `c5225ac` plus uncommitted v2 spec update
**Verdict:** RATIFY-WITH-AMENDMENTS

## Summary

The v2 update cleanly encodes A2: cloud is a tool, not a vessel; the local Maez
runtime path is the speaker, with local inference as the final voice step.
The new architecture is implementable and materially better than the current
`wrap_maez_voice(cloud_text)` shape.

The panel has one required engineering fold before re-canonicalization:
`model_output` is a new provenance class, and the spec must define its exact
closed-vocabulary and policy placement. The current text correctly says it is
new and must be deliberate, but implementation needs one concrete target.

## Required Fold

### 1. Specify `model_output` vocabulary and policy placement

`model_output` is not currently in the closed egress origin vocabulary. The
runtime vocabulary lives in `core/egress/gate.py`; the canonical vocabulary is
also named in `docs/slices/privacy-egress-gate/spec.md` and
`docs/slices/privacy-egress-provenance-plumbing/spec.md`.

The v2 spec says:

- `model_output` is not `public_fact`;
- not trusted memory;
- not Maez voice;
- not automatically non-private;
- conservative unless a later reviewed policy permits a narrower flow.

That is the right covenant shape, but the implementation slice needs a precise
engineering target. Fold in one of these equivalent forms:

- Add `model_output` to a new conservative bucket such as
  `UNTRUSTED_EXTERNAL_OUTPUT`, with policy treatment equivalent to
  minimizable/private-origin material for cloud egress: not allow-by-default,
  redaction/minimization required if it ever crosses egress again.
- Or place `model_output` in the existing minimizable-conservative policy set
  while documenting that it is egress-sensitive external tool output, not
  private memory.

Do not place `model_output` under `NON_PRIVATE`, `tool_result_public`, or
`public_fact`. That would erase the whole point of A2: external model output is
not trusted or public merely because Maez requested it.

The spec should also say which canonical vocabulary source is updated:

- either this v2 spec explicitly extends the closed vocabulary for this slice,
  and implementation updates `core/egress/gate.py`,
  `core/egress/provenance.py`, and policy tests accordingly;
- or a separate small provenance-vocabulary v2 canonical update lands first.

Panel recommendation: let this v2 spec explicitly extend the closed vocabulary
and require the implementation slice to update code and tests deliberately.
That keeps the change local to the slice that needs it while making the new
class visible.

## Role Notes

- **Dewey:** RATIFY-WITH-AMENDMENTS. The empirical path is clear: v2 adds
  tests for local attribution, cloud failure, and model-output provenance. The
  only missing piece is the exact expected policy behavior for `model_output`
  when it appears in an outbound request.
- **Feynman:** RATIFY-WITH-AMENDMENTS. The phrase "not public, not trusted" is
  conceptually clear, but code needs a set membership. Without it, the first
  implementer must invent the policy at implementation time.
- **Locke:** RATIFY-WITH-AMENDMENTS. Backward compatibility is preserved: the
  old `claude_tier.call(...)` path remains, and the new cloud-as-tool path can
  be additive.
- **Descartes:** RATIFY-WITH-AMENDMENTS. No contradiction found in A2. The only
  ambiguity is whether `model_output` is a new bucket or an existing
  minimizable-conservative member.
- **Ohm:** RATIFY-WITH-AMENDMENTS. Implementation is feasible, but it will
  touch several seams: `web_interface.py`, `claude_router.py`,
  `claude_tier.py`, `core/egress/gate.py`, `core/egress/provenance.py`, and
  ledger/trajectory tests. That is still one coherent slice if RED-first.
- **Goodall:** RATIFY-WITH-AMENDMENTS. The cloud-as-tool resolution protects
  Maez's voice and biography. `model_output` must not be allowed to masquerade
  as a public/tool-public result.

## Non-Blocking Notes

- The v2 status is correctly `DRAFT v2 UPDATE`, not canonical. Content changed;
  fresh lane review is required.
- The speaking-subject wording guard is honored. The spec does not collapse
  Maez into "the local LLM."
- `fast_backend_cloud`, Telegram, enforcement, consent-aware egress, and OS
  enforcement remain correctly out of scope.

## Recommendation

Fold the `model_output` vocabulary/policy placement into the spec, then run the
Claude covenant pass on that fold. If cleared, re-canonicalize v2. Do not begin
implementation until v2 is canonical.
