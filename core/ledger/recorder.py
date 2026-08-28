# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""The A3 recorder seam — one record contract for every mouth.

Twenty-second council round (2026-08-27, folded 3-0): attempt custody;
classify durably if possible; make loss loud; egress regardless. This
module is the seam every interceptor-path closure records through, and
the ONLY production write path A3 adds — the closures call the two
public functions below; nothing here restructures interceptor order
(ADR 0035: guard -> admit user_message -> interceptors -> record ->
transport).

The TYPED, IDENTITY-BEARING result
----------------------------------
``try_write_turn`` returns ``None`` for dormancy, dead-letter AND total
loss, and the pause lane returns ``None`` for successful durable
custody. The seam returns :class:`RecordResult` instead:

  DORMANT                      flag unset; ZERO residue (no spool file,
                               no dead-letter, no db touch).
  COMMITTED(turn_id)           the row is in the chain; thread children
                               by ``parent_turn_id``.
  CUSTODY(submission_id,       the payload is durably held for a later
          producer)            commit by the drainer; thread children
                               by ``parent_submission_id``. This is the
                               twenty-second round's fold onto the
                               twentieth round's four states — custody
                               is not committed (drain may refuse), not
                               dead-lettered (nothing failed), not lost
                               (the bytes are on disk, fsynced).
  DEAD_LETTERED(attempt_id,    the write failed or was refused; the
                category)      FULL payload is in the dead-letter
                               sidecar under ``attempt_id``.
  LOST(attempt_id)             even the dead-letter append failed to
                               COMPLETE durably; named at CRITICAL.
                               Partial bytes may exist (an append can
                               land and its directory fsync still
                               fail — Codex walk B3); nothing durably
                               DISCOVERABLE is guaranteed, so a
                               non-owner process's LOST cannot reach
                               the daemon cockpit and that residual is
                               named in the round, not papered over.

Routing (inside the seam, the full shipped precedent)
-----------------------------------------------------
spool custody when: the process is not the ledger owner, OR commits are
paused, OR the parent edge exists only as a submission id (a child must
not owner-direct-write before its parent drains). Otherwise the
owner-direct classified write. The spool producer is the REAL
conversation surface — never the organ (``event_origin`` carries organ
identity), never ``owner_daemon`` for interceptor speech (one
conversation, one mailbox), never blank.

Latency posture (stated, ruled): one synchronous recording attempt; no
recorder-added retries or sleeps; never raises on the record path;
NOT hard latency-bounded (the direct writer waits up to its
busy_timeout under contention; custody fsyncs without an application
timeout). The S4 closure judges its latency exception against this
baseline.

Model-generated speech is NAMED OUT: ``persist_model_reply``
(core/ledger/model_reply_persistence.py) is the shipped model-speech
recorder — the clarified dialog branch and every other generation goes
there with honest provenance. This seam records only the two ruled
canned shapes, and a generic turn_kind passthrough is deliberately
absent (a second flag in drag).

