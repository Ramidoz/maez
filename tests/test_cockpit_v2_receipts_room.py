import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path


def _paths(root: Path):
    from core.cockpit.readers import CockpitSourcePaths

    return CockpitSourcePaths(memory_dir=root / "memory", logs_dir=root / "logs")


def _seed_fabrication_events(memory_dir: Path, *, count: int) -> None:
    db = memory_dir / "fabrication_log.db"
    db.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(db)) as con, con:
        con.execute(
            """
            CREATE TABLE fabrication_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts REAL NOT NULL,
                surface TEXT NOT NULL,
                text TEXT NOT NULL,
                signals_absent TEXT NOT NULL,
                signals_present TEXT NOT NULL DEFAULT '[]',
                reason TEXT NOT NULL,
                mode TEXT NOT NULL
            )
            """
        )
        for idx in range(count):
            con.execute(
                """
                INSERT INTO fabrication_events (
                    ts, surface, text, signals_absent, signals_present, reason, mode
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    1000.0 + idx,
                    "telegram",
                    f"unsupported claim {idx}",
                    "[]",
                    "[]",
                    "not grounded",
                    "judge",
                ),
            )


def _seed_claim_receipt_outcomes(memory_dir: Path) -> None:
    db = memory_dir / "consequence_memory.db"
    with closing(sqlite3.connect(db)) as con, con:
        con.execute(
            """
            CREATE TABLE events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts REAL NOT NULL,
                class TEXT NOT NULL,
                surface TEXT NOT NULL DEFAULT 'unknown',
                context TEXT NOT NULL DEFAULT '',
                outcome TEXT NOT NULL DEFAULT '',
                feedback TEXT NOT NULL DEFAULT '',
                tags TEXT NOT NULL DEFAULT '',
                extra_json TEXT NOT NULL DEFAULT '{}',
                heeded INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        for outcome in ("accepted", "floor"):
            con.execute(
                """
                INSERT INTO events (
                    ts, class, surface, context, outcome, feedback, tags, extra_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    1200.0,
                    "claim_receipt_redo",
                    "telegram",
                    f"action_type=web_search pattern_id=search_initiating outcome={outcome}",
                    outcome,
                    "claims a this-turn search/action with no type-matched receipt",
                    "scar,claim_receipt_redo",
                    "{}",
                ),
            )


def _seed_veto_with_explicit_zero(memory_dir: Path) -> None:
    from core.routing.veto_ledger import VetoLedger

    ledger = VetoLedger(db_path=memory_dir / "veto_ledger.db")
    ledger.record_veto(
        class_id="weather",
        tool="web_search",
        prior_n=1,
        prior_success_rate=0.0,
        prior_confidence=0.6,
        turn_id="turn-1",
        surface="telegram",
        now=1000.0,
    )


class CockpitV2ReceiptsRoomTests(unittest.TestCase):
    def test_receipts_room_preserves_zero_no_data_and_outcomes(self):
        from core.cockpit.receipts_room import build_receipts_room

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            memory = root / "memory"
            _seed_fabrication_events(memory, count=0)
            _seed_claim_receipt_outcomes(memory)
            _seed_veto_with_explicit_zero(memory)

            room = build_receipts_room(_paths(root))

        fabrication = room["fabrication_events"]
        self.assertEqual(fabrication["status"], "ok")
        self.assertEqual(fabrication["receipt_count"], 0)
        self.assertEqual(fabrication["empty_state"], "explicit_zero")
        self.assertEqual(fabrication["label"], "fabrication event receipts")

        veto = room["routing_veto"]
        self.assertEqual(veto["status"], "ok")
        self.assertEqual(veto["likely_wrong_count"], 0)
        self.assertEqual(veto["total_veto_events"], 1)
        self.assertEqual(veto["empty_state"], "explicit_zero")

        claim_receipt = room["claim_receipt_redo"]
        self.assertEqual(claim_receipt["status"], "ok")
        self.assertEqual(claim_receipt["outcomes"]["accepted"], 1)
        self.assertEqual(claim_receipt["outcomes"]["floor"], 1)
        self.assertEqual(claim_receipt["outcome_labels"]["accepted"], "corrected_before_send")
        self.assertEqual(claim_receipt["outcome_labels"]["floor"], "held_with_floor_notice")

        missing = room["logs"]["maez"]
        self.assertEqual(missing["status"], "no_data")
        self.assertFalse((root / "logs").exists())

    def test_receipts_room_payload_and_dom_are_receipts_not_confessions(self):
        from core.cockpit.receipts_room import (
            build_receipts_room,
            render_receipts_room_dom_text,
        )

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            memory = root / "memory"
            _seed_fabrication_events(memory, count=2)
            room = build_receipts_room(_paths(root))

        payload = json.dumps(room, sort_keys=True).lower()
        dom_text = render_receipts_room_dom_text(room).lower()
        for text in (payload, dom_text):
            self.assertIn("fabrication event receipts", text)
            self.assertIn("third-person", text)
            self.assertNotIn("i fabricated", text)
            self.assertNotIn("i have fabricated", text)
            self.assertNotIn("my fabrication", text)
            self.assertNotIn("confession", text)
            self.assertNotIn("integrity score", text)

    def test_receipts_room_missing_sources_create_no_files(self):
        from core.cockpit.receipts_room import build_receipts_room

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            room = build_receipts_room(_paths(root))
            created = sorted(p.relative_to(root).as_posix() for p in root.rglob("*"))

        self.assertEqual(created, [])
        self.assertEqual(room["fabrication_events"]["status"], "no_data")
        self.assertEqual(room["fabrication_events"]["empty_state"], "no_data")
        self.assertEqual(room["claim_receipt_redo"]["status"], "no_data")
        self.assertEqual(room["logs"]["maez"]["status"], "no_data")

    def test_receipts_room_ui_uses_narrow_endpoint_and_receipt_language(self):
        index = Path("web/cockpit/v2/index.html").read_text()
        sim = Path("web/cockpit/v2/sim.jsx").read_text()
        ui = Path("web/cockpit/v2/terminal-ui.jsx").read_text()
        combined = "\n".join((index, sim, ui)).lower()

        self.assertIn("id: 'receipts'", index)
        self.assertIn("surface === 'receipts'", index)
        self.assertIn("/api/v2/cockpit/receipts-room", sim)
        self.assertIn("function receiptssurface", ui.lower())
        self.assertIn("fabrication event receipts", ui)
        self.assertIn("corrected_before_send", ui)
        self.assertIn("held_with_floor_notice", ui)
        for forbidden in (
            "i fabricated",
            "i have fabricated",
            "my fabrication",
            "confession",
            "integrity score",
        ):
            self.assertNotIn(forbidden, combined)


if __name__ == "__main__":
    unittest.main()
