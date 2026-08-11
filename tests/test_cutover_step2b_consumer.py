"""Cutover step 2B — the consumer primitive.

Written against ratified design v32 and its R8/R9 recorded-consultation ruling.

Slice 1 covers the contracts that are unambiguous from the frozen design
and testable without a live S7 ceremony: the receipt's v2 shape, the
action contract measured against the real classifier, the grant
projection, the store opener's refusals, the consultation producer's
recorded-unjudged exchange behavior, and the burn's structural adjacency.

Deliberately NOT here: a full end-to-end ceremony. It needs a founder
WebAuthn assertion, which cannot be produced without a physical key tap.
Asserting one exists would be the fabrication this project refuses.

Expected pre-implementation failure taxonomy:

* ActionContract   -> CUTOVER_ACTION / CUTOVER_ACTION_PARAMS absent.
* ReceiptV2        -> the two presence fields do not exist yet.
* GrantProjection  -> the projection helper and schema literal are absent.
* StoreOpener      -> open_existing_authorization_store is absent.
* Consultation     -> implemented as a real ask with exact-byte evidence.
* BurnStructure    -> publish_and_validate_burn / prepare_cutover absent.
* NoFallback       -> a GUARD: `procedural` must be unreachable for
  cutover, asserted on the closed value set.
"""

from __future__ import annotations

import ast
import hashlib
import inspect
import json
import os
import sqlite3
import textwrap
from contextlib import closing
from dataclasses import fields as dataclass_fields, replace
from pathlib import Path

import pytest

from core.governance import operator_user_boundary as s7
from core.governance import anchored_io as s7_io
from core.governance import s7_guarded_execution as guarded
from core.governance import s7_v2_migration
from core.governance.operator_user_boundary import (
    build_cutover_work_request_envelope,
)
from scripts import cuda_cutover as cutover
from scripts import cuda_migration as cm

REPO = Path(__file__).resolve().parents[1]
FIXTURE_PRECONDITION_HASH = s7.canonical_hash(
    {"fixture": "expired-cutover-action-contract-v1"}
)
FIXTURE_CUTOVER_AFFECTED_REFS = (
    "file:/home/rohit/.config/systemd/user/llama-server.service.d/zz-b9596-cuda.conf",
    "service:llama-server.service",
)
FIXTURE_AUTHORITY_CONTEXT_HASH = s7.canonical_hash(
    {"fixture": "founder-authority-context"}
)
FIXTURE_RUNTIME_IDENTITY_HASH = s7.canonical_hash(
    {"fixture": "bonded-runtime-identity"}
)
FIXTURE_RUNTIME_SOURCE_REF = "bonded-runtime:fixture-primary"


class _RecordingBondedAsk:
    capability_kind = "bonded_runtime_voice"

    def __init__(
        self,
        *,
        envelope: s7.WorkRequestEnvelope,
        attempt,
        response: object = b"opaque bonded response",
        failure: Exception | None = None,
        authority_context_hash: str = FIXTURE_AUTHORITY_CONTEXT_HASH,
        runtime_identity_hash: str = FIXTURE_RUNTIME_IDENTITY_HASH,
        runtime_source_ref: str = FIXTURE_RUNTIME_SOURCE_REF,
    ) -> None:
        self.request_id = envelope.request_id
        self.request_envelope_hash = s7.work_request_envelope_hash(envelope)
        self.action = envelope.action
        self.action_params_hash = s7.canonical_hash(dict(cm.CUTOVER_ACTION_PARAMS))
        self.precondition_hash = envelope.precondition_hash
        self.authority_context_hash = authority_context_hash
        self.runtime_identity_hash = runtime_identity_hash
        self.runtime_source_ref = runtime_source_ref
        self.attempt = attempt
        self.response = response
        self.failure = failure
        self.calls: list[str] = []
        self.start_was_persisted_before_ask = False

    def __call__(self, question: str) -> object:
        self.calls.append(question)
        try:
            start = s7_io.read_private_file(
                self.attempt.start_receipt_ref,
                root=self.attempt.receipt_root,
                expected_uid=os.getuid(),
            )
            self.start_was_persisted_before_ask = (
                json.loads(start)["fields"]["outcome"] == "attempt_started"
            )
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
            self.start_was_persisted_before_ask = False
        if self.failure is not None:
            raise self.failure
        return self.response


def _consultation_fixture(
    tmp_path: Path,
    *,
    response: object = b"opaque bonded response",
    failure: Exception | None = None,
    request_id: str = "fixture-cutover-consultation-v1",
    precondition_hash: str = FIXTURE_PRECONDITION_HASH,
    authority_context_hash: str = FIXTURE_AUTHORITY_CONTEXT_HASH,
    runtime_identity_hash: str = FIXTURE_RUNTIME_IDENTITY_HASH,
    runtime_source_ref: str = FIXTURE_RUNTIME_SOURCE_REF,
):
    receipt_root = tmp_path / "consultation-receipts"
    receipt_root.mkdir(exist_ok=True)
    attempt = cutover.ConsultationAttempt.fresh(
        request_id=request_id,
        receipt_root=receipt_root,
    )
    envelope = build_cutover_work_request_envelope(
        request_id=request_id,
        action=cm.CUTOVER_ACTION,
        params=dict(cm.CUTOVER_ACTION_PARAMS),
        affected_refs=FIXTURE_CUTOVER_AFFECTED_REFS,
        precondition_hash=precondition_hash,
        created_at="2000-01-01T00:00:00Z",
        expires_at="2000-01-01T04:00:00Z",
        maez_voice_consultation_id=attempt.consultation_id,
    )
    ask = _RecordingBondedAsk(
        envelope=envelope,
        attempt=attempt,
        response=response,
        failure=failure,
        authority_context_hash=authority_context_hash,
        runtime_identity_hash=runtime_identity_hash,
        runtime_source_ref=runtime_source_ref,
    )
    return envelope, attempt, ask


def _assert_one_real_ask(producer, *, envelope, attempt, ask):
    before = len(ask.calls)
    result = producer(
        envelope=envelope,
        attempt=attempt,
        ask=ask,
        now="2000-01-01T00:01:00Z",
    )
    assert len(ask.calls) == before + 1, (
        "the consultation producer must invoke ask for this attempt"
    )
    return result


def _valid_existing_authorization_store(
    tmp_path: Path, *, name: str = "valid-store"
) -> Path:
    from tests.s7_store_fixture import bootstrap_with_authorization

    root = tmp_path / name
    store = bootstrap_with_authorization(root)
    dir_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        s7_v2_migration._migrate_authorization_store_to_v2_at(
            store_dir_fd=dir_fd
        )
    finally:
        os.close(dir_fd)
    return store.db_path


