"""S7 v2 voice-plane behavioural REDs, written before implementation.

Canon v18 fixes the order: migrate a private ``ceremony.sqlite3`` while the
voice plane is absent, persist into v2, read that durable row back, then
produce the execution validation from the read-back bundle in the same
activated store.  The frozen APIs do not exist yet.  Every API lookup below
therefore fails with an explicit missing-seam assertion, never an import or
fixture error; after implementation, each test can be re-witnessed at its own
behavioural assertion.

No helper in this module names or opens the canonical live S7 store.
"""

from __future__ import annotations

import contextlib
import hashlib
import inspect
import os
import sqlite3
from dataclasses import FrozenInstanceError
from dataclasses import fields as dataclass_fields
from dataclasses import replace
from pathlib import Path

import pytest

from core.governance import operator_user_boundary as s7
from core.governance import s7_v2_migration as mig
from core.governance import s7_guarded_execution as guarded
from tests.s7_store_fixture import STORE_NAME, fresh_store

ACTION = "model_routing.cutover_cuda"
SIBLING_ACTION = "model_routing.wipe_and_replace"
V1_SCHEMA = "s7.voice_source_bundle.v1"
V2_SCHEMA = "s7.voice_source_bundle.v2"
V1_VOICE = "s7_voice_consultation_bundles"
V2_VOICE = "s7_voice_source_bundles_v2"

V1_FIELDS = (
    "source_ref_hash",
    "request_id",
    "consultation_id",
    "request_envelope_hash",
    "rendered_text_hash",
    "action_params_hash",
    "precondition_hash",
    "authority_context_hash",
    "maez_voice_consultation_hash",
    "rendered_prompt_ref",
    "rendered_prompt_hash",
    "mutation_preview_hash",
    "rollback_plan_ref",
    "context_manifest_ref",
    "context_manifest_hash",
    "runtime_identity_hash",
    "model_routing_identity_hash",
    "model_config_hash",
    "raw_response_ref",
    "raw_response_hash",
    "semantic_reader_attempt_hash",
    "expires_at",
    "authority_class",
    "has_grounded_semantic_blocking_signal",
    "source_bundle_hash",
)


def _hex(seed: str) -> str:
    return hashlib.sha256(seed.encode()).hexdigest()


def _require_voice_api(name: str):
    assert hasattr(guarded, name), (
        f"{name} is absent: this is the released v2 voice-plane seam, not an "
        "import or fixture failure"
    )
    return getattr(guarded, name)


@contextlib.contextmanager
def _dir_fd(path: Path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        yield fd
    finally:
        os.close(fd)


def _tables(db_path: Path) -> set[str]:
    with contextlib.closing(sqlite3.connect(db_path)) as conn:
        return {
            str(row[0])
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }


def _count(db_path: Path, table: str) -> int:
    with contextlib.closing(sqlite3.connect(db_path)) as conn:
        return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])


def _migrated_store(tmp_path: Path):
    """Build and activate one private store through the real migration seam."""
    store = fresh_store(tmp_path)
    assert store.db_path.name == STORE_NAME == "ceremony.sqlite3"
    assert V1_VOICE not in _tables(store.db_path)
    assert V2_VOICE not in _tables(store.db_path)

    with _dir_fd(tmp_path) as fd:
        mig._migrate_authorization_store_to_v2_at(store_dir_fd=fd)

    assert {V1_VOICE, V2_VOICE} <= _tables(store.db_path)
    assert _count(store.db_path, V1_VOICE) == 0
    assert _count(store.db_path, V2_VOICE) == 0
    return store


