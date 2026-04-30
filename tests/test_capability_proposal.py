# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Capability proposal tests (Step 4 of the Decision-19/20 pipeline).

Step 4 turns eligible CapabilityEvaluation objects into structured
proposal artifacts. It does NOT install anything, run field search,
create consent cards, or persist to a DB. The proposal is the
return value; pending_cards integration is Step 4b.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))


# ── synthetic fixtures ────────────────────────────────────────────


def _entry_text(
    *,
    capability_id: str,
    title: str = "Test capability",
    status: str = "stable",
    gap_signals: list[str] | None = None,
    body: str = (
        "# Test\n\n## When this matters\n\n"
        "Plain English explanation of when this capability fires.\n\n"
        "## Cost\n\nMore content.\n"
    ),
) -> str:
    if gap_signals is None:
        gap_signals = ["user wants something"]
    sigs = "\n".join(f"  - {json.dumps(s)}" for s in gap_signals)
    return (
        "---\n"
        f"capability_id: {capability_id}\n"
        f"title: {title}\n"
        f"status: {status}\n"
        f"gap_signals:\n{sigs}\n"
        "prerequisites: []\n"
        "external_prerequisites: []\n"
        "acquisition: self-dev\n"
        "covenant:\n"
        "  consent-card-required: true\n"
        "  exact-phrase-ratification: false\n"
        "  covenant-touch: low\n"
        "conflicts_with: []\nreference_papers: []\n"
        "implementation_files: []\n"
        f"---\n{body}"
    )


def _write_entry(root: Path, capability_id: str, **kwargs) -> Path:
    p = root / f"{capability_id}.md"
    p.write_text(_entry_text(capability_id=capability_id, **kwargs))
    return p


def _make_eligible_evaluation(entry, score: float = 0.5):
    """Build an evaluation with decision=eligible (no blockers)."""
    from core.capability_evaluator import CapabilityEvaluation, EvaluationReason

    return CapabilityEvaluation(
        capability_id=entry.capability_id,
        title=entry.title,
        match_score=score,
        decision="eligible",
        reasons=[EvaluationReason(
            code="no_hardware_requirement_declared",
            severity="info",
            message="(test fixture)",
            evidence={},
        )],
        missing_prerequisites=[],
        external_prerequisites=list(entry.external_prerequisites),
        covenant_touch=entry.covenant.covenant_touch,
        consent_card_required=entry.covenant.consent_card_required,
        exact_phrase_ratification=entry.covenant.exact_phrase_ratification,
        hardware_snapshot={},
        entry=entry,
    )


def _make_deferred_evaluation(entry, score: float = 0.5):
    from core.capability_evaluator import CapabilityEvaluation, EvaluationReason

    return CapabilityEvaluation(
        capability_id=entry.capability_id,
        title=entry.title,
        match_score=score,
        decision="defer",
        reasons=[EvaluationReason(
            code="missing_internal_prerequisite",
            severity="blocker",
            message="(test fixture)",
            evidence={"prerequisite": "ghost"},
        )],
        missing_prerequisites=["ghost"],
        external_prerequisites=[],
        covenant_touch=entry.covenant.covenant_touch,
        consent_card_required=entry.covenant.consent_card_required,
        exact_phrase_ratification=entry.covenant.exact_phrase_ratification,
        hardware_snapshot={},
        entry=entry,
    )


def _make_rejected_evaluation(entry, score: float = 0.5):
    from core.capability_evaluator import CapabilityEvaluation, EvaluationReason

    return CapabilityEvaluation(
        capability_id=entry.capability_id,
        title=entry.title,
        match_score=score,
        decision="reject",
        reasons=[EvaluationReason(
            code="status_deprecated",
            severity="blocker",
            message="(test fixture)",
            evidence={"status": "deprecated"},
        )],
        missing_prerequisites=[],
        external_prerequisites=[],
        covenant_touch=entry.covenant.covenant_touch,
        consent_card_required=entry.covenant.consent_card_required,
        exact_phrase_ratification=entry.covenant.exact_phrase_ratification,
        hardware_snapshot={},
        entry=entry,
    )


# ── eligible → proposal ────────────────────────────────────────────


