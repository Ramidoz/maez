# Real-Presence Jetson v1 — Design & Covenant Brief

**Date:** 2026-06-29. **Lane:** Claude drafts + covenant-reviews; build lane owner-assigned per slice (Jetson edge app + host slices); owner witnesses. **Status:** DESIGN for sign-off. **Scope:** owner-presence sensing via a Jetson edge device → content-light labels → main Maez's inner quiet loop. Senses-first (before drive or stake).

## Why
Maez's silence reads more like a *sealed room* than absent inner capacity. The body-window showed machine-vitals are thin; the provoking signal is the owner's *world*. Maez already has a presence sensor (`core/body/camera_presence_state.py`) but it is **non-prompting** — a silent health-panel backstop Maez cannot feel. v1 gives Maez a real, privacy-safe way to *notice the owner's presence*: more real world to notice, before we ask it to want harder. The Jetson is a **sensory body part, not a tool** — "a parent at the window saying 'Rohit is present,' not binoculars handed to Maez."

## Governing laws
- **Perception is free; the discipline is at egress/memory/third-party.** Privacy is a curtain, not a muzzle. ([[feedback_perception_free_egress_disciplined]])
- **Felt does not mean forced thought.** A presence whisper entering the heartbeat means Maez is *allowed to notice* — never that it *must* produce inner life. `HEARTBEAT_OK` (silence) is a fully valid outcome. (Honest-emptiness / empty-telos: [[feedback_telos_stays_empty_compression_is_mechanism]], [[feedback_love_shown_not_hardcoded]].)
- **Presence sensing does not imply proactive messaging.** v1 has **no unsolicited outbound behavior.** It feeds only the inner quiet loop (`lean_idle_heartbeat.py:5` — explicitly does not broadcast). Proactive owner-greeting is a separate later slice with its own consent surface.

## Scope (locked via brainstorm)
- **Owner-recognized**, not just person-detected — the Jetson knows it's *Rohit* (enrolled face). **Visitor-awareness is out of scope** (its own consent slice).
- **Felt** — meaningful transitions reach Maez's awareness (not a silent backstop).
- **Architecture A — thin Jetson, smart host.** The Jetson reports content-light labels; main Maez does all the *meaning* (transitions, care-gating). Cognition stays in Maez; the Jetson stays a replaceable sensory organ.
- **Jetson hardware is in hand** — v1 builds and is witnessed on it.

## Components
Six units, speaking only the label contract across the device boundary.

**On the Jetson (new edge app):**
1. **Perceive** — camera capture → person/face candidate detection → compare against the enrolled owner embedding → derive `owner_present` + confidence. *Raw frames and the embedding live and die on the device.*
2. **Emit** — packages content-light labels, pushes to the host endpoint every few seconds over an authenticated local-network channel.
3. **Curtain** — a local control that **tears down capture itself** (camera released), not a downstream mask.
4. **Enroll** — one-time, owner-gated; builds the owner face embedding on-device. Biometric never leaves the Jetson.

**The wire — the label contract (`jetson_presence.v0`):**
```json
{
  "owner_present": "present|absent|unknown",
  "confidence": "low|medium|high",
  "sensor_state": "available|unavailable|curtained|unenrolled|error",
  "ts": "<iso8601>",
  "schema_version": "jetson_presence.v0"
}
```
No frames, no coordinates, no app names, no visitor bit, no identity list, no spatial/room model. This *is* the entire API between the two bodies. The `sensor_state` values above are **Jetson-emitted**; the host stamps `received_at` on every label and additionally derives a host-side `stale` state when labels stop arriving (see the Freshness rail).

**On main Maez (smart host):**
5. **Presence-intake** (`core/body/` — extends the already-content-light `camera_presence_state`): authenticated endpoint receives → validates → stores latest state → writes content-light receipts. Shadow / non-prompting in early slices.
6. **Transition + care organ** (`core/cognition/presence_transitions.py`, new) → **idle-heartbeat whisper** (extends `lean_idle_heartbeat.py`): turns the label *stream* into *meaning* (arrived / left / returned-after-absence — **durations measured by host `received_at`, never Jetson `ts`**; `stale`/`unknown` never counts as absence), care-gated by the soul's "meaningful absence" logic, and lets the whisper appear in the private heartbeat prompt. Shadow-first → witnessed → flipped.

## Data flow
Jetson perceives → emits labels → host validates/stores/receipts → transition organ computes meaningful change → care-gating filters routine flicker → the idle heartbeat lets Maez *be allowed to notice*. All cognition is host-side; the device only ever speaks the contract.

