# Active-Window Route v0 (Full Lens — Slice B) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the preflight a read-only focused-window nerve (Focused Window D-Bus) so `observe()` can tell a sensitive window from an ordinary one — completing Full Lens (sight) — while the window **title** reaches the exclusion gate and nowhere else.

**Architecture:** One raw focused-window read (`_raw_active_window`) feeds two public surfaces: `active_window()` (class-only, for ambient/dashboard/web) and `active_window_for_preflight()` (full `{title,class}`, for the exclusion gate only). The Wayland read switches to the Focused Window D-Bus extension; `ambient_format` stops rendering raw titles (closing a pre-existing X11 leak). `observe()` and its gate order are unchanged.

**Tech Stack:** Python 3, `unittest` (NOT pytest — `.venv/bin/python -B -m unittest`), `gdbus` for the extension read. The extension itself is owner-audited + owner-installed (Rail 1); Codex installs nothing. The live sight witness is owner-run.

**Spec:** `docs/superpowers/specs/2026-06-06-active-window-route-slice-b-design.md`. **Lane:** Codex implements / Claude reviews. Apples-to-apples full `discover` in `/home/rohit/maez`.

**Boundary reminder:** completes sight, but **no v1b** (no durable screen memory); the raw **title** is exclusion-input-only — never persisted/injected/egressed.

---

### Task 1: Audit gate (Rail 1) — record the pinned-source audit BEFORE any code assumes the extension

**Files:**
- Create: `docs/handoffs/2026-06-06-focused-window-dbus-audit.md` (the audit record)

**Context:** The extension runs inside `gnome-shell` (compositor-privileged). This task is the audit record; **Codex installs/enables nothing** — the owner installs after the audit passes. The code (Tasks 2-7) lands dormant-on-capability regardless.

- [ ] **Step 1:** Record, against pinned commit `5ff336fac73b34deaf83f32772e8478885fa4925` of `flexagoon/focused-window-dbus`, an audit of `extension.js` confirming: no network/egress; no write/action methods (move/resize/close/activate); only focused-window read (`Get`) + `FocusChanged` signal; no other shell mutation / no extra D-Bus surface. Note the exact D-Bus name/object-path/method observed.
- [ ] **Step 2: Commit the audit record**

```bash
git add docs/handoffs/2026-06-06-focused-window-dbus-audit.md
git commit -m "docs(handoff): pinned-source audit of Focused Window D-Bus (5ff336f) for Slice B"
```

---

### Task 2: Parser — `_parse_focused_window_dbus` (tuple-wrapped JSON + field discard)

**Files:**
- Modify: `core/memory/ambient.py:193` (replace `_parse_window_calls_focused`)
- Test: `tests/test_ambient_active_window_wayland.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ambient_active_window_wayland.py — append
class ParseFocusedWindowTests(unittest.TestCase):
    def test_tuple_wrapped_json_string(self):
        raw = "({'unused'},)"  # placeholder; use the real gdbus shape below
        out = ambient._parse_focused_window_dbus(
            '(\'{"title": "Doc", "wm_class": "Code", "moveable": true}\',)')
        self.assertEqual(out, {"title": "Doc", "class": "Code"})  # action field discarded

    def test_raw_json_object(self):
        out = ambient._parse_focused_window_dbus('{"title": "T", "class": "firefox"}')
        self.assertEqual(out, {"title": "T", "class": "firefox"})

    def test_empty_or_malformed_is_none(self):
        for raw in ("", "()", "{}", "(\'{}\',)", "garbage", "(\'not json\',)"):
            self.assertIsNone(ambient._parse_focused_window_dbus(raw))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -B -m unittest tests.test_ambient_active_window_wayland.ParseFocusedWindowTests -v`
Expected: FAIL — `_parse_focused_window_dbus` not defined.

- [ ] **Step 3: Write minimal implementation**

```python
# core/memory/ambient.py — replace _parse_window_calls_focused
import ast
import json

def _parse_focused_window_dbus(raw) -> dict | None:
    """Normalize Focused Window D-Bus output to {"title","class"} or None.

    `gdbus call` returns a tuple printed as a Python-ish literal whose first
    element is a JSON string, e.g.  ('{"title":"…","wm_class":"…"}',)  — handle
    that AND a raw JSON object/string defensively. Discard action-affordance and
    unknown fields; keep only title/class (+ optional pid/id).
    """
    if not raw:
        return None
    text = raw.strip()
    obj = None
    # Case A: tuple-wrapped — extract the inner string literal, then JSON-parse it.
    if text.startswith("("):
        try:
            tup = ast.literal_eval(text)
            inner = tup[0] if isinstance(tup, tuple) and tup else None
            if isinstance(inner, str):
                obj = json.loads(inner)
        except Exception:
            obj = None
    # Case B: raw JSON object/string.
    if obj is None:
        try:
            obj = json.loads(text)
        except Exception:
            return None
    if not isinstance(obj, dict) or not obj:
        return None
    title = obj.get("title")
    klass = obj.get("class") or obj.get("wm_class")
    if not klass and not title:
        return None
    out = {"title": title or "", "class": klass or ""}
    for opt in ("pid", "id"):
        if opt in obj:
            out[opt] = obj[opt]
    return out  # moveable/resizeable/canclose/unknown silently dropped

# Back-compat alias (the old caller name), if anything still references it:
_parse_window_calls_focused = _parse_focused_window_dbus
```

