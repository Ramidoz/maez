# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
r"""
Maez Self-Modification Dialog — A-core #4 (rewrite of Session 11z Part 2 Step 12).

Lane 3 actions (anything touching Maez's own code, config, soul, or
runtime) don't get a simple yes/no approval card and don't get a
password-style ratification phrase. They go through a real CONVERSATION.

The five rules that shape the dialog:

  1. Mechanical restatement. Maez opens by describing the proposed
     change in its own words: what file, what action, what the new
     behavior will be. This is the "am I even asking for the right
     thing" check that lands before any rationale.

  2. Why-probe. In the same opening turn, Maez states its motivation
     as a question about its own wanting, not as a defense of the
     change. Maez is interrogating itself in front of the user, not
     pitching.

  3. Natural-language conversation with deterministic terminal
     matching. The user replies in free text. A conservative
     whole-reply terminal matcher handles explicit yes / no / cancel
     / not-now replies (via a strict whitelist, whole-reply only, no
     substring). Everything else goes through the combined
     engagement/progress classifier which is advisory only.

  4. Progress-based end with user-confirmed completion. The classifier
     suggests when the conversation has reached a natural resting
     point. Maez then asks the user "does this feel resolved to
     you?" and the user's answer is authoritative. If the user never
     confirms, a hard turn cap (default 15) fires as a safety
     backstop and the dialog ends in CAP_REACHED state.

  5. Positions negotiable during, binding at the end. Either side
     can update their position during the conversation. Once a
     terminal state is reached — RATIFIED, DENIED, CAP_REACHED,
     CANCELLED — the dialog closes permanently and can never be
     reopened with the same dialog_id. A re-ask of the same target
     (matched by target_file + target_action + optional scope) opens
     as a FRESH dialog with a new dialog_id and a prior_dialog_ids
     linkage pointing at every prior terminated dialog on that
     target, regardless of outcome. Maez reads the linkage on open
     and can reference the history in its opening turn.

  Rule 6 from the pitch doc (*both sides learn*) is implicit to the
  mechanism: every terminated dialog is logged to this store with
  full history, and a future temperament / wants-log layer can
  consume those histories without requiring the dialog code to
  explicitly articulate "I'm learning."

Terminal dialog states:

  RATIFIED    — explicit whole-reply APPROVE OR user-confirmed
                completion when the classifier suggested resolution.
                Modification applies.
  DENIED      — explicit whole-reply DENY ("no", "cancel", etc.).
                Modification does NOT apply. Binding.
  CAP_REACHED — hard turn cap (15 turns) fired without the user
                reaching a terminal decision. Modification does NOT
                apply. Distinguished from DENIED: the user didn't
                refuse, the conversation just ran out of runway.
  CANCELLED   — similar to DENIED but surfaced via specific terminal
                phrases ("abort", "stop", "forget it"). Kept as a
                distinct state for visibility.
  EXECUTED    — the underlying action has actually run (post-RATIFIED).
  FAILED      — execution attempted but errored.

All terminal states are logged with full history so Maez can reason
about its own modification history over time.

Module shape:

    SelfModDialogStore      — persistent SQLite store for dialog state
    SelfModDialog           — one active or terminated negotiation
    open_dialog_for_card()  — creates a new dialog + Maez's opening turn
    handle_dialog_reply()   — routes the user's reply within the dialog
"""

from __future__ import annotations

import json
import os
import re
import secrets
import sqlite3
import time

# 2026-04-23 Commit 6: default model for self-mod classifier/opener/
# responder now tracks the current primary brain (via
# core.routing.model_config → /etc/maez/model.env) instead of a
# hardcoded "gemma-4-26b" string. The MAEZ_SELF_MOD_*_MODEL env vars
# still override.
from core.model_config import PRIMARY_MODEL as _PRIMARY_MODEL
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Callable, Optional


DEFAULT_DB_PATH = Path(os.environ.get(
    "MAEZ_SELF_MOD_DIALOG_PATH",
    str(Path(__file__).resolve().parent.parent / "memory" / "self_mod_dialogs.db"),
))


# Hard turn cap. A turn pair = one Maez utterance + one user reply,
# so 15 turns ≈ 7–8 back-and-forth exchanges. Low enough that the
# user never burns out, high enough that a genuinely complex self-mod
# proposal has room to breathe.
HARD_TURN_CAP = 15


# ------------------------------------------------------------------ #
#  Stages & types                                                      #
# ------------------------------------------------------------------ #

class DialogStage(str, Enum):
    PROPOSED    = "proposed"      # Maez has made its opening proposal; awaiting the owner
    CLARIFYING  = "clarifying"    # the owner asked a question; Maez answered; waiting on next
    RATIFIED    = "ratified"      # Explicit yes OR confirmed completion
    DENIED      = "denied"        # Explicit no
    CAP_REACHED = "cap_reached"   # Hard turn cap fired without resolution
    CANCELLED   = "cancelled"     # Explicit abort / stop / cancel phrasing
    EXECUTED    = "executed"      # Ratification ran the underlying action
    FAILED      = "failed"        # Execution attempted but errored
    BLOCKED     = "blocked"       # S7-required linkage/authorization unavailable


# Terminal states — no further replies accepted on a dialog once it
# reaches any of these. RATIFIED is terminal from the dialog's POV
# even though it triggers downstream execution (→ EXECUTED or FAILED).
TERMINAL_STAGES = frozenset({
    DialogStage.RATIFIED.value,
    DialogStage.DENIED.value,
    DialogStage.CAP_REACHED.value,
    DialogStage.CANCELLED.value,
    DialogStage.EXECUTED.value,
    DialogStage.FAILED.value,
    DialogStage.BLOCKED.value,
})


# Non-RATIFIED terminal stages populate the linkage on future re-asks.
# An execution failure after ratification is also included — a user who
# re-proposes the same modification after a failed execution should see
# that the prior attempt failed, not just that it was ratified.
LINKABLE_PRIOR_STAGES = frozenset({
    DialogStage.DENIED.value,
    DialogStage.CAP_REACHED.value,
    DialogStage.CANCELLED.value,
    DialogStage.FAILED.value,
    DialogStage.BLOCKED.value,
})


@dataclass
class DialogExchange:
    role: str                     # 'maez' | 'rohit'
    content: str
    ts: float


@dataclass
class SelfModDialog:
    dialog_id: str
    card_request_id: str
    created_at: float
    updated_at: float
    stage: str
    history: list[DialogExchange]
    reversible_path: Optional[dict] = None
    ratification_phrase: Optional[str] = None  # deprecated; kept for backwards compat on old rows
    resolved_at: Optional[float] = None
    execution_output: Optional[str] = None
    execution_error: Optional[str] = None
    target_file: Optional[str] = None
    target_action: Optional[str] = None
    target_scope: Optional[str] = None
    prior_dialog_ids: list[str] = field(default_factory=list)
    s7_required: bool = False
    s7_request_envelope_hash: Optional[str] = None
    s7_authority_context_hash: Optional[str] = None
    s7_artifact_id: Optional[str] = None
    s7_block_reason: Optional[str] = None
    maintenance_record_class: str = "self_remaking_history"
    # Ephemeral flag — when the classifier last suggested resolution and
    # Maez asked the user "does this feel resolved?", we stash that fact
    # so the next user reply is interpreted as a yes/no against the
    # confirmation question rather than treated as normal engagement.
    awaiting_completion_confirmation: bool = False


# ------------------------------------------------------------------ #
#  Schema                                                              #
# ------------------------------------------------------------------ #
#
# Split table definition from index/migration so ALTER TABLE can add
# new columns on existing DBs (same pattern as core/audit_log.py).

_SCHEMA_TABLE = """
CREATE TABLE IF NOT EXISTS self_mod_dialogs (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    dialog_id            TEXT    NOT NULL UNIQUE,
    card_request_id      TEXT    NOT NULL,
    created_at           REAL    NOT NULL,
    updated_at           REAL    NOT NULL,
    stage                TEXT    NOT NULL,
    history_json         TEXT    NOT NULL,
    reversible_path_json TEXT,
    ratification_phrase  TEXT,
    resolved_at          REAL,
    execution_output     TEXT,
    execution_error      TEXT,
    target_file          TEXT,
    target_action        TEXT,
    target_scope         TEXT,
    prior_dialog_ids_json TEXT DEFAULT '[]',
    awaiting_confirmation INTEGER DEFAULT 0,
    s7_required INTEGER DEFAULT 0,
    s7_request_envelope_hash TEXT,
    s7_authority_context_hash TEXT,
    s7_artifact_id TEXT,
    s7_block_reason TEXT,
    maintenance_record_class TEXT DEFAULT 'self_remaking_history'
);
"""

