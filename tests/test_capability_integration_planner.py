# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Capability integration planner tests (Step 5a).

The planner consumes queued acquisition intents and produces a
reviewable integration *plan*. It MUST NOT fetch code, install
dependencies, modify Maez files, mark queue rows completed, or call
out to network/Claude-tier services. v1 is deterministic and
offline; field-search enrichment is Step 5b.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))


# ── helpers ────────────────────────────────────────────────────────


_TEMPORAL_PATH = (
    _REPO / "docs" / "maez_manual" / "temporal-arithmetic-at-recall.md"
)
_RLM_PATH = (
    _REPO / "docs" / "maez_manual" / "recursive-context-engine.md"
)


def _seed_queue(td: Path, *, capability_id: str, manual_path: Path,
                acquisition: str = "self-dev",
                proposal_id: str = "prop-abc12345",
                card_request_id: str = "card-9999") -> tuple[object, str]:
    """Seed the queue with one queued row; return (queue, row_id)."""
    from core.capability_acquisition_queue import AcquisitionQueue

    q = AcquisitionQueue(td / "queue.db")
    row_id = q.enqueue(
        capability_id=capability_id,
        source="manual",
        manual_source_path=str(manual_path),
        acquisition=acquisition,
        proposal_id=proposal_id,
        card_request_id=card_request_id,
        reason="operator-driven gap match: 'test'",
        plain_english="Proposal text.",
        payload_json='{"k": "v"}',
    )
    return q, row_id


# ── happy path ─────────────────────────────────────────────────────


class TestPlanNextConsumesQueuedRow(unittest.TestCase):
    def test_returns_plan_for_oldest_queued_row(self):
        from core.capability_integration_planner import plan_next

        with tempfile.TemporaryDirectory() as td:
            q, row_id = _seed_queue(
                Path(td),
                capability_id="temporal-arithmetic-at-recall",
                manual_path=_TEMPORAL_PATH,
            )
            plan = plan_next(q)
            self.assertIsNotNone(plan)
            self.assertEqual(plan.queue_id, row_id)
            self.assertEqual(
                plan.capability_id, "temporal-arithmetic-at-recall",
            )
            self.assertEqual(plan.source, "manual")
            self.assertEqual(plan.acquisition, "self-dev")
            self.assertIn(plan.status, {"draft", "needs_field_search"})

    def test_plan_carries_provenance_evidence(self):
        from core.capability_integration_planner import plan_next

        with tempfile.TemporaryDirectory() as td:
            q, row_id = _seed_queue(
                Path(td),
                capability_id="temporal-arithmetic-at-recall",
                manual_path=_TEMPORAL_PATH,
                proposal_id="prop-deadbeef",
                card_request_id="card-1234",
            )
            plan = plan_next(q)
            self.assertEqual(plan.evidence["queue_id"], row_id)
            self.assertEqual(plan.evidence["proposal_id"], "prop-deadbeef")
            self.assertEqual(plan.evidence["card_request_id"], "card-1234")
            self.assertEqual(
                plan.evidence["manual_source_path"], str(_TEMPORAL_PATH),
            )

    def test_explicit_id_selects_specific_row(self):
        from core.capability_integration_planner import plan_next

        with tempfile.TemporaryDirectory() as td:
            q, row_id_a = _seed_queue(
                Path(td),
                capability_id="temporal-arithmetic-at-recall",
                manual_path=_TEMPORAL_PATH,
            )
            # Cancel the first so a second can be queued (open-row guard).
            q.transition(row_id_a, "cancelled")
            row_id_b = q.enqueue(
                capability_id="recursive-context-engine",
                source="manual",
                manual_source_path=str(_RLM_PATH),
                acquisition="self-dev",
                proposal_id="prop-xx",
                card_request_id="card-yy",
            )
            plan = plan_next(q, queue_id=row_id_b)
            self.assertEqual(plan.queue_id, row_id_b)
            self.assertEqual(plan.capability_id, "recursive-context-engine")


# ── revalidation ──────────────────────────────────────────────────


