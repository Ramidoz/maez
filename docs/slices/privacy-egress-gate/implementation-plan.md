# Privacy / Egress Gate Shadow Slice Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first RED-first implementation slice for Roadmap #3: cloud/subscription-proxy shadow-mode egress decisions, with no enforcement flip.

**Architecture:** Add a small `core.egress` module with source-attached `EgressSegment` / `EgressRequest` / `EgressDecision`, deterministic policy decisions, and telemetry-safe records. Wire only the subscription proxy to call the gate in shadow mode before external adapter calls and before trajectory logging; the payload sent to adapters is unchanged in this slice.

**Tech Stack:** Python unittest, FastAPI proxy internals, SQLite trajectory DB, existing `core.safety.cloud_redactor`.

---

### Task 1: Core Egress Types And Shadow Policy

**Files:**
- Create: `core/egress/__init__.py`
- Create: `core/egress/gate.py`
- Test: `tests/test_privacy_egress_gate.py`

- [ ] Write RED tests for:
  - raw string payloads are invalid/unclassified and block;
  - downgrade attempts are blocked;
  - reserved-denied raw blocks for `cloud_model_inference`;
  - minimizable private context redacts in shadow mode and returns sanitized segments;
  - non-private weather/system query allows.

- [ ] Implement minimal dataclasses/enums and `decide_egress(request)` to pass.

- [ ] Run `tests.test_privacy_egress_gate`.

### Task 2: Safe Telemetry Primitive

**Files:**
- Modify: `core/egress/gate.py`
- Test: `tests/test_privacy_egress_gate.py`

- [ ] Write RED tests that telemetry records keyed digests/counts/reasons but never raw bonded payload or bare SHA digest.

- [ ] Implement `decision_to_telemetry(decision, key=...)`.

- [ ] Run `tests.test_privacy_egress_gate`.

### Task 3: Subscription Proxy Shadow Hook

**Files:**
- Modify: `core/subscription_proxy/server.py`
- Test: `tests/test_subscription_proxy_egress_shadow.py`

- [ ] Write RED tests that:
  - proxy computes a shadow decision before adapter call;
  - bonded probe text is not stored in `prompt_preview`;
  - shadow mode does not change the prompt sent to the adapter;
  - proxy rows include egress decision metadata.

- [ ] Implement minimal proxy integration, still shadow-only.

- [ ] Run `tests.test_subscription_proxy_egress_shadow tests.test_subscription_proxy tests.test_subscription_proxy_provenance`.

### Task 4: Network Inventory Scaffold

**Files:**
- Create: `docs/slices/privacy-egress-gate/network_migration_allowlist.yaml`
- Create: `tests/test_privacy_egress_inventory.py`

- [ ] Write RED test that requires the migration allow-list file and required fields.

- [ ] Add initial inventory file for known legacy surfaces as tracked-not-ignored, not migrated.

- [ ] Run `tests.test_privacy_egress_inventory`.

### Task 5: Focused Verification

- [ ] Run all new tests.
- [ ] Run existing subscription proxy tests.
- [ ] Run focused memory/daemon-adjacent smoke tests only if touched by imports.
- [ ] Confirm user `maez.service` PID is unchanged; this branch must not restart or disturb the daemon.
