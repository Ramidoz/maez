# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Capability acquisition queue tests (Step 4b).

The queue records *intent* — owner approved acquiring capability X
on date Y. It does NOT fetch code, install dependencies, or modify
files. Step 5 (later) consumes this queue to actually integrate.

Hard contract: append-only-ish. Status transitions are allowed
(queued → cancelled / completed / failed) but rows are never
deleted. The queue is the audit trail of approved intent.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))


# ── helpers ────────────────────────────────────────────────────────


def _enqueue_kwargs(**overrides) -> dict:
    base = {
        "capability_id": "alpha",
        "source": "manual",
        "manual_source_path": "/home/rohit/maez/docs/maez_manual/alpha.md",
        "acquisition": "self-dev",
        "proposal_id": "prop-12345678",
        "card_request_id": "card-abc",
        "reason": "operator-driven gap match: 'test'",
        "plain_english": "This is a proposal to acquire alpha.",
        "payload_json": '{"action": "capability.acquire"}',
    }
    base.update(overrides)
    return base


# ── basic CRUD ─────────────────────────────────────────────────────


class TestEnqueueAndList(unittest.TestCase):
    def test_enqueue_returns_id_and_persists(self):
        from core.capability_acquisition_queue import (
            AcquisitionQueue, enqueue,
        )

        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "queue.db"
            q = AcquisitionQueue(db_path)
            row_id = enqueue(q, **_enqueue_kwargs())
            self.assertTrue(row_id)
            rows = q.list_all()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["id"], row_id)
        self.assertEqual(rows[0]["capability_id"], "alpha")
        self.assertEqual(rows[0]["status"], "queued")

    def test_multiple_capabilities_have_distinct_rows(self):
        from core.capability_acquisition_queue import (
            AcquisitionQueue, enqueue,
        )

        with tempfile.TemporaryDirectory() as td:
            q = AcquisitionQueue(Path(td) / "queue.db")
            enqueue(q, **_enqueue_kwargs(capability_id="alpha"))
            enqueue(q, **_enqueue_kwargs(capability_id="beta"))
            rows = q.list_all()
        ids = sorted(r["capability_id"] for r in rows)
        self.assertEqual(ids, ["alpha", "beta"])


# ── duplicate suppression ──────────────────────────────────────────


class TestDuplicateSuppression(unittest.TestCase):
    """A second enqueue of an already-queued capability returns the
    existing queued row's id, not a new one. Otherwise repeated
    approvals would balloon the queue."""

    def test_second_enqueue_for_queued_capability_returns_existing(self):
        from core.capability_acquisition_queue import (
            AcquisitionQueue, enqueue,
        )

        with tempfile.TemporaryDirectory() as td:
            q = AcquisitionQueue(Path(td) / "queue.db")
            id1 = enqueue(q, **_enqueue_kwargs(capability_id="alpha"))
            id2 = enqueue(q, **_enqueue_kwargs(capability_id="alpha"))
            rows = q.list_all()
        self.assertEqual(id1, id2)
        self.assertEqual(len(rows), 1)

    def test_after_completion_new_enqueue_creates_new_row(self):
        """Completed/cancelled/failed rows don't suppress new ones —
        the previous attempt is over, a new intent is real."""
        from core.capability_acquisition_queue import (
            AcquisitionQueue, enqueue,
        )

        with tempfile.TemporaryDirectory() as td:
            q = AcquisitionQueue(Path(td) / "queue.db")
            id1 = enqueue(q, **_enqueue_kwargs(capability_id="alpha"))
            q.transition(id1, "completed")
            id2 = enqueue(q, **_enqueue_kwargs(capability_id="alpha"))
        self.assertNotEqual(id1, id2)


# ── append-only-ish: no deletes; only transitions ────────────────


