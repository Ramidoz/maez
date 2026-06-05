import unittest
from unittest import mock

from core.intake_bus import PromotionPosture
from core.information_limb import github_v1
from core.information_limb.github_store import PendingRecord


class GithubV1ConnectorTests(unittest.TestCase):
    def _adapter_fact(self, *, repo_count=7, count_field="public_repos"):
        store = mock.Mock()
        store.oldest_pending.return_value = PendingRecord(
            ingest_record_id="ir-1",
            fetch_batch_id="fb-1",
            repo_count=repo_count,
            count_field=count_field,
            created_at="2026-06-04T00:00:00+00:00",
        )
        return github_v1.GithubStoreAdapter(store).oldest_pending()

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
        fact = self._adapter_fact(repo_count=7, count_field="public_repos")

        self.assertIn("public repositories", fact.content)
        self.assertNotIn("owned by the owner", fact.content)
        self.assertEqual(fact.egress_origin_class, "owner_account_context")
        self.assertTrue(str(fact.provenance_source).lower().endswith("tool_observation"))
        self.assertEqual(fact.source_ref, "github.s2:ir-1")
        self.assertEqual(fact.fetch_batch_id, "fb-1")
        self.assertEqual(fact.promotion_posture, PromotionPosture.ADMIT_TO_BODY)

    def test_total_field_uses_owned_wording(self):
        fact = self._adapter_fact(repo_count=9, count_field="total")

        self.assertIn(
            "repositories owned by the owner",
            fact.content,
        )


if __name__ == "__main__":
    unittest.main()