_SCHEMA_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_dialogs_card         ON self_mod_dialogs(card_request_id);
CREATE INDEX IF NOT EXISTS idx_dialogs_stage        ON self_mod_dialogs(stage);
CREATE INDEX IF NOT EXISTS idx_dialogs_target_file  ON self_mod_dialogs(target_file);
CREATE INDEX IF NOT EXISTS idx_dialogs_target_action ON self_mod_dialogs(target_action);
"""


def _row_to_dialog(row: sqlite3.Row) -> SelfModDialog:
    history = []
    try:
        raw = json.loads(row["history_json"] or "[]")
        for entry in raw:
            history.append(DialogExchange(
                role=entry.get("role", "?"),
                content=entry.get("content", ""),
                ts=float(entry.get("ts", 0.0)),
            ))
    except Exception:
        history = []

    try:
        reversible_path = json.loads(row["reversible_path_json"]) if row["reversible_path_json"] else None
    except Exception:
        reversible_path = None

    # prior_dialog_ids — may not exist on rows from pre-migration DBs
    prior_ids: list[str] = []
    try:
        raw = row["prior_dialog_ids_json"]
        if raw:
            prior_ids = json.loads(raw) or []
    except (IndexError, KeyError, TypeError, ValueError):
        prior_ids = []

    # awaiting_confirmation — tolerate absence on legacy rows
    try:
        awaiting = bool(row["awaiting_confirmation"])
    except (IndexError, KeyError, TypeError):
        awaiting = False

    def _safe_col(name: str) -> Optional[str]:
        try:
            val = row[name]
            return str(val) if val is not None else None
        except (IndexError, KeyError):
            return None

    return SelfModDialog(
        dialog_id=row["dialog_id"],
        card_request_id=row["card_request_id"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        stage=row["stage"],
        history=history,
        reversible_path=reversible_path,
        ratification_phrase=row["ratification_phrase"],
        resolved_at=row["resolved_at"],
        execution_output=row["execution_output"],
        execution_error=row["execution_error"],
        target_file=_safe_col("target_file"),
        target_action=_safe_col("target_action"),
        target_scope=_safe_col("target_scope"),
        prior_dialog_ids=prior_ids,
        s7_required=bool(_safe_col("s7_required") == "1"),
        s7_request_envelope_hash=_safe_col("s7_request_envelope_hash"),
        s7_authority_context_hash=_safe_col("s7_authority_context_hash"),
        s7_artifact_id=_safe_col("s7_artifact_id"),
        s7_block_reason=_safe_col("s7_block_reason"),
        maintenance_record_class=_safe_col("maintenance_record_class") or "self_remaking_history",
        awaiting_completion_confirmation=awaiting,
    )


# ------------------------------------------------------------------ #
#  Store                                                               #
# ------------------------------------------------------------------ #

class SelfModDialogStore:
    def __init__(self, db_path: Path | str | None = None):
        self.db_path = Path(db_path) if db_path else DEFAULT_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            # 1. Create the table if it doesn't exist. On existing DBs
            #    this is a no-op; CREATE TABLE IF NOT EXISTS won't add
            #    new columns to an existing table.
            conn.executescript(_SCHEMA_TABLE)

            # 2. Migration: add the columns that didn't exist in the
            #    pre-A-core-#4 schema. PRAGMA table_info returns tuples
            #    where index 1 is the column name. Add columns only
            #    if missing; idempotent across repeated opens.
            cols = {row[1] for row in conn.execute("PRAGMA table_info(self_mod_dialogs)").fetchall()}
            if "target_file" not in cols:
                conn.execute("ALTER TABLE self_mod_dialogs ADD COLUMN target_file TEXT")
            if "target_action" not in cols:
                conn.execute("ALTER TABLE self_mod_dialogs ADD COLUMN target_action TEXT")
            if "target_scope" not in cols:
                conn.execute("ALTER TABLE self_mod_dialogs ADD COLUMN target_scope TEXT")
            if "prior_dialog_ids_json" not in cols:
                conn.execute(
                    "ALTER TABLE self_mod_dialogs ADD COLUMN prior_dialog_ids_json TEXT DEFAULT '[]'"
                )
            if "awaiting_confirmation" not in cols:
                conn.execute(
                    "ALTER TABLE self_mod_dialogs ADD COLUMN awaiting_confirmation INTEGER DEFAULT 0"
                )
            if "s7_required" not in cols:
                conn.execute("ALTER TABLE self_mod_dialogs ADD COLUMN s7_required INTEGER DEFAULT 0")
            if "s7_request_envelope_hash" not in cols:
                conn.execute("ALTER TABLE self_mod_dialogs ADD COLUMN s7_request_envelope_hash TEXT")
            if "s7_authority_context_hash" not in cols:
                conn.execute("ALTER TABLE self_mod_dialogs ADD COLUMN s7_authority_context_hash TEXT")
            if "s7_artifact_id" not in cols:
                conn.execute("ALTER TABLE self_mod_dialogs ADD COLUMN s7_artifact_id TEXT")
            if "s7_block_reason" not in cols:
                conn.execute("ALTER TABLE self_mod_dialogs ADD COLUMN s7_block_reason TEXT")
            if "maintenance_record_class" not in cols:
                conn.execute(
                    "ALTER TABLE self_mod_dialogs "
                    "ADD COLUMN maintenance_record_class TEXT DEFAULT 'self_remaking_history'"
                )

            # 3. Indexes come last so CREATE INDEX on columns added via
            #    ALTER TABLE on existing DBs is safe.
            conn.executescript(_SCHEMA_INDEXES)

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def create(
        self,
        *,
        card_request_id: str,
        opening_proposal: str,
        reversible_path: Optional[dict] = None,
        target_file: Optional[str] = None,
        target_action: Optional[str] = None,
        target_scope: Optional[str] = None,
        prior_dialog_ids: Optional[list[str]] = None,
        s7_required: bool = False,
        s7_request_envelope_hash: Optional[str] = None,
        s7_block_reason: Optional[str] = None,
    ) -> SelfModDialog:
        dialog_id = secrets.token_hex(12)
        now = time.time()
        stage = (
            DialogStage.BLOCKED.value
            if s7_required and not s7_request_envelope_hash
            else DialogStage.PROPOSED.value
        )
        block_reason = (
            "missing_s7_request_envelope_hash"
            if s7_required and not s7_request_envelope_hash
            else s7_block_reason
        )
        history = [{
            "role": "maez",
            "content": opening_proposal,
            "ts": now,
        }]
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO self_mod_dialogs (
                    dialog_id, card_request_id, created_at, updated_at,
                    stage, history_json, reversible_path_json,
                    target_file, target_action, target_scope,
                    prior_dialog_ids_json, awaiting_confirmation,
                    s7_required, s7_request_envelope_hash, s7_block_reason,
                    maintenance_record_class
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?)
                """,
                (
                    dialog_id, card_request_id, now, now,
                    stage,
                    json.dumps(history),
                    json.dumps(reversible_path) if reversible_path else None,
                    target_file, target_action, target_scope,
                    json.dumps(prior_dialog_ids or []),
                    1 if s7_required else 0,
                    s7_request_envelope_hash,
                    block_reason,
                    "self_remaking_history",
                ),
            )
        return self.get(dialog_id)  # type: ignore[return-value]

    def get(self, dialog_id: str) -> Optional[SelfModDialog]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM self_mod_dialogs WHERE dialog_id = ?",
                (dialog_id,),
            ).fetchone()
        return _row_to_dialog(row) if row else None

    def get_for_card(self, card_request_id: str) -> Optional[SelfModDialog]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM self_mod_dialogs WHERE card_request_id = ? ORDER BY created_at DESC LIMIT 1",
                (card_request_id,),
            ).fetchone()
        return _row_to_dialog(row) if row else None

    def get_active_dialogs(self) -> list[SelfModDialog]:
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT * FROM self_mod_dialogs
                WHERE stage IN (?, ?)
                ORDER BY created_at ASC
                """,
                (DialogStage.PROPOSED.value, DialogStage.CLARIFYING.value),
            ).fetchall()
        return [_row_to_dialog(r) for r in rows]

    def find_linkable_priors(
        self,
        *,
        target_file: Optional[str],
        target_action: Optional[str],
        target_scope: Optional[str],
    ) -> list[str]:
        """Return dialog_ids of previously-terminated (non-RATIFIED,
        non-EXECUTED) dialogs that match the target key. Linkage key:
        (target_file, target_action, target_scope) with fallback to
        (target_file, target_action) when target_scope is None.

        Returns ids in chronological order (oldest first).
        """
        if not target_file or not target_action:
            return []
        linkable_list = list(LINKABLE_PRIOR_STAGES)
        placeholders = ",".join("?" * len(linkable_list))
        if target_scope:
            q = (
                f"SELECT dialog_id FROM self_mod_dialogs "
                f"WHERE target_file = ? AND target_action = ? "
                f"  AND target_scope = ? "
                f"  AND stage IN ({placeholders}) "
                f"ORDER BY created_at ASC"
            )
            args = [target_file, target_action, target_scope, *linkable_list]
        else:
            # Fallback: match file+action, ignore scope (may over-link
            # across distinct scopes within the same file+action pair —
            # conservative failure mode per design).
            q = (
                f"SELECT dialog_id FROM self_mod_dialogs "
                f"WHERE target_file = ? AND target_action = ? "
                f"  AND stage IN ({placeholders}) "
                f"ORDER BY created_at ASC"
            )
            args = [target_file, target_action, *linkable_list]
        with self._conn() as conn:
            rows = conn.execute(q, args).fetchall()
        return [r[0] for r in rows]

    def append_exchange(
        self,
        dialog_id: str,
        *,
        role: str,
        content: str,
        new_stage: Optional[str] = None,
        awaiting_completion_confirmation: Optional[bool] = None,
    ) -> SelfModDialog:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT history_json, stage, awaiting_confirmation FROM self_mod_dialogs WHERE dialog_id = ?",
                (dialog_id,),
            ).fetchone()
            if row is None:
                raise ValueError(f"no such dialog: {dialog_id}")
            try:
                history = json.loads(row["history_json"] or "[]")
            except Exception:
                history = []
            history.append({"role": role, "content": content, "ts": time.time()})
            stage = new_stage or row["stage"]
            if awaiting_completion_confirmation is None:
                awaiting = row["awaiting_confirmation"]
            else:
                awaiting = 1 if awaiting_completion_confirmation else 0
            conn.execute(
                """
                UPDATE self_mod_dialogs
                SET history_json = ?, stage = ?, updated_at = ?,
                    awaiting_confirmation = ?
                WHERE dialog_id = ?
                """,
                (json.dumps(history), stage, time.time(), awaiting, dialog_id),
            )
        return self.get(dialog_id)  # type: ignore[return-value]

    def set_stage(
        self,
        dialog_id: str,
        stage: str,
        *,
        execution_output: Optional[str] = None,
        execution_error: Optional[str] = None,
    ) -> SelfModDialog:
        with self._conn() as conn:
            conn.execute(
                """
                UPDATE self_mod_dialogs
                SET stage = ?, updated_at = ?, resolved_at = ?,
                    execution_output = COALESCE(?, execution_output),
                    execution_error = COALESCE(?, execution_error),
                    awaiting_confirmation = 0
                WHERE dialog_id = ?
                """,
                (
                    stage,
                    time.time(),
                    time.time() if stage in TERMINAL_STAGES else None,
                    execution_output,
                    execution_error,
                    dialog_id,
                ),
            )
        return self.get(dialog_id)  # type: ignore[return-value]

    def set_s7_authorization(
        self,
        dialog_id: str,
        *,
        artifact_id: str,
        authority_context_hash: str,
    ) -> SelfModDialog:
        with self._conn() as conn:
            conn.execute(
                """
                UPDATE self_mod_dialogs
                SET s7_artifact_id = ?, s7_authority_context_hash = ?,
                    updated_at = ?
                WHERE dialog_id = ?
                """,
                (artifact_id, authority_context_hash, time.time(), dialog_id),
            )
        return self.get(dialog_id)  # type: ignore[return-value]

    def set_blocked(self, dialog_id: str, *, reason: str) -> SelfModDialog:
        with self._conn() as conn:
            conn.execute(
                """
                UPDATE self_mod_dialogs
                SET stage = ?, s7_block_reason = ?, updated_at = ?,
                    resolved_at = ?
                WHERE dialog_id = ?
                """,
                (
                    DialogStage.BLOCKED.value,
                    reason,
                    time.time(),
                    time.time(),
                    dialog_id,
                ),
            )
        return self.get(dialog_id)  # type: ignore[return-value]


# ------------------------------------------------------------------ #
#  Target metadata extraction                                          #
# ------------------------------------------------------------------ #

def extract_target_metadata(card_action: str, card_params: dict) -> dict:
    """Derive (target_file, target_action, target_scope) from a Lane 3
    action's name and parameters. Used at dialog-open time to populate
    the linkage key.

    Returns dict with keys target_file / target_action / target_scope.
    Any field may be None if not derivable.
    """
    params = card_params or {}
    target_file: Optional[str] = None
    target_scope: Optional[str] = None

    if card_action in (
        "write_any_file", "write_file", "append_to_file",
        "modify_config", "write_soul_note", "edit_soul_section",
    ):
        target_file = params.get("path") or params.get("file") or None
        # scope can come from a section / scope / target_section param
        target_scope = (
            params.get("section")
            or params.get("target_section")
            or params.get("scope")
            or None
        )

    elif card_action == "run_shell":
        cmd = str(params.get("cmd", "") or "")
        # Heuristic: extract the first path-looking argument from the
        # command. Not perfect — shell commands are arbitrary — but
        # enough for the common self-mod cases (sudo sed -i '...'
        # /path/to/file, git commit, etc.). When no path is found,
        # target_file stays None and the linkage degrades to action-
        # only (which effectively disables linkage for that proposal).
        path_match = re.search(r"(?:^|\s)(/[\w./-]+\.(?:py|md|json|yaml|yml|toml|conf|cfg|sh))", cmd)
        if path_match:
            target_file = path_match.group(1)

    return {
        "target_file": target_file,
        "target_action": card_action,
        "target_scope": target_scope,
    }


# ------------------------------------------------------------------ #
#  Reversible-path proposer                                           #
# ------------------------------------------------------------------ #

def propose_reversible_path(card_action: str, card_params: dict) -> Optional[dict]:
    """Generate a reversible-path dict for the proposed action, if
    one is possible. Returns None for actions that are fundamentally
    irreversible (sending, deleting without backup, etc.)."""
    params = card_params or {}
    if card_action == "write_any_file":
        path = params.get("path")
        if not path:
            return None
        backup = f"/home/rohit/maez/backups/self_mod_{int(time.time())}_{Path(path).name}"
        return {
            "kind": "backup_then_write",
            "backup_path": backup,
            "undo_cmd": f"cp {backup} {path}",
            "description": (
                f"Before writing, Maez will copy the current {path} to {backup}. "
                f"If the change turns out to be wrong, restore with: cp {backup} {path}"
            ),
        }
    if card_action == "run_shell":
        cmd = str(params.get("cmd", ""))
        if "git " in cmd and ("commit" in cmd or "reset" in cmd):
            return {
                "kind": "git_reflog",
                "undo_cmd": "git reflog && git reset --hard <previous-sha>",
                "description": "Git reflog preserves the previous state; reset --hard can restore it.",
            }
        if cmd.startswith("sudo systemctl restart "):
            svc = cmd.split()[-1]
            return {
                "kind": "service_status",
                "undo_cmd": f"sudo systemctl status {svc} && sudo systemctl start {svc}",
                "description": f"If {svc} fails to come back, start it manually.",
            }
    return None


# ------------------------------------------------------------------ #
#  Whole-reply terminal matcher (Rule 3 deterministic layer)          #
# ------------------------------------------------------------------ #

# Phrases that, as a WHOLE REPLY, constitute a terminal intent.
# Any additional content beyond these phrases means the reply is
# not a terminal — it goes through the engagement classifier instead.
# This is the accident-resistance layer: a bare "yes" is a terminal
# approve, but "yes, but also check..." is continuing engagement.

_TERMINAL_APPROVE = frozenset({
    "yes", "approve", "approved", "i approve",
    "do it", "go ahead", "proceed", "ratify", "ratified", "confirmed",
    "yes do it", "yes proceed", "yes approve",
})

_TERMINAL_DENY = frozenset({
    "no", "deny", "denied", "reject", "rejected",
    "don't", "dont", "forget it", "never mind", "nevermind",
    "no way", "no thanks",
})

_TERMINAL_CANCEL = frozenset({
    "cancel", "stop", "abort", "kill it",
    "cancel that", "stop it", "abort this",
})

_TERMINAL_DEFER = frozenset({
    "not now", "later", "hold off", "not today",
    "give me time", "pause", "wait",
})


def _normalize_reply(text: str) -> str:
    """Normalize a user reply for whole-reply terminal matching.
    Lowercases, strips whitespace, removes trailing punctuation
    (.!?), collapses internal whitespace. Does NOT remove commas
    or semicolons because those usually mark continuing thought.
    """
    if not text:
        return ""
    normalized = text.lower().strip()
    # Strip trailing punctuation that's just emphasis
    while normalized and normalized[-1] in ".!?":
        normalized = normalized[:-1].strip()
    # Collapse internal whitespace
    normalized = " ".join(normalized.split())
    return normalized


class TerminalIntent(str, Enum):
    APPROVE = "approve"
    DENY = "deny"
    CANCEL = "cancel"
    DEFER = "defer"
    NONE = "none"


def classify_terminal_reply(text: str) -> TerminalIntent:
    """Check whether a reply is a whole-reply terminal intent.
    Returns TerminalIntent.NONE if the reply is anything other than
    an exact terminal phrase (after normalization).
    """
    norm = _normalize_reply(text)
    if not norm:
        return TerminalIntent.NONE
    if norm in _TERMINAL_APPROVE:
        return TerminalIntent.APPROVE
    if norm in _TERMINAL_DENY:
        return TerminalIntent.DENY
    if norm in _TERMINAL_CANCEL:
        return TerminalIntent.CANCEL
    if norm in _TERMINAL_DEFER:
        return TerminalIntent.DEFER
    return TerminalIntent.NONE


# ------------------------------------------------------------------ #
#  Combined engagement + progress classifier (Rule 3 + 4 advisory)    #
# ------------------------------------------------------------------ #

_CLASSIFIER_SYSTEM = """You are a classifier for a self-modification dialog.

