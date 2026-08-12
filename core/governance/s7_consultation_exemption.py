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
from pathlib import Path
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

#: R11's justification is the owner's bench evaluation, so the exemption must
#: BIND that evidence rather than merely cite a well-formed hash. Before this
#: the field was validated as 64 hex characters and never read, and the
#: passing fixture used an invented value -- the ruling rested on nothing.
#: The receipt is owner-local and gitignored, so it is re-read at admit time
#: and its absence REFUSES: no receipt, no exemption.
R11_QUALITY_EVIDENCE_PATH = (
    Path(__file__).resolve().parents[2]
    / "local"
    / "cuda_migration_bench"
    / "receipts"
    / "quality-evidence.json"
)
R11_EXPECTED_QUALITY_EVIDENCE_SHA256 = (
    "dba239959389b199632726715b0b81cca11b39a6cf0006e7fc8ffd27e135f327"
)
#: The receipt is a small JSON document; anything larger is not it.
_R11_RECEIPT_MAX_BYTES = 64 * 1024

#: `WorkRequestEnvelope` derives from params and then DISCARDS them, so a
#: changed preimage can yield the same envelope hash. The exemption binds the
#: preimage independently, and the gate joins it to the operation's own.
#:
#: A1 FIRST BOUND THIS TO A FROZEN LITERAL, AND THAT WAS WRONG. The real
#: cutover preimage (`_cutover_action_preimage`) has EIGHT fields and is
#: PER-CEREMONY: it binds the authorization document's binding hash, its
#: window id, the stage-2 receipt hashes and the target runtime identity.
#: A constant cannot equal it, so the frozen check would either refuse every
#: honest operation or -- worse -- admit while a different preimage was
#: rendered and executed. That is a field named for a binding that binds
#: nothing, the exact defect this arc exists to close, committed by the lane
#: closing it. The constant is deleted rather than corrected.
#:
#: What remains here is the JOIN only: the exemption must carry the same
#: preimage hash the ceremony derived from its durable selection. The gate
#: cannot yet derive that hash itself, so this one value is a caller
#: assertion, and closing it belongs with the production wiring, where the
#: gate will hold the selection. Until then R11 is dormant and no live path
#: relies on it.
R11_ACTION_PREIMAGE_IS_PER_CEREMONY = True

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
    action_params_hash: str
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
        s7._validate_hash64(self.action_params_hash, field="action_params_hash")
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
            "action_params_hash": self.action_params_hash,
            "created_at": self.created_at,
            "statement": _R11_STATEMENT,
        }


def born_by_any_signal() -> bool:
    """True if EITHER birth signal says born. Refusing is the safe direction.

    The durable `meta.birth_event_turn_id` anchor is the canonical,
    irreversible birth truth; `MAEZ_LEDGER_WRITES` is a mutable service flag.
    The repository recognises that the two diverge in both directions -- on
    before birth, off after birth -- so R11 expires on the OR of them, and an
    unreadable ledger counts as born rather than reopening the exemption.
    """
    from core.ledger.writes_flag import ledger_writes_enabled

    if ledger_writes_enabled():
        return True
    try:
        from core.memory import birth_phase
    except Exception:
        return True
    try:
        if birth_phase.is_born():
            return True
        path = birth_phase.default_ledger_path()
    except Exception:
        return True
    # `is_born` collapses "unreadable" and "readable but unborn" to the same
    # False. Those are different facts, and only the first is dangerous.
    # Measured during gestation: the ledger file EXISTS and has no `meta`
    # table at all, so neither file presence nor a missing table indicates
    # birth -- both are ordinary pre-birth shapes that is_born reads
    # correctly. The one gap is a database that will not OPEN, where the
    # anchor could exist unseen; that is treated as born, because reopening
    # R11 on a broken read is the dangerous direction.
    try:
        if not path.exists():
            return False
    except Exception:
        return True
    import sqlite3

    # `is_born` collapses "no meta table" (an ordinary gestation shape) and
    # "the query failed" (which could hide a real anchor) into the same False.
    # Re-run the query here so the two can be told apart: a readable ledger
    # whose meta table is simply absent stays unborn, while any other failure
    # counts as born.
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    except Exception:
        return True
    try:
        names = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        if "meta" not in names:
            return False
        row = conn.execute(
            "SELECT value FROM meta WHERE key = 'birth_event_turn_id'"
        ).fetchone()
    except Exception:
        return True
    finally:
        try:
            conn.close()
        except Exception:
            pass
    return bool(row and str(row[0] or "").strip())


