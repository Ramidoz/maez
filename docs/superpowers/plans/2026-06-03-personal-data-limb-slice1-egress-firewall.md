# Personal Data Limb — Slice 1: Egress Firewall (owner_account_context) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make personal-account-derived data block cloud-model egress by default — add an `owner_account_context` origin class to `core/egress/gate.py` that `cloud_model_inference` blocks categorically (even when `redaction_allowed=True`).

**Architecture:** `core/egress/gate.py` already groups origin classes into policy sets and routes by `call_class`; the gate is enforced live at `core/subscription_proxy/server.py:658` on every cloud call. We add a new categorical-block set `OWNER_ACCOUNT_CONTEXT` (parallel to `RESERVED_DENIED_RAW` — blocks regardless of `redaction_allowed`, with its own legible reason code) and a block branch in `_decide_cloud_model_inference`. This is the lock; *tagging* personal-account data with this origin class is later ingestion slices. No Privacy Filter, no provider registry, no credential ceremony, no Reddit OAuth in this slice.

**Tech Stack:** Python 3.14, `unittest` (NOT pytest — runner is `.venv/bin/python -m unittest`). Frozen dataclasses `EgressRequest` / `EgressSegment` / `EgressDecision`. Content-free HMAC telemetry via `decision_to_telemetry`.

**Spec:** `docs/superpowers/parked/2026-06-03-self-extending-senses-personal-data-ingestion-parked-sketch.md` (⚑ SETTLED DESIGN → Final build order → Slice 1, with the four locked acceptance tests).

**Covenant note:** This is the centerpiece rail — personal life does not silently leave the local body to a cloud model. It mirrors the existing *inbound* `external_llm_tainted` taint (`core/policies/sandbox_witnesses.py`) in the *outbound* direction.

**Amendment (2026-06-03, post-Codex-review):** The original plan claimed the gate was "enforced live at `subscription_proxy:658`." That was a static-trace error — the proxy was **shadow-mode** (computed the verdict, then sent the original prompt regardless). Corrected: a dedicated enforcement (commit `d4fa588`) now honors the `owner_account_context` block at the proxy (no adapter call, HTTP 403, content-free record, `egress_shadow_mode=False`), with an end-to-end integration witness (`tests/test_subscription_proxy_owner_account_enforcement.py`). The broader shadow→enforce flip for the reserved classes (soul/credentials, which also flow today) is the named urgent follow-up: [reserved-denied-cloud-enforcement-followup](../parked/2026-06-03-reserved-denied-cloud-enforcement-followup.md).

---

## File Structure

- **Modify:** `core/egress/gate.py` — add `OWNER_ACCOUNT_CONTEXT` set, add it to `KNOWN_ORIGINS`, add a categorical-block branch in `_decide_cloud_model_inference`. (~6 lines, additive — does NOT touch any existing set or branch.)
- **Create:** `tests/test_egress_owner_account_firewall.py` — the four locked acceptance tests + the telemetry/regression guards. (Follows the established `tests/test_egress_*` + `EgressRequest(call_class="cloud_model_inference", segments=[EgressSegment(...)])` fixture style.)

No other files change. The gate is already wired into `subscription_proxy`, so this rule takes effect on the live cloud path with zero wiring work.

---

## Task 1: owner_account_context categorical cloud block

**Files:**
- Modify: `core/egress/gate.py:38-56` (sets + `KNOWN_ORIGINS`) and `core/egress/gate.py:200-208` (the per-segment loop in `_decide_cloud_model_inference`)
- Test: `tests/test_egress_owner_account_firewall.py`

- [ ] **Step 1: Write the failing test file**

Create `tests/test_egress_owner_account_firewall.py`:

```python
# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Slice 1 of the Personal Data Limb Runtime: the egress firewall.

Personal-account-derived data (origin_class="owner_account_context") must block
cloud_model_inference by default — categorically, regardless of redaction_allowed.
This is the lock installed before any ingestion tags data with this class.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from core.egress.gate import (  # noqa: E402
    EgressRequest,
    EgressSegment,
    decide_egress,
    decision_to_telemetry,
)

_KEY = b"k" * 32


def _cloud_request(segments: list[EgressSegment], request_id: str = "r") -> EgressRequest:
    return EgressRequest(
        call_class="cloud_model_inference",
        destination="openai",
        segments=segments,
        caller="test_owner_account_firewall",
        request_id=request_id,
    )


class OwnerAccountEgressFirewallTests(unittest.TestCase):
    def test_owner_account_blocks_cloud_even_when_redaction_allowed(self):
        # redaction_allowed=True must NOT downgrade an owner-account block.
        decision = decide_egress(
            _cloud_request(
                [
                    EgressSegment(
                        text="a saved reddit post that reveals something personal",
                        origin_class="owner_account_context",
                        source_ref="owner_account.reddit.saved:abc123",
                        redaction_allowed=True,
                    )
                ],
                request_id="r1",
            )
        )
        self.assertEqual(decision.decision, "block")
        self.assertIn("owner_account_context_blocked_default", decision.reason_codes)
        self.assertEqual(decision.sanitized_segments, [])

    def test_mixed_public_and_owner_account_blocks_whole_request(self):
        # A public segment alongside an owner-account segment must BLOCK the whole
        # request — never "redact the private part and send the rest".
        decision = decide_egress(
            _cloud_request(
                [
                    EgressSegment(
                        text="today's weather is sunny",
                        origin_class="public_fact",
                        source_ref="weather",
                        redaction_allowed=True,
                    ),
                    EgressSegment(
                        text="my gmail thread with a family member",
                        origin_class="owner_account_context",
                        source_ref="owner_account.gmail.thread:1",
                        redaction_allowed=True,
                    ),
                ],
                request_id="r2",
            )
        )
        self.assertEqual(decision.decision, "block")
        self.assertEqual(decision.sanitized_segments, [])
        self.assertEqual(decision.sanitized_text(), "")

    def test_owner_account_block_telemetry_is_content_free(self):
        secret = "private detail: appointment at 4pm with Dr. Real Name"
        decision = decide_egress(
            _cloud_request(
                [
                    EgressSegment(
                        text=secret,
                        origin_class="owner_account_context",
                        source_ref="owner_account.calendar.event:9",
                        redaction_allowed=True,
                    )
                ],
                request_id="r3",
            )
        )
        telemetry = decision_to_telemetry(decision, key=_KEY)
        encoded = json.dumps(telemetry)
        self.assertNotIn(secret, encoded)
        self.assertNotIn("Dr. Real Name", encoded)
        self.assertNotIn("appointment", encoded)
        # the class NAME and the decision/reason are fine (not content)
        self.assertEqual(telemetry["decision"], "block")
        self.assertIn("owner_account_context", telemetry["origin_classes"])
        self.assertIn("owner_account_context_blocked_default", telemetry["reason_codes"])

    def test_existing_minimizable_private_context_still_redacts(self):
        # Regression guard: the new rule must NOT change existing private-context
        # handling. 'memory' is MINIMIZABLE_PRIVATE_CONTEXT — with redaction_allowed
        # it still REDACTS (not blocks).
        decision = decide_egress(
            _cloud_request(
                [
                    EgressSegment(
                        text="a lived memory about the owner",
                        origin_class="memory",
                        source_ref="lived:1",
                        redaction_allowed=True,
                    )
                ],
                request_id="r4",
            )
        )
        self.assertEqual(decision.decision, "redact")
        self.assertNotIn("owner_account_context_blocked_default", decision.reason_codes)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests and verify they FAIL for the right reason**

Run: `.venv/bin/python -m unittest tests.test_egress_owner_account_firewall -v`

Expected: `test_owner_account_blocks_cloud_even_when_redaction_allowed` and the mixed/telemetry tests FAIL. Reason: `owner_account_context` is not yet in `KNOWN_ORIGINS`, so the gate blocks it with reason `("unclassified",)` — the request still blocks, but the assertion `assertIn("owner_account_context_blocked_default", ...)` fails. (The regression test `test_existing_minimizable_private_context_still_redacts` should already PASS — it guards unchanged behavior.) Confirm the failure is the missing reason code, NOT an import error.

- [ ] **Step 3: Implement the categorical block in `core/egress/gate.py`**

Add the new set after `INTENTIONAL_OUTBOUND` (around line 47):

```python
OWNER_ACCOUNT_CONTEXT = {
    "owner_account_context",
}
```

Add it to `KNOWN_ORIGINS` (around line 49-56):

```python
KNOWN_ORIGINS = (
    RESERVED_DENIED_RAW
    | MINIMIZABLE_PRIVATE_CONTEXT
    | NON_PRIVATE
    | UNTRUSTED_EXTERNAL_OUTPUT
    | INTENTIONAL_OUTBOUND
    | OWNER_ACCOUNT_CONTEXT
    | {"unclassified"}
)
```

In `_decide_cloud_model_inference`, add the block branch as the FIRST check inside the per-segment `for` loop — immediately after `origin = segment.origin_class` and BEFORE the `RESERVED_DENIED_RAW` check (around line 201-202), so it blocks regardless of `redaction_allowed`:

```python
    for segment in request.segments:
        origin = segment.origin_class
        if origin in OWNER_ACCOUNT_CONTEXT:
            # Personal-account-derived data does not leave the local body to a
            # cloud model by default — categorical, ignores redaction_allowed.
            # Slice 1 of the Personal Data Limb Runtime; mirrors the inbound
            # external_llm_tainted taint in the outbound direction.
            return _block(
                reason_codes=("owner_account_context_blocked_default",),
                request=request,
                origin_classes=origins,
                original_char_count=original_chars,
            )
        if origin in RESERVED_DENIED_RAW:
            return _block(
                reason_codes=("reserved_denied_raw",),
                request=request,
                origin_classes=origins,
                original_char_count=original_chars,
            )
        # ... existing MINIMIZABLE / NON_PRIVATE branches unchanged ...
