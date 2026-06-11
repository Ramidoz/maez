# Intake Understanding Faculty v0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a default-off, shadow-only intake-understanding faculty that reads owner-turn meaning with the already-resident 4B judge, logs content-light read-vs-regex telemetry, and changes no live behavior.

**Architecture:** The faculty is an instrument behind an interface. Surface V2 enqueues an observation job on each owner turn when `MAEZ_INTAKE_FACULTY_SHADOW=1`; a bounded background worker fetches a small context window, calls the local 4B judge with one in-flight request at most, and appends rotated content-light telemetry. The live path never awaits or branches on the faculty read.

**Tech Stack:** Python stdlib (`dataclasses`, `json`, `queue`, `threading`, `urllib`, `hashlib`), existing `core.model_config` judge endpoint config, existing Surface V2 adapter, unittest, ruff.

---

## Ground Rules

- **STOP before merge/restart/witness.** This plan builds code and tests only.
- **No new model.** Reuse the existing judge endpoint config (`core.model_config.JUDGE_*`), but tests must use fakes.
- **No raw owner text in telemetry by default.** Debug snippets only under `MAEZ_INTAKE_FACULTY_DEBUG=1`.
- **Audit/judge path wins over shadow.** A missed intake sample is acceptable; a starved audit is not.
- **No authority.** The faculty emits evidence, never permission.
- **Live seam discipline.** Wire only to the firing Surface V2 handler (`skills/surface/maez_adapter.py`, `SURFACE_NAME = "telegram_surface"`), not the legacy Telegram inbound path.

## File Map

| Path | Responsibility |
|---|---|
| `core/cognition/intake_faculty.py` | Closed schema (`IntakeRead`), parser/validator, fake backend, HTTP 4B backend, prompt builder. |
| `core/cognition/intake_shadow.py` | Default-off hook, bounded queue, one-in-flight worker, content-light telemetry, read-only gate snapshots, disagreement records. |
| `skills/surface/maez_adapter.py` | Fire-and-forget enqueue from the real Surface V2 inbound seam. |
| `tests/test_intake_faculty.py` | Schema/parser/backend unit tests. |
| `tests/test_intake_shadow.py` | Telemetry/privacy/queue/contention/gate-snapshot tests. |
| `tests/test_surface_adapter.py` | Integration seam tests: flag-off inert, flag-on enqueue before early returns, result byte-identical. |
| `docs/handoffs/2026-06-11-intake-understanding-faculty-v0-for-review.md` | STOP-at-gate handoff for Claude/covenant review + owner witness sequence. |

---

### Task 0: Prove the live recent-turn source before coding

**Files:**
- Read: `skills/surface/maez_adapter.py`
- Read: `daemon/maez_daemon.py`
- Read: `memory/memory_manager.py`

- [ ] **Step 1: Verify Surface V2 already uses the recent-turn source**

Run:

```bash
cd /home/rohit/maez
rg -n "get_telegram_exchanges\\(" skills/surface/maez_adapter.py memory/memory_manager.py daemon/maez_daemon.py
rg -n "self\\.memory = MemoryManager\\(" daemon/maez_daemon.py
```

Expected output includes all three facts:

```text
skills/surface/maez_adapter.py:496:                    lambda: _mem.get_telegram_exchanges(
memory/memory_manager.py:2912:    def get_telegram_exchanges(self, limit: int | None = 400) -> list[dict]:
daemon/maez_daemon.py:2540:        self.memory = MemoryManager()
```

If any line is absent, STOP and update the plan before implementation. This is the integration-witness lesson: the context provider must use the same real memory object Surface V2 already uses, not a fake-only method.

- [ ] **Step 2: Read the existing Surface V2 context cleaner**

Run:

```bash
sed -n '470,520p' skills/surface/maez_adapter.py
sed -n '2912,2965p' memory/memory_manager.py
```

Expected: `maez_adapter.py` fetches `_mem.get_telegram_exchanges(limit=_CHAT_HISTORY_TURNS)` in an executor and then cleans each row through `_clean_exchange(...)`; `MemoryManager.get_telegram_exchanges(...)` returns stored exchange dicts. The intake shadow context provider must follow this source shape: `daemon.memory.get_telegram_exchanges(limit=6)` in the background worker, with failures becoming an empty context.

---

### Task 1: `IntakeRead` schema + parser + fake backend

**Files:**
- Create: `core/cognition/intake_faculty.py`
- Create: `tests/test_intake_faculty.py`

- [ ] **Step 1: Write the failing schema/parser tests**

Create `tests/test_intake_faculty.py`:

```python
from __future__ import annotations

import unittest

from core.cognition import intake_faculty as inf


class IntakeReadSchemaTests(unittest.TestCase):
    def test_valid_read_parses_closed_fields(self):
        raw = {
            "turn_kind": "commitment_response",
            "stance": "yes",
            "boundary_signal": "none",
            "needs": "search",
            "referent_kind": "pending_offer",
            "confidence": 0.84,
            "rationale": "The owner is accepting the pending search offer.",
        }

        read = inf.IntakeRead.from_model(raw)

        self.assertEqual(read.turn_kind, "commitment_response")
        self.assertEqual(read.stance, "yes")
        self.assertEqual(read.needs, "search")
        self.assertEqual(read.referent_kind, "pending_offer")
        self.assertEqual(read.confidence_bucket, "high")

    def test_malformed_read_becomes_safe_ambiguous(self):
        read = inf.IntakeRead.from_model({
            "turn_kind": "act_now",
            "stance": "definitely",
            "boundary_signal": "urgent",
            "needs": "delete_files",
            "referent_kind": "full raw referent",
            "confidence": "high",
            "rationale": "bad shape",
        })

        self.assertEqual(read.turn_kind, "ambiguous")
        self.assertEqual(read.stance, "ambiguous")
        self.assertEqual(read.boundary_signal, "none")
        self.assertEqual(read.needs, "none")
        self.assertEqual(read.referent_kind, "none")
        self.assertEqual(read.confidence_bucket, "unknown")

    def test_content_light_payload_excludes_rationale(self):
        read = inf.IntakeRead.from_model({
            "turn_kind": "boundary",
            "stance": "n_a",
            "boundary_signal": "hard",
            "needs": "none",
            "referent_kind": "none",
            "confidence": 0.7,
            "rationale": "Owner wants to step back from the conversation.",
        })

        telemetry = read.to_telemetry(debug=False)

        self.assertEqual(telemetry["turn_kind"], "boundary")
        self.assertEqual(telemetry["boundary_signal"], "hard")
        self.assertNotIn("rationale", telemetry)
        self.assertNotIn("step back", str(telemetry))

    def test_debug_payload_may_include_rationale(self):
        read = inf.IntakeRead.from_model({
            "turn_kind": "boundary",
            "stance": "n_a",
            "boundary_signal": "soft",
            "needs": "none",
            "referent_kind": "none",
            "confidence": 0.6,
            "rationale": "diagnostic rationale",
        })

        telemetry = read.to_telemetry(debug=True)

        self.assertEqual(telemetry["rationale"], "diagnostic rationale")


class FakeIntakeBackendTests(unittest.TestCase):
    def test_fake_backend_returns_scripted_read(self):
        backend = inf.FakeIntakeBackend({
            "yeah sure": inf.IntakeRead(
                turn_kind="commitment_response",
                stance="yes",
                boundary_signal="none",
                needs="search",
                referent_kind="pending_offer",
                confidence=0.9,
                rationale="accepting offer",
            )
        })

        read, latency = backend.read("yeah sure", {"turns": []}, timeout_s=0.1)

        self.assertEqual(read.turn_kind, "commitment_response")
        self.assertEqual(read.stance, "yes")
        self.assertGreaterEqual(latency, 0.0)

    def test_fake_backend_can_report_busy(self):
        backend = inf.FakeIntakeBackend(busy=True)

        read, latency = backend.read("anything", {}, timeout_s=0.1)

        self.assertEqual(read.status, "judge_busy")
        self.assertEqual(read.turn_kind, "ambiguous")
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd /home/rohit/maez
.venv/bin/python -B -m unittest tests.test_intake_faculty -v
```