class TestEligibleGeneratesProposal(unittest.TestCase):
    def test_eligible_evaluation_generates_one_proposal(self):
        from core.capability_proposal import generate_proposals
        from core.capability_manual import load_manual

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_entry(root, "alpha")
            manual = load_manual(root)
            entry = manual.find_by_id("alpha")
            evals = [_make_eligible_evaluation(entry)]
            proposals = generate_proposals("test query", evals)
        self.assertEqual(len(proposals), 1)
        self.assertEqual(proposals[0].capability_id, "alpha")
        self.assertTrue(proposals[0].actionable)

    def test_proposal_has_required_fields(self):
        from core.capability_proposal import generate_proposals
        from core.capability_manual import load_manual

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_entry(root, "alpha")
            manual = load_manual(root)
            entry = manual.find_by_id("alpha")
            evals = [_make_eligible_evaluation(entry, score=0.42)]
            proposals = generate_proposals("test query", evals)
        p = proposals[0]
        # Identity
        self.assertTrue(p.proposal_id)
        self.assertGreater(p.created_at, 0)
        self.assertEqual(p.felt_limitation, "test query")
        # Source / capability
        self.assertEqual(p.capability_id, "alpha")
        self.assertEqual(p.source, "manual")
        self.assertEqual(p.match_score, 0.42)
        # Covenant fields
        self.assertEqual(p.covenant_touch, "low")
        self.assertTrue(p.consent_card_required)
        # Body excerpt is non-empty (entry has a body)
        self.assertTrue(p.body_excerpt)
        # Owner-facing card text
        self.assertTrue(p.card_plain_english)
        # Card payload
        self.assertIsInstance(p.card_action_payload, dict)
        # Manual source path is present
        self.assertIsNotNone(p.manual_source_path)


# ── deferred / rejected: skipped by default ───────────────────────


class TestDefaultSkipsDeferredAndRejected(unittest.TestCase):
    def test_deferred_evaluation_skipped_by_default(self):
        from core.capability_proposal import generate_proposals
        from core.capability_manual import load_manual

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_entry(root, "alpha")
            manual = load_manual(root)
            entry = manual.find_by_id("alpha")
            evals = [_make_deferred_evaluation(entry)]
            proposals = generate_proposals("q", evals)
        self.assertEqual(proposals, [])

    def test_rejected_evaluation_skipped_by_default(self):
        from core.capability_proposal import generate_proposals
        from core.capability_manual import load_manual

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_entry(root, "alpha", status="deprecated")
            manual = load_manual(root)
            entry = manual.find_by_id("alpha")
            evals = [_make_rejected_evaluation(entry)]
            proposals = generate_proposals("q", evals)
        self.assertEqual(proposals, [])


# ── include_deferred flag ────────────────────────────────────────


class TestIncludeDeferredFlag(unittest.TestCase):
    def test_include_deferred_emits_non_actionable_artifacts(self):
        from core.capability_proposal import generate_proposals
        from core.capability_manual import load_manual

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_entry(root, "alpha")
            _write_entry(root, "beta", status="deprecated")
            manual = load_manual(root)
            evals = [
                _make_eligible_evaluation(manual.find_by_id("alpha")),
                _make_deferred_evaluation(manual.find_by_id("alpha")),
                _make_rejected_evaluation(manual.find_by_id("beta")),
            ]
            proposals = generate_proposals(
                "q", evals, include_deferred=True,
            )
        self.assertEqual(len(proposals), 3)
        actionable_count = sum(1 for p in proposals if p.actionable)
        self.assertEqual(actionable_count, 1)
        # Eligible is actionable; deferred and rejected are not.
        for p in proposals:
            if p.evaluation_decision == "eligible":
                self.assertTrue(p.actionable)
            else:
                self.assertFalse(p.actionable)


# ── card_action_payload shape (PendingCard-compatible) ────────────


