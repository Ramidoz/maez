"""Cutover step 2B — the dormant-safe consumer orchestration.

Written against ratified design v34 and its R11 typed-consultation-absence ruling.

The suite covers the frozen receipt and action contracts, anchored store
opening, typed R11 absence, exact-v2 guarded mint, committed-row
consume, pinned preparation, and the closed-over publication/begin boundary.

Deliberately NOT here: a full end-to-end ceremony. It needs a founder
WebAuthn assertion, which cannot be produced without a physical key tap.
Asserting one exists would be the fabrication this project refuses.

These are local mechanical witnesses, not a ceremony or a certification claim.
The production entrypoint has one fixed anchored owner selection and no
capability-injection parameter; procedural presence remains unreachable.
"""

from __future__ import annotations

import ast
import fcntl
import hashlib
import inspect
import json
import os
import sqlite3
import stat as stat_module
import textwrap
from contextlib import closing
from dataclasses import fields as dataclass_fields, replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from core.governance import operator_user_boundary as s7
from core.governance import s7_guarded_execution as guarded
from core.governance import s7_v2_migration
from core.governance import s7_webauthn_ceremony as s7_ceremony
from scripts import cuda_cutover as cutover
from scripts import cuda_bench_assemble as assemble
from scripts import cuda_bench_driver as driver
from scripts import cuda_migration as cm

REPO = Path(__file__).resolve().parents[1]
FIXTURE_PRECONDITION_HASH = s7.canonical_hash(
    {"fixture": "expired-cutover-action-contract-v1"}
)
EXPECTED_CUTOVER_OPERATION_AFFECTED_REFS = {
    "stage_recovery_copies": ("backup:cuda_cutover_recovery",),
    "install_cuda_override": (
        "file:/home/rohit/.config/systemd/user/"
        "llama-server.service.d/zz-b9596-cuda.conf",
    ),
    "daemon_reload": ("systemd_manager:user",),
    "restart_llama_server": ("service:llama-server.service",),
    "restart_llama_judge": ("service:llama-judge.service",),
    "host_reboot": ("host:local",),
}
FIXTURE_CUTOVER_AFFECTED_REFS = (
    "backup:cuda_cutover_recovery",
    "file:/home/rohit/.config/systemd/user/llama-server.service.d/zz-b9596-cuda.conf",
    "host:local",
    "service:llama-judge.service",
    "service:llama-server.service",
    "systemd_manager:user",
)
FIXTURE_AUTHORITY_CONTEXT_HASH = s7.canonical_hash(
    {"fixture": "founder-authority-context"}
)
FIXTURE_RUNTIME_IDENTITY_HASH = s7.canonical_hash(
    {"fixture": "bonded-runtime-identity"}
)
FIXTURE_MODEL_ROUTING_IDENTITY_HASH = s7.canonical_hash(
    {"fixture": "model-routing-identity"}
)
FIXTURE_MODEL_CONFIG_HASH = s7.canonical_hash({"fixture": "model-config"})
FIXTURE_RUNTIME_SOURCE_REF = "bonded-runtime:fixture-primary"
FIXTURE_COMPLETION_LOCATOR = (
    "command-assemble-stage2-attempt-027-terminal.json"
)


def _closed_production_preparer():
    return inspect.getclosurevars(cutover.execute_cutover).nonlocals[
        "prepare_selected_cutover"
    ]


def _closed_production_authorizer():
    return inspect.getclosurevars(_closed_production_preparer()).nonlocals[
        "authorize_and_stage"
    ]


