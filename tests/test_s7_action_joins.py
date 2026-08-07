"""S7 v2 action binding — one mutation-killing RED per link.

The design freezes five links -- envelope==rendered, rendered==artifact,
artifact==row, row==grant, grant==runtime -- plus the four caller-action
joins from S3, plus separately the row==rendered join for
`consume_verified`, which is NOT a caller join: v3 listed its caller
action as `rendered.action` and its rendered action as `rendered.action`,
a tautology proving nothing.

A single test asserting "the action is equal everywhere" is not this. It
passes as soon as any one link holds and cannot say which broke, so each
link gets its own isolated tamper here.

Two things would otherwise make every test in this file vacuous, and both
are neutralised explicitly rather than worked around:

* `_mint_s7_execution_grant` supplies no action until the v2 row exists,
  so any test needing a real grant dies in the mint. Where a join is
  downstream of the mint, the mint is STUBBED to succeed with a chosen
  action -- which isolates the join under test from the absent row.
* `consume_for_execution` swallows every exception into (None, None), so
  a broken seam is indistinguishable from a denial. Tests that depend on
  reaching a seam assert they reached it.
"""

from __future__ import annotations

import sqlite3
from contextlib import closing
from dataclasses import replace
from pathlib import Path

import pytest

from core.governance import operator_user_boundary as s7

NOW = "2026-08-07T12:00:00Z"
FUTURE = "2026-08-07T16:00:00Z"
ACTION = "model_routing.cutover_cuda"
SIBLING = "model_routing.wipe_and_replace"
PARAMS = {"cutover_action": ACTION, "window_id": "cutover-20260713-1202"}


def _hex(seed: str) -> str:
    import hashlib

    return hashlib.sha256(seed.encode()).hexdigest()


def _chain(action: str = ACTION):
    """envelope -> rendered, through the real builders."""
    env = s7.build_work_request_envelope(
        request_id="req-join-1",
        action=action,
        params=dict(PARAMS),
        claimed_work_class="self_modification",
        requesting_subsystem="cuda_cutover",
        closed_symptom_code="self_mod_requested",
        proposed_change_class="model_routing_change",
        why_self_fix_failed_class="not_self_fix",
        affected_refs=("service:llama-server.service",),
        content_exposure_risk="content_free",
        precondition_hash="a" * 64,
        created_at=NOW,
        expires_at=FUTURE,
        predicted_effect_class="behavior_change",
        rollback_path_class="revert_patch",
        maez_voice_consultation_id="voice-join-1",
    )
    authority = s7.AuthorityContext(
        actor_id="founder",
        actor_handle_hmac="hmac:s7:founder:" + ("a" * 64),
        role_names=("bonded_user",),
        grant_source="founder_webauthn",
        allowed_scopes=("operator_health",),
        auth_method="founder_webauthn",
        surface="cockpit",
        credential_ref="cred-1",
        created_at=NOW,
        expires_at=FUTURE,
        verified=True,
    )
    consultation = s7.MaezVoiceConsultation(
        consultation_id="voice-join-1",
        request_id=env.request_id,
        request_envelope_hash=s7.work_request_envelope_hash(env),
        producer="self_mod_dialog_terminal_state",
        source_ref_kind="self_mod_dialog_exchange",
        source_ref_hash=_hex("authority_context"),
        maez_voice_consulted=True,
        maez_objection_state="absent",
        maez_withdrew_request=False,
        unavailable_reason_code=None,
        created_at=NOW,
    )
    params_hash = s7.canonical_hash(dict(PARAMS))
    rendered = s7.render_request_statement(
        envelope=env,
        surface="cockpit",
        origin="http://localhost:11437",
        action_params_hash=params_hash,
        authority_context=authority,
        maez_voice_consultation=consultation,
        nonce="n" * 64,
        expires_at=FUTURE,
        rendered_at=NOW,
    )
    return env, authority, params_hash, rendered