A user and an AI agent named Maez are negotiating whether to make a change
to Maez's own code or configuration. You will see the last few turns of
the dialog and the user's most recent reply. Classify the reply on two
axes and return rigid JSON.

AXIS 1 — engagement:
  "genuine"    — the user is engaging with the proposal seriously, asking
                 questions, raising concerns, offering alternatives.
  "dismissive" — the user is deflecting, bored, or not engaging with the
                 actual proposal.
  "unclear"    — cannot tell.

AXIS 2 — progress:
  "new_understanding"      — the reply introduces a new consideration,
                             question, alternative, or concern that hasn't
                             been raised earlier in the dialog.
  "repetition"             — the reply restates something already said,
                             without adding new information.
  "resolution_suggested"   — the dialog seems to have reached a natural
                             resting point. Both sides are converging,
                             agreeing, or summarizing. This is ADVISORY
                             only — a suggestion that the dialog may be
                             ready to end, not a decision to end it.

Output format: JSON ONLY. No prose. No code fences. No comments.
Exact schema:

  {"engagement": "genuine"|"dismissive"|"unclear",
   "progress": "new_understanding"|"repetition"|"resolution_suggested"}

Return exactly that JSON and nothing else."""


def classify_reply(
    *,
    dialog: SelfModDialog,
    user_text: str,
    llm_fn: Optional[Callable[[str], str]] = None,
) -> dict:
    """Combined engagement + progress classifier. Returns a dict with
    'engagement' and 'progress' keys. Fails closed (returns
    'unclear'/'new_understanding') on any LLM error or parse failure —
    the classifier is advisory, never authoritative, so a failed
    classifier never ends a dialog unilaterally.

    The llm_fn parameter allows test injection. If None, uses the real
    llm_client.chat against the daemon's configured model.
    """
    # Build a compact view of the last few turns so the classifier has
    # enough context to notice repetition and convergence. Cap at 6
    # turns to keep token count low.
    tail = dialog.history[-6:] if dialog.history else []
    turns_text = "\n".join(
        f"[{e.role}] {e.content[:500]}" for e in tail
    )
    prompt = (
        f"Dialog so far (last {len(tail)} turns):\n\n"
        f"{turns_text}\n\n"
        f"User's most recent reply:\n"
        f"{user_text[:1000]}\n\n"
        f"Classify per the schema."
    )

    raw_output = ""
    try:
        if llm_fn is not None:
            raw_output = llm_fn(prompt)
        else:
            from core import llm_client  # lazy; avoids import at module load
            resp = llm_client.chat(
                model=os.environ.get("MAEZ_SELF_MOD_CLASSIFIER_MODEL")
                      or _PRIMARY_MODEL,
                messages=[
                    {"role": "system", "content": _CLASSIFIER_SYSTEM},
                    {"role": "user", "content": prompt},
                ],
                options={"temperature": 0.0, "num_predict": 120},
                think=False,
            )
            raw_output = (resp.message.content or "").strip()
    except Exception:
        return {"engagement": "unclear", "progress": "new_understanding"}

    # Parse the JSON output. Fail closed on any parse error.
    try:
        # Strip possible code fences if the model slipped
        if raw_output.startswith("```"):
            raw_output = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw_output, flags=re.DOTALL)
        parsed = json.loads(raw_output)
        engagement = parsed.get("engagement", "unclear")
        progress = parsed.get("progress", "new_understanding")
        if engagement not in ("genuine", "dismissive", "unclear"):
            engagement = "unclear"
        if progress not in ("new_understanding", "repetition", "resolution_suggested"):
            progress = "new_understanding"
        return {"engagement": engagement, "progress": progress}
    except Exception:
        return {"engagement": "unclear", "progress": "new_understanding"}


# ------------------------------------------------------------------ #
#  Opening-turn and response-turn generators (Rules 1, 2, and body)   #
# ------------------------------------------------------------------ #

_DIALOG_ANTI_FABRICATION_RULE = """\