```

Do NOT add `owner_account_context` to any existing set, and do NOT touch the transport deciders — an `owner_account_context` segment on a transport call already blocks via the existing `origin_not_permitted_for_*_transport` fall-through (safe default; explicit transport policy is a later concern, out of Slice 1 scope).

- [ ] **Step 4: Run the tests and verify they PASS**

Run: `.venv/bin/python -m unittest tests.test_egress_owner_account_firewall -v`

Expected: all 4 tests PASS. Output pristine (no warnings).

- [ ] **Step 5: Prove the guard has teeth (mutation check)**

Temporarily change the new branch's reason to a wrong value, e.g. comment out the `if origin in OWNER_ACCOUNT_CONTEXT:` block entirely, then re-run. Expected: the firewall tests go RED (it falls back to `unclassified`). Restore the block. Then add `owner_account_context` to `MINIMIZABLE_PRIVATE_CONTEXT` instead of its own set and re-run: `test_owner_account_blocks_cloud_even_when_redaction_allowed` must go RED (it would `redact`, not `block`, when `redaction_allowed=True`). Restore. This proves the categorical-block (not redact-eligible) placement is load-bearing.

- [ ] **Step 6: Run the broader egress suite — no regression**

Run: `.venv/bin/python -m unittest tests.test_privacy_egress_gate tests.test_egress_model_output_policy tests.test_egress_claude_router_provenance tests.test_subscription_proxy_egress_shadow -v 2>&1 | tail -15`

Expected: all green (the change is additive — a new known origin + a new block branch — and touches no existing set or branch). If any fail, confirm the failure is pre-existing/ambient by checking it also fails on `HEAD` before your change.

- [ ] **Step 7: Commit**

```bash
git add core/egress/gate.py tests/test_egress_owner_account_firewall.py
git commit -m "feat(egress): owner_account_context blocks cloud egress by default

Slice 1 of the Personal Data Limb Runtime. Personal-account-derived data
(origin_class=owner_account_context) blocks cloud_model_inference
categorically, regardless of redaction_allowed — the outbound mirror of the
inbound external_llm_tainted taint. Enforced live via subscription_proxy.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Self-Review

**1. Spec coverage** — the four locked acceptance tests:
- "owner-account text blocks even when `redaction_allowed=True`" → `test_owner_account_blocks_cloud_even_when_redaction_allowed` ✓ (the block branch precedes any redaction check)
- "mixed public + owner-account blocks, not 'redacts and sends'" → `test_mixed_public_and_owner_account_blocks_whole_request` ✓ (`_block` short-circuits the request; `sanitized_segments == []`)
- "telemetry stays content-free" → `test_owner_account_block_telemetry_is_content_free` ✓ (HMAC digest only; class name + reason are not content)
- "existing memory/private redaction behavior unchanged" → `test_existing_minimizable_private_context_still_redacts` ✓ (regression guard)

**2. Placeholder scan** — none; all steps carry exact code, paths, and `unittest` commands.

**3. Type consistency** — uses the real frozen dataclasses (`EgressRequest`/`EgressSegment`/`EgressDecision`) and helper (`decision_to_telemetry`, `decision.sanitized_segments`/`.sanitized_text()`) exactly as defined in `gate.py`. New reason code `owner_account_context_blocked_default` is consistent across implementation, tests, and telemetry assertions.

**Scope guard** — Slice 1 only. Confirmed NOT in this plan: Privacy Filter, provider descriptor registry, credential ceremony, Reddit OAuth, the producer-side *tagging* of data with `owner_account_context`, and transport-path explicit policy.