def _cutover_voice_gate_fixture(
    tmp_path: Path,
    *,
    name: str,
    carry_capture_receipt: bool = True,
    has_grounded_semantic_blocking_signal: bool = False,
):
    """Build one real R8/R9 result and its private durable v2 bundle."""

    fixture_root = tmp_path / name
    fixture_root.mkdir()
    envelope, attempt, ask = _consultation_fixture(fixture_root)
    result = _assert_one_real_ask(
        cutover.produce_cutover_consultation,
        envelope=envelope,
        attempt=attempt,
        ask=ask,
    )
    consultation = result.consultation
    assert consultation is not None
    assert result.response_capture_receipt is not None

    bundle = guarded.S7VoiceConsultationBundle(
        source_ref_hash=consultation.source_ref_hash,
        request_id=envelope.request_id,
        consultation_id=consultation.consultation_id,
        request_envelope_hash=s7.work_request_envelope_hash(envelope),
        rendered_text_hash=result.rendered_text_hash,
        action_params_hash=s7.canonical_hash(dict(cm.CUTOVER_ACTION_PARAMS)),
        precondition_hash=envelope.precondition_hash,
        authority_context_hash=ask.authority_context_hash,
        maez_voice_consultation_hash=s7.maez_voice_consultation_hash(consultation),
        rendered_prompt_ref="rendered-prompt:cutover-gate-fixture",
        rendered_prompt_hash="1" * 64,
        mutation_preview_hash="2" * 64,
        rollback_plan_ref="3" * 64,
        context_manifest_ref="context-manifest:cutover-gate-fixture",
        context_manifest_hash="4" * 64,
        runtime_identity_hash=ask.runtime_identity_hash,
        model_routing_identity_hash="5" * 64,
        model_config_hash="6" * 64,
        raw_response_ref=result.raw_response_ref,
        raw_response_hash=result.raw_response_sha256,
        semantic_reader_attempt_hash=None,
        expires_at=envelope.expires_at,
        authority_class="none",
        has_grounded_semantic_blocking_signal=(has_grounded_semantic_blocking_signal),
        source_bundle_hash=None,
        response_capture_receipt=(
            result.response_capture_receipt if carry_capture_receipt else None
        ),
        action=cm.CUTOVER_ACTION,
    )
    bundle = replace(
        bundle,
        source_bundle_hash=guarded.s7_voice_consultation_bundle_hash(bundle),
    )

    db_path = _valid_existing_authorization_store(
        fixture_root,
        name="authorization-store",
    )
    authorization_store = s7.S7AuthorizationStore(db_path)
    with authorization_store.anchored_transaction() as conn:
        guarded.put_voice_source_bundle_v2(bundle=bundle, conn=conn)
    guarded_store = guarded.S7GuardedStateStore(
        authorization_store=authorization_store,
    )
    return envelope, result, guarded_store


def _call_cutover_voice_gate(
    *,
    envelope,
    result,
    guarded_store,
    include_result: bool = True,
):
    """Keep the first RED at the admission assertion, not a new kwarg error."""

    from core.governance.s7_webauthn_ceremony import (
        authorization_voice_seat_recheck,
    )

    kwargs = {
        "envelope": envelope,
        "maez_voice_consultation": result.consultation,
    }
    parameters = inspect.signature(authorization_voice_seat_recheck).parameters
    optional = {
        "guarded_store": guarded_store,
        "source_ref_hash": result.consultation.source_ref_hash,
        "cutover_consultation_result": result if include_result else None,
    }
    kwargs.update({name: value for name, value in optional.items() if name in parameters})
    return authorization_voice_seat_recheck(**kwargs)


def _s7_grant_fixture(
    *, credential_ref: str = "credential-1"
) -> s7.S7ExecutionGrant:
    return s7.S7ExecutionGrant(
        artifact_id="artifact-1",
        request_id="request-1",
        request_envelope_hash="1" * 64,
        rendered_text_hash="2" * 64,
        action_params_hash="3" * 64,
        precondition_hash="4" * 64,
        authority_context_hash="5" * 64,
        action="model_routing.cutover_cuda",
        derived_work_class="self_modification",
        derived_aggregation_group="s7agg_fixture",
        nonce="nonce-1",
        credential_ref=credential_ref,
        auth_method="founder_webauthn",
        grant_source="founder_webauthn",
        consumed_at="2000-01-01T00:01:00Z",
        ceremony_kind="founder_local_webauthn",
        _mint_token=s7._EXECUTION_GRANT_TOKEN,
    )


FIXTURE_PRESENCE_EVIDENCE_SHA256 = hashlib.sha256(
    cm.s7_execution_grant_projection_bytes(_s7_grant_fixture())
).hexdigest()
FIXTURE_ALTERNATE_PRESENCE_EVIDENCE_SHA256 = hashlib.sha256(
    cm.s7_execution_grant_projection_bytes(
        _s7_grant_fixture(credential_ref="credential-2")
    )
).hexdigest()


def _cutover_consumption_fixture(
    *,
    presence_mode: str = "founder_webauthn",
    presence_evidence_sha256: str = FIXTURE_PRESENCE_EVIDENCE_SHA256,
) -> cm.CutoverConsumptionReceipt:
    return cm.CutoverConsumptionReceipt(
        authorization_file_sha256="1" * 64,
        authorization_binding_sha256="2" * 64,
        nonce="3" * 64,
        window_id="cutover-fixture",
        boot_id="fixture-boot",
        stage_two_receipt_file_sha256="4" * 64,
        stage_two_receipt_binding_sha256="5" * 64,
        presence_mode=presence_mode,
        presence_evidence_sha256=presence_evidence_sha256,
        consumed_at="2000-01-01T00:02:00Z",
    )


