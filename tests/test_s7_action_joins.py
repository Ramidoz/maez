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
from core.governance import s7_v2_migration as mig
from tests.s7_callsite_scanner import find_callsites
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
        mig._migrate_authorization_store_to_v2_at(store_dir_fd=fd)
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
            mig._migrate_authorization_store_to_v2_at(store_dir_fd=fd)
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
            mig._migrate_authorization_store_to_v2_at(store_dir_fd=fd)
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
        """The mint carries its `stored_action` through to `grant.action`,
        and the rendered statement cannot displace it.

        SCOPE, stated honestly: this test SUPPLIES `stored_action` itself,
        so it pins the mint's parameter plumbing -- that the value reaching
        the mint is the value on the grant, and that a differing
        `rendered.action` sitting right beside it does not win. It does NOT
        witness the production join, because it never drives
        `consume_for_execution`, which is the code that DECIDES where the
        action comes from. Mutating that decision leaves this test green.

        An earlier version of this docstring claimed a mint reading the
        caller-carried statement would fail here. That is false, and the
        claim was worse than no claim: it read as behavioural coverage of
        the production source while covering only the plumbing.

        What guards the production source today is the atomic
        `UPDATE ... RETURNING action` -- the action is returned by the same
        statement that consumes the row, so there is no second read to
        launder -- plus the AST provenance chain in
        `test_the_mint_does_not_take_the_action_from_the_caller`. The
        real-path behavioural witness belongs with the row-to-rendered
        refusal join, which is where a mismatch acquires defined semantics;
        until that lands, a mismatch reaching the mint is unreachable in
        production for reasons no test here asserts.
        """
        env, authority, params_hash, _stored_rendered = _chain(action=OTHER_ACTION)
        assert OTHER_ACTION != ACTION
        store = _migrated_store(tmp_path)
        store.put(_artifact(env, authority, params_hash, _stored_rendered))
        with closing(sqlite3.connect(store.db_path)) as conn:
            row = conn.execute(
                f"SELECT action FROM {V2_TABLE} WHERE artifact_id = ?",
                ("artifact-join-1",),
            ).fetchone()
        assert row == (OTHER_ACTION,), "the authority row was not durably committed"

        _caller_env, _caller_authority, caller_params_hash, caller_rendered = _chain(
            action=ACTION
        )
        grant = s7._mint_s7_execution_grant(
            artifact_id="artifact-join-1",
            rendered=caller_rendered,
            stored_action=row[0],
            action_params_hash=caller_params_hash,
            precondition_hash="a" * 64,
            authority_context_hash=s7.authority_context_hash(_caller_authority),
            derived_work_class="self_modification",
            derived_aggregation_group="g",
            credential_ref="cred-1",
            auth_method="founder_webauthn",
            grant_source="founder_webauthn",
            ceremony_kind="founder_local_webauthn",
            consumed_at=NOW,
        )
        assert caller_rendered.action == ACTION
        assert grant.action == OTHER_ACTION

    def test_the_mint_does_not_take_the_action_from_the_caller(self) -> None:
        """The matched SQL row must feed the mint and then the grant."""
        import ast
        import inspect
        import textwrap

        tree = ast.parse(
            textwrap.dedent(inspect.getsource(s7._mint_s7_execution_grant))
        )
        grant_calls = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "S7ExecutionGrant"
        ]
        assert len(grant_calls) == 1
        action_values = [
            ast.unparse(keyword.value)
            for keyword in grant_calls[0].keywords
            if keyword.arg == "action"
        ]
        assert action_values == ["stored_action"], (
            "the grant action must come from the committed-row carrier, not "
            "from rendered or from an absent constructor argument"
        )

        consume_tree = ast.parse(
            textwrap.dedent(inspect.getsource(s7.S7AuthorizationStore.consume_for_execution))
        )
        mint_calls = [
            node
            for node in ast.walk(consume_tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "_mint_s7_execution_grant"
        ]
        assert len(mint_calls) == 1
        stored_sources = [
            ast.unparse(keyword.value)
            for keyword in mint_calls[0].keywords
            if keyword.arg == "stored_action"
        ]
        assert stored_sources == ["matched_row[0]"], (
            "the production mint call must use the action returned by the "
            "matched durable-row update"
        )

        cur_assignments = [
            node
            for node in ast.walk(consume_tree)
            if isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name) and target.id == "cur"
                for target in node.targets
            )
        ]
        assert len(cur_assignments) == 1
        execute_call = cur_assignments[0].value
        assert (
            isinstance(execute_call, ast.Call)
            and isinstance(execute_call.func, ast.Attribute)
            and isinstance(execute_call.func.value, ast.Name)
            and execute_call.func.value.id == "conn"
            and execute_call.func.attr == "execute"
        )
        sql_literals = [
            node.value
            for node in ast.walk(execute_call.args[0])
            if isinstance(node, ast.Constant) and isinstance(node.value, str)
        ]
        assert any("RETURNING action" in literal for literal in sql_literals)

        row_assignments = [
            node
            for node in ast.walk(consume_tree)
            if isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name) and target.id == "matched_row"
                for target in node.targets
            )
        ]
        assert len(row_assignments) == 1, (
            "matched_row must be assigned once from the UPDATE cursor; a "
            "second assignment could launder rendered.action"
        )
        fetch_call = row_assignments[0].value
        assert (
            isinstance(fetch_call, ast.Call)
            and isinstance(fetch_call.func, ast.Attribute)
            and isinstance(fetch_call.func.value, ast.Name)
            and fetch_call.func.value.id == "cur"
            and fetch_call.func.attr == "fetchone"
            and not fetch_call.args
            and not fetch_call.keywords
        )
        assert (
            cur_assignments[0].lineno
            < row_assignments[0].lineno
            < mint_calls[0].lineno
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

        minted: list[object] = []

        def recording_mint(**_kwargs):
            minted.append(object())
            return object()

        monkeypatch.setattr(s7, "_mint_s7_execution_grant", recording_mint)
        # The EXACT type: pytest.raises(Exception) would pass on any
        # unrelated crash and call this a refusal.
        with pytest.raises(s7.S7GuardedExecutionUnavailable):
            self._consume(store, env, authority, params_hash, rendered)
        assert minted == [], "the mint was reached despite the refusal"
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

    def test_a_supplied_connection_is_refused_not_trusted(
        self, tmp_path: Path
    ) -> None:
        """Even the store's OWN database refuses through a supplied
        connection.

        A connection's held inode is not observable from Python, and
        PRAGMA reports only a NAME -- repoint it and another store's
        receipt authorizes this write. Refusing what cannot be pinned is
        the honest answer; pretending to validate it is not.
        """
        good = tmp_path / "A"
        good.mkdir()
        store = self._migrated(good, keep_receipt=True)
        env, authority, params_hash, rendered = _chain()
        with closing(sqlite3.connect(store.db_path)) as conn:
            with pytest.raises(ValueError, match="caller-supplied"):
                store.put(
                    _artifact(env, authority, params_hash, rendered),
                    connection=conn,
                )

    def test_the_stores_own_put_still_works(self, tmp_path: Path) -> None:
        """CONTROL: refusing everything would satisfy the tests above while
        breaking storage entirely."""
        good = tmp_path / "A"
        good.mkdir()
        store = self._migrated(good, keep_receipt=True)
        env, authority, params_hash, rendered = _chain()
        store.put(_artifact(env, authority, params_hash, rendered))
        with closing(sqlite3.connect(store.db_path)) as conn:
            assert conn.execute(
                f"SELECT count(*) FROM {V2_TABLE}"
            ).fetchone()[0] == 1


class TestTheGuardedWriterStaysAtomicAfterMigration:
    """The sole guarded voice-seat writer reserves the bundle and inserts
    the artifact in ONE transaction. Refusing its connection secured
    storage by killing the only route real minting uses.

    The store must OWN the anchored transaction end-to-end and let the
    caller compose into it -- not accept a connection whose held database
    it cannot identify.
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

    def test_the_store_vends_an_anchored_transaction(
        self, tmp_path: Path
    ) -> None:
        store = self._migrated(tmp_path)
        assert hasattr(store, "anchored_transaction"), (
            "the store cannot own the transaction the guarded writer needs"
        )

    def test_a_vended_transaction_accepts_the_put(self, tmp_path: Path) -> None:
        store = self._migrated(tmp_path)
        env, authority, params_hash, rendered = _chain()
        with store.anchored_transaction() as conn:
            store.put(
                _artifact(env, authority, params_hash, rendered),
                connection=conn,
            )
        with closing(sqlite3.connect(store.db_path)) as check:
            assert check.execute(
                f"SELECT count(*) FROM {V2_TABLE}"
            ).fetchone()[0] == 1

    def test_a_foreign_connection_is_still_refused(
        self, tmp_path: Path
    ) -> None:
        """Vending must not become a blanket permit."""
        store = self._migrated(tmp_path)
        env, authority, params_hash, rendered = _chain()
        with closing(sqlite3.connect(store.db_path)) as foreign:
            with pytest.raises(ValueError, match="caller-supplied"):
                store.put(
                    _artifact(env, authority, params_hash, rendered),
                    connection=foreign,
                )

    def test_a_failure_inside_the_transaction_rolls_back_whole(
        self, tmp_path: Path
    ) -> None:
        """Atomicity is the point: a reservation must not survive an
        artifact insert that failed."""
        store = self._migrated(tmp_path)
        env, authority, params_hash, rendered = _chain()

        class Boom(RuntimeError):
            pass

        with contextlib.suppress(Boom):
            with store.anchored_transaction() as conn:
                store.put(
                    _artifact(env, authority, params_hash, rendered),
                    connection=conn,
                )
                raise Boom("after the insert, before the commit")

        with closing(sqlite3.connect(store.db_path)) as check:
            assert check.execute(
                f"SELECT count(*) FROM {V2_TABLE}"
            ).fetchone()[0] == 0


class TestVendingIsPerStore:
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

    def test_one_stores_vended_connection_cannot_write_another(
        self, tmp_path: Path
    ) -> None:
        """A process-global set proves only that SOME store vended this
        connection. Reproduced: A vended one and B.put(connection=connA)
        succeeded, writing A."""
        a_dir = tmp_path / "A"
        b_dir = tmp_path / "B"
        a_dir.mkdir()
        b_dir.mkdir()
        store_a = self._migrated(a_dir)
        store_b = self._migrated(b_dir)
        env, authority, params_hash, rendered = _chain()

        with store_a.anchored_transaction() as conn_a:
            with pytest.raises(ValueError, match="caller-supplied"):
                store_b.put(
                    _artifact(env, authority, params_hash, rendered),
                    connection=conn_a,
                )

        for store in (store_a, store_b):
            with closing(sqlite3.connect(store.db_path)) as check:
                assert check.execute(
                    f"SELECT count(*) FROM {V2_TABLE}"
                ).fetchone()[0] == 0


def _migrated_v2_guarded_route_material(tmp_path: Path):
    """Persist and validate voice evidence in the migrated store itself."""
    from core.governance import s7_guarded_execution as guarded
    from tests.test_s7_voice_bundle_v2 import _voice_bundle

    store = _migrated_store(tmp_path)
    env, authority, params_hash, rendered = _chain()
    artifact = _artifact(env, authority, params_hash, rendered)
    bundle = replace(
        _voice_bundle(seed="route-atomicity", action=artifact.action),
        request_id=artifact.request_id,
        request_envelope_hash=artifact.request_envelope_hash,
        rendered_text_hash=artifact.rendered_text_hash,
        action_params_hash=artifact.action_params_hash,
        precondition_hash=artifact.precondition_hash,
        authority_context_hash=artifact.authority_context_hash,
        source_bundle_hash=None,
    )
    bundle = replace(
        bundle,
        source_bundle_hash=guarded.s7_voice_consultation_bundle_hash(bundle),
    )

    with store.anchored_transaction() as conn:
        guarded.put_voice_source_bundle_v2(bundle=bundle, conn=conn)
    with store.anchored_transaction() as conn:
        read_back, version = guarded.read_voice_source_bundle(
            source_ref_hash=bundle.source_ref_hash,
            conn=conn,
        )
        validation = guarded.validate_voice_source_bundle(
            bundle=read_back,
            version=version,
            purpose="execution",
        )
    assert type(validation) is guarded.S7VoiceSourceBundleValidationResultV2
    assert validation.schema_version == "s7.voice_source_bundle.v2"
    assert validation.source_bundle_hash == bundle.source_bundle_hash
    assert validation.action == artifact.action
    assert validation.mint_eligible is True

    bundle_use_store = guarded.S7VoiceBundleUseStore(store.db_path)
    bundle_use_store.put_unreserved(
        guarded.S7VoiceBundleUse.new_unreserved(
            request_id=artifact.request_id,
            source_ref_hash=bundle.source_ref_hash,
            consultation_id=bundle.consultation_id,
            used_at=NOW,
        )
    )
    guarded_store = guarded.S7GuardedStateStore(
        authorization_store=store,
        voice_bundle_use_store=bundle_use_store,
    )
    return store, guarded_store, bundle_use_store, artifact, bundle, validation


def _v2_artifact_row(db_path: Path, artifact_id: str):
    with closing(sqlite3.connect(db_path)) as conn:
        return conn.execute(
            f"SELECT artifact_id, action FROM {V2_TABLE} WHERE artifact_id = ?",
            (artifact_id,),
        ).fetchone()


class TestTheRealGuardedRouteStaysAtomicAfterMigration:
    def test_success_commits_the_artifact_and_voice_reservation_together(
        self, tmp_path: Path
    ) -> None:
        (
            store,
            guarded_store,
            bundle_use_store,
            artifact,
            bundle,
            validation,
        ) = _migrated_v2_guarded_route_material(tmp_path)

        guarded_store.put_artifact_with_bundle_reservation(
            artifact=artifact,
            source_bundle_validation=validation,
            source_ref_hash=bundle.source_ref_hash,
            reservation_token="route-success-token",
            now=NOW,
        )

        assert _v2_artifact_row(store.db_path, artifact.artifact_id) == (
            artifact.artifact_id,
            artifact.action,
        )
        bundle_use = bundle_use_store.get_for_source_ref(bundle.source_ref_hash)
        assert bundle_use is not None
        assert (
            bundle_use.reservation_state,
            bundle_use.artifact_id,
            bundle_use.reservation_token_hash,
            bundle_use.reserved_at,
            bundle_use.consumed_at,
        ) == (
            "reserved",
            artifact.artifact_id,
            s7.canonical_hash("route-success-token"),
            NOW,
            None,
        )

    def test_insert_failure_rolls_back_artifact_and_voice_reservation(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        (
            store,
            guarded_store,
            bundle_use_store,
            artifact,
            bundle,
            validation,
        ) = _migrated_v2_guarded_route_material(tmp_path)
        blocker = replace(artifact, artifact_id="artifact-atomicity-blocker")
        assert blocker.artifact_id != artifact.artifact_id
        assert blocker.nonce == artifact.nonce
        store.put(blocker)
        real_put = store.put
        reservation_states_at_insert: list[str | None] = []

        def observing_real_put(candidate, *, connection=None):
            if connection is None:
                reservation_states_at_insert.append(None)
            else:
                pending_use = bundle_use_store.get_for_source_ref(
                    bundle.source_ref_hash,
                    connection=connection,
                )
                reservation_states_at_insert.append(
                    None if pending_use is None else pending_use.reservation_state
                )
            return real_put(candidate, connection=connection)

        monkeypatch.setattr(store, "put", observing_real_put)

        with pytest.raises(
            sqlite3.IntegrityError,
            match=r"UNIQUE constraint failed: s7_authorization_artifacts_v2\.nonce",
        ):
            guarded_store.put_artifact_with_bundle_reservation(
                artifact=artifact,
                source_bundle_validation=validation,
                source_ref_hash=bundle.source_ref_hash,
                reservation_token="route-rollback-token",
                now=NOW,
            )

        assert reservation_states_at_insert == ["reserved"]
        assert _v2_artifact_row(store.db_path, artifact.artifact_id) is None
        assert _v2_artifact_row(store.db_path, blocker.artifact_id) == (
            blocker.artifact_id,
            blocker.action,
        )
        bundle_use = bundle_use_store.get_for_source_ref(bundle.source_ref_hash)
        assert bundle_use is not None
        assert (
            bundle_use.reservation_state,
            bundle_use.artifact_id,
            bundle_use.reservation_token_hash,
            bundle_use.reserved_at,
            bundle_use.consumed_at,
        ) == ("unreserved", None, None, None, None)
        assert (
            bundle_use_store.get_for_artifact(
                bundle.source_ref_hash,
                artifact.artifact_id,
            )
            is None
        )

        # POSITIVE CONTROL: remove only the nonce collision. The same durable
        # bundle, validator result, artifact and reservation route must work.
        with store.anchored_transaction() as conn:
            conn.execute(
                f"DELETE FROM {V2_TABLE} WHERE artifact_id = ?",
                (blocker.artifact_id,),
            )
        guarded_store.put_artifact_with_bundle_reservation(
            artifact=artifact,
            source_bundle_validation=validation,
            source_ref_hash=bundle.source_ref_hash,
            reservation_token="route-rollback-token",
            now=NOW,
        )
        assert _v2_artifact_row(store.db_path, artifact.artifact_id) == (
            artifact.artifact_id,
            artifact.action,
        )
        reserved = bundle_use_store.get_for_source_ref(bundle.source_ref_hash)
        assert reserved is not None
        assert reservation_states_at_insert == ["reserved", "reserved"]
        assert reserved.reservation_state == "reserved"
        assert reserved.artifact_id == artifact.artifact_id


class TestTheStorePathIsWalkedComponentwise:
    """Opening the whole parent path once with O_NOFOLLOW protects only the
    FINAL component. Reproduced: an intermediate symlink was followed and a
    v2 row landed in the real target store.
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

    def test_an_intermediate_symlink_cannot_choose_the_store(
        self, tmp_path: Path
    ) -> None:
        real = tmp_path / "real"
        real.mkdir()
        self._migrated(real)
        link = tmp_path / "via"
        link.symlink_to(real)

        env, authority, params_hash, rendered = _chain()
        with pytest.raises(OSError):
            s7.S7AuthorizationStore(link / "ceremony.sqlite3").put(
                _artifact(env, authority, params_hash, rendered)
            )
        with closing(sqlite3.connect(real / "ceremony.sqlite3")) as check:
            assert check.execute(
                f"SELECT count(*) FROM {V2_TABLE}"
            ).fetchone()[0] == 0

    def test_a_legitimate_nested_path_still_works(self, tmp_path: Path) -> None:
        """CONTROL: refusing every multi-component path would satisfy the
        test above while breaking ordinary nested store locations."""
        nested = tmp_path / "a" / "b" / "c"
        nested.mkdir(parents=True)
        store = self._migrated(nested)
        env, authority, params_hash, rendered = _chain()
        store.put(_artifact(env, authority, params_hash, rendered))
        with closing(sqlite3.connect(store.db_path)) as check:
            assert check.execute(
                f"SELECT count(*) FROM {V2_TABLE}"
            ).fetchone()[0] == 1


class TestHeldStoreVerificationHasAnExactCallsiteAllowlist:
    """The amended canon names a second authority, so it needs the same
    guard the initializer has -- built from the SAME hardened scanner
    rather than a fresh weaker copy.

    My first version collapsed duplicates into a set, and missed
    assignment aliases and getattr entirely. It was neither
    occurrence-exact nor route-exhaustive.
    """

    TARGET = "_verify_held_store_activation"
    ALLOWED = [
        "core/governance/operator_user_boundary.py::"
        "S7AuthorizationStore.anchored_transaction",
        "core/governance/operator_user_boundary.py::"
        "S7AuthorizationStore.consume_for_execution",
    ]

    def _callsites(self) -> list[str]:
        import os

        repo = Path(__file__).resolve().parents[1]
        skip = {".git", ".venv", "node_modules", "__pycache__", "tests", "docs"}
        found: list[str] = []
        for dirpath, dirnames, filenames in os.walk(repo):
            dirnames[:] = [
                d for d in dirnames if d not in skip and not d.startswith(".")
            ]
            for name in filenames:
                if not name.endswith(".py"):
                    continue
                path = Path(dirpath, name)
                try:
                    source = path.read_text()
                except (OSError, UnicodeDecodeError):
                    continue
                try:
                    scopes = find_callsites(source, self.TARGET)
                except SyntaxError:
                    continue
                rel = str(path.relative_to(repo))
                found += [f"{rel}::{scope}" for scope in scopes]
        return sorted(found)

    def test_something_verifies_at_all(self) -> None:
        """CONTROL: an empty sweep makes the allowlist vacuous."""
        assert self._callsites(), "nothing verifies held-store activation"

    def test_the_callsites_are_exactly_the_allowlist(self) -> None:
        """OCCURRENCE-exact: a list, not a set, so a second call inside an
        allowed method cannot hide behind the first."""
        assert self._callsites() == sorted(self.ALLOWED)


class TestTheCallsiteScannerIsItselfAttacked:
    """Five bypasses, each of which defeated an earlier scanner."""

    TARGET = "_verify_held_store_activation"

    def test_a_direct_call_is_seen(self) -> None:
        assert find_callsites(
            "class S:\n    def f(self):\n"
            "        _verify_held_store_activation(1, 2, 3)\n",
            self.TARGET,
        ) == ["S.f"]

    def test_multiplicity_is_preserved(self) -> None:
        """A set collapsed two calls into one entry."""
        assert find_callsites(
            "class S:\n    def f(self):\n"
            "        _verify_held_store_activation(1, 2, 3)\n"
            "        _verify_held_store_activation(4, 5, 6)\n",
            self.TARGET,
        ) == ["S.f", "S.f"]

    def test_an_assignment_alias_is_seen(self) -> None:
        assert find_callsites(
            "class S:\n    def f(self):\n"
            "        v = _verify_held_store_activation\n"
            "        v(1, 2, 3)\n",
            self.TARGET,
        ) == ["S.f"]

    def test_an_annotated_alias_is_seen(self) -> None:
        assert find_callsites(
            "class S:\n    def f(self):\n"
            "        v: object = _verify_held_store_activation\n"
            "        v(1, 2, 3)\n",
            self.TARGET,
        ) == ["S.f"]

    def test_getattr_by_string_is_seen(self) -> None:
        assert find_callsites(
            'class S:\n    def f(self):\n'
            '        getattr(m, "_verify_held_store_activation")(1, 2, 3)\n',
            self.TARGET,
        ) == ["S.f"]

    def test_a_nested_scope_is_not_the_method(self) -> None:
        """Lexical qualification: a closure is NOT its enclosing method, so
        a call hidden in one cannot satisfy an allowlist written for the
        method.

        Asserted as the PROPERTY, not a label. The scanner's nested naming
        is diagnostically imprecise -- a known, accepted wart -- but every
        nested scope stays prefixed, which is what the guard relies on.
        """
        found = find_callsites(
            "class S:\n    def f(self):\n        def inner():\n"
            "            _verify_held_store_activation(1, 2, 3)\n",
            self.TARGET,
        )
        assert found, "the nested call was not seen at all"
        assert found != ["S.f"], "a closure was reported as its method"
        assert all(scope.startswith("S.f") for scope in found), found

    def test_an_unrelated_call_is_not_seen(self) -> None:
        assert find_callsites(
            "class S:\n    def f(self):\n        something_else()\n",
            self.TARGET,
        ) == []

    def test_a_decoy_function_cannot_impersonate_the_class_method(self) -> None:
        """THE bypass. Capitalization-guessing rendered a nested function
        named like a class identically to the real class method, so a dead
        call in a decoy certified the allowlist while the live transaction
        verified nothing."""
        decoy = find_callsites(
            "def S7AuthorizationStore():\n"
            "    def anchored_transaction():\n"
            "        _verify_held_store_activation()\n",
            self.TARGET,
        )
        real = find_callsites(
            "class S7AuthorizationStore:\n"
            "    def anchored_transaction(self):\n"
            "        _verify_held_store_activation()\n",
            self.TARGET,
        )
        assert decoy != real, "a decoy function impersonated the class method"
        assert real == ["S7AuthorizationStore.anchored_transaction"]

    def test_a_lowercase_class_is_still_a_class(self) -> None:
        assert find_callsites(
            "class helper:\n"
            "    def f(self):\n"
            "        _verify_held_store_activation()\n",
            self.TARGET,
        ) == ["helper.f"]

    def test_an_uppercase_function_is_still_a_function(self) -> None:
        assert find_callsites(
            "def Helper():\n"
            "    def f():\n"
            "        _verify_held_store_activation()\n",
            self.TARGET,
        ) == ["Helper.<locals>.f"]

    def test_mixed_nesting_qualifies_by_kind(self) -> None:
        assert find_callsites(
            "class A:\n"
            "    def m(self):\n"
            "        class B:\n"
            "            def n(self):\n"
            "                _verify_held_store_activation()\n",
            self.TARGET,
        ) == ["A.m.<locals>.B.n"]  # class-in-function IS a <locals> scope

    def test_a_reverse_ordered_alias_chain_is_seen(self) -> None:
        assert find_callsites(
            "class S:\n"
            "    def f(self):\n"
            "        d = c\n"
            "        c = b\n"
            "        b = a\n"
            "        a = _verify_held_store_activation\n"
            "        d()\n",
            self.TARGET,
        ) == ["S.f"]


class TestScannerScopeCollisionsAreClosed:
    """Every shape that once rendered identically to the real class method
    while never executing the verifier."""

    TARGET = "_verify_held_store_activation"
    REAL = (
        "class S7AuthorizationStore:\n"
        "    def anchored_transaction(self):\n"
        "        _verify_held_store_activation()\n"
    )

    def _real(self) -> list[str]:
        return find_callsites(self.REAL, self.TARGET)

    def test_the_real_method_is_the_baseline(self) -> None:
        assert self._real() == ["S7AuthorizationStore.anchored_transaction"]

    def test_a_class_nested_in_a_function_does_not_collide(self) -> None:
        """`<locals>` must appear whenever the ENCLOSING scope is a
        function, whatever the nested definition is -- which is how Python
        itself qualifies it."""
        assert find_callsites(
            "def S7AuthorizationStore():\n"
            "    class anchored_transaction:\n"
            "        _verify_held_store_activation()\n",
            self.TARGET,
        ) != self._real()

    def test_a_lambda_body_does_not_collide(self) -> None:
        """A lambda does not run where it is written."""
        assert find_callsites(
            "class S7AuthorizationStore:\n"
            "    def anchored_transaction(self):\n"
            "        _u = lambda: _verify_held_store_activation()\n",
            self.TARGET,
        ) != self._real()

    def test_a_generator_body_does_not_collide(self) -> None:
        assert find_callsites(
            "class S7AuthorizationStore:\n"
            "    def anchored_transaction(self):\n"
            "        _u = (_verify_held_store_activation() for _ in ())\n",
            self.TARGET,
        ) != self._real()


class TestActivationIsActuallyVerifiedAtRuntime:
    """BEHAVIOURAL, because structure can always be gamed.

    A structural allowlist proves a call APPEARS in an allowed scope. It
    cannot prove the call RUNS -- a lambda, a comprehension, or a dead
    branch all satisfy it. These drive both allowed methods and require
    the verifier to fire exactly once.
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

    def _counting(self, monkeypatch) -> list[object]:
        calls: list[object] = []
        real = s7._verify_held_store_activation

        def counting(dir_fd, store_fd, conn):
            calls.append(object())
            return real(dir_fd, store_fd, conn)

        monkeypatch.setattr(s7, "_verify_held_store_activation", counting)
        return calls

    def test_anchored_transaction_verifies_exactly_once(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        store = self._migrated(tmp_path)
        calls = self._counting(monkeypatch)
        with store.anchored_transaction():
            pass
        assert len(calls) == 1, calls

    def test_consume_for_execution_verifies_exactly_once(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        store = self._migrated(tmp_path)
        env, authority, params_hash, rendered = _chain()
        store.put(_artifact(env, authority, params_hash, rendered))
        calls = self._counting(monkeypatch)
        monkeypatch.setattr(
            s7, "_mint_s7_execution_grant", lambda **_kwargs: object()
        )
        store.consume_for_execution(
            "artifact-join-1",
            rendered=rendered,
            action_params_hash=params_hash,
            authority_context=authority,
            precondition_hash=env.precondition_hash,
            derived_work_class=env.derived_work_class,
            derived_aggregation_group=env.derived_aggregation_group,
            now=NOW,
        )
        assert len(calls) == 1, calls
