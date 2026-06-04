import inspect
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest import mock


class OldestPendingTests(unittest.TestCase):
    def test_oldest_pending_by_created_at(self):
        from core.information_limb.github_store import GithubStore

        with tempfile.TemporaryDirectory() as d:
            store = GithubStore(Path(d) / "github_v1.db")
            store.initialize()
            store.stage_repo_count(
                ingest_record_id="ir-A",
                fetch_batch_id="fb-A",
                repo_count=7,
                count_field="public_repos",
            )
            store.stage_repo_count(
                ingest_record_id="ir-B",
                fetch_batch_id="fb-B",
                repo_count=8,
                count_field="public_repos",
            )

            pending = store.oldest_pending()
            self.assertIsNotNone(pending)
            self.assertEqual(pending.ingest_record_id, "ir-A")
            self.assertEqual(pending.repo_count, 7)
            self.assertEqual(pending.count_field, "public_repos")
            self.assertEqual(pending.fetch_batch_id, "fb-A")

            store.mark_admitted("ir-A", body_memory_id="mem-A")
            self.assertEqual(store.oldest_pending().ingest_record_id, "ir-B")

            store.mark_admitted("ir-B", body_memory_id="mem-B")
            self.assertIsNone(store.oldest_pending())

    def test_created_at_migrates_for_existing_rows(self):
        from core.information_limb.github_store import GithubStore

        with tempfile.TemporaryDirectory() as d:
            db = Path(d) / "github_v1.db"
            with closing(sqlite3.connect(db)) as conn:
                conn.executescript(
                    """
                    CREATE TABLE github_provider_mirror (
                        ingest_record_id TEXT PRIMARY KEY,
                        fetch_batch_id TEXT NOT NULL,
                        repo_count INTEGER NOT NULL,
                        count_field TEXT NOT NULL,
                        count_hash TEXT NOT NULL,
                        record_state TEXT NOT NULL DEFAULT 'active',
                        promotion_state TEXT NOT NULL DEFAULT 'pending',
                        body_memory_id TEXT,
                        github_store_schema_version TEXT NOT NULL,
                        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                    );
                    CREATE TABLE github_policy_versions (
                        policy_name TEXT PRIMARY KEY,
                        policy_version TEXT NOT NULL,
                        github_store_schema_version TEXT NOT NULL,
                        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                    );
                    INSERT INTO github_provider_mirror (
                        ingest_record_id,
                        fetch_batch_id,
                        repo_count,
                        count_field,
                        count_hash,
                        record_state,
                        promotion_state,
                        github_store_schema_version,
                        updated_at
                    ) VALUES (
                        'ir-old',
                        'fb-old',
                        7,
                        'public_repos',
                        'hash-old',
                        'active',
                        'pending',
                        '2',
                        '2026-06-04T12:34:56+00:00'
                    );
                    """
                )

            store = GithubStore(db)
            store.initialize()

            with closing(sqlite3.connect(db)) as conn:
                row = conn.execute(
                    """
                    SELECT created_at, updated_at
                    FROM github_provider_mirror
                    WHERE ingest_record_id='ir-old'
                    """
                ).fetchone()
            self.assertEqual(row[0], row[1])
            self.assertEqual(row[0], "2026-06-04T12:34:56+00:00")


class SourceRefLookupTests(unittest.TestCase):
    def test_returns_id_only_for_owner_account_row(self):
        from memory.memory_manager import MemoryManager, ProvenanceSource
        from tests.test_memory_manager import _temp_memory_manager

        memory = _temp_memory_manager()
        owner_id = memory.store(
            content="GitHub reports 7 public repositories on the owner's profile",
            cycle=0,
            provenance_source=ProvenanceSource.TOOL_OBSERVATION,
            egress_origin_class="owner_account_context",
            metadata={"source_ref": "github.s2:ir-1"},
        )
        memory.store(
            content="unrelated",
            cycle=0,
            metadata={"source_ref": "github.s2:ir-1"},
        )

        self.assertEqual(
            memory.owner_account_row_id_by_source_ref("github.s2:ir-1"),
            owner_id,
        )
        self.assertIsNone(
            memory.owner_account_row_id_by_source_ref("github.s2:absent")
        )
        self.assertIsNone(memory.owner_account_row_id_by_source_ref(""))

        signature = inspect.signature(MemoryManager.store)
        self.assertNotIn("memory_id", signature.parameters)
        self.assertNotIn("explicit_id", signature.parameters)

    def test_generic_row_with_source_ref_does_not_satisfy_owner_lookup(self):
        from tests.test_memory_manager import _temp_memory_manager

        memory = _temp_memory_manager()
        memory.store(
            content="generic GitHub note",
            cycle=0,
            metadata={"source_ref": "github.s2:ir-generic"},
        )

        self.assertIsNone(
            memory.owner_account_row_id_by_source_ref("github.s2:ir-generic")
        )

    def test_lookup_failure_raises_instead_of_laundering_to_absent(self):
        from memory.memory_manager import MemoryManager

        class FailingRaw:
            def get(self, **_kwargs):
                raise RuntimeError("raw collection unavailable")

        memory = MemoryManager.__new__(MemoryManager)
        memory.raw = FailingRaw()

        with self.assertRaises(RuntimeError):
            memory.owner_account_row_id_by_source_ref("github.s2:ir-1")


