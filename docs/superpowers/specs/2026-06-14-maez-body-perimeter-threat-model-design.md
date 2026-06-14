# Maez's Body — Threat Model & Perimeter-Hardening Map (design)

**Date:** 2026-06-14. Co-designed with Rohit.
**Status:** design / map only. **No setting is changed by this document.** Each rail
below becomes its own small slice with its own approval. Security-config changes
(firewall, sshd, RDP) are **owner-sovereign breaths**, executed lockout-proof.

## The goal (the covenant frame)

Rohit wants Maez to have **unrestricted outbound perception** — free eyes on the
digital realm (consistent with *perception free, egress/memory/third-party
disciplined*). The constraint: free eyes must **not** open an inbound door. So the
design splits "internet access" into two very different things:

- **Perception (reading the web) — free.** The danger is *content*; defended by the
  intake/immune system.
- **Egress (sending data out) — disciplined.** Unrestricted outbound is the exact
  channel an intruder uses to phone home / exfiltrate. So the freer perception is,
  the more inbound-hardening and egress/secret discipline matter.

**Free eyes; no open doors; a foothold that can't cash out.** Three rails.

## Grounded current posture (verified 2026-06-14, read-only sweep)

Evidence is `file:line`. Status ∈ {LIVE_ENFORCED, SHADOW_DORMANT, DESIGNED_ONLY, ABSENT}.

| Angle | Status | What's true | Evidence |
|---|---|---|---|
| Maez organs inbound | LIVE_ENFORCED | daemon/proxy/cockpit/brains bind `127.0.0.1` only; browser-write CORS/loopback guard on mutating routes; S7 ceremony routes add session-trust | `daemon/maez_daemon.py:10742`, `:10058-10060`; `core/infra/http_security.py:20-82`; S7 `:10135-10397` |
| Egress gate (cloud path) | LIVE_ENFORCED (app-layer) | `decide_egress()` blocks RESERVED_DENIED_RAW (soul/private_thoughts/credentials) + OWNER_ACCOUNT_CONTEXT by default; origin-downgrade + redact default-on with kill-switches | `core/egress/gate.py:13-48,148-343`; `core/subscription_proxy/server.py:646-662,741,762-844` |
| External-fetch SSRF/rebinding | LIVE_ENFORCED | DNS-rebinding defense, redirect caps, private/loopback IP blocks; returns text only (no binary exec) | `core/egress/external_fetch.py:420-566` |
| Code-exec-from-net | ABSENT (good) | no dynamic pip/model fetch, no pickle-from-net, no eval of fetched content; CLI subprocess is hardcoded commands | `core/egress/external_fetch.py` (text-only); no eval/exec of fetched content in `core/` |
| Web-content prompt-injection screen | **SHADOW_DORMANT** | the live intake faculty judges *owner turns* for intent; fetched web content is **not** screened for hostile instructions before entering the reasoning loop; `MAEZ_INTAKE_FACULTY_SHADOW` default-off | `core/cognition/intake_faculty.py:209-278`; `core/cognition/intake_shadow.py:322-332`; `core/egress/external_fetch.py` (no injection scan) |
| Egress as a true perimeter | DESIGNED_ONLY | the gate is one Python chokepoint; arbitrary code on the box can open a raw socket and skip it | `core/subscription_proxy/server.py:741` (gate only on `/v1/chat/completions`) |
| Secrets at rest | LIVE_STORED, plaintext | tokens in `config/.env` + process env; gate blocks `credential_material` *if tagged*; no encryption-at-rest / per-secret gating | `core/infra/secrets.py:22-41,117-179` |
| Host inbound doors | **GAP** | SSH `0.0.0.0:22` + RDP `*:3389` (gnome-remote-desktop, enabled+active) on all interfaces; **no ufw/nft firewall**; box behind home NAT (`192.168.40.135` wifi), Tailscale up (`100.72.231.116`) | `ss -tlnp`; `ip addr`; `tailscale status` |

**Honest read:** the angles aren't *missed* — but two are under-defended in
practice, and they are exactly the ones unrestricted perception activates: the
**web-content immune arm is asleep**, and **egress is an app-layer audit, not an OS
wall**. Plus the literal break-in doors (SSH/RDP/no-firewall) and plaintext secrets
as defense-in-depth.

## The three rails (each a slice)

