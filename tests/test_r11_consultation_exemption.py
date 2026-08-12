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
import hashlib
import os
from types import SimpleNamespace

import pytest

from core.governance import operator_user_boundary as s7
from core.governance import s7_consultation_exemption as exemption_mod
from core.governance.s7_consultation_exemption import (
    R11_REASON_CODE,
    S7ConsultationExemption,
    consultation_exemption_admits,
)
from scripts import cuda_cutover, cuda_migration as cm


def _durable_selection(seed: str = "r11-fixture"):
    """Synthetic typed selection for unit joins, never tap evidence."""

    def digest(label: str) -> str:
        return hashlib.sha256(f"{label}:{seed}".encode()).hexdigest()

    return cuda_cutover.ValidatedCutoverSelection(
        completion_locator=f"completion-{seed}.json",
        completion=None,
        admission=None,
        receipt_ref=f"receipt-{seed}.json",
        receipt=SimpleNamespace(binding_sha256=digest("receipt-binding")),
        receipt_bytes=b"fixture",
        regenerated_receipt_bytes=b"fixture",
        receipt_file_sha256=digest("receipt-file"),
        authorization=SimpleNamespace(
            binding_sha256=digest("authorization-binding"),
            rollback_manifest_sha256=digest("rollback"),
            window_id=f"cutover-window-{seed}",
            issued_at="2026-08-12T12:00:00Z",
            expires_at="2026-08-12T16:00:00Z",
        ),
        authorization_file_sha256=digest("authorization-file"),
        bundle=SimpleNamespace(
            runtime_identity_doc=SimpleNamespace(
                file_sha256=digest("runtime-identity")
            )
        ),
        precondition_hash=digest("precondition"),
        operation_affected_refs={},
        affected_refs=("host:local",),
        _selection_token=cuda_cutover._VALIDATED_CUTOVER_SELECTION_TOKEN,
    )


_DURABLE_SELECTION = _durable_selection()
_CEREMONY_PREIMAGE_HASH = cuda_cutover._action_params_hash_from_durable_selection(
    _DURABLE_SELECTION
)


def _envelope_for_selection(selected, action: str = cm.CUTOVER_ACTION):
    return s7.build_work_request_envelope(
        request_id=selected.authorization.window_id,
        action=action,
        params=dict(cuda_cutover._cutover_action_preimage(selected)),
        claimed_work_class="self_modification",
        requesting_subsystem="cuda_cutover",
        closed_symptom_code="self_mod_requested",
        proposed_change_class="model_routing_change",
        why_self_fix_failed_class="not_self_fix",
        affected_refs=selected.affected_refs,
        content_exposure_risk="content_free",
        precondition_hash=selected.precondition_hash,
        created_at=selected.authorization.issued_at,
        expires_at=selected.authorization.expires_at,
        predicted_effect_class="behavior_change",
        rollback_path_class="revert_patch",
        maez_voice_consultation_id=None,
        free_text_ref_hash=None,
    )


def _envelope(action: str = cm.CUTOVER_ACTION):
    return _envelope_for_selection(_DURABLE_SELECTION, action)


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
        durable_cutover_selection=_DURABLE_SELECTION,
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
        durable_cutover_selection=_DURABLE_SELECTION,
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
        durable_cutover_selection=_DURABLE_SELECTION,
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
        durable_cutover_selection=_DURABLE_SELECTION,
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
        durable_cutover_selection=_DURABLE_SELECTION,
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
        durable_cutover_selection=_DURABLE_SELECTION,
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
        durable_cutover_selection=_DURABLE_SELECTION,
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
        durable_cutover_selection=_DURABLE_SELECTION,
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
        durable_cutover_selection=_DURABLE_SELECTION,
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
        durable_cutover_selection=_DURABLE_SELECTION,
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
        durable_cutover_selection=_DURABLE_SELECTION,
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
        durable_cutover_selection=_DURABLE_SELECTION,
        ledger_writes_enabled=False,
    )


def test_the_minter_refuses_a_non_cutover_action() -> None:
    with pytest.raises(exemption_mod.ExemptionMintRefused, match="cutover"):
        exemption_mod.mint_consultation_exemption(
            envelope=_envelope(action="edit_soul_section"),
            durable_cutover_selection=_DURABLE_SELECTION,
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
            durable_cutover_selection=_DURABLE_SELECTION,
            created_at="2026-08-12T12:00:00Z",
        )


