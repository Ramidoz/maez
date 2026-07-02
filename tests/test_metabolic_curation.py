import unittest

from scripts.metabolic_curation import (
    NEGATIVE_CONTROL_PREDICATES,
    PendingReviewError,
    RowRef,
    archive_restore_proof,
    is_raw_bulk_candidate,
    is_journal_row,
    parse_review_artifact_text,
    require_raw_rule_samples_reviewed,
    require_review_complete,
    verify_keep_rows_still_hot,
    _rows,
)


class CurationPredicateTests(unittest.TestCase):
    def test_daily_journal_matches(self):
        self.assertTrue(is_journal_row("daily", {"type": "daily_consolidation"}))

    def test_core_nightly_journal_matches(self):
        self.assertTrue(
            is_journal_row("core", {"source": "nightly_journal", "type": "core_memory"})
        )

    def test_negative_controls_never_match(self):
        controls = [
            {"source": "soul_evolution", "type": "core_memory"},
            {"trust_tier": "covenant", "type": "core_memory"},
            {"type": "core_memory", "source": "owner"},
            {"metabolic_durable_reason": "covenant", "type": "core_memory"},
        ]
        self.assertGreaterEqual(len(NEGATIVE_CONTROL_PREDICATES), 4)
        for meta in controls:
            for tier in ("core", "daily"):
                with self.subTest(meta=meta, tier=tier):
                    self.assertFalse(is_journal_row(tier, meta))

    def test_who_rohit_is_fixture_never_matches(self):
        meta = {"type": "core_memory", "source": "owner", "trust_tier": "covenant"}
        self.assertFalse(is_journal_row("core", meta))

    def test_raw_bulk_candidate_requires_old_uncited_introspection(self):
        base = {
            "type": "reasoning",
            "provenance_source": "introspection",
            "timestamp": "2026-06-01T00:00:00+00:00",
        }
        self.assertTrue(is_raw_bulk_candidate(base, now_ts="2026-07-02T00:00:00+00:00"))
        self.assertFalse(
            is_raw_bulk_candidate(
                {**base, "timestamp": "2026-07-01T00:00:00+00:00"},
                now_ts="2026-07-02T00:00:00+00:00",
            )
        )
        self.assertFalse(is_raw_bulk_candidate({**base, "source": "owner"}))
        self.assertFalse(is_raw_bulk_candidate({**base, "metabolic_durable_reason": "covenant"}))
        self.assertFalse(is_raw_bulk_candidate({**base, "episode_id": "ep-1"}))


class ReviewArtifactTests(unittest.TestCase):
    def test_parse_review_artifact_splits_approved_keep_and_pending(self):
        artifact = "\n".join(
            [
                "- [x] MOVE core/core-1 -- preview -- source=nightly_journal",
                "- [ ] KEEP daily/daily-keep -- preview -- owner kept",
                "- [ ] MOVE daily/daily-pending -- preview -- type=daily_consolidation",
            ]
        )
        parsed = parse_review_artifact_text(artifact)
        self.assertEqual(parsed.approved_moves, [RowRef("core", "core-1")])
        self.assertEqual(parsed.kept_rows, [RowRef("daily", "daily-keep")])
        self.assertEqual(parsed.pending_rows, [RowRef("daily", "daily-pending")])

    def test_pending_review_blocks_apply(self):
        parsed = parse_review_artifact_text(
            "- [ ] MOVE core/core-pending -- preview -- source=nightly_journal"
        )
        with self.assertRaises(PendingReviewError):
            require_review_complete(parsed)

    def test_raw_rule_samples_must_be_reviewed(self):
        with self.assertRaises(PendingReviewError):
            require_raw_rule_samples_reviewed(
                "- [ ] RAW-RULE-SAMPLE raw/raw-1 -- preview -- provenance_source=introspection"
            )
        require_raw_rule_samples_reviewed(
            "- [x] RAW-RULE-SAMPLE raw/raw-1 -- preview -- provenance_source=introspection"
        )


class _FakeCollection:
    def __init__(self, rows=None, *, max_limit=None):
        self.rows = dict(rows or {})
        self.max_limit = max_limit

    def count(self):
        return len(self.rows)

    def get(self, *, ids=None, include=None, limit=None, offset=0):
        if limit is not None:
            if self.max_limit is not None and limit > self.max_limit:
                raise RuntimeError("too many SQL variables")
            got_ids = list(self.rows.keys())[offset : offset + limit]
        else:
            got_ids = [row_id for row_id in ids if row_id in self.rows]
        docs = [self.rows[row_id][0] for row_id in got_ids]
        metas = [self.rows[row_id][1] for row_id in got_ids]
        return {"ids": got_ids, "documents": docs, "metadatas": metas}

    def add(self, *, ids, documents, metadatas):
        for row_id, doc, meta in zip(ids, documents, metadatas, strict=True):
            self.rows[row_id] = (doc, meta)

    def delete(self, *, ids):
        for row_id in ids:
            self.rows.pop(row_id, None)


class CurationApplyVerifyTests(unittest.TestCase):
    def test_rows_batches_large_collections(self):
        collection = _FakeCollection(
            {f"row-{i}": (f"doc {i}", {"idx": i}) for i in range(7)},
            max_limit=3,
        )
        rows = _rows(collection, batch_size=3)
        self.assertEqual([row_id for row_id, _doc, _meta in rows], [f"row-{i}" for i in range(7)])
        self.assertEqual(rows[-1], ("row-6", "doc 6", {"idx": 6}))

    def test_verify_keep_rows_still_hot_raises_when_keep_missing(self):
        collections = {"core": _FakeCollection({"present": ("doc", {})})}
        verify_keep_rows_still_hot(collections, [RowRef("core", "present")])
        with self.assertRaises(AssertionError):
            verify_keep_rows_still_hot(collections, [RowRef("core", "missing")])

    def test_archive_restore_proof_round_trips_byte_identical_row(self):
        hot = _FakeCollection({"row-1": ("original doc", {"source": "nightly_journal"})})
        archive = _FakeCollection()
        archive_restore_proof(hot, archive, RowRef("core", "row-1"))
        self.assertEqual(hot.rows["row-1"], ("original doc", {"source": "nightly_journal"}))
        self.assertIn("core/row-1", archive.rows)
