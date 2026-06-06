# Handoff → Codex: execute ScreenCast Capture + Privacy Curtain v0 (Full Lens — Slice A)

**From:** Claude (covenant/review lane) · **To:** Codex (implementation lane) · **Date:** 2026-06-06
**Relayed by:** Rohit (owner). Two-team switchboard: Codex implements, Claude reviews.

## READ THIS FIRST — what this slice is NOT

- This is **Slice A / the capture half ONLY.**
- It does **NOT** make `observe()` see — `observe()` stays byte-unchanged and fail-safe-blind.
- It does **NOT** unblock v1b.
- It must **NOT install anything** — system python3 already has `gi`/`Gst`/`Gio`; the venv shells out to it.
- The **only escalation is Rohit's one-time ScreenCast grant** (`restore_token`).
- The **live portal/Gst capture path is owner-witnessed**, not unit-tested; unit tests cover everything around it.

If you find yourself making the eye *see ordinary windows through `observe()`*, building durable screen memory, installing a package/extension, or adding a per-capture prompt — **stop, you've left Slice A.**

## What you're building

A standalone `scripts/screencast_capture.py` (runs on **system `/usr/bin/python3`**) that returns **one frame** from a governed ScreenCast stream (grant-once / `restore_token`), sampled on demand, temp-only, discarded after read — plus a **privacy curtain** (soft = look away / keep token; hard = withdraw the eye / revoke token) that **truly stops capture**. The daemon (`skills/screen_perception.py`) shells to it as a new `screencast` capture candidate.

## Documents (read both)

- **Plan (execute task-by-task):** `docs/superpowers/plans/2026-06-06-screencast-capture-privacy-curtain-v0.md` — 10 TDD tasks, complete code for the testable parts.
- **Spec (the why + rails):** `docs/superpowers/specs/2026-06-06-screencast-capture-privacy-curtain-v0-design.md`.

## Hard constraints (owner-set; violating them fails review)

- **Helper MUST import under the maez venv without `gi`.** `gi`/`Gst`/`Gio` imports are **lazy** — inside the live functions only, never at module top. This is the first place you could accidentally make the whole suite environment-dependent. Test 1/T1 asserts it.
- **No per-capture permission prompt.** After the one-time grant, `restore_token` must restore no-prompt — or the helper honestly reports it (`needs_grant` / re-prompt finding), never fakes a frame.
- **Install NOTHING** — no `apt`, no pip, no GNOME extension. System python3 has the bindings.
- **Token is a `0600` capability secret** — `~/.config/maez/screencast_restore_token`, never logged, never in stdout JSON, never in prompt/cognition/audit/telemetry.
- **Helper output is content-free** — JSON contract only (`status` ∈ {ok, needs_grant, curtain_drawn, capture_failed} + temp_path, bytes, duration_ms, error_class). **Never screen content, never a traceback or raw portal error, never the token.** Every exit path (including unexpected exceptions) emits the contract with a **stage** name (`portal`/`pipewire`/`gst`/`timeout`/`permission_denied`).
- **No durable frame archive** — temp-only; helper deletes its temp on failure, daemon deletes after read on success (after path validation: existing regular file, system temp dir, `maez-screencast-` prefix; reject symlink/foreign/missing).
- **Latency measured, reported honestly** — `duration_ms`; "works but too slow for cycle use" is a valid verdict, never smuggled.
- **`observe()` byte-unchanged** — the screencast candidate is reached only via the direct capture path; the fail-safe preflight still excludes unknown windows in the full `observe()` flow. Lens v0 / v1a / gate suites must stay green.
- **Test runner is `unittest`, not pytest:** `.venv/bin/python -B -m unittest …`. Full `discover` in `/home/rohit/maez` (apples-to-apples — worktree floor is confounded by missing owner-local assets).
- **`## Predicted effect`** on behavior-affecting commits (T6, T7 carry them in the plan).

## Owner-witnessed (neither lane can run these — T9)

The live portal+PipeWire+Gst path needs the session's capture authority + an interactive grant. **Rohit runs T9** in the graphical session: first grant → no-prompt restore → vision ok → soft curtain stops capture → hard revoke forces re-grant → latency verdict. Claude reads the content-free result. Implement T6 to the interface contract; do **not** claim it works from a headless shell.

## Claude's review anchors (what I'll scrutinize hardest)

1. **Helper importable in the venv without `gi`** (lazy imports) — I'll import it under the venv and assert no `gi` at module top.
2. **Token never leaks** — `0600`, absent from stdout/logs/prompt; I'll grep the diff and mutation-check.
3. **Helper output content-free, no traceback** — I'll inject a raising mock and assert the raw text/handle never reaches stdout; only a stage name does.
4. **`observe()` byte-unchanged** — capture-half boundary; Lens v0/v1a/gate green; not claimed as sight.
5. **Path validation has teeth** — foreign/symlink/missing/out-of-dir paths rejected and not read.
6. **Temp ownership clean** — helper-on-failure, daemon-on-success; no orphans.
7. **Curtain actually tears down capture** — not a downstream mask; soft keeps the token, hard revokes it.

## Current live state (don't disturb)

main `075d908`, local-only (NO push). Daemon `2230316`, redact enforcing, screen flag reverted on-disk (eye returns to `disabled` on next restart). `memory/db` is the crown jewel — witness against copies, never open it concurrently with the daemon. The grant ceremony + any restart stay the owner's breath.