class TestRevalidationRejectsDriftedState(unittest.TestCase):
    def test_non_queued_status_rejected(self):
        from core.capability_integration_planner import (
            IntegrationPlannerError, plan_next,
        )

        with tempfile.TemporaryDirectory() as td:
            q, row_id = _seed_queue(
                Path(td),
                capability_id="temporal-arithmetic-at-recall",
                manual_path=_TEMPORAL_PATH,
            )
            q.transition(row_id, "cancelled")
            with self.assertRaises(IntegrationPlannerError):
                plan_next(q, queue_id=row_id)

    def test_external_manual_path_rejected(self):
        from core.capability_integration_planner import (
            IntegrationPlannerError, plan_next,
        )
        from core.capability_acquisition_queue import AcquisitionQueue

        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            fake = tdp / "docs" / "maez_manual"
            fake.mkdir(parents=True)
            fake_entry = fake / "ghost.md"
            fake_entry.write_text(
                "---\ncapability_id: ghost\ntitle: G\nstatus: stable\n"
                "gap_signals:\n  - 'x'\n"
                "prerequisites: []\nexternal_prerequisites: []\n"
                "acquisition: self-dev\n"
                "covenant:\n  consent-card-required: true\n"
                "  exact-phrase-ratification: false\n"
                "  covenant-touch: low\n"
                "conflicts_with: []\nreference_papers: []\n"
                "implementation_files: []\n"
                "---\nbody\n",
            )
            q = AcquisitionQueue(tdp / "queue.db")
            # Bypass handler — write a row directly via enqueue. The
            # queue's own enqueue() does NOT validate path containment;
            # only the action handler does. The planner is the second
            # line of defence for rows that landed via some other path.
            row_id = q.enqueue(
                capability_id="ghost",
                source="manual",
                manual_source_path=str(fake_entry),
                acquisition="self-dev",
            )
            with self.assertRaises(IntegrationPlannerError):
                plan_next(q, queue_id=row_id)

    def test_manual_capability_id_drift_rejected(self):
        from core.capability_integration_planner import (
            IntegrationPlannerError, plan_next,
        )
        from core.capability_acquisition_queue import AcquisitionQueue

        with tempfile.TemporaryDirectory() as td:
            q = AcquisitionQueue(Path(td) / "queue.db")
            # Row claims capability_id='ghost', but the path resolves
            # to a real entry with id 'temporal-arithmetic-at-recall'.
            row_id = q.enqueue(
                capability_id="ghost",
                source="manual",
                manual_source_path=str(_TEMPORAL_PATH),
                acquisition="self-dev",
            )
            with self.assertRaises(IntegrationPlannerError):
                plan_next(q, queue_id=row_id)

    def test_manual_acquisition_drift_rejected(self):
        from core.capability_integration_planner import (
            IntegrationPlannerError, plan_next,
        )
        from core.capability_acquisition_queue import AcquisitionQueue

        with tempfile.TemporaryDirectory() as td:
            q = AcquisitionQueue(Path(td) / "queue.db")
            row_id = q.enqueue(
                capability_id="temporal-arithmetic-at-recall",
                source="manual",
                manual_source_path=str(_TEMPORAL_PATH),
                acquisition="owner-install",  # drift — manual says self-dev
            )
            with self.assertRaises(IntegrationPlannerError):
                plan_next(q, queue_id=row_id)

    def test_deprecated_manual_entry_rejected(self):
        from core.capability_integration_planner import (
            IntegrationPlannerError, plan_next,
        )
        from core.capability_acquisition_queue import AcquisitionQueue

        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            real_root = tdp / "docs" / "maez_manual"
            real_root.mkdir(parents=True)
            depr = real_root / "stale.md"
            depr.write_text(
                "---\ncapability_id: stale\ntitle: Stale\n"
                "status: deprecated\n"
                "gap_signals:\n  - 'x'\n"
                "prerequisites: []\nexternal_prerequisites: []\n"
                "acquisition: self-dev\n"
                "covenant:\n  consent-card-required: true\n"
                "  exact-phrase-ratification: false\n"
                "  covenant-touch: low\n"
                "conflicts_with: []\nreference_papers: []\n"
                "implementation_files: []\n"
                "---\nbody\n",
            )
            q = AcquisitionQueue(tdp / "queue.db")
            row_id = q.enqueue(
                capability_id="stale",
                source="manual",
                manual_source_path=str(depr),
                acquisition="self-dev",
            )
            with self.assertRaises(IntegrationPlannerError):
                # manual_root override so the planner accepts the
                # tmp manual directory as valid; the rejection should
                # come from the deprecated status, not path containment.
                plan_next(
                    q, queue_id=row_id,
                    manual_root=tdp / "docs" / "maez_manual",
                )

    def test_unknown_queue_id_raises(self):
        from core.capability_integration_planner import (
            IntegrationPlannerError, plan_next,
        )
        from core.capability_acquisition_queue import AcquisitionQueue

        with tempfile.TemporaryDirectory() as td:
            q = AcquisitionQueue(Path(td) / "queue.db")
            with self.assertRaises(IntegrationPlannerError):
                plan_next(q, queue_id="acq-doesnotexist")

    def test_no_queued_rows_returns_none(self):
        from core.capability_integration_planner import plan_next
        from core.capability_acquisition_queue import AcquisitionQueue

        with tempfile.TemporaryDirectory() as td:
            q = AcquisitionQueue(Path(td) / "queue.db")
            self.assertIsNone(plan_next(q))


# ── plan content ──────────────────────────────────────────────────