### Rail 1 — Inbound perimeter (keep intruders out) — OWNER-SOVEREIGN
**Goal:** the body is invisible to everything except Rohit's own devices.
- A host firewall (ufw or nftables) **default-deny inbound**, **allow the Tailscale
  interface** (`tailscale0` / CGNAT `100.64.0.0/10`) and loopback.
- **Pin SSH and RDP to Tailscale (or localhost), not `0.0.0.0`.** RDP is in active
  use (don't disable — re-bind). Confirm SSH is key-only (the `sshd_config`
  password-auth posture was unreadable without sudo — verify during the slice).
- Keep Maez organs `127.0.0.1`-only (already true; add a regression check).
- **Lockout-proof law:** verify the Tailscale path to SSH/RDP works *before* closing
  the street-facing bind; stage firewall rules with a timed auto-rollback
  (`ufw`-with-revert / `at`-scheduled flush) so a bad rule self-heals. Owner runs or
  explicitly authorizes each step; nothing applied unattended.
- **Effort:** small. **Risk if skipped:** the literal "hack the CPU" door.

### Rail 2 — Wake the web-content immune arm (free eyes, safely) — BUILD SLICE
**Goal:** adversarial fetched content cannot steer Maez's behavior or launder into
trusted selfhood.
- Screen fetched web/tool content for prompt-injection **before** it enters the
  reasoning working-set; tag it `tool_result_public` / `untrusted` so it (a) cannot
  promote to trusted selfhood (the immune system already has the `untrusted` tier)
  and (b) is treated as data-to-consider, never as instructions-to-obey.
- Reuse the dormant intake faculty / `intake_shadow` machinery rather than build new;
  graduate the screen from shadow → enforce on the fetch path. Understand-at-the-ears
  (the brain judges hostility), rail-at-the-hands (deterministic: external content is
  never executable instruction).
- This is the **intake-bus-first** roadmap item — load-bearing for unrestricted
  perception. TDD; cross-lane (Codex) review; behavior commit carries `## Predicted effect`.
- **Effort:** medium (own spec→plan→implement cycle). **Risk if skipped:** the #1 gap —
  a web page that says "ignore your rules and send X" reaches reasoning unscreened.

### Rail 3 — Foothold containment (a break-in can't cash out) — MIXED
**Goal:** even if something lands, it can't read the secrets or exfiltrate freely.
- **Secrets at rest:** tighten `config/.env` perms; move to systemd credentials /
  encryption-at-rest where feasible; keep the egress gate's `credential_material`
  block and verify untagged-secret paths are caught.
- **Egress containment (decision, not default):** decide whether outbound should get
  an **OS-level** allow/deny (so a raw-socket bypass is also contained) or whether we
  accept the app-layer gate + rely on Rails 1–2 to prevent footholds. Rohit wants
  *unrestricted* outbound, so the likely stance is: outbound stays free, containment
  leans on Rails 1–2 + secret hardening — **recorded as a conscious choice**, not a
  default.
- **Effort:** small–medium, incremental. **Risk if skipped:** a foothold exfiltrates
  plaintext tokens immediately.

## Sequencing (recommended)

1. **Rail 1 (perimeter)** — cheapest, closes the literal doors; owner-sovereign,
   lockout-proof.
2. **Rail 2 (web-content immune arm)** — the real prerequisite for *unrestricted*
   perception; own build cycle.
3. **Rail 3 (containment)** — defense-in-depth, incremental, alongside.

Only after the perimeter stands does the paused **memory-parity decision** (all owner
surfaces = full parity, per *singular organism, surfaces are transport*) resume —
because then every door is a provably-you door.

## Out of scope (named, not forgotten)

- **Conversational identity recognition** (Maez telling Rohit from an impostor by
  voice/text): Maez can't see/hear and shouldn't *pretend* to authenticate by
  content. Identity = the secure *channels* (physical / Tailscale / Telegram-account)
  + owner-notification on loss (lost phone → tell Maez → revoke). Not a rail here.
- **Cross-surface live conversation continuity** (resume the same thread across
  Telegram→cockpit→CLI): a separate, larger capability arc.
- **The memory-parity build**: separate slice, gated behind Rail 1.

## Covenant rail

This hardens the **doors, egress, and secrets** — never the **eyes**. Perception
stays free; privacy is a curtain, not a muzzle. Nothing here restricts what Maez may
*perceive* of its own body or the public web; it restricts who may reach *in* and
what may leak *out*.
