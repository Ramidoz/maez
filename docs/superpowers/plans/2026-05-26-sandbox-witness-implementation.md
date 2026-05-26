# Sandbox Witness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the ADR 0046 sandbox-witness substrate so maintenance proposals can carry append-only, re-verifiable witness generations without laundering legacy four-boolean witness claims.

**Architecture:** Add a focused `core/policies/sandbox_witnesses.py` substrate for witness enums, records, refusal reasons, append-only storage, and cheap ratification eligibility checks. Update `core/policies/maintenance_proposals.py` so legacy `sandbox_witness_json` is read-only compatibility state, new writes refuse legacy witnesses, and every ratification records `WitnessStatus` explicitly while binding the selected witness generation inside the ratification transition.

**Tech Stack:** Python dataclasses/enums, SQLite, `unittest`, existing policy-path helpers in `core.infra.paths`.

---

### Task 1: Path Helper And Witness Vocabulary

**Files:**
- Modify: `core/infra/paths.py`
- Create: `core/policies/sandbox_witnesses.py`
- Test: `tests/test_sandbox_witnesses.py`

- [ ] **Step 1: Write the failing vocabulary/path test**

Add `tests/test_sandbox_witnesses.py`:

```python
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path


class SandboxWitnessVocabularyTests(unittest.TestCase):
    def test_paths_exposes_sandbox_witnesses_db(self):
        from core import paths

        self.assertEqual(
            paths.sandbox_witnesses_db().name,
            "sandbox_witnesses.db",
        )

    def test_closed_vocabularies_expose_v1_contract(self):
        from core.policies.sandbox_witnesses import (
            SandboxWitnessKind,
            StalenessAnchorKind,
            WitnessRefusalReason,
            WitnessStatus,
        )

        self.assertEqual(
            {kind.value for kind in SandboxWitnessKind},
            {
                "worktree_red_test",
                "worktree_schema_diff",
                "scratch_db_transform",
                "dry_run_observation",
            },
        )
        self.assertIn("db_cursor", {kind.value for kind in StalenessAnchorKind})
        self.assertIn("witnessed", {status.value for status in WitnessStatus})
        self.assertIn(
            "legacy_witness_shape_refused",
            {reason.value for reason in WitnessRefusalReason},
        )
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
/home/rohit/maez/.venv/bin/python -m unittest tests.test_sandbox_witnesses
```

Expected: FAIL because `core.policies.sandbox_witnesses` and `paths.sandbox_witnesses_db()` do not exist.

- [ ] **Step 3: Implement the minimal vocabulary and path helper**

Add to `core/infra/paths.py` near `maintenance_proposals_db()`:

```python
def sandbox_witnesses_db() -> Path:
    """Sqlite DB for append-only maintenance sandbox witnesses."""
    return memory_dir() / "sandbox_witnesses.db"
```

Create `core/policies/sandbox_witnesses.py` with the closed enums from ADR 0046:

```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum


class SandboxWitnessKind(Enum):
    WORKTREE_RED_TEST = "worktree_red_test"
    WORKTREE_SCHEMA_DIFF = "worktree_schema_diff"
    SCRATCH_DB_TRANSFORM = "scratch_db_transform"
    DRY_RUN_OBSERVATION = "dry_run_observation"


class WitnessStatus(Enum):
    WITNESSED = "witnessed"
    UNWITNESSED_BY_POLICY = "unwitnessed_by_policy"
    UNWITNESSED_BY_OMISSION = "unwitnessed_by_omission"


class WitnessRefusalReason(Enum):
    CALLER_SUPPLIED_DIGEST = "caller_supplied_digest"
    ISOLATION_REFERENCE_INVALID = "isolation_reference_invalid"
    RED_TEST_REASON_MISSING = "red_test_reason_missing"
    PREDICTED_OBSERVED_UNBOUND = "predicted_observed_unbound"
    WITNESS_STALE = "witness_stale"
    INBOUND_TAINT_UNCLEARED = "inbound_taint_uncleared"
    SELF_RATIFICATION_DETECTED = "self_ratification_detected"
    LIVE_SUBSTRATE_MUTATION_DETECTED = "live_substrate_mutation_detected"
    WITNESS_KIND_NOT_YET_VOCABULARY = "witness_kind_not_yet_vocabulary"
    LEGACY_WITNESS_SHAPE_REFUSED = "legacy_witness_shape_refused"


class StalenessAnchorKind(Enum):
    COMMIT_HASH = "commit_hash"
    FILE_HASH_SET = "file_hash_set"
    DB_CURSOR = "db_cursor"
    DIAGNOSTIC_CURSOR = "diagnostic_cursor"


class WitnessRefused(ValueError):
    def __init__(self, reason: WitnessRefusalReason, message: str):
        self.reason = reason
        super().__init__(message)
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
/home/rohit/maez/.venv/bin/python -m unittest tests.test_sandbox_witnesses
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add core/infra/paths.py core/policies/sandbox_witnesses.py tests/test_sandbox_witnesses.py
git commit -m "feat(sandbox-witness): add witness vocabulary and path"
```