def test_the_minter_refuses_after_birth(monkeypatch) -> None:
    monkeypatch.setenv("MAEZ_LEDGER_WRITES", "1")
    with pytest.raises(exemption_mod.ExemptionMintRefused, match="birth"):
        exemption_mod.mint_consultation_exemption(
            envelope=_envelope(),
            durable_cutover_selection=_DURABLE_SELECTION,
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
        durable_cutover_selection=_DURABLE_SELECTION,
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


def _render(
    envelope,
    exemption,
    action_params_hash=None,
    durable_cutover_selection=_DURABLE_SELECTION,
):
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
        durable_cutover_selection=durable_cutover_selection,
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


def _voice_fact_for(envelope):
    return s7.MaezVoiceConsultation(
        consultation_id="voice-r11-must-not-coexist",
        request_id=envelope.request_id,
        request_envelope_hash=s7.work_request_envelope_hash(envelope),
        producer="s7_voice_consultation_turn",
        source_ref_kind="s7_voice_turn",
        source_ref_hash="c" * 64,
        maez_voice_consulted=True,
        maez_objection_state="absent",
        maez_withdrew_request=False,
        unavailable_reason_code=None,
        created_at="2026-08-12T12:00:00Z",
    )


def test_rendering_refuses_exemption_and_voice_evidence_together() -> None:
    envelope = _envelope()
    with pytest.raises(ValueError, match="both"):
        s7.render_request_statement(
            envelope=envelope,
            surface="cockpit",
            origin="http://localhost:11437",
            action_params_hash=_CEREMONY_PREIMAGE_HASH,
            authority_context=_authority(),
            maez_voice_consultation=_voice_fact_for(envelope),
            nonce="n" * 64,
            expires_at="2026-08-12T16:00:00Z",
            rendered_at="2026-08-12T12:00:00Z",
            consultation_exemption=_exemption(envelope),
            durable_cutover_selection=_DURABLE_SELECTION,
        )


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
        durable_cutover_selection=_DURABLE_SELECTION,
        ledger_writes_enabled=False,
    )


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("request_id", "alternate-window"),
        ("precondition_hash", "f" * 64),
        ("derived_work_class", "routine_custody"),
        ("derived_aggregation_group", "s7agg_alternate"),
    ),
)
def test_artifact_authority_fields_must_match_the_durable_selection(
    field: str,
    value: str,
) -> None:
    """The artifact may not consistently cite a caller-invented authority field."""
    envelope = _envelope()
    assert not exemption_mod.exemption_admits_for_artifact(
        artifact=_artifact(envelope, **{field: value}),
        exemption=_exemption(envelope),
        durable_cutover_selection=_DURABLE_SELECTION,
        ledger_writes_enabled=False,
    )


def test_the_exemption_refuses_an_artifact_for_a_different_envelope() -> None:
    envelope = _envelope()
    other = replace(envelope, request_id="req-r11-other")
    assert not exemption_mod.exemption_admits_for_artifact(
        artifact=_artifact(other),
        exemption=_exemption(envelope),
        durable_cutover_selection=_DURABLE_SELECTION,
        ledger_writes_enabled=False,
    )


def test_the_exemption_refuses_an_artifact_for_a_different_action() -> None:
    envelope = _envelope()
    assert not exemption_mod.exemption_admits_for_artifact(
        artifact=_artifact(envelope, action="edit_soul_section"),
        exemption=_exemption(envelope),
        durable_cutover_selection=_DURABLE_SELECTION,
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
                durable_cutover_selection=_DURABLE_SELECTION,
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
            durable_cutover_selection=_DURABLE_SELECTION,
        )


def test_the_exempt_mint_still_goes_THROUGH_the_guarded_store() -> None:
    """It must never reach the raw authorization store, exemption or not."""
    from core.governance import s7_guarded_execution as guarded

    envelope = _envelope()
    seen = {}

    class _Store:
        def put_artifact_under_consultation_exemption(
            self,
            *,
            artifact,
            consultation_exemption,
            durable_cutover_selection,
        ):
            seen["artifact"] = artifact
            seen["exemption"] = consultation_exemption
            seen["selection"] = durable_cutover_selection

    class _RawStore:
        def put(self, _artifact):
            raise AssertionError("the raw store must never be reached")

    guarded.mint_authorization_artifact(
        artifact=_artifact(envelope),
        authorization_store=_RawStore(),
        guarded_store=_Store(),
        consultation_exemption=_exemption(envelope),
        durable_cutover_selection=_DURABLE_SELECTION,
    )
    assert seen["artifact"].action == cm.CUTOVER_ACTION