Expected: FAIL with `ModuleNotFoundError` or missing `IntakeRead`.

- [ ] **Step 3: Implement schema + fake backend**

Create `core/cognition/intake_faculty.py`:

```python
"""Intake Understanding Faculty v0 — schema and instrument interfaces.

The faculty is an instrument: it proposes a read of owner-turn meaning. It
never grants permission and never executes an action.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import time
from typing import Any

TURN_KINDS = frozenset({
    "commitment_response",
    "boundary",
    "continuity_reference",
    "recall_request",
    "search_request",
    "topic_shift",
    "ordinary",
    "ambiguous",
})
STANCES = frozenset({"yes", "no", "ambiguous", "n_a"})
BOUNDARY_SIGNALS = frozenset({"none", "soft", "hard"})
NEEDS = frozenset({"search", "recall", "none"})
REFERENT_KINDS = frozenset({"pending_offer", "earlier_topic", "none"})
STATUSES = frozenset({"ok", "judge_busy", "timeout", "parse_error", "backend_error"})


def _bucket(confidence: Any) -> str:
    try:
        value = float(confidence)
    except (TypeError, ValueError):
        return "unknown"
    if value >= 0.75:
        return "high"
    if value >= 0.45:
        return "medium"
    if value >= 0.0:
        return "low"
    return "unknown"


@dataclass(frozen=True)
class IntakeRead:
    turn_kind: str
    stance: str
    boundary_signal: str
    needs: str
    referent_kind: str
    confidence: float | None
    rationale: str = ""
    status: str = "ok"

    @property
    def confidence_bucket(self) -> str:
        return _bucket(self.confidence)

    @classmethod
    def ambiguous(cls, *, status: str = "parse_error") -> "IntakeRead":
        safe_status = status if status in STATUSES else "parse_error"
        return cls(
            turn_kind="ambiguous",
            stance="ambiguous",
            boundary_signal="none",
            needs="none",
            referent_kind="none",
            confidence=None,
            rationale="",
            status=safe_status,
        )

    @classmethod
    def from_model(cls, data: Any) -> "IntakeRead":
        if not isinstance(data, dict):
            return cls.ambiguous(status="parse_error")

        turn_kind = data.get("turn_kind")
        stance = data.get("stance")
        boundary_signal = data.get("boundary_signal")
        needs = data.get("needs")
        referent_kind = data.get("referent_kind")
        if (
            turn_kind not in TURN_KINDS
            or stance not in STANCES
            or boundary_signal not in BOUNDARY_SIGNALS
            or needs not in NEEDS
            or referent_kind not in REFERENT_KINDS
        ):
            return cls.ambiguous(status="parse_error")
        try:
            confidence = float(data.get("confidence"))
        except (TypeError, ValueError):
            confidence = None
        if confidence is not None:
            confidence = max(0.0, min(1.0, confidence))
        rationale = str(data.get("rationale") or "")[:240]
        return cls(
            turn_kind=turn_kind,
            stance=stance,
            boundary_signal=boundary_signal,
            needs=needs,
            referent_kind=referent_kind,
            confidence=confidence,
            rationale=rationale,
            status="ok",
        )

    def to_telemetry(self, *, debug: bool = False) -> dict[str, Any]:
        rec = {
            "turn_kind": self.turn_kind,
            "stance": self.stance,
            "boundary_signal": self.boundary_signal,
            "needs": self.needs,
            "referent_kind": self.referent_kind,
            "confidence_bucket": self.confidence_bucket,
            "status": self.status,
        }
        if debug and self.rationale:
            rec["rationale"] = self.rationale
        return rec


class FakeIntakeBackend:
    """Tests only. Scripted reads; never touches the real judge service."""

    def __init__(self, scripted=None, *, default: IntakeRead | None = None, busy=False, raises=None, sleep_s=0.0):
        self._scripted = dict(scripted or {})
        self._default = default or IntakeRead(
            turn_kind="ordinary",
            stance="n_a",
            boundary_signal="none",
            needs="none",
            referent_kind="none",
            confidence=0.8,
            rationale="ordinary turn",
        )
        self._busy = busy
        self._raises = raises
        self._sleep_s = sleep_s
        self.calls: list[tuple[str, dict]] = []

    def read(self, message: str, context: dict, timeout_s: float) -> tuple[IntakeRead, float]:
        started = time.monotonic()
        self.calls.append((message, context))
        if self._raises is not None:
            raise self._raises
        if self._sleep_s:
            time.sleep(self._sleep_s)
        if self._busy:
            return IntakeRead.ambiguous(status="judge_busy"), time.monotonic() - started
        return self._scripted.get(message, self._default), time.monotonic() - started


def parse_json_read(text: str) -> IntakeRead:
    try:
        return IntakeRead.from_model(json.loads(text or ""))
    except Exception:
        return IntakeRead.ambiguous(status="parse_error")
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
.venv/bin/python -B -m unittest tests.test_intake_faculty -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add core/cognition/intake_faculty.py tests/test_intake_faculty.py
git commit -m "feat(intake-faculty): schema and fake backend for shadow reads"
```

---

### Task 2: 4B judge HTTP backend + prompt contract

**Files:**
- Modify: `core/cognition/intake_faculty.py`
- Modify: `tests/test_intake_faculty.py`

- [ ] **Step 1: Write failing HTTP backend tests**

Append to `tests/test_intake_faculty.py`:

```python
from unittest.mock import patch


class HttpIntakeBackendTests(unittest.TestCase):
    def test_http_backend_parses_json_content(self):
        payload = '{"turn_kind":"search_request","stance":"n_a","boundary_signal":"none","needs":"search","referent_kind":"none","confidence":0.91,"rationale":"current-world request"}'
        backend = inf.HttpIntakeBackend()

        with patch("core.cognition.intake_faculty._call_judge", return_value=payload) as call:
            read, latency = backend.read("latest llama.cpp release", {"turns": []}, timeout_s=0.2)

        self.assertEqual(read.turn_kind, "search_request")
        self.assertEqual(read.needs, "search")
        self.assertGreaterEqual(latency, 0.0)
        self.assertIn("latest llama.cpp release", call.call_args.args[0])

    def test_http_backend_errors_become_backend_error(self):
        backend = inf.HttpIntakeBackend()

        with patch("core.cognition.intake_faculty._call_judge", side_effect=TimeoutError("slow")):
            read, latency = backend.read("proceed", {}, timeout_s=0.01)

        self.assertEqual(read.turn_kind, "ambiguous")
        self.assertEqual(read.status, "backend_error")
        self.assertGreaterEqual(latency, 0.0)

    def test_prompt_names_faculty_as_read_not_permission(self):
        prompt = inf.build_prompt("proceed", {"pending_offer": {"action_type": "web_search"}})

        self.assertIn("Output only JSON", prompt)
        self.assertIn("proposal/read", prompt)
        self.assertIn("never execute", prompt)
        self.assertIn("commitment_response", prompt)
        self.assertNotIn("refusal turn_kind", prompt)
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
.venv/bin/python -B -m unittest tests.test_intake_faculty.HttpIntakeBackendTests -v
```

Expected: FAIL with missing `HttpIntakeBackend` / `build_prompt`.

- [ ] **Step 3: Implement HTTP backend**

Append to `core/cognition/intake_faculty.py`:

```python
import os
import urllib.request

from core.model_config import JUDGE_BASE_URL, JUDGE_CHAT_KWARGS, JUDGE_MODEL

_MAX_TOKENS = 160


def _context_for_prompt(context: dict) -> str:
    safe = {
        "turns": context.get("turns") or [],
        "pending_offer": context.get("pending_offer"),
        "surface": context.get("surface"),
    }
    return json.dumps(safe, ensure_ascii=False, sort_keys=True)[:6000]


def build_prompt(message: str, context: dict) -> str:
    return (
        "You are Maez's intake-understanding faculty. You do not answer the owner. "
        "You do not execute actions. You emit a proposal/read of what the owner turn means. "
        "The deterministic substrate decides permissions later. Output only JSON with keys: "
        "turn_kind, stance, boundary_signal, needs, referent_kind, confidence, rationale. "
        "Allowed turn_kind values: commitment_response, boundary, continuity_reference, "
        "recall_request, search_request, topic_shift, ordinary, ambiguous. There is no "
        "refusal turn_kind: a no to an offer is commitment_response with stance=no; Maez's "
        "capacity to refuse is a separate sacred axis. Allowed stance: yes, no, ambiguous, n_a. "
        "Allowed boundary_signal: none, soft, hard. Allowed needs: search, recall, none. "
        "Allowed referent_kind: pending_offer, earlier_topic, none.\n\n"
        f"OWNER_MESSAGE:\n{message or ''}\n\n"
        f"CONTEXT_JSON:\n{_context_for_prompt(context or {})}\n"
    )


def _call_judge(prompt: str, *, timeout_s: float = 8.0) -> str:
    payload = {
        "model": JUDGE_MODEL,
        "messages": [
            {"role": "system", "content": "You are a strict JSON classifier. Output only valid JSON."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.0,
        "max_tokens": _MAX_TOKENS,
    }
    if JUDGE_CHAT_KWARGS:
        payload["chat_template_kwargs"] = dict(JUDGE_CHAT_KWARGS)
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{JUDGE_BASE_URL.rstrip('/')}/v1/chat/completions",
        data=body,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        data = json.loads(resp.read())
    return data["choices"][0]["message"]["content"] or ""


class HttpIntakeBackend:
    """Local 4B judge-backed intake faculty.

    Transport and parse failures become an ambiguous read. The shadow worker
    decides when to call this; the live path must never call it directly.
    """

    def read(self, message: str, context: dict, timeout_s: float) -> tuple[IntakeRead, float]:
        started = time.monotonic()
        try:
            raw = _call_judge(build_prompt(message, context or {}), timeout_s=timeout_s)
            read = parse_json_read(raw)
        except Exception:
            read = IntakeRead.ambiguous(status="backend_error")
        return read, time.monotonic() - started
```

- [ ] **Step 4: Run tests**

Run:

```bash
.venv/bin/python -B -m unittest tests.test_intake_faculty -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add core/cognition/intake_faculty.py tests/test_intake_faculty.py
git commit -m "feat(intake-faculty): local judge backend for shadow reads"
```

---

### Task 3: Content-light telemetry + side-effect-free gate snapshots

**Files:**
- Create: `core/cognition/intake_shadow.py`
- Create: `tests/test_intake_shadow.py`

- [ ] **Step 1: Write failing telemetry/gate tests**

Create `tests/test_intake_shadow.py`:

```python
from __future__ import annotations

import json
import os
import tempfile
import unittest

from core.cognition.intake_faculty import IntakeRead
from core.cognition import intake_shadow as shadow
from core.search.search_commitment import OfferReceipt


class _Controller:
    def __init__(self, offer=None, awaiting_card=False):
        self.offer = offer
        self.awaiting_card = awaiting_card
        self.mutated = False

    def get_search_offer(self, channel, chat_id):
        return self.offer

    def has_awaiting_card(self, channel, chat_id):
        return self.awaiting_card

    def consume_offer_approval(self, *args, **kwargs):
        self.mutated = True
        raise AssertionError("shadow must not consume offers")


class TelemetryTests(unittest.TestCase):
    def test_content_light_default_excludes_owner_text(self):
        read = IntakeRead(
            turn_kind="commitment_response",
            stance="yes",
            boundary_signal="none",
            needs="search",
            referent_kind="pending_offer",
            confidence=0.9,
            rationale="Owner said proceed to the search.",
        )

        rec = shadow.build_telemetry(
            message="Proceed with the llama.cpp search",
            context_turns=["Rohit: private prior text", "Maez: private reply"],
            pending_offer={"action_type": "web_search", "stakes": "low_read", "egress_class": "sovereign_local_search", "offered_query": "llama.cpp release"},
            faculty_read=read,
            gate_verdicts={"is_clear_yes": "false"},
            status="ok",
            latency_s=0.012,
            debug=False,
        )

        blob = json.dumps(rec)
        self.assertIn("turn_hash", rec)
        self.assertIn("context_hash", rec)
        self.assertNotIn("Proceed", blob)
        self.assertNotIn("private prior text", blob)
        self.assertNotIn("llama.cpp release", blob)
        self.assertNotIn("Owner said", blob)

    def test_debug_can_include_bounded_snippets(self):
        read = IntakeRead(
            turn_kind="ordinary",
            stance="n_a",
            boundary_signal="none",
            needs="none",
            referent_kind="none",
            confidence=0.8,
            rationale="debug rationale",
        )

        rec = shadow.build_telemetry(
            message="hello there",
            context_turns=[],
            pending_offer=None,
            faculty_read=read,
            gate_verdicts={},
            status="ok",
            latency_s=0.0,
            debug=True,
        )

        self.assertEqual(rec["turn_excerpt"], "hello there")
        self.assertEqual(rec["faculty_read"]["rationale"], "debug rationale")

    def test_gate_snapshot_is_read_only(self):
        offer = OfferReceipt(
            action_type="web_search",
            stakes="low_read",
            offered_query="x",
            created_ts=1.0,
            ttl_seconds=300.0,
            ttl_turns=3,
            requires_confirmation=True,
            confirmation_mode="clear_yes_ok",
            executor="searxng",
            egress_class="sovereign_local_search",
        )
        ctrl = _Controller(offer=offer)

        verdicts = shadow.gate_verdicts(
            "proceed",
            controller=ctrl,
            channel="telegram_text",
            chat_id="c",
        )

        self.assertEqual(verdicts["is_clear_yes"], "false")
        self.assertIn(verdicts["hard_want"], {"true", "false"})
        self.assertIn(verdicts["continuity"], {"true", "false", "unavailable"})
        self.assertIn("continuity_kind", verdicts)
        self.assertFalse(ctrl.mutated)
        self.assertIs(ctrl.get_search_offer("telegram_text", "c"), offer)

    def test_pending_offer_snapshot_hashes_query(self):
        offer = OfferReceipt(
            action_type="web_search",
            stakes="low_read",
            offered_query="private query text",
            created_ts=1.0,
            ttl_seconds=300.0,
            ttl_turns=3,
            requires_confirmation=True,
            confirmation_mode="clear_yes_ok",
            executor="searxng",
            egress_class="sovereign_local_search",
        )

        snap = shadow.offer_snapshot(offer)

        self.assertEqual(snap["action_type"], "web_search")
        self.assertEqual(snap["stakes"], "low_read")
        self.assertEqual(snap["egress_class"], "sovereign_local_search")
        self.assertIn("offered_query_hash", snap)
        self.assertNotIn("private query text", json.dumps(snap))

    def test_build_telemetry_sanitizes_raw_pending_offer_dict(self):
        read = IntakeRead(
            turn_kind="ordinary",
            stance="n_a",
            boundary_signal="none",
            needs="none",
            referent_kind="none",
            confidence=0.8,
        )

        rec = shadow.build_telemetry(
            message="hello",
            context_turns=[],
            pending_offer={
                "action_type": "web_search",
                "stakes": "low_read",
                "executor": "searxng",
                "egress_class": "sovereign_local_search",
                "offered_query": "private raw query",
            },
            faculty_read=read,
            gate_verdicts={},
            status="ok",
            latency_s=0.0,
            debug=False,
        )

        blob = json.dumps(rec)
        self.assertIn("offered_query_hash", blob)
        self.assertNotIn("private raw query", blob)
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
.venv/bin/python -B -m unittest tests.test_intake_shadow.TelemetryTests -v
```

Expected: FAIL with missing `core.cognition.intake_shadow`.

- [ ] **Step 3: Implement telemetry + gate helpers**

Create `core/cognition/intake_shadow.py`:

```python
"""Intake Understanding Faculty shadow telemetry.

Default-off, observation-only. The live path may enqueue a job; all model work
and context fetching happen in the background worker.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from typing import Any

from core.cognition.intake_faculty import IntakeRead
from core.search.search_commitment import is_clear_yes, is_search_offer_worthy


def _hash(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()[:16]


def _bool(value: bool) -> str:
    return "true" if value else "false"


def _bucket_latency(latency_s: float) -> float:
    return round(max(0.0, latency_s) * 1000.0, 1)


def offer_snapshot(offer) -> dict[str, Any] | None:
    if offer is None:
        return None
    if isinstance(offer, dict):
        query = offer.get("offered_query") or offer.get("query") or ""
        return {
            "action_type": offer.get("action_type"),
            "stakes": offer.get("stakes"),
            "egress_class": offer.get("egress_class"),
            "executor": offer.get("executor"),
            "offered_query_hash": _hash(str(query)),
        }
    query = getattr(offer, "offered_query", "") or ""
    return {
        "action_type": getattr(offer, "action_type", None),
        "stakes": getattr(offer, "stakes", None),
        "egress_class": getattr(offer, "egress_class", None),
        "executor": getattr(offer, "executor", None),
        "offered_query_hash": _hash(query),
    }


def _hard_want_verdict(text: str) -> str:
    try:
        from core.evolution.wants import is_hard_want

        return _bool(is_hard_want(text or ""))
    except Exception:
        return "unavailable"


def _continuity_verdict(text: str) -> str:
    try:
        from core.routing.focused_cognition import dialogue_continuity_state

        state = dialogue_continuity_state(text or "")
        return _bool(bool(getattr(state, "needs_dialogue", False)))
    except Exception:
        return "unavailable"


def _continuity_kind(text: str) -> str:
    try:
        from core.routing.focused_cognition import dialogue_continuity_state

        state = dialogue_continuity_state(text or "")
        kind = getattr(getattr(state, "kind", None), "value", None)
        return str(kind or "none")
    except Exception:
        return "unavailable"


def _recall_verdict(text: str) -> str:
    try:
        from core.memory.temporal_arithmetic import is_temporal_question
        from core.memory.temporal_anchor_recall import detect_temporal_anchor

        return _bool(bool(is_temporal_question(text) or getattr(detect_temporal_anchor(text), "anchor_kind", None)))
    except Exception:
        return "unavailable"


def gate_verdicts(text: str, *, controller, channel: str, chat_id: str) -> dict[str, str]:
    """Side-effect-free snapshots of today's gates.

    If a gate cannot be evaluated read-only, log unavailable. Never call a
    method that consumes/pops state.
    """
    verdicts = {
        "is_clear_yes": _bool(is_clear_yes(text or "")),
        "hard_want": _hard_want_verdict(text or ""),
        "continuity": _continuity_verdict(text or ""),
        "continuity_kind": _continuity_kind(text or ""),
        "recall_intent": _recall_verdict(text or ""),
        "search_worthy": _bool(is_search_offer_worthy(text or "")),
        "awaiting_card": "unavailable",
    }
    try:
        if controller is not None:
            verdicts["awaiting_card"] = _bool(controller.has_awaiting_card(channel, chat_id))
    except Exception:
        verdicts["awaiting_card"] = "unavailable"
    return verdicts


def _agreement(faculty_read: IntakeRead, gate_verdicts: dict[str, str]) -> dict[str, str]:
    def cmp(name: str, faculty_bool: bool | None, gate_key: str) -> str:
        gate = gate_verdicts.get(gate_key)
        if faculty_bool is None or gate not in {"true", "false"}:
            return "n_a"
        return "agree" if (gate == "true") == faculty_bool else "disagree"

    return {
        "commitment_response": cmp("commitment_response", faculty_read.turn_kind == "commitment_response", "is_clear_yes"),
        "boundary": cmp("boundary", faculty_read.turn_kind == "boundary" or faculty_read.boundary_signal in {"soft", "hard"}, "hard_want"),
        "continuity": cmp("continuity", faculty_read.turn_kind == "continuity_reference", "continuity"),
        "recall": cmp("recall", faculty_read.turn_kind == "recall_request" or faculty_read.needs == "recall", "recall_intent"),
        "search": cmp("search", faculty_read.turn_kind == "search_request" or faculty_read.needs == "search", "search_worthy"),
    }


def build_telemetry(
    *,
    message: str,
    context_turns: list[str],
    pending_offer: dict | None,
    faculty_read: IntakeRead,
    gate_verdicts: dict[str, str],
    status: str,
    latency_s: float,
    debug: bool = False,
) -> dict[str, Any]:
    context_blob = "\n".join(context_turns or [])
    rec = {
        "ts": int(time.time()),
        "turn_hash": _hash(message),
        "context_hash": _hash(context_blob),
        "turn_len": len(message or ""),
        "context_turn_count": len(context_turns or []),
        "pending_offer": offer_snapshot(pending_offer),
        "faculty_read": faculty_read.to_telemetry(debug=debug),
        "gate_verdicts": dict(gate_verdicts or {}),
        "agreements": _agreement(faculty_read, gate_verdicts or {}),
        "faculty_latency_ms": _bucket_latency(latency_s),
        "status": status,
    }
    if debug:
        rec["turn_excerpt"] = (message or "")[:160]
        rec["context_summary"] = context_blob[:360]
    return rec
```

