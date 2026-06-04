# Owner-Account Memory Taint Rail v0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Durable owner-account-derived memory carries `owner_account_context` through recall into the web owner-bridge cloud consult, where the subscription proxy blocks it.

**Architecture:** Add an explicit `egress_origin_class` metadata rail to `memory/memory_manager.py`, a provenance-aware recall renderer that emits per-row `ProvenancedText` spans, and wire only the web owner-bridge cloud path to use it. Prove the rail with a synthetic canary that flows through the real web cloud payload assembly, `claude_tier` span bundling, and subscription proxy enforcement.

**Tech Stack:** Python unittest, Chroma-style fake collections, `core.egress.provenance.ProvenancedText`, `core.routing.claude_tier`, in-process subscription proxy tests.

---

## File Structure

- Modify `memory/memory_manager.py`
  - Add egress-origin validation/write-through.
  - Add `format_for_prompt_provenanced(...) -> ProvenancedText`.
  - Keep `format_for_prompt(...) -> str` byte-equivalent.
- Modify `core/egress/provenance.py`
  - Add `OWNER_ACCOUNT_CONTEXT` to `_RESTRICTIVENESS`.
- Modify `skills/web_interface.py`
  - Use the provenanced recall renderer for owner-memory cloud payloads.
  - Preserve string recall for local web prompting.
- Modify `tests/test_memory_provenance.py`
  - Write API tests for `egress_origin_class`.
- Modify `tests/test_memory_manager.py` or create `tests/test_owner_account_memory_taint_rail.py`
  - Provenanced renderer tests and cloud canary witness.
- Modify `tests/test_egress_claude_router_provenance.py`
  - Web payload provenance expectations.
- Create `tests/test_owner_account_memory_cloud_surface_guard.py`
  - Static forward guard for recall-to-cloud surfaces.

---

### Task 1: Store `egress_origin_class` on memory rows

**Files:**
- Modify: `memory/memory_manager.py`
- Modify: `tests/test_memory_provenance.py`

- [ ] **Step 1: Write failing tests for write-through and validation**

Add these tests to `tests/test_memory_provenance.py` under `ProvenanceWriteApiTests`:

```python
    def test_store_accepts_egress_origin_class(self):
        mm = _mm_with_fakes()
        mid = mm.store(
            "owner-account memory canary",
            cycle=11,
            egress_origin_class="owner_account_context",
        )

        self.assertTrue(mid)
        meta = mm.raw.add_calls[-1]["metadatas"][0]
        self.assertEqual(meta["egress_origin_class"], "owner_account_context")

    def test_store_telegram_accepts_egress_origin_class(self):
        mm = _mm_with_fakes()
        mid = mm.store_telegram(
            "owner account exchange canary",
            egress_origin_class="owner_account_context",
        )

        self.assertTrue(mid)
        meta = mm.raw.add_calls[-1]["metadatas"][0]
        self.assertEqual(meta["egress_origin_class"], "owner_account_context")

    def test_store_core_accepts_egress_origin_class(self):
        mm = _mm_with_fakes()
        mid = mm.store_core(
            "owner-account-derived core canary",
            egress_origin_class="owner_account_context",
        )

        self.assertTrue(mid.startswith("core-"))
        meta = mm.core.add_calls[-1]["metadatas"][0]
        self.assertEqual(meta["egress_origin_class"], "owner_account_context")

    def test_invalid_egress_origin_class_raises_before_write(self):
        mm = _mm_with_fakes()
        with self.assertRaises(ValueError):
            mm.store(
                "bad egress origin",
                cycle=1,
                egress_origin_class="owner_account_contex",
            )
        self.assertEqual(mm.raw.add_calls, [])
```

- [ ] **Step 2: Run tests to verify RED**

Run:

```bash
.venv/bin/python -m unittest \
  tests.test_memory_provenance.ProvenanceWriteApiTests.test_store_accepts_egress_origin_class \
  tests.test_memory_provenance.ProvenanceWriteApiTests.test_store_telegram_accepts_egress_origin_class \
  tests.test_memory_provenance.ProvenanceWriteApiTests.test_store_core_accepts_egress_origin_class \
  tests.test_memory_provenance.ProvenanceWriteApiTests.test_invalid_egress_origin_class_raises_before_write
```

Expected: fail with unexpected keyword argument `egress_origin_class`.

- [ ] **Step 3: Implement egress-origin metadata helpers**

In `memory/memory_manager.py`, add this import near existing imports if `KNOWN_ORIGINS` is not already imported:

```python
from core.egress.gate import KNOWN_ORIGINS
```

Add helpers near `_provenance_metadata(...)`:

```python
def _coerce_egress_origin_class(value) -> str:
    """Validate the cloud-egress origin class for a memory row.

    This is separate from provenance_source/trust_tier. Unknown values
    raise before write so typoed owner_account_context cannot launder
    into generic memory.
    """
    origin = str(value)
    if origin not in KNOWN_ORIGINS:
        valid = ", ".join(sorted(KNOWN_ORIGINS))
        raise ValueError(
            f"unknown egress_origin_class {value!r}; expected one of: {valid}"
        )
    return origin


def _egress_origin_metadata(egress_origin_class) -> dict:
    """Return write-through egress metadata for durable memory rows."""
    if egress_origin_class is None:
        return {}
    return {
        "egress_origin_class": _coerce_egress_origin_class(egress_origin_class)
    }
```

Update signatures and validation:

```python
def store(self, content: str, cycle: int, snapshot: dict | None = None,
          metadata: dict | None = None, *,
          provenance_source=None, trust_tier=None,
          egress_origin_class=None) -> str:
    provenance_extra = _provenance_metadata(provenance_source, trust_tier)
    egress_origin_extra = _egress_origin_metadata(egress_origin_class)
```

Then after `doc_metadata.update(provenance_extra)` add:

```python
doc_metadata.update(egress_origin_extra)
```

Update `store_telegram(...)` similarly:

```python
def store_telegram(self, content: str, *,
                   provenance_source=None, trust_tier=None,
                   egress_origin_class=None) -> str:
    provenance_extra = _provenance_metadata(provenance_source, trust_tier)
    egress_origin_extra = _egress_origin_metadata(egress_origin_class)
```

Then after `meta.update(provenance_extra)` add:

```python
meta.update(egress_origin_extra)
```

Update `store_core(...)` similarly:

```python
def store_core(self, content: str, source: str = "reasoning", *,
               provenance_source=None, trust_tier=None,
               egress_origin_class=None,
               promoted_from: list[str] | None = None,
               allow_untrusted_ancestors: bool = False) -> str:
```

Before `memory_id = ...`, after `provenance_extra = ...`, add:

```python
egress_origin_extra = _egress_origin_metadata(egress_origin_class)
```

Then after `meta.update(provenance_extra)` add:

```python
meta.update(egress_origin_extra)
```

- [ ] **Step 4: Run tests to verify GREEN**

Run:

```bash
.venv/bin/python -m unittest tests.test_memory_provenance
```

Expected: OK.

- [ ] **Step 5: Commit**

```bash
git add memory/memory_manager.py tests/test_memory_provenance.py
git commit -m "feat(memory): persist egress origin class on memory rows"
```

Commit body:

```text
## Predicted effect

Durable memory write APIs can carry egress_origin_class="owner_account_context";
unknown classes raise before write and legacy rows remain unchanged.

Tests: .venv/bin/python -m unittest tests.test_memory_provenance
```

---

### Task 2: Make owner-account restrictiveness explicit

**Files:**
- Modify: `core/egress/provenance.py`
- Modify: `tests/test_egress_provenance.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_egress_provenance.py`:

```python
class OwnerAccountRestrictivenessTests(unittest.TestCase):
    def test_owner_account_context_has_explicit_restrictiveness_score(self):
        import core.egress.provenance as provenance

        self.assertIn("owner_account_context", provenance._RESTRICTIVENESS)
        self.assertEqual(provenance._RESTRICTIVENESS["owner_account_context"], 3)

    def test_owner_account_context_dominates_memory_in_blended_summary(self):
        from core.egress.provenance import ProvenancedText

        owner = ProvenancedText.owner_account_context(
            "private account fact",
            source_ref="test:owner_account",
        )
        memory = ProvenancedText.memory(
            "ordinary recalled memory",
            source_ref="test:memory",
        )

        summary = ProvenancedText.blended_summary(
            "summary of both",
            sources=[memory, owner],
            source_ref="test:blend",
        )

        self.assertEqual(summary.spans[0].origin_class, "owner_account_context")
        self.assertFalse(summary.spans[0].redaction_allowed)

    def test_owner_account_context_dominates_memory_in_derived_output(self):
        from core.egress.provenance import ProvenancedText

        source = ProvenancedText.owner_account_context(
            "private account fact",
            source_ref="test:owner_account",
        )

        derived = ProvenancedText.derived_output(
            "derived private account observation",
            source=source,
            source_ref="test:derived",
        )

        self.assertEqual(derived.spans[0].origin_class, "owner_account_context")
        self.assertFalse(derived.spans[0].redaction_allowed)
```

- [ ] **Step 2: Run tests to verify RED**

Run:

```bash
.venv/bin/python -m unittest tests.test_egress_provenance.OwnerAccountRestrictivenessTests
```

Expected: fail because owner-account falls through restrictiveness handling instead of being explicit.

- [ ] **Step 3: Implement restrictiveness entry**

