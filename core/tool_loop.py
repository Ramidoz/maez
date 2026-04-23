# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""
tool_loop.py — shared primitives for the CLI and daemon tool-use loops.

Pure functions. No Rich, no prompt_toolkit, no UI. Rendering lives in
the caller (CLI uses Rich panels; daemon uses log lines + the pending-
cards machinery).

Extracted from cli/maez_chat.py so that both the chat surface and the
daemon's exploratory-mind cycle use the *same* command extraction,
safety gates, and subprocess execution. Behavioral parity matters:
what one accepts, the other must accept; what one refuses, the other
must refuse.
"""
from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from core.action_engine import _covenant_violation as _covenant_check

_MAEZ_ROOT = Path(__file__).resolve().parent.parent

# ── runtime caps (overridable via env) ─────────────────────────────────
TOOL_TIMEOUT_SEC = int(os.environ.get("MAEZ_TOOL_TIMEOUT_SEC", "60"))
TOOL_OUTPUT_MAX = int(os.environ.get("MAEZ_TOOL_OUTPUT_MAX", "4000"))

# ── regexes ────────────────────────────────────────────────────────────
BASH_FENCE_RE = re.compile(
    r"```(?:bash|sh|zsh|shell)?\s*\n(.*?)```",
    re.DOTALL,
)

# ── safety: paths ──────────────────────────────────────────────────────
_DANGEROUS_ROOT_DIRS = {
    "etc", "usr", "var", "boot", "lib", "lib64", "sys", "proc",
    "dev", "root", "srv", "opt", "mnt", "bin", "sbin", "run", "home",
}
_SAFE_RM_PREFIXES = ("/tmp/", "/var/tmp/", "/var/cache/")


# ── data types ─────────────────────────────────────────────────────────
@dataclass
class ToolRun:
    cmd: str
    stdout: str = ""
    stderr: str = ""
    returncode: int = 0
    skipped: bool = False
    refused_reason: str = ""


# ── extraction ─────────────────────────────────────────────────────────
def extract_shell_commands(text: str) -> list[str]:
    """Pull ```bash/sh/zsh/shell``` blocks out of model output.
    Returns deduplicated, stripped command strings in order of appearance.
    """
    out: list[str] = []
    seen: set[str] = set()
    for m in BASH_FENCE_RE.finditer(text):
        block = m.group(1).strip()
        if not block or block in seen:
            continue
        seen.add(block)
        out.append(block)
    return out


# ── safety ─────────────────────────────────────────────────────────────
def _rm_rf_danger(cmd_low: str) -> Optional[str]:
    """Inspect rm -rf targets. Return reason if catastrophic, else None.

    Allow:  /tmp/*, /var/tmp/*, /var/cache/*, ./*, relative paths,
            user-owned non-system absolute paths
    Deny:   /, /* expansion, /home (root user dir), /etc, /usr, /boot,
            /lib, /sys, /proc, /dev, /bin, /sbin, /opt, /mnt, /srv, /run
    """
    for m in re.finditer(r"\brm\s+(?:-[a-z]*[rRfF][a-z]*\s+)+([^\s;|&`$<>]+)",
                          cmd_low):
        target = m.group(1).strip().rstrip("/")
        if target in ("/", "/*", "/.", ""):
            return "rm -rf / forbidden"
        if any(target.startswith(p) or target == p.rstrip("/")
               for p in _SAFE_RM_PREFIXES):
            continue
        if target.startswith("/"):
            first = target.lstrip("/").split("/")[0]
            if target == "/home":
                return "rm -rf /home forbidden"
            if first in _DANGEROUS_ROOT_DIRS and first != "home":
                return f"rm -rf inside /{first} forbidden"
    return None


def safety_check(cmd: str) -> Optional[str]:
    """Extra defensive layer on top of core.action_engine's covenant regex.

    Philosophy: explicit y/N approval from the user IS the permission. We
    only hard-refuse things that would bypass covenant or destroy the Maez
    tree even with approval — those aren't one-off mistakes, they're
    category failures.

    sudo is intentionally NOT hard-refused here. It flows to approval.

    Returns a reason string if hard-blocked, None if OK.
    """
    low = cmd.lower()
    reason = _covenant_check(low)
    if reason:
        return f"covenant: {reason}"
    rm_danger = _rm_rf_danger(low)
    if rm_danger:
        return rm_danger
    maez_root = str(_MAEZ_ROOT).lower()
    if maez_root in low and re.search(
        r"\b(rm\s|mv\s|sed\s+-i|tee\s+|>\s*|>>\s*|truncate\s|chmod\s|chown\s)",
        low,
    ):
        return (f"write/modify inside {maez_root} needs to go through the "
                f"evolution engine, not an ad-hoc shell command")
    return None


# ── read-only gate (daemon auto-exec) ──────────────────────────────────
# First-word binaries that are considered safe to auto-run without human
# approval. The rest of the safety stack still applies (covenant, rm -rf,
# maez-tree writes). Caller (daemon) uses this to decide auto-exec vs card.
_READ_ONLY_BINARIES = frozenset({
    "ps", "ls", "ll", "cat", "head", "tail", "grep", "egrep", "fgrep", "rg",
    "find", "locate", "file", "stat", "wc", "sort", "uniq", "cut", "awk", "sed",
    "systemctl", "journalctl", "pgrep", "pidof", "service",
    "free", "du", "df", "top", "uptime", "who", "whoami", "id", "groups",
    "echo", "printf", "env", "date", "hostname", "uname", "true", "false",
    "dpkg", "apt-cache", "apt-show-versions", "which", "whereis", "command",
    "nvidia-smi", "lscpu", "lsusb", "lspci", "lsblk", "lsof", "lsmod",
    "readlink", "realpath", "basename", "dirname", "md5sum", "sha256sum",
    "cmp", "diff", "column", "tree", "jq", "xxd", "hexdump",
})

# Anything in this set makes the command NOT read-only no matter what.
_ALWAYS_MUTATING = re.compile(
    r"""
    (\bsudo\b)                          # privilege escalation
    | (\bdd\b)                          # raw disk writes
    | (\$\([^)]*\))                     # command substitution (can hide writes)
    | (`[^`]+`)                         # backtick substitution
    | (\|\s*(bash|sh|zsh|python\w*))    # pipe-to-shell pattern
    | (\s>\s*[^\s;|&]+)                 # output redirect
    | (\s>>\s*[^\s;|&]+)                # append redirect
    | (\s2>\s*[^\s;|&]+)                # stderr redirect
    """,
    re.VERBOSE,
)

# sed is on the read-only list but `sed -i` is destructive — catch it.
_SED_WRITE = re.compile(r"\bsed\s+[^|;&]*-i\b")


def is_read_only(cmd: str) -> bool:
    """Return True if cmd looks safe to auto-execute without human approval.

    Conservative: when in doubt, returns False (→ caller queues an approval
    card). safety_check() is still the authoritative refuse layer; this
    decides auto vs card for the commands that already passed safety.
    """
    stripped = cmd.strip()
    if not stripped:
        return False
    if _ALWAYS_MUTATING.search(stripped):
        return False
    if _SED_WRITE.search(stripped):
        return False
    # Require EVERY stage of a pipeline to be a read-only binary.
    # Split on top-level `|`, `;`, `&&`, `||` — approximation, doesn't
    # handle quoting perfectly but good enough for daemon auto-exec gate
    # (when in doubt it says False, which is the safe side).
    stages = re.split(r"[;|&]+", stripped)
    for stage in stages:
        stage = stage.strip()
        if not stage:
            continue
        # First token of the stage
        first = stage.split(None, 1)[0] if stage.split() else ""
        # Strip env-var prefixes like FOO=bar cmd
        while "=" in first and not first.startswith("-"):
            parts = stage.split(None, 2)
            if len(parts) < 2:
                break
            stage = parts[1] + (" " + parts[2] if len(parts) > 2 else "")
            first = stage.split(None, 1)[0] if stage.split() else ""
        # Strip path
        base = os.path.basename(first).lower()
        if base not in _READ_ONLY_BINARIES:
            return False
    return True


# ── execution ──────────────────────────────────────────────────────────
def run_shell(cmd: str, timeout: Optional[int] = None,
              output_max: Optional[int] = None) -> tuple[str, str, int]:
    """Run a shell command via `bash -lc`, capture output.

    Truncates each of stdout and stderr to output_max chars.
    On timeout, returns ("", "[timeout after Ns]", 124).
    """
    t = timeout if timeout is not None else TOOL_TIMEOUT_SEC
    m = output_max if output_max is not None else TOOL_OUTPUT_MAX
    try:
        r = subprocess.run(
            ["bash", "-lc", cmd],
            capture_output=True, text=True, timeout=t,
        )
        out = (r.stdout or "")[:m]
        err = (r.stderr or "")[:m]
        return out, err, r.returncode
    except subprocess.TimeoutExpired:
        return "", f"[timeout after {t}s]", 124
    except Exception as e:
        return "", f"[runner error: {e}]", 1


# Backward-compat alias for the existing CLI callers.
_run_shell = run_shell


# ── feedback formatter ────────────────────────────────────────────────
def format_tool_results_for_model(runs: list[ToolRun]) -> str:
    """Produce a single message the model can read as real tool output.
    Used by both CLI (chat continuation) and daemon (learning synthesis).
    """
    lines = ["I ran these commands and these are the actual outputs:\n"]
    for i, tr in enumerate(runs, 1):
        lines.append(f"### command {i}")
        lines.append("```bash")
        lines.append(tr.cmd.strip())
        lines.append("```")
        if tr.skipped:
            lines.append(f"_(skipped: {tr.refused_reason or 'user declined'})_")
            lines.append("")
            continue
        lines.append(f"exit code: {tr.returncode}")
        if tr.stdout.strip():
            lines.append("stdout:")
            lines.append("```")
            lines.append(tr.stdout.rstrip())
            lines.append("```")
        if tr.stderr.strip():
            lines.append("stderr:")
            lines.append("```")
            lines.append(tr.stderr.rstrip())
            lines.append("```")
        lines.append("")
    return "\n".join(lines)
