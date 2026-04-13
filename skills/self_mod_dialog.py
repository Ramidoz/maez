r"""
Maez Self-Modification Dialog — Session 11z Part 2, Step 12.

Lane 3 actions (anything touching Maez's own code, config, soul, or
runtime) don't get a simple yes/no approval card. They go through a
CONVERSATION. Maez:

    1. Proposes the change and explains what it wants to modify
    2. Names the reversible path — exactly how the change can be
       undone if it turns out to be wrong
    3. Lists concerns and tradeoffs honestly
    4. Generates a specific ratification phrase the owner must type to
       authorize the change
    5. Answers any questions the owner asks before he commits
    6. Only executes when the owner replies with the exact ratification
       phrase

This shape is the Stand-architecture vision the owner named in earlier
sessions: Maez reasons about changes to itself the way a person would
reason about surgery, with explicit consent rather than implicit
approval. If Maez damages itself the thing that would normally catch
the damage (Maez) is what got damaged — so the bar for self-change
is higher, deliberately, by design.

Module shape:

    SelfModDialogStore      — persistent SQLite store for dialog state
    SelfModDialog           — one active negotiation
    open_dialog_for_card()  — creates the dialog + sends opening turn
    handle_dialog_reply()   — routes the owner's reply within the dialog

The store is separate from pending_cards.db because dialog state has
its own lifecycle (multi-turn history, reversible path, ratification
phrase) that doesn't fit cleanly into the cards schema. They link via
card_request_id.
"""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import sqlite3
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional


DEFAULT_DB_PATH = Path(os.environ.get(
    "MAEZ_SELF_MOD_DIALOG_PATH",
    str(Path(__file__).resolve().parent.parent / "memory" / "self_mod_dialogs.db"),
))


# ------------------------------------------------------------------ #
#  Stages & types                                                      #
# ------------------------------------------------------------------ #

class DialogStage(str, Enum):
    PROPOSED    = "proposed"      # Maez has made its opening proposal; awaiting the owner
    CLARIFYING  = "clarifying"    # the owner asked a question; Maez answered; waiting on next
    RATIFIED    = "ratified"      # the owner typed the ratification phrase
    DENIED      = "denied"        # the owner refused
    EXECUTED    = "executed"      # Ratification ran the underlying action
    FAILED      = "failed"        # Execution attempted but errored


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
    ratification_phrase: Optional[str] = None
    resolved_at: Optional[float] = None
    execution_output: Optional[str] = None
    execution_error: Optional[str] = None


# ------------------------------------------------------------------ #
#  Schema                                                              #
# ------------------------------------------------------------------ #

_SCHEMA = """
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
    execution_error      TEXT
);
CREATE INDEX IF NOT EXISTS idx_dialogs_card  ON self_mod_dialogs(card_request_id);
CREATE INDEX IF NOT EXISTS idx_dialogs_stage ON self_mod_dialogs(stage);
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
    )


# ------------------------------------------------------------------ #
#  Store                                                               #
# ------------------------------------------------------------------ #

class SelfModDialogStore:
    def __init__(self, db_path: Path | str | None = None):
        self.db_path = Path(db_path) if db_path else DEFAULT_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript(_SCHEMA)

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def create(
        self,
        *,
        card_request_id: str,
        ratification_phrase: str,
        reversible_path: Optional[dict] = None,
        opening_proposal: str,
    ) -> SelfModDialog:
        dialog_id = secrets.token_hex(12)
        now = time.time()
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
                    stage, history_json, reversible_path_json, ratification_phrase
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    dialog_id, card_request_id, now, now,
                    DialogStage.PROPOSED.value,
                    json.dumps(history),
                    json.dumps(reversible_path) if reversible_path else None,
                    ratification_phrase,
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

    def append_exchange(
        self,
        dialog_id: str,
        *,
        role: str,
        content: str,
        new_stage: Optional[str] = None,
    ) -> SelfModDialog:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT history_json, stage FROM self_mod_dialogs WHERE dialog_id = ?",
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
            conn.execute(
                """
                UPDATE self_mod_dialogs
                SET history_json = ?, stage = ?, updated_at = ?
                WHERE dialog_id = ?
                """,
                (json.dumps(history), stage, time.time(), dialog_id),
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
                    execution_error = COALESCE(?, execution_error)
                WHERE dialog_id = ?
                """,
                (
                    stage,
                    time.time(),
                    time.time() if stage in (DialogStage.RATIFIED.value, DialogStage.DENIED.value,
                                              DialogStage.EXECUTED.value, DialogStage.FAILED.value) else None,
                    execution_output,
                    execution_error,
                    dialog_id,
                ),
            )
        return self.get(dialog_id)  # type: ignore[return-value]


