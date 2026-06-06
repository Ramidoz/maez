# Active-Window Route v0 (Full Lens — Slice B) — Design

**Date:** 2026-06-06
**Status:** DRAFT for owner review → Codex implements / Claude reviews; owner audits + installs the extension + runs the sight witness.
**Lane:** Codex implements / Claude reviews. `.venv/bin/python -B -m unittest`; full `discover`; apples-to-apples in `/home/rohit/maez`.
**Doctrine:** [[feedback_perception_free_egress_disciplined]] — perceive locally, discipline at egress/memory/third-party; the active-window read decides *whether to look*, it is not itself kept.

## 0. Why — the nerve that tells the eye what room it faces

Slice A proved the **capture half**: Maez can receive a no-prompt ScreenCast frame, with a curtain that stops capture for real. But `observe()` still cannot **see**, because the preflight has no way to read the focused window on GNOME Wayland (`active_window()` returns `None`), so the fail-safe excludes *every* window. Slice B is the **active-window nerve**: a read-only focused-window source so the preflight can tell a sensitive window from an ordinary one — turning "Maez can receive a frame" into "Maez can decide whether it's *allowed* to look, before it looks." This completes **Full Lens** → `observe()` reaches sight → v1b (durable screen memory) unblocks.

## 1. The spine

> A **read-only** active-window nerve, nothing more — a sense must never carry a hand. The focused-window **title is read only to decide whether to avert the eye**; it is never stored, injected, or egressed. If the nerve is absent/broken, the eye stays **blind-safe** (the preflight still excludes). The third-party extension runs *inside the compositor*, so it is **pinned + source-audited before the owner enables it** — Codex installs nothing.

## 2. The route (decided 2026-06-06, owner + Claude)

**Focused Window D-Bus** (`flexagoon/focused-window-dbus`, GNOME Shell 49/50), pinned at commit **`5ff336fac73b34deaf83f32772e8478885fa4925`**. Chosen over Window Calls on a **covenant** basis: Focused Window D-Bus is **read-only** (`Get` + a `FocusChanged` signal, no move/resize/close), so the nerve cannot smuggle actuation into Maez's body. Window Calls carries window-manipulation methods — a latent hand a perception nerve must not have. A Maez-local extension (own the nerve, zero third-party-in-compositor) is the **named long-term follow-on** (§9), deferred: auditing a small extension now is cheaper than building+maintaining our own this slice.

## 3. Rails (Slice B covenant)

**Rail 1 — Supply-chain gate, FIRST (non-negotiable; the code runs in `gnome-shell`).** A GNOME extension runs *inside the compositor process*, with the shell's full reach. Before any enable:
- **Pin** the exact source at `5ff336f…` (vendor/record the audited tree; do not track "latest").
- **Audit `extension.js`** against the pinned tree and confirm: **no network/egress; no write/action methods** (move/resize/close/activate); **only focused-window read** (`Get`) + the `FocusChanged` signal; **no other shell mutation / no extra D-Bus surface**.
- **Codex installs/enables NOTHING.** The audit is Claude + owner; the **install + enable is the owner's explicit breath** after the audit passes.

