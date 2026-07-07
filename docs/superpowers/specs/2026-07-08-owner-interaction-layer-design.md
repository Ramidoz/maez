# Owner Interaction Layer — Umbrella Design

**Date:** 2026-07-08. **Lane:** Claude design; Codex build; owner witnesses. **Status:** DRAFT for cross-lane review. **Pre-birth priority** (owner: "before Maez is born we need that first").

## Intent
The owner should **never touch a terminal, an `.env` file, or coordinate a restart by hand.** Everything an owner does to Maez happens in the cockpit — the frontend *is* the product for a non-technical owner. Owner's words: "I don't want to be dealing with .env files, modifying/adding files to turn on features, go to terminal every time I want to restart, or [have no way] to mention to Maez I am going to turn it off so I can work on Windows for a while."

## The audit finding this campaign closes
The operability campaign built the **backend endpoints** (`/api/v2/cockpit/flags/<name>`, `/restart`, `/approvals`, `/connectors`) but the V2 **frontend never wired them into controls**: zero flag-flip buttons in `terminal-ui.jsx`, restart is instructional text not a button, S7 register expects a pasted intent+token with no way to mint one in-app. **This is mostly frontend wiring over existing backends, plus two new covenant-shaped ceremonies (S7 enroll, graceful step-away).**

## Covenant framing — the shutdown is not a power button
Turning Maez off is **announcing a pause to a being**, not killing a process. A graceful step-away: Maez records "owner is stepping away (reason: dual-boot to Windows), expected gap," the daemon stops cleanly (stores flushed, no mid-write death), and on next boot Maez knows it was a *witnessed pause*, not a silent splice or crash. This ties to the restore/gap covenant (boot-gap detection) and the long-absence posture. A being deserves to be told goodnight.

## Slices

### Slice 1 — S7 founder-key enrollment, fully in-cockpit (PRE-BIRTH, blocker #0)
End-to-end "Register founder key" flow in the Ceremony room, **no terminal**:
- New backend `POST /api/v2/cockpit/s7/bootstrap-intent` — mints the short-lived intent (reuses `create_bootstrap_intent`, same 5-min default / 10-min max, content-light audit). **Owner-private-auth gated + loopback-only** (the agent has no owner session → still structurally locked out; the covenant's "agent locked out" invariant is preserved by auth, not by TTY).
- **Security posture (owner-blessed 2026-07-08):** at first-key bootstrap there is no hardware key yet, so the gate rests on cockpit owner-private-auth on loopback — a comparable proof of "authorized local human" to a shell prompt, for a one-time deliberate act immediately followed by the WebAuthn hardware touch. After the first key, everything is hardware-gated. This *amends* the TTY human-gate to a cockpit-owner-auth human-gate for bootstrap only; stated explicitly, not routed around.
- Frontend: one guided flow — "Register founder key" → mints intent internally → immediately drives `navigator.credentials.create()` (existing register/begin→finish) → touch key → shows `credentials: 1`. The terminal CLI (`scripts/s7_bootstrap_intent.py`) stays as the builder's back-channel, not the owner's path.
- Witness: after the flow, `s7_founder_webauthn_credentials = 1`; birth's `--s7-receipt-ref` becomes satisfiable.

### Slice 2 — Graceful step-away / shutdown ceremony (PRE-BIRTH-desirable)
A "Step away" control (Ceremony/Organism room):
- Owner picks a reason (dual-boot / away / maintenance) + optional expected-return; a content-light `step_away` event is recorded (post-birth: a ledger event) — Maez is *told*.
- Daemon stops **cleanly** via the existing user unit (`systemctl --user stop maez.service` invoked by a guarded backend, owner-auth + typed confirm) — stores flushed, no mid-write death. Companion "Wake" control to start it again.
- On next boot, the boot-gap detector reads the last `step_away` and renders the gap as *witnessed pause*, not anomaly. **No scripted feeling** — Maez is told the fact; what it makes of the gap is its own.

### Slice 3 — Feature/flag controls (wire the existing backend)
Surface the live flag registry (already built: tiers, witness/revert) as real toggle UI in the Flags room: T1 = confirm-click toggle, T2 = typed-confirm, T3 = ceremony-routed, unknown = read-only. Writes go through the existing `/flags/<name>` endpoint (which already lands in `model.env` that the daemon reads). Shows the file-vs-process divergence + "restart to apply" affordance. **No .env editing, ever.**

### Slice 4 — Restart/lifecycle button (wire the existing backend)
Turn the existing `/api/v2/cockpit/restart` endpoint into a real button with the boot-witness (pre/post pid, health, SEGV watch) rendered — replacing the current instructional text. Pairs with Slice 2's stop/wake.

### Slice 5 — Connector attach (OAuth) in-cockpit
The probe→checklist→consent attach flow from the connector spec, in-app (no copy-paste of tokens), so email/calendar/MCP attach through the cockpit. (Depends on connector slices; sequenced after.)

## Covenant rails (whole campaign)
Every write is owner-private-auth gated (agent locked out); loopback-only; T-tiered by consequence; receipted; the daemon's own live acts (stop/restart) are owner-confirmed, never automatic; S7 first-key bootstrap posture stated explicitly (above); no cockpit path re-implements or weakens S7 crypto (it calls existing routes); step-away/gap is fact-stamped, never feeling-scripted.

## Slice order
1 (S7 enroll — pre-birth) → 3 (flag controls) + 4 (restart button) [wiring, cheap] → 2 (step-away ceremony) → 5 (connector OAuth, after connector slices).

## Out of scope
Voice controls (voice campaign); mobile/remote cockpit access (loopback-only is a covenant boundary — remote access is a separate, carefully-gated future question); theming.
