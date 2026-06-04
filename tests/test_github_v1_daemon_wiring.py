from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))


def _read(path: str) -> str:
    return (_REPO / path).read_text(encoding="utf-8")


def _method_body(src: str, method_name: str) -> str:
    pattern = re.compile(rf"^    def {re.escape(method_name)}\(", re.MULTILINE)
    match = pattern.search(src)
    if match is None:
        raise AssertionError(f"method not found: {method_name}")
    start = match.start()
    next_method = re.search(r"^    def \w+\(", src[start + 1 :], re.MULTILINE)
    end = start + 1 + next_method.start() if next_method else len(src)
    return src[start:end]


class GithubV1DaemonWiringTests(unittest.TestCase):
    def test_v1_mode_initializes_github_store(self):
        src = _read("daemon/maez_daemon.py")
        init_body = _method_body(src, "__init__")

        self.assertIn("GithubStore(", init_body)
        self.assertIn("self._github_mode == GithubMode.V1", init_body)
        self.assertIn("github_store_schema_mismatch", init_body)
        self.assertIn("source_unavailable", init_body)
        self.assertIn("GITHUB_STORE_DB_PATH", src)

    def test_health_includes_content_free_github_v1_state(self):
        src = _read("daemon/maez_daemon.py")
        body_health = _method_body(src, "_body_health")
        health_server = _method_body(src, "_run_health_server")

        self.assertIn('"github_v1"', body_health)
        self.assertIn("self._github_health()", body_health)
        self.assertIn('"github_v1"', health_server)
        self.assertIn("self._github_health()", health_server)

    def test_github_v1_health_method_uses_store_and_limb_auth_without_content(self):
        src = _read("daemon/maez_daemon.py")
        health_body = _method_body(src, "_github_health")

        self.assertIn("self._github_store.health()", health_body)
        self.assertIn("_GITHUB_LIMB.health()", health_body)
        self.assertIn("auth_ready", health_body)
        self.assertNotIn("repo_count", health_body)
        self.assertNotIn("login", health_body)


if __name__ == "__main__":
    unittest.main()
