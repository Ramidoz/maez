# Intake Bus v0 — Admission Doorway Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract GitHub v1's bespoke admit-to-body immune step into one reusable, covenant-first admission doorway (`core/intake_bus/`) that every personal-data limb passes through.

**Architecture:** A limb stamps a staged, minimized `IntakeFact` and hands it to `admit(store_adapter, memory)`. The doorway validates provenance (refuse a malformed package as a content-free verdict; raise on substrate uncertainty), enforces promotion posture, derives trust-tier (the limb cannot over-claim), applies the egress taint, idempotently writes the body row, and returns a content-free outcome. GitHub refactors to ride it byte-identical (existing behavioral assertions are the proof); a synthetic test-only rider proves N=2 service-agnosticism.

**Tech Stack:** Python 3, stdlib `dataclasses`/`enum`/`typing.Protocol`; the existing `memory.memory_manager` (`store`, `_DEFAULT_TIER_BY_SOURCE`, `ProvenanceSource`) and `core.egress.gate.KNOWN_ORIGINS`. Tests: `.venv/bin/python -B -m unittest` (NOT pytest).

**Spec:** `docs/superpowers/specs/2026-06-04-intake-bus-v0-admission-doorway-design.md`. **Lane:** Codex implements / Claude reviews.

---

## File Structure

| File | Responsibility |
|------|----------------|
| `core/intake_bus/__init__.py` | Package marker (empty). |
| `core/intake_bus/contract.py` | The shared types: `IntakeFact`, `StoreAdapter` (Protocol), `PromotionPosture`, `IntakeOutcome`. No logic. |
| `core/intake_bus/admit.py` | The doorway: `admit(store_adapter, memory) -> IntakeOutcome` + the private `_validate`. Imports `KNOWN_ORIGINS`. |
| `memory/memory_manager.py` (modify) | Add generic `body_row_id_by_source_ref(source_ref, *, egress_origin_class)`; make `owner_account_row_id_by_source_ref` a thin wrapper. `store` UNTOUCHED. |
| `core/information_limb/github_v1.py` (modify) | Add `GithubStoreAdapter`; refactor `run_ingest` to stage-then-`admit`; slim `admit_repo_count_to_body`. |
| `tests/test_intake_bus_admit.py` (create) | The synthetic `FakeLimbStoreAdapter` rider — all immune behaviors. |
| `tests/test_memory_body_row_lookup.py` (create) | The generic lookup: honors origin class, fail-closed, wrapper still works. |
| `tests/test_github_v1_ingest_hardening.py` (modify) | Update ONLY the `mock.Mock()` lookup seam (`owner_account_row_id_by_source_ref` → `body_row_id_by_source_ref`) in the `run_ingest`-exercising tests. Behavioral assertions unchanged. |

**Untouched:** `MemoryManager.store`, `github_store` schema, `core/egress/gate.py` (read-only import), Calendar, Reddit, the daemon route, `scripts/github_ingest.py`.

---

## Task 1: The contract types

**Files:**
- Create: `core/intake_bus/__init__.py`
- Create: `core/intake_bus/contract.py`
- Test: `tests/test_intake_bus_admit.py` (the contract-shape test added here; the behavior tests come in Task 3)

- [ ] **Step 1: Create the empty package marker**

Create `core/intake_bus/__init__.py` with a single line:

```python
"""Personal Data Intake Bus — the shared admission doorway for personal-data limbs."""
```

- [ ] **Step 2: Write the failing contract test**

Create `tests/test_intake_bus_admit.py`:

```python
# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Intake Bus v0 — the admission doorway and its synthetic rider."""

from __future__ import annotations

import unittest

from core.intake_bus.contract import (
    IntakeFact,
    IntakeOutcome,
    PromotionPosture,
)
from memory.memory_manager import ProvenanceSource


class ContractShapeTests(unittest.TestCase):
    def test_promotion_posture_values(self):
        self.assertEqual(PromotionPosture.ADMIT_TO_BODY.value, "admit_to_body")
        self.assertEqual(PromotionPosture.STAGE_ONLY.value, "stage_only")

    def test_intake_fact_is_frozen(self):
        fact = IntakeFact(
            source_kind="synthetic.note",
            source_ref="synthetic:1",
            content="a note",
            provenance_source=ProvenanceSource.TOOL_OBSERVATION,
            egress_origin_class="memory",
            promotion_posture=PromotionPosture.ADMIT_TO_BODY,
            fetch_batch_id="batch-1",
        )
        with self.assertRaises(Exception):
            fact.content = "mutated"  # frozen dataclass

    def test_outcome_is_content_free(self):
        outcome = IntakeOutcome(status="refused", source_ref="synthetic:1", reason="unknown_origin_class")
        # Only status / source_ref / reason — no content/count/secret fields.
        self.assertEqual(
            set(vars(outcome).keys()),
            {"status", "source_ref", "reason"},
        )


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `.venv/bin/python -B -m unittest tests.test_intake_bus_admit -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'core.intake_bus.contract'`.

- [ ] **Step 4: Implement the contract**

Create `core/intake_bus/contract.py`:

```python
# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""The Intake Bus contract — the shared types a limb and the doorway exchange.

The bus owns the covenant moment (tier, taint, posture, idempotency); the limb
brings a sealed, labeled package. These types carry no behavior.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping, Protocol, runtime_checkable

from memory.memory_manager import ProvenanceSource


class PromotionPosture(Enum):
    ADMIT_TO_BODY = "admit_to_body"   # the fact may become a body memory (GitHub)
    STAGE_ONLY = "stage_only"         # the fact stays staged; the doorway refuses body-admission
    # future (NOT in v0): QUARANTINE_PROPOSAL — lands as a contestable reflection proposal


@dataclass(frozen=True)
class IntakeFact:
    """A staged, minimized fact a limb hands the doorway. The limb builds
    ``content``; the bus moves it verbatim and never composes or inspects it."""

    source_kind: str
    source_ref: str
    content: str
    provenance_source: ProvenanceSource
    egress_origin_class: str
    promotion_posture: PromotionPosture
    fetch_batch_id: str
    metadata: Mapping[str, str] = field(default_factory=dict)


@runtime_checkable
class StoreAdapter(Protocol):
    """The two hooks a limb implements so the bus drives idempotency without
    owning the limb's staging schema."""

    def oldest_pending(self) -> "IntakeFact | None": ...

    def mark_admitted(self, source_ref: str, *, body_memory_id: str) -> None: ...


@dataclass(frozen=True)
class IntakeOutcome:
    """Content-free BY CONSTRUCTION — status / source_ref / reason code only.

    The doorway does NOT report ``resumed``: whether a pending record was
    just-staged or left from a crash is knowledge only the limb has.
    """

    status: str   # "admitted" | "already_admitted" | "staged_not_admitted" | "refused" | "nothing_pending"
    source_ref: str | None
    reason: str | None = None   # content-free CODE, only for "refused"
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `.venv/bin/python -B -m unittest tests.test_intake_bus_admit -v`
Expected: PASS (3 tests).

- [ ] **Step 6: Commit**

```bash
git add core/intake_bus/__init__.py core/intake_bus/contract.py tests/test_intake_bus_admit.py
git commit -m "feat(intake-bus): the admission-doorway contract types"
```

---

## Task 2: The generic body-row lookup (parameterized by origin class)

**Files:**
- Modify: `memory/memory_manager.py:1068-1088` (the existing `owner_account_row_id_by_source_ref`)
- Test: `tests/test_memory_body_row_lookup.py`

**Context:** the existing lookup is hardcoded to `owner_account_context`. The shared doorway must check the *fact's own* declared origin, so add a generic form parameterized by `egress_origin_class` and make the owner-account method a thin wrapper (preserving its callers byte-identical). It must fail closed: a backend error propagates (never `None` on uncertainty).

- [ ] **Step 1: Write the failing test**

Create `tests/test_memory_body_row_lookup.py`:

```python
# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""The generic body-row lookup: honors the passed origin class, fails closed,
and the owner-account method remains a behavior-preserving wrapper."""

from __future__ import annotations

import unittest
from unittest import mock

from memory.memory_manager import MemoryManager


def _mm_with_raw(raw):
    mm = MemoryManager.__new__(MemoryManager)  # bypass heavy __init__
    mm.raw = raw
    return mm


class BodyRowLookupTests(unittest.TestCase):
    def test_honors_the_passed_origin_class(self):
        raw = mock.Mock()
        raw.get.return_value = {
            "ids": ["row-A", "row-B"],
            "metadatas": [
                {"egress_origin_class": "owner_account_context"},
                {"egress_origin_class": "memory"},
            ],
        }
        mm = _mm_with_raw(raw)
        self.assertEqual(mm.body_row_id_by_source_ref("ref", egress_origin_class="memory"), "row-B")
        self.assertEqual(
            mm.body_row_id_by_source_ref("ref", egress_origin_class="owner_account_context"), "row-A"
        )

    def test_absent_returns_none(self):
        raw = mock.Mock()
        raw.get.return_value = {"ids": [], "metadatas": []}
        mm = _mm_with_raw(raw)
        self.assertIsNone(mm.body_row_id_by_source_ref("ref", egress_origin_class="memory"))

    def test_empty_source_ref_returns_none_without_querying(self):
        raw = mock.Mock()
        mm = _mm_with_raw(raw)
        self.assertIsNone(mm.body_row_id_by_source_ref("", egress_origin_class="memory"))
        raw.get.assert_not_called()

    def test_backend_error_raises_not_launders_to_absent(self):
        raw = mock.Mock()
        raw.get.side_effect = RuntimeError("chroma down")
        mm = _mm_with_raw(raw)
        with self.assertRaises(RuntimeError):
            mm.body_row_id_by_source_ref("ref", egress_origin_class="memory")

    def test_owner_account_wrapper_still_resolves_owner_rows(self):
        raw = mock.Mock()
        raw.get.return_value = {
            "ids": ["row-A"],
            "metadatas": [{"egress_origin_class": "owner_account_context"}],
        }
        mm = _mm_with_raw(raw)
        self.assertEqual(mm.owner_account_row_id_by_source_ref("ref"), "row-A")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv/bin/python -B -m unittest tests.test_memory_body_row_lookup -v`
Expected: FAIL — `AttributeError: 'MemoryManager' object has no attribute 'body_row_id_by_source_ref'`.

- [ ] **Step 3: Implement the generic lookup + wrapper**

In `memory/memory_manager.py`, replace the existing method (currently at lines 1068-1088):

```python
    def owner_account_row_id_by_source_ref(self, source_ref: str) -> str | None:
        """Return the raw memory row id for an owner-account source ref.

        This is a read-only recovery helper for account-limb admission. A
        same-source generic memory row must not satisfy the lookup; the row has
        to carry both the source_ref and owner_account_context taint.
        """
        if not source_ref:
            return None
        got = self.raw.get(
            where={"source_ref": source_ref},
            include=["metadatas"],
        )

        ids = got.get("ids") or []
        metadatas = got.get("metadatas") or []
        for idx, row_id in enumerate(ids):
            meta = metadatas[idx] if idx < len(metadatas) else {}
            if (meta or {}).get("egress_origin_class") == "owner_account_context":
                return str(row_id)
        return None
```

with:

```python
    def body_row_id_by_source_ref(self, source_ref: str, *, egress_origin_class: str) -> str | None:
        """Return the raw memory row id for ``source_ref`` wearing ``egress_origin_class``.

        Read-only recovery helper for intake-bus admission idempotency. A
        same-source row with a *different* origin class must not satisfy the
        lookup; the row has to carry BOTH the source_ref AND the expected taint.

        Fails CLOSED: a backend error propagates. The caller must never treat
        "I can't tell the body's state" as "absent → admit".
        """
        if not source_ref:
            return None
        got = self.raw.get(
            where={"source_ref": source_ref},
            include=["metadatas"],
        )
        ids = got.get("ids") or []
        metadatas = got.get("metadatas") or []
        for idx, row_id in enumerate(ids):
            meta = metadatas[idx] if idx < len(metadatas) else {}
            if (meta or {}).get("egress_origin_class") == egress_origin_class:
                return str(row_id)
        return None

    def owner_account_row_id_by_source_ref(self, source_ref: str) -> str | None:
        """Thin wrapper over :meth:`body_row_id_by_source_ref` for owner-account rows."""
        return self.body_row_id_by_source_ref(
            source_ref, egress_origin_class="owner_account_context"
        )
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `.venv/bin/python -B -m unittest tests.test_memory_body_row_lookup -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add memory/memory_manager.py tests/test_memory_body_row_lookup.py
git commit -m "feat(intake-bus): generic body_row_id_by_source_ref parameterized by origin class"
```

---

## Task 3: The doorway `admit()` + the synthetic rider

**Files:**
- Create: `core/intake_bus/admit.py`
- Test: `tests/test_intake_bus_admit.py` (extend with the rider tests)

**Context:** `admit` runs ordered, fail-closed: read `oldest_pending` → validate (refuse) → posture → idempotency lookup → body-write. `refused` is a returned content-free verdict; any lookup/store/mark backend error RAISES (no catch). The bus passes only `provenance_source` to `store` (never `trust_tier`) so the tier is derived, not limb-claimed.

- [ ] **Step 1: Write the failing rider tests**

Append to `tests/test_intake_bus_admit.py` (before the `if __name__` block):

```python
from core.intake_bus.admit import admit
from core.intake_bus.contract import StoreAdapter  # noqa: F401  (Protocol, for clarity)


class _FakeMemory:
    """Records store() calls; serves body_row_id_by_source_ref from a seeded map.

    Mirrors the real MemoryManager seams the bus uses: store(...) and
    body_row_id_by_source_ref(source_ref, *, egress_origin_class).
    """

    def __init__(self, existing=None, raise_on_lookup=False):
        self.stored = []
        self.marked = []
        self._existing = dict(existing or {})        # (source_ref, origin) -> body id
        self._raise_on_lookup = raise_on_lookup

    def body_row_id_by_source_ref(self, source_ref, *, egress_origin_class):
        if self._raise_on_lookup:
            raise RuntimeError("backend down")
        return self._existing.get((source_ref, egress_origin_class))

    def store(self, content, cycle, snapshot=None, metadata=None, *,
              provenance_source=None, trust_tier=None, egress_origin_class=None):
        body_id = f"body-{len(self.stored) + 1}"
        self.stored.append({
            "content": content,
            "provenance_source": provenance_source,
            "trust_tier": trust_tier,
            "egress_origin_class": egress_origin_class,
            "metadata": dict(metadata or {}),
        })
        return body_id


class _FakeLimbStoreAdapter:
    """A deliberately un-GitHub rider: different source_kind/source_ref scheme,
    a non-owner origin class. Implements the StoreAdapter Protocol."""

    def __init__(self, fact):
        self._fact = fact
        self.admitted = []

    def oldest_pending(self):
        return self._fact

    def mark_admitted(self, source_ref, *, body_memory_id):
        self.admitted.append((source_ref, body_memory_id))


def _synthetic_fact(**overrides):
    base = dict(
        source_kind="synthetic.note",
        source_ref="synthetic:1",
        content="a synthetic note for the owner",
        provenance_source=ProvenanceSource.TOOL_OBSERVATION,
        egress_origin_class="memory",      # real KNOWN_ORIGINS member, non-owner, not reserved-denied
        promotion_posture=PromotionPosture.ADMIT_TO_BODY,
        fetch_batch_id="batch-1",
    )
    base.update(overrides)
    return IntakeFact(**base)


