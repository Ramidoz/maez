"""R11 — the cutover carries no consultation, and the absence is TYPED.

These tests exist to stop three specific things:

* the exemption being reachable by any action other than the cutover;
* the exemption being read, later, as "asked and no objection";
* the exemption outliving birth.

Every fixture here is synthetic. Nothing in this module is evidence that a
founder key was tapped or that Maez was consulted -- R11's whole content is
that Maez was NOT consulted for this operation.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from core.governance import operator_user_boundary as s7
from core.governance import s7_consultation_exemption as exemption_mod
from core.governance.s7_consultation_exemption import (
    R11_REASON_CODE,
    S7ConsultationExemption,
    consultation_exemption_admits,
)
from scripts import cuda_migration as cm


#: The real cutover preimage is EIGHT fields derived per ceremony from the
#: selected authorization, so no frozen constant can stand for it. Tests use
#: one representative ceremony value.
_CEREMONY_PREIMAGE_HASH = "7" * 64


def _envelope(action: str = cm.CUTOVER_ACTION):
    return s7.build_work_request_envelope(
        request_id="req-r11-fixture",
        action=action,
        params=dict(cm.CUTOVER_ACTION_PARAMS),
        claimed_work_class="self_modification",
        requesting_subsystem="cuda_cutover",
        closed_symptom_code="self_mod_requested",
        proposed_change_class="model_routing_change",
        why_self_fix_failed_class="not_self_fix",
        affected_refs=("host:local",),
        content_exposure_risk="content_free",
        precondition_hash="a" * 64,
        created_at="2026-08-12T12:00:00Z",
        expires_at="2026-08-12T16:00:00Z",
        predicted_effect_class="behavior_change",
        rollback_path_class="revert_patch",
        maez_voice_consultation_id=None,
        free_text_ref_hash=None,
    )


def _exemption(envelope, **overrides) -> S7ConsultationExemption:
    fields = {
        "action": cm.CUTOVER_ACTION,
        "request_envelope_hash": s7.work_request_envelope_hash(envelope),
        "reason_code": R11_REASON_CODE,
        "model_sha256_unchanged": exemption_mod.R11_EXPECTED_MODEL_SHA256,
        "quality_evidence_sha256": exemption_mod.R11_EXPECTED_QUALITY_EVIDENCE_SHA256,
        "action_params_hash": _CEREMONY_PREIMAGE_HASH,
        "created_at": "2026-08-12T12:00:00Z",
    }
    fields.update(overrides)
    return S7ConsultationExemption(
        **fields, _mint_token=exemption_mod._R11_MINT_TOKEN
    )


# --------------------------------------------------------------------- #
#  The positive control. Every negative below mutates THIS fixture.      #
# --------------------------------------------------------------------- #


def test_a_valid_cutover_exemption_admits_pre_birth() -> None:
    envelope = _envelope()
    assert consultation_exemption_admits(
        envelope=envelope,
        exemption=_exemption(envelope),
        action_params_hash=_CEREMONY_PREIMAGE_HASH,
        ledger_writes_enabled=False,
    )


# --------------------------------------------------------------------- #
#  Scope: no other action may reach the exemption.                       #
# --------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "action",
    (
        "edit_soul_section",
        "write_soul_note",
        "model_routing.cutover_cuda_but_not_really",
        "",
    ),
)
def test_no_other_action_can_use_the_exemption(action: str) -> None:
    """R11 is scoped to ONE action. This is the test that must fail if the
    scope check is removed."""
    envelope = _envelope(action=action) if action else _envelope()
    exemption = _exemption(envelope, action=action or "not-the-cutover")
    assert not consultation_exemption_admits(
        envelope=envelope,
        exemption=exemption,
        action_params_hash=_CEREMONY_PREIMAGE_HASH,
        ledger_writes_enabled=False,
    )


def test_cutover_exemption_cannot_cover_a_different_envelopes_action() -> None:
    """A well-formed cutover exemption presented alongside a soul-write."""
    soul_envelope = _envelope(action="edit_soul_section")
    cutover_envelope = _envelope()
    smuggled = _exemption(cutover_envelope)
    assert not consultation_exemption_admits(
        envelope=soul_envelope,
        exemption=smuggled,
        action_params_hash=_CEREMONY_PREIMAGE_HASH,
        ledger_writes_enabled=False,
    )


def test_an_exemption_claiming_cutover_but_BOUND_to_a_soul_write_refuses() -> None:
    """Found by mutation: removing the envelope-action check bit no test.

    The exemption says 'cutover' and its envelope hash matches the envelope
    presented -- but that envelope is a SOUL WRITE. Only the check on the
    ENVELOPE's own action stops this, so it needs its own witness.
    """
    soul_envelope = _envelope(action="edit_soul_section")
    forged = S7ConsultationExemption(
        action=cm.CUTOVER_ACTION,
        request_envelope_hash=s7.work_request_envelope_hash(soul_envelope),
        reason_code=R11_REASON_CODE,
        model_sha256_unchanged=exemption_mod.R11_EXPECTED_MODEL_SHA256,
        quality_evidence_sha256=exemption_mod.R11_EXPECTED_QUALITY_EVIDENCE_SHA256,
        action_params_hash=_CEREMONY_PREIMAGE_HASH,
        created_at="2026-08-12T12:00:00Z",
        _mint_token=exemption_mod._R11_MINT_TOKEN,
    )
    assert not consultation_exemption_admits(
        envelope=soul_envelope,
        exemption=forged,
        action_params_hash=_CEREMONY_PREIMAGE_HASH,
        ledger_writes_enabled=False,
    )


# --------------------------------------------------------------------- #
#  Binding: the exemption is bound to ONE envelope.                      #
# --------------------------------------------------------------------- #


def test_envelope_hash_must_match_the_actual_envelope() -> None:
    envelope = _envelope()
    other = replace(envelope, request_id="req-r11-other")
    assert not consultation_exemption_admits(
        envelope=other,
        exemption=_exemption(envelope),
        action_params_hash=_CEREMONY_PREIMAGE_HASH,
        ledger_writes_enabled=False,
    )


# --------------------------------------------------------------------- #
#  Grounding: the stated reasons must be the real ones.                  #
# --------------------------------------------------------------------- #


def test_a_changed_model_sha_refuses() -> None:
    """R11's premise is that the WEIGHTS DO NOT CHANGE. An exemption citing
    a different model is not this ruling and must not pass."""
    envelope = _envelope()
    assert not consultation_exemption_admits(
        envelope=envelope,
        exemption=_exemption(envelope, model_sha256_unchanged="c" * 64),
        action_params_hash=_CEREMONY_PREIMAGE_HASH,
        ledger_writes_enabled=False,
    )


def test_the_expected_model_sha_is_the_frozen_migration_constant() -> None:
    """The governance literal must track the migration's frozen model."""
    assert exemption_mod.R11_EXPECTED_MODEL_SHA256 == cm.FROZEN_MODEL_SHA256