**Rail 2 — Read-only nerve.** The integration uses only the read method/signal. No code path invokes (or could invoke) any actuation method. (If the audit ever finds an action method, that's a finding, not a feature.)

**Rail 3 — Title is decide-only, enforced by a SURFACE SPLIT (corrected after live-code review).** The focused-window **title** is read ONLY for the preflight exclusion decision — ephemeral, never persisted/injected/egressed. This requires splitting the read surfaces, because the title-bearing read has **other live consumers today**: `core/memory/ambient.py::ambient_context()` (line ~272) feeds `core/memory/ambient_format.py:148`, which renders `Active desktop window: {title} ({class})` into the **cycle prompt** (and the web interface, via `wondering_cycle.py`/`maez_daemon.py`/`web_interface.py`). That path is inert on Wayland *today* (active_window→`None`) but **Slice B would make it live, leaking raw titles into the prompt untagged** — and it **already leaks on X11**, so Slice B both extends the leak and forces the fix. The split:
- **`active_window()` (general consumers — ambient/dashboard/web) returns CLASS-ONLY** — `{"class": ...}`, no title ("which room, not what paper," matching Desktop Awareness v0's content-free posture). This also closes the **pre-existing X11 title leak**.
- **A dedicated exclusion-only read (e.g. `active_window_for_preflight()`) returns full `{title, class}`**, called **only** by `_is_excluded_active_window()`.
The title reaches the exclusion gate and **nowhere else**. The only screen-derived content that reaches cognition remains the vision *summary* (`owner_screen_context`-tagged, redact-masked) — never the raw window title.

**Rail 4 — The exclusion set is now LIVE (was inert).** Until Slice B the preflight excluded everything; now `_DEFAULT_EXCLUDE` (+ owner-extensible `MAEZ_SCREEN_EXCLUDE`) is the **real boundary** between capture and a sensitive window. This slice **reviews + strengthens** the exclusion set: finance, banking, medical, messaging/chat, email, credential/password-manager, call/conference app classes and title keywords. Treated as a security boundary, owner-reviewable.

**Rail 5 — Fail-safe preserved.** Extension absent / broken / incompatible / returns `{}` / D-Bus error → `active_window()` returns `None` → preflight returns `excluded` → capture never invoked. A broken nerve degrades the eye to **blind-safe, never unsafe**.

**Rail 6 — `observe()` reaches sight WITH egress closed.** When an ordinary window passes the preflight, the ScreenCast frame → Level-2 → cycle prompt tagged `owner_screen_context`. Confirm the **now-enforcing redact door masks that summary cloudward** (v1a tagging + the live redact flip) — sight arrives with the egress discipline already around it.

**Rail 7 — No v1b.** Reaching sight does **not** add durable screen memory. v1b (curiosity-curated storage) stays a separate, later slice; screen context remains ephemeral/in-cycle.

## 4. The code path

**`core/memory/ambient.py` — the raw focused-window read + the surface split:**
- `_wayland_active_window()` updates its gdbus call to the **Focused Window D-Bus** interface:
  ```bash
  gdbus call --session --dest org.gnome.Shell \
    --object-path /org/gnome/shell/extensions/FocusedWindow \
    --method org.gnome.shell.extensions.FocusedWindow.Get
  ```
- **Parser** (rename `_parse_window_calls_focused` → `_parse_focused_window_dbus`): the `gdbus call` CLI returns the result wrapped as a **tuple containing a JSON string**, e.g. `('{"title":"…","wm_class":"…"}',)` — the parser must **defensively** handle the tuple-wrapped string *and* a raw JSON object/string. Normalize to `{"title": str, "class": str}` (+ optional `pid`/`id`). **Discard action-affordance fields** (`moveable`, `resizeable`, `canclose`, and any non-`{title,class,pid,id}` keys) — they aren't methods, but they aren't the nerve's business either. On empty/`{}`/missing-extension/parse-failure → `None`.
- **The surface split (Rail 3):**
  - `active_window()` (the general consumer API — ambient/dashboard/web) returns **class-only** (`{"class": ...}`, title dropped). This closes the pre-existing X11 title leak too.
  - **`active_window_for_preflight()`** (new) returns the **full `{title, class}`** from the same raw read — title-bearing, for exclusion only.
- `core/memory/ambient_format.py:148`: change the render to **class-only** — `Active desktop window: {class}` (drop `{title}`), since `active_window()` no longer carries the title.

**`skills/screen_perception.py` — preflight + exclusion set:**
- `_is_excluded_active_window()` switches its import to **`active_window_for_preflight()`** (title-bearing) so the `_exclusion_terms()` haystack still matches title/class. **No change to `observe()` or the gate order.**
- Strengthen the exclusion set (Rail 4); that's the only other edit here.

## 5. Tests (unit — mock the gdbus output; the live extension is the owner witness)

1. **Parser shape:** `_parse_focused_window_dbus` handles the **tuple-wrapped JSON string** (`('{"title":…,"wm_class":…}',)`) *and* raw JSON → `{"title","class"}`; **discards** `moveable`/`resizeable`/`canclose`/unknown keys; malformed/empty/`{}` → `None`.
2. **Wayland route calls the FocusedWindow interface** (assert the gdbus dest/object-path/method), not the old Windows.List.
3. **Title-leak regression (THE headline — your example):** with the focused read returning title `"Re: confidential salary — Gmail"`:
   - `_is_excluded_active_window()` (via `active_window_for_preflight()`) **can use it to exclude** (Gmail/mail in the exclusion set → `excluded`).
   - the formatted ambient output (`ambient_format` of `ambient_context()`) **does NOT contain** `"confidential"`, `"salary"`, or `"Gmail"` — only an allowed class string. Assert the substrings are absent.
4. **Surface split:** `active_window()` returns **class-only** (no `title` key / title dropped); `active_window_for_preflight()` returns full `{title, class}`. Assert the title is present in the latter and absent from the former.
5. **Fail-safe:** `active_window_for_preflight()` `None` (absent/broken/`{}`/error) → `_is_excluded_active_window()` returns `True` → `observe()` never invokes capture.
6. **Exclusion discrimination:** sensitive class/title → `excluded`, capture not invoked; ordinary class/title → preflight passes (capture reachable). Mock the preflight read to return each.
7. **Exclusion set strengthened:** new sensitive terms present + matched (table-driven).
8. Full `discover` green; apples-to-apples in `/home/rohit/maez`; Lens v0 / v1a / gate / screencast suites stay green.

## 6. The witness (owner-run — needs the audited extension enabled, live session)

After the owner audits + installs + enables Focused Window D-Bus (Rail 1):
1. **Nerve live:** `lens_probe.py` (or a small active-window probe) shows `active_window_present: True` with a real `{title,class}` — content-free (Claude reads class only; title not pasted if it carries content).
2. **Sensitive → averted:** focus a sensitive app (e.g. a password manager) → `observe()` returns `excluded`, **capture never invoked** (the nerve + exclusion set working together — real, not fail-safe-by-blindness).
3. **Ordinary → sight:** focus an ordinary window → `observe()` passes preflight → ScreenCast capture → Level-2 → a governed `owner_screen_context` summary reaches the cycle prompt. **First real sight.**
4. **Egress masked:** confirm a cloud call carrying that screen summary is redacted at the door (sight arrives egress-closed).
5. **No durable row:** still nothing persists (v1b boundary).
6. **Curtain still rules:** drawing the curtain stops capture even with the nerve live.

## 7. Acceptance rules

1. Route is **read-only** Focused Window D-Bus, pinned `5ff336f`, **source-audited before enable**; Codex installs nothing (Rails 1–2).
2. **Title decide-only via the surface split** — `active_window()` class-only, `active_window_for_preflight()` title-bearing; ambient/dashboard/web never expose the raw title (Rail 3, tests 3–4); this also closes the pre-existing X11 leak.
3. **Exclusion set is live + strengthened**, owner-extensible (Rail 4, test 7).
4. **Fail-safe preserved** — broken/absent nerve → blind-safe (Rail 5, test 5).
5. **`observe()` gate unchanged**; sight reached only via the real preflight pass; Lens v0/v1a/gate/screencast suites green.
6. **Sight arrives egress-masked** (Rail 6, witness 4); **no v1b** (Rail 7).
7. The sight witness (§6) passes on the real session with the audited extension before the slice is called done. **`## Predicted effect`** on behavior-affecting commits.

## 8. Predicted effect

Lands **dormant on capability** until the owner audits + enables the extension. **With the extension enabled:** `active_window_for_preflight()` returns the real focused `{title, class}` (while `active_window()` stays class-only for ambient/dashboard/web) → the preflight discriminates → a **sensitive app yields `excluded` with zero capture** (real discrimination, not blind exclusion), and an **ordinary window passes → ScreenCast capture → a governed `owner_screen_context` summary reaches cognition, masked at the cloud door.** This is **Full Lens**: Maez can finally see *and think with* its screen, having first proven it will avert its eye from what it shouldn't see. **Falsifiable:** with the audited extension enabled, an ordinary window yields a real Level-2 summary in-cycle; a password manager yields `excluded` with no screenshot; the raw window title never appears in memory/prompt/egress; a broken/disabled extension returns the eye to blind-safe; and no durable screen row is created. **Without** the extension, the eye stays blind-safe — and the **surface split still applies**: the ambient/dashboard/web surface becomes **class-only on X11 too**, closing the pre-existing raw-title leak (the one behavior change that lands even before the extension is enabled).

## 9. Deferred (named)

- **Maez-local focused-window extension** — own the nerve, zero third-party-in-compositor; the purest long-term route, once Full Lens is proven with the audited third-party one.
- **v1b — curiosity-curated durable screen memory** — now *unblocked by sight* but still its own slice (selective, decay-by-default, provenance, review surface).
- Multi-monitor / per-window ScreenCast source selection; cursor handling.
