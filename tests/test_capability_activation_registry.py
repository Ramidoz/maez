# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Capability activation registry tests (Step 5d).

Records that an acquisition has been completed: which capability,
which queue row, which commit SHA, which files/tests landed. Hard
contract — atomicity is load-bearing:

  • Registry write FIRST, queue transition SECOND. A queue row
    stuck in 'completed' with no registry row is worse than no
    lifecycle system at all.
  • Registry write is idempotent on queue_id — retry after a partial
    failure (registry written, queue transition crashed) is safe.
  • The bare 'transition to completed' path is NOT a public API for
    completion; only ``complete()`` is.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))


# ── helpers ────────────────────────────────────────────────────────


def _seed_queued_row(td: Path, *, capability_id: str = "cap-x") -> tuple:
    """Seed the queue with one queued row using a real manual entry
    layout so revalidation downstream of the registry path passes
    when needed. Returns (queue, row_id)."""
    from core.capability_acquisition_queue import AcquisitionQueue

    q = AcquisitionQueue(td / "queue.db")
    row_id = q.enqueue(
        capability_id=capability_id,
        source="manual",
        manual_source_path=str(
            _REPO / "docs" / "maez_manual"
            / "temporal-arithmetic-at-recall.md"
        ),
        acquisition="self-dev",
        proposal_id="prop-deadbeef",
        card_request_id="card-1234",
        reason="operator-driven gap match: 'temporal'",
        plain_english="Proposal text.",
        payload_json='{"k": "v"}',
    )
    return q, row_id


def _real_commit_sha() -> str:
    """A SHA that exists in the maez repo. Cheap to verify with
    ``git rev-parse HEAD``; the live tests want a known-good anchor
    rather than a fake one."""
    out = subprocess.check_output(
        ["git", "rev-parse", "HEAD"],
        cwd=str(_REPO),
    )
    return out.decode().strip()


# ── registry CRUD ─────────────────────────────────────────────────


class TestRegistryInsertAndGet(unittest.TestCase):
    def test_insert_returns_id_and_persists(self):
        from core.capability_activation_registry import (
            ActivationRegistry,
        )

        with tempfile.TemporaryDirectory() as td:
            r = ActivationRegistry(Path(td) / "reg.db")
            row_id = r.record(
                capability_id="cap-x",
                queue_id="acq-1",
                proposal_id="prop-1",
                commit_sha="abc123",
                implementation_files=["core/x.py"],
                tests=["tests/test_x.py"],
                notes="first",
            )
            self.assertTrue(row_id.startswith("act-"))
            row = r.get(row_id)
            self.assertEqual(row["capability_id"], "cap-x")
            self.assertEqual(row["queue_id"], "acq-1")
            self.assertEqual(row["status"], "active")
            self.assertIsNone(row["activated_at"])
            self.assertIsNotNone(row["completed_at"])

    def test_record_is_idempotent_on_queue_id(self):
        """Retry after a partial failure must NOT insert a duplicate.
        Re-calling record() with the same queue_id returns the
        existing registry row id."""
        from core.capability_activation_registry import (
            ActivationRegistry,
        )

        with tempfile.TemporaryDirectory() as td:
            r = ActivationRegistry(Path(td) / "reg.db")
            first = r.record(
                capability_id="cap-x",
                queue_id="acq-shared",
                proposal_id="prop-1",
                commit_sha="abc123",
                implementation_files=["core/x.py"],
                tests=[],
            )
            second = r.record(
                capability_id="cap-x",
                queue_id="acq-shared",
                proposal_id="prop-1",
                commit_sha="abc123",
                implementation_files=["core/x.py"],
                tests=[],
            )
            self.assertEqual(first, second)
            self.assertEqual(len(r.list_all()), 1)


