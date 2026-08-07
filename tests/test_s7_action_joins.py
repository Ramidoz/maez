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


# The design freezes a SEPARATE v2 table and leaves v1 untouched, so a
# test that inspects v1 for the new column stays red no matter how
# correctly v2 is built.
V2_TABLE = "s7_authorization_artifacts_v2"
V1_TABLE = "s7_authorization_artifacts"


def _migrated_store(tmp: Path):
    """A private store carried through the REAL migration seam.

    Opening the store must not make v2 appear -- the design forbids
    open-time migration -- so the fixture invokes the migration explicitly.
    That entrypoint does not exist yet; tests that need it are red on a
    named blocker rather than on an absent column.
    """
    import os

    store = s7.S7AuthorizationStore(tmp / "ceremony.sqlite3")
    fd = os.open(tmp, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        s7._migrate_authorization_store_to_v2_at(store_dir_fd=fd)
    finally:
        os.close(fd)
    return store


def _columns(db_path, table: str) -> set[str]:
    with closing(sqlite3.connect(db_path)) as conn:
        return {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}


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


def _matches(artifact, rendered, env, authority, params_hash) -> bool:
    return s7.authorization_artifact_matches(
        artifact,
        rendered=rendered,
        action_params_hash=params_hash,
        authority_context_hash=s7.authority_context_hash(authority),
        precondition_hash=env.precondition_hash,
        derived_work_class=env.derived_work_class,
        derived_aggregation_group=env.derived_aggregation_group,
        now=NOW,
    )


class TestLinkRenderedToArtifact:
    """The join lives at authorization_artifact_matches, not at the
    constructor: S7AuthorizationArtifact never receives the rendered
    statement, so it cannot possibly detect a mismatch against it.
    """

    def test_the_control_matches(self) -> None:
        """Without this the refusal below could come from any of the nine
        other fields the boundary compares."""
        env, authority, params_hash, rendered = _chain()
        artifact = _artifact(env, authority, params_hash, rendered)
        assert _matches(artifact, rendered, env, authority, params_hash)

    def test_an_artifact_carrying_a_different_action_does_not_match(self) -> None:
        """RED: `action` is absent from the boundary's expected-field map,
        so a record rendered for one operation matches an artifact stored
        for another."""
        env, authority, params_hash, rendered = _chain()
        artifact = _artifact(env, authority, params_hash, rendered, action=SIBLING)
        assert not _matches(artifact, rendered, env, authority, params_hash)


class TestLinkArtifactToRow:
    def test_the_v2_row_carries_an_action_column(self, tmp_path: Path) -> None:
        """RED, and the prerequisite for every join below it. Checked on the
        SEPARATE v2 table: v1 is left untouched by design, so inspecting it
        for the new column would stay red however correctly v2 is built."""
        store = _migrated_store(tmp_path)
        assert "action" in _columns(store.db_path, V2_TABLE)

    def test_v1_is_left_untouched(self, tmp_path: Path) -> None:
        """The migration adds a table; it must not alter the old one."""
        store = _migrated_store(tmp_path)
        assert "action" not in _columns(store.db_path, V1_TABLE)


class TestLinkRowToGrant:
    def test_the_grant_action_comes_from_the_committed_row(
        self, tmp_path: Path
    ) -> None:
        """Behavioural, not source-text: hardcoded or unrelated `action`
        text in the mint would green a source check while establishing no
        join at all. This stores a row, consumes it, and reads the grant.
        """
        env, authority, params_hash, rendered = _chain()
        store = _migrated_store(tmp_path)
        store.put(_artifact(env, authority, params_hash, rendered))
        grant, _result = store.consume_for_execution(
            "artifact-join-1",
            rendered=rendered,
            action_params_hash=params_hash,
            authority_context=authority,
            precondition_hash=env.precondition_hash,
            derived_work_class=env.derived_work_class,
            derived_aggregation_group=env.derived_aggregation_group,
            now=NOW,
        )
        assert grant is not None, "consumption produced no grant"
        assert grant.action == ACTION

    def test_the_mint_does_not_take_the_action_from_the_caller(self) -> None:
        """The one structural check that IS the point: the action must not
        come from the caller-carried rendered record. Kept as an AST check
        because it asserts an ABSENCE, which no behavioural test can."""
        import ast
        import inspect
        import textwrap

        tree = ast.parse(
            textwrap.dedent(inspect.getsource(s7._mint_s7_execution_grant))
        )
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                for kw in node.keywords:
                    if kw.arg == "action":
                        assert ast.unparse(kw.value) != "rendered.action", (
                            "the mint takes the action from the caller-carried "
                            "record; it must read the committed row"
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

    def test_a_row_whose_action_differs_from_the_rendered_action_refuses(
        self, tmp_path: Path
    ) -> None:
        """Behavioural. A source check for the word `action` would green on
        unrelated text; this stores a row whose action differs from the
        signed statement and requires the verification to refuse it."""
        env, authority, params_hash, rendered = _chain()
        store = _migrated_store(tmp_path)
        store.put(_artifact(env, authority, params_hash, rendered, action=SIBLING))
        verified = store.consume_verified(
            "artifact-join-1",
            rendered=rendered,
            action_params_hash=params_hash,
            authority_context=authority,
            precondition_hash=env.precondition_hash,
            derived_work_class=env.derived_work_class,
            derived_aggregation_group=env.derived_aggregation_group,
            now=NOW,
        )
        assert not verified

    def test_the_control_verifies_a_matching_row(self, tmp_path: Path) -> None:
        env, authority, params_hash, rendered = _chain()
        store = _migrated_store(tmp_path)
        store.put(_artifact(env, authority, params_hash, rendered))
        assert store.consume_verified(
            "artifact-join-1",
            rendered=rendered,
            action_params_hash=params_hash,
            authority_context=authority,
            precondition_hash=env.precondition_hash,
            derived_work_class=env.derived_work_class,
            derived_aggregation_group=env.derived_aggregation_group,
            now=NOW,
        )


def _action_uses(func) -> tuple[set[str], set[str]]:
    """(expressions compared with ==, expressions passed as `action=`).

    Substring checks are not proofs: `"x" in source` passes on a comment or
    a dead branch. These two shapes are the only ones that can bind an
    action.

    Expressions are returned UNPARSED, not just string constants. The two
    fixed-literal ceremonies bind a constant, but the decision pipeline's
    authoritative action is `card.action` and dream state's is
    `envelope.action` -- a constants-only helper could never accept the
    correct dynamic implementation, which would make those two tests
    unpassable rather than red.
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
                compared.add(ast.unparse(side))
        if isinstance(node, ast.Call):
            for kw in node.keywords:
                if kw.arg == "action":
                    passed.add(ast.unparse(kw.value))
    return compared, passed


def _binds_an_action(func) -> bool:
    """Any comparison or `action=` argument that mentions an action."""
    compared, passed = _action_uses(func)
    return any("action" in expr for expr in compared | passed) or bool(passed)


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

    def test_the_consumers_are_reachable_where_the_tests_look(self) -> None:
        """CONTROL. Both consumers are METHODS, not module functions. Looking
        for them at module level raises AttributeError, and a test that dies
        that way is red for neither its stated reason nor any real one."""
        from core.decision.decision_pipeline import DecisionPipeline
        from core.evolution.dream_state import DreamState

        assert callable(DecisionPipeline._consume_s7_execution_authorization)
        assert callable(DreamState._consume_s7_execution_authorization_for_envelope)

    def test_the_decision_pipeline_consumer_binds_an_action(self) -> None:
        """Its authoritative action is `card.action` -- an attribute, not a
        literal, so this must accept a dynamic expression."""
        from core.decision.decision_pipeline import DecisionPipeline

        assert _binds_an_action(
            DecisionPipeline._consume_s7_execution_authorization
        ), "the decision pipeline consumer neither compares nor passes an action"

    def test_the_dream_state_consumer_binds_an_action(self) -> None:
        """Its authoritative action is the reconstructed `envelope.action`."""
        from core.evolution.dream_state import DreamState

        assert _binds_an_action(
            DreamState._consume_s7_execution_authorization_for_envelope
        ), "the dream-state consumer neither compares nor passes an action"

    def test_the_backup_ceremony_binds_its_fixed_literal(self) -> None:
        from core.governance import s7_webauthn_ceremony as ceremony

        compared, passed = _action_uses(
            ceremony._consume_backup_registration_authorization
        )
        assert "'register_backup_webauthn_credential'" in (compared | passed), (
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
        assert "'disable_founder_webauthn_credential'" in passed, (
            "the disable consumer never passes the action to the edge"
        )
