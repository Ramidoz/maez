from __future__ import annotations

import unittest
from pathlib import Path


class WorktreeAirlockImportTests(unittest.TestCase):
    def test_web_interface_does_not_inject_founder_checkout_into_sys_path(self):
        repo = Path(__file__).resolve().parent.parent
        source = repo / "skills" / "web_interface.py"

        self.assertNotIn(
            'sys.path.insert(0, "/home/rohit/maez")',
            source.read_text(encoding="utf-8"),
        )

    def test_skills_do_not_prepend_founder_checkout_to_sys_path(self):
        repo = Path(__file__).resolve().parent.parent
        offenders = []
        for source in (repo / "skills").glob("*.py"):
            text = source.read_text(encoding="utf-8")
            if 'sys.path.insert(0, str(Path("/home/rohit/maez")))' in text:
                offenders.append(source.relative_to(repo).as_posix())

        self.assertEqual([], offenders)

    def test_tests_do_not_prepend_founder_checkout_to_sys_path(self):
        repo = Path(__file__).resolve().parent.parent
        forbidden = (
            'sys.path.insert(0, "/home/rohit/maez")',
            "sys.path.insert(0, '/home/rohit/maez')",
        )
        offenders = []
        for source in (repo / "tests").glob("test_*.py"):
            if source == Path(__file__).resolve():
                continue
            text = source.read_text(encoding="utf-8")
            if any(pattern in text for pattern in forbidden):
                offenders.append(source.relative_to(repo).as_posix())

        self.assertEqual([], offenders)


if __name__ == "__main__":
    unittest.main()