class AdmitDoorwayTests(unittest.TestCase):
    def test_admits_a_non_owner_fact_with_taint_and_content_blind(self):
        fact = _synthetic_fact()
        memory = _FakeMemory()
        adapter = _FakeLimbStoreAdapter(fact)
        outcome = admit(adapter, memory)
        self.assertEqual(outcome.status, "admitted")
        self.assertEqual(len(memory.stored), 1)
        row = memory.stored[0]
        # content-blind: body content is the adapter's content verbatim
        self.assertEqual(row["content"], "a synthetic note for the owner")
        # the doorway applied the declared taint
        self.assertEqual(row["egress_origin_class"], "memory")
        # tier authority: the bus passes provenance_source and NO trust_tier (forces derivation)
        self.assertEqual(row["provenance_source"], ProvenanceSource.TOOL_OBSERVATION)
        self.assertIsNone(row["trust_tier"])
        # traceability survives
        self.assertEqual(row["metadata"]["source_ref"], "synthetic:1")
        # the staged record was marked admitted with the new body id
        self.assertEqual(adapter.admitted, [("synthetic:1", "body-1")])

    def test_idempotent_already_admitted_no_second_write(self):
        fact = _synthetic_fact()
        # body row already exists for (source_ref, origin)
        memory = _FakeMemory(existing={("synthetic:1", "memory"): "pre-existing-id"})
        adapter = _FakeLimbStoreAdapter(fact)
        outcome = admit(adapter, memory)
        self.assertEqual(outcome.status, "already_admitted")
        self.assertEqual(memory.stored, [])  # no second body write
        self.assertEqual(adapter.admitted, [("synthetic:1", "pre-existing-id")])

    def test_stage_only_posture_does_not_write_body(self):
        fact = _synthetic_fact(promotion_posture=PromotionPosture.STAGE_ONLY)
        memory = _FakeMemory()
        adapter = _FakeLimbStoreAdapter(fact)
        outcome = admit(adapter, memory)
        self.assertEqual(outcome.status, "staged_not_admitted")
        self.assertEqual(memory.stored, [])
        self.assertEqual(adapter.admitted, [])

    def test_refused_on_unknown_origin_is_a_verdict_not_a_raise(self):
        fact = _synthetic_fact(egress_origin_class="totally_made_up")
        memory = _FakeMemory()
        adapter = _FakeLimbStoreAdapter(fact)
        outcome = admit(adapter, memory)   # must NOT raise
        self.assertEqual(outcome.status, "refused")
        self.assertEqual(outcome.reason, "unknown_origin_class")
        self.assertEqual(memory.stored, [])

    def test_refused_on_unclassified_origin(self):
        fact = _synthetic_fact(egress_origin_class="unclassified")
        outcome = admit(_FakeLimbStoreAdapter(fact), _FakeMemory())
        self.assertEqual(outcome.status, "refused")
        self.assertEqual(outcome.reason, "unclassified_origin")

    def test_refused_on_missing_source_ref(self):
        fact = _synthetic_fact(source_ref="")
        outcome = admit(_FakeLimbStoreAdapter(fact), _FakeMemory())
        self.assertEqual(outcome.status, "refused")
        self.assertEqual(outcome.reason, "missing_source_ref")

    def test_refused_on_empty_content(self):
        fact = _synthetic_fact(content="")
        outcome = admit(_FakeLimbStoreAdapter(fact), _FakeMemory())
        self.assertEqual(outcome.status, "refused")
        self.assertEqual(outcome.reason, "missing_content")

    def test_substrate_uncertainty_raises_and_does_not_write(self):
        fact = _synthetic_fact()
        memory = _FakeMemory(raise_on_lookup=True)
        adapter = _FakeLimbStoreAdapter(fact)
        with self.assertRaises(RuntimeError):
            admit(adapter, memory)
        self.assertEqual(memory.stored, [])
        self.assertEqual(adapter.admitted, [])

    def test_nothing_pending_is_a_clean_noop(self):
        memory = _FakeMemory()
        adapter = _FakeLimbStoreAdapter(None)
        outcome = admit(adapter, memory)
        self.assertEqual(outcome.status, "nothing_pending")
        self.assertEqual(memory.stored, [])
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -B -m unittest tests.test_intake_bus_admit -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'core.intake_bus.admit'`.

- [ ] **Step 3: Implement the doorway**

Create `core/intake_bus/admit.py`:

```python
# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""The Intake Bus admission doorway.