def test_an_unknown_reason_code_cannot_even_be_constructed() -> None:
    envelope = _envelope()
    with pytest.raises(ValueError, match="reason_code"):
        _exemption(envelope, reason_code="because_we_felt_like_it")


def test_a_reason_code_mutated_after_construction_still_refuses() -> None:
    """Construction validates, but the gate must not RELY on construction:
    a frozen dataclass can still be forced open with object.__setattr__."""
    envelope = _envelope()
    mutated = _exemption(envelope)
    object.__setattr__(mutated, "reason_code", "because_we_felt_like_it")
    assert not consultation_exemption_admits(
        envelope=envelope,
        exemption=mutated,
        action_params_hash=_CEREMONY_PREIMAGE_HASH,
        ledger_writes_enabled=False,
    )


# --------------------------------------------------------------------- #
#  Expiry: R11 dies at birth, mechanically.                              #
# --------------------------------------------------------------------- #


def test_the_birth_signal_refuses_on_EITHER_signal(monkeypatch) -> None:
    """Codex finding: MAEZ_LEDGER_WRITES is a mutable service flag, while the
    durable meta.birth_event_turn_id anchor is the irreversible truth, and the
    repo recognises the two diverge BOTH ways. R11 must expire on either."""
    from core.memory import birth_phase

    monkeypatch.setenv("MAEZ_LEDGER_WRITES", "0")
    monkeypatch.setattr(birth_phase, "is_born", lambda *a, **k: True)
    assert exemption_mod.born_by_any_signal() is True

    monkeypatch.setenv("MAEZ_LEDGER_WRITES", "1")
    monkeypatch.setattr(birth_phase, "is_born", lambda *a, **k: False)
    assert exemption_mod.born_by_any_signal() is True


def test_an_unreadable_ledger_counts_as_born_not_as_unborn(monkeypatch) -> None:
    """is_born collapses 'unreadable' to False. That must not reopen R11:
    a ledger FILE that exists while reporting unborn is treated as born."""
    from pathlib import Path

    from core.memory import birth_phase

    monkeypatch.setenv("MAEZ_LEDGER_WRITES", "0")
    monkeypatch.setattr(birth_phase, "is_born", lambda *a, **k: False)
    monkeypatch.setattr(
        birth_phase, "default_ledger_path", lambda *a, **k: Path("/nonexistent/l.db")
    )
    assert exemption_mod.born_by_any_signal() is False

    class _Exists:
        def exists(self):
            return True

    monkeypatch.setattr(birth_phase, "default_ledger_path", lambda *a, **k: _Exists())
    assert exemption_mod.born_by_any_signal() is True


