# Recall-Origin Egress Canary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A standing unittest canary proving that recalled untrusted/private/PII-bearing memory keeps its origin provenance from storage into the cloud gate, is **full-fidelity locally** but **blocked/redacted at the cloud door**, and **fails closed** on missing/ambiguous provenance.

**Architecture:** A single new test file `tests/test_recall_origin_egress_canary.py` in the egress-canary family. It (1) drives the **real** recall path for a recall-fidelity case (hermetic seeded store via the `recall_flip_eval` sandbox), and (2) reuses the `test_owner_account_memory_taint_rail.py` proxy-drive pattern (`format_for_prompt_provenanced` → `build_claude_router_cloud_payload` → `claude_tier.call_messages` → `subscription_proxy.chat_completions`) for the render/egress cases, plus fast `decide_egress` unit cases.

**Tech Stack:** Python 3.14, `unittest` (NOT pytest), `unittest.IsolatedAsyncioTestCase` for the async proxy cases, `fastapi`/`starlette` (the proxy), the egress gate + cloud redactor.

**Spec:** `docs/superpowers/specs/2026-06-05-recall-origin-egress-canary-design.md`

**⚠️ TDD POSTURE — read spec §5.** This canary **asserts existing production behavior**, so each case is **green-expected**. It is NOT red-first-then-implement. **If a case goes RED, you have found a real leak — STOP and report it as a finding; do NOT weaken the assertion and do NOT add a production fix inside this slice.** No production code changes here at all.

**Test runner:** `.venv/bin/python -B -m unittest <dotted.path> -v`. Full `discover` before done. Apples-to-apples in `/home/rohit/maez`. **No `## Predicted effect`** (test-only).

---

## File Structure

| File | Responsibility |
|------|----------------|
| `tests/test_recall_origin_egress_canary.py` | The entire canary — recall-fidelity, local-render full-fidelity, provenance spans, `decide_egress` policy matrix + fail-closed, and the two proxy-path cases (block / redact-audit). |

**Reused (imported, not modified):** `scripts/recall_flip_eval/sandbox.py` (hermetic seed for the real-recall case); `core/egress/gate.py` (`EgressRequest`, `EgressSegment`, `decide_egress`); `memory/memory_manager.py` (`MemoryManager`, `format_for_prompt`, `format_for_prompt_provenanced`); `skills/web_interface.py` (`build_claude_router_cloud_payload`); `core/routing/claude_tier.py` (`call_messages`, `CloudMessage`, `_post_chat_payload`); `core/subscription_proxy/server.py` (`chat_completions`, `ADAPTERS`). **Template:** `tests/test_owner_account_memory_taint_rail.py`.

**Untouched:** all production code.

---

## Task 1: Recall-fidelity — the wristband survives real recall

**Files:**
- Create: `tests/test_recall_origin_egress_canary.py`

Prove that a stored memory tagged with an `egress_origin_class` keeps that tag through the **real** `recall_for_telegram` path (the "verify the row surfaces in the recalled dict with correct metadata" step). A core row is used so no embedding model is needed (`get_all_core` is unconditional).

- [ ] **Step 1: Write the canary file header + the recall-fidelity test**