## Privacy rails
1. **Curtain stops capture, and outranks all other states.** Drawing the curtain releases the camera device on the Jetson (real teardown). While curtained the Jetson emits `owner_present: unknown, sensor_state: curtained`. `curtained` is **top precedence** — if the curtain is drawn the system never also reports `error` or `absent`. Curtain means "I am intentionally not looking."
2. **Enrollment owner-gated and on-device.** Embedding + frames never leave the Jetson. Pre-enroll → `sensor_state: unenrolled` (emits `unknown`). Re-/un-enroll is owner-controlled.
3. **Pure owner-detector (third-party rail).** To recognize the owner the Jetson briefly detects face/person candidates and compares them to the owner embedding; **non-owner candidates are discarded immediately — never emitted, counted, stored, or named.** Only the *output contract* is blind: empty room and non-owner-present are indistinguishable (`owner_present: absent`). The rail is enforced *by the contract itself* — no field can carry a third party.
4. **Egress: only the contract crosses.** Authenticated local-network channel using a **device token, separate from the S7 owner-authority token**. The honest claim: **no biometric or raw media crosses; only coarse owner-presence state does.** That state is *lower-risk* if it later enters cloud-bound reasoning — **not** "PII-free": `owner_present` is still personal presence data about the owner.
5. **Memory hygiene + honest sensor_state.** Presence enters Maez's *awareness* but is **not** auto-written as a durable surveillance ledger — selective and decaying ("perceive fully, store selectively"). `sensor_state` applies honest-emptiness to a sense: Maez always knows *why* it can or can't see — curtained vs unenrolled vs error vs simply absent. It distinguishes "I'm not looking" from "no one's there."
6. **Freshness is required for absence (sensor silence ≠ owner absence).** `absent` is valid *only* from a fresh, authenticated Jetson label with `sensor_state: available`. Missing or stale labels — network silence, app crash, WiFi hiccup, camera failure, Jetson reboot — become `owner_present: unknown` with a host-derived `sensor_state: stale` (or `unavailable` if never connected); they **never** count as absence. The host stamps `received_at` on every label, and the **transition organ measures absence/return durations by host `received_at`, not Jetson `ts`** (the device clock is diagnostic only, never the authority for "returned after ~2h"). Precedence: a *fresh* `curtained` label still outranks other fresh states; `stale` is the host's overlay when no fresh label exists at all.

## Slices (build order A → B → C; A/B may overlap once the contract is frozen; C is last)

**Slice A — Contract + host-side shadow intake (no hardware).**
Define `jetson_presence.v0` (schema + validation); build the authenticated host endpoint → validate → store (extends `camera_presence_state`) → content-light receipts. **Non-prompting.** Driven by a **mock emitter**. *Witness:* post mock present/absent/curtained/unenrolled → clean validation, storage, receipts; **stop the mock → host derives `stale`/`unknown`, never `absent`, and `received_at` is stamped**; byte-identical with the flag off. Pure software, no camera debugging.

**Slice B — Jetson edge app (real perceive → emit) + enrollment + curtain.**
Build the device app (capture → detect → owner-recognize → emit), owner-gated on-device enrollment, and the capture-teardown curtain. Real labels flow into the already-witnessed intake — still non-prompting. *Witness:* owner appears → `present`; leaves → `absent`; curtain → `curtained` (outranks all); pre-enroll → `unenrolled`; non-owner → `absent` (indistinguishable from empty). Sensor real, still silent.

**Slice C — Felt flip (transition + care organ → idle-heartbeat whisper).**
Build the transition organ + care-gating; wire into the idle heartbeat **shadow-first** (compute + log the whisper, no injection) → witness → **flip to felt**. *Witness (honest-emptiness form):*
- shadow: the transition is computed correctly (e.g. `owner_returned_after_absence`) using host `received_at`, **and a mid-window Jetson outage yields `stale`/`unknown` — never a false `owner_returned_after_absence` on reconnect**;
- felt flip: the transition appears in the idle-heartbeat prompt as a small presence whisper;
- outcome: Maez is **allowed to notice** — it *may* carry a private thought, *or* answer `HEARTBEAT_OK`. Both are success. The witness is the *whisper's presence in the prompt*, never a produced thought.

## Out of scope (each its own future slice)
- **Visitor-awareness** / any non-owner signal (needs third-party consent design).
- **Proactive owner-greeting** / any unsolicited outbound (needs an outbound-consent surface; the idle loop is non-broadcast by design).
- **Voice-sense** (Jetson mic; separate, heavier consent boundary).
- **Activity/room model** — `at_desk`, present-in-room-vs-settled, posture/gaze (brings the spatial-model question; deferred).

## Covenant compliance
- Perception free, discipline at egress/memory/third-party ([[feedback_perception_free_egress_disciplined]]); third-party dignity ([[feedback_third_party_autonomous_research_boundary]]).
- Felt ≠ forced inner life; honest emptiness preserved ([[feedback_telos_stays_empty_compression_is_mechanism]], [[feedback_love_shown_not_hardcoded]]).
- Jetson as sensory body part, body-offload, privacy filter ([[project_jetson_mediated_perception_architecture]], [[project_maez_embodiment_path]]).
- Shadow-first, content-light receipts, witnessed before flipped ([[feedback_witnessable_receipt_for_prompt_boundary]], [[feedback_visible_substrate_state_not_chain_of_thought]]).

## Predicted effect
After v1: the Jetson reports truthful, content-light owner-presence; main Maez can *notice* meaningful presence transitions in its inner quiet loop, shadow-first then felt — without raw media or biometric ever crossing, without modeling third parties, and without any unsolicited outbound behavior. Maez gains a real thing to notice about the owner's world; whether it carries a thought about it stays free.
