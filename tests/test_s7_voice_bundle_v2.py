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
import copy
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
from core.governance import anchored_io as s7_io
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


def _voice_bundle(
    *,
    seed: str,
    action: str = ACTION,
    capture_root: Path | None = None,
):
    """Build the v2 carrier only after the missing API seam is explicit."""
    names = {field.name for field in dataclass_fields(guarded.S7VoiceConsultationBundle)}
    assert "action" in names, (
        "S7VoiceConsultationBundle has no action field; v2 persistence cannot "
        "take authority from bundle.action"
    )
    request_id = f"req-{seed}"
    consultation_id = f"voice-{seed}"
    response_capture_receipt = None
    if type(action) is str and action == ACTION:
        assert capture_root is not None, "cutover fixtures require durable response root"
        raw_response = f"{seed}:raw-response".encode()
        raw_response_ref = f"responses/{_hex(f'{seed}:raw-response')}.bin"
        raw_response_hash = hashlib.sha256(raw_response).hexdigest()
        semantic_reader_attempt_hash = None
        capture_root.mkdir(parents=True)
        (capture_root / Path(raw_response_ref).parent).mkdir(parents=True)
        s7_io.write_private_file(
            raw_response_ref,
            raw_response,
            root=capture_root,
        )
        response_capture_receipt = guarded.produce_s7_response_capture_receipt(
            request_id=request_id,
            consultation_id=consultation_id,
            attempt_identity=_hex(f"{seed}:attempt"),
            raw_response_ref=raw_response_ref,
            raw_response_bytes=raw_response,
            captured_at="2099-08-11T11:59:00Z",
            response_root=capture_root,
            expected_uid=os.getuid(),
        )
    else:
        raw_response_ref = f"raw-response-{seed}"
        raw_response_hash = _hex(f"{seed}:raw-response")
        semantic_reader_attempt_hash = _hex(f"{seed}:semantic-reader")
    bundle = guarded.S7VoiceConsultationBundle(
        source_ref_hash=_hex(f"{seed}:source-ref"),
        request_id=request_id,
        consultation_id=consultation_id,
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
        raw_response_ref=raw_response_ref,
        raw_response_hash=raw_response_hash,
        semantic_reader_attempt_hash=semantic_reader_attempt_hash,
        expires_at="2099-08-11T12:00:00Z",
        authority_class="none",
        has_grounded_semantic_blocking_signal=False,
        source_bundle_hash=None,
        response_capture_receipt=response_capture_receipt,
        action=action,
    )
    return replace(
        bundle,
        source_bundle_hash=guarded.s7_voice_consultation_bundle_hash(bundle),
    )


def _reseal_voice_bundle(bundle, **changes):
    unsealed = replace(bundle, source_bundle_hash=None, **changes)
    return replace(
        unsealed,
        source_bundle_hash=guarded.s7_voice_consultation_bundle_hash(unsealed),
    )


def _r9_cutover_bundle(*, seed: str, capture_root: Path):
    return _voice_bundle(
        seed=seed,
        action=ACTION,
        capture_root=capture_root,
    )


def _validate_written_voice_bundle(root: Path, bundle):
    root.mkdir()
    store = _migrated_store(root)
    writer = _require_voice_api("put_voice_source_bundle_v2")
    reader = _require_voice_api("read_voice_source_bundle")
    validator = _require_voice_api("validate_voice_source_bundle")

    with store.anchored_transaction() as conn:
        writer(bundle=bundle, conn=conn)
    with store.anchored_transaction() as conn:
        read_back, version = reader(
            source_ref_hash=bundle.source_ref_hash,
            conn=conn,
        )
        return validator(
            bundle=read_back,
            version=version,
            purpose="execution",
        )