In `core/egress/provenance.py`, add `OWNER_ACCOUNT_CONTEXT` to the import from `core.egress.gate`:

```python
from core.egress.gate import (
    EgressSegment,
    INTENTIONAL_OUTBOUND,
    KNOWN_ORIGINS,
    MINIMIZABLE_PRIVATE_CONTEXT,
    NON_PRIVATE,
    OWNER_ACCOUNT_CONTEXT,
    RESERVED_DENIED_RAW,
    UNTRUSTED_EXTERNAL_OUTPUT,
)
```

Then update `_RESTRICTIVENESS`:

```python
_RESTRICTIVENESS = {
    **{origin: 3 for origin in RESERVED_DENIED_RAW},
    **{origin: 3 for origin in OWNER_ACCOUNT_CONTEXT},
    **{origin: 2 for origin in MINIMIZABLE_PRIVATE_CONTEXT},
    **{origin: 2 for origin in UNTRUSTED_EXTERNAL_OUTPUT},
    **{origin: 1 for origin in INTENTIONAL_OUTBOUND},
    **{origin: 0 for origin in NON_PRIVATE},
    "unclassified": 4,
}
```

- [ ] **Step 4: Run tests to verify GREEN**

Run:

```bash
.venv/bin/python -m unittest tests.test_egress_provenance.OwnerAccountRestrictivenessTests tests.test_egress_provenance
```

Expected: OK.

- [ ] **Step 5: Commit**

```bash
git add core/egress/provenance.py tests/test_egress_provenance.py
git commit -m "feat(egress): score owner-account provenance explicitly"
```

Commit body:

```text
## Predicted effect

Derived or blended output from owner_account_context keeps owner_account_context
when mixed with ordinary memory/lived-store material. The known unclassified
blend residual remains documented in the spec.

Tests: .venv/bin/python -m unittest tests.test_egress_provenance
```

---

### Task 3: Add provenanced recall renderer with per-row spans

**Files:**
- Modify: `memory/memory_manager.py`
- Create or modify: `tests/test_owner_account_memory_taint_rail.py`

- [ ] **Step 1: Write failing renderer tests**

Create `tests/test_owner_account_memory_taint_rail.py`:

```python
from __future__ import annotations

import sys
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))


def _mm():
    from memory.memory_manager import MemoryManager
    return MemoryManager.__new__(MemoryManager)


def _raw_row(row_id: str, content: str, *, egress_origin_class: str | None = None):
    meta = {
        "cycle": 7,
        "timestamp": "2026-06-04T12:00:00+00:00",
        "type": "reasoning",
    }
    if egress_origin_class:
        meta["egress_origin_class"] = egress_origin_class
    return {
        "id": row_id,
        "content": content,
        "metadata": meta,
        "distance": 0.123,
    }


class ProvenancedRecallRendererTests(unittest.TestCase):
    def test_provenanced_text_matches_existing_string_renderer(self):
        recalled = {
            "core": [{"id": "core-a", "content": "core continuity", "metadata": {}}],
            "daily": [],
            "raw": [
                _raw_row(
                    "raw-owner",
                    "OWNER_ACCOUNT_MEMORY_CANARY",
                    egress_origin_class="owner_account_context",
                ),
                _raw_row("raw-ordinary", "ordinary memory"),
            ],
        }
        mm = _mm()

        text = mm.format_for_prompt(recalled, max_chars=8000)
        provenanced = mm.format_for_prompt_provenanced(recalled, max_chars=8000)

        self.assertEqual(provenanced.text, text)

    def test_owner_account_row_gets_owner_account_span(self):
        recalled = {
            "core": [],
            "daily": [],
            "raw": [
                _raw_row(
                    "raw-owner",
                    "OWNER_ACCOUNT_MEMORY_CANARY",
                    egress_origin_class="owner_account_context",
                )
            ],
        }

        provenanced = _mm().format_for_prompt_provenanced(recalled)
        owner_spans = [
            span for span in provenanced.spans
            if "OWNER_ACCOUNT_MEMORY_CANARY" in span.text
        ]

        self.assertTrue(owner_spans)
        self.assertTrue(
            all(span.origin_class == "owner_account_context" for span in owner_spans)
        )
        self.assertTrue(all(not span.redaction_allowed for span in owner_spans))

    def test_mixed_recall_uses_per_row_spans(self):
        recalled = {
            "core": [],
            "daily": [],
            "raw": [
                _raw_row(
                    "raw-owner",
                    "OWNER_ACCOUNT_MEMORY_CANARY",
                    egress_origin_class="owner_account_context",
                ),
                _raw_row("raw-ordinary", "ORDINARY_MEMORY_CANARY"),
            ],
        }

        provenanced = _mm().format_for_prompt_provenanced(recalled)
        owner_origins = {
            span.origin_class
            for span in provenanced.spans
            if "OWNER_ACCOUNT_MEMORY_CANARY" in span.text
        }
        ordinary_origins = {
            span.origin_class
            for span in provenanced.spans
            if "ORDINARY_MEMORY_CANARY" in span.text
        }

        self.assertEqual(owner_origins, {"owner_account_context"})
        self.assertEqual(ordinary_origins, {"memory"})
        self.assertIn("owner_account_context", {s.origin_class for s in provenanced.spans})
        self.assertIn("memory", {s.origin_class for s in provenanced.spans})

    def test_legacy_rows_have_no_owner_account_span(self):
        recalled = {
            "core": [{"id": "core-a", "content": "legacy core", "metadata": {}}],
            "daily": [],
            "raw": [_raw_row("raw-ordinary", "legacy raw")],
        }

        provenanced = _mm().format_for_prompt_provenanced(recalled)

        self.assertNotIn(
            "owner_account_context",
            {span.origin_class for span in provenanced.spans},
        )
        self.assertIn("memory", {span.origin_class for span in provenanced.spans})
```

