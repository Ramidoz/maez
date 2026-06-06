# Desktop Perception v1a Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the existing screen-perception eye **safe to open for cognition** — preflight sensitive-app exclusion (never-looked), third-party minimization before the prompt, egress-tagged for the now-closed door, a deterministic pause primitive, and **no durable screen storage at all** — all default-off (lands dormant).

**Architecture:** Rehabilitate `skills/screen_perception.py` `observe()` (add pause + preflight gates *before* capture/probe/vision; add third-party governance after parse; new states/fields) and `core/egress/gate.py` (new `owner_screen_context` origin), and **remove** the unconditional durable-storage seam in `daemon/maez_daemon.py:8443`. No parallel eye; no durable write in v1a.

**Tech Stack:** Python 3.14, `unittest` (NOT pytest), the existing `requests`/screenshot/vision plumbing, `core/memory/ambient.active_window` (the preflight), the egress gate.

**Spec:** `docs/superpowers/specs/2026-06-06-desktop-perception-v1-design.md`

**Lands dormant** (default `MAEZ_SCREEN_PERCEPTION` unset → `disabled`). The daemon commit (Task 6) carries the `## Predicted effect`. Test runner `.venv/bin/python -B -m unittest`; full `discover`; apples-to-apples in `/home/rohit/maez`. **v1b (curiosity-curated durable memory) is deferred** — do NOT add a durable screen-write in this slice.

---

## File Structure

| File | Change |
|------|--------|
| `skills/screen_perception.py` | `ScreenObservation` new fields/states; `_is_paused()` + pause gate; `_is_excluded_active_window()` + preflight gate; `THIRD_PARTY` vision field + parse; `_apply_screen_governance()` (third-party minimization + origin); honest-blind format. |
| `core/egress/gate.py` | Add `owner_screen_context` to `MINIMIZABLE_PRIVATE_CONTEXT`. |
| `daemon/maez_daemon.py` | **Remove** the unconditional durable screen-storage append (`:8443` `format_for_memory()` screen_note). |
| `tests/test_screen_perception_v1a.py` | All v1a tests (preflight headline, pause, third-party, states, egress, no-storage). |

**Reused:** `core/memory/ambient.active_window`, `core/egress/gate.decide_egress`.

---

## Task 1: `ScreenObservation` — new fields + states + honest-blind

**Files:**
- Modify: `skills/screen_perception.py`
- Test: `tests/test_screen_perception_v1a.py`

- [ ] **Step 1: Extend the dataclass + states**

In `ScreenObservation` (skills/screen_perception.py ~80), add two fields (with defaults, after `state`):

```python
    state: str = "error"
    third_party_content_present: bool = False
    egress_origin_class: str = "owner_screen_context"
```

Add the new states to the docstring vocab and to `format_for_context()` so `paused`/`excluded` are honest-blind (no detail). In `format_for_context()`, after the `disabled` branch:

```python
        if self.state == "paused":
            return "[SCREEN] paused by owner (no capture)"
        if self.state == "excluded":
            return "[SCREEN] excluded — sensitive app in focus (not captured)"
```

- [ ] **Step 2: Write the failing test**

```python
# tests/test_screen_perception_v1a.py
from __future__ import annotations

import unittest
from skills.screen_perception import ScreenObservation


class ScreenObservationShapeTests(unittest.TestCase):
    def _obs(self, **kw):
        base = dict(activity="", application="", detail="", focus_level="",
                    raw_response="", timestamp=0.0, success=False)
        base.update(kw)
        return ScreenObservation(**base)

    def test_new_fields_default(self):
        o = self._obs(state="ok", success=True, activity="coding")
        self.assertFalse(o.third_party_content_present)
        self.assertEqual(o.egress_origin_class, "owner_screen_context")

    def test_paused_and_excluded_are_honest_blind(self):
        for st in ("paused", "excluded"):
            o = self._obs(state=st, detail="SHOULD_NOT_APPEAR")
            ctx = o.format_for_context()
            self.assertNotIn("SHOULD_NOT_APPEAR", ctx)  # blind states carry no detail
```

