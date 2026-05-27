import json
import tempfile
import unittest
from pathlib import Path


def _contract_dict(*, model: str = "all-MiniLM-L6-v2", dimension: int = 384) -> dict:
    return {
        "schema_version": "maez-embedding-contract-v1",
        "embedding": {
            "provider": "chromadb.default",
            "function": "ONNXMiniLM_L6_V2",
            "model": model,
            "dimension": dimension,
            "distance_metric": "cosine",
            "artifact_hashes": {
                "onnx_tar_gz_sha256": "tar",
                "model_onnx_sha256": "model",
            },
            "tokenizer": {
                "truncation_tokens": 256,
                "evidence": "test",
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


def _write_contract(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


class ONNXMiniLM_L6_V2:
    MODEL_NAME = "all-MiniLM-L6-v2"

    def __init__(self) -> None:
        self.calls = []

    def max_tokens(self) -> int:
        return 256

    def __call__(self, input):
        self.calls.append(list(input))
        return [[0.01] * 384 for _ in input]


class MemoryEmbedderTests(unittest.TestCase):
    def setUp(self):
        try:
            from memory.embedder import reset_encoder_for_tests

            reset_encoder_for_tests()
        except ModuleNotFoundError:
            pass

    def tearDown(self):
        try:
            from memory.embedder import reset_encoder_for_tests

            reset_encoder_for_tests()
        except ModuleNotFoundError:
            pass

    def test_get_encoder_uses_contract_and_is_singleton(self):
        from memory.embedder import get_encoder

        with tempfile.TemporaryDirectory() as tmp:
            contract_path = Path(tmp) / "embedding_contract.json"
            _write_contract(contract_path, _contract_dict())

            first = get_encoder(
                contract_path=contract_path,
                embedding_function_factory=ONNXMiniLM_L6_V2,
            )
            second = get_encoder(
                contract_path=contract_path,
                embedding_function_factory=lambda: self.fail("singleton reloaded"),
            )

        self.assertIs(first, second)
        self.assertEqual(first.model, "all-MiniLM-L6-v2")
        self.assertEqual(first.dimension, 384)
        self.assertEqual(len(first.encode("hello")), 384)
        self.assertEqual(len(first.encode_many(["a", "b"])), 2)
        self.assertIs(first.embedding_function, second.embedding_function)

    def test_contract_model_or_dimension_drift_refuses_encoder(self):
        from memory.embedder import EncoderContractDriftError, get_encoder

        with tempfile.TemporaryDirectory() as tmp:
            contract_path = Path(tmp) / "embedding_contract.json"
            _write_contract(contract_path, _contract_dict(model="different-model"))

            with self.assertRaises(EncoderContractDriftError) as ctx:
                get_encoder(
                    contract_path=contract_path,
                    embedding_function_factory=ONNXMiniLM_L6_V2,
                )

        self.assertIn("model", str(ctx.exception))

        with tempfile.TemporaryDirectory() as tmp:
            contract_path = Path(tmp) / "embedding_contract.json"
            _write_contract(contract_path, _contract_dict())
            reset = __import__("memory.embedder", fromlist=["reset_encoder_for_tests"])
            reset.reset_encoder_for_tests()
            wrong_dimension_factory = type(
                "ONNXMiniLM_L6_V2",
                (),
                {
                    "MODEL_NAME": "all-MiniLM-L6-v2",
                    "max_tokens": lambda self: 256,
                    "__call__": lambda self, input: [[0.01] * 3 for _ in input],
                },
            )

            encoder = get_encoder(
                contract_path=contract_path,
                embedding_function_factory=wrong_dimension_factory,
            )
            with self.assertRaises(EncoderContractDriftError) as dim_ctx:
                encoder.encode("dimension probe")

        self.assertIn("dimension", str(dim_ctx.exception))


if __name__ == "__main__":
    unittest.main()
