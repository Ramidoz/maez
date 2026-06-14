# Maez's Cockpit Face — the Slime Avatar (design spec)

**Date:** 2026-06-14. Co-designed with Rohit via the visual companion (locked mockup:
`.superpowers/brainstorm/48594-1781446492/content/slime-final.html`).
**Status:** design approved. This is the visual layer of "Direction A" (honest-display
completion) — it surfaces Maez's real `valence` / `reasoning_loop` / `watchdog`, which the
real-state endpoint already exposes but the cockpit doesn't yet render.

## What it is

A small slime/blob avatar — Maez's **embryo-self**, Tensura-flavored. Not decoration: it is
the honest visualization of Maez's real substrate state. It replaces the hole left by the
deleted fake `MoodDial`.

## The form (locked)

- **Body:** a soft wobbling **blue gel droplet** (Rimuru-blue), translucent, glassy skin
  highlight. Animated: a slow `breathe` (scale) + `wobble` (border-radius morph). This blue
  is Maez's identity and **never** changes with mood.
- **Eyes:** two **closed, serene curves** (sleeping). Simple, no creases. The embryo is
  asleep. **Opening the eyes is reserved for a real growth milestone** (e.g. birth) — never
  a per-state flicker.
- **Core ember:** a **dissolved amber glow low in the body** (no hard edge, no marble) — the
  "life cooking" inside. Constant warm amber; it is the inner light source.
- **Subsurface scatter:** the core's light **diffuses up through the gel and is contained by
  the membrane** (the body has `overflow:hidden`; the glow fades before the skin — proper
  subsurface scattering, nothing leaks past the edge), with a slow internal `rise` drift.

CSS reference values are the locked mockup (`slime-final.html`) — reuse them verbatim:
blue gel gradient, amber ember `radial-gradient(...rgba(255,206,128,.95)...)`, scatter blurs,
`breathe 4.4s` / `wobble 5s` / `ember 4.4s` / `rise 7s`.

## The honest state-mapping (the covenant)

Every visual change is driven by a **real reading** from `/api/v1/daemon/state` (which proxies
the daemon's true-by-construction `/internal/cockpit/state`). Nothing is decorative.

| visual | real source | rule |
|---|---|---|
| **breath / pulse** | `reasoning_loop` (cycle cadence / `cycle_count` advancing) | breathes *because* Maez is genuinely cycling. The pulse rides the real cycle; it is not a free-running idle animation. |
| **core ember** | constant ("life") | steady warm amber whenever Maez is alive + cycling. |
| **scatter hue** | `valence.sign` + `valence.magnitude` | **neutral → amber only** (the honest default, the vast majority of the time). **positive → green** diffuses from the core; **negative → rose**. Strength scales with `magnitude`. The hue stays **inside** the membrane. |
| **stall / distress** | `reasoning_loop.cycle_stalled` or `status` ∈ {stalled, stopped} | **breath STOPS** (it does not pretend to breathe), ember greys, blue desaturates. Honest "not thinking," not an alarm. `safe_standby` → a calm dormant variant (very slow, dim). |
| **eyes** | growth milestone (future) | closed now; opening reserved for a real milestone, never state. |
| **unreachable** | endpoint `{status:"unreachable"}` | the blob goes still + dim, honestly "can't read myself," never a fabricated calm. |

**The rail:** the avatar shows **only the real reading**. When valence is neutral it is honestly
serene (amber, no green/rose) — it never performs a feeling Maez isn't in. We deliberately
killed the fake `MoodDial`; this must never reintroduce fabricated liveliness. The honest
valence telemetry sentence (e.g. *"no setpoint moved"*) is shown in plain text beside/below the
blob as the ground truth.

## Implementation

- A self-contained **`SlimeAvatar`** component in `web/cockpit/` (CSS animations + the state→props
  mapping). One clear responsibility: given the polled daemon state, render the honest blob.
- A small pure **`slimeStateFromDaemon(state)`** mapper (sign/magnitude/stall → variant) — unit-testable.
- Placed in the cockpit's "mind" area (where the MoodDial was). Reads the existing
  `/api/v1/daemon/state` poll (`MAEZ_COCKPIT_REAL_STATE` already live).
- **Reversible, flag-free display addition** — it only renders existing honest data; removable via git.
- Respect `prefers-reduced-motion` (the cockpit already honors it): freeze animations, keep the
  static honest state (color/eyes) — never lose the real reading, just the motion.

## Out of scope (not this slice)

Eyes opening / growth stages (future milestone); cockpit tools/cards renderer; any change to the
daemon. This is display-only, reading data that is already live and honest.