- [ ] **Step 3: Run → pass.** `.venv/bin/python -B -m unittest tests.test_screen_perception_v1a.ScreenObservationShapeTests -v`

- [ ] **Step 4: Commit**

```bash
git add skills/screen_perception.py tests/test_screen_perception_v1a.py
git commit -m "feat(body): screen obs v1a fields + honest-blind paused/excluded states

Add third_party_content_present + egress_origin_class; paused/excluded render
no detail. Tooling/dormant. Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2: Pause primitive (deterministic, no-restart, top of `observe()`)

**Files:**
- Modify: `skills/screen_perception.py`
- Test: `tests/test_screen_perception_v1a.py`

- [ ] **Step 1: Add `_is_paused()` + gate it FIRST in `observe()`**

```python
# near _is_enabled() in skills/screen_perception.py
import os

def _pause_file() -> str:
    return os.environ.get(
        "MAEZ_SCREEN_PAUSE_FILE",
        os.path.expanduser("~/.config/maez/screen_perception.paused"),
    )

def _is_paused() -> bool:
    # Deterministic, no-restart: touch the file to close the eye, remove to reopen.
    return os.path.exists(_pause_file())
```

In `observe()`, **before** the `_is_enabled()` check (so pause wins even when enabled), insert:

```python
    timestamp = time.time()

    if _is_paused():
        return ScreenObservation(
            activity="", application="", detail="", focus_level="",
            raw_response="", timestamp=timestamp, success=False,
            state="paused", error="screen perception paused by owner",
        )
```

- [ ] **Step 2: Write the failing test (no capture/probe/call when paused)**

```python
# tests/test_screen_perception_v1a.py
import os, tempfile
from unittest import mock
import skills.screen_perception as sp


class PausePrimitiveTests(unittest.TestCase):
    def test_paused_skips_capture_probe_vision(self):
        tmp = tempfile.mkdtemp()
        pause = os.path.join(tmp, "paused")
        open(pause, "w").close()
        with mock.patch.dict(os.environ, {
            "MAEZ_SCREEN_PERCEPTION": "1", "MAEZ_SCREEN_PAUSE_FILE": pause,
        }, clear=False), \
             mock.patch.object(sp, "_capture_screenshot") as cap, \
             mock.patch.object(sp, "_vision_endpoint_probe") as probe, \
             mock.patch.object(sp.requests, "post") as post:
            obs = sp.observe()
        self.assertEqual(obs.state, "paused")
        cap.assert_not_called(); probe.assert_not_called(); post.assert_not_called()
```

- [ ] **Step 3: Run → pass.** `.venv/bin/python -B -m unittest tests.test_screen_perception_v1a.PausePrimitiveTests -v`

- [ ] **Step 4: Commit**

```bash
git add skills/screen_perception.py tests/test_screen_perception_v1a.py
git commit -m "feat(body): screen pause primitive (file-based, no-restart, gates before capture)

paused => state=paused, zero screenshot/probe/vision. Touch/rm the pause file
live. Tooling/dormant. Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 3: Preflight sensitive-app exclusion — the HEADLINE (never-looked)

**Files:**
- Modify: `skills/screen_perception.py`
- Test: `tests/test_screen_perception_v1a.py`

- [ ] **Step 1: Add the exclusion set + `_is_excluded_active_window()` + gate it BEFORE probe/capture**

