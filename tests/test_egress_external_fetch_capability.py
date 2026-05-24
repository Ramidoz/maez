from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path


FETCH_MAPPING = {
    "fetch_type": "public_docs_lookup",
    "threat_model_class": "public_lookup",
    "result_origin_class": "tool_result_public",
    "destination_family": "public documentation",
    "class_exists": True,
}


class ExternalFetchCapabilityTests(unittest.TestCase):
    def test_card_payload_uses_nested_fetch_mapping_and_plain_english(self):
        from core.infra.capability_proposal import _compose_card_action_payload

        payload = _compose_card_action_payload(
            felt_limitation="needs public docs",
            capability_id="public_docs_lookup",
            source="manual",
            manual_source_path="docs/maez_manual/example.md",
            acquisition="self-dev",
            plain_english="Card body.",
            proposal_id="prop-test",
            fetch_mapping=FETCH_MAPPING,
        )

        self.assertEqual(payload["params"]["fetch_mapping"], FETCH_MAPPING)
        self.assertIn(
            "This capability would make outbound HTTP requests as public_docs_lookup, "
            "treated as public_lookup, producing tool_result_public.",
            payload["plain_english"],
        )

    def test_action_engine_refuses_external_http_capability_without_fetch_mapping(self):
        from core.actions.action_engine import ActionEngine

        result = ActionEngine()._do_capability_acquire(
            capability_id="public_docs_lookup",
            source="manual",
            manual_source_path="docs/maez_manual/example.md",
            acquisition="self-dev",
            requires_external_http=True,
        )

        self.assertEqual(
            result,
            "capability.acquire refused: external HTTP capability requires fetch_mapping",
        )

    def test_valid_fetch_mapping_is_preserved_in_queue_payload(self):
        from core.actions.action_engine import ActionEngine

        with tempfile.TemporaryDirectory() as td:
            queue_path = Path(td) / "queue.sqlite"
            result = ActionEngine()._do_capability_acquire(
                capability_id="recursive-context-engine",
            source="manual",
            manual_source_path="docs/maez_manual/recursive-context-engine.md",
            acquisition="self-dev",
                proposal_id="prop-test",
                requires_external_http=True,
                fetch_mapping=FETCH_MAPPING,
                queue_path=str(queue_path),
            )

            self.assertIn("Acquisition intent queued", result)
            conn = sqlite3.connect(queue_path)
            try:
                payload_json = conn.execute(
                    "select payload_json from acquisition_queue"
                ).fetchone()[0]
            finally:
                conn.close()
            payload = json.loads(payload_json)
            self.assertEqual(payload["fetch_mapping"], FETCH_MAPPING)


if __name__ == "__main__":
    unittest.main()
