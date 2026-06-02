# Temporal–Continuity Precedence (verdict-propagation) — Implementation Plan v2

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans. Steps use checkbox (`- [ ]`).
>
> Supersedes the vetoed first plan (`2026-05-30-temporal-continuity-precedence.md`). Re-planned from the **POST-VETO REVISION** in `docs/superpowers/specs/2026-05-30-temporal-continuity-precedence-design.md`. The vetoed branch `temporal-continuity-precedence` is NOT the base — start fresh from `main`. Its reusable parts (the `temporal_cue` move, basic assemble precedence) may be cherry-picked, but the architecture here is different.

**Goal:** Make the recall layer's verdict (`date_confirmed` vs `semantic_fallback` vs empty) the authority for temporal-vs-continuity precedence — carried as first-class evidence-item provenance, with an address-intent cue that beats continuity only for genuine date questions, a daemon gate that closes the legacy escape hatch, and the rule that only `date_confirmed` may answer a dated frame.

**Architecture:** New `AbsoluteRecallCue` (`{window, is_address, override_continuity, reason}`) from `absolute_recall_cue()` in `core/routing/temporal_cue.py` drives behavior; `_absolute_date_window` stays the low-level parser; `has_absolute_recall_cue` is parser-parity only and must not drive behavior. `assemble_working_set` parses the `<RECALLED date_match="…">` envelope into `EvidenceItem.temporal_provenance` and keys ranking/answer-eligibility/status on it. The daemon gate opens for `is_address` turns and, on a date-addressed focused-None/error, uses deterministic dated-recall honesty instead of legacy synthesis.

**Tech Stack:** Python 3, `unittest` (pytest NOT installed → `.venv/bin/python -m unittest`), `ruff`.

**BINDING RULE (verbatim):** *"Explicit temporal address creates the primary recall frame. Dialogue anchor may be included only as secondary context and must never replace, outrank, or answer for the dated frame. If no dated match exists, do not fall back to dialogue as the answer."*

**HARD CONSTRAINTS:** only `date_confirmed` (or a future producer carrying `confirmed=True`) satisfies a dated frame; `semantic_fallback`/`web_context` are never `[E1]` and never suppress the status under a date cue; provenance is read from the `<RECALLED>` opening-tag envelope, never from body substrings; no memory-ranker/recency, renderer, memory-write, or flag changes beyond what's listed; brain-swap-safe.

---

## File map
- **Create** `core/routing/temporal_cue.py` — moved window/helpers + `AbsoluteRecallCue` + `absolute_recall_cue()` + parity-only `has_absolute_recall_cue`.
- **Modify** `memory/memory_manager.py` — re-import moved symbols (mechanical move).
- **Modify** `core/routing/focused_cognition.py` — `EvidenceItem.temporal_provenance`; envelope parse; provenance-keyed ranking/eligibility/status; named ranks.
- **Modify** `core/brain/brain_loop.py` — adapter uses `override_continuity`.
- **Modify** `daemon/maez_daemon.py` — `_focused_candidate` opens for `is_address`; date-addressed focused-None/error → deterministic dated-recall honesty, not legacy.
- **Tests** `tests/test_memory_manager.py`, `tests/test_focused_cognition.py`, `tests/test_living_recall.py`, `tests/test_routing_observation.py` (or the daemon test module that already constructs `handle_message`).

---

## Task 1: `temporal_cue.py` — move + `AbsoluteRecallCue` + verified address-intent resolver

**Files:** Create `core/routing/temporal_cue.py`; Modify `memory/memory_manager.py`. Test: `tests/test_memory_manager.py`.

- [ ] **Step 1: Write the failing tests** (the verified B1 battery + parity)

