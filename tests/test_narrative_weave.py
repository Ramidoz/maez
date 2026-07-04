import tempfile
import unittest
from pathlib import Path


RAW_ID = "123e4567-e89b-12d3-a456-426614174000"
RAW_ID_2 = "123e4567-e89b-12d3-a456-426614174001"


def _ep(eid: str, summary: str, sources: list[str] | None = None) -> dict:
    return {
        "id": eid,
        "title": eid,
        "summary": summary,
        "source_memory_ids": sources or [],
        "status": "active",
    }


class FakeEncoder:
    model = "fake-minilm"
    dimension = 2

    def __init__(self, vectors: dict[str, list[float]]):
        self._vectors = vectors

    def encode(self, text: str) -> list[float]:
        return list(self._vectors[text])


class NarrativeWeaveTests(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.db = Path(self._td.name) / "lived_episodes.db"
        from core.memory.narrative import NarrativeStore

        self.store = NarrativeStore(self.db)

    def tearDown(self):
        self._td.cleanup()

    def test_proposals_carry_instrument_receipt(self):
        from core.memory.narrative_weave import propose_same_story_candidates

        encoder = FakeEncoder({"alpha": [1.0, 0.0], "near alpha": [0.99, 0.01]})

        written = propose_same_story_candidates(
            [_ep("ep-a", "alpha"), _ep("ep-b", "near alpha")],
            self.store,
            encoder=encoder,
            distance_threshold=0.02,
        )

        proposals = self.store.pending_proposals()
        self.assertEqual(written, 1)
        self.assertEqual(len(proposals), 1)
        self.assertEqual(proposals[0]["kind"], "same_story")
        self.assertEqual(proposals[0]["embedder_id"], "fake-minilm:2")
        self.assertLess(proposals[0]["distance"], 0.02)

    def test_no_llm_structural_guard_trips_on_planted_import(self):
        from core.memory.narrative_weave import assert_no_llm_in_weave_source

        assert_no_llm_in_weave_source("from memory.embedder import get_encoder\n")
        with self.assertRaisesRegex(AssertionError, "LLM"):
            assert_no_llm_in_weave_source(
                "from core.routing import llm_client\n"
                "def bad():\n"
                "    return llm_client.chat(messages=[])\n"
            )

    def test_already_linked_pair_gets_no_proposal(self):
        from core.memory.narrative_weave import propose_same_story_candidates

        self.store.upsert_link(
            link_type="same_thread",
            from_episode_id="ep-a",
            to_episode_id="ep-b",
            trust="derived",
            evidence_ids=[RAW_ID],
            detector_version="v0",
        )
        encoder = FakeEncoder({"alpha": [1.0, 0.0], "near alpha": [0.99, 0.01]})

        written = propose_same_story_candidates(
            [_ep("ep-a", "alpha"), _ep("ep-b", "near alpha")],
            self.store,
            encoder=encoder,
            distance_threshold=0.02,
        )

        self.assertEqual(written, 0)
        self.assertEqual(self.store.pending_proposals(), [])

    def test_promotion_refuses_non_joinable_confirmation(self):
        from core.memory.narrative import LinkCandidate
        from core.memory.narrative_weave import promote_confirmed_same_thread

        proposal_id = self.store.add_proposal(
            kind="same_story",
            ep_a="ep-a",
            ep_b="ep-b",
            embedder_id="fake-minilm:2",
            distance=0.01,
        )

        promoted = promote_confirmed_same_thread(
            self.store,
            LinkCandidate(
                link_type="same_thread",
                from_id="ep-a",
                to_id="ep-b",
                evidence_ids=["core-shared-summary"],
            ),
        )

        self.assertEqual(promoted, 0)
        self.assertEqual(self.store.pending_proposals()[0]["proposal_id"], proposal_id)
        self.assertEqual(self.store.links_for("ep-a"), [])

    def test_confirming_joinable_receipt_promotes_with_both_evidence_entries(self):
        from core.memory.narrative import LinkCandidate
        from core.memory.narrative_weave import promote_confirmed_same_thread

        proposal_id = self.store.add_proposal(
            kind="same_story",
            ep_a="ep-a",
            ep_b="ep-b",
            embedder_id="fake-minilm:2",
            distance=0.01,
        )

        promoted = promote_confirmed_same_thread(
            self.store,
            LinkCandidate(
                link_type="same_thread",
                from_id="ep-b",
                to_id="ep-a",
                evidence_ids=[RAW_ID],
            ),
        )

        self.assertEqual(promoted, 1)
        self.assertEqual(self.store.pending_proposals(), [])
        links = self.store.links_for("ep-a")
        self.assertEqual(len(links), 1)
        self.assertEqual(links[0]["trust"], "confirmed")
        self.assertEqual([entry["ids"] for entry in links[0]["evidence"]], [[RAW_ID], [f"proposal:{proposal_id}"]])
        self.assertEqual(self.store.pending_proposals(), [])

    def test_confirmation_can_promote_when_it_connects_existing_threads(self):
        from core.memory.narrative import LinkCandidate
        from core.memory.narrative_weave import promote_confirmed_same_thread

        self.store.upsert_link(
            link_type="same_thread",
            from_episode_id="ep-a",
            to_episode_id="ep-b",
            trust="derived",
            evidence_ids=[RAW_ID],
            detector_version="v0",
        )
        proposal_id = self.store.add_proposal(
            kind="same_story",
            ep_a="ep-a",
            ep_b="ep-c",
            embedder_id="fake-minilm:2",
            distance=0.01,
        )

        promoted = promote_confirmed_same_thread(
            self.store,
            LinkCandidate(
                link_type="same_thread",
                from_id="ep-b",
                to_id="ep-c",
                evidence_ids=[RAW_ID_2],
            ),
        )

        self.assertEqual(promoted, 1)
        self.assertEqual(self.store.pending_proposals(), [])
        links = self.store.links_for("ep-b")
        confirmed = [link for link in links if link["trust"] == "confirmed"]
        self.assertEqual(len(confirmed), 1)
        self.assertEqual({confirmed[0]["from_episode_id"], confirmed[0]["to_episode_id"]}, {"ep-b", "ep-c"})
        self.assertEqual(confirmed[0]["evidence"][1]["ids"], [f"proposal:{proposal_id}"])

    def test_unconfirmed_proposal_survives_without_expiry_path(self):
        self.store.add_proposal(
            kind="same_story",
            ep_a="ep-a",
            ep_b="ep-b",
            embedder_id="fake-minilm:2",
            distance=0.01,
        )

        self.assertEqual(len(self.store.pending_proposals()), 1)
        self.assertFalse(hasattr(self.store, "expire_proposals"))


if __name__ == "__main__":
    unittest.main()