def test_r11_evidence_table_has_an_explicit_idempotent_provisioning_authority(
    tmp_path,
) -> None:
    """Opening and minting stay verification-only; setup owns creation."""
    import os
    import sqlite3

    from core.governance import s7_guarded_execution as guarded
    from tests.s7_store_fixture import bootstrap_with_authorization

    store = bootstrap_with_authorization(tmp_path / "r11-store")
    with sqlite3.connect(store.db_path) as connection:
        connection.execute(
            "ALTER TABLE s7_ceremony_challenges "
            "DROP COLUMN consultation_exemption_projection_hash"
        )
    # Ordinary store opening is not R11 setup authority.
    from core.governance.s7_webauthn_bootstrap import S7WebAuthnBootstrapStore

    S7WebAuthnBootstrapStore(store.root)
    with sqlite3.connect(store.db_path) as connection:
        assert "consultation_exemption_projection_hash" not in {
            row[1]
            for row in connection.execute(
                "PRAGMA table_info(s7_ceremony_challenges)"
            )
        }
    dir_fd = os.open(
        store.db_path.parent,
        os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
    )
    try:
        guarded._provision_r11_exemption_evidence_at(store_dir_fd=dir_fd)
        with sqlite3.connect(store.db_path) as conn:
            first = guarded._r11_exemption_evidence_contract(conn)
            challenge_columns = {
                row[1]: tuple(row)
                for row in conn.execute(
                    "PRAGMA table_info(s7_ceremony_challenges)"
                )
            }
        guarded._provision_r11_exemption_evidence_at(store_dir_fd=dir_fd)
        with sqlite3.connect(store.db_path) as conn:
            second = guarded._r11_exemption_evidence_contract(conn)
    finally:
        os.close(dir_fd)

    assert first == guarded._expected_r11_exemption_evidence_contract()
    assert second == first
    assert challenge_columns["consultation_exemption_projection_hash"][2:] == (
        "TEXT",
        0,
        None,
        0,
    )
    # The exact schema produced for an existing store is the exact schema
    # canonical cutover preflight expects, not merely a table with the right
    # names in a different order.
    with cuda_cutover.open_existing_authorization_store(
        db_path=store.db_path,
        expected_uid=os.getuid(),
    ):
        pass


def test_r11_artifact_rolls_back_when_its_evidence_row_cannot_persist(
    tmp_path,
) -> None:
    import sqlite3

    from core.governance import s7_guarded_execution as guarded
    from tests.s7_store_fixture import bootstrap_with_authorization

    store = bootstrap_with_authorization(tmp_path / "r11-atomic-store")
    dir_fd = os.open(
        store.db_path.parent,
        os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
    )
    try:
        guarded._provision_r11_exemption_evidence_at(store_dir_fd=dir_fd)
    finally:
        os.close(dir_fd)
    with sqlite3.connect(store.db_path) as connection:
        connection.execute(
            f"CREATE TRIGGER refuse_r11_evidence BEFORE INSERT ON "
            f"{guarded.R11_EXEMPTION_EVIDENCE_TABLE} "
            "BEGIN SELECT RAISE(ABORT, 'refuse_r11_evidence'); END"
        )
    authorization_store = s7.S7AuthorizationStore(store.db_path)
    guarded_store = guarded.S7GuardedStateStore(
        authorization_store=authorization_store,
    )
    envelope = _envelope()

    with pytest.raises(sqlite3.IntegrityError, match="refuse_r11_evidence"):
        guarded_store.put_artifact_under_consultation_exemption(
            artifact=_artifact(envelope),
            consultation_exemption=_exemption(envelope),
            durable_cutover_selection=_DURABLE_SELECTION,
        )

    with sqlite3.connect(store.db_path) as connection:
        assert connection.execute(
            "SELECT count(*) FROM s7_authorization_artifacts_v2"
        ).fetchone()[0] == 0
        assert connection.execute(
            f"SELECT count(*) FROM {guarded.R11_EXEMPTION_EVIDENCE_TABLE}"
        ).fetchone()[0] == 0


