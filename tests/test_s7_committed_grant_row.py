"""S7 v2 committed-row consumption and founder-presence proof.

All stores in this module are disposable private fixtures.  Synthetic rows
exercise storage plumbing only; they are not evidence that an owner read a
consultation or touched a founder key.
"""

from __future__ import annotations

import sqlite3
from contextlib import closing
from dataclasses import fields, replace
from inspect import signature
import os
from pathlib import Path

import pytest

from core.governance import operator_user_boundary as s7
from tests.test_s7_action_joins import NOW, _artifact, _chain, _migrated_store


ROW_BACKED_GRANT_FIELDS = (
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
)


def test_committed_grant_row_carries_the_complete_frozen_shape() -> None:
    assert tuple(field.name for field in fields(s7.CommittedGrantRow)) == (
        *ROW_BACKED_GRANT_FIELDS,
        "schema_version",
        "user_presence",
        "user_verification",
        "created_at",
        "expires_at",
        "consumed_by_request_id",
    )


def _stored_authorization(tmp_path: Path):
    env, authority, params_hash, rendered = _chain()
    store = _migrated_store(tmp_path)
    store.put(_artifact(env, authority, params_hash, rendered))
    consume_kwargs = {
        "rendered": rendered,
        "action_params_hash": params_hash,
        "authority_context": authority,
        "precondition_hash": env.precondition_hash,
        "derived_work_class": env.derived_work_class,
        "derived_aggregation_group": env.derived_aggregation_group,
        "now": NOW,
    }
    return store, consume_kwargs


def test_connection_taking_consume_uses_the_callers_held_connection(
    tmp_path: Path, monkeypatch
) -> None:
    store, consume_kwargs = _stored_authorization(tmp_path)
    callback_states: list[bool] = []

    with s7._held_store(store.db_path) as (dir_fd, store_fd, connection):
        def pathname_reopen_is_forbidden(*_args, **_kwargs):
            raise AssertionError("consumption reopened the store by pathname")

        monkeypatch.setattr(s7.sqlite3, "connect", pathname_reopen_is_forbidden)
        grant, callback_result, committed_row = (
            s7.consume_for_execution_with_committed_row(
                connection,
                "artifact-join-1",
                after_consume_before_commit=lambda _grant: callback_states.append(
                    connection.in_transaction
                ),
                **consume_kwargs,
            )
        )

        assert connection.in_transaction is False

    assert grant is not None
    assert callback_result is None
    assert callback_states == [True]
    assert committed_row is not None
    assert committed_row.artifact_id == grant.artifact_id
    assert committed_row.consumed_by_request_id == grant.request_id


def test_connection_primitive_cannot_take_independent_store_descriptors() -> None:
    params = signature(s7.consume_for_execution_on_connection).parameters

    assert "connection" in params
    assert "store_dir_fd" not in params
    assert "store_fd" not in params


def test_unbound_connection_cannot_borrow_another_stores_activation(
    tmp_path: Path,
) -> None:
    store, consume_kwargs = _stored_authorization(tmp_path)

    with s7._held_store(store.db_path) as (_dir_fd, _store_fd, held):
        assert held.execute(
            "SELECT consumed_at FROM s7_authorization_artifacts_v2 "
            "WHERE artifact_id = 'artifact-join-1'"
        ).fetchone() == (None,)

    with closing(sqlite3.connect(store.db_path)) as unbound:
        with pytest.raises(ValueError, match="verified held connection"):
            s7.consume_for_execution_on_connection(
                unbound,
                "artifact-join-1",
                **consume_kwargs,
            )

    with s7._held_store(store.db_path) as (_dir_fd, _store_fd, held):
        assert held.execute(
            "SELECT consumed_at FROM s7_authorization_artifacts_v2 "
            "WHERE artifact_id = 'artifact-join-1'"
        ).fetchone() == (None,)


def test_connection_bound_to_one_store_cannot_borrow_another_receipt(
    tmp_path: Path,
) -> None:
    env, authority, params_hash, rendered = _chain()
    store_a = _migrated_store(tmp_path / "store-a")
    store_b = _migrated_store(tmp_path / "store-b")
    store_b.put(_artifact(env, authority, params_hash, rendered))
    dir_a_fd = os.open(
        store_a.db_path.parent,
        os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
    )
    store_b_fd = os.open(store_b.db_path, os.O_RDWR | os.O_NOFOLLOW)
    try:
        mismatched = s7._open_s7_connection_from_held_store(
            dir_fd=dir_a_fd,
            store_fd=store_b_fd,
        )
        try:
            with pytest.raises(ValueError, match="does not describe"):
                s7.consume_for_execution_on_connection(
                    mismatched,
                    "artifact-join-1",
                    rendered=rendered,
                    action_params_hash=params_hash,
                    authority_context=authority,
                    precondition_hash=env.precondition_hash,
                    derived_work_class=env.derived_work_class,
                    derived_aggregation_group=env.derived_aggregation_group,
                    now=NOW,
                )
        finally:
            mismatched.close()
    finally:
        os.close(store_b_fd)
        os.close(dir_a_fd)

    with s7._held_store(store_b.db_path) as (_dir_fd, _store_fd, connection):
        assert connection.execute(
            "SELECT consumed_at FROM s7_authorization_artifacts_v2 "
            "WHERE artifact_id = 'artifact-join-1'"
        ).fetchone() == (None,)