The type cannot express "don't write": there is no no-op recorder, the
production default is a module singleton identity-pinned by
tests/test_ledger_recorder_seam.py, and ``recorder=None`` raises.
Dormancy is a RESULT, not a different recorder.
"""

from __future__ import annotations

import enum
import logging
import os
import threading
import uuid
from dataclasses import dataclass
from pathlib import Path

__all__ = [
    "RecordState",
    "RecordResult",
    "ProductionRecorder",
    "RehearsalRecorder",
    "PRODUCTION",
    "OrganProvenance",
    "ProducedReply",
    "record_owner_message",
    "record_organ_event",
    "record_approval_decision",
    "recorder_status",
]

_LOGGER = logging.getLogger("core.ledger.recorder")


class OrganProvenance(enum.Enum):
    """A CLOSED set of named shapes for what an organ row's bytes ARE.

    Twenty-third round, folded 3-0 over a recorded dissent: the producer
    declares a NAMED SHAPE and the seam binds the taint set, so no taint
    list ever crosses a closure. The dissent — that a fourth vocabulary
    beside TAINT_LABEL_ORDER / KNOWN_ORIGINS / PROVENANCE_VALUES is the
    one-column-two-namespaces sin — was ANSWERED, not overruled, by the
    constraint pinned here: **this enum introduces no LABEL.** Every
    shape maps onto labels that already exist, and a test asserts it.

    Why a shape and not a taint list: a caller-supplied set restores
    exactly the free choice the twenty-second round called "a second
    flag in drag". Why not a ``str`` subclass carrying provenance: DEAD
    BY EXECUTION — it survives object-identical to the closure and then
    evaporates at the first of five string transformations in
    platform_base before transport. Provenance on a type that any
    ``.strip()`` silently downgrades is a trapdoor.
    """

    #: Text the organ wrote itself, with nothing foreign embedded.
    CANNED = "canned"
    #: Text embedding LIVE WEB CONTENT — result titles, snippets, URLs.
    #: The owner's echoed query is NOT a provenance component: owner
    #: provenance rides the PARENT EDGE (owner ruling, 2026-08-28), so
    #: the frozen taint map is not widened and this set is one the
    #: writer already admits for system_event.
    WEB_RESULTS = "web_results"


#: The ONE auditable place shape becomes taint. Never a label this
#: vocabulary did not already have.
_PROVENANCE_TAINTS: dict[OrganProvenance, tuple[str, ...]] = {
    OrganProvenance.CANNED: ("self_generated",),
    OrganProvenance.WEB_RESULTS: (
        "self_generated",
        "tool_output",
        "internet_derived",
    ),
}


@dataclass(frozen=True)
class ProducedReply:
    """What a producer returns: the exact bytes AND their shape.

    The producer is the only thing that knows which branch spoke, so it
    is the only thing that can declare provenance honestly. Both fields
    are required; empty text is refused at construction, because a
    producer that returns an empty reply should return ``None`` (no
    intent) rather than a reply nobody can record.
    """

    text: str
    provenance: OrganProvenance

    def __post_init__(self) -> None:
        if not isinstance(self.text, str) or not self.text.strip():
            raise ValueError(
                "ProducedReply.text must be a non-empty string — a "
                "producer with nothing to say returns None"
            )
        if not isinstance(self.provenance, OrganProvenance):
            raise TypeError(
                "ProducedReply.provenance must be an OrganProvenance "
                f"member, got {self.provenance!r}"
            )


class RecordState(enum.Enum):
    DORMANT = "dormant"
    COMMITTED = "committed"
    CUSTODY = "custody"
    DEAD_LETTERED = "dead_lettered"
    LOST = "lost"


@dataclass(frozen=True)
class RecordResult:
    """The identity-bearing outcome of one recording attempt.

    Structurally unable to state contradictions (Codex boundary walk,
    2026-08-27): each state requires exactly the identity it earns and
    refuses the identities it did not — a COMMITTED without a turn, a
    CUSTODY claiming a turn, a LOST with no attempt identity are all
    construction errors, because parent routing TRUSTS these fields.
    """

    state: RecordState
    turn_id: str | None = None
    submission_id: str | None = None
    producer: str | None = None
    attempt_id: str | None = None
    category: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.state, RecordState):
            raise TypeError(
                f"state must be a RecordState, got {self.state!r}"
            )
        required, allowed = _RESULT_SHAPE[self.state]
        fields = {
            "turn_id": self.turn_id,
            "submission_id": self.submission_id,
            "producer": self.producer,
            "attempt_id": self.attempt_id,
            "category": self.category,
        }
        for name in required:
            if fields[name] is None:
                raise ValueError(
                    f"{self.state.name} requires {name} — a result "
                    "claiming an outcome without its identity is a lie "
                    "parent routing would trust"
                )
        for name, value in fields.items():
            if value is not None and name not in allowed:
                raise ValueError(
                    f"{self.state.name} must not carry {name} — a "
                    "contradictory identity is a lie parent routing "
                    "would trust"
                )


#: Per-state identity contract: (required, allowed).
_RESULT_SHAPE: dict[RecordState, tuple[tuple[str, ...], tuple[str, ...]]] = {
    RecordState.DORMANT: ((), ()),
    RecordState.COMMITTED: (("turn_id",), ("turn_id",)),
    RecordState.CUSTODY: (
        ("submission_id", "producer"),
        ("submission_id", "producer"),
    ),
    RecordState.DEAD_LETTERED: (
        ("attempt_id", "category"),
        ("attempt_id", "category"),
    ),
    RecordState.LOST: (("attempt_id",), ("attempt_id",)),
}


def _canonical_db_path() -> str:
    """The daemon's own derivation (maez_daemon.py:196), resolved per
    call so the seam and the body can never disagree about the target."""
    override = os.environ.get("MAEZ_LEDGER_DB_PATH")
    if override:
        return override
    from core.infra import paths as _paths

    return str(_paths.memory_dir() / "ledger.db")


def _blank(value) -> bool:
    return not isinstance(value, str) or not value.strip()


class UnmappableProvenance(ValueError):
    """Raised when neither a ruled fixed taint set nor a mappable
    producer-declared shape was supplied. Never a taint label —
    unknown provenance is an epistemic failure state."""


def _resolve_taints(
    taint_labels: list[str] | None,
    provenance: "OrganProvenance | None",
) -> list[str]:
    """Shape -> taint, in the ONE place the mapping lives.

    Called BEFORE any taint is bound into write kwargs, so a refusal
    dead-letters a payload carrying RAW kwargs and NO guessed labels —
    replay preserves kwargs verbatim, and a guess in a sidecar could be
    laundered into the chain later.
    """
    if (taint_labels is None) == (provenance is None):
        raise UnmappableProvenance(
            "recorder: exactly one of taint_labels (a ruled fixed set) "
            "or provenance (a producer-declared shape) must be supplied"
        )
    if provenance is None:
        return list(taint_labels or [])
    # Type FIRST: ``x in dict`` raises TypeError on an unhashable, which
    # would escape the fail-closed belt entirely (Codex walk M4).
    if not isinstance(provenance, OrganProvenance):
        raise UnmappableProvenance(
            "recorder: provenance must be an OrganProvenance member, "
            f"got {type(provenance).__name__} — refusing admission "
            "rather than guessing a taint set"
        )
    if provenance not in _PROVENANCE_TAINTS:
        raise UnmappableProvenance(
            f"recorder: unmappable organ provenance {provenance!r} — "
            "refusing admission rather than guessing a taint set"
        )
    return list(_PROVENANCE_TAINTS[provenance])


class ProductionRecorder:
    """The classified production record path.

    Composes the shipped primitives none of which is the recorder alone:
    ``owner_commit`` classifies but neither dead-letters nor checks the
    pause flag; ``owner_write_turn`` dead-letters but swallows identity;
    ``spool.enqueue`` is durable custody that never reads the writes
    flag. One synchronous attempt, classified; never raises.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.counts: dict[str, int] = {s.value: 0 for s in RecordState}

    # ------------------------------------------------------------- util

    def _count(self, result: RecordResult) -> RecordResult:
        with self._lock:
            self.counts[result.state.value] += 1
        return result

    def _reset_counts_for_tests(self) -> None:
        with self._lock:
            for key in self.counts:
                self.counts[key] = 0

    # ----------------------------------------------------------- record

    def _record(
        self,
        turn_kind: str,
        raw_text: str | None,
        *,
        surface: str,
        kwargs: dict,
        taint_labels: list[str] | None = None,
        provenance: "OrganProvenance | None" = None,
        parent: RecordResult | None = None,
    ) -> RecordResult:
        from core.ledger.writes_flag import (
            ledger_commits_paused,
            ledger_writes_enabled,
        )

        # The flag gates BEFORE any residue: spool.enqueue never reads
        # it, and an ungated seam would grow a pre-birth pile that
        # drains as life on flip.
        if not ledger_writes_enabled():
            return self._count(RecordResult(state=RecordState.DORMANT))

        db_path = _canonical_db_path()
        attempt_id = uuid.uuid4().hex

        # Seam misuse with a payload is never silent and never fatal to
        # the reply: dead-letter as the writer's own refusal category.
        if _blank(surface):
            return self._count(self._dead_letter(
                db_path, turn_kind, raw_text, kwargs, attempt_id,
                ValueError("recorder: surface must be a non-empty string"),
            ))
        if "event_origin" in kwargs and _blank(kwargs["event_origin"]):
            return self._count(self._dead_letter(
                db_path, turn_kind, raw_text, kwargs, attempt_id,
                ValueError(
                    "recorder: event_origin must be a non-empty string "
                    "on an organ event (the seam is fail-closed; the "
                    "writer stays permitted-not-required)"
                ),
            ))

        # PROVENANCE REFUSAL — deliberately HERE, beside the other
        # early checks and BEFORE taint binding, so the dead-lettered
        # payload carries RAW kwargs. Unreachable on a green path:
        # ``provenance`` is a required parameter with no default, so a
        # forgotten wiring is a BUILD failure. This is the belt.
        try:
            taint_labels = _resolve_taints(taint_labels, provenance)
        except UnmappableProvenance as exc:
            return self._count(self._dead_letter(
                db_path, turn_kind, raw_text, kwargs, attempt_id, exc,
            ))

        from core.ledger import owner as _owner

        # Parent edge, from the typed result of the prior record call.
        parent_turn_id: str | None = None
        parent_submission_id: str | None = None
        if parent is not None:
            if parent.state is RecordState.COMMITTED:
                parent_turn_id = parent.turn_id
            elif parent.state is RecordState.CUSTODY:
                parent_submission_id = parent.submission_id
            # DEAD_LETTERED / LOST / DORMANT: record-without-join,
            # never refuse (ruled by name).

        spool_lane = (
            not _owner.this_process_is_owner()
            or ledger_commits_paused()
            or parent_submission_id is not None
        )

        write_kwargs = dict(kwargs)
        write_kwargs["surface"] = surface
        write_kwargs["taint_labels"] = list(taint_labels)
        write_kwargs.setdefault("privacy_access", "public")

        if spool_lane:
            return self._count(self._record_custody(
                db_path, turn_kind, raw_text, surface, write_kwargs,
                attempt_id, parent_turn_id, parent_submission_id,
            ))
        return self._count(self._record_owner_direct(
            db_path, turn_kind, raw_text, write_kwargs, attempt_id,
            parent_turn_id,
        ))

    # ------------------------------------------------------------ lanes

    def _record_custody(
        self,
        db_path: str,
        turn_kind: str,
        raw_text: str | None,
        surface: str,
        write_kwargs: dict,
        attempt_id: str,
        parent_turn_id: str | None,
        parent_submission_id: str | None,
    ) -> RecordResult:
        from core.ledger import owner as _owner
        from core.ledger import spool as _spool

        if parent_turn_id is not None and parent_submission_id is None:
            # A COMMITTED parent on the custody lane (pause): translate
            # the turn edge into the spool's native grammar via the
            # committed row's own identity. None -> unparented, honest.
            parent_submission_id = _owner._paused_parent_submission_id(
                db_path, parent_turn_id
            )
            if parent_submission_id is None:
                _LOGGER.warning(
                    "recorder custody: parent turn %s has no submission "
                    "identity; recording unparented (record-without-join)",
                    parent_turn_id,
                )
        # Writes-off WINS (Codex walk B2): re-check the brake at the last
        # instant before residue. A flip DURING the enqueue syscall itself
        # remains a named race — one check per side of the call is the
        # honest boundary; the seam adds no locks over a process-global
        # env flag.
        from core.ledger.writes_flag import ledger_writes_enabled

        if not ledger_writes_enabled():
            return RecordResult(state=RecordState.DORMANT)
        try:
            sid = _spool.enqueue(
                _spool.default_spool_root(db_path),
                producer=surface,
                turn_kind=turn_kind,
                raw_text=raw_text,
                kwargs=write_kwargs,
                parent_submission_id=parent_submission_id,
            )
        except Exception as e:  # noqa: BLE001 — classified, never silent
            return self._dead_letter(
                db_path, turn_kind, raw_text, write_kwargs, attempt_id, e,
                parent_submission_id=parent_submission_id,
            )
        return RecordResult(
            state=RecordState.CUSTODY,
            submission_id=sid,
            producer=surface,
        )

    def _record_owner_direct(
        self,
        db_path: str,
        turn_kind: str,
        raw_text: str | None,
        write_kwargs: dict,
        attempt_id: str,
        parent_turn_id: str | None,
    ) -> RecordResult:
        from core.ledger import owner as _owner
        from core.ledger.writes_flag import ledger_writes_enabled

        if parent_turn_id is not None:
            write_kwargs["parent_turn_id"] = parent_turn_id
        # Pre-minted identity ON the committed row: the same key names
        # this attempt whether it commits or dead-letters.
        write_kwargs.setdefault("submission_id", attempt_id)
        outcome, detail = _owner.owner_commit(
            db_path, turn_kind, raw_text, **write_kwargs
        )
        if outcome == "acked":
            return RecordResult(state=RecordState.COMMITTED, turn_id=detail)
        if outcome == "failed" and not ledger_writes_enabled():
            # The brake flipped mid-call: flag OFF stops recording
            # including custody (frozen brake semantic) — dormant, not
            # a failure.
            return RecordResult(state=RecordState.DORMANT)
        return self._dead_letter(
            db_path, turn_kind, raw_text, write_kwargs, attempt_id,
            detail if isinstance(detail, BaseException)
            else RuntimeError(str(detail)),
        )

    # ------------------------------------------------------- dead letter

    def _dead_letter(
        self,
        db_path: str,
        turn_kind: str,
        raw_text: str | None,
        kwargs: dict,
        attempt_id: str,
        error: BaseException,
        *,
        parent_submission_id: str | None = None,
    ) -> RecordResult:
        from core.ledger.writer import _REFUSAL_ERRORS, _dead_letter

        category = "refused" if isinstance(error, _REFUSAL_ERRORS) else "failed"
        try:
            path = _dead_letter(
                db_path, turn_kind, raw_text, kwargs, error,
                "recorder", attempt_id,
                parent_submission_id=parent_submission_id,
            )
            _LOGGER.error(
                "recorder %s (kind=%r): %s — payload dead-lettered to %s",
                category, turn_kind, error, path,
            )
            return RecordResult(
                state=RecordState.DEAD_LETTERED,
                attempt_id=attempt_id,
                category=category,
            )
        except Exception as dl_error:
            _LOGGER.critical(
                "recorder (kind=%r): %s — AND the dead-letter append "
                "failed (%s); the payload is LOST",
                turn_kind, error, dl_error,
            )
            return RecordResult(
                state=RecordState.LOST, attempt_id=attempt_id
            )


