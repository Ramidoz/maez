# Desktop Attention-Shadow v0 — Design & Covenant Brief

**Date:** 2026-06-29. **Lane:** Claude drafts + covenant-reviews; Codex co-designs/builds; owner signs the field table + witnesses. **Status:** DESIGN — approved in brainstorm; no build until the field table is signed. **Parent:** the Real-Eyes arc (the silence lever), first slice.

## What this honestly is (and is not)
The body-state window proved machine vitals are *thin* — Maez shrugged at its own CPU/process changes. The hypothesis: the **owner's world** is the provoking signal. This slice takes the smallest honest step toward that — and names itself precisely so its result can't be misread.

**It is a *desktop attention* shadow, not presence and not eyes.** Maez senses *that Rohit's active computer surface changed* — never *to what*, and **not** whether Rohit is physically there. It answers exactly one narrow question: *does Maez respond differently when it can feel that Rohit's attention moved on the machine?*

**It is NOT** presence ("came back / stepped away" — needs idle/camera), NOT vision, NOT voice, NOT the screen. Real presence and voice are the **Jetson-mediated arc** ([[project_jetson_mediated_perception_architecture]]): raw camera/mic stay on a Jetson edge body, only tiny content-light labels cross, and perception is offloaded off the main GPU. That is deferred to its own slices.

## The governing law
**The shadow of attention moving, never the name of what it moved to.** Maez may feel *"Rohit's active surface changed."* It may never receive the app class, a category of the app, a direction, the screen, or anything about *what* Rohit is doing. A content-free change signal into the quiet loop — not a window into the work.

## What exists (verified 2026-06-29)
- **The raw perception works on this Wayland machine.** `core.memory.ambient.active_window()` returns the active window class via the Wayland dbus path — confirmed live: `{"class": "code"}`. `_session_is_wayland()` → `True`.
- **The sensor wrapper currently gates it out.** `core/body/desktop_presence_state.py::sample_desktop_presence` returns `DesktopPresenceState(sensor_state, app_class, reason, sampled_at)`, but `_desktop_availability()` **hard-requires `xdotool`** (an X11 tool) — which is **absent** here — so it returns `unavailable / tools_missing` even though the Wayland dbus path works. It is also disabled by default (`MAEZ_DESKTOP_PERCEPTION` unset). This xdotool hard-gate is effectively a bug on Wayland.
- **No idle/presence detection exists** anywhere in `core/body/`; `xprintidle`/`xssstate` are absent; Wayland idle is compositor-specific. So present/absent is genuinely unavailable without the Jetson/camera arc.
- **The idle heartbeat does not receive desktop signal.** `build_lean_idle_prompt` ([core/cognition/lean_idle_heartbeat.py](../../../core/cognition/lean_idle_heartbeat.py)) assembles `body_state` + `body_state_window` (the body-window) only. Adding the attention shadow is additive, same wiring pattern as the body-window.

## Architecture (three pieces)
1. **Wayland sensor fix (precondition).** Make `desktop_presence_state` availability **Wayland-aware**: available when the active-window path actually returns a window (the dbus path on Wayland, `xdotool` on X11), rather than hard-gated on an X11 binary. Reuse `ambient`'s existing Wayland path; do not add new perception. This makes the sensor return real `app_class` on this machine. (Honest scope: tiny, but non-zero — the raw perception works; the wrapper needs this fix.)
2. **Attention-shadow window module (new).** Reuses the body-window's content-light/salt/cold-start primitives. Computes a **salted-hash signature of `app_class`**, compares beat-to-beat, and emits a **directionless** `"active surface changed"` delta plus a sensor-availability label. Persists only the salted signature to its **own transient runtime cache** — **`~/.local/state/maez/desktop_attention_shadow_signatures.json`**, schema `desktop_attention_shadow.v0` — **distinct from the body-window's `world_window_signatures.json`** (never reuse or share it). Not under `memory/`. Cold-start is baseline-only (records signature, emits nothing).
3. **Heartbeat wiring.** Behind `MAEZ_DESKTOP_ATTENTION_SHADOW` (default off), the daemon computes the shadow and passes it into `build_lean_idle_prompt` as its **own distinct fact key `desktop_attention_shadow`**, rendered as its **own block `DESKTOP ATTENTION SHADOW`** — **never** piggybacking on the body-window's `body_state_window` key / `BODY-STATE WINDOW` block (a shared seam would muddy the witness: attention must never read as body-state). Flag-off → no block, **byte-identical**, no cache created.

**Flag & sensor-gate interaction (pin in Task 0).** `MAEZ_DESKTOP_ATTENTION_SHADOW` is the **single gate** for this slice. When on, the shadow samples the Wayland-fixed active-window path *for its own use*. Task 0 must pin **how**: either it drives `sample_desktop_presence` with the perception env passed locally, or it reads the fixed availability + `ambient` path directly — but it must **not silently flip the broader `MAEZ_DESKTOP_PERCEPTION` sense** for other consumers (dream-state, etc.). The Wayland availability fix itself is behavior-neutral while everything stays disabled by default; only this slice's flag activates sampling. Flag off → nothing sampled, byte-identical.

## The field table (the slice IS this table — owner sign-off gate)