```python
class AbsoluteRecallCueTests(unittest.TestCase):
    def _now(self):
        from datetime import datetime
        from core.time.temporal_spine import owner_timezone
        return datetime(2026, 5, 30, 12, 0, tzinfo=owner_timezone())

    def test_address_intent_battery(self):
        from core.routing.temporal_cue import absolute_recall_cue
        now = self._now()
        not_address = [
            "I will be 30 in may", "remind me to march 3 miles",
            "in March we should ship", "pick 2 may options",
            "what were we just talking about, the 3 may bugs?",
            "what were we just talking about?",
        ]
        address = [
            "what did we note around April 27?", "what were we doing April 27?",
            "what happened May 6?", "remind me what we were doing around April 27",
            "what about January 3?", "what were we working on last month?",
        ]
        for q in not_address:
            with self.subTest(q=q):
                self.assertFalse(absolute_recall_cue(q, now).is_address)
                self.assertFalse(absolute_recall_cue(q, now).override_continuity)
        for q in address:
            with self.subTest(q=q):
                self.assertTrue(absolute_recall_cue(q, now).is_address)
                self.assertTrue(absolute_recall_cue(q, now).override_continuity)

    def test_cue_carries_window_when_address(self):
        from core.routing.temporal_cue import absolute_recall_cue
        cue = absolute_recall_cue("what did we note around April 27?", self._now())
        self.assertIsNotNone(cue.window)
        self.assertEqual(cue.window.method, "exact_date")

    def test_has_absolute_recall_cue_is_parser_parity_only(self):
        from core.routing.temporal_cue import has_absolute_recall_cue, _absolute_date_window
        now = self._now()
        for q in ["pick 2 may options", "what did we note around April 27?", "hello"]:
            self.assertEqual(has_absolute_recall_cue(q, now), _absolute_date_window(q, now) is not None)
```

- [ ] **Step 2: Run → FAIL** (`No module named 'core.routing.temporal_cue'`).

- [ ] **Step 3: Create `core/routing/temporal_cue.py`** — move verbatim from `memory/memory_manager.py` (~lines 705–800): `_NIGHTLY_FWD_TOL_DAYS`, `_MONTH_NAMES` (+loop), `AbsoluteRecallWindow`, `_owner_local_to_utc`, `_day_bounds_local`, `_most_recent_year_for`, `_exact_window`, `_month_window`, `_absolute_date_window`. Header + the new resolver (this `absolute_recall_cue` body is VERIFIED against the full battery above — do not weaken it):

```python
"""Absolute-date recall cue detection — single source of truth.
Lightweight (depends only on core.time.temporal_spine). _absolute_date_window is
the low-level parser; absolute_recall_cue() is the behavior-driving resolver."""
import calendar
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from core.time.temporal_spine import owner_timezone

# <<< moved verbatim: _NIGHTLY_FWD_TOL_DAYS, _MONTH_NAMES(+loop), AbsoluteRecallWindow,
#     _owner_local_to_utc, _day_bounds_local, _most_recent_year_for, _exact_window,
#     _month_window, _absolute_date_window >>>

_MONTH_ALT = "|".join(re.escape(name) for name in _MONTH_NAMES)
# Recall/history intent: the query asks ABOUT the past, not plans/commands.
_RECALL_INTENT = re.compile(
    r"\b(what (did|were|was)|what happened|what about|remind me what|did we|"
    r"we (were|did|discuss|discussed|talked|covered|noted)|working on)\b")
# Future-planning / imperative: a calendar word here is NOT a recall address.
_FUTURE_OR_IMPERATIVE = re.compile(
    r"\b(will|i'?ll|shall|should|gonna|going to|let'?s|lets|need to|"
    r"remind me to|schedule|plan to|pick|choose)\b")
# Incidental quantity phrase: "<num> <month> <word>" (e.g. "3 may bugs") — the
# number is a count and the month-name is part of a noun phrase, not a date.
_INCIDENTAL_QTY = re.compile(rf"\b\d{{1,2}}\s+(?:{_MONTH_ALT})\s+[a-z]{{2,}}")


@dataclass(frozen=True)
class AbsoluteRecallCue:
    window: "AbsoluteRecallWindow | None"
    is_address: bool          # query is a genuine recall/history question about a date
    override_continuity: bool # address strong enough to beat a present continuity cue
    reason: str


def absolute_recall_cue(question: str, now_local: datetime | None = None) -> AbsoluteRecallCue:
    q = " " + (question or "").lower().strip() + " "
    window = _absolute_date_window(question, now_local)
    if window is None:
        return AbsoluteRecallCue(None, False, False, "no_date_token")
    if _FUTURE_OR_IMPERATIVE.search(q):
        return AbsoluteRecallCue(window, False, False, "future_or_imperative")
    if _INCIDENTAL_QTY.search(q):
        return AbsoluteRecallCue(window, False, False, "incidental_quantity_phrase")
    if not _RECALL_INTENT.search(q):
        return AbsoluteRecallCue(window, False, False, "no_recall_intent")
    # genuine date-recall address; in v1 is_address implies override_continuity.
    return AbsoluteRecallCue(window, True, True, "address")


def has_absolute_recall_cue(question: str, now_local: datetime | None = None) -> bool:
    """PARSER-PARITY ONLY. Mirrors _absolute_date_window presence. MUST NOT drive
    behavior — behavior keys on absolute_recall_cue(...).is_address/override_continuity."""
    return _absolute_date_window(question, now_local) is not None
```
**v1 limitation to record in the witness doc:** a number-first date inside a recall query ("6 April we discussed…") reads as `incidental_quantity_phrase` (false-negative address). Acceptable — full NL date-intent is out of scope; the safe failure is "treated as continuity," never a wrong dated answer.