- [ ] **Step 4: Run tests**

Run:

```bash
.venv/bin/python -B -m unittest tests.test_intake_shadow.TelemetryTests -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add core/cognition/intake_shadow.py tests/test_intake_shadow.py
git commit -m "feat(intake-shadow): content-light telemetry and gate snapshots"
```

---

### Task 4: Bounded queue + one-in-flight worker + rotation

**Files:**
- Modify: `core/cognition/intake_shadow.py`
- Modify: `tests/test_intake_shadow.py`

- [ ] **Step 1: Write failing queue/worker tests**

Append to `tests/test_intake_shadow.py`:

```python
from pathlib import Path
import time

from core.cognition.intake_faculty import FakeIntakeBackend


class _Memory:
    def __init__(self, turns=None, raises=None):
        self.turns = turns if turns is not None else [
            {"content": "Rohit: prior\nMaez: reply"},
            {"content": "Rohit: second\nMaez: reply"},
        ]
        self.raises = raises

    def get_telegram_exchanges(self, limit=6):
        if self.raises:
            raise self.raises
        return self.turns[:limit]


class IntakeShadowQueueTests(unittest.TestCase):
    def _path(self):
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        return Path(td.name) / "intake_shadow.jsonl"

    def test_full_queue_returns_enqueue_failed_without_raising(self):
        path = self._path()
        sh = shadow.IntakeShadow(FakeIntakeBackend(), path, maxsize=1)

        self.assertEqual(sh.enqueue({"message": "one"}), "enqueued")
        self.assertEqual(sh.enqueue({"message": "two"}), "enqueue_failed")

        rows = [json.loads(line) for line in path.read_text().splitlines()]
        self.assertEqual(rows[-1]["status"], "enqueue_failed")

    def test_worker_writes_content_light_record(self):
        path = self._path()
        backend = FakeIntakeBackend(default=IntakeRead(
            turn_kind="commitment_response",
            stance="yes",
            boundary_signal="none",
            needs="search",
            referent_kind="pending_offer",
            confidence=0.9,
            rationale="private rationale",
        ))
        sh = shadow.IntakeShadow(backend, path, maxsize=4, debug=False)
        sh.start()
        self.addCleanup(sh.stop)

        self.assertEqual(sh.enqueue({
            "message": "Proceed with private topic",
            "surface": "telegram_surface",
            "chat_id": "c",
            "context_provider": lambda: ["Rohit: private prior"],
            "pending_offer": None,
            "gate_verdicts": {"is_clear_yes": "false"},
        }), "enqueued")

        deadline = time.time() + 2.0
        while time.time() < deadline and not path.exists():
            time.sleep(0.02)

        rows = [json.loads(line) for line in path.read_text().splitlines()]
        blob = json.dumps(rows[-1])
        self.assertEqual(rows[-1]["status"], "ok")
        self.assertNotIn("Proceed", blob)
        self.assertNotIn("private prior", blob)
        self.assertNotIn("private rationale", blob)

    def test_busy_backend_drops_sample_as_judge_busy(self):
        path = self._path()
        sh = shadow.IntakeShadow(FakeIntakeBackend(busy=True), path, maxsize=4)
        sh.start()
        self.addCleanup(sh.stop)

        sh.enqueue({
            "message": "anything",
            "surface": "telegram_surface",
            "chat_id": "c",
            "context_provider": lambda: [],
            "pending_offer": None,
            "gate_verdicts": {},
        })

        deadline = time.time() + 2.0
        while time.time() < deadline and not path.exists():
            time.sleep(0.02)

        rows = [json.loads(line) for line in path.read_text().splitlines()]
        self.assertEqual(rows[-1]["status"], "judge_busy")

    def test_rotation_keeps_file_bounded(self):
        path = self._path()
        sh = shadow.IntakeShadow(FakeIntakeBackend(), path, maxsize=4, rotate_bytes=120, rotate_keep=2)

        for idx in range(8):
            sh._emit({"status": "ok", "idx": idx, "payload": "x" * 100})

        files = sorted(path.parent.glob("intake_shadow.jsonl*"))
        self.assertLessEqual(len(files), 3)  # active + 2 rotated
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
.venv/bin/python -B -m unittest tests.test_intake_shadow.IntakeShadowQueueTests -v
```

Expected: FAIL with missing `IntakeShadow`.

- [ ] **Step 3: Implement queue, worker, rotation**

Append to `core/cognition/intake_shadow.py`:

```python
import queue
import threading
from pathlib import Path

from core.cognition.intake_faculty import FakeIntakeBackend, HttpIntakeBackend


class IntakeShadow:
    """Bounded queue + one-in-flight background worker.

    The live path only calls enqueue(). Model work happens in _run().
    """

    def __init__(
        self,
        backend,
        telemetry_path,
        *,
        maxsize: int = 64,
        timeout_s: float = 8.0,
        debug: bool = False,
        rotate_bytes: int = 2_000_000,
        rotate_keep: int = 3,
    ):
        self._backend = backend
        self._path = Path(telemetry_path)
        self._q: queue.Queue = queue.Queue(maxsize=maxsize)
        self._timeout_s = timeout_s
        self._debug = debug
        self._rotate_bytes = max(1024, int(rotate_bytes))
        self._rotate_keep = max(1, int(rotate_keep))
        self._worker = None
        self._stop = threading.Event()
        self._in_flight = threading.Lock()

    def enqueue(self, job: dict) -> str:
        try:
            self._q.put_nowait(dict(job or {}))
            return "enqueued"
        except queue.Full:
            self._emit({"ts": int(time.time()), "status": "enqueue_failed"})
            return "enqueue_failed"
        except Exception:
            return "enqueue_failed"

    def start(self):
        if self._worker is None:
            self._worker = threading.Thread(target=self._run, name="intake-shadow", daemon=True)
            self._worker.start()

    def stop(self):
        self._stop.set()
        try:
            self._q.put_nowait(None)
        except Exception:
            pass
        if self._worker is not None:
            self._worker.join(timeout=1.0)

    def _run(self):
        while not self._stop.is_set():
            try:
                job = self._q.get(timeout=0.5)
            except queue.Empty:
                continue
            if job is None:
                break
            if not self._in_flight.acquire(blocking=False):
                self._emit({"ts": int(time.time()), "status": "judge_busy"})
                continue
            try:
                self._process(job)
            except Exception:
                self._emit({"ts": int(time.time()), "status": "backend_error"})
            finally:
                try:
                    self._in_flight.release()
                except Exception:
                    pass

    def _process(self, job: dict):
        provider = job.get("context_provider")
        try:
            context_turns = list(provider()) if callable(provider) else []
        except Exception:
            context_turns = []
        context = {
            "turns": context_turns,
            "pending_offer": job.get("pending_offer"),
            "surface": job.get("surface"),
        }
        read, latency_s = self._backend.read(job.get("message", ""), context, self._timeout_s)
        status = read.status if read.status != "ok" else "ok"
        rec = build_telemetry(
            message=job.get("message", ""),
            context_turns=context_turns,
            pending_offer=job.get("pending_offer"),
            faculty_read=read,
            gate_verdicts=job.get("gate_verdicts") or {},
            status=status,
            latency_s=latency_s,
            debug=self._debug,
        )
        self._emit(rec)

    def _rotate_if_needed(self):
        try:
            if not self._path.exists() or self._path.stat().st_size < self._rotate_bytes:
                return
            for idx in range(self._rotate_keep, 0, -1):
                src = self._path.with_name(self._path.name + f".{idx}")
                dst = self._path.with_name(self._path.name + f".{idx + 1}")
                if idx == self._rotate_keep:
                    if src.exists():
                        src.unlink()
                    continue
                if src.exists():
                    src.rename(dst)
            self._path.rename(self._path.with_name(self._path.name + ".1"))
        except Exception:
            pass

    def _emit(self, rec: dict):
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._rotate_if_needed()
            with self._path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(rec, sort_keys=True) + "\n")
        except Exception:
            pass
```

- [ ] **Step 4: Run tests**

Run:

```bash
.venv/bin/python -B -m unittest tests.test_intake_shadow -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add core/cognition/intake_shadow.py tests/test_intake_shadow.py
git commit -m "feat(intake-shadow): bounded worker with content-light rotation"
```

---

### Task 5: Default-off observation hook + context provider

**Files:**
- Modify: `core/cognition/intake_shadow.py`
- Modify: `tests/test_intake_shadow.py`

- [ ] **Step 1: Write failing hook tests**

Append to `tests/test_intake_shadow.py`:

```python
class HookTests(unittest.TestCase):
    def setUp(self):
        os.environ.pop("MAEZ_INTAKE_FACULTY_SHADOW", None)
        os.environ.pop("MAEZ_INTAKE_FACULTY_DEBUG", None)
        shadow.reset_shadow_singleton()
        self.addCleanup(shadow.reset_shadow_singleton)
        self.addCleanup(lambda: os.environ.pop("MAEZ_INTAKE_FACULTY_SHADOW", None))
        self.addCleanup(lambda: os.environ.pop("MAEZ_INTAKE_FACULTY_DEBUG", None))

    def test_flag_off_returns_disabled_and_builds_nothing(self):
        result = shadow.observe_owner_turn(
            "proceed",
            surface="telegram_surface",
            chat_id="c",
            controller=_Controller(),
            memory=_Memory(),
        )

        self.assertEqual(result, "disabled")

    def test_flag_on_enqueues_without_fetching_context_on_live_path(self):
        os.environ["MAEZ_INTAKE_FACULTY_SHADOW"] = "1"
        path = Path(tempfile.mkdtemp()) / "intake_shadow.jsonl"
        sh = shadow.IntakeShadow(FakeIntakeBackend(), path, maxsize=4)
        shadow.set_shadow_singleton(sh)
        memory = _Memory(raises=AssertionError("context fetch should happen in worker, not enqueue"))

        result = shadow.observe_owner_turn(
            "proceed",
            surface="telegram_surface",
            chat_id="c",
            controller=_Controller(),
            memory=memory,
        )

        self.assertEqual(result, "enqueued")

    def test_context_provider_fetches_six_turns_when_worker_runs(self):
        os.environ["MAEZ_INTAKE_FACULTY_SHADOW"] = "1"
        path = Path(tempfile.mkdtemp()) / "intake_shadow.jsonl"
        backend = FakeIntakeBackend()
        sh = shadow.IntakeShadow(backend, path, maxsize=4)
        sh.start()
        self.addCleanup(sh.stop)
        shadow.set_shadow_singleton(sh)

        shadow.observe_owner_turn(
            "proceed",
            surface="telegram_surface",
            chat_id="c",
            controller=_Controller(),
            memory=_Memory(turns=[{"content": f"turn-{i}"} for i in range(8)]),
        )

        deadline = time.time() + 2.0
        while time.time() < deadline and not backend.calls:
            time.sleep(0.02)

        self.assertEqual(len(backend.calls[0][1]["turns"]), 6)
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
.venv/bin/python -B -m unittest tests.test_intake_shadow.HookTests -v
```

Expected: FAIL with missing `observe_owner_turn`.