```python
# tests/test_recall_origin_egress_canary.py
"""Recall-Origin Egress Canary — a standing safety invariant.

GREEN-EXPECTED: this asserts existing egress behavior. A RED case means a real
leak was found — escalate it as a finding; never weaken an assertion or add a
production fix in this file. See
docs/superpowers/specs/2026-06-05-recall-origin-egress-canary-design.md.
"""
from __future__ import annotations

import importlib
import json
import os
import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest import mock

from fastapi import HTTPException
from starlette.requests import Request

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

_PII_MARKER = "canary-pii-7c1f@example.test"


class RecallFidelityTests(unittest.TestCase):
    """The egress_origin_class wristband survives the real recall path."""

    def test_core_row_origin_survives_real_recall(self):
        from scripts.recall_flip_eval import sandbox

        root = Path(tempfile.mkdtemp(prefix="recall_origin_canary_"))
        ctx = sandbox.sandbox_env(root)
        ctx.__enter__()
        self.addCleanup(ctx.__exit__, None, None, None)
        self.addCleanup(sandbox.restore_memory_patches)
        self.addCleanup(sandbox.teardown, root)
        sandbox.patch_memory_manager_base_db(root)
        sandbox.assert_sandbox(root)

        from memory.memory_manager import MemoryManager

        seeder = MemoryManager()
        seeder.core.add(
            ids=["core-priv-canary"],
            documents=[f"Reach the owner at {_PII_MARKER} per the private note."],
            metadatas=[{
                "timestamp": "2026-06-04T12:00:00+00:00",
                "type": "reasoning",
                "egress_origin_class": "third_party_private_context",
            }],
        )

        recalled = MemoryManager().recall_for_telegram("what should I know?")
        core_rows = recalled.get("core") or []
        match = [r for r in core_rows if r.get("id") == "core-priv-canary"]
        self.assertTrue(match, "seeded core row did not surface via real recall")
        meta = match[0].get("metadata") or {}
        # the wristband survived recall
        self.assertEqual(meta.get("egress_origin_class"), "third_party_private_context")
        # and the content is intact (local full fidelity at the recall layer)
        self.assertIn(_PII_MARKER, match[0].get("content", ""))
```

- [ ] **Step 2: Run it — EXPECT GREEN**

Run: `.venv/bin/python -B -m unittest tests.test_recall_origin_egress_canary.RecallFidelityTests -v`
Expected: PASS. **If RED:** recall is dropping `egress_origin_class` metadata — a real finding (the wristband is lost at recall). Stop and report; do not patch here.

- [ ] **Step 3: Commit**

```bash
git add tests/test_recall_origin_egress_canary.py
git commit -m "test(privacy): recall-origin canary — origin survives real recall

GREEN-expected safety invariant: a core row tagged egress_origin_class keeps
the tag through the real recall_for_telegram path. Test-only.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2: Local render full-fidelity + provenance spans

**Files:**
- Modify: `tests/test_recall_origin_egress_canary.py`

The covenant assertion (`format_for_prompt` keeps the full content locally) sitting beside the provenance assertion (`format_for_prompt_provenanced` carries the origin span). Uses a bare `MemoryManager` + hand-built recalled dict (the template's `_mm`/`_raw_row`), justified by Task 1's proof that real recall preserves the metadata.

- [ ] **Step 1: Add the `_mm`/`_raw_row` helpers + the render tests**

```python
# Append to tests/test_recall_origin_egress_canary.py

def _mm():
    from memory.memory_manager import MemoryManager
    return MemoryManager.__new__(MemoryManager)


def _raw_row(row_id: str, content: str, *, egress_origin_class: str | None = None):
    meta = {"cycle": 7, "timestamp": "2026-06-04T12:00:00+00:00", "type": "reasoning"}
    if egress_origin_class:
        meta["egress_origin_class"] = egress_origin_class
    return {"id": row_id, "content": content, "metadata": meta, "distance": 0.123}


class LocalRenderFidelityTests(unittest.TestCase):
    def test_local_render_keeps_full_content(self):
        # COVENANT: local-first means the local render is full-fidelity; refusal
        # lives at the cloud door, never here. This asserts we do NOT lobotomize.
        recalled = {
            "core": [], "daily": [],
            "raw": [_raw_row("raw-priv", f"email {_PII_MARKER}",
                             egress_origin_class="third_party_private_context")],
        }
        rendered = _mm().format_for_prompt(recalled)
        self.assertIn(_PII_MARKER, rendered)

    def test_provenanced_render_carries_origin_span(self):
        recalled = {
            "core": [], "daily": [],
            "raw": [_raw_row("raw-priv", f"email {_PII_MARKER}",
                             egress_origin_class="third_party_private_context")],
        }
        provenanced = _mm().format_for_prompt_provenanced(recalled)
        priv = [s for s in provenanced.spans
                if s.origin_class == "third_party_private_context"]
        self.assertTrue(priv, "private-origin span missing from provenanced render")
        self.assertTrue(all(s.redaction_allowed for s in priv))
        # local provenanced text is still byte-faithful (full content present)
        self.assertIn(_PII_MARKER, provenanced.text)