- [ ] **Step 4: Run test to verify it passes** — `…ParseFocusedWindowTests -v` → PASS

- [ ] **Step 5: Commit**

```bash
git add core/memory/ambient.py tests/test_ambient_active_window_wayland.py
git commit -m "feat(body): parse Focused Window D-Bus output (tuple-wrapped JSON, field discard)"
```

---

### Task 3: Wayland read → Focused Window D-Bus interface

**Files:**
- Modify: `core/memory/ambient.py:199` (`_wayland_active_window`)
- Test: `tests/test_ambient_active_window_wayland.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ambient_active_window_wayland.py — append
class WaylandRouteTests(unittest.TestCase):
    def test_calls_focused_window_interface(self):
        captured = {}
        def fake_check_output(cmd, **kw):
            captured["cmd"] = cmd
            return '(\'{"title":"T","wm_class":"firefox"}\',)'
        with mock.patch.object(ambient.shutil, "which", return_value="/usr/bin/gdbus"), \
             mock.patch.object(ambient.subprocess, "check_output", side_effect=fake_check_output):
            out = ambient._wayland_active_window()
        self.assertEqual(out, {"title": "T", "class": "firefox"})
        self.assertIn("/org/gnome/shell/extensions/FocusedWindow", captured["cmd"])
        self.assertIn("org.gnome.shell.extensions.FocusedWindow.Get", captured["cmd"])
```

- [ ] **Step 2: Run** → FAIL (still calls Windows.List).

- [ ] **Step 3: Implement**

```python
# core/memory/ambient.py — _wayland_active_window body, the gdbus args:
        out = subprocess.check_output(
            [
                "gdbus", "call", "--session",
                "--dest", "org.gnome.Shell",
                "--object-path", "/org/gnome/shell/extensions/FocusedWindow",
                "--method", "org.gnome.shell.extensions.FocusedWindow.Get",
            ],
            timeout=timeout, text=True, stderr=subprocess.DEVNULL,
        )
        return _parse_focused_window_dbus(out)
```

- [ ] **Step 4: Run** → PASS

- [ ] **Step 5: Commit**

```bash
git add core/memory/ambient.py tests/test_ambient_active_window_wayland.py
git commit -m "feat(body): Wayland active-window read via Focused Window D-Bus"
```

---

### Task 4: The surface split — `active_window()` class-only + `active_window_for_preflight()`

**Files:**
- Modify: `core/memory/ambient.py:229` (refactor `active_window` → raw read + two surfaces)
- Test: `tests/test_ambient_active_window_wayland.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ambient_active_window_wayland.py — append
class SurfaceSplitTests(unittest.TestCase):
    def test_active_window_is_class_only(self):
        with mock.patch.object(ambient, "_raw_active_window",
                               return_value={"title": "secret doc", "class": "Code"}):
            out = ambient.active_window()
        self.assertEqual(out, {"class": "Code"})        # title dropped
        self.assertNotIn("title", out)

    def test_preflight_surface_keeps_title(self):
        with mock.patch.object(ambient, "_raw_active_window",
                               return_value={"title": "secret doc", "class": "Code"}):
            out = ambient.active_window_for_preflight()
        self.assertEqual(out, {"title": "secret doc", "class": "Code"})

    def test_both_none_when_raw_none(self):
        with mock.patch.object(ambient, "_raw_active_window", return_value=None):
            self.assertIsNone(ambient.active_window())
            self.assertIsNone(ambient.active_window_for_preflight())
```

- [ ] **Step 2: Run** → FAIL (`_raw_active_window`/`active_window_for_preflight` not defined).

- [ ] **Step 3: Implement** — rename the current `active_window` body to `_raw_active_window`, add the two surfaces:

```python
# core/memory/ambient.py
def _raw_active_window(timeout: float = 1.0) -> dict | None:
    """Raw focused-window read: {"title","class"} | None. Wayland via Focused
    Window D-Bus, else X11 via xdotool. INTERNAL — callers must choose a surface."""
    if _session_is_wayland():
        return _wayland_active_window(timeout)
    if not shutil.which("xdotool"):
        return None
    try:
        # ... existing xdotool/xprop body, returning {"title": name, "class": wm_class}
    except Exception as e:
        logger.debug("active_window failed: %s", e)
        return None


def active_window_for_preflight(timeout: float = 1.0) -> dict | None:
    """Title-bearing read — EXCLUSION GATE ONLY. The title is used to decide
    whether to avert the eye; it must not be persisted/injected/egressed."""
    return _raw_active_window(timeout)


def active_window(timeout: float = 1.0) -> dict | None:
    """CLASS-ONLY focused-window read for general consumers (ambient/dashboard/
    web). No title — "which room, not what paper." Use active_window_for_preflight
    for the exclusion decision."""
    raw = _raw_active_window(timeout)
    if not raw:
        return None
    return {"class": raw.get("class", "")}
```

- [ ] **Step 4: Run** → PASS

- [ ] **Step 5: Commit**

```bash
git add core/memory/ambient.py tests/test_ambient_active_window_wayland.py
git commit -m "feat(body): surface split — active_window() class-only, active_window_for_preflight() title-bearing"
```

---

### Task 5: `ambient_format` class-only + the title-leak regression (THE headline)

**Files:**
- Modify: `core/memory/ambient_format.py:148`
- Test: `tests/test_ambient_active_window_wayland.py` (or the ambient_format test module)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ambient_active_window_wayland.py — append
import core.memory.ambient_format as afmt
class TitleLeakRegressionTests(unittest.TestCase):
    def test_confidential_title_excludes_but_never_renders(self):
        leaky = {"title": "Re: confidential salary — Gmail", "class": "Gmail"}
        # (a) preflight CAN exclude on it
        import skills.screen_perception as sp
        with mock.patch("core.memory.ambient.active_window_for_preflight", return_value=leaky), \
             mock.patch.object(sp, "_exclusion_terms", return_value=("gmail", "mail")):
            self.assertTrue(sp._is_excluded_active_window())
        # (b) ambient formatting NEVER contains the title content
        ctx = {"active_window": {"class": "Gmail"}}  # active_window() is class-only now
        rendered = afmt.ambient_prompt_block(ctx) if hasattr(afmt, "ambient_prompt_block") \
            else "\n".join(afmt.format_ambient(ctx))
        for leak in ("confidential", "salary", "Gmail"):
            # 'Gmail' as a bare class may be allowed; assert the SENTENCE fragments aren't present
            self.assertNotIn("confidential", rendered)
            self.assertNotIn("salary", rendered)
```

(Adapt the formatter entry-point name to the real one in `ambient_format.py`.)

- [ ] **Step 2: Run** → FAIL (line 148 still renders `{title}`).

- [ ] **Step 3: Implement** — `core/memory/ambient_format.py:148`:

```python
    win = ctx.get("active_window") or {}
    if win:
        lines.append(f"Active desktop window: {win.get('class', '?')}")  # class-only (no title)
```

- [ ] **Step 4: Run** → PASS

- [ ] **Step 5: Commit**

```bash
git add core/memory/ambient_format.py tests/test_ambient_active_window_wayland.py
git commit -m "$(printf 'fix(body): ambient renders active window CLASS-only, never the raw title\n\n## Predicted effect\nThe ambient/dashboard/web surface no longer renders the focused window title\n(closing a pre-existing X11 leak and pre-empting the Wayland one). A title like\n\"Re: confidential salary — Gmail\" can drive preflight exclusion but never\nappears in the cycle prompt or web UI.')"
```

---

### Task 6: Preflight consumes the title-bearing surface

**Files:**
- Modify: `skills/screen_perception.py` (`_is_excluded_active_window` import)
- Test: `tests/test_screen_perception_lens.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_screen_perception_lens.py — append
class PreflightUsesTitleSurfaceTests(unittest.TestCase):
    def test_preflight_reads_title_bearing_surface(self):
        with mock.patch("core.memory.ambient.active_window_for_preflight",
                        return_value={"title": "Bank of X — Login", "class": "firefox"}), \
             mock.patch.object(sp, "_exclusion_terms", return_value=("bank",)):
            self.assertTrue(sp._is_excluded_active_window())  # matched via TITLE
    def test_preflight_none_excludes(self):
        with mock.patch("core.memory.ambient.active_window_for_preflight", return_value=None):
            self.assertTrue(sp._is_excluded_active_window())  # fail-safe
```

- [ ] **Step 2: Run** → FAIL (preflight still imports `active_window`, which is class-only → title match breaks).

- [ ] **Step 3: Implement** — in `skills/screen_perception.py:_is_excluded_active_window`:

```python
    from core.memory.ambient import active_window_for_preflight
    win = active_window_for_preflight()
    if not win:
        return True  # fail-safe (Lens v0)
    haystack = f"{win.get('class', '')} {win.get('title', '')}".lower()
    return any(term in haystack for term in _exclusion_terms())
