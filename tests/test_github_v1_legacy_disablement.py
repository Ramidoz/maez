import ast
import inspect
import unittest

from daemon import maez_daemon


def _daemon_tree() -> ast.Module:
    tree = ast.parse(inspect.getsource(maez_daemon))
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            child.parent = node  # type: ignore[attr-defined]
    return tree


def _contains_legacy_guard(node: ast.AST) -> bool:
    for child in ast.walk(node):
        if (
            isinstance(child, ast.Attribute)
            and child.attr == "_github_legacy_enabled"
            and isinstance(child.value, ast.Name)
            and child.value.id == "self"
        ):
            return True
    return False


def _is_guarded_by_legacy_mode(node: ast.AST) -> bool:
    parent = getattr(node, "parent", None)
    while parent is not None:
        if isinstance(parent, ast.If) and _contains_legacy_guard(parent.test):
            return True
        parent = getattr(parent, "parent", None)
    return False


def _is_self_attr(node: ast.AST, attr: str) -> bool:
    return (
        isinstance(node, ast.Attribute)
        and node.attr == attr
        and isinstance(node.value, ast.Name)
        and node.value.id == "self"
    )


class GithubLegacyDisablementTests(unittest.TestCase):
    def test_daemon_resolves_github_mode(self):
        src = inspect.getsource(maez_daemon)
        self.assertIn("GithubMode", src)
        self.assertIn("resolve_github_mode", src)
        self.assertIn("GITHUB_MODE = resolve_github_mode(os.environ)", src)

    def test_github_skill_is_constructed_only_under_legacy_guard(self):
        tree = _daemon_tree()
        calls = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "GitHubSkill"
        ]
        self.assertTrue(calls, "daemon should still retain the legacy GitHubSkill path")
        for call in calls:
            self.assertTrue(
                _is_guarded_by_legacy_mode(call),
                "GitHubSkill() must not be constructed outside legacy dev mode",
            )

    def test_legacy_fetch_is_guarded(self):
        tree = _daemon_tree()
        calls = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "get_context_block"
            and _is_self_attr(node.func.value, "github")
        ]
        self.assertTrue(calls, "daemon should still retain the legacy GitHub fetch path")
        for call in calls:
            self.assertTrue(
                _is_guarded_by_legacy_mode(call),
                "self.github.get_context_block() must be legacy-dev-only",
            )

    def test_legacy_prompt_injection_is_guarded(self):
        tree = _daemon_tree()
        text_refs = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Attribute)
            and node.attr == "text"
            and _is_self_attr(node.value, "_last_github_block")
        ]
        self.assertTrue(text_refs, "daemon should still retain the legacy block text path")
        for ref in text_refs:
            self.assertTrue(
                _is_guarded_by_legacy_mode(ref),
                "self._last_github_block.text must not feed prompts outside legacy dev mode",
            )

    def test_normal_mode_has_honest_absence_signal(self):
        src = inspect.getsource(maez_daemon)
        self.assertIn("GitHub v1 S2 ingest; legacy reader off", src)


if __name__ == "__main__":
    unittest.main()
