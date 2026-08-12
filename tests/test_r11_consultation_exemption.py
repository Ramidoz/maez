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
        "quality_evidence_sha256": "b" * 64,
        "created_at": "2026-08-12T12:00:00Z",
    }
    fields.update(overrides)
    return S7ConsultationExemption(**fields)


# --------------------------------------------------------------------- #
#  The positive control. Every negative below mutates THIS fixture.      #
# --------------------------------------------------------------------- #


def test_a_valid_cutover_exemption_admits_pre_birth() -> None:
    envelope = _envelope()
    assert consultation_exemption_admits(
        envelope=envelope,
        exemption=_exemption(envelope),
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
        quality_evidence_sha256="b" * 64,
        created_at="2026-08-12T12:00:00Z",
    )
    assert not consultation_exemption_admits(
        envelope=soul_envelope,
        exemption=forged,
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
        ledger_writes_enabled=False,
    )


# --------------------------------------------------------------------- #
#  Expiry: R11 dies at birth, mechanically.                              #
# --------------------------------------------------------------------- #


def test_the_exemption_refuses_once_the_ledger_is_writing() -> None:
    """'Expires at birth' is enforced, not merely promised. The durable
    per-turn ledger writing IS the birth signal."""
    envelope = _envelope()
    assert not consultation_exemption_admits(
        envelope=envelope,
        exemption=_exemption(envelope),
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
        quality_evidence_sha256 = "b" * 64
        created_at = "2026-08-12T12:00:00Z"

        def __init__(self, envelope_hash: str) -> None:
            self.request_envelope_hash = envelope_hash

    envelope = _envelope()
    assert not consultation_exemption_admits(
        envelope=envelope,
        exemption=LooksLikeAnExemption(s7.work_request_envelope_hash(envelope)),
        ledger_writes_enabled=False,
    )


def test_none_is_not_an_exemption() -> None:
    envelope = _envelope()
    assert not consultation_exemption_admits(
        envelope=envelope,
        exemption=None,
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
        quality_evidence_sha256="b" * 64,
        created_at="2026-08-12T12:00:00Z",
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