class RehearsalRecorder:
    """The injectable rehearsal lane — the ONLY way A3 is rehearsed.

    Wraps a rehearsal-mode :class:`LedgerWriter` over a disposable
    sidecar (logs/rehearsal/x6_*/ledger.db shape) and stamps
    ``lifecycle_stage='rehearsal'`` on every row, which the production
    writer refuses by construction. Rows carry REAL surface labels
    (nineteenth round constraint 2). The witness process arms the flag
    for ITSELF — womb-life practise, not birth. Loud by design: a
    rehearsal failure raises; a witness must never mistake a broken
    lane for a green one.
    """

    def __init__(self, db_path: str, *, rehearsal_root: str | Path) -> None:
        from core.ledger.writer import LedgerWriter

        self._writer = LedgerWriter(
            db_path, rehearsal_mode=True, rehearsal_root=rehearsal_root
        )

    def _record(
        self,
        turn_kind: str,
        raw_text: str | None,
        *,
        surface: str,
        kwargs: dict,
        taint_labels: list[str] | None = None,
        provenance: "OrganProvenance | None" = None,
        parent: RecordResult | None = None,
    ) -> RecordResult:
        # Loud by design (see the class docstring): the rehearsal lane
        # RAISES rather than dead-lettering, so a witness can never
        # mistake an unmappable provenance for a green rehearsal.
        taint_labels = _resolve_taints(taint_labels, provenance)
        write_kwargs = dict(kwargs)
        write_kwargs["surface"] = surface
        write_kwargs["taint_labels"] = list(taint_labels)
        write_kwargs.setdefault("privacy_access", "public")
        write_kwargs["lifecycle_stage"] = "rehearsal"
        if parent is not None and parent.state is RecordState.COMMITTED:
            write_kwargs["parent_turn_id"] = parent.turn_id
        turn_id = self._writer.write_turn(turn_kind, raw_text, **write_kwargs)
        if turn_id is None:
            raise RuntimeError(
                "rehearsal recorder wrote nothing — arm MAEZ_LEDGER_WRITES "
                "in the witness process (womb-life practise, not birth)"
            )
        return RecordResult(state=RecordState.COMMITTED, turn_id=turn_id)

    def close(self) -> None:
        self._writer.close()


