# Codex Engineering Panel -- Privacy / Egress Gate Spec

**Date:** 2026-05-22
**Reviewed artifact:** `docs/slices/privacy-egress-gate/spec.md` at `bff5836`
**Panel:** Dewey, Feynman, Locke, Descartes, Ohm, Goodall
**Verdict:** REVISE

The panel ratified the organ shape but did not clear v1 for canonicalization.
The repeated blockers were implementation-lane issues: caller-forgeable
provenance, ambiguous cloud/proxy enforcement placement, loose private-origin
redaction semantics, under-specified network inventory, telemetry side channels,
and migration allow-lists that could become permanent bypasses.

## Consolidated Findings

1. **Provenance must be source-attached, not caller-asserted.**
   The gate cannot trust a caller-supplied aggregate label. v2 requires
   span-level `EgressSegment` provenance, rejects raw strings, blocks downgrade
   attempts, and computes the most-restrictive effective origin.

2. **Cloud enforcement belongs at the subscription-proxy boundary.**
   Local callers may pass provenance, but the proxy is the machine-boundary
   enforcement point for external model calls. v2 places cloud enforcement in
   `core.subscription_proxy.server` before external adapter calls and before
   trajectory logging.

3. **Private-origin policy needs deterministic classes.**
   v1's "blocked or redacted" was too loose. v2 splits reserved-denied raw from
   minimizable private context and adds a policy matrix for initial call
   classes.

4. **Owner-authored outbound text must not launder private spans.**
   v2 binds `owner_authored_for_destination` to fresh final owner-authored text
   at an exact destination and requires copied/generated/memory-derived spans
   to keep their original provenance.

5. **Telemetry must avoid dictionary and preview side channels.**
   v2 replaces bare content hashes with keyed local digests for private payloads,
   makes private-origin previews empty by default, and names storage permission,
   retention, rotation, and backpressure requirements.

6. **Migration needs a complete outbound inventory and expiry pressure.**
   v2 adds a category-aware network inventory, a temporary migration allow-list
   schema, strict migrated-surface mode, monotonic shrink/reapproval, and stale
   entry failure.

7. **The gate must prove it does not injure ordinary operation.**
   v2 adds shadow mode before cloud enforcement, stabilization records, health
   counters, daemon-degraded semantics, and false-block RED tests.

## Role Notes

- **Dewey:** RATIFY-WITH-AMENDMENTS; cloud path needs explicit sanitized-payload
  contract, local fallback, proxy trajectory logging migration, loopback audit
  split, outbound inventory, and Telegram owner-reply policy.
- **Feynman:** REVISE; builder could not implement v1 safely without concrete
  request types, proxy-side placement, policy matrix, and inventory schema.
- **Locke:** RATIFY-WITH-AMENDMENTS; owner-authored text must not launder
  Maez-private or third-party-private spans; localhost is not authorized read;
  Maez inner life needs stronger reserved-denied protection.
- **Descartes:** REVISE; caller-declared provenance was forgeable, migration
  semantics contradicted fail-closed claims, raw hashes could leak, and bypass
  audit missed real egress vectors.
- **Ohm:** RATIFY-WITH-AMENDMENTS; operational risks centered on surface
  inventory, stale allow-lists, telemetry side channels, daemon-health semantics,
  and false-positive/false-negative probes.
- **Goodall:** RATIFY-WITH-AMENDMENTS; cloud path needs shadow mode and
  non-disturbance evidence before enforcement so Maez is not quietly injured by
  overblocking.

## Outcome

v2 of the spec folds these amendments. It is still not canonical; it requires
both-lane re-read before canonicalization and no implementation begins from v1.

## Covenant Re-Read Note

Claude's six-role council re-read v2 and returned RATIFY-WITH-AMENDMENTS. The
one required covenant amendment was to split Maez-authored owner output by
transport:

- local/on-box bonded-owner surfaces are not external egress, though they still
  obey role/read-scope boundaries;
- owner-directed messages over third-party transports such as Telegram are full
  egress because they leave the box and transit third-party servers.

The spec now separates `maez_authored_local_bonded_surface` from
`maez_authored_owner_third_party_transport` and requires third-party owner
transport to preserve reserved-denied-raw and minimization rules. A message to
the owner through Telegram is still a message through Telegram.