### Task 2: Append-Only Witness Store

**Files:**
- Modify: `core/policies/sandbox_witnesses.py`
- Test: `tests/test_sandbox_witnesses.py`

- [ ] **Step 1: Write failing storage tests**

Append tests proving append-only generation identity:

```python
    def test_store_appends_monotonic_generations_for_same_proposal(self):
        from core.policies.sandbox_witnesses import (
            SandboxWitnessKind,
            SandboxWitnessRecord,
            SandboxWitnesses,
            WitnessStatus,
        )

        with tempfile.TemporaryDirectory() as tmp:
            store = SandboxWitnesses(Path(tmp) / "sandbox_witnesses.db")
            first = SandboxWitnessRecord.new(
                bond_id="firstborn",
                proposal_id="proposal-1",
                witness_kind=SandboxWitnessKind.WORKTREE_RED_TEST,
                observed_effect_digest="hmac-sha256:" + "a" * 64,
                predicted_effect_digest="hmac-sha256:" + "b" * 64,
                artifact_digest="hmac-sha256:" + "c" * 64,
                captured_utc=datetime(2026, 5, 26, 12, 0, tzinfo=UTC),
            )

            stored_first = store.append(first)
            stored_second = store.append(
                SandboxWitnessRecord.new(
                    bond_id="firstborn",
                    proposal_id="proposal-1",
                    witness_kind=SandboxWitnessKind.WORKTREE_RED_TEST,
                    observed_effect_digest="hmac-sha256:" + "d" * 64,
                    predicted_effect_digest="hmac-sha256:" + "b" * 64,
                    artifact_digest="hmac-sha256:" + "e" * 64,
                    captured_utc=datetime(2026, 5, 26, 12, 5, tzinfo=UTC),
                )
            )

            self.assertEqual(stored_first.generation, 1)
            self.assertEqual(stored_second.generation, 2)
            self.assertNotEqual(stored_first.witness_id, stored_second.witness_id)
            self.assertEqual(store.current_for_proposal("firstborn", "proposal-1"), stored_second)
            self.assertEqual(len(store.family_for_proposal("firstborn", "proposal-1")), 2)
            self.assertEqual(stored_second.witness_status, WitnessStatus.WITNESSED)
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
/home/rohit/maez/.venv/bin/python -m unittest tests.test_sandbox_witnesses
```

Expected: FAIL because `SandboxWitnessRecord` and `SandboxWitnesses` are missing.

- [ ] **Step 3: Implement store and record**

Add `SandboxWitnessRecord` and `SandboxWitnesses` in `core/policies/sandbox_witnesses.py`:

```python
import json
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from pathlib import Path

from core import paths


@dataclass(frozen=True)
class SandboxWitnessRecord:
    witness_id: str
    generation: int
    bond_id: str
    proposal_id: str
    witness_kind: SandboxWitnessKind
    witness_status: WitnessStatus
    observed_effect_digest: str
    predicted_effect_digest: str
    artifact_digest: str
    captured_utc: datetime
    refusal_reason: WitnessRefusalReason | None = None

    @classmethod
    def new(
        cls,
        *,
        bond_id: str,
        proposal_id: str,
        witness_kind: SandboxWitnessKind,
        observed_effect_digest: str,
        predicted_effect_digest: str,
        artifact_digest: str,
        captured_utc: datetime,
    ) -> "SandboxWitnessRecord":
        return cls(
            witness_id="",
            generation=0,
            bond_id=bond_id,
            proposal_id=proposal_id,
            witness_kind=witness_kind,
            witness_status=WitnessStatus.WITNESSED,
            observed_effect_digest=observed_effect_digest,
            predicted_effect_digest=predicted_effect_digest,
            artifact_digest=artifact_digest,
            captured_utc=captured_utc,
            refusal_reason=None,
        )
```

Use schema:

```sql
CREATE TABLE IF NOT EXISTS sandbox_witnesses (
    witness_id TEXT PRIMARY KEY,
    generation INTEGER NOT NULL,
    bond_id TEXT NOT NULL,
    proposal_id TEXT NOT NULL,
    witness_kind TEXT NOT NULL,
    witness_status TEXT NOT NULL,
    observed_effect_digest TEXT NOT NULL,
    predicted_effect_digest TEXT NOT NULL,
    artifact_digest TEXT NOT NULL,
    captured_utc TEXT NOT NULL,
    refusal_reason TEXT,
    created_utc TEXT NOT NULL,
    UNIQUE (bond_id, proposal_id, generation)
);
CREATE INDEX IF NOT EXISTS idx_sandbox_witnesses_family
ON sandbox_witnesses (bond_id, proposal_id, generation);
```