def _quality_receipt_still_matches() -> bool:
    """Re-read the owner's bench receipt and byte-compare it at admit time.

    A constant alone would only stop an exemption citing a DIFFERENT bench
    run; re-reading also proves the evidence still exists and is unaltered.
    Absent or unreadable REFUSES -- R11 rests on this receipt, so its absence
    is not permission.
    """
    import hashlib
    import os
    import stat as stat_module

    fd = -1
    try:
        # O_NOFOLLOW: a symlink to byte-identical content elsewhere must not
        # stand in for the receipt. O_NONBLOCK: a FIFO/FUSE target must not
        # block authorization indefinitely. Size-bounded: an unbounded target
        # must not raise MemoryError out of a predicate.
        fd = os.open(
            R11_QUALITY_EVIDENCE_PATH,
            os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC,
        )
        info = os.fstat(fd)
        # Defence in depth, redundant BY MEASUREMENT rather than by argument:
        # mutation shows removing this still refuses, because a FIFO opened
        # non-blocking yields empty bytes that fail the digest and a directory
        # raises on read. Kept because it refuses for the right reason and at
        # the right layer, but it is not what carries the protection.
        if not stat_module.S_ISREG(info.st_mode):
            return False
        if info.st_size > _R11_RECEIPT_MAX_BYTES:
            return False
        payload = os.read(fd, _R11_RECEIPT_MAX_BYTES)
        if len(payload) != info.st_size:
            return False
    except (OSError, ValueError):
        return False
    finally:
        if fd >= 0:
            try:
                os.close(fd)
            except OSError:
                pass
    return hashlib.sha256(payload).hexdigest() == R11_EXPECTED_QUALITY_EVIDENCE_SHA256


def consultation_exemption_admits(
    *,
    envelope: Any,
    exemption: Any,
    action_params_hash: str | None,
    ledger_writes_enabled: bool,
) -> bool:
    """True only for a valid R11 exemption on the one action, pre-birth.

    Every predicate is exact and re-derived here rather than trusted from
    the caller. A caller-shaped lookalike is refused by exact typing.
    """
    if type(exemption) is not S7ConsultationExemption:
        return False
    # The TWELFTH guard. `work_request_envelope_hash` type-checks nothing, so
    # a distinct dataclass carrying identical fields hashes identically and
    # was admitted. Exact typing was promised for the exemption and not given
    # to the envelope it is joined against.
    if type(envelope) is not s7.WorkRequestEnvelope:
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
    # The bench receipt is the justification, joined three ways: the exemption
    # must cite the frozen receipt, the operation's own preimage must be the
    # frozen cutover preimage, and the exemption must cite that same preimage.
    if exemption.quality_evidence_sha256 != R11_EXPECTED_QUALITY_EVIDENCE_SHA256:
        return False
    if type(action_params_hash) is not str:
        return False
    try:
        s7._validate_hash64(action_params_hash, field="action_params_hash")
    except ValueError:
        return False
    if exemption.action_params_hash != action_params_hash:
        return False
    if not _quality_receipt_still_matches():
        return False
    try:
        expected_envelope_hash = s7.work_request_envelope_hash(envelope)
    except (AttributeError, TypeError, ValueError):
        return False
    if exemption.request_envelope_hash != expected_envelope_hash:
        return False
    return True
