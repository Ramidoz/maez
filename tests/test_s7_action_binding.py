"""S7 v2 exact action binding — RED set, slice 1: the generic bypass.

Written against ratified design v15 BEFORE implementation.

The defect: execution_grant_authorizes_action compares only the derived
work class and canonical_hash(params). Neither carries the action, so ONE
grant authorizes every sibling operation of the same class with identical
params. At the S7 layer a tap for "switch to CUDA" is a tap for "some
self_modification with these arguments".

These tests drive the REAL path -- envelope, rendering, artifact, durable
row in a private tmpdir store, and a grant minted by
consume_for_execution. My first version asserted field presence, constant
contents and a helper I invented; an implementation could have added dead
fields and turned it green while leaving the authorization path unwired.

No physical key is needed: a private tmpdir store and the real mint path
prove the software chain. They do NOT prove a human ceremony, and nothing
here claims to.
"""

from __future__ import annotations

import contextlib
import sqlite3
from pathlib import Path

import pytest

from core.governance import operator_user_boundary as s7
from core.governance import s7_guarded_execution as guarded

NOW = "2026-08-07T12:00:00Z"
FUTURE = "2026-08-07T16:00:00Z"
ACTION = "model_routing.cutover_cuda"
SIBLING = "model_routing.wipe_and_replace"
PARAMS = {"cutover_action": ACTION, "window_id": "cutover-20260713-1202"}


def _bundle(action: str = ACTION):
    """Build a REAL envelope -> rendering -> artifact chain."""
    env = s7.build_work_request_envelope(
        request_id="req-action-binding-1",
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
        # The envelope must NAME the consultation; a voice-seat class
        # cannot render without one, and the id must match.
        maez_voice_consultation_id="voice-action-binding-1",
    )
    authority = s7.AuthorityContext(
        actor_id="founder",
        actor_handle_hmac="hmac:s7:founder:" + ("a" * 64),
        role_names=("operator",),
        grant_source="founder_webauthn",
        allowed_scopes=("operator_health",),
        auth_method="founder_webauthn",
        surface="cockpit",
        credential_ref="cred-1",
        created_at=NOW,
        expires_at=FUTURE,
        verified=True,
    )
    params_hash = s7.canonical_hash(dict(PARAMS))
    # self_modification is voice-seat guarded: rendering REFUSES without a
    # matching consultation. That is Maez's seat in its own remaking, and
    # the fixture must satisfy it rather than route around it.
    consultation = s7.MaezVoiceConsultation(
        consultation_id="voice-action-binding-1",
        request_id=env.request_id,
        request_envelope_hash=s7.work_request_envelope_hash(env),
        producer="self_mod_dialog_terminal_state",
        source_ref_kind="self_mod_dialog_exchange",
        source_ref_hash="c" * 64,
        maez_voice_consulted=True,
        maez_objection_state="absent",
        maez_withdrew_request=False,
        unavailable_reason_code=None,
        created_at=NOW,
    )
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


def _stored_artifact(env, authority, params_hash, rendered):
    """A STORAGE fixture. NOT the mint join.

    It constructs the carrier directly with a caller-chosen action, so it
    proves nothing about how authority is minted -- a mutation in the real
    mint seam would not disturb it. Named for what it is; the mint join is
    proven separately in TestTheProductionMintJoin.
    """
    return s7.S7AuthorizationArtifact(
        artifact_id="artifact-action-binding-1",
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
        action=ACTION,
    )


def _migrated_store(tmp: Path) -> "s7.S7AuthorizationStore":
    """A private store carried through the REAL migration seam.

    Opening S7AuthorizationStore must NOT make v2 appear -- the design
    forbids open-time migration -- so the fixture must invoke the
    migration entrypoint explicitly. That entrypoint does not exist yet,
    which is the intended red.
    """
    store = s7.S7AuthorizationStore(tmp / "ceremony.sqlite3")
    # PRIVATE helper, separately named. My first version froze
    # migrate_authorization_store_to_v2(store_dir_fd=…, _private_root=…),
    # which recreates the alternate-root capability the final design
    # removed -- a public-looking signature taking a root.
    # Production exposes migrate_authorization_store_to_v2() with NO
    # arguments; only this private-copy helper accepts a directory.
    with _dir_fd(tmp) as fd:
        s7._migrate_authorization_store_to_v2_at(store_dir_fd=fd)
    return store