- [ ] **Step 4: Re-import in `memory/memory_manager.py`** — delete the moved symbols; add near line 25:
```python
from core.routing.temporal_cue import (
    AbsoluteRecallWindow,
    _absolute_date_window,
    _MONTH_NAMES,
)
```

- [ ] **Step 5: Run → PASS** (`AbsoluteRecallCueTests` + the relocated `AbsoluteDateWindowTests`/`AbsoluteDateRecallTests` still green).

- [ ] **Step 6: Commit** `feat(recall): AbsoluteRecallCue address-intent resolver (B1) + temporal_cue move (single source of truth)`

---

## Task 2: `EvidenceItem.temporal_provenance` + envelope parse + provenance-keyed precedence

**Files:** Modify `core/routing/focused_cognition.py`. Test: `tests/test_focused_cognition.py`.

- [ ] **Step 1: Write the failing tests** (B3 + provenance)

```python
class TemporalProvenancePrecedenceTests(unittest.TestCase):
    CONFIRMED = ('[memory context]\n'
                 '<RECALLED tier="core" age="permanent" id="c1" date_match="exact_date" '
                 'date_match_label="matched by exact date (2026-04-27)">\n'
                 'infrastructure ground-truth fabrication-class incident\n</RECALLED>')
    FALLBACK = ('[memory context]\n'
                '<RECALLED tier="core" age="permanent" id="c2" date_match="semantic_fallback" '
                'date_match_label="semantic match, timing uncertain (not date-confirmed)">\n'
                'some loosely related note\n</RECALLED>')

    def test_confirmed_is_primary_provenance_populated(self):
        from core.routing.focused_cognition import assemble_working_set
        ws = assemble_working_set(transcript=self.CONFIRMED, web_context="",
                                  owner_question="what did we note around April 27?")
        self.assertIsNotNone(ws)
        top = ws.items[0]
        self.assertEqual(top.source_type, "memory_context")
        self.assertTrue(top.temporal_provenance and top.temporal_provenance["confirmed"])
        self.assertEqual(top.temporal_provenance["method"], "exact_date")

    def test_semantic_fallback_never_E1_status_fires(self):
        from core.routing.focused_cognition import assemble_working_set
        ws = assemble_working_set(transcript=self.FALLBACK, web_context="",
                                  owner_question="what did we note around April 27?")
        self.assertIsNotNone(ws)
        # a date cue with no date_confirmed row → status item exists and is primary
        self.assertTrue(any(i.source_type == "temporal_recall_status" for i in ws.items))
        self.assertEqual(ws.items[0].source_type, "temporal_recall_status")
        # the fallback row is present but never E1
        fb = [i for i in ws.items if i.source_type == "memory_context"]
        for i in fb:
            self.assertNotEqual(i.local_label, "E1")

    def test_web_not_E1_and_not_suppress_status(self):
        from core.routing.focused_cognition import assemble_working_set
        ws = assemble_working_set(transcript="", web_context="- some web result line",
                                  owner_question="what happened May 6?")
        self.assertIsNotNone(ws)
        self.assertTrue(any(i.source_type == "temporal_recall_status" for i in ws.items))
        self.assertEqual(ws.items[0].source_type, "temporal_recall_status")
        for i in ws.items:
            if i.source_type == "web_context":
                self.assertNotEqual(i.local_label, "E1")

    def test_provenance_from_envelope_not_body_substring(self):
        from core.routing.focused_cognition import assemble_working_set
        # body MENTIONS the word but the envelope says exact_date → confirmed wins,
        # proving we read the tag attr, not the body text
        tx = ('[memory context]\n'
              '<RECALLED tier="core" age="permanent" id="c3" date_match="exact_date">\n'
              'this note discusses semantic_fallback as a topic\n</RECALLED>')
        ws = assemble_working_set(transcript=tx, web_context="",
                                  owner_question="what did we note around April 27?")
        self.assertTrue(ws.items[0].temporal_provenance["confirmed"])
```