def _put_unreserved_voice_use(store, *, source_ref_hash: str):
    from core.governance import s7_guarded_execution as guarded

    voice_store = guarded.S7VoiceBundleUseStore(store.db_path)
    voice_store.put_unreserved(
        guarded.S7VoiceBundleUse.new_unreserved(
            request_id=_DURABLE_SELECTION.authorization.window_id,
            source_ref_hash=source_ref_hash,
            consultation_id="voice-r11-mutual-exclusion",
            used_at="2026-08-12T12:00:00Z",
        )
    )
    return voice_store


def test_voice_first_durably_blocks_r11_artifact_and_evidence_atomically(
    tmp_path,
) -> None:
    import sqlite3

    from core.governance import s7_guarded_execution as guarded
    from tests.s7_store_fixture import bootstrap_with_authorization

    store = bootstrap_with_authorization(tmp_path / "voice-first")
    dir_fd = os.open(
        store.db_path.parent,
        os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
    )
    try:
        guarded._provision_r11_exemption_evidence_at(store_dir_fd=dir_fd)
    finally:
        os.close(dir_fd)
    source_ref_hash = "7" * 64
    voice_store = _put_unreserved_voice_use(
        store,
        source_ref_hash=source_ref_hash,
    )
    envelope = _envelope()
    artifact = _artifact(envelope)
    voice_store.reserve_for_artifact(
        source_ref_hash=source_ref_hash,
        artifact_id=artifact.artifact_id,
        reservation_token_hash="8" * 64,
        reserved_at="2026-08-12T12:00:01Z",
    )

    guarded_store = guarded.S7GuardedStateStore(
        authorization_store=s7.S7AuthorizationStore(store.db_path),
        voice_bundle_use_store=voice_store,
    )
    with pytest.raises(ValueError, match="also carry voice-bundle"):
        guarded_store.put_artifact_under_consultation_exemption(
            artifact=artifact,
            consultation_exemption=_exemption(envelope),
            durable_cutover_selection=_DURABLE_SELECTION,
        )

    with sqlite3.connect(store.db_path) as connection:
        assert connection.execute(
            "SELECT count(*) FROM s7_authorization_artifacts_v2"
        ).fetchone()[0] == 0
        assert connection.execute(
            f"SELECT count(*) FROM {guarded.R11_EXEMPTION_EVIDENCE_TABLE}"
        ).fetchone()[0] == 0
        assert connection.execute(
            "SELECT artifact_id, reservation_state FROM s7_voice_bundle_uses "
            "WHERE source_ref_hash = ?",
            (source_ref_hash,),
        ).fetchone() == (artifact.artifact_id, "reserved")


def test_r11_first_durably_blocks_voice_reservation_without_mutation(
    tmp_path,
) -> None:
    store, artifact, _rendered, _exemption_record = (
        _persisted_r11_consumption_fixture(tmp_path / "r11-first")
    )
    source_ref_hash = "9" * 64
    voice_store = _put_unreserved_voice_use(
        store,
        source_ref_hash=source_ref_hash,
    )

    with pytest.raises(ValueError, match="R11 exemption evidence"):
        voice_store.reserve_for_artifact(
            source_ref_hash=source_ref_hash,
            artifact_id=artifact.artifact_id,
            reservation_token_hash="a" * 64,
            reserved_at="2026-08-12T12:00:01Z",
        )

    use = voice_store.get_for_source_ref(source_ref_hash)
    assert use is not None
    assert use.reservation_state == "unreserved"
    assert use.artifact_id is None


def _persisted_r11_consumption_fixture(tmp_path):
    import os

    from core.governance import s7_guarded_execution as guarded
    from tests.s7_store_fixture import bootstrap_with_authorization

    store = bootstrap_with_authorization(tmp_path)
    dir_fd = os.open(
        store.db_path.parent,
        os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
    )
    try:
        guarded._provision_r11_exemption_evidence_at(store_dir_fd=dir_fd)
    finally:
        os.close(dir_fd)
    envelope = _envelope()
    exemption = _exemption(envelope)
    rendered = _render(envelope, exemption)
    artifact = _artifact(
        envelope,
        rendered_text_hash=rendered.rendered_text_hash,
        authority_context_hash=rendered.authority_context_hash,
        nonce=rendered.nonce,
    )
    authorization_store = s7.S7AuthorizationStore(store.db_path)
    guarded.S7GuardedStateStore(
        authorization_store=authorization_store,
    ).put_artifact_under_consultation_exemption(
        artifact=artifact,
        consultation_exemption=exemption,
        durable_cutover_selection=_DURABLE_SELECTION,
    )
    return store, artifact, rendered, exemption