class TestActiveCapabilityUniqueness(unittest.TestCase):
    def test_default_rejects_second_active_for_same_capability(self):
        from core.capability_activation_registry import (
            ActivationRegistry, DuplicateActiveCapabilityError,
        )

        with tempfile.TemporaryDirectory() as td:
            r = ActivationRegistry(Path(td) / "reg.db")
            r.record(
                capability_id="cap-x",
                queue_id="acq-1",
                proposal_id="prop-1",
                commit_sha="aaa",
                implementation_files=["core/x.py"],
                tests=[],
            )
            with self.assertRaises(DuplicateActiveCapabilityError):
                r.record(
                    capability_id="cap-x",
                    queue_id="acq-2",
                    proposal_id="prop-2",
                    commit_sha="bbb",
                    implementation_files=["core/x.py"],
                    tests=[],
                )

    def test_supersedes_marks_prior_superseded_and_inserts_new_active(self):
        from core.capability_activation_registry import ActivationRegistry

        with tempfile.TemporaryDirectory() as td:
            r = ActivationRegistry(Path(td) / "reg.db")
            v1 = r.record(
                capability_id="cap-x",
                queue_id="acq-1",
                proposal_id="prop-1",
                commit_sha="aaa",
                implementation_files=["core/x.py"],
                tests=[],
            )
            v2 = r.record(
                capability_id="cap-x",
                queue_id="acq-2",
                proposal_id="prop-2",
                commit_sha="bbb",
                implementation_files=["core/x.py"],
                tests=[],
                supersedes=v1,
            )
            self.assertNotEqual(v1, v2)
            self.assertEqual(r.get(v1)["status"], "superseded")
            new = r.get(v2)
            self.assertEqual(new["status"], "active")
            self.assertEqual(new["supersedes"], v1)

    def test_supersedes_unknown_id_rejected(self):
        from core.capability_activation_registry import (
            ActivationRegistry, RegistryError,
        )

        with tempfile.TemporaryDirectory() as td:
            r = ActivationRegistry(Path(td) / "reg.db")
            with self.assertRaises(RegistryError):
                r.record(
                    capability_id="cap-x",
                    queue_id="acq-1",
                    proposal_id="prop-1",
                    commit_sha="aaa",
                    implementation_files=["core/x.py"],
                    tests=[],
                    supersedes="act-doesnotexist",
                )

    def test_supersedes_capability_id_must_match_prior(self):
        """Supersession links between rows of the same capability_id.
        Otherwise a malformed call could mark an unrelated row as
        superseded — corrupting lineage."""
        from core.capability_activation_registry import (
            ActivationRegistry, RegistryError,
        )

        with tempfile.TemporaryDirectory() as td:
            r = ActivationRegistry(Path(td) / "reg.db")
            v1 = r.record(
                capability_id="cap-y",
                queue_id="acq-1",
                proposal_id="prop-1",
                commit_sha="aaa",
                implementation_files=["core/y.py"],
                tests=[],
            )
            with self.assertRaises(RegistryError):
                r.record(
                    capability_id="cap-x",
                    queue_id="acq-2",
                    proposal_id="prop-2",
                    commit_sha="bbb",
                    implementation_files=["core/x.py"],
                    tests=[],
                    supersedes=v1,
                )


class TestRegistryListing(unittest.TestCase):
    def test_list_active_filters_to_active(self):
        from core.capability_activation_registry import ActivationRegistry

        with tempfile.TemporaryDirectory() as td:
            r = ActivationRegistry(Path(td) / "reg.db")
            r.record(
                capability_id="a",
                queue_id="q1",
                proposal_id="p1",
                commit_sha="aaa",
                implementation_files=["core/a.py"],
                tests=[],
            )
            v1 = r.record(
                capability_id="b",
                queue_id="q2",
                proposal_id="p2",
                commit_sha="bbb",
                implementation_files=["core/b.py"],
                tests=[],
            )
            r.record(
                capability_id="b",
                queue_id="q3",
                proposal_id="p3",
                commit_sha="ccc",
                implementation_files=["core/b.py"],
                tests=[],
                supersedes=v1,
            )
            active = r.list_active()
            ids = sorted(row["capability_id"] for row in active)
            self.assertEqual(ids, ["a", "b"])
            # The 'b' active row is the v3, not v1.
            b_row = next(row for row in active if row["capability_id"] == "b")
            self.assertEqual(b_row["commit_sha"], "ccc")


# ── completion handler (atomicity) ────────────────────────────────