- [ ] **Step 2: Run tests to verify RED**

Run:

```bash
.venv/bin/python -m unittest tests.test_owner_account_memory_taint_rail.ProvenancedRecallRendererTests
```

Expected: fail because `format_for_prompt_provenanced` does not exist.

- [ ] **Step 3: Implement renderer with shared line parts**

In `memory/memory_manager.py`, add imports near the top:

```python
from dataclasses import dataclass
from core.egress.provenance import ProvenanceSpan, ProvenancedText
```

Add a small internal render-line class near the memory provenance helpers:

```python
@dataclass(frozen=True)
class _RecallRenderLine:
    text: str
    origin_class: str
    source_ref: str
    redaction_allowed: bool
```

Add helpers near `_egress_origin_metadata(...)`:

```python
def _redaction_allowed_for_origin(origin_class: str) -> bool:
    from core.egress.gate import MINIMIZABLE_PRIVATE_CONTEXT, UNTRUSTED_EXTERNAL_OUTPUT

    return (
        origin_class in MINIMIZABLE_PRIVATE_CONTEXT
        or origin_class in UNTRUSTED_EXTERNAL_OUTPUT
    )


def _memory_row_origin(meta: dict | None) -> str:
    meta = meta or {}
    raw = meta.get("egress_origin_class")
    if not raw:
        return "memory"
    return _coerce_egress_origin_class(raw)


def _memory_row_source_ref(tier: str, mem_id: str) -> str:
    return f"memory:{tier}:{mem_id}"
```

Refactor `format_for_prompt(...)` by extracting its body into a private line renderer:

```python
    def _format_for_prompt_lines(
        self,
        recalled: dict,
        max_chars: "int | None" = None,
    ) -> list[_RecallRenderLine]:
        core = recalled.get("core", []) or []
        daily = recalled.get("daily", []) or []
        raw = recalled.get("raw", []) or []

        if not (core or daily or raw):
            return []

        now = datetime.now(timezone.utc)
        lines: list[_RecallRenderLine] = []

        def add_system(text: str) -> None:
            lines.append(_RecallRenderLine(
                text=text,
                origin_class="system_bounded_query",
                source_ref="memory:recall_renderer:framing",
                redaction_allowed=False,
            ))

        def add_row_line(text: str, *, tier: str, mem_id: str, meta: dict | None) -> None:
            origin = _memory_row_origin(meta)
            lines.append(_RecallRenderLine(
                text=text,
                origin_class=origin,
                source_ref=_memory_row_source_ref(tier, mem_id),
                redaction_allowed=_redaction_allowed_for_origin(origin),
            ))
```

Then move the existing `format_for_prompt(...)` line-building logic into this helper, replacing:

```python
lines.append("text")
```

for framing/header/tail with:

```python
add_system("text")
```

and replacing each core/daily/raw block append with `add_row_line(...)`. For example, the raw block becomes:

```python
            mem_id = str(mem.get("id", f"raw-{i}"))[:16]
            # ...
            add_row_line(
                f'<RECALLED tier="raw" age="{age}" cycle="{cycle}" '
                f'timestamp="{ts_str}" id="{mem_id}"{dist_attr}{prov}{temporal}>',
                tier="raw",
                mem_id=mem_id,
                meta=meta,
            )
            add_row_line(content, tier="raw", mem_id=mem_id, meta=meta)
            add_row_line("</RECALLED>", tier="raw", mem_id=mem_id, meta=meta)
            add_row_line("", tier="raw", mem_id=mem_id, meta=meta)
```

Keep the existing raw truncation invariant by deleting four `_RecallRenderLine` objects:

```python
del lines[start : start + 4]
```

End the helper with:

```python
        return lines
```

Rewrite `format_for_prompt(...)` as:

```python
    def format_for_prompt(self, recalled: dict, max_chars: "int | None" = None) -> str:
        """Format multi-tier recalled memories into a structured prompt block."""
        return "\n".join(line.text for line in self._format_for_prompt_lines(
            recalled,
            max_chars=max_chars,
        ))
```

Add the new method:

```python
    def format_for_prompt_provenanced(
        self,
        recalled: dict,
        max_chars: "int | None" = None,
    ) -> ProvenancedText:
        """Format recalled memories as text plus per-row egress provenance."""
        lines = self._format_for_prompt_lines(recalled, max_chars=max_chars)
        spans: list[ProvenanceSpan] = []
        for idx, line in enumerate(lines):
            text = line.text
            if idx < len(lines) - 1:
                text += "\n"
            if not text:
                continue
            spans.append(ProvenanceSpan(
                text=text,
                origin_class=line.origin_class,
                source_ref=line.source_ref,
                redaction_allowed=line.redaction_allowed,
            ))
        return ProvenancedText.from_spans(spans)
```

- [ ] **Step 4: Run renderer tests**

Run:

```bash
.venv/bin/python -m unittest \
  tests.test_owner_account_memory_taint_rail.ProvenancedRecallRendererTests \
  tests.test_memory_manager \
  tests.test_memory_provenance_5xc
```

Expected: OK. Pay special attention to `.text == format_for_prompt(...)`.

- [ ] **Step 5: Commit**

```bash
git add memory/memory_manager.py tests/test_owner_account_memory_taint_rail.py
git commit -m "feat(memory): render recalled owner-account rows with egress spans"
```

Commit body:

```text
## Predicted effect

Cloud-bound recall can carry per-row egress provenance while the existing
string prompt renderer remains byte-equivalent for legacy/local callers.

Tests: .venv/bin/python -m unittest tests.test_owner_account_memory_taint_rail tests.test_memory_manager tests.test_memory_provenance_5xc
```

---

### Task 4: Wire web owner-bridge cloud payload to provenanced recall

**Files:**
- Modify: `skills/web_interface.py`
- Modify: `tests/test_egress_claude_router_provenance.py`

- [ ] **Step 1: Write failing payload test**

In `tests/test_egress_claude_router_provenance.py`, update `test_web_interface_has_provenance_payload_builder_at_insertion_points` to pass a `ProvenancedText` owner memory and assert its origin survives:

```python
        from core.egress.provenance import ProvenancedText

        _, messages = build_claude_router_cloud_payload(
            owner_bridge=True,
            message="What does this code do?",
            history=[
                {"role": "user", "content": "raw prior turn"},
                {"role": "user", "content": "What does this code do?"},
            ],
            owner_memory=ProvenancedText.owner_account_context(
                "OWNER_ACCOUNT_MEMORY_CANARY",
                source_ref="memory:raw:owner-canary",
            ),
            lived_brief="lived recall",
            envelope={"status": "ok", "sources": []},
            envelope_block="Evidence envelope",
            jarvis_transcript_web="tool transcript",
        )

        origins = [
            span.origin_class
            for message in messages
            for span in message["content"].spans
        ]
        self.assertIn("owner_account_context", origins)
        self.assertIn("memory", origins)
        self.assertIn("unclassified", origins)
        self.assertIn("lived_store", origins)
        self.assertIn("owner_message_context", origins)
```

- [ ] **Step 2: Run test to verify RED**

Run:

```bash
.venv/bin/python -m unittest tests.test_egress_claude_router_provenance.WebInterfaceCloudAsToolTests.test_web_interface_has_provenance_payload_builder_at_insertion_points
```

Expected: fail because `owner_memory` is wrapped as generic memory or treated as a string.

- [ ] **Step 3: Update payload builder and chat path**

In `skills/web_interface.py`, change the `build_claude_router_cloud_payload(...)` signature:

```python
    owner_memory: object = "",
```

Then replace the owner-memory block with:

```python
    if owner_bridge and owner_memory:
        owner_prefix = (
            "Shared continuity with the owner from the long-running private channel:\n\n"
        )
        if isinstance(owner_memory, ProvenancedText):
            owner_memory_content = (
                ProvenancedText.memory(
                    owner_prefix,
                    source_ref="web_interface:owner_memory_prefix",
                )
                + owner_memory
            )
        else:
            owner_memory_content = ProvenancedText.memory(
                owner_prefix + str(owner_memory),
                source_ref="web_interface:owner_memory",
            )
        cloud_messages.append({
            "role": "user",
            "content": owner_memory_content,
        })
```

In the owner-bridge chat path, compute recall once and render both views:

```python
        owner_recalled = memory.recall_for_telegram(message)
        owner_memory = memory.format_for_prompt(
            owner_recalled,
            max_chars=resolve_recall_cap_chars(),
        )
        owner_memory_cloud = memory.format_for_prompt_provenanced(
            owner_recalled,
            max_chars=resolve_recall_cap_chars(),
        )
```

Then pass `owner_memory_cloud` into the cloud payload:

```python
                owner_memory=owner_memory_cloud if owner_bridge else "",
```

Keep the local `messages_list` path using `owner_memory` as a string.

- [ ] **Step 4: Run tests**

Run:

```bash
.venv/bin/python -m unittest tests.test_egress_claude_router_provenance.WebInterfaceCloudAsToolTests
```

Expected: OK.

- [ ] **Step 5: Commit**

```bash
git add skills/web_interface.py tests/test_egress_claude_router_provenance.py
git commit -m "feat(web): preserve owner-account recall spans in cloud payload"
```

Commit body:

```text
## Predicted effect

The web owner-bridge local prompt keeps the existing string recall block, while
the cloud consult receives a ProvenancedText recall block whose owner-account
rows remain owner_account_context.

Tests: .venv/bin/python -m unittest tests.test_egress_claude_router_provenance.WebInterfaceCloudAsToolTests
```

---

### Task 5: Add end-to-end canary witness through builder, claude_tier, and proxy

**Files:**
- Modify: `tests/test_owner_account_memory_taint_rail.py`

- [ ] **Step 1: Add failing canary test**

Append to `tests/test_owner_account_memory_taint_rail.py`:

```python
import importlib
import json
import os
import sqlite3
import tempfile
from unittest import mock

from fastapi import HTTPException
from starlette.requests import Request

from core.subscription_proxy.adapters.base import CallResult


class _NeverCalledAdapter:
    name = "owner_memory_canary"

    def __init__(self):
        self.prompts = []

    def handles_model(self, model: str) -> bool:
        return model == "owner-memory-test"

    def health(self) -> dict:
        return {"adapter": self.name, "ok": True}

    async def call(self, *, prompt, system_prompt, model):
        self.prompts.append(prompt)
        return CallResult(
            reply="must never be produced",
            model_used=model,
            input_toks=1,
            output_toks=1,
        )


def _make_proxy_request(body: dict):
    raw = json.dumps(body).encode("utf-8")

    async def receive():
        return {"type": "http.request", "body": raw, "more_body": False}

    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/v1/chat/completions",
            "headers": [(b"x-maez-caller", b"owner-memory-canary")],
        },
        receive,
    )


class OwnerAccountMemoryCanaryProxyTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self._tmp.name) / "proxy.db"
        self._env = mock.patch.dict(
            os.environ,
            {
                "MAEZ_SUBSCRIPTION_PROXY_DB": str(self.db_path),
                "MAEZ_EGRESS_TELEMETRY_KEY": "owner-memory-canary-test",
            },
            clear=False,
        )
        self._env.start()
        from core.subscription_proxy import server

        importlib.reload(server)
        self.server = server
        self.adapter = _NeverCalledAdapter()
        self._adapters = mock.patch.object(server, "ADAPTERS", [self.adapter])
        self._adapters.start()

    def tearDown(self):
        self._adapters.stop()
        self._env.stop()
        self._tmp.cleanup()

    async def test_owner_account_memory_recalled_to_cloud_is_refused(self):
        from core.routing import claude_tier
        from skills.web_interface import build_claude_router_cloud_payload

        recalled = {
            "core": [],
            "daily": [],
            "raw": [
                _raw_row(
                    "raw-owner",
                    "OWNER_ACCOUNT_MEMORY_CANARY",
                    egress_origin_class="owner_account_context",
                )
            ],
        }
        owner_memory = _mm().format_for_prompt_provenanced(recalled)
        system_prompt, web_messages = build_claude_router_cloud_payload(
            owner_bridge=True,
            message="can you reason about this?",
            history=[{"role": "user", "content": "can you reason about this?"}],
            owner_memory=owner_memory,
        )
        cloud_messages = [
            claude_tier.CloudMessage(role=m["role"], content=m["content"])
            for m in web_messages
        ]

        captured: dict = {}

        def _capture_payload(*, body_payload, model, caller, timeout_s=None):
            captured["body"] = body_payload
            from core.claude_tier import TierReply

            return TierReply("not used", model, 1, 1, {})

        with mock.patch(
            "core.routing.claude_tier._post_chat_payload",
            side_effect=_capture_payload,
        ):
            claude_tier.call_messages(
                system_prompt=system_prompt,
                messages=cloud_messages,
                model="owner-memory-test",
                caller="owner-memory-canary",
            )

        with self.assertRaises(HTTPException) as ctx:
            await self.server.chat_completions(_make_proxy_request(captured["body"]))

        self.assertEqual(ctx.exception.status_code, 403)
        self.assertEqual(self.adapter.prompts, [])

        with sqlite3.connect(self.db_path) as con:
            row = con.execute(
                "SELECT egress_decision, egress_reason_codes, egress_shadow_mode, "
                "prompt_preview, egress_origin_classes FROM calls"
            ).fetchone()

        self.assertIsNotNone(row)
        decision, reasons, shadow_mode, prompt_preview, origin_classes = row
        self.assertEqual(decision, "block")
        self.assertIn("owner_account_context_blocked_default", reasons)
        self.assertEqual(shadow_mode, 0)
        self.assertIn("owner_account_context", origin_classes)
        self.assertNotIn("OWNER_ACCOUNT_MEMORY_CANARY", prompt_preview or "")
```