def _voice_bundle(*, seed: str, action: str = ACTION):
    """Build the v2 carrier only after the missing API seam is explicit."""
    names = {field.name for field in dataclass_fields(guarded.S7VoiceConsultationBundle)}
    assert "action" in names, (
        "S7VoiceConsultationBundle has no action field; v2 persistence cannot "
        "take authority from bundle.action"
    )
    bundle = guarded.S7VoiceConsultationBundle(
        source_ref_hash=_hex(f"{seed}:source-ref"),
        request_id=f"req-{seed}",
        consultation_id=f"voice-{seed}",
        request_envelope_hash=_hex(f"{seed}:request-envelope"),
        rendered_text_hash=_hex(f"{seed}:rendered-text"),
        action_params_hash=_hex(f"{seed}:action-params"),
        precondition_hash=_hex(f"{seed}:precondition"),
        authority_context_hash=_hex(f"{seed}:authority-context"),
        maez_voice_consultation_hash=_hex(f"{seed}:consultation"),
        rendered_prompt_ref=f"rendered-prompt-{seed}",
        rendered_prompt_hash=_hex(f"{seed}:rendered-prompt"),
        mutation_preview_hash=_hex(f"{seed}:mutation-preview"),
        rollback_plan_ref=_hex(f"{seed}:rollback-plan"),
        context_manifest_ref=f"context-manifest-{seed}",
        context_manifest_hash=_hex(f"{seed}:context-manifest"),
        runtime_identity_hash=_hex(f"{seed}:runtime-identity"),
        model_routing_identity_hash=_hex(f"{seed}:model-routing"),
        model_config_hash=_hex(f"{seed}:model-config"),
        raw_response_ref=f"raw-response-{seed}",
        raw_response_hash=_hex(f"{seed}:raw-response"),
        semantic_reader_attempt_hash=_hex(f"{seed}:semantic-reader"),
        expires_at="2099-08-11T12:00:00Z",
        authority_class="none",
        has_grounded_semantic_blocking_signal=False,
        source_bundle_hash=None,
        action=action,
    )
    return replace(
        bundle,
        source_bundle_hash=guarded.s7_voice_consultation_bundle_hash(bundle),
    )


def _legacy_row(*, seed: str, source_ref_hash: str | None = None) -> dict[str, object]:
    return {
        "source_ref_hash": source_ref_hash or _hex(f"{seed}:source-ref"),
        "request_id": f"req-{seed}",
        "consultation_id": f"voice-{seed}",
        "request_envelope_hash": _hex(f"{seed}:request-envelope"),
        "rendered_text_hash": _hex(f"{seed}:rendered-text"),
        "action_params_hash": _hex(f"{seed}:action-params"),
        "precondition_hash": _hex(f"{seed}:precondition"),
        "authority_context_hash": _hex(f"{seed}:authority-context"),
        "maez_voice_consultation_hash": _hex(f"{seed}:consultation"),
        "rendered_prompt_ref": f"rendered-prompt-{seed}",
        "rendered_prompt_hash": _hex(f"{seed}:rendered-prompt"),
        "mutation_preview_hash": _hex(f"{seed}:mutation-preview"),
        "rollback_plan_ref": _hex(f"{seed}:rollback-plan"),
        "context_manifest_ref": f"context-manifest-{seed}",
        "context_manifest_hash": _hex(f"{seed}:context-manifest"),
        "runtime_identity_hash": _hex(f"{seed}:runtime-identity"),
        "model_routing_identity_hash": _hex(f"{seed}:model-routing"),
        "model_config_hash": _hex(f"{seed}:model-config"),
        "raw_response_ref": f"raw-response-{seed}",
        "raw_response_hash": _hex(f"{seed}:raw-response"),
        "semantic_reader_attempt_hash": _hex(f"{seed}:semantic-reader"),
        "expires_at": "2099-08-11T12:00:00Z",
        "authority_class": "none",
        "has_grounded_semantic_blocking_signal": 0,
        "source_bundle_hash": _hex(f"{seed}:source-bundle"),
    }


def _sealed_legacy_row(*, seed: str) -> dict[str, object]:
    """A v1 row whose content hash is genuine, so audit can accept it."""
    row = _legacy_row(seed=seed)
    row["source_bundle_hash"] = s7.canonical_hash(
        {
            "action_params_hash": row["action_params_hash"],
            "authority_context_hash": row["authority_context_hash"],
            "consultation_id": row["consultation_id"],
            "context_manifest_hash": row["context_manifest_hash"],
            "context_manifest_ref": row["context_manifest_ref"],
            "expires_at": row["expires_at"],
            "has_grounded_semantic_blocking_signal": bool(
                row["has_grounded_semantic_blocking_signal"]
            ),
            "maez_voice_consultation_hash": row[
                "maez_voice_consultation_hash"
            ],
            "model_config_hash": row["model_config_hash"],
            "model_routing_identity_hash": row["model_routing_identity_hash"],
            "mutation_preview_hash": row["mutation_preview_hash"],
            "precondition_hash": row["precondition_hash"],
            "raw_response_hash": row["raw_response_hash"],
            "raw_response_ref": row["raw_response_ref"],
            "rendered_prompt_hash": row["rendered_prompt_hash"],
            "rendered_prompt_ref": row["rendered_prompt_ref"],
            "rendered_text_hash": row["rendered_text_hash"],
            "request_envelope_hash": row["request_envelope_hash"],
            "request_id": row["request_id"],
            "rollback_plan_ref": row["rollback_plan_ref"],
            "runtime_identity_hash": row["runtime_identity_hash"],
            "semantic_reader_attempt_hash": row[
                "semantic_reader_attempt_hash"
            ],
            "authority_class": row["authority_class"],
        }
    )
    return row