```python
# skills/screen_perception.py
# Default sensitive-app exclusions (Decision 9 hard exclusion). Matched
# case-insensitively against the active window's WM_CLASS and title.
# Extend via MAEZ_SCREEN_EXCLUDE (comma-separated substrings).
_DEFAULT_EXCLUDE = (
    "keepassxc", "bitwarden", "1password", "gnome-keyring",   # credentials
    "signal", "whatsapp", "telegram", "slack",                # private messages
    "zoom", "meet.google", "teams",                           # calls (v1a: treat as excluded)
    "bank", "chase", "wellsfargo", "fidelity", "vanguard",    # finance (title substrings)
    "mychart", "health", "patient",                           # medical (title substrings)
)

def _exclusion_terms() -> tuple[str, ...]:
    extra = os.environ.get("MAEZ_SCREEN_EXCLUDE", "")
    extra_terms = tuple(t.strip().lower() for t in extra.split(",") if t.strip())
    return _DEFAULT_EXCLUDE + extra_terms

def _is_excluded_active_window() -> bool:
    """Preflight: decide WITHOUT capturing. Uses the cheap X11 active-window
    class/title only. Fail-safe: if the active window CAN be read and matches
    an exclusion term, exclude. (If active_window is unavailable, we do NOT
    exclude here — the vision probe/capture gates still apply; v1a errs toward
    not-capturing only on a positive match.)"""
    from core.memory.ambient import active_window
    win = active_window()
    if not win:
        return False
    hay = f"{win.get('class','')} {win.get('title','')}".lower()
    return any(term in hay for term in _exclusion_terms())
```

In `observe()`, **after** the pause + `_is_enabled()` checks but **before** `_vision_endpoint_probe()` / `_capture_screenshot()`:

```python
    if _is_excluded_active_window():
        return ScreenObservation(
            activity="", application="", detail="", focus_level="",
            raw_response="", timestamp=timestamp, success=False,
            state="excluded", error="sensitive app in focus (preflight exclusion)",
        )
```

- [ ] **Step 2: Write the failing HEADLINE test (excluded ⇒ capture + vision NEVER invoked)**

```python
# tests/test_screen_perception_v1a.py
class PreflightExclusionTests(unittest.TestCase):
    def test_excluded_app_is_never_looked_at(self):
        with mock.patch.dict(os.environ, {"MAEZ_SCREEN_PERCEPTION": "1"}, clear=False), \
             mock.patch("core.memory.ambient.active_window",
                        return_value={"class": "KeePassXC", "title": "vault"}), \
             mock.patch.object(sp, "_vision_endpoint_probe") as probe, \
             mock.patch.object(sp, "_capture_screenshot") as cap, \
             mock.patch.object(sp.requests, "post") as post:
            obs = sp.observe()
        self.assertEqual(obs.state, "excluded")
        # THE PROOF: don't even look — no probe, no screenshot, no vision call.
        probe.assert_not_called(); cap.assert_not_called(); post.assert_not_called()

    def test_non_excluded_app_proceeds_to_capture(self):
        with mock.patch.dict(os.environ, {"MAEZ_SCREEN_PERCEPTION": "1"}, clear=False), \
             mock.patch("core.memory.ambient.active_window",
                        return_value={"class": "code", "title": "plan.md"}), \
             mock.patch.object(sp, "_vision_endpoint_probe", return_value=False) as probe:
            obs = sp.observe()
        probe.assert_called()  # not excluded → reached the probe stage
        self.assertEqual(obs.state, "unavailable")  # probe stubbed False
```

- [ ] **Step 3: Run → pass.** `.venv/bin/python -B -m unittest tests.test_screen_perception_v1a.PreflightExclusionTests -v`. The first test is the slice's spine — `excluded` means *never-looked*.

- [ ] **Step 4: Commit**

```bash
git add skills/screen_perception.py tests/test_screen_perception_v1a.py
git commit -m "feat(body): preflight sensitive-app exclusion (never-looked, before capture)

active_window() class/title checked BEFORE probe/capture/vision; excluded =>
state=excluded with ZERO screenshot/probe/vision (Decision 9 hard exclusion,
not capture-then-discard). Tooling/dormant.
Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 4: THIRD_PARTY vision field + minimization before prompt

**Files:**
- Modify: `skills/screen_perception.py`
- Test: `tests/test_screen_perception_v1a.py`

- [ ] **Step 1: Add the THIRD_PARTY field to the vision prompt + parse it**

Append to `VISION_PROMPT` (after the FOCUS_LEVEL line):

```
THIRD_PARTY: [yes | no — is private content authored by OTHER people visible (a message, email, chat, or call from someone other than the owner)? Answer yes if unsure.]
```

In `_parse_vision_response`, add (and seed the default to the fail-safe `yes`-on-missing only via the governance step, not here):

```python
        elif line.startswith('THIRD_PARTY:'):
            result['third_party'] = line[12:].strip().lower()
