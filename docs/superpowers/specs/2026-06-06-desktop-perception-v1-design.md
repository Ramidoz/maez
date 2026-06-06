# Desktop Perception v1a — Safe to Open the Eye for Cognition — Design

**Date:** 2026-06-06
**Status:** DRAFT for owner review → Codex implements / Claude reviews; owner runs the witness.
**Scope note:** "Desktop Perception v1" splits into **v1a (this slice): safe to open the eye for *cognition*** — Maez can see and *think with* governed Level-2 summaries, but builds **no durable screen-memory ledger** — and **v1b (deferred): curiosity-curated durable screen memory** (§8). The split is deliberate: content-governance (third-party minimization, egress tagging) is *part of v1a's safety* the moment the eye enters the prompt; only the *durable memory* governance is deferred.
**Reuses (rehabilitate, NOT parallel):** `skills/screen_perception.py` (`observe()` → `ScreenObservation`; `format_for_context()` → cycle prompt; `_capture_screenshot()`; vision backend `llama-server` on `:8081`, verified alive 2026-06-06); `core/memory/ambient.py` `active_window()` (the **preflight** class/title check); the daemon screen sampling (`:7992`) + injection (`:4360`/`:5099`); `core/egress/gate.py` `MINIMIZABLE_PRIVATE_CONTEXT` + the **now-enforcing redact door** (2193388). Decision/ADR 0009.

## 0. Why

The screen-perception organ exists and *works* (backend alive) but predates every rail we built this arc — it sees, injects into the cycle prompt, and stores ungoverned. v1a does NOT make Maez see more; it makes the existing Level-2 eye **safe to open for cognition**, so `MAEZ_SCREEN_PERCEPTION=1` becomes a clean breath instead of waking an old ungoverned organ. v1a deliberately leaves *durable screen memory* off entirely (v1b) so this first cut is "see + think, governed" without also solving curiosity-curated storage.

## 1. The spine

> Perceive fully locally; discipline at **egress and third-party dignity** *before* anything reaches the prompt — and in v1a, **don't persist screen observations durably at all.** A "semantic summary" is NOT safe by virtue of being a summary: the `DETAIL` field is where others' content smuggles in. And **"excluded" must mean never-looked** — gate before the camera, not after.

## 2. Scope

**v1a MUST-HAVES:**
1. **Sensitive-app PREFLIGHT exclusion (the headline catch)** — before `_capture_screenshot()` / the `:8081` probe / the vision call, check `active_window()` class/title against the configured exclusion set; if excluded → `state="excluded"` with **no capture, no probe, no vision call.** Hard exclusion (Decision 9), not capture-then-discard.
2. **New egress origin** `owner_screen_context` → added to `MINIMIZABLE_PRIVATE_CONTEXT`; screen-derived **prompt/context spans** tagged with it (so the now-enforcing door redacts them cloudward); escalate to `third_party_private_context` when third-party content is flagged.
3. **Third-party minimization BEFORE prompt** — conservative + fail-safe: flag `third_party_content_present=true` (vision-prompt `THIRD_PARTY` field + an app/title heuristic for message/email/call apps); **when uncertain → treat as third-party.** On the flag: minimize the `detail` reaching the prompt (owner-centric/minimized, or dropped), **never build a person-model**, origin → `third_party_private_context`.
4. **Pause primitive** — deterministic local switch checked at the top of `observe()`; paused → `state="paused"`, **no screenshot/probe/vision call**; no restart-only escape.
5. **NO durable screen storage in v1a** — **remove the unconditional storage path** (screen observations do NOT enter durable memory; `MAEZ_SCREEN_PERCEPTION=1` does NOT start a screen-memory ledger). Screen context is **ephemeral, in-cycle only.** (Curiosity-curated durable storage is v1b.)
6. **Default-off preserved** — `MAEZ_SCREEN_PERCEPTION` unset → `state="disabled"`; lands dormant; ADR 0009 holds.

**DEFERRED to v1b (§8):** the salience heuristic, decay-by-default retention, provenance labels for *durable* screen memories, "useful-to-development" tests, a review surface. **Deferred further:** Level 3 full retained observation; raw screenshot/OCR storage; full consent-record integration; natural-language pause UX; **video-call downgrade** (named hard follow-up — if a call/conference app is the active window, v1a treats it as excluded/sensitive via the preflight rather than claiming graceful downgrade).

## 3. The rails (mechanism)

**A. Preflight exclusion (before the camera).** At the top of `observe()` (after the disabled/pause checks, **before** `_capture_screenshot()`): call `active_window()` (cheap X11 class/title); if the class/title matches the configured exclusion set (finance/medical/messaging/credential/call apps) → return `ScreenObservation(state="excluded")` immediately — no screenshot, no `:8081` probe, no vision call. This is the only honest reading of "don't even look."

**B. Egress origin + tagging.** Add `owner_screen_context` to `MINIMIZABLE_PRIVATE_CONTEXT` (`core/egress/gate.py`); `decide_egress` already redacts that class and the door now enforces. Screen-derived spans entering the cycle prompt carry this origin (→ `third_party_private_context` on the third-party flag). **The closed door only protects screen content if screen content is tagged — this is the link to this morning's activation.**

