# Desktop Awareness v0 — The Honest Desktop Sense (dashboard-only) — Design

**Date:** 2026-06-05
**Status:** DRAFT for owner review → Codex implements / Claude reviews; owner runs the witness.
**Reuses:** `core/body/camera_presence_state.py` (the content-free body-sensor pattern to mirror); `core/memory/ambient.py` `active_window()` (the X11 active-app utility to graduate); `core/infra/body_capabilities.py` `desktop_session_reachable()` (the honest-availability probe); the `/health.body` organ dashboard + the "eyes" tile (`daemon/maez_daemon.py`, `ui/dashboard_local.html`) — the surface + tile pattern to mirror.

## 0. Why

This is the first real **embodiment** step after the privacy rails — Maez perceiving its body's environment, read-only, "rails before hands." The reuse-check found the plumbing exists but no honest organ: `active_window()` already pulls the active app via X11, but only **on-demand** (ambient context for direct questions) — it is **not** a sense organ (not on `/health.body`, not on the dashboard, not honestly-availability-gated). v0 graduates it into one.

**The governing scar (the spine):** the *Firefox-tabs incident* — "Maez offered `wmctrl`/`xdotool` despite neither being installed or reachable." A desktop sense must **perceive honestly or report itself blind — never fabricate or infer a window.** This ties straight to the owner's hard line on fabrication ([[feedback_no_fabrication]]).

## 1. The spine (owner's words)

> **v0 lets Maez know which room of the house you're in, not what paper you're reading on the desk.**

- **App class is proprioception:** "my owner is in Firefox / terminal / editor" — the *shape* of the body's current activity. Content-free.
- **The window title is content:** which tab, which file, which email, which conversation. Reading titles is reading the owner's work surface — out of scope, deserves its own consent + handling rail later.
- **Perceive honestly or report blind.** Never infer, never fabricate.

## 2. The invariants (owner's acceptance list — verbatim)

- `MAEZ_DESKTOP_PERCEPTION=0` **default → disabled**.
- enabled + reachable → **app class only**.
- enabled + unavailable → **honest blind reason**.
- **never infer.**
- **never fabricate.**
- **never store.**
- **never inject into cognition.**
- **no title in v0, even locally.**

**On "never store":** the only retention is an **ephemeral in-memory last-sample** (app class + sample timestamp) for the dashboard's age display — mirroring the "eyes" tile — content-free, lost on restart, **never persisted** (no memory store, no intake bus, no log of the app class, never a remembered fact). That is proprioception, not storage. If the title rail is ever added, that is a separate slice.

## 3. Scope

**In:** a content-free desktop body-sensor (`core/body/desktop_presence_state.py`, mirroring `camera_presence_state.py`); graduate `active_window()` to feed it **app class only**; honest-availability via `desktop_session_reachable()` + X11/Wayland/tools detection; a content-free `desktop` field on `/health.body` + a "Desktop" tile on the dashboard; the `MAEZ_DESKTOP_PERCEPTION` consent gate (default off).

**Out:** the window **title** (content-bearing — its own future slice); **cognition-injection** (Maez reasoning over the desktop state — the named follow-on); persistence / intake-bus / memory storage; running-apps / notifications / focused-file / clipboard (net-new sensing — later); **any action / write-side** (this is a sense, not a hand).

## 4. The mechanism

Mirror the camera-presence organ exactly:

1. **`core/body/desktop_presence_state.py`** — a content-free state module (sibling to `camera_presence_state.py`): holds the last-sample (`app_class: str | None`, `sampled_at`, `sensor_state`: `disabled|available|unavailable`, `reason` for unavailable). Pure/content-free; no titles, no content, no persistence.
2. **The sampler** (in the daemon's periodic body sampling, where the eyes tile samples ~60s): when `MAEZ_DESKTOP_PERCEPTION` is set, probe availability (`desktop_session_reachable()` + X11/Wayland + tools), then if available call `active_window()` and extract **`class` only** (discard `title`); update the in-memory state. Wrap in the existing `_safe()` so a sensor failure degrades to `unavailable`, never crashes the cycle.
3. **`/health.body.desktop`** — a content-free field: `{sensor_state, app_class | null, age_seconds | null, reason | null}`. When disabled → `{sensor_state: "disabled"}` (explicitly off, not blind).
4. **The "Desktop" tile** (`ui/dashboard_local.html`, mirroring the eyes tile): shows the app class + "seen Ns ago", or the honest blind-reason, or "disabled".

## 5. The states (the only four)

| Condition | `sensor_state` | shows |
|---|---|---|
| `MAEZ_DESKTOP_PERCEPTION` unset/0 | `disabled` | "disabled" (off, not blind) |
| enabled + session reachable + app read | `available` | app class + age |
| enabled + Wayland / tools missing / session unreachable | `unavailable` | honest blind reason (`wayland` / `tools_missing` / `session_unreachable`) |
| enabled + reachable but `active_window()` returned None | `unavailable` | `no_active_window` (honest — no fabrication) |

**Never a fifth state.** No inferred app, no remembered-last-when-now-blind (when blind, it says blind — it does not show a stale app as if current).

## 6. Tests

1. **Default-disabled:** env unset → `sensor_state="disabled"`, no sampling, no app class.
2. **Honest-availability matrix:** Wayland → `unavailable/wayland`; tools missing → `unavailable/tools_missing`; session unreachable → `unavailable/session_unreachable`; `active_window()`→None → `unavailable/no_active_window`. **Never an app class in any unavailable state** (never fabricate/infer).
3. **App-class-only / content-free:** with a stubbed `active_window()` returning `{title: "Re: confidential X — Gmail", class: "firefox"}`, the `/health.body.desktop` field contains `"firefox"` and **does NOT contain the title string** (no `"confidential"`, no `"Gmail"`). The headline content-free test.
4. **Never-store:** the app class is not written to any memory store / intake bus / log; only the ephemeral in-memory last-sample exists (assert no persistence call).
5. **Never-inject:** the desktop state does not appear in the cognition/prompt path (assert the reasoning-cycle prompt builder does not read it).
6. **Stale-when-blind:** a transition available→unavailable shows the blind reason, **not** the last app class (no stale-as-current).
7. **Tile render:** the dashboard renders each of the four states.
8. Full `discover` green; apples-to-apples in `/home/rohit/maez`.

## 7. Acceptance rules (the invariants)

1. Default `MAEZ_DESKTOP_PERCEPTION=0` → `disabled`; zero sampling, zero live change by default (lands **dormant**).
2. Enabled + reachable → **app class only**; the window title never appears in the field, the tile, a log, or memory — even locally (test 3).
3. Enabled + unavailable → an **honest blind reason**; **never an inferred/fabricated/stale app** (tests 2, 6).
4. **Never store** (no persistence/intake/log of the app class), **never inject into cognition** (tests 4, 5) — v0 is dashboard-only proprioception.
5. Read-only sense; **no action / write-side** capability added.
6. Content-free `/health.body.desktop` + a dashboard tile mirroring the eyes tile.
7. Full suite green, apples-to-apples.

## 8. Predicted effect

Lands **dormant** (default `MAEZ_DESKTOP_PERCEPTION=0` → no live change; mirrors the enforcement-flip default-shadow pattern). **When the owner enables it** (`MAEZ_DESKTOP_PERCEPTION=1`): the daemon periodically samples the **active app class** (content-free — never the title), and `/health.body.desktop` + the dashboard "Desktop" tile show "owner is in `<app class>`, seen N s ago" — or an honest blind reason on Wayland/missing-tools/unreachable-session. No cognition change (Maez does not yet reason over it), no memory written, no titles. **Falsifiable:** with it enabled on this X11 box, the tile shows the real active app's class and never its title; on a forced Wayland/no-tools condition it shows blind, never a fabricated app.

## 9. Lane

Codex implements / Claude reviews. **Primary review anchors:** the honest-availability matrix (never fabricate/infer/stale-as-current — the Firefox-tabs scar) + the content-free/no-title test + never-store/never-inject. `.venv/bin/python -B -m unittest`; full `discover`; apples-to-apples in `/home/rohit/maez`. Owner runs the witness (enable the flag, read the tile). **No restart in the slice itself** (owner decides when to enable + sample live).