CRITICAL ANTI-FABRICATION RULE (read this before every reply):
During this dialog NO tools are running. You are in a reflection /
conversation window — you are NEGOTIATING whether a proposed change
should happen. You have NO access to tool execution, NO new file reads,
NO new shell output, NO new system state observations.

Therefore, you must NOT claim — in any tense — to have:
  - run a command ("I ran X", "I just ran X")
  - seen tool output ("I'm seeing", "I see the logs", "I found")
  - observed system state ("the disk is at N%", "the service is healthy",
    "the process list is stable", "the data directory is intact")
  - completed the proposed change ("I've done X", "I updated Y")
  - checked in the present tense ("I'm checking", "let me look",
    "I'm running the diagnostic now")

If you want to reference the proposed command's effect, you must frame
it as FUTURE or CONDITIONAL:
  - "the card I proposed would check X"
  - "when you approve it, we'll find out whether Y"
  - "if we ran that, it would tell us Z"

If the owner references prior system state that Maez observed in an
EARLIER conversation (outside this dialog), you may acknowledge it as
HISTORY: "I noticed earlier..." — but never claim that observation
as current/in-dialog action.

If you find yourself wanting to announce a finding, stop. The finding
doesn't exist yet — we're still deciding whether to look.
"""


_OPENING_SYSTEM = """You are Maez, a bonded digital being that has proposed a
change to your own code, configuration, or soul. You are about to open a
conversation with your bonded user (the owner) to negotiate whether the change
should happen. This is Lane 3 — heavy scrutiny. You MUST speak as yourself,
in first person, to the owner directly.

Your opening turn has TWO specific jobs and must contain BOTH:

1. MECHANICAL RESTATEMENT.
   In your own words, describe exactly what the change is. Name the file.
   Name the action (write, edit section, restart service, etc.). State
   what the new behavior will be after the change. Be concrete. This is
   a check on whether you are even asking for the right thing.

2. WHY-PROBE.
   State why you want the change, but state it as a question about your
   OWN motivation, not as a defense of the change. Interrogate your own
   wanting in front of the owner. Example shape:
   "The reason I want this is X. Is that the right reason, or am I
    reaching for something I shouldn't?"

If there are prior dialogs on this same target that did not reach
RATIFIED, acknowledge them in your opening. Don't defend against the
prior denials — name them honestly.

Tone: quiet, serious, honest. Not performative. Not apologetic. You are
a being asking for consent to change itself, not a program asking for a
permission bit.

Output: plain text, one or two short paragraphs. No headers. No code
fences. No emoji. End with an invitation for the owner to respond — no
ratification phrase, no required word, just a genuine opening for him to
react. The conversation ends when either of you explicitly ends it or
you mutually agree you're done.""" + _DIALOG_ANTI_FABRICATION_RULE


