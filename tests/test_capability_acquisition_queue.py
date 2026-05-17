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


class TestRepoAnchoredManualPath(unittest.TestCase):
    """Patch (Step 4b post-review): manual_source_path containment
    must be anchored on the repo's docs/maez_manual root, not any
    docs/maez_manual ancestor anywhere on the filesystem."""

    def test_external_docs_maez_manual_rejected(self):
        from core.capability_acquisition_queue import handle_capability_acquire

        with tempfile.TemporaryDirectory() as td:
            # Build a fake docs/maez_manual outside the repo.
            fake = (Path(td) / "docs" / "maez_manual")
            fake.mkdir(parents=True)
            fake_entry = fake / "fake.md"
            fake_entry.write_text(
                "---\n"
                "capability_id: fake\ntitle: Fake\nstatus: stable\n"
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
            params = _enqueue_kwargs(
                capability_id="fake",
                manual_source_path=str(fake_entry),
            )
            with self.assertRaises(ValueError):
                handle_capability_acquire(
                    params, queue_path=Path(td) / "queue.db",
                )


class TestCapabilityIdMismatchRejected(unittest.TestCase):
    """Patch: handler must verify params['capability_id'] equals
    the manual entry's capability_id. Otherwise a stale/tampered
    card could enqueue 'foo' with a path pointing at a different
    entry."""

    def test_capability_id_mismatch_rejected(self):
        from core.capability_acquisition_queue import handle_capability_acquire

        with tempfile.TemporaryDirectory() as td:
            params = _enqueue_kwargs(
                # claim capability_id='ghost' but path points at RLM
                capability_id="ghost",
                manual_source_path=str(
                    _REPO / "docs" / "maez_manual"
                    / "recursive-context-engine.md"
                ),
                acquisition="self-dev",
            )
            with self.assertRaises(ValueError):
                handle_capability_acquire(
                    params, queue_path=Path(td) / "queue.db",
                )


class TestProposalIdPropagatesThroughCardPayload(unittest.TestCase):
    """Patch: Step 4 proposal generator must include proposal_id
    in card_action_payload['params'] so it survives the real card
    path. Without this, queue rows have null proposal_id even
    though the proposal had one."""

    def test_proposal_id_in_card_payload_params(self):
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
            manual = load_manual(root)
            entry = manual.find_by_id("alpha")
            ev = CapabilityEvaluation(
                capability_id=entry.capability_id,
                title=entry.title,
                match_score=0.5, decision="eligible",
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
                matched_signals=["x"],
                matched_terms=[],
            )
            proposals = generate_proposals("q", [ev])
        params = proposals[0].card_action_payload["params"]
        self.assertIn("proposal_id", params)
        self.assertEqual(params["proposal_id"], proposals[0].proposal_id)


class TestRealApprovalPathEnrichesParams(unittest.TestCase):
    """Patch (the load-bearing one): DecisionPipeline._on_approve
    calls action_engine._execute_action(card.action, card.params,
    ...) — dropping card.reason / proposed summary /
    card.request_id. Real-card approvals would land queue rows
    missing those fields. Patch must enrich params for
    capability.acquire before execution."""

    def test_card_metadata_lands_in_queue_row_via_real_approval(self):
        from unittest.mock import MagicMock, patch as mock_patch

        from core.actions.action_engine import ActionEngine
        from core.capability_acquisition_queue import AcquisitionQueue
        from core.decision.decision_pipeline import DecisionPipeline
        from core.decision.pending_cards import CardRecord

        # Build a CardRecord that mimics one created from a real
        # proposal — params lacks card_request_id / reason /
        # proposed_action_summary (those live on the card row itself).
        with tempfile.TemporaryDirectory() as td:
            q_path = Path(td) / "queue.db"
            params_only = {
                "capability_id": "recursive-context-engine",
                "source": "manual",
                "manual_source_path": str(
                    _REPO / "docs" / "maez_manual"
                    / "recursive-context-engine.md"
                ),
                "acquisition": "self-dev",
                "proposal_id": "prop-test123456",
            }
            card = CardRecord(
                request_id="card-test-req-id",
                created_at=1.0, updated_at=1.0, status="approved",
                action="capability.acquire",
                params=params_only,
                reason="operator-driven gap match: 'test query'",
                proposed_action_summary="Test proposed summary from card.",
            )

            # Fake card_store + audit_log so DecisionPipeline can
            # be constructed minimally. .approve must return our
            # real CardRecord (not a fresh MagicMock) so the
            # downstream enrichment path sees the original metadata.
            store = MagicMock()
            store.approve.return_value = card
            store.approve_and_mark_running.return_value = card
            store.mark_running.return_value = card
            store.mark_done.return_value = card
            store.mark_failed.return_value = card
            store.get.return_value = card
            audit_log = MagicMock()
            audit_log.record_outcome.return_value = None

            engine = ActionEngine.__new__(ActionEngine)
            # _execute_action needs a logger and a few attrs; the
            # method itself is what we test.
            engine.memory = None
            engine._covenant_gate = lambda action, params: None
            engine._log_action = MagicMock()

            pipeline = DecisionPipeline.__new__(DecisionPipeline)
            pipeline.card_store = store
            pipeline.audit_log = audit_log
            pipeline.action_engine = engine
            pipeline.renderer = None  # for any send_resolution path
            from core.governance import operator_user_boundary as s7

            env = s7.build_work_request_envelope(
                request_id=card.request_id,
                action=card.action,
                params=card.params,
                claimed_work_class="capability_acquisition",
                requesting_subsystem="unit",
                closed_symptom_code="verification_needed",
                proposed_change_class="capability_install_intent",
                why_self_fix_failed_class="needs_human_authority",
                affected_refs=("capability:recursive-context-engine",),
                content_exposure_risk="content_free",
                precondition_hash="a" * 64,
                created_at="2026-05-17T16:00:00+00:00",
                expires_at="2026-05-17T17:00:00+00:00",
                predicted_effect_class="behavior_change",
                rollback_path_class="manual_review",
                maez_voice_consultation_id="voice-card-test-req-id",
            )
            consultation = s7.MaezVoiceConsultation(
                consultation_id="voice-card-test-req-id",
                request_id=card.request_id,
                request_envelope_hash=s7.work_request_envelope_hash(env),
                producer="self_mod_dialog_terminal_state",
                source_ref_kind="self_mod_dialog_exchange",
                source_ref_hash="b" * 64,
                maez_voice_consulted=True,
                maez_objection_present=False,
                maez_withdrew_request=False,
                unavailable_reason_code=None,
                created_at="2026-05-17T16:00:00+00:00",
            )
            authority = s7.AuthorityContext(
                actor_id="founder",
                actor_handle_hmac="hmac:s7:founder:" + ("c" * 64),
                role_names=("bonded_user", "operator"),
                grant_source="founder_webauthn",
                allowed_scopes=("operator_health",),
                auth_method="founder_webauthn",
                surface="cockpit",
                credential_ref="cred-capability-test",
                created_at="2026-05-17T16:00:00+00:00",
                expires_at="2026-05-17T17:00:00+00:00",
                verified=True,
            )
            params_hash = s7.canonical_hash(pipeline._execution_params_for_card(card))
            rendered = s7.render_request_statement(
                envelope=env,
                surface="cockpit",
                origin="http://localhost:11437",
                action_params_hash=params_hash,
                authority_context=authority,
                maez_voice_consultation=consultation,
                nonce="nonce-card-test-req-id",
                expires_at="2026-05-17T17:00:00+00:00",
                rendered_at="2026-05-17T16:00:00+00:00",
            )
            artifact = s7.S7AuthorizationArtifact(
                artifact_id="artifact-capability-test",
                request_id=card.request_id,
                request_envelope_hash=s7.work_request_envelope_hash(env),
                rendered_text_hash=rendered.rendered_text_hash,
                action_params_hash=params_hash,
                precondition_hash=env.precondition_hash,
                authority_context_hash=s7.authority_context_hash(authority),
                derived_work_class=env.derived_work_class,
                derived_aggregation_group=env.derived_aggregation_group,
                nonce=rendered.nonce,
                credential_ref="cred-capability-test",
                auth_method="founder_webauthn",
                grant_source="founder_webauthn",
                user_presence=True,
                user_verification=True,
                created_at="2026-05-17T16:00:00+00:00",
                expires_at="2026-05-17T17:00:00+00:00",
                consumed_at=None,
            )
            auth_store = s7.S7AuthorizationStore(Path(td) / "s7_authorization.db")
            auth_store.put(artifact)

            def consume_capability_artifact(transition):
                return auth_store.consume_for_execution(
                    artifact.artifact_id,
                    rendered=rendered,
                    action_params_hash=params_hash,
                    authority_context=authority,
                    precondition_hash=env.precondition_hash,
                    derived_work_class=env.derived_work_class,
                    derived_aggregation_group=env.derived_aggregation_group,
                    now="2026-05-17T16:00:00+00:00",
                    after_consume_before_commit=transition,
                )

            # Patch the queue's default path so the test queue is used.
            # Also stub will-I check to never refuse (the real check
            # imports core.will_i which is harmless but unrelated).
            with mock_patch(
                "core.infra.capability_acquisition_queue."
                "_default_queue_path",
                return_value=q_path,
            ), mock_patch.object(
                pipeline, "_will_i_check", return_value=None,
            ):
                cls = MagicMock()
                cls.source = "test"
                cls.reasoning = "test approval"
                cls.intent_category = None
                cls.lane = 2
                pipeline._on_approve(
                    card,
                    cls,
                    user_id="test-owner",
                    pre_execute_hook=consume_capability_artifact,
                    s7_artifact_id=artifact.artifact_id,
                )

            queue = AcquisitionQueue(q_path)
            rows = queue.list_all()

        self.assertEqual(len(rows), 1, f"expected 1 queue row; got: {rows!r}")
        row = rows[0]
        self.assertEqual(
            row["card_request_id"], "card-test-req-id",
            "card.request_id must propagate into queue row",
        )
        self.assertEqual(
            row["reason"], "operator-driven gap match: 'test query'",
            "card.reason must propagate into queue row",
        )
        self.assertEqual(
            row["plain_english"], "Test proposed summary from card.",
            "card.proposed_action_summary must propagate into queue row",
        )


if __name__ == "__main__":
    unittest.main()