class TestCardActionPayloadShape(unittest.TestCase):
    def test_payload_has_pending_card_kwargs(self):
        from core.capability_proposal import generate_proposals
        from core.capability_manual import load_manual

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_entry(root, "alpha")
            manual = load_manual(root)
            entry = manual.find_by_id("alpha")
            evals = [_make_eligible_evaluation(entry)]
            proposals = generate_proposals("test query", evals)
        p = proposals[0]
        payload = p.card_action_payload
        # Required kwargs of PendingCardStore.create_card.
        for key in ("action", "params", "reason", "plain_english"):
            self.assertIn(key, payload)
        self.assertEqual(payload["action"], "capability.acquire")
        # Params shape
        params = payload["params"]
        for key in ("capability_id", "source", "manual_source_path",
                    "acquisition"):
            self.assertIn(key, params)
        self.assertEqual(params["capability_id"], "alpha")
        self.assertEqual(params["source"], "manual")
        self.assertEqual(params["acquisition"], "self-dev")
        # Reason references the felt limitation.
        self.assertIn("test query", payload["reason"])

    def test_payload_invocable_via_create_card_kwargs(self):
        """Forward-compatibility: payload keys must MATCH the
        kwargs of PendingCardStore.create_card, so a future Step 4b
        can call create_card(**payload) without translation."""
        from core.capability_proposal import generate_proposals
        from core.capability_manual import load_manual
        import inspect
        from core.decision.pending_cards import PendingCardStore

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_entry(root, "alpha")
            manual = load_manual(root)
            entry = manual.find_by_id("alpha")
            evals = [_make_eligible_evaluation(entry)]
            proposals = generate_proposals("test query", evals)
        sig = inspect.signature(PendingCardStore.create_card)
        valid_kwargs = set(sig.parameters.keys()) - {"self"}
        payload_keys = set(proposals[0].card_action_payload.keys())
        # Every key in our payload must be a valid create_card kwarg.
        unknown = payload_keys - valid_kwargs
        self.assertEqual(
            unknown, set(),
            f"payload has keys not accepted by create_card: {unknown}",
        )


# ── body excerpt rule ────────────────────────────────────────────


class TestBodyExcerpt(unittest.TestCase):
    def test_excerpt_first_non_blank_paragraph(self):
        from core.capability_proposal import generate_proposals
        from core.capability_manual import load_manual

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_entry(
                root, "alpha",
                body=(
                    "# Title\n\n"
                    "## When this matters\n\n"
                    "First substantive paragraph.\n\n"
                    "Second paragraph.\n"
                ),
            )
            manual = load_manual(root)
            evals = [_make_eligible_evaluation(manual.find_by_id("alpha"))]
            proposals = generate_proposals("q", evals)
        excerpt = proposals[0].body_excerpt
        # First non-blank paragraph after stripping headings.
        self.assertIn("First substantive paragraph", excerpt)
        # Second paragraph not included (we want the first).
        self.assertNotIn("Second paragraph", excerpt)

    def test_excerpt_capped_at_800_chars(self):
        from core.capability_proposal import generate_proposals
        from core.capability_manual import load_manual

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            long_para = "x " * 600  # ~1200 chars
            _write_entry(
                root, "alpha",
                body=f"# Title\n\n{long_para}\n",
            )
            manual = load_manual(root)
            evals = [_make_eligible_evaluation(manual.find_by_id("alpha"))]
            proposals = generate_proposals("q", evals)
        self.assertLessEqual(len(proposals[0].body_excerpt), 800)

    def test_excerpt_handles_empty_body(self):
        from core.capability_proposal import generate_proposals
        from core.capability_manual import load_manual

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_entry(root, "alpha", body="")
            manual = load_manual(root)
            evals = [_make_eligible_evaluation(manual.find_by_id("alpha"))]
            proposals = generate_proposals("q", evals)
        # Empty excerpt is acceptable; what matters is no crash.
        self.assertIsInstance(proposals[0].body_excerpt, str)


# ── source field ──────────────────────────────────────────────────


class TestSourceField(unittest.TestCase):
    def test_source_is_manual_in_v1(self):
        from core.capability_proposal import generate_proposals
        from core.capability_manual import load_manual

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_entry(root, "alpha")
            manual = load_manual(root)
            evals = [_make_eligible_evaluation(manual.find_by_id("alpha"))]
            proposals = generate_proposals("q", evals)
        self.assertEqual(proposals[0].source, "manual")
        self.assertEqual(
            proposals[0].card_action_payload["params"]["source"], "manual",
        )