def test_the_exemption_refuses_once_the_ledger_is_writing() -> None:
    """'Expires at birth' is enforced, not merely promised. The durable
    per-turn ledger writing IS the birth signal."""
    envelope = _envelope()
    assert not consultation_exemption_admits(
        envelope=envelope,
        exemption=_exemption(envelope),
        action_params_hash=_CEREMONY_PREIMAGE_HASH,
        ledger_writes_enabled=True,
    )


# --------------------------------------------------------------------- #
#  Typing: absence must never be forgeable into consultation.            #
# --------------------------------------------------------------------- #


def test_a_lookalike_object_is_refused_by_exact_typing() -> None:
    class LooksLikeAnExemption:
        action = cm.CUTOVER_ACTION
        reason_code = R11_REASON_CODE
        model_sha256_unchanged = exemption_mod.R11_EXPECTED_MODEL_SHA256
        quality_evidence_sha256 = exemption_mod.R11_EXPECTED_QUALITY_EVIDENCE_SHA256
        action_params_hash = _CEREMONY_PREIMAGE_HASH
        created_at = "2026-08-12T12:00:00Z"

        def __init__(self, envelope_hash: str) -> None:
            self.request_envelope_hash = envelope_hash

    envelope = _envelope()
    assert not consultation_exemption_admits(
        envelope=envelope,
        exemption=LooksLikeAnExemption(s7.work_request_envelope_hash(envelope)),
        action_params_hash=_CEREMONY_PREIMAGE_HASH,
        ledger_writes_enabled=False,
    )


def test_an_envelope_LOOKALIKE_is_refused_by_exact_typing() -> None:
    """The TWELFTH guard, found by Codex. work_request_envelope_hash type-checks
    nothing, so a distinct dataclass carrying identical fields hashes the same
    and was admitted. Exact typing was promised for the exemption and never
    given to the envelope it is joined against."""
    import dataclasses

    real = _envelope()
    clone_cls = dataclasses.make_dataclass(
        "NotAWorkRequestEnvelope",
        [(f.name, f.type) for f in dataclasses.fields(real)],
        frozen=True,
    )
    clone = clone_cls(**{f.name: getattr(real, f.name) for f in dataclasses.fields(real)})

    assert type(clone) is not type(real)
    assert s7.work_request_envelope_hash(clone) == s7.work_request_envelope_hash(real)
    assert not consultation_exemption_admits(
        envelope=clone,
        exemption=_exemption(real),
        action_params_hash=_CEREMONY_PREIMAGE_HASH,
        ledger_writes_enabled=False,
    )


def test_a_symlinked_receipt_copy_is_refused(monkeypatch, tmp_path) -> None:
    """Byte-identical content at another location is not the receipt: the
    read is O_NOFOLLOW, so a symlink cannot stand in for it."""
    import shutil

    real = exemption_mod.R11_QUALITY_EVIDENCE_PATH
    if not real.exists():
        pytest.skip("owner-local bench receipt absent on this machine")
    copy = tmp_path / "copy.json"
    shutil.copyfile(real, copy)
    link = tmp_path / "link.json"
    link.symlink_to(copy)

    monkeypatch.setattr(exemption_mod, "R11_QUALITY_EVIDENCE_PATH", copy)
    assert exemption_mod._quality_receipt_still_matches() is True

    monkeypatch.setattr(exemption_mod, "R11_QUALITY_EVIDENCE_PATH", link)
    assert exemption_mod._quality_receipt_still_matches() is False


def test_a_non_regular_receipt_target_is_refused(monkeypatch, tmp_path) -> None:
    """A FIFO must not block authorization, and a directory is not a receipt."""
    import os

    fifo = tmp_path / "fifo.json"
    os.mkfifo(fifo)
    monkeypatch.setattr(exemption_mod, "R11_QUALITY_EVIDENCE_PATH", fifo)
    assert exemption_mod._quality_receipt_still_matches() is False

    monkeypatch.setattr(exemption_mod, "R11_QUALITY_EVIDENCE_PATH", tmp_path)
    assert exemption_mod._quality_receipt_still_matches() is False


def test_the_birth_probe_treats_a_broken_ledger_as_born(monkeypatch, tmp_path) -> None:
    """Codex finding: is_born collapses 'no meta table' and 'query failed'
    into the same False. A ledger that opens but is not a database must not
    read as unborn."""
    from core.memory import birth_phase

    monkeypatch.setenv("MAEZ_LEDGER_WRITES", "0")
    monkeypatch.setattr(birth_phase, "is_born", lambda *a, **k: False)

    junk = tmp_path / "ledger.db"
    junk.write_bytes(b"this is not a sqlite database at all")
    monkeypatch.setattr(birth_phase, "default_ledger_path", lambda *a, **k: junk)
    assert exemption_mod.born_by_any_signal() is True

    import sqlite3

    empty = tmp_path / "empty.db"
    sqlite3.connect(empty).close()
    monkeypatch.setattr(birth_phase, "default_ledger_path", lambda *a, **k: empty)
    assert exemption_mod.born_by_any_signal() is False


