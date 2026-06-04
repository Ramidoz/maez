from __future__ import annotations

import sys
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))


PRODUCTION_ROOTS = ("core", "daemon", "memory", "skills")


def _production_py_files() -> list[Path]:
    files: list[Path] = []
    for root in PRODUCTION_ROOTS:
        files.extend((_REPO / root).rglob("*.py"))
    return [
        path for path in files
        if "__pycache__" not in path.parts and path.name != "__init__.py"
    ]


class OwnerAccountMemoryCloudSurfaceGuardTests(unittest.TestCase):
    def test_web_owner_bridge_uses_provenanced_recall_for_cloud(self):
        src = (_REPO / "skills" / "web_interface.py").read_text(encoding="utf-8")
        self.assertIn("owner_recalled = memory.recall_for_telegram(message)", src)
        self.assertIn("memory.format_for_prompt(", src)
        self.assertIn("memory.format_for_prompt_provenanced(", src)
        self.assertRegex(
            src,
            r"build_claude_router_cloud_payload\([\s\S]*owner_memory="
            r"owner_memory_cloud if owner_bridge else \"\"",
        )

    def test_no_recall_to_cloud_path_uses_raw_format_for_prompt_only(self):
        offenders: list[str] = []
        for path in _production_py_files():
            src = path.read_text(encoding="utf-8")
            if "call_claude(" not in src and "call_messages(" not in src:
                continue
            if "format_for_prompt(" not in src:
                continue
            if "format_for_prompt_provenanced(" in src:
                continue
            offenders.append(str(path.relative_to(_REPO)))

        self.assertEqual(
            offenders,
            [],
            "cloud-bound recalled memory must use format_for_prompt_provenanced: "
            + ", ".join(offenders),
        )

    def test_known_local_recall_surfaces_remain_enumerated(self):
        expected_local = {
            "daemon/maez_daemon.py",
            "skills/telegram_voice.py",
            "core/brain/brain_loop.py",
        }
        actual_local = set()
        for path in _production_py_files():
            src = path.read_text(encoding="utf-8")
            if "format_for_prompt(" in src and "call_claude(" not in src:
                rel = str(path.relative_to(_REPO))
                if rel in expected_local:
                    actual_local.add(rel)

        self.assertEqual(actual_local, expected_local)


if __name__ == "__main__":
    unittest.main()
