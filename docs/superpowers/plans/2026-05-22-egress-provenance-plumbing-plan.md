# Egress Provenance Plumbing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement cloud-path provenance plumbing so tagged spans flow from feeders through `claude_tier` into the subscription proxy shadow gate.

**Architecture:** Add a small `core.egress.provenance` module with `ProvenanceSpan` and `ProvenancedText`. Extend `claude_tier.call` to serialize role-aware provenance bundles for system and prompt text. Extend the subscription proxy to validate span bundles per message part before constructing `EgressRequest`; legacy raw calls remain compatible but conservative in shadow.

**Tech Stack:** Python stdlib dataclasses/unittest, existing `core.egress.gate`, `core.routing.claude_tier`, `core.subscription_proxy.server`.

---

### Task 1: Provenance Primitive

**Files:**
- Create: `core/egress/provenance.py`
- Modify: `core/egress/__init__.py`
- Test: `tests/test_egress_provenance.py`

- [ ] Write RED tests for span ordering, raw-string conservative construction, most-restrictive blended summaries, and no upgrade of tool/model output.
- [ ] Implement `ProvenanceSpan`, `ProvenancedText`, helper constructors, serialization, and deserialization.
- [ ] Run `tests.test_egress_provenance`.

### Task 2: Gate Decisions With Tagged Spans

**Files:**
- Modify: `core/egress/gate.py`
- Test: `tests/test_privacy_egress_gate.py`

- [ ] Write RED tests for public/system allow, memory/owner redact, reserved-denied block, mixed spans, and unknown/mismatch unclassified behavior.
- [ ] Implement any minimal gate support needed for existing `EgressSegment` decisions and telemetry origin visibility.
- [ ] Run `tests.test_privacy_egress_gate tests.test_egress_provenance`.

### Task 3: Claude Tier Carries Bundles

**Files:**
- Modify: `core/routing/claude_tier.py`
- Test: `tests/test_claude_tier.py`

- [ ] Write RED tests that tagged prompt/system bundles are sent as `maez_egress_segments` while legacy raw strings remain compatible and conservative.
- [ ] Implement bundle serialization without changing `TierReply`.
- [ ] Run `tests.test_claude_tier`.

### Task 4: Proxy Role-Aware Validation

**Files:**
- Modify: `core/subscription_proxy/server.py`
- Test: `tests/test_subscription_proxy_egress_shadow.py`

- [ ] Write RED tests that system and prompt bytes are both covered, mismatch becomes unclassified/block in shadow telemetry, and telemetry stores no raw prompt or reply payloads.
- [ ] Implement role-aware validation and conservative legacy fallback.
- [ ] Run `tests.test_subscription_proxy_egress_shadow tests.test_subscription_proxy tests.test_subscription_proxy_provenance`.

### Task 5: First Feeders And Inventory

**Files:**
- Modify: `core/self_dev/__init__.py`
- Modify: `core/eval/judge.py`
- Modify: `docs/slices/privacy-egress-gate/network_migration_allowlist.yaml`
- Test: focused tests from Tasks 1-4.

- [ ] Convert selected `claude_tier` producers to pass tagged pieces instead of pre-blended raw prompt strings.
- [ ] Record direct cloud routes outside `claude_tier` as explicit unmigrated enforcement blockers.
- [ ] Run focused tests and confirm live daemon/proxy PIDs are unchanged.