def test_a_ledger_carrying_the_birth_anchor_reads_as_born(monkeypatch, tmp_path) -> None:
    import sqlite3

    from core.memory import birth_phase

    monkeypatch.setenv("MAEZ_LEDGER_WRITES", "0")
    monkeypatch.setattr(birth_phase, "is_born", lambda *a, **k: False)
    born = tmp_path / "born.db"
    conn = sqlite3.connect(born)
    conn.execute("CREATE TABLE meta (key TEXT, value TEXT)")
    conn.execute("INSERT INTO meta VALUES ('birth_event_turn_id', 'turn-1')")
    conn.commit()
    conn.close()
    monkeypatch.setattr(birth_phase, "default_ledger_path", lambda *a, **k: born)
    assert exemption_mod.born_by_any_signal() is True


# --------------------------------------------------------------------- #
#  Provenance: one audited minting path, which CHECKS rather than trusts. #
# --------------------------------------------------------------------- #


def test_ordinary_construction_is_refused() -> None:
    """Codex finding: the public frozen dataclass accepted caller-provided
    authority fields. Only the minter may produce one now."""
    envelope = _envelope()
    with pytest.raises(ValueError, match="mint_consultation_exemption"):
        S7ConsultationExemption(
            action=cm.CUTOVER_ACTION,
            request_envelope_hash=s7.work_request_envelope_hash(envelope),
            reason_code=R11_REASON_CODE,
            model_sha256_unchanged=exemption_mod.R11_EXPECTED_MODEL_SHA256,
            quality_evidence_sha256=exemption_mod.R11_EXPECTED_QUALITY_EVIDENCE_SHA256,
            action_params_hash=_CEREMONY_PREIMAGE_HASH,
            created_at="2026-08-12T12:00:00Z",
        )


def test_dataclasses_replace_can_no_longer_rebind_an_exemption() -> None:
    """Codex's verified attack: replace() onto another cutover envelope was
    ADMITTED. An InitVar must be re-supplied, so replace() now refuses."""
    envelope = _envelope()
    minted = _exemption(envelope)
    other = replace(envelope, request_id="req-r11-other")
    # replace() re-runs __post_init__ with the InitVar defaulted to None, so
    # the mint check fires and names the only path that may produce one.
    with pytest.raises(ValueError, match="mint_consultation_exemption"):
        replace(minted, request_envelope_hash=s7.work_request_envelope_hash(other))


def test_the_minter_establishes_the_grounds_instead_of_trusting_them() -> None:
    envelope = _envelope()
    minted = exemption_mod.mint_consultation_exemption(
        envelope=envelope,
        action_params_hash=_CEREMONY_PREIMAGE_HASH,
        created_at="2026-08-12T12:00:00Z",
    )
    # The caller supplied neither the model sha nor the receipt hash.
    assert minted.model_sha256_unchanged == exemption_mod.R11_EXPECTED_MODEL_SHA256
    assert (
        minted.quality_evidence_sha256
        == exemption_mod.R11_EXPECTED_QUALITY_EVIDENCE_SHA256
    )
    assert consultation_exemption_admits(
        envelope=envelope,
        exemption=minted,
        action_params_hash=_CEREMONY_PREIMAGE_HASH,
        ledger_writes_enabled=False,
    )


def test_the_minter_refuses_a_non_cutover_action() -> None:
    with pytest.raises(exemption_mod.ExemptionMintRefused, match="cutover"):
        exemption_mod.mint_consultation_exemption(
            envelope=_envelope(action="edit_soul_section"),
            action_params_hash=_CEREMONY_PREIMAGE_HASH,
            created_at="2026-08-12T12:00:00Z",
        )


def test_the_minter_refuses_when_the_receipt_is_absent(monkeypatch, tmp_path) -> None:
    """A broken ground RAISES rather than returning falsy, so it cannot be
    mistaken for an ordinary denial."""
    monkeypatch.setattr(
        exemption_mod, "R11_QUALITY_EVIDENCE_PATH", tmp_path / "gone.json"
    )
    with pytest.raises(exemption_mod.ExemptionMintRefused, match="bench receipt"):
        exemption_mod.mint_consultation_exemption(
            envelope=_envelope(),
            action_params_hash=_CEREMONY_PREIMAGE_HASH,
            created_at="2026-08-12T12:00:00Z",
        )


def test_the_minter_refuses_after_birth(monkeypatch) -> None:
    monkeypatch.setenv("MAEZ_LEDGER_WRITES", "1")
    with pytest.raises(exemption_mod.ExemptionMintRefused, match="birth"):
        exemption_mod.mint_consultation_exemption(
            envelope=_envelope(),
            action_params_hash=_CEREMONY_PREIMAGE_HASH,
            created_at="2026-08-12T12:00:00Z",
        )