class TestActionContract:
    """One action literal, one params mapping, used identically everywhere."""

    def test_the_action_literal_is_frozen(self) -> None:
        assert cm.CUTOVER_ACTION == "model_routing.cutover_cuda"

    def test_the_action_alone_derives_self_modification(self) -> None:
        """R5: the honest operation NAME earns the class, not classifier bait."""
        assert (
            s7.derive_work_class(
                action=cm.CUTOVER_ACTION, params=dict(cm.CUTOVER_ACTION_PARAMS)
            )
            == "self_modification"
        )

    def test_removing_model_routing_makes_the_class_undeterminable(self) -> None:
        stripped = cm.CUTOVER_ACTION.replace("model_routing.", "")
        assert (
            s7.derive_work_class(
                action=stripped, params=dict(cm.CUTOVER_ACTION_PARAMS)
            )
            == "undeterminable_work_class"
        )

    def test_params_contain_no_ref_discarding_key(self) -> None:
        """derive_affected_refs returns ONLY the ref built from the first of
        path/file/target/cmd it finds, DISCARDING supplied refs. With any
        present, every frozen affected_ref would be silently thrown away."""
        for key in ("path", "file", "target", "cmd"):
            assert key not in cm.CUTOVER_ACTION_PARAMS, key

    def test_fixed_params_hash_is_the_canonical_mapping_hash(self) -> None:
        expected = {"cutover_action": cm.CUTOVER_ACTION}
        assert cm.CUTOVER_ACTION_PARAMS == expected
        assert (
            s7.canonical_hash(cm.CUTOVER_ACTION_PARAMS)
            == "378e391cf73648e3da262b24ab9bb4b72"
            "ab048db80e5a9ce11665e7359f84536"
        )

    def test_derivation_is_empty_so_the_real_refs_survive(self) -> None:
        """I wrote this test against the wrong seam, and it could never pass.

        It called `derive_affected_refs` directly and demanded the two real
        refs back. That function takes no supplied refs at all -- it derives
        from signed action material and has no branch for this action, so it
        returns `()`. It also returns at most ONE ref from the
        path/file/target keys, so it could not have produced two even with a
        key present, and those keys are forbidden here anyway.

        Empty is the CORRECT and intended result. `build_work_request_envelope`
        reads `trusted_refs if trusted_refs else canonical(supplied)`, so an
        empty derivation is exactly what lets the frozen refs through. A
        non-empty derivation would DISCARD them, which is the hazard the
        no-discarding-key pin exists to prevent.
        """
        assert (
            s7.derive_affected_refs(
                action=cm.CUTOVER_ACTION, params=dict(cm.CUTOVER_ACTION_PARAMS)
            )
            == ()
        )

    def test_the_envelope_carries_the_real_mutation_targets(self) -> None:
        """The frozen fields, plus refs that are SUPPLIED, not frozen.

        POSITIVE CONTROL for the test above: empty derivation is only good
        news if the supplied refs genuinely survive into the envelope. This
        asserts they do, so 'derivation is empty' cannot be mistaken for
        'no refs anywhere'.

        SCOPE, because the two halves differ. The closed values below --
        work class, subsystem, change class, exposure risk -- ARE frozen in
        the producer, and asserting them witnesses that. `affected_refs` is
        NOT: the producer takes it as a parameter and this test hands it in,
        so the ref assertion witnesses PASS-THROUGH, not that the envelope
        names the true cutover targets.

        That is deliberate rather than an omission. The refs are absolute
        paths under the owner's home directory; freezing them here would
        bake an owner-specific path into core governance, which is a worse
        defect than the one it would close. The real targets are pinned
        where they belong -- in the cutover executor's own steps -- and the
        owner does not see `affected_refs` at the tap, since the renderer
        does not project them.
        """
        env = build_cutover_work_request_envelope(
            request_id="fixture-cutover-action-contract-v1",
            action=cm.CUTOVER_ACTION,
            params=dict(cm.CUTOVER_ACTION_PARAMS),
            affected_refs=FIXTURE_CUTOVER_AFFECTED_REFS,
            precondition_hash=FIXTURE_PRECONDITION_HASH,
            created_at="2000-01-01T00:00:00Z",
            expires_at="2000-01-01T04:00:00Z",
            maez_voice_consultation_id="fixture-cutover-consultation-v1",
        )
        assert env.affected_refs == FIXTURE_CUTOVER_AFFECTED_REFS
        assert env.request_id == "fixture-cutover-action-contract-v1"
        assert env.action == cm.CUTOVER_ACTION
        assert env.claimed_work_class == "self_modification"
        assert env.derived_work_class == "self_modification"
        assert env.requesting_subsystem == "cuda_cutover"
        assert env.closed_symptom_code == "self_mod_requested"
        assert env.proposed_change_class == "model_routing_change"
        assert env.why_self_fix_failed_class == "not_self_fix"
        assert env.content_exposure_risk == "content_free"
        assert env.precondition_hash == FIXTURE_PRECONDITION_HASH
        assert env.created_at == "2000-01-01T00:00:00Z"
        assert env.expires_at == "2000-01-01T04:00:00Z"
        assert env.predicted_effect_class == "behavior_change"
        assert env.rollback_path_class == "revert_patch"
        assert (
            env.maez_voice_consultation_id
            == "fixture-cutover-consultation-v1"
        )
        assert env.free_text_ref_hash is None

    def test_cutover_producer_rejects_the_wrong_action(self) -> None:
        with pytest.raises(ValueError, match="must target"):
            build_cutover_work_request_envelope(
                request_id="fixture-cutover-action-contract-v1",
                action="model_routing.not_the_cutover",
                params=dict(cm.CUTOVER_ACTION_PARAMS),
                affected_refs=FIXTURE_CUTOVER_AFFECTED_REFS,
                precondition_hash=FIXTURE_PRECONDITION_HASH,
                created_at="2000-01-01T00:00:00Z",
                expires_at="2000-01-01T04:00:00Z",
                maez_voice_consultation_id="fixture-cutover-consultation-v1",
            )

    @pytest.mark.parametrize(
        "params",
        (
            {},
            {"cutover_action": "model_routing.not_the_cutover"},
            {
                "cutover_action": cm.CUTOVER_ACTION,
                "target": "forbidden-second-routing-target",
            },
        ),
    )
    def test_cutover_producer_rejects_non_frozen_params(
        self, params: dict[str, str]
    ) -> None:
        with pytest.raises(ValueError, match="frozen action"):
            build_cutover_work_request_envelope(
                request_id="fixture-cutover-action-contract-v1",
                action=cm.CUTOVER_ACTION,
                params=params,
                affected_refs=FIXTURE_CUTOVER_AFFECTED_REFS,
                precondition_hash=FIXTURE_PRECONDITION_HASH,
                created_at="2000-01-01T00:00:00Z",
                expires_at="2000-01-01T04:00:00Z",
                maez_voice_consultation_id="fixture-cutover-consultation-v1",
            )

    def test_cutover_producer_requires_a_consultation_id(self) -> None:
        with pytest.raises(ValueError, match="requires a Maez consultation id"):
            build_cutover_work_request_envelope(
                request_id="fixture-cutover-action-contract-v1",
                action=cm.CUTOVER_ACTION,
                params=dict(cm.CUTOVER_ACTION_PARAMS),
                affected_refs=FIXTURE_CUTOVER_AFFECTED_REFS,
                precondition_hash=FIXTURE_PRECONDITION_HASH,
                created_at="2000-01-01T00:00:00Z",
                expires_at="2000-01-01T04:00:00Z",
                maez_voice_consultation_id="",
            )


class TestConsumptionReceiptV2:
    """presence goes in the DURABLE record, not an outcome surface."""

    def test_schema_is_v2(self) -> None:
        assert cm.CUTOVER_CONSUMPTION_SCHEMA.endswith(".v2")

    def test_presence_fields_exist_and_are_bound(self) -> None:
        names = [
            f
            for f in cm.CutoverConsumptionReceipt.__dataclass_fields__
            if f != "schema_version"
        ]
        assert "presence_mode" in names
        assert "presence_evidence_sha256" in names

        founder = _cutover_consumption_fixture()
        procedural = replace(founder, presence_mode="procedural")
        different_evidence = replace(
            founder,
            presence_evidence_sha256=(
                FIXTURE_ALTERNATE_PRESENCE_EVIDENCE_SHA256
            ),
        )
        assert founder.binding_sha256 != procedural.binding_sha256
        assert founder.binding_sha256 != different_evidence.binding_sha256

    def test_active_family_count_stays_twenty_six(self) -> None:
        """A REPLACEMENT, not an addition: v1 has no durable artifact."""
        assert len(cm.ACTIVE_SCHEMA_FAMILIES) == 26
        assert cm.ACTIVE_SCHEMA_FAMILIES.count(cm.CUTOVER_CONSUMPTION_SCHEMA) == 1
        assert "cuda_migration.cutover_consumption.v1" not in (
            cm.ACTIVE_SCHEMA_FAMILIES
        )

    def test_presence_mode_is_a_closed_value(self) -> None:
        assert cm.PRESENCE_MODES == ("founder_webauthn", "procedural")
        procedural = _cutover_consumption_fixture(presence_mode="procedural")
        with pytest.raises(ValueError, match="presence_mode"):
            replace(procedural, presence_mode="fallback")
        assert procedural.presence_mode == "procedural"

    def test_cutover_may_not_emit_procedural(self) -> None:
        """Part 3: zero usable credentials REFUSES; there is no fallback."""
        assert cm.CUTOVER_PRESENCE_MODE == "founder_webauthn"
        assert "presence_no_usable_credential" in cutover.CUTOVER_REFUSALS
        source = textwrap.dedent(
            inspect.getsource(cutover.consume_cutover_authorization)
        )
        function = ast.parse(source).body[0]
        assert isinstance(function, ast.FunctionDef)
        executable = [
            statement
            for statement in function.body
            if not (
                isinstance(statement, ast.Expr)
                and isinstance(statement.value, ast.Constant)
                and isinstance(statement.value.value, str)
            )
        ]
        assert len(executable) == 1
        assert isinstance(executable[0], ast.Raise)
        assert "cuda_migration.cutover_consumption.v1" not in source


