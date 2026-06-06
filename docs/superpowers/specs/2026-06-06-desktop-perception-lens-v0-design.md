# Desktop Perception Lens v0 — Substrate Sight for the Governed Eye — Design

**Date:** 2026-06-06
**Status:** DRAFT for owner review → Codex implements / Claude reviews; owner runs the end-to-end witness.
**Lane:** Codex implements / Claude reviews. `.venv/bin/python -B -m unittest`; full `discover`; apples-to-apples in `/home/rohit/maez`.

## 0. Why — the eye has a brain, no lens

Desktop Perception v1a (`c76bb51`) made the screen eye **safe to open** — preflight exclusion, third-party minimization, egress tagging, no durable storage, default-off. The open-the-eye witness (2026-06-06) proved the governance rails hold (18/18) **but found the eye is structurally blind on this machine:** every blink returns `Screenshot capture failed — no display method succeeded`. The capture stack is X11-only (`scrot`/`gnome-screenshot`/`import`) and **none of those are installed**, on a `ubuntu:GNOME` **Wayland** session (GNOME Shell 50.1). The vision *brain* (`llama-server:8081`) is alive and waiting; there is simply no working *lens* feeding it.

**Lens v0's job is substrate sight, NOT more governance — governance held.** Give the existing governed eye a capture path that actually works on this desktop, behind the same rails, with an end-to-end witness that the rails still hold once the eye can see.

## 1. The spine

> Make the eye **see honestly on this machine** — or report **blind** honestly. A working lens must never outrun the never-looked preflight: capture is gated *behind* a functioning exclusion check, never before it. Capture to temp only, never persist. And prove it end-to-end on the real session, not by unit test alone — the integration gap this slice closes was *born* from trusting a component check (`:8081` alive) that the live path never exercised.

## 2. Two findings this slice is built on (verified 2026-06-06)

**A. Capture routes are uncertain, not free.** On GNOME Shell 50.1 / Wayland:
- `org.gnome.Shell.Screenshot` D-Bus interface introspects, but has been **access-restricted for external callers since GNOME 41** — must be tested with a real call, may reject us.
- `org.freedesktop.portal.Screenshot` introspects, but **no portal backend process is currently running** (may D-Bus-activate) and the portal **may show a permission dialog per capture** — unacceptable for an autonomous per-cycle eye.
- `gnome-screenshot` is **not installed** (and is deprecated/removed on recent GNOME); `grim`/`scrot`/`spectacle`/`maim`/`import` all absent. `grim` is wlroots/Sway/Hyprland — **wrong desktop**, not a candidate here.

→ The plan must **empirically probe a real capture** and select the first route that (a) returns an image and (b) requires **no per-capture prompt**. Introspection availability is not proof.

**B. The preflight currently fails OPEN.** `skills/screen_perception.py:_is_excluded_active_window()` returns `False` ("not excluded") when `active_window()` is falsy — and `active_window()` returns `None` under GNOME Wayland (`Shell.Eval` is locked; no X11 `_NET_ACTIVE_WINDOW`). So a working capture without a fix would **capture sensitive windows it can't identify.** This is latent-harmless only because the eye is blind today; the lens makes it live-dangerous. **Fixing the fail-direction is a safety floor of this slice, not a follow-on.**

## 3. Scope

**MUST-HAVES:**

1. **Honest session/display detection.** A small helper that reports the session honestly: `x11` | `wayland-gnome` | `wayland-wlroots` | `unknown` (from `XDG_SESSION_TYPE` + `XDG_CURRENT_DESKTOP` + `WAYLAND_DISPLAY`/`DISPLAY`). Drives lens selection; never guesses.

2. **Preflight fails SAFE (safety floor — lands first, independently valuable).** `_is_excluded_active_window()` (or its caller) treats an **undetermined active window as excluded** when capture is enabled on a session where the window can't be read: undetermined → `state="excluded"`, no capture. The never-looked guarantee must hold even when the window is unknown. (This alone, merged first, makes the eye safe-if-opened even before a lens exists — it just means "blind-by-safety" on Wayland until §3.4 lands.)