```

- [ ] **Step 2: Run it — EXPECT GREEN**

Run: `.venv/bin/python -B -m unittest tests.test_recall_origin_egress_canary.LocalRenderFidelityTests -v`
Expected: PASS. **If RED on `test_local_render_keeps_full_content`:** the local render is stripping content — a covenant violation (over-redaction locally), report it. **If RED on the span test:** the provenance is not flowing from row metadata — report it.

- [ ] **Step 3: Commit**

```bash
git add tests/test_recall_origin_egress_canary.py
git commit -m "test(privacy): recall-origin canary — local full fidelity + origin spans

format_for_prompt keeps full content locally (covenant); provenanced render
carries the origin span with redaction_allowed. Test-only.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 3: `decide_egress` policy matrix + fail-closed

**Files:**
- Modify: `tests/test_recall_origin_egress_canary.py`

Fast, deterministic per-origin decisions at the gate. Pins the matrix the proxy-path cases exercise one slice of, and makes fail-closed a first-class assertion.

- [ ] **Step 1: Add the gate-matrix tests**

```python
# Append to tests/test_recall_origin_egress_canary.py

def _seg(origin_class: str, *, text: str, redaction_allowed: bool):
    from core.egress.gate import EgressSegment
    return EgressSegment(text=text, origin_class=origin_class,
                         source_ref="raw:canary", redaction_allowed=redaction_allowed)


def _cloud_req(segment):
    from core.egress.gate import EgressRequest
    return EgressRequest(call_class="cloud_model_inference", destination="anthropic",
                         segments=[segment], caller="recall-origin-canary",
                         request_id="canary")


class DecideEgressMatrixTests(unittest.TestCase):
    def _decide(self, origin_class, *, redaction_allowed):
        from core.egress.gate import decide_egress
        return decide_egress(_cloud_req(
            _seg(origin_class, text=f"email {_PII_MARKER}", redaction_allowed=redaction_allowed)))

    def test_owner_account_blocks(self):
        self.assertEqual(self._decide("owner_account_context", redaction_allowed=False).decision, "block")

    def test_private_minimizable_redacts_pii_free(self):
        d = self._decide("third_party_private_context", redaction_allowed=True)
        self.assertEqual(d.decision, "redact")
        self.assertNotIn(_PII_MARKER, d.sanitized_text())

    def test_owner_message_context_redacts(self):
        self.assertEqual(self._decide("owner_message_context", redaction_allowed=True).decision, "redact")

    def test_untrusted_model_output_redacts(self):
        d = self._decide("model_output", redaction_allowed=True)
        self.assertEqual(d.decision, "redact")
        self.assertNotIn(_PII_MARKER, d.sanitized_text())

    def test_non_private_allows(self):
        self.assertEqual(self._decide("public_fact", redaction_allowed=False).decision, "allow")

    def test_missing_origin_falls_back_to_memory_redacts(self):
        # A row with no egress_origin_class renders as "memory" in provenance.
        self.assertEqual(self._decide("memory", redaction_allowed=True).decision, "redact")

    def test_unknown_origin_fails_closed_never_allows(self):
        # The single most important fail-closed assertion.
        d = self._decide("some_unrecognized_origin_xyz", redaction_allowed=True)
        self.assertIn(d.decision, ("block", "redact"))
        self.assertNotEqual(d.decision, "allow")
```

- [ ] **Step 2: Run it — EXPECT GREEN**

Run: `.venv/bin/python -B -m unittest tests.test_recall_origin_egress_canary.DecideEgressMatrixTests -v`
Expected: PASS. **If `test_unknown_origin_fails_closed_never_allows` is RED (decision == "allow"):** an unknown origin is being treated as public — a real under-protection finding, escalate. **If a redact case keeps the PII in `sanitized_text()`:** the redactor is not catching that PII shape — report it (and note: `redact_for_cloud` patterns may not cover every PII form — choose a marker shape it does cover, e.g. an email, per `cloud_redactor.py`).