def _consume_stored_authorization(tmp_path: Path):
    store, consume_kwargs = _stored_authorization(tmp_path)
    with s7._held_store(store.db_path) as (dir_fd, store_fd, connection):
        grant, _callback_result, committed_row = (
            s7.consume_for_execution_with_committed_row(
                connection,
                "artifact-join-1",
                **consume_kwargs,
            )
        )
    assert grant is not None
    assert committed_row is not None
    return grant, committed_row


def test_committed_row_proves_the_frozen_founder_self_modification_join(
    tmp_path: Path,
) -> None:
    grant, committed_row = _consume_stored_authorization(tmp_path)

    assert s7.committed_grant_row_proves_founder_self_modification(
        committed_row, grant
    )


@pytest.mark.parametrize("field", ROW_BACKED_GRANT_FIELDS)
def test_each_row_backed_grant_value_is_compared(
    tmp_path: Path, field: str
) -> None:
    grant, committed_row = _consume_stored_authorization(tmp_path)

    mutated = replace(
        committed_row,
        **{field: getattr(committed_row, field) + "-different"},
    )

    assert not s7.committed_grant_row_proves_founder_self_modification(
        mutated, grant
    )


class _EqualStringOfTheWrongType(str):
    pass


@pytest.mark.parametrize("field", ROW_BACKED_GRANT_FIELDS)
def test_each_row_backed_grant_type_is_compared_exactly(
    tmp_path: Path, field: str
) -> None:
    grant, committed_row = _consume_stored_authorization(tmp_path)
    original = getattr(committed_row, field)
    mutated = replace(
        committed_row,
        **{field: _EqualStringOfTheWrongType(original)},
    )
    assert getattr(mutated, field) == getattr(grant, field)

    assert not s7.committed_grant_row_proves_founder_self_modification(
        mutated, grant
    )


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("user_presence", True),
        ("user_presence", 2),
        ("user_presence", "1"),
        ("user_presence", 0),
        ("user_verification", True),
        ("user_verification", 2),
        ("user_verification", "1"),
        ("user_verification", 0),
    ),
)
def test_presence_and_verification_require_the_integer_one(
    tmp_path: Path, field: str, value: object
) -> None:
    grant, committed_row = _consume_stored_authorization(tmp_path)

    assert not s7.committed_grant_row_proves_founder_self_modification(
        replace(committed_row, **{field: value}), grant
    )


def _grant_with_contract_mutation(
    grant: s7.S7ExecutionGrant, field: str, value: str
) -> s7.S7ExecutionGrant:
    mutated = replace(grant, _mint_token=s7._EXECUTION_GRANT_TOKEN)
    object.__setattr__(mutated, field, value)
    return mutated


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("derived_work_class", "routine_custody"),
        ("ceremony_kind", "not_the_founder_ceremony"),
        ("auth_method", "service_local"),
        ("grant_source", "service_local"),
    ),
)
def test_founder_self_modification_constants_are_not_just_equality_joins(
    tmp_path: Path, field: str, value: str
) -> None:
    grant, committed_row = _consume_stored_authorization(tmp_path)
    mutated_grant = _grant_with_contract_mutation(grant, field, value)
    mutated_row = replace(committed_row, **{field: value})

    assert getattr(mutated_row, field) == getattr(mutated_grant, field)
    assert not s7.committed_grant_row_proves_founder_self_modification(
        mutated_row, mutated_grant
    )


def test_row_schema_and_consuming_request_binding_are_required(
    tmp_path: Path,
) -> None:
    grant, committed_row = _consume_stored_authorization(tmp_path)

    assert not s7.committed_grant_row_proves_founder_self_modification(
        replace(committed_row, schema_version="s7.authorization_artifact.v1"),
        grant,
    )
    assert not s7.committed_grant_row_proves_founder_self_modification(
        replace(committed_row, consumed_by_request_id="another-request"),
        grant,
    )


def test_grant_schema_is_the_derived_execution_grant_version(
    tmp_path: Path,
) -> None:
    grant, committed_row = _consume_stored_authorization(tmp_path)
    mutated_grant = _grant_with_contract_mutation(
        grant, "schema_version", "s7.execution_grant.v1"
    )

    assert not s7.committed_grant_row_proves_founder_self_modification(
        committed_row, mutated_grant
    )


@pytest.mark.parametrize(
    "changes",
    (
        {"created_at": "2026-08-07T12:00:01+00:00"},
        {"expires_at": "2026-08-07T12:00:00+00:00"},
        {"created_at": "2026-08-07T12:00:00Z"},
        {"expires_at": "2026-08-07T16:00:00Z"},
    ),
)
def test_chronology_requires_canonical_strings_and_order(
    tmp_path: Path, changes: dict[str, str]
) -> None:
    grant, committed_row = _consume_stored_authorization(tmp_path)

    assert not s7.committed_grant_row_proves_founder_self_modification(
        replace(committed_row, **changes), grant
    )


