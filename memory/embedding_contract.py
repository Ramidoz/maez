from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

logger = logging.getLogger("maez")

REPO_ROOT = Path(__file__).resolve().parent.parent
CONTRACT_PATH = Path(__file__).resolve().parent / "embedding_contract.json"
DIAGNOSTIC_PATH = Path(__file__).resolve().parent / "embedding_contract_diagnostics.json"

STAMP_KEYS = {
    "schema_version": "maez_embedding_schema_version",
    "model": "maez_embedding_model",
    "dimension": "maez_embedding_dimension",
    "space": "maez_embedding_space",
}


@dataclass(frozen=True)
class EmbeddingContract:
    schema_version: str
    provider: str
    embedding_function: str
    model: str
    dimension: int
    distance_metric: str
    onnx_tar_gz_sha256: str
    model_onnx_sha256: str
    tokenizer_truncation_tokens: int
    chunk_strategy: str
    vector_chunking: str
    prompt_side_consolidation_applies: bool
    prompt_side_consolidation_char_budget: int

    @property
    def stamp(self) -> dict:
        return {
            STAMP_KEYS["schema_version"]: self.schema_version,
            STAMP_KEYS["model"]: self.model,
            STAMP_KEYS["dimension"]: self.dimension,
            STAMP_KEYS["space"]: self.distance_metric,
        }


@dataclass(frozen=True)
class EmbeddingContractStatus:
    ok: bool
    reads_allowed: bool
    writes_allowed: bool
    diagnostics: tuple[str, ...] = ()


class EmbeddingContractDriftError(RuntimeError):
    pass