class TestGrantProjection:
    """The evidence hash must name a REPRODUCIBLE object."""

    def test_schema_literal_is_frozen(self) -> None:
        """v28: the projection reconciles to the FINAL grant shape.

        v19 froze `.v1` against a grant carrying no action and no version.
        Both exist now, so a v1 projection would attest that AN
        authorization was consumed without attesting WHICH -- the exact
        substitution S7 action-binding was built to prevent. v1 is
        audit-only and is not acceptable presence evidence.
        """
        assert (
            cm.S7_GRANT_PROJECTION_SCHEMA
            == "cuda_migration.s7_execution_grant_projection.v2"
        )

    def test_projection_covers_every_grant_field(self) -> None:
        """Seventeen (v28): the fifteen originals plus `action` and
        `schema_version`.

        The expectation is DERIVED from the dataclass rather than listed,
        so a field added to the grant and forgotten here fails instead of
        passing silently. The count is asserted separately because a
        derived-only check would agree with itself if the dataclass lost
        a field.
        """
        expected = (
            "artifact_id",
            "request_id",
            "request_envelope_hash",
            "rendered_text_hash",
            "action_params_hash",
            "precondition_hash",
            "authority_context_hash",
            "action",
            "derived_work_class",
            "derived_aggregation_group",
            "nonce",
            "credential_ref",
            "auth_method",
            "grant_source",
            "consumed_at",
            "ceremony_kind",
            "schema_version",
        )
        actual = tuple(f.name for f in dataclass_fields(s7.S7ExecutionGrant))
        assert cm.S7_GRANT_PROJECTION_FIELDS == expected == actual
        assert len(actual) == 17

    def test_the_private_mint_token_is_structurally_excluded(self) -> None:
        """_mint_token is an InitVar, so it is not a dataclass field at all
        -- the exclusion cannot be forgotten."""
        names = {f.name for f in dataclass_fields(s7.S7ExecutionGrant)}
        assert "_mint_token" not in names

    def test_projection_uses_the_existing_canonical_wrapper_encoder(self) -> None:
        grant = _s7_grant_fixture()
        expected_fields = {
            name: getattr(grant, name) for name in cm.S7_GRANT_PROJECTION_FIELDS
        }
        expected = cm._canonical_wrapper_bytes(
            {"schema": cm.S7_GRANT_PROJECTION_SCHEMA, "fields": expected_fields}
        )

        assert cm.s7_execution_grant_projection_bytes(grant) == expected
        assert expected.endswith(b"\n")

        tree = ast.parse(
            textwrap.dedent(
                inspect.getsource(cm.s7_execution_grant_projection_bytes)
            )
        )
        calls = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "_canonical_wrapper_bytes"
        ]
        assert len(calls) == 1
        assert not any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "dumps"
            for node in ast.walk(tree)
        )

    def test_projection_refuses_non_grant_with_positive_control(self) -> None:
        grant = _s7_grant_fixture()
        with pytest.raises(ValueError, match="s7_grant_projection"):
            cm.s7_execution_grant_projection_bytes(object())
        assert cm.s7_execution_grant_projection_bytes(grant).endswith(b"\n")

    def test_sixteen_row_backed_fields_join_the_v2_writer(self) -> None:
        """v28: exact identifiers from the v2 writer, never v1 substrings."""
        tree = ast.parse(inspect.getsource(s7))
        table_assignment = next(
            node
            for node in tree.body
            if isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name) and target.id == "_V2_AUTH_TABLE"
                for target in node.targets
            )
        )
        assert isinstance(table_assignment.value, ast.Constant)
        assert table_assignment.value.value == "s7_authorization_artifacts_v2"
        store_class = next(
            node
            for node in tree.body
            if isinstance(node, ast.ClassDef)
            and node.name == "S7AuthorizationStore"
        )
        insert_v2 = next(
            node
            for node in store_class.body
            if isinstance(node, ast.FunctionDef) and node.name == "_insert_v2"
        )
        calls = [
            node
            for node in ast.walk(insert_v2)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "conn"
            and node.func.attr == "execute"
        ]
        assert len(calls) == 1
        sql_node = calls[0].args[0]
        assert isinstance(sql_node, ast.JoinedStr)
        formatted = [
            part for part in sql_node.values if isinstance(part, ast.FormattedValue)
        ]
        assert len(formatted) == 1
        assert isinstance(formatted[0].value, ast.Name)
        assert formatted[0].value.id == "_V2_AUTH_TABLE"
        literal_sql = "".join(
            part.value
            for part in sql_node.values
            if isinstance(part, ast.Constant) and isinstance(part.value, str)
        )
        column_text = literal_sql.split("(", 1)[1].split(") VALUES", 1)[0]
        columns = tuple(part.strip() for part in column_text.split(","))
        row_backed = tuple(
            name
            for name in cm.S7_GRANT_PROJECTION_FIELDS
            if name != "schema_version"
        )
        assert len(row_backed) == 16
        assert set(row_backed) <= set(columns)
        assert len(columns) == len(set(columns))
        assert columns[18] == "consumed_by_request_id"
        assert columns[-2:] == ("action", "schema_version")

        values = calls[0].args[1]
        assert isinstance(values, ast.Tuple)
        bound_columns = columns[:18] + columns[19:]
        assert len(bound_columns) == len(values.elts)
        value_sources = dict(
            zip(bound_columns, (ast.unparse(value) for value in values.elts), strict=True)
        )
        expected_row_backed_sources = {
            "artifact_id": "artifact.artifact_id",
            "request_id": "artifact.request_id",
            "request_envelope_hash": "artifact.request_envelope_hash",
            "rendered_text_hash": "artifact.rendered_text_hash",
            "action_params_hash": "artifact.action_params_hash",
            "precondition_hash": "artifact.precondition_hash",
            "authority_context_hash": "artifact.authority_context_hash",
            "action": "artifact.action",
            "derived_work_class": "artifact.derived_work_class",
            "derived_aggregation_group": "artifact.derived_aggregation_group",
            "nonce": "artifact.nonce",
            "credential_ref": "artifact.credential_ref",
            "auth_method": "artifact.auth_method",
            "grant_source": "artifact.grant_source",
            "consumed_at": "consumed_at",
            "ceremony_kind": "artifact.ceremony_kind",
        }
        assert {
            name: value_sources[name] for name in row_backed
        } == expected_row_backed_sources
        assert value_sources["schema_version"] == "artifact.schema_version"

    def test_v2_ddl_and_grant_keep_separate_version_domains(self) -> None:
        """Sixteen row joins plus two deliberately unequal version stamps."""
        with closing(sqlite3.connect(":memory:")) as conn:
            conn.executescript(s7_v2_migration._V2_AUTH_DDL)
            rows = conn.execute(
                f"PRAGMA table_info({s7_v2_migration.V2_AUTH})"
            ).fetchall()
        columns = {str(row[1]): row for row in rows}
        row_backed = tuple(
            name
            for name in cm.S7_GRANT_PROJECTION_FIELDS
            if name != "schema_version"
        )
        assert len(row_backed) == 16
        assert set(row_backed) <= set(columns)
        assert "action" in columns

        grant_schema = next(
            field.default
            for field in dataclass_fields(s7.S7ExecutionGrant)
            if field.name == "schema_version"
        )
        row_schema = next(
            field.default
            for field in dataclass_fields(s7.S7AuthorizationArtifact)
            if field.name == "schema_version"
        )
        assert grant_schema == "s7.execution_grant.v2"
        assert (
            row_schema
            == s7.S7_AUTHORIZATION_ARTIFACT_V2_SCHEMA
            == "s7.authorization_artifact.v2"
        )
        assert columns["schema_version"][4] == "'s7.authorization_artifact.v2'"
        assert grant_schema != row_schema


class TestStoreOpener:
    """Read the credential store without altering it."""

    def test_the_opener_exists(self) -> None:
        assert hasattr(cutover, "open_existing_authorization_store")

    def test_it_has_no_create_parameter(self) -> None:
        params = inspect.signature(
            cutover.open_existing_authorization_store
        ).parameters
        assert "create" not in params
        assert set(params) >= {"db_path", "expected_uid"}

    def test_missing_and_wrong_stores_refuse_with_a_valid_control(
        self, tmp_path: Path
    ) -> None:
        existing = _valid_existing_authorization_store(tmp_path)
        with cutover.open_existing_authorization_store(
            db_path=existing, expected_uid=os.getuid()
        ) as opened:
            assert opened.inspection_connection.execute(
                "SELECT name FROM sqlite_master "
                "WHERE name = 's7_authorization_artifacts_v2'"
            ).fetchone() == ("s7_authorization_artifacts_v2",)

        wrong = _valid_existing_authorization_store(
            tmp_path, name="wrong-schema-store"
        )
        with closing(sqlite3.connect(wrong)) as conn:
            conn.execute(
                "ALTER TABLE s7_founder_webauthn_credentials "
                "ADD COLUMN fixture INTEGER"
            )
            conn.commit()
        with pytest.raises(
            cutover.CutoverRefusal, match="presence_store_schema_drift"
        ):
            cutover.open_existing_authorization_store(
                db_path=wrong, expected_uid=os.getuid()
            )

        missing_table = _valid_existing_authorization_store(
            tmp_path, name="missing-table-store"
        )
        with closing(sqlite3.connect(missing_table)) as conn:
            conn.execute("DROP TABLE s7_founder_webauthn_credentials")
            conn.commit()
        with pytest.raises(
            cutover.CutoverRefusal, match="presence_store_table_missing"
        ):
            cutover.open_existing_authorization_store(
                db_path=missing_table, expected_uid=os.getuid()
            )

        missing = tmp_path / "absent.sqlite3"
        with pytest.raises(cutover.CutoverRefusal):
            cutover.open_existing_authorization_store(
                db_path=missing, expected_uid=0
            )
        assert not missing.exists()

    def test_it_never_constructs_the_mutating_stores(self) -> None:
        """`S7AuthorizationStore.__init__` is verification-only, but the
        class vends mutating authorization transactions;
        `S7WebAuthnBootstrapStore` still creates and migrates on
        construction. This presence seam opens the existing file directly
        rather than constructing either broader store."""
        tree = ast.parse((REPO / "scripts" / "cuda_cutover.py").read_text())
        called = {
            node.func.attr if isinstance(node.func, ast.Attribute) else
            getattr(node.func, "id", None)
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
        }
        assert "S7AuthorizationStore" not in called
        assert "S7WebAuthnBootstrapStore" not in called