- [ ] **Step 2: Run test to verify RED**

Run:

```bash
.venv/bin/python -m unittest tests.test_owner_account_memory_taint_rail.OwnerAccountMemoryCanaryProxyTests
```

Expected before Tasks 3-4 implementation: fail because provenanced renderer/payload path is missing or flattened. After Tasks 3-4, if it passes immediately, mutation-test by changing the builder to wrap `str(owner_memory)` as `ProvenancedText.memory(...)`; the test must fail.

- [ ] **Step 3: Run canary GREEN**

Run:

```bash
.venv/bin/python -m unittest tests.test_owner_account_memory_taint_rail
```

Expected: OK.

- [ ] **Step 4: Commit**

```bash
git add tests/test_owner_account_memory_taint_rail.py
git commit -m "test(egress): witness owner-account memory blocked at proxy"
```

Commit body:

```text
## Predicted effect

A durable-memory row tagged owner_account_context, when recalled into the web
owner-bridge cloud consult, reaches the proxy as owner_account_context and is
403-blocked before any adapter call.

Tests: .venv/bin/python -m unittest tests.test_owner_account_memory_taint_rail
```

---

### Task 6: Add forward guard for recall-to-cloud surfaces

**Files:**
- Create: `tests/test_owner_account_memory_cloud_surface_guard.py`

- [ ] **Step 1: Write failing guard**

Create `tests/test_owner_account_memory_cloud_surface_guard.py`:

```python
from __future__ import annotations

import sys
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))


PRODUCTION_ROOTS = ("core", "daemon", "memory", "skills")


def _production_py_files() -> list[Path]:
    files: list[Path] = []
    for root in PRODUCTION_ROOTS:
        files.extend((_REPO / root).rglob("*.py"))
    return [
        path for path in files
        if "__pycache__" not in path.parts and path.name != "__init__.py"
    ]


class OwnerAccountMemoryCloudSurfaceGuardTests(unittest.TestCase):
    def test_web_owner_bridge_uses_provenanced_recall_for_cloud(self):
        src = (_REPO / "skills" / "web_interface.py").read_text(encoding="utf-8")
        self.assertIn("owner_recalled = memory.recall_for_telegram(message)", src)
        self.assertIn("memory.format_for_prompt(owner_recalled", src)
        self.assertIn("memory.format_for_prompt_provenanced(owner_recalled", src)
        self.assertRegex(
            src,
            r"build_claude_router_cloud_payload\([\s\S]*owner_memory="
            r"owner_memory_cloud if owner_bridge else \"\"",
        )

    def test_no_recall_to_cloud_path_uses_raw_format_for_prompt_only(self):
        offenders: list[str] = []
        for path in _production_py_files():
            src = path.read_text(encoding="utf-8")
            if "call_claude(" not in src and "call_messages(" not in src:
                continue
            if "format_for_prompt(" not in src:
                continue
            if "format_for_prompt_provenanced(" in src:
                continue
            offenders.append(str(path.relative_to(_REPO)))

        self.assertEqual(
            offenders,
            [],
            "cloud-bound recalled memory must use format_for_prompt_provenanced: "
            + ", ".join(offenders),
        )

    def test_known_local_recall_surfaces_remain_enumerated(self):
        expected_local = {
            "daemon/maez_daemon.py",
            "skills/telegram_voice.py",
            "core/brain/brain_loop.py",
        }
        actual_local = set()
        for path in _production_py_files():
            src = path.read_text(encoding="utf-8")
            if "format_for_prompt(" in src and "call_claude(" not in src:
                rel = str(path.relative_to(_REPO))
                if rel in expected_local:
                    actual_local.add(rel)

        self.assertEqual(actual_local, expected_local)
```

- [ ] **Step 2: Run guard to verify RED or strict GREEN**

Run:

```bash
.venv/bin/python -m unittest tests.test_owner_account_memory_cloud_surface_guard
```

