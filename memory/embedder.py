"""Shared MiniLM encoder for Maez embedding consumers.

ADR 0047 needs the dispatcher and Chroma-backed memory to depend on one
contract-bound encoder surface. This module owns that singleton. It exposes
encoding, but it does not classify, score archetypes, or choose routes.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from memory.embedding_contract import CONTRACT_PATH, load_embedding_contract


class EncoderContractDriftError(RuntimeError):
    pass


@dataclass(frozen=True)
class MiniLMEncoder:
    embedding_function: Callable[[list[str]], Sequence[Sequence[float]]]
    model: str
    dimension: int
    tokenizer_truncation_tokens: int

    def encode(self, text: str) -> list[float]:
        vectors = self.encode_many([text])
        return vectors[0]

    def encode_many(self, texts: Sequence[str]) -> list[list[float]]:
        vectors = self.embedding_function(list(texts))
        normalized = [list(vector) for vector in vectors]
        for vector in normalized:
            if len(vector) != self.dimension:
                raise EncoderContractDriftError(
                    f"vector dimension {len(vector)!r} != manifest {self.dimension!r}"
                )
        return normalized


_ENCODER: MiniLMEncoder | None = None


def get_encoder(
    *,
    contract_path: Path | str = CONTRACT_PATH,
    embedding_function_factory: Callable[[], Any] | None = None,
) -> MiniLMEncoder:
    global _ENCODER
    if _ENCODER is not None:
        return _ENCODER

    contract = load_embedding_contract(contract_path)
    factory = embedding_function_factory or _default_embedding_function_factory
    embedding_function = factory()

    observed_function = type(embedding_function).__name__
    if observed_function != contract.embedding_function:
        raise EncoderContractDriftError(
            f"embedding function {observed_function!r} != manifest "
            f"{contract.embedding_function!r}"
        )

    observed_model = getattr(embedding_function, "MODEL_NAME", None)
    if observed_model != contract.model:
        raise EncoderContractDriftError(
            f"model {observed_model!r} != manifest {contract.model!r}"
        )

    max_tokens = getattr(embedding_function, "max_tokens", None)
    if not callable(max_tokens):
        raise EncoderContractDriftError("embedding function lacks max_tokens()")
    observed_tokens = int(max_tokens())
    if observed_tokens != contract.tokenizer_truncation_tokens:
        raise EncoderContractDriftError(
            f"tokenizer max_tokens {observed_tokens!r} != manifest "
            f"{contract.tokenizer_truncation_tokens!r}"
        )

    _ENCODER = MiniLMEncoder(
        embedding_function=embedding_function,
        model=contract.model,
        dimension=contract.dimension,
        tokenizer_truncation_tokens=contract.tokenizer_truncation_tokens,
    )
    return _ENCODER


def _default_embedding_function_factory() -> Any:
    from chromadb.utils.embedding_functions.onnx_mini_lm_l6_v2 import (
        ONNXMiniLM_L6_V2,
    )

    return ONNXMiniLM_L6_V2()


def reset_encoder_for_tests() -> None:
    global _ENCODER
    _ENCODER = None