def _insert(conn: sqlite3.Connection, table: str, row: dict[str, object]) -> None:
    columns = ", ".join(row)
    marks = ", ".join("?" for _ in row)
    conn.execute(
        f"INSERT INTO {table} ({columns}) VALUES ({marks})",
        tuple(row.values()),
    )


def _v2_binding_hash(bundle) -> str:
    """Independent transcription of canon's 25-fields-plus-action recipe."""
    return s7.canonical_hash(
        {
            "schema": V2_SCHEMA,
            "fields": {
                **{field: getattr(bundle, field) for field in V1_FIELDS},
                "action": bundle.action,
            },
        }
    )


class TestFrozenVoicePlaneAPI:
    def test_writer_is_keyword_only_and_takes_no_action_argument(self) -> None:
        writer = _require_voice_api("put_voice_source_bundle_v2")
        params = inspect.signature(writer).parameters

        assert tuple(params) == ("bundle", "conn"), tuple(params)
        assert all(
            param.kind is inspect.Parameter.KEYWORD_ONLY for param in params.values()
        )
        assert "action" not in params

    def test_reader_is_keyword_only_and_bound_to_source_ref_hash(self) -> None:
        reader = _require_voice_api("read_voice_source_bundle")
        params = inspect.signature(reader).parameters

        assert tuple(params) == ("source_ref_hash", "conn"), tuple(params)
        assert all(
            param.kind is inspect.Parameter.KEYWORD_ONLY for param in params.values()
        )


class TestV2VoicePersistence:
    def test_writer_persists_only_in_the_v2_voice_table(self, tmp_path: Path) -> None:
        store = _migrated_store(tmp_path)
        writer = _require_voice_api("put_voice_source_bundle_v2")
        bundle = _voice_bundle(seed="v2-only")

        with store.anchored_transaction() as conn:
            assert writer(bundle=bundle, conn=conn) is None

        assert _count(store.db_path, V2_VOICE) == 1
        assert _count(store.db_path, V1_VOICE) == 0

    def test_stored_row_takes_action_and_schema_from_the_bundle(
        self, tmp_path: Path
    ) -> None:
        store = _migrated_store(tmp_path)
        writer = _require_voice_api("put_voice_source_bundle_v2")
        bundle = _voice_bundle(seed="stored-authority", action=SIBLING_ACTION)

        with store.anchored_transaction() as conn:
            assert writer(bundle=bundle, conn=conn) is None
        with contextlib.closing(sqlite3.connect(store.db_path)) as conn:
            row = conn.execute(
                f"SELECT action, schema_version FROM {V2_VOICE} "
                "WHERE source_ref_hash = ?",
                (bundle.source_ref_hash,),
            ).fetchone()

        assert row == (bundle.action, V2_SCHEMA)

    def test_read_back_selects_the_exact_source_ref_and_returns_v2(
        self, tmp_path: Path
    ) -> None:
        store = _migrated_store(tmp_path)
        writer = _require_voice_api("put_voice_source_bundle_v2")
        reader = _require_voice_api("read_voice_source_bundle")
        wanted = _voice_bundle(seed="wanted")
        neighbour = _voice_bundle(seed="neighbour", action=SIBLING_ACTION)

        with store.anchored_transaction() as conn:
            writer(bundle=wanted, conn=conn)
            writer(bundle=neighbour, conn=conn)
        with store.anchored_transaction() as conn:
            read_back, version = reader(
                source_ref_hash=wanted.source_ref_hash,
                conn=conn,
            )

        assert version == V2_SCHEMA
        assert read_back == wanted
        assert read_back.source_ref_hash == wanted.source_ref_hash
        assert read_back.action == ACTION
        assert read_back != neighbour