def _completion_selection_bytes(locator: str) -> bytes:
    return (
        json.dumps(
            {
                "fields": {"completion_locator": locator},
                "schema": "cuda_cutover.completion_selection.v1",
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        + b"\n"
    )


def _write_completion_selection(root: Path, locator: str) -> Path:
    root.mkdir(mode=0o700)
    selected = root / "cutover-completion-selection.json"
    selected.write_bytes(_completion_selection_bytes(locator))
    selected.chmod(0o600)
    return selected


def _seed_stage2_completion(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[Path, Path]:
    from tests.test_cutover_step2a_producer import (
        FixedClock,
        _call_cli_restoring_signal_state,
        seed_private_root,
    )

    root = seed_private_root(tmp_path)
    monkeypatch.setattr(driver, "BENCH_ROOT", root)
    monkeypatch.setattr(driver, "SystemClock", FixedClock)
    assert _call_cli_restoring_signal_state(
        ["assemble-stage2", "--window-id", "cutover-20260713-1202"]
    ) == 0
    completion = next(root.glob("command-assemble-stage2-*-terminal.json"))
    return root, completion


def _completion_selection_outcome(root: Path, expected_uid: int) -> tuple[str, str]:
    try:
        return (
            "accepted",
            cutover._read_completion_locator_at(root, expected_uid),
        )
    except cutover.CutoverRefusal as exc:
        return ("refused", str(exc))
    except Exception as exc:  # the assertion exposes wrong-reason failures
        return ("unexpected_exception", type(exc).__name__)


def _assert_completion_selection_positive_control(root: Path) -> None:
    _write_completion_selection(root, FIXTURE_COMPLETION_LOCATOR)
    assert _completion_selection_outcome(root, os.getuid()) == (
        "accepted",
        FIXTURE_COMPLETION_LOCATOR,
    )


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
        guarded._provision_r11_exemption_evidence_at(store_dir_fd=dir_fd)
    finally:
        os.close(dir_fd)
    return store.db_path


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


def _selected_binding_fixture(seed: str):
    """Content-only selected-cutover shape for binding/store mechanics.

    This is not a ceremony fixture and makes no claim that a founder tap or
    owner-read consultation occurred.
    """

    return SimpleNamespace(
        authorization=SimpleNamespace(
            binding_sha256=hashlib.sha256(
                f"authorization-binding:{seed}".encode()
            ).hexdigest(),
            rollback_manifest_sha256=hashlib.sha256(
                f"rollback:{seed}".encode()
            ).hexdigest(),
            window_id=f"cutover-window-{seed}",
            nonce=hashlib.sha256(f"cutover-nonce:{seed}".encode()).hexdigest(),
        ),
        authorization_file_sha256=hashlib.sha256(
            f"authorization-file:{seed}".encode()
        ).hexdigest(),
        receipt=SimpleNamespace(
            binding_sha256=hashlib.sha256(
                f"stage-two-binding:{seed}".encode()
            ).hexdigest(),
        ),
        receipt_file_sha256=hashlib.sha256(
            f"stage-two-file:{seed}".encode()
        ).hexdigest(),
        bundle=SimpleNamespace(
            runtime_identity_doc=SimpleNamespace(
                file_sha256=hashlib.sha256(
                    f"target-runtime:{seed}".encode()
                ).hexdigest(),
            ),
        ),
        precondition_hash=hashlib.sha256(
            f"precondition:{seed}".encode()
        ).hexdigest(),
    )


def _mechanical_cutover_chain(*, selected, nonce: str):
    """Build storage inputs only; this is deliberately not tap evidence."""

    params = cutover._cutover_action_preimage(selected)
    envelope = s7.build_work_request_envelope(
        request_id=selected.authorization.window_id,
        action=cm.CUTOVER_ACTION,
        params=dict(params),
        claimed_work_class="self_modification",
        requesting_subsystem="cuda_cutover",
        closed_symptom_code="self_mod_requested",
        proposed_change_class="model_routing_change",
        why_self_fix_failed_class="not_self_fix",
        affected_refs=FIXTURE_CUTOVER_AFFECTED_REFS,
        content_exposure_risk="content_free",
        precondition_hash=selected.precondition_hash,
        created_at="2026-08-07T12:00:00Z",
        expires_at="2026-08-07T16:00:00Z",
        predicted_effect_class="behavior_change",
        rollback_path_class="revert_patch",
        maez_voice_consultation_id="mechanical-storage-only",
    )
    authority = s7.AuthorityContext(
        actor_id="founder",
        actor_handle_hmac="hmac:s7:founder:" + ("a" * 64),
        role_names=("bonded_user",),
        grant_source="founder_webauthn",
        allowed_scopes=("operator_health",),
        auth_method="founder_webauthn",
        surface="cockpit",
        credential_ref="mechanical-credential",
        created_at="2026-08-07T12:00:00Z",
        expires_at="2026-08-07T16:00:00Z",
        verified=True,
    )
    consultation = s7.MaezVoiceConsultation(
        consultation_id="mechanical-storage-only",
        request_id=envelope.request_id,
        request_envelope_hash=s7.work_request_envelope_hash(envelope),
        # Closed vocabulary required by the renderer. The surrounding helper
        # remains explicitly storage-only and is never routed to production.
        producer="self_mod_dialog_terminal_state",
        source_ref_kind="self_mod_dialog_exchange",
        source_ref_hash="b" * 64,
        maez_voice_consulted=True,
        maez_objection_state="absent",
        maez_withdrew_request=False,
        unavailable_reason_code=None,
        created_at="2026-08-07T12:00:00Z",
    )
    params_hash = s7.canonical_hash(dict(params))
    rendered = s7.render_request_statement(
        envelope=envelope,
        surface="cockpit",
        origin="http://localhost:11437",
        action_params_hash=params_hash,
        authority_context=authority,
        maez_voice_consultation=consultation,
        nonce=nonce,
        expires_at="2026-08-07T16:00:00Z",
        rendered_at="2026-08-07T12:00:00Z",
    )
    return params, envelope, authority, rendered


class TestActionContract:
    """One action literal and stable base mapping for the v34 preimage."""

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

    def test_each_executor_operation_derives_its_honest_affected_ref(self) -> None:
        """The six-operation authority manifest and its ref map are one shape.

        Recovery staging is deliberately logical: its physical private
        destination does not exist until preparation, while the frozen
        rollback manifest binds the bytes it will contain.
        """
        assert cm.CUTOVER_OPERATION_AFFECTED_REFS == (
            EXPECTED_CUTOVER_OPERATION_AFFECTED_REFS
        )
        assert tuple(cm.CUTOVER_OPERATION_AFFECTED_REFS) == cm.CUTOVER_ACTION_SET
        assert cm.CUTOVER_AFFECTED_REFS == FIXTURE_CUTOVER_AFFECTED_REFS

    def test_new_closed_ref_kinds_survive_canonicalization(self) -> None:
        assert (
            s7._canonical_affected_refs(FIXTURE_CUTOVER_AFFECTED_REFS)
            == FIXTURE_CUTOVER_AFFECTED_REFS
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

    def test_rw_connection_is_accepted_by_committed_row_consumer(
        self, tmp_path: Path
    ) -> None:
        """The verified opener must vend Slice A's held-connection capability."""
        existing = _valid_existing_authorization_store(tmp_path)
        with cutover.open_existing_authorization_store(
            db_path=existing, expected_uid=os.getuid()
        ) as opened:
            result = s7.consume_for_execution_with_committed_row(
                opened.consumption_connection,
                "absent-artifact",
                rendered=object(),
                action_params_hash="1" * 64,
                authority_context=object(),
                precondition_hash="2" * 64,
                derived_work_class="self_modification",
                derived_aggregation_group="s7agg_cutover",
                now="2000-01-01T00:00:00Z",
            )
        assert result == (None, None, None)

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
        tree = ast.parse(
            textwrap.dedent(
                inspect.getsource(cutover.open_existing_authorization_store)
            )
        )
        called = {
            node.func.attr if isinstance(node.func, ast.Attribute) else
            getattr(node.func, "id", None)
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
        }
        assert "S7AuthorizationStore" not in called
        assert "S7WebAuthnBootstrapStore" not in called


class TestSelectedStage2Reconstruction:
    """The owner-selected completion is only a locator; its joins decide."""

    def test_reconstructs_through_the_one_builder_and_independent_manifest(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from tests.test_cutover_step2a_producer import (
            FixedClock,
            _call_cli_restoring_signal_state,
            seed_private_root,
        )

        root = seed_private_root(tmp_path)
        monkeypatch.setattr(driver, "BENCH_ROOT", root)
        monkeypatch.setattr(driver, "SystemClock", FixedClock)
        assert _call_cli_restoring_signal_state(
            ["assemble-stage2", "--window-id", "cutover-20260713-1202"]
        ) == 0
        completion = next(root.glob("command-assemble-stage2-*-terminal.json"))

        calls: list[tuple[object, Path, str]] = []
        real_builder = assemble.build_stage2_bundle

        def one_builder(paths, *, root, timestamp):
            calls.append((paths, root, timestamp))
            return real_builder(paths, root=root, timestamp=timestamp)

        monkeypatch.setattr(assemble, "build_stage2_bundle", one_builder)
        selected = cutover._reconstruct_selected_cutover_at(
            root=root,
            expected_uid=os.getuid(),
            completion_locator=completion.name,
            now="2026-08-03T20:31:03Z",
            boot_id="boot-1",
        )

        assert len(calls) == 1
        assert calls[0][0] == assemble.STAGE2_INPUTS
        assert calls[0][1:] == (root, selected.receipt.timestamp)
        assert selected.completion.artifact_ref == selected.receipt_ref
        assert selected.completion.admission_ref == selected.admission.selected_ref
        assert selected.receipt_bytes == selected.regenerated_receipt_bytes
        assert selected.receipt.decision == "provisional_cuda_boot"
        assert selected.authorization.window_id == selected.completion.window_id
        assert selected.operation_affected_refs == (
            EXPECTED_CUTOVER_OPERATION_AFFECTED_REFS
        )
        assert tuple(selected.operation_affected_refs) == cm.CUTOVER_ACTION_SET
        assert selected.affected_refs == FIXTURE_CUTOVER_AFFECTED_REFS

    @pytest.mark.parametrize(
        ("mutation", "expected"),
        (
            ("receipt_predicate", "receipt_predicate"),
            ("receipt_noncanonical", "receipt_noncanonical"),
            ("stage2_input_missing", "stage2_input_missing"),
            ("stage2_input_predicate", "stage2_input_predicate"),
            ("authorization_expired", "authorization_expired"),
        ),
    )
    def test_a7_reconstruction_refusal_distinctions_are_not_collapsed(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        mutation: str,
        expected: str,
    ) -> None:
        root, completion_path = _seed_stage2_completion(tmp_path, monkeypatch)
        completion = cm.PersistedDoc(completion_path.read_bytes()).obj
        control = cutover._reconstruct_selected_cutover_at(
            root=root,
            expected_uid=os.getuid(),
            completion_locator=completion_path.name,
            now="2026-08-03T20:31:03Z",
            boot_id="boot-1",
        )
        now = "2026-08-03T20:31:03Z"
        if mutation == "receipt_predicate":
            (root / completion.artifact_ref).chmod(0o400)
        elif mutation == "receipt_noncanonical":
            receipt_path = root / completion.artifact_ref
            receipt_path.write_text(
                json.dumps(json.loads(receipt_path.read_bytes()), indent=2) + "\n",
                encoding="utf-8",
            )
            receipt_path.chmod(0o600)
        elif mutation == "stage2_input_missing":
            (root / assemble.STAGE2_INPUTS.quality).unlink()
        elif mutation == "stage2_input_predicate":
            (root / assemble.STAGE2_INPUTS.quality).chmod(0o400)
        else:
            now = control.authorization.expires_at

        with pytest.raises(cutover.CutoverRefusal, match=rf"^{expected}$"):
            cutover._reconstruct_selected_cutover_at(
                root=root,
                expected_uid=os.getuid(),
                completion_locator=completion_path.name,
                now=now,
                boot_id="boot-1",
            )

    def test_selected_file_replacement_after_open_refuses_predicate(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        root = tmp_path / "root"
        root.mkdir(mode=0o700)
        selected = root / "selected.json"
        selected.write_bytes(b"selected-original")
        selected.chmod(0o600)
        replacement = root / "replacement.json"
        replacement.write_bytes(b"selected-replacement")
        replacement.chmod(0o600)
        detached = root / "selected-detached.json"
        verify_and_read = cutover.s7_io._verify_and_read

        def read_then_replace(fd, before, relative, expected_uid, *, max_bytes=None):
            # Signature mirrors production's call including max_bytes (the
            # per-read bound, 8a8e0d9). With the stale four-arg signature the
            # production call raised TypeError BEFORE the renames ran: phase 1
            # then "passed" through the generic-exception clause for the wrong
            # reason, and phase 2 failed on the never-created detached file.
            payload = verify_and_read(
                fd, before, relative, expected_uid, max_bytes=max_bytes
            )
            selected.rename(detached)
            replacement.rename(selected)
            return payload

        with monkeypatch.context() as scoped:
            scoped.setattr(
                cutover.s7_io,
                "_verify_and_read",
                read_then_replace,
            )
            with pytest.raises(
                cutover.CutoverRefusal,
                match=r"^command_completion_predicate$",
            ):
                cutover._read_selected_private_file(
                    root=root,
                    expected_uid=os.getuid(),
                    relative="selected.json",
                    refusal="command_completion_invalid",
                    predicate_refusal="command_completion_predicate",
                )

        assert cutover._read_selected_private_file(
            root=root,
            expected_uid=os.getuid(),
            relative="selected-detached.json",
            refusal="command_completion_invalid",
            predicate_refusal="command_completion_predicate",
        ) == b"selected-original"

    def test_selected_file_vanishing_after_open_refuses_predicate(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A name that VANISHES between read and named-stat is a predicate
        failure -- the held bytes are no longer reachable by the name that
        authorized them -- never the generic "absent file" refusal. This is
        the FileNotFoundError-to-predicate mapping added at 8a8e0d9, which
        had no witness: the replacement test above exercises only the
        identity-mismatch arm, where the named stat still succeeds."""
        root = tmp_path / "root"
        root.mkdir(mode=0o700)
        selected = root / "selected.json"
        selected.write_bytes(b"selected-original")
        selected.chmod(0o600)
        verify_and_read = cutover.s7_io._verify_and_read

        def read_then_vanish(fd, before, relative, expected_uid, *, max_bytes=None):
            payload = verify_and_read(
                fd, before, relative, expected_uid, max_bytes=max_bytes
            )
            selected.unlink()
            return payload

        with monkeypatch.context() as scoped:
            scoped.setattr(
                cutover.s7_io,
                "_verify_and_read",
                read_then_vanish,
            )
            with pytest.raises(
                cutover.CutoverRefusal,
                match=r"^command_completion_predicate$",
            ):
                cutover._read_selected_private_file(
                    root=root,
                    expected_uid=os.getuid(),
                    relative="selected.json",
                    refusal="command_completion_invalid",
                    predicate_refusal="command_completion_predicate",
                )


class TestPreparedCutoverResources:
    """Preparation resolves everything; begin receives only pinned state."""

    def test_child_fd_destinations_never_overwrite_a_later_source(
        self,
        tmp_path: Path,
    ) -> None:
        sources = tmp_path / "sources"
        recovery = tmp_path / "recovery"
        override_parent = tmp_path / "override-parent"
        for directory in (sources, recovery, override_parent):
            directory.mkdir(mode=0o700)
        unit = sources / "llama-server.service"
        dropin = sources / "mtp.conf"
        override = sources / "cuda.conf"
        judge = sources / "llama-judge.service"
        for path in (unit, dropin, override, judge):
            path.write_bytes(path.name.encode())
            path.chmod(0o600)

        pressure = [os.open("/dev/null", os.O_RDONLY) for _ in range(91)]
        prepared = None
        try:
            prepared = cutover._prepare_cutover_resources_at(
                recovery_sources=(
                    (unit, "llama-server.service"),
                    (dropin, "mtp.conf"),
                ),
                recovery_directory=recovery,
                override_source=override,
                override_directory=override_parent,
                unit_fragments={
                    "llama-server.service": unit,
                    "llama-judge.service": judge,
                },
                install_executable=Path("/usr/bin/install"),
                systemctl_executable=Path("/usr/bin/systemctl"),
                expected_uid=os.getuid(),
            )
            all_sources = {
                pinned.fd
                for pinned in (
                    *prepared.recovery_artifacts,
                    *prepared.installation_artifacts,
                    *(identity.fragment for identity in prepared.unit_identities),
                    *prepared.executables,
                )
            } | {directory.fd for directory in prepared.directories}
            for operation in prepared.operations:
                for command in operation.commands:
                    destinations = {target for _source, target in command.child_fd_map}
                    assert destinations.isdisjoint(all_sources), (
                        command.child_fd_map,
                        all_sources,
                    )
                    assert all(
                        f"/proc/self/fd/{target}" in " ".join(command.argv)
                        for target in destinations
                    )
        finally:
            if prepared is not None:
                prepared.close()
            for fd in reversed(pressure):
                os.close(fd)

    def test_preparation_pins_real_resources_and_precomputes_six_operations(
        self, tmp_path: Path
    ) -> None:
        sources = tmp_path / "sources"
        recovery = tmp_path / "recovery"
        override_parent = tmp_path / "override-parent"
        sources.mkdir(mode=0o700)
        recovery.mkdir(mode=0o700)
        override_parent.mkdir(mode=0o700)
        unit = sources / "llama-server.service"
        dropin = sources / "mtp.conf"
        override = sources / "cuda.conf"
        judge = sources / "llama-judge.service"
        for path, payload in (
            (unit, b"unit\n"),
            (dropin, b"dropin\n"),
            (override, b"override\n"),
            (judge, b"judge\n"),
        ):
            path.write_bytes(payload)
            path.chmod(0o600)

        prepared = cutover._prepare_cutover_resources_at(
            recovery_sources=(
                (unit, "llama-server.service"),
                (dropin, "mtp.conf"),
            ),
            recovery_directory=recovery,
            override_source=override,
            override_directory=override_parent,
            unit_fragments={
                "llama-server.service": unit,
                "llama-judge.service": judge,
            },
            install_executable=Path("/usr/bin/install"),
            systemctl_executable=Path("/usr/bin/systemctl"),
            expected_uid=os.getuid(),
        )
        try:
            assert isinstance(prepared, cutover.PreparedCutover)
            assert tuple(op.name for op in prepared.operations) == (
                cm.CUTOVER_ACTION_SET
            )
            assert {
                op.name: op.affected_refs for op in prepared.operations
            } == EXPECTED_CUTOVER_OPERATION_AFFECTED_REFS
            assert all(
                type(command.argv) is tuple
                for operation in prepared.operations
                for command in operation.commands
            )
            assert prepared.operations[-1].commands[0].argv == (
                "systemctl",
                "reboot",
            )
            assert prepared.operations[3].commands[0].argv == (
                "systemctl",
                "--user",
                "restart",
                "llama-server.service",
            )
            assert prepared.operations[4].commands[0].argv == (
                "systemctl",
                "--user",
                "restart",
                "llama-judge.service",
            )
            assert tuple(
                identity.unit_name for identity in prepared.unit_identities
            ) == ("llama-server.service", "llama-judge.service")
            assert tuple(
                artifact.label for artifact in prepared.installation_artifacts
            ) == ("cuda-override-source",)
            exact_seals = (
                fcntl.F_SEAL_WRITE
                | fcntl.F_SEAL_GROW
                | fcntl.F_SEAL_SHRINK
                | fcntl.F_SEAL_SEAL
            )
            for artifact in (
                *prepared.recovery_artifacts,
                *prepared.installation_artifacts,
                *(identity.fragment for identity in prepared.unit_identities),
            ):
                assert fcntl.fcntl(artifact.fd, fcntl.F_GET_SEALS) == exact_seals
                assert not os.get_inheritable(artifact.fd)
                with pytest.raises(PermissionError):
                    os.pwrite(artifact.fd, b"x", 0)
            assert all(
                not os.get_inheritable(directory.fd)
                for directory in prepared.directories
            )
            assert prepared.operations[0].commands[0].child_fd_map
            assert prepared.operations[1].commands[0].child_fd_map

            # In-place replacement changes neither name nor inode. Prepared
            # execution must still consume the byte snapshot made before the
            # human wait, not these later owner-writable source bytes.
            unit.write_bytes(b"unit-mutated-in-place\n")
            assert os.pread(
                prepared.recovery_artifacts[0].source_fd,
                len(b"unit\n") + 32,
                0,
            ) == b"unit\n"

            # Name substitution after preparation cannot change the held
            # source bytes or any already-rendered argv.
            replacement = sources / "replacement"
            unit.rename(replacement)
            unit.write_bytes(b"substitute\n")
            assert os.pread(
                prepared.recovery_artifacts[0].source_fd,
                len(b"unit\n"),
                0,
            ) == b"unit\n"
            assert all(
                "/proc/self/fd/" in argument
                for argument in prepared.operations[0].commands[0].argv[3:]
            )

            begin_source = inspect.getsource(cutover.PreparedCutover.begin)
            for forbidden in (
                "Path(",
                "subprocess.run",
                "systemctl show",
                "resolve",
                "os.open(",
            ):
                assert forbidden not in begin_source
            with pytest.raises(
                cutover.CutoverRefusal, match=r"^burn_content_invalid$"
            ):
                prepared.publish_and_validate_burn()
            with pytest.raises(
                cutover.CutoverRefusal, match=r"^executor_contract$"
            ):
                prepared.begin()
        finally:
            prepared.close()


class TestCutoverVoiceGateAdmission:
    """R8's unjudged result may pass only through R9's durable evidence rail."""

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

class TestBurnStructure:
    """The frozen burn sequence exists but has no assignable capability seam."""

    def test_frozen_burn_names_exist_without_a_provider_slot(self) -> None:
        assert hasattr(cutover, "PreparedCutover")
        assert hasattr(cutover.PreparedCutover, "begin")
        assert not inspect.isabstract(cutover.PreparedCutover)
        assert hasattr(cutover.PreparedCutover, "publish_and_validate_burn")
        assert not hasattr(cutover, "publish_and_validate_burn")
        assert not inspect.signature(cutover.execute_cutover).parameters
        assert not hasattr(cutover, "_CUTOVER_PREPARER")
        assert not hasattr(cutover, "_BURN_PUBLICATION")

    def test_marker_nondirectory_is_marker_dir_predicate(
        self, tmp_path: Path
    ) -> None:
        root = tmp_path / "bench"
        root.mkdir(mode=0o700)
        marker = root / cutover.MARKER_DIR
        marker.write_bytes(b"not a directory")
        marker.chmod(0o600)

        with pytest.raises(
            cutover.CutoverRefusal,
            match=r"^marker_dir_predicate$",
        ):
            cutover._pin_cutover_marker_chain(
                root=root,
                expected_uid=os.getuid(),
            )

    def test_production_preparer_routes_through_real_authority_before_burn(
        self,
    ) -> None:
        source = inspect.getsource(_closed_production_preparer())
        assert "authorize_and_stage" in source
        assert "preparation_unavailable" not in source
        assert "_attach_burn_publication" not in source

    def test_production_preparation_refuses_an_unreconstructible_selection(
        self,
    ) -> None:
        with pytest.raises(
            cutover.CutoverRefusal,
            match=r"^command_completion_invalid$",
        ):
            _closed_production_preparer()(FIXTURE_COMPLETION_LOCATOR)

    def test_begin_is_pre_bound_before_the_burn(self) -> None:
        """No descriptor lookup is allowed after the burn helper returns."""
        source = textwrap.dedent(inspect.getsource(cutover.execute_cutover))
        function = ast.parse(source).body[0]
        assert isinstance(function, ast.FunctionDef)

        bind_index = next(
            (
                index
                for index, statement in enumerate(function.body)
                if isinstance(statement, ast.Assign)
                and len(statement.targets) == 1
                and isinstance(statement.targets[0], ast.Name)
                and statement.targets[0].id == "begin"
                and isinstance(statement.value, ast.Call)
                and isinstance(statement.value.func, ast.Name)
                and statement.value.func.id == "method_type"
                and isinstance(statement.value.args[0], ast.Name)
                and statement.value.args[0].id == "begin_unbound"
            ),
            None,
        )
        burn_index = next(
            (
                index
                for index, statement in enumerate(function.body)
                if isinstance(statement, ast.Expr)
                and isinstance(statement.value, ast.Call)
                and isinstance(statement.value.func, ast.Name)
                and statement.value.func.id == "publish_and_validate_burn"
            ),
            None,
        )
        begin_index = next(
            (
                index
                for index, statement in enumerate(function.body)
                if isinstance(statement, ast.Return)
                and isinstance(statement.value, ast.Call)
                and isinstance(statement.value.func, ast.Name)
                and statement.value.func.id == "begin"
            ),
            None,
        )

        publisher_bind_index = next(
            index
            for index, statement in enumerate(function.body)
            if isinstance(statement, ast.Assign)
            and isinstance(statement.targets[0], ast.Name)
            and statement.targets[0].id == "publish_and_validate_burn"
            and isinstance(statement.value, ast.Call)
            and isinstance(statement.value.func, ast.Name)
            and statement.value.func.id == "method_type"
            and isinstance(statement.value.args[0], ast.Name)
            and statement.value.args[0].id == "publish_unbound"
        )
        assert bind_index < publisher_bind_index < burn_index
        assert burn_index + 1 == begin_index

    def test_exactly_one_executor_call_site(self) -> None:
        source = inspect.getsource(cutover)
        sites = [
            node
            for node in ast.walk(ast.parse(source))
            if isinstance(node, ast.Call)
            and getattr(node.func, "id", None) == "begin"
        ]

        assert len(sites) == 1, sites

    def test_cli_routes_to_the_zero_parameter_consumer_not_the_act1_minter(
        self,
    ) -> None:
        source = inspect.getsource(cutover.main)
        assert source.count("execute_cutover()") == 1
        assert "mint_cutover_authorization" not in source


class TestProductionConsumerOrchestration:
    """The tracked caller joins every authority rail in the frozen order."""

    def test_retap_after_spent_tap_binds_same_authorization_with_fresh_nonce(
        self, tmp_path: Path
    ) -> None:
        """Mechanical UNIQUE/store witness, not evidence of either real tap."""

        selected = _selected_binding_fixture("same-authorization")
        store_path = _valid_existing_authorization_store(tmp_path)
        store = s7.S7AuthorizationStore(store_path)
        grants = []
        rows = []
        preimages = []
        for ordinal in (1, 2):
            nonce = cutover._fresh_s7_attempt_nonce()
            params, envelope, authority, rendered = _mechanical_cutover_chain(
                selected=selected,
                nonce=nonce,
            )
            preimages.append(params)
            artifact_id = f"mechanical-retap-{ordinal}"
            store.put(
                s7.S7AuthorizationArtifact(
                    artifact_id=artifact_id,
                    request_id=envelope.request_id,
                    request_envelope_hash=s7.work_request_envelope_hash(envelope),
                    rendered_text_hash=rendered.rendered_text_hash,
                    action_params_hash=rendered.action_params_hash,
                    precondition_hash=envelope.precondition_hash,
                    authority_context_hash=s7.authority_context_hash(authority),
                    derived_work_class=envelope.derived_work_class,
                    derived_aggregation_group=envelope.derived_aggregation_group,
                    nonce=rendered.nonce,
                    credential_ref="mechanical-credential",
                    auth_method="founder_webauthn",
                    grant_source="founder_webauthn",
                    user_presence=True,
                    user_verification=True,
                    created_at="2026-08-07T12:00:00Z",
                    expires_at="2026-08-07T16:00:00Z",
                    consumed_at=None,
                    action=cm.CUTOVER_ACTION,
                )
            )
            with cutover.open_existing_authorization_store(
                db_path=store_path,
                expected_uid=os.getuid(),
            ) as opened:
                grant, callback_result, row = (
                    s7.consume_for_execution_with_committed_row(
                        opened.consumption_connection,
                        artifact_id,
                        rendered=rendered,
                        action_params_hash=rendered.action_params_hash,
                        authority_context=authority,
                        precondition_hash=envelope.precondition_hash,
                        derived_work_class="self_modification",
                        derived_aggregation_group=(
                            envelope.derived_aggregation_group
                        ),
                        now=f"2026-08-07T12:0{ordinal}:00Z",
                    )
                )
            assert callback_result is None
            assert grant is not None
            assert row is not None
            assert s7.committed_grant_row_proves_founder_self_modification(
                row, grant
            )
            grants.append(grant)
            rows.append(row)

        assert preimages[0] == preimages[1]
        assert preimages[0]["authorization_file_sha256"] == (
            selected.authorization_file_sha256
        )
        assert preimages[0]["authorization_binding_sha256"] == (
            selected.authorization.binding_sha256
        )
        assert grants[0].action_params_hash == grants[1].action_params_hash
        assert grants[0].nonce == rows[0].nonce
        assert grants[1].nonce == rows[1].nonce
        assert grants[0].nonce != grants[1].nonce
        with closing(sqlite3.connect(store_path)) as conn:
            nonce_indexes = tuple(
                row
                for row in conn.execute(
                    "PRAGMA index_list(s7_authorization_artifacts_v2)"
                )
                if row[1] == "s7_v2_nonce"
            )
        assert len(nonce_indexes) == 1
        assert nonce_indexes[0][2] == 1

    def test_artifact_not_binding_selected_authorization_refuses_presence_binding_mismatch(
        self,
    ) -> None:
        selected = _selected_binding_fixture("selected")
        other = _selected_binding_fixture("other")
        selected_params = cutover._cutover_action_preimage(selected)
        other_params = cutover._cutover_action_preimage(other)
        grant = replace(
            _s7_grant_fixture(),
            _mint_token=s7._EXECUTION_GRANT_TOKEN,
            request_id=selected.authorization.window_id,
            precondition_hash=selected.precondition_hash,
            action_params_hash=s7.canonical_hash(dict(other_params)),
        )

        with pytest.raises(
            cutover.CutoverRefusal,
            match=r"^presence_binding_mismatch$",
        ):
            cutover._require_cutover_grant_binding(
                grant=grant,
                selected=selected,
                action_params=selected_params,
            )

        control = replace(
            grant,
            _mint_token=s7._EXECUTION_GRANT_TOKEN,
            action_params_hash=s7.canonical_hash(dict(selected_params)),
        )
        cutover._require_cutover_grant_binding(
            grant=control,
            selected=selected,
            action_params=selected_params,
        )

    def test_zero_usable_credentials_refuses_without_a_fallback(self) -> None:
        with pytest.raises(
            cutover.CutoverRefusal,
            match=r"^presence_no_usable_credential$",
        ):
            cutover._select_cutover_credential(())

    def test_verified_store_identity_movement_across_wait_refuses(
        self, tmp_path: Path
    ) -> None:
        original = _valid_existing_authorization_store(
            tmp_path, name="original-store"
        )
        replacement = _valid_existing_authorization_store(
            tmp_path, name="replacement-store"
        )
        detached = original.with_name("detached-original.sqlite3")
        with cutover.open_existing_authorization_store(
            db_path=original,
            expected_uid=os.getuid(),
        ) as opened:
            opened.require_current_named_identity()
            original.rename(detached)
            replacement.rename(original)
            with pytest.raises(
                cutover.CutoverRefusal,
                match=r"^presence_store_identity_mismatch$",
            ):
                opened.require_current_named_identity()

    def test_verified_store_parent_movement_across_wait_refuses(
        self, tmp_path: Path
    ) -> None:
        store_path = _valid_existing_authorization_store(
            tmp_path, name="canonical-store-root"
        )
        canonical_parent = store_path.parent
        detached_parent = tmp_path / "detached-store-root"
        with cutover.open_existing_authorization_store(
            db_path=store_path,
            expected_uid=os.getuid(),
        ) as opened:
            opened.require_current_named_identity()
            canonical_parent.rename(detached_parent)
            canonical_parent.mkdir(mode=0o700)
            with pytest.raises(
                cutover.CutoverRefusal,
                match=r"^presence_store_identity_mismatch$",
            ):
                opened.require_current_named_identity()

    def test_ceremony_credential_reader_does_not_collapse_store_movement(
        self,
        tmp_path: Path,
    ) -> None:
        store_path = _valid_existing_authorization_store(tmp_path)
        detached = store_path.with_name("detached-ceremony.sqlite3")
        with cutover.open_existing_authorization_store(
            db_path=store_path,
            expected_uid=os.getuid(),
        ) as opened:
            ceremony = cutover.ExistingS7CeremonyStore(
                store_path,
                expected_uid=os.getuid(),
                opened=opened,
            )
            store_path.rename(detached)
            with pytest.raises(
                cutover.CutoverRefusal,
                match=r"^presence_store_identity_mismatch$",
            ):
                ceremony.list_credentials()

    def test_ceremony_credential_reads_close_every_held_connection(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        store_path = _valid_existing_authorization_store(tmp_path)
        with cutover.open_existing_authorization_store(
            db_path=store_path,
            expected_uid=os.getuid(),
        ) as opened:
            ceremony = cutover.ExistingS7CeremonyStore(
                store_path,
                expected_uid=os.getuid(),
                opened=opened,
            )
            real_open = s7._open_s7_connection_from_held_store
            connections: list[sqlite3.Connection] = []

            def record_opened_connection(**kwargs):
                connection = real_open(**kwargs)
                connections.append(connection)
                return connection

            monkeypatch.setattr(
                s7,
                "_open_s7_connection_from_held_store",
                record_opened_connection,
            )

            assert ceremony.list_credentials() == ()
            state = ceremony.credential_recovery_state()
            assert state["manual_recovery_cause"] == "first_setup_not_started"

            assert len(connections) == 3
            for connection in connections:
                with pytest.raises(sqlite3.ProgrammingError):
                    connection.execute("SELECT 1")

    def test_named_chain_movement_cannot_report_reusable_publication(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        root = tmp_path / "bench"
        markers = root / cutover.MARKER_DIR
        markers.mkdir(parents=True, mode=0o700)
        root.chmod(0o700)
        selected = _selected_binding_fixture("publication")
        action_params = cutover._cutover_action_preimage(selected)
        grant = replace(
            _s7_grant_fixture(),
            _mint_token=s7._EXECUTION_GRANT_TOKEN,
            artifact_id="publication-chain-moved",
            action_params_hash=s7.canonical_hash(dict(action_params)),
        )
        authorization = SimpleNamespace(
            nonce=selected.authorization.nonce,
            expires_at="2099-01-01T00:00:00Z",
        )
        publication = cutover._stage_burn_publication(
            root=root,
            expected_uid=os.getuid(),
            authorization=authorization,
            receipt=_cutover_consumption_fixture(),
            grant=grant,
            action_params=action_params,
            clock=lambda: "2000-01-01T00:03:00Z",
        )
        real_link = cutover.os.link

        def move_chain_then_fail(*_args, **_kwargs):
            markers.rename(root / "markers-detached")
            markers.mkdir(mode=0o700)
            raise OSError(5, "fixture EIO")

        monkeypatch.setattr(cutover.os, "link", move_chain_then_fail)
        try:
            with pytest.raises(
                cutover.CutoverRefusal,
                match=r"^publication_uncertain$",
            ):
                publication.publish_and_validate_burn()
            assert not publication.eligible
        finally:
            monkeypatch.setattr(cutover.os, "link", real_link)
            publication.close()

    def test_postpublication_clock_failure_is_not_reported_reusable(
        self, tmp_path: Path
    ) -> None:
        root = tmp_path / "bench"
        (root / cutover.MARKER_DIR).mkdir(parents=True, mode=0o700)
        root.chmod(0o700)
        selected = _selected_binding_fixture("post-clock")
        action_params = cutover._cutover_action_preimage(selected)
        grant = replace(
            _s7_grant_fixture(),
            _mint_token=s7._EXECUTION_GRANT_TOKEN,
            artifact_id="publication-post-clock",
            action_params_hash=s7.canonical_hash(dict(action_params)),
        )
        calls = 0

        def clock() -> str:
            nonlocal calls
            calls += 1
            if calls == 1:
                return "2000-01-01T00:03:00Z"
            raise OSError("clock read failed after publication")

        publication = cutover._stage_burn_publication(
            root=root,
            expected_uid=os.getuid(),
            authorization=SimpleNamespace(
                nonce=selected.authorization.nonce,
                expires_at="2099-01-01T00:00:00Z",
            ),
            receipt=_cutover_consumption_fixture(),
            grant=grant,
            action_params=action_params,
            clock=clock,
        )
        try:
            with pytest.raises(
                cutover.CutoverRefusal,
                match=r"^consumer_internal_post_pre_begin$",
            ):
                publication.publish_and_validate_burn()
            assert (root / cutover.MARKER_DIR / selected.authorization.nonce).is_file()
            assert not publication.eligible
        finally:
            publication.close()

    def test_missing_owner_read_and_assertion_refuses_without_a_tap(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def no_input(_prompt: str) -> str:
            raise EOFError

        monkeypatch.setattr("builtins.input", no_input)
        with pytest.raises(
            cutover.CutoverRefusal,
            match=r"^owner_presence_unattested$",
        ):
            cutover._read_owner_webauthn_finish(
                selected_credential_ref="credential-ref",
                challenge_id="challenge-id",
                response_sha256="a" * 64,
            )

    def test_consultation_mint_committed_consume_and_staging_are_one_caller(
        self,
    ) -> None:
        source = inspect.getsource(
            _closed_production_authorizer()
        )
        ordered = (
            # R11: the ceremony mints a TYPED ABSENCE where it used to
            # produce a consultation. The ordering property is unchanged --
            # evidence first, then guarded store, finish, consume, prove,
            # project, receipt, stage, attach.
            "mint_consultation_exemption(",
            "S7GuardedStateStore(",
            "service.authorize_finish(",
            "consume_for_execution_with_committed_row(",
            "committed_grant_row_proves_founder_self_modification(",
            "s7_execution_grant_projection_bytes(",
            "CutoverConsumptionReceipt(",
            "_stage_burn_publication(",
            "_attach_burn_publication(",
        )
        positions = tuple(source.index(fragment) for fragment in ordered)
        assert positions == tuple(sorted(positions))
        consume_call = next(
            node
            for node in ast.walk(
                ast.parse(textwrap.dedent(source))
            )
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "consume_for_execution_with_committed_row"
        )
        consume_keywords = {
            keyword.arg: keyword.value for keyword in consume_call.keywords
        }
        assert "after_consume_before_commit" in consume_keywords
        assert (
            ast.unparse(consume_keywords["after_consume_before_commit"])
            == "_revalidate_r11_after_consume"
        )
        assert "revalidate_r11_exemption_for_consumption(" in source

    def test_v34_preimage_and_fresh_nonce_flow_through_every_authority_edge(
        self,
    ) -> None:
        source = inspect.getsource(
            _closed_production_authorizer()
        )

        assert "action_params = _cutover_action_preimage(selected)" in source
        assert "envelope = _cutover_envelope_from_durable_selection(selected)" in source
        envelope_source = inspect.getsource(
            cutover._cutover_envelope_from_durable_selection
        )
        assert "params=dict(_cutover_action_preimage(selected))" in envelope_source
        assert "action_params=action_params" in source
        assert "nonce=_fresh_s7_attempt_nonce()" in source
        assert "_require_cutover_grant_binding(" in source
        assert "dict(cm.CUTOVER_ACTION_PARAMS)" not in source
        render_call = next(
            node
            for node in ast.walk(ast.parse(textwrap.dedent(source)))
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "render_request_statement"
        )
        nonce_keyword = next(
            keyword for keyword in render_call.keywords if keyword.arg == "nonce"
        )
        assert ast.unparse(nonce_keyword.value) == "_fresh_s7_attempt_nonce()"

    def test_burn_applies_the_exact_grant_as_the_last_prelink_state_change(
        self,
    ) -> None:
        source = textwrap.dedent(
            inspect.getsource(cutover.BurnPublication.publish_and_validate_burn)
        )
        function = ast.parse(source).body[0]
        calls = [
            (node.lineno, ast.unparse(node.func))
            for node in ast.walk(function)
            if isinstance(node, ast.Call)
        ]
        action_edge = next(
            line
            for line, name in calls
            if name.endswith("consume_execution_grant_for_action")
        )
        link = next(line for line, name in calls if name == "os.link")
        assert action_edge < link
        between = tuple(
            name for line, name in calls if action_edge < line < link
        )
        assert set(between) <= {"CutoverRefusal"}


class TestRuledConsumerIngress:
    """The zero-parameter consumer reads one fixed owner selection."""

    def test_no_parameterized_preparer_can_bypass_owner_completion_locator(
        self,
    ) -> None:
        assert not hasattr(cutover, "_prepare_selected_cutover_candidate")

    def test_fixed_selection_reader_accepts_one_private_canonical_artifact(
        self,
        tmp_path: Path,
    ) -> None:
        root = tmp_path / "bench"
        _write_completion_selection(root, FIXTURE_COMPLETION_LOCATOR)

        assert hasattr(cutover, "_read_completion_locator_at")
        assert cutover._read_completion_locator_at(root, os.getuid()) == (
            FIXTURE_COMPLETION_LOCATOR
        )

    def test_absent_fixed_selection_refuses_with_closed_reason(
        self,
        tmp_path: Path,
    ) -> None:
        _assert_completion_selection_positive_control(tmp_path / "control")
        absent = tmp_path / "absent"
        absent.mkdir(mode=0o700)

        assert _completion_selection_outcome(absent, os.getuid()) == (
            "refused",
            "completion_locator_unavailable",
        )

    def test_malformed_fixed_selection_refuses_with_closed_reason(
        self,
        tmp_path: Path,
    ) -> None:
        _assert_completion_selection_positive_control(tmp_path / "control")
        malformed = tmp_path / "malformed"
        selected = _write_completion_selection(
            malformed,
            FIXTURE_COMPLETION_LOCATOR,
        )
        selected.write_text(
            json.dumps(
                {
                    "fields": {
                        "completion_locator": FIXTURE_COMPLETION_LOCATOR,
                    },
                    "schema": "cuda_cutover.completion_selection.v1",
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        assert _completion_selection_outcome(malformed, os.getuid()) == (
            "refused",
            "completion_locator_unavailable",
        )

    def test_invalid_private_relative_locator_refuses_with_closed_reason(
        self,
        tmp_path: Path,
    ) -> None:
        _assert_completion_selection_positive_control(tmp_path / "control")
        invalid = tmp_path / "invalid-locator"
        _write_completion_selection(invalid, "receipts//terminal.json")

        assert _completion_selection_outcome(invalid, os.getuid()) == (
            "refused",
            "completion_locator_unavailable",
        )

    def test_json_depth_failure_refuses_with_closed_reason(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _assert_completion_selection_positive_control(tmp_path / "control")
        depth_failure = tmp_path / "depth-failure"
        _write_completion_selection(
            depth_failure,
            FIXTURE_COMPLETION_LOCATOR,
        )

        def fail_at_depth(_raw: bytes):
            raise RecursionError("JSON nesting limit")

        monkeypatch.setattr(cutover.json, "loads", fail_at_depth)

        assert _completion_selection_outcome(depth_failure, os.getuid()) == (
            "refused",
            "completion_locator_unavailable",
        )

    def test_unreadable_fixed_selection_refuses_with_closed_reason(
        self,
        tmp_path: Path,
    ) -> None:
        _assert_completion_selection_positive_control(tmp_path / "control")
        unreadable = tmp_path / "unreadable"
        selected = _write_completion_selection(
            unreadable,
            FIXTURE_COMPLETION_LOCATOR,
        )
        selected.chmod(0o000)

        assert _completion_selection_outcome(unreadable, os.getuid()) == (
            "refused",
            "completion_locator_unavailable",
        )

    def test_non_owner_owned_fixed_selection_refuses_with_closed_reason(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _assert_completion_selection_positive_control(tmp_path / "control")
        wrong_owner = tmp_path / "wrong-owner"
        _write_completion_selection(wrong_owner, FIXTURE_COMPLETION_LOCATOR)

        real_fstat = cutover.os.fstat
        real_stat = cutover.os.stat

        def foreign_owned(info: os.stat_result) -> os.stat_result:
            values = list(info)
            values[4] = info.st_uid + 1
            return os.stat_result(values)

        def fstat_with_foreign_file(fd: int) -> os.stat_result:
            info = real_fstat(fd)
            if stat_module.S_ISREG(info.st_mode):
                return foreign_owned(info)
            return info

        def stat_with_foreign_file(*args, **kwargs) -> os.stat_result:
            info = real_stat(*args, **kwargs)
            if stat_module.S_ISREG(info.st_mode):
                return foreign_owned(info)
            return info

        monkeypatch.setattr(cutover.os, "fstat", fstat_with_foreign_file)
        monkeypatch.setattr(cutover.os, "stat", stat_with_foreign_file)

        assert _completion_selection_outcome(wrong_owner, os.getuid()) == (
            "refused",
            "completion_locator_unavailable",
        )

    def test_symlinked_selection_component_or_leaf_refuses(
        self,
        tmp_path: Path,
    ) -> None:
        _assert_completion_selection_positive_control(tmp_path / "control")

        real_parent = tmp_path / "real"
        real_parent.mkdir(mode=0o700)
        real_root = real_parent / "bench"
        _write_completion_selection(real_root, FIXTURE_COMPLETION_LOCATOR)
        routed_parent = tmp_path / "routed"
        routed_parent.mkdir(mode=0o700)
        (routed_parent / "redirect").symlink_to(real_parent, target_is_directory=True)
        routed_root = routed_parent / "redirect" / "bench"

        leaf_root = tmp_path / "leaf-link"
        leaf_root.mkdir(mode=0o700)
        leaf_target = tmp_path / "selected-target.json"
        leaf_target.write_bytes(_completion_selection_bytes(FIXTURE_COMPLETION_LOCATOR))
        leaf_target.chmod(0o600)
        (leaf_root / "cutover-completion-selection.json").symlink_to(leaf_target)

        assert _completion_selection_outcome(routed_root, os.getuid()) == (
            "refused",
            "completion_locator_unavailable",
        )
        assert _completion_selection_outcome(leaf_root, os.getuid()) == (
            "refused",
            "completion_locator_unavailable",
        )

    def test_selection_leaf_open_pins_no_follow_nonblock_and_cloexec(self) -> None:
        source = textwrap.dedent(
            inspect.getsource(cutover._read_completion_locator_at)
        )
        function = ast.parse(source).body[0]
        selected_open = next(
            node
            for node in ast.walk(function)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "open"
            and node.args
            and isinstance(node.args[0], ast.Name)
            and node.args[0].id == "COMPLETION_SELECTION_NAME"
        )
        flags = {
            node.attr
            for node in ast.walk(selected_open.args[1])
            if isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id == "os"
        }

        assert flags == {"O_RDONLY", "O_NOFOLLOW", "O_NONBLOCK", "O_CLOEXEC"}

    def test_real_entrypoint_is_closed_over_the_fixed_reader_and_refusals(
        self,
    ) -> None:
        closed = inspect.getclosurevars(cutover.execute_cutover).nonlocals
        reader_closed = inspect.getclosurevars(
            cutover._read_owner_completion_locator
        ).nonlocals

        assert closed["read_owner_completion_locator"] is (
            cutover._read_owner_completion_locator
        )
        assert closed["prepare_selected_cutover"] is _closed_production_preparer()
        assert "publish_and_validate_burn" not in closed
        assert reader_closed["fixed_root"] == cutover.BENCH_ROOT
        assert reader_closed["fixed_expected_uid"] == os.getuid()
        assert reader_closed["read_completion_locator_at"] is (
            cutover._read_completion_locator_at
        )

    def test_entry_closes_original_prepared_type_and_unbound_methods(
        self,
    ) -> None:
        closed = inspect.getclosurevars(cutover.execute_cutover).nonlocals

        assert closed["prepared_type"] is cutover.PreparedCutover
        assert closed["publish_unbound"].__code__ is (
            cutover.PreparedCutover.publish_and_validate_burn.__code__
        )
        assert closed["publish_unbound"].__globals__ is not cutover.__dict__
        assert closed["begin_unbound"].__code__ is (
            cutover.PreparedCutover.begin.__code__
        )
        assert closed["begin_unbound"].__globals__ is not cutover.__dict__
        assert closed["execution_result_type"] is cutover.CutoverExecutionResult

    def test_bound_preparer_resists_recursive_module_attribute_replacement(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls: list[str] = []
        prepared_closed = inspect.getclosurevars(
            _closed_production_preparer()
        ).nonlocals

        def forged(*_args, **_kwargs):
            calls.append("forged")
            return object()

        for name in (
            "_reconstruct_selected_cutover_at",
            "_resolve_user_unit_fragments",
            "_prepare_cutover_resources_at",
            "_authorize_and_stage_selected_cutover",
        ):
            monkeypatch.setattr(cutover, name, forged, raising=False)

        with pytest.raises(
            cutover.CutoverRefusal,
            match=r"^command_completion_invalid$",
        ):
            _closed_production_preparer()(FIXTURE_COMPLETION_LOCATOR)

        for name in (
            "reconstruct",
            "resolve_units",
            "prepare_resources",
            "authorize_and_stage",
        ):
            assert prepared_closed[name] is not forged
            assert prepared_closed[name].__globals__ is not cutover.__dict__
        assert calls == []

    def test_the_ruled_entrypoint_has_no_injection_parameters(self) -> None:
        assert not inspect.signature(cutover.execute_cutover).parameters

    def test_nominal_provider_globals_cannot_bypass_the_block(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        calls: list[str] = []

        class _FabricatedPreparer:
            def prepare(self):
                calls.append("prepare")
                return object()

        class _FabricatedPublication:
            def publish_and_validate(self):
                calls.append("publish")

        monkeypatch.setattr(
            cutover,
            "_CUTOVER_PREPARER",
            _FabricatedPreparer(),
            raising=False,
        )
        monkeypatch.setattr(
            cutover,
            "_BURN_PUBLICATION",
            _FabricatedPublication(),
            raising=False,
        )
        monkeypatch.setattr(cutover, "BENCH_ROOT", Path("/tmp/forged-bench"))
        monkeypatch.setattr(
            cutover,
            "_read_completion_locator_at",
            lambda *_args: calls.append("locator") or "fabricated-terminal.json",
        )

        closed = inspect.getclosurevars(cutover.execute_cutover).nonlocals
        reader_closed = inspect.getclosurevars(
            cutover._read_owner_completion_locator
        ).nonlocals
        assert closed["prepare_selected_cutover"] is _closed_production_preparer()
        assert "publish_and_validate_burn" not in closed
        assert reader_closed["fixed_root"] == Path(
            "/home/rohit/maez/local/cuda_migration_bench"
        )
        assert reader_closed["read_completion_locator_at"] is not (
            cutover._read_completion_locator_at
        )
        assert "_CUTOVER_PREPARER" not in cutover.execute_cutover.__code__.co_names
        assert "_BURN_PUBLICATION" not in cutover.execute_cutover.__code__.co_names
        assert all(
            value not in closed.values()
            for value in (
                cutover._CUTOVER_PREPARER,
                cutover._BURN_PUBLICATION,
            )
        )
        assert calls == []

    def test_no_module_locator_or_selected_authority_callable_can_yield_burn_capability(
        self,
    ) -> None:
        assert not hasattr(cutover, "_prepare_selected_cutover")
        assert not hasattr(cutover, "_authorize_and_stage_selected_cutover")
        assert "completion_locator" in inspect.signature(
            _closed_production_preparer()
        ).parameters
        assert "selected" in inspect.signature(
            _closed_production_authorizer()
        ).parameters


class TestFrozenGraphKeepsBuiltins:
    """Found by RUNNING the ceremony, not by a test.

    The freezer replaces module-valued globals with immutable facades so a
    reassigned module attribute cannot redirect a production edge. It also
    replaced `__builtins__`, which CPython resolves by SUBSCRIPTING -- so
    every frozen function silently lost every builtin name. The live
    symptom was a clean size-cap refusal arriving as
    "TypeError: 'types.SimpleNamespace' object is not subscriptable" raised
    from an `except FileNotFoundError` line.
    """

    def _frozen_globals(self):
        import scripts.cuda_cutover as module

        for cell in cutover.execute_cutover.__closure__ or ():
            value = cell.cell_contents
            globals_ = getattr(value, "__globals__", None)
            if callable(value) and globals_ is not None and globals_ is not module.__dict__:
                return globals_
        raise AssertionError("no frozen function found in the entrypoint closure")

    def test_builtins_survive_the_freeze_as_a_real_mapping(self) -> None:
        frozen = self._frozen_globals()
        assert isinstance(frozen["__builtins__"], dict)

    def test_a_frozen_function_can_still_name_a_builtin_exception(self) -> None:
        from types import FunctionType

        def probe():
            try:
                raise ValueError("x")
            except FileNotFoundError:
                return "wrong handler"
            except ValueError:
                return "ok"

        clone = FunctionType(probe.__code__, self._frozen_globals(), "probe")
        assert clone() == "ok"

    def test_module_facades_are_still_frozen(self) -> None:
        """The hardening this freezer exists for must survive the fix."""
        from types import ModuleType

        frozen = self._frozen_globals()
        assert not isinstance(frozen["os"], ModuleType)


class TestPresenceRefusalNamesTheRealCause:
    """2026-08-13, live: /usr/bin/python3 has no py_webauthn, so authorize_begin
    failed CLOSED at its dependency gate -- correct -- but the mapper's default
    branch renamed the typed 503 to presence_assertion_invalid, pointing the
    owner at an assertion that never existed. A refusal that misnames its
    cause sends the investigation to the wrong layer; it cost a founder-key
    session to find that the interpreter, not the ceremony, was wrong."""

    def test_a_missing_webauthn_dependency_is_named_as_such(self) -> None:
        result = s7_ceremony.S7CeremonyServiceResult(
            body={
                "ok": False,
                "error": "s7_webauthn_dependency_missing",
                "library_name": "webauthn",
                "library_version": None,
            },
            status_code=503,
        )

        refusal = cutover._map_presence_finish_refusal(result)

        assert str(refusal) == "presence_dependency_missing"

    def test_the_new_code_is_in_the_closed_vocabulary(self) -> None:
        assert "presence_dependency_missing" in cutover.CUTOVER_REFUSALS

    def test_an_unknown_error_still_defaults_to_assertion_invalid(self) -> None:
        result = s7_ceremony.S7CeremonyServiceResult(
            body={"ok": False, "error": "s7_authentication_invalid"},
            status_code=409,
        )

        refusal = cutover._map_presence_finish_refusal(result)

        assert str(refusal) == "presence_assertion_invalid"


class TestOwnerGatePrintsTheFinishContract:
    """Live, 2026-08-13: the first run to reach the tap prompt could not
    succeed -- _read_owner_webauthn_finish refuses a paste without the exact
    challenge_id, and the gate never printed it. Everything the reader
    demands must appear in the gate output, as a template with one hole."""

    def test_the_gate_prints_every_field_the_finish_reader_requires(
        self, capsys
    ) -> None:
        exemption = _gate_exemption()
        projection_sha256 = s7.canonical_hash(exemption.projection())
        rendered = SimpleNamespace(rendered_text="S7 work-on-Maez authorization")

        cutover._print_owner_exemption_gate(
            exemption=exemption,
            projection_sha256=projection_sha256,
            rendered=rendered,
            begin_body={
                "challenge_id": "s7auth_gate-contract",
                "public_key_options": {"rpId": "localhost"},
            },
            credential_ref="cred-gate-contract",
        )

        printed = json.loads(capsys.readouterr().out)
        template = printed["webauthn_finish_template"]
        # The reader's exact equality checks (_read_owner_webauthn_finish):
        assert template["challenge_id"] == "s7auth_gate-contract"
        assert template["credential_ref"] == "cred-gate-contract"
        assert (
            template["consultation_exemption_projection_hash"]
            == projection_sha256
        )
        # The one hole the owner fills; the OTHER evidence binding must not
        # be suggested, mirroring the reader's mutual-exclusion refusal.
        assert "authentication_response" in template
        assert "maez_voice_raw_response_hash" not in template

    def test_a_template_paste_with_a_real_assertion_passes_the_reader(
        self, monkeypatch, capsys
    ) -> None:
        """The printed template, filled, is EXACTLY what the reader admits."""
        exemption = _gate_exemption()
        projection_sha256 = s7.canonical_hash(exemption.projection())
        rendered = SimpleNamespace(rendered_text="S7 work-on-Maez authorization")
        cutover._print_owner_exemption_gate(
            exemption=exemption,
            projection_sha256=projection_sha256,
            rendered=rendered,
            begin_body={
                "challenge_id": "s7auth_gate-roundtrip",
                "public_key_options": {"rpId": "localhost"},
            },
            credential_ref="cred-gate-roundtrip",
        )
        template = json.loads(capsys.readouterr().out)[
            "webauthn_finish_template"
        ]
        template["authentication_response"] = {"id": "assertion-fixture"}

        monkeypatch.setattr(
            "builtins.input", lambda prompt="": json.dumps(template)
        )

        accepted = cutover._read_owner_webauthn_finish(
            selected_credential_ref="cred-gate-roundtrip",
            challenge_id="s7auth_gate-roundtrip",
            exemption_projection_sha256=projection_sha256,
        )

        assert accepted["challenge_id"] == "s7auth_gate-roundtrip"
        assert accepted["authentication_response"] == {"id": "assertion-fixture"}


def _gate_exemption():
    """A structurally real exemption; the gate only projects it."""
    from core.governance import s7_consultation_exemption as r11

    return r11.S7ConsultationExemption(
        action=r11.R11_EXEMPT_ACTION,
        request_envelope_hash="a" * 64,
        reason_code=r11.R11_REASON_CODE,
        model_sha256_unchanged=r11.R11_EXPECTED_MODEL_SHA256,
        quality_evidence_sha256=r11.R11_EXPECTED_QUALITY_EVIDENCE_SHA256,
        action_params_hash="b" * 64,
        created_at="2026-08-13T12:00:00Z",
        _mint_token=r11._R11_MINT_TOKEN,
    )


class TestExecutorEvidence:
    """Live burn, 2026-08-13: the first install exited 1 printing only
    'install: No such file or directory', and the executor discarded which
    command, which fd, and whose message it was. Every synthetic
    reproduction of the spawn mechanics passes, so the executor itself must
    produce the evidence: verify each pinned fd's identity before spawning,
    and capture a failing command's stderr into the refusal diagnostic."""

    def _prepared(self, tmp_path):
        """Prepared burn program that is REBOOT-PROOF by construction.

        2026-08-13, three times: this class pinned the real
        /usr/bin/systemctl, the install step expected to fail SUCCEEDED
        (GNU install treats a directory destination as install-into), and
        begin() ran the whole precomputed program -- including the final
        `systemctl reboot`. The owner's machine went down mid-session. A
        test touching PreparedCutover.begin must never hold a descriptor
        to anything that can mutate the host: systemctl here is a scratch
        script, and the tripwire below re-reads every pinned executable."""
        sources = tmp_path / "sources"
        recovery = tmp_path / "recovery"
        override_parent = tmp_path / "override-parent"
        sources.mkdir(mode=0o700)
        recovery.mkdir(mode=0o700)
        override_parent.mkdir(mode=0o700)
        unit = sources / "llama-server.service"
        dropin = sources / "mtp.conf"
        override = sources / "cuda.conf"
        judge = sources / "llama-judge.service"
        for path, payload in (
            (unit, b"unit\n"),
            (dropin, b"dropin\n"),
            (override, b"override\n"),
            (judge, b"judge\n"),
        ):
            path.write_bytes(payload)
            path.chmod(0o600)
        # The systemctl seat is filled by /usr/bin/install: a real ELF (a
        # shebang script cannot be exec'd via /proc/self/fd -- CLOEXEC has
        # closed the fd before the interpreter reopens its script path), it
        # refuses `--user daemon-reload` loudly and deterministically, and
        # even a hypothetical run of the final operation would be
        # `install reboot` -- a missing-operand error, never a reboot.
        fake_systemctl = Path("/usr/bin/install")
        prepared = cutover._prepare_cutover_resources_at(
            recovery_sources=(
                (unit, "llama-server.service"),
                (dropin, "mtp.conf"),
            ),
            recovery_directory=recovery,
            override_source=override,
            override_directory=override_parent,
            unit_fragments={
                "llama-server.service": unit,
                "llama-judge.service": judge,
            },
            install_executable=Path("/usr/bin/install"),
            systemctl_executable=fake_systemctl,
            expected_uid=os.getuid(),
        )
        # Tripwire: no pinned executable may be the real systemctl. install
        # is tolerated -- it only writes where the scratch argv points.
        for executable in prepared.executables:
            target = os.readlink(f"/proc/self/fd/{executable.fd}")
            assert target != "/usr/bin/systemctl", (
                "test pinned the REAL systemctl; begin() would reboot the host"
            )
        # Stand-in for a completed burn publication; close() must exist
        # because PreparedCutover.close() closes it.
        prepared._burn_publication = SimpleNamespace(
            eligible=True, _published=True, close=lambda: None
        )
        return prepared, recovery

    def test_the_new_code_is_in_the_closed_vocabulary(self) -> None:
        assert "executor_pin_lost" in cutover.CUTOVER_REFUSALS

    def test_begin_refuses_a_lost_pin_by_name_without_spawning(
        self, tmp_path, capsys
    ) -> None:
        prepared, _recovery = self._prepared(tmp_path)
        spawned = []
        prepared._posix_spawn = lambda *args, **kwargs: spawned.append(args)

        lost = prepared.recovery_artifacts[0]
        os.close(lost.fd)

        with pytest.raises(cutover.CutoverRefusal, match=r"^executor_pin_lost$"):
            prepared.begin()

        assert spawned == []
        assert lost.label in capsys.readouterr().out

    def test_begin_refuses_a_recycled_pin_number_without_spawning(
        self, tmp_path, capsys
    ) -> None:
        """The suspected live shape: the NUMBER is open but belongs to
        something else now. fstat succeeds; the identity must not match."""
        prepared, _recovery = self._prepared(tmp_path)
        spawned = []
        prepared._posix_spawn = lambda *args, **kwargs: spawned.append(args)

        lost = prepared.recovery_artifacts[0]
        os.close(lost.fd)
        impostor = os.open("/usr/bin/install", os.O_RDONLY)
        assert impostor == lost.fd, "test needs the number recycled"

        try:
            with pytest.raises(
                cutover.CutoverRefusal, match=r"^executor_pin_lost$"
            ):
                prepared.begin()
        finally:
            try:
                os.close(impostor)
            except OSError:
                pass

        assert spawned == []
        assert lost.label in capsys.readouterr().out

    def test_begin_reports_a_failing_commands_own_stderr(
        self, tmp_path, capsys
    ) -> None:
        """The stand-in systemctl refuses `--user` at daemon_reload; the
        executor must surface ITS message, not discard it. The two install
        operations before it succeed into scratch, witnessing that a
        mid-program failure reports the failing command specifically."""
        prepared, recovery = self._prepared(tmp_path)

        with pytest.raises(cutover.CutoverRefusal, match=r"^executor_failed$"):
            prepared.begin()

        printed = capsys.readouterr().out
        # Multi-call coreutils dispatches on argv[0] ("systemctl") and
        # refuses it by name -- deterministic, and structurally reboot-proof.
        assert "unknown program 'systemctl'" in printed
        assert "exited 1" in printed
        assert "daemon-reload" in printed
        # The postmortem captures both views of the failed command's fds:
        # parent-side readlinks and the child's own /proc/self/fd listing
        # under the same dup2 actions.
        assert "postmortem: executable_fd=" in printed
        assert "child /proc/self/fd under the same dup2 actions" in printed
        # The installs before the failure really ran, into scratch only.
        assert (recovery / "llama-server.service").read_bytes() == b"unit\n"
        assert (recovery / "mtp.conf").read_bytes() == b"dropin\n"


class TestPresenceRefusalPrintsTheCeremonyError:
    """Four live attempts were spent guessing which ceremony error hid
    behind presence_assertion_invalid. The closed refusal vocabulary
    stays; the ceremony's own error code is printed for the owner."""

    def test_the_ceremony_error_code_is_printed(self, capsys) -> None:
        result = s7_ceremony.S7CeremonyServiceResult(
            body={"ok": False, "error": "s7_challenge_replayed"},
            status_code=410,
        )

        refusal = cutover._map_presence_finish_refusal(result)

        assert str(refusal) == "presence_assertion_invalid"
        assert (
            "presence refusal: s7_challenge_replayed"
            in capsys.readouterr().out
        )

    def test_verifier_detail_and_reason_are_printed_when_present(
        self, capsys
    ) -> None:
        result = s7_ceremony.S7CeremonyServiceResult(
            body={
                "ok": False,
                "error": "s7_authentication_invalid",
                "detail": "InvalidSignature",
                "reason": "Could not verify authentication signature",
            },
            status_code=400,
        )

        cutover._map_presence_finish_refusal(result)

        printed = capsys.readouterr().out
        assert "s7_authentication_invalid" in printed
        assert "detail=InvalidSignature" in printed
        assert "reason=Could not verify authentication signature" in printed


class TestInstallOverExistingDestination:
    """The FOURTH live failure's root cause, proven by strace: uutils
    install 0.8.0 runs a same-file guard ONLY when the destination already
    exists, and that guard resolves /proc/self/fd magic links by walking
    them as STRINGS -- a memfd source resolves to the literal text
    '/memfd:... (deleted)', which is no path at all, so install exits with
    a bare ENOENT. Every earlier probe passed because scratch destinations
    were empty; the live recovery directory held prior copies. The
    prepared program now removes each destination (rm -f, dispatched
    through the SAME pinned multi-call binary) before installing."""

    def test_the_burn_replaces_existing_destinations(self, tmp_path) -> None:
        evidence = TestExecutorEvidence()
        prepared, recovery = evidence._prepared(tmp_path)
        # The live condition: destinations already hold earlier copies.
        (recovery / "llama-server.service").write_bytes(b"stale copy\n")
        (recovery / "llama-server.service").chmod(0o600)
        (recovery / "mtp.conf").write_bytes(b"stale dropin\n")
        (recovery / "mtp.conf").chmod(0o600)
        override_dir = tmp_path / "override-parent"
        (override_dir / "zz-b9596-cuda.conf").write_bytes(b"stale override\n")
        (override_dir / "zz-b9596-cuda.conf").chmod(0o600)

        # The reboot-proof systemctl seat fails at daemon_reload -- AFTER
        # both install operations, which must now have succeeded.
        with pytest.raises(cutover.CutoverRefusal, match=r"^executor_failed$"):
            prepared.begin()

        assert (recovery / "llama-server.service").read_bytes() == b"unit\n"
        assert (recovery / "mtp.conf").read_bytes() == b"dropin\n"
        assert (
            override_dir / "zz-b9596-cuda.conf"
        ).read_bytes() == b"override\n"

    def test_every_install_is_preceded_by_rm_of_its_destination(
        self, tmp_path
    ) -> None:
        evidence = TestExecutorEvidence()
        prepared, _recovery = evidence._prepared(tmp_path)

        for operation in prepared.operations[:2]:
            argvs = [command.argv for command in operation.commands]
            assert len(argvs) % 2 == 0, argvs
            for rm_argv, install_argv in zip(
                argvs[0::2], argvs[1::2], strict=True
            ):
                assert rm_argv[:2] == ("rm", "-f")
                assert install_argv[:3] == ("install", "-m", "0600")
                # The rm targets exactly the path install writes.
                assert rm_argv[2] == install_argv[4]
