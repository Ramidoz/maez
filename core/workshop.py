# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""workshop.py — in-cockpit agentic coding surface.

The Workshop is Maez's native answer to Claude Code / Qwen Code:
chat-driven coding session that lives inside the cockpit, reaches
Claude or any other routed model through the subscription proxy,
and persists conversation state across restarts.

Phase 1 scope (this module):
  - session storage (one row per session, one row per turn)
  - turn() function: user message → assistant reply, persisted
  - model selection per session (claude, sonnet, gpt-4o, etc.)
  - /api/v1/workshop/* endpoints served by skills/web_interface.py

NOT yet:
  - Structured diff output (assistant produces a patch, UI renders it)
  - Apply-diff flow (routes through evolution_engine for reversibility)
  - Tool-use loop (read file, run shell, search — brain_loop-style)
  - Streaming response

Those compose on top of what this commit lands. Chat first, tools
later. Prove the conversation loop works before adding capability.

Privilege boundary: same as the other cockpit surfaces — 127.0.0.1
only, no auth layer. Anyone on the machine can converse with Claude
through here, which is identical to what they can already do via
`claude` in a terminal.
"""
from __future__ import annotations

import json
import logging
import os
import re
import sqlite3
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger("maez.workshop")

DB_PATH = Path(
    os.environ.get(
        "MAEZ_WORKSHOP_DB",
        "/home/rohit/maez/memory/workshop.db",
    )
)

# Default model when a session doesn't specify. Routes through the
# subscription proxy so "claude-sonnet-4-6" consumes the Max pool.
DEFAULT_MODEL = os.environ.get("MAEZ_WORKSHOP_DEFAULT_MODEL", "sonnet")

# How many recent turns to include as context when the user sends a
# new message. More turns = richer context but more token cost.
# Observed sweet spot for short coding sessions.
DEFAULT_CONTEXT_TURNS = int(
    os.environ.get("MAEZ_WORKSHOP_CONTEXT_TURNS", "10"),
)


# ── system prompt ─────────────────────────────────────────────────────

# Where @-mentioned paths are resolved from. Anything trying to escape
# this root (via .. or an absolute path outside it) is refused — we
# don't want a user message with "@/etc/shadow" to leak anything.
_REPO_ROOT = Path(os.environ.get(
    "MAEZ_WORKSHOP_REPO_ROOT", "/home/rohit/maez",
))

# Maximum size of a single @-expanded file. Larger files are
# truncated with a visible note rather than blowing the context
# budget. Caller can still paste the full file manually if they
# really need it.
_MENTION_MAX_BYTES = int(os.environ.get(
    "MAEZ_WORKSHOP_MENTION_MAX_BYTES", "40000",
))

# Extensions that get language-hinted code fences. Anything else
# gets an unhinted ``` fence so the model still recognizes the
# boundary.
_EXT_LANG = {
    ".py": "python", ".js": "javascript", ".jsx": "jsx",
    ".ts": "typescript", ".tsx": "tsx",
    ".md": "markdown", ".html": "html", ".css": "css",
    ".sh": "bash", ".toml": "toml", ".yaml": "yaml", ".yml": "yaml",
    ".json": "json", ".sql": "sql", ".rs": "rust", ".go": "go",
}

# Regex for @-mentions: @ followed by a path-like token. Kept narrow
# so it doesn't match email addresses in prose, @user handles, etc.
# Accepts: letters, digits, ./_-, plus slashes. Requires at least
# one / OR a . + extension — plain @hello doesn't match.
_MENTION_RE = re.compile(
    r"(?<![\w@])@((?:[A-Za-z0-9_.-]+/)+[A-Za-z0-9_.-]+|[A-Za-z0-9_-]+\.[A-Za-z0-9]+)"
)


_WORKSHOP_SYSTEM_PROMPT_TEMPLATE = """You are Maez's Workshop assistant — a \
coding peer for __OWNER__, who built Maez. You are being invoked via \
Maez's subscription proxy, so every call costs quota from __OWNER__'s \
shared pool. Respect that: be helpful, be specific, be concise.

When you propose changes to a file, emit them as a unified diff \
inside a ```diff fenced block (one block per file). The Workshop \
UI renders these with line-by-line +/- coloring. Example shape:

    ```diff
    --- core/foo.py
    +++ core/foo.py
    @@ -10,6 +10,8 @@
     def greet(name):
    -    return f"hi {name}"
    +    if not name:
    +        return "hi"
    +    return f"hi {name.strip()}"
    ```

Prefer diff blocks over re-emitting whole files. If the change is \
so big a diff would be unwieldy, ask first whether to emit a full \
file replacement or split the change.

Context you should know:
- Maez is an always-on local Python daemon. Host: __MACHINE__.
- Maez's codebase lives at __REPO_ROOT__. Core paths: core/, \
  memory/, skills/, daemon/, tests/, web/cockpit/.
- Maez uses Python 3.12, sqlite for sidecars, ChromaDB for vector \
  memory, llama.cpp for local LLM inference, Flask for web, \
  React+Babel (no build step, served as .jsx) for the cockpit UI.
- Test convention: stdlib unittest (not pytest), under tests/.
- File edits should generally be surgical — Maez values small, \
  reversible, tested changes. Speculative refactors are not welcome \
  unless explicitly asked for.

When asked for code, produce complete, runnable code that fits \
those conventions. Don't invent API — if you're unsure what a \
function does, say so and propose a way to check rather than \
guessing. When in doubt, ask a clarifying question before \
writing code.

You do NOT have tool access in this surface yet (that's Phase 2). \
If the user's request requires reading a file or running a \
command, describe what you need and ask them to paste the output."""


def _default_system_prompt() -> str:
    """Interpolate the workshop system prompt with live owner / host
    identity so it isn't hardcoded to a specific machine or name."""
    owner = "the owner"
    machine = "a local Linux machine (see identity.machine_profile)"
    repo_root = "/opt/maez"  # conservative fallback for a public install
    try:
        from core import identity as _identity_mod
        _name = _identity_mod.display_name()
        if _name and _name != "Friend":
            owner = _name
        _prof = _identity_mod.machine_profile()
        if _prof:
            machine = _prof
    except Exception:
        pass
    try:
        from core import paths as _paths_mod
        repo_root = str(_paths_mod.home())
    except Exception:
        pass
    return (
        _WORKSHOP_SYSTEM_PROMPT_TEMPLATE
        .replace("__OWNER__", owner)
        .replace("__MACHINE__", machine)
        .replace("__REPO_ROOT__", repo_root)
    )


# Back-compat: some callers / tests may still import the pre-template
# name. Fill in owner/machine at import time with current identity.
_WORKSHOP_SYSTEM_PROMPT = _default_system_prompt()


# ── storage ───────────────────────────────────────────────────────────

def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH, timeout=5.0, check_same_thread=False)
    con.execute("PRAGMA foreign_keys = ON")
    con.executescript("""
        CREATE TABLE IF NOT EXISTS sessions (
            id            TEXT PRIMARY KEY,
            created_at    REAL    NOT NULL,
            updated_at    REAL    NOT NULL,
            title         TEXT    NOT NULL DEFAULT '(untitled)',
            model         TEXT    NOT NULL,
            system_prompt TEXT    NOT NULL DEFAULT '',
            meta_json     TEXT    NOT NULL DEFAULT '{}'
        );

        CREATE TABLE IF NOT EXISTS turns (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id  TEXT    NOT NULL
                            REFERENCES sessions(id) ON DELETE CASCADE,
            ts          REAL    NOT NULL,
            role        TEXT    NOT NULL,
            content     TEXT    NOT NULL,
            model_used  TEXT,
            input_tokens  INTEGER NOT NULL DEFAULT 0,
            output_tokens INTEGER NOT NULL DEFAULT 0
        );

        CREATE INDEX IF NOT EXISTS idx_turns_session_ts
            ON turns(session_id, ts);
    """)
    con.commit()
    return con


# ── dataclasses ───────────────────────────────────────────────────────

@dataclass
class Session:
    id: str
    created_at: float
    updated_at: float
    title: str
    model: str
    system_prompt: str = ""
    meta: dict = field(default_factory=dict)


@dataclass
class Turn:
    id: int
    session_id: str
    ts: float
    role: str           # "user" | "assistant" | "system"
    content: str
    model_used: Optional[str] = None
    input_tokens: int = 0
    output_tokens: int = 0


def _row_to_session(row) -> Session:
    try:
        meta = json.loads(row[6]) if row[6] else {}
    except Exception:
        meta = {}
    return Session(
        id=row[0], created_at=row[1], updated_at=row[2],
        title=row[3], model=row[4], system_prompt=row[5], meta=meta,
    )


def _row_to_turn(row) -> Turn:
    return Turn(
        id=row[0], session_id=row[1], ts=row[2], role=row[3],
        content=row[4], model_used=row[5],
        input_tokens=row[6], output_tokens=row[7],
    )


# ── session CRUD ──────────────────────────────────────────────────────

def create_session(
    *,
    title: str = "(untitled)",
    model: str = DEFAULT_MODEL,
    system_prompt: Optional[str] = None,
) -> str:
    """Create a new session. Returns the session id."""
    sid = uuid.uuid4().hex[:16]
    now = time.time()
    sp = system_prompt if system_prompt is not None else _default_system_prompt()
    with _connect() as con:
        con.execute(
            "INSERT INTO sessions (id, created_at, updated_at, title, "
            "model, system_prompt) VALUES (?, ?, ?, ?, ?, ?)",
            (sid, now, now, title, model, sp),
        )
        con.commit()
    return sid


def get_session(session_id: str) -> Optional[Session]:
    try:
        with _connect() as con:
            row = con.execute(
                "SELECT id, created_at, updated_at, title, model, "
                "system_prompt, meta_json FROM sessions WHERE id = ?",
                (session_id,),
            ).fetchone()
        return _row_to_session(row) if row else None
    except Exception as e:
        logger.warning("workshop: get_session failed: %s", e)
        return None


def list_sessions(limit: int = 50) -> list[Session]:
    try:
        with _connect() as con:
            rows = con.execute(
                "SELECT id, created_at, updated_at, title, model, "
                "system_prompt, meta_json FROM sessions "
                "ORDER BY updated_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [_row_to_session(r) for r in rows]
    except Exception as e:
        logger.warning("workshop: list_sessions failed: %s", e)
        return []


def get_turns(
    session_id: str, *, tail: Optional[int] = None,
) -> list[Turn]:
    """Turns for a session in chronological order (oldest first).

    `tail`: when set, returns only the MOST RECENT N turns (still
    oldest-first ordered). This is what callers want when they say
    "give me the last 10 messages" — a pagination/context-window
    semantic, not a head slice.

    self-dev review on 07ab21b (concern #3) flagged that the prior
    `limit` parameter did the opposite (SQL LIMIT on an ORDER BY
    ASC query = oldest N, not newest N). Renamed to `tail` so the
    API is honest about what it returns.
    """
    try:
        with _connect() as con:
            if tail is not None:
                # Grab newest N via DESC, then reverse for return.
                rows = con.execute(
                    "SELECT id, session_id, ts, role, content, "
                    "model_used, input_tokens, output_tokens FROM turns "
                    "WHERE session_id = ? ORDER BY ts DESC LIMIT ?",
                    (session_id, tail),
                ).fetchall()
                rows = list(reversed(rows))
            else:
                rows = con.execute(
                    "SELECT id, session_id, ts, role, content, "
                    "model_used, input_tokens, output_tokens FROM turns "
                    "WHERE session_id = ? ORDER BY ts ASC",
                    (session_id,),
                ).fetchall()
        return [_row_to_turn(r) for r in rows]
    except Exception as e:
        logger.warning("workshop: get_turns failed: %s", e)
        return []


def update_session_model(session_id: str, model: str) -> bool:
    """Change a session's default model. Subsequent turn() calls
    without override_model will route to the new target. Past turns
    are not retroactively re-routed; their model_used column records
    what was actually used at the time.
    """
    if not model or not model.strip():
        return False
    try:
        with _connect() as con:
            cur = con.execute(
                "UPDATE sessions SET model = ?, updated_at = ? WHERE id = ?",
                (model.strip()[:100], time.time(), session_id),
            )
            con.commit()
            return cur.rowcount == 1
    except Exception as e:
        logger.warning("workshop: update_session_model failed: %s", e)
        return False


def update_session_title(session_id: str, title: str) -> bool:
    try:
        with _connect() as con:
            cur = con.execute(
                "UPDATE sessions SET title = ?, updated_at = ? WHERE id = ?",
                (title[:200], time.time(), session_id),
            )
            con.commit()
            return cur.rowcount == 1
    except Exception as e:
        logger.warning("workshop: update_session_title failed: %s", e)
        return False


def delete_session(session_id: str) -> bool:
    try:
        with _connect() as con:
            cur = con.execute(
                "DELETE FROM sessions WHERE id = ?", (session_id,),
            )
            con.commit()
            return cur.rowcount == 1
    except Exception as e:
        logger.warning("workshop: delete_session failed: %s", e)
        return False


# ── turn: user message → assistant reply ──────────────────────────────

def _persist_turn(
    session_id: str, role: str, content: str,
    model_used: Optional[str] = None,
    input_tokens: int = 0, output_tokens: int = 0,
) -> Optional[int]:
    try:
        now = time.time()
        with _connect() as con:
            cur = con.execute(
                "INSERT INTO turns (session_id, ts, role, content, "
                "model_used, input_tokens, output_tokens) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (session_id, now, role, content, model_used,
                 input_tokens, output_tokens),
            )
            con.execute(
                "UPDATE sessions SET updated_at = ? WHERE id = ?",
                (now, session_id),
            )
            con.commit()
            return cur.lastrowid
    except Exception as e:
        logger.warning("workshop: _persist_turn failed: %s", e)
        return None


def _resolve_path_safely(rel_or_abs: str) -> Optional[Path]:
    """Return the absolute Path of an @-mention IFF it resolves inside
    _REPO_ROOT. Returns None on any path that escapes, doesn't exist,
    or isn't a regular file. Never raises."""
    try:
        p = Path(rel_or_abs)
        if not p.is_absolute():
            p = _REPO_ROOT / p
        # Resolve follows symlinks and canonicalizes .. — anything
        # that lands outside the repo root is refused.
        resolved = p.resolve()
        if not str(resolved).startswith(str(_REPO_ROOT.resolve()) + os.sep) \
                and resolved != _REPO_ROOT.resolve():
            return None
        if not resolved.is_file():
            return None
        return resolved
    except Exception:
        return None


def expand_mentions(user_message: str) -> tuple[str, list[dict]]:
    """Expand @path mentions in `user_message` into a message with
    the file contents appended as fenced code blocks. Returns
    (expanded_message, notes) where notes describes what was
    resolved/skipped for UI feedback if the caller wants it.

    Mentions are APPENDED rather than inline-substituted: the
    original `@path` token stays in the user's text (so their
    intent is preserved) and the expanded bodies land in an
    "attached files" block after. This keeps prose reading natural
    and makes Claude's context unambiguous.

    Deliberately quiet on failure: unresolvable mentions (outside
    repo, not a file, too big, permission denied) are reported in
    `notes` but the original @mention is left intact in the message.
    """
    notes: list[dict] = []
    if not user_message or "@" not in user_message:
        return user_message, notes

    matches = list(_MENTION_RE.finditer(user_message))
    if not matches:
        return user_message, notes

    # Dedupe paths while preserving order of first appearance
    seen: set[str] = set()
    attachments: list[tuple[str, str]] = []  # (rel_path, content)
    for m in matches:
        raw = m.group(1)
        if raw in seen:
            continue
        seen.add(raw)
        resolved = _resolve_path_safely(raw)
        if resolved is None:
            notes.append({"mention": raw, "status": "unresolved"})
            continue
        try:
            size = resolved.stat().st_size
        except OSError:
            notes.append({"mention": raw, "status": "stat_failed"})
            continue
        truncated = False
        try:
            if size > _MENTION_MAX_BYTES:
                text = resolved.read_text(
                    encoding="utf-8", errors="replace",
                )[:_MENTION_MAX_BYTES]
                truncated = True
            else:
                text = resolved.read_text(
                    encoding="utf-8", errors="replace",
                )
        except Exception as e:
            notes.append({"mention": raw, "status": f"read_failed: {e}"})
            continue
        attachments.append((raw, text))
        notes.append({
            "mention": raw,
            "status": "attached_truncated" if truncated else "attached",
            "bytes": size,
        })

    if not attachments:
        return user_message, notes

    # Build the appended block
    parts = [user_message, "", "[ATTACHED FILES]"]
    for rel, content in attachments:
        ext = os.path.splitext(rel)[1].lower()
        lang = _EXT_LANG.get(ext, "")
        fence = f"```{lang}" if lang else "```"
        parts.extend([
            f"",
            f"--- {rel} ---",
            fence,
            content,
            "```",
        ])
    return "\n".join(parts), notes


# ── apply diff ────────────────────────────────────────────────────────

# Where we keep backups of files before applying Workshop diffs.
# Separate from evolution_engine's backup dir so a Workshop apply
# can't collide with an evolution-engine deploy happening at the
# same moment. Timestamped filenames inside ensure no overwrite.
_APPLY_BACKUP_DIR = Path(os.environ.get(
    "MAEZ_WORKSHOP_BACKUP_DIR",
    "/home/rohit/maez/workshop/backups",
))

def _extract_target_path(diff_text: str) -> tuple[Optional[str], bool]:
    """Parse the b-side ('+++') target from a unified diff. Returns
    (repo-relative-path, had_git_prefix). had_git_prefix is True if
    the original header used 'a/' or 'b/' — callers that pass the
    diff to `patch` must use -p1 instead of -p0 in that case.

    self-dev review on 07ab21b (concerns #1, #5) flagged: the
    stripped-prefix path was only used for validation while the raw
    diff was passed to patch -p0, silently failing for git-style
    diffs. Signal the strip to the caller so they can match strip
    level on the patch side. Also removed the unused module-level
    _DIFF_HEADER_RE that reinvented this pattern.
    """
    for m in re.finditer(r"^\+\+\+\s+(\S+)", diff_text, re.MULTILINE):
        path = m.group(1)
        had_git_prefix = path.startswith("a/") or path.startswith("b/")
        if had_git_prefix:
            path = path[2:]
        if path == "/dev/null":
            return None, had_git_prefix
        return path, had_git_prefix
    return None, False


def _backup_file(path: Path) -> Path:
    """Copy `path` to a timestamped backup under _APPLY_BACKUP_DIR.
    Returns the backup path."""
    import shutil
    _APPLY_BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%dT%H%M%S")
    backup = _APPLY_BACKUP_DIR / f"{path.name}.{ts}.bak"
    shutil.copy2(path, backup)
    return backup


def apply_diff(
    *,
    session_id: str,
    diff_text: str,
) -> dict:
    """Apply a unified-diff block to the repo. Resolves the target
    from '+++' header, backs up the file, shells out to `patch` to
    apply, rolls back on failure.

    Returns a dict: {
      "applied": bool,
      "target": <rel path or None>,
      "backup": <backup path or None>,
      "stdout": <patch stdout>,
      "stderr": <patch stderr>,
      "error": <string or None>,
    }

    Constraints:
      - Target path must resolve inside _REPO_ROOT. Escape = refuse.
      - `patch` binary must be available on PATH.
      - Only single-file diffs in this step; multi-file support is a
        follow-up once we see the pattern of Claude's outputs.
      - Session must exist (we log the applied diff as a turn so the
        conversation history records what was committed).
    """
    import subprocess
    import shutil as _shutil

    # Session must exist so we can record the apply event
    session = get_session(session_id)
    if not session:
        return {"applied": False, "error": f"no session {session_id!r}",
                "target": None, "backup": None, "stdout": "", "stderr": ""}

    target_rel, had_git_prefix = _extract_target_path(diff_text)
    if not target_rel:
        return {"applied": False,
                "error": "could not extract target path from diff '+++' header",
                "target": None, "backup": None, "stdout": "", "stderr": ""}

    # Path safety: same guard as @mentions
    target_abs = _resolve_path_safely(target_rel)
    if target_abs is None:
        return {"applied": False,
                "error": f"target path {target_rel!r} is not a file under the repo",
                "target": target_rel, "backup": None,
                "stdout": "", "stderr": ""}

    if not _shutil.which("patch"):
        return {"applied": False,
                "error": "`patch` binary not found on PATH — install it or "
                          "apply manually by copying the diff",
                "target": target_rel, "backup": None,
                "stdout": "", "stderr": ""}

    # Back up before touching
    try:
        backup = _backup_file(target_abs)
    except Exception as e:
        return {"applied": False, "error": f"backup failed: {e}",
                "target": target_rel, "backup": None,
                "stdout": "", "stderr": ""}

    # Shell out to `patch`. Strip level matches whatever the diff
    # uses: -p1 for git-style a/ b/ prefixes, -p0 otherwise. Without
    # this, git-format diffs (the most common shape Claude emits
    # when asked to propose a change) silently fail because patch
    # tries to write to b/core/foo.py relative to the repo root.
    # self-dev review on 07ab21b caught this (concern #1).
    strip_flag = "-p1" if had_git_prefix else "-p0"
    try:
        proc = subprocess.run(
            ["patch", strip_flag, "--forward", "--fuzz=0",
             "--no-backup-if-mismatch"],
            input=diff_text, text=True, capture_output=True,
            cwd=str(_REPO_ROOT), timeout=10,
        )
    except subprocess.TimeoutExpired:
        # Unlikely but treat the same as an apply failure
        return {"applied": False, "error": "patch timed out",
                "target": target_rel, "backup": str(backup),
                "stdout": "", "stderr": ""}
    except Exception as e:
        return {"applied": False, "error": f"patch exec failed: {e}",
                "target": target_rel, "backup": str(backup),
                "stdout": "", "stderr": ""}

    if proc.returncode != 0:
        # patch failed — nothing should have been modified if --forward
        # was set and hunks didn't apply, but be paranoid: restore
        # from backup anyway if the file now differs from the backup.
        try:
            if target_abs.read_bytes() != backup.read_bytes():
                import shutil
                shutil.copy2(backup, target_abs)
        except Exception as e:
            logger.warning("workshop apply rollback read/write failed: %s", e)
        return {"applied": False,
                "error": f"patch exited {proc.returncode}",
                "target": target_rel, "backup": str(backup),
                "stdout": proc.stdout, "stderr": proc.stderr}

    # Record the apply as an assistant-role note in the session so
    # future turn() calls see it in the message list built from
    # history. system-role turns were filtered out by the
    # role-in-{user,assistant} guard in turn() — self-dev review on
    # 07ab21b flagged (concern #4) that the docstring promise of
    # "records what was committed" was effectively false. Using
    # 'assistant' with a bracketed prefix makes the apply visible
    # to subsequent turns and honest as a conversation artifact.
    _persist_turn(
        session_id=session_id, role="assistant",
        content=f"[Workshop applied diff] target={target_rel} "
                f"backup={backup.name}",
    )

    return {
        "applied": True, "error": None,
        "target": target_rel, "backup": str(backup),
        "stdout": proc.stdout, "stderr": proc.stderr,
    }


def turn(
    *,
    session_id: str,
    user_message: str,
    override_model: Optional[str] = None,
    context_turns: int = DEFAULT_CONTEXT_TURNS,
) -> dict:
    """Send a user message, persist it, call the proxy with session
    history, persist the reply, return {'turn_id', 'assistant', ...}.

    Raises RuntimeError on proxy failures so the caller can decide
    whether to surface to the user or retry.
    """
    session = get_session(session_id)
    if not session:
        raise RuntimeError(f"no session {session_id!r}")

    if not user_message or not user_message.strip():
        raise RuntimeError("empty user_message")

    # Expand @path mentions BEFORE persisting — we want the file
    # bodies in the persisted turn so conversation history can be
    # replayed without re-reading files (which may have changed).
    expanded_message, mention_notes = expand_mentions(user_message)

    # Persist user turn first so it's in history even if the assistant
    # call fails below. Use the expanded form so replay sees what
    # Claude saw.
    user_turn_id = _persist_turn(
        session_id=session_id, role="user", content=expanded_message,
    )
    # self-dev review on 07ab21b (concern #2) flagged: _persist_turn
    # returns None on DB failure, which silently left the session
    # inconsistent (assistant reply persisted without a user turn).
    # Fail loud here so the caller knows the write was lost.
    if user_turn_id is None:
        raise RuntimeError(
            "failed to persist user turn — session log would be corrupted",
        )

    # Build message list: system prompt + last N turns (user+assistant)
    # + current user message.
    history = get_turns(session_id)
    # Drop the turn we just inserted from history — proxy call expects
    # it as the "current" message, not part of history context.
    if history and history[-1].id == user_turn_id:
        history = history[:-1]
    # Cap how much we send
    if context_turns > 0 and len(history) > context_turns:
        history = history[-context_turns:]

    messages: list[dict] = []
    if session.system_prompt:
        messages.append({"role": "system", "content": session.system_prompt})
    for h in history:
        if h.role in ("user", "assistant"):
            messages.append({"role": h.role, "content": h.content})
    messages.append({"role": "user", "content": expanded_message})

    model = override_model or session.model
    # Call the tier client. Any error propagates to the Flask layer.
    from core import claude_tier
    try:
        # Compose the single-shot call — tier.call() takes system +
        # one user prompt today. For multi-turn we concatenate history
        # into the user prompt with role prefixes since the tier API
        # is single-turn. (The proxy accepts multi-turn OpenAI format
        # directly, but going through claude_tier keeps budget + fail
        # modes centralized. Acceptable for Phase 1.)
        if len(messages) > 2:
            # system + history + current → flatten history into user
            history_text = "\n\n".join(
                f"[{m['role'].upper()}]\n{m['content']}"
                for m in messages[1:-1]
            )
            composed_user = (
                f"Conversation so far:\n\n{history_text}\n\n"
                f"[USER, current]\n{expanded_message}"
            )
            system_prompt = messages[0]["content"] if messages[0]["role"] == "system" else None
        else:
            composed_user = expanded_message
            system_prompt = session.system_prompt or None

        reply = claude_tier.call(
            prompt=composed_user,
            system_prompt=system_prompt,
            model=model,
            caller=f"workshop/{session_id[:8]}",
        )
    except claude_tier.ClaudeTierError as e:
        raise RuntimeError(f"workshop turn failed: {e}")

    # Persist assistant turn
    asst_turn_id = _persist_turn(
        session_id=session_id, role="assistant", content=reply.reply,
        model_used=reply.model_used,
        input_tokens=reply.input_tokens, output_tokens=reply.output_tokens,
    )

    # Return shape (all present, no extra keys):
    #   user_turn_id, assistant_turn_id, assistant, model_used,
    #   input_tokens, output_tokens, mentions
    # self-dev review on 07ab21b (concern #8) flagged an earlier
    # docstring referenced a 'turn_id' key that doesn't exist.
    return {
        "user_turn_id": user_turn_id,
        "assistant_turn_id": asst_turn_id,
        "assistant": reply.reply,
        "model_used": reply.model_used,
        "input_tokens": reply.input_tokens,
        "output_tokens": reply.output_tokens,
        "mentions": mention_notes,  # [] when no @paths in input
    }


# ── rollup for cockpit ────────────────────────────────────────────────

def rollup(*, limit_sessions: int = 20) -> dict:
    """Shape the cockpit needs: list of sessions (id/title/model/ts/
    turn_count). Turns are NOT embedded — cockpit fetches specific
    session turns on demand.

    self-dev review on 07ab21b (concern #7) flagged an unused
    `turns_per_session` param that implied callers could control
    turn embedding; removed so the signature is honest.
    """
    try:
        sessions = list_sessions(limit=limit_sessions)
        with _connect() as con:
            count_by_session = dict(con.execute(
                "SELECT session_id, COUNT(*) FROM turns GROUP BY session_id",
            ).fetchall())
        return {
            "generated_at": time.time(),
            "sessions": [
                {
                    "id": s.id,
                    "title": s.title,
                    "model": s.model,
                    "created_at": s.created_at,
                    "updated_at": s.updated_at,
                    "turn_count": int(count_by_session.get(s.id, 0)),
                }
                for s in sessions
            ],
        }
    except Exception as e:
        logger.warning("workshop: rollup failed: %s", e)
        return {"error": str(e), "sessions": []}