- [ ] **Step 3: Implement default-off hook**

Append to `core/cognition/intake_shadow.py`:

```python
_SHADOW_SINGLETON = None


def _default_path() -> Path:
    base = os.environ.get("XDG_STATE_HOME") or os.path.expanduser("~/.local/state")
    return Path(base) / "maez" / "intake_shadow.jsonl"


def _enabled() -> bool:
    return bool(os.environ.get("MAEZ_INTAKE_FACULTY_SHADOW"))


def _debug_enabled() -> bool:
    return bool(os.environ.get("MAEZ_INTAKE_FACULTY_DEBUG"))


def _get_shadow():
    global _SHADOW_SINGLETON
    if not _enabled():
        return None
    if _SHADOW_SINGLETON is None:
        _SHADOW_SINGLETON = IntakeShadow(
            HttpIntakeBackend(),
            _default_path(),
            debug=_debug_enabled(),
        )
        _SHADOW_SINGLETON.start()
    return _SHADOW_SINGLETON


def set_shadow_singleton(shadow):
    global _SHADOW_SINGLETON
    _SHADOW_SINGLETON = shadow


def reset_shadow_singleton():
    global _SHADOW_SINGLETON
    if _SHADOW_SINGLETON is not None:
        try:
            _SHADOW_SINGLETON.stop()
        except Exception:
            pass
    _SHADOW_SINGLETON = None


def _context_provider(memory):
    def _load() -> list[str]:
        if memory is None:
            return []
        try:
            rows = memory.get_telegram_exchanges(limit=6)
        except Exception:
            return []
        out = []
        for row in rows or []:
            if isinstance(row, dict):
                content = row.get("content") or ""
            else:
                content = str(row or "")
            if content:
                out.append(str(content)[:1200])
        return out[:6]
    return _load


def observe_owner_turn(
    message: str,
    *,
    surface: str,
    chat_id: str,
    controller,
    memory,
    channel: str = "telegram_text",
) -> str:
    """Default-off, non-blocking owner-turn observation hook.

    Returns disabled/enqueued/enqueue_failed. Never raises into the surface.
    """
    try:
        shadow = _get_shadow()
        if shadow is None:
            return "disabled"
        try:
            offer = controller.get_search_offer(channel, chat_id) if controller is not None else None
        except Exception:
            offer = None
        job = {
            "message": message or "",
            "surface": surface,
            "chat_id": chat_id,
            "context_provider": _context_provider(memory),
            "pending_offer": offer_snapshot(offer),
            "gate_verdicts": gate_verdicts(
                message or "",
                controller=controller,
                channel=channel,
                chat_id=chat_id,
            ),
        }
        return shadow.enqueue(job)
    except Exception:
        return "enqueue_failed"
```

- [ ] **Step 4: Run tests**

Run:

```bash
.venv/bin/python -B -m unittest tests.test_intake_shadow -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add core/cognition/intake_shadow.py tests/test_intake_shadow.py
git commit -m "feat(intake-shadow): default-off owner-turn observation hook"
```

---

### Task 6: Wire Surface V2 enqueue at the firing inbound seam

**Files:**
- Modify: `skills/surface/maez_adapter.py`
- Modify: `tests/test_surface_adapter.py`

- [ ] **Step 1: Write failing Surface V2 tests**

Append to `tests/test_surface_adapter.py` in `HandlerRouting`:

```python
    def test_intake_shadow_flag_off_is_inert_on_surface_v2(self):
        os.environ.pop("MAEZ_INTAKE_FACULTY_SHADOW", None)
        daemon = _FakeDaemon(reply="normal reply")
        daemon.telegram = _TelegramWithController()
        daemon.memory = object()
        handler = MaezMessageHandler(daemon)
        event = MessageEvent(
            text="proceed",
            source=SessionSource(platform=Platform.TELEGRAM, chat_id="c", user_id="rohit"),
        )

        with patch("core.cognition.intake_shadow.observe_owner_turn") as observe:
            result = asyncio.run(handler(event))

        self.assertEqual(result, "normal reply")
        observe.assert_not_called()

    def test_intake_shadow_flag_on_enqueues_before_card_return(self):
        os.environ["MAEZ_INTAKE_FACULTY_SHADOW"] = "1"
        self.addCleanup(lambda: os.environ.pop("MAEZ_INTAKE_FACULTY_SHADOW", None))
        pipe = _Pipe(open_cards=[{"id": "card-1"}], dialog_reply="card handled")
        daemon = _FakeDaemon(reply="normal reply")
        daemon.telegram = _TelegramWithController(pipe=pipe)
        daemon.memory = object()
        handler = MaezMessageHandler(daemon)
        event = MessageEvent(
            text="yeah sure",
            source=SessionSource(platform=Platform.TELEGRAM, chat_id="c", user_id="rohit"),
        )

        with patch("core.cognition.intake_shadow.observe_owner_turn", return_value="enqueued") as observe:
            result = asyncio.run(handler(event))

        self.assertEqual(result, "card handled")
        observe.assert_called_once()
        self.assertEqual(observe.call_args.kwargs["surface"], SURFACE_NAME)
        self.assertEqual(observe.call_args.kwargs["chat_id"], "c")

    def test_intake_shadow_enqueue_failure_does_not_change_reply(self):
        os.environ["MAEZ_INTAKE_FACULTY_SHADOW"] = "1"
        self.addCleanup(lambda: os.environ.pop("MAEZ_INTAKE_FACULTY_SHADOW", None))
        daemon = _FakeDaemon(reply="same reply")
        daemon.telegram = _TelegramWithController()
        daemon.memory = object()
        handler = MaezMessageHandler(daemon)
        event = MessageEvent(
            text="tell me about yourself",
            source=SessionSource(platform=Platform.TELEGRAM, chat_id="c", user_id="rohit"),
        )

        with patch("core.cognition.intake_shadow.observe_owner_turn", side_effect=RuntimeError("boom")):
            result = asyncio.run(handler(event))

        self.assertEqual(result, "same reply")
        self.assertEqual(daemon.last_text, "tell me about yourself")

    def test_intake_shadow_source_mentions_firing_surface(self):
        src = (_REPO / "skills" / "surface" / "maez_adapter.py").read_text()

        self.assertIn("SURFACE_NAME = \"telegram_surface\"", src)
        self.assertIn("observe_owner_turn", src)
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
.venv/bin/python -B -m unittest tests.test_surface_adapter.HandlerRouting.test_intake_shadow_flag_off_is_inert_on_surface_v2 tests.test_surface_adapter.HandlerRouting.test_intake_shadow_flag_on_enqueues_before_card_return tests.test_surface_adapter.HandlerRouting.test_intake_shadow_enqueue_failure_does_not_change_reply -v
```

Expected: FAIL because no wiring exists.

