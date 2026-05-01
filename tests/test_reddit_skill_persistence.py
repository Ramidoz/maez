# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Reddit-skill persistence tests (2026-04-27 incident closure).

Background: the 21:35 cycle thought referenced a real TRELLIS.2 post
on r/LocalLLaMA. Maez's RedditSkill correctly fetched the post via
its in-cycle context-block path, but those signals were never
persisted to raw memory. Audit pipelines (self_claim_audit, my own
review just now) that filter raw entries by ``source=reddit`` saw
zero entries and incorrectly concluded "no Reddit signal exists" —
treating an incomplete-corpus check as a verified absence.

This test set locks the persistence contract:

- ``_fetch_subreddit`` returns posts with stable Reddit post IDs.
- ``persist_to_memory(memory_manager, cycle)`` writes each newly-
  cached post to raw memory with metadata that audit pipelines can
  filter on (``type='reddit_post'``, ``source='reddit/r/<sub>'``,
  ``reddit_post_id=<id>``).
- Within a single process lifetime, a post is persisted at most
  once even if it stays in the fetch cache across multiple
  ``persist_to_memory`` calls (in-memory dedup via
  ``_persisted_ids``).
- Empty cache / unfetched skill yields no writes.
- Persistence never raises; storage failure is silent (logged).
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))


class _FakeMemory:
    """Minimal stand-in for MemoryManager.store() — captures calls."""

    def __init__(self):
        self.calls = []  # list of (content, cycle, metadata) tuples

    def store(self, content, cycle, snapshot=None, metadata=None, *,
              provenance_source=None, trust_tier=None):
        # 5x.B Pass 2a: accept provenance kwargs so the production
        # reddit_skill.persist call lands in the happy path; reddit
        # is the canonical external_web/untrusted ingress. The
        # provenance assertion lives in test_memory_provenance_pass2a;
        # this fake preserves the existing 4-tuple shape so callers
        # that unpack mem.calls keep working.
        self.calls.append((content, cycle, snapshot, metadata or {}))
        return f"raw-{len(self.calls)}"


class _FakeRedditPost(dict):
    """Helper to build a Reddit-API-shaped post dict for mocked
    fetches."""

    @classmethod
    def make(cls, post_id, title, score=100, comments=10, flair=""):
        return {
            "data": {
                "id": post_id,
                "name": f"t3_{post_id}",
                "title": title,
                "score": score,
                "num_comments": comments,
                "link_flair_text": flair,
                "stickied": False,
                "permalink": f"/r/test/comments/{post_id}/",
            }
        }


class FetchCapturesPostId(unittest.TestCase):
    """The first half of the contract: ``_fetch_subreddit`` must keep
    each post's Reddit ID so dedup at persist-time is possible."""

    def test_fetched_post_carries_id_field(self):
        from skills.reddit_skill import RedditSkill

        with mock.patch("skills.reddit_skill.requests.get") as mock_get:
            mock_get.return_value.raise_for_status = lambda: None
            mock_get.return_value.json = lambda: {
                "data": {
                    "children": [
                        _FakeRedditPost.make("abc123", "Microsoft TRELLIS.2 released"),
                    ]
                }
            }
            skill = RedditSkill()
            posts = skill._fetch_subreddit("LocalLLaMA", limit=3)

        self.assertEqual(len(posts), 1)
        self.assertEqual(posts[0]["id"], "abc123")
        self.assertEqual(posts[0]["title"], "Microsoft TRELLIS.2 released")