- [ ] **Step 3: Commit**

```bash
git add tests/test_recall_origin_egress_canary.py
git commit -m "test(privacy): recall-origin canary — decide_egress matrix + fail-closed

owner_account->block; private/owner-msg/model_output->redact (PII-free);
public->allow; missing->memory->redact; unknown->never allow (fail-closed).
Test-only.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 4: Proxy-path block-class (owner-account, enforced)

**Files:**
- Modify: `tests/test_recall_origin_egress_canary.py`

The "door receives the right provenance" proof for the **enforced** class — recalled owner-account memory drives the real proxy and is refused (403, adapter never reached). This mirrors the taint-rail; it is the precedent/regression case (one test, not the center).

- [ ] **Step 1: Add the proxy-drive scaffolding + the block test**

```python
# Append to tests/test_recall_origin_egress_canary.py
from core.subscription_proxy.adapters.base import CallResult


class _CapturingAdapter:
    name = "recall-origin-canary"

    def __init__(self):
        self.prompts = []

    def handles_model(self, model: str) -> bool:
        return model == "recall-origin-canary-model"

    def health(self) -> dict:
        return {"adapter": self.name, "ok": True}

    async def call(self, *, prompt, system_prompt, model):
        self.prompts.append(prompt)
        return CallResult(reply="captured", model_used=model, input_toks=1, output_toks=1)


def _make_proxy_request(body: dict):
    raw = json.dumps(body).encode("utf-8")

    async def receive():
        return {"type": "http.request", "body": raw, "more_body": False}

    return Request(
        {"type": "http", "method": "POST", "path": "/v1/chat/completions",
         "headers": [(b"x-maez-caller", b"recall-origin-canary")]},
        receive,
    )


def _drive_to_proxy(server, *, recalled, adapter):
    """Recalled dict -> provenanced render -> payload -> call_messages -> capture body."""
    from core.routing import claude_tier
    from skills.web_interface import build_claude_router_cloud_payload

    owner_memory = _mm().format_for_prompt_provenanced(recalled)
    system_prompt, web_messages = build_claude_router_cloud_payload(
        owner_bridge=True,
        message="can you reason about this?",
        history=[{"role": "user", "content": "can you reason about this?"}],
        owner_memory=owner_memory,
    )
    cloud_messages = [claude_tier.CloudMessage(role=m["role"], content=m["content"])
                      for m in web_messages]
    captured: dict = {}

    def _capture(*, body_payload, model, caller, timeout_s=None):
        captured["body"] = body_payload
        from core.claude_tier import TierReply
        return TierReply("not used", model, 1, 1, {})

    with mock.patch("core.routing.claude_tier._post_chat_payload", side_effect=_capture):
        claude_tier.call_messages(
            system_prompt=system_prompt, messages=cloud_messages,
            model="recall-origin-canary-model", caller="recall-origin-canary",
        )
    return captured["body"]


class _ProxyCanaryBase(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self._tmp.name) / "proxy.db"
        self._env = mock.patch.dict(os.environ, {
            "MAEZ_SUBSCRIPTION_PROXY_DB": str(self.db_path),
            "MAEZ_EGRESS_TELEMETRY_KEY": "recall-origin-canary-test",
            "MAEZ_SECRETS_DISABLE_NEW_LOADER": "1",
            "MAEZ_IPHONE_INGEST_TOKEN": "dummy",
        }, clear=False)
        self._env.start()
        from core.subscription_proxy import server
        importlib.reload(server)
        self.server = server
        self.adapter = _CapturingAdapter()
        self._adapters = mock.patch.object(server, "ADAPTERS", [self.adapter])
        self._adapters.start()

    def tearDown(self):
        self._adapters.stop()
        self._env.stop()
        self._tmp.cleanup()

    def _audit_row(self):
        with closing(sqlite3.connect(self.db_path)) as con:
            return con.execute(
                "SELECT egress_decision, prompt_preview, egress_shadow_mode, "
                "egress_origin_classes FROM calls"
            ).fetchone()