# ── no persistence ────────────────────────────────────────────────


class TestNoPersistence(unittest.TestCase):
    def test_no_db_or_store_created(self):
        """v1 contract: proposal is function output, not persisted.
        Generation must not touch any DB or create files (telemetry
        log is the sole exception and is best-effort)."""
        from core.capability_proposal import generate_proposals
        from core.capability_manual import load_manual

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_entry(root, "alpha")
            manual = load_manual(root)
            evals = [_make_eligible_evaluation(manual.find_by_id("alpha"))]
            with patch(
                "core.infra.capability_proposal._append_telemetry",
                side_effect=lambda payload: None,  # no-op
            ):
                generate_proposals("q", evals)
            # Tmpdir should contain only the manual entry we wrote.
            extra = [
                p for p in root.iterdir()
                if p.name not in {"alpha.md"}
            ]
            self.assertEqual(extra, [])

    def test_no_pending_card_created(self):
        """The proposal generator must NOT call PendingCardStore.
        That's Step 4b's job."""
        from core.capability_proposal import generate_proposals
        from core.capability_manual import load_manual

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_entry(root, "alpha")
            manual = load_manual(root)
            evals = [_make_eligible_evaluation(manual.find_by_id("alpha"))]
            with patch(
                "core.decision.pending_cards.PendingCardStore.create_card",
            ) as mock_create:
                generate_proposals("q", evals)
            self.assertEqual(mock_create.call_count, 0)


# ── telemetry ──────────────────────────────────────────────────────


class TestTelemetry(unittest.TestCase):
    def test_telemetry_failure_does_not_break_generation(self):
        from core.capability_proposal import generate_proposals
        from core.capability_manual import load_manual

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_entry(root, "alpha")
            manual = load_manual(root)
            evals = [_make_eligible_evaluation(manual.find_by_id("alpha"))]
            with patch(
                "core.infra.capability_proposal._append_telemetry",
                side_effect=RuntimeError("simulated"),
            ):
                proposals = generate_proposals("q", evals)
        self.assertEqual(len(proposals), 1)

    def test_telemetry_payload_shape(self):
        from core.capability_proposal import generate_proposals
        from core.capability_manual import load_manual

        captured = []
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_entry(root, "alpha")
            manual = load_manual(root)
            evals = [_make_eligible_evaluation(manual.find_by_id("alpha"))]
            with patch(
                "core.infra.capability_proposal._append_telemetry",
                side_effect=lambda payload: captured.append(payload),
            ):
                generate_proposals("test query", evals)
        # One telemetry line per evaluation processed.
        self.assertEqual(len(captured), 1)
        for k in ("timestamp", "query", "capability_id",
                  "proposal_id", "generated"):
            self.assertIn(k, captured[0])
        self.assertTrue(captured[0]["generated"])
        self.assertEqual(captured[0]["query"], "test query")

    def test_telemetry_records_skipped_evaluations(self):
        """When include_deferred=False, deferred evaluations are
        skipped — but the skip should still appear in telemetry so
        we can analyze why proposals didn't fire."""
        from core.capability_proposal import generate_proposals
        from core.capability_manual import load_manual

        captured = []
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_entry(root, "alpha")
            manual = load_manual(root)
            evals = [_make_deferred_evaluation(manual.find_by_id("alpha"))]
            with patch(
                "core.infra.capability_proposal._append_telemetry",
                side_effect=lambda payload: captured.append(payload),
            ):
                generate_proposals("q", evals)
        self.assertEqual(len(captured), 1)
        self.assertFalse(captured[0]["generated"])
        self.assertEqual(captured[0]["decision"], "defer")


# ── owner-facing text says "proposal, not installed" ──────────────