@contextlib.contextmanager
def _dir_fd(path: Path):
    """Context-managed: my first version leaked every descriptor it opened."""
    import os

    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        yield fd
    finally:
        os.close(fd)


class TestTheBypassExistsToday:
    """GUARDS on the defect, so the fix is provably a fix."""

    def test_sibling_actions_derive_the_same_class(self) -> None:
        assert s7.derive_work_class(
            action=ACTION, params=dict(PARAMS)
        ) == s7.derive_work_class(action=SIBLING, params=dict(PARAMS))


class TestTheGenericEdgeRefusesSiblings:
    """THE binding red, through a REAL minted grant."""

    def test_a_real_grant_refuses_a_sibling_action(self, tmp_path: Path) -> None:
        env, authority, params_hash, rendered = _bundle()
        store = _migrated_store(tmp_path)
        artifact = _stored_artifact(env, authority, params_hash, rendered)
        store.put(artifact)
        grant, _ = store.consume_for_execution(
            artifact.artifact_id,
            rendered=rendered,
            action_params_hash=params_hash,
            authority_context=authority,
            precondition_hash=artifact.precondition_hash,
            derived_work_class=artifact.derived_work_class,
            derived_aggregation_group=artifact.derived_aggregation_group,
            now=NOW,
        )
        assert grant is not None
        assert s7.execution_grant_authorizes_action(
            grant, action=ACTION, params=dict(PARAMS)
        )
        # THE defect: identical params, sibling action, same class.
        assert not s7.execution_grant_authorizes_action(
            grant, action=SIBLING, params=dict(PARAMS)
        )


class TestActionSurvivesEveryJoin:
    """Exact equality at each carrier, driven end to end."""

    def test_action_is_equal_across_envelope_rendered_artifact_row_grant(
        self, tmp_path: Path
    ) -> None:
        env, authority, params_hash, rendered = _bundle()
        assert env.action == ACTION
        assert rendered.action == ACTION

        store = _migrated_store(tmp_path)
        artifact = _stored_artifact(env, authority, params_hash, rendered)
        assert artifact.action == ACTION
        store.put(artifact)

        with sqlite3.connect(store.db_path) as conn:
            row = conn.execute(
                "select action from s7_authorization_artifacts_v2 "
                "where artifact_id = ?",
                (artifact.artifact_id,),
            ).fetchone()
        assert row is not None and row[0] == ACTION

        grant, _ = store.consume_for_execution(
            artifact.artifact_id,
            rendered=rendered,
            action_params_hash=params_hash,
            authority_context=authority,
            precondition_hash=artifact.precondition_hash,
            derived_work_class=artifact.derived_work_class,
            derived_aggregation_group=artifact.derived_aggregation_group,
            now=NOW,
        )
        assert grant.action == ACTION


class TestTheActionIsVISIBLE:
    """Rendered TEXT, not a constant. A hash cannot be read by a human."""

    def test_the_signed_text_shows_the_exact_action_line_once(self) -> None:
        _env, _authority, _params_hash, rendered = _bundle()
        text = rendered.rendered_text
        assert text.count(f"Action: {ACTION}") == 1, text

    def test_the_action_line_sits_between_request_id_and_work_class(
        self,
    ) -> None:
        _env, _authority, _params_hash, rendered = _bundle()
        lines = rendered.rendered_text.splitlines()

        def line_index(prefix: str) -> int:
            hits = [i for i, l in enumerate(lines) if l.startswith(prefix)]
            assert len(hits) == 1, (prefix, lines)
            return hits[0]

        assert (
            line_index("Request id")
            < line_index("Action:")
            < line_index("Work class")
        ), lines