class TestVoicePlaneRefusals:
    def test_frozen_legacy_insert_aborts_and_leaves_the_table_empty(
        self, tmp_path: Path
    ) -> None:
        """Witness INSERT only; empty-table UPDATE/DELETE would be vacuous."""
        store = _migrated_store(tmp_path)
        with contextlib.closing(sqlite3.connect(store.db_path)) as conn:
            with pytest.raises(sqlite3.IntegrityError, match="s7_vb_v1_frozen"):
                _insert(conn, V1_VOICE, _legacy_row(seed="legacy-frozen"))
        assert _count(store.db_path, V1_VOICE) == 0

    def test_v2_write_succeeds_on_the_migrated_store(self, tmp_path: Path) -> None:
        store = _migrated_store(tmp_path)
        writer = _require_voice_api("put_voice_source_bundle_v2")
        bundle = _voice_bundle(seed="v2-control")
        with store.anchored_transaction() as conn:
            writer(bundle=bundle, conn=conn)
        assert _count(store.db_path, V2_VOICE) == 1
        assert _count(store.db_path, V1_VOICE) == 0

    def test_v2_writer_refuses_a_plain_connection(self, tmp_path: Path) -> None:
        store = _migrated_store(tmp_path)
        writer = _require_voice_api("put_voice_source_bundle_v2")
        bundle = _voice_bundle(seed="plain-writer-refused")

        with contextlib.closing(sqlite3.connect(store.db_path)) as conn:
            with pytest.raises(ValueError, match="store-vended"):
                writer(bundle=bundle, conn=conn)
        assert _count(store.db_path, V2_VOICE) == 0

        # CONTROL: the same complete bundle succeeds through the activated
        # transaction this store vends.
        with store.anchored_transaction() as conn:
            writer(bundle=bundle, conn=conn)
        assert _count(store.db_path, V2_VOICE) == 1

    def test_v2_reader_refuses_a_plain_connection(self, tmp_path: Path) -> None:
        store = _migrated_store(tmp_path)
        writer = _require_voice_api("put_voice_source_bundle_v2")
        reader = _require_voice_api("read_voice_source_bundle")
        bundle = _voice_bundle(seed="plain-reader-refused")
        with store.anchored_transaction() as conn:
            writer(bundle=bundle, conn=conn)

        with contextlib.closing(sqlite3.connect(store.db_path)) as conn:
            with pytest.raises(ValueError, match="store-vended"):
                reader(source_ref_hash=bundle.source_ref_hash, conn=conn)

        # CONTROL: the activated read returns the exact durable v2 bundle.
        with store.anchored_transaction() as conn:
            read_back, version = reader(
                source_ref_hash=bundle.source_ref_hash,
                conn=conn,
            )
        assert version == V2_SCHEMA
        assert read_back == bundle

    def test_reader_keeps_v1_audit_only_when_v2_is_absent(
        self, tmp_path: Path
    ) -> None:
        store = fresh_store(tmp_path)

        # This is deliberately an UNMIGRATED legacy-audit fixture.  The v18
        # execution witness above is the migrated same-store route; this row
        # exists only to prove that a readable v1 record is not a fallback
        # execution permission when v2 is absent.
        guarded.S7VoiceConsultationBundleStore(store.db_path)
        legacy = _sealed_legacy_row(seed="v1-audit")
        with contextlib.closing(sqlite3.connect(store.db_path)) as conn:
            _insert(conn, V1_VOICE, legacy)
            conn.commit()
        assert V2_VOICE not in _tables(store.db_path)
        assert _count(store.db_path, V1_VOICE) == 1

        reader = _require_voice_api("read_voice_source_bundle")
        validator = _require_voice_api("validate_voice_source_bundle")
        with contextlib.closing(sqlite3.connect(store.db_path)) as conn:
            read_back, version = reader(
                source_ref_hash=str(legacy["source_ref_hash"]),
                conn=conn,
            )
        assert version == V1_SCHEMA

        audit = validator(bundle=read_back, version=version, purpose="audit")
        execution = validator(
            bundle=read_back,
            version=version,
            purpose="execution",
        )
        assert audit.source_bundle_valid is True
        assert audit.schema_version == V1_SCHEMA
        assert audit.action is None
        assert audit.mint_eligible is False
        assert execution.schema_version == V1_SCHEMA
        assert execution.action is None
        assert execution.mint_eligible is False