class ResumeTests(unittest.TestCase):
    def _store(self):
        from core.information_limb.github_store import GithubStore

        tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(tempdir.cleanup)
        store = GithubStore(Path(tempdir.name) / "github_v1.db")
        store.initialize()
        return store

    def test_crash_after_admit_resumes_no_double_write(self):
        from core.information_limb import github_v1

        store = self._store()
        memory = mock.Mock()
        memory.store.return_value = "mem-1"
        memory.owner_account_row_id_by_source_ref.return_value = None

        original_mark = store.mark_admitted
        mark_calls = {"count": 0}

        def flaky_mark_admitted(ingest_record_id, *, body_memory_id):
            mark_calls["count"] += 1
            if mark_calls["count"] == 1:
                raise RuntimeError("crash after body write")
            return original_mark(ingest_record_id, body_memory_id=body_memory_id)

        with (
            mock.patch(
                "core.information_limb.github_v1.github_limb.fetch_repo_count",
                return_value=7,
            ),
            mock.patch.object(store, "mark_admitted", side_effect=flaky_mark_admitted),
        ):
            with self.assertRaises(RuntimeError):
                github_v1.run_ingest(
                    limb_session=object(),
                    store=store,
                    memory=memory,
                    fetch_batch_id="fb-A",
                )
            memory.owner_account_row_id_by_source_ref.return_value = "mem-1"
            result = github_v1.run_ingest(
                limb_session=object(),
                store=store,
                memory=memory,
                fetch_batch_id="fb-B",
            )

        self.assertTrue(result["resumed"])
        self.assertFalse(result["admitted"])
        self.assertEqual(result["fetch_batch_id"], "fb-A")
        self.assertEqual(memory.store.call_count, 1)

    def test_crash_after_stage_resumes_from_staged_count_no_refetch(self):
        from core.information_limb import github_v1

        store = self._store()
        memory = mock.Mock()
        memory.store.return_value = "mem-1"
        memory.owner_account_row_id_by_source_ref.return_value = None

        with (
            mock.patch(
                "core.information_limb.github_v1.github_limb.fetch_repo_count",
                return_value=7,
            ),
            mock.patch(
                "core.information_limb.github_v1.admit_repo_count_to_body",
                side_effect=RuntimeError("crash after stage"),
            ),
        ):
            with self.assertRaises(RuntimeError):
                github_v1.run_ingest(
                    limb_session=object(),
                    store=store,
                    memory=memory,
                    fetch_batch_id="fb-A",
                )

        with mock.patch(
            "core.information_limb.github_v1.github_limb.fetch_repo_count",
            side_effect=AssertionError("must not re-fetch on resume"),
        ):
            result = github_v1.run_ingest(
                limb_session=object(),
                store=store,
                memory=memory,
                fetch_batch_id="fb-B",
            )

        self.assertTrue(result["resumed"])
        self.assertTrue(result["admitted"])
        self.assertEqual(result["fetch_batch_id"], "fb-A")
        self.assertEqual(memory.store.call_count, 1)

    def test_no_pending_is_a_new_observation(self):
        from core.information_limb import github_v1

        store = self._store()
        memory = mock.Mock()
        memory.store.return_value = "mem-1"
        memory.owner_account_row_id_by_source_ref.return_value = None

        with mock.patch(
            "core.information_limb.github_v1.github_limb.fetch_repo_count",
            return_value=7,
        ):
            result = github_v1.run_ingest(
                limb_session=object(),
                store=store,
                memory=memory,
                fetch_batch_id="fb-A",
            )

        self.assertFalse(result["resumed"])
        self.assertTrue(result["admitted"])
        for key in ("repo_count", "count_field", "login"):
            self.assertNotIn(key, result)


if __name__ == "__main__":
    unittest.main()