class TestPlanContent(unittest.TestCase):
    def test_required_consents_includes_card_when_covenant_demands(self):
        from core.capability_integration_planner import plan_next

        with tempfile.TemporaryDirectory() as td:
            q, _ = _seed_queue(
                Path(td),
                capability_id="temporal-arithmetic-at-recall",
                manual_path=_TEMPORAL_PATH,
            )
            plan = plan_next(q)
            joined = " | ".join(plan.required_consents).lower()
            self.assertIn("consent card", joined)

    def test_disclaimer_present_in_rendered_text(self):
        from core.capability_integration_planner import plan_next

        with tempfile.TemporaryDirectory() as td:
            q, _ = _seed_queue(
                Path(td),
                capability_id="temporal-arithmetic-at-recall",
                manual_path=_TEMPORAL_PATH,
            )
            plan = plan_next(q)
            text = plan.render_text()
            self.assertIn(
                "integration plan, not an implemented capability",
                text.lower(),
            )

    def test_temporal_entry_produces_concrete_draft(self):
        """User spec: the temporal-arithmetic entry names files and
        behaviour specifically enough that the planner should not
        bail to needs_field_search."""
        from core.capability_integration_planner import plan_next

        with tempfile.TemporaryDirectory() as td:
            q, _ = _seed_queue(
                Path(td),
                capability_id="temporal-arithmetic-at-recall",
                manual_path=_TEMPORAL_PATH,
            )
            plan = plan_next(q)
            self.assertEqual(plan.status, "draft")
            self.assertEqual(plan.next_action, "review_plan")
            # Should surface at least one risk lifted from the
            # "What can go wrong" body section.
            self.assertGreater(len(plan.risks), 0)

    def test_rlm_entry_does_not_fake_certainty(self):
        """User spec: RLM is broad; the planner must NOT pretend it
        has a complete implementation roadmap. Either a draft with
        risks (>= len(risks) >= 2) OR needs_field_search."""
        from core.capability_integration_planner import plan_next

        with tempfile.TemporaryDirectory() as td:
            q, _ = _seed_queue(
                Path(td),
                capability_id="recursive-context-engine",
                manual_path=_RLM_PATH,
            )
            plan = plan_next(q)
            if plan.status == "draft":
                # Draft is acceptable iff it carries real risks.
                self.assertGreaterEqual(len(plan.risks), 2)
            else:
                self.assertEqual(plan.status, "needs_field_search")
                self.assertEqual(
                    plan.next_action, "field_search_required",
                )


# ── side-effect freedom ───────────────────────────────────────────


class TestPlannerHasNoSideEffects(unittest.TestCase):
    def test_does_not_call_subprocess(self):
        from core.capability_integration_planner import plan_next

        with tempfile.TemporaryDirectory() as td:
            q, _ = _seed_queue(
                Path(td),
                capability_id="temporal-arithmetic-at-recall",
                manual_path=_TEMPORAL_PATH,
            )
            with mock.patch(
                "subprocess.run",
                side_effect=AssertionError("planner must not subprocess"),
            ), mock.patch(
                "subprocess.Popen",
                side_effect=AssertionError("planner must not subprocess"),
            ):
                plan_next(q)

    def test_does_not_open_network(self):
        from core.capability_integration_planner import plan_next
        import socket

        with tempfile.TemporaryDirectory() as td:
            q, _ = _seed_queue(
                Path(td),
                capability_id="temporal-arithmetic-at-recall",
                manual_path=_TEMPORAL_PATH,
            )
            real_socket = socket.socket

            def boom(*a, **kw):
                raise AssertionError("planner must not open sockets")

            with mock.patch.object(socket, "socket", boom):
                # SQLite uses no sockets locally; the planner reads
                # the manual file and the queue DB only.
                plan_next(q)
            # Sanity restore.
            self.assertIs(socket.socket, real_socket)

    def test_does_not_modify_queue_status(self):
        from core.capability_integration_planner import plan_next

        with tempfile.TemporaryDirectory() as td:
            q, row_id = _seed_queue(
                Path(td),
                capability_id="temporal-arithmetic-at-recall",
                manual_path=_TEMPORAL_PATH,
            )
            before = q.get(row_id)
            plan_next(q)
            after = q.get(row_id)
            self.assertEqual(before["status"], "queued")
            self.assertEqual(after["status"], "queued")
            self.assertEqual(after["updated_at"], before["updated_at"])

    def test_does_not_write_to_repo(self):
        """Planner must not touch any file under the repo root.
        Snapshot the docs/ + core/ + scripts/ mtimes before and
        after; nothing should change."""
        from core.capability_integration_planner import plan_next

        watched: list[Path] = []
        for sub in ("core", "docs/maez_manual", "scripts"):
            for p in (_REPO / sub).rglob("*"):
                if p.is_file():
                    watched.append(p)

        before = {p: p.stat().st_mtime_ns for p in watched}

        with tempfile.TemporaryDirectory() as td:
            q, _ = _seed_queue(
                Path(td),
                capability_id="temporal-arithmetic-at-recall",
                manual_path=_TEMPORAL_PATH,
            )
            plan_next(q)

        after = {p: p.stat().st_mtime_ns for p in watched}
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
