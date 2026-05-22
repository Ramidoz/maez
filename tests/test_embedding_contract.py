from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path


class _FakeCollection:
    def __init__(self, *, metadata=None):
        self.metadata = dict(metadata or {"hnsw:space": "cosine"})
        self.modify_calls = []
        self.add_calls = []

    def modify(self, *, metadata):
        self.modify_calls.append(dict(metadata))
        self.metadata = dict(metadata)

    def add(self, *, ids, documents, metadatas):
        self.add_calls.append({
            "ids": ids,
            "documents": documents,
            "metadatas": metadatas,
        })


def _contract_dict() -> dict:
    return {
        "schema_version": "maez-embedding-contract-v1",
        "embedding": {
            "provider": "chromadb.default",
            "function": "ONNXMiniLM_L6_V2",
            "model": "all-MiniLM-L6-v2",
            "dimension": 384,
            "distance_metric": "cosine",
            "artifact_hashes": {
                "onnx_tar_gz_sha256": (
                    "913d7300ceae3b2dbc2c50d1de4baacab4be7b9380491c27"
                    "fab7418616a16ec3"
                ),
                "model_onnx_sha256": (
                    "4f148ba8ae9c2c7fbee4af2b132db8d06c6a6545b47fc83"
                    "bbb98c3d22b8393e6"
                ),
            },
            "tokenizer": {
                "truncation_tokens": 256,
                "evidence": "chromadb ONNXMiniLM_L6_V2 max_tokens()",
            },
        },
        "vector_storage": {
            "chunk_strategy": "whole_document",
            "vector_chunking": "none",
            "prompt_side_consolidation_chunking": {
                "applies_to_embedding_contract": False,
                "char_budget": 96000,
            },
        },
    }


class EmbeddingContractManifestTests(unittest.TestCase):
    def test_manifest_loads_authoritative_verified_values(self):
        from memory.embedding_contract import load_embedding_contract

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "embedding_contract.json"
            path.write_text(json.dumps(_contract_dict()), encoding="utf-8")

            contract = load_embedding_contract(path)

        self.assertEqual(contract.schema_version, "maez-embedding-contract-v1")
        self.assertEqual(contract.model, "all-MiniLM-L6-v2")
        self.assertEqual(contract.embedding_function, "ONNXMiniLM_L6_V2")
        self.assertEqual(contract.dimension, 384)
        self.assertEqual(contract.distance_metric, "cosine")
        self.assertEqual(contract.tokenizer_truncation_tokens, 256)
        self.assertEqual(
            contract.onnx_tar_gz_sha256,
            "913d7300ceae3b2dbc2c50d1de4baacab4be7b9380491c27"
            "fab7418616a16ec3",
        )
        self.assertEqual(
            contract.model_onnx_sha256,
            "4f148ba8ae9c2c7fbee4af2b132db8d06c6a6545b47fc83"
            "bbb98c3d22b8393e6",
        )

    def test_missing_collection_stamp_is_written_without_changing_hnsw_space(self):
        from memory.embedding_contract import (
            load_embedding_contract,
            reconcile_collection_stamps,
        )

        collection = _FakeCollection(metadata={"hnsw:space": "cosine"})
        contract = load_embedding_contract.from_dict(_contract_dict())

        status = reconcile_collection_stamps(
            {"raw": collection},
            contract,
            stamp_missing=True,
        )

        self.assertTrue(status.ok, status.diagnostics)
        self.assertTrue(status.writes_allowed)
        self.assertTrue(status.reads_allowed)
        self.assertEqual(collection.modify_calls, [collection.metadata])
        self.assertEqual(collection.metadata["hnsw:space"], "cosine")
        self.assertEqual(
            collection.metadata["maez_embedding_schema_version"],
            "maez-embedding-contract-v1",
        )
        self.assertEqual(collection.metadata["maez_embedding_model"], "all-MiniLM-L6-v2")
        self.assertEqual(collection.metadata["maez_embedding_dimension"], 384)
        self.assertEqual(collection.metadata["maez_embedding_space"], "cosine")

    def test_manifest_wins_on_stamp_disagreement_and_blocks_writes_only(self):
        from memory.embedding_contract import (
            EmbeddingContractDriftError,
            assert_embedding_writes_allowed,
            load_embedding_contract,
            record_embedding_contract_diagnostic,
            reconcile_collection_stamps,
        )

        collection = _FakeCollection(
            metadata={
                "hnsw:space": "cosine",
                "maez_embedding_schema_version": "maez-embedding-contract-v1",
                "maez_embedding_model": "different-model",
                "maez_embedding_dimension": 384,
                "maez_embedding_space": "cosine",
            }
        )
        contract = load_embedding_contract.from_dict(_contract_dict())

        status = reconcile_collection_stamps({"raw": collection}, contract)

        self.assertFalse(status.ok)
        self.assertFalse(status.writes_allowed)
        self.assertTrue(status.reads_allowed)
        self.assertTrue(any("raw" in d and "model" in d for d in status.diagnostics))
        with self.assertRaises(EmbeddingContractDriftError):
            assert_embedding_writes_allowed(status)
        with tempfile.TemporaryDirectory() as tmp:
            diagnostic_path = Path(tmp) / "diagnostic.json"
            record_embedding_contract_diagnostic(status, path=diagnostic_path)
            payload = json.loads(diagnostic_path.read_text(encoding="utf-8"))
        self.assertFalse(payload["writes_allowed"])
        self.assertTrue(payload["reads_allowed"])
        self.assertIn("different-model", payload["diagnostics"][0])

    def test_memory_manager_write_chokepoint_blocks_on_contract_drift(self):
        from memory.embedding_contract import EmbeddingContractStatus
        from memory.memory_manager import MemoryManager

        mm = MemoryManager.__new__(MemoryManager)
        mm.raw = _FakeCollection()
        mm._embedding_contract_status = EmbeddingContractStatus(
            ok=False,
            reads_allowed=True,
            writes_allowed=False,
            diagnostics=("forced drift for test",),
        )

        with self.assertRaises(RuntimeError) as ctx:
            mm.store("owner allowed careful access", cycle=1)

        self.assertIn("embedding contract drift", str(ctx.exception))
        self.assertEqual(mm.raw.add_calls, [])
