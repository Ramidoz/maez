from __future__ import annotations

import ast
import re
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INTERACTION_PACKAGE = ROOT / "core" / "interaction_preferences"
SCRIPT = ROOT / "scripts" / "interaction_preferences.py"
DAEMON = ROOT / "daemon" / "maez_daemon.py"
CASUAL_PRESENCE_FILES = [ROOT / "core" / "routing" / "recent_activity_status.py"]
AUTONOMY_FORBIDDEN = [
    r"core\.policies\.autonomy_preferences",
    r"\bAutonomyPreferences\b",
    r"\bautonomy_preferences_db\b",
]
POST_GENERATION_FORBIDDEN = [
    r"\bsuppress\w*\b",
    r"\bfilter_generated\b",
    r"\brewrite_reply\b",
    r"\bdelete_question\b",
    r"\bquestion_cap\b",
    r"\bpost_generation\b",
]
RECALL_FEED_FORBIDDEN = [
    r"\bEpisodeStore\b",
    r"\bRelationshipGraph\b",
    r"\bbuild_lived_recall_brief\b",
    r"core\.memory\.episode_builder",
    r"core\.memory\.episodes",
    r"core\.memory\.lived_recall",
    r"\bstore_telegram\b",
]


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _interaction_files() -> list[Path]:
    return sorted(INTERACTION_PACKAGE.glob("*.py")) + [SCRIPT]


def _daemon_handle_source(source: str | None = None) -> str:
    text = source if source is not None else _read(DAEMON)
    tree = ast.parse(text)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "handle_message":
            return ast.get_source_segment(text, node) or ""
    raise AssertionError("handle_message not found")


def _daemon_interaction_regions(source: str | None = None) -> str:
    handle = _daemon_handle_source(source)
    lines = handle.splitlines()
    regions: list[str] = []
    for idx, line in enumerate(lines):
        if "interaction_preferences" in line:
            start = max(0, idx - 8)
            end = min(len(lines), idx + 12)
            regions.extend(lines[start:end])
    return "\n".join(regions)


def _interaction_calls_after_send(source: str) -> list[int]:
    tree = ast.parse(textwrap.dedent(source))
    send_lines: list[int] = []
    interaction_lines: list[int] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = ""
        if isinstance(func, ast.Name):
            name = func.id
        elif isinstance(func, ast.Attribute):
            name = func.attr
        if name in {"_bot_send_message", "_ws_broadcast", "send_message"}:
            send_lines.append(node.lineno)
        if name in {
            "process_owner_turn_preference",
            "interaction_preferences_prompt_context",
        }:
            interaction_lines.append(node.lineno)
    if not send_lines:
        return []
    first_send = min(send_lines)
    return [line for line in interaction_lines if line > first_send]


def _forbidden_production_hits(patterns: list[str]) -> list[str]:
    sources = {
        str(path.relative_to(ROOT)): _read(path)
        for path in _interaction_files()
    }
    sources["daemon/maez_daemon.py interaction-region"] = (
        _daemon_interaction_regions()
    )
    return _forbidden_hits_in_sources(sources, patterns)


def _forbidden_hits_in_sources(
    sources: dict[str, str],
    patterns: list[str],
) -> list[str]:
    hits: list[str] = []
    for label, source in sources.items():
        for pattern in patterns:
            if re.search(pattern, source):
                hits.append(f"{label}:{pattern}")
    return hits


def _post_generation_hits_in_sources(sources: dict[str, str]) -> list[str]:
    return _forbidden_hits_in_sources(sources, POST_GENERATION_FORBIDDEN)


def _casual_presence_import_hits(sources: dict[str, str]) -> list[str]:
    return [
        label
        for label, source in sources.items()
        if "core.interaction_preferences" in source
    ]


def _recall_feed_hits_in_sources(sources: dict[str, str]) -> list[str]:
    return _forbidden_hits_in_sources(sources, RECALL_FEED_FORBIDDEN)