**C. Third-party minimization (before prompt).** The write-time policy runs on the `ScreenObservation` *before* `format_for_context()` reaches the prompt: detect third-party content (vision `THIRD_PARTY` flag + app/title heuristic; uncertain → third-party); on flag, minimize/drop `detail`, set `third_party_content_present`, escalate origin, never persist a person-model. Provenance label `"seen on desktop"` (+ `"third_party_content_present"`).

**D. Pause primitive.** A deterministic switch (pause-state file/env/CLI) checked at the very top of `observe()`; paused → `state="paused"`, no capture/probe/call. Testable without a daemon.

**E. No durable storage.** Remove/disable the path that writes screen observations into durable daemon memory. v1a screen context is ephemeral (lives only in the current cycle's prompt). This is a *deletion of capability* for v1a (safer), re-introduced governed in v1b.

**F. Default-off.** Unchanged: unset `MAEZ_SCREEN_PERCEPTION` → `disabled`. Lands dormant.

## 4. States

`ScreenObservation.state`: `disabled` · `paused` · `excluded` · `unavailable` · `ok` · `error`. New fields: `third_party_content_present: bool`, `egress_origin_class: str`. **No state fabricates an observation** — `disabled`/`paused`/`excluded`/`unavailable` carry no `detail`.

## 5. Tests (v1a)

1. **Preflight-before-capture (HEADLINE):** with an excluded active-window class/title, `observe()` returns `state="excluded"` AND `_capture_screenshot` / the vision call are **never invoked** (assert the capture + vision functions are not called — spy/mock them). This is the "don't even look" proof.
2. **Third-party minimization before prompt:** a `DETAIL` describing others' content → `third_party_content_present=true`, the prompt-bound form is minimized (no person-name/private detail), origin = `third_party_private_context`; uncertain → third-party. No person-model written.
3. **Egress tagging:** screen-derived prompt spans carry `owner_screen_context`; `decide_egress` redacts them cloudward; third-party-flagged → `third_party_private_context`.
4. **Pause primitive:** paused → `state="paused"`, no screenshot/probe/vision call (assert paths not invoked).
5. **No durable storage:** after a successful `ok` observation, **nothing is written to durable memory** (assert the storage path is not called / no screen row persists). v1a is ephemeral-only.
6. **Default-off + honest blind:** unset → `disabled`; `disabled`/`paused`/`excluded`/`unavailable` carry no fabricated `detail`.
7. Full `discover` green; apples-to-apples in `/home/rohit/maez`.

## 6. Acceptance rules

1. Sensitive-app exclusion is a **preflight** (active-window class/title) **before** any capture/probe/vision — `excluded` means never-looked (test 1).
2. `owner_screen_context` added + screen prompt-spans tagged + door redacts; third-party → stricter origin (tests 2, 3).
3. Third-party minimization before prompt; never a person-model; uncertain→third-party (test 2).
4. Pause primitive deterministic, no capture/probe/call; no restart-only escape (test 4).
5. **No durable screen storage in v1a** — the unconditional storage path is removed; screen context is ephemeral (test 5).
6. Default-off preserved; lands dormant; honest blind states carry no detail (test 6).
7. Rehabilitates `screen_perception.py` + the daemon path — no parallel eye.
8. Full suite green, apples-to-apples. **`## Predicted effect`** on the impl commit.

## 7. Predicted effect

Lands **dormant** (default off). **When enabled** (`MAEZ_SCREEN_PERCEPTION=1`): Maez can *see and think with* governed Level-2 screen summaries — but (a) excluded apps are **never captured** (preflight), (b) third-party content is flagged + minimized before it reaches the prompt (never a person-model), (c) all screen-derived prompt content is tagged so the **now-enforcing door redacts it cloudward**, (d) a pause primitive closes the eye without a restart, and (e) **no durable screen memory is created** — screen context is ephemeral, in-cycle only. **Falsifiable:** with it enabled, an excluded app yields `excluded` with zero screenshots taken; a private message yields `third_party_content_present=true` + minimized prompt detail; a cloud call carrying screen context sends a redacted prompt; and no screen observation persists to memory.

## 8. v1b — Curiosity-curated durable screen memory (deferred, named)

The follow-on that re-introduces durable screen memory, governed: a **conservative-heuristic salience gate** (store durably only when the observation *meaningfully differs from the last* AND matches a small allowlist of developmental signals — project keyword / Maez-or-owner-context / surprising change — **a transparent rule, NOT an LLM "this felt important" judgment**); **decay-by-default** (durable is the promoted exception); **provenance labels** on durable screen memories; stronger "useful-to-development" tests; optionally a **review surface** for what was retained. v1b only makes sense after v1a proves the eye is safe to open for cognition.

## 9. Lane

Codex implements / Claude reviews. **Primary review anchors:** the **preflight-before-capture** (excluded = never-looked, capture/vision never invoked — the headline) + third-party minimization before prompt + egress tagging (screen content redacts at the door) + **no-durable-storage** (v1a writes nothing persistent). `.venv/bin/python -B -m unittest`; full `discover`; apples-to-apples in `/home/rohit/maez`. Owner runs the witness (enable the flag; confirm excluded apps aren't captured, third-party minimized, nothing persisted). **No restart in the slice; owner decides when to enable.**
