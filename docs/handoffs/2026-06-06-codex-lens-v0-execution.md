# Handoff → Codex: execute Desktop Perception Lens v0

**From:** Claude (covenant/review lane) · **To:** Codex (implementation lane) · **Date:** 2026-06-06
**Relayed by:** Rohit (owner). Two-team switchboard: Codex implements, Claude reviews.

## What you're building

Give the **already-governed** screen eye a working **no-prompt** capture path on this **GNOME Wayland** body, behind a **fail-SAFE** preflight, and prove it (or honestly report blind) end-to-end on the real session.

This is **substrate sight, NOT more governance.** v1a's governance held (18/18). Do not re-litigate the rails — slot into the `preflight` and `capture` steps only; the gate order stays `pause → enabled → preflight → probe → capture → vision → govern`.

## Documents (read both before starting)

- **Plan (execute this task-by-task):** `docs/superpowers/plans/2026-06-06-desktop-perception-lens-v0.md` — 9 TDD tasks, complete code.
- **Spec (the why + the constraints):** `docs/superpowers/specs/2026-06-06-desktop-perception-lens-v0-design.md`.

## The two findings the slice is built on (verified 2026-06-06, don't re-derive)

1. **The preflight fails OPEN today.** `skills/screen_perception.py:_is_excluded_active_window()` returns `False` when `active_window()` is falsy, and GNOME Wayland returns `None` → it would capture unidentifiable windows. **Task 2 inverts this to fail-SAFE** (undetermined → excluded). This is the safety floor and lands first.
2. **No capture tool exists + the stack is X11-only.** `scrot`/`gnome-screenshot`/`import`/`grim`/`spectacle`/`maim` all absent; GNOME Shell 50.1 Wayland. The lens must add a session-aware no-prompt route (Tasks 3–5) and an empirical probe (Task 8) that decides the outcome.

## Hard constraints (these are owner-set; violating them fails review)

- **No per-capture permission prompt.** A route that prompts on every capture is disqualified → eye reports `unavailable`. (A one-time grant is acceptable ONLY if no-prompt afterward.)
- **Install NOTHING autonomously** — no `apt`, no GNOME extension enable. If a package/extension is needed, **stop and report** it as the next owner-authorized slice (spec §6).
- **No durable screenshot.** Capture to temp only, always cleaned up (Task 6). v1a's no-durable-storage invariant must survive.
- **Content-free everywhere.** The probe (Task 8) and any witness report route names / booleans / byte-sizes / states — **never screen content**.
- **Test runner is `unittest`, not pytest:** `.venv/bin/python -B -m unittest …`. Full `discover` before done, in `/home/rohit/maez` (apples-to-apples — the worktree floor is confounded by missing owner-local assets).
- **`## Predicted effect`** on behavior-affecting commits (Tasks 2, 8 have them in the plan); docs/test-only commits don't.

## Two honest outcomes — name which one you reached (do NOT conflate)

- **Full Lens v0 (sight):** active-window read works AND a no-prompt capture works → ordinary window blinks `ok`. **Only this unblocks v1b.**
- **Safety-floor Lens v0 (safe closed eyelid, NOT sight):** either missing → honest `excluded`/`unavailable`. A **real win** (closes the fail-open hole) — but it must be labeled blind/safe, never "ready to see/remember," and it does **not** unblock v1b.

**Expected outcome is likely Safety-floor** (GNOME 50.1 `Shell.Screenshot` is probably restricted to external callers; no installed no-prompt active-window route; `Shell.Eval` locked). That is a **valid, expected result, not a failure** — land the fail-safe + probes + honest blind, name the next slice, stop.

## Claude's review anchors (what I'll scrutinize hardest)

1. **Task 2 — the fail-safe inversion is real and has teeth.** `active_window()==None → excluded`, `_capture_screenshot` never invoked. I'll mutation-check it. Any v1a test that changed must be a *documented, deliberate* consequence of the inversion — never green-by-weakening.
2. **No working lens outruns the preflight.** Capture is reachable only *after* a functioning exclusion check. A Full outcome must prove exclusion *with a working lens* (real, not just mocked).
3. **No blind-but-safe outcome mislabeled as sight.** The probe/witness wording and the canon note must call a Safety-floor result blind/safe, not v1b-ready.
4. **No autonomous install/enable** anywhere in the diff.
5. **Temp-only + cleanup** survives the Task-3 capture refactor (the `finally: unlink` must wrap the whole candidate loop).

## Owner-only steps (neither lane can take these)

- **Task 8 Step 2** — run `scripts/lens_probe.py` on the **live graphical session** (the daemon holds session capture authority; a detached shell is blind — proven this morning).
- **Task 8 Step 3** — the Full witness (enable `MAEZ_SCREEN_PERCEPTION=1` + restart), if the probe reached Full.
- The **merge** of the finished branch is owner-delegable to Claude; the **enable+restart activation breath stays the owner's.**

## Current live state (don't disturb)

Daemon `2230316`, redact enforcing, screen flag reverted on-disk (eye returns to `disabled` on the next restart; enabled-but-blind/fails-safe until then). `memory/db` is the crown jewel — witness against copies, never open it concurrently with the daemon.