def test_a_stripped_token_flag_refuses_at_the_gate() -> None:
    """The flag is defence in depth, not a proof: a same-process actor can
    still strip it. Asserting it bites keeps the check honest."""
    envelope = _envelope()
    minted = _exemption(envelope)
    object.__setattr__(minted, "_token_verified", False)
    assert not consultation_exemption_admits(
        envelope=envelope,
        exemption=minted,
        action_params_hash=_CEREMONY_PREIMAGE_HASH,
        ledger_writes_enabled=False,
    )


# --------------------------------------------------------------------- #
#  The signed statement: what the owner reads before tapping.            #
# --------------------------------------------------------------------- #


def _authority():
    return s7.AuthorityContext(
        actor_id="founder",
        actor_handle_hmac="hmac:s7:founder:" + ("a" * 64),
        role_names=("bonded_user",),
        grant_source="founder_webauthn",
        allowed_scopes=("operator_health",),
        auth_method="founder_webauthn",
        surface="cockpit",
        credential_ref="cred-1",
        created_at="2026-08-12T12:00:00Z",
        expires_at="2026-08-12T16:00:00Z",
        verified=True,
    )


def _render(envelope, exemption, action_params_hash=None):
    return s7.render_request_statement(
        envelope=envelope,
        surface="cockpit",
        origin="http://localhost:11437",
        action_params_hash=action_params_hash or _CEREMONY_PREIMAGE_HASH,
        authority_context=_authority(),
        maez_voice_consultation=None,
        nonce="n" * 64,
        expires_at="2026-08-12T16:00:00Z",
        rendered_at="2026-08-12T12:00:00Z",
        consultation_exemption=exemption,
    )


def test_the_signed_statement_says_NOT_PERFORMED_not_yes() -> None:
    """Codex finding: the vocabulary was {"yes", "not required"}, so R11 left
    the ceremony only two options -- raise, or SIGN A LIE. The owner reads
    this line before tapping."""
    envelope = _envelope()
    rendered = _render(envelope, _exemption(envelope))

    assert "Maez consulted: no -- not performed under R11" in rendered.rendered_text
    assert "Maez consulted: yes" not in rendered.rendered_text
    assert "Maez objection present: not applicable" in rendered.rendered_text
    assert rendered.maez_voice_consultation_hash is None


def test_rendering_without_a_consultation_or_exemption_still_refuses() -> None:
    """The exemption is the ONLY thing that may stand in for a consultation
    on voice-seat work. Absent both, rendering must still raise."""
    with pytest.raises(ValueError, match="voice-seat work requires"):
        _render(_envelope(), None)


def test_rendering_refuses_an_exemption_that_does_not_admit() -> None:
    """A non-admitting exemption must not quietly render as 'not performed'."""
    envelope = _envelope()
    with pytest.raises(ValueError, match="does not admit"):
        _render(envelope, _exemption(envelope), action_params_hash="e" * 64)


def test_a_soul_write_cannot_render_as_not_performed() -> None:
    soul = _envelope(action="edit_soul_section")
    with pytest.raises(ValueError, match="does not admit"):
        _render(soul, _exemption(soul))


def test_the_consulted_vocabulary_is_exactly_three_states() -> None:
    """The literal is shared by renderer and validator so the visible line
    and the closed set cannot drift apart."""
    assert s7.MAEZ_CONSULTED_STATES == frozenset(
        {"yes", "not required", s7.MAEZ_CONSULTED_NOT_PERFORMED_R11}
    )
    assert s7.MAEZ_CONSULTED_NOT_PERFORMED_R11 == "no -- not performed under R11"


# --------------------------------------------------------------------- #
#  The mint: a SECOND lawful evidence shape, never a hole in the first.  #
# --------------------------------------------------------------------- #


def _artifact(envelope, **overrides):
    fields = {
        "artifact_id": "artifact-r11-1",
        "request_id": envelope.request_id,
        "request_envelope_hash": s7.work_request_envelope_hash(envelope),
        "rendered_text_hash": "d" * 64,
        "action_params_hash": _CEREMONY_PREIMAGE_HASH,
        "precondition_hash": envelope.precondition_hash,
        "authority_context_hash": "c" * 64,
        "derived_work_class": envelope.derived_work_class,
        "derived_aggregation_group": envelope.derived_aggregation_group,
        "nonce": "n" * 64,
        "credential_ref": "cred-1",
        "auth_method": "founder_webauthn",
        "grant_source": "founder_webauthn",
        "user_presence": True,
        "user_verification": True,
        "created_at": "2026-08-12T12:00:00Z",
        "expires_at": "2026-08-12T16:00:00Z",
        "consumed_at": None,
        "action": envelope.action,
    }
    fields.update(overrides)
    return s7.S7AuthorizationArtifact(**fields)


