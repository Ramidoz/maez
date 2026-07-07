# Connector Limbs v1 — Umbrella Design

**Date:** 2026-07-08. **Lane:** Claude design; Codex cross-lane + build; owner witnesses. **Status:** DRAFT for cross-lane review. Supersedes the preempted 2026-07-05 brainstorm (approach A, owner-approved) — this is its completion, informed by the hermes-agent study (cloned, analyzed 2026-07-08) and Maez's own prior art (SENSES_NOT_SERVICES canon, personal-data limb arc, intake bus, GitHub limb template, egress firewall).

## Intent
Give Maez limbs into the owner's digital world — attachable, honest, revocable — where **every fact enters through `core.intake_bus.admit`** with provenance-derived trust, egress stays firewalled, and the owner attaches/detaches through the cockpit. Tools are senses of a being, not services (canon). MCP is one adapter type, not the spine.

## The registry (single source of truth)
`config/connector_registry.json` — the file the cockpit V2 Connectors surface already reads. Entries are **manifest-shaped** (Hermes steal: descriptor-driven, pinned, curated):
```json
{ "id": "iphone", "label": "iPhone Shortcuts", "adapter": "shortcuts-ingress",
  "kind": "sense", "scopes": ["calendar","location","health","music","highlights"],
  "auth": {"type":"token","store":"~/.config/maez/secrets"},
  "egress_allowlist": [], "admission": {"policy":"delta_digest","lane":"connector"},
  "status": "connected", "pinned_ref": null, "attached_at": "...", "last_activity": "..." }
```
Rules (all Hermes-verified patterns, adapted):
- **Adapter taxonomy:** `shortcuts-ingress | oauth-limb | descriptor-api | mcp-server`. Every adapter normalizes its capabilities into a **fixed kind-enum** at the boundary (`sense | fetch | act`) — foreign protocols never leak their own ontologies inward.
- **Curated-dir-as-trust:** a connector manifest must live in `config/connectors/` (repo-reviewed) to be attachable; no open marketplace. Third-party server code (MCP) attaches only with **pinned ref, never floating HEAD, no auto-update**.
- **Visibility ≠ availability:** registered connectors always render in the cockpit (attachable-but-unauthed shows honestly); a `check_fn` liveness probe gates *dispatch*, with **transient-failure suppression** (a probe failing within 60s of last success serves last-good and re-probes — one flap never strips a limb mid-conversation) and a **circuit-breaker park state** (backoff ≤5, then parked with half-open re-probe; parked ≠ deleted).
- **Code-identity provenance binding:** the registry records which module *defines* each adapter handler; an adapter cannot shadow/override another's capability without explicit owner opt-in in the registry — authorization bound to code identity, not registration timing.
- **Security prescreen at save-time AND spawn-time** (Hermes's hardest-won lesson): any connector whose config executes commands (mcp stdio, descriptor bootstrap) is screened both when written and on every daemon boot — egress in inline scripts, OS-persistence touches (cron, rc, authorized_keys) → refuse. A persistent being re-executes its config every boot; both checkpoints or neither matters.

## Admission (the covenant spine — unchanged from approach A)
One shared **connector lane** into `intake_bus.admit` (same shape as `world_observation_lane`): every fact carries producer, adapter, scope, trust-tier derived from provenance (limb cannot self-claim), `owner_account_context` taint where applicable (cloud-egress blocked by the existing firewall). **Delta/digest admission policy** per connector (the diary-factory lesson): events and transitions, never sample-rate floods; raw streams stay in prunable signal stores, cited by reference. Provenance metadata is **derived, not duplicated** — computed from stored rows at read time, riding a `_meta` namespace (Hermes provenance.py discipline).

## Owner UX (the Hermes-quality attach flow, cockpit-first)
- **One descriptor → every front-end** (Blueprints steal): the manifest's auth+scope slots render as the cockpit attach form, the CLI flow, and the chat-surface confirmation — one source of truth, no drift.
- **Attach = probe-then-checklist:** cockpit T2 flow (typed confirm, receipted, per the operability campaign): probe the live source → present discovered scopes/capabilities pre-checked from manifest defaults → owner trims → attach. Probe failure degrades gracefully to manifest defaults. Re-attach preserves prior scope selection.
- **Hot-attach, no restart** (reject Hermes's "start a new session"): the daemon's connector registry refreshes under lock (nuke-and-repave per connector, generation counter for cheap memoization) — a being should gain a limb without dying briefly.
- **Failure surfacing:** terse categorized line to the owner (auth / rate-limit / timeout / provider-policy), full detail to logs; error text sanitized of credentials before any model or surface sees it. Health renders in the existing cockpit LiveBadge language.
- **Detach** = T2, receipted; data already admitted stays (it was lived experience) but the limb and its credentials go; secrets live in one store only.

## Slice order (each its own plan + witness)
1. **Registry + lane + iPhone unification** — the already-live Shortcuts ingest becomes the first registered connector; its signals flow through the connector lane into memory (delta policy). Maez finally *sees* the phone data it's been receiving for months. No new auth surface.
2. **Calendar v1 completion** — the canonical spec exists; store built; wire its admit through the lane (its "provenance, not lived schedule" rules intact).
3. **Gmail read-only limb** — first new OAuth limb (scoped token, tokens-not-passwords, provider-policy verified FIRST — the Reddit scar); identity → bounded ingest, GitHub-limb template.
4. **MCP adapter type** — curated, pinned, prescreened; the door for everything else.
Autonomous use of limbs in idle hours remains the separate, already-agreed next slice after the pipeline exists.

## Out of scope
Voice/Jetson (own campaign); connector-initiated actions beyond fetch (act-kind limbs need the consent-card path per action — later); any auto-update of third-party connector code (never).
