# Capability State / Voice Boundary v0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop Maez from describing its own body in dashboard prose ("YOUR LIVE BODY", "gatekeeper mode") and stop owner slash commands being improvised by the brain — by feeding self-knowledge as *structured state the self speaks in its own voice*, and handling commands deterministically.

**Architecture:** One strict flag `MAEZ_VOICE_BOUNDARY_ENABLED` gates three changes. **Component A+B** live inside the single function both prompt paths already call — `core/cognition/capability_card.py::capability_prompt_block()` — so the daemon path and the focused-cognition path change *identically and automatically* (this is the strongest possible implementation of the spec's "both paths or the wound survives in one"). Flag-off returns the exact old prose, byte-identical. Flag-on returns a structured capability-state envelope followed by a voice-boundary instruction. **Component C** intercepts `/proposals` and `/show` in `skills/surface/telegram_adapter.py::_handle_command` *before* the `handle_message` fallthrough, reusing the live MaezMessageHandler instance's Surface-Parity data accessors and its shared last-shown store so a following natural-language "yes" still binds.

**Tech Stack:** Python 3.14, stdlib only (no new deps). Test runner: `/home/rohit/maez/.venv/bin/python -B -m unittest` (NOT pytest). Telegram surface via `python-telegram-bot` (already present). Flask embedded daemon HTTP brain bench at `127.0.0.1:11435` for A/B witness.

**Lane:** Codex implements (zero-context) / Claude reviews (covenant axis — this is Maez's voice about its own body + the owner's command surface). Branch: `capability-state-voice-boundary-v0`. main is local-only @24c7373 — **no push**. STOP at the review gate (owner breaths for merge/flag/restart).

---

## File Structure

| File | Responsibility | Change |
|---|---|---|
| `core/cognition/capability_card.py` | Self-knowledge feed. Adds strict flag `voice_boundary_enabled()`; `capability_prompt_block()` branches prose vs envelope+instruction. | Modify |
| `core/dispatcher/proposal_commands.py` | **New.** Pure deterministic formatters for `/proposals` listing and `/show <id>` detail (testable without a Telegram `Update`). | Create |
| `skills/surface/telegram_adapter.py` | Component C1: intercept `/proposals` / `/show` in `_handle_command` before the `handle_message(event)` fallthrough (`:2762`). | Modify |
| `skills/surface/maez_adapter.py` | Component C2: **no functional change** — only a regression guard test that natural `show #N`/`yes`/`reject #N` stays here and still binds. | Test-only |
| `core/routing/focused_cognition.py` / `daemon/maez_daemon.py` | Capability-card consumers. **No code change** — they already call `capability_prompt_block()`; coverage tests prove both receive A+B. | Test-only (guard) |
| `docs/MAEZ_BUILD_LEDGER.md` | Ledger rows updated at the gate (maintenance law). | Modify (Task 6) |

---

## Task 0: Proof obligations (the wrong-seam pattern has bitten 4+ times — verify, do not guess)

**No feature wiring until these are recorded.** All five were discharged during planning; this task is the implementer re-confirming them against the live tree before writing code. If any line number has drifted, adjust and note it — do not encode a stale number.

**Files:** read-only (`grep`/`sed`).

- [ ] **Step 0a: Confirm the TWO capability-card consumers.**

```bash
cd /home/rohit/maez
grep -nE "_capability_block|capability_prompt_block" daemon/maez_daemon.py
grep -nE "_focused_capability_card|capability_prompt_block|_voice_card" core/routing/focused_cognition.py
```
Expected (verified @24c7373): daemon assigns `_capability_block = capability_prompt_block()` at **:5770**, folds it into `ambient_block` at :5784. focused defines `_focused_capability_card()` at **:208**, calls `capability_prompt_block()` at **:214**, consumed via `_voice_card(surface)` at :881 (used at 908/986/1209 — all funnel through the single `_focused_capability_card()`).
**Adjust-rule:** if either line moved, record the new line. The load-bearing fact — *both* paths call `capability_prompt_block()` and nothing else builds the card — must still hold; if a third caller appears, STOP and escalate (the single-function design depends on exactly these two consumers).

- [ ] **Step 0b: Confirm the C1 seam.**

```bash
grep -nE "def _handle_command|/receipts|_try_handle_dream_command_event|await self.handle_message|filters.COMMAND|filters.TEXT" skills/surface/telegram_adapter.py | head
```
Expected: `_handle_command` at **:2742**; `/receipts` at :2752; dream at :2760; fallthrough `await self.handle_message(event)` at **:2762**. Filters split :909-913 (`TEXT & ~COMMAND → _handle_text_message`; `COMMAND → _handle_command`) — `_handle_command` is the ONLY slash sink. **C1 interception goes immediately before :2762.**
**Adjust-rule:** if the fallthrough line moved, the rule is unchanged — intercept right before the line that reads `await self.handle_message(event)` inside `_handle_command`.

- [ ] **Step 0c: Confirm the card signature, cache, and retired prose strings.**

```bash
sed -n '16,108p' core/cognition/capability_card.py
```
Expected: `_CARD_TTL_S = 30.0`; `_CARD_CACHE`; `reset_card_cache()`; `capability_prompt_block(registry=None) -> str` returns `""` when `not evidence_precedence_enabled()`, else cached-or-built prose. Retired INPUT strings (old shape, not a Maez word-ban): `"YOUR LIVE BODY (live/cached substrate probe)"` and `"gatekeeper mode"` (the `search commitment` on-text at :71). Registry: `web sense`, `page read`, `recall`, `search commitment`, `felt time`.
**Critical nuance:** the card only renders at all when `MAEZ_EVIDENCE_PRECEDENCE_ENABLED` is on. The voice-boundary flag toggles the render *form* within that. So byte-identity has three cells: (precedence off → `""` regardless of voice flag); (precedence on + voice off → old prose); (precedence on + voice on → envelope+instruction).

- [ ] **Step 0d: Confirm C1's reuse sources + the shared last-shown store.**

```bash
grep -nE "_surface_parity_pending_evolution_candidates|_surface_parity_pending_dream_rows|_last_shown_proposal" skills/surface/maez_adapter.py | head
grep -nE "def set_message_handler|self._message_handler|async def handle_message" skills/surface/platform_base.py | head
sed -n '40,42p' core/dispatcher/proposal_resolver.py
```
Expected: MaezMessageHandler (maez_adapter) exposes `_surface_parity_pending_evolution_candidates() -> list[dict]` (:222; dict keys include `id`, `weakness`, `target_file`), `_surface_parity_pending_dream_rows() -> list[tuple]` (:245; tuples `(pid, created, insight)`), and the instance attribute `_last_shown_proposal: dict[chat_id, {"id":int,"source":str,"shown_at":float}]` (:179, written :385/:465). The adapter reaches this instance as `self._message_handler` (set in `platform_base.set_message_handler` :1097; invoked by `handle_message` :1745). Last-shown `source` literals are exactly **`"evolution"`** and **`"dream"`** (matching `proposal_resolver._CONTEXT_WORDS` keys at :40-41 and the C2 writes at :385/:465).
**Adjust-rule:** C1 must reach the SAME instance (`self._message_handler`) for both the pending-data accessors and the last-shown write. If `self._message_handler` is not a `MaezMessageHandler` at runtime (e.g. None before wiring), C1 falls through to today's behavior (see Task 4 Step 7). Verify with the grep; do not hardcode a different handle.

- [ ] **Step 0e: Create the branch.**

```bash
cd /home/rohit/maez
git checkout -b capability-state-voice-boundary-v0
git rev-parse --abbrev-ref HEAD   # expect: capability-state-voice-boundary-v0
git log --oneline -1              # expect main tip 24c7373 as parent
```

---

## Task 1: Strict flag `voice_boundary_enabled()`

**Files:**
- Modify: `core/cognition/capability_card.py` (add beside `evidence_precedence_enabled` at :21)
- Test: `tests/test_voice_boundary_flag.py` (create)

The 0-truthy footgun (`bool(os.environ.get(...))` treats `"0"` as ON) is a named HAZARD. Reuse the strict pattern already proven in this file at `evidence_precedence_enabled()` (:21-27) and in `core/cognition/parity_flag.py::surface_parity_enabled()`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_voice_boundary_flag.py`:
```python
import os
import unittest

from core.cognition.capability_card import voice_boundary_enabled


class VoiceBoundaryFlagTest(unittest.TestCase):
    def setUp(self):
        self._saved = os.environ.get("MAEZ_VOICE_BOUNDARY_ENABLED")
        os.environ.pop("MAEZ_VOICE_BOUNDARY_ENABLED", None)

    def tearDown(self):
        if self._saved is None:
            os.environ.pop("MAEZ_VOICE_BOUNDARY_ENABLED", None)
        else:
            os.environ["MAEZ_VOICE_BOUNDARY_ENABLED"] = self._saved

    def test_unset_is_off(self):
        self.assertFalse(voice_boundary_enabled())

    def test_zero_is_off_not_truthy(self):
        os.environ["MAEZ_VOICE_BOUNDARY_ENABLED"] = "0"
        self.assertFalse(voice_boundary_enabled())  # the footgun this guards

    def test_false_no_off_are_off(self):
        for val in ("false", "no", "off", "", "  "):
            os.environ["MAEZ_VOICE_BOUNDARY_ENABLED"] = val
            self.assertFalse(voice_boundary_enabled(), val)

    def test_truthy_set_enables(self):
        for val in ("1", "true", "yes", "on", "ON", " True "):
            os.environ["MAEZ_VOICE_BOUNDARY_ENABLED"] = val
            self.assertTrue(voice_boundary_enabled(), val)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_voice_boundary_flag -v`
Expected: FAIL — `ImportError: cannot import name 'voice_boundary_enabled'`.

- [ ] **Step 3: Write minimal implementation**

In `core/cognition/capability_card.py`, immediately after `evidence_precedence_enabled()` (after :27):
```python
def voice_boundary_enabled() -> bool:
    """Strict parser: only ``1/true/yes/on`` enable. ``"0"`` is OFF.

    Deliberately rejects the house-wide ``bool(os.environ.get(...))`` footgun
    (``"0"`` would read truthy). Mirrors ``evidence_precedence_enabled``.
    """
    return (
        (os.environ.get("MAEZ_VOICE_BOUNDARY_ENABLED", "") or "")
        .strip()
        .lower()
        in {"1", "true", "yes", "on"}
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_voice_boundary_flag -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add core/cognition/capability_card.py tests/test_voice_boundary_flag.py
git commit -m "feat(voice-boundary): strict MAEZ_VOICE_BOUNDARY_ENABLED flag

Mirrors evidence_precedence_enabled's strict {1,true,yes,on} parser; rejects
the 0-truthy footgun. Reads only; gates Components A/B/C in later tasks.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2: Component A — capability-state envelope (with Component B instruction bundled)

**Files:**
- Modify: `core/cognition/capability_card.py::capability_prompt_block()` (:77-108)
- Test: `tests/test_voice_boundary_envelope.py` (create)

**Design decision (deviation-with-justification for review):** Components A *and* B are both emitted by `capability_prompt_block()`, the single function both prompt consumers call. The spec sketches two separate insertion points (daemon + focused) for B; bundling B into the same function that emits A is *strictly safer* — it makes "if only one path changes, the wound survives" structurally impossible, because there is exactly one render function and both paths already call it (proven in 0a). Daemon and focused-cognition need **zero** code changes. Task 3 proves both receive A+B.

The new metadata (`source` per entry: probe vs flag) is kept in an envelope-only map so the registry tuples stay byte-identical (protecting flag-off prose and existing `tests/test_capability_card.py` / `test_capability_registry.py`). Status values are the **raw probe outputs** (faithful to the Non-Goal "no change to the truth probes themselves except their rendered form").

- [ ] **Step 1: Write the failing tests**

Create `tests/test_voice_boundary_envelope.py`:
```python
import json
import os
import unittest

from core.cognition import capability_card
from core.cognition.capability_card import capability_prompt_block, reset_card_cache


def _fake_registry():
    return (
        ("web sense", lambda: "searxng healthy"),
        ("page read", lambda: "on"),
        ("search commitment", lambda: "gatekeeper mode"),
        ("felt time", lambda: "attached"),
    )


def _boom_registry():
    def _boom():
        raise RuntimeError("probe down")
    return (("web sense", _boom),)


class VoiceBoundaryEnvelopeTest(unittest.TestCase):
    OLD_PROSE_HEADER = "YOUR LIVE BODY (live/cached substrate probe)"

    def setUp(self):
        reset_card_cache()
        self._saved = {
            k: os.environ.get(k)
            for k in ("MAEZ_EVIDENCE_PRECEDENCE_ENABLED", "MAEZ_VOICE_BOUNDARY_ENABLED")
        }
        os.environ["MAEZ_EVIDENCE_PRECEDENCE_ENABLED"] = "1"  # card renders at all
        os.environ.pop("MAEZ_VOICE_BOUNDARY_ENABLED", None)

    def tearDown(self):
        reset_card_cache()
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    # --- flag OFF: byte-identical old prose ---
    def test_flag_off_returns_exact_old_prose(self):
        out = capability_prompt_block(registry=_fake_registry())
        self.assertIn(self.OLD_PROSE_HEADER, out)
        self.assertIn("search commitment: gatekeeper mode", out)
        self.assertNotIn("capability_state", out)

    def test_precedence_off_returns_empty_regardless_of_voice_flag(self):
        os.environ["MAEZ_EVIDENCE_PRECEDENCE_ENABLED"] = "0"
        os.environ["MAEZ_VOICE_BOUNDARY_ENABLED"] = "1"
        reset_card_cache()
        self.assertEqual(capability_prompt_block(registry=_fake_registry()), "")

    # --- flag ON: structured envelope + instruction ---
    def test_flag_on_emits_structured_envelope(self):
        os.environ["MAEZ_VOICE_BOUNDARY_ENABLED"] = "1"
        reset_card_cache()
        out = capability_prompt_block(registry=_fake_registry())
        # old INPUT shape is gone because the feed changed, not because a word is banned
        self.assertNotIn(self.OLD_PROSE_HEADER, out)
        # a parseable structured payload is present (schema, not word-blacklist)
        start = out.index("{")
        end = out.rindex("}") + 1
        payload = json.loads(out[start:end])
        self.assertEqual(payload["kind"], "capability_state")
        self.assertEqual(payload["freshness"], "live_or_cached_30s")
        self.assertEqual(payload["authority"], "current_self_capability_state")
        self.assertIn("outranks stale memory", payload["precedence"])
        names = {e["name"]: e for e in payload["entries"]}
        self.assertEqual(names["web sense"]["status"], "searxng healthy")
        self.assertEqual(names["web sense"]["source"], "probe")
        self.assertEqual(names["page read"]["source"], "flag")

    def test_flag_on_includes_voice_boundary_instruction(self):
        os.environ["MAEZ_VOICE_BOUNDARY_ENABLED"] = "1"
        reset_card_cache()
        out = capability_prompt_block(registry=_fake_registry())
        self.assertIn("private grounding", out)
        self.assertIn("Do not quote", out)
        self.assertIn("do not override this state", out)

    def test_flag_on_unknown_probe_is_explicit_not_missing(self):
        os.environ["MAEZ_VOICE_BOUNDARY_ENABLED"] = "1"
        reset_card_cache()
        out = capability_prompt_block(registry=_boom_registry())
        start = out.index("{"); end = out.rindex("}") + 1
        payload = json.loads(out[start:end])
        entry = payload["entries"][0]
        self.assertEqual(entry["status"], "unknown")
        self.assertEqual(entry["error"], "probe_error")

    def test_30s_cache_preserved_under_flag_on(self):
        os.environ["MAEZ_VOICE_BOUNDARY_ENABLED"] = "1"
        reset_card_cache()
        first = capability_prompt_block(registry=_fake_registry())
        # second call with a registry that would differ must return the cached first
        second = capability_prompt_block(registry=_boom_registry())
        self.assertEqual(first, second)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_voice_boundary_envelope -v`
Expected: the flag-ON tests FAIL (envelope not built yet); the two flag-OFF tests PASS (current behavior already correct).

- [ ] **Step 3: Implement the envelope branch**

In `core/cognition/capability_card.py`, add the source-map and the instruction constant near the top (after `_CARD_CACHE`, ~:18):
```python
# Envelope-only metadata: probe-vs-flag provenance per registry name.
# Kept separate from the registry tuples so those stay byte-identical (the
# flag-off prose and existing card tests depend on the 2-tuple shape).
_ENTRY_SOURCE = {
    "web sense": "probe",
    "page read": "flag",
    "recall": "flag",
    "search commitment": "flag",
    "felt time": "probe",
}

_VOICE_BOUNDARY_INSTRUCTION = (
    "Use CAPABILITY_STATE as private grounding about your current body. Do not "
    "quote its field names or diagnostic labels as your voice. If asked about "
    "your current body or capabilities, answer from this state in your own "
    "voice. Memories may explain what used to be true; they do not override "
    "this state."
)
```

Add a builder function (after `_default_registry`, ~:74):
```python
def _build_capability_envelope(
    registry: Sequence[tuple[str, Callable[[], str]]],
) -> str:
    """Structured capability-state envelope + voice-boundary instruction.

    Status is the raw probe output (rendered form only — no probe change).
    A failed probe renders an explicit ``unknown``/``probe_error`` entry; a
    MISSING entry would be a quieter lie than a visible unknown.
    """
    entries: list[dict[str, str]] = []
    for name, probe in registry:
        source = _ENTRY_SOURCE.get(name, "probe")
        try:
            entries.append({"name": name, "status": probe(), "source": source})
        except Exception:
            entries.append(
                {"name": name, "status": "unknown", "source": source, "error": "probe_error"}
            )
    payload = {
        "kind": "capability_state",
        "freshness": "live_or_cached_30s",
        "authority": "current_self_capability_state",
        "precedence": "for current body/capability questions, this outranks stale memory",
        "entries": entries,
    }
    import json as _json

    return (
        "CAPABILITY_STATE (current self-capability; private grounding):\n"
        + _json.dumps(payload, indent=2)
        + "\n"
        + _VOICE_BOUNDARY_INSTRUCTION
    )
```

Then branch inside `capability_prompt_block()` — replace the `try:` block body that builds `text` (the existing :88-105) so the form is chosen by the flag, while keeping the cache and the `evidence_precedence_enabled()` gate:
```python
    try:
        reg = registry if registry is not None else _default_registry()
        if voice_boundary_enabled():
            text = _build_capability_envelope(reg)
        else:
            entries: list[str] = []
            for name, probe in reg:
                try:
                    entries.append(f"{name}: {probe()}")
                except Exception:
                    entries.append(f"{name}: unknown (probe error)")
            text = (
                "YOUR LIVE BODY (live/cached substrate probe):\n "
                + " | ".join(entries)
                + "\n This is probed substrate state. It outranks any MEMORY of your former\n"
                " body or former tools. If a recalled memory disagrees with this card,\n"
                " the memory describes your past, not your present."
            )
        _CARD_CACHE["text"] = text
        _CARD_CACHE["ts"] = now
        return text
    except Exception:
        logger.debug("capability card build failed", exc_info=True)
        return ""
```
(The flag-off `else` branch is the exact original string — keep it character-for-character so flag-off stays byte-identical.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_voice_boundary_envelope -v`
Expected: PASS (all). Then the pre-existing card tests must stay green:
Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_capability_card tests.test_capability_registry -v`
Expected: PASS (flag-off byte-identity intact).

- [ ] **Step 5: Commit**

```bash
git add core/cognition/capability_card.py tests/test_voice_boundary_envelope.py
git commit -m "feat(voice-boundary): structured capability-state envelope + boundary instruction

## Predicted effect
With MAEZ_VOICE_BOUNDARY_ENABLED on (and precedence on), the capability card
feed changes from the 'YOUR LIVE BODY ... gatekeeper mode' prose paragraph to a
structured capability_state envelope (kind/freshness/authority/precedence/
entries) followed by a voice-boundary instruction. Because both the daemon
ambient block and focused-cognition voice card call this one function, both
prompt paths change together. Maez should describe its current body in its own
voice instead of echoing dashboard labels. Flag off: byte-identical old prose.
Failed probe renders an explicit unknown entry, never a missing line.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 3: Component B coverage — prove BOTH prompt paths receive A+B (no divergent path)

**Files:**
- Test: `tests/test_voice_boundary_both_paths.py` (create)

No production code changes — this task is the guard that the single-function design actually reaches both consumers, and that flag-off leaves both untouched. It encodes the spec's "if only one is changed, the wound survives in the other" as an executable invariant.

- [ ] **Step 1: Write the failing/guard tests**

Create `tests/test_voice_boundary_both_paths.py`:
```python
import os
import unittest

from core.cognition.capability_card import reset_card_cache


class VoiceBoundaryBothPathsTest(unittest.TestCase):
    """Both prompt consumers must emit the envelope+instruction under the flag,
    and neither may build the card by a path that bypasses capability_prompt_block.
    """

    def setUp(self):
        reset_card_cache()
        self._saved = {
            k: os.environ.get(k)
            for k in ("MAEZ_EVIDENCE_PRECEDENCE_ENABLED", "MAEZ_VOICE_BOUNDARY_ENABLED")
        }
        os.environ["MAEZ_EVIDENCE_PRECEDENCE_ENABLED"] = "1"

    def tearDown(self):
        reset_card_cache()
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def test_focused_path_emits_envelope_under_flag(self):
        os.environ["MAEZ_VOICE_BOUNDARY_ENABLED"] = "1"
        reset_card_cache()
        from core.routing.focused_cognition import _focused_capability_card
        card = _focused_capability_card()
        self.assertIn("capability_state", card)
        self.assertIn("private grounding", card)

    def test_focused_path_old_prose_flag_off(self):
        os.environ.pop("MAEZ_VOICE_BOUNDARY_ENABLED", None)
        reset_card_cache()
        from core.routing.focused_cognition import _focused_capability_card
        card = _focused_capability_card()
        self.assertIn("YOUR LIVE BODY", card)
        self.assertNotIn("capability_state", card)

    def test_both_consumers_call_one_render_function(self):
        # Structural guard: the only card builder is capability_prompt_block.
        # If a future edit inlines a second renderer, this catches the drift.
        import inspect
        import daemon.maez_daemon as d
        import core.routing.focused_cognition as f
        self.assertIn("capability_prompt_block", inspect.getsource(d))
        self.assertIn("capability_prompt_block", inspect.getsource(f._focused_capability_card))
```

- [ ] **Step 2: Run tests**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_voice_boundary_both_paths -v`
Expected: PASS (Task 2 already made the envelope flow through `capability_prompt_block`; these tests confirm both consumers inherit it). If `test_focused_path_emits_envelope_under_flag` FAILS, the focused path is not calling `capability_prompt_block` as proven in 0a — STOP and re-verify 0a, do not patch focused with a second renderer.

- [ ] **Step 3: Commit**

```bash
git add tests/test_voice_boundary_both_paths.py
git commit -m "test(voice-boundary): guard that both prompt paths inherit A+B from one function

Encodes the spec invariant 'if only one path changes, the wound survives' as an
executable check: the focused-cognition card and the daemon both render via
capability_prompt_block, so the envelope+instruction reach both, and flag-off
leaves both as the old prose.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 4: Component C1 — deterministic `/proposals` and `/show` in `_handle_command`

**Files:**
- Create: `core/dispatcher/proposal_commands.py` (pure formatters)
- Modify: `skills/surface/telegram_adapter.py::_handle_command` (before the `:2762` fallthrough)
- Test: `tests/test_voice_boundary_commands.py` (create)

C1 reuses the live `MaezMessageHandler` instance (`self._message_handler`) for pending data and for the shared last-shown store. Slash handling must **not** call the brain. `/show <id>` records last-shown with the exact shape/source C2 reads (`{"id":int,"source":"evolution"|"dream","shown_at":float}`).

- [ ] **Step 1: Write the failing tests for the pure formatters**

Create `tests/test_voice_boundary_commands.py`:
```python
import unittest

from core.dispatcher.proposal_commands import (
    render_proposals_listing,
    render_proposal_detail,
    parse_show_id,
)


class ProposalCommandFormatterTest(unittest.TestCase):
    EVO = [{"id": 22, "weakness": "cannot summarize long pages", "target_file": "x.py"}]
    DREAM = [(7, "2026-06-10", "I keep losing the thread after a tool call")]

    def test_listing_lists_both_kinds_deterministically(self):
        out = render_proposals_listing(self.EVO, self.DREAM)
        self.assertIn("#22", out)
        self.assertIn("#7", out)
        self.assertIn("cannot summarize", out)
        # deterministic: same input -> same output
        self.assertEqual(out, render_proposals_listing(self.EVO, self.DREAM))

    def test_listing_empty_is_honest(self):
        out = render_proposals_listing([], [])
        self.assertIn("no pending proposals", out.lower())

    def test_detail_evolution(self):
        out, source = render_proposal_detail(22, self.EVO, self.DREAM)
        self.assertEqual(source, "evolution")
        self.assertIn("#22", out)
        self.assertIn("cannot summarize", out)

    def test_detail_dream(self):
        out, source = render_proposal_detail(7, self.EVO, self.DREAM)
        self.assertEqual(source, "dream")
        self.assertIn("#7", out)
        self.assertIn("losing the thread", out)

    def test_detail_missing(self):
        out, source = render_proposal_detail(99, self.EVO, self.DREAM)
        self.assertIsNone(source)
        self.assertIn("99", out)
        self.assertIn("don't", out.lower())

    def test_parse_show_id(self):
        self.assertEqual(parse_show_id("/show 22"), 22)
        self.assertEqual(parse_show_id("/show #22"), 22)
        self.assertEqual(parse_show_id("/show@maezbot 22"), 22)
        self.assertIsNone(parse_show_id("/show"))
        self.assertIsNone(parse_show_id("/show xyz"))
```

- [ ] **Step 2: Run to verify they fail**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_voice_boundary_commands -v`
Expected: FAIL — module `core.dispatcher.proposal_commands` does not exist.

- [ ] **Step 3: Implement the pure formatters**

Create `core/dispatcher/proposal_commands.py`:
```python
"""Deterministic renderers for the /proposals and /show slash commands.

Pure functions over the Surface-Parity pending-data shapes so they are testable
without a Telegram Update and never call the brain. The adapter (C1) supplies
the data via the live MaezMessageHandler instance.
"""
from __future__ import annotations

import re
from typing import Optional

# evolution candidates: list[dict] with keys id, weakness, target_file
# dream rows: list[tuple] (pid, created, insight)


def parse_show_id(text: str) -> Optional[int]:
    """Extract the integer id from '/show 22', '/show #22', '/show@bot 22'."""
    m = re.search(r"/show(?:@\S+)?\s+#?(\d+)\b", (text or "").strip())
    return int(m.group(1)) if m else None


def render_proposals_listing(evolution: list[dict], dream: list[tuple]) -> str:
    if not evolution and not dream:
        return "You have no pending proposals right now."
    lines = [f"{len(evolution) + len(dream)} pending proposal(s):", ""]
    for row in evolution[:10]:
        lines.append(f"  #{row['id']}: {(row.get('weakness') or '')[:80]}")
    for pid, _created, insight in dream[:10]:
        lines.append(f"  #{pid}: {(insight or '')[:80]}")
    lines.append("")
    lines.append('Use /show <id> for detail, then reply "yes to #<id>" or "reject #<id>".')
    return "\n".join(lines)


def render_proposal_detail(
    proposal_id: int, evolution: list[dict], dream: list[tuple]
) -> tuple[str, Optional[str]]:
    """Return (text, source) where source is 'evolution'|'dream'|None(not found)."""
    for row in evolution:
        if int(row["id"]) == proposal_id:
            body = row.get("weakness") or ""
            target = row.get("target_file") or ""
            text = f"Proposal #{proposal_id} (growth):\n{body}"
            if target:
                text += f"\n(target: {target})"
            text += '\n\nReply "yes" to approve or "reject #%d".' % proposal_id
            return text, "evolution"
    for pid, _created, insight in dream:
        if int(pid) == proposal_id:
            text = (
                f"Proposal #{proposal_id} (dream):\n{(insight or '')[:500]}"
                f'\n\nReply "yes" to approve or "reject #{proposal_id}".'
            )
            return text, "dream"
    return (f"I don't see a pending proposal #{proposal_id}. It may already be resolved.", None)
```

- [ ] **Step 4: Run to verify the formatters pass**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_voice_boundary_commands -v`
Expected: PASS.

- [ ] **Step 5: Write the failing test for the `_handle_command` interception (no brain call)**

Append to `tests/test_voice_boundary_commands.py`:
```python
import asyncio
import os
import types


class FakeMaezHandler:
    def __init__(self, evo, dream):
        self._evo = evo
        self._dream = dream
        self._last_shown_proposal = {}
    def _surface_parity_pending_evolution_candidates(self):
        return self._evo
    def _surface_parity_pending_dream_rows(self):
        return self._dream


class HandleCommandInterceptTest(unittest.TestCase):
    def setUp(self):
        self._saved = os.environ.get("MAEZ_VOICE_BOUNDARY_ENABLED")
        os.environ["MAEZ_VOICE_BOUNDARY_ENABLED"] = "1"

    def tearDown(self):
        if self._saved is None:
            os.environ.pop("MAEZ_VOICE_BOUNDARY_ENABLED", None)
        else:
            os.environ["MAEZ_VOICE_BOUNDARY_ENABLED"] = self._saved

    def _adapter(self, evo, dream):
        from skills.surface.telegram_adapter import TelegramAdapter
        from skills.surface.platform_base import PlatformConfig
        a = TelegramAdapter(PlatformConfig(enabled=True, token="x", reply_to_mode="off", extra={}))
        a._message_handler = FakeMaezHandler(evo, dream)
        sent = []
        async def _fake_send(event, text, **kw):
            sent.append(text)
            return True
        a._send_command_reply = _fake_send  # the helper C1 uses (see Step 6)
        a.handle_message = lambda event: (_ for _ in ()).throw(
            AssertionError("slash command must NOT call the brain")
        )
        return a, sent

    def _event(self, text):
        return types.SimpleNamespace(
            text=text, chat_id="c1", user_id="u1", message_id=1, raw=None,
        )

    def test_proposals_handled_without_brain(self):
        a, sent = self._adapter([{"id": 22, "weakness": "w", "target_file": "x"}], [])
        handled = asyncio.run(a._try_command_proposal_surface(self._event("/proposals")))
        self.assertTrue(handled)
        self.assertIn("#22", sent[0])

    def test_show_records_last_shown_for_followup_yes(self):
        a, sent = self._adapter([{"id": 22, "weakness": "w", "target_file": "x"}], [])
        handled = asyncio.run(a._try_command_proposal_surface(self._event("/show 22")))
        self.assertTrue(handled)
        binding = a._message_handler._last_shown_proposal["c1"]
        self.assertEqual(binding["id"], 22)
        self.assertEqual(binding["source"], "evolution")  # matches C2's read

    def test_show_no_id_usage(self):
        a, sent = self._adapter([], [])
        handled = asyncio.run(a._try_command_proposal_surface(self._event("/show")))
        self.assertTrue(handled)
        self.assertIn("/show <id>", sent[0])

    def test_unrelated_slash_not_handled(self):
        a, sent = self._adapter([], [])
        handled = asyncio.run(a._try_command_proposal_surface(self._event("/weather")))
        self.assertFalse(handled)  # falls through to handle_message in real _handle_command
```

**Note for the implementer:** `_event` and the `event` shape must match the real `MessageEvent` used by `_handle_command`. Verify the field names before relying on this fake:
```bash
grep -nE "class MessageEvent|chat_id|user_id|message_id|\.text" skills/surface/platform_base.py | head
sed -n '2742,2762p' skills/surface/telegram_adapter.py
```
**Adjust-rule:** make `_event` produce the same attributes `_handle_command` reads off the event; if `_handle_command` builds the event from `update`/`context` rather than receiving one, factor the proposal-surface logic into `_try_command_proposal_surface(self, event)` taking the already-built event (built at the top of `_handle_command`), and call it from `_handle_command` after the event is constructed.

- [ ] **Step 6: Implement C1 in `telegram_adapter.py`**

First confirm how `_handle_command` builds its `event` and how `/receipts` replies (to mirror the send path):
```bash
sed -n '2742,2763p' skills/surface/telegram_adapter.py
```
Add a small reply helper if one is not already used by `/receipts` (mirror whatever `/receipts` calls — likely a `_reply_text`/`_send_*`). Then add the interceptor method and call it before the fallthrough. Insert into `_handle_command` immediately before `await self.handle_message(event)` (:2762):
```python
        if await self._try_command_proposal_surface(event):
            return
        await self.handle_message(event)
```

Add the method (near `_try_handle_dream_command_event`):
```python
    async def _try_command_proposal_surface(self, event) -> bool:
        """C1: deterministic /proposals and /show. Never calls the brain.

        Reuses the live MaezMessageHandler's Surface-Parity pending-data
        accessors and its shared last-shown store, so a following natural
        'yes' still binds via the C2 resolver. Returns True if it handled the
        command; False lets _handle_command fall through to the brain.
        """
        from core.cognition.capability_card import voice_boundary_enabled
        if not voice_boundary_enabled():
            return False
        text = (getattr(event, "text", "") or "").strip()
        is_proposals = text.split()[0].split("@")[0] == "/proposals" if text else False
        is_show = text.split()[0].split("@")[0] == "/show" if text else False
        if not (is_proposals or is_show):
            return False

        handler = getattr(self, "_message_handler", None)
        if handler is None or not hasattr(handler, "_surface_parity_pending_evolution_candidates"):
            return False  # no live handler -> let the normal path run

        from core.dispatcher.proposal_commands import (
            render_proposals_listing,
            render_proposal_detail,
            parse_show_id,
        )

        try:
            evolution = handler._surface_parity_pending_evolution_candidates()
            dream = handler._surface_parity_pending_dream_rows()
        except Exception:
            self.logger.debug("C1 pending-proposal fetch failed", exc_info=True)
            return False

        if is_proposals:
            await self._send_command_reply(event, render_proposals_listing(evolution, dream))
            return True

        # /show
        import time as _time
        proposal_id = parse_show_id(text)
        if proposal_id is None:
            await self._send_command_reply(event, "Usage: /show <id>  (e.g. /show 22)")
            return True
        detail, source = render_proposal_detail(proposal_id, evolution, dream)
        if source is not None:
            chat_id = str(getattr(event, "chat_id", "") or "")
            handler._last_shown_proposal[chat_id] = {
                "id": int(proposal_id),
                "source": source,
                "shown_at": _time.time(),
            }
        await self._send_command_reply(event, detail)
        return True
```

Implement `_send_command_reply` to mirror the existing `/receipts` reply path (use the SAME call `/receipts` uses — read it at :2752-2759 and copy the mechanism; do not invent a new send). If `/receipts` already exposes a reusable reply helper, call that and skip adding a new one (then update the test's monkeypatch target accordingly).

- [ ] **Step 7: Run the full command test file**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_voice_boundary_commands -v`
Expected: PASS (formatters + interception, including the brain-not-called assertion and the last-shown binding).

- [ ] **Step 8: Commit**

```bash
git add core/dispatcher/proposal_commands.py skills/surface/telegram_adapter.py tests/test_voice_boundary_commands.py
git commit -m "feat(voice-boundary): deterministic /proposals and /show on Surface V2

## Predicted effect
With the flag on, /proposals and /show <id> are answered deterministically in
telegram_adapter._handle_command BEFORE the handle_message fallthrough, instead
of being improvised by the brain. /show <id> records last-shown into the live
MaezMessageHandler's shared store using the same {id,source,shown_at} shape the
C2 resolver reads, so a following natural 'yes' still binds. Reuses the
Surface-Parity pending-data accessors (no duplicate proposal engine) and never
calls the brain. Flag off or no live handler: unchanged fallthrough.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 5: Component C2 — regression guard (natural-language proposal turns unchanged)

**Files:**
- Test: `tests/test_voice_boundary_c2_regression.py` (create)

No production change. Guards that natural `show #N` / `yes` / `reject #N` still resolve in `MaezMessageHandler` via the Surface-Parity resolver, that `show #<id>` never emits a literal `N` placeholder, and that approval still goes through the existing engine after a C1 `/show`.

- [ ] **Step 1: Write the regression tests**

Create `tests/test_voice_boundary_c2_regression.py`:
```python
import unittest

from core.dispatcher.proposal_resolver import detect_proposal_intent, resolve_proposal_target


class C2NaturalLanguageRegressionTest(unittest.TestCase):
    def test_show_n_parses_as_show_with_id(self):
        action, explicit = detect_proposal_intent("show #5")
        self.assertEqual(action, "show")
        self.assertEqual(explicit, 5)

    def test_no_literal_N_placeholder(self):
        # the resolver returns an int id, never the string 'N'
        action, explicit = detect_proposal_intent("show #5")
        self.assertIsInstance(explicit, int)

    def test_bare_yes_binds_to_c1_last_shown(self):
        # C1 wrote {'id':22,'source':'evolution','shown_at':now}; a later bare 'yes'
        # must resolve to 22 through the SAME resolver C2 uses.
        action, explicit = detect_proposal_intent("yes")
        target = resolve_proposal_target(
            action=action or "approve",
            explicit_id=explicit,
            pending_ids=[22],
            last_shown={"id": 22, "source": "evolution", "shown_at": 10_000.0},
            source="evolution",
            text="yes",
            now=10_001.0,
            freshness_s=600.0,
        )
        self.assertEqual(target, 22)
```

- [ ] **Step 2: Run**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_voice_boundary_c2_regression -v`
Expected: PASS (resolver already supports this — the test pins it so a future C1/C2 edit can't desync the last-shown contract). If `test_bare_yes_binds_to_c1_last_shown` FAILS, the C1 last-shown shape in Task 4 does not match what the resolver reads — fix Task 4's write shape, not this test.

- [ ] **Step 3: Run the pre-existing resolver + Surface-Parity proposal suites (no regression)**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_proposal_resolver tests.test_surface_parity_proposals -v`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add tests/test_voice_boundary_c2_regression.py
git commit -m "test(voice-boundary): C2 natural-language proposal turns unchanged + C1/C2 binding pinned

Guards that 'show #N' resolves to an int id (no literal N placeholder) and that
a bare 'yes' after a C1 /show binds via the same resolver+last-shown contract,
so the slash and natural-language halves stay in sync.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 6: STOP-at-gate handoff (update the Build Ledger; do NOT merge/flag/restart)

**Files:**
- Modify: `docs/MAEZ_BUILD_LEDGER.md`
- Create: `docs/handoffs/2026-06-12-voice-boundary-v0-codex-to-claude.md`

The maintenance law: every gate handoff updates the ledger rows it touches; "ledger rows updated" is a standing Claude review anchor.

- [ ] **Step 1: Run the full touched-surface test set (gate-green before handoff)**

```bash
/home/rohit/maez/.venv/bin/python -B -m unittest \
  tests.test_voice_boundary_flag \
  tests.test_voice_boundary_envelope \
  tests.test_voice_boundary_both_paths \
  tests.test_voice_boundary_commands \
  tests.test_voice_boundary_c2_regression \
  tests.test_capability_card \
  tests.test_capability_registry \
  tests.test_proposal_resolver \
  tests.test_surface_parity_proposals -v
```
Expected: all PASS. (Do NOT full-discover in `/home/rohit/maez` — S7 live-tree hazard.)

- [ ] **Step 2: Update the Build Ledger**

Add/refresh rows in `docs/MAEZ_BUILD_LEDGER.md` (match the existing 12-column table shape; `updated_by` = `claude`, `last_verified_commit` = the branch tip from Step 4):
- `Voice boundary v0 (capability-state envelope + voice instruction)` · `BUILT_ASLEEP` (witness-pending) · live seam `core/cognition/capability_card.py::capability_prompt_block (both consumers)` · dead seam `n/a` · flag `MAEZ_VOICE_BOUNDARY_ENABLED` · witness `pending — :11435 A/B + Telegram C` · owner breath `merge+flag+restart+witness` · dup-risk `single render fn = no two-path drift; JSON still quotable (residual)` · next action `A/B via 11435, C via Telegram`.
- `Capability card render form` row: note the prose→envelope render-form change is voice-flag-gated; flag-off byte-identical.
- `Command surface on Surface V2 (/proposals, /show)` · `BUILT_ASLEEP` · live seam `telegram_adapter._handle_command::_try_command_proposal_surface` · flag `MAEZ_VOICE_BOUNDARY_ENABLED` · dup-risk `reuses MaezMessageHandler accessors + shared last-shown; no new engine`.
- Cross-link the existing `cockpit/HTTP path skips adapter interceptors` HAZARD row: note Component C is adapter-only → A/B witnessable on :11435, C only on Telegram.

- [ ] **Step 3: Write the handoff doc**

Create `docs/handoffs/2026-06-12-voice-boundary-v0-codex-to-claude.md` covering:
- **Branch tip + commit list** (the 5 feature/test commits).
- **Verified seams (Task 0):** the two card consumers (daemon :5770 / focused :214), the C1 fallthrough (:2762), the shared last-shown store (`self._message_handler._last_shown_proposal`, source literals `evolution`/`dream`).
- **The design deviation + justification:** A+B both emitted by `capability_prompt_block()` (single function both consumers call) rather than two insertion points — this *strengthens* the spec's both-paths requirement. Flag this explicitly for review.
- **Review anchors (for Claude):**
  1. **off-means-off byte-identity matrix** — flag-off returns the EXACT old prose (string-equality), both prompt paths unchanged, command routing unchanged; precedence-off → `""` regardless of voice flag.
  2. **both-paths-or-the-wound-survives** — the structural guard test (Task 3) and the proof that no second renderer exists.
  3. **C1-not-in-MaezMessageHandler** — C1 lives in `telegram_adapter._handle_command` (the real slash sink), not the text-only handler.
  4. **slash-does-not-call-brain** — the interceptor returns before `handle_message`; the test asserts `handle_message` raises if called.
  5. **C1/C2 last-shown contract** — C1 writes the same `{id,source,shown_at}` shape/source C2 reads; the binding regression test pins it.
  6. **residual risk** — the JSON envelope is still quotable; v0 claims a cleaner feed, not a guaranteed voice cure (spec Residual Risk). The witness decides.
  7. **ledger rows updated.**
- **Witness plan (record the bench split):**
  - **A/B via the :11435 brain bench** (no Telegram needed): with `maez.service` restarted under the flag, `POST 127.0.0.1:11435/message {"message":"What's the state of your web search tools?"}` → current truth in natural voice, no "YOUR LIVE BODY"/"gatekeeper mode" phrasing; `{"message":"Are you able to feel time?"}` → attached/unattached truth, no metadata lecture.
  - **C via Telegram only** (slash commands live in the Telegram adapter): `/proposals` → deterministic listing, not chat prose; `/show` → deterministic usage; `/show <id>` then natural `yes` → approval via the existing engine.
  - The terminal-access probe is intentionally NOT a witness (registry has no terminal entry; un-probed = fake confidence — spec line 275).
- **Owner breath sequence:** merge → add `MAEZ_VOICE_BOUNDARY_ENABLED=1` to `~/.config/maez/model.env` (with a strict-parser revert note: "set 0 or remove + restart") → owner restart `maez.service` → witness.

- [ ] **Step 4: Commit the handoff + ledger**

```bash
git add docs/MAEZ_BUILD_LEDGER.md docs/handoffs/2026-06-12-voice-boundary-v0-codex-to-claude.md
git commit -m "docs(voice-boundary): gate handoff + Build Ledger rows (witness-pending)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
git log --oneline -6
git rev-parse --short HEAD   # record as the ledger last_verified_commit
```

- [ ] **Step 5: STOP.** Do not merge, do not flag, do not restart. Report the branch tip, the verification outputs, and the owner-breath sequence. Merge/flag/restart/witness are owner breaths.

---

## Self-Review (run against the spec)

**Spec coverage:**
- Component A (structured envelope, registry stays source of truth, unknown-explicit, 30s cache) → Task 2. ✓
- Component B (voice-boundary instruction on BOTH paths, not a word blacklist) → Task 2 (bundled) + Task 3 (both-paths guard). ✓
- Component C1 (`/proposals`, `/show <id>`, `/show` usage, `/show <missing>`, before fallthrough, reuse engines, no brain) → Task 4. ✓
- Component C2 (natural-language stays in MaezMessageHandler, no `N` placeholder) → Task 5. ✓
- Strict flag, off=byte-identical → Task 1 + Task 2 flag-off tests. ✓
- Error handling (probe→unknown; builder failure→omit-not-block via the outer `try/except return ""`; malformed slash→deterministic usage; missing target→deterministic not-found) → Tasks 2 & 4. ✓
- Tests assert by schema not banned-word; flag-off byte-identity; C1 fingerprint that `_handle_command` forwards unregistered slashes → Tasks 2/3/4. ✓
- Terminal-access probe removed → Task 6 witness note. ✓
- Predicted-effect on behavior commits (Tasks 2, 4) → present. ✓

**Placeholder scan:** no TBD/TODO; every code step shows complete code; adjust-rules name exact verification commands rather than "handle edge cases." ✓

**Type consistency:** `voice_boundary_enabled()`, `capability_prompt_block(registry=None) -> str`, `_build_capability_envelope(registry) -> str`, `render_proposals_listing(evolution, dream) -> str`, `render_proposal_detail(id, evolution, dream) -> (str, Optional[str])`, `parse_show_id(text) -> Optional[int]`, `_try_command_proposal_surface(self, event) -> bool`, last-shown shape `{"id":int,"source":str,"shown_at":float}` — consistent across tasks. ✓

**Known fragilities flagged for the implementer (with adjust-rules, not guesses):** the real `MessageEvent` field names (Task 4 Step 5), the `/receipts` reply mechanism to mirror for `_send_command_reply` (Task 4 Step 6), and any line-number drift since @24c7373 (Task 0). Each carries a verification command + adjust-rule.