class TestProposalFraming(unittest.TestCase):
    def test_card_plain_english_says_proposal_not_installed(self):
        """Load-bearing social contract: the card text must make
        clear that the proposal is just a proposal — owner approval
        is what triggers acquisition, not the proposal generation."""
        from core.capability_proposal import generate_proposals
        from core.capability_manual import load_manual

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_entry(root, "alpha")
            manual = load_manual(root)
            evals = [_make_eligible_evaluation(manual.find_by_id("alpha"))]
            proposals = generate_proposals("q", evals)
        text = proposals[0].card_plain_english.lower()
        # At least one of these phrases must appear, signaling the
        # social contract.
        self.assertTrue(
            "proposal" in text or "propose" in text,
            f"card text doesn't frame as proposal: {text!r}",
        )
        self.assertTrue(
            "not installed" in text
            or "approval" in text
            or "approve" in text
            or "consent" in text,
            f"card text doesn't reference approval/consent gate: {text!r}",
        )


class TestEvidencePreservationInProposal(unittest.TestCase):
    """Patch (2026-04-30): proposal must surface matched_signals /
    matched_terms from the evaluation. When evidence is absent the
    'Matched because:' line is omitted rather than fabricated."""

    def _make_eligible_with_evidence(self, entry, *, signals, terms,
                                     score: float = 0.5):
        from core.capability_evaluator import (
            CapabilityEvaluation, EvaluationReason,
        )
        return CapabilityEvaluation(
            capability_id=entry.capability_id,
            title=entry.title,
            match_score=score,
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
            matched_signals=signals,
            matched_terms=terms,
        )

    def test_proposal_includes_matched_signals_and_terms(self):
        from core.capability_proposal import generate_proposals
        from core.capability_manual import load_manual

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_entry(root, "alpha")
            manual = load_manual(root)
            entry = manual.find_by_id("alpha")
            ev = self._make_eligible_with_evidence(
                entry,
                signals=["user wants something",
                         "user asked X"],
                terms=["wants", "x"],
            )
            proposals = generate_proposals("test query", [ev])
        p = proposals[0]
        self.assertEqual(
            p.matched_signals,
            ["user wants something", "user asked X"],
        )
        self.assertEqual(p.matched_terms, ["wants", "x"])

    def test_card_text_includes_matched_because_when_evidence_present(self):
        from core.capability_proposal import generate_proposals
        from core.capability_manual import load_manual

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_entry(root, "alpha")
            manual = load_manual(root)
            entry = manual.find_by_id("alpha")
            ev = self._make_eligible_with_evidence(
                entry,
                signals=["user requests synthesis across many days"],
                terms=["synthesis", "days"],
            )
            proposals = generate_proposals("q", [ev])
        text = proposals[0].card_plain_english
        self.assertIn("Matched because", text)
        # The actual signal text appears in the card — not a
        # fabricated paraphrase.
        self.assertIn(
            "user requests synthesis across many days", text,
        )

    def test_card_text_omits_matched_because_when_evidence_empty(self):
        """No fabrication: when matched_signals AND matched_terms
        are both empty, the 'Matched because:' line MUST be absent
        from the card text. The proposal cannot claim evidence it
        doesn't have."""
        from core.capability_proposal import generate_proposals
        from core.capability_manual import load_manual

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_entry(root, "alpha")
            manual = load_manual(root)
            entry = manual.find_by_id("alpha")
            ev = self._make_eligible_with_evidence(
                entry, signals=[], terms=[],
            )
            proposals = generate_proposals("q", [ev])
        text = proposals[0].card_plain_english
        self.assertNotIn("Matched because", text)

    def test_card_text_falls_back_to_terms_when_only_terms_present(self):
        """Phrase-hit-only matches produce empty matched_signals
        but non-empty matched_terms. The card should still surface
        SOMETHING — token-level overlap — rather than fabricating
        a signal sentence."""
        from core.capability_proposal import generate_proposals
        from core.capability_manual import load_manual

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_entry(root, "alpha")
            manual = load_manual(root)
            entry = manual.find_by_id("alpha")
            ev = self._make_eligible_with_evidence(
                entry, signals=[], terms=["foo", "bar", "baz"],
            )
            proposals = generate_proposals("q", [ev])
        text = proposals[0].card_plain_english
        # Some kind of matched-because surface is expected.
        self.assertIn("Matched because", text)
        # But the specific token content should appear.
        self.assertIn("foo", text)


if __name__ == "__main__":
    unittest.main()