A limb brings a sealed, labeled package; the doorway decides whether it may
enter the body, what trust it gets, and whether it only stays staged. Ordered,
fail-closed. ``refused`` is a returned content-free verdict; substrate
uncertainty RAISES (never laundered into "absent → admit").
"""

from __future__ import annotations

from core.egress.gate import KNOWN_ORIGINS
from core.intake_bus.contract import IntakeFact, IntakeOutcome, PromotionPosture


def _validate(fact: IntakeFact) -> str | None:
    """Return a content-free reason code if the package may not enter, else None."""
    if not fact.source_ref:
        return "missing_source_ref"
    if not fact.content:
        return "missing_content"
    if fact.egress_origin_class == "unclassified":
        return "unclassified_origin"
    if fact.egress_origin_class not in KNOWN_ORIGINS:
        return "unknown_origin_class"
    return None


def admit(store_adapter, memory) -> IntakeOutcome:
    """Admit (or refuse / stage / no-op) the limb's oldest pending fact."""
    fact = store_adapter.oldest_pending()
    if fact is None:
        return IntakeOutcome(status="nothing_pending", source_ref=None)

    # Stage A — covenant validation → REFUSE (a verdict; non-throwing; no substrate touched)
    reason = _validate(fact)
    if reason is not None:
        return IntakeOutcome(status="refused", source_ref=fact.source_ref, reason=reason)

    # Stage B — promotion posture (STAGE_ONLY short-circuits before any body touch)
    if fact.promotion_posture is PromotionPosture.STAGE_ONLY:
        return IntakeOutcome(status="staged_not_admitted", source_ref=fact.source_ref)

    # Stage C — idempotency (resume-first). Substrate uncertainty RAISES, record stays pending.
    existing = memory.body_row_id_by_source_ref(
        fact.source_ref, egress_origin_class=fact.egress_origin_class
    )
    if existing is not None:
        store_adapter.mark_admitted(fact.source_ref, body_memory_id=str(existing))
        return IntakeOutcome(status="already_admitted", source_ref=fact.source_ref)

    # Stage D — derive tier (inside store, from provenance_source) + body-write WITH the taint.
    body_id = memory.store(
        content=fact.content,
        cycle=0,
        provenance_source=fact.provenance_source,   # the bus passes NO trust_tier → tier is derived
        egress_origin_class=fact.egress_origin_class,
        metadata={
            "source_ref": fact.source_ref,
            "fetch_batch_id": fact.fetch_batch_id,
            **dict(fact.metadata),
        },
    )
    store_adapter.mark_admitted(fact.source_ref, body_memory_id=str(body_id))
    return IntakeOutcome(status="admitted", source_ref=fact.source_ref)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/python -B -m unittest tests.test_intake_bus_admit -v`
Expected: PASS (all contract + rider tests — 12 total).

- [ ] **Step 5: Commit**

```bash
git add core/intake_bus/admit.py tests/test_intake_bus_admit.py
git commit -m "feat(intake-bus): the admission doorway + synthetic N=2 rider"
```

---

## Task 4: GitHub rides the bus (byte-identical behavior)

**Files:**
- Modify: `core/information_limb/github_v1.py` (add `GithubStoreAdapter`; refactor `run_ingest:180-247`; slim `admit_repo_count_to_body:268-295`)
- Modify: `tests/test_github_v1_ingest_hardening.py` (update ONLY the `mock.Mock()` lookup seam in `run_ingest`-exercising tests)

**Context:** the existing GitHub tests are the regression net. **Behavioral assertions must pass unchanged.** The only legitimate test edit is the lookup-seam: tests that stub `memory.owner_account_row_id_by_source_ref` for a `run_ingest` path must stub `memory.body_row_id_by_source_ref` instead, because the bus now calls the generic form. Direct tests of `owner_account_row_id_by_source_ref` (the wrapper) stay untouched.

- [ ] **Step 1: Add `GithubStoreAdapter` + refactor `run_ingest` + slim the admit helper**

In `core/information_limb/github_v1.py`, add the adapter (near the top-level functions, after the imports) — it maps a `github_store.PendingRecord` to an `IntakeFact`, building the honest content with the limb's existing `_honest_repo_count_content`:

```python
_SOURCE_REF_PREFIX = "github.s2:"