Expected: If Task 4 is already implemented, this may pass. Mutation-test by changing `owner_memory_cloud` back to `owner_memory` in the cloud call; the first guard must fail.

- [ ] **Step 3: Commit**

```bash
git add tests/test_owner_account_memory_cloud_surface_guard.py
git commit -m "test(egress): guard recalled memory cloud surfaces"
```

Commit body:

```text
## Predicted effect

Future recall-to-cloud surfaces fail tests unless they use the provenanced recall
renderer or deliberately update the surface enumeration.

Tests: .venv/bin/python -m unittest tests.test_owner_account_memory_cloud_surface_guard
```

---

### Task 7: Regression, mutation checks, and final review prep

**Files:**
- No new files expected.

- [ ] **Step 1: Run focused test set**

Run:

```bash
.venv/bin/python -m unittest \
  tests.test_memory_provenance \
  tests.test_memory_manager \
  tests.test_memory_provenance_5xc \
  tests.test_owner_account_memory_taint_rail \
  tests.test_owner_account_memory_cloud_surface_guard \
  tests.test_egress_provenance \
  tests.test_egress_claude_router_provenance \
  tests.test_subscription_proxy_owner_account_enforcement
```

Expected: OK.

- [ ] **Step 2: Run mutation checks manually**

Perform these temporary edits one at a time, run the named test, then restore:

1. Change `_coerce_egress_origin_class(...)` to return `"memory"` for unknown values.

Run:

```bash
.venv/bin/python -m unittest tests.test_memory_provenance.ProvenanceWriteApiTests.test_invalid_egress_origin_class_raises_before_write
```

Expected: FAIL.

2. Change `build_claude_router_cloud_payload(...)` to wrap `str(owner_memory)` as `ProvenancedText.memory(...)`.

Run:

```bash
.venv/bin/python -m unittest tests.test_owner_account_memory_taint_rail.OwnerAccountMemoryCanaryProxyTests
```

Expected: FAIL because the proxy no longer sees `owner_account_context`.

3. Remove `"owner_account_context"` from the synthetic row metadata in `test_owner_account_memory_recalled_to_cloud_is_refused`.

Run:

```bash
.venv/bin/python -m unittest tests.test_owner_account_memory_taint_rail.OwnerAccountMemoryCanaryProxyTests
```

Expected: FAIL because the canary reaches the adapter or no longer blocks.

- [ ] **Step 3: Run lint and compile**

Run:

```bash
.venv/bin/ruff check memory/memory_manager.py core/egress/provenance.py skills/web_interface.py tests/test_memory_provenance.py tests/test_owner_account_memory_taint_rail.py tests/test_owner_account_memory_cloud_surface_guard.py tests/test_egress_claude_router_provenance.py tests/test_egress_provenance.py
.venv/bin/python -m compileall memory/memory_manager.py core/egress/provenance.py skills/web_interface.py tests/test_owner_account_memory_taint_rail.py tests/test_owner_account_memory_cloud_surface_guard.py
```

Expected: ruff clean; compileall success.

- [ ] **Step 4: Run full suite floor**

Run:

```bash
.venv/bin/python -m unittest discover -s tests -p 'test_*.py'
```

Expected: no new failures relative to current main floor. If ambient failures occur, rerun the exact failing tests on main before claiming them ambient.

- [ ] **Step 5: Final commit if needed**

If mutation-check restoration or lint fixes changed files:

```bash
git add memory/memory_manager.py core/egress/provenance.py skills/web_interface.py tests/test_memory_provenance.py tests/test_owner_account_memory_taint_rail.py tests/test_owner_account_memory_cloud_surface_guard.py tests/test_egress_claude_router_provenance.py tests/test_egress_provenance.py
git commit -m "test(memory): prove owner-account taint rail end to end"
```

Commit body:

```text
## Predicted effect

Owner-account-derived durable memory is safe to recall into the web owner-bridge
cloud consult because its egress_origin_class survives as owner_account_context
and the proxy blocks it before adapter execution.

Tests: focused unittest set, mutation checks, ruff, compileall, full unittest floor
```

---

## Self-Review Checklist

- Spec §1 covered by Task 6 enumeration guard.
- Spec §2 covered by Task 1 stored `egress_origin_class`.
- Spec §3.1 covered by Task 1 validation/write-through.
- Spec §3.2 covered by Task 2 restrictiveness tests.
- Spec §3.3 covered by Task 3 per-row provenanced renderer and `.text` equality.
- Spec §3.4 covered by Task 4 web owner-bridge wiring.
- Spec §4 covered by Task 1 legacy no-field behavior and Task 3 legacy renderer behavior.
- Spec §5 acceptance rule 7 covered by Task 5 canary witness.
- Spec §7 no real account ingestion maintained: tests use synthetic rows only; no GitHub/Reddit API calls.
