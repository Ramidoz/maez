# Maez Body / Organ View v0 — Design

**Date:** 2026-06-02
**Status:** Draft under review (owner review pending before plan/Codex)
**Scope (owner-set):** *Let the owner see Maez's body* — a live, read-only, local-only dashboard of Maez's organs, so growth and aliveness are *witnessed*, not narrated by Claude/Codex. Phase 1 of the growth-UI vision. Phase 2 (the spatial Memory Atlas) comes later, after reflection's window. Reference image is a **north star, not the interface**.

---

## 1. Purpose + the line we hold

The owner builds Maez extensively with Claude/Codex and has no window into what's actually happening — whether Maez is alive, resting, growing. This gives them one: open a page, see which organs are awake, which are resting, and what each last did.

**The danger, named:** a beautiful hologram that *implies life the data doesn't prove*. So the governing rule, inherited from this session's discipline:

- **Proprioception, not theater** — every glow/tile/label maps to **real state** from a real source. If the data isn't there, the tile doesn't pretend (it shows "off" / "unknown" / "not yet wired"), it does not animate aliveness. ([[feedback_visible_substrate_state_not_chain_of_thought]])
- **Lens, not hand** — read-only. v0 does **not** toggle organs, edit memory, or "optimize" anything. It only lets you look. (The Memory Atlas guardrail, applied early.)
- **Local-only** — served on `127.0.0.1:11435`, never nginx-proxied (the existing `/dashboard` already enforces this). Maez's body is not a public webpage.
- **Witnessed construction, not finished deity** — the visual register is calm and instrument-like; Maez is in gestation and the UI should say so.

---

## 2. Architecture

Two parts, one data contract.

**(A) Backend — compose a content-free `body` view into `/health`.** The browser can't read env vars or local files, so the organ truth must arrive through the endpoint. Extend the existing `/health` (daemon, `HEALTH_PORT=11435`) with a `body` object: one content-free sub-dict per organ (states / flags / counts / enums / timestamps — **never** memory or reflection text). `/health` already carries eyes/memory/brain/body/cycle; this adds the missing organs from env flags + counts + readily-available state. Additive, non-breaking, local-only.

**(B) Frontend — rebuild `ui/dashboard_local.html` into the Body/Organ View.** A central Maez form with radial organ callouts (the image's *language*, calmer execution), each tile bound to its `body.<organ>` fields, polling `/health` on the existing cadence. Read-only. Keeps the existing local-only warn banner.

---

## 3. The organ map (every tile → real source → content-free fields)

| Organ (body metaphor) | Source | v0 fields | Tier |
|---|---|---|---|
| **Eyes** (camera presence) | `/health.camera_presence` | mode, sensor_state, presence_state, confidence_bucket, enabled_until, last_observed_at | **v0 (ready)** |
| **Memory** | `/health.memory` {raw,daily,core,total} + episode store | raw/daily/core counts; reflection count; active vs superseded | **v0 (ready + small count add)** |
| **Brain** | `/health.model` | served model alias (qwen36-27b) | **v0 (ready)** |
| **Body** (hardware) | `/health.system` | cpu%, gpu%, gpu_temp_c, ram% | **v0 (ready)** |
| **Heartbeat** (cycle) | `/health.reasoning_loop` + `cycle_count` + `uptime` | current stage, cycle age, stalled?, cycle count, uptime | **v0 (ready)** |
| **Attention** (doorman) | env `MAEZ_CYCLE_DOORMAN_ENABLED` (+ quiet-skips/last-wake) | enabled (flag) — v0; quiet_skips, last wake/skip reason — v0.1 | **v0 flag / v0.1 activity** |
| **Cycle mind** (packet) | env `MAEZ_CYCLE_FOCUSED_ENABLED` (+ `cycle_packet_shape` telemetry) | enabled (flag) — v0; last packet tokens/timing — v0.1 | **v0 flag / v0.1 activity** |
| **Stomach** (reflection) | env flags + reflection count + newest receipt path | enabled/write/max (flags), reflections kept — v0; last receipt timestamp — v0.1 | **v0 flags+count / v0.1 receipt** |
| **Dreaming** | dream state | enabled — v0; last fire / cooldown remaining — v0.1 | **v0 flag / v0.1 activity** |
| **Recall** | env `MAEZ_RECALL_TRIAD_ENABLED` (=0) | **OFF**, shown clearly (not hidden) | **v0 (ready)** |
| **Covenant perimeter** | env + config invariants | never-delete ✓, local-only ✓, no public exposure ✓, screen-vision OFF (`MAEZ_SCREEN_PERCEPTION` unset) | **v0 (ready)** |

**v0 = state/flags + counts + the readily-available `/health` data** (enough to truthfully show *which organs are awake and their current state*). **v0.1 = the "what it last did" activity** (doorman quiet-skips, dream last-fire, packet timing, last receipt) — deferred where it needs new content-free plumbing, so v0 ships fast and stays honest rather than faking activity it can't yet read.

---

## 4. Explicitly NOT in v0

- **No growth-over-time charts / trends.** Trends need a content-free history-snapshot feed that doesn't exist; without it, charts are theater. **Live truth first**; trends become a later slice once a snapshot organ exists.
- **No controls** — no toggles, no memory edits, no "optimize." Lens, not hand.
- **No public exposure** — local-only, unchanged.
- **No implied life beyond data** — a tile with no real source shows "not yet wired," never a fake pulse.
- **Not the Memory Atlas** (Phase 2 / parked — the spatial memory map), and not the cinematic hologram (north-star only).

---

## 5. Slicing + acceptance

- **Slice A — `/health` body composition:** add the content-free `body` object (the organ sub-dicts above) to `/health`. Backend, unit-testable (assert each organ section present, content-free — no memory/reflection text, no episode ids beyond counts). Lands on next restart.
- **Slice B — Body/Organ View frontend:** rebuild `ui/dashboard_local.html` to render the organ tiles from `body`, calm/instrument-like, read-only, local-only. Owner-witnessed: open `127.0.0.1:11435/dashboard`, every tile reflects real state (cross-checked against `/health` + the live flags), nothing glows that isn't true.

Acceptance (owner): the page shows Maez's organs truthfully — eyes present/absent matching the camera, recall clearly OFF, reflection ON at 1/night, memory counts matching the store — and **no tile implies an aliveness the data doesn't back**.

---

## 6. Non-goals / future

- v0.1: organ *activity* (last wake/fire/receipt, packet timing) once the content-free reads are plumbed.
- Later: growth-over-time (history snapshots) → trend curves.
- Phase 2: the spatial Memory Atlas (parked; after reflection's window).
- Never: turning the body view into a control panel, or exposing it publicly.