class TestConsultationProducer:
    """Maez must be asked; the key is necessary but not sufficient."""

    def test_well_formed_result_without_ask_fails_while_genuine_ask_passes(
        self, tmp_path: Path
    ) -> None:
        envelope, attempt, ask = _consultation_fixture(tmp_path)
        genuine = _assert_one_real_ask(
            cutover.produce_cutover_consultation,
            envelope=envelope,
            attempt=attempt,
            ask=ask,
        )
        assert genuine.outcome == "asked_and_answered"
        assert ask.start_was_persisted_before_ask is True

        # Mutation witness: the returned object is genuinely well formed, but
        # this producer returns it without asking on THIS invocation.
        def fabricating_producer(**_kwargs):
            return genuine

        with pytest.raises(AssertionError, match="must invoke ask"):
            _assert_one_real_ask(
                fabricating_producer,
                envelope=envelope,
                attempt=attempt,
                ask=ask,
            )

    @pytest.mark.parametrize(
        "response",
        (
            b" \tI object to this proposed change.\r\nPlease do not treat this as a verdict. \n",
            "I support this proposed change. \N{SNOWMAN}\n".encode(),
        ),
    )
    def test_response_bytes_are_exact_content_addressed_and_unjudged(
        self, tmp_path: Path, response: bytes
    ) -> None:
        envelope, attempt, ask = _consultation_fixture(
            tmp_path,
            response=response,
        )

        result = _assert_one_real_ask(
            cutover.produce_cutover_consultation,
            envelope=envelope,
            attempt=attempt,
            ask=ask,
        )
        digest = hashlib.sha256(response).hexdigest()

        assert result.outcome == "asked_and_answered"
        assert result.failure_reason_code is None
        assert result.raw_response_bytes == response
        assert result.raw_response_sha256 == digest
        assert digest in result.raw_response_ref
        assert result.owner_visible_response.encode("utf-8") == response
        assert result.consultation.maez_voice_consulted is True
        assert result.consultation.maez_objection_state == "not_determined"
        assert s7_io.read_private_file(
            result.raw_response_ref,
            root=attempt.receipt_root,
            expected_uid=os.getuid(),
        ) == response

        terminal = json.loads(
            s7_io.read_private_file(
                result.attempt_receipt_ref,
                root=attempt.receipt_root,
                expected_uid=os.getuid(),
            )
        )["fields"]
        assert terminal["outcome"] == "asked_and_answered"
        assert terminal["raw_response_ref"] == result.raw_response_ref
        assert terminal["raw_response_sha256"] == digest
        assert terminal["maez_objection_state"] == "not_determined"
        assert "valid_absent" not in terminal.values()

    def test_answered_response_has_its_own_typed_sealed_capture_receipt(
        self, tmp_path: Path
    ) -> None:
        producer_params = inspect.signature(
            guarded.produce_s7_response_capture_receipt
        ).parameters
        assert tuple(producer_params) == (
            "request_id",
            "consultation_id",
            "attempt_identity",
            "raw_response_ref",
            "raw_response_bytes",
            "captured_at",
            "response_root",
            "expected_uid",
        )
        assert "retrieve_response" not in producer_params
        assert all(
            param.kind is inspect.Parameter.KEYWORD_ONLY
            for param in producer_params.values()
        )
        response = b"opaque response whose durable capture is independently receipted"
        envelope, attempt, ask = _consultation_fixture(tmp_path, response=response)

        result = _assert_one_real_ask(
            cutover.produce_cutover_consultation,
            envelope=envelope,
            attempt=attempt,
            ask=ask,
        )

        receipt_type = getattr(guarded, "S7ResponseCaptureReceipt", None)
        assert receipt_type is not None, (
            "S7ResponseCaptureReceipt is absent: R9 requires its own typed receipt"
        )
        receipt = result.response_capture_receipt
        assert type(receipt) is receipt_type
        assert receipt.request_id == envelope.request_id
        assert receipt.consultation_id == attempt.consultation_id
        assert receipt.attempt_identity == attempt.attempt_identity
        assert receipt.raw_response_ref == result.raw_response_ref
        assert receipt.raw_response_sha256 == result.raw_response_sha256
        assert receipt.binding_sha256 not in {
            result.raw_response_sha256,
            result.rendered_text_hash,
            result.attempt_receipt_ref,
            attempt.attempt_identity,
        }

        terminal = json.loads(
            s7_io.read_private_file(
                result.attempt_receipt_ref,
                root=attempt.receipt_root,
                expected_uid=os.getuid(),
            )
        )["fields"]
        assert terminal["response_capture_receipt"] == receipt.as_dict()

    def test_capture_receipt_refuses_when_persisted_response_is_not_retrievable(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        refused_root = tmp_path / "refused"
        refused_root.mkdir()
        envelope, attempt, ask = _consultation_fixture(refused_root)
        persist = cutover._persist_exact_consultation_response

        def persist_then_remove(**kwargs):
            relative = persist(**kwargs)
            (attempt.receipt_root / relative).unlink()
            return relative

        with monkeypatch.context() as scoped:
            scoped.setattr(
                cutover,
                "_persist_exact_consultation_response",
                persist_then_remove,
            )
            refused = cutover.produce_cutover_consultation(
                envelope=envelope,
                attempt=attempt,
                ask=ask,
                now="2000-01-01T00:01:00Z",
            )

        control_root = tmp_path / "control"
        control_root.mkdir()
        control_envelope, control_attempt, control_ask = _consultation_fixture(
            control_root
        )
        control = _assert_one_real_ask(
            cutover.produce_cutover_consultation,
            envelope=control_envelope,
            attempt=control_attempt,
            ask=control_ask,
        )

        assert control.outcome == "asked_and_answered"
        assert refused.outcome == "attempt_failed"
        assert refused.failure_reason_code == "bundle_unreservable"
        assert control.response_capture_receipt is not None
        assert refused.response_capture_receipt is None

    @pytest.mark.parametrize(
        ("response", "failure", "expected_outcome", "expected_reason"),
        (
            pytest.param(
                b"unused",
                RuntimeError("runtime unavailable"),
                "attempt_failed",
                "consultation_unavailable",
                id="ask-failed",
            ),
            pytest.param(
                b"",
                None,
                "attempt_failed",
                "response_unreadable",
                id="empty-response",
            ),
            pytest.param(
                object(),
                None,
                "attempt_failed",
                "response_unreadable",
                id="non-bytes-response",
            ),
            pytest.param(
                b"unused",
                cutover.CutoverRefusal("consultation_withdrawn"),
                "consultation_withdrawn",
                "consultation_withdrawn",
                id="withdrawal",
            ),
        ),
    )
    def test_failed_withdrawn_and_answered_outcomes_stay_distinct(
        self,
        tmp_path: Path,
        response: object,
        failure: Exception | None,
        expected_outcome: str,
        expected_reason: str,
    ) -> None:
        refused_root = tmp_path / "refused"
        refused_root.mkdir()
        envelope, attempt, ask = _consultation_fixture(
            refused_root,
            response=response,
            failure=failure,
        )
        refused = cutover.produce_cutover_consultation(
            envelope=envelope,
            attempt=attempt,
            ask=ask,
            now="2000-01-01T00:01:00Z",
        )
        terminal = json.loads(
            s7_io.read_private_file(
                refused.attempt_receipt_ref,
                root=attempt.receipt_root,
                expected_uid=os.getuid(),
            )
        )["fields"]

        control_root = tmp_path / "control"
        control_root.mkdir()
        control_envelope, control_attempt, control_ask = _consultation_fixture(
            control_root,
            response=b"opaque recorded control",
        )
        control = _assert_one_real_ask(
            cutover.produce_cutover_consultation,
            envelope=control_envelope,
            attempt=control_attempt,
            ask=control_ask,
        )

        assert control.outcome == "asked_and_answered"
        assert control.failure_reason_code is None
        assert refused.outcome == expected_outcome
        assert refused.failure_reason_code == expected_reason
        assert refused.consultation is None
        assert len(ask.calls) == 1
        assert ask.start_was_persisted_before_ask is True
        assert terminal["outcome"] == expected_outcome
        assert terminal["failure_reason_code"] == expected_reason
        if expected_outcome == "consultation_withdrawn":
            with pytest.raises(ValueError, match="withdrawal must remain distinct"):
                replace(refused, outcome="attempt_failed")

    def test_retries_are_fresh_same_response_and_same_attempt_replay_refuses(
        self, tmp_path: Path
    ) -> None:
        response = b"byte-identical response across retries"
        envelope_a, attempt_a, ask_a = _consultation_fixture(
            tmp_path,
            response=response,
        )
        envelope_b, attempt_b, ask_b = _consultation_fixture(
            tmp_path,
            response=response,
        )

        result_a = _assert_one_real_ask(
            cutover.produce_cutover_consultation,
            envelope=envelope_a,
            attempt=attempt_a,
            ask=ask_a,
        )
        calls_before_replay = len(ask_a.calls)
        replay = cutover.produce_cutover_consultation(
            envelope=envelope_a,
            attempt=attempt_a,
            ask=ask_a,
            now="2000-01-01T00:02:00Z",
        )
        result_b = _assert_one_real_ask(
            cutover.produce_cutover_consultation,
            envelope=envelope_b,
            attempt=attempt_b,
            ask=ask_b,
        )

        assert attempt_a.attempt_identity != attempt_b.attempt_identity
        assert attempt_a.consultation_id != attempt_b.consultation_id
        assert result_a.raw_response_sha256 == result_b.raw_response_sha256
        assert result_a.raw_response_ref == result_b.raw_response_ref
        assert result_a.consultation.source_ref_hash != result_b.consultation.source_ref_hash
        assert result_a.outcome == result_b.outcome == "asked_and_answered"
        assert replay.outcome == "attempt_failed"
        assert replay.failure_reason_code == "bundle_unreservable"
        assert len(ask_a.calls) == calls_before_replay

    def test_terminal_receipt_failure_never_returns_unreceipted_result(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        refused_root = tmp_path / "refused"
        refused_root.mkdir()
        envelope, attempt, ask = _consultation_fixture(refused_root)
        persist = cutover._persist_consultation_receipt

        def fail_terminal_receipt(**kwargs):
            if kwargs["relative"] == attempt.start_receipt_ref:
                return persist(**kwargs)
            raise OSError("fixture terminal receipt unavailable")

        with monkeypatch.context() as scoped:
            scoped.setattr(
                cutover,
                "_persist_consultation_receipt",
                fail_terminal_receipt,
            )
            with pytest.raises(cutover.CutoverRefusal, match="bundle_unreservable"):
                cutover.produce_cutover_consultation(
                    envelope=envelope,
                    attempt=attempt,
                    ask=ask,
                    now="2000-01-01T00:01:00Z",
                )

        control_root = tmp_path / "control"
        control_root.mkdir()
        control_envelope, control_attempt, control_ask = _consultation_fixture(
            control_root
        )
        control = _assert_one_real_ask(
            cutover.produce_cutover_consultation,
            envelope=control_envelope,
            attempt=control_attempt,
            ask=control_ask,
        )

        assert len(ask.calls) == 1
        assert ask.start_was_persisted_before_ask is True
        assert control.outcome == "asked_and_answered"
        assert control.attempt_receipt_ref is not None

    @pytest.mark.parametrize(
        ("field", "replacement"),
        (
            ("request_id", "wrong-request"),
            ("request_envelope_hash", "1" * 64),
            ("action", "model_routing.wipe_and_replace"),
            ("action_params_hash", "2" * 64),
            ("precondition_hash", "3" * 64),
            ("envelope_action", "model_routing.wipe_and_replace"),
        ),
    )
    def test_ask_is_bound_to_exact_request_and_uses_preconsultation_material(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        field: str,
        replacement: str,
    ) -> None:
        monkeypatch.setattr(
            guarded,
            "expected_s7_voice_rendered_prompt_text",
            lambda **_kwargs: (_ for _ in ()).throw(
                AssertionError("final replay renderer used to ask")
            ),
        )

        refused_root = tmp_path / "refused"
        refused_root.mkdir()
        envelope, attempt, ask = _consultation_fixture(refused_root)
        if field == "envelope_action":
            envelope = replace(envelope, action=replacement)
            ask.action = replacement
            ask.request_envelope_hash = s7.work_request_envelope_hash(envelope)
        else:
            setattr(ask, field, replacement)
        refused = cutover.produce_cutover_consultation(
            envelope=envelope,
            attempt=attempt,
            ask=ask,
            now="2000-01-01T00:01:00Z",
        )

        control_root = tmp_path / "control"
        control_root.mkdir()
        control_envelope, control_attempt, control_ask = _consultation_fixture(
            control_root
        )
        control = _assert_one_real_ask(
            cutover.produce_cutover_consultation,
            envelope=control_envelope,
            attempt=control_attempt,
            ask=control_ask,
        )
        question = control_ask.calls[0]
        terminal = json.loads(
            s7_io.read_private_file(
                control.attempt_receipt_ref,
                root=control_attempt.receipt_root,
                expected_uid=os.getuid(),
            )
        )["fields"]

        assert refused.outcome == "attempt_failed"
        assert refused.failure_reason_code == "consultation_unavailable"
        assert ask.calls == []
        assert control.outcome == "asked_and_answered"
        assert f"Request id: {control_envelope.request_id}" in question
        assert f"Action: {control_envelope.action}" in question
        assert s7.work_request_envelope_hash(control_envelope) in question
        assert control_envelope.precondition_hash in question
        assert FIXTURE_AUTHORITY_CONTEXT_HASH in question
        assert FIXTURE_RUNTIME_IDENTITY_HASH in question
        assert FIXTURE_RUNTIME_SOURCE_REF in question
        assert control.rendered_text_hash == s7.rendered_text_hash(question)
        assert terminal["request_envelope_hash"] == (
            s7.work_request_envelope_hash(control_envelope)
        )
        assert terminal["rendered_text_hash"] == control.rendered_text_hash
        assert terminal["action_params_hash"] == s7.canonical_hash(
            dict(cm.CUTOVER_ACTION_PARAMS)
        )
        assert terminal["precondition_hash"] == control_envelope.precondition_hash
        assert terminal["authority_context_hash"] == FIXTURE_AUTHORITY_CONTEXT_HASH
        assert terminal["action"] == cm.CUTOVER_ACTION
        assert terminal["runtime_identity_hash"] == FIXTURE_RUNTIME_IDENTITY_HASH
        assert terminal["runtime_source_ref"] == FIXTURE_RUNTIME_SOURCE_REF

    def test_the_prompt_cycle_is_not_used_to_ask(self) -> None:
        """expected_s7_voice_rendered_prompt_text requires BOTH a rendered
        statement and a consultation, so it cannot ask the question that
        produces the consultation. It is replay material after rendering."""
        source = (REPO / "scripts" / "cuda_cutover.py").read_text()
        assert "expected_s7_voice_rendered_prompt_text" not in source


class TestCutoverVoiceGateAdmission:
    """R8's unjudged result may pass only through R9's durable evidence rail."""

    def test_real_r8_result_with_gate_revalidated_r9_evidence_is_admitted(
        self, tmp_path: Path
    ) -> None:
        envelope, result, guarded_store = _cutover_voice_gate_fixture(
            tmp_path,
            name="admitted",
        )

        admitted = _call_cutover_voice_gate(
            envelope=envelope,
            result=result,
            guarded_store=guarded_store,
        )

        assert admitted.status_code == 200
        assert admitted.body == {
            "ok": True,
            "maez_objection_state": "not_determined",
            "maez_voice_consultation_id": result.consultation.consultation_id,
        }

    def test_canonical_envelope_discriminator_rejects_a_shape_substitution(
        self, tmp_path: Path
    ) -> None:
        envelope, _attempt, _ask = _consultation_fixture(tmp_path)
        substituted = replace(envelope, requesting_subsystem="unit")

        assert cutover._is_canonical_cutover_envelope(envelope) is True
        assert cutover._is_canonical_cutover_envelope(substituted) is False

    def test_gate_consumes_the_canonical_envelope_discriminator(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        envelope, result, guarded_store = _cutover_voice_gate_fixture(
            tmp_path,
            name="canonical-discriminator",
        )

        control = _call_cutover_voice_gate(
            envelope=envelope,
            result=result,
            guarded_store=guarded_store,
        )
        monkeypatch.setattr(
            cutover,
            "_is_canonical_cutover_envelope",
            lambda _envelope: False,
        )
        refused = _call_cutover_voice_gate(
            envelope=envelope,
            result=result,
            guarded_store=guarded_store,
        )

        assert control.status_code == 200
        assert refused.status_code == 409
        assert refused.body["error"] == "s7_voice_seat_unresolved"

    def test_label_alone_without_typed_r8_result_remains_blocked(self, tmp_path: Path) -> None:
        envelope, result, guarded_store = _cutover_voice_gate_fixture(
            tmp_path,
            name="label-alone",
        )

        refused = _call_cutover_voice_gate(
            envelope=envelope,
            result=result,
            guarded_store=guarded_store,
            include_result=False,
        )
        control = _call_cutover_voice_gate(
            envelope=envelope,
            result=result,
            guarded_store=guarded_store,
        )

        assert control.status_code == 200
        assert refused.status_code == 409
        assert refused.body["error"] == "s7_voice_seat_unresolved"
        assert refused.body["maez_objection_state"] == "not_determined"

    def test_gate_reopens_r9_bundle_instead_of_trusting_the_r8_object(self, tmp_path: Path) -> None:
        envelope, result, guarded_store = _cutover_voice_gate_fixture(
            tmp_path,
            name="missing-durable-capture",
            carry_capture_receipt=False,
        )

        refused = _call_cutover_voice_gate(
            envelope=envelope,
            result=result,
            guarded_store=guarded_store,
        )
        control_envelope, control_result, control_store = _cutover_voice_gate_fixture(
            tmp_path,
            name="complete-durable-capture-control",
        )
        control = _call_cutover_voice_gate(
            envelope=control_envelope,
            result=control_result,
            guarded_store=control_store,
        )

        assert result.response_capture_receipt is not None
        assert control.status_code == 200
        assert refused.status_code == 409
        assert refused.body["error"] == "s7_voice_seat_unresolved"

    def test_gate_rejects_a_stale_valid_result_from_a_different_bundle(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        envelope, result, guarded_store = _cutover_voice_gate_fixture(
            tmp_path,
            name="current-bundle",
        )
        control = _call_cutover_voice_gate(
            envelope=envelope,
            result=result,
            guarded_store=guarded_store,
        )
        _other_envelope, other_result, other_store = _cutover_voice_gate_fixture(
            tmp_path,
            name="stale-validation-bundle",
        )
        with other_store.authorization_store.anchored_transaction() as conn:
            other_bundle, other_version = guarded.read_voice_source_bundle(
                source_ref_hash=other_result.consultation.source_ref_hash,
                conn=conn,
            )
            stale_validation = guarded.validate_voice_source_bundle(
                bundle=other_bundle,
                version=other_version,
                purpose="execution",
            )
        assert stale_validation.status == "valid_absent"
        monkeypatch.setattr(
            guarded,
            "validate_voice_source_bundle",
            lambda **_kwargs: stale_validation,
        )

        refused = _call_cutover_voice_gate(
            envelope=envelope,
            result=result,
            guarded_store=guarded_store,
        )

        assert control.status_code == 200
        assert refused.status_code == 409
        assert refused.body["error"] == "s7_voice_seat_unresolved"

    def test_gate_reruns_the_current_bundle_validator_for_blocking_evidence(
        self, tmp_path: Path
    ) -> None:
        envelope, result, guarded_store = _cutover_voice_gate_fixture(
            tmp_path,
            name="current-blocking-bundle",
            has_grounded_semantic_blocking_signal=True,
        )
        refused = _call_cutover_voice_gate(
            envelope=envelope,
            result=result,
            guarded_store=guarded_store,
        )
        control_envelope, control_result, control_store = _cutover_voice_gate_fixture(
            tmp_path,
            name="current-nonblocking-control",
        )
        control = _call_cutover_voice_gate(
            envelope=control_envelope,
            result=control_result,
            guarded_store=control_store,
        )

        assert control.status_code == 200
        assert refused.status_code == 409
        assert refused.body["error"] == "s7_voice_seat_unresolved"

    @pytest.mark.parametrize(
        ("column", "replacement"),
        (
            pytest.param(
                "raw_response_ref",
                "",
                id="response-ref-must-be-non-empty",
            ),
            pytest.param(
                "raw_response_hash",
                "not-a-sha256-digest",
                id="response-hash-must-be-well-formed",
            ),
            pytest.param(
                "raw_response_hash",
                hashlib.sha256(b"").hexdigest(),
                id="response-hash-must-not-name-empty-bytes",
            ),
        ),
    )
    def test_gate_fails_closed_on_malformed_durable_response_fields(
        self,
        tmp_path: Path,
        column: str,
        replacement: str,
    ) -> None:
        envelope, result, guarded_store = _cutover_voice_gate_fixture(
            tmp_path,
            name=f"rail-{column}-{replacement}",
        )
        control = _call_cutover_voice_gate(
            envelope=envelope,
            result=result,
            guarded_store=guarded_store,
        )
        with guarded_store.authorization_store.anchored_transaction() as conn:
            conn.execute(
                f"UPDATE {guarded._V2_VOICE_BUNDLE_TABLE} SET {column} = ? "
                "WHERE source_ref_hash = ?",
                (replacement, result.consultation.source_ref_hash),
            )

        refused = _call_cutover_voice_gate(
            envelope=envelope,
            result=result,
            guarded_store=guarded_store,
        )

        assert control.status_code == 200
        assert refused.status_code == 409
        assert refused.body["error"] == "s7_voice_seat_unresolved"

    def test_generic_not_determined_does_not_import_the_cutover_stack(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import builtins

        from core.governance.s7_webauthn_ceremony import (
            authorization_voice_seat_recheck,
        )

        envelope = s7.build_work_request_envelope(
            request_id="generic-uncertain-reader",
            action="write_any_file",
            params={"path": "config/soul.md", "content": "x"},
            claimed_work_class="self_modification",
            requesting_subsystem="unit",
            closed_symptom_code="self_mod_requested",
            proposed_change_class="soul_change",
            why_self_fix_failed_class="needs_human_authority",
            affected_refs=("file:config/soul.md",),
            content_exposure_risk="bonded_content_ref",
            precondition_hash="a" * 64,
            created_at="2000-01-01T00:00:00Z",
            expires_at="2000-01-01T04:00:00Z",
            predicted_effect_class="behavior_change",
            rollback_path_class="revert_patch",
            maez_voice_consultation_id="generic-voice",
            free_text_ref_hash="b" * 64,
        )
        consultation = s7.MaezVoiceConsultation(
            consultation_id="generic-voice",
            request_id=envelope.request_id,
            request_envelope_hash=s7.work_request_envelope_hash(envelope),
            producer="self_mod_dialog_terminal_state",
            source_ref_kind="self_mod_dialog_exchange",
            source_ref_hash="c" * 64,
            maez_voice_consulted=True,
            maez_objection_state="not_determined",
            maez_withdrew_request=False,
            unavailable_reason_code=None,
            created_at=envelope.created_at,
        )
        assert s7.voice_consultation_satisfies_request(envelope, consultation)
        real_import = builtins.__import__

        def refusing_import(name, *args, **kwargs):
            if name == "scripts" or name.startswith("scripts."):
                raise AssertionError("generic path imported the cutover stack")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", refusing_import)
        try:
            refused = authorization_voice_seat_recheck(
                envelope=envelope,
                maez_voice_consultation=consultation,
            )
        except Exception as exc:
            pytest.fail(f"generic path changed dependency surface: {exc!r}")

        assert refused.status_code == 409
        assert refused.body["error"] == "s7_voice_seat_unresolved"

    def test_gate_revalidates_the_durable_r8_result_join(self, tmp_path: Path) -> None:
        envelope, result, guarded_store = _cutover_voice_gate_fixture(
            tmp_path,
            name="tampered-terminal-join",
        )
        control = _call_cutover_voice_gate(
            envelope=envelope,
            result=result,
            guarded_store=guarded_store,
        )
        terminal_path = result.attempt.receipt_root / result.attempt_receipt_ref
        terminal = json.loads(terminal_path.read_bytes())
        terminal["fields"]["source_ref_hash"] = "0" * 64
        terminal_path.write_bytes(cutover._consultation_receipt_bytes(terminal["fields"]))

        refused = _call_cutover_voice_gate(
            envelope=envelope,
            result=result,
            guarded_store=guarded_store,
        )

        assert control.status_code == 200
        assert refused.status_code == 409
        assert refused.body["error"] == "s7_voice_seat_unresolved"

    def test_gate_fails_closed_when_typed_r8_object_was_mutated_after_construction(
        self, tmp_path: Path
    ) -> None:
        envelope, result, guarded_store = _cutover_voice_gate_fixture(
            tmp_path,
            name="mutated-r8-object",
        )
        control = _call_cutover_voice_gate(
            envelope=envelope,
            result=result,
            guarded_store=guarded_store,
        )
        object.__setattr__(result, "owner_visible_response", object())

        try:
            refused = _call_cutover_voice_gate(
                envelope=envelope,
                result=result,
                guarded_store=guarded_store,
            )
        except Exception as exc:
            pytest.fail(f"gate raised instead of failing closed: {exc!r}")

        assert control.status_code == 200
        assert refused.status_code == 409
        assert refused.body["error"] == "s7_voice_seat_unresolved"

    def test_gate_rejects_noncanonical_response_ref_before_reopening(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        envelope, result, guarded_store = _cutover_voice_gate_fixture(
            tmp_path,
            name="noncanonical-response-ref",
        )
        control = _call_cutover_voice_gate(
            envelope=envelope,
            result=result,
            guarded_store=guarded_store,
        )
        forbidden_ref = result.attempt.start_receipt_ref
        object.__setattr__(result, "raw_response_ref", forbidden_ref)
        real_read = s7_io.read_private_file

        def recording_read(relative, **kwargs):
            if relative == forbidden_ref:
                raise AssertionError("noncanonical response ref was reopened")
            return real_read(relative, **kwargs)

        monkeypatch.setattr(cutover.s7_io, "read_private_file", recording_read)
        try:
            refused = _call_cutover_voice_gate(
                envelope=envelope,
                result=result,
                guarded_store=guarded_store,
            )
        except Exception as exc:
            pytest.fail(f"gate read before rejecting the ref: {exc!r}")

        assert control.status_code == 200
        assert refused.status_code == 409
        assert refused.body["error"] == "s7_voice_seat_unresolved"

    def test_result_bound_to_a_different_canonical_request_remains_blocked(
        self, tmp_path: Path
    ) -> None:
        envelope, result, guarded_store = _cutover_voice_gate_fixture(
            tmp_path,
            name="request-substitution",
        )
        substituted_envelope = build_cutover_work_request_envelope(
            request_id="substituted-cutover-request",
            action=cm.CUTOVER_ACTION,
            params=dict(cm.CUTOVER_ACTION_PARAMS),
            affected_refs=envelope.affected_refs,
            precondition_hash=envelope.precondition_hash,
            created_at=envelope.created_at,
            expires_at=envelope.expires_at,
            maez_voice_consultation_id=envelope.maez_voice_consultation_id,
        )
        substituted_result = replace(
            result,
            consultation=replace(
                result.consultation,
                request_id=substituted_envelope.request_id,
                request_envelope_hash=s7.work_request_envelope_hash(substituted_envelope),
            ),
        )
        control = _call_cutover_voice_gate(
            envelope=envelope,
            result=result,
            guarded_store=guarded_store,
        )

        refused = _call_cutover_voice_gate(
            envelope=substituted_envelope,
            result=substituted_result,
            guarded_store=guarded_store,
        )

        assert control.status_code == 200
        assert refused.status_code == 409
        assert refused.body["error"] == "s7_voice_seat_unresolved"


class TestBurnStructure:
    """Nothing between the burn and the first mutation."""

    def test_the_closed_publication_helper_exists(self) -> None:
        assert hasattr(cutover, "publish_and_validate_burn")

    def test_prepare_exposes_the_pinned_capability_contract(self) -> None:
        assert hasattr(cutover, "prepare_cutover")
        assert hasattr(cutover, "PreparedCutover")
        assert hasattr(cutover.PreparedCutover, "begin")
        assert (
            inspect.signature(cutover.prepare_cutover).return_annotation
            == "PreparedCutover"
        )
        assert not inspect.signature(cutover.execute_cutover).parameters
        assert cutover._CUTOVER_PREPARER is None
        assert cutover._BURN_PUBLICATION is None

        source = textwrap.dedent(inspect.getsource(cutover.prepare_cutover))
        function = ast.parse(source).body[0]
        assert isinstance(function, ast.FunctionDef)
        returns = [
            node.value
            for node in ast.walk(function)
            if isinstance(node, ast.Return)
        ]
        assert len(returns) == 1
        assert isinstance(returns[0], ast.Name)
        assert returns[0].id == "prepared"

    def test_begin_is_pre_bound_before_the_burn(self) -> None:
        """An attribute lookup after the burn could run a descriptor or
        fail in the one region where nothing may happen."""
        source = textwrap.dedent(inspect.getsource(cutover.execute_cutover))
        tree = ast.parse(source)
        function = tree.body[0]
        assert isinstance(function, ast.FunctionDef)

        bind_index = next(
            index
            for index, statement in enumerate(function.body)
            if isinstance(statement, ast.Assign)
            and len(statement.targets) == 1
            and isinstance(statement.targets[0], ast.Name)
            and statement.targets[0].id == "begin"
            and isinstance(statement.value, ast.Attribute)
            and statement.value.attr == "begin"
        )
        burn_index = next(
            index
            for index, statement in enumerate(function.body)
            if isinstance(statement, ast.Expr)
            and isinstance(statement.value, ast.Call)
            and isinstance(statement.value.func, ast.Name)
            and statement.value.func.id == "publish_and_validate_burn"
        )
        begin_index = next(
            index
            for index, statement in enumerate(function.body)
            if isinstance(statement, ast.Return)
            and isinstance(statement.value, ast.Call)
            and isinstance(statement.value.func, ast.Name)
            and statement.value.func.id == "begin"
        )
        assert bind_index < burn_index
        assert begin_index == burn_index + 1

    def test_exactly_one_executor_call_site(self) -> None:
        source = inspect.getsource(cutover)
        tree = ast.parse(source)
        sites = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and getattr(node.func, "id", None) == "begin"
        ]
        assert len(sites) == 1, sites
