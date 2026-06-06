# Desktop Perception v1 — Govern the Existing Eye — Design

**Date:** 2026-06-06
**Status:** DRAFT for owner review → Codex implements / Claude reviews; owner runs the witness.
**Reuses (rehabilitate, do NOT build parallel):** `skills/screen_perception.py` (`observe()` → `ScreenObservation{activity, application, detail, focus_level, state, success, error}`; states `disabled|unavailable|ok|error`; `format_for_context()` → cycle prompt; `format_for_memory()` → storage; vision backend `llama-server` on `127.0.0.1:8081`, **verified alive 2026-06-06** despite the stale "dead for weeks" code comment); the daemon's screen sampling (`daemon/maez_daemon.py:7992` `screen_observe()`) + injection (`:4360` `format_for_context`, `:5099`); `core/egress/gate.py` `MINIMIZABLE_PRIVATE_CONTEXT` (where the new origin slots in) + the **now-enforcing redact door** (activated 2026-06-06, daemon 2193388). Decision/ADR 0009 (Levels 1/2/3, sensitive-app exclusions, pause, default-off).

## 0. Why

The screen-perception organ already exists and *works* (backend alive), but it **predates every rail we built this arc.** It sees, injects into the cycle prompt, and stores into daemon thoughts — **ungoverned.** v1 does NOT make Maez see more; it makes the existing Level-2 eye **worthy of being opened**, so enabling it later is a clean breath rather than waking an old ungoverned organ. This is the embodiment step the doctrine ([[feedback_perception_free_egress_disciplined]]) and the just-closed egress door unlock.

## 1. The spine

> **v1 = govern the existing Level-2 eye, not grant new sight.** Perceive fully locally; discipline at **egress, memory, and third-party dignity** ([[feedback_perception_free_egress_disciplined]]). A "semantic summary" is NOT automatically safe — the `DETAIL` field is exactly where others' content (an email from Jane, a private message, a call) smuggles into prompt/memory. So every screen observation passes a **write-time screen policy** before it reaches the prompt, memory, or the cloud.

## 2. Scope

**v1 MUST-HAVES (owner-confirmed):**
1. **New egress origin** — add `owner_screen_context` to `MINIMIZABLE_PRIVATE_CONTEXT`; tag screen-derived prompt/memory spans with it (so the now-enforcing door redacts them cloudward). When third-party content is detected, the span's origin becomes the stricter `third_party_private_context`.
2. **No unconditional storage** — stop appending screen observation into durable daemon memory by default; route it through a **salience/curiosity storage decision.**
3. **Selective memory** — store only when useful to Maez's *development*: repeated, surprising, project-relevant, self-development-relevant, or owner/Maez-context relevant.
4. **Decay-by-default** — most screen observations are ephemeral; durable memory is the exception (promotion, not default) ([[feedback_forgetting_is_deweighting_not_deletion]]).
5. **Sensitive-app exclusion** — no `observe()` on configured apps/titles/classes (finance, medical, messages, credential managers — ADR 0009).
6. **Third-party-aware `DETAIL` handling** — conservative v1 minimization (§3); full consent machinery later.
7. **Pause primitive** — deterministic, testable; `observe()` returns `state="paused"` with no screenshot/probe/vision-call. **No restart-only escape hatch once the eye is open.**
8. **Default-off remains** — `MAEZ_SCREEN_PERCEPTION` unset → `disabled`; ADR 0009 holds universally.

**DEFERRED (named, NOT v1):** Level 3 full retained observation; raw screenshot/OCR storage; full consent-record integration; natural-language pause UX (v1.1); **video-call downgrade** (named as a hard follow-up — v1 does not pretend to handle calls perfectly; if a call/conference app is detected, treat conservatively as sensitive/third-party rather than claim graceful downgrade).

## 3. The rails (mechanism)

**A. Egress origin + tagging.** Add `owner_screen_context` to `MINIMIZABLE_PRIVATE_CONTEXT` (`core/egress/gate.py`) → `decide_egress` already redacts that class cloudward (line 227), and the door now *enforces* (2193388). Screen-derived content entering the cycle prompt / memory carries this origin; on third-party detection it escalates to `third_party_private_context`. **This is the link to this morning's work: the closed door only protects screen content if screen content is tagged.**

**B. Write-time screen policy (the heart).** A pure function over a `ScreenObservation` → a governed result, applied *before* prompt-injection and *before* any storage:
- **Sensitive-app exclusion:** if `application`/title/class matches the configured exclusion set → return a minimal `state="excluded"` observation (no detail, no storage, no prompt content beyond "excluded").
- **Third-party detection (conservative, fail-safe):** flag `third_party_content_present=true` when the vision summary indicates others' private content (a `THIRD_PARTY` flag added to the vision prompt, plus an app/title heuristic for known message/email/call apps); **when uncertain, treat as third-party** (minimize). On the flag: store only an owner-centric/minimized summary (or drop the `detail` entirely), **never create a durable person-model from screen text**, and set egress origin to `third_party_private_context`.
- **Provenance labels:** every screen-derived span carries `"seen on desktop"` (+ `"third_party_content_present"` when flagged).