```
and add `"third_party": ""` to the `result` defaults dict.

- [ ] **Step 2: Add `_apply_screen_governance()` + call it after parse in `observe()`**

```python
# skills/screen_perception.py
_THIRD_PARTY_APP_HINTS = ("signal", "whatsapp", "telegram", "slack", "mail",
                          "thunderbird", "gmail", "outlook", "messages", "discord")

def _looks_third_party(parsed: dict) -> bool:
    # Fail-safe: vision said yes, OR an app hint, OR the vision flag is missing/uncertain.
    flag = (parsed.get("third_party") or "").strip().lower()
    app = (parsed.get("application") or "").lower()
    if flag in ("yes", "true", "unsure", "uncertain", ""):
        if flag in ("yes", "true", "unsure", "uncertain"):
            return True
        # flag empty/missing → only treat as third-party if an app hint matches
    if any(h in app for h in _THIRD_PARTY_APP_HINTS):
        return True
    return flag in ("yes", "true", "unsure", "uncertain")

def _apply_screen_governance(parsed: dict, *, timestamp: float, raw: str) -> ScreenObservation:
    third_party = _looks_third_party(parsed)
    detail = parsed["detail"]
    origin = "owner_screen_context"
    if third_party:
        # Minimize: drop the detail (where a person/message would smuggle in);
        # never build a person-model. Escalate egress origin.
        detail = "[minimized: third-party content present]"
        origin = "third_party_private_context"
    return ScreenObservation(
        activity=parsed["activity"], application=parsed["application"],
        detail=detail, focus_level=parsed["focus_level"],
        raw_response=raw, timestamp=timestamp, success=True, state="ok",
        third_party_content_present=third_party, egress_origin_class=origin,
    )
```

In `observe()`, replace the success-path `return ScreenObservation(... state="ok")` (after `parsed = _parse_vision_response(raw)`) with:

```python
        parsed = _parse_vision_response(raw)
        return _apply_screen_governance(parsed, timestamp=timestamp, raw=raw)
```

- [ ] **Step 3: Write the failing test**

```python
# tests/test_screen_perception_v1a.py
class ThirdPartyMinimizationTests(unittest.TestCase):
    def test_third_party_detail_is_minimized(self):
        parsed = {"activity": "reading email", "application": "thunderbird",
                  "detail": "Email from Jane Doe about the lawsuit settlement",
                  "focus_level": "browsing", "third_party": "yes"}
        obs = sp._apply_screen_governance(parsed, timestamp=0.0, raw="r")
        self.assertTrue(obs.third_party_content_present)
        self.assertEqual(obs.egress_origin_class, "third_party_private_context")
        self.assertNotIn("Jane", obs.detail)
        self.assertNotIn("lawsuit", obs.detail)
        self.assertNotIn("Jane", obs.format_for_context())

    def test_uncertain_treated_as_third_party(self):
        parsed = {"activity": "x", "application": "unknown", "detail": "d",
                  "focus_level": "x", "third_party": ""}  # vision didn't answer
        # app hint absent + flag missing → not auto-third-party; but an app hint forces it:
        parsed2 = {**parsed, "application": "Signal", "third_party": ""}
        self.assertTrue(sp._looks_third_party(parsed2))
        self.assertTrue(sp._looks_third_party({**parsed, "third_party": "unsure"}))

    def test_owner_only_keeps_detail(self):
        parsed = {"activity": "coding", "application": "code",
                  "detail": "editing plan.md", "focus_level": "deep_work",
                  "third_party": "no"}
        obs = sp._apply_screen_governance(parsed, timestamp=0.0, raw="r")
        self.assertFalse(obs.third_party_content_present)
        self.assertEqual(obs.egress_origin_class, "owner_screen_context")
        self.assertIn("plan.md", obs.detail)