def _load_dict(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _contract_from_dict(data: Mapping) -> EmbeddingContract:
    emb = data["embedding"]
    artifacts = emb["artifact_hashes"]
    tokenizer = emb["tokenizer"]
    storage = data["vector_storage"]
    prompt_chunk = storage["prompt_side_consolidation_chunking"]
    return EmbeddingContract(
        schema_version=str(data["schema_version"]),
        provider=str(emb["provider"]),
        embedding_function=str(emb["function"]),
        model=str(emb["model"]),
        dimension=int(emb["dimension"]),
        distance_metric=str(emb["distance_metric"]),
        onnx_tar_gz_sha256=str(artifacts["onnx_tar_gz_sha256"]),
        model_onnx_sha256=str(artifacts["model_onnx_sha256"]),
        tokenizer_truncation_tokens=int(tokenizer["truncation_tokens"]),
        chunk_strategy=str(storage["chunk_strategy"]),
        vector_chunking=str(storage["vector_chunking"]),
        prompt_side_consolidation_applies=bool(
            prompt_chunk["applies_to_embedding_contract"]
        ),
        prompt_side_consolidation_char_budget=int(prompt_chunk["char_budget"]),
    )


def load_embedding_contract(path: Path | str = CONTRACT_PATH) -> EmbeddingContract:
    return _contract_from_dict(_load_dict(Path(path)))


load_embedding_contract.from_dict = _contract_from_dict  # type: ignore[attr-defined]


def _collection_metadata(collection) -> dict:
    return dict(getattr(collection, "metadata", None) or {})


def reconcile_collection_stamps(
    collections: Mapping[str, object],
    contract: EmbeddingContract,
    *,
    stamp_missing: bool = False,
) -> EmbeddingContractStatus:
    diagnostics: list[str] = []
    for name, collection in collections.items():
        metadata = _collection_metadata(collection)
        if metadata.get("hnsw:space") != contract.distance_metric:
            diagnostics.append(
                f"{name}: hnsw:space {metadata.get('hnsw:space')!r} "
                f"!= manifest {contract.distance_metric!r}"
            )
        observed_dimension = metadata.get("maez_observed_collection_dimension")
        if observed_dimension is not None and observed_dimension != contract.dimension:
            diagnostics.append(
                f"{name}: collection dimension {observed_dimension!r} "
                f"!= manifest {contract.dimension!r}"
            )
        missing_stamp = [
            key for key in contract.stamp
            if key not in metadata
        ]
        if missing_stamp and stamp_missing:
            updated = dict(metadata)
            updated.update(contract.stamp)
            modify = getattr(collection, "modify", None)
            if not callable(modify):
                diagnostics.append(f"{name}: collection cannot be stamped")
            else:
                modify(metadata=updated)
                metadata = _collection_metadata(collection)
        for stamp_key, expected in contract.stamp.items():
            if stamp_key not in metadata:
                diagnostics.append(f"{name}: missing stamp {stamp_key}")
                continue
            if metadata.get(stamp_key) != expected:
                short = stamp_key.removeprefix("maez_embedding_")
                diagnostics.append(
                    f"{name}: stamp {short} {metadata.get(stamp_key)!r} "
                    f"!= manifest {expected!r}"
                )

    ok = not diagnostics
    return EmbeddingContractStatus(
        ok=ok,
        reads_allowed=True,
        writes_allowed=ok,
        diagnostics=tuple(diagnostics),
    )


def _sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_current_chroma_package(contract: EmbeddingContract) -> tuple[str, ...]:
    """Return package/artifact drift diagnostics.

    This confirms the Chroma default embedding implementation currently
    resolves to the same model/tokenizer facts as the manifest. Missing
    optional artifacts are reported as drift rather than silently
    accepted; #2 is a pinning slice, not a best-effort guess.
    """
    diagnostics: list[str] = []
    try:
        from chromadb.utils.embedding_functions.onnx_mini_lm_l6_v2 import (
            ONNXMiniLM_L6_V2,
        )

        fn = ONNXMiniLM_L6_V2()
        if getattr(fn, "MODEL_NAME", None) != contract.model:
            diagnostics.append(
                f"package model {getattr(fn, 'MODEL_NAME', None)!r} "
                f"!= manifest {contract.model!r}"
            )
        max_tokens = fn.max_tokens()
        if max_tokens != contract.tokenizer_truncation_tokens:
            diagnostics.append(
                f"package tokenizer max_tokens {max_tokens!r} "
                f"!= manifest {contract.tokenizer_truncation_tokens!r}"
            )
        download_path = Path(fn.DOWNLOAD_PATH)
        tar_hash = _sha256(download_path / "onnx.tar.gz")
        model_hash = _sha256(download_path / "onnx" / "model.onnx")
        if tar_hash != contract.onnx_tar_gz_sha256:
            diagnostics.append(
                f"onnx.tar.gz sha256 {tar_hash!r} "
                f"!= manifest {contract.onnx_tar_gz_sha256!r}"
            )
        if model_hash != contract.model_onnx_sha256:
            diagnostics.append(
                f"model.onnx sha256 {model_hash!r} "
                f"!= manifest {contract.model_onnx_sha256!r}"
            )
    except Exception as exc:  # noqa: BLE001 - startup gate records exact reason
        diagnostics.append(f"package evidence unavailable: {exc}")
    return tuple(diagnostics)


def reconcile_embedding_contract(
    collections: Mapping[str, object],
    *,
    contract_path: Path | str = CONTRACT_PATH,
    sqlite_collections: Mapping[str, tuple[Path | str, str]] | None = None,
    stamp_missing: bool = True,
    verify_package: bool = True,
) -> EmbeddingContractStatus:
    contract = load_embedding_contract(contract_path)
    if sqlite_collections and stamp_missing:
        for _name, (db_path, collection_name) in sqlite_collections.items():
            stamp_chroma_sqlite_collection(db_path, collection_name, contract)
    stamp_status = reconcile_collection_stamps(
        (
            _sqlite_metadata_collections(sqlite_collections)
            if sqlite_collections
            else collections
        ),
        contract,
        stamp_missing=(stamp_missing and not sqlite_collections),
    )
    diagnostics = list(stamp_status.diagnostics)
    if verify_package:
        diagnostics.extend(verify_current_chroma_package(contract))
    ok = not diagnostics
    status = EmbeddingContractStatus(
        ok=ok,
        reads_allowed=True,
        writes_allowed=ok,
        diagnostics=tuple(diagnostics),
    )
    if not status.ok:
        record_embedding_contract_diagnostic(status)
    return status


class _MetadataOnlyCollection:
    def __init__(self, metadata: Mapping):
        self.metadata = dict(metadata)


def _sqlite_metadata_collections(
    sqlite_collections: Mapping[str, tuple[Path | str, str]],
) -> dict[str, _MetadataOnlyCollection]:
    return {
        name: _MetadataOnlyCollection(
            read_chroma_sqlite_collection_metadata(db_path, collection_name)
        )
        for name, (db_path, collection_name) in sqlite_collections.items()
    }


def read_chroma_sqlite_collection_metadata(
    db_path: Path | str,
    collection_name: str,
) -> dict:
    path = Path(db_path)
    with sqlite3.connect(path) as db:
        row = db.execute(
            "SELECT id, dimension FROM collections WHERE name = ?",
            (collection_name,),
        ).fetchone()
        if row is None:
            raise ValueError(f"missing Chroma collection {collection_name!r} in {path}")
        collection_id, dimension = row
        out: dict = {
            "maez_observed_collection_dimension": (
                int(dimension) if dimension is not None else None
            )
        }
        for key, str_value, int_value, float_value, bool_value in db.execute(
            "SELECT key, str_value, int_value, float_value, bool_value "
            "FROM collection_metadata WHERE collection_id = ?",
            (collection_id,),
        ):
            if str_value is not None:
                out[key] = str_value
            elif int_value is not None:
                out[key] = int(int_value)
            elif float_value is not None:
                out[key] = float(float_value)
            elif bool_value is not None:
                out[key] = bool(bool_value)
            else:
                out[key] = None
        return out


def _sqlite_value_columns(value) -> tuple[str | None, int | None, float | None, int | None]:
    if isinstance(value, bool):
        return None, None, None, int(value)
    if isinstance(value, int):
        return None, value, None, None
    if isinstance(value, float):
        return None, None, value, None
    return str(value), None, None, None


def stamp_chroma_sqlite_collection(
    db_path: Path | str,
    collection_name: str,
    contract: EmbeddingContract,
) -> None:
    """Append Maez stamp metadata without using Chroma's replace-metadata API.

    Chroma refuses ``modify(metadata=...)`` when ``hnsw:space`` is present,
    because it treats re-sending that key as a forbidden distance-function
    change. Directly writing these metadata rows preserves the existing
    `hnsw:space=cosine` evidence and does not touch embeddings.
    """
    path = Path(db_path)
    with sqlite3.connect(path) as db:
        row = db.execute(
            "SELECT id FROM collections WHERE name = ?",
            (collection_name,),
        ).fetchone()
        if row is None:
            raise ValueError(f"missing Chroma collection {collection_name!r} in {path}")
        collection_id = row[0]
        for key, value in contract.stamp.items():
            str_value, int_value, float_value, bool_value = _sqlite_value_columns(value)
            db.execute(
                "INSERT OR REPLACE INTO collection_metadata "
                "(collection_id, key, str_value, int_value, float_value, bool_value) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (collection_id, key, str_value, int_value, float_value, bool_value),
            )


def record_embedding_contract_diagnostic(
    status: EmbeddingContractStatus,
    *,
    path: Path | str = DIAGNOSTIC_PATH,
) -> None:
    payload = {
        "schema_version": "maez-embedding-contract-diagnostic-v1",
        "ok": status.ok,
        "reads_allowed": status.reads_allowed,
        "writes_allowed": status.writes_allowed,
        "diagnostics": list(status.diagnostics),
    }
    try:
        Path(path).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    except Exception as exc:  # noqa: BLE001 - diagnostic path is best-effort
        logger.warning("failed to record embedding contract diagnostic: %s", exc)


def assert_embedding_writes_allowed(status: EmbeddingContractStatus) -> None:
    if status.writes_allowed:
        return
    reason = "; ".join(status.diagnostics) or "unknown drift"
    raise EmbeddingContractDriftError(
        f"embedding contract drift blocks new memory writes: {reason}"
    )