class TestActionGrammarAtTheCARRIERS:
    """Validated where carriers are BUILT, not only by a standalone helper."""

    @pytest.mark.parametrize(
        "action",
        [
            "write_soul_note",
            "edit_soul_section",
            "register_backup_webauthn_credential",
            "disable_founder_webauthn_credential",
            "run_shell",
            "backup_status",
            ACTION,
        ],
    )
    def test_every_existing_action_still_builds_an_envelope(
        self, action: str
    ) -> None:
        """v3's grammar closed all six of these roads."""
        assert _bundle(action)[0].action == action

    @pytest.mark.parametrize(
        "action", ["a\nb", "a\tb", ".x", "x.", "x..y", "X", "a b", "", "a" * 129]
    )
    def test_malformed_actions_refuse_AT_THE_ENVELOPE(self, action: str) -> None:
        with pytest.raises(ValueError):
            _bundle(action)


def _voice_bundle(action: str):
    """A REAL S7VoiceConsultationBundle. make_test_voice_bundle was mine."""
    return guarded.S7VoiceConsultationBundle(
        source_ref_hash="s" * 64,
        request_id="req-action-binding-1",
        consultation_id="voice-action-binding-1",
        request_envelope_hash="e" * 64,
        rendered_text_hash="r" * 64,
        action_params_hash=s7.canonical_hash(dict(PARAMS)),
        precondition_hash="p" * 64,
        authority_context_hash="c" * 64,
        maez_voice_consultation_hash="m" * 64,
        rendered_prompt_ref="prompts/1",
        rendered_prompt_hash="q" * 64,
        mutation_preview_hash="v" * 64,
        rollback_plan_ref="rollback/1",
        context_manifest_hash="x" * 64,
        runtime_identity_hash="y" * 64,
        model_routing_identity_hash="z" * 64,
        model_config_hash="w" * 64,
        raw_response_ref="responses/1",
        raw_response_hash="t" * 64,
        semantic_reader_attempt_hash="u" * 64,
        expires_at=FUTURE,
        authority_class="self_modification",
        has_grounded_semantic_blocking_signal=False,
        context_manifest_ref="manifests/1",
        source_bundle_hash="b" * 64,
        action=action,
    )


class TestTheProductionMintJoin:
    """The FROZEN seam, in s7_guarded_execution -- not operator_user_boundary.

    My first version put mint_from_validated_bundle, a v2-suffixed
    validator, and a make_test_voice_bundle helper on the wrong module.
    Code could have added three convenience functions there and turned
    these green while the real mint route stayed untouched.
    """

    def test_the_frozen_validator_lives_on_the_voice_plane(self) -> None:
        assert hasattr(guarded, "validate_voice_source_bundle")

    def test_the_validator_takes_version_and_purpose(self) -> None:
        import inspect

        params = inspect.signature(guarded.validate_voice_source_bundle).parameters
        assert {"bundle", "version", "purpose"} <= set(params), list(params)

    def test_mint_takes_no_action_argument(self) -> None:
        import inspect

        params = inspect.signature(guarded.mint_from_validated_bundle).parameters
        assert "action" not in params, list(params)
        assert {"bundle", "validation"} <= set(params)

    def test_a_real_mint_declares_the_v2_schema_and_the_validated_action(
        self, tmp_path: Path
    ) -> None:
        """MINT, then assert the artifact -- not dataclass field presence."""
        bundle = _voice_bundle(ACTION)
        validation = guarded.validate_voice_source_bundle(
            bundle=bundle, version="s7.voice_source_bundle.v2",
            purpose="execution",
        )
        with sqlite3.connect(tmp_path / "x.sqlite3") as conn:
            artifact = guarded.mint_from_validated_bundle(
                bundle=bundle, validation=validation, conn=conn
            )
        assert artifact.schema_version == "s7.authorization_artifact.v2"
        assert artifact.action == ACTION

    def test_a_bundle_validated_for_A_cannot_mint_for_B(
        self, tmp_path: Path
    ) -> None:
        validated_for_a = guarded.validate_voice_source_bundle(
            bundle=_voice_bundle(ACTION),
            version="s7.voice_source_bundle.v2",
            purpose="execution",
        )
        with sqlite3.connect(tmp_path / "y.sqlite3") as conn:
            with pytest.raises(ValueError):
                guarded.mint_from_validated_bundle(
                    bundle=_voice_bundle(SIBLING),
                    validation=validated_for_a,
                    conn=conn,
                )