def test_consumption_rereads_and_revalidates_the_persisted_r11_projection(
    tmp_path,
) -> None:
    from core.governance import s7_guarded_execution as guarded

    store, artifact, rendered, exemption = _persisted_r11_consumption_fixture(
        tmp_path / "consume-positive"
    )
    with s7._held_store(store.db_path) as (_dir_fd, _store_fd, connection):
        grant, revalidated, committed = s7.consume_for_execution_with_committed_row(
            connection,
            artifact.artifact_id,
            rendered=rendered,
            action_params_hash=rendered.action_params_hash,
            authority_context=_authority(),
            precondition_hash=artifact.precondition_hash,
            derived_work_class=artifact.derived_work_class,
            derived_aggregation_group=artifact.derived_aggregation_group,
            now="2026-08-12T12:01:00Z",
            after_consume_before_commit=lambda fresh_grant: (
                guarded.revalidate_r11_exemption_for_consumption(
                    connection=connection,
                    grant=fresh_grant,
                    durable_cutover_selection=_DURABLE_SELECTION,
                )
            ),
        )

    assert grant is not None
    assert revalidated == exemption
    assert committed is not None
    assert committed.consumed_at == "2026-08-12T12:01:00+00:00"


@pytest.mark.parametrize(
    ("mutation", "expected"),
    (
        ("birth", "grounds no longer admit"),
        ("receipt", "grounds no longer admit"),
        ("projection", "projection is not canonical"),
        ("artifact_binding", "evidence binding is invalid"),
        ("voice_collision", "also carries voice-bundle"),
    ),
)
def test_consumption_rechecks_every_r11_ground_and_rolls_back(
    tmp_path,
    monkeypatch,
    mutation: str,
    expected: str,
) -> None:
    import sqlite3

    from core.governance import s7_guarded_execution as guarded

    store, artifact, rendered, _exemption_record = (
        _persisted_r11_consumption_fixture(tmp_path / mutation)
    )
    if mutation == "birth":
        monkeypatch.setattr(exemption_mod, "born_by_any_signal", lambda: True)
    elif mutation == "receipt":
        monkeypatch.setattr(
            exemption_mod,
            "R11_QUALITY_EVIDENCE_PATH",
            tmp_path / "receipt-disappeared.json",
        )
    elif mutation in {"projection", "artifact_binding"}:
        with sqlite3.connect(store.db_path) as connection:
            if mutation == "projection":
                connection.execute(
                    f"UPDATE {guarded.R11_EXEMPTION_EVIDENCE_TABLE} "
                    "SET projection_json = '{}' WHERE artifact_id = ?",
                    (artifact.artifact_id,),
                )
            else:
                connection.execute(
                    f"UPDATE {guarded.R11_EXEMPTION_EVIDENCE_TABLE} "
                    "SET artifact_binding_sha256 = ? WHERE artifact_id = ?",
                    ("f" * 64, artifact.artifact_id),
                )
    else:
        source_ref_hash = "b" * 64
        _put_unreserved_voice_use(store, source_ref_hash=source_ref_hash)
        with sqlite3.connect(store.db_path) as connection:
            connection.execute(
                "UPDATE s7_voice_bundle_uses SET artifact_id = ?, "
                "reservation_token_hash = ?, reservation_state = 'reserved', "
                "reserved_at = ? WHERE source_ref_hash = ?",
                (
                    artifact.artifact_id,
                    "c" * 64,
                    "2026-08-12T12:00:01Z",
                    source_ref_hash,
                ),
            )

    with s7._held_store(store.db_path) as (_dir_fd, _store_fd, connection):
        with pytest.raises(ValueError, match=expected):
            s7.consume_for_execution_with_committed_row(
                connection,
                artifact.artifact_id,
                rendered=rendered,
                action_params_hash=rendered.action_params_hash,
                authority_context=_authority(),
                precondition_hash=artifact.precondition_hash,
                derived_work_class=artifact.derived_work_class,
                derived_aggregation_group=artifact.derived_aggregation_group,
                now="2026-08-12T12:01:00Z",
                after_consume_before_commit=lambda fresh_grant: (
                    guarded.revalidate_r11_exemption_for_consumption(
                        connection=connection,
                        grant=fresh_grant,
                        durable_cutover_selection=_DURABLE_SELECTION,
                    )
                ),
            )

    with sqlite3.connect(store.db_path) as connection:
        assert connection.execute(
            "SELECT consumed_at FROM s7_authorization_artifacts_v2 "
            "WHERE artifact_id = ?",
            (artifact.artifact_id,),
        ).fetchone()[0] is None