- [ ] **Step 2: Run → FAIL** (`EvidenceItem` has no `temporal_provenance`; no envelope parse; status not primary).

- [ ] **Step 3: Add the field + envelope parser.** In `core/routing/focused_cognition.py`:
```python
@dataclass(frozen=True)
class EvidenceItem:
    local_label: str
    source_type: str
    text: str
    durable_id: str
    temporal_provenance: dict | None = None   # {method, confirmed, confidence?, ...} or None
```
Add a RECALLED-envelope parser + a provenance reader (keyed on the opening-tag attrs, NOT body):
```python
_RECALLED_RE = re.compile(r"<RECALLED\b([^>]*)>(.*?)</RECALLED>", re.DOTALL)
_DATE_MATCH_ATTR = re.compile(r'date_match="([a-z_]+)"')

def _temporal_provenance_from_attrs(attrs: str) -> dict | None:
    m = _DATE_MATCH_ATTR.search(attrs or "")
    if not m:
        return None
    method = m.group(1)
    return {"method": method, "confirmed": method in ("exact_date", "month_window")}

def _memory_items_with_provenance(body: str) -> list[tuple[str, dict | None]]:
    """For a memory block body, return (text, provenance) per RECALLED envelope.
    Falls back to the whole body as one item with no provenance if no envelopes."""
    out = []
    for attrs, content in _RECALLED_RE.findall(body or ""):
        text = content.strip()
        if text:
            out.append((text, _temporal_provenance_from_attrs(attrs)))
    if not out:
        b = (body or "").strip()
        return [(b, None)] if b else []
    return out
```

- [ ] **Step 4: Rewire `assemble_working_set`** to (a) use the cue, (b) parse memory blocks into provenance-bearing items, (c) enforce eligibility + status. Replace the item-gathering + guards region:
```python
    from core.routing.temporal_cue import absolute_recall_cue
    cue = absolute_recall_cue(owner_question)
    date_cue = cue.is_address          # opens temporal-primary mode
    override = cue.override_continuity # beats a present continuity cue
    ...
    dialogue_authoritative = (
        dialogue_state.kind in (ContinuityKind.DIRECT, ContinuityKind.ANAPHORIC)
        and not override
    )
    anchors = (
        dialogue_anchor_items(chat_history)
        if (dialogue_state.needs_dialogue or dialogue_state.fail_safe_legacy or date_cue)
        else []
    )
    if dialogue_authoritative or date_cue:
        anchors = anchors[:1]
    if (dialogue_state.needs_dialogue or dialogue_state.fail_safe_legacy) and not anchors and not date_cue:
        return None
    if not state.evidence_present and not anchors and not date_cue:
        return None

    raw_items: list[tuple[str, str, str | None, dict | None]] = []  # (source_type, text, durable_id, provenance)
    if not dialogue_authoritative:
        for marker, body in _split_blocks(transcript or ""):
            src = _SOURCE_TYPE[marker]
            if src in ("memory_context", "memory_evidence"):
                for item_text, prov in _memory_items_with_provenance(body):
                    raw_items.append((src, item_text, None, prov))
            else:
                for item_text in _atomic_items(body):
                    raw_items.append((src, item_text, None, None))
        web_context = web_context or ""
        if web_context.strip() and _WEB_NO_RESULTS not in web_context:
            for item_text in _atomic_items(web_context):
                raw_items.append(("web_context", item_text, None, None))
    for anchor in anchors:
        raw_items.append((anchor.source_type, anchor.text, anchor.durable_id, None))

    if date_cue:
        has_confirmed = any(p and p.get("confirmed") for _, _, _, p in raw_items)
        if not has_confirmed:
            # only date_confirmed may answer a dated frame; emit honest status as the
            # primary item; semantic_fallback/web/anchor remain only as ranked-below context.
            raw_items.append((
                "temporal_recall_status",
                "No dated memory matched the explicit date cue in the question.",
                None, None))

    if not raw_items:
        return None
    raw_items = _ranked_items_for_state(raw_items, dialogue_state, date_cue)
    items = [
        EvidenceItem(local_label=f"E{i+1}", source_type=st, text=t,
                     durable_id=did or _content_hash(t), temporal_provenance=prov)
        for i, (st, t, did, prov) in enumerate(raw_items)
    ]
```
(Adjust `_ranked_items_for_state` + the ordered-text/`top` build to the 4-tuple; the rendered lines + tail-repeat keep `[E#]` exactly.)