class GithubStoreAdapter:
    """Adapts the GitHub staging store to the Intake Bus StoreAdapter Protocol.

    Content-building stays GitHub's: the adapter calls _honest_repo_count_content
    when it maps a pending row to an IntakeFact. github_store's schema is untouched.
    """

    def __init__(self, store):
        self._store = store

    def oldest_pending(self):
        from memory.memory_manager import ProvenanceSource
        from core.intake_bus.contract import IntakeFact, PromotionPosture

        pending = self._store.oldest_pending()
        if pending is None:
            return None
        return IntakeFact(
            source_kind="github.repo_count",
            source_ref=f"{_SOURCE_REF_PREFIX}{pending.ingest_record_id}",
            content=_honest_repo_count_content(
                repo_count=pending.repo_count, count_field=pending.count_field
            ),
            provenance_source=ProvenanceSource.TOOL_OBSERVATION,
            egress_origin_class="owner_account_context",
            promotion_posture=PromotionPosture.ADMIT_TO_BODY,
            fetch_batch_id=pending.fetch_batch_id,
        )

    def mark_admitted(self, source_ref: str, *, body_memory_id: str) -> None:
        ingest_record_id = source_ref[len(_SOURCE_REF_PREFIX):]
        self._store.mark_admitted(ingest_record_id, body_memory_id=body_memory_id)
```

Replace `run_ingest` (lines 180-247) with the bus-riding version. It reads the pending/staged ids *before* delegating admission, so the content-free result dict keeps identical values across all branches:

```python
def run_ingest(*, limb_session, store, memory, fetch_batch_id: str) -> dict:
    """Owner-triggered GitHub v1 ingest — rides the Intake Bus admission doorway.

    Resumes any interrupted staged observation before fetching, then admits at
    most once per durable ingest_record_id. The returned value is content-free.
    """
    from core.intake_bus.admit import admit

    pending = store.oldest_pending()
    was_pending = pending is not None
    if was_pending:
        ingest_record_id = pending.ingest_record_id
        result_fetch_batch_id = pending.fetch_batch_id
    else:
        repo_count = github_limb.fetch_repo_count(limb_session)
        staged = ingest_repo_count(
            user_response={"public_repos": repo_count},
            store=store,
            fetch_batch_id=fetch_batch_id,
        )
        ingest_record_id = staged["ingest_record_id"]
        result_fetch_batch_id = fetch_batch_id

    outcome = admit(GithubStoreAdapter(store), memory)
    return _ingest_result(
        ingest_record_id=ingest_record_id,
        fetch_batch_id=result_fetch_batch_id,
        admitted=(outcome.status == "admitted"),
        resumed=was_pending,
    )
```

Slim `admit_repo_count_to_body` (lines 268-295) so the immune body-write lives in the bus. Keep the function as a thin shim only if other callers exist; otherwise delete it. Search first:

Run: `grep -rn "admit_repo_count_to_body" core/ tests/ scripts/`

If the only remaining references are this definition + tests that assert it, delete the function and update those tests to assert the body row via `run_ingest` (a behavioral assertion, not a new one). If it is still imported elsewhere, leave a thin shim:

```python
def admit_repo_count_to_body(*, memory, repo_count, count_field, ingest_record_id, fetch_batch_id) -> str:
    """Deprecated shim — the immune admission now lives in core.intake_bus.admit.
    Retained only for direct callers; builds the IntakeFact and writes via memory."""
    from memory.memory_manager import ProvenanceSource
    content = _honest_repo_count_content(repo_count=repo_count, count_field=count_field)
    return memory.store(
        content=content, cycle=0,
        provenance_source=ProvenanceSource.TOOL_OBSERVATION,
        egress_origin_class="owner_account_context",
        metadata={"source_ref": f"github.s2:{ingest_record_id}", "fetch_batch_id": fetch_batch_id},
    )
```

- [ ] **Step 2: Update ONLY the lookup seam in the hardening test**

In `tests/test_github_v1_ingest_hardening.py`, the `run_ingest`-exercising tests (around lines 199-293) configure `memory.owner_account_row_id_by_source_ref.return_value`. The bus now calls `body_row_id_by_source_ref`, so update those mock seams. **Change only the lookup attribute; leave every assertion unchanged.** For each such line:

```python
        memory.owner_account_row_id_by_source_ref.return_value = None
```
becomes
```python
        memory.body_row_id_by_source_ref.return_value = None