# --------------------------------------------------------------------- #
#  The owner's tap: it proves WHAT the owner saw, not merely presence.   #
# --------------------------------------------------------------------- #


def _finish_input(monkeypatch, payload):
    import json as _json

    monkeypatch.setattr("builtins.input", lambda *_a: _json.dumps(payload))


def _tap(**kwargs):
    from scripts import cuda_cutover

    return cuda_cutover._read_owner_webauthn_finish(
        selected_credential_ref="cred-1", challenge_id="chal-1", **kwargs
    )


def test_the_tap_binds_to_the_exemption_projection_when_nothing_was_asked(
    monkeypatch,
) -> None:
    envelope = _envelope()
    projection_hash = s7.canonical_hash(_exemption(envelope).projection())
    _finish_input(
        monkeypatch,
        {
            "challenge_id": "chal-1",
            "credential_ref": "cred-1",
            "consultation_exemption_projection_hash": projection_hash,
            "authentication_response": {"id": "x"},
        },
    )
    request = _tap(exemption_projection_sha256=projection_hash)
    assert request["consultation_exemption_projection_hash"] == projection_hash


def test_the_tap_refuses_a_wrong_projection_hash(monkeypatch) -> None:
    from scripts import cuda_cutover

    _finish_input(
        monkeypatch,
        {
            "challenge_id": "chal-1",
            "credential_ref": "cred-1",
            "consultation_exemption_projection_hash": "9" * 64,
            "authentication_response": {"id": "x"},
        },
    )
    with pytest.raises(cuda_cutover.CutoverRefusal, match="owner_presence_unattested"):
        _tap(exemption_projection_sha256="8" * 64)


def test_the_tap_refuses_BOTH_bindings_or_neither(monkeypatch) -> None:
    from scripts import cuda_cutover

    with pytest.raises(cuda_cutover.CutoverRefusal, match="binding_ambiguous"):
        _tap(response_sha256="a" * 64, exemption_projection_sha256="b" * 64)
    with pytest.raises(cuda_cutover.CutoverRefusal, match="binding_ambiguous"):
        _tap()


def test_an_assertion_cannot_be_REPLAYED_across_ceremony_kinds(monkeypatch) -> None:
    """An assertion produced for a consultation ceremony must not satisfy an
    exemption ceremony, or the reverse: the other binding must be ABSENT."""
    from scripts import cuda_cutover

    projection_hash = "c" * 64
    _finish_input(
        monkeypatch,
        {
            "challenge_id": "chal-1",
            "credential_ref": "cred-1",
            "consultation_exemption_projection_hash": projection_hash,
            "maez_voice_raw_response_hash": "d" * 64,
            "authentication_response": {"id": "x"},
        },
    )
    with pytest.raises(cuda_cutover.CutoverRefusal, match="owner_presence_unattested"):
        _tap(exemption_projection_sha256=projection_hash)


def test_the_consultation_tap_binding_is_unchanged(monkeypatch) -> None:
    """Seam 2 must not alter the existing path while the live ask remains."""
    response_hash = "e" * 64
    _finish_input(
        monkeypatch,
        {
            "challenge_id": "chal-1",
            "credential_ref": "cred-1",
            "maez_voice_raw_response_hash": response_hash,
            "authentication_response": {"id": "x"},
        },
    )
    request = _tap(response_sha256=response_hash)
    assert request["maez_voice_raw_response_hash"] == response_hash


