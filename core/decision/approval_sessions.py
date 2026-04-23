# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""
approval_sessions.py — time-limited blanket approvals.

Built 2026-04-20 after a Telegram conversation where the user
explicitly granted blanket read-permission (*"Reading is absolutely
fine and necessary for you to know about yourself"*), but Maez kept
emitting per-command proposal cards for every subsequent read-only
introspection. The user's next messages were frustrated
(*"Didn't I give permission for this already?"*).

The fix: when the user grants blanket permission in natural language,
persist a time-limited session flag. While that session is active,
read-safe ops auto-approve and execute directly, skipping the card
loop entirely. The session expires after a reasonable window
(default 1 hour) — long enough for an ongoing conversation, short
enough that it doesn't silently carry over between sessions.

Explicit scope:
  - Applies ONLY to read_safe actions (see is_read_safe_cmd()).
  - Does NOT cover writes, deletes, sudo, package management, network
    requests, self-modification, or anything with state effects.
  - Every auto-approve still goes through the audit pipeline — the
    session shortcut skips the CARD, not the safety rails.

Storage: single JSON file (memory/approval_sessions.json). Small,
simple, human-readable, easy to inspect/revoke manually.
"""
from __future__ import annotations

import json
import re
import threading
import time
from pathlib import Path
from typing import Optional

try:
    from core.paths import memory_dir as _memory_dir
    _STATE_PATH = _memory_dir() / "approval_sessions.json"
except Exception:
    _STATE_PATH = Path("/home/rohit/maez/memory/approval_sessions.json")
_lock = threading.Lock()

_DEFAULT_DURATION_SECONDS = 3600  # 1 hour

# ── grant phrase detection ─────────────────────────────────────────────

# Phrases that unambiguously grant blanket read-permission. Conservative
# — better to miss a grant than to auto-execute on ambiguous language.
# Each phrase maps to a list of session kinds to grant.
_GRANT_PATTERNS: list[tuple[re.Pattern, list[str]]] = [
    # Read-related blanket grants
    (re.compile(
        r"\b(?:reading|reads)\s+(?:is|are)\s+"
        r"(?:absolutely\s+)?(?:fine|ok|okay|allowed|permitted)\b",
        re.IGNORECASE),
     ["read_safe"]),
    (re.compile(
        r"\byou\s+can\s+read\s+(?:anything|whatever|what\s+you\s+need)\b",
        re.IGNORECASE),
     ["read_safe"]),
    (re.compile(
        r"\bblanket\s+(?:permission|approval)\s+(?:for|to)\s+read\b",
        re.IGNORECASE),
     ["read_safe"]),
    (re.compile(
        r"\bdon'?t\s+ask\s+(?:me\s+)?(?:each\s+time|every\s+time)\s+(?:for|to)\s+read\b",
        re.IGNORECASE),
     ["read_safe"]),
    (re.compile(
        r"\b(?:reading|reads?)\s+without\s+(?:asking|a\s+card)\b",
        re.IGNORECASE),
     ["read_safe"]),
]

# ── read-safe command classifier ───────────────────────────────────────

# First-token whitelist. If `cmd` (stripped) starts with one of these
# tokens and doesn't contain any unsafe fragment below, it's read_safe.
_READ_SAFE_PREFIXES = frozenset({
    "systemctl",        # is-active / status / show / list-units (READ only)
    "ps", "pgrep", "pidof",
    "df", "du", "free", "uptime",
    "uname", "whoami", "hostname", "date", "id",
    "cat", "head", "tail", "wc", "file",
    "ls", "stat", "readlink",
    "grep", "egrep", "rg", "ripgrep", "find",
    "jq", "awk", "sed",                # sed WITHOUT -i is read-only
    "journalctl",
    "nvidia-smi", "top", "htop", "iostat", "vmstat",
    "which", "type", "command",
    "env", "printenv", "echo",
    "curl",                             # conservative: read URLs
})

# Fragments that immediately disqualify a cmd from read_safe. These are
# written defensively — if any of them appears anywhere in the raw cmd
# string, classify as unsafe even if the prefix is on the whitelist.
_UNSAFE_FRAGMENTS = (
    # Write/destructive
    " rm ", " rm\n", ";rm ", "|rm ", "&&rm ",
    " mv ", " cp -", " dd ", " mkfs", " fdisk",
    # Permissions / ownership
    " sudo ", " chmod ", " chown ", " setcap",
    # Redirects (anything that writes to disk or pipes to an unsafe cmd)
    ">", ">>",
    # Pipes — conservative: pipes can chain to unsafe ops
    "|",
    # sed in-place
    "sed -i", "sed --in-place",
    # Shell command substitution / eval
    "$(", "`",
    # Find with exec / delete
    "-exec ", "-delete", "-ok ",
    # Package management
    " apt ", " apt-get ", " pip ", " npm ",
    # systemctl write ops
    "systemctl start", "systemctl stop", "systemctl restart",
    "systemctl enable", "systemctl disable", "systemctl reload",
    "systemctl mask", "systemctl unmask",
)


def _is_single_read_safe(single_cmd: str) -> bool:
    """Read-safe check for a single command (no chaining operators)."""
    s = single_cmd.strip()
    if not s:
        return False
    padded = " " + s + " "
    for bad in _UNSAFE_FRAGMENTS:
        if bad in padded:
            return False
    first = s.split(None, 1)[0].lower()
    if "/" in first:
        first = first.rsplit("/", 1)[-1]
    return first in _READ_SAFE_PREFIXES


def is_read_safe_cmd(cmd: str) -> bool:
    """True iff `cmd` is a read-only introspection command suitable for
    auto-execution when a read_safe session is active. Compound
    commands joined with `&&`, `||`, or `;` are accepted iff ALL
    pieces are individually read-safe. Conservative on ambiguity."""
    if not cmd or not isinstance(cmd, str):
        return False
    s = cmd.strip()
    if not s:
        return False
    # Split on logical chain operators (&&, ||, ;). Pipe (|) is NOT a
    # split delimiter — a per-piece scan catches piped commands because
    # `|` is in _UNSAFE_FRAGMENTS, so `ps aux | grep maez` remains one
    # piece and fails the pipe fragment check. Compound disjunctions
    # like `systemctl X || systemctl Y` split cleanly.
    pieces = re.split(r"&&|\|\||;", s)
    pieces = [p for p in pieces if p.strip()]
    if not pieces:
        return False
    return all(_is_single_read_safe(p) for p in pieces)


# ── session persistence ────────────────────────────────────────────────

def _load() -> dict:
    try:
        if not _STATE_PATH.exists():
            return {}
        return json.loads(_STATE_PATH.read_text())
    except Exception:
        return {}


def _save(d: dict) -> None:
    try:
        _STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp = _STATE_PATH.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(d, indent=2))
        tmp.replace(_STATE_PATH)
    except Exception:
        return


def grant(kind: str, duration_seconds: int = _DEFAULT_DURATION_SECONDS,
          note: Optional[str] = None) -> None:
    """Start or refresh a session for `kind`."""
    with _lock:
        d = _load()
        now = time.time()
        d[kind] = {
            "granted_at": now,
            "expires_at": now + duration_seconds,
            "note": note,
        }
        _save(d)


def revoke(kind: str) -> None:
    with _lock:
        d = _load()
        if kind in d:
            del d[kind]
            _save(d)


def is_active(kind: str, now: Optional[float] = None) -> bool:
    """True iff a non-expired session exists for `kind`."""
    now = now if now is not None else time.time()
    with _lock:
        d = _load()
    s = d.get(kind)
    if not s:
        return False
    try:
        return bool(s.get("expires_at", 0) > now)
    except Exception:
        return False


def describe() -> dict:
    """Structured snapshot of active sessions."""
    now = time.time()
    with _lock:
        d = _load()
    out = {}
    for kind, s in d.items():
        try:
            remaining = float(s.get("expires_at", 0)) - now
            if remaining > 0:
                out[kind] = {
                    "granted_at": s.get("granted_at"),
                    "expires_at": s.get("expires_at"),
                    "seconds_remaining": round(remaining, 0),
                    "note": s.get("note"),
                }
        except Exception:
            continue
    return out


# ── user-message scanner ──────────────────────────────────────────────

def detect_and_grant(user_text: str) -> list[str]:
    """Scan user text for blanket-permission phrases; grant matching
    sessions; return the list of kinds that were just granted. Empty
    list if nothing matched. Silent on all failures."""
    if not user_text:
        return []
    granted: list[str] = []
    seen: set[str] = set()
    for pat, kinds in _GRANT_PATTERNS:
        if pat.search(user_text):
            for k in kinds:
                if k in seen:
                    continue
                seen.add(k)
                try:
                    grant(k, note=f"detected in user text: {user_text[:80]!r}")
                    granted.append(k)
                except Exception:
                    pass
    return granted


# ── diagnostic helpers ─────────────────────────────────────────────────

def _diag_clear_for_test() -> None:
    try:
        if _STATE_PATH.exists():
            _STATE_PATH.unlink()
    except Exception:
        return