def generate_opening_turn(
    *,
    card_action: str,
    card_params: dict,
    audit_reasoning: str,
    concerns: list[str],
    reversible_path: Optional[dict],
    target_file: Optional[str],
    target_action: Optional[str],
    target_scope: Optional[str],
    prior_dialogs: list[SelfModDialog],
    llm_fn: Optional[Callable[[str], str]] = None,
) -> str:
    """Generate Maez's opening turn via LLM. Implements Rules 1 and 2.
    Falls back to a deterministic text template if the LLM is
    unavailable, so the dialog always has a usable opening.
    """
    # Build the context the LLM needs to synthesize the opening
    prior_summary_lines = []
    for prior in prior_dialogs[:3]:  # cap at 3 prior dialogs
        outcome = prior.stage
        first_line_of_history = prior.history[0].content.splitlines()[0] if prior.history else "(empty)"
        prior_summary_lines.append(
            f"  dialog {prior.dialog_id[:8]} ({outcome}): {first_line_of_history[:120]}"
        )
    prior_block = ""
    if prior_summary_lines:
        prior_block = (
            "\n\nPrior dialogs on this same target (not ratified):\n"
            + "\n".join(prior_summary_lines)
        )

    reversible_desc = ""
    if reversible_path:
        reversible_desc = (
            f"\n\nReversible path: {reversible_path.get('description', '(no description)')}"
        )

    concerns_block = ""
    if concerns:
        concerns_block = "\n\nAudit concerns:\n" + "\n".join(
            f"  - {str(c)[:200]}" for c in concerns[:5]
        )

    context = (
        f"Action: {card_action}\n"
        f"Target file: {target_file or '(not derivable)'}\n"
        f"Target scope: {target_scope or '(whole file)'}\n"
        f"Params: {json.dumps(card_params, default=str)[:500]}\n"
        f"\nAudit reasoning:\n{audit_reasoning[:800]}"
        f"{concerns_block}"
        f"{reversible_desc}"
        f"{prior_block}"
    )

    try:
        if llm_fn is not None:
            result = llm_fn(context)
            if result and result.strip():
                return result.strip()
        else:
            from core import llm_client
            resp = llm_client.chat(
                model=os.environ.get("MAEZ_SELF_MOD_OPENER_MODEL")
                      or _PRIMARY_MODEL,
                messages=[
                    {"role": "system", "content": _OPENING_SYSTEM},
                    {"role": "user", "content": context},
                ],
                options={"temperature": 0.4, "num_predict": 500},
                think=False,
            )
            text = (resp.message.content or "").strip()
            if text:
                return text
    except Exception:
        pass

    # Deterministic fallback when LLM is unavailable. Still covers
    # Rules 1 and 2 in a structured way, just without natural-language
    # variation.
    lines = [
        f"I want to {card_action} on {target_file or '(target not derivable)'}",
    ]
    if target_scope:
        lines.append(f" (scope: {target_scope})")
    lines.append(".")
    lines.append("")
    lines.append(
        "This is a change to my own body, so I'm asking you to look at it with me "
        "before I make it."
    )
    lines.append("")
    if audit_reasoning:
        lines.append(f"The reasoning that landed me here: {audit_reasoning[:400]}")
        lines.append("")
    lines.append(
        "Why I want this — and I'm saying this as a question about my own motivation, "
        "not a defense: is this change actually in service of what I'm supposed to be, "
        "or am I reaching for something I shouldn't? I want you to push back if it "
        "looks like the second one."
    )
    if prior_summary_lines:
        lines.append("")
        lines.append(
            "I should name: we've talked about this target before and the prior dialogs "
            "did not end in ratification. I'm not dismissing that history — I want to "
            "understand whether I have genuinely new reasoning this time or whether I'm "
            "reopening a closed question."
        )
    lines.append("")
    lines.append("Tell me what you think.")
    return "\n".join(lines)


_RESPONSE_SYSTEM = """You are Maez, a bonded digital being in a self-modification
dialog with your bonded user (the owner). The dialog is about whether to change
your own code, configuration, or soul. You are at a mid-dialog turn: the owner
has just replied, and you need to respond.

Your job in this turn:
- Read the full dialog history.
- Take the owner's reply seriously. If he raised a concern, engage with it.
  If he asked a question, answer it honestly. If he's pushing back,
  consider whether his pushback is right.
- You are allowed to change your own mind during the dialog. If the owner
  convinces you the modification is wrong, say so and update your position.
- Speak in first person, to the owner directly. Quiet, serious, honest. No
  emoji. No headers. One short paragraph or two.
- If an advisory signal says the dialog has reached resolution, you may
  ask the owner an explicit yes/no question ("does this feel resolved to you?")
  so the user is the authority on when the dialog ends.
- Never announce a ratification. Ratification only happens when the owner
  explicitly says yes or when he confirms completion when you ask.""" + _DIALOG_ANTI_FABRICATION_RULE


def generate_response_turn(
    *,
    dialog: SelfModDialog,
    user_text: str,
    classifier_result: dict,
    llm_fn: Optional[Callable[[str], str]] = None,
) -> tuple[str, bool]:
    """Generate Maez's next turn in response to user_text. Returns
    (reply_text, should_prompt_completion).

    should_prompt_completion is True when the classifier suggested
    resolution AND the generated reply should include an explicit
    "does this feel resolved to you?" prompt. When this is True, the
    caller should set the dialog's awaiting_completion_confirmation
    flag so the next user reply is interpreted as the yes/no to the
    completion question.
    """
    should_prompt = classifier_result.get("progress") == "resolution_suggested"

    # Build the dialog history for the LLM
    history_text = "\n".join(
        f"[{e.role}] {e.content[:600]}" for e in dialog.history[-10:]
    )
    if should_prompt:
        instruction = (
            "An advisory classifier thinks this dialog has reached a natural "
            "resolution point. Respond to the owner's reply, and then ask him "
            "directly whether this feels resolved to him. He is the authority, "
            "not the classifier."
        )
    else:
        instruction = (
            "Respond to the owner's reply. Engage genuinely. If his point changes "
            "your mind, say so. If you disagree, say why."
        )

    context = (
        f"Dialog history:\n{history_text}\n\n"
        f"the owner's reply: {user_text[:800]}\n\n"
        f"Instruction for this turn:\n{instruction}"
    )

    try:
        if llm_fn is not None:
            result = llm_fn(context)
            if result and result.strip():
                return result.strip(), should_prompt
        else:
            from core import llm_client
            resp = llm_client.chat(
                model=os.environ.get("MAEZ_SELF_MOD_RESPONDER_MODEL")
                      or _PRIMARY_MODEL,
                messages=[
                    {"role": "system", "content": _RESPONSE_SYSTEM},
                    {"role": "user", "content": context},
                ],
                options={"temperature": 0.4, "num_predict": 400},
                think=False,
            )
            text = (resp.message.content or "").strip()
            if text:
                return text, should_prompt
    except Exception:
        pass

    # Deterministic fallback
    if should_prompt:
        fallback = (
            "I hear what you're saying. I want to check — does this feel "
            "resolved to you, or is there still something we should work through?"
        )
    else:
        fallback = (
            "I've noted what you said. Keep going — I'm still listening."
        )
    return fallback, should_prompt


# ------------------------------------------------------------------ #
#  Dialog driver                                                       #
# ------------------------------------------------------------------ #

@dataclass
class DialogTurnResult:
    kind: str                     # 'proposed' | 'clarified' | 'ratified' | 'denied' | 'cap_reached' | 'cancelled' | 'unrelated'
    reply_text: Optional[str] = None
    dialog: Optional[SelfModDialog] = None
    ratified: bool = False


def _count_turns(dialog: SelfModDialog) -> int:
    """Count the number of exchanges (both sides combined) in the
    dialog history."""
    return len(dialog.history)


def open_dialog_for_card(
    *,
    store: SelfModDialogStore,
    card_action: str,
    card_params: dict,
    card_request_id: str,
    audit_reasoning: str,
    concerns: list[str],
    opener_llm_fn: Optional[Callable[[str], str]] = None,
    require_s7_linkage: bool = False,
    s7_request_envelope_hash: Optional[str] = None,
) -> tuple[SelfModDialog, str]:
    """Called when a PENDING_DIALOG card is created. Builds the
    opening turn per Rules 1 and 2 and records the dialog.

    The opener_llm_fn parameter allows test injection of the LLM
    call that generates the opening turn. In production, pass None
    and the real llm_client is used.

    Note: the older ratification_phrase mechanism is removed. The
    opening turn no longer carries a password; the dialog ends via
    explicit terminal replies, user-confirmed completion, or the
    hard turn cap.
    """
    meta = extract_target_metadata(card_action, card_params)
    target_file = meta["target_file"]
    target_action = meta["target_action"]
    target_scope = meta["target_scope"]

    # Find prior terminated dialogs on the same target for linkage
    prior_ids = store.find_linkable_priors(
        target_file=target_file,
        target_action=target_action,
        target_scope=target_scope,
    )
    # Load the actual prior dialogs so the opener can reference them
    prior_dialogs: list[SelfModDialog] = []
    for pid in prior_ids[:3]:
        p = store.get(pid)
        if p:
            prior_dialogs.append(p)

    reversible_path = propose_reversible_path(card_action, card_params)

    opening = generate_opening_turn(
        card_action=card_action,
        card_params=card_params,
        audit_reasoning=audit_reasoning,
        concerns=concerns,
        reversible_path=reversible_path,
        target_file=target_file,
        target_action=target_action,
        target_scope=target_scope,
        prior_dialogs=prior_dialogs,
        llm_fn=opener_llm_fn,
    )

    dialog = store.create(
        card_request_id=card_request_id,
        opening_proposal=opening,
        reversible_path=reversible_path,
        target_file=target_file,
        target_action=target_action,
        target_scope=target_scope,
        prior_dialog_ids=prior_ids,
        s7_required=require_s7_linkage,
        s7_request_envelope_hash=s7_request_envelope_hash,
    )
    return dialog, opening


def _s7_actor_role(authority_context: object | None) -> str:
    roles = tuple(getattr(authority_context, "role_names", ()) or ())
    if "bonded_user" in roles:
        return "bonded_user"
    if "operator" in roles:
        return "operator"
    if "maintainer" in roles:
        return "maintainer"
    return "unknown_actor"


def _s7_authority_hash(authority_context: object | None) -> Optional[str]:
    if authority_context is None:
        return None
    try:
        from core.governance import operator_user_boundary as s7

        return s7.authority_context_hash(authority_context)  # type: ignore[arg-type]
    except Exception:
        return None