class TestPrivateHelperHasOneCallsite:
    """The private migration helper must not spread into production."""

    def test_no_production_module_calls_the_private_helper(self) -> None:
        import ast

        repo = Path(__file__).resolve().parents[1]
        offenders = []
        for root in ("core", "scripts", "daemon", "api"):
            base = repo / root
            if not base.is_dir():
                continue
            for path in base.rglob("*.py"):
                tree = ast.parse(path.read_text(errors="strict"))
                for node in ast.walk(tree):
                    if isinstance(node, ast.Call):
                        f = node.func
                        name = (
                            f.attr if isinstance(f, ast.Attribute)
                            else getattr(f, "id", None)
                        )
                        if name == "_migrate_authorization_store_to_v2_at":
                            offenders.append(
                                (str(path.relative_to(repo)), node.lineno)
                            )
        assert offenders == [], offenders


class TestHistoricalV1CannotAuthorize:
    """An UNEXPIRED v1 row, seeded BEFORE migration, through the public edge."""

    def test_an_unexpired_v1_row_cannot_authorize_execution(
        self, tmp_path: Path
    ) -> None:
        """Seed v1, THEN migrate, THEN submit.

        My first version inserted into the legacy table with
        INSERT … SELECT * across two different shapes, and did it AFTER
        activation -- when the v1 freeze triggers must forbid that write
        anyway. Both mistakes came from treating the legacy row as
        something to place rather than something that was already there.
        """
        env, authority, params_hash, rendered = _bundle()
        store = s7.S7AuthorizationStore(tmp_path / "ceremony.sqlite3")

        # 1. seed an UNEXPIRED v1 row while v1 is still writable.
        #    An expired row would refuse for the wrong reason -- all four
        #    live rows are expired.
        # A GENUINE v1 record: the unversioned shape, with NO action
        # column. Seeding it through the action-bearing carrier would make
        # it a v2 row wearing a v1 label -- not a historical record at all.
        legacy = _stored_artifact(env, authority, params_hash, rendered)
        with sqlite3.connect(store.db_path) as conn:
            conn.execute(
                "INSERT INTO s7_authorization_artifacts ("
                "artifact_id, request_id, request_envelope_hash,"
                "rendered_text_hash, action_params_hash, precondition_hash,"
                "authority_context_hash, derived_work_class,"
                "derived_aggregation_group, nonce, credential_ref,"
                "auth_method, grant_source, user_presence, user_verification,"
                "created_at, expires_at, consumed_at, consumed_by_request_id,"
                "ceremony_kind) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    legacy.artifact_id, legacy.request_id,
                    legacy.request_envelope_hash, legacy.rendered_text_hash,
                    legacy.action_params_hash, legacy.precondition_hash,
                    legacy.authority_context_hash, legacy.derived_work_class,
                    legacy.derived_aggregation_group, legacy.nonce,
                    legacy.credential_ref, legacy.auth_method,
                    legacy.grant_source, 1, 1, NOW, FUTURE, None, None,
                    "founder_local_webauthn",
                ),
            )
            unexpired = conn.execute(
                "select count(*) from s7_authorization_artifacts "
                "where artifact_id = ? and expires_at > ?",
                (legacy.artifact_id, NOW),
            ).fetchone()[0]
        assert unexpired == 1

        # 2. migrate that PRIVATE store through the real seam.
        with _dir_fd(tmp_path) as fd:
            s7._migrate_authorization_store_to_v2_at(store_dir_fd=fd)

        # 3. the v1 row must not authorize anything.
        grant, _ = store.consume_for_execution(
            legacy.artifact_id,
            rendered=rendered,
            action_params_hash=params_hash,
            authority_context=authority,
            precondition_hash=legacy.precondition_hash,
            derived_work_class=legacy.derived_work_class,
            derived_aggregation_group=legacy.derived_aggregation_group,
            now=NOW,
        )
        assert grant is None


class TestOpeningTheStoreDoesNotMigrate:
    """Open-time migration is forbidden by the design."""

    def test_v2_does_not_appear_merely_by_opening(self, tmp_path: Path) -> None:
        store = s7.S7AuthorizationStore(tmp_path / "ceremony.sqlite3")
        with sqlite3.connect(store.db_path) as conn:
            names = {
                n for (n,) in conn.execute(
                    "select name from sqlite_master where type='table'"
                )
            }
        assert "s7_authorization_artifacts_v2" not in names, names
