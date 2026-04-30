# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Capability evaluator tests (Step 3 of the Decision-19/20
capability-acquisition pipeline arc).

The evaluator answers "can Maez responsibly consider this candidate
now?" — eligible / defer / reject — based on prerequisites, status,
covenant impact, and hardware constraints. It does NOT answer
"should we install it" (that's Step 4 / proposal + consent).
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


# ── synthetic manual fixture ───────────────────────────────────────


def _entry_text(
    *,
    capability_id: str,
    title: str = "Test capability",
    status: str = "stable",
    gap_signals: list[str] | None = None,
    prerequisites: list[str] | None = None,
    external_prerequisites: list[str] | None = None,
    conflicts_with: list[str] | None = None,
    covenant_touch: str = "low",
    consent_card_required: bool = True,
    extra_front_matter: dict | None = None,
    body: str = "Body.\n",
) -> str:
    """Build a valid manual entry. Extra front-matter (e.g.
    min_vram_mb) is appended verbatim — the loader preserves it
    in raw_front_matter."""
    if gap_signals is None:
        gap_signals = ["user wants something"]
    if prerequisites is None:
        prerequisites = []
    if external_prerequisites is None:
        external_prerequisites = []
    if conflicts_with is None:
        conflicts_with = []
    sigs = "\n".join(f"  - {json.dumps(s)}" for s in gap_signals)
    prereqs = "\n".join(f"  - {p}" for p in prerequisites)
    ext_prereqs = "\n".join(f"  - {p}" for p in external_prerequisites)
    confs = "\n".join(f"  - {c}" for c in conflicts_with)
    extra = ""
    if extra_front_matter:
        for k, v in extra_front_matter.items():
            if isinstance(v, bool):
                extra += f"{k}: {'true' if v else 'false'}\n"
            elif isinstance(v, str):
                extra += f"{k}: {json.dumps(v)}\n"
            elif v is None:
                extra += f"{k}: null\n"
            else:
                extra += f"{k}: {v}\n"
    return (
        "---\n"
        f"capability_id: {capability_id}\n"
        f"title: {title}\n"
        f"status: {status}\n"
        f"gap_signals:\n{sigs}\n"
        f"prerequisites:\n{prereqs}\n"
        f"external_prerequisites:\n{ext_prereqs}\n"
        "acquisition: self-dev\n"
        "covenant:\n"
        f"  consent-card-required: {'true' if consent_card_required else 'false'}\n"
        "  exact-phrase-ratification: false\n"
        f"  covenant-touch: {covenant_touch}\n"
        f"conflicts_with:\n{confs}\n"
        "reference_papers: []\n"
        "implementation_files: []\n"
        f"{extra}"
        f"---\n{body}"
    )


def _write_entry(root: Path, capability_id: str, **kwargs) -> Path:
    p = root / f"{capability_id}.md"
    p.write_text(_entry_text(capability_id=capability_id, **kwargs))
    return p


def _make_match(entry, score: float = 0.5):
    """Build a CapabilityMatch wrapping the given entry."""
    from core.capability_gap_matcher import CapabilityMatch

    return CapabilityMatch(
        capability_id=entry.capability_id,
        title=entry.title,
        score=score,
        matched_signals=list(entry.gap_signals),
        matched_terms=[],
        status=entry.status,
        source_path=entry.source_path,
        entry=entry,
    )


# ── deprecated entry → reject ──────────────────────────────────────


class TestDeprecatedReject(unittest.TestCase):
    def test_deprecated_entry_rejected(self):
        from core.capability_evaluator import evaluate_match
        from core.capability_manual import load_manual

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_entry(root, "old-thing", status="deprecated")
            manual = load_manual(root)
            entry = manual.find_by_id("old-thing")
            ev = evaluate_match(_make_match(entry), manual=manual,
                                hardware={})
        self.assertEqual(ev.decision, "reject")
        codes = [r.code for r in ev.reasons]
        self.assertIn("status_deprecated", codes)


# ── missing internal prereq → defer ───────────────────────────────


class TestMissingInternalPrereqDefers(unittest.TestCase):
    def test_missing_internal_prereq_defers(self):
        from core.capability_evaluator import evaluate_match
        from core.capability_manual import load_manual

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_entry(
                root, "alpha",
                prerequisites=["beta-not-in-manual"],
            )
            manual = load_manual(root)
            entry = manual.find_by_id("alpha")
            ev = evaluate_match(_make_match(entry), manual=manual,
                                hardware={})
        self.assertEqual(ev.decision, "defer")
        codes = [r.code for r in ev.reasons]
        self.assertIn("missing_internal_prerequisite", codes)
        self.assertIn("beta-not-in-manual", ev.missing_prerequisites)

    def test_internal_prereq_present_does_not_defer_for_that_reason(self):
        from core.capability_evaluator import evaluate_match
        from core.capability_manual import load_manual

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_entry(root, "beta")
            _write_entry(root, "alpha", prerequisites=["beta"])
            manual = load_manual(root)
            entry = manual.find_by_id("alpha")
            ev = evaluate_match(_make_match(entry), manual=manual,
                                hardware={})
        codes = [r.code for r in ev.reasons]
        self.assertNotIn("missing_internal_prerequisite", codes)


# ── deprecated transitive prereq → defer ──────────────────────────


class TestDeprecatedTransitivePrereq(unittest.TestCase):
    """If A's prerequisite B exists in the manual but is deprecated,
    A is not eligible. Decision='defer' with prerequisite_deprecated
    warning."""

    def test_prereq_deprecated_defers(self):
        from core.capability_evaluator import evaluate_match
        from core.capability_manual import load_manual

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_entry(root, "old-base", status="deprecated")
            _write_entry(root, "alpha", prerequisites=["old-base"])
            manual = load_manual(root)
            entry = manual.find_by_id("alpha")
            ev = evaluate_match(_make_match(entry), manual=manual,
                                hardware={})
        self.assertEqual(ev.decision, "defer")
        codes = [r.code for r in ev.reasons]
        self.assertIn("prerequisite_deprecated", codes)


# ── external prereq does not block ────────────────────────────────


class TestExternalPrereqNonBlocking(unittest.TestCase):
    def test_external_prereq_is_informational(self):
        from core.capability_evaluator import evaluate_match
        from core.capability_manual import load_manual

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_entry(
                root, "alpha",
                external_prerequisites=["working-self"],
            )
            manual = load_manual(root)
            entry = manual.find_by_id("alpha")
            ev = evaluate_match(_make_match(entry), manual=manual,
                                hardware={})
        # External prereq does not produce a blocker.
        blocker_codes = [
            r.code for r in ev.reasons if r.severity == "blocker"
        ]
        self.assertNotIn("missing_external_prerequisite", blocker_codes)
        # And shouldn't push decision to defer/reject by itself.
        self.assertEqual(ev.decision, "eligible")


# ── covenant high touch → defer with warning ──────────────────────


class TestCovenantHighTouchDefers(unittest.TestCase):
    def test_high_covenant_touch_defers(self):
        from core.capability_evaluator import evaluate_match
        from core.capability_manual import load_manual

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_entry(root, "alpha", covenant_touch="high")
            manual = load_manual(root)
            entry = manual.find_by_id("alpha")
            ev = evaluate_match(_make_match(entry), manual=manual,
                                hardware={})
        self.assertEqual(ev.decision, "defer")
        codes = [r.code for r in ev.reasons]
        self.assertIn("covenant_touch_high", codes)


# ── conflicts_with → skipped with single info reason ──────────────


class TestConflictsCheckSkipped(unittest.TestCase):
    def test_conflicts_check_emits_skip_info_reason(self):
        """No activation registry yet, so conflicts_with isn't
        meaningfully checkable. Spec: emit one info reason rather
        than implementing a half-check."""
        from core.capability_evaluator import evaluate_match
        from core.capability_manual import load_manual

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_entry(
                root, "alpha",
                conflicts_with=["other-thing"],
            )
            manual = load_manual(root)
            entry = manual.find_by_id("alpha")
            ev = evaluate_match(_make_match(entry), manual=manual,
                                hardware={})
        codes = [r.code for r in ev.reasons]
        self.assertIn(
            "conflicts_check_skipped_no_activation_registry", codes,
        )

    def test_conflicts_skip_does_not_change_decision(self):
        """The skip is informational only — the evaluator does not
        defer or reject because of conflicts_with."""
        from core.capability_evaluator import evaluate_match
        from core.capability_manual import load_manual

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_entry(
                root, "alpha", conflicts_with=["other"],
            )
            manual = load_manual(root)
            entry = manual.find_by_id("alpha")
            ev = evaluate_match(_make_match(entry), manual=manual,
                                hardware={})
        # No conflict-driven blocker.
        self.assertEqual(ev.decision, "eligible")


# ── hardware checks ───────────────────────────────────────────────


class TestHardwareChecks(unittest.TestCase):
    def test_no_hardware_requirement_emits_info_reason(self):
        from core.capability_evaluator import evaluate_match
        from core.capability_manual import load_manual

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_entry(root, "alpha")
            manual = load_manual(root)
            entry = manual.find_by_id("alpha")
            ev = evaluate_match(_make_match(entry), manual=manual,
                                hardware={"vram_available_mb": 4000})
        codes = [r.code for r in ev.reasons]
        self.assertIn("no_hardware_requirement_declared", codes)
        self.assertEqual(ev.decision, "eligible")

    def test_min_vram_insufficient_rejects(self):
        from core.capability_evaluator import evaluate_match
        from core.capability_manual import load_manual

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_entry(
                root, "alpha",
                extra_front_matter={"min_vram_mb": 16000},
            )
            manual = load_manual(root)
            entry = manual.find_by_id("alpha")
            ev = evaluate_match(
                _make_match(entry), manual=manual,
                hardware={"vram_available_mb": 4000},
            )
        self.assertEqual(ev.decision, "reject")
        codes = [r.code for r in ev.reasons]
        self.assertIn("vram_insufficient", codes)

    def test_min_vram_unknown_hardware_defers(self):
        from core.capability_evaluator import evaluate_match
        from core.capability_manual import load_manual

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_entry(
                root, "alpha",
                extra_front_matter={"min_vram_mb": 16000},
            )
            manual = load_manual(root)
            entry = manual.find_by_id("alpha")
            ev = evaluate_match(
                _make_match(entry), manual=manual,
                hardware={"vram_available_mb": None},
            )
        self.assertEqual(ev.decision, "defer")
        codes = [r.code for r in ev.reasons]
        self.assertIn("vram_unknown", codes)
        self.assertNotIn("vram_insufficient", codes)

    def test_min_vram_sufficient_passes(self):
        from core.capability_evaluator import evaluate_match
        from core.capability_manual import load_manual

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_entry(
                root, "alpha",
                extra_front_matter={"min_vram_mb": 4000},
            )
            manual = load_manual(root)
            entry = manual.find_by_id("alpha")
            ev = evaluate_match(
                _make_match(entry), manual=manual,
                hardware={"vram_available_mb": 8000},
            )
        codes = [r.code for r in ev.reasons]
        self.assertIn("vram_sufficient", codes)
        self.assertNotIn("vram_insufficient", codes)
        self.assertNotIn("vram_unknown", codes)

    def test_min_context_window_insufficient_rejects(self):
        from core.capability_evaluator import evaluate_match
        from core.capability_manual import load_manual

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_entry(
                root, "alpha",
                extra_front_matter={"min_context_window": 100000},
            )
            manual = load_manual(root)
            entry = manual.find_by_id("alpha")
            ev = evaluate_match(
                _make_match(entry), manual=manual,
                hardware={"current_context_window": 32000},
            )
        self.assertEqual(ev.decision, "reject")
        codes = [r.code for r in ev.reasons]
        self.assertIn("context_window_insufficient", codes)

    def test_min_context_window_unknown_defers(self):
        from core.capability_evaluator import evaluate_match
        from core.capability_manual import load_manual

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_entry(
                root, "alpha",
                extra_front_matter={"min_context_window": 100000},
            )
            manual = load_manual(root)
            entry = manual.find_by_id("alpha")
            ev = evaluate_match(
                _make_match(entry), manual=manual,
                hardware={"current_context_window": None},
            )
        self.assertEqual(ev.decision, "defer")
        codes = [r.code for r in ev.reasons]
        self.assertIn("context_window_unknown", codes)


# ── hardware dict contract ────────────────────────────────────────


class TestHardwareDictContract(unittest.TestCase):
    """Documented contract: evaluator reads only vram_total_mb,
    vram_available_mb, current_context_window. Other keys ignored.
    Wrong-key dicts behave as if VRAM/ctx were absent."""

    def test_wrong_keys_treated_as_unknown(self):
        from core.capability_evaluator import evaluate_match
        from core.capability_manual import load_manual

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_entry(
                root, "alpha",
                extra_front_matter={"min_vram_mb": 16000},
            )
            manual = load_manual(root)
            entry = manual.find_by_id("alpha")
            # Caller passes wrong key — evaluator must treat as
            # vram_available_mb=None → defer, not crash.
            ev = evaluate_match(
                _make_match(entry), manual=manual,
                hardware={"vram": 24000},  # wrong key
            )
        self.assertEqual(ev.decision, "defer")
        codes = [r.code for r in ev.reasons]
        self.assertIn("vram_unknown", codes)


# ── evaluate_matches: summarize() called once ─────────────────────


class TestEvaluateMatchesResolvesHardwareOnce(unittest.TestCase):
    def test_summarize_called_at_most_once_for_many_matches(self):
        from core.capability_evaluator import evaluate_matches
        from core.capability_manual import load_manual

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            for cid in ("alpha", "beta", "gamma", "delta", "epsilon"):
                _write_entry(root, cid)
            manual = load_manual(root)
            matches = [
                _make_match(manual.find_by_id(cid))
                for cid in ("alpha", "beta", "gamma", "delta", "epsilon")
            ]
            with patch(
                "core.self_knowledge.summarize",
                return_value={"vram_available_mb": 4000},
            ) as mock_summary:
                results = evaluate_matches(matches, manual=manual)
        self.assertEqual(len(results), 5)
        self.assertEqual(
            mock_summary.call_count, 1,
            "summarize() must be resolved once for the whole batch",
        )

    def test_summarize_not_called_when_hardware_provided(self):
        from core.capability_evaluator import evaluate_matches
        from core.capability_manual import load_manual

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_entry(root, "alpha")
            manual = load_manual(root)
            matches = [_make_match(manual.find_by_id("alpha"))]
            with patch(
                "core.self_knowledge.summarize",
                return_value={"vram_available_mb": 4000},
            ) as mock_summary:
                evaluate_matches(matches, manual=manual,
                                 hardware={"vram_available_mb": 1})
        self.assertEqual(
            mock_summary.call_count, 0,
            "summarize() must not be called when caller supplies hardware",
        )


# ── consent-card-required is informational ────────────────────────


class TestConsentCardRequiredInfo(unittest.TestCase):
    def test_consent_card_required_is_info_not_blocker(self):
        from core.capability_evaluator import evaluate_match
        from core.capability_manual import load_manual

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_entry(
                root, "alpha",
                consent_card_required=True,
            )
            manual = load_manual(root)
            entry = manual.find_by_id("alpha")
            ev = evaluate_match(_make_match(entry), manual=manual,
                                hardware={})
        # Consent-card-required is something the proposal stage
        # handles. The evaluator only notes it.
        blocker_codes = [
            r.code for r in ev.reasons if r.severity == "blocker"
        ]
        self.assertNotIn("consent_card_required", blocker_codes)


# ── telemetry ──────────────────────────────────────────────────────


class TestTelemetry(unittest.TestCase):
    def test_telemetry_write_failure_does_not_break_evaluation(self):
        from core.capability_evaluator import evaluate_match
        from core.capability_manual import load_manual

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_entry(root, "alpha")
            manual = load_manual(root)
            entry = manual.find_by_id("alpha")
            with patch(
                "core.infra.capability_evaluator._append_telemetry",
                side_effect=RuntimeError("simulated"),
            ):
                ev = evaluate_match(_make_match(entry), manual=manual,
                                    hardware={})
        self.assertEqual(ev.capability_id, "alpha")

    def test_telemetry_payload_shape(self):
        from core.capability_evaluator import evaluate_match
        from core.capability_manual import load_manual

        captured = []

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_entry(root, "alpha")
            manual = load_manual(root)
            entry = manual.find_by_id("alpha")
            with patch(
                "core.infra.capability_evaluator._append_telemetry",
                side_effect=lambda payload: captured.append(payload),
            ):
                evaluate_match(_make_match(entry, score=0.42),
                               manual=manual, hardware={})
        self.assertEqual(len(captured), 1)
        for k in ("timestamp", "capability_id", "decision",
                  "blocker_codes", "warning_codes", "match_score"):
            self.assertIn(k, captured[0])
        self.assertEqual(captured[0]["capability_id"], "alpha")
        self.assertEqual(captured[0]["match_score"], 0.42)


# ── real manual smoke ─────────────────────────────────────────────


class TestRealManualSmoke(unittest.TestCase):
    """Real manual must evaluate without crashing. Behavior depends
    on current state (seed entries are aspirational with external
    prereqs) so we don't pin specific decisions, only non-crash."""

    def test_real_manual_evaluates_without_crash(self):
        from core.capability_evaluator import evaluate_matches
        from core.capability_gap_matcher import (
            clear_cache, match_gap,
        )

        clear_cache()
        matches = match_gap(
            "synthesize across many months of memory and audit codebase"
        )
        # Even if matches is empty, evaluate_matches([]) returns []
        evaluations = evaluate_matches(matches)
        self.assertIsInstance(evaluations, list)
        for ev in evaluations:
            self.assertIn(ev.decision, {"eligible", "defer", "reject"})


if __name__ == "__main__":
    unittest.main()