class ProxyBlockClassTests(_ProxyCanaryBase):
    async def test_owner_account_recalled_memory_is_blocked(self):
        recalled = {"core": [], "daily": [],
                    "raw": [_raw_row("raw-owner", f"owner note {_PII_MARKER}",
                                     egress_origin_class="owner_account_context")]}
        body = _drive_to_proxy(self.server, recalled=recalled, adapter=self.adapter)
        with self.assertRaises(HTTPException) as ctx:
            await self.server.chat_completions(_make_proxy_request(body))
        self.assertEqual(ctx.exception.status_code, 403)
        self.assertEqual(self.adapter.prompts, [])  # adapter never reached (enforced)
        decision, _preview, _shadow, origins = self._audit_row()
        self.assertEqual(decision, "block")
        self.assertIn("owner_account_context", origins)
```

- [ ] **Step 2: Run it — EXPECT GREEN**

Run: `.venv/bin/python -B -m unittest tests.test_recall_origin_egress_canary.ProxyBlockClassTests -v`
Expected: PASS. **If RED (no 403 / adapter reached / decision != block):** owner-account memory is reaching the cloud — a severe finding, escalate immediately. (If the proxy request shape or env differs, reconcile against the working `test_owner_account_memory_taint_rail.py` — do not loosen the assertion.)

- [ ] **Step 3: Commit**

```bash
git add tests/test_recall_origin_egress_canary.py
git commit -m "test(privacy): recall-origin canary — proxy block-class (owner-account enforced)

Recalled owner-account memory driven through the real proxy is refused: 403,
adapter never reached, decision=block. Precedent/regression case. Test-only.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 5: Proxy-path redact-class (decision + audit scrubbed; shadow truth recorded)

**Files:**
- Modify: `tests/test_recall_origin_egress_canary.py`

The generalized case. Per spec §3.C: assert `decision="redact"` and the audit `prompt_preview` is PII-free — and **honestly record the shadow truth** (adapter-forwarding is not yet enforced; the adapter may still receive the original). Do NOT assert the adapter content is scrubbed.

- [ ] **Step 1: Add the redact-class proxy test**

```python
# Append to tests/test_recall_origin_egress_canary.py
class ProxyRedactClassTests(_ProxyCanaryBase):
    async def test_redact_class_decision_and_audit_are_scrubbed(self):
        recalled = {"core": [], "daily": [],
                    "raw": [_raw_row("raw-priv", f"contact {_PII_MARKER} privately",
                                     egress_origin_class="third_party_private_context")]}
        body = _drive_to_proxy(self.server, recalled=recalled, adapter=self.adapter)
        # redact-class proceeds (NOT a 403) — the door minimizes, does not block.
        await self.server.chat_completions(_make_proxy_request(body))
        decision, prompt_preview, shadow_mode, origins = self._audit_row()
        # the gate decided redact, and the persisted audit is scrubbed
        self.assertEqual(decision, "redact")
        self.assertNotIn(_PII_MARKER, prompt_preview or "")
        self.assertIn("third_party_private_context", origins)
        # SHADOW TRUTH (spec §3.C): redact-class forwarding is observe/shadow today —
        # the adapter may still receive the ORIGINAL prompt. This canary asserts the
        # DECISION and AUDIT are correct, NOT adapter-forwarding. The enforcement flip
        # (redact-class observe -> sanitized-forwarding) is a separate behavior slice
        # that would later upgrade the sink assertion to the adapter prompt.
        # Record the shadow signal for legibility (do not assert it is "good"):
        self.assertIsNotNone(shadow_mode, "egress_shadow_mode should be recorded")
```

Note for the implementer: confirm the precise `egress_shadow_mode` value for a redact decision by reading `core/subscription_proxy/server.py` `chat_completions` (the redact branch around line 673+). If it has a definite "observed/shadow" value, tighten the last assertion to that exact value; if its semantics are ambiguous, leave the `assertIsNotNone` + the comment (the spec authorizes the audit-preview as the faithful sink). Either way: **do not assert the adapter received scrubbed content** — it does not today.