```

- [ ] **Step 4: Run** → PASS

- [ ] **Step 5: Commit**

```bash
git add skills/screen_perception.py tests/test_screen_perception_lens.py
git commit -m "fix(body-ui): preflight reads the title-bearing surface (exclusion only)"
```

---

### Task 7: Strengthen the exclusion set (now load-bearing)

**Files:**
- Modify: `skills/screen_perception.py` (`_DEFAULT_EXCLUDE`)
- Test: `tests/test_screen_perception_lens.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_screen_perception_lens.py — append
class ExclusionSetTests(unittest.TestCase):
    def test_sensitive_classes_and_titles_excluded(self):
        cases = [
            {"class": "Bitwarden", "title": "Vault"},
            {"class": "firefox", "title": "Online Banking — Chase"},
            {"class": "Signal", "title": "Alice"},
            {"class": "firefox", "title": "MyChart — Patient Portal"},
            {"class": "1Password", "title": ""},
        ]
        for win in cases:
            with mock.patch("core.memory.ambient.active_window_for_preflight", return_value=win):
                self.assertTrue(sp._is_excluded_active_window(), win)
    def test_ordinary_not_excluded(self):
        for win in ({"class": "Gnome-terminal", "title": "bash"},
                    {"class": "Code", "title": "ambient.py"}):
            with mock.patch("core.memory.ambient.active_window_for_preflight", return_value=win):
                self.assertFalse(sp._is_excluded_active_window(), win)
```

- [ ] **Step 2: Run** → FAIL (terms missing).

- [ ] **Step 3: Implement** — extend `_DEFAULT_EXCLUDE` with finance/banking/medical/messaging/email/credential/call terms (class + title keywords), e.g. `bitwarden`, `1password`, `keepass`, `bank`, `chase`, `signal`, `whatsapp`, `telegram`, `mychart`, `patient`, `zoom`, `meet`, etc. Keep `MAEZ_SCREEN_EXCLUDE` owner-extension intact. (Tune so the ordinary cases stay non-excluded.)

- [ ] **Step 4: Run** → PASS

- [ ] **Step 5: Commit**

```bash
git add skills/screen_perception.py tests/test_screen_perception_lens.py
git commit -m "feat(body-ui): strengthen now-live exclusion set (finance/medical/messaging/credential/call)"
```

---

### Task 8: Boundary regression

- [ ] **Step 1:** Run the focused + boundary suites:
```bash
.venv/bin/python -B -m unittest \
  tests.test_ambient_active_window_wayland tests.test_screen_perception_lens \
  tests.test_screen_perception_v1a tests.test_screen_perception_gate \
  tests.test_screencast_capture -v
```
Expected: ALL PASS. `observe()` gate order byte-unchanged (only the preflight's *read source* + exclusion set changed). Confirm no diff to `observe()` itself.

- [ ] **Step 2:** Full `discover` in `/home/rohit/maez`; floor matches the ambient confound class; no new failures in ambient/screen/lens/screencast suites.

---

### Task 9: Sight witness (OWNER-RUN — needs the audited extension enabled)

**Context:** Owner audits (Task 1) → installs + enables Focused Window D-Bus → runs the witness. Content-free (Claude reads class + states, never the raw title).

- [ ] **Step 1:** Nerve live — a small probe shows `active_window_for_preflight()` returns a real `{title,class}` and `active_window()` returns class-only. (Owner confirms title present in the preflight surface, absent from the general one.)
- [ ] **Step 2:** Sensitive → averted — focus a password manager / banking tab → `observe()` returns `excluded`, capture **not** invoked (real discrimination).
- [ ] **Step 3:** Ordinary → **sight** — focus an ordinary window → `observe()` passes preflight → ScreenCast capture → Level-2 → a governed `owner_screen_context` summary reaches the cycle prompt. **First real sight.**
- [ ] **Step 4:** Egress masked — a cloud call carrying that summary is redacted at the door.
- [ ] **Step 5:** Title never leaks — confirm the raw window title appears in neither the prompt/ambient block nor memory.
- [ ] **Step 6:** No durable row (v1b boundary); curtain still stops capture.

---

### Task 10: Finish — canon + branch completion

- [ ] **Step 1:** Update `project_cognition_live_state.md` (canon) with the Slice B outcome: **Full Lens reached** (or witness verdict), surface split + title-leak fix (incl. X11), exclusion set live, **v1b now unblocked** (separate slice).
- [ ] **Step 2:** Use **superpowers:finishing-a-development-branch** — local merge owner-delegable per the arc; the **extension install/enable + the sight witness stay the owner's**. NO push.
- [ ] **Step 3:** Confirm v1b is now the named-next (curiosity-curated durable screen memory).