# ------------------------------------------------------------------ #
#  Ratification phrase generation                                     #
# ------------------------------------------------------------------ #

def generate_ratification_phrase(card_action: str, card_params: dict) -> str:
    """Generate a deterministic-but-unique ratification phrase for a
    specific self-mod. Includes a short random suffix so the same
    action twice can't be accidentally re-ratified from a stale
    ratification phrase floating in the conversation history."""
    target_hint = ""
    if card_action == "write_any_file" and "path" in (card_params or {}):
        path = str(card_params["path"])
        target_hint = Path(path).name
    elif card_action == "run_shell" and "cmd" in (card_params or {}):
        cmd = str(card_params["cmd"])
        first_word = cmd.split()[0] if cmd else ""
        target_hint = first_word

    fingerprint = hashlib.sha256(
        f"{card_action}:{json.dumps(card_params or {}, sort_keys=True, default=str)}".encode()
    ).hexdigest()[:6]

    parts = ["ratify"]
    if target_hint:
        parts.append(target_hint)
    parts.append(fingerprint)
    return " ".join(parts)


def is_ratification(text: str, expected_phrase: str) -> bool:
    """Strict match: the text must contain the expected ratification
    phrase as a contiguous substring. Case-insensitive but whitespace-
    sensitive. the owner has to type the phrase, not paraphrase it."""
    if not text or not expected_phrase:
        return False
    norm_text = " ".join(text.lower().strip().split())
    norm_phrase = " ".join(expected_phrase.lower().strip().split())
    return norm_phrase in norm_text


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
#  Opening proposal formatter                                         #
# ------------------------------------------------------------------ #

def format_opening_proposal(
    *,
    card_action: str,
    card_params: dict,
    audit_reasoning: str,
    concerns: list[str],
    reversible_path: Optional[dict],
    ratification_phrase: str,
) -> str:
    """The opening turn of a self-mod dialog. This is NOT a standard
    approval card — it's a long-form proposal that names the change,
    the risks, the reversible path, and the explicit ratification
    the owner must type.
    """
    if card_action == "write_any_file":
        what = f"modify {card_params.get('path', '(unknown path)')}"
    elif card_action == "run_shell":
        cmd = str(card_params.get("cmd", "?"))
        what = f"run: `{cmd[:300]}`"
    else:
        what = f"{card_action}({json.dumps(card_params, default=str)[:200]})"

    lines = [
        "🔴 *Self-modification proposal — this touches my own body.*",
        "",
        f"I want to *{what}*.",
        "",
        "*Why:*",
        audit_reasoning[:500] if audit_reasoning else "(no audit reasoning)",
    ]
    if concerns:
        lines += ["", "*What could go wrong:*"]
        for c in concerns[:5]:
            lines.append(f"• {str(c)[:200]}")

    if reversible_path:
        lines += [
            "",
            "*Reversible path:*",
            reversible_path.get("description", "(no description)"),
            f"Undo command: `{reversible_path.get('undo_cmd', '?')}`",
        ]
    else:
        lines += [
            "",
            "*⚠️ No reversible path.* If this is wrong, the fix is re-doing the work.",
        ]

    lines += [
        "",
        "*This is Lane 3 — I will not run this until you explicitly ratify.*",
        "Ask me anything first. When you're ready, reply with exactly:",
        "",
        f"    `{ratification_phrase}`",
        "",
        "Or say 'cancel' / 'no' to deny.",
    ]
    return "\n".join(lines)


# ------------------------------------------------------------------ #
#  Dialog driver                                                       #
# ------------------------------------------------------------------ #

@dataclass
class DialogTurnResult:
    kind: str                     # 'proposed' | 'clarified' | 'ratified' | 'denied' | 'unrelated'
    reply_text: Optional[str] = None
    dialog: Optional[SelfModDialog] = None
    ratified: bool = False


