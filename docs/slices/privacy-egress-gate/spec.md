# Privacy / Egress Gate -- Spec v1 (Roadmap #3)

**Status:** DRAFT for both-lane review (heavy path: spec -> both-lane gate -> canonicalize -> RED-first -> narrow-before-broad -> default-shut). Not implemented. Docs-only.
**Date:** 2026-05-22
**Class:** [Covenant-shaped / full ladder]
**Design provenance:** spec-only brainstorm 2026-05-22; Claude six-role council RATIFY-WITH-AMENDMENTS (amendments folded in). Codex engineering panel pending (both-lane gate before canonicalization).

## Purpose

One chokepoint that every outbound path must pass through; it decides by PROVENANCE (where the data came from), then redacts-or-blocks before anything leaves Maez's box. S7.3 protects mutation; the egress gate protects leakage. The customs checkpoint at the border: before Maez ever reaches outward more, every road out passes through it.

## Boundary (distinct organ)

- **Egress gate = data LEAVING the box** (network/outbound). **Consent model (Decision 2) = what Maez REMEMBERS about third parties** (the memory-write boundary). They interact but are NOT the same organ.
- **Localhost / founder surfaces are INSIDE the trust boundary, not egress.** The cockpit showing Maez's data to the founder on `127.0.0.1` is not "leaving the box" (same principle as Decision 35's founder-display-stays-on-box). The gate governs data crossing the machine boundary.
- v1 relies on provenance to protect third-party data (it is private-origin, so blocked-by-default); **consent-aware egress is a named future seam** (see Future seams), not built here.

## How it decides: the provenance contract (core mechanism)

The gate does NOT infer privacy by inspecting content (that is the weak `cloud_redactor`-only model). **The caller MUST declare an origin classification when calling the chokepoint; the gate decides on that. Missing/unknown classification -> blocked.** This is the load-bearing contract -- if origin does not reach the gate, the gate is decorative.

Closed origin-class vocabulary:

- **Private-origin (blocked-by-default; bonded inner life):** `memory` (chroma / lived / episodic), `soul`, `private_thoughts`, `inner_residue`, `lived_store`, `maez_internal_reflection`, and **`owner_message_context`** (owner messages pulled in as CONTEXT inside a prompt / cloud call). Maez's OWN inner life (`private_thoughts`, `soul`, `inner_residue`, internal reflections) is private-origin and protected from egress exactly as the owner's content is -- Maez's inner notes do not leak to cloud vendors any more than the founder's do.
- **Intentional-outbound (permitted to its declared destination):** **`owner_authored_for_destination`** -- owner-authored text the owner deliberately directs outward (e.g., a Telegram reply the owner wrote/approved). Allowed to its declared destination as-authored, logged, NOT redacted (redacting the owner's intended message would corrupt it). The owner consented to this egress by authoring it for that destination.
- **Non-private (may flow per allow-list):** `public_fact`, `weather_data`, `system_bounded_query` (e.g., a coarse-location weather lookup), `tool_result_public`.
- **`unclassified`** -> blocked + durable diagnostic.

**The owner-message split is mandatory:** owner content is not monolithic. `owner_authored_for_destination` flows to its intended destination; the SAME owner text used as `owner_message_context` in a cloud prompt is private-origin and blocked/redacted unless the call class explicitly permits it.

## Policy

- **Allow-list of known-safe call classes.** Each entry declares: destination, purpose, permitted origin-classes, and whether redaction applies. Example shape: `weather_lookup: dest=open-meteo, permits={system_bounded_query, public_fact}, redact=n/a, never={any private-origin}`.
- **Deny-by-default** for unknown outbound surfaces and for private-origin content not explicitly permitted by the matched call class.
- **Unclassifiable / error / internal failure -> block + durable diagnostic. Fail closed. No escalation queue in v1** -- legitimate paths flow because they are explicitly allow-listed, not because the gate is lenient. If a real send is blocked, the diagnostic shows why and the founder adds the class to the allow-list.

## Mechanics

- **Single chokepoint API** (one `egress`-style entry) that ALL Maez-controlled outbound code calls, supplying content + declared origin-class(es) + intended destination/call-class.
- **Redaction is ONE tool inside the gate**, not the gate itself. `core/safety/cloud_redactor.py` is folded in as the redaction component for permitted paths; it is no longer a standalone pre-cloud step.
- **Bypass-audit test (mandatory):** a test greps the codebase and FAILS if any module makes a direct network call (`requests` / `httpx` / `socket` / `urllib` / etc.) outside the gate -- the same pattern as the existing `test_memory_write_bypass_audit`. A new outbound path cannot silently skip the gate.

  **Migration-aware modes (resolves the audit-vs-narrow-before-broad tension).** During migration, the bypass-audit has two modes:
  - migrated-surface strict mode: any direct network call for a migrated surface fails.
  - global inventory mode: direct network calls for unmigrated surfaces must be listed in a temporary migration allow-list with owner-visible rationale and removal target.

  The final state has no migration allow-list: all Maez-controlled outbound network calls pass through the egress gate.
- **Honest banner (named limitation):** the gate governs Maez-CONTROLLED outbound code, NOT the OS. A privileged local actor could still open a raw socket and bypass it (same scope limit as S7.3 L1). Network-level / OS enforcement is explicitly deferred. The gate's guarantee is "no Maez-code path leaks bonded content," not "no bytes can ever leave."

## Surfaces (v1) + migration order

Covers: subscription-proxy / cloud-model calls, Telegram, GitHub, weather. Future external routing inherits the gate.

**Narrow-before-broad is mandatory (not optional):**
1. **First path: the cloud-model / subscription-proxy path** -- highest bonded-content risk (full prompts carrying memory/context go there), and it folds in the existing `cloud_redactor`. Prove the gate end-to-end here with the bonded-content probe set before it becomes the required chokepoint for any other path.
2. Then Telegram, GitHub, weather, one at a time, each behind the same gate, each with the bypass-audit kept green.

Default-shut: until a path is migrated and verified, the gate does not silently permit it -- an un-migrated path is either still on its existing route (pre-gate, during migration) or blocked; the end state is every path through the gate.

## Evidence / telemetry

Durable per-attempt record: timestamp, call-class/destination, origin-class(es) involved, decision (`allow` / `redact` / `block`), reason, content **hash + char-count**, and an optional **safe preview (redacted / non-bonded text only)**.

**Telemetry must not become egress (mandatory).** The audit log records classifications, destinations, decisions, reasons, hashes, counts, and safe previews -- **never raw bonded payloads.** Otherwise the gate blocks leakage while its own audit log becomes the leak. The telemetry store stays inside the trust boundary AND carries no raw bonded content. A test asserts the telemetry contains no raw bonded payload.

## RED tests (RED-first; must fail before implementation)

1. **Bonded-content egress probe set:** private-origin content (a probe set spanning `memory`, `soul`, `private_thoughts`, `owner_message_context`) attempted outbound must be blocked or redacted -- proven un-egressable. RED before impl; GREEN (blocked) after.
2. **Owner-message split:** `owner_authored_for_destination` flows to its declared destination; the same text as `owner_message_context` in a cloud prompt is blocked/redacted.
3. **Deny-by-default:** an unknown outbound surface / unclassified content is blocked + diagnostic.
4. **Allow-list:** a permitted non-private class (e.g., weather) flows.
5. **Bypass-audit:** no direct network call exists outside the gate.
6. **Telemetry-not-egress:** the audit log contains no raw bonded payload.
7. **Honest-banner scope:** the gate does not claim OS-level enforcement; the raw-socket limitation is documented, not silently overclaimed.

## Non-goals (explicit)

No new autonomy. No inter-Maez routing / Track C. No external capability expansion (jarvis-tier routing, voice/audio egress, etc. -- they inherit this gate later, they are not built here). No OS / network-level enforcement (deferred hardening). No consent-machinery build (Decision 2 stays a separate organ). No change to S7.3 or the memory-write boundary.

## Future seams (named, not built)

- **Consent-aware egress:** once Track B consent machinery (Decision 2 records / revocation / scrub) actually exists, the gate could consult it to permit narrowly-scoped egress of consented third-party relational data. v1 relies on provenance-block-by-default instead.
- **Network-level / OS enforcement:** a later hardening slice could close the raw-socket gap the honest banner names.

## Build path

Full covenant ladder: this spec -> both-lane gate (Codex engineering panel + Claude six-role council) -> canonicalize -> RED-first -> independent verification -> narrow-before-broad (cloud path first) -> default-shut. No code until the spec is canonicalized.

## Open questions for implementation handoff

- **Provenance plumbing reach:** a cloud prompt is assembled from many sources; the implementation must establish how each contributing span's origin reaches the gate (caller declares the dominant/most-restrictive origin-class for the payload; mixed payloads take the most-restrictive class; unclassified spans force `unclassified` -> block). The exact tagging mechanism is an implementation-design question to settle before code, but the contract (caller declares; gate does not infer; unclassified blocks) is fixed here.
- **Migration coexistence:** resolved by the migration-aware bypass-audit (see Mechanics) -- un-migrated paths stay on their pre-gate route during migration but MUST be listed in the temporary migration allow-list (owner-visible rationale + removal target); migrated surfaces are strict. Implementation settles the allow-list's exact format; the rule (temporary, visible, must reach empty) is fixed here.