- [ ] **Step 5: Update `_ranked_items_for_state` for the 4-tuple + provenance-aware date mode** (named ranks, per Creative's advisory):
```python
_RANK_PRIMARY_AFTER_EVIDENCE = 50   # dialogue_anchor under a date cue: strictly after evidence
# date-cue ranks: date_confirmed first, then status, then fallback/web context, then anchor
def _ranked_items_for_state(raw_items, dialogue_state, date_cue=False):
    def rank(item):
        source_type, _text, _did, prov = item
        if date_cue:
            if source_type in ("memory_context", "memory_evidence") and prov and prov.get("confirmed"):
                return 0
            if source_type == "temporal_recall_status":
                return 1
            if source_type == "dialogue_anchor":
                return _RANK_PRIMARY_AFTER_EVIDENCE
            return _PRIORITY.get(source_type, 9) + 2   # fallback/web context, below status, above anchor
        # ... existing non-date branches unchanged, adapted to the 4-tuple ...
    return sorted(raw_items, key=rank)
```

- [ ] **Step 6: Run → PASS** (`TemporalProvenancePrecedenceTests`).
- [ ] **Step 7: Full focused suite → OK** (`.venv/bin/python -m unittest tests.test_focused_cognition -v`; existing assemble/continuity/trust-tier/honest-empty green; `check_groundedness` keys on `local_label`, unaffected by the new field).
- [ ] **Step 8: Commit** `fix(focused): temporal_provenance from RECALLED envelope; only date_confirmed answers a dated frame; status primary on no-match`

---

## Task 3: Adapter uses `override_continuity`

**Files:** Modify `core/brain/brain_loop.py`. Test: `tests/test_living_recall.py`.

- [ ] **Step 1: RED in-process test** — date-addressed continuity-shaped query: adapter must not inject "Recent dialogue anchor". (Seed an April core row; chat_history present; query `"remind me what we were doing around April 27"`.) Assert temporal content reaches the prompt and `"Recent dialogue anchor"` does not.
- [ ] **Step 2: Run → FAIL.**
- [ ] **Step 3: Implement.** In `_dispatcher_recall_adapters`, replace the import + cue:
```python
        from core.routing.temporal_cue import absolute_recall_cue
        _override_continuity_for_date = absolute_recall_cue(user_text).override_continuity
```
and the guard (replacing the `has_absolute_recall_cue` line from the vetoed branch):
```python
        if _continuity_needs_dialogue_anchor() and not _override_continuity_for_date:
```
Add a one-line comment: `# date-address override: precedence half lives in assemble_working_set; here we only decline to fabricate a dialogue-anchor producer (provenance half).`
- [ ] **Step 4: Run → PASS.** **Step 5: Commit** `fix(brain_loop): adapter declines dialogue-anchor fabrication on date-addressed turns (override_continuity)`

---

## Task 4: Daemon gate opens for `is_address`; close the legacy escape hatch

**Files:** Modify `daemon/maez_daemon.py`. Test: the daemon test module (e.g. `tests/test_routing_observation.py` / `tests/test_memory_integrity_invariant.py` — whichever constructs `handle_message`).

- [ ] **Step 1: RED tests** (daemon-path; mirror the existing `handle_message` test fixtures):
  1. A no-match dated query ("What did I record on January 3?") with focused cognition enabled → `assemble_working_set` IS reached (focused path taken), the reply is the honest dated-status answer, and the **legacy megaprompt is NOT used** (assert via the `call_purpose`/prompt-shape log or the focused-run record).
  2. A date-addressed turn where focused synthesis returns `None`/raises → reply is a deterministic dated-recall honesty string, NOT legacy chat synthesis.
- [ ] **Step 2: Run → FAIL** (gate excludes the no-match dated query → legacy path).
- [ ] **Step 3: Implement.** Near the gate (`~maez_daemon.py:3848`):
```python
        from core.routing.temporal_cue import absolute_recall_cue
        _abs_recall_cue = absolute_recall_cue(text)
        _focused_candidate = (
            _focused_cognition_enabled()
            and source != "voice"
            and not _current_turn_echo_reply
            and (
                _evidence_state.evidence_present
                or _dialogue_needs_or_uncertain
                or _abs_recall_cue.is_address          # date-addressed turns must reach focused
            )
        )
```
In the focused branch, when the turn is date-addressed (`_abs_recall_cue.is_address`) and the focused path yields no reply (working set None, or synthesize error/empty), set a deterministic honest reply instead of falling through to legacy:
```python
        if _abs_recall_cue.is_address and not _focused_used and reply is None:
            reply = (
                "I don't have a dated memory for that window. I'm not going to "
                "answer it from recent chat or guesswork."
            )
            _focused_used = True   # prevents the legacy megaprompt fall-through
```
(Place this AFTER the focused try/except and BEFORE the `if not _focused_used:` legacy block at ~4015. Confirm `_focused_used`/`reply` variable names against the actual code; adapt if drifted — keep the intent: date-addressed turns never reach legacy synthesis.)
- [ ] **Step 4: Run → PASS.** **Step 5: Commit** `fix(daemon): date-addressed turns reach focused cognition + never fall through to legacy (deterministic dated honesty)`

---

## Task 5: Integration-path + regression + lint

- [ ] **Step 1: Integration test** (`tests/test_living_recall.py`) — both-shaped query end-to-end (dispatcher → merge → `assemble_working_set`): `"remind me what we were doing around April 27"` with an April-dated core row + chat_history → `ws.items[0].source_type == "memory_context"` and `ws.items[0].temporal_provenance["confirmed"]`, anchor never `[E1]`. Run → PASS.
- [ ] **Step 2:** `.venv/bin/python -m unittest tests.test_memory_manager tests.test_focused_cognition tests.test_living_recall <daemon_test_module> -v` → OK.
- [ ] **Step 3:** `.venv/bin/ruff check core/routing/temporal_cue.py core/routing/focused_cognition.py core/brain/brain_loop.py daemon/maez_daemon.py memory/memory_manager.py` → clean.
- [ ] **Step 4:** Broad floor: confirm only the documented pre-existing failures (web_search inventory; owner_bridge envelope; the ordering-flaky service-audit). Report honestly.
- [ ] **Step 5: Commit** `test(recall): integration-path + regression for temporal-continuity precedence v2`

---

## Witness (Claude, after green): full Claude switchboard re-review of the diff, THEN triad re-witness
Per the reinstated switchboard, the post-implementation review fires Claude's six again on the new diff (Logical re-checks: cue over-trigger gone, daemon gate closed, web/fallback can't answer, provenance structural). THEN the live triad re-witness:
1. "remind me what we were doing around April 27" → April-27 record primary (provenance confirmed), recent thread at most a labeled side-note.
2. "what about January 3?" → honest dated-status (focused path taken; **not** legacy) — witness records the resolved window bounds.
3. "what were we just talking about, the 3 may bugs?" → stays continuity (date incidental).
4. Plain continuity / plain recency / plain temporal → all still green.
Green → triad eligible for the explicit default-on decision (separate step, full switchboard, Rohit's call). Red → split.

---

## Self-Review
**Spec coverage:** `AbsoluteRecallCue`+resolver, address-intent B1, parser-parity `has_absolute_recall_cue` (Task 1) = revision §3,4 + verified battery ✓. `temporal_provenance` from envelope, only-confirmed-answers, semantic_fallback/web never-E1-never-suppress-status, status-primary-on-no-match, named ranks (Task 2) = revision §1,2 + B3 ✓. Adapter `override_continuity` (Task 3) = boundary-1 ✓. Daemon gate + legacy-escape-hatch closure (Task 4) = B2 §3 ✓. Integration + switchboard re-review + triad re-witness (Task 5/Witness) = revision witness ✓. Advisories: named ranks ✓, cross-ref comment ✓, confidence growth-seam (note in temporal_cue) ✓, witness records window bounds ✓.
**Placeholder scan:** none — Task 1 ships the battery-verified resolver; Task 2 ships the envelope parser + rewire; daemon edit shows the gate + the honest-fallback; tests carry full assertions. The one heuristic (B1) is verified-green, not a guess.
**Type consistency:** `AbsoluteRecallCue{window,is_address,override_continuity,reason}`; `EvidenceItem(...,temporal_provenance=None)`; `temporal_provenance={"method","confirmed"}`; `_ranked_items_for_state(raw_items, dialogue_state, date_cue=False)` over 4-tuples; `absolute_recall_cue(question, now_local=None)` signature consistent across temporal_cue/focused/brain_loop/daemon; `temporal_recall_status` source-type string identical at emit + tests.
