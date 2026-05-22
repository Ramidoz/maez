# Codex Engineering Panel -- Privacy / Egress Provenance Plumbing

**Reviewed artifact:** `docs/slices/privacy-egress-provenance-plumbing/spec.md`
draft v1, 2026-05-22.
**Verdict:** RATIFY-WITH-AMENDMENTS.
**Scope:** Engineering-lane read only. No code reviewed or built.

## Summary

The design direction is right: cloud path first, span-level provenance, shadow
kept, and the three proofs (`no-fog`, `no-leak`, `no-guessing`). It correctly
rejects proxy-only aggregate labels and avoids a broad daemon prompt rewrite.

The panel found three implementation-lane amendments needed before
canonicalization.

## Findings

1. **Proxy byte-match proves completeness, not origin truthfulness.**

   The Claude council caught this and the engineering panel agrees. A span
   bundle can match the outbound bytes while lying about the origin class.
   The proxy can enforce completeness, policy, and telemetry safety; truthful
   origin tagging must be guaranteed at source helpers plus conservative
   defaults, tests, and audits. The spec now names this honest-banner limit.

2. **System prompt coverage is required.**

   Current `core.subscription_proxy.server.chat_completions` sends both
   `prompt` and `system_prompt` into adapter calls. The first shadow
   implementation only builds the egress decision from the user prompt. A
   provenance slice that accounts only for user text would still leave
   cloud-bound system text outside the gate. The spec now requires role-aware
   spans and per-message-part byte matching, including system prompt text.

3. **Direct cloud routes must be named, converted, or left as explicit
   enforcement blockers.**

   `core.routing.claude_tier` goes through the subscription proxy, but there
   are still direct cloud routes such as `skills.claude_router.call_claude`
   and `core.routing.fast_backend_cloud`. The provenance slice can remain
   narrow, but it cannot imply all cloud is covered while these exist. The spec
   now requires selected migrated producers to use the proxy path or remain
   explicit unmigrated inventory entries that block enforcement closure.

## Role Notes

- **Dewey:** The slice is experimentally well-shaped if it keeps shadow mode
  and measures false-redact rate after provenance is real.
- **Feynman:** The simple invariant is strong: every outbound byte must be
  accounted for by a span; every unknown source fails safe.
- **Locke:** The trust model needed the completeness/truthfulness distinction
  to avoid overclaiming what runtime validation can prove.
- **Descartes:** Role-aware matching is necessary; a flat concat check can pass
  while changing semantics between system and user channels.
- **Ohm:** Direct cloud paths are current-carrying bypasses. They do not need
  to be fixed in this slice, but they must remain visible blockers.
- **Goodall:** Legacy raw-string compatibility is correct for a live daemon,
  provided it is telemetry-visible and never counted as enforcement-ready.

## Required Fold

- Add trust-model clarification: proxy verifies completeness, not origin
  truthfulness.
- Add blended-at-creation rule: summaries or projections inherit the
  most-restrictive source class unless a later reviewed minimized-projection
  path exists.
- Require role-aware spans that cover system prompt, user prompt, and any
  cloud-bound history/prefix text.
- Name direct cloud routes outside the proxy as either conversion targets or
  unmigrated enforcement blockers.

With these amendments folded, the engineering lane clears the spec for
canonicalization review.