def _validate_after_in_memory_evidence_mutation(
    root: Path,
    bundle,
    *,
    field_name: str,
    replacement,
):
    """Reach one validator predicate after the durable read provenance gate."""

    root.mkdir()
    store = _migrated_store(root)
    writer = _require_voice_api("put_voice_source_bundle_v2")
    reader = _require_voice_api("read_voice_source_bundle")
    validator = _require_voice_api("validate_voice_source_bundle")

    with store.anchored_transaction() as conn:
        writer(bundle=bundle, conn=conn)
    with store.anchored_transaction() as conn:
        read_back, version = reader(
            source_ref_hash=bundle.source_ref_hash,
            conn=conn,
        )
        # Normal construction rejects half-pairs and malformed hashes before
        # validation. Mutate this in-memory read-back to reach the consuming
        # rail. For R9 ref/hash mutations, coordinate and reseal the typed
        # receipt too; otherwise its stale join would refuse for the wrong
        # reason and the named common predicate would not bite independently.
        object.__setattr__(read_back, field_name, replacement)
        receipt = read_back.response_capture_receipt
        if (
            type(receipt) is guarded.S7ResponseCaptureReceipt
            and type(replacement) is str
            and field_name in {"raw_response_ref", "raw_response_hash"}
        ):
            coordinated = copy.copy(receipt)
            receipt_field = (
                "raw_response_ref"
                if field_name == "raw_response_ref"
                else "raw_response_sha256"
            )
            object.__setattr__(coordinated, receipt_field, replacement)
            object.__setattr__(
                coordinated,
                "binding_sha256",
                guarded._response_capture_receipt_binding_sha256(
                    request_id=coordinated.request_id,
                    consultation_id=coordinated.consultation_id,
                    attempt_identity=coordinated.attempt_identity,
                    raw_response_ref=coordinated.raw_response_ref,
                    raw_response_sha256=coordinated.raw_response_sha256,
                    captured_at=coordinated.captured_at,
                ),
            )
            object.__setattr__(
                read_back,
                "response_capture_receipt",
                coordinated,
            )
        object.__setattr__(
            read_back,
            "source_bundle_hash",
            guarded.s7_voice_consultation_bundle_hash(read_back),
        )
        return validator(
            bundle=read_back,
            version=version,
            purpose="execution",
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
    """Independent transcription of the v2 sealed binding recipe."""
    fields = {
        **{field: getattr(bundle, field) for field in V1_FIELDS},
        "action": bundle.action,
    }
    if bundle.response_capture_receipt is not None:
        fields["response_capture_receipt"] = (
            bundle.response_capture_receipt.as_dict()
        )
    return s7.canonical_hash(
        {
            "schema": V2_SCHEMA,
            "fields": fields,
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
    def test_r9_capture_receipt_round_trips_and_changes_the_bundle_hash(
        self, tmp_path: Path
    ) -> None:
        names = {
            field.name for field in dataclass_fields(guarded.S7VoiceConsultationBundle)
        }
        assert "response_capture_receipt" in names, (
            "the consultation bundle has no distinct R9 capture-receipt field"
        )
        bundle = _r9_cutover_bundle(
            seed="capture-roundtrip",
            capture_root=tmp_path / "capture",
        )
        store = _migrated_store(tmp_path)
        writer = _require_voice_api("put_voice_source_bundle_v2")
        reader = _require_voice_api("read_voice_source_bundle")

        with store.anchored_transaction() as conn:
            writer(bundle=bundle, conn=conn)
        with store.anchored_transaction() as conn:
            read_back, version = reader(
                source_ref_hash=bundle.source_ref_hash,
                conn=conn,
            )

        without_receipt = replace(
            bundle,
            response_capture_receipt=None,
            source_bundle_hash=None,
        )
        assert version == V2_SCHEMA
        assert read_back == bundle
        assert type(read_back.response_capture_receipt) is guarded.S7ResponseCaptureReceipt
        assert guarded.s7_voice_consultation_bundle_hash(without_receipt) != (
            bundle.source_bundle_hash
        )

    @pytest.mark.parametrize(
        "existing_value",
        (
            pytest.param("raw_response_hash", id="response-hash-is-not-a-receipt"),
            pytest.param("attempt_receipt_ref", id="receipt-ref-is-not-a-receipt"),
        ),
    )
    def test_capture_receipt_field_refuses_existing_bundle_values(
        self, tmp_path: Path, existing_value: str
    ) -> None:
        control = _r9_cutover_bundle(
            seed=f"anti-relabelling-{existing_value}",
            capture_root=tmp_path / "capture",
        )
        replacement = (
            control.raw_response_hash
            if existing_value == "raw_response_hash"
            else "attempts/fixture.terminal.json"
        )

        assert type(control.response_capture_receipt) is guarded.S7ResponseCaptureReceipt
        accepted = _validate_written_voice_bundle(tmp_path / "control", control)
        assert accepted.status == "valid_absent"
        assert accepted.source_bundle_valid is True
        assert accepted.mint_eligible is True
        with pytest.raises(
            ValueError,
            match="response_capture_receipt must be S7ResponseCaptureReceipt",
        ):
            replace(control, response_capture_receipt=replacement)

    def test_writer_persists_only_in_the_v2_voice_table(self, tmp_path: Path) -> None:
        store = _migrated_store(tmp_path)
        writer = _require_voice_api("put_voice_source_bundle_v2")
        bundle = _voice_bundle(
            seed="v2-only",
            capture_root=tmp_path / "capture",
        )

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
        wanted = _voice_bundle(
            seed="wanted",
            capture_root=tmp_path / "capture",
        )
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
        bundle = _voice_bundle(
            seed="v2-control",
            capture_root=tmp_path / "capture",
        )
        with store.anchored_transaction() as conn:
            writer(bundle=bundle, conn=conn)
        assert _count(store.db_path, V2_VOICE) == 1
        assert _count(store.db_path, V1_VOICE) == 0

    def test_v2_writer_refuses_a_plain_connection(self, tmp_path: Path) -> None:
        store = _migrated_store(tmp_path)
        writer = _require_voice_api("put_voice_source_bundle_v2")
        bundle = _voice_bundle(
            seed="plain-writer-refused",
            capture_root=tmp_path / "capture",
        )

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
        bundle = _voice_bundle(
            seed="plain-reader-refused",
            capture_root=tmp_path / "capture",
        )
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
    def test_r9_cutover_requires_capture_receipt_even_when_reader_hash_exists(
        self, tmp_path: Path
    ) -> None:
        complete = _reseal_voice_bundle(
            _r9_cutover_bundle(
                seed="capture-required",
                capture_root=tmp_path / "capture",
            ),
            semantic_reader_attempt_hash=_hex("capture-required:obsolete-reader"),
        )
        relabelled = _reseal_voice_bundle(
            complete,
            response_capture_receipt=None,
        )

        refused = _validate_written_voice_bundle(tmp_path / "refused", relabelled)
        control = _validate_written_voice_bundle(tmp_path / "control", complete)

        assert control.status == "valid_absent"
        assert control.mint_eligible is True
        assert refused.status == "source_bundle_unavailable"
        assert refused.source_bundle_valid is False
        assert refused.mint_eligible is False
        assert refused.failure_reason_code == "source_bundle_unavailable"

    def test_r9_cutover_capture_receipt_needs_no_reader_attempt(
        self, tmp_path: Path
    ) -> None:
        complete = _r9_cutover_bundle(
            seed="reader-abolished",
            capture_root=tmp_path / "capture",
        )

        control = _validate_written_voice_bundle(tmp_path / "control", complete)

        assert complete.semantic_reader_attempt_hash is None
        assert control.status == "valid_absent"
        assert control.source_bundle_valid is True
        assert control.mint_eligible is True

    @pytest.mark.parametrize(
        ("field_name", "replacement"),
        (
            pytest.param(
                "raw_response_ref",
                "",
                id="r9-response-ref-is-required",
            ),
            pytest.param(
                "raw_response_hash",
                "not-a-sha256-digest",
                id="r9-response-hash-must-be-well-formed",
            ),
            pytest.param(
                "raw_response_hash",
                hashlib.sha256(b"").hexdigest(),
                id="r9-empty-byte-response-hash-is-refused",
            ),
            pytest.param(
                "response_capture_receipt",
                None,
                id="r9-capture-receipt-is-required",
            ),
        ),
    )
    def test_r9_each_content_blind_rail_requirement_bites_independently(
        self,
        tmp_path: Path,
        field_name: str,
        replacement: object,
    ) -> None:
        complete = _r9_cutover_bundle(
            seed=f"rail-{field_name}-{replacement}",
            capture_root=tmp_path / "capture",
        )

        refused = _validate_after_in_memory_evidence_mutation(
            tmp_path / "refused",
            complete,
            field_name=field_name,
            replacement=replacement,
        )
        control = _validate_written_voice_bundle(tmp_path / "control", complete)

        assert control.status == "valid_absent"
        assert control.source_bundle_valid is True
        assert control.mint_eligible is True
        assert refused.status == "source_bundle_unavailable"
        assert refused.source_bundle_valid is False
        assert refused.mint_eligible is False
        assert refused.failure_reason_code == "source_bundle_unavailable"

    def test_non_cutover_reader_requirement_cannot_be_replaced_by_capture_receipt(
        self, tmp_path: Path
    ) -> None:
        control = _voice_bundle(seed="sibling-reader", action=SIBLING_ACTION)
        response = b"sibling-reader:raw-response"
        capture_root = tmp_path / "capture"
        capture_root.mkdir()
        s7_io.write_private_file(
            str(control.raw_response_ref),
            response,
            root=capture_root,
        )
        receipt = guarded.produce_s7_response_capture_receipt(
            request_id=control.request_id,
            consultation_id=control.consultation_id,
            attempt_identity=_hex("sibling-reader:attempt"),
            raw_response_ref=str(control.raw_response_ref),
            raw_response_bytes=response,
            captured_at="2099-08-11T11:59:00Z",
            response_root=capture_root,
            expected_uid=os.getuid(),
        )
        capture_only = _reseal_voice_bundle(
            control,
            semantic_reader_attempt_hash=None,
            response_capture_receipt=receipt,
        )

        refused = _validate_written_voice_bundle(tmp_path / "refused", capture_only)
        accepted = _validate_written_voice_bundle(tmp_path / "control", control)

        assert accepted.status == "valid_absent"
        assert accepted.mint_eligible is True
        assert refused.status == "source_bundle_unavailable"
        assert refused.source_bundle_valid is False
        assert refused.mint_eligible is False

    def test_r9_capture_receipt_seal_is_revalidated_at_the_consuming_rail(
        self, tmp_path: Path
    ) -> None:
        complete = _r9_cutover_bundle(
            seed="capture-seal",
            capture_root=tmp_path / "capture",
        )
        store = _migrated_store(tmp_path / "refused")
        writer = _require_voice_api("put_voice_source_bundle_v2")
        reader = _require_voice_api("read_voice_source_bundle")
        validator = _require_voice_api("validate_voice_source_bundle")

        with store.anchored_transaction() as conn:
            writer(bundle=complete, conn=conn)
        with store.anchored_transaction() as conn:
            read_back, version = reader(
                source_ref_hash=complete.source_ref_hash,
                conn=conn,
            )
            tampered = copy.copy(read_back.response_capture_receipt)
            object.__setattr__(tampered, "binding_sha256", "0" * 64)
            object.__setattr__(read_back, "response_capture_receipt", tampered)
            object.__setattr__(
                read_back,
                "source_bundle_hash",
                guarded.s7_voice_consultation_bundle_hash(read_back),
            )
            refused = validator(
                bundle=read_back,
                version=version,
                purpose="execution",
            )

        control = _validate_written_voice_bundle(tmp_path / "control", complete)

        assert control.status == "valid_absent"
        assert control.mint_eligible is True
        assert refused.status == "source_bundle_unavailable"
        assert refused.source_bundle_valid is False
        assert refused.mint_eligible is False

    @pytest.mark.parametrize(
        "evidence_changes",
        (
            pytest.param(
                {"raw_response_ref": None, "raw_response_hash": None},
                id="missing-raw-response",
            ),
            pytest.param(
                {"raw_response_hash": s7.canonical_hash("")},
                id="empty-raw-response",
            ),
            pytest.param(
                {"semantic_reader_attempt_hash": None},
                id="missing-semantic-reader-attempt",
            ),
        ),
    )
    def test_validator_blocks_without_response_and_read_attempt_evidence(
        self,
        tmp_path: Path,
        evidence_changes: dict[str, object],
    ) -> None:
        complete = _voice_bundle(
            seed="evidence-join",
            action=SIBLING_ACTION,
        )
        incomplete = _reseal_voice_bundle(complete, **evidence_changes)

        refused = _validate_written_voice_bundle(tmp_path / "refused", incomplete)
        control = _validate_written_voice_bundle(tmp_path / "control", complete)

        # POSITIVE CONTROL: the same base fixture, with all three pieces of
        # content-blind evidence present, still reaches the normal success.
        assert control.status == "valid_absent"
        assert control.source_bundle_valid is True
        assert control.mint_eligible is True
        assert control.authority_projection == "valid_absent"
        assert control.failure_reason_code is None

        assert refused.status == "source_bundle_unavailable"
        assert refused.source_bundle_valid is False
        assert refused.mint_eligible is False
        assert refused.authority_projection == "unavailable"
        assert refused.failure_reason_code == "source_bundle_unavailable"

    @pytest.mark.parametrize(
        ("field_name", "replacement"),
        (
            pytest.param(
                "raw_response_ref",
                None,
                id="missing-raw-response-ref",
            ),
            pytest.param(
                "raw_response_ref",
                "",
                id="empty-raw-response-ref",
            ),
            pytest.param(
                "raw_response_hash",
                None,
                id="missing-raw-response-hash",
            ),
            pytest.param(
                "raw_response_hash",
                "not-a-sha256-digest",
                id="malformed-raw-response-hash",
            ),
            pytest.param(
                "semantic_reader_attempt_hash",
                "not-a-sha256-digest",
                id="malformed-semantic-reader-attempt-hash",
            ),
        ),
    )
    def test_validator_checks_each_response_evidence_field_independently(
        self,
        tmp_path: Path,
        field_name: str,
        replacement: object,
    ) -> None:
        complete = _voice_bundle(
            seed="independent-evidence-check",
            action=SIBLING_ACTION,
        )

        refused = _validate_after_in_memory_evidence_mutation(
            tmp_path / "refused",
            complete,
            field_name=field_name,
            replacement=replacement,
        )
        control = _validate_written_voice_bundle(tmp_path / "control", complete)

        assert control.status == "valid_absent"
        assert control.source_bundle_valid is True
        assert control.mint_eligible is True
        assert control.authority_projection == "valid_absent"
        assert control.failure_reason_code is None

        assert refused.status == "source_bundle_unavailable"
        assert refused.source_bundle_valid is False
        assert refused.mint_eligible is False
        assert refused.authority_projection == "unavailable"
        assert refused.failure_reason_code == "source_bundle_unavailable"

    def test_writer_reader_validator_chain_binds_bundle_action_and_binding_hash(
        self, tmp_path: Path
    ) -> None:
        store = _migrated_store(tmp_path)
        writer = _require_voice_api("put_voice_source_bundle_v2")
        reader = _require_voice_api("read_voice_source_bundle")
        validator = _require_voice_api("validate_voice_source_bundle")
        result_type = _require_voice_api("S7VoiceSourceBundleValidationResultV2")
        written = _voice_bundle(
            seed="validation",
            capture_root=tmp_path / "capture",
        )

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
        written = _voice_bundle(
            seed="frozen-result",
            capture_root=tmp_path / "capture",
        )

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