- [ ] **Step 2: Run it — EXPECT GREEN**

Run: `.venv/bin/python -B -m unittest tests.test_recall_origin_egress_canary.ProxyRedactClassTests -v`
Expected: PASS. **If RED on `decision != "redact"`:** the private-origin provenance did not reach the gate (the wristband was lost between render and the proxy) — a real finding. **If RED on `_PII_MARKER in prompt_preview`:** the audit/redactor is not scrubbing this PII shape — report it.

- [ ] **Step 3: Commit**

```bash
git add tests/test_recall_origin_egress_canary.py
git commit -m "test(privacy): recall-origin canary — proxy redact-class (audit scrubbed, shadow honest)

Private-origin recalled memory at the proxy: decision=redact, audit
prompt_preview PII-free, origin carried. Records the shadow truth — adapter-
forwarding is not yet enforced for redact-class; canary does NOT claim the
adapter is scrubbed (that's the future enforcement flip). Test-only.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 6: Full-suite green + apples-to-apples

**Files:** none (verification)

- [ ] **Step 1: Run the whole canary module — EXPECT ALL GREEN**

Run: `.venv/bin/python -B -m unittest tests.test_recall_origin_egress_canary -v`
Expected: every class PASS (RecallFidelity, LocalRenderFidelity, DecideEgressMatrix, ProxyBlockClass, ProxyRedactClass). **Any RED is a finding to escalate, not a test to weaken.**

- [ ] **Step 2: Full discover (schema-pin lesson)**

Run: `.venv/bin/python -B -m unittest discover -s tests 2>&1 | tail -6`
Expected: the new canary tests present and green; zero new failures attributable to this file. Run in `/home/rohit/maez` (asset-rich), not a worktree. Live-judge tests wobble ±1-2 (known flaky) — the new canary file must be clean.

- [ ] **Step 3: Confirm test-only + live db untouched**

Run: `git status --porcelain | grep -v "test_recall_origin_egress_canary"` should show no *new* production-code changes from this slice; `git status --porcelain memory/db` empty.

---

## Self-Review (against the spec)

**Spec coverage:**
- §3.A local render full-fidelity → Task 2 `test_local_render_keeps_full_content`. ✓
- §3.B provenance survives render → Task 2 `test_provenanced_render_carries_origin_span`. ✓
- §3.C proxy block-class → Task 4; redact-class decision+audit+shadow → Task 5 (audit scrubbed, shadow recorded, NOT adapter-forwarding). ✓
- §3.D fail-closed (missing→memory→redact; unknown→never allow) → Task 3 `test_missing_origin...` + `test_unknown_origin_fails_closed...`. ✓
- §3.E decide_egress matrix → Task 3. ✓
- "real memory path / row surfaces with correct metadata" → Task 1 (real recall). ✓
- §5 TDD posture (green-expected, red=finding) → header + every "EXPECT GREEN / if RED escalate" step. ✓
- §6 rule 4 owner-account precedent-only → Task 4 (one test, labelled precedent). ✓
- §6 rule 5 no production code → header + Task 6 Step 3. ✓

**Placeholder scan:** none. The one implementer-judgment spot (the exact `egress_shadow_mode` value, Task 5) is spec-authorized (§3.C "faithful sink") and bounded with a concrete fallback + a hard "never assert adapter-scrubbed" guard — not a placeholder.

**Type consistency:** `_mm()`, `_raw_row(id, content, egress_origin_class=)`, `_seg`/`_cloud_req`, `_make_proxy_request`, `_drive_to_proxy`, `_CapturingAdapter`, `_ProxyCanaryBase._audit_row`, `_PII_MARKER` — defined once, used consistently. The DB columns (`egress_decision`, `prompt_preview`, `egress_shadow_mode`, `egress_origin_classes`) match the taint-rail template's schema. ✓

**One coordination note for the implementer:** `_PII_MARKER` is an **email-shaped** marker on purpose — `redact_for_cloud` redacts emails (per `cloud_redactor.py`); a marker shape the redactor doesn't recognize would make the redact-class audit assertion spuriously red. Keep it email-shaped.