def test_none_is_not_an_exemption() -> None:
    envelope = _envelope()
    assert not consultation_exemption_admits(
        envelope=envelope,
        exemption=None,
        durable_cutover_selection=_DURABLE_SELECTION,
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
        durable_cutover_selection=_DURABLE_SELECTION,
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
        durable_cutover_selection=_DURABLE_SELECTION,
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
        durable_cutover_selection=_DURABLE_SELECTION,
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
        durable_cutover_selection=_durable_selection("different-preimage"),
        ledger_writes_enabled=False,
    )


def test_an_exemption_citing_the_wrong_preimage_refuses() -> None:
    envelope = _envelope()
    assert not consultation_exemption_admits(
        envelope=envelope,
        exemption=_exemption(envelope, action_params_hash="f" * 64),
        durable_cutover_selection=_DURABLE_SELECTION,
        ledger_writes_enabled=False,
    )


def test_the_boundary_derives_the_preimage_from_the_durable_selection(
    tmp_path, monkeypatch
) -> None:
    """A caller citing one forged hash consistently cannot override the
    eight fields independently reconstructed from the selected completion."""
    from scripts import cuda_cutover
    from tests.test_cutover_step2b_consumer import _seed_stage2_completion

    root, completion = _seed_stage2_completion(tmp_path, monkeypatch)
    selected = cuda_cutover._reconstruct_selected_cutover_at(
        root=root,
        expected_uid=root.stat().st_uid,
        completion_locator=completion.name,
        now="2026-08-03T20:31:03Z",
        boot_id="boot-1",
    )
    derived = s7.canonical_hash(dict(cuda_cutover._cutover_action_preimage(selected)))
    forged = "e" * 64
    assert forged != derived
    envelope = _envelope()

    assert not consultation_exemption_admits(
        envelope=envelope,
        exemption=_exemption(envelope, action_params_hash=forged),
        durable_cutover_selection=selected,
        ledger_writes_enabled=False,
    )


def test_the_minter_accepts_no_caller_supplied_preimage(
    tmp_path, monkeypatch
) -> None:
    from scripts import cuda_cutover
    from tests.test_cutover_step2b_consumer import _seed_stage2_completion

    root, completion = _seed_stage2_completion(tmp_path, monkeypatch)
    selected = cuda_cutover._reconstruct_selected_cutover_at(
        root=root,
        expected_uid=root.stat().st_uid,
        completion_locator=completion.name,
        now="2026-08-03T20:31:03Z",
        boot_id="boot-1",
    )
    expected = s7.canonical_hash(dict(cuda_cutover._cutover_action_preimage(selected)))

    minted = exemption_mod.mint_consultation_exemption(
        envelope=_envelope_for_selection(selected),
        durable_cutover_selection=selected,
        created_at="2026-08-12T12:00:00Z",
    )

    assert minted.action_params_hash == expected


def test_a_selection_lookalike_is_refused_by_exact_typing() -> None:
    """A content-identical object is not reconstructed durable evidence."""
    envelope = _envelope()
    real = _DURABLE_SELECTION
    lookalike = SimpleNamespace(
        authorization=real.authorization,
        authorization_file_sha256=real.authorization_file_sha256,
        receipt=real.receipt,
        receipt_file_sha256=real.receipt_file_sha256,
        bundle=real.bundle,
        _durable_selection_verified=True,
    )
    with pytest.raises(cuda_cutover.CutoverRefusal):
        cuda_cutover._action_params_hash_from_durable_selection(lookalike)
    assert not consultation_exemption_admits(
        envelope=envelope,
        exemption=_exemption(envelope),
        durable_cutover_selection=lookalike,
        ledger_writes_enabled=False,
    )


def test_durable_selection_cannot_be_constructed_without_reconstruction_token() -> None:
    real = _DURABLE_SELECTION
    with pytest.raises(ValueError, match="durable cutover reconstruction"):
        cuda_cutover.ValidatedCutoverSelection(
            completion_locator=real.completion_locator,
            completion=real.completion,
            admission=real.admission,
            receipt_ref=real.receipt_ref,
            receipt=real.receipt,
            receipt_bytes=real.receipt_bytes,
            regenerated_receipt_bytes=real.regenerated_receipt_bytes,
            receipt_file_sha256=real.receipt_file_sha256,
            authorization=real.authorization,
            authorization_file_sha256=real.authorization_file_sha256,
            bundle=real.bundle,
            precondition_hash=real.precondition_hash,
            operation_affected_refs=real.operation_affected_refs,
            affected_refs=real.affected_refs,
        )