```

- [ ] **Step 4: Run → pass.** `.venv/bin/python -B -m unittest tests.test_screen_perception_v1a.ThirdPartyMinimizationTests -v`

- [ ] **Step 5: Commit**

```bash
git add skills/screen_perception.py tests/test_screen_perception_v1a.py
git commit -m "feat(body): third-party minimization before prompt (flag + minimize + escalate)

Vision THIRD_PARTY field + app heuristic; uncertain->third-party (fail-safe);
on flag, drop detail + never a person-model + origin->third_party_private_context.
Tooling/dormant. Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 5: Egress origin — `owner_screen_context` redacts at the door

**Files:**
- Modify: `core/egress/gate.py`
- Test: `tests/test_screen_perception_v1a.py`

- [ ] **Step 1: Add the origin to `MINIMIZABLE_PRIVATE_CONTEXT`**

In `core/egress/gate.py` (~line 24):

```python
MINIMIZABLE_PRIVATE_CONTEXT = {
    "memory",
    "lived_store",
    "owner_message_context",
    "third_party_private_context",
    "owner_screen_context",
}
```

(Match the existing exact member set — add only `owner_screen_context`.)

- [ ] **Step 2: Write the failing test (the door redacts screen origins)**

```python
# tests/test_screen_perception_v1a.py
class ScreenEgressOriginTests(unittest.TestCase):
    def _decide(self, origin):
        from core.egress.gate import EgressRequest, EgressSegment, decide_egress
        return decide_egress(EgressRequest(
            call_class="cloud_model_inference", destination="anthropic",
            segments=[EgressSegment(text="email a@b.test", origin_class=origin,
                                    source_ref="raw:screen", redaction_allowed=True)],
            caller="screen-v1a", request_id="t"))

    def test_owner_screen_context_redacts(self):
        d = self._decide("owner_screen_context")
        self.assertEqual(d.decision, "redact")
        self.assertNotIn("a@b.test", d.sanitized_text())

    def test_third_party_private_context_redacts(self):
        self.assertEqual(self._decide("third_party_private_context").decision, "redact")
```

- [ ] **Step 3: Run → pass.** `.venv/bin/python -B -m unittest tests.test_screen_perception_v1a.ScreenEgressOriginTests -v`. (The door is *enforcing* live as of this morning, so this redact is real, not shadow.)

- [ ] **Step 4: Confirm the gate's own suite still passes**

Run: `.venv/bin/python -B -m unittest tests.test_privacy_egress_gate tests.test_recall_origin_egress_canary 2>&1 | tail -3`
Expected: PASS (adding a member to MINIMIZABLE_PRIVATE_CONTEXT is additive).

- [ ] **Step 5: Commit**

```bash
git add core/egress/gate.py tests/test_screen_perception_v1a.py
git commit -m "feat(egress): owner_screen_context origin (minimizable; redacts at the door)

Screen-derived content classified redactable; the now-enforcing door masks it
cloudward; third-party -> third_party_private_context.
Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 6: Remove the unconditional durable screen storage (daemon) — `## Predicted effect`

**Files:**
- Modify: `daemon/maez_daemon.py`
- Test: `tests/test_screen_perception_v1a.py`

- [ ] **Step 1: Remove the screen-memory append at `:8443`**

Find the block around `daemon/maez_daemon.py:8443`:

```python
                    screen_note = f" | {self._last_screen_obs.format_for_memory()}"
```