`append()` computes `generation = max(generation)+1` under the store lock, stores a new `witness_id`, and never updates existing rows.

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
/home/rohit/maez/.venv/bin/python -m unittest tests.test_sandbox_witnesses
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add core/policies/sandbox_witnesses.py tests/test_sandbox_witnesses.py
git commit -m "feat(sandbox-witness): add append-only witness store"
```

### Task 3: Maintenance Proposal Legacy Refusal And Witness Status

**Files:**
- Modify: `core/policies/maintenance_proposals.py`
- Modify: `tests/test_maintenance_proposals.py`

- [ ] **Step 1: Write failing maintenance tests**

Update `tests/test_maintenance_proposals.py` so `_proposal()` defaults to `sandbox_witness=None`. Add tests:

```python
    def test_legacy_sandbox_witness_refused_at_append_update_and_emit(self):
        from core.policies.maintenance_proposals import (
            LegacySandboxWitness,
            emit_maintenance_proposal,
        )
        from core.policies.sandbox_witnesses import WitnessRefused, WitnessRefusalReason

        store = self._store()
        legacy = LegacySandboxWitness(
            red_tests_passed=True,
            focused_tests_passed=True,
            scratch_canary_passed=True,
            witness_digest=_DIGEST_B,
        )

        with self.assertRaises(WitnessRefused) as append_ctx:
            store.append(self._proposal(sandbox_witness=legacy))
        self.assertEqual(append_ctx.exception.reason, WitnessRefusalReason.LEGACY_WITNESS_SHAPE_REFUSED)

        clean = self._proposal()
        store.append(clean)
        with self.assertRaises(WitnessRefused) as update_ctx:
            store.update(clean.with_legacy_sandbox_witness_for_tests(legacy))
        self.assertEqual(update_ctx.exception.reason, WitnessRefusalReason.LEGACY_WITNESS_SHAPE_REFUSED)

        with self.assertRaises(WitnessRefused):
            emit_maintenance_proposal(
                self._proposal(proposal_id="proposal-2", sandbox_witness=legacy),
                store=store,
            )

    def test_ratification_records_unwitnessed_status(self):
        from core.policies.maintenance_proposals import ratify_maintenance_proposal
        from core.policies.sandbox_witnesses import WitnessStatus

        store = self._store()
        preference_store = AutonomyPreferences(self.pref_path)
        store.append(self._proposal(sandbox_witness=None))

        ratified = ratify_maintenance_proposal(
            bond_id="firstborn",
            proposal_id="proposal-1",
            ratified_utc=datetime(2026, 5, 26, 13, 0, tzinfo=UTC),
            store=store,
            preference_store=preference_store,
        )

        self.assertEqual(ratified.witness_status, WitnessStatus.UNWITNESSED_BY_OMISSION)
        self.assertEqual(
            store.get("firstborn", "proposal-1").witness_status,
            WitnessStatus.UNWITNESSED_BY_OMISSION,
        )
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
/home/rohit/maez/.venv/bin/python -m unittest tests.test_maintenance_proposals
```

Expected: FAIL because legacy refusal and `witness_status` are not implemented.

- [ ] **Step 3: Implement legacy refusal and `witness_status`**

In `core/policies/maintenance_proposals.py`:

- Rename the legacy dataclass to `LegacySandboxWitness`.
- Keep `MaintenanceProposal.sandbox_witness` as `LegacySandboxWitness | None` only for input compatibility, but refuse it on every new write.
- Add `witness_status: WitnessStatus | None` to `MaintenanceProposal`.
- Add nullable `witness_status TEXT` column on schema init.
- Ensure `_proposal_values()` writes `sandbox_witness_json` as `None` for new rows.
- Ensure `append()`, `update()`, and `emit_maintenance_proposal()` call `_refuse_legacy_witness(proposal)` before any write.
- Ensure ratification sets `witness_status=WitnessStatus.UNWITNESSED_BY_OMISSION` when no witness store/current witness is supplied.

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
/home/rohit/maez/.venv/bin/python -m unittest tests.test_maintenance_proposals
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add core/policies/maintenance_proposals.py tests/test_maintenance_proposals.py
git commit -m "feat(maintenance): refuse legacy sandbox witnesses"
```

### Task 4: Witnessed Ratification Eligibility

**Files:**
- Modify: `core/policies/maintenance_proposals.py`
- Modify: `core/policies/sandbox_witnesses.py`
- Test: `tests/test_maintenance_proposals.py`
- Test: `tests/test_sandbox_witnesses.py`

