"""S7 v2 exact action binding — RED set, slice 1: the generic bypass.

Written against ratified design v15 BEFORE implementation.

The defect this slice exists to close: execution_grant_authorizes_action
compares only the derived work class and canonical_hash(params). Neither
carries the action, so ONE grant authorizes every sibling operation of
the same class with identical params. At the S7 layer a tap for "switch
to CUDA" is a tap for "some self_modification with these arguments".

These reds are at the GENERIC edge, not in the cutover consumer. A
consumer-local check cannot make a generic grant refuse anything.
"""

from __future__ import annotations

import inspect

import pytest

from core.governance import operator_user_boundary as s7

SIBLING_PARAMS = {
    "window_id": "cutover-20260713-1202",
    "authorization_file_sha256": "a" * 64,
}


class TestTheBypassExistsToday:
    """GUARDS on the defect itself, so the fix is provably a fix."""

    def test_sibling_actions_derive_the_same_class(self) -> None:
        assert s7.derive_work_class(
            action="model_routing.cutover_cuda", params=dict(SIBLING_PARAMS)
        ) == s7.derive_work_class(
            action="model_routing.wipe_and_replace", params=dict(SIBLING_PARAMS)
        )

    def test_the_edge_reads_neither_an_action_field(self) -> None:
        """Today's comparison is class + params hash only."""
        source = inspect.getsource(s7.execution_grant_authorizes_action)
        assert "derived_work_class" in source
        assert "action_params_hash" in source


class TestActionTravelsEveryCarrier:
    """The exact action must survive envelope -> row -> grant."""

    def test_envelope_retains_the_action(self) -> None:
        from dataclasses import fields

        assert "action" in {f.name for f in fields(s7.WorkRequestEnvelope)}

    def test_the_authorization_artifact_carries_the_action(self) -> None:
        from dataclasses import fields

        assert "action" in {f.name for f in fields(s7.S7AuthorizationArtifact)}

    def test_the_execution_grant_carries_the_action(self) -> None:
        from dataclasses import fields

        assert "action" in {f.name for f in fields(s7.S7ExecutionGrant)}

    def test_the_rendered_statement_carries_the_action(self) -> None:
        from dataclasses import fields

        assert "action" in {f.name for f in fields(s7.RenderedRequestStatement)}


class TestTheActionIsVISIBLE:
    """"What you see is what you sign" cannot be met by a hash."""

    def test_the_rendered_text_shows_an_exact_action_line(self) -> None:
        assert hasattr(s7, "render_request_statement")
        assert s7.RENDERER_VERSION == "s7.rendered_request.v2"

    def test_the_action_line_sits_between_request_id_and_work_class(
        self,
    ) -> None:
        order = s7.RENDERED_STATEMENT_FIELD_ORDER
        assert order.index("Request id") < order.index("Action")
        assert order.index("Action") < order.index("Work class")


class TestTheGenericEdgeRefusesSiblings:
    """THE binding red. Generic, not cutover-specific."""

    def test_a_grant_refuses_a_sibling_action_with_identical_params(
        self,
    ) -> None:
        grant = s7.S7ExecutionGrant(
            artifact_id="a" * 32,
            request_id="r" * 32,
            request_envelope_hash="b" * 64,
            rendered_text_hash="c" * 64,
            action_params_hash=s7.canonical_hash(dict(SIBLING_PARAMS)),
            precondition_hash="d" * 64,
            authority_context_hash="e" * 64,
            derived_work_class="self_modification",
            derived_aggregation_group="g",
            nonce="n" * 64,
            credential_ref="cred",
            auth_method="founder_webauthn",
            grant_source="founder_webauthn",
            consumed_at="2026-08-07T12:00:00Z",
            ceremony_kind="founder_local_webauthn",
            action="model_routing.cutover_cuda",
            _mint_token=s7._GRANT_MINT_TOKEN,
        )
        assert s7.execution_grant_authorizes_action(
            grant,
            action="model_routing.cutover_cuda",
            params=dict(SIBLING_PARAMS),
        )
        assert not s7.execution_grant_authorizes_action(
            grant,
            action="model_routing.wipe_and_replace",
            params=dict(SIBLING_PARAMS),
        )


class TestActionGrammar:
    """It must not close roads already in use."""

    @pytest.mark.parametrize(
        "action",
        [
            "write_soul_note",
            "edit_soul_section",
            "register_backup_webauthn_credential",
            "disable_founder_webauthn_credential",
            "run_shell",
            "backup_status",
            "model_routing.cutover_cuda",
        ],
    )
    def test_every_existing_action_is_accepted(self, action: str) -> None:
        assert s7.validate_action_literal(action) == action

    @pytest.mark.parametrize(
        "action",
        ["a\nb", "a\tb", ".x", "x.", "x..y", "X", "a b", "", "a" * 129],
    )
    def test_malformed_actions_refuse_at_construction(self, action: str) -> None:
        with pytest.raises(ValueError):
            s7.validate_action_literal(action)


class TestHistoricalV1CannotAuthorize:
    """v1 records stay auditable and can never authorize execution."""

    def test_an_unexpired_v1_row_still_refuses(self) -> None:
        """An EXPIRED v1 row would refuse for the wrong reason -- all four
        live rows are expired, so the test must construct an unexpired one."""
        assert hasattr(s7, "v1_row_may_authorize")
        assert s7.v1_row_may_authorize(expired=False) is False
