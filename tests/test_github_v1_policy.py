import unittest

from core.information_limb import github_connector_policy as pol


class GithubConnectorPolicyTests(unittest.TestCase):
    def test_allowed_scope_is_read_user_only(self):
        self.assertEqual(pol.ALLOWED_SCOPE, "read:user")
        self.assertEqual(pol.assert_scope_allowed("read:user"), "read:user")

    def test_broad_scope_rejected(self):
        for scope in ("repo", "read:org", "user", "read:user repo"):
            with self.subTest(scope=scope):
                with self.assertRaises(pol.GithubPolicyError):
                    pol.assert_scope_allowed(scope)

    def test_count_only_fact_passes(self):
        self.assertTrue(pol.assert_fact_minimized({"repo_count": 7, "count_field": "public_repos"}))
        self.assertTrue(pol.assert_fact_minimized({"repo_count": 7, "count_field": "total"}))

    def test_extra_or_raw_fields_rejected(self):
        raw_facts = [
            {"repo_count": 7, "repo_names": ["x"]},
            {"repo_count": 7, "login": "owner"},
            {"repo_count": 7, "private_repos": 3},
        ]
        for fact in raw_facts:
            with self.subTest(fact=fact):
                with self.assertRaises(pol.GithubPolicyError):
                    pol.assert_fact_minimized(fact)

    def test_count_must_be_non_negative_integer_with_resolved_field(self):
        invalid = [
            {"repo_count": "7", "count_field": "public_repos"},
            {"repo_count": -1, "count_field": "public_repos"},
            {"repo_count": 7, "count_field": "private_repos"},
            {"repo_count": 7},
        ]
        for fact in invalid:
            with self.subTest(fact=fact):
                with self.assertRaises(pol.GithubPolicyError):
                    pol.assert_fact_minimized(fact)


if __name__ == "__main__":
    unittest.main()