| field | source | class | projection | prompt phrase |
|---|---|---|---|---|
| active surface (`app_class`) | desktop sensor (Wayland-fixed) | `sensitive_delta` | **salted-hash change only** — never the value, never a category, never a direction | `"active surface changed"` |
| desktop sensor state | `sensor_state` | safe label | `available` / `unavailable` / `disabled` | `"desktop attention sense unavailable"` (when not available) |

## The salt — honest threat model (owner tightening)
The salted hash is **not** host-level secrecy. App classes are a small universe; anyone with local filesystem access plus the salt/cache could still reason about which class a signature represents. We do **not** claim the hash is irreversible.

**The honest, sufficient claim:** *Maez never receives the raw app class.* The prompt, memory, and any Maez-facing receipt/log get **only** the content-light change signal (`"active surface changed"`). The salt serves **Maez-facing privacy and cache hygiene** — keeping the raw class out of Maez's experience and out of casual cache reads — **not** host-level confidentiality. (Host-level confidentiality of what app is focused is out of scope; that's an OS-trust question, not this slice's.)

## Safety invariants
- **Raw `app_class` never reaches the prompt, never enters Maez memory stores / private stores, and never enters any Maez-facing receipt/log.** The **only** place it leaves a trace is the salted signature in the transient runtime cache (intentional, for beat-to-beat comparison) — the runtime cache is *not* a Maez memory store, so allowing the salted signature there does not contradict the "never enters memory" rule.
- **Directionless.** "active surface changed" — never which app, never a category bucket (the owner's C-not-B decision: no taste mapping of Rohit's life).
- **Cold-start emits nothing** (records signature, no delta).
- **Unavailable/disabled → honest label, no deltas.** Blind beats stale; can't see → say so. Honest-emptiness preserved (`HEARTBEAT_OK` line unchanged).
- **No command path.** Read-only signal into the prompt; no tool, search, action, message, soul, or memory write. AST-asserted, like the body-window.
- **Flag-off byte-identical**, default off, no cache created when off.

## Tests (load-bearing)
**The absence rule (owner-specified) — plant and prove:** plant a raw class value (e.g. `signal`, `code`) and assert it is:
- **absent from the prompt**,
- **absent from Maez memory stores / private stores**,
- **absent from any Maez-facing receipt/log**,
- present **only** as a salted signature in the transient runtime cache (the one intentionally-allowed location — and *not* a Maez memory store).

Plus the structural guards (mirroring the body-window suite):
- **Shadow fires on change:** a changed `app_class` between beats yields exactly one `"active surface changed"` delta; an unchanged class yields none.
- **Directionless:** the rendered phrase contains no app name, no category, no "to/from".
- **Cold-start baseline-only:** first beat / post-restart with no prior signature emits zero deltas (records the signature).
- **Unavailable handling:** `sensor_state != available` → the availability label, no surface delta.
- **No command path:** the module imports no tool/search/action/soul/memory writer (AST-asserted).
- **Flag-off byte-identical:** prompt is byte-for-byte the pre-slice prompt; no cache file created.
- **Wayland sensor fix (HERMETIC):** the availability logic is tested with **mocked** Wayland/dbus reachability — available when the (mocked) active-window path returns a window, unavailable when it doesn't — so the suite never depends on the live desktop session. A real `xdotool`-present X11 path and a Wayland-dbus path are both asserted via mocks.
- **Live witness (SEPARATE, post-merge — not a suite test):** after merge, confirm once on the real machine that the fixed sensor returns a real `app_class` (proves the precondition, no ghost). This is a witness, never a unit/integration test.

## Covenant compliance
- **Perception free, door disciplined** ([[feedback_perception_free_egress_disciplined]]) — Maez may feel its world's *change*; the raw content stays behind the curtain, and "what changed to" never crosses.
- **No hidden taste** — the C-not-B decision: no app→category mapping that would teach Maez our buckets of Rohit's life ([[feedback_owner_chose_equality_not_privilege]] applies in spirit — no projecting our read of the owner onto Maez).
- **Understand at the ears, rails at the hands** ([[feedback_understanding_at_ears_rails_at_hands]]) — attention signal informs the quiet loop; it never becomes a command.
- **Honest naming** ([[feedback_witnessable_receipt_for_prompt_boundary]] spirit) — called *attention*, not presence; a quiet result means *attention-shadow alone is thin*, **not** "Rohit's world doesn't stir Maez." The real presence organ is the deferred Jetson arc.

## Out of scope (named)
Present/absent + idle detection; camera; mic/voice; raw screen; screen text; app name; app categories; direction of focus change; git (a ghost — no source exists); connectors; vision. All → Real-Presence v1 (Jetson) / Voice-sense, each with its own consent boundary.

## Predicted effect
With the shadow flag on, Maez's idle heartbeat begins receiving a content-light, directionless signal that *Rohit's active computer surface changed* — never the app, never a category, never whether Rohit is physically present. The raw class never enters Maez's prompt, memory, or receipts; only a salted signature sits in a transient runtime cache. Nothing is acted on; `HEARTBEAT_OK` stays valid. This does **not** give Maez presence, voice, or sight. If Maez stays quiet, the honest conclusion is "attention-shadow alone is thin" — pointing at the Jetson-mediated presence/voice arc as the next signal — not "the owner's world doesn't stir Maez."
