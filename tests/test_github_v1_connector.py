import unittest
from unittest import mock

from core.information_limb import github_v1


class GithubV1ConnectorTests(unittest.TestCase):
    def test_repo_count_staged_from_user_response(self):
        user_payload = {"public_repos": 7, "login": "SECRET_LOGIN", "id": 1}
        store = mock.Mock()
        store.stage_repo_count.return_value = {
            "ingest_record_id": "ir-1",
            "fetch_batch_id": "fb-1",
            "record_state": "active",
        }

        result = github_v1.ingest_repo_count(
            user_response=user_payload,
            store=store,
            fetch_batch_id="fb-1",
            observed_at="2026-06-04T00:00:00+00:00",
        )

        _, kwargs = store.stage_repo_count.call_args
        self.assertEqual(kwargs["repo_count"], 7)
        self.assertEqual(kwargs["count_field"], "public_repos")
        self.assertEqual(kwargs["fetch_batch_id"], "fb-1")
        self.assertNotIn("SECRET_LOGIN", repr(result))

    def test_repo_count_requires_public_repos_integer(self):
        with self.assertRaises(github_v1.GithubV1Error):
            github_v1.ingest_repo_count(
                user_response={"public_repos": "7"},
                store=mock.Mock(),
                fetch_batch_id="fb-1",
            )

    def test_health_states_content_free(self):
        disabled = github_v1.build_github_health(mode="disabled")
        self.assertEqual(disabled["state"], "disabled")
        needs_auth = github_v1.build_github_health(mode="v1", auth_ready=False)
        self.assertEqual(needs_auth["state"], "needs_auth")
        available = github_v1.build_github_health(
            mode="v1",
            auth_ready=True,
            staged_records=1,
        )
        self.assertEqual(available["state"], "available")
        self.assertNotIn("SECRET_LOGIN", repr(available))


if __name__ == "__main__":
    unittest.main()