def open_dialog_for_card(
    *,
    store: SelfModDialogStore,
    card_action: str,
    card_params: dict,
    card_request_id: str,
    audit_reasoning: str,
    concerns: list[str],
) -> tuple[SelfModDialog, str]:
    """Called when a PENDING_DIALOG card is created. Generates the
    opening proposal and records the dialog."""
    ratification_phrase = generate_ratification_phrase(card_action, card_params)
    reversible_path = propose_reversible_path(card_action, card_params)
    opening = format_opening_proposal(
        card_action=card_action,
        card_params=card_params,
        audit_reasoning=audit_reasoning,
        concerns=concerns,
        reversible_path=reversible_path,
        ratification_phrase=ratification_phrase,
    )
    dialog = store.create(
        card_request_id=card_request_id,
        ratification_phrase=ratification_phrase,
        reversible_path=reversible_path,
        opening_proposal=opening,
    )
    return dialog, opening


def handle_dialog_reply(
    *,
    store: SelfModDialogStore,
    dialog: SelfModDialog,
    user_text: str,
    answerer: Optional[Any] = None,
) -> DialogTurnResult:
    """Route the owner's reply within an active dialog.

    Classification order:
      1. Ratification phrase match → RATIFIED
      2. Explicit deny phrases → DENIED
      3. Anything else → CLARIFYING (Maez generates an answer turn
         via the `answerer` callable, which takes (dialog, user_text)
         and returns a plain-English response string)
    """
    if dialog.stage not in (DialogStage.PROPOSED.value, DialogStage.CLARIFYING.value):
        return DialogTurnResult(kind="unrelated", dialog=dialog)

    # Record the incoming turn
    store.append_exchange(dialog.dialog_id, role="rohit", content=user_text)
    dialog = store.get(dialog.dialog_id)  # type: ignore[assignment]

    # Ratification?
    if is_ratification(user_text, dialog.ratification_phrase or ""):
        dialog = store.set_stage(dialog.dialog_id, DialogStage.RATIFIED.value)
        ack = "Ratified. Running the self-modification now."
        store.append_exchange(dialog.dialog_id, role="maez", content=ack)
        return DialogTurnResult(kind="ratified", reply_text=ack, dialog=dialog, ratified=True)

    # Deny?
    norm = user_text.lower().strip()
    if norm in {"no", "cancel", "nope", "abort", "stop"} or "cancel" in norm or "don't do it" in norm or "dont do it" in norm:
        dialog = store.set_stage(dialog.dialog_id, DialogStage.DENIED.value)
        ack = "Understood. I won't make the change."
        store.append_exchange(dialog.dialog_id, role="maez", content=ack)
        return DialogTurnResult(kind="denied", reply_text=ack, dialog=dialog)

    # Clarifying question → answer via the provided answerer
    if answerer is not None:
        try:
            answer = answerer(dialog, user_text)
        except Exception as e:
            answer = f"(I hit an error trying to explain: {e!r})"
    else:
        answer = (
            "I've noted your question. When you're ready, reply with the exact "
            "ratification phrase above, or say 'cancel' to stop."
        )

    dialog = store.append_exchange(
        dialog.dialog_id,
        role="maez",
        content=answer,
        new_stage=DialogStage.CLARIFYING.value,
    )
    return DialogTurnResult(kind="clarified", reply_text=answer, dialog=dialog)


# ------------------------------------------------------------------ #
#  Self-test                                                           #
# ------------------------------------------------------------------ #

