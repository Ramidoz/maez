import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from core.infra.private_thoughts import (
    AllowedFlow,
    ConsentTier,
    PrivateThoughts,
    ProducerId,
    RetentionRule,
    SignalKind,
)
from core.memory import birth_phase


class WriterStampsCurrentPhase(unittest.TestCase):
    def _store(self, td: str) -> PrivateThoughts:
        return PrivateThoughts(db_path=str(Path(td) / "pt.db"))

    def test_prebirth_write_stamps_gestation(self):
        with TemporaryDirectory() as td:
            store = self._store(td)
            with mock.patch.object(birth_phase, "is_born", return_value=False):
                tid = store.record_thought(content="x", provenance="explicit_api")
            row = store.get_thought(tid)
            self.assertEqual(row["memory_phase"], "gestation")

    def test_postbirth_write_stamps_lived(self):
        with TemporaryDirectory() as td:
            store = self._store(td)
            with mock.patch.object(birth_phase, "is_born", return_value=True):
                tid = store.record_thought(content="x", provenance="explicit_api")
            row = store.get_thought(tid)
            self.assertEqual(row["memory_phase"], "lived")

    def test_explicit_phase_still_wins(self):
        with TemporaryDirectory() as td:
            store = self._store(td)
            with mock.patch.object(birth_phase, "is_born", return_value=True):
                tid = store.record_thought(
                    content="x",
                    provenance="explicit_api",
                    memory_phase="gestation",
                )
            self.assertEqual(store.get_thought(tid)["memory_phase"], "gestation")

    def test_recent_by_source_none_phase_spans_eras(self):
        with TemporaryDirectory() as td:
            store = self._store(td)
            common = dict(
                content="x",
                source="self_card:v1",
                subject="maez_internal_state",
                signal_kind=SignalKind.SELF_WONDERING,
                producer_id=ProducerId.SELF_WONDERING,
                consent_tier=ConsentTier.OWNER_PRIVATE,
                retention=RetentionRule.UNTIL_REVIEWED,
                allowed_flows=(AllowedFlow.PRIVATE_READER,),
                context_extra={},
            )
            store.record_signal(memory_phase="gestation", **common)
            store.record_signal(memory_phase="lived", **common)
            rows = store.recent_by_source("self_card:v1", limit=10, phase=None)
            phases = sorted(r["memory_phase"] for r in rows)
            self.assertEqual(phases, ["gestation", "lived"])


if __name__ == "__main__":
    unittest.main()