class TestVoicePlaneDefenceInDepth:
    def test_v2_exclusion_trigger_refuses_an_unreachable_v1_collision(
        self, tmp_path: Path
    ) -> None:
        """Raw-SQL alarm for a defence-in-depth, production-unreachable state.

        Migration requires the voice plane absent, creates v1 empty, and
        freezes it in the same transaction.  Production therefore cannot
        create this collision.  The disposable fixture must disable the v1
        INSERT freeze solely to construct it; this is not a writer-API route.
        """
        store = _migrated_store(tmp_path)
        collision_source_ref = _hex("collision:source-ref")
        control = {
            **_legacy_row(seed="fresh-control"),
            "action": ACTION,
            "schema_version": V2_SCHEMA,
        }
        collision = {
            **_legacy_row(
                seed="collision-v2",
                source_ref_hash=collision_source_ref,
            ),
            "action": ACTION,
            "schema_version": V2_SCHEMA,
        }

        with contextlib.closing(sqlite3.connect(store.db_path)) as conn:
            exclusion_trigger = conn.execute(
                "SELECT sql FROM sqlite_master "
                "WHERE type = 'trigger' AND name = 's7_vb_v2_no_v1'"
            ).fetchone()
            assert exclusion_trigger is not None and exclusion_trigger[0]
            freeze_trigger = conn.execute(
                "SELECT sql FROM sqlite_master "
                "WHERE type = 'trigger' AND name = 's7_vb_v1_frozen_insert'"
            ).fetchone()
            assert freeze_trigger is not None and freeze_trigger[0]
            conn.execute("DROP TRIGGER s7_vb_v1_frozen_insert")
            _insert(
                conn,
                V1_VOICE,
                _legacy_row(
                    seed="collision-legacy",
                    source_ref_hash=collision_source_ref,
                ),
            )
            conn.execute(str(freeze_trigger[0]))

            # CONTROL: the complete v2 row shape remains writable for a
            # source_ref_hash absent from v1, so the collision cannot pass
            # merely because every raw insert refuses.
            _insert(conn, V2_VOICE, control)
            with pytest.raises(
                sqlite3.IntegrityError,
                match="s7_cross_version_bundle",
            ):
                _insert(conn, V2_VOICE, collision)
            conn.commit()

        assert _count(store.db_path, V2_VOICE) == 1
        with contextlib.closing(sqlite3.connect(store.db_path)) as conn:
            assert conn.execute(
                f"SELECT source_ref_hash FROM {V2_VOICE}"
            ).fetchone() == (control["source_ref_hash"],)


class TestV2VoiceValidation:
    def test_writer_reader_validator_chain_binds_bundle_action_and_binding_hash(
        self, tmp_path: Path
    ) -> None:
        store = _migrated_store(tmp_path)
        writer = _require_voice_api("put_voice_source_bundle_v2")
        reader = _require_voice_api("read_voice_source_bundle")
        validator = _require_voice_api("validate_voice_source_bundle")
        result_type = _require_voice_api("S7VoiceSourceBundleValidationResultV2")
        written = _voice_bundle(seed="validation")

        with store.anchored_transaction() as conn:
            writer(bundle=written, conn=conn)
        with store.anchored_transaction() as conn:
            read_back, version = reader(
                source_ref_hash=written.source_ref_hash,
                conn=conn,
            )
            validation = validator(
                bundle=read_back,
                version=version,
                purpose="execution",
            )

        assert read_back == written
        assert isinstance(validation, result_type)
        assert validation.status == "valid_absent"
        assert validation.source_bundle_valid is True
        assert validation.mint_eligible is True
        assert validation.authority_projection == "valid_absent"
        assert validation.failure_reason_code is None
        assert validation.schema_version == V2_SCHEMA
        assert validation.action == written.action == ACTION
        assert validation.source_bundle_hash == written.source_bundle_hash
        assert validation.binding_hash == _v2_binding_hash(written)

    def test_writer_reader_validator_result_is_frozen(self, tmp_path: Path) -> None:
        store = _migrated_store(tmp_path)
        writer = _require_voice_api("put_voice_source_bundle_v2")
        reader = _require_voice_api("read_voice_source_bundle")
        validator = _require_voice_api("validate_voice_source_bundle")
        written = _voice_bundle(seed="frozen-result")

        with store.anchored_transaction() as conn:
            writer(bundle=written, conn=conn)
        with store.anchored_transaction() as conn:
            read_back, version = reader(
                source_ref_hash=written.source_ref_hash,
                conn=conn,
            )
            validation = validator(
                bundle=read_back,
                version=version,
                purpose="execution",
            )

        for field_name, replacement in (
            ("action", SIBLING_ACTION),
            ("source_bundle_hash", _hex("replacement-source-bundle")),
            ("binding_hash", _hex("replacement-binding")),
        ):
            with pytest.raises(FrozenInstanceError):
                setattr(validation, field_name, replacement)

    def test_v2_validation_result_cannot_be_caller_forged(self) -> None:
        result_type = _require_voice_api("S7VoiceSourceBundleValidationResultV2")

        with pytest.raises(ValueError, match="^s7_validation_result_forged$"):
            result_type(
                status="valid_absent",
                source_bundle_valid=True,
                mint_eligible=True,
                authority_projection="valid_absent",
                failure_reason_code=None,
                action=ACTION,
                schema_version=V2_SCHEMA,
                source_bundle_hash=_hex("forged-source-bundle"),
                binding_hash=_hex("forged-binding"),
            )
