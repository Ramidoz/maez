import json
import tempfile
import unittest
from pathlib import Path


def _tmp_sources(root: str | Path) -> dict:
    root = Path(root)
    return {
        "fabrication_db": root / "fabrication_log.db",
        "veto_db": root / "veto_ledger.db",
        "consequence_db": root / "consequence_memory.db",
        "scar_sidecar_db": root / "scar_tissue.db",
    }


def _seed_veto_rows(path: Path, *, likely_wrong: int = 0, total: int = 3) -> None:
    from core.routing.veto_ledger import VetoLedger

    ledger = VetoLedger(db_path=path)
    for idx in range(total):
        event_id = ledger.record_veto(
            class_id=f"class-{idx}",
            tool="web",
            prior_n=3,
            prior_success_rate=0.1,
            prior_confidence=0.4,
            turn_id=f"turn-{idx}",
            surface="test",
            now=1000.0 + idx,
        )
        if idx < likely_wrong:
            ledger.attach_reask_outcome(
                event_id,
                reask_turn_id=f"reask-{idx}",
                reask_outcome_quality="structured_evidence",
            )


def _seed_fabrication_row(path: Path, *, row_id: int | None = None) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    import sqlite3

    con = sqlite3.connect(path)
    try:
        con.executescript(
            """
            CREATE TABLE IF NOT EXISTS fabrication_events (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                ts              REAL NOT NULL,
                surface         TEXT NOT NULL,
                text            TEXT NOT NULL,
                signals_absent  TEXT NOT NULL,
                reason          TEXT NOT NULL,
                mode            TEXT NOT NULL,
                signals_present TEXT NOT NULL DEFAULT '[]'
            );
            """
        )
        if row_id is None:
            cur = con.execute(
                "INSERT INTO fabrication_events "
                "(ts, surface, text, signals_absent, reason, mode, signals_present) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (1000.0, "test", "fabricated", "[]", "reason", "shadow", "[]"),
            )
        else:
            cur = con.execute(
                "INSERT INTO fabrication_events "
                "(id, ts, surface, text, signals_absent, reason, mode, signals_present) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (row_id, 1000.0, "test", "fabricated", "[]", "reason", "shadow", "[]"),
            )
        con.commit()
        return int(row_id if row_id is not None else cur.lastrowid)
    finally:
        con.close()


def _seed_consequence_row(path: Path, *, kind: str) -> int:
    from core.learning import consequence_memory as cm

    old = cm.DB_PATH
    try:
        cm.DB_PATH = path
        row_id = cm.record_event(
            kind=kind,
            context=f"{kind} context",
            outcome=f"{kind} outcome",
            surface="test",
        )
    finally:
        cm.DB_PATH = old
    assert row_id is not None
    return int(row_id)


class DigestSourcesTests(unittest.TestCase):
    def _digest(self, **overrides):
        from core.learning import self_evidence

        return self_evidence.self_evidence_digest(**overrides)

    def test_missing_source_renders_no_data_not_omitted(self):
        with tempfile.TemporaryDirectory() as td:
            digest = self._digest(_sources=_tmp_sources(td))
        for key in (
            "fabrication_events",
            "veto_proven_wrong",
            "consequence_scar_classes",
            "scar_sidecar",
        ):
            self.assertIn(key, digest["sources"])
            self.assertEqual(digest["sources"][key]["status"], "no_data")

    def test_explicit_zero_for_veto_with_no_likely_wrong(self):
        with tempfile.TemporaryDirectory() as td:
            sources = _tmp_sources(td)
            _seed_veto_rows(sources["veto_db"], likely_wrong=0, total=3)
            digest = self._digest(_sources=sources)

        veto = digest["sources"]["veto_proven_wrong"]
        self.assertEqual(veto["status"], "ok")
        self.assertEqual(veto["count"], 0)
        self.assertEqual(veto["total_veto_events"], 3)

    def test_no_score_key_anywhere(self):
        with tempfile.TemporaryDirectory() as td:
            blob = json.dumps(self._digest(_sources=_tmp_sources(td))).lower()
        for banned in ('"score"', '"grade"', '"rating"'):
            self.assertNotIn(banned, blob)

    def test_redo_is_combined_with_unstructured_detail(self):
        from core.learning import consequence_memory as cm

        with tempfile.TemporaryDirectory() as td:
            sources = _tmp_sources(td)
            _seed_consequence_row(
                sources["consequence_db"],
                kind=cm.CLASS_CLAIM_RECEIPT_REDO,
            )
            digest = self._digest(_sources=sources)

        consequence = digest["sources"]["consequence_scar_classes"]
        self.assertEqual(
            consequence["outcome_detail"]["claim_receipt_redo"],
            "unstructured",
        )
        self.assertEqual(
            consequence["by_class"][cm.CLASS_CLAIM_RECEIPT_REDO],
            1,
        )

    def test_coverage_note_present_no_global_alltime(self):
        with tempfile.TemporaryDirectory() as td:
            digest = self._digest(_sources=_tmp_sources(td))

        self.assertEqual(digest["kind"], "self_evidence_integrity_ledger")
        self.assertIn("per-source", digest["coverage_note"])
        self.assertIn("no single all-time", digest["coverage_note"])