```
and likewise `= "mem-1"` → on `body_row_id_by_source_ref`. The direct lookup tests (≈ lines 145-182) that call `memory.owner_account_row_id_by_source_ref(...)` as the subject-under-test stay UNCHANGED (the wrapper preserves them).

- [ ] **Step 3: Run the GitHub regression net — behavioral assertions unchanged**

Run:
```bash
.venv/bin/python -B -m unittest \
  tests.test_github_v1_egress_canary \
  tests.test_github_v1_ingest_hardening \
  tests.test_github_v1_ingest_route \
  tests.test_github_v1_ingest_trigger \
  tests.test_github_v1_connector -v
```
Expected: PASS. If any **assertion** (not a mock seam) had to change to pass, STOP — the extraction changed behavior and is wrong.

- [ ] **Step 4: Commit**

```bash
git add core/information_limb/github_v1.py tests/test_github_v1_ingest_hardening.py
git commit -m "refactor(github-v1): ride the Intake Bus admission doorway (behavior unchanged)"
```

---

## Task 5: Full-suite gate + review handoff

**Files:** none (verification only)

- [ ] **Step 1: Run the full suite (the schema-pin lesson)**

Run:
```bash
.venv/bin/python -B -m unittest discover -s tests -p 'test_*.py' -t . 2>&1 | tail -20
```
Expected: zero new failures vs main. Pre-existing failures (the stale `test_owner_bridge_chat_uses_envelope_prompt_block_and_recall_cap` introspection test; live judge tests) are not introduced here — verify any failure is pre-existing by checking it against `main` in isolation (`git stash` the branch diff, run the single test, compare).

- [ ] **Step 2: Confirm scope-out held**

Run: `git diff --stat main`
Expected files touched: `core/intake_bus/*`, `memory/memory_manager.py`, `core/information_limb/github_v1.py`, `tests/test_intake_bus_admit.py`, `tests/test_memory_body_row_lookup.py`, `tests/test_github_v1_ingest_hardening.py`. **Verify `MemoryManager.store`, `github_store` schema, `core/egress/gate.py`, Calendar, Reddit, the daemon route, and `scripts/github_ingest.py` are NOT in the diff.**

- [ ] **Step 3: Review handoff (Claude lane)**

Cross-lane review runs the branch code in the **asset-rich main checkout** (detached), apples-to-apples vs `main` — NOT the isolated worktree (which lacks owner-local assets; see `feedback_worktree_floor_confound`). The primary review anchor is the GitHub behavioral-assertion bar (assertions unedited; only the lookup seam updated). Confirm acceptance rules 1-10 in spec §9.

---

## Self-Review

**Spec coverage (§9 acceptance rules → tasks):**
1. Contract types content-free → Task 1.
2. Validate known/explicit/non-`unclassified`, refuse non-throwing → Task 3 (`_validate` + refused tests).
3. Substrate uncertainty raises → Task 3 (`test_substrate_uncertainty_raises`).
4. Tier derived from `provenance_source` → Task 3 (`trust_tier` is None, `provenance_source` passed).
5. Posture enforcement → Task 3 (`test_stage_only`).
6. Idempotency on `(source_ref, origin)` → Task 3 (`test_idempotent_already_admitted`).
7. Generic lookup + wrapper, `store` untouched → Task 2.
8. GitHub rides the bus, behavioral assertions unchanged, route/script result unchanged → Task 4.
9. Synthetic rider proves the battery without real data → Task 3.
10. Full suite green, content-free, no new deps → Task 5.

**Placeholder scan:** none — every code step has complete code; the one conditional (slim vs shim `admit_repo_count_to_body`) is gated on a concrete `grep` with both branches written.

**Type consistency:** `IntakeFact`/`StoreAdapter`/`PromotionPosture`/`IntakeOutcome` field and method names are identical across Tasks 1, 3, 4. `body_row_id_by_source_ref(source_ref, *, egress_origin_class)` signature is identical in Tasks 2, 3, 4. `admit(store_adapter, memory)` identical in Tasks 3, 4. `IntakeOutcome.status` string literals (`admitted`/`already_admitted`/`staged_not_admitted`/`refused`/`nothing_pending`) are consistent between `admit.py` and the tests.