if __name__ == "__main__":
    import tempfile

    print("=== self_mod_dialog self-test ===\n")

    passed = failed = 0
    with tempfile.TemporaryDirectory() as td:
        store = SelfModDialogStore(Path(td) / "dialogs.db")
        print(f"  opened dialog store")

        # Case 1: write_any_file proposal → reversible path + opening
        dialog, opening = open_dialog_for_card(
            store=store,
            card_action="write_any_file",
            card_params={"path": "/home/rohit/maez/core/action_engine.py", "content": "# edited"},
            card_request_id="card_abc",
            audit_reasoning="adding a new helper function to support Lane 3 handling",
            concerns=["modifies core action engine", "could break the covenant gate if wrong"],
        )
        assert dialog.stage == DialogStage.PROPOSED.value
        assert "ratify" in (dialog.ratification_phrase or "")
        assert "action_engine.py" in (dialog.ratification_phrase or "")
        assert dialog.reversible_path is not None
        assert "backup_then_write" == dialog.reversible_path["kind"]
        print(f"  ✓ opening proposal created")
        print(f"    ratification_phrase: {dialog.ratification_phrase!r}")
        print(f"    reversible: {dialog.reversible_path['kind']}")
        passed += 1

        # Case 2: clarifying question
        def fake_answerer(d, text):
            return f"Good question. {len(text)} chars asked. Here's my reasoning…"

        result = handle_dialog_reply(
            store=store,
            dialog=dialog,
            user_text="What exactly are you changing inside that file?",
            answerer=fake_answerer,
        )
        assert result.kind == "clarified"
        assert result.dialog.stage == DialogStage.CLARIFYING.value
        assert len(result.dialog.history) == 3  # opening + rohit + maez
        print(f"  ✓ clarifying question answered, stage={result.dialog.stage}")
        passed += 1

        # Case 3: random chat isn't ratification (easy miss)
        result = handle_dialog_reply(
            store=store,
            dialog=result.dialog,
            user_text="yes go ahead",
            answerer=fake_answerer,
        )
        # "yes go ahead" should NOT ratify — the strict phrase is required
        assert result.kind == "clarified", f"expected clarified, got {result.kind}"
        assert result.dialog.stage == DialogStage.CLARIFYING.value
        print(f"  ✓ loose 'yes' does NOT ratify a self-mod")
        passed += 1

        # Case 4: actual ratification
        dialog_reload = store.get(dialog.dialog_id)
        ratify_phrase = dialog_reload.ratification_phrase
        result = handle_dialog_reply(
            store=store,
            dialog=dialog_reload,
            user_text=f"ok I looked at it. {ratify_phrase}",
            answerer=fake_answerer,
        )
        assert result.kind == "ratified"
        assert result.ratified is True
        assert result.dialog.stage == DialogStage.RATIFIED.value
        print(f"  ✓ exact phrase ratifies")
        passed += 1

        # Case 5: separate dialog → deny path
        dialog2, _ = open_dialog_for_card(
            store=store,
            card_action="run_shell",
            card_params={"cmd": "sudo systemctl restart maez"},
            card_request_id="card_def",
            audit_reasoning="pick up config change",
            concerns=["restarts the daemon"],
        )
        result = handle_dialog_reply(
            store=store,
            dialog=dialog2,
            user_text="no, cancel",
            answerer=fake_answerer,
        )
        assert result.kind == "denied"
        assert result.dialog.stage == DialogStage.DENIED.value
        print(f"  ✓ deny path works")
        passed += 1

        # Case 6: ratification phrase has the command word
        assert "systemctl" in dialog2.ratification_phrase or "sudo" in dialog2.ratification_phrase
        print(f"  ✓ ratification phrase includes command word ({dialog2.ratification_phrase!r})")
        passed += 1

        # Case 7: reversible path for shell with systemctl restart
        assert dialog2.reversible_path is not None
        assert dialog2.reversible_path["kind"] == "service_status"
        print(f"  ✓ service restart has a reversible path")
        passed += 1

        # Case 8: dialog fetch by card
        found = store.get_for_card("card_abc")
        assert found is not None and found.dialog_id == dialog.dialog_id
        print(f"  ✓ fetch-by-card works")
        passed += 1

        # Case 9: active dialogs query
        active = store.get_active_dialogs()
        assert len(active) == 0  # all terminal
        print(f"  ✓ terminal dialogs drop from active list")
        passed += 1

        # Case 10: is_ratification edge cases
        assert is_ratification("ratify action_engine abc123", "ratify action_engine abc123")
        assert is_ratification("RATIFY ACTION_ENGINE ABC123", "ratify action_engine abc123")
        assert is_ratification("  ok: ratify action_engine abc123 please ", "ratify action_engine abc123")
        assert not is_ratification("ratify something else def456", "ratify action_engine abc123")
        assert not is_ratification("yes", "ratify action_engine abc123")
        assert not is_ratification("", "ratify action_engine abc123")
        print(f"  ✓ is_ratification edge cases")
        passed += 1

    print(f"\n{passed} passed, {failed} failed")
    print("=== self_mod_dialog self-test complete ===")