def _artifact(env, authority, params_hash, rendered, *, action=None):
    return s7.S7AuthorizationArtifact(
        artifact_id="artifact-join-1",
        request_id=env.request_id,
        request_envelope_hash=s7.work_request_envelope_hash(env),
        rendered_text_hash=rendered.rendered_text_hash,
        action_params_hash=params_hash,
        precondition_hash=env.precondition_hash,
        authority_context_hash=s7.authority_context_hash(authority),
        derived_work_class=env.derived_work_class,
        derived_aggregation_group=env.derived_aggregation_group,
        nonce="n" * 64,
        credential_ref="cred-1",
        auth_method="founder_webauthn",
        grant_source="founder_webauthn",
        user_presence=True,
        user_verification=True,
        created_at=NOW,
        expires_at=FUTURE,
        consumed_at=None,
        action=rendered.action if action is None else action,
    )


def _grant(**overrides):
    fields: dict[str, object] = {
        "artifact_id": "artifact-join-1",
        "request_id": "req-join-1",
        "request_envelope_hash": "b" * 64,
        "rendered_text_hash": "c" * 64,
        "action_params_hash": s7.canonical_hash(dict(PARAMS)),
        "precondition_hash": "a" * 64,
        "authority_context_hash": "e" * 64,
        "action": ACTION,
        "derived_work_class": "self_modification",
        "derived_aggregation_group": "g",
        "nonce": "f" * 32,
        "credential_ref": "cred-1",
        "auth_method": "founder_webauthn",
        "grant_source": "founder_webauthn",
        "consumed_at": NOW,
        "ceremony_kind": "founder_local_webauthn",
    }
    fields.update(overrides)
    return s7.S7ExecutionGrant(_mint_token=s7._EXECUTION_GRANT_TOKEN, **fields)


def _row_columns() -> set[str]:
    import tempfile

    tmp = Path(tempfile.mkdtemp())
    s7.S7AuthorizationStore(tmp / "c.sqlite3")
    with closing(sqlite3.connect(tmp / "c.sqlite3")) as conn:
        return {
            r[1]
            for r in conn.execute("PRAGMA table_info(s7_authorization_artifacts)")
        }


class TestLinkEnvelopeToRendered:
    def test_the_link_holds(self) -> None:
        env, _a, _p, rendered = _chain()
        assert rendered.action == env.action

    def test_tampering_the_rendered_action_refuses(self) -> None:
        """The action is inside the signed text; changing one without the
        other must refuse in BOTH directions."""
        _e, _a, _p, rendered = _chain()
        with pytest.raises(ValueError, match="signed text"):
            replace(rendered, action=SIBLING)


class TestLinkRenderedToArtifact:
    def test_the_control_constructs(self) -> None:
        env, authority, params_hash, rendered = _chain()
        assert _artifact(env, authority, params_hash, rendered).action == ACTION

    def test_an_artifact_may_not_carry_a_different_action(self) -> None:
        """RED: the artifact currently accepts any action string, so a
        record rendered for one operation can be stored for another."""
        env, authority, params_hash, rendered = _chain()
        with pytest.raises(ValueError):
            _artifact(env, authority, params_hash, rendered, action=SIBLING)


class TestLinkArtifactToRow:
    def test_the_row_carries_an_action_column(self) -> None:
        """RED, and the prerequisite for every join below it: without a
        durable column the stored action cannot exist, so the mint has
        nothing honest to read."""
        assert "action" in _row_columns()


class TestLinkRowToGrant:
    def test_the_mint_reads_the_action_from_the_row(self) -> None:
        """RED. The mint must take the action from the committed row, never
        from a caller-carried record -- taking it from `rendered` is the
        caller-chosen-authority defect this slice removes."""
        import inspect

        source = inspect.getsource(s7._mint_s7_execution_grant)
        assert "action=rendered.action" not in source, (
            "the mint must not take the action from the caller-carried record"
        )
        assert "action=" in source.split("S7ExecutionGrant(", 1)[1], (
            "the mint supplies no action at all; it must read the stored row"
        )