class TestAppendOnly(unittest.TestCase):
    def test_no_public_delete_method(self):
        """Audit trail: rows can transition status, never disappear."""
        from core.capability_acquisition_queue import AcquisitionQueue

        with tempfile.TemporaryDirectory() as td:
            q = AcquisitionQueue(Path(td) / "queue.db")
        # No public delete on the queue.
        self.assertFalse(hasattr(q, "delete"))
        self.assertFalse(hasattr(q, "remove"))

    def test_transition_changes_status_not_row_count(self):
        from core.capability_acquisition_queue import (
            AcquisitionQueue, enqueue,
        )

        with tempfile.TemporaryDirectory() as td:
            q = AcquisitionQueue(Path(td) / "queue.db")
            row_id = enqueue(q, **_enqueue_kwargs())
            self.assertEqual(len(q.list_all()), 1)
            q.transition(row_id, "cancelled")
            self.assertEqual(len(q.list_all()), 1)
            row = q.get(row_id)
        self.assertEqual(row["status"], "cancelled")

    def test_transition_rejects_invalid_status(self):
        from core.capability_acquisition_queue import (
            AcquisitionQueue, enqueue,
        )

        with tempfile.TemporaryDirectory() as td:
            q = AcquisitionQueue(Path(td) / "queue.db")
            row_id = enqueue(q, **_enqueue_kwargs())
            with self.assertRaises(ValueError):
                q.transition(row_id, "garbage")


# ── filters ────────────────────────────────────────────────────────


class TestQueryHelpers(unittest.TestCase):
    def test_list_open_returns_only_queued_rows(self):
        from core.capability_acquisition_queue import (
            AcquisitionQueue, enqueue,
        )

        with tempfile.TemporaryDirectory() as td:
            q = AcquisitionQueue(Path(td) / "queue.db")
            id1 = enqueue(q, **_enqueue_kwargs(capability_id="alpha"))
            id2 = enqueue(q, **_enqueue_kwargs(capability_id="beta"))
            q.transition(id1, "completed")
            open_rows = q.list_open()
        self.assertEqual(len(open_rows), 1)
        self.assertEqual(open_rows[0]["id"], id2)


# ── action handler param validation ───────────────────────────────


class TestActionHandlerValidation(unittest.TestCase):
    def test_handler_rejects_missing_capability_id(self):
        from core.capability_acquisition_queue import handle_capability_acquire

        with tempfile.TemporaryDirectory() as td:
            q_path = Path(td) / "queue.db"
            params = _enqueue_kwargs()
            params.pop("capability_id")
            with self.assertRaises(ValueError):
                handle_capability_acquire(params, queue_path=q_path)

    def test_handler_rejects_non_manual_source_in_v1(self):
        from core.capability_acquisition_queue import handle_capability_acquire

        with tempfile.TemporaryDirectory() as td:
            q_path = Path(td) / "queue.db"
            params = _enqueue_kwargs(source="field-search")
            with self.assertRaises(ValueError):
                handle_capability_acquire(params, queue_path=q_path)

    def test_handler_rejects_path_outside_maez_manual(self):
        from core.capability_acquisition_queue import handle_capability_acquire

        with tempfile.TemporaryDirectory() as td:
            q_path = Path(td) / "queue.db"
            params = _enqueue_kwargs(
                manual_source_path="/etc/passwd",
            )
            with self.assertRaises(ValueError):
                handle_capability_acquire(params, queue_path=q_path)

    def test_handler_rejects_path_traversal(self):
        from core.capability_acquisition_queue import handle_capability_acquire

        with tempfile.TemporaryDirectory() as td:
            q_path = Path(td) / "queue.db"
            params = _enqueue_kwargs(
                manual_source_path=str(
                    _REPO / "docs" / "maez_manual" / ".." / ".." /
                    "config" / "identity.yaml"
                ),
            )
            with self.assertRaises(ValueError):
                handle_capability_acquire(params, queue_path=q_path)

    def test_handler_rejects_acquisition_mismatch_with_manual(self):
        """If params claim acquisition='owner-install' but the
        manual entry says 'self-dev', that's a mismatch — could be
        a stale or tampered card. Refuse."""
        from core.capability_acquisition_queue import handle_capability_acquire

        with tempfile.TemporaryDirectory() as td:
            q_path = Path(td) / "queue.db"
            params = _enqueue_kwargs(
                # The seed RLM entry says self-dev; we lie.
                capability_id="recursive-context-engine",
                manual_source_path=str(
                    _REPO / "docs" / "maez_manual"
                    / "recursive-context-engine.md"
                ),
                acquisition="owner-install",
            )
            with self.assertRaises(ValueError):
                handle_capability_acquire(params, queue_path=q_path)

    def test_handler_writes_one_queued_row_on_valid_params(self):
        from core.capability_acquisition_queue import (
            AcquisitionQueue, handle_capability_acquire,
        )

        with tempfile.TemporaryDirectory() as td:
            q_path = Path(td) / "queue.db"
            params = _enqueue_kwargs(
                capability_id="recursive-context-engine",
                manual_source_path=str(
                    _REPO / "docs" / "maez_manual"
                    / "recursive-context-engine.md"
                ),
                acquisition="self-dev",
            )
            output = handle_capability_acquire(params, queue_path=q_path)
            q = AcquisitionQueue(q_path)
            rows = q.list_all()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["status"], "queued")
        self.assertEqual(
            rows[0]["capability_id"], "recursive-context-engine",
        )
        # Owner-visible message must be honest about non-installation.
        text = output.lower()
        self.assertIn("queued", text)
        self.assertTrue(
            "no code was fetched" in text
            or "no code is fetched" in text
            or "not installed" in text,
            f"handler output must declare non-installation: {text!r}",
        )


