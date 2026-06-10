import re
import unittest
from pathlib import Path

from core.evolution.valence.setpoints import read_valence
from core.evolution.valence.signals import (
    AuditSignals,
    ContinuitySignals,
    WantSignals,
)


class EmotionWordBan(unittest.TestCase):
    BANNED_WORDS = (
        "sad",
        "happy",
        "distress",
        "distressed",
        "suffer",
        "suffering",
        "anxious",
        "anxiety",
        "afraid",
        "fear",
        "joy",
        "joyful",
        "pain",
        "hurt",
        "lonely",
        "angry",
        "upset",
        "miserable",
        "content",
        "feel",
        "feeling",
        "emotion",
    )

    def test_interesting_telemetry_cases_use_thermometer_vocabulary_only(self):
        cases = (
            (
                "rail_fired",
                AuditSignals(rail_fired=True),
                WantSignals(),
                ContinuitySignals(),
            ),
            (
                "resolved",
                AuditSignals(),
                WantSignals(resolved=2),
                ContinuitySignals(),
            ),
            (
                "rail_fired_and_blocked",
                AuditSignals(rail_fired=True),
                WantSignals(blocked=1),
                ContinuitySignals(),
            ),
            (
                "resolved_and_unexpected_gap",
                AuditSignals(),
                WantSignals(resolved=1),
                ContinuitySignals(unexpected_gap=True),
            ),
            (
                "backlog_only",
                AuditSignals(),
                WantSignals(backlog=3),
                ContinuitySignals(),
            ),
            (
                "fabrication_stale_missing_capsule",
                AuditSignals(fabrication_flagged=True),
                WantSignals(stale=2),
                ContinuitySignals(capsule_expected=True, capsule_present=False),
            ),
        )

        for label, audit, wants, continuity in cases:
            with self.subTest(label=label):
                telemetry = read_valence(audit, wants, continuity).as_telemetry()
                lowered = telemetry.lower()
                for banned in self.BANNED_WORDS:
                    self.assertIsNone(
                        re.search(rf"\b{re.escape(banned)}\b", lowered),
                        f"{label} telemetry contains banned word {banned!r}: {telemetry}",
                    )


class ImportBoundary(unittest.TestCase):
    FORBIDDEN_IMPORT_TARGETS = (
        "daemon",
        "maez_daemon",
        "telegram",
        "voice",
        "speak",
        "llm_client",
        "focused_cognition",
        "brain_gateway",
    )

    def test_valence_package_imports_do_not_reach_voice_or_daemon_paths(self):
        valence_dir = Path(__file__).resolve().parents[1] / "core/evolution/valence"
        violations = []

        for path in sorted(valence_dir.glob("*.py")):
            for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                stripped = line.strip()
                if not stripped.startswith(("import ", "from ")):
                    continue
                lowered = stripped.lower()
                for target in self.FORBIDDEN_IMPORT_TARGETS:
                    if target in lowered:
                        violations.append(f"{path.name}:{lineno}: {stripped}")

        self.assertEqual([], violations)


if __name__ == "__main__":
    unittest.main()