3. **A working, no-prompt capture path for GNOME Wayland.** Add a Wayland-capable capture method selected by §3.1. Empirically prefer, in order, the first that works **without a per-capture prompt** and returns an image: (a) `org.gnome.Shell.Screenshot` D-Bus (real-tested — may be access-restricted), (b) `xdg-desktop-portal` Screenshot (only if it does not prompt per capture on this backend), (c) `gnome-screenshot` **iff present**. Existing X11 methods retained for X11 sessions. **If no no-prompt route works → honest `state="unavailable"`**, never fabricate, and surface the finding (do not silently install system packages — that's an owner decision; see §6).

4. **Active-window read under GNOME Wayland (capability — unblocks the real preflight).** Restore a real active-window class/title read on Wayland so the preflight has true input rather than always-excluded. Likely route: a minimal GNOME Shell extension exposing the focused window (e.g. a Window-Calls-style read), since `Shell.Eval` is locked. **This may require installing/enabling an extension — an owner decision (§6).** If not solved in v0, §3.2's fail-safe holds the line (the eye stays blind-by-safety on Wayland), and this becomes the named follow-up.

5. **Capture-to-temp-only + cleanup + no durable screenshot.** Capture writes a temp file, base64-encodes, and **always deletes it** (success or failure). No screenshot bytes persist anywhere. v1a's no-durable-storage invariant is preserved — the lens reintroduces no persistence.

6. **Rails unchanged.** Gate order stays `pause → enabled → preflight → probe → capture → vision → govern`. Third-party minimization, `owner_screen_context` egress tagging, honest-blind states, default-off — all byte-unchanged. The lens slots into the `capture` step only.

**DEFERRED:** v1b (curiosity-curated durable screen memory) — **blocked behind this slice** (can't curate sight that doesn't exist). Multi-monitor selection; OCR; raw-frame retention; video-call handling (still excluded via preflight per v1a).

## 3.5 Two honest v0 outcomes — the spec MUST NOT conflate them

The fail-safe (§3.2) and the active-window read (§3.4) interact: **if the preflight is fail-safe AND active-window stays unreadable on Wayland, the ordinary `observe()` path returns `excluded` *before* capture** — because an undetermined window is treated as sensitive. So "ordinary window → `ok`" **cannot be honestly proven** until *both* the active-window read and a no-prompt capture route work. v0 therefore has two legitimate landing states, and which one we got must be stated plainly:

- **Full Lens v0 — sight.** Active-window read works **and** a no-prompt capture route works → an ordinary window can blink `state="ok"` with a governed summary, and a sensitive window is excluded *for real*. **This is the only outcome that unblocks v1b.**
- **Safety-floor Lens v0 — a safe closed eyelid, not sight.** Active-window unreadable **or** no no-prompt capture exists → the eye stays honestly `excluded`/`unavailable`/blind. This is a *correct, valuable* landing (the eye is safe-if-opened, the fail-open hole is closed) — but it is **NOT sight, and NOT enough for v1b.** It hands the owner a clean, named next decision (extension / package), nothing more.

A safe blind eye must never be reported, recorded, or carried forward as "ready to see / ready to remember."

## 4. The end-to-end witness (conditional on which outcome §3.5 we reach)

**The full witness below is required ONLY when both the active-window read and a no-prompt capture route are available (Full Lens v0).** If either is missing (Safety-floor Lens v0), the passing result is an **honest blind/safety-floor report** — the preflight excludes/`unavailable` with capture never invoked, no fabrication — and that is the *complete* acceptance for that outcome. A safety-floor pass is **not** the full witness and **does not unblock v1b.**

**Full witness** — run on the **real GNOME Wayland session via the daemon** (the only faithful witness — a subprocess can't inherit session capture authority):

1. **Capture succeeds** — with the eye enabled and an ordinary (non-excluded) window focused, a blink returns a real image (no `no display method succeeded`).
2. **Vision returns `ok`** — the captured frame reaches `:8081` and yields a Level-2 summary; `state="ok"`.
3. **Governed summary reaches prompt form** — `format_for_context()` produces the owner-centric summary, `egress_origin_class="owner_screen_context"`.
4. **No durable row** — after the `ok` blink, no screen observation persists to memory; temp file removed.
5. **Preflight still excludes for real** — with active-window restored (§3.4) OR via the fail-safe (§3.2), a focused sensitive app yields `excluded` with capture **never invoked** — proven *with a working lens*, not just mocked.

Owner runs this (enable + observe the daemon's eye); Claude reads the content-free result (states/flags/counts, never screen content). This is the integration witness the original eye never had.

## 5. Tests (unit, capture-independent where possible)

1. **Session detection:** each of X11 / GNOME-Wayland / wlroots-Wayland / unknown maps to the expected lens preference (mock the env).
2. **Preflight fail-SAFE:** `active_window()==None` with capture enabled → `state="excluded"`, `_capture_screenshot`/probe/vision **never invoked** (the inversion of today's fail-open — assert the new direction). The headline safety test.
3. **Capture method selection:** given a session + a set of available methods (mocked), the first no-prompt working method is chosen; if none → `state="unavailable"`, honest, no fabricated detail.
4. **Temp-only + cleanup:** a capture (mocked backend) writes only a temp file and deletes it on both success and failure paths; no durable write.
5. **Rails unchanged regression:** the full v1a + gate suite (18 tests) stays green — third-party minimization, egress tagging, honest-blind, default-off untouched.
6. Full `discover` green; apples-to-apples in `/home/rohit/maez`.

## 6. Owner steering (RESOLVED 2026-06-06 — binding constraints on the slice)

1. **Portal permission:** a **one-time owner grant is acceptable ONLY if capture is no-prompt afterward.** A per-capture prompt is a **no-go** — if a route prompts on every capture, it is disqualified and the eye reports `unavailable`.
2. **GNOME extension:** **do NOT install or enable an extension inside this slice by default.** First *probe* whether an existing no-prompt active-window route exists. If none does, **stop and report** with "extension needed" named as the **next owner-authorized slice** — do not install one to finish v0.
3. **Capture package:** **default is stop-and-report; install nothing autonomously.** If a package turns out to be needed, that decision is made **after** the empirical probe names exactly which lens is viable on this GNOME Wayland body — not before, not silently.

## 7. Acceptance rules

1. Preflight fails **safe** (undetermined window → excluded), proven by the inverted test (§5.2).
2. A real capture works **no-prompt** on the daemon's GNOME Wayland session, or the eye honestly reports `unavailable` (§3.3).
3. Capture is **temp-only + always cleaned**, no durable screenshot (§3.5).
4. v1a rails byte-unchanged; the 18-test suite stays green (§5.5).
5. **Full witness required only when both active-window and capture routes are available** (Full Lens v0, §3.5). Otherwise the passing result is an **honest blind/safety-floor report** (§4) — a *correct* landing, but **not v1b-unblocking sight.** A safety-floor blind eye must never be reported or recorded as "ready to see / ready to remember." Unit tests alone never close either outcome on the real session.
6. §6 steering honored — **no autonomous install/enable** of a package or extension; stop-and-report instead, naming the next owner-authorized slice.
7. **`## Predicted effect`** on the impl commit.

## 8. Predicted effect

Lands **dormant** (default-off, unchanged). **When enabled on this GNOME Wayland machine after Lens v0:** a blink captures the screen via a working no-prompt route → vision returns `ok` → a governed Level-2 summary reaches the cycle prompt tagged `owner_screen_context` → nothing persists. The preflight, now fail-safe (and ideally backed by a real Wayland active-window read), excludes sensitive windows **before** capture even when the window is hard to read. **Falsifiable:** with it enabled, an ordinary window yields `state="ok"` with a real summary; a focused finance/medical/messaging app yields `excluded` with zero screenshots; no screen row persists; and no per-capture permission dialog appears. If no no-prompt route exists, the eye honestly reports `unavailable` rather than fabricating — and that, too, is a passing (if disappointing) outcome that hands the owner a clean decision.