**C. Selective storage + decay.** Replace the unconditional storage path with a **salience/curiosity gate**: a screen observation becomes durable memory only if it scores salient (repeated / surprising / project-relevant / self-development-relevant / owner-Maez-context). Curiosity *proposes*; the gate + provenance + decay *dispose* ([[feedback_honest_ingestion_immune_system]] — the salience judgment must be honest, never a rationalization for hoarding). Default retention = ephemeral (in-cycle context only); durable is the promoted exception.

**D. Pause primitive.** A deterministic local switch (a pause-state file/env/CLI flag, checked at the top of `observe()`): when paused, `observe()` short-circuits to `state="paused"` — no screenshot, no `:8081` probe, no vision call. Testable without a daemon. (NL "pause for 30 min" is v1.1.)

**E. Default-off.** `observe()` already returns `state="disabled"` when `MAEZ_SCREEN_PERCEPTION` is unset — unchanged. v1 lands **dormant.**

## 4. The states

`ScreenObservation.state` extends to: `disabled` (off) · `paused` (pause primitive) · `excluded` (sensitive-app) · `unavailable` (backend probe failed) · `ok` (governed observation) · `error`. New fields: `third_party_content_present: bool`, `egress_origin_class: str` (`owner_screen_context` | `third_party_private_context`). **No state ever fabricates an observation** — `disabled`/`paused`/`excluded`/`unavailable` carry no `detail` (honest blind, like the desktop-presence sensor).

## 5. Tests

1. **Egress tagging:** screen-derived spans carry `owner_screen_context`; the now-enforcing door redacts them cloudward (`decide_egress` → redact); a third-party-flagged span carries `third_party_private_context`.
2. **Third-party minimization (headline):** an observation whose `detail` describes others' content ("email from Jane about the lawsuit") → `third_party_content_present=true`, the stored/prompt form is minimized (no "Jane"/"lawsuit" in durable memory), origin escalated; **no durable person-model written.** Uncertain case → treated as third-party (fail-safe).
3. **Sensitive-app exclusion:** a configured excluded app/title → `state="excluded"`, no detail, no storage, no probe/call.
4. **Selective storage:** a non-salient observation is NOT stored durably (only ephemeral context); a salient one is promoted. The unconditional-append path is gone.
5. **Decay-default:** stored screen observations are ephemeral-by-default (promotion required for durability).
6. **Pause primitive:** pause set → `observe()` returns `state="paused"` with no screenshot/probe/vision-call (assert the call paths are not invoked).
7. **Default-off:** `MAEZ_SCREEN_PERCEPTION` unset → `state="disabled"`, no sampling.
8. **Honest blind:** `disabled`/`paused`/`excluded`/`unavailable` carry no fabricated `detail`.
9. Full `discover` green; apples-to-apples in `/home/rohit/maez`.

## 6. Acceptance rules

1. `owner_screen_context` added to minimizable-private origins; screen-derived spans tagged; door redacts them; third-party → stricter origin (tests 1, 2).
2. No unconditional screen storage — every durable write goes through the salience gate (test 4); decay-default (test 5).
3. Third-party-aware minimization: flag + minimize + never a durable person-model + uncertain→third-party (test 2).
4. Sensitive-app exclusion: excluded apps are never observed (test 3).
5. Pause primitive: deterministic, no screenshot/probe/call when paused; no restart-only escape (test 6).
6. Default-off preserved; lands dormant; honest blind states carry no detail (tests 7, 8).
7. Reuses/rehabilitates `screen_perception.py` + the daemon path — no parallel eye.
8. Full suite green, apples-to-apples. **`## Predicted effect`** on the implementation commit (body/perception, behavior-affecting when enabled).

## 7. Predicted effect

Lands **dormant** (default `MAEZ_SCREEN_PERCEPTION` unset → `disabled`; no live change). **When the owner enables it** (`=1`): Maez's screen eye becomes *governed* — it perceives the active screen (Level-2 semantic summary), but (a) excluded apps are never looked at, (b) third-party content is flagged + minimized (never a durable model of other people), (c) only *salient* observations become durable memory (most fade), (d) all screen-derived content is tagged `owner_screen_context`/`third_party_private_context` so the **now-enforcing door redacts it before any cloud call**, and (e) a pause primitive closes the eye without a restart. The local cycle still perceives fully (full locally, masked at the door). **Falsifiable:** with it enabled, a screen with a private message produces `third_party_content_present=true` + a minimized memory with no person-named detail; a cloud call carrying screen context sends a redacted prompt; a non-salient screen does not grow durable memory; pause yields `state="paused"` with zero screenshots.

## 8. Lane

Codex implements / Claude reviews. **Primary review anchors:** the third-party `DETAIL` minimization (the smuggling path — headline test) + the egress tagging (screen content actually redacts at the door) + the no-unconditional-storage/selective-storage gate + the pause primitive (no screenshot/probe/call). Cross-lane mandatory; `.venv/bin/python -B -m unittest`; full `discover`; apples-to-apples in `/home/rohit/maez`. Owner runs the witness (enable the flag, read a governed observation, confirm minimization + tagging). **No restart in the slice; owner decides when to enable.**