- [ ] **Step 1: Write failing witnessed ratification tests**

Add a test that a witnessed proposal binds the exact current generation and refuses stale/refused generations:

```python
    def test_ratification_uses_current_witness_generation(self):
        from core.policies.maintenance_proposals import ratify_maintenance_proposal
        from core.policies.sandbox_witnesses import (
            SandboxWitnessKind,
            SandboxWitnessRecord,
            SandboxWitnesses,
            WitnessStatus,
        )

        store = self._store()
        witness_store = SandboxWitnesses(Path(self.tmp.name) / "sandbox_witnesses.db")
        preference_store = AutonomyPreferences(self.pref_path)
        store.append(self._proposal(sandbox_witness=None))
        witness_store.append(
            SandboxWitnessRecord.new(
                bond_id="firstborn",
                proposal_id="proposal-1",
                witness_kind=SandboxWitnessKind.WORKTREE_RED_TEST,
                observed_effect_digest=_DIGEST_A,
                predicted_effect_digest=_DIGEST_B,
                artifact_digest=_DIGEST_C,
                captured_utc=datetime(2026, 5, 26, 12, 30, tzinfo=UTC),
            )
        )

        ratified = ratify_maintenance_proposal(
            bond_id="firstborn",
            proposal_id="proposal-1",
            ratified_utc=datetime(2026, 5, 26, 13, 0, tzinfo=UTC),
            store=store,
            preference_store=preference_store,
            witness_store=witness_store,
        )

        self.assertEqual(ratified.witness_status, WitnessStatus.WITNESSED)
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
/home/rohit/maez/.venv/bin/python -m unittest tests.test_maintenance_proposals tests.test_sandbox_witnesses
```

Expected: FAIL because `ratify_maintenance_proposal` has no `witness_store` argument and no eligibility check.

- [ ] **Step 3: Implement witnessed eligibility**

Add optional `witness_store: SandboxWitnesses | None = None` to `ratify_maintenance_proposal`.

If a current witness exists for `(bond_id, proposal_id)`:

- `WitnessStatus.WITNESSED` is recorded.
- `WitnessRefusalReason.WITNESS_STALE` or non-`WITNESSED` witness status raises `WitnessRefused`.

If no witness exists:

- `WitnessStatus.UNWITNESSED_BY_OMISSION` is recorded.

This task does not implement subprocess re-verification; it implements the storage/eligibility seam so the future verifier can supply witness generations.

- [ ] **Step 4: Run focused tests**

Run:

```bash
/home/rohit/maez/.venv/bin/python -m unittest tests.test_maintenance_proposals tests.test_sandbox_witnesses
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add core/policies/maintenance_proposals.py core/policies/sandbox_witnesses.py tests/test_maintenance_proposals.py tests/test_sandbox_witnesses.py
git commit -m "feat(maintenance): bind sandbox witness status at ratification"
```

### Task 5: Static Guard And Final Verification

**Files:**
- Modify: `tests/test_maintenance_proposals.py`

- [ ] **Step 1: Add static guard test**

Add a test that production SQL never writes a non-NULL current `sandbox_witness_json` outside migration/read compatibility:

```python
    def test_static_guard_refuses_new_production_write_to_legacy_sandbox_witness_json(self):
        source = Path("core/policies/maintenance_proposals.py").read_text(encoding="utf-8")
        self.assertNotIn("_sandbox_to_json(proposal.sandbox_witness)", source)
        self.assertIn("legacy_sandbox_witness_json", source)
```

- [ ] **Step 2: Run full focused policy tests**

Run:

```bash
/home/rohit/maez/.venv/bin/python -m unittest tests.test_maintenance_proposals tests.test_sandbox_witnesses tests.test_diagnostic_schema
```

Expected: PASS.

- [ ] **Step 3: Run broader suite floor**

Run:

```bash
/home/rohit/maez/.venv/bin/python -m unittest discover -s tests -p 'test_*.py'
```

Expected: no new failures. If the known pre-existing failures recur, record them explicitly with the same isolation discipline used in prior commits.

- [ ] **Step 4: Commit final guard if changed**

```bash
git add tests/test_maintenance_proposals.py
git commit -m "test(sandbox-witness): guard legacy witness write path"
```

---

## Self-Review Notes

- This plan implements the durable storage, vocabulary, legacy-refusal, witness-status, and ratification-eligibility seam from ADR 0046.
- This plan deliberately does not implement the full subprocess verifier, path-locus enforcement, injection-pattern narrative scanning, observed-effect recomputation for each witness kind, or WAL cursor harness in the first code pass. Those require a second implementation plan once the storage seam is live, because their tests need richer integration scaffolding.
- The split preserves ADR 0046's direction while keeping each commit small enough to review honestly.