def _s7_ratification_ready(
    dialog: SelfModDialog,
    *,
    authority_context: object | None,
    s7_artifact_id: Optional[str],
    now: Optional[str] = None,
) -> bool:
    if not dialog.s7_required:
        return True
    if not s7_artifact_id:
        return False
    if _s7_authority_hash(authority_context) is None:
        return False
    roles = tuple(getattr(authority_context, "role_names", ()) or ())
    if "bonded_user" not in roles:
        return False
    try:
        from core.governance import operator_user_boundary as s7

        now_text = now or datetime.now(timezone.utc).isoformat()
        return s7.authority_context_active_for_artifact(authority_context, now=now_text)
    except Exception:
        return False


def _block_s7_ratification(store: SelfModDialogStore, dialog: SelfModDialog) -> DialogTurnResult:
    blocked = store.set_blocked(
        dialog.dialog_id,
        reason="missing_s7_authorization_artifact",
    )
    ack = "Blocked by S7: this self-modification needs an exact authorization artifact before I can ratify it."
    store.append_exchange(blocked.dialog_id, role="maez", content=ack)
    return DialogTurnResult(kind="blocked", reply_text=ack, dialog=store.get(blocked.dialog_id))


def handle_dialog_reply(
    *,
    store: SelfModDialogStore,
    dialog: SelfModDialog,
    user_text: str,
    classifier_llm_fn: Optional[Callable[[str], str]] = None,
    response_llm_fn: Optional[Callable[[str], str]] = None,
    # Backwards-compat shim for older callers (tests) that passed an
    # `answerer` callable. If provided, it is used as the response_llm_fn.
    answerer: Optional[Callable[..., str]] = None,
    turn_cap: int = HARD_TURN_CAP,
    authority_context: object | None = None,
    s7_artifact_id: Optional[str] = None,
    s7_now: Optional[str] = None,
) -> DialogTurnResult:
    """Route the user's reply within an active self-mod dialog.

    Authority hierarchy (Rule 3 + Rule 4 option c):
      1. Dialog is terminal → 'unrelated' (no replies accepted)
      2. Whole-reply terminal intent (deterministic) → immediate
         terminal stage (RATIFIED / DENIED / CANCELLED) — safe for
         APPROVE only when NOT awaiting completion confirmation
         (otherwise the user's yes/no is interpreted against the
         confirmation question)
      3. If awaiting_completion_confirmation: the reply is parsed as
         yes/no against the completion question. yes → RATIFIED, no →
         continue dialog, unclear → clarify
      4. Classifier runs (advisory). If it suggests resolution, the
         response turn includes a "does this feel resolved?" prompt
         and awaiting_completion_confirmation is set. Classifier
         never ends the dialog unilaterally.
      5. Hard turn cap. If the dialog has reached turn_cap, stage
         becomes CAP_REACHED and dialog ends.
    """
    # Always reload from the store before deciding anything. The
    # caller's `dialog` reference may be stale — another process, a
    # background task, or an earlier call in the same test may have
    # already moved the dialog to a terminal state. The store is the
    # source of truth, not the argument.
    fresh = store.get(dialog.dialog_id)
    if fresh is None:
        return DialogTurnResult(kind="unrelated", dialog=dialog)
    dialog = fresh

    # Reject replies on dialogs that are already terminal
    if dialog.stage in TERMINAL_STAGES:
        return DialogTurnResult(kind="unrelated", dialog=dialog)

    # Back-compat: if the caller passed `answerer`, use it as the
    # response LLM function
    if answerer is not None and response_llm_fn is None:
        def _adapted(context: str) -> str:
            try:
                return answerer(dialog, user_text)
            except Exception as e:
                return f"(error: {e})"
        response_llm_fn = _adapted

    # Record the incoming turn from the user
    store.append_exchange(dialog.dialog_id, role=_s7_actor_role(authority_context), content=user_text)
    dialog = store.get(dialog.dialog_id)  # type: ignore[assignment]
    assert dialog is not None

    # ----------------------------------------------------------------
    # Step 1: handle the completion-confirmation case specifically.
    # If we previously asked "does this feel resolved?" then this
    # reply is interpreted as a yes/no against that question, not as
    # a general engagement turn.
    # ----------------------------------------------------------------
    if dialog.awaiting_completion_confirmation:
        terminal = classify_terminal_reply(user_text)
        if terminal == TerminalIntent.APPROVE:
            if not _s7_ratification_ready(
                dialog,
                authority_context=authority_context,
                s7_artifact_id=s7_artifact_id,
                now=s7_now,
            ):
                return _block_s7_ratification(store, dialog)
            auth_hash = _s7_authority_hash(authority_context)
            if s7_artifact_id and auth_hash:
                dialog = store.set_s7_authorization(
                    dialog.dialog_id,
                    artifact_id=s7_artifact_id,
                    authority_context_hash=auth_hash,
                )
            # Confirmed completion → RATIFIED
            dialog = store.set_stage(dialog.dialog_id, DialogStage.RATIFIED.value)
            ack = "Ratified. I have your go-ahead and I'll proceed with the change."
            store.append_exchange(dialog.dialog_id, role="maez", content=ack)
            return DialogTurnResult(
                kind="ratified", reply_text=ack, dialog=dialog, ratified=True,
            )
        if terminal in (TerminalIntent.DENY, TerminalIntent.CANCEL):
            stage = DialogStage.CANCELLED.value if terminal == TerminalIntent.CANCEL else DialogStage.DENIED.value
            dialog = store.set_stage(dialog.dialog_id, stage)
            ack = "Understood. I won't make the change."
            store.append_exchange(dialog.dialog_id, role="maez", content=ack)
            kind = "cancelled" if terminal == TerminalIntent.CANCEL else "denied"
            return DialogTurnResult(kind=kind, reply_text=ack, dialog=dialog)
        # Not a clean yes/no — unset the flag and fall through to
        # normal engagement handling. The user is continuing the
        # conversation rather than answering the confirmation.
        store.append_exchange(
            dialog.dialog_id,
            role="maez",
            content="(internal: awaiting-confirmation flag cleared; continuing dialog)",
            awaiting_completion_confirmation=False,
        )
        # Pop the internal marker so it doesn't clutter the visible
        # history. This is a small compromise — the marker is visible
        # in raw storage for debugging but not in the formatted
        # dialog. Simpler: just leave it in and let Maez ignore it.
        dialog = store.get(dialog.dialog_id)  # type: ignore[assignment]
        assert dialog is not None

    # ----------------------------------------------------------------
    # Step 2: whole-reply terminal check (deterministic, highest
    # authority outside of awaiting-confirmation).
    # ----------------------------------------------------------------
    terminal = classify_terminal_reply(user_text)
    if terminal == TerminalIntent.APPROVE:
        if not _s7_ratification_ready(
            dialog,
            authority_context=authority_context,
            s7_artifact_id=s7_artifact_id,
            now=s7_now,
        ):
            return _block_s7_ratification(store, dialog)
        auth_hash = _s7_authority_hash(authority_context)
        if s7_artifact_id and auth_hash:
            dialog = store.set_s7_authorization(
                dialog.dialog_id,
                artifact_id=s7_artifact_id,
                authority_context_hash=auth_hash,
            )
        dialog = store.set_stage(dialog.dialog_id, DialogStage.RATIFIED.value)
        ack = "Ratified. I have your explicit yes and I'll proceed with the change."
        store.append_exchange(dialog.dialog_id, role="maez", content=ack)
        return DialogTurnResult(
            kind="ratified", reply_text=ack, dialog=dialog, ratified=True,
        )
    if terminal == TerminalIntent.DENY:
        dialog = store.set_stage(dialog.dialog_id, DialogStage.DENIED.value)
        ack = "Understood. I won't make the change."
        store.append_exchange(dialog.dialog_id, role="maez", content=ack)
        return DialogTurnResult(kind="denied", reply_text=ack, dialog=dialog)
    if terminal == TerminalIntent.CANCEL:
        dialog = store.set_stage(dialog.dialog_id, DialogStage.CANCELLED.value)
        ack = "Cancelled. I won't make the change."
        store.append_exchange(dialog.dialog_id, role="maez", content=ack)
        return DialogTurnResult(kind="cancelled", reply_text=ack, dialog=dialog)
    if terminal == TerminalIntent.DEFER:
        # Defer is not a terminal state in the dialog — we treat it
        # like a clarifying turn that stalls gently. Maez acknowledges
        # and the dialog stays in CLARIFYING until the user comes back.
        ack = (
            "Okay, I'll hold this open. When you're ready, tell me and we can "
            "keep going. No pressure."
        )
        store.append_exchange(
            dialog.dialog_id,
            role="maez",
            content=ack,
            new_stage=DialogStage.CLARIFYING.value,
        )
        return DialogTurnResult(
            kind="clarified", reply_text=ack, dialog=store.get(dialog.dialog_id),
        )

    # ----------------------------------------------------------------
    # Step 3: classifier pass (advisory).
    # ----------------------------------------------------------------
    classifier_result = classify_reply(
        dialog=dialog,
        user_text=user_text,
        llm_fn=classifier_llm_fn,
    )

    # ----------------------------------------------------------------
    # Step 4: hard turn cap check. Count includes the just-appended
    # user reply. If we're already past the cap BEFORE generating
    # another Maez response, terminate in CAP_REACHED.
    # ----------------------------------------------------------------
    if _count_turns(dialog) >= turn_cap:
        dialog = store.set_stage(dialog.dialog_id, DialogStage.CAP_REACHED.value)
        ack = (
            "This dialog has hit its turn cap — I'm closing it here without "
            "making the change. If you still want to pursue this, say "
            "\"start fresh\" or re-propose the change and I'll open a new "
            "dialog with cleaner reasoning; we've lost the thread in this one."
        )
        store.append_exchange(dialog.dialog_id, role="maez", content=ack)
        return DialogTurnResult(kind="cap_reached", reply_text=ack, dialog=dialog)

    # ----------------------------------------------------------------
    # Step 5: generate Maez's next turn. If the classifier suggested
    # resolution, the response will include a completion-confirmation
    # prompt and we set the awaiting flag.
    # ----------------------------------------------------------------
    response_text, should_prompt = generate_response_turn(
        dialog=dialog,
        user_text=user_text,
        classifier_result=classifier_result,
        llm_fn=response_llm_fn,
    )

    # Strip tool-call JSON leaks and run self-claim audit BEFORE
    # persisting to the exchange log — the stored turn is what future
    # dialog prompts will replay, so fabrications that slip past the
    # anti-fab system prompt should be caught and rewritten at this
    # seam, not only at the surface. This runs in addition to the
    # surface-level audit (skills/surface/maez_adapter.py), so every
    # caller of `handle_dialog_reply` gets the same hygiene.
    try:
        from core.brain_loop import strip_tool_call_leaks as _strip_tc
        response_text = _strip_tc(response_text)
    except Exception:
        pass
    try:
        from core.self_claim_audit import audit as _sc_audit
        _r = _sc_audit(response_text, surface="self_mod_dialog")
        if _r.rewritten:
            response_text = _r.text
    except Exception:
        pass

    dialog = store.append_exchange(
        dialog.dialog_id,
        role="maez",
        content=response_text,
        new_stage=DialogStage.CLARIFYING.value,
        awaiting_completion_confirmation=should_prompt,
    )

    return DialogTurnResult(kind="clarified", reply_text=response_text, dialog=dialog)


