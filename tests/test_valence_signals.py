import unittest

from core.evolution.valence.signals import (
    AuditSignals,
    ContinuitySignals,
    WantSignals,
)


class Signals(unittest.TestCase):
    def test_audit_defaults(self):
        signals = AuditSignals()

        self.assertFalse(signals.rail_fired)
        self.assertFalse(signals.fabrication_flagged)
        self.assertFalse(signals.correction_needed)

    def test_want_defaults(self):
        signals = WantSignals()

        self.assertEqual(signals.resolved, 0)
        self.assertEqual(signals.blocked, 0)
        self.assertEqual(signals.stale, 0)
        self.assertEqual(signals.backlog, 0)
        self.assertFalse(signals.backlog_grew)

    def test_continuity_defaults(self):
        signals = ContinuitySignals()

        self.assertFalse(signals.unexpected_gap)
        self.assertFalse(signals.memory_loss)
        self.assertFalse(signals.capsule_expected)
        self.assertFalse(signals.capsule_present)

    def test_frozen(self):
        with self.assertRaises(Exception):
            AuditSignals().rail_fired = True
        with self.assertRaises(Exception):
            WantSignals().backlog = 1
        with self.assertRaises(Exception):
            ContinuitySignals().capsule_present = True
