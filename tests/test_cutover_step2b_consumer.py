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
from pathlib import Path

import pytest

from core.governance import operator_user_boundary as s7
from scripts import cuda_cutover as cutover
from scripts import cuda_migration as cm

REPO = Path(__file__).resolve().parents[1]


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

    def test_affected_refs_name_the_real_mutation_targets(self) -> None:
        refs = set(
            s7.derive_affected_refs(
                action=cm.CUTOVER_ACTION, params=dict(cm.CUTOVER_ACTION_PARAMS)
            )
        )
        assert "service:llama-server.service" in refs, refs
        assert any(r.startswith("file:") and "zz-b9596-cuda" in r for r in refs), refs

    def test_no_synthetic_classifier_ref_is_derived(self) -> None:
        refs = s7.derive_affected_refs(
            action=cm.CUTOVER_ACTION, params=dict(cm.CUTOVER_ACTION_PARAMS)
        )
        assert "file:model_routing" not in refs, refs


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
        assert (
            cm.S7_GRANT_PROJECTION_SCHEMA
            == "cuda_migration.s7_execution_grant_projection.v1"
        )

    def test_projection_covers_every_grant_field(self) -> None:
        from dataclasses import fields as dataclass_fields

        expected = tuple(f.name for f in dataclass_fields(s7.S7ExecutionGrant))
        assert cm.S7_GRANT_PROJECTION_FIELDS == expected
        assert len(expected) == 15

    def test_the_private_mint_token_is_structurally_excluded(self) -> None:
        """_mint_token is an InitVar, so it is not a dataclass field at all
        -- the exclusion cannot be forgotten."""
        from dataclasses import fields as dataclass_fields

        names = {f.name for f in dataclass_fields(s7.S7ExecutionGrant)}
        assert "_mint_token" not in names

    def test_every_projected_field_has_a_committed_row_column(self) -> None:
        """Reconstruction from durable state is the whole point."""
        source = inspect.getsource(s7)
        start = source.index("s7_authorization_artifacts (")
        columns = source[start : source.index(")", start)]
        for name in cm.S7_GRANT_PROJECTION_FIELDS:
            assert name in columns, name


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