# ── non-installation guarantee ─────────────────────────────────────


class TestNoSideEffects(unittest.TestCase):
    def test_handler_does_not_modify_repo_files(self):
        """The handler must NOT write anywhere except the queue DB."""
        from core.capability_acquisition_queue import handle_capability_acquire

        # Snapshot the manual entry's mtime + content before; verify
        # unchanged after.
        manual = (
            _REPO / "docs" / "maez_manual"
            / "recursive-context-engine.md"
        )
        before_content = manual.read_bytes()
        before_mtime = manual.stat().st_mtime

        with tempfile.TemporaryDirectory() as td:
            q_path = Path(td) / "queue.db"
            params = _enqueue_kwargs(
                capability_id="recursive-context-engine",
                manual_source_path=str(manual),
                acquisition="self-dev",
            )
            handle_capability_acquire(params, queue_path=q_path)

        self.assertEqual(manual.read_bytes(), before_content)
        self.assertEqual(manual.stat().st_mtime, before_mtime)

    def test_handler_does_not_call_subprocess(self):
        """The handler must not run shell commands. Ever."""
        from unittest.mock import patch
        from core.capability_acquisition_queue import handle_capability_acquire

        with tempfile.TemporaryDirectory() as td:
            q_path = Path(td) / "queue.db"
            params = _enqueue_kwargs(
                capability_id="recursive-context-engine",
                manual_source_path=str(
                    _REPO / "docs" / "maez_manual"
                    / "recursive-context-engine.md"
                ),
                acquisition="self-dev",
            )
            with patch("subprocess.run") as mock_run, \
                 patch("subprocess.Popen") as mock_popen, \
                 patch("subprocess.check_output") as mock_chk:
                handle_capability_acquire(params, queue_path=q_path)
        self.assertEqual(mock_run.call_count, 0)
        self.assertEqual(mock_popen.call_count, 0)
        self.assertEqual(mock_chk.call_count, 0)


# ── proposal payload still create_card-compatible after Step 4b ───


class TestProposalPayloadCompatibility(unittest.TestCase):
    """Step 4b adds the action handler. The payload shape from
    Step 4 must still be invocable as create_card(**payload).
    Regression-protect."""

    def test_create_card_accepts_proposal_payload(self):
        from core.capability_proposal import generate_proposals
        from core.capability_evaluator import (
            CapabilityEvaluation, EvaluationReason,
        )
        from core.capability_manual import load_manual

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "alpha.md").write_text(
                "---\n"
                "capability_id: alpha\ntitle: Alpha\nstatus: stable\n"
                "gap_signals:\n  - 'user wants something'\n"
                "prerequisites: []\nexternal_prerequisites: []\n"
                "acquisition: self-dev\n"
                "covenant:\n  consent-card-required: true\n"
                "  exact-phrase-ratification: false\n"
                "  covenant-touch: low\n"
                "conflicts_with: []\nreference_papers: []\n"
                "implementation_files: []\n"
                "---\nBody.\n",
            )
            manual = load_manual(root)
            entry = manual.find_by_id("alpha")
            ev = CapabilityEvaluation(
                capability_id=entry.capability_id,
                title=entry.title,
                match_score=0.5,
                decision="eligible",
                reasons=[EvaluationReason(
                    code="ok", severity="info",
                    message="(test)", evidence={},
                )],
                missing_prerequisites=[],
                external_prerequisites=[],
                covenant_touch=entry.covenant.covenant_touch,
                consent_card_required=entry.covenant.consent_card_required,
                exact_phrase_ratification=entry.covenant.exact_phrase_ratification,
                hardware_snapshot={},
                entry=entry,
                matched_signals=["user wants something"],
                matched_terms=["wants"],
            )
            proposals = generate_proposals("test query", [ev])
        # PendingCardStore.create_card must accept the payload.
        import inspect
        from core.decision.pending_cards import PendingCardStore

        sig = inspect.signature(PendingCardStore.create_card)
        valid_kwargs = set(sig.parameters.keys()) - {"self"}
        payload_keys = set(proposals[0].card_action_payload.keys())
        self.assertTrue(
            payload_keys.issubset(valid_kwargs),
            f"payload keys {payload_keys - valid_kwargs} not in create_card kwargs",
        )