Remove the `screen_note` construction AND its concatenation into the durable memory/thought string at that site (search for where `screen_note` is appended — drop both the assignment and the usage so screen content never enters the durable write). Replace with nothing (screen context remains available for the *ephemeral* cycle prompt via `format_for_context()` at `:4360`, which is unchanged — that's in-cycle, not durable).

- [ ] **Step 2: Write the failing guard test (no durable screen seam remains)**

```python
# tests/test_screen_perception_v1a.py
from pathlib import Path

class NoDurableScreenStorageTests(unittest.TestCase):
    def test_format_for_memory_not_appended_in_daemon(self):
        # v1a invariant: no unconditional durable screen-memory write.
        src = Path("daemon/maez_daemon.py").read_text()
        self.assertNotIn("format_for_memory()", src,
                         "v1a must not append screen observations to durable memory")
```

- [ ] **Step 3: Run → pass.** `.venv/bin/python -B -m unittest tests.test_screen_perception_v1a.NoDurableScreenStorageTests -v` then `.venv/bin/python -B -m py_compile daemon/maez_daemon.py`. (If `format_for_memory` is referenced elsewhere in the daemon, scope the assertion to the screen-note site; the intent is: no screen observation enters durable memory.)

- [ ] **Step 4: Commit (carries `## Predicted effect`)**

```bash
git add daemon/maez_daemon.py tests/test_screen_perception_v1a.py
git commit -m "feat(body): remove unconditional durable screen storage (v1a ephemeral-only)

Screen observations no longer append into durable daemon memory; screen
context is in-cycle/ephemeral only. Durable curiosity-curated screen memory is
v1b.

## Predicted effect
Default MAEZ_SCREEN_PERCEPTION unset -> dormant, no change. WHEN ENABLED (=1):
Maez sees + thinks with governed Level-2 screen summaries — excluded apps are
never captured (preflight), third-party content is flagged+minimized before the
prompt (never a person-model), screen-derived prompt content is tagged
owner_screen_context/third_party_private_context so the now-enforcing door
redacts it cloudward, a pause file closes the eye without restart, and NO screen
observation persists to memory (ephemeral, in-cycle only). Falsifiable: excluded
app -> zero screenshots; private message -> minimized prompt detail; cloud call
with screen context -> redacted; no screen memory row appears.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 7: Full-suite green + apples-to-apples

**Files:** none

- [ ] **Step 1: The v1a module** — `.venv/bin/python -B -m unittest tests.test_screen_perception_v1a -v` → all classes PASS.
- [ ] **Step 2: Full discover** — `.venv/bin/python -B -m unittest discover -s tests 2>&1 | tail -6` → zero new failures attributable to this slice; run in `/home/rohit/maez`. Live-judge flaky floor wobbles ±1-2.
- [ ] **Step 3: Confirm dormant + read-only** — `git grep -n "MAEZ_SCREEN_PERCEPTION" skills/ daemon/` shows the default-off gate; confirm `observe()` returns `disabled` when unset; `git status --porcelain memory/db` empty.

---

## Self-Review (against the spec)

**Spec coverage:**
- §2.1 preflight exclusion (before capture) → Task 3 (headline test asserts capture+vision never invoked). ✓
- §2.2 owner_screen_context egress origin + tagging → Task 5 (gate) + Task 4 (`egress_origin_class` on the obs). ✓
- §2.3 third-party minimization before prompt → Task 4 (flag + minimize + escalate + uncertain→third-party + no person-model). ✓
- §2.4 pause primitive (no capture/probe/call) → Task 2. ✓
- §2.5 NO durable storage → Task 6 (remove the `:8443` append + the guard test). ✓
- §2.6 default-off preserved → unchanged `_is_enabled()`; Task 7 Step 3. ✓
- §4 states (paused/excluded honest-blind) → Task 1. ✓
- §6.8 `## Predicted effect` → Task 6 commit. ✓

**Placeholder scan:** none. One bounded implementer-judgment (Task 6: if `format_for_memory` is referenced elsewhere, scope the guard to the screen-note site) is flagged with the intent, not a placeholder.

**Type consistency:** `ScreenObservation(... third_party_content_present, egress_origin_class)`, `_is_paused`, `_pause_file`, `_is_excluded_active_window`, `_exclusion_terms`, `_looks_third_party`, `_apply_screen_governance(parsed, *, timestamp, raw)`, the `"paused"/"excluded"` states, and `MINIMIZABLE_PRIVATE_CONTEXT` membership — consistent across Tasks 1-6. The origin strings (`owner_screen_context`, `third_party_private_context`) match the gate. ✓

**Ordering note for the implementer:** Tasks gate `observe()` in this order — **pause → enabled → preflight-exclusion → probe → capture → vision → governance.** The preflight MUST sit before probe/capture (Task 3); the pause MUST sit before everything (Task 2). Keep that order when editing `observe()`.
