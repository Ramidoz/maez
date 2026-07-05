import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path


SECRET = "PRIVATE A7 THOUGHT BODY MUST NOT REACH JSON OR DOM"


def _runtime(root: Path):
    from core.cockpit.state import RuntimePaths

    return RuntimePaths(root / "memory", root / "logs", root / "config")


def _seed_private_thought(memory_dir: Path) -> None:
    db = memory_dir / "private_thoughts.db"
    db.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(db)) as con, con:
        con.execute(
            "CREATE TABLE private_thoughts "
            "(thought_id INTEGER PRIMARY KEY, content TEXT NOT NULL)"
        )
        con.execute("INSERT INTO private_thoughts (content) VALUES (?)", (SECRET,))


def _seed_narrative_links(memory_dir: Path) -> None:
    from core.memory.narrative import NarrativeStore

    store = NarrativeStore(memory_dir / "lived_episodes.db")
    store.upsert_link(
        link_type="strings",
        from_episode_id="ep-reflection",
        to_episode_id="ep-source",
        trust="derived",
        evidence_ids=["ep-source"],
        detector_version="test",
    )


def _seed_scar(memory_dir: Path) -> None:
    from core.learning.scar_tissue import ScarSidecar

    db = memory_dir / "scar_tissue.db"
    sidecar = ScarSidecar(db)
    sidecar.register(
        "scar:test",
        episode_id="ep-scar",
        receipt_ref="dream:42",
        occurred_at="2026-07-05T12:00:00Z",
    )
    sidecar.merge_evidence(
        "scar:test",
        receipt_refs=["consequence:7"],
        occurred_at="2026-07-05T12:00:00Z",
        count_occurrence=False,
    )

    episodes = memory_dir / "lived_episodes.db"
    episodes.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(episodes)) as con, con:
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS episodes (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                occurred_at TEXT,
                title TEXT NOT NULL,
                summary TEXT NOT NULL,
                participants_json TEXT NOT NULL,
                emotional_tone TEXT,
                importance INTEGER NOT NULL DEFAULT 3,
                open_loop TEXT,
                source_memory_ids_json TEXT NOT NULL,
                source_kind TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                authorship TEXT,
                memory_voice TEXT
            )
            """
        )
        con.execute(
            """
            INSERT INTO episodes (
                id, created_at, occurred_at, title, summary, participants_json,
                source_memory_ids_json, source_kind, status, importance,
                authorship, memory_voice
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "ep-scar",
                "2026-07-05T12:00:00Z",
                "2026-07-05T12:00:00Z",
                "Correction received: dream rejected",
                "Correction received (dream_rejected, dream, 2026-07-05T12:00:00Z). "
                'Context: dream proposal rejected. The correction: "episode fallback should not win". '
                "Receipts: dream:42, consequence:7.",
                json.dumps(["Maez"]),
                json.dumps(["dream:42", "consequence:7"]),
                "scar",
                "active",
                4,
                "scar_detector",
                "external_to_maez",
            ),
        )
    consequence = memory_dir / "consequence_memory.db"
    with closing(sqlite3.connect(consequence)) as con, con:
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
        con.execute(
            """
            INSERT INTO events (
                id, ts, class, surface, context, outcome, feedback, tags, extra_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                7,
                1.0,
                "dream_rejected",
                "dream",
                "dream proposal rejected",
                "too grand; keep it grounded",
                "too grand; keep it grounded",
                "scar,dream_rejected",
                "{}",
            ),
        )


def _seed_interaction_preferences(memory_dir: Path) -> None:
    from core.interaction_preferences.store import InteractionPreferencesStore

    store = InteractionPreferencesStore(memory_dir / "interaction_preferences.db")
    active = store.record_capture(
        preference_id="pref-active",
        preference_class="question_cadence",
        owner_statement="stop asking me so many questions",
        source_ref="telegram:111",
        surface="telegram",
        statement_sha256="sha-active",
        created_at="2026-07-05T12:00:00Z",
    )
    store.record_retraction(
        preference_id="pref-retract",
        preference_class="question_cadence",
        owner_statement="actually, ask away",
        source_ref="telegram:222",
        surface="telegram",
        statement_sha256="sha-retract",
        supersedes_preference_id=active.preference_id,
        retraction_reason="owner_unsaid",
        created_at="2026-07-05T12:01:00Z",
    )


class CockpitV2MemoryRoomTests(unittest.TestCase):
    def test_memory_room_payload_is_sealed_and_honest(self):
        from core.cockpit.state import build_state

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            memory = root / "memory"
            _seed_private_thought(memory)
            _seed_narrative_links(memory)
            _seed_scar(memory)
            _seed_interaction_preferences(memory)

            state = build_state(
                runtime=_runtime(root),
                command_runner=lambda _cmd: "0\n",
            )

        payload = json.dumps(state["memory_room"], sort_keys=True)
        self.assertNotIn(SECRET, payload)
        self.assertEqual(
            state["memory_room"]["a7_interiority"]["content_policy"],
            "sealed",
        )
        self.assertFalse(state["memory_room"]["a7_interiority"]["raw_text_included"])
        self.assertEqual(
            state["memory_room"]["a7_interiority"]["private_thought_count"],
            1,
        )

        narrative = state["memory_room"]["narrative"]
        self.assertEqual(narrative["links"]["strings"], 1)
        self.assertEqual(narrative["links"]["same_thread"], 0)
        self.assertEqual(narrative["same_thread_state"], "honest_empty")
        self.assertNotEqual(narrative["status"], "error")

        scars = state["memory_room"]["scars"]
        self.assertEqual(scars["active_episodes"], 1)
        self.assertEqual(
            scars["recent"][0]["correction_quote"],
            "too grand; keep it grounded",
        )
        self.assertEqual(
            scars["recent"][0]["receipt_refs"],
            ["dream:42", "consequence:7"],
        )

        prefs = state["memory_room"]["interaction_preferences"]
        self.assertEqual(prefs["active"], 0)
        self.assertEqual(prefs["retracted"], 2)
        self.assertIn("receipt_path", prefs)

        evidence = state["memory_room"]["self_evidence"]
        evidence_payload = json.dumps(evidence, sort_keys=True).lower()
        self.assertIn("merged_events", evidence)
        self.assertNotIn("score", evidence_payload)
        for token in ("i have", "i fabricated", "my integrity"):
            self.assertNotIn(token, evidence_payload)

        continuity = state["memory_room"]["continuity"]
        self.assertEqual(continuity["status"], "no_data")
        self.assertEqual(continuity["latest_verdict"], "insufficient_data")
        self.assertNotIn("continuity_survived", json.dumps(continuity))

    def test_memory_room_renderer_does_not_leak_private_text_to_dom(self):
        from core.cockpit.memory_room import render_memory_room_dom_text

        memory_room = {
            "a7_interiority": {
                "status": "ok",
                "private_thought_count": 1,
                "fresh_moment_receipt_count": 0,
                "raw_text_included": False,
                "content_policy": "sealed",
            },
            "narrative": {
                "status": "ok",
                "links": {"strings": 2, "same_thread": 0, "because_of": 0},
                "same_thread_state": "honest_empty",
            },
            "scars": {
                "status": "ok",
                "active_episodes": 1,
                "total_occurrences": 1,
                "recent": [
                    {
                        "episode_id": "ep-scar",
                        "scar_class": "dream_rejected",
                        "correction_quote": "too grand; keep it grounded",
                        "receipt_refs": ["dream:42"],
                    }
                ],
            },
            "self_evidence": {
                "status": "ok",
                "merged_events": {
                    "distinct_integrity_events": 4,
                    "by_class": {"scar": 4},
                },
                "label": "integrity receipt count",
            },
            "continuity": {"status": "no_data", "latest_verdict": "insufficient_data"},
            "interaction_preferences": {
                "active": 0,
                "retracted": 1,
                "receipt_path": "T2 receipt path",
            },
        }

        dom_text = render_memory_room_dom_text(memory_room)

        self.assertIn("A7 Interiority", dom_text)
        self.assertIn("content sealed", dom_text)
        self.assertIn("same_thread 0", dom_text)
        self.assertIn('The correction: "too grand; keep it grounded"', dom_text)
        self.assertIn("integrity receipt count", dom_text)
        self.assertNotIn(SECRET, dom_text)
        for forbidden in (
            "thought body",
            "representative sample",
            "private excerpt",
            "continuity_survived",
            "integrity score",
        ):
            self.assertNotIn(forbidden, dom_text.lower())

    def test_memory_room_component_does_not_read_a7_text_fields(self):
        source = Path("web/cockpit/v2/terminal-ui.jsx").read_text()

        self.assertIn("/api/v2/cockpit/memory-room", source)
        for suffix in ("text", "body", "excerpt", "sample", "summary", "content"):
            with self.subTest(suffix=suffix):
                self.assertNotRegex(
                    source,
                    rf"\ba7\.[A-Za-z0-9_]*{suffix}[A-Za-z0-9_]*",
                )


if __name__ == "__main__":
    unittest.main()
