# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""The stamp gate every census consumer calls (S1 protocol §4).

One helper, so sixteen call sites cannot drift apart. The contract:

    dormant  -> return the legacy phase, unchanged, always
    enabled  -> 'gestation'/'lived' pass through; 'unknown' REFUSES
    caller-supplied phase is REVALIDATED: a caller may narrow, never
    assert 'lived' while the gate says otherwise

The refusal is the whole point. §4: "silent success, or a `gestation`
stamp, is a kill." A consumer that swallows the refusal and writes
'gestation' anyway reproduces the A6 defect this slice exists to close.
"""
from __future__ import annotations

import os
import shutil
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from core.memory.birth_phase import (  # noqa: E402
    PhaseUnknownRefusal, phase_for_stamp,
)

MIGRATIONS = REPO / "core" / "ledger" / "migrations"


class _Fixtures:
    """Healthy (gestation) and partial (unknown when enabled)."""

    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="stampgate_"))
        from core.ledger.migrate import run
        self.healthy = self.root / "healthy.db"
        run(str(self.healthy))
        self.partial = self.root / "partial.db"
        conn = sqlite3.connect(self.partial)
        for name in ("0001_init.sql", "0002_triggers.sql"):
            conn.executescript((MIGRATIONS / name).read_text())
        conn.commit(); conn.close()
        self._prior = os.environ.get("MAEZ_S1_PHASE_TRUTH")

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)
        if self._prior is None:
            os.environ.pop("MAEZ_S1_PHASE_TRUTH", None)
        else:
            os.environ["MAEZ_S1_PHASE_TRUTH"] = self._prior

    def enable(self):
        os.environ["MAEZ_S1_PHASE_TRUTH"] = "1"

    def disable(self):
        os.environ.pop("MAEZ_S1_PHASE_TRUTH", None)


class Dormant(_Fixtures, unittest.TestCase):
    """Flags off, the gate must be invisible. T5's baseline depends on it."""

    def test_dormant_returns_gestation_on_a_healthy_ledger(self):
        self.disable()
        self.assertEqual(phase_for_stamp(db_path=self.healthy), "gestation")

    def test_dormant_returns_gestation_even_on_a_broken_ledger(self):
        """The legacy answer, preserved exactly — including its defect."""
        self.disable()
        self.assertEqual(phase_for_stamp(db_path=self.partial), "gestation")

    def test_dormant_never_raises(self):
        self.disable()
        for db in (self.healthy, self.partial, self.root / "nope.db"):
            phase_for_stamp(db_path=db)   # must not raise


class Enabled(_Fixtures, unittest.TestCase):

    def test_healthy_ledger_still_stamps_gestation(self):
        self.enable()
        self.assertEqual(phase_for_stamp(db_path=self.healthy), "gestation")

    def test_broken_ledger_refuses(self):
        self.enable()
        with self.assertRaises(PhaseUnknownRefusal) as ctx:
            phase_for_stamp(db_path=self.partial)
        self.assertIn("structural", str(ctx.exception),
                      "the refusal must carry the reason, or a report cannot "
                      "say WHY the stamp was refused")

    def test_refusal_names_the_consumer(self):
        self.enable()
        with self.assertRaises(PhaseUnknownRefusal) as ctx:
            phase_for_stamp(db_path=self.partial, consumer="memory_manager.store")
        self.assertIn("memory_manager.store", str(ctx.exception))


class CallerSuppliedRevalidation(_Fixtures, unittest.TestCase):
    """§4: a caller may narrow, never assert 'lived' against the gate."""

    def test_caller_may_pass_the_phase_the_gate_agrees_with(self):
        self.enable()
        self.assertEqual(
            phase_for_stamp(db_path=self.healthy, supplied="gestation"),
            "gestation")

    def test_caller_cannot_assert_lived_while_the_gate_says_gestation(self):
        self.enable()
        with self.assertRaises(ValueError):
            phase_for_stamp(db_path=self.healthy, supplied="lived")

    def test_caller_cannot_assert_anything_while_the_gate_is_unknown(self):
        self.enable()
        with self.assertRaises((PhaseUnknownRefusal, ValueError)):
            phase_for_stamp(db_path=self.partial, supplied="gestation")

    def test_an_unknown_phase_string_is_rejected(self):
        self.enable()
        with self.assertRaises(ValueError):
            phase_for_stamp(db_path=self.healthy, supplied="banana")

    def test_dormant_still_honours_a_supplied_phase(self):
        """Dormant must not change existing caller-supplied behaviour."""
        self.disable()
        self.assertEqual(
            phase_for_stamp(db_path=self.healthy, supplied="lived"), "lived")


if __name__ == "__main__":
    unittest.main()