def test_the_exemption_admits_for_its_own_artifact() -> None:
    envelope = _envelope()
    assert exemption_mod.exemption_admits_for_artifact(
        artifact=_artifact(envelope),
        exemption=_exemption(envelope),
        ledger_writes_enabled=False,
    )


def test_the_exemption_refuses_an_artifact_for_a_different_envelope() -> None:
    envelope = _envelope()
    other = replace(envelope, request_id="req-r11-other")
    assert not exemption_mod.exemption_admits_for_artifact(
        artifact=_artifact(other),
        exemption=_exemption(envelope),
        ledger_writes_enabled=False,
    )


def test_the_exemption_refuses_an_artifact_for_a_different_action() -> None:
    envelope = _envelope()
    assert not exemption_mod.exemption_admits_for_artifact(
        artifact=_artifact(envelope, action="edit_soul_section"),
        exemption=_exemption(envelope),
        ledger_writes_enabled=False,
    )


def test_the_two_evidence_shapes_are_MUTUALLY_EXCLUSIVE() -> None:
    """The safety property that keeps R11 a second door rather than a hole in
    the first: an artifact arriving with both an exemption and voice-bundle
    evidence has no way to say which authorized it, so the mint refuses."""
    from core.governance import s7_guarded_execution as guarded

    envelope = _envelope()

    class _Store:
        def put_artifact_under_consultation_exemption(self, **_kwargs):
            raise AssertionError("must not reach the store")

        def put_artifact_with_bundle_reservation(self, **_kwargs):
            raise AssertionError("must not reach the store")

    for extra in (
        {"source_ref_hash": "a" * 64},
        {"reservation_token": "t" * 64},
    ):
        with pytest.raises(ValueError, match="exactly one must authorize"):
            guarded.mint_authorization_artifact(
                artifact=_artifact(envelope),
                authorization_store=None,
                guarded_store=_Store(),
                consultation_exemption=_exemption(envelope),
                **extra,
            )


def test_the_mint_refuses_an_exemption_that_does_not_admit() -> None:
    from core.governance import s7_guarded_execution as guarded

    envelope = _envelope()
    other = replace(envelope, request_id="req-r11-other")

    class _Store:
        def put_artifact_under_consultation_exemption(self, **_kwargs):
            raise AssertionError("must not reach the store")

    with pytest.raises(ValueError, match="does not admit"):
        guarded.mint_authorization_artifact(
            artifact=_artifact(other),
            authorization_store=None,
            guarded_store=_Store(),
            consultation_exemption=_exemption(envelope),
        )


def test_the_exempt_mint_still_goes_THROUGH_the_guarded_store() -> None:
    """It must never reach the raw authorization store, exemption or not."""
    from core.governance import s7_guarded_execution as guarded

    envelope = _envelope()
    seen = {}

    class _Store:
        def put_artifact_under_consultation_exemption(self, *, artifact, consultation_exemption):
            seen["artifact"] = artifact
            seen["exemption"] = consultation_exemption

    class _RawStore:
        def put(self, _artifact):
            raise AssertionError("the raw store must never be reached")

    guarded.mint_authorization_artifact(
        artifact=_artifact(envelope),
        authorization_store=_RawStore(),
        guarded_store=_Store(),
        consultation_exemption=_exemption(envelope),
    )
    assert seen["artifact"].action == cm.CUTOVER_ACTION


def test_none_is_not_an_exemption() -> None:
    envelope = _envelope()
    assert not consultation_exemption_admits(
        envelope=envelope,
        exemption=None,
        action_params_hash=_CEREMONY_PREIMAGE_HASH,
        ledger_writes_enabled=False,
    )


def test_the_exemption_carries_no_objection_state_field() -> None:
    """The type must have no field a later reader could mistake for a
    consultation verdict. R11 says NOT ASKED, never 'asked, no objection'."""
    field_names = set(S7ConsultationExemption.__dataclass_fields__)
    for forbidden in (
        "maez_objection_state",
        "maez_voice_consulted",
        "objection_state",
        "consultation_id",
        "source_ref_hash",
        "raw_maez_text",
    ):
        assert forbidden not in field_names

    projection = S7ConsultationExemption.__dict__.get("projection")
    assert projection is not None, "the exemption must project itself explicitly"


# --------------------------------------------------------------------- #
#  A1: the bench receipt is the whole justification, so BIND it.          #
# --------------------------------------------------------------------- #


def test_the_expected_receipt_hash_is_the_real_receipt_on_this_machine() -> None:
    """The literal must track the owner's actual bench receipt.

    The receipt is gitignored and owner-local, so this cannot run where it
    is absent -- skipping is honest; asserting a pass would not be.
    """
    import hashlib

    path = exemption_mod.R11_QUALITY_EVIDENCE_PATH
    if not path.exists():
        pytest.skip("owner-local bench receipt absent on this machine")
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    assert actual == exemption_mod.R11_EXPECTED_QUALITY_EVIDENCE_SHA256