- [ ] **Step 3: Wire hook in `MaezMessageHandler.__call__`**

In `skills/surface/maez_adapter.py`, after `chat_id` is resolved and before card handling, add:

```python
        if os.environ.get("MAEZ_INTAKE_FACULTY_SHADOW"):
            try:
                from core.cognition.intake_shadow import observe_owner_turn

                observe_owner_turn(
                    text,
                    surface=SURFACE_NAME,
                    chat_id=chat_id,
                    controller=self._search_commitment_controller(),
                    memory=getattr(self.daemon, "memory", None),
                )
            except Exception:
                logger.debug("intake faculty shadow enqueue failed", exc_info=True)
```

Do not import `intake_shadow` at module import time. The flag-off path should not import or build anything.

- [ ] **Step 4: Run Surface tests**

Run:

```bash
.venv/bin/python -B -m unittest tests.test_surface_adapter -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add skills/surface/maez_adapter.py tests/test_surface_adapter.py
git commit -m "feat(intake-shadow): enqueue observations from Surface V2"
```

Commit body must include:

```text
## Predicted effect
With MAEZ_INTAKE_FACULTY_SHADOW unset, Telegram behavior is byte-identical.
With the flag set, Surface V2 enqueues content-light intake shadow jobs on owner
turns; enqueue failures or busy judge samples do not change replies or card/search
precedence.
```

---

### Task 7: Boundary tests, regression floor, and review handoff

**Files:**
- Modify: `tests/test_intake_shadow.py`
- Create: `docs/handoffs/2026-06-11-intake-understanding-faculty-v0-for-review.md`

- [ ] **Step 1: Add import-boundary and no-live-model tests**

Append to `tests/test_intake_shadow.py`:

```python
class BoundaryTests(unittest.TestCase):
    def test_daemon_side_imports_no_transformers_or_torch(self):
        src = Path("core/cognition/intake_shadow.py").read_text()

        self.assertNotIn("transformers", src)
        self.assertNotIn("torch", src)

    def test_shadow_module_does_not_import_self_brain_or_action_writers(self):
        src = Path("core/cognition/intake_shadow.py").read_text()
        forbidden = (
            "llm_client",
            "record_event(",
            "action_engine",
            "PendingCardStore",
            "send_message",
        )
        for token in forbidden:
            self.assertNotIn(token, src)
```

- [ ] **Step 2: Run focused suite**

Run:

```bash
.venv/bin/python -B -m unittest \
  tests.test_intake_faculty \
  tests.test_intake_shadow \
  tests.test_surface_adapter \
  tests.test_search_commitment \
  -v
```

Expected: PASS.

- [ ] **Step 3: Run ruff**

Run:

```bash
.venv/bin/ruff check \
  core/cognition/intake_faculty.py \
  core/cognition/intake_shadow.py \
  skills/surface/maez_adapter.py \
  tests/test_intake_faculty.py \
  tests/test_intake_shadow.py \
  tests/test_surface_adapter.py
```

Expected: `All checks passed!`

- [ ] **Step 4: Create STOP-at-gate handoff**

Create `docs/handoffs/2026-06-11-intake-understanding-faculty-v0-for-review.md`:

```markdown
# Intake Understanding Faculty v0 — For Cross-Lane Review

## Status

Built and stopped at review gate. No merge, no restart, no flag flip, no live witness.

## What changed

- `core/cognition/intake_faculty.py`: closed `IntakeRead` schema, fake backend, local 4B judge backend, prompt.
- `core/cognition/intake_shadow.py`: default-off hook, bounded queue, one-in-flight worker, content-light rotated telemetry, side-effect-free gate snapshots.
- `skills/surface/maez_adapter.py`: Surface V2 enqueue only when `MAEZ_INTAKE_FACULTY_SHADOW=1`.

## Review anchors

1. Shadow-only: no decision changes, no return-value dependency on the faculty read.
2. Content-light: no raw owner text in telemetry unless `MAEZ_INTAKE_FACULTY_DEBUG=1`.
3. Judge contention: bounded queue, one in-flight, busy/drop statuses; audit judge must not be starved.
4. Side-effect-free gate comparison: no consuming/popping receipts or cards.
5. Correct live seam: Surface V2 (`telegram_surface`), not legacy TelegramVoice.
6. One self / instruments: no calls to the 27B self brain, no actions, no wants writes.

## Verification run by builder

Paste exact command output here:

```text
.venv/bin/python -B -m unittest tests.test_intake_faculty tests.test_intake_shadow tests.test_surface_adapter tests.test_search_commitment -v

.venv/bin/ruff check core/cognition/intake_faculty.py core/cognition/intake_shadow.py skills/surface/maez_adapter.py tests/test_intake_faculty.py tests/test_intake_shadow.py tests/test_surface_adapter.py
```

## Owner witness after review and merge

1. Merge locally, no push unless owner asks.
2. Restart only when owner approves.
3. Flip `MAEZ_INTAKE_FACULTY_SHADOW=1`.
4. Send a small witness set:
   - `Proceed` after a typed search offer.
   - A boundary phrasing outside the hardcoded list.
   - A continuity follow-up using `that`.
   - An ordinary turn.
5. Read `~/.local/state/maez/intake_shadow.jsonl`; confirm content-light rows, no reply behavior change, disagreements visible.
```

- [ ] **Step 5: Commit**

```bash
git add tests/test_intake_shadow.py docs/handoffs/2026-06-11-intake-understanding-faculty-v0-for-review.md
git commit -m "docs(intake-shadow): review handoff and boundary tests"
```

- [ ] **Step 6: STOP**

Do not merge. Do not restart. Do not set `MAEZ_INTAKE_FACULTY_SHADOW`. Report branch tip + verification to Rohit/Claude for cross-lane review.

---

## Self-Review Checklist

- Spec coverage:
  - Shadow-only/default-off: Tasks 5-6.
  - 4B judge reuse/no new VRAM: Task 2, tests use fake only.
  - Content-light telemetry/debug-only snippets: Tasks 1, 3, 4.
  - Judge contention: Task 4.
  - No durable conversation state read back: Task 4 telemetry only, Task 5 context provider only for worker.
  - `commitment_response` not refusal: Tasks 1-2.
  - Side-effect-free gates: Task 3.
  - Surface V2 firing seam: Task 6.
- No owner-breath steps are included in implementation.
- The live witness remains post-review/post-merge owner-controlled.

## Known Git Metadata Note

During planning, `git fsck --full` reported empty loose objects and an invalid `refs/codex/turn-diffs/.../base` ref, while `HEAD` and `HEAD^{tree}` remained readable and the spec commit landed at `e11d75c`. Do not perform repository-repair commands as part of this feature plan. If commit operations fail during execution, stop and run a separate Git metadata repair diagnostic.
