import unittest
from unittest import mock
import tempfile
from pathlib import Path


class IngestTokenLoadableTests(unittest.TestCase):
    def test_ingest_token_is_classified_secret(self):
        from core.infra.secrets import is_secret_name

        self.assertTrue(is_secret_name("MAEZ_GITHUB_INGEST_TOKEN"))

    def test_ingest_token_allowlisted(self):
        from core.infra.secrets import SECRET_NAMES

        self.assertIn("MAEZ_GITHUB_INGEST_TOKEN", SECRET_NAMES)


class FetchRepoCountTests(unittest.TestCase):
    def _session(self):
        from core.information_limb import github_limb

        now = 1000.0
        return github_limb.GithubSession("TOK", ["read:user"], now, now + 3600)

    def test_returns_only_public_repos(self):
        from core.information_limb import github_limb

        response = mock.Mock()
        response.status_code = 200
        response.json.return_value = {
            "public_repos": 7,
            "login": "SECRET_LOGIN",
            "id": 1,
        }
        with mock.patch.object(github_limb.requests, "get", return_value=response):
            count = github_limb.fetch_repo_count(self._session())
        self.assertEqual(count, 7)
        self.assertNotIn("SECRET_LOGIN", repr(count))

    def test_missing_field_raises(self):
        from core.information_limb import github_limb

        response = mock.Mock()
        response.status_code = 200
        response.json.return_value = {"login": "x"}
        with mock.patch.object(github_limb.requests, "get", return_value=response):
            with self.assertRaises(github_limb.GithubAuthError):
                github_limb.fetch_repo_count(self._session())

    def test_non_200_raises(self):
        from core.information_limb import github_limb

        response = mock.Mock()
        response.status_code = 403
        with mock.patch.object(github_limb.requests, "get", return_value=response):
            with self.assertRaises(github_limb.GithubAuthError):
                github_limb.fetch_repo_count(self._session())


class DurablePromotionTests(unittest.TestCase):
    def test_promotion_state_persists_across_reinstantiation(self):
        from core.information_limb.github_store import GithubStore

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "github_v1.db"
            store = GithubStore(path)
            store.initialize()
            store.stage_repo_count(
                ingest_record_id="ir-1",
                fetch_batch_id="fb-1",
                repo_count=7,
                count_field="public_repos",
            )
            self.assertEqual(store.promotion_state("ir-1"), "pending")
            store.mark_admitted("ir-1", body_memory_id="mem-1")

            reopened = GithubStore(path)
            reopened.initialize()
            self.assertEqual(reopened.promotion_state("ir-1"), "admitted")
            self.assertEqual(reopened.admitted_body_memory_id("ir-1"), "mem-1")


class RunIngestTests(unittest.TestCase):
    def _real_store(self):
        from core.information_limb.github_store import GithubStore

        tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(tempdir.cleanup)
        store = GithubStore(Path(tempdir.name) / "github_v1.db")
        store.initialize()
        return store

    def test_same_batch_admits_once_durably(self):
        from core.information_limb import github_v1

        store = self._real_store()
        memory = mock.Mock()
        memory.store.return_value = "mem-1"

        with mock.patch(
            "core.information_limb.github_v1.github_limb.fetch_repo_count",
            return_value=7,
        ):
            first = github_v1.run_ingest(
                limb_session=object(),
                store=store,
                memory=memory,
                fetch_batch_id="fb-1",
            )
            second = github_v1.run_ingest(
                limb_session=object(),
                store=store,
                memory=memory,
                fetch_batch_id="fb-1",
            )

        self.assertTrue(first["admitted"])
        self.assertFalse(second["admitted"])
        self.assertEqual(memory.store.call_count, 1)
        self.assertEqual(first["ingest_record_id"], second["ingest_record_id"])
        for key in ("repo_count", "count_field", "login"):
            self.assertNotIn(key, first)
            self.assertNotIn(key, second)

    def test_different_batch_is_a_new_observation(self):
        from core.information_limb import github_v1

        store = self._real_store()
        memory = mock.Mock()
        memory.store.return_value = "mem"

        with mock.patch(
            "core.information_limb.github_v1.github_limb.fetch_repo_count",
            return_value=7,
        ):
            github_v1.run_ingest(
                limb_session=object(),
                store=store,
                memory=memory,
                fetch_batch_id="fb-1",
            )
            github_v1.run_ingest(
                limb_session=object(),
                store=store,
                memory=memory,
                fetch_batch_id="fb-2",
            )

        self.assertEqual(memory.store.call_count, 2)


if __name__ == "__main__":
    unittest.main()
