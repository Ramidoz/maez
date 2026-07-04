import unittest


RAW_ID = "123e4567-e89b-12d3-a456-426614174000"


def _ep(eid: str, sources: list[str], *, source_kind: str = "reflection") -> dict:
    return {
        "id": eid,
        "title": eid,
        "summary": eid,
        "source_memory_ids": sources,
        "source_kind": source_kind,
        "status": "active",
    }


class CitationClassifierTests(unittest.TestCase):
    def test_classifies_joinable_and_excluded_citation_types(self):
        from core.memory.narrative import classify_citation

        self.assertEqual(classify_citation(RAW_ID), "raw_uuid")
        self.assertEqual(classify_citation("consequence:42"), "receipt_store")
        self.assertEqual(classify_citation("fabrication:7"), "receipt_store")
        self.assertEqual(classify_citation("dream:3"), "receipt_store")
        self.assertEqual(classify_citation("veto:9"), "receipt_store")
        self.assertEqual(classify_citation("card:abc"), "receipt_store")
        self.assertEqual(classify_citation("followup-doc:docs/x.md"), "followup")
        self.assertEqual(classify_citation("exhibit:daily/row-1"), "exhibit")
        self.assertEqual(classify_citation("ep-abc123"), "episode")
        self.assertEqual(classify_citation("core-row-1"), "core")
        self.assertEqual(classify_citation("daily-2026-07-03"), "daily")


class NarrativeDetectorTests(unittest.TestCase):
    def test_reflection_cocitation_blob_produces_strings_not_same_thread(self):
        from core.memory.narrative import detect_links

        new_ep = _ep("ep-reflection", ["ep-a", "ep-b"])
        links = detect_links(new_ep, [_ep("ep-a", []), _ep("ep-b", [])], scar_sidecar_rows=[])

        self.assertEqual(
            [(c.link_type, c.from_id, c.to_id, c.evidence_ids) for c in links],
            [
                ("strings", "ep-reflection", "ep-a", ["ep-a"]),
                ("strings", "ep-reflection", "ep-b", ["ep-b"]),
            ],
        )

    def test_shared_raw_uuid_creates_same_thread(self):
        from core.memory.narrative import detect_links

        links = detect_links(
            _ep("ep-new", [RAW_ID]),
            [_ep("ep-old", [RAW_ID])],
            scar_sidecar_rows=[],
        )

        self.assertEqual(len(links), 1)
        self.assertEqual(links[0].link_type, "same_thread")
        self.assertEqual({links[0].from_id, links[0].to_id}, {"ep-new", "ep-old"})
        self.assertEqual(links[0].evidence_ids, [RAW_ID])

    def test_core_cocitation_is_not_a_thread(self):
        from core.memory.narrative import detect_links

        links = detect_links(
            _ep("ep-new", ["core-shared"]),
            [_ep("ep-old", ["core-shared"])],
            scar_sidecar_rows=[],
        )

        self.assertEqual(links, [])

    def test_sidecar_multiple_episode_ids_creates_same_thread_only(self):
        from core.memory.narrative import detect_links

        links = detect_links(
            _ep("ep-active", []),
            [_ep("ep-prior", [])],
            scar_sidecar_rows=[
                {
                    "dedup_key": "fabrication:claim-about-body",
                    "active_episode_id": "ep-active",
                    "prior_episode_ids": ["ep-prior"],
                    "receipt_refs": ["fabrication:1", "consequence:2"],
                }
            ],
        )

        self.assertEqual(len(links), 1)
        self.assertEqual(links[0].link_type, "same_thread")
        self.assertEqual({links[0].from_id, links[0].to_id}, {"ep-active", "ep-prior"})
        self.assertIn("scar-sidecar:fabrication:claim-about-body", links[0].evidence_ids)
        self.assertIsNone(links[0].hook_class)

    def test_sidecar_empty_prior_ids_is_armed_but_silent(self):
        from core.memory.narrative import detect_links

        links = detect_links(
            _ep("ep-active", []),
            [],
            scar_sidecar_rows=[
                {
                    "dedup_key": "fabrication:claim-about-body",
                    "active_episode_id": "ep-active",
                    "prior_episode_ids": [],
                    "receipt_refs": ["fabrication:1", "consequence:2"],
                }
            ],
        )

        self.assertEqual(links, [])

    def test_no_typed_hook_means_no_because_of(self):
        from core.memory.narrative import detect_links

        links = detect_links(
            _ep("ep-new", ["fabrication:1"], source_kind="reflection"),
            [_ep("ep-old", ["fabrication:1"])],
            scar_sidecar_rows=[],
        )

        self.assertEqual([c.link_type for c in links], ["same_thread"])
        self.assertNotIn("because_of", {c.link_type for c in links})

    def test_scar_shared_receipt_store_id_creates_typed_because_of(self):
        from core.memory.narrative import detect_links

        links = detect_links(
            _ep("ep-scar", ["fabrication:1"], source_kind="scar"),
            [_ep("ep-prior", ["fabrication:1"])],
            scar_sidecar_rows=[],
        )

        self.assertEqual([c.link_type for c in links], ["same_thread", "because_of"])
        because = links[1]
        self.assertEqual(because.hook_class, "scar:fabrication")
        self.assertEqual(because.evidence_ids, ["fabrication:1"])


if __name__ == "__main__":
    unittest.main()