class TestClassifierRouting(unittest.TestCase):
    """capability.acquire must route to Lane 2 (audit + card) so
    owner approval is required. Lane 0 would auto-execute, which
    would defeat the whole consent-card pattern."""

    def test_capability_acquire_routes_to_lane_2(self):
        from core.actions.action_classifier import classify_action

        result = classify_action(
            "capability.acquire",
            {"capability_id": "alpha", "source": "manual"},
        )
        self.assertEqual(result.lane, 2)


class TestActionEngineDispatch(unittest.TestCase):
    """The dispatch shim in _execute_action must route
    'capability.acquire' (dotted) to _do_capability_acquire (the
    valid Python identifier)."""

    def test_action_engine_resolves_dotted_capability_acquire(self):
        from core.actions.action_engine import ActionEngine

        # Construct a minimal ActionEngine — _do_capability_acquire
        # exists as a method.
        engine = ActionEngine.__new__(ActionEngine)
        self.assertTrue(hasattr(engine, "_do_capability_acquire"))
        self.assertTrue(callable(engine._do_capability_acquire))


class TestEndToEndProposalToQueue(unittest.TestCase):
    """The full chain: proposal payload → create_card → handler →
    queue row. Step 4b's definition of done."""

    def test_create_card_then_handler_lands_one_queued_row(self):
        """Simulate the approval flow without involving the full
        decision pipeline. The point: confirm that the
        proposal.card_action_payload is invocable end-to-end and
        that handler execution lands exactly one queued row."""
        from core.capability_acquisition_queue import (
            AcquisitionQueue, handle_capability_acquire,
        )
        from core.capability_proposal import generate_proposals
        from core.capability_evaluator import (
            CapabilityEvaluation, EvaluationReason,
        )
        from core.capability_manual import load_manual

        with tempfile.TemporaryDirectory() as td:
            q_path = Path(td) / "queue.db"

            # Use the real seed manual.
            manual = load_manual()
            entry = manual.find_by_id("recursive-context-engine")
            ev = CapabilityEvaluation(
                capability_id=entry.capability_id,
                title=entry.title,
                match_score=0.7,
                decision="eligible",
                reasons=[EvaluationReason(
                    code="ok", severity="info",
                    message="(test fixture)", evidence={},
                )],
                missing_prerequisites=[],
                external_prerequisites=list(entry.external_prerequisites),
                covenant_touch=entry.covenant.covenant_touch,
                consent_card_required=entry.covenant.consent_card_required,
                exact_phrase_ratification=entry.covenant.exact_phrase_ratification,
                hardware_snapshot={},
                entry=entry,
                matched_signals=["user requests synthesis across "
                                 "more than 30 days of memory"],
                matched_terms=["synthesis"],
            )
            proposals = generate_proposals(
                "synthesize across many months", [ev],
            )
            self.assertEqual(len(proposals), 1)
            payload = proposals[0].card_action_payload

            # Simulate approval: hand the payload's params to the
            # handler. (In production the action_engine dispatches
            # this on Lane 2 card approval.)
            output = handle_capability_acquire(
                payload["params"], queue_path=q_path,
            )
            queue = AcquisitionQueue(q_path)
            rows = queue.list_all()

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["status"], "queued")
        self.assertEqual(
            rows[0]["capability_id"], "recursive-context-engine",
        )
        # Output declares non-installation honestly.
        self.assertIn("queued", output.lower())
        self.assertIn("no code", output.lower())


if __name__ == "__main__":
    unittest.main()