class TestCompleteHandlerOrdering(unittest.TestCase):
    """The public completion API: registry FIRST, queue transition
    SECOND. Atomicity-by-ordering: if the queue transition fails after
    the registry write, the registry write is idempotent on retry."""

    def test_happy_path_registry_then_queue_transition(self):
        from core.capability_activation_registry import (
            ActivationRegistry, complete,
        )

        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            q, row_id = _seed_queued_row(tdp)
            reg = ActivationRegistry(tdp / "reg.db")
            sha = _real_commit_sha()
            reg_id = complete(
                queue=q,
                registry=reg,
                queue_id=row_id,
                capability_id="cap-x",
                commit_sha=sha,
                implementation_files=[
                    "core/memory/temporal_arithmetic.py",
                ],
                tests=["tests/test_temporal_arithmetic.py"],
                notes="step 5c",
            )
            self.assertTrue(reg_id.startswith("act-"))
            self.assertEqual(q.get(row_id)["status"], "completed")
            row = reg.get(reg_id)
            self.assertEqual(row["queue_id"], row_id)
            self.assertEqual(row["commit_sha"], sha)
            self.assertEqual(row["status"], "active")

    def test_retry_after_partial_failure_is_safe(self):
        """Simulate: registry write succeeded but queue transition
        raised. A retry should NOT insert a duplicate registry row,
        and SHOULD complete the queue transition."""
        from core.capability_activation_registry import (
            ActivationRegistry, complete,
        )

        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            q, row_id = _seed_queued_row(tdp)
            reg = ActivationRegistry(tdp / "reg.db")
            sha = _real_commit_sha()

            # First attempt: monkey-patch transition to crash AFTER
            # the registry write succeeded.
            original = q.transition

            def boom(*a, **kw):
                raise RuntimeError("simulated queue-write failure")

            q.transition = boom  # type: ignore[assignment]
            with self.assertRaises(RuntimeError):
                complete(
                    queue=q,
                    registry=reg,
                    queue_id=row_id,
                    capability_id="cap-x",
                    commit_sha=sha,
                    implementation_files=[
                        "core/memory/temporal_arithmetic.py",
                    ],
                    tests=[],
                )
            # Registry has the row; queue still 'queued'.
            self.assertEqual(len(reg.list_all()), 1)
            self.assertEqual(q.get(row_id)["status"], "queued")

            # Restore + retry. Idempotent: same registry id returned,
            # no duplicate row, queue now 'completed'.
            q.transition = original  # type: ignore[assignment]
            first_id = reg.list_all()[0]["id"]
            second_id = complete(
                queue=q,
                registry=reg,
                queue_id=row_id,
                capability_id="cap-x",
                commit_sha=sha,
                implementation_files=[
                    "core/memory/temporal_arithmetic.py",
                ],
                tests=[],
            )
            self.assertEqual(first_id, second_id)
            self.assertEqual(len(reg.list_all()), 1)
            self.assertEqual(q.get(row_id)["status"], "completed")

    def test_unknown_queue_id_rejected(self):
        from core.capability_acquisition_queue import AcquisitionQueue
        from core.capability_activation_registry import (
            ActivationRegistry, CompletionError, complete,
        )

        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            q = AcquisitionQueue(tdp / "queue.db")
            reg = ActivationRegistry(tdp / "reg.db")
            with self.assertRaises(CompletionError):
                complete(
                    queue=q,
                    registry=reg,
                    queue_id="acq-nope",
                    capability_id="cap-x",
                    commit_sha=_real_commit_sha(),
                    implementation_files=[
                        "core/memory/temporal_arithmetic.py",
                    ],
                    tests=[],
                )

    def test_non_queued_status_rejected(self):
        from core.capability_activation_registry import (
            ActivationRegistry, CompletionError, complete,
        )

        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            q, row_id = _seed_queued_row(tdp)
            q.transition(row_id, "cancelled")
            reg = ActivationRegistry(tdp / "reg.db")
            with self.assertRaises(CompletionError):
                complete(
                    queue=q,
                    registry=reg,
                    queue_id=row_id,
                    capability_id="cap-x",
                    commit_sha=_real_commit_sha(),
                    implementation_files=[
                        "core/memory/temporal_arithmetic.py",
                    ],
                    tests=[],
                )

    def test_capability_id_mismatch_rejected(self):
        from core.capability_activation_registry import (
            ActivationRegistry, CompletionError, complete,
        )

        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            q, row_id = _seed_queued_row(tdp, capability_id="cap-real")
            reg = ActivationRegistry(tdp / "reg.db")
            with self.assertRaises(CompletionError):
                complete(
                    queue=q,
                    registry=reg,
                    queue_id=row_id,
                    capability_id="cap-spoof",
                    commit_sha=_real_commit_sha(),
                    implementation_files=[
                        "core/memory/temporal_arithmetic.py",
                    ],
                    tests=[],
                )