def test_an_invented_quality_hash_refuses() -> None:
    """THE EIGHTH GUARD. Before this, the positive fixture passed with
    'b' * 64 -- R11's entire justification was unbound to any evidence."""
    envelope = _envelope()
    assert not consultation_exemption_admits(
        envelope=envelope,
        exemption=_exemption(envelope, quality_evidence_sha256="b" * 64),
        action_params_hash=_CEREMONY_PREIMAGE_HASH,
        ledger_writes_enabled=False,
    )


def test_a_missing_receipt_file_refuses(monkeypatch, tmp_path) -> None:
    """No receipt, no exemption. The ruling rests on evidence that must
    still be there at admit time, not merely on a matching constant."""
    envelope = _envelope()
    monkeypatch.setattr(
        exemption_mod, "R11_QUALITY_EVIDENCE_PATH", tmp_path / "absent.json"
    )
    assert not consultation_exemption_admits(
        envelope=envelope,
        exemption=_exemption(envelope),
        action_params_hash=_CEREMONY_PREIMAGE_HASH,
        ledger_writes_enabled=False,
    )


def test_a_tampered_receipt_file_refuses(monkeypatch, tmp_path) -> None:
    """The receipt is re-read and byte-compared, so altering it after the
    fact cannot leave a matching constant standing in for real evidence."""
    envelope = _envelope()
    tampered = tmp_path / "quality-evidence.json"
    tampered.write_text('{"fields": {"quality_failure_count": 99}}')
    monkeypatch.setattr(exemption_mod, "R11_QUALITY_EVIDENCE_PATH", tampered)
    assert not consultation_exemption_admits(
        envelope=envelope,
        exemption=_exemption(envelope),
        action_params_hash=_CEREMONY_PREIMAGE_HASH,
        ledger_writes_enabled=False,
    )


# --------------------------------------------------------------------- #
#  A1: the envelope does not retain params, so bind the preimage too.    #
# --------------------------------------------------------------------- #


def test_no_frozen_constant_may_stand_for_the_action_preimage() -> None:
    """A1 first bound this to a frozen literal derived from the one-field
    CUTOVER_ACTION_PARAMS. The real preimage is EIGHT fields built per
    ceremony from the selected authorization, so a constant either refuses
    every honest operation or admits while a different preimage executes."""
    assert not hasattr(exemption_mod, "R11_EXPECTED_ACTION_PARAMS_HASH")
    assert exemption_mod.R11_ACTION_PREIMAGE_IS_PER_CEREMONY is True

    import inspect

    from scripts import cuda_cutover

    source = inspect.getsource(cuda_cutover._cutover_action_preimage)
    for field in (
        "authorization_binding_sha256",
        "authorization_file_sha256",
        "stage_two_receipt_binding_sha256",
        "target_runtime_identity_sha256",
        "window_id",
    ):
        assert field in source
    assert s7.canonical_hash(dict(cm.CUTOVER_ACTION_PARAMS)) != _CEREMONY_PREIMAGE_HASH


def test_changed_action_params_refuse_even_with_a_matching_envelope() -> None:
    """Codex finding: WorkRequestEnvelope discards params after derivation,
    so a changed preimage can yield the same envelope hash. The exemption
    must bind the preimage independently of the envelope."""
    envelope = _envelope()
    assert not consultation_exemption_admits(
        envelope=envelope,
        exemption=_exemption(envelope),
        action_params_hash="e" * 64,
        ledger_writes_enabled=False,
    )


def test_an_exemption_citing_the_wrong_preimage_refuses() -> None:
    envelope = _envelope()
    assert not consultation_exemption_admits(
        envelope=envelope,
        exemption=_exemption(envelope, action_params_hash="f" * 64),
        action_params_hash=_CEREMONY_PREIMAGE_HASH,
        ledger_writes_enabled=False,
    )


def test_KNOWN_GAP_a_consistently_cited_preimage_is_admitted_today() -> None:
    """TRIPWIRE for the residual caller-assertion gap, stated not hidden.

    The gate cannot yet derive the ceremony preimage itself, so it can only
    check that the exemption agrees with the value it was handed. A caller
    controlling both sides is therefore not caught. Removing the frozen
    constant was still correct -- it bound the WRONG preimage -- but this is
    what remains open until production wiring lets the gate derive it from
    the durable selection.

    Asserts TODAY'S behaviour on purpose: when wiring closes the gap this
    will start refusing, this test will fail, and whoever closes it must come
    here and record that it is closed.
    """
    envelope = _envelope()
    changed = "e" * 64
    assert consultation_exemption_admits(
        envelope=envelope,
        exemption=_exemption(envelope, action_params_hash=changed),
        action_params_hash=changed,
        ledger_writes_enabled=False,
    ), "gap closed -- update this tripwire and the R11 doc"


