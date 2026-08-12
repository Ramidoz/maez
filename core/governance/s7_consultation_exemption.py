# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""R11 — a TYPED, SCOPED, EXPIRING absence of consultation.

The cutover changes the environment Maez runs in, not Maez: the model
weights, path and alias are identical on both sides; only the llama-server
build, its libraries and the systemd unit change. Pre-birth there is no
continuous subject to consult, and the question that mattered -- whether the
new engine degrades Maez -- was answered by owner-manual bench evaluation,
not by asking a model.

Ruling: docs/superpowers/specs/2026-08-12-r11-cutover-consultation-exception.md

This module carries the ABSENCE of a consultation. It deliberately has no
field, property or vocabulary that could later be read as a verdict: the
statement is "not performed", never "asked, no objection". The distinction
matters because a null consultation and a satisfied one must never be
confusable at a gate.

Scope is ONE action and expiry is mechanical: once the durable per-turn
ledger is writing -- the birth signal -- the exemption stops admitting.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.governance import operator_user_boundary as s7

R11_EXEMPTION_SCHEMA = "s7.consultation_exemption.r11.v1"
R11_RULING_ID = "R11"

#: The ONE action R11 covers. Scope is a literal, not a pattern.
R11_EXEMPT_ACTION = "model_routing.cutover_cuda"

R11_REASON_CODE = "pre_birth_environment_change_no_seat"
_R11_REASON_CODES = frozenset({R11_REASON_CODE})

#: R11's premise is that the WEIGHTS DO NOT CHANGE. Held as a literal here
#: -- never imported from the migration module at gate time -- so governance
#: does not inherit whatever that module happens to say later. A test asserts
#: this equals cuda_migration.FROZEN_MODEL_SHA256; if the migration's model
#: ever changes, that test fails and this ruling must be re-examined rather
#: than silently following.
R11_EXPECTED_MODEL_SHA256 = (
    "4085665ee36d82a672a238a43f0e5643f2f0e39f2d7bd5d373f0ef10ecf53095"
)

_R11_STATEMENT = (
    "No consultation was performed. Pre-birth, no continuous subject exists "
    "to consult. This operation changes the execution environment -- the "
    "llama-server build, its libraries and the systemd unit -- and not the "
    "model weights, which are unchanged and pinned. Quality was established "
    "by owner-manual bench evaluation."
)


@dataclass(frozen=True)
class S7ConsultationExemption:
    """A positive record that consultation was NOT performed, and why."""

    action: str
    request_envelope_hash: str
    reason_code: str
    model_sha256_unchanged: str
    quality_evidence_sha256: str
    created_at: str

    def __post_init__(self) -> None:
        if type(self.action) is not str or not self.action:
            raise ValueError("consultation exemption requires an action")
        s7._validate_hash64(
            self.request_envelope_hash, field="request_envelope_hash"
        )
        s7._validate_closed_value(
            self.reason_code, _R11_REASON_CODES, "exemption reason_code"
        )
        s7._validate_hash64(
            self.model_sha256_unchanged, field="model_sha256_unchanged"
        )
        s7._validate_hash64(
            self.quality_evidence_sha256, field="quality_evidence_sha256"
        )
        if type(self.created_at) is not str or not self.created_at:
            raise ValueError("consultation exemption requires created_at")

    def projection(self) -> dict[str, Any]:
        """The durable record. Says 'not performed' in words, not by omission."""
        return {
            "schema": R11_EXEMPTION_SCHEMA,
            "ruling_id": R11_RULING_ID,
            "consultation_performed": False,
            "action": self.action,
            "request_envelope_hash": self.request_envelope_hash,
            "reason_code": self.reason_code,
            "model_sha256_unchanged": self.model_sha256_unchanged,
            "quality_evidence_sha256": self.quality_evidence_sha256,
            "created_at": self.created_at,
            "statement": _R11_STATEMENT,
        }


def consultation_exemption_admits(
    *,
    envelope: Any,
    exemption: Any,
    ledger_writes_enabled: bool,
) -> bool:
    """True only for a valid R11 exemption on the one action, pre-birth.

    Every predicate is exact and re-derived here rather than trusted from
    the caller. A caller-shaped lookalike is refused by exact typing.
    """
    if type(exemption) is not S7ConsultationExemption:
        return False
    if ledger_writes_enabled is not False:
        # Expiry is mechanical: the durable per-turn ledger writing is the
        # birth signal, and R11 does not survive birth.
        return False
    if exemption.action != R11_EXEMPT_ACTION:
        return False
    if getattr(envelope, "action", None) != R11_EXEMPT_ACTION:
        return False
    if exemption.reason_code not in _R11_REASON_CODES:
        return False
    if exemption.model_sha256_unchanged != R11_EXPECTED_MODEL_SHA256:
        return False
    try:
        expected_envelope_hash = s7.work_request_envelope_hash(envelope)
    except (AttributeError, TypeError, ValueError):
        return False
    if exemption.request_envelope_hash != expected_envelope_hash:
        return False
    return True