def test_durable_selection_cannot_be_rebound_with_dataclasses_replace() -> None:
    with pytest.raises(ValueError, match="durable cutover reconstruction"):
        replace(_DURABLE_SELECTION, precondition_hash="f" * 64)


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("request_id", "different-window"),
        ("precondition_hash", "f" * 64),
        ("affected_refs", ("service:llama-server.service",)),
        ("created_at", "2026-08-12T12:00:01Z"),
        ("expires_at", "2026-08-12T15:59:59Z"),
    ),
)
def test_durable_selection_must_semantically_match_the_envelope(
    field: str,
    value,
) -> None:
    envelope = _envelope()
    mismatched = replace(envelope, **{field: value})
    assert not consultation_exemption_admits(
        envelope=mismatched,
        exemption=_exemption(mismatched),
        durable_cutover_selection=_DURABLE_SELECTION,
        ledger_writes_enabled=False,
    )
    with pytest.raises(exemption_mod.ExemptionMintRefused, match="durable selection"):
        exemption_mod.mint_consultation_exemption(
            envelope=mismatched,
            durable_cutover_selection=_DURABLE_SELECTION,
            created_at="2026-08-12T12:00:00Z",
        )
def test_a_missing_durable_selection_refuses() -> None:
    """Absent durable evidence is not permission."""
    envelope = _envelope()
    assert not consultation_exemption_admits(
        envelope=envelope,
        exemption=_exemption(envelope),
        durable_cutover_selection=None,
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
        "durable_cutover_selection": _DURABLE_SELECTION,
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


def test_the_direct_gate_refuses_exemption_and_voice_evidence_together() -> None:
    envelope = _envelope()
    result = _gate(
        envelope,
        _exemption(envelope),
        maez_voice_consultation=_voice_fact_for(envelope),
    )

    assert result.status_code == 409
    assert result.body["reason"] == "exemption_and_consultation_both_present"


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


def test_cutover_without_r11_refuses_before_any_consultation_authority() -> None:
    """R11 removes consultation as a lawful authority shape for THIS action.

    A typed, request-bound voice fact must not fall through to either the
    retired cutover admission or the generic bundle rail.  The same action's
    exemption positive control is ``test_the_gate_admits...`` above.
    """
    envelope = _envelope()
    consultation = s7.MaezVoiceConsultation(
        consultation_id="retired-cutover-consultation",
        request_id=envelope.request_id,
        request_envelope_hash=s7.work_request_envelope_hash(envelope),
        producer="s7_voice_consultation_turn",
        source_ref_kind="s7_voice_turn",
        source_ref_hash="c" * 64,
        maez_voice_consulted=True,
        maez_objection_state="not_determined",
        maez_withdrew_request=False,
        unavailable_reason_code=None,
        created_at=envelope.created_at,
    )

    result = _gate(
        envelope,
        None,
        maez_voice_consultation=consultation,
    )

    assert result.status_code == 409
    assert result.body["reason"] == "r11_consultation_exemption_required"


def test_the_retired_cutover_consultation_surface_is_deleted() -> None:
    """Deletion witness: no alternate caller can reconstruct the retired ask."""
    from core.governance import s7_webauthn_ceremony as ceremony
    from core.governance import operator_user_boundary
    from scripts import cuda_cutover

    retired_ceremony_symbols = (
        "_cutover_voice_evidence_revalidated_at_gate",
    )
    retired_cutover_symbols = (
        "ConsultationAttempt",
        "CutoverConsultationAsk",
        "CutoverConsultationResult",
        "produce_cutover_consultation",
        "revalidate_cutover_consultation_result",
        "_cutover_voice_bundle",
        "_persist_and_validate_cutover_voice_bundle",
        "_print_owner_cutover_gate",
    )

    assert all(not hasattr(ceremony, name) for name in retired_ceremony_symbols)
    assert not hasattr(
        operator_user_boundary,
        "build_cutover_work_request_envelope",
    )
    assert all(not hasattr(cuda_cutover, name) for name in retired_cutover_symbols)


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