class InteractionPreferencesGuardTests(unittest.TestCase):
    def test_no_autonomy_preferences_store_or_policy_import(self):
        self.assertEqual(_forbidden_production_hits(AUTONOMY_FORBIDDEN), [])

    def test_autonomy_preferences_guard_trips_on_planted_sample(self):
        planted = "from core.policies.autonomy_preferences import AutonomyPreferences"

        self.assertEqual(
            _forbidden_hits_in_sources(
                {"core/interaction_preferences/planted.py": planted},
                AUTONOMY_FORBIDDEN,
            ),
            [
                "core/interaction_preferences/planted.py:core\\.policies\\.autonomy_preferences",
                "core/interaction_preferences/planted.py:\\bAutonomyPreferences\\b",
            ],
        )

    def test_no_post_generation_suppressor_or_rewriter_in_interaction_package(self):
        self.assertEqual(
            _post_generation_hits_in_sources(
                {
                    str(path.relative_to(ROOT)): _read(path)
                    for path in _interaction_files()
                }
            ),
            [],
        )

    def test_post_generation_guard_trips_on_planted_suppressor(self):
        planted = """
        def filter_generated(reply):
            return delete_question(reply)
        """

        self.assertEqual(
            _post_generation_hits_in_sources(
                {"core/interaction_preferences/planted.py": planted}
            ),
            [
                "core/interaction_preferences/planted.py:\\bfilter_generated\\b",
                "core/interaction_preferences/planted.py:\\bdelete_question\\b",
            ],
        )

    def test_daemon_interaction_calls_stay_before_consolidation_and_send(self):
        source = _daemon_handle_source()

        self.assertLess(
            source.index("process_owner_turn_preference"),
            source.index("_consolidate_system_messages"),
        )
        self.assertLess(
            source.index("interaction_preferences_prompt_context"),
            source.index("_consolidate_system_messages"),
        )
        self.assertEqual(_interaction_calls_after_send(source), [])

    def test_daemon_send_order_guard_trips_on_planted_sample(self):
        planted = """
        def handle_message():
            _bot_send_message("already sent")
            interaction_preferences_prompt_context()
        """

        self.assertEqual(_interaction_calls_after_send(planted), [4])

    def test_no_casual_presence_renderer_imports_interaction_preferences(self):
        self.assertEqual(
            _casual_presence_import_hits(
                {
                    str(path.relative_to(ROOT)): _read(path)
                    for path in CASUAL_PRESENCE_FILES
                }
            ),
            [],
        )

    def test_casual_presence_guard_trips_on_planted_import(self):
        planted = "from core.interaction_preferences.render import render_interaction_preferences"

        self.assertEqual(
            _casual_presence_import_hits(
                {"core/routing/recent_activity_status.py": planted}
            ),
            ["core/routing/recent_activity_status.py"],
        )

    def test_no_recall_or_episode_feed_from_interaction_preferences(self):
        self.assertEqual(
            _recall_feed_hits_in_sources(
                {
                    str(path.relative_to(ROOT)): _read(path)
                    for path in sorted(INTERACTION_PACKAGE.glob("*.py"))
                }
            ),
            [],
        )

    def test_recall_feed_guard_trips_on_planted_sample(self):
        planted = "from core.memory.episodes import EpisodeStore"

        self.assertEqual(
            _recall_feed_hits_in_sources(
                {"core/interaction_preferences/planted.py": planted}
            ),
            [
                "core/interaction_preferences/planted.py:\\bEpisodeStore\\b",
                "core/interaction_preferences/planted.py:core\\.memory\\.episodes",
            ],
        )

    def test_no_normalized_fact_field_in_v0_production_code(self):
        hits = []
        for path in _interaction_files():
            source = _read(path)
            if "normalized_fact" in source:
                hits.append(str(path.relative_to(ROOT)))
        self.assertEqual(hits, [])

    def test_missing_db_read_surfaces_do_not_create_files(self):
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "missing" / "interaction_preferences.db"
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "list",
                    "--db",
                    str(db),
                ],
                check=False,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse(db.exists())


if __name__ == "__main__":
    unittest.main()