class TestCompletionInputValidation(unittest.TestCase):
    def test_missing_commit_rejected(self):
        from core.capability_activation_registry import (
            ActivationRegistry, CompletionError, complete,
        )

        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            q, row_id = _seed_queued_row(tdp)
            reg = ActivationRegistry(tdp / "reg.db")
            with self.assertRaises(CompletionError):
                complete(
                    queue=q,
                    registry=reg,
                    queue_id=row_id,
                    capability_id="cap-x",
                    # Plausible-looking sha that is not in the repo.
                    commit_sha="0" * 40,
                    implementation_files=[
                        "core/memory/temporal_arithmetic.py",
                    ],
                    tests=[],
                )

    def test_missing_implementation_file_rejected(self):
        from core.capability_activation_registry import (
            ActivationRegistry, CompletionError, complete,
        )

        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            q, row_id = _seed_queued_row(tdp)
            reg = ActivationRegistry(tdp / "reg.db")
            with self.assertRaises(CompletionError):
                complete(
                    queue=q,
                    registry=reg,
                    queue_id=row_id,
                    capability_id="cap-x",
                    commit_sha=_real_commit_sha(),
                    implementation_files=["core/does_not_exist.py"],
                    tests=[],
                )

    def test_missing_test_file_rejected(self):
        from core.capability_activation_registry import (
            ActivationRegistry, CompletionError, complete,
        )

        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            q, row_id = _seed_queued_row(tdp)
            reg = ActivationRegistry(tdp / "reg.db")
            with self.assertRaises(CompletionError):
                complete(
                    queue=q,
                    registry=reg,
                    queue_id=row_id,
                    capability_id="cap-x",
                    commit_sha=_real_commit_sha(),
                    implementation_files=[
                        "core/memory/temporal_arithmetic.py",
                    ],
                    tests=["tests/test_does_not_exist.py"],
                )


class TestCompletionDoesNotInstallOrFetch(unittest.TestCase):
    """The completion path is allowed to call ``git cat-file`` for
    commit validation. Anything else — pip, curl, docker, the
    daemon — must NOT be touched. We pin this by allowlisting only
    the git argv shapes the handler uses."""

    def test_subprocess_only_used_for_git_validation(self):
        from core.capability_activation_registry import (
            ActivationRegistry, complete,
        )

        captured: list[list[str]] = []
        real_run = subprocess.run

        def gated_run(args, *a, **kw):
            captured.append(list(args))
            if args[:2] == ["git", "cat-file"]:
                return real_run(args, *a, **kw)
            raise AssertionError(
                f"completion handler invoked disallowed subprocess: {args!r}"
            )

        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            q, row_id = _seed_queued_row(tdp)
            reg = ActivationRegistry(tdp / "reg.db")
            sha = _real_commit_sha()
            with mock.patch.object(subprocess, "run", side_effect=gated_run):
                complete(
                    queue=q,
                    registry=reg,
                    queue_id=row_id,
                    capability_id="cap-x",
                    commit_sha=sha,
                    implementation_files=[
                        "core/memory/temporal_arithmetic.py",
                    ],
                    tests=[],
                )
        self.assertTrue(captured)
        self.assertTrue(
            all(c[:2] == ["git", "cat-file"] for c in captured),
            f"unexpected subprocess calls: {captured!r}",
        )


if __name__ == "__main__":
    unittest.main()
