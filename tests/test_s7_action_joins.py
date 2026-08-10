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

import contextlib
import json
import os
import sqlite3
from contextlib import closing
from dataclasses import replace
from pathlib import Path

import pytest

from core.governance import operator_user_boundary as s7
from tests.s7_store_fixture import fresh_store

NOW = "2026-08-07T12:00:00Z"
FUTURE = "2026-08-07T16:00:00Z"
ACTION = "model_routing.cutover_cuda"
SIBLING = "model_routing.wipe_and_replace"
# Same derived class as ACTION, deliberately NOT the cutover: a mint that
# hardcodes the cutover action must not be able to pass the row->grant join.
OTHER_ACTION = "model_routing.rollback_vulkan"
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

    store = fresh_store(tmp)
    fd = os.open(tmp, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        s7._migrate_authorization_store_to_v2_at(store_dir_fd=fd)
    finally:
        os.close(fd)
    return store


def _columns(db_path, table: str) -> set[str]:
    with closing(sqlite3.connect(db_path)) as conn:
        return {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}


# The migration is REQUIRED to add three freeze triggers to v1. An
# invariance guard that swept every sqlite_master object for the table
# would therefore REJECT the correct migration -- so triggers are excluded
# here and asserted separately and exactly.
V1_FREEZE_TRIGGERS = (
    "s7_v1_frozen_delete",
    "s7_v1_frozen_insert",
    "s7_v1_frozen_update",
)


def _triggers_on(db_path, table: str) -> dict:
    with closing(sqlite3.connect(db_path)) as conn:
        return dict(
            conn.execute(
                "SELECT name, sql FROM sqlite_master "
                "WHERE tbl_name = ? AND type = 'trigger'",
                (table,),
            )
        )


def _table_shape(db_path, table: str) -> tuple:
    """v1's own shape: columns, plus its CREATE TABLE and indexes.

    Triggers EXCLUDED -- see V1_FREEZE_TRIGGERS. Everything else must be
    untouched: checking only that no `action` column appeared would miss a
    widened type, a dropped NOT NULL, a changed default, a reordered column
    or a rewritten primary key, all of which leave the column NAMES
    identical.
    """
    with closing(sqlite3.connect(db_path)) as conn:
        info = tuple(conn.execute(f"PRAGMA table_info({table})"))
        ddl = tuple(
            conn.execute(
                "SELECT type, name, sql FROM sqlite_master "
                "WHERE tbl_name = ? AND type != 'trigger' ORDER BY type, name",
                (table,),
            )
        )
    return info, ddl


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

    def test_v1_is_left_byte_identical(self, tmp_path: Path) -> None:
        """The migration adds a table; it must not alter the old one.

        Captured BEFORE and compared AFTER, over the complete table_info and
        the frozen DDL -- not merely "no action column appeared", which a
        widened type or a dropped NOT NULL would slip past.
        """
        store = fresh_store(tmp_path)
        before = _table_shape(store.db_path, V1_TABLE)
        assert before[0], "v1 table absent; the comparison would be vacuous"

        import os

        fd = os.open(tmp_path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            s7._migrate_authorization_store_to_v2_at(store_dir_fd=fd)
        finally:
            os.close(fd)

        assert _table_shape(store.db_path, V1_TABLE) == before

    def test_v1_gains_exactly_the_three_freeze_triggers(
        self, tmp_path: Path
    ) -> None:
        """The one v1 change the design DOES require, asserted exactly, so
        excluding triggers from the invariance guard above leaves no hole."""
        store = fresh_store(tmp_path)
        assert not _triggers_on(store.db_path, V1_TABLE), (
            "v1 already carries triggers before migration; the assertion "
            "below would not measure what the migration added"
        )

        import os

        fd = os.open(tmp_path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            s7._migrate_authorization_store_to_v2_at(store_dir_fd=fd)
        finally:
            os.close(fd)

        assert (
            tuple(sorted(_triggers_on(store.db_path, V1_TABLE)))
            == V1_FREEZE_TRIGGERS
        )


class TestLinkRowToGrant:
    def test_the_grant_action_comes_from_the_committed_row(
        self, tmp_path: Path
    ) -> None:
        """Behavioural, not source-text: hardcoded or unrelated `action`
        text in the mint would green a source check while establishing no
        join at all. This stores a row, consumes it, and reads the grant.

        A mint that hardcodes the cutover action would pass a test built on
        the cutover action, so this stores a DIFFERENT one and requires the
        grant to carry it.
        """
        env, authority, params_hash, rendered = _chain(action=OTHER_ACTION)
        assert OTHER_ACTION != ACTION
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
        assert grant.action == OTHER_ACTION

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


# The calls that actually consume an action. An `action=` keyword handed
# to anything else -- a logger, a metric, an audit line -- binds nothing.
_CONSUMING_CALLS = frozenset(
    {
        "consume_execution_grant_for_action",
        "execution_grant_authorizes_action",
        "execution_grant_authorizes_card_transition",
    }
)


def _joins_action_in_source(
    source: str, expression: str, *, counterpart: str
) -> bool:
    """Does this SOURCE equate `expression` with an action, or hand it to a
    consuming call?

    Five shapes short of this were accepted by earlier versions and none
    is a join:

    * any mention of "action" -- every consumer already says
      `action_params_hash`, which greened both caller joins;
    * `if card.action in ALLOWED:` -- a membership test, whose sides both
      land in a set of "compared" expressions;
    * `log_event(action=card.action)` -- an `action=` keyword to a call
      that consumes nothing;
    * `card.action == authorization.action_params_hash` -- both sides
      contain "action", but one is a HASH;
    * `card.action == audit.action` or `card.action == 'anything'` -- both
      sides ARE actions, but the counterpart is not the authority the
      caller must be joined to.

    So the caller expression must be equated with THE named counterpart --
    supplied by the test, never inferred -- or handed to a call that
    actually consumes an action.

    Takes source rather than a function so the helper can be attacked with
    synthetic cases instead of only exercised on production code.
    """
    import ast
    import textwrap

    tree = ast.parse(textwrap.dedent(source))
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare):
            if len(node.ops) != 1 or not isinstance(node.ops[0], ast.Eq):
                continue
            sides = {ast.unparse(node.left), ast.unparse(node.comparators[0])}
            if sides == {expression, counterpart}:
                return True
        if isinstance(node, ast.Call):
            name = (
                node.func.attr
                if isinstance(node.func, ast.Attribute)
                else getattr(node.func, "id", None)
            )
            if name not in _CONSUMING_CALLS:
                continue
            for kw in node.keywords:
                if kw.arg == "action" and ast.unparse(kw.value) == expression:
                    return True
    return False


def _joins_action(func, expression: str, *, counterpart: str) -> bool:
    import inspect

    return _joins_action_in_source(
        inspect.getsource(func), expression, counterpart=counterpart
    )


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

    def test_action_params_hash_does_not_count_as_binding_an_action(self) -> None:
        """CONTROL, and the reason the two tests below name an exact
        expression. Every consumer already mentions `action_params_hash`;
        a substring test on "action" greened both caller joins while
        neither bound an action at all."""
        from core.decision.decision_pipeline import DecisionPipeline

        compared, passed = _action_uses(
            DecisionPipeline._consume_s7_execution_authorization
        )
        mentions = {e for e in compared | passed if "action" in e}
        assert mentions, "expected the params-hash mentions that caused the defect"
        assert all("action_params_hash" in e for e in mentions), mentions

    def test_the_decision_pipeline_consumer_binds_card_action(self) -> None:
        """Its authoritative action is `card.action` -- pinned exactly, not
        by substring."""
        from core.decision.decision_pipeline import DecisionPipeline

        assert _joins_action(
            DecisionPipeline._consume_s7_execution_authorization,
            "card.action",
            counterpart="rendered.action",
        ), "the decision pipeline consumer never joins card.action to rendered.action"

    def test_the_dream_state_consumer_binds_envelope_action(self) -> None:
        """Its authoritative action is the reconstructed `envelope.action`."""
        from core.evolution.dream_state import DreamState

        assert _joins_action(
            DreamState._consume_s7_execution_authorization_for_envelope,
            "envelope.action",
            counterpart="rendered.action",
        ), "the dream-state consumer never joins envelope.action to rendered.action"

    def test_the_backup_ceremony_joins_its_fixed_literal(self) -> None:
        """Same strict helper as the other two: membership in a loose set of
        "compared or passed" expressions is not a join."""
        from core.governance import s7_webauthn_ceremony as ceremony

        assert _joins_action(
            ceremony._consume_backup_registration_authorization,
            "'register_backup_webauthn_credential'",
            counterpart="rendered.action",
        ), "the backup consumer never joins its literal to the rendered action"

    def test_the_disable_ceremony_joins_its_fixed_literal(self) -> None:
        from daemon import maez_daemon

        assert _joins_action(
            maez_daemon._s7_disable_credential_for_proof,
            "'disable_founder_webauthn_credential'",
            counterpart="rendered.action",
        ), "the disable consumer never joins its literal to the rendered action"


class TestTheJoinHelperIsItselfAttacked:
    """This helper decides whether every caller join passes, and three
    earlier versions were wrong in escalating ways -- any mention of
    "action", then any comparison side or `action=` keyword, then any
    action-shaped counterpart including a hash, an unrelated audit record
    or a bare literal. So it is attacked directly rather than trusted
    because production happens to be red.

    RENDERED = "rendered.action"

    is the counterpart every caller must be joined to; the tests supply it
    explicitly so the helper can never infer an authority of its own.
    """

    RENDERED = "rendered.action"

    def test_a_membership_test_is_not_a_join(self) -> None:
        assert not _joins_action_in_source(
            "def f(card):\n    if card.action in ALLOWED: pass\n",
            "card.action",
            counterpart=self.RENDERED,
        )

    def test_an_action_kwarg_to_a_non_consumer_is_not_a_join(self) -> None:
        assert not _joins_action_in_source(
            "def f(card):\n    log_event(action=card.action)\n",
            "card.action",
            counterpart=self.RENDERED,
        )

    def test_an_inequality_is_not_a_join(self) -> None:
        assert not _joins_action_in_source(
            "def f(card, rendered):\n"
            "    return card.action != rendered.action\n",
            "card.action",
            counterpart=self.RENDERED,
        )

    def test_a_params_hash_counterpart_is_not_a_join(self) -> None:
        """Both sides contain "action", but one is a HASH."""
        assert not _joins_action_in_source(
            "def f(card, a):\n"
            "    return card.action == a.action_params_hash\n",
            "card.action",
            counterpart=self.RENDERED,
        )

    def test_an_unrelated_action_counterpart_is_not_a_join(self) -> None:
        """Both sides ARE actions -- but an audit record is not the
        authority the caller must be joined to."""
        assert not _joins_action_in_source(
            "def f(card, audit):\n    return card.action == audit.action\n",
            "card.action",
            counterpart=self.RENDERED,
        )

    def test_an_arbitrary_literal_counterpart_is_not_a_join(self) -> None:
        assert not _joins_action_in_source(
            "def f(card):\n    return card.action == 'anything'\n",
            "card.action",
            counterpart=self.RENDERED,
        )

    def test_equality_against_the_named_counterpart_is_a_join(self) -> None:
        assert _joins_action_in_source(
            "def f(card, rendered):\n"
            "    return card.action == rendered.action\n",
            "card.action",
            counterpart=self.RENDERED,
        )

    def test_the_join_is_order_insensitive(self) -> None:
        assert _joins_action_in_source(
            "def f(card, rendered):\n"
            "    return rendered.action == card.action\n",
            "card.action",
            counterpart=self.RENDERED,
        )

    def test_handing_it_to_a_consuming_call_is_a_join(self) -> None:
        assert _joins_action_in_source(
            "def f(card, g):\n"
            "    return execution_grant_authorizes_action("
            "g, action=card.action, params={})\n",
            "card.action",
            counterpart=self.RENDERED,
        )

    def test_a_fixed_literal_joined_to_the_rendered_action(self) -> None:
        assert _joins_action_in_source(
            "def f(rendered):\n"
            "    return rendered.action == 'register_backup_webauthn_credential'\n",
            "'register_backup_webauthn_credential'",
            counterpart=self.RENDERED,
        )


class TestStorageFollowsTheMigratedPlane:
    """After migration v1 is FROZEN, so storage has nowhere to go unless it
    moves to v2. Reproduced before this existed: put() aborted with
    s7_v1_frozen and both tables stayed empty.

    Scope note: this slice routes STORAGE. Receipt-gated activation of
    guarded EXECUTION -- "absent is not permission" -- belongs to the mint
    and consume seams, not here.
    """

    def _migrated(self, tmp: Path):
        import os

        from core.governance import s7_v2_migration as mig

        store = fresh_store(tmp)
        fd = os.open(tmp, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            mig._migrate_authorization_store_to_v2_at(store_dir_fd=fd)
        finally:
            os.close(fd)
        return store

    def _rows(self, db_path, table):
        with closing(sqlite3.connect(db_path)) as conn:
            return conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0]

    def test_a_put_after_migration_lands_in_v2(self, tmp_path: Path) -> None:
        store = self._migrated(tmp_path)
        env, authority, params_hash, rendered = _chain()
        store.put(_artifact(env, authority, params_hash, rendered))
        assert self._rows(store.db_path, V2_TABLE) == 1

    def test_a_put_after_migration_writes_nothing_to_frozen_v1(
        self, tmp_path: Path
    ) -> None:
        store = self._migrated(tmp_path)
        env, authority, params_hash, rendered = _chain()
        store.put(_artifact(env, authority, params_hash, rendered))
        assert self._rows(store.db_path, V1_TABLE) == 0

    def test_the_stored_row_carries_the_action(self, tmp_path: Path) -> None:
        """The whole point of v2. A row without it cannot bind anything."""
        store = self._migrated(tmp_path)
        env, authority, params_hash, rendered = _chain(action=OTHER_ACTION)
        store.put(_artifact(env, authority, params_hash, rendered))
        with closing(sqlite3.connect(store.db_path)) as conn:
            stored = conn.execute(
                f"SELECT action FROM {V2_TABLE}"
            ).fetchone()[0]
        assert stored == OTHER_ACTION

    def test_the_stored_row_declares_the_v2_schema(self, tmp_path: Path) -> None:
        store = self._migrated(tmp_path)
        env, authority, params_hash, rendered = _chain()
        store.put(_artifact(env, authority, params_hash, rendered))
        with closing(sqlite3.connect(store.db_path)) as conn:
            version = conn.execute(
                f"SELECT schema_version FROM {V2_TABLE}"
            ).fetchone()[0]
        assert version == "s7.authorization_artifact.v2"

    def test_an_unmigrated_store_still_uses_v1(self, tmp_path: Path) -> None:
        """CONTROL. Routing everything to v2 would break every store that
        has not migrated yet, and pre-activation behaviour is not this
        slice's to change."""
        store = fresh_store(tmp_path)
        env, authority, params_hash, rendered = _chain()
        store.put(_artifact(env, authority, params_hash, rendered))
        assert self._rows(store.db_path, V1_TABLE) == 1


class TestOnlyAVerifiedReceiptGrantsV2Storage:
    """The table existing is NOT activation.

    Reproduced: migrate, remove the receipt (the commit-before-publication
    window), and put() wrote a v2 row anyway -- which then made recovery
    refuse the store as indeterminate, because committed-not-published
    requires BOTH v2 tables empty. Writing on table-presence alone
    destroys the frozen recovery path.
    """

    def _migrated(self, tmp: Path):
        import os

        from core.governance import s7_v2_migration as mig

        store = fresh_store(tmp)
        fd = os.open(tmp, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            mig._migrate_authorization_store_to_v2_at(store_dir_fd=fd)
        finally:
            os.close(fd)
        return store

    def _v2_rows(self, db_path) -> int:
        with closing(sqlite3.connect(db_path)) as conn:
            return conn.execute(f"SELECT count(*) FROM {V2_TABLE}").fetchone()[0]

    def test_a_verified_receipt_permits_storage(self, tmp_path: Path) -> None:
        """CONTROL: refusing always would satisfy every test below."""
        store = self._migrated(tmp_path)
        env, authority, params_hash, rendered = _chain()
        store.put(_artifact(env, authority, params_hash, rendered))
        assert self._v2_rows(store.db_path) == 1

    def test_a_missing_receipt_refuses_storage(self, tmp_path: Path) -> None:
        store = self._migrated(tmp_path)
        (tmp_path / "s7_migration_receipt.json").unlink()
        env, authority, params_hash, rendered = _chain()
        with pytest.raises((ValueError, OSError)):
            store.put(_artifact(env, authority, params_hash, rendered))
        assert self._v2_rows(store.db_path) == 0

    def test_a_missing_receipt_leaves_recovery_intact(
        self, tmp_path: Path
    ) -> None:
        """The harm, stated directly: a row written in that window makes
        the store indeterminate and unrecoverable."""
        import os

        from core.governance import s7_v2_migration as mig

        store = self._migrated(tmp_path)
        (tmp_path / "s7_migration_receipt.json").unlink()
        env, authority, params_hash, rendered = _chain()
        with contextlib.suppress(Exception):
            store.put(_artifact(env, authority, params_hash, rendered))
        fd = os.open(tmp_path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            mig._migrate_authorization_store_to_v2_at(store_dir_fd=fd)
        finally:
            os.close(fd)

    def test_a_corrupt_receipt_refuses_storage(self, tmp_path: Path) -> None:
        store = self._migrated(tmp_path)
        receipt = tmp_path / "s7_migration_receipt.json"
        receipt.unlink()
        receipt.write_bytes(b"{ not json")
        os.chmod(receipt, 0o600)
        env, authority, params_hash, rendered = _chain()
        with pytest.raises((ValueError, OSError)):
            store.put(_artifact(env, authority, params_hash, rendered))
        assert self._v2_rows(store.db_path) == 0

    def test_a_foreign_receipt_refuses_storage(self, tmp_path: Path) -> None:
        """dev/ino pin the receipt to its own store."""
        store = self._migrated(tmp_path)
        receipt = tmp_path / "s7_migration_receipt.json"
        body = json.loads(receipt.read_bytes())
        body["store_ino"] = body["store_ino"] + 1
        receipt.unlink()
        receipt.write_bytes(
            json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
        )
        os.chmod(receipt, 0o600)
        env, authority, params_hash, rendered = _chain()
        with pytest.raises((ValueError, OSError)):
            store.put(_artifact(env, authority, params_hash, rendered))
        assert self._v2_rows(store.db_path) == 0


class TestSchemaIdentityIsNotLaundered:
    def test_a_forged_artifact_schema_version_refuses(self) -> None:
        """A forged identity was ACCEPTED at construction and then written
        as a valid v2 row, because the insert hardcoded the label. The
        durable row would then assert an identity the object never had."""
        env, authority, params_hash, rendered = _chain()
        artifact = _artifact(env, authority, params_hash, rendered)
        with pytest.raises(ValueError):
            replace(artifact, schema_version="s7.authorization_artifact.v999")

    def test_the_stored_label_comes_from_the_artifact(
        self, tmp_path: Path
    ) -> None:
        """Hardcoding it means the row's identity is asserted by the writer
        rather than carried by the record."""
        import ast
        import inspect
        import textwrap

        # dedent, not cleandoc: cleandoc mangles the indentation and
        # ast.parse then fails, which is a broken TEST rather than a
        # finding about the writer.
        source = textwrap.dedent(inspect.getsource(s7.S7AuthorizationStore))
        tree = ast.parse(source)
        hardcoded = [
            node.value
            for node in ast.walk(tree)
            if isinstance(node, ast.Constant)
            and node.value == "s7.authorization_artifact.v2"
        ]
        assert not hardcoded, "the v2 label is hardcoded in the writer"


class TestConsumptionFollowsTheMigratedPlane:
    """The read half of storage. The banked order required receipt-validated
    v2 READS as well as writes; shipping only the write half was a
    narrowing I should not have made.

    The mint is STUBBED to succeed here on purpose: it has no action source
    until the next slice, so without the stub this would die in the mint
    and prove nothing about which table was consumed.
    """

    def _migrated(self, tmp: Path):
        import os

        from core.governance import s7_v2_migration as mig

        store = fresh_store(tmp)
        fd = os.open(tmp, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            mig._migrate_authorization_store_to_v2_at(store_dir_fd=fd)
        finally:
            os.close(fd)
        return store

    def _consumed_at(self, db_path, table):
        with closing(sqlite3.connect(db_path)) as conn:
            row = conn.execute(f"SELECT consumed_at FROM {table}").fetchone()
        return row[0] if row else "NO ROW"

    def _consume(self, store, env, authority, params_hash, rendered):
        return store.consume_for_execution(
            "artifact-join-1",
            rendered=rendered,
            action_params_hash=params_hash,
            authority_context=authority,
            precondition_hash=env.precondition_hash,
            derived_work_class=env.derived_work_class,
            derived_aggregation_group=env.derived_aggregation_group,
            now=NOW,
        )

    def test_consumption_marks_the_v2_row(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        store = self._migrated(tmp_path)
        env, authority, params_hash, rendered = _chain()
        store.put(_artifact(env, authority, params_hash, rendered))
        monkeypatch.setattr(
            s7, "_mint_s7_execution_grant", lambda **_kwargs: object()
        )
        self._consume(store, env, authority, params_hash, rendered)
        assert self._consumed_at(store.db_path, V2_TABLE) is not None

    def test_consumption_leaves_frozen_v1_alone(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        store = self._migrated(tmp_path)
        env, authority, params_hash, rendered = _chain()
        store.put(_artifact(env, authority, params_hash, rendered))
        monkeypatch.setattr(
            s7, "_mint_s7_execution_grant", lambda **_kwargs: object()
        )
        self._consume(store, env, authority, params_hash, rendered)
        assert self._consumed_at(store.db_path, V1_TABLE) == "NO ROW"

    def test_an_unmigrated_store_refuses_guarded_execution(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """ABSENT IS NOT PERMISSION.

        This test previously REQUIRED the v1 fallback, which is the
        opposite of the frozen rule: if the v2 table is absent, every
        guarded execution path refuses rather than silently proceeding on
        a store that was never migrated. A test can enshrine a defect as
        firmly as code can.
        """
        store = fresh_store(tmp_path)
        env, authority, params_hash, rendered = _chain()
        store.put(_artifact(env, authority, params_hash, rendered))
        monkeypatch.setattr(
            s7, "_mint_s7_execution_grant", lambda **_kwargs: object()
        )
        with pytest.raises(Exception):
            self._consume(store, env, authority, params_hash, rendered)
        assert self._consumed_at(store.db_path, V1_TABLE) is None


class TestTheReceiptBindsTheDatabaseItAuthorizes:
    """The trust root and the mutated object must be the same object.

    Reproduced: store A migrated with a valid receipt, store B migrated
    with its receipt removed, then `storeA.put(artifact, connection=connB)`
    -- A rows 0, B rows 1, and B's recovery then refused. A's receipt had
    authorized a write into B.
    """

    def _migrated(self, tmp: Path, *, keep_receipt: bool):
        import os

        from core.governance import s7_v2_migration as mig

        store = fresh_store(tmp)
        fd = os.open(tmp, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            mig._migrate_authorization_store_to_v2_at(store_dir_fd=fd)
        finally:
            os.close(fd)
        if not keep_receipt:
            (tmp / "s7_migration_receipt.json").unlink()
        return store

    def test_one_stores_receipt_cannot_authorize_another(
        self, tmp_path: Path
    ) -> None:
        good = tmp_path / "A"
        bare = tmp_path / "B"
        good.mkdir()
        bare.mkdir()
        store_a = self._migrated(good, keep_receipt=True)
        store_b = self._migrated(bare, keep_receipt=False)

        env, authority, params_hash, rendered = _chain()
        with closing(sqlite3.connect(store_b.db_path)) as conn_b:
            with pytest.raises((ValueError, OSError)):
                store_a.put(
                    _artifact(env, authority, params_hash, rendered),
                    connection=conn_b,
                )
            conn_b.commit()

        with closing(sqlite3.connect(store_b.db_path)) as conn:
            rows = conn.execute(
                f"SELECT count(*) FROM {V2_TABLE}"
            ).fetchone()[0]
        assert rows == 0, "another store's receipt authorized this write"

    def test_the_matching_connection_still_works(self, tmp_path: Path) -> None:
        """CONTROL: refusing every supplied connection would satisfy the
        test above while breaking the API."""
        good = tmp_path / "A"
        good.mkdir()
        store = self._migrated(good, keep_receipt=True)
        env, authority, params_hash, rendered = _chain()
        with closing(sqlite3.connect(store.db_path)) as conn:
            store.put(
                _artifact(env, authority, params_hash, rendered),
                connection=conn,
            )
            conn.commit()
        with closing(sqlite3.connect(store.db_path)) as conn:
            assert conn.execute(
                f"SELECT count(*) FROM {V2_TABLE}"
            ).fetchone()[0] == 1
