import sqlite3
import tempfile
import unittest
from pathlib import Path


class CoverageReadOnlyTests(unittest.TestCase):
    def test_fabrication_missing_db_returns_no_data_and_creates_no_file(self):
        from core.learning import fabrication_memory as fm

        with tempfile.TemporaryDirectory() as td:
            missing = Path(td) / "nope.db"
            cov = fm._coverage_at(missing)
            self.assertEqual(cov["status"], "no_data")
            self.assertFalse(missing.exists())

    def test_fabrication_coverage_reports_retention_from_module_constant(self):
        from core.learning import fabrication_memory as fm

        self.assertIn(str(fm._FAB_RETENTION_DAYS), fm.coverage()["retention"])

    def test_ro_connect_cannot_write(self):
        from core.infra.ro_sqlite import _ro_connect

        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "x.db"
            con = sqlite3.connect(path)
            con.executescript("CREATE TABLE t(a); INSERT INTO t VALUES(1);")
            con.close()

            ro = _ro_connect(path)
            self.assertIsNotNone(ro)
            with self.assertRaises(sqlite3.OperationalError):
                ro.execute("INSERT INTO t VALUES(2)")
            ro.close()


class ConsequenceCoverageReadOnlyTests(unittest.TestCase):
    def _seeded_consequence_db(self) -> Path:
        from core.learning import consequence_memory as cm

        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        path = Path(td.name) / "consequence_memory.db"
        old = cm.DB_PATH
        try:
            cm.DB_PATH = path
            cm.record_event(
                kind=cm.CLASS_TOOL_FAILURE,
                context="tool failed",
                outcome="non-zero",
            )
            cm.record_event(
                kind=cm.CLASS_CARD_REJECTED,
                context="card rejected",
                outcome="owner rejected",
            )
        finally:
            cm.DB_PATH = old
        return path

    def test_coverage_missing_db_no_data_no_create(self):
        from core.learning import consequence_memory as cm

        with tempfile.TemporaryDirectory() as td:
            missing = Path(td) / "consequence_memory.db"
            cov = cm.coverage(_db_path=missing)
            self.assertEqual(cov["status"], "no_data")
            self.assertFalse(missing.exists())

    def test_coverage_counts_only_scar_classes(self):
        from core.learning import consequence_memory as cm

        cov = cm.coverage(_db_path=self._seeded_consequence_db())
        self.assertIn(cm.CLASS_CARD_REJECTED, cov["by_class"])
        self.assertNotIn(cm.CLASS_TOOL_FAILURE, cov["by_class"])


class VetoCoverageReadOnlyTests(unittest.TestCase):
    def test_coverage_missing_db_no_data_no_create(self):
        from core.routing import veto_ledger

        with tempfile.TemporaryDirectory() as td:
            missing = Path(td) / "veto_ledger.db"
            cov = veto_ledger.coverage(_db_path=missing)
            self.assertEqual(cov["status"], "no_data")
            self.assertFalse(missing.exists())

    def test_coverage_reports_likely_wrong_zero_explicitly(self):
        from core.routing import veto_ledger

        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "veto_ledger.db"
            ledger = veto_ledger.VetoLedger(db_path=path)
            ledger.record_veto(
                class_id="search",
                tool="web",
                prior_n=3,
                prior_success_rate=0.1,
                prior_confidence=0.4,
                turn_id="t1",
                surface="test",
                now=1000.0,
            )
            cov = veto_ledger.coverage(_db_path=path)
            self.assertEqual(cov["total_events"], 1)
            self.assertEqual(cov["likely_wrong"], 0)


class SidecarReadSurfaceTests(unittest.TestCase):
    def test_list_all_at_and_coverage_at_missing_no_create(self):
        from core.learning.scar_tissue import ScarSidecar

        with tempfile.TemporaryDirectory() as td:
            missing = Path(td) / "scar_tissue.db"
            self.assertEqual(ScarSidecar.list_all_at(missing), [])
            self.assertEqual(ScarSidecar.coverage_at(missing)["status"], "no_data")
            self.assertFalse(missing.exists())

    def test_list_all_at_enumerates_rows(self):
        from core.learning.scar_tissue import ScarSidecar

        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "scar_tissue.db"
            sidecar = ScarSidecar(path)
            sidecar.register(
                "k1",
                episode_id="ep-1",
                receipt_ref="fabrication:5",
                occurred_at="2026-07-03T00:00:00Z",
            )
            sidecar.register(
                "k2",
                episode_id="ep-2",
                receipt_ref="veto:9",
                occurred_at="2026-07-03T00:00:00Z",
            )

            rows = ScarSidecar.list_all_at(path)
            self.assertEqual({row["dedup_key"] for row in rows}, {"k1", "k2"})
            refs = [ref for row in rows for ref in row["receipt_refs"]]
            self.assertIn("fabrication:5", refs)