class MergedDedupTests(unittest.TestCase):
    def test_scarred_fabrication_row_counts_once(self):
        from core.learning import consequence_memory as cm
        from core.learning import self_evidence
        from core.learning.scar_tissue import ScarSidecar

        with tempfile.TemporaryDirectory() as td:
            sources = _tmp_sources(td)
            fab_id = _seed_fabrication_row(sources["fabrication_db"], row_id=5)
            consequence_id = _seed_consequence_row(
                sources["consequence_db"],
                kind=cm.CLASS_FABRICATION_CATCH,
            )
            sidecar = ScarSidecar(sources["scar_sidecar_db"])
            sidecar.register(
                "fabrication:token",
                episode_id="ep-1",
                receipt_ref=f"fabrication:{fab_id}",
                occurred_at="2026-07-03T00:00:00Z",
            )
            sidecar.merge_evidence(
                "fabrication:token",
                receipt_refs=[f"consequence:{consequence_id}"],
                occurred_at="2026-07-03T00:00:00Z",
                count_occurrence=False,
            )

            digest = self_evidence.self_evidence_digest(_sources=sources)

        merged = digest["merged_events"]
        self.assertEqual(merged["overlap_unified"], 2)
        self.assertEqual(merged["distinct_integrity_events"], 1)

    def test_unscarred_raw_fabrication_row_is_counted(self):
        from core.learning import self_evidence

        with tempfile.TemporaryDirectory() as td:
            sources = _tmp_sources(td)
            _seed_fabrication_row(sources["fabrication_db"])

            digest = self_evidence.self_evidence_digest(_sources=sources)

        merged = digest["merged_events"]
        self.assertEqual(merged["overlap_unified"], 0)
        self.assertEqual(merged["distinct_integrity_events"], 1)


class ReadOnlyFilesystemProofTests(unittest.TestCase):
    def test_missing_sources_leave_directory_empty(self):
        from core.learning import self_evidence

        with tempfile.TemporaryDirectory() as td:
            self_evidence.self_evidence_digest(_sources=_tmp_sources(td))
            self.assertEqual(list(Path(td).iterdir()), [])

    def test_seeded_sources_are_not_modified_by_digest(self):
        from core.learning import consequence_memory as cm
        from core.learning import self_evidence
        from core.learning.scar_tissue import ScarSidecar

        with tempfile.TemporaryDirectory() as td:
            sources = _tmp_sources(td)
            _seed_fabrication_row(sources["fabrication_db"])
            _seed_veto_rows(sources["veto_db"], likely_wrong=1, total=2)
            consequence_id = _seed_consequence_row(
                sources["consequence_db"],
                kind=cm.CLASS_CARD_REJECTED,
            )
            sidecar = ScarSidecar(sources["scar_sidecar_db"])
            sidecar.register(
                "card:abc",
                episode_id="ep-card",
                receipt_ref=f"consequence:{consequence_id}",
                occurred_at="2026-07-03T00:00:00Z",
            )
            before = {
                key: (path.stat().st_size, path.stat().st_mtime_ns)
                for key, path in sources.items()
            }

            self_evidence.self_evidence_digest(_sources=sources)

            after = {
                key: (path.stat().st_size, path.stat().st_mtime_ns)
                for key, path in sources.items()
            }
        self.assertEqual(after, before)
