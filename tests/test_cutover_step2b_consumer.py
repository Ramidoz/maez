"""Cutover step 2B — the consumer primitive. RED set, slice 1.

Written against ratified design v25 BEFORE implementation.

Slice 1 covers the contracts that are unambiguous from the frozen design
and testable without a live S7 ceremony: the receipt's v2 shape, the
action contract measured against the real classifier, the grant
projection, the store opener's refusals, the consultation producer's
signature, and the burn's structural adjacency.

Deliberately NOT here: a full end-to-end ceremony. It needs a founder
WebAuthn assertion, which cannot be produced without a physical key tap.
Asserting one exists would be the fabrication this project refuses.

Expected pre-implementation failure taxonomy:

* ActionContract   -> CUTOVER_ACTION / CUTOVER_ACTION_PARAMS absent.
* ReceiptV2        -> the two presence fields do not exist yet.
* GrantProjection  -> the projection helper and schema literal are absent.
* StoreOpener      -> open_existing_authorization_store is absent.
* Consultation     -> produce_cutover_consultation is absent.
* BurnStructure    -> publish_and_validate_burn / prepare_cutover absent.
* NoFallback       -> a GUARD: `procedural` must be unreachable for
  cutover, asserted on the closed value set.
"""

from __future__ import annotations

import ast
import inspect
import sqlite3
import textwrap
from contextlib import closing
from dataclasses import fields as dataclass_fields
from pathlib import Path

import pytest

from core.governance import operator_user_boundary as s7
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


def _s7_grant_fixture() -> s7.S7ExecutionGrant:
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
        credential_ref="credential-1",
        auth_method="founder_webauthn",
        grant_source="founder_webauthn",
        consumed_at="2000-01-01T00:01:00Z",
        ceremony_kind="founder_local_webauthn",
        _mint_token=s7._EXECUTION_GRANT_TOKEN,
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

    def test_active_family_count_stays_twenty_six(self) -> None:
        """A REPLACEMENT, not an addition: v1 has no durable artifact."""
        assert len(cm.ACTIVE_SCHEMA_FAMILIES) == 26

    def test_presence_mode_is_a_closed_value(self) -> None:
        assert cm.PRESENCE_MODES == ("founder_webauthn", "procedural")

    def test_cutover_may_not_emit_procedural(self) -> None:
        """Part 3: zero usable credentials REFUSES; there is no fallback."""
        assert cm.CUTOVER_PRESENCE_MODE == "founder_webauthn"
        assert "presence_no_usable_credential" in cutover.CUTOVER_REFUSALS


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

    def test_a_missing_store_refuses_and_creates_nothing(
        self, tmp_path: Path
    ) -> None:
        missing = tmp_path / "absent.sqlite3"
        with pytest.raises(cutover.CutoverRefusal):
            cutover.open_existing_authorization_store(
                db_path=missing, expected_uid=0
            )
        assert not missing.exists()

    def test_it_never_constructs_the_mutating_stores(self) -> None:
        """S7AuthorizationStore.__init__ mkdirs, executescripts, ALTERs and
        commits; S7WebAuthnBootstrapStore likewise. Constructing either at
        this seam would WRITE while merely asking who is present."""
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

    def test_the_producer_exists(self) -> None:
        assert hasattr(cutover, "produce_cutover_consultation")

    def test_its_signature_is_the_frozen_contract(self) -> None:
        params = inspect.signature(
            cutover.produce_cutover_consultation
        ).parameters
        assert set(params) == {"envelope", "attempt", "ask", "now"}

    def test_the_result_keeps_the_reader_attempt_separate(self) -> None:
        """Never collapsed to a boolean: a failed read is not a refusal."""
        from dataclasses import fields as dataclass_fields

        names = {
            f.name for f in dataclass_fields(cutover.CutoverConsultationResult)
        }
        assert {"consultation", "raw_response", "reader_attempt"} <= names

    def test_the_failure_outcomes_are_closed_and_none_default_to_approval(
        self,
    ) -> None:
        assert cutover.CONSULTATION_FAILURES == (
            "consultation_unavailable",
            "response_unreadable",
            "semantic_reader_failed",
            "objection_recorded",
            "consultation_withdrawn",
            "bundle_unreservable",
        )

    def test_the_consultation_id_is_never_none(self) -> None:
        assert hasattr(cutover, "ConsultationAttempt")
        params = inspect.signature(cutover.ConsultationAttempt).parameters
        assert "attempt_identity" in params

    def test_the_prompt_cycle_is_not_used_to_ask(self) -> None:
        """expected_s7_voice_rendered_prompt_text requires BOTH a rendered
        statement and a consultation, so it cannot ask the question that
        produces the consultation. It is replay material after rendering."""
        source = (REPO / "scripts" / "cuda_cutover.py").read_text()
        assert "expected_s7_voice_rendered_prompt_text" not in source


class TestBurnStructure:
    """Nothing between the burn and the first mutation."""

    def test_the_closed_publication_helper_exists(self) -> None:
        assert hasattr(cutover, "publish_and_validate_burn")

    def test_prepare_returns_a_pinned_capability(self) -> None:
        assert hasattr(cutover, "prepare_cutover")
        assert hasattr(cutover, "PreparedCutover")
        assert hasattr(cutover.PreparedCutover, "begin")

    def test_begin_is_pre_bound_before_the_burn(self) -> None:
        """An attribute lookup after the burn could run a descriptor or
        fail in the one region where nothing may happen."""
        source = inspect.getsource(cutover.execute_cutover)
        tree = ast.parse(source.lstrip())
        binds: list[int] = []
        burns: list[int] = []
        calls: list[int] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign) and isinstance(
                node.value, ast.Attribute
            ):
                if node.value.attr == "begin":
                    binds.append(node.lineno)
            if isinstance(node, ast.Call):
                name = (
                    node.func.attr
                    if isinstance(node.func, ast.Attribute)
                    else getattr(node.func, "id", None)
                )
                if name == "publish_and_validate_burn":
                    burns.append(node.lineno)
                if name == "begin":
                    calls.append(node.lineno)
        assert binds and burns and calls
        assert binds[0] < burns[0] < calls[0]

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