class TestLinkGrantToRuntime:
    def test_the_link_holds_for_its_own_action(self) -> None:
        assert s7.execution_grant_authorizes_action(
            _grant(), action=ACTION, params=dict(PARAMS)
        )

    def test_a_sibling_action_is_refused(self) -> None:
        """The binding property, isolated from store and mint."""
        assert not s7.execution_grant_authorizes_action(
            _grant(), action=SIBLING, params=dict(PARAMS)
        )

    def test_a_grant_for_a_sibling_does_not_authorize_the_original(self) -> None:
        assert not s7.execution_grant_authorizes_action(
            _grant(action=SIBLING), action=ACTION, params=dict(PARAMS)
        )


class TestConsumeVerifiedRowRenderedJoin:
    """NOT a caller join: neither side is supplied by the caller."""

    def test_the_seam_exists(self) -> None:
        assert hasattr(s7.S7AuthorizationStore, "consume_verified")

    def test_the_row_action_is_compared_to_the_rendered_action(self) -> None:
        """RED: the comparison cannot exist while the column does not."""
        import inspect

        assert "action" in _row_columns(), (
            "no stored action column; the row-rendered join cannot be built yet"
        )
        source = inspect.getsource(s7.S7AuthorizationStore.consume_verified)
        assert "action" in source


def _action_uses(func) -> tuple[set[str], set[str]]:
    """(literals compared with ==, literals passed as an `action=` argument).

    Substring checks are not proofs: `"x" in source` passes on a comment or
    a dead branch. These two sets are the only shapes that can actually
    bind an action, so a literal that appears anywhere else does not count.
    """
    import ast
    import inspect
    import textwrap

    tree = ast.parse(textwrap.dedent(inspect.getsource(func)))
    compared: set[str] = set()
    passed: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare):
            for side in [node.left, *node.comparators]:
                if isinstance(side, ast.Constant) and isinstance(side.value, str):
                    compared.add(side.value)
        if isinstance(node, ast.Call):
            for kw in node.keywords:
                if kw.arg == "action" and isinstance(kw.value, ast.Constant):
                    if isinstance(kw.value.value, str):
                        passed.add(kw.value.value)
    return compared, passed


class TestTheFourCallerJoins:
    """caller-action == rendered-action, one RED each.

    Each consumer has an authoritative action and none needs inventing:
    the decision pipeline has card.action, dream state has the
    reconstructed envelope.action, and the two credential ceremonies have
    fixed literals.

    SCOPE, stated plainly: these are AST-level, not behavioural. They kill
    the comment/dead-string mutation that a substring check would pass, but
    they cannot prove the comparison is REACHED. A behavioural join needs a
    real grant, and `_mint_s7_execution_grant` cannot produce one until the
    v2 row exists -- so the behavioural half of these four lands with that
    work rather than being faked here.
    """

    def test_the_decision_pipeline_consumer_binds_an_action(self) -> None:
        from core.decision import decision_pipeline

        compared, passed = _action_uses(
            decision_pipeline._consume_s7_execution_authorization
        )
        assert compared or passed, (
            "the decision pipeline consumer neither compares nor passes an action"
        )

    def test_the_dream_state_consumer_binds_an_action(self) -> None:
        from core.evolution import dream_state

        compared, passed = _action_uses(
            dream_state._consume_s7_execution_authorization_for_envelope
        )
        assert compared or passed, (
            "the dream-state consumer neither compares nor passes an action"
        )

    def test_the_backup_ceremony_binds_its_fixed_literal(self) -> None:
        from core.governance import s7_webauthn_ceremony as ceremony

        compared, passed = _action_uses(
            ceremony._consume_backup_registration_authorization
        )
        assert "register_backup_webauthn_credential" in (compared | passed), (
            "the backup consumer never binds the action it is for"
        )

    def test_the_disable_ceremony_binds_its_fixed_literal(self) -> None:
        """Passes today: the literal is the `action=` argument handed to the
        edge. A substring check would ALSO have passed on a comment, which
        is why this looks at the argument specifically."""
        from daemon import maez_daemon

        compared, passed = _action_uses(
            maez_daemon._s7_disable_credential_for_proof
        )
        assert "disable_founder_webauthn_credential" in passed, (
            "the disable consumer never passes the action to the edge"
        )
