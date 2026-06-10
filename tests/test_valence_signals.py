import unittest

from core.evolution.valence.signals import (
    AuditSignals,
    ContinuitySignals,
    WantSignals,
)


class Signals(unittest.TestCase):
    def test_defaults(self):
        self.assertFalse(AuditSignals().rail_fired)
        self.assertEqual(WantSignals().backlog, 0)
        self.assertFalse(WantSignals().backlog_grew)
        self.assertFalse(ContinuitySignals().capsule_expected)

    def test_frozen(self):
        with self.assertRaises(Exception):
            AuditSignals().rail_fired = True