#: The production default. Identity-pinned by the seam tests: both
#: public functions default to THIS object, and the module constructs
#: exactly one.
PRODUCTION = ProductionRecorder()


def _require_recorder(recorder) -> None:
    if recorder is None:
        raise TypeError(
            "the recorder type cannot express 'don't write' — pass a "
            "real recorder (the production default, or an injected "
            "rehearsal recorder); None is a second flag in drag"
        )


def record_owner_message(
    *,
    surface: str,
    raw_text: str,
    raw_surface: str | None = None,
    parent: RecordResult | None = None,
    recorder=PRODUCTION,
) -> RecordResult:
    """Record the owner's message IN FULL as ``user_message``.

    Ruling 1 (eighteenth round): exact bytes, ``{owner_utterance}``.
    ``event_origin`` is structurally absent — the owner is not an organ
    and the writer forbids the field on this kind.
    """
    _require_recorder(recorder)
    kwargs: dict = {}
    if raw_surface is not None:
        kwargs["raw_surface"] = raw_surface
    return recorder._record(
        "user_message",
        raw_text,
        surface=surface,
        taint_labels=["owner_utterance"],
        kwargs=kwargs,
        parent=parent,
    )


def record_organ_event(
    *,
    surface: str,
    event_origin: str,
    raw_text: str,
    provenance: OrganProvenance,
    raw_surface: str | None = None,
    parent: RecordResult | None = None,
    pending_card_id: int | None = None,
    self_mod_dialog_id: int | None = None,
    audit_verdict: dict | None = None,
    evidence_envelope: dict | None = None,
    recorder=PRODUCTION,
) -> RecordResult:
    """Record canned organ output as ``system_event`` with EXACT bytes.

    ``event_origin`` is REQUIRED non-empty here — the seam is the first
    caller that knows it is recording organ output; the writer stays
    permitted-not-required for genesis/reconcile. Named optionals only,
    all writer-legal on ``system_event``; the TEXT dialog id rides as
    typed reconciliation debt inside ``audit_verdict``, never as a
    type-lying ``self_mod_dialog_id``. Rows recorded BEFORE a transport
    invocation must not claim EMITTED — at the pre-send custody point
    the honest claim is eligibility/intent (twenty-second round).

    ``provenance`` is REQUIRED with NO DEFAULT (twenty-third round):
    only the producer knows which branch spoke, and a default would let
    a forgotten wiring silently stamp a lie. A missing argument is a
    BUILD failure, not a runtime path. The seam binds shape -> taint
    here so no taint list ever crosses a closure.

    ``raw_text`` is the bytes the organ PRODUCED (twenty-fourth round,
    3-0) — never "what the owner received". The surface transforms the
    reply after this call returns, and egress is not even a byte-string.
    """
    _require_recorder(recorder)
    kwargs: dict = {"event_origin": event_origin}
    if raw_surface is not None:
        kwargs["raw_surface"] = raw_surface
    if pending_card_id is not None:
        kwargs["pending_card_id"] = pending_card_id
    if self_mod_dialog_id is not None:
        kwargs["self_mod_dialog_id"] = self_mod_dialog_id
    if audit_verdict is not None:
        kwargs["audit_verdict"] = audit_verdict
    if evidence_envelope is not None:
        kwargs["evidence_envelope"] = evidence_envelope
    return recorder._record(
        "system_event",
        raw_text,
        surface=surface,
        provenance=provenance,
        kwargs=kwargs,
        parent=parent,
    )


