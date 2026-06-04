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

    def test_body_admission_honest_wording_taint_and_traceability(self):
        memory = mock.Mock()
        memory.store.return_value = "mem-1"

        github_v1.admit_repo_count_to_body(
            memory=memory,
            repo_count=7,
            count_field="public_repos",
            ingest_record_id="ir-1",
            fetch_batch_id="fb-1",
        )

        _, kwargs = memory.store.call_args
        self.assertIn("public repositories", kwargs["content"])
        self.assertNotIn("owned by the owner", kwargs["content"])
        self.assertEqual(kwargs["cycle"], 0)
        self.assertEqual(kwargs["egress_origin_class"], "owner_account_context")
        self.assertTrue(str(kwargs["provenance_source"]).lower().endswith("tool_observation"))
        self.assertEqual(kwargs["metadata"]["source_ref"], "github.s2:ir-1")
        self.assertEqual(kwargs["metadata"]["fetch_batch_id"], "fb-1")

    def test_total_field_uses_owned_wording(self):
        memory = mock.Mock()
        memory.store.return_value = "mem-2"

        github_v1.admit_repo_count_to_body(
            memory=memory,
            repo_count=9,
            count_field="total",
            ingest_record_id="ir-2",
            fetch_batch_id="fb-2",
        )

        self.assertIn(
            "repositories owned by the owner",
            memory.store.call_args.kwargs["content"],
        )


if __name__ == "__main__":
    unittest.main()