def test_consumed_at_cannot_bypass_canonical_parsing_through_grant_equality(
    tmp_path: Path,
) -> None:
    grant, committed_row = _consume_stored_authorization(tmp_path)
    noncanonical = "2026-08-07T12:00:00Z"
    mutated_grant = _grant_with_contract_mutation(
        grant, "consumed_at", noncanonical
    )
    mutated_row = replace(committed_row, consumed_at=noncanonical)

    assert mutated_row.consumed_at == mutated_grant.consumed_at
    assert not s7.committed_grant_row_proves_founder_self_modification(
        mutated_row, mutated_grant
    )


def test_post_commit_reader_uses_the_consuming_rw_only_after_commit(
    tmp_path: Path, monkeypatch
) -> None:
    store, consume_kwargs = _stored_authorization(tmp_path)
    observations: list[tuple[object, bool]] = []
    real_reader = s7._read_committed_grant_row_after_commit

    with s7._held_store(store.db_path) as (dir_fd, store_fd, connection):
        def recording_reader(committed_connection, artifact_id):
            read_connection = committed_connection.connection
            observations.append(
                (read_connection, read_connection.in_transaction)
            )
            return real_reader(committed_connection, artifact_id)

        monkeypatch.setattr(
            s7, "_read_committed_grant_row_after_commit", recording_reader
        )
        grant, _callback_result, committed_row = (
            s7.consume_for_execution_with_committed_row(
                connection,
                "artifact-join-1",
                **consume_kwargs,
            )
        )

        assert observations == [(connection, False)]

    assert grant is not None
    assert committed_row is not None


def test_previously_used_read_only_connection_is_refused_by_the_reader(
    tmp_path: Path,
) -> None:
    store, consume_kwargs = _stored_authorization(tmp_path)
    grant, _callback_result = store.consume_for_execution(
        "artifact-join-1", **consume_kwargs
    )
    assert grant is not None

    with closing(
        sqlite3.connect(f"file:{store.db_path}?mode=ro", uri=True)
    ) as inspection:
        inspection.execute("SELECT name FROM sqlite_master").fetchall()
        with pytest.raises(ValueError, match="consuming RW connection"):
            s7._read_committed_grant_row_after_commit(
                inspection, "artifact-join-1"
            )


def test_pathname_api_routes_through_the_connection_primitive_unchanged(
    tmp_path: Path, monkeypatch
) -> None:
    store, consume_kwargs = _stored_authorization(tmp_path)
    calls: list[tuple[bool, str]] = []
    real_consume = s7.consume_for_execution_on_connection

    def recording_consume(connection, artifact_id, **kwargs):
        calls.append((isinstance(connection, s7._S7HeldConnection), artifact_id))
        return real_consume(connection, artifact_id, **kwargs)

    monkeypatch.setattr(
        s7, "consume_for_execution_on_connection", recording_consume
    )
    result = store.consume_for_execution("artifact-join-1", **consume_kwargs)

    assert len(result) == 2
    grant, callback_result = result
    assert grant is not None
    assert callback_result is None
    assert calls == [(True, "artifact-join-1")]


def test_pathname_api_does_not_add_the_cutover_post_commit_read(
    tmp_path: Path, monkeypatch
) -> None:
    store, consume_kwargs = _stored_authorization(tmp_path)

    def forbidden_cutover_read(*_args, **_kwargs):
        raise AssertionError("legacy pathname consumption added a row reread")

    monkeypatch.setattr(
        s7, "_read_committed_grant_row_after_commit", forbidden_cutover_read
    )

    grant, callback_result = store.consume_for_execution(
        "artifact-join-1", **consume_kwargs
    )
    assert grant is not None
    assert callback_result is None


def test_future_dated_created_at_consumes_but_fails_the_post_commit_proof(
    tmp_path: Path,
) -> None:
    env, authority, params_hash, rendered = _chain()
    store = _migrated_store(tmp_path)
    future_created = replace(
        _artifact(env, authority, params_hash, rendered),
        created_at="2026-08-07T12:00:01+00:00",
    )
    store.put(future_created)

    with s7._held_store(store.db_path) as (dir_fd, store_fd, connection):
        grant, _callback_result, committed_row = (
            s7.consume_for_execution_with_committed_row(
                connection,
                "artifact-join-1",
                rendered=rendered,
                action_params_hash=params_hash,
                authority_context=authority,
                precondition_hash=env.precondition_hash,
                derived_work_class=env.derived_work_class,
                derived_aggregation_group=env.derived_aggregation_group,
                now=NOW,
            )
        )

    assert grant is not None, "the underlying consume gap must remain reproduced"
    assert committed_row is not None
    assert not s7.committed_grant_row_proves_founder_self_modification(
        committed_row, grant
    )