def record_approval_decision(
    *,
    surface: str,
    raw_text: str,
    audit_verdict: dict,
    pending_card_id: int,
    raw_surface: str | None = None,
    parent: RecordResult | None = None,
    recorder=PRODUCTION,
) -> RecordResult:
    """Record an approval/denial resolution as ``approval_decision``.

    THE THIRD PUBLIC METHOD — an owner-ruled amendment (2026-08-28) to
    the twenty-second round's "exactly two public methods". That ruling
    remains correct IN PURPOSE: it exists to prevent semantic
    passthrough, and this is not one. Implementation evidence forced the
    amendment — ``approval_decision`` is a first-class ledger kind that
    **structurally FORBIDS ``event_origin``** while
    ``record_organ_event`` REQUIRES it, so neither existing method could
    represent it honestly. Recording it as ``system_event`` would flatten
    approval/rejection AUTHORITY into organ speech.

    Narrowly scoped by construction: ``turn_kind`` is the literal
    ``"approval_decision"``, there is no caller-supplied kind, no
    ``event_origin``, and no ``**kwargs`` escape hatch. The schema's
    real required fields are mandatory parameters with no defaults, so
    a forgotten one is a BUILD failure.

    NAMED RESIDUAL, recorded rather than papered over: this kind admits
    exactly one taint set, ``{owner_utterance}``. The bytes are
    substrate-RENDERED (``format_resolution_text``) even though the
    DECISION they record is the owner's act. The schema leaves no
    alternative, so the label is the schema's claim about whose act this
    is, not a claim that Maez transcribed owner speech. A future reader
    must not present these bytes as words the owner typed.
    """
    _require_recorder(recorder)
    if not isinstance(pending_card_id, int) or isinstance(pending_card_id, bool):
        raise TypeError(
            "record_approval_decision: pending_card_id must be an int — "
            "the card receipt is the parent action's identity"
        )
    kwargs: dict = {
        "audit_verdict": audit_verdict,
        "pending_card_id": pending_card_id,
    }
    if raw_surface is not None:
        kwargs["raw_surface"] = raw_surface
    return recorder._record(
        "approval_decision",
        raw_text,
        surface=surface,
        taint_labels=["owner_utterance"],
        kwargs=kwargs,
        parent=parent,
    )


def recorder_status() -> dict:
    """Process-local recorder health: counts by state since import.

    Counters are per-process BY DEFINITION (module state); the daemon
    cockpit labels its block ``scope=daemon_process`` and the
    non-owner-process LOST residual is NAMED in the twenty-second
    round, not papered over here.
    """
    with PRODUCTION._lock:
        counts = dict(PRODUCTION.counts)
    return {"pid": os.getpid(), "counts": counts}
