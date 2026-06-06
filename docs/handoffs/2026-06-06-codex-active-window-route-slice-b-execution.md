# Handoff → Codex: execute Active-Window Route v0 (Full Lens — Slice B)

**From:** Claude (covenant/review lane) · **To:** Codex (implementation lane) · **Date:** 2026-06-06
**Relayed by:** Rohit (owner). Two-team switchboard: Codex implements, Claude reviews.

## READ THIS FIRST

- This is the **read-only active-window nerve** — it lets the preflight tell a sensitive window from an ordinary one. It is **NOT** more capture, **NOT** durable memory.
- **Install NOTHING.** The GNOME extension runs *inside `gnome-shell`* (compositor-privileged). It is **owner-audited + owner-installed/enabled** (Task 1 / Rail 1). Codex writes the integration code (which lands dormant-on-capability) and installs/enables nothing.
- The window **title** is **decide-only** — it reaches the exclusion gate and *nowhere else*. This is enforced by a **surface split** (below); getting it wrong leaks raw window titles into the prompt and the web UI.
- Completing this reaches **sight** (`observe()` can finally see ordinary windows) → **v1b unblocks** — but **do not build v1b** (no durable screen memory in this slice).
- The live sight witness (Task 9) is **owner-run** (needs the audited extension enabled).

## Documents

- **Plan (execute task-by-task):** `docs/superpowers/plans/2026-06-06-active-window-route-slice-b.md` — 10 TDD tasks, complete code.
- **Spec:** `docs/superpowers/specs/2026-06-06-active-window-route-slice-b-design.md`.

## The route (decided)

**Focused Window D-Bus** (`flexagoon/focused-window-dbus`), pinned `5ff336fac73b34deaf83f32772e8478885fa4925`. Read-only (`Get` + `FocusChanged`). Chosen over **Window Calls** on covenant grounds: Window Calls carries move/resize/close — **a sense must not carry a hand.** Do not switch routes.

## The surface split (the load-bearing correction — get this exactly right)

A live-code review caught that `core/memory/ambient.py::ambient_context()` → `ambient_format.py:148` renders `Active desktop window: {title} ({class})` into the **cycle prompt and web UI**. That path is inert on Wayland today (active_window→None) but this slice makes it live — and it **already leaks on X11**. So:

- **`active_window()`** (general consumers — ambient/dashboard/web) → **CLASS-ONLY** (`{"class": …}`, no title).
- **`active_window_for_preflight()`** (NEW) → full `{title, class}`, called **only** by `_is_excluded_active_window()`.
- **`ambient_format.py:148`** → render **class-only**.
- One raw read (`_raw_active_window`) feeds both surfaces.

**Headline regression test (must pass):** focused title `"Re: confidential salary — Gmail"` → preflight *excludes* on it, **and** the formatted ambient output contains none of `confidential`/`salary`/`Gmail`.

## Hard constraints (owner-set; violating them fails review)

- **No install/enable** of the extension by Codex (Rail 1). Audit-and-pin is Task 1.
- **Read-only** — no code path invokes any window-manipulation method (Rail 2).
- **Title decide-only via the surface split** (Rail 3) — never persisted/injected/egressed.
- **Parser** handles the `gdbus` **tuple-wrapped JSON string** (`('{...}',)`) + raw JSON; **discards** `moveable`/`resizeable`/`canclose`/unknown keys.
- **Fail-safe preserved** (Rail 5) — broken/absent/`{}`/error → `None` → preflight `excluded` → no capture.
- **`observe()` byte-unchanged** — only the preflight's *read source* + the exclusion set change; the gate order is untouched. Lens v0 / v1a / gate / screencast suites stay green.
- **No v1b** (Rail 7). **`unittest`, not pytest.** Full `discover` in `/home/rohit/maez`. **`## Predicted effect`** on behavior-affecting commits.

## Claude's review anchors

1. **Surface split is real** — `active_window()` class-only, `active_window_for_preflight()` title-bearing; the title-leak regression passes. I'll mutation-check (e.g. revert ambient to render title → the regression must go RED).
2. **Title never reaches prompt/memory/egress** — grep the diff for any other `active_window()` consumer that could surface the title.
3. **Read-only** — no actuation method anywhere; the audit (Task 1) confirms the extension exposes none.
4. **Fail-safe** — broken/absent nerve → blind-safe; I'll mutation-check the `None→excluded` guard still has teeth.
5. **`observe()` byte-unchanged** — gate order intact; sight reached only via a real preflight pass.
6. **Exclusion set** — sensitive cases excluded, ordinary cases pass; owner-extensible intact.
7. **Parser** — tuple-wrap + field discard; malformed → None.

## Owner-only

Task 1 audit sign-off + the extension install/enable + the Task 9 sight witness. The audit record (`docs/handoffs/2026-06-06-focused-window-dbus-audit.md`) should be filled against the pinned commit before enable.

## Current live state (don't disturb)

main `59dd585`, local-only (NO push). Daemon `2230316` untouched; redact enforcing; screen flag off-disk; ScreenCast restore token resting `0600` behind an absent curtain. `memory/db` is the crown jewel — witness against copies. The extension install + sight witness stay the owner's breath.