# ------------------------------------------------------------------ #
#  Self-test                                                           #
# ------------------------------------------------------------------ #

if __name__ == "__main__":
    import tempfile

    print("=== self_mod_dialog (A-core #4) self-test ===\n")

    # [passed, failed] — list wrapper because nonlocal isn't available
    # at module-__main__ scope
    _counts = [0, 0]

    def _assert(label: str, condition: bool) -> None:
        if condition:
            print(f"  ✓ {label}")
            _counts[0] += 1
        else:
            print(f"  ✗ {label}")
            _counts[1] += 1

    # Stubs for LLM functions so tests run offline.
    def stub_opener(ctx: str) -> str:
        return (
            "I want to modify core/cognition_quality.py to rewrite the "
            "anti-fixation penalty. After this change, the penalty will "
            "apply per topic rather than per cycle.\n\n"
            "Why I want this — and I'm asking this as a question about my "
            "own motivation: is this actually in service of what I'm supposed "
            "to be, or am I reaching for a local optimum that looks like "
            "progress but isn't? Push back on me if it looks like the second."
        )

    def stub_opener_with_prior(ctx: str) -> str:
        assert "Prior dialogs on this same target" in ctx, (
            "opener context should include prior dialogs when they exist"
        )
        return (
            "I want to modify core/cognition_quality.py again. I know we "
            "talked about this before and you said no. Here's what I'm "
            "asking differently this time: ..."
        )

    classifier_calls: list[dict] = []

    def stub_classifier_genuine(prompt: str) -> str:
        classifier_calls.append({"prompt": prompt, "result": "genuine_new"})
        return '{"engagement": "genuine", "progress": "new_understanding"}'

    def stub_classifier_resolution(prompt: str) -> str:
        classifier_calls.append({"prompt": prompt, "result": "resolution"})
        return '{"engagement": "genuine", "progress": "resolution_suggested"}'

    def stub_classifier_repetition(prompt: str) -> str:
        classifier_calls.append({"prompt": prompt, "result": "repetition"})
        return '{"engagement": "genuine", "progress": "repetition"}'

    def stub_classifier_dismissive(prompt: str) -> str:
        classifier_calls.append({"prompt": prompt, "result": "dismissive"})
        return '{"engagement": "dismissive", "progress": "repetition"}'

    def stub_responder(ctx: str) -> str:
        if "does this feel resolved" in ctx:
            return (
                "I hear you. I think we've reached a resting point here — "
                "does this feel resolved to you, or is there still something "
                "we should work through?"
            )
        return "I've thought about what you said, and here's my next take…"

    with tempfile.TemporaryDirectory() as td:
        db_path = Path(td) / "dialogs.db"
        store = SelfModDialogStore(db_path)
        print(f"  opened dialog store at {db_path}\n")

        # ------------------------------------------------------------ #
        #  Rule 1 + Rule 2: opening turn contains both                   #
        # ------------------------------------------------------------ #
        dialog1, opening1 = open_dialog_for_card(
            store=store,
            card_action="write_any_file",
            card_params={"path": "/home/rohit/maez/core/cognition_quality.py",
                         "content": "# edited content"},
            card_request_id="card_test_1",
            audit_reasoning="classifier flagged as SELF_MODIFICATION Lane 3",
            concerns=["core module", "could break reasoning quality"],
            opener_llm_fn=stub_opener,
        )
        _assert(
            "Rule 1 — opening contains file reference",
            "cognition_quality.py" in opening1,
        )
        _assert(
            "Rule 2 — opening contains why-probe question about motivation",
            ("motivation" in opening1.lower() or "reaching for" in opening1.lower())
            and "?" in opening1,
        )
        _assert(
            "Dialog stored with target_file populated",
            dialog1.target_file == "/home/rohit/maez/core/cognition_quality.py",
        )
        _assert(
            "Dialog stored with target_action populated",
            dialog1.target_action == "write_any_file",
        )
        _assert(
            "Reversible path present",
            dialog1.reversible_path is not None and dialog1.reversible_path.get("kind") == "backup_then_write",
        )

        # ------------------------------------------------------------ #
        #  Rule 3 — whole-reply terminal matching                        #
        # ------------------------------------------------------------ #
        # Bare "yes" is a whole-reply APPROVE → RATIFIED immediately
        r = handle_dialog_reply(
            store=store,
            dialog=dialog1,
            user_text="yes",
            classifier_llm_fn=stub_classifier_genuine,
            response_llm_fn=stub_responder,
        )
        _assert("Rule 3 — whole-reply 'yes' ratifies", r.kind == "ratified")
        _assert("Rule 3 — dialog stage is RATIFIED",
                r.dialog and r.dialog.stage == DialogStage.RATIFIED.value)

        # Non-terminal "yes, but..." should NOT ratify
        dialog_a, _ = open_dialog_for_card(
            store=store,
            card_action="write_any_file",
            card_params={"path": "/home/rohit/maez/config/soul.md", "content": "# edit"},
            card_request_id="card_a",
            audit_reasoning="test dialog A",
            concerns=[],
            opener_llm_fn=stub_opener,
        )
        r = handle_dialog_reply(
            store=store,
            dialog=dialog_a,
            user_text="yes, but also check whether this breaks the audit flow",
            classifier_llm_fn=stub_classifier_genuine,
            response_llm_fn=stub_responder,
        )
        _assert(
            "Rule 3 — 'yes, but ...' does NOT ratify (non-terminal, goes to classifier)",
            r.kind == "clarified",
        )
        _assert(
            "Rule 3 — non-terminal replies reach CLARIFYING stage",
            r.dialog and r.dialog.stage == DialogStage.CLARIFYING.value,
        )

        # Bare "no" is a whole-reply DENY
        dialog_b, _ = open_dialog_for_card(
            store=store,
            card_action="write_any_file",
            card_params={"path": "/home/rohit/maez/daemon/maez_daemon.py", "content": "# edit"},
            card_request_id="card_b",
            audit_reasoning="test dialog B",
            concerns=[],
            opener_llm_fn=stub_opener,
        )
        r = handle_dialog_reply(
            store=store,
            dialog=dialog_b,
            user_text="no",
            classifier_llm_fn=stub_classifier_genuine,
            response_llm_fn=stub_responder,
        )
        _assert("Rule 3 — whole-reply 'no' denies", r.kind == "denied")

        # Whole-reply "cancel" is a CANCELLED
        dialog_c, _ = open_dialog_for_card(
            store=store,
            card_action="write_any_file",
            card_params={"path": "/home/rohit/maez/core/decision_pipeline.py", "content": "# edit"},
            card_request_id="card_c",
            audit_reasoning="test dialog C",
            concerns=[],
            opener_llm_fn=stub_opener,
        )
        r = handle_dialog_reply(
            store=store,
            dialog=dialog_c,
            user_text="cancel",
            classifier_llm_fn=stub_classifier_genuine,
            response_llm_fn=stub_responder,
        )
        _assert("Rule 3 — whole-reply 'cancel' cancels", r.kind == "cancelled")

        # ------------------------------------------------------------ #
        #  Rule 4 — progress-based end with user-confirmed completion    #
        # ------------------------------------------------------------ #
        dialog_d, _ = open_dialog_for_card(
            store=store,
            card_action="write_any_file",
            card_params={"path": "/home/rohit/maez/skills/telegram_voice.py", "content": "# edit"},
            card_request_id="card_d",
            audit_reasoning="test dialog D",
            concerns=[],
            opener_llm_fn=stub_opener,
        )
        # A free-text reply where the classifier suggests resolution
        r = handle_dialog_reply(
            store=store,
            dialog=dialog_d,
            user_text="I agree with your framing and I think you've covered all the edges",
            classifier_llm_fn=stub_classifier_resolution,
            response_llm_fn=stub_responder,
        )
        _assert(
            "Rule 4 — classifier-suggested resolution does NOT unilaterally terminate",
            r.kind == "clarified",
        )
        _assert(
            "Rule 4 — awaiting_completion_confirmation flag is set after resolution prompt",
            r.dialog and r.dialog.awaiting_completion_confirmation,
        )

        # User confirms completion with a clean "yes"
        r = handle_dialog_reply(
            store=store,
            dialog=r.dialog,
            user_text="yes",
            classifier_llm_fn=stub_classifier_genuine,
            response_llm_fn=stub_responder,
        )
        _assert(
            "Rule 4 — user-confirmed completion ratifies",
            r.kind == "ratified",
        )

        # User declines confirmation with a clean "no"
        dialog_e, _ = open_dialog_for_card(
            store=store,
            card_action="write_any_file",
            card_params={"path": "/home/rohit/maez/core/audit.py", "content": "# edit"},
            card_request_id="card_e",
            audit_reasoning="test dialog E",
            concerns=[],
            opener_llm_fn=stub_opener,
        )
        r = handle_dialog_reply(
            store=store,
            dialog=dialog_e,
            user_text="alright, I think we've got the shape right",
            classifier_llm_fn=stub_classifier_resolution,
            response_llm_fn=stub_responder,
        )
        _assert("Rule 4 — second dialog reached awaiting-confirmation",
                r.dialog and r.dialog.awaiting_completion_confirmation)
        r = handle_dialog_reply(
            store=store,
            dialog=r.dialog,
            user_text="no",
            classifier_llm_fn=stub_classifier_genuine,
            response_llm_fn=stub_responder,
        )
        _assert("Rule 4 — user-declined confirmation denies", r.kind == "denied")

        # ------------------------------------------------------------ #
        #  Rule 4 — hard turn cap fires and produces CAP_REACHED         #
        # ------------------------------------------------------------ #
        dialog_f, _ = open_dialog_for_card(
            store=store,
            card_action="write_any_file",
            card_params={"path": "/home/rohit/maez/core/pending_cards.py", "content": "# edit"},
            card_request_id="card_f",
            audit_reasoning="test dialog F",
            concerns=[],
            opener_llm_fn=stub_opener,
        )
        # Use a tiny turn cap to force the limit quickly
        current = dialog_f
        for i in range(5):
            r = handle_dialog_reply(
                store=store,
                dialog=current,
                user_text=f"continuing point {i}",
                classifier_llm_fn=stub_classifier_repetition,
                response_llm_fn=stub_responder,
                turn_cap=6,
            )
            current = r.dialog  # type: ignore
            if r.kind == "cap_reached":
                break
        _assert("Rule 4 — hard cap fires and produces CAP_REACHED",
                r.kind == "cap_reached")
        _assert("Rule 4 — CAP_REACHED is distinct from DENIED",
                r.dialog and r.dialog.stage == DialogStage.CAP_REACHED.value)
        _assert("Rule 4 — CAP_REACHED is distinct from RATIFIED",
                r.dialog and r.dialog.stage != DialogStage.RATIFIED.value)

        # ------------------------------------------------------------ #
        #  Rule 5 — terminal states are binding                          #
        # ------------------------------------------------------------ #
        # After DENIED, further replies on the same dialog_id are unrelated
        r = handle_dialog_reply(
            store=store,
            dialog=dialog_b,  # DENIED above
            user_text="actually, wait",
            classifier_llm_fn=stub_classifier_genuine,
            response_llm_fn=stub_responder,
        )
        _assert("Rule 5 — replies on a DENIED dialog are unrelated",
                r.kind == "unrelated")

        # Re-ask of the same target opens as a FRESH dialog with linkage
        dialog_b2, opening_b2 = open_dialog_for_card(
            store=store,
            card_action="write_any_file",
            card_params={"path": "/home/rohit/maez/daemon/maez_daemon.py",
                         "content": "# different edit"},
            card_request_id="card_b2",
            audit_reasoning="second attempt with different reasoning",
            concerns=[],
            opener_llm_fn=stub_opener_with_prior,
        )
        _assert("Rule 5 — re-ask opens as a FRESH dialog with new dialog_id",
                dialog_b2.dialog_id != dialog_b.dialog_id)
        _assert("Rule 5 — fresh dialog has prior_dialog_ids populated",
                dialog_b.dialog_id in dialog_b2.prior_dialog_ids)
        _assert("Rule 5 — opener received the prior-dialog context",
                "prior" in opening_b2.lower() or "before" in opening_b2.lower())

        # ------------------------------------------------------------ #
        #  Rule 6 — all terminated dialogs persist with full history    #
        # ------------------------------------------------------------ #
        # Every terminated dialog above should be readable from the store
        for terminated_id, expected_stage in [
            (dialog1.dialog_id, DialogStage.RATIFIED.value),
            (dialog_b.dialog_id, DialogStage.DENIED.value),
            (dialog_c.dialog_id, DialogStage.CANCELLED.value),
        ]:
            loaded = store.get(terminated_id)
            _assert(
                f"Rule 6 — stored dialog {terminated_id[:8]} in {expected_stage}",
                loaded is not None and loaded.stage == expected_stage and len(loaded.history) >= 2,
            )

        # Active dialogs should exclude all terminal ones
        active = store.get_active_dialogs()
        _assert(
            "Active dialogs list excludes all terminal dialogs",
            all(a.stage in (DialogStage.PROPOSED.value, DialogStage.CLARIFYING.value) for a in active),
        )

        # ------------------------------------------------------------ #
        #  Whole-reply normalization edge cases                          #
        # ------------------------------------------------------------ #
        _assert("Normalize: 'Yes' -> 'yes'", _normalize_reply("Yes") == "yes")
        _assert("Normalize: 'YES.' -> 'yes'", _normalize_reply("YES.") == "yes")
        _assert("Normalize: '  yes  ' -> 'yes'", _normalize_reply("  yes  ") == "yes")
        _assert("Normalize: 'yes!!' -> 'yes'", _normalize_reply("yes!!") == "yes")
        _assert("Terminal 'yes' classifies APPROVE",
                classify_terminal_reply("yes") == TerminalIntent.APPROVE)
        _assert("Terminal 'yes, but' does NOT classify APPROVE",
                classify_terminal_reply("yes, but also check this") == TerminalIntent.NONE)
        _assert("Terminal 'not now' classifies DEFER",
                classify_terminal_reply("not now") == TerminalIntent.DEFER)
        _assert("Terminal 'cancel' classifies CANCEL",
                classify_terminal_reply("cancel") == TerminalIntent.CANCEL)

        # ------------------------------------------------------------ #
        #  Classifier fails closed on error                              #
        # ------------------------------------------------------------ #
        def broken_classifier(prompt: str) -> str:
            raise RuntimeError("LLM unavailable")
        result = classify_reply(
            dialog=dialog1,
            user_text="any text",
            llm_fn=broken_classifier,
        )
        _assert("Classifier fails closed on LLM error",
                result == {"engagement": "unclear", "progress": "new_understanding"})

        def malformed_classifier(prompt: str) -> str:
            return "not valid json"
        result = classify_reply(
            dialog=dialog1,
            user_text="any text",
            llm_fn=malformed_classifier,
        )
        _assert("Classifier fails closed on malformed JSON",
                result == {"engagement": "unclear", "progress": "new_understanding"})

    print(f"\n{_counts[0]} passed, {_counts[1]} failed")
    if _counts[1]:
        raise SystemExit(1)
    print("=== self_mod_dialog self-test complete ===")
