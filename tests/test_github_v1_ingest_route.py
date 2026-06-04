import os
import time
import unittest
from unittest import mock

from core.information_limb import github_limb, github_v1
from core.information_limb.github_v1_config import GithubMode


class _Headers(dict):
    def get(self, k, default=None):
        return super().get(k, default)


class GithubV1IngestRouteTests(unittest.TestCase):
    def setUp(self):
        os.environ[github_v1.GITHUB_INGEST_TOKEN_ENV] = "INGEST_SECRET"
        os.environ[github_limb.GITHUB_HANDOFF_TOKEN_ENV] = "HANDOFF_SECRET"
        self.addCleanup(os.environ.pop, github_v1.GITHUB_INGEST_TOKEN_ENV, None)
        self.addCleanup(os.environ.pop, github_limb.GITHUB_HANDOFF_TOKEN_ENV, None)

    def test_ingest_trusted_requires_dedicated_secret(self):
        self.assertFalse(github_v1.ingest_trusted(_Headers()))
        self.assertFalse(
            github_v1.ingest_trusted(
                _Headers({github_limb.GITHUB_HANDOFF_HEADER: "HANDOFF_SECRET"})
            )
        )
        self.assertFalse(
            github_v1.ingest_trusted(
                _Headers({github_v1.GITHUB_INGEST_HEADER: "HANDOFF_SECRET"})
            )
        )
        self.assertTrue(
            github_v1.ingest_trusted(
                _Headers({github_v1.GITHUB_INGEST_HEADER: "INGEST_SECRET"})
            )
        )

    def test_origin_untrusted_even_with_right_secret(self):
        self.assertFalse(
            github_v1.ingest_trusted(
                _Headers(
                    {
                        github_v1.GITHUB_INGEST_HEADER: "INGEST_SECRET",
                        "Origin": "http://evil",
                    }
                )
            )
        )

    def test_bad_secret_rejects_before_limb_or_store_action(self):
        limb = mock.Mock()
        limb.health.side_effect = AssertionError("limb read before auth")
        store = mock.Mock()
        memory = mock.Mock()

        result, status = github_v1.handle_ingest(
            headers=_Headers({github_v1.GITHUB_INGEST_HEADER: "WRONG"}),
            mode=GithubMode.V1,
            limb=limb,
            store=store,
            memory=memory,
            fetch_batch_id_factory=lambda: "fb-1",
        )

        self.assertEqual(status, 403)
        self.assertEqual(result["error"], "github_ingest_untrusted")
        limb.health.assert_not_called()
        memory.store.assert_not_called()

    def test_non_v1_mode_rejects(self):
        limb = mock.Mock()
        store = mock.Mock()

        result, status = github_v1.handle_ingest(
            headers=_Headers({github_v1.GITHUB_INGEST_HEADER: "INGEST_SECRET"}),
            mode=GithubMode.DISABLED,
            limb=limb,
            store=store,
            memory=mock.Mock(),
            fetch_batch_id_factory=lambda: "fb-1",
        )

        self.assertEqual(status, 409)
        self.assertEqual(result["error"], "github_v1_not_enabled")
        limb.health.assert_not_called()
        store.mock_calls.clear()

    def test_unauthed_limb_rejects(self):
        limb = mock.Mock()
        limb.available_session.return_value = None

        result, status = github_v1.handle_ingest(
            headers=_Headers({github_v1.GITHUB_INGEST_HEADER: "INGEST_SECRET"}),
            mode=GithubMode.V1,
            limb=limb,
            store=mock.Mock(),
            memory=mock.Mock(),
            fetch_batch_id_factory=lambda: "fb-1",
        )

        self.assertEqual(status, 409)
        self.assertEqual(result["error"], "github_limb_unauthed")

    def test_missing_store_rejects(self):
        limb = mock.Mock()
        limb.health.return_value = {"state": "available"}

        result, status = github_v1.handle_ingest(
            headers=_Headers({github_v1.GITHUB_INGEST_HEADER: "INGEST_SECRET"}),
            mode=GithubMode.V1,
            limb=limb,
            store=None,
            memory=mock.Mock(),
            fetch_batch_id_factory=lambda: "fb-1",
        )

        self.assertEqual(status, 409)
        self.assertEqual(result["error"], "github_store_unavailable")

    def test_good_secret_v1_available_store_returns_content_free_allowlist(self):
        limb = github_limb.GithubLimb()
        session = github_limb.GithubSession(
            access_token="SESSION_SECRET",
            scopes=["read:user"],
            obtained_at=time.time(),
            expires_at=time.time() + 3600,
        )
        limb.set_session(session)
        limb.mark_state("available", now=1000.0)
        store = mock.Mock()
        memory = mock.Mock()

        with mock.patch.object(
            github_v1,
            "run_ingest",
            return_value={
                "ok": True,
                "ingest_record_id": "ir-1",
                "fetch_batch_id": "fb-1",
                "staged": True,
                "admitted": True,
                "state": "admitted",
                "resumed": True,
                "repo_count": 7,
                "login": "SECRET_LOGIN",
            },
        ) as run_ingest:
            result, status = github_v1.handle_ingest(
                headers=_Headers({github_v1.GITHUB_INGEST_HEADER: "INGEST_SECRET"}),
                mode=GithubMode.V1,
                limb=limb,
                store=store,
                memory=memory,
                fetch_batch_id_factory=lambda: "fb-1",
            )

        self.assertEqual(status, 200)
        run_ingest.assert_called_once_with(
            limb_session=session,
            store=store,
            memory=memory,
            fetch_batch_id="fb-1",
        )
        self.assertEqual(
            set(result),
            {
                "ok",
                "ingest_record_id",
                "fetch_batch_id",
                "staged",
                "admitted",
                "state",
                "resumed",
            },
        )
        self.assertTrue(result["resumed"])
        self.assertNotIn("SECRET_LOGIN", repr(result))
        self.assertNotIn("SESSION_SECRET", repr(result))


if __name__ == "__main__":
    unittest.main()
