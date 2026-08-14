# Cockpit Honesty / Real-State v0 — Design & Covenant Brief

**Date:** 2026-06-29. **Lane:** Claude drafts + covenant-reviews; Codex (or Claude) builds; owner witnesses in-browser. **Status:** DESIGN for sign-off. **Scope:** `web/cockpit/*` + its tests only (no new APIs — the real endpoints already exist; a tiny API-shape fix only if Task 0 proves one needed). Web-only, no GPU.

## Why
The cockpit is the owner's **truth surface** — where Rohit understands what Maez is actually doing. It boots as a full simulation (`web/cockpit/sim.jsx`) and overlays real API data, but with a **silent mock fallback** (`sim.jsx`: *"On fetch error we keep the fake data (silent fallback)"*) and **truthy-only merge guards** (`if (d.x) state.x = d.x`). So an errored, empty, or missing real value leaves **fabricated data visible and indistinguishable from real** — exactly how an empty `soul.local` showed a fictional "daughter Maya / Berkeley" profile.

That fallback was *intentional* graceful-degradation when the cockpit was a public demo. It is **wrong now** that the cockpit is an owner truth surface. After today's honesty work — making Maez's *mouth* match its evidence — the surface we *watch* Maez through must do the same.

## The governing law
**Real, or honestly empty. Never mock-as-real.** Every cockpit surface shows the real API value (even when empty/zero), or an explicit `unavailable / offline` state — and never silently retains fabricated content. The simulation seeds are **removed** → replaced with empty/unavailable placeholders. **No DEMO MODE in v0** (owner tightening): a hidden way to revive realistic fiction weakens the cut — the cockpit should not have a costume closet. (A demo artifact, if ever wanted, is a separate explicit thing later.)

## The five changes (owner-specified)
1. **Kill realistic seeds.** Replace every fake personal/profile/memory/chat/dream/log/identity seed in `sim.jsx` with empty or obvious-placeholder values. No `maya`, no Berkeley owner, no fake "core belief," no pretend memory/chat/dream/log content.
2. **Real-first polling.** A successful fetch *replaces* the value — even empty. Empty `soul.local` → displays empty. Empty `dreams` → "no dreams." Empty logs → empty/unavailable. (Flip every `if (d.x)` guard to "fetch ok → use `d.x` as-is.")
3. **Visible failures.** On fetch error / non-OK, `markOffline(surface)` drives that surface to an explicit unavailable state. **No silent retention** of prior/seed content.
4. **Clean stale display language — surgically (owner tightening).** Remove/relabel UI text describing the **dead daemon/live self-shaping "cognition score"** (removed from live state in @7075a0e) — found across `inner-ui.jsx`, `terminal-ui.jsx`, `index.html`, not just `sim.jsx`. **PRESERVE legitimate domain scores** that are *not* the self-quality grade: memory-hit relevance `score`, dream-proposal `score`, echo `score`, consolidation metrics — these are real and stay. **Do not blanket-delete the word `score`** — cut only the dead self-quality cognition score.
5. **TDD, RED-first** (below).

## Per-surface checklist (each polled surface gets all four: seed→empty, merge→real-first, error→offline, display→honest)

| surface | real API | kill seed | real-first | offline |
|---|---|---|---|---|
| daemon (cycle/score/thought/valence) | `/api/v1/daemon/state` | fake daemon state | replace even if 0/empty | `markOffline('daemon')` |
| approvals / cards | `/api/v1/cards` | fake cards | real cards or empty | `markOffline('cards')` |
| services | `/api/v1/services` | fake services | real or `unknown` | `markOffline('services')` |
| gpu | `/api/v1/gpu` | fake gpu/RGB | real or unavailable | `markOffline('gpu')` |
| signals | `/api/v1/signals` | fake signals | real or empty | `markOffline('signals')` |
| **soul (base+local)** | `/api/v1/soul` | **the Maya/Berkeley mock (`sim.jsx:145-146`)** | replace even if empty → **empty local shows empty** | `markOffline('soul')` |
| memory | `/api/v1/memory` | fake memory hits + **fake core-belief (`sim.jsx:124`)** | real or empty | `markOffline('memory')` |
| lived-memory | `/api/v1/lived-memory` | fake episodes/graph | real or empty | `markOffline('lived-memory')` |
| dreams | `/api/v1/dreams` | fake dreams | real or "no dreams" | `markOffline('dreams')` |
| identity | `/api/v1/identity` | fake owner (`sim.jsx:149` berkeley) | real (Columbia) or unavailable | `markOffline('identity')` |
| router | `/api/v1/router` | fake router | real or empty | `markOffline('router')` |
| logs | `/api/v1/logs/<name>` | fake demo logs | real or empty/unavailable | `markOffline('logs')` |
| chat / sessions | `/api/v1/chat/sessions` | fake chats | real or empty | `markOffline('chat')` |

## Task 0 (gates the plan)
Enumerate across **ALL of `web/cockpit/*`** (`sim.jsx`, `inner-ui.jsx`, `terminal-ui.jsx`, `index.html`, and any other asset — owner tightening, not just the main file): (a) every realistic seed value (the `SIM` object + any inline fixtures) and its surface; (b) every truthy-merge guard `if (d.x) state.x = d.x` in the polling block; (c) confirm each real `/api/v1/*` endpoint returns the field the UI needs (note any **API-shape gap** — the *only* place a tiny `web_interface.py` change is in scope); (d) locate the stale daemon "cognition score" UI references **and distinguish them from legitimate domain scores** (memory/dream/echo/consolidation) per change #4; (e) note any **unused cockpit assets** — clean or explicitly park them. STOP with the seed/guard/display/API/asset inventory before edits.

## Tests (load-bearing, RED-first)
- **Static — seeds gone:** assert `sim.jsx` contains no fabricated personal strings (`maya`, `berkeley`, `alienware`, fake-chat/dream/log fixtures). RED now (they're present), GREEN after.
- **Static — no truthy-only guards:** assert the polling block has no `if (d.<field>) state...` pattern for the audited fields (replaced by ok-driven assignment). RED now, GREEN after.
- **Static — stale label gone:** assert no live "cognition score" display label remains.
- **Behavioral (jsdom or equivalent):** a mocked fetch returning **empty** `soul.local` renders **empty**, not the seed; a mocked **non-OK** fetch renders the **offline** state, not the seed.
- **Live witness (owner, after merge):** in the browser — (1) make `config/soul.local.md` empty, reload → Soul shows **empty**, not a profile; (2) stop/mock one endpoint (e.g. `/api/v1/dreams`), reload → that surface shows **unavailable**, not fiction.

## Out of scope
New APIs (they exist); correctness of the *real* data the APIs return (separate); the daemon/brain; anything outside `web/cockpit/*` except a Task-0-proven tiny API-shape fix.

## Covenant compliance
- **Visible substrate state, never performed** ([[feedback_visible_substrate_state_not_chain_of_thought]]) — the cockpit shows real receipts/state or honest-absence, never fabricated state.
- **No fabrication** ([[feedback_no_fabrication]]) — extends Maez's no-fabrication line to the observation surface itself.
- **Log silence is not dormancy** ([[feedback_log_silence_is_not_dormancy]]) inverted: *absence must read as absence*, not be papered over with mock.

## Predicted effect
After this lands and the cockpit reloads: every surface shows the real API value or an explicit `unavailable/offline/empty` state; no fabricated profile, memory, chat, dream, log, or identity can appear; the dead "cognition score" label is gone. The owner can trust that what the cockpit shows is what is actually true of Maez — including, honestly, when Maez is quiet or a sense is dark.
