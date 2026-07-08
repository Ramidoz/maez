from __future__ import annotations

import sqlite3
import tempfile
import unittest
from contextlib import closing
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest import mock


class InnerContinuityFactTests(unittest.TestCase):
    def _paths(self, tmp: str) -> tuple[Path, Path]:
        root = Path(tmp)
        return (
            root / "dreams.db",
            root / "wonderings.db",
        )

    def _init_stores(self, tmp: str):
        from core.evolution.dream_state import DreamState
        from core.evolution.wonderings import Wonderings

        dream_db, wondering_db = self._paths(tmp)
        dreams = DreamState(None, None, None, db_path=str(dream_db))
        wonderings = Wonderings(db_path=wondering_db)
        return dream_db, wondering_db, dreams, wonderings

    def _seed_dreams(self, db_path: Path, now: datetime) -> None:
        with closing(sqlite3.connect(db_path)) as conn:
            conn.execute(
                "INSERT INTO dream_proposals "
                "(id, created_at, insight, status, proposal_type) "
                "VALUES (?, ?, ?, ?, ?)",
                (65, (now - timedelta(hours=8)).timestamp(), "hidden dream alpha", "pending", "append"),
            )
            conn.execute(
                "INSERT INTO dream_proposals "
                "(id, created_at, insight, status, proposal_type) "
                "VALUES (?, ?, ?, ?, ?)",
                (66, (now - timedelta(hours=2)).timestamp(), "hidden dream beta", "pending", "append"),
            )
            conn.execute(
                "INSERT INTO dream_proposals "
                "(id, created_at, insight, status, proposal_type) "
                "VALUES (?, ?, ?, ?, ?)",
                (67, (now - timedelta(hours=20)).timestamp(), "applied hidden", "applied", "append"),
            )
            conn.execute(
                "INSERT INTO dream_proposals "
                "(id, created_at, insight, status, proposal_type) "
                "VALUES (?, ?, ?, ?, ?)",
                (68, (now - timedelta(hours=30)).timestamp(), "rejected hidden", "rejected", "append"),
            )
            conn.commit()

    def _seed_wonderings(self, db_path: Path, now: datetime) -> None:
        with closing(sqlite3.connect(db_path)) as conn:
            conn.execute(
                "INSERT INTO wonderings (id, created_at, question, status, source) "
                "VALUES (?, ?, ?, ?, ?)",
                (10, (now - timedelta(hours=5)).timestamp(), "hidden question one", "open", "manual"),
            )
            conn.execute(
                "INSERT INTO wonderings (id, created_at, question, status, source) "
                "VALUES (?, ?, ?, ?, ?)",
                (11, (now - timedelta(hours=1)).timestamp(), "hidden question two", "active", "manual"),
            )
            conn.execute(
                "INSERT INTO wonderings (id, created_at, question, status, source) "
                "VALUES (?, ?, ?, ?, ?)",
                (12, (now - timedelta(hours=9)).timestamp(), "resolved hidden", "resolved", "manual"),
            )
            conn.commit()

    def test_block_renders_only_fact_metadata_from_tmp_stores(self):
        from core.routing.inner_continuity_facts import build_inner_continuity_facts

        now = datetime(2026, 7, 8, 18, 0, tzinfo=UTC)
        with tempfile.TemporaryDirectory() as tmp:
            dream_db, wondering_db, _dreams, _wonderings = self._init_stores(tmp)
            self._seed_dreams(dream_db, now)
            self._seed_wonderings(wondering_db, now)

            block = build_inner_continuity_facts(
                dream_db_path=dream_db,
                wonderings_db_path=wondering_db,
                now=now,
            )

        self.assertIn("INNER CONTINUITY FACTS", block)
        self.assertIn("dream proposals: 2 pending", block)
        self.assertIn("#65 age 8h", block)
        self.assertIn("#66 age 2h", block)
        self.assertIn("oldest 8h", block)
        self.assertIn("open wonderings: 2", block)
        self.assertIn("oldest 5h", block)
        self.assertNotIn("owner exchange", block)
        self.assertNotIn("hidden dream", block)
        self.assertNotIn("hidden question", block)
        self.assertNotIn("#67", block)
        self.assertNotIn("#68", block)

    def test_flag_off_returns_absent_block(self):
        from core.routing.inner_continuity_facts import inner_continuity_prompt_block

        with tempfile.TemporaryDirectory() as tmp:
            dream_db, wondering_db, _dreams, _wonderings = self._init_stores(tmp)
            with mock.patch.dict("os.environ", {}, clear=True), self.subTest("unset"):
                self.assertEqual(
                    "",
                    inner_continuity_prompt_block(
                        dream_db_path=dream_db,
                        wonderings_db_path=wondering_db,
                    ),
                )

    def test_quarantined_wonderings_are_not_counted_or_identified(self):
        from core.routing.inner_continuity_facts import build_inner_continuity_facts

        now = datetime(2026, 7, 8, 18, 0, tzinfo=UTC)
        with tempfile.TemporaryDirectory() as tmp:
            dream_db, wondering_db, _dreams, _wonderings = self._init_stores(tmp)
            with closing(sqlite3.connect(wondering_db)) as conn:
                conn.execute(
                    "INSERT INTO wonderings (id, created_at, question, status, source) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (20, (now - timedelta(hours=12)).timestamp(), "quarantined hidden", "open", "digestion"),
                )
                conn.execute(
                    "INSERT INTO wonderings (id, created_at, question, status, source) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (21, (now - timedelta(hours=3)).timestamp(), "visible hidden", "open", "manual"),
                )
                conn.commit()

            block = build_inner_continuity_facts(
                dream_db_path=dream_db,
                wonderings_db_path=wondering_db,
                now=now,
            )

        self.assertIn("open wonderings: 1", block)
        self.assertIn("oldest 3h", block)
        self.assertNotIn("12h", block)
        self.assertNotIn("#20", block)
        self.assertNotIn("digestion", block)
        self.assertNotIn("quarantined hidden", block)

    def test_empty_stores_return_absent_block(self):
        from core.routing.inner_continuity_facts import build_inner_continuity_facts

        with tempfile.TemporaryDirectory() as tmp:
            dream_db, wondering_db, _dreams, _wonderings = self._init_stores(tmp)

            block = build_inner_continuity_facts(
                dream_db_path=dream_db,
                wonderings_db_path=wondering_db,
                now=datetime(2026, 7, 8, 18, 0, tzinfo=UTC),
            )

        self.assertEqual("", block)

    def test_domain_swap_keeps_same_render_for_same_store_metadata(self):
        from core.routing.inner_continuity_facts import build_inner_continuity_facts

        now = datetime(2026, 7, 8, 18, 0, tzinfo=UTC)
        rendered: list[str] = []
        for dream_text, question_text in (
            ("hidden dream about disks", "hidden question about logs"),
            ("hidden dream about music", "hidden question about color"),
        ):
            with tempfile.TemporaryDirectory() as tmp:
                dream_db, wondering_db, _dreams, _wonderings = self._init_stores(tmp)
                with closing(sqlite3.connect(dream_db)) as conn:
                    conn.execute(
                        "INSERT INTO dream_proposals "
                        "(id, created_at, insight, status, proposal_type) "
                        "VALUES (?, ?, ?, ?, ?)",
                        (65, (now - timedelta(hours=8)).timestamp(), dream_text, "pending", "append"),
                    )
                    conn.commit()
                with closing(sqlite3.connect(wondering_db)) as conn:
                    conn.execute(
                        "INSERT INTO wonderings (id, created_at, question, status, source) "
                        "VALUES (?, ?, ?, ?, ?)",
                        (10, (now - timedelta(hours=5)).timestamp(), question_text, "open", "manual"),
                    )
                    conn.commit()
                rendered.append(
                    build_inner_continuity_facts(
                        dream_db_path=dream_db,
                        wonderings_db_path=wondering_db,
                        now=now,
                    )
                )

        self.assertEqual(rendered[0], rendered[1])

    def test_module_has_no_a7_store_references(self):
        source = Path("core/routing/inner_continuity_facts.py").read_text(encoding="utf-8")
        forbidden = "private" + "_" + "thoughts"

        self.assertNotIn(forbidden, source.lower())


if __name__ == "__main__":
    unittest.main()