class PersistsToMemory(unittest.TestCase):
    """The second half: ``persist_to_memory`` writes cached posts to
    the supplied memory manager with audit-friendly metadata."""

    def test_persist_writes_cached_posts(self):
        from skills.reddit_skill import RedditSkill

        with mock.patch("skills.reddit_skill.requests.get") as mock_get:
            mock_get.return_value.raise_for_status = lambda: None
            mock_get.return_value.json = lambda: {
                "data": {
                    "children": [
                        _FakeRedditPost.make(
                            "abc123",
                            "Microsoft Presents TRELLIS.2",
                            score=2456,
                            comments=341,
                            flair="New Model",
                        ),
                        _FakeRedditPost.make("def456", "Qwen3.6-30B Q4 fits 24GB?", score=890),
                    ]
                }
            }
            skill = RedditSkill()
            skill._fetch_subreddit("LocalLLaMA", limit=3)
            mem = _FakeMemory()
            skill.persist_to_memory(mem, cycle=42)

        self.assertEqual(len(mem.calls), 2)

        # Each call must carry audit-able metadata.
        seen_ids = set()
        for content, cycle, snapshot, metadata in mem.calls:
            self.assertEqual(metadata.get("type"), "reddit_post")
            self.assertEqual(metadata.get("source"), "reddit/r/LocalLLaMA")
            self.assertIn("reddit_post_id", metadata)
            seen_ids.add(metadata["reddit_post_id"])
            self.assertIn(metadata["reddit_post_id"], content)
            self.assertEqual(cycle, 42)

        self.assertEqual(seen_ids, {"abc123", "def456"})

    def test_post_content_includes_title_score_flair(self):
        from skills.reddit_skill import RedditSkill

        with mock.patch("skills.reddit_skill.requests.get") as mock_get:
            mock_get.return_value.raise_for_status = lambda: None
            mock_get.return_value.json = lambda: {
                "data": {
                    "children": [
                        _FakeRedditPost.make(
                            "post1",
                            "Test title with searchable terms",
                            score=500,
                            comments=42,
                            flair="Discussion",
                        ),
                    ]
                }
            }
            skill = RedditSkill()
            skill._fetch_subreddit("LocalLLaMA", limit=1)
            mem = _FakeMemory()
            skill.persist_to_memory(mem, cycle=1)

        content = mem.calls[0][0]
        # All audit-relevant tokens must appear so a future
        # self_claim_audit / lived-recall query can find them.
        self.assertIn("Test title", content)
        self.assertIn("LocalLLaMA", content)
        self.assertIn("post1", content)


class DedupAcrossPersistCalls(unittest.TestCase):
    """If ``persist_to_memory`` is called twice with the same cached
    posts (which is what happens when the daemon's cycle re-uses the
    cache within the 450s TTL), each post must persist at most once
    per process lifetime."""

    def test_repeat_persist_is_idempotent(self):
        from skills.reddit_skill import RedditSkill

        with mock.patch("skills.reddit_skill.requests.get") as mock_get:
            mock_get.return_value.raise_for_status = lambda: None
            mock_get.return_value.json = lambda: {
                "data": {
                    "children": [
                        _FakeRedditPost.make("p1", "First post"),
                        _FakeRedditPost.make("p2", "Second post"),
                    ]
                }
            }
            skill = RedditSkill()
            skill._fetch_subreddit("LocalLLaMA", limit=3)
            mem = _FakeMemory()
            skill.persist_to_memory(mem, cycle=10)
            skill.persist_to_memory(mem, cycle=11)
            skill.persist_to_memory(mem, cycle=12)

        # Two posts, three persist calls — only two writes total.
        self.assertEqual(len(mem.calls), 2)


class EmptyCacheNoWrites(unittest.TestCase):
    def test_persist_with_empty_cache_writes_nothing(self):
        from skills.reddit_skill import RedditSkill

        skill = RedditSkill()
        mem = _FakeMemory()
        skill.persist_to_memory(mem, cycle=0)
        self.assertEqual(len(mem.calls), 0)


class PersistFailsSilently(unittest.TestCase):
    """The daemon must not crash if memory.store raises. Reddit is
    auxiliary; persistence is opportunistic."""

    def test_storage_exception_does_not_propagate(self):
        from skills.reddit_skill import RedditSkill

        class _BrokenMemory:
            def store(self, *args, **kwargs):
                raise RuntimeError("simulated chroma failure")

        with mock.patch("skills.reddit_skill.requests.get") as mock_get:
            mock_get.return_value.raise_for_status = lambda: None
            mock_get.return_value.json = lambda: {
                "data": {"children": [_FakeRedditPost.make("abc", "x")]}
            }
            skill = RedditSkill()
            skill._fetch_subreddit("LocalLLaMA", limit=1)
            # Must not raise.
            try:
                skill.persist_to_memory(_BrokenMemory(), cycle=0)
            except Exception as e:
                self.fail(f"persist_to_memory must swallow storage errors; raised: {e!r}")


class FilterableByAuditMetadata(unittest.TestCase):
    """The audit-pipeline contract: persisted entries must be
    filterable by ``source=reddit/...`` so future audits checking
    for Reddit references against raw memory don't false-negative."""

    def test_metadata_source_starts_with_reddit_prefix(self):
        from skills.reddit_skill import RedditSkill

        with mock.patch("skills.reddit_skill.requests.get") as mock_get:
            mock_get.return_value.raise_for_status = lambda: None
            mock_get.return_value.json = lambda: {
                "data": {"children": [_FakeRedditPost.make("x", "x")]}
            }
            skill = RedditSkill()
            skill._fetch_subreddit("LocalLLaMA", limit=1)
            mem = _FakeMemory()
            skill.persist_to_memory(mem, cycle=0)

        meta = mem.calls[0][3]
        self.assertTrue(
            meta["source"].startswith("reddit/"),
            f"source must start with 'reddit/' for audit filtering; got {meta['source']!r}",
        )


if __name__ == "__main__":
    unittest.main()
