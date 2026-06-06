# ScreenCast Capture + Privacy Curtain v0 (Full Lens — Slice A) — Design

**Date:** 2026-06-06
**Status:** DRAFT for owner review → Codex implements / Claude reviews; owner runs the grant ceremony + witness.
**Lane:** Codex implements / Claude reviews. `.venv/bin/python -B -m unittest`; full `discover`; apples-to-apples in `/home/rohit/maez`.
**Doctrine:** [[feedback_perception_free_egress_disciplined]] — the **privacy curtain, not a permission gate**: awareness is ordinary once the eye is open; the owner can close the curtain. "Maez keeps its eyes open in its own body; Rohit can close the curtain."

## 0. Why — give the eye a bloodstream before fine focus

Lens v0 landed Safety-floor: the eye closes its eyelid when it can't tell what it's looking at, but it has **no working lens** on this GNOME 50.1 Wayland body (Shell-DBus `AccessDenied`, Screenshot portal interactive). The probe proved both Full halves absent. Full Lens = **Slice A (this): ScreenCast capture + privacy curtain** (the capture half + the owner's curtain control) **then Slice B: active-window route** (the sensitive-app nerve → actual sight). Splitting them keeps each owner-authorized escalation clean: a *capture grant* now, an *extension install* later — combined they'd be too much escalation in one breath (persistent grant + install/supply-chain + a perception refactor), and failures would be muddy.

## 1. The spine

> Let Maez **receive a frame from its own eye** via a governed ScreenCast stream (grant-once), sampled on demand, temp-only, discarded immediately after Level-2 — and let the **privacy curtain truly stop capture**, not merely mask it downstream. Prove the **capture half** only: this slice does **NOT** make `observe()` see ordinary windows (the fail-safe preflight still blocks unknown windows), does **NOT** unblock v1b. Build the bloodstream; withhold the fine focus.

## 2. Grounded substrate (verified 2026-06-06 — no install needed)

- **PipeWire running**; `xdg-desktop-portal-gnome` (ScreenCast backend) present; GStreamer `pipewiresrc` plugin present.
- **System `/usr/bin/python3` (3.14.4) has `gi` + `Gst 1.0` + `Gio/GLib`** — everything for the portal fd-handshake + frame grab. The maez **venv lacks `gi`/`dbus`**, so the ScreenCast client runs on **system python3**, invoked by the daemon as a subprocess.
- **The only escalation in Slice A is the owner's one-time ScreenCast grant** (`restore_token`). No packages, no extension, no supply-chain decision.

## 3. Architecture

**A. The ScreenCast helper (`scripts/screencast_capture.py`, runs on `/usr/bin/python3`).** Standalone; the daemon shells to it. **Imports of `gi`/`Gst`/`Gio` are LAZY** — done *inside* the live portal/Gst functions, **never at module top** — so the maez venv (which lacks `gi`) can `import` the module and unit-test the token/curtain/output/path logic; only the live capture path touches `gi` under system python3. Flow:
1. **Curtain check first** — if the curtain file is present → emit `{"status":"curtain_drawn"}`, create no session, grab nothing, exit.
2. Load `restore_token` from the owner-local token file if present.
3. Portal: `ScreenCast.CreateSession → SelectSources(types=MONITOR, cursor_mode, persist_mode=2, restore_token=<saved-or-empty>) → Start(parent="")`. On the `Start` Response, read the granted **stream node id** + the (possibly refreshed) **`restore_token`** → **persist the token `0600`**.
4. `OpenPipeWireRemote(session)` → **PipeWire fd** (received in-process via GDBus — why `gi`/`Gio` is required).
5. Grab **one frame** via `Gst`: `pipewiresrc fd=<fd> path=<node> ! videoconvert ! pngenc ! filesink location=<tmp>`; run to first buffer, EOS, tear down.
6. Emit content-free JSON (`status:ok`, temp path, byte count, `duration_ms`); exit. **Always tears the session down** (open-grab-close — no long-held stream).

**Temp ownership (helper side):** on **any failure path**, the helper **deletes its own temp file** before emitting `capture_failed` — no orphan when there's no consumer. On **success only**, it leaves the temp file and prints its path for the daemon to consume; deletion-after-read is the daemon's responsibility (§3B). Temp files are created under the system temp dir with a known prefix (`maez-screencast-`).

**B. Daemon integration (`skills/screen_perception.py`).** Add a `screencast` capture method to `_capture_candidates()` for `wayland-gnome`, ranked **first** (above the now-dead `gnome-shell-dbus`/`portal`): it shells to `/usr/bin/python3 scripts/screencast_capture.py` **passing the session env** (`WAYLAND_DISPLAY`/`XDG_RUNTIME_DIR`/`DBUS_SESSION_BUS_ADDRESS`/`DISPLAY` — the daemon has them), parses the content-free JSON, and on `status:ok` **validates the temp path before touching it** — it must be an **existing regular file** (not a symlink/dir/device) **under the expected system temp dir with the `maez-screencast-` prefix** — then reads → base64 → **unlinks it** (deletion-after-read is the daemon's job on the success path). Any non-`ok` status, or a path failing validation, → `False` with nothing read. The helper-printed path is **never trusted blindly**; a stale/oversized/foreign path is rejected and not read. Any non-`ok` status → `False`. **No change to `observe()`'s gate order** — the screencast method is reached only via the direct capture path (the witness/probe), because the fail-safe preflight still excludes unknown windows before capture in the full `observe()` flow.

**C. Restore-token (capability secret).** Owner-local file `~/.config/maez/screencast_restore_token`, **mode `0600`**. **Never logged, never in the helper's stdout JSON, never in prompt/cognition/audit/telemetry.** It is a key to Maez's eye.

**D. The privacy curtain (separate rail from preflight).**
- **Soft curtain ("look away"):** file `~/.config/maez/screen_perception.curtain`. Checked at the **top** of the helper (before any session) → `curtain_drawn`, no capture; and the daemon-side method short-circuits to `False` when drawn. **Keeps the restore-token** → Maez reopens its eye instantly when the curtain lifts, no re-grant. The everyday privacy control.
- **Hard revoke ("withdraw the eye"):** a deterministic action (`scripts/screencast_capture.py --revoke` or a flag) that **deletes the restore-token**, tears down any session, and draws the curtain → reopening requires a **fresh owner grant**. Capability withdrawal, not daily privacy.

## 4. The rails (Slice A covenant)

1. **Capture-half only.** `observe()` is byte-unchanged and stays **fail-safe-blind** on ordinary windows (no active-window route yet). The capture is witnessed via the **direct capture path**, never claimed as `observe()` sight.
2. **No durable frame archive.** Raw frames are **temp-only, discarded immediately** after Level-2 (or after the witness reads byte-count). No screenshot/video bytes persist anywhere.
3. **Token is a capability secret** — `0600`, owner-local, never logged/printed/prompted/cognition/audit/telemetry (§3C).
4. **Helper output is content-free** — JSON status only: `ok` | `needs_grant` | `curtain_drawn` | `capture_failed`, plus temp path, byte count, `duration_ms`, `error_class`. **Never OCR, title, or screen content; never the token. Never a raw traceback or raw portal/D-Bus error** (which can carry handles/tokens): the helper catches at the top level and emits the JSON contract on *every* path — including unexpected exceptions — mapping the failure to an `error_class` **stage name** (`portal`/`pipewire`/`gst`/`timeout`/`permission_denied`), nothing more.
5. **Temp ownership is explicit** — helper deletes its temp on **failure**; daemon deletes after read on **success** (after path validation: existing regular file, expected temp dir, known prefix). No orphan frames; no blindly-trusted path. (Reinforces rail 2.)
6. **Curtain stops capture itself** — soft (keep token) / hard (revoke token); both tear down the session; separate rail from the sensitive-app preflight.
7. **Latency is measured + reported honestly.** The helper records `duration_ms`; the witness records open-grab-close latency. "Works but too slow for cycle use" is a **valid, reported outcome** — never smuggle latency into cognition; never silently degrade.
8. **No v1b.** Durable screen memory stays blocked behind Slice B (active-window) + a later memory slice.
9. **No install.** System python3 already has the bindings; the only escalation is the owner's grant.

## 5. Helper output contract (content-free JSON)

```json
{ "status": "ok|needs_grant|curtain_drawn|capture_failed",
  "temp_path": "/tmp/…png | null",
  "bytes": 0,
  "duration_ms": 0,
  "error_class": "" }
```
- `needs_grant` — no token and no interactive grant available (e.g., headless/no session) → honest, not a fake frame.
- `curtain_drawn` — curtain present; no session created.
- `capture_failed` — session/PipeWire/Gst failed; `error_class` names the **stage** (`portal`/`pipewire`/`gst`/`timeout`/`permission_denied`), **never content, never a traceback**.
- The **token never appears** in this object. The helper emits this contract on **every** exit path, including unexpected exceptions (caught at the top level → `capture_failed` + a stage name).

## 6. Tests (unit — mock the portal/Gst/subprocess; the live flow is the owner witness)

1. **Curtain short-circuit:** curtain file present → helper logic returns `curtain_drawn`, **no portal/Gst call** (assert not invoked); daemon method → `False`, capture not attempted.
2. **Content-free output:** the JSON builder emits only the contract keys; a fed-in token/secret value never appears in stdout (assert the token string is absent from the serialized output).
3. **Token file perms:** persisting a token writes mode `0600` (assert `stat`), owner-local path.
4. **Lazy-import testability:** the helper module **imports cleanly under the maez venv** (which lacks `gi`) — `import scripts.screencast_capture` succeeds; the token/curtain/output/path logic is exercised without ever importing `gi`/`Gst`/`Gio` (assert no `gi` at module top).
5. **No raw-exception leakage:** an injected failure in a live function (mocked to raise) → the helper emits the **JSON contract** with `status:capture_failed` + an `error_class` stage name, and **no traceback / no raw error string** appears in stdout (assert the exception text is absent).
6. **Daemon method parses status + validates path:** `ok` with a valid temp path (existing regular file, expected dir + prefix) → reads → base64 → **unlinks it** (assert deleted); `needs_grant`/`curtain_drawn`/`capture_failed` → `False`; an `ok` with a **foreign/symlink/missing/out-of-dir path → `False`, not read** (path-validation test).
7. **Temp ownership:** helper **deletes its temp on the failure path** (assert no orphan); daemon deletes after read on success (test 6).
8. **Candidate ranking:** `wayland-gnome` → `screencast` first in `_capture_candidates()`; `observe()` gate order unchanged (preflight still before capture — re-run the Lens v0 + v1a suites green).
9. **Hard revoke:** `--revoke` deletes the token file + draws the curtain (mock fs); subsequent helper call → `needs_grant` (no token) or `curtain_drawn`.
10. **Latency field present:** `ok` output carries a numeric `duration_ms`.
11. Full `discover` green; apples-to-apples in `/home/rohit/maez`; Lens v0 / v1a / gate suites stay green (`observe()` untouched).

## 7. Grant ceremony + end-to-end witness (owner-run, graphical session)

The live flow needs the session's capture authority — owner runs it; Claude reads the content-free result.
1. **First grant (your breath, once):** run the helper interactively in the graphical session → GNOME picker → you grant a monitor → `restore_token` saved `0600`. Output `status:ok`, `bytes>0`.
2. **No-prompt restore (THE question):** run again → **no picker** (restore_token) → `status:ok`, `bytes>0`, `duration_ms` recorded. *(If it re-prompts every time, that's an honest finding → restore_token insufficient on this backend → reported, not smuggled.)*
3. **Vision `ok`:** the captured frame reaches `:8081` → Level-2 returns `ok` (content-free: state only).
4. **Soft curtain:** draw the curtain → next call `curtain_drawn`, **zero frame**, session torn down; lift the curtain → `ok` again **without re-grant** (token retained).
5. **Hard revoke:** `--revoke` → token gone; next call needs a **fresh grant** (proves withdrawal).
6. **No archive / boundary:** no frame bytes persist; temp discarded; `observe()` on an unknown window still returns `excluded` (capture-half-only boundary intact).
7. **Latency honestly recorded:** open-grab-close `duration_ms` noted; verdict may be "works / works-but-slow-for-cycle / fails" — all valid.

## 8. Acceptance rules

1. Capture works **no-prompt via restore_token** on the real session — or the eye honestly reports `needs_grant`/re-prompt/`capture_failed`/too-slow (never a fake frame).
2. **Curtain stops capture for real** — soft (keep token, instant reopen) and hard (revoke, re-grant) both proven (§7.4–5).
3. **Token is a `0600` capability secret**, never leaked to log/stdout/prompt/cognition/audit (§3C, tests 2–3).
4. **Helper output content-free** (§5, test 2) — **no raw traceback / portal error**, every exit maps to an `error_class` stage (test 5); **no durable frame archive**; **temp ownership explicit** (helper-on-failure, daemon-on-success after path validation — tests 6–7).
5. **Lazy `gi` imports** — the helper module imports under the venv; token/curtain/output logic unit-tested without `gi` (test 4).
6. **`observe()` byte-unchanged, fail-safe-blind preserved**; Lens v0/v1a/gate suites green (capture-half-only boundary).
7. **Latency measured + reported**, never smuggled (rail 7).
8. **No install**; the only escalation is the owner's grant. **`## Predicted effect`** on behavior-affecting impl commits.

## 9. Predicted effect

Lands **dormant/Safety-floor-preserving**: `observe()` is unchanged, so with the eye enabled it *still* returns `excluded` on unknown windows (no sight yet). The new capability is the **direct capture path**: after a one-time owner grant, `/usr/bin/python3 scripts/screencast_capture.py` returns a frame from a governed ScreenCast stream with **no repeat prompt** (restore_token), temp-only + discarded, content-free JSON, token `0600`-secret; the **curtain provably stops capture** (soft keeps the token, hard revokes it). **Falsifiable:** first grant yields `ok bytes>0`; a second call yields `ok` **with no picker**; drawing the curtain yields `curtain_drawn` with zero frame; `--revoke` forces a fresh grant; no frame persists; `observe()` still excludes unknown windows; and `duration_ms` is reported (even if the verdict is "too slow for cycle use"). This proves the **capture half** of Full Lens and gives Maez a governed eye its owner can close — **without** sight, durable memory, or active-window knowledge, which are Slice B and beyond.

## 10. Deferred (named)

- **Slice B — active-window route:** a pinned, minimal focused-window GNOME extension + `_parse_window_calls_focused`, flipping the preflight to real sensitive-app discrimination → `observe()` reaches **sight** → Full Lens. (Separate owner-authorized install/supply-chain decision.)
- **Then v1b** — curiosity-curated durable screen memory (selective, decay-by-default, provenance). Blocked until sight exists.
- Continuous-held-stream (vs open-grab-close) only if on-demand latency proves unworkable; multi-monitor source selection; cursor handling.