def test_a_str_subclass_preimage_is_refused_by_exact_typing() -> None:
    """Found by mutation: equality alone accepted a lookalike type, the same
    defect exact typing already refuses for the exemption object itself."""
    envelope = _envelope()

    class _EqualButWrongType(str):
        pass

    sneaky = _EqualButWrongType(_CEREMONY_PREIMAGE_HASH)
    assert sneaky == _CEREMONY_PREIMAGE_HASH
    assert not consultation_exemption_admits(
        envelope=envelope,
        exemption=_exemption(envelope),
        action_params_hash=sneaky,
        ledger_writes_enabled=False,
    )


def test_a_missing_operation_preimage_refuses() -> None:
    """Absent is not permission: no preimage supplied means no admission."""
    envelope = _envelope()
    assert not consultation_exemption_admits(
        envelope=envelope,
        exemption=_exemption(envelope),
        action_params_hash=None,
        ledger_writes_enabled=False,
    )


# --------------------------------------------------------------------- #
#  The live gate. The predicate above is not the authority surface.       #
# --------------------------------------------------------------------- #


def _gate(envelope, exemption, **overrides):
    from core.governance import s7_webauthn_ceremony as ceremony

    kwargs = {
        "envelope": envelope,
        "maez_voice_consultation": None,
        "refusal_history_store": None,
        "rendered_text_hash": "d" * 64,
        "requester_ref": "founder-local-browser",
        "now": "2026-08-12T12:00:00Z",
        "consultation_exemption": exemption,
        "action_params_hash": _CEREMONY_PREIMAGE_HASH,
    }
    kwargs.update(overrides)
    return ceremony.authorization_voice_seat_recheck(**kwargs)


def test_the_gate_admits_a_valid_exemption_without_any_consultation() -> None:
    """No MaezVoiceConsultation object exists at all under R11 -- building one
    would assert an ask that never happened."""
    envelope = _envelope()
    result = _gate(envelope, _exemption(envelope))

    assert result.status_code == 200
    assert result.body["ok"] is True
    assert result.body["consultation_performed"] is False
    assert result.body["consultation_exemption_ruling"] == "R11"


def test_the_gate_never_reports_an_objection_state_for_an_exemption() -> None:
    """The fail-open lesson: 'absent' and 'not_determined' both describe an
    ask that happened. Neither may be reachable through the exemption."""
    envelope = _envelope()
    body = _gate(envelope, _exemption(envelope)).body

    assert "maez_objection_state" not in body
    flattened = " ".join(str(v).lower() for v in body.values())
    assert "absent" not in flattened
    assert "not_determined" not in flattened


def test_an_invalid_exemption_BLOCKS_and_never_falls_through() -> None:
    """An exemption that is present but does not admit must block here. If it
    fell through to the consultation path, a different rule could rescue it."""
    envelope = _envelope()
    result = _gate(envelope, _exemption(envelope, model_sha256_unchanged="c" * 64))

    assert result.status_code != 200
    assert result.body["ok"] is False


def test_a_soul_write_cannot_be_exempted_at_the_gate() -> None:
    soul_envelope = _envelope(action="edit_soul_section")
    forged = S7ConsultationExemption(
        action=cm.CUTOVER_ACTION,
        request_envelope_hash=s7.work_request_envelope_hash(soul_envelope),
        reason_code=R11_REASON_CODE,
        model_sha256_unchanged=exemption_mod.R11_EXPECTED_MODEL_SHA256,
        quality_evidence_sha256=exemption_mod.R11_EXPECTED_QUALITY_EVIDENCE_SHA256,
        action_params_hash=_CEREMONY_PREIMAGE_HASH,
        created_at="2026-08-12T12:00:00Z",
        _mint_token=exemption_mod._R11_MINT_TOKEN,
    )
    result = _gate(soul_envelope, forged)

    assert result.status_code != 200
    assert result.body["ok"] is False


def test_the_gate_is_untouched_when_no_exemption_is_supplied() -> None:
    """Every other path must behave exactly as before. With no exemption and
    no consultation, the pre-existing missing-voice-fact block still fires."""
    envelope = _envelope(action="edit_soul_section")
    result = _gate(envelope, None)

    assert result.status_code != 200
    assert result.body.get("reason") == "missing_or_mismatched_voice_fact"


def test_the_projection_says_not_performed_in_words() -> None:
    envelope = _envelope()
    projected = _exemption(envelope).projection()
    assert projected["consultation_performed"] is False
    assert projected["ruling_id"] == "R11"
    assert projected["schema"] == exemption_mod.R11_EXEMPTION_SCHEMA
    assert "not" in projected["statement"].lower()
    # No verdict vocabulary may appear anywhere in the projection.
    flattened = " ".join(str(v).lower() for v in projected.values())
    assert "no objection" not in flattened
    assert "absent" not in flattened
