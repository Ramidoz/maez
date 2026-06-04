import unittest

from core.information_limb.github_v1_config import GithubMode, resolve_github_mode


class GithubModeTests(unittest.TestCase):
    def test_default_is_disabled(self):
        self.assertEqual(resolve_github_mode({}), GithubMode.DISABLED)

    def test_v1(self):
        self.assertEqual(resolve_github_mode({"MAEZ_GITHUB_MODE": "v1"}), GithubMode.V1)

    def test_legacy_requires_gate(self):
        with self.assertRaises(ValueError):
            resolve_github_mode({"MAEZ_GITHUB_MODE": "legacy_dev_only"})
        self.assertEqual(
            resolve_github_mode({
                "MAEZ_GITHUB_MODE": "legacy_dev_only",
                "MAEZ_GITHUB_ALLOW_LEGACY_TEST_MODE": "1",
            }),
            GithubMode.LEGACY_DEV_ONLY,
        )

    def test_unsupported_raises(self):
        with self.assertRaises(ValueError):
            resolve_github_mode({"MAEZ_GITHUB_MODE": "bogus"})


if __name__ == "__main__":
    unittest.main()
