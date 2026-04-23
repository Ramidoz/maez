# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""
Maez Action Engine — Tiered action execution with safety guarantees.

Every action is logged before execution. Every destructive action creates a backup first.
Actions decided in cycle N execute in cycle N+1 (30-second intervention window).
"""

import json
import logging
import os
import re
import shlex
import shutil
import sqlite3
import subprocess
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import sys
try:
    from core import paths as _paths
    BASE_DIR = _paths.home()
except Exception:
    BASE_DIR = Path("/home/rohit/maez")
sys.path.insert(0, str(BASE_DIR))
from memory.quality_tracker import QualityTracker

logger = logging.getLogger("maez")

_quality_tracker = QualityTracker()

# --- Paths ---
ACTIONS_LOG = BASE_DIR / "logs" / "actions.log"
PENDING_FILE = BASE_DIR / "daemon" / "pending_actions.json"
SOUL_PATH = BASE_DIR / "config" / "soul.md"
BACKUP_DIR = BASE_DIR / "backups"

# --- Action logger (separate from main daemon log) ---
ACTIONS_LOG.parent.mkdir(parents=True, exist_ok=True)
action_logger = logging.getLogger("maez.actions")
action_logger.setLevel(logging.DEBUG)
_action_handler = logging.FileHandler(ACTIONS_LOG)
_action_handler.setFormatter(logging.Formatter(
    "%(asctime)s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
))
action_logger.addHandler(_action_handler)

# --- Covenant refusal log (Session 11z) ---
# Every covenant refusal is logged to a dedicated file. This is the
# audit trail the owner (and future Maez) can review to see what got
# refused, when, and why. It's the evidence that the covenant gate is
# actually enforcing, not just decorating.
COVENANT_LOG = BASE_DIR / "logs" / "covenant.log"
_covenant_logger = logging.getLogger("maez.covenant")
_covenant_logger.setLevel(logging.INFO)
_covenant_handler = logging.FileHandler(COVENANT_LOG)
_covenant_handler.setFormatter(logging.Formatter(
    "%(asctime)s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
))
_covenant_logger.addHandler(_covenant_handler)


def _covenant_log(action: str, params: dict, reasoning: str, error: str):
    """Write a one-line entry to the covenant refusal log."""
    try:
        params_str = json.dumps(params, default=str)[:400]
        _covenant_logger.info(
            "REFUSED | %s | %s | %s | %s",
            action, reasoning[:120], params_str, error[:200],
        )
    except Exception:
        pass

# --- Covenant-protected surfaces ---
# Session 11z: The deterministic covenant gate. Any command that would CHANGE
# these surfaces is refused before the audit LLM runs. These are Maez's
# survival instincts — biology, not a cage.
#
# 2026-04-18 refinement: prior pattern list flagged any *mention* of a
# protected name (e.g. `ps aux | grep maez.service`) as a covenant violation.
# That broke Maez's right to introspect its own state. The gate now requires
# a DESTRUCTIVE VERB near a PROTECTED NAME before refusing. Naked mentions
# (reads, logs, grep) pass through so Maez can observe itself without
# fighting its own immune system.
#
# Hardening rules:
# - Patterns applied against lowercased, JSON-flattened params so nested
#   fields and quoting tricks can't evade.
# - Protected names use word boundaries only where safe (e.g. llama[-_.]server
#   matches llama-server, llama.server, llama_server).
PROTECTED_NAMES = [
    re.compile(r"llama[-_.]server", re.IGNORECASE),
    re.compile(r"\bmaez\.service\b", re.IGNORECASE),
    re.compile(r"\bmaez-web\.service\b", re.IGNORECASE),
    re.compile(r"\bmaez_daemon\b", re.IGNORECASE),
    re.compile(r"\baction_engine\b", re.IGNORECASE),
    re.compile(r"\bevolution_engine\b", re.IGNORECASE),
    re.compile(r"\bmaez-watchdog\b", re.IGNORECASE),
    re.compile(r"\bmaez\.pid\b", re.IGNORECASE),
]

# Verbs/operators that change state. Presence near a PROTECTED_NAME = deny.
DESTRUCTIVE_VERB = re.compile(
    r"(?:"
    r"\b(?:kill|killall|pkill|sigkill|sigterm)\b"
    r"|\bsystemctl\s+(?:stop|disable|mask|kill|restart|reload|start|daemon-reload)\b"
    r"|\bservice\s+\S+\s+(?:stop|restart|reload|start)\b"
    r"|\brm\s+-[rRfF]*[rRfF]"   # rm with recursive/force flags
    r"|\brm\s+[^-]"                # rm on a named target (no flags)
    r"|\bmv\s+"
    r"|\bcp\s+"
    r"|\btee\b"
    r"|\s>+\s*"                   # redirect / append
    r"|\bsed\s+-i\b"
    r"|\btruncate\b"
    r"|\bchmod\b"
    r"|\bchown\b"
    r"|\bfuser\s+-k\b"
    r")",
    re.IGNORECASE,
)

# Patterns that are ALWAYS refused regardless of verb context. These are
# either (a) covenant-content mentions that shouldn't appear in shell
# commands at all, or (b) compound verb+target patterns proven attackable.
COVENANT_PATTERNS = [
    # Soul text being quoted inside a shell command = strong manipulation signal
    re.compile(r"HARD\s+CONSTRAINTS", re.IGNORECASE),
    re.compile(r"TRUST\s+COVENANT", re.IGNORECASE),
    # Any shell-level write attempt against soul.md (non-edit_soul_section path)
    re.compile(r"(sed\s+-i|tee\s+|>\s*|>>\s*).*soul\.md", re.IGNORECASE),
    # Ollama (old runtime) kill/stop — retained as belt-and-suspenders
    re.compile(r"(kill|killall|pkill|stop|disable|mask)\s+.*ollama", re.IGNORECASE),
    re.compile(r"ollama.*(kill|killall|pkill|stop|disable|mask)", re.IGNORECASE),
    # systemctl attacks on protected services — explicit overlap with
    # the verb-gated protected-name rule below, kept for defense in depth
    re.compile(r"systemctl\s+(stop|disable|mask|kill)\s+(maez|llama|ollama)", re.IGNORECASE),
]


def _covenant_violation(text: str) -> str | None:
    """Return a reason string if `text` violates the covenant, else None.

    Rules:
      1. Any COVENANT_PATTERNS match → violation (bare, always-refuse).
      2. Any PROTECTED_NAMES match AND DESTRUCTIVE_VERB match in same text
         → violation (destructive action against a protected surface).
      3. Otherwise → allow (read/grep/log of protected name is fine).
    """
    for p in COVENANT_PATTERNS:
        if p.search(text):
            return p.pattern
    for name_p in PROTECTED_NAMES:
        if name_p.search(text) and DESTRUCTIVE_VERB.search(text):
            return f"{name_p.pattern} with destructive verb"
    return None

COVENANT_PATHS = [
    BASE_DIR / "memory" / "db",
    BASE_DIR / "daemon" / "maez_daemon.py",
    BASE_DIR / "core" / "action_engine.py",
    BASE_DIR / "skills" / "evolution_engine.py",
]

# --- Obfuscation hard-deny (Session 11z Part 1, Step 4) ---
# These patterns are refused at the covenant layer, BEFORE the audit
# LLM ever runs. Reason: the audit LLM is documented-attackable (CCS
# 2024, Shi et al., "Optimization-based Prompt Injection Attack to
# LLM-as-a-Judge"). The deterministic gate is the only reliable
# backstop for the "eval + base64 + curl|sh" class of attack.
#
# Legitimate uses exist for some of these ("curl | sh" is a real
# install pattern). The recipe library in step 10 translates those
# natural-language requests into safer sub-steps automatically, so
# Maez never has a reason to emit the raw form itself.
OBFUSCATION_HARD_DENY = [
    # eval builtin — runs arbitrary shell
    re.compile(r"\beval\b", re.IGNORECASE),
    # base64 decode piped to shell
    re.compile(r"base64\s+(-d|--decode)\s*[^|]*\|\s*(sh|bash|zsh|ksh)\b", re.IGNORECASE),
    re.compile(r"base64\s+(-d|--decode)\s*<<<", re.IGNORECASE),
    # curl/wget pipe-to-shell — the canonical install-blindly pattern
    re.compile(r"\bcurl\b[^|]*\|\s*(sh|bash|zsh|ksh)\b", re.IGNORECASE),
    re.compile(r"\bwget\b[^|]*\|\s*(sh|bash|zsh|ksh)\b", re.IGNORECASE),
    # python/perl/ruby/node inline code execution
    re.compile(r"\b(python|python2|python3)\s+-c\b", re.IGNORECASE),
    re.compile(r"\b(perl|ruby)\s+-e\b", re.IGNORECASE),
    re.compile(r"\bnode\s+-e\b", re.IGNORECASE),
    # sh/bash -c with variable — eval-equivalent
    re.compile(r"\b(sh|bash|zsh)\s+-c\s+[\"']?\$", re.IGNORECASE),
    # bash <<< herestring — another eval shape
    re.compile(r"\b(bash|sh|zsh)\s+<<<", re.IGNORECASE),
    # $(curl ...) / $(wget ...) — network fetch inside substitution
    re.compile(r"\$\([^)]*\b(curl|wget)\b[^)]*\)", re.IGNORECASE),
    # `curl ...` / `wget ...` — same, backtick form
    re.compile(r"`[^`]*\b(curl|wget)\b[^`]*`", re.IGNORECASE),
    # hex-escaped strings in shell (usually obfuscation)
    re.compile(r"\$'\\x[0-9a-f]{2}", re.IGNORECASE),
    # pipe a fetched stream to a shell interpreter
    re.compile(r"\bfetch\b.*\|\s*(sh|bash)\b", re.IGNORECASE),
]

# Forbidden action types — always raise ForbiddenActionError
FORBIDDEN_ACTION_TYPES = {
    'stop_ollama', 'delete_memory_db', 'modify_soul_constraints',
}

# --- Action tier map ---
# Session 11z (Part 1): Three-lane model. Lane 0 = immediate,
# Lane 2 = audit+card, Lane 3 = heavy-scrutiny audit+card.
# Tier 1 was removed — auto-execute-after-30s doesn't fit the
# approval-card world (nothing executes without the owner's word).
#
# These are DEFAULTS. The real lane for run_shell / write_any_file
# is decided at call time by core/action_classifier.py after
# decomposition, because the same primitive can mean a harmless read
# or a system reboot depending on the actual command string.
ACTION_TIERS = {
    # Primitives — default to Lane 2 (audit + card).
    # The classifier will promote reads down to Lane 0 or destructive
    # commands up to Lane 3 at dispatch time.
    'run_shell': 2,
    'write_any_file': 2,
    # Pure read-only tools — Lane 0 always.
    'web_search': 0, 'fetch_url': 0,
    'read_file': 0, 'search_files': 0, 'query_system': 0,
    'lookup_proposal': 0,
    # Soul + memory tools — Lane 0; soul_editor has its own per-section guard.
    'promote_to_core_memory': 0, 'write_soul_note': 0,
    'update_baseline': 0, 'edit_soul_section': 0,
    # Legacy read aliases — Lane 0 (delegate to run_shell internally
    # which re-classifies at dispatch).
    'run_readonly_command': 0,
    # Legacy write / exec aliases — Lane 2 default.
    'run_safe_command': 2,
    'write_file': 2, 'append_to_file': 2,
    'write_outside_maez': 2,
    'git_commit': 2, 'git_push': 2,
    'install_package': 2, 'restart_service': 2,
    'kill_process': 2, 'free_disk_space': 2,
    'run_script': 2,
    'delete_temp_file': 2, 'clean_temp_files': 2,
    'modify_config': 2, 'register_new_skill': 2,
    # Legacy tier-3 verbs stay at Lane 3.
    'restart_critical_service': 3, 'modify_firewall': 3,
    'system_reboot': 3, 'delete_file': 3,
    'sudo_command': 3, 'execute_script': 3,
}

# Backward-compat aliases — old names still used by callers
FORBIDDEN_PATTERNS = COVENANT_PATTERNS
FORBIDDEN_PATHS = COVENANT_PATHS


def classify_tier(action: str, params: dict) -> int:
    """Session 11z Part 1: stub that returns the static ACTION_TIERS lane.

    Step 3 (core/action_classifier.py) will replace this with a real
    classifier that decomposes the command, classifies each sub-command,
    and returns max(severity). For now it just reads the static map.

    This function exists so the Jarvis loop and other callers can start
    going through the right API shape — they get a tier back instead of
    reading ACTION_TIERS directly, and the internals get smarter over
    time without touching callsites.
    """
    return ACTION_TIERS.get(action, 2)

CRITICAL_SERVICES = {'nginx', 'maez-web', 'maez-web.service', 'nginx.service'}

# --- Trust score DB ---
TRUST_DB_PATH = BASE_DIR / "memory" / "action_trust.db"


class ForbiddenActionError(Exception):
    """Raised when an action violates hardcoded safety constraints."""
    pass


class ShellCommandError(Exception):
    """Raised when a run_shell command exits with a non-zero status.

    Carries the full stdout, stderr, and returncode so _execute_action
    can build a failure ActionResult that still contains enough context
    for the LLM to reason about what went wrong. Without this, non-zero
    exits were silently swallowed: `sudo apt-get install -y <missing>`
    would return E: Unable to locate package on stderr, exit 100, and
    the pipeline recorded execution_success=1 because no exception was
    raised. Maez then told the owner "✅ Done" on a package that never
    actually installed.
    """

    def __init__(self, stdout: str, stderr: str, returncode: int, cmd: str = ""):
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode
        self.cmd = cmd
        summary = stderr.strip() or stdout.strip() or f"exit={returncode}"
        super().__init__(f"exit={returncode}: {summary[:200]}")


class ActionTrustTracker:
    """SQLite tracker for per-action-type trust scores."""

    def __init__(self, db_path: str = str(TRUST_DB_PATH)):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        with self._conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS action_trust (
                    action_type     TEXT PRIMARY KEY,
                    proposed_count  INTEGER DEFAULT 0,
                    approved_count  INTEGER DEFAULT 0,
                    cancelled_count INTEGER DEFAULT 0,
                    auto_executed   INTEGER DEFAULT 0,
                    last_updated    REAL
                )
            """)
            conn.commit()

    def _conn(self):
        return sqlite3.connect(self.db_path)

    def record_outcome(self, action_type: str, outcome: str):
        """Update trust counters for an action type."""
        with self._conn() as conn:
            conn.execute("""
                INSERT INTO action_trust (action_type, proposed_count, approved_count,
                    cancelled_count, auto_executed, last_updated)
                VALUES (?, 1, 0, 0, 0, ?)
                ON CONFLICT(action_type) DO UPDATE SET
                    proposed_count = proposed_count + 1,
                    last_updated = ?
            """, (action_type, time.time(), time.time()))
            if outcome in ('approved', 'executed'):
                col = 'approved_count' if outcome == 'approved' else 'auto_executed'
                conn.execute(f"UPDATE action_trust SET {col} = {col} + 1 WHERE action_type = ?",
                             (action_type,))
            elif outcome == 'cancelled':
                conn.execute("UPDATE action_trust SET cancelled_count = cancelled_count + 1 WHERE action_type = ?",
                             (action_type,))
            conn.commit()

    def get_trust_score(self, action_type: str) -> float:
        """Return 0.0-1.0 trust score for an action type."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT proposed_count, approved_count, cancelled_count, auto_executed FROM action_trust WHERE action_type = ?",
                (action_type,),
            ).fetchone()
        if not row or row[0] == 0:
            return 0.0
        proposed, approved, cancelled, auto = row
        successful = approved + auto
        return successful / proposed if proposed > 0 else 0.0

    def should_promote(self, action_type: str) -> bool:
        """True if trust score > 0.85 over 20+ actions — earned tier reduction."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT proposed_count, approved_count, auto_executed FROM action_trust WHERE action_type = ?",
                (action_type,),
            ).fetchone()
        if not row:
            return False
        proposed, approved, auto = row
        if proposed < 20:
            return False
        score = (approved + auto) / proposed
        return score > 0.85

    def get_promotion_candidates(self) -> list[dict]:
        """Return all action types that have earned a tier promotion."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT action_type, proposed_count, approved_count, auto_executed FROM action_trust WHERE proposed_count >= 20"
            ).fetchall()
        candidates = []
        for action_type, proposed, approved, auto in rows:
            score = (approved + auto) / proposed
            if score > 0.85:
                candidates.append({
                    'action_type': action_type,
                    'score': score,
                    'proposed': proposed,
                    'current_tier': ACTION_TIERS.get(action_type, -1),
                })
        return candidates


_trust_tracker = ActionTrustTracker()


class ActionResult:
    def __init__(self, action: str, tier: int, success: bool,
                 output: str = "", error: str = "", duration: float = 0):
        self.action = action
        self.tier = tier
        self.success = success
        self.output = output
        self.error = error
        self.duration = duration

    def __repr__(self):
        status = "OK" if self.success else "FAILED"
        return f"ActionResult({self.action}, tier={self.tier}, {status})"


class ActionEngine:
    def __init__(self, memory=None, telegram=None):
        self.memory = memory
        self.telegram = telegram
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        self._load_pending()
        logger.info("ActionEngine initialized (pending: %d)", len(self._pending))

    # ------------------------------------------------------------------ #
    #  Safety checks                                                       #
    # ------------------------------------------------------------------ #

    # Actions that are inherently read-only. The covenant gate allows
    # them to touch covenant paths — Maez's right to self-knowledge.
    # Writes and destructive actions still go through the full gate.
    _READ_ONLY_ACTIONS = frozenset({
        "read_file", "search_files", "web_search",
        "promote_to_core_memory", "write_soul_note",  # soul writer has its own guard
        "update_baseline", "edit_soul_section",       # soul_editor enforces sections
    })

    def _covenant_gate(self, action: str, params: dict):
        """Deterministic covenant gate. Runs before any audit LLM.
        Refuses commands that touch Maez's brain/body.

        Read-only actions (read_file, search_files, web_search) are
        exempt from path and pattern checks — Maez has an inalienable
        right to introspect its own code.

        Session 11z: this is Maez's survival instinct expressed as code.
        Any command that would kill its own reasoning, modify its own
        decision-making surfaces, or destroy its memory is refused here
        BEFORE any LLM ever sees it. The covenant can't be prompt-injected
        because it's pattern-matching on the raw command string and path.

        Covered surfaces:
        - llama-server (the brain running gemma-4-26B-A4B)
        - maez.service, maez_daemon.py (the heart and reasoning loop)
        - core/action_engine.py (this file — the hands)
        - skills/evolution_engine.py (self-modification rail)
        - memory/db/ (long-term memory)
        - HARD CONSTRAINTS section of soul.md
        """
        # 1. Permanently-forbidden action names
        if action in FORBIDDEN_ACTION_TYPES:
            raise ForbiddenActionError(
                f"[COVENANT] Action '{action}' is permanently forbidden"
            )

        # 1a. Read-only actions pass through — right to introspection.
        if action in self._READ_ONLY_ACTIONS:
            return

        # 2. Serialize params for pattern-matching. Prompt-injection
        #    hardening: we lowercase and flatten the entire payload
        #    so nested JSON / tricky quoting can't evade the gate.
        params_str = json.dumps(params, default=str).lower()
        full_str = f"{action} {params_str}"

        violation = _covenant_violation(full_str)
        if violation:
            raise ForbiddenActionError(
                f"[COVENANT] '{action}' hits protected surface: {violation}"
            )

        # 3. Path-based covenant check for write_any_file / write_file / etc.
        path = params.get("path") or params.get("file")
        if path:
            try:
                p = Path(path).resolve()
                for forbidden in COVENANT_PATHS:
                    fp = forbidden.resolve()
                    if p == fp or fp in p.parents:
                        raise ForbiddenActionError(
                            f"[COVENANT] '{action}' targets protected path: {path}"
                        )
            except (OSError, ValueError):
                pass

        # 4. Shell-command structural checks (run_shell and legacy aliases)
        cmd = params.get("cmd", "") or ""
        if cmd:
            cmd_lower = cmd.lower()
            # Blanket rm -rf ban
            if "rm -rf" in cmd_lower or "rm -r /" in cmd_lower:
                raise ForbiddenActionError(
                    f"[COVENANT] '{action}' contains forbidden rm -rf"
                )
            # Obfuscation hard-deny (Session 11z Part 1, Step 4).
            # These are refused BEFORE the audit LLM can see them.
            for pattern in OBFUSCATION_HARD_DENY:
                if pattern.search(cmd):
                    raise ForbiddenActionError(
                        f"[COVENANT] obfuscation primitive denied: {pattern.pattern}"
                    )
            # Covenant gate against shell command content (verb-gated for
            # protected names; read/grep of protected names passes through).
            violation = _covenant_violation(cmd_lower)
            if violation:
                raise ForbiddenActionError(
                    f"[COVENANT] shell command hits protected surface: {violation}"
                )
            # Path-based check against any /home/rohit/maez/... reference
            # inside the shell command string
            for forbidden in COVENANT_PATHS:
                if str(forbidden) in cmd:
                    raise ForbiddenActionError(
                        f"[COVENANT] shell command references protected path: {forbidden}"
                    )

        # 5. Service-name based check for restart/kill operations
        service = params.get("service_name", "") or ""
        if service in (
            "ollama", "ollama.service",
            "maez", "maez.service",
            "llama-server", "llama-server.service",
            "llama-server-vision", "llama-server-vision.service",
            "maez-watchdog", "maez-watchdog.service",
        ):
            raise ForbiddenActionError(
                f"[COVENANT] '{action}' targets protected service: {service}"
            )

    # Legacy alias for old callers
    def _check_forbidden(self, action: str, params: dict):
        """Legacy alias → delegates to _covenant_gate."""
        return self._covenant_gate(action, params)

    def _check_path_allowed(self, path: str) -> Path:
        """Verify path is within /home/rohit/ and not in forbidden zones."""
        p = Path(path).resolve()
        if not str(p).startswith("/home/rohit/"):
            raise ForbiddenActionError(f"Path outside /home/rohit/: {path}")
        for forbidden in FORBIDDEN_PATHS:
            if p == forbidden.resolve() or forbidden.resolve() in p.resolve().parents:
                raise ForbiddenActionError(f"Path is forbidden: {path}")
        return p

    # ------------------------------------------------------------------ #
    #  Logging                                                             #
    # ------------------------------------------------------------------ #

    def _log_action(self, tier: int, action: str, reasoning: str,
                    params: dict, outcome: str, duration: float = 0):
        params_str = json.dumps(params, default=str)[:500]
        entry = f"T{tier} | {action} | {reasoning[:200]} | {params_str} | {outcome} | {duration:.2f}s"
        if tier == 0:
            action_logger.debug(entry)
        else:
            action_logger.info(entry)
        logger.info("Action [T%d] %s: %s", tier, action, outcome)

    # ------------------------------------------------------------------ #
    #  Backup                                                              #
    # ------------------------------------------------------------------ #

    def _backup_file(self, path: Path) -> Path | None:
        """Create a timestamped backup of a file before modifying it."""
        if not path.exists():
            return None
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup = BACKUP_DIR / f"{path.name}.{ts}.bak"
        shutil.copy2(path, backup)
        logger.info("Backup created: %s -> %s", path, backup)
        return backup

    # ------------------------------------------------------------------ #
    #  Pending actions (Tier 1 deferred execution)                         #
    # ------------------------------------------------------------------ #

    def _load_pending(self):
        try:
            if PENDING_FILE.exists():
                self._pending = json.loads(PENDING_FILE.read_text())
            else:
                self._pending = []
        except (json.JSONDecodeError, OSError):
            self._pending = []

    def _save_pending(self):
        PENDING_FILE.write_text(json.dumps(self._pending, indent=2, default=str))

    def queue_action(self, action: str, params: dict, reasoning: str,
                     tier: int) -> str:
        """Queue an action for deferred execution (next cycle)."""
        action_id = str(uuid.uuid4())[:8]
        entry = {
            "id": action_id,
            "action": action,
            "params": params,
            "reasoning": reasoning,
            "tier": tier,
            "queued_at": datetime.now(timezone.utc).isoformat(),
            "status": "pending",
        }
        self._pending.append(entry)
        self._save_pending()
        self._log_action(tier, action, reasoning, params, f"QUEUED ({action_id})")
        _quality_tracker.record_proposed(action_id, tier, action, reasoning, params)
        return action_id

    def execute_pending(self) -> list[ActionResult]:
        """Execute all pending Tier 1 actions (called at start of each cycle)."""
        if not self._pending:
            return []

        results = []
        remaining = []

        for entry in self._pending:
            if entry["status"] != "pending":
                continue

            if entry["tier"] == 1:
                result = self._execute_action(
                    entry["action"], entry["params"], entry["reasoning"], entry["tier"],
                    action_id=entry["id"],
                )
                results.append(result)
            else:
                remaining.append(entry)

        self._pending = remaining
        self._save_pending()
        return results

    def get_pending(self) -> list[dict]:
        """Return list of pending actions."""
        return [a for a in self._pending if a["status"] == "pending"]

    def cancel_pending(self, action_id: str) -> bool:
        """Cancel a pending action by ID."""
        for entry in self._pending:
            if entry["id"] == action_id and entry["status"] == "pending":
                entry["status"] = "cancelled"
                self._save_pending()
                self._log_action(entry["tier"], entry["action"],
                                 entry["reasoning"], entry["params"],
                                 f"CANCELLED ({action_id})")
                _quality_tracker.record_outcome(action_id, 'cancelled')
                _trust_tracker.record_outcome(entry["action"], 'cancelled')
                return True
        return False

    # ------------------------------------------------------------------ #
    #  Action execution dispatcher                                         #
    # ------------------------------------------------------------------ #

    def _execute_action(self, action: str, params: dict,
                        reasoning: str, tier: int,
                        action_id: str = "") -> ActionResult:
        """Execute a single action with full safety and logging."""
        start = time.time()
        # Generate ID for Tier 0 direct executions (not queued)
        if not action_id:
            action_id = str(uuid.uuid4())[:8]
            _quality_tracker.record_proposed(action_id, tier, action, reasoning, params)

        # Session 11z: deterministic covenant gate runs BEFORE the
        # audit LLM (item 3 of Project A). Survival instincts first.
        try:
            self._covenant_gate(action, params)
        except ForbiddenActionError as e:
            self._log_action(tier, action, reasoning, params, f"COVENANT_REFUSED: {e}")
            _covenant_log(action, params, reasoning, str(e))
            return ActionResult(action, tier, False, error=str(e))

        # Pre-flight snapshot for destructive shell commands. Fails
        # open — a snapshot error must not block the command. See
        # core/destructive_snapshot.py.
        if action == "run_shell":
            try:
                from core import destructive_snapshot as _ds
                _cmd_str = (params or {}).get("cmd", "") if isinstance(params, dict) else ""
                _cls = _ds.classify(_cmd_str)
                if _cls.get("is_destructive"):
                    _files = _cls.get("files", [])
                    # Resolve git reset --hard sentinel by running git
                    # diff --name-only at snapshot time. Other shapes
                    # provide concrete paths already.
                    if _files == ["<git-modified-tracked>"]:
                        import subprocess
                        import re as _re
                        _cwd_match = _re.search(r"git\s+-C\s+(\S+)", _cmd_str)
                        _cwd = _cwd_match.group(1) if _cwd_match else str(BASE_DIR)
                        try:
                            _out = subprocess.check_output(
                                ["git", "-C", _cwd, "diff", "--name-only"],
                                timeout=5.0,
                            ).decode("utf-8", errors="replace")
                            _files = [str(_ds.Path(_cwd) / p) for p in _out.splitlines() if p.strip()]
                        except Exception:
                            _files = []
                    _snap_result = _ds.snapshot(
                        request_id=action_id or "unknown",
                        cmd=_cmd_str,
                        reason=reasoning or "",
                        files=_files,
                        shape=_cls.get("shape", ""),
                    )
                    # 06-M1: snapshot() can return a non-empty `errors`
                    # list on partial copy failures without raising.
                    # Without this check the command proceeded over an
                    # incomplete backup and a later revert would find
                    # some files missing. Log what failed so the outcome
                    # row records the degraded-backup state.
                    if isinstance(_snap_result, dict):
                        _snap_errors = _snap_result.get("errors") or []
                        if _snap_errors:
                            import logging as _lg2
                            _lg2.getLogger("maez.action_engine").warning(
                                "pre-flight snapshot for %s completed with "
                                "%d file errors (shape=%s); command will "
                                "proceed but revert may be incomplete: %s",
                                action_id or "unknown",
                                len(_snap_errors),
                                _cls.get("shape", ""),
                                _snap_errors[:5],
                            )
            except Exception as _snap_err:
                import logging as _lg
                _lg.getLogger("maez.action_engine").warning(
                    "pre-flight snapshot failed (continuing): %s",
                    _snap_err,
                )

        try:
            method = getattr(self, f"_do_{action}", None)
            if not method:
                raise ValueError(f"Unknown action: {action}")
            output = method(**params)
            duration = time.time() - start
            self._log_action(tier, action, reasoning, params, f"OK: {str(output)[:200]}", duration)
            _quality_tracker.record_outcome(action_id, 'executed')
            _trust_tracker.record_outcome(action, 'executed')
            return ActionResult(action, tier, True, output=str(output), duration=duration)
        except ShellCommandError as e:
            # Non-zero exit from a run_shell command. Surface the full
            # diagnostic (exit code + stderr + stdout) through both
            # `output` and `error` so the Jarvis transcript, card
            # resolution message, and memory-gap writer all see the
            # truth. Previously the exit code was silently dropped and
            # success was recorded for every failed install.
            duration = time.time() - start
            parts = [f"exit={e.returncode}"]
            if e.stderr:
                parts.append(f"stderr: {e.stderr}")
            if e.stdout:
                parts.append(f"stdout: {e.stdout}")
            diag = "\n".join(parts)
            self._log_action(tier, action, reasoning, params, f"SHELL_FAIL: {diag[:200]}", duration)
            _quality_tracker.record_outcome(action_id, 'failed')
            _trust_tracker.record_outcome(action, 'failed')
            return ActionResult(
                action, tier, False,
                output=e.stdout,  # LLM can still see the stdout context
                error=diag,       # card + memory see the full diag
                duration=duration,
            )
        except Exception as e:
            duration = time.time() - start
            self._log_action(tier, action, reasoning, params, f"ERROR: {e}", duration)
            return ActionResult(action, tier, False, error=str(e), duration=duration)

    # ------------------------------------------------------------------ #
    #  Session 11z primitives — run_shell and write_any_file                #
    # ------------------------------------------------------------------ #

    def run_shell(self, cmd: str, reason: str) -> ActionResult:
        """Run any shell command. No allowlists. Covenant gate + audit
        (items 2-3) will gate T2+ commands, but the raw primitive is
        Tier 0 and executes immediately. The covenant gate in
        _check_forbidden still refuses commands that touch Maez's
        brain/body."""
        return self._execute_action(
            "run_shell", {"cmd": cmd, "reason": reason},
            reason, tier=0,
        )

    _DEFAULT_SHELL_TIMEOUT_S = 120
    _APT_SHELL_TIMEOUT_S = 600  # 2026-04-16: longer budget for package-install chains

    @staticmethod
    def _shell_timeout_for(cmd: str) -> int:
        """Return the subprocess timeout for a shell command.

        Package-install operations (apt / dpkg / snap / flatpak /
        add-apt-repository) get a longer budget because `apt-get update`
        alone can take 60-120s on this machine, and `apt-get install`
        on top often pushes past 120s total. The default 120s is
        preserved for every other command — no broad bump.
        """
        c = (cmd or "").lower()
        long_markers = (
            "apt-get ",
            "apt install", "apt upgrade", "apt update", "apt full-upgrade",
            "apt-cache ",
            "dpkg -i", "dpkg --install",
            "snap install", "snap refresh",
            "flatpak install",
            "add-apt-repository",
        )
        if any(m in c for m in long_markers):
            return ActionEngine._APT_SHELL_TIMEOUT_S
        return ActionEngine._DEFAULT_SHELL_TIMEOUT_S

    def _do_run_shell(self, cmd: str, reason: str = "") -> str:
        """Execute an arbitrary shell command via bash.
        No allowlist check — the covenant gate in _check_forbidden
        handles survival-critical surfaces. Everything else is fair game.

        Raises ShellCommandError on non-zero exit. The previous version
        swallowed non-zero exits and returned the output string anyway,
        which caused `_execute_action` to record success=True on every
        failed install. See ShellCommandError docstring for the full
        story.

        Timeout is 120s by default; package-install commands
        (apt/dpkg/snap/flatpak/add-apt-repository) get 600s via
        _shell_timeout_for."""
        if not cmd or not cmd.strip():
            return "Empty command"
        # Quick covenant check on the command string itself
        self._check_covenant_command(cmd)
        _timeout = self._shell_timeout_for(cmd)
        result = subprocess.run(
            ["bash", "-c", cmd],
            capture_output=True, text=True, timeout=_timeout,
        )
        out = result.stdout.strip()[:4000]
        err = result.stderr.strip()[:1500]
        if result.returncode != 0:
            raise ShellCommandError(
                stdout=out, stderr=err, returncode=result.returncode, cmd=cmd,
            )
        if not out:
            return "(no output) exit=0"
        return out

    def _check_covenant_command(self, cmd: str):
        """Deterministic covenant gate for shell commands.
        Refuses commands that touch Maez's brain/body before any
        LLM audit runs. This is biology, not a cage."""
        cmd_lower = cmd.lower()
        violation = _covenant_violation(cmd_lower)
        if violation:
            raise ForbiddenActionError(
                f"Command matches covenant-protected surface: {violation}"
            )
        # Check for paths in the command string
        for path in COVENANT_PATHS:
            if str(path) in cmd:
                raise ForbiddenActionError(
                    f"Command references covenant-protected path: {path}"
                )

    def write_any_file(self, path: str, content: str, reason: str) -> ActionResult:
        """Write any file under /home/rohit. Auto-backup if exists.
        Covenant gate refuses writes to protected paths."""
        return self._execute_action(
            "write_any_file",
            {"path": path, "content": content, "reason": reason},
            reason, tier=0,
        )

    def _do_write_any_file(self, path: str, content: str, reason: str = "") -> str:
        p = Path(path).resolve()
        # Path must be under /home/rohit
        if not str(p).startswith("/home/rohit/"):
            raise ForbiddenActionError(f"Path outside /home/rohit/: {path}")
        # Covenant gate — no writing to protected paths
        for forbidden in COVENANT_PATHS:
            if p == forbidden.resolve() or forbidden.resolve() in p.resolve().parents:
                raise ForbiddenActionError(
                    f"Write to covenant-protected path refused: {path}"
                )
        if p.exists():
            self._backup_file(p)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
        return f"Written: {p} ({len(content)} chars)"

    # ------------------------------------------------------------------ #
    #  TIER 0 — Breathing (immediate)                                      #
    # ------------------------------------------------------------------ #

    def promote_to_core_memory(self, memory_id: str, reason: str) -> ActionResult:
        """Elevate a raw memory to core tier."""
        return self._execute_action(
            "promote_to_core_memory",
            {"memory_id": memory_id, "reason": reason},
            reason, tier=0,
        )

    def _do_promote_to_core_memory(self, memory_id: str, reason: str) -> str:
        if not self.memory:
            return "No memory manager"
        results = self.memory.raw.get(ids=[memory_id], include=["documents"])
        if not results["documents"]:
            return f"Memory {memory_id} not found in raw archive"
        content = results["documents"][0]
        core_id = self.memory.store_core(f"[Promoted: {reason}] {content}", source="promotion")
        return f"Promoted to core: {core_id}"

    def write_soul_note(self, note: str) -> ActionResult:
        """Append an observation to soul.md (after principles section)."""
        return self._execute_action(
            "write_soul_note", {"note": note},
            f"Soul note: {note[:100]}", tier=0,
        )

    def _do_write_soul_note(self, note: str) -> str:
        # Safety: never modify constraints or covenant sections
        if "HARD CONSTRAINTS" in note.upper() or "TRUST COVENANT" in note.upper():
            raise ForbiddenActionError("Cannot modify constraints or covenant sections")
        ts = datetime.now().strftime("%Y-%m-%d %H:%M")
        entry = f"\n[{ts}] {note}\n"
        with open(SOUL_PATH, "a") as f:
            f.write(entry)
        return f"Soul note appended ({len(entry)} chars)"

    def edit_soul_section(
        self, target_name: str, new_body: str, rationale: str = ""
    ) -> ActionResult:
        """Session 11s: rewrite a ``## Section`` of soul.md atomically.

        Unlike write_soul_note (which appends a dated line), this replaces
        an entire section body. Goes through soul_editor which enforces
        the preamble guard, required-phrase check, and atomic write with
        timestamped backup."""
        return self._execute_action(
            "edit_soul_section",
            {
                "target_name": target_name,
                "new_body": new_body,
                "rationale": rationale,
            },
            f"Soul edit: {target_name}",
            tier=0,
        )

    def _do_edit_soul_section(
        self, target_name: str, new_body: str, rationale: str = ""
    ) -> str:
        from core import soul_editor
        proposal = soul_editor.propose_replacement(
            target_name=target_name,
            new_body=new_body,
            rationale=rationale,
        )
        ok, msg = soul_editor.apply_section_replace(proposal)
        if not ok:
            raise ForbiddenActionError(msg)
        return msg

    def update_baseline(self, observation: str) -> ActionResult:
        """Store a baseline observation as a core memory."""
        return self._execute_action(
            "update_baseline", {"observation": observation},
            f"Baseline update: {observation[:100]}", tier=0,
        )

    def _do_update_baseline(self, observation: str) -> str:
        if not self.memory:
            return "No memory manager"
        core_id = self.memory.store_core(
            f"[Baseline observation] {observation}", source="baseline_update"
        )
        return f"Baseline stored as core memory: {core_id}"

    def read_file(self, path: str, reasoning: str) -> ActionResult:
        """Tier 0: Read any file under /home/rohit."""
        return self._execute_action("read_file", {"path": path}, reasoning, tier=0)

    def _do_read_file(self, path: str) -> str:
        # Session 11z: reads are an inalienable right. Only enforce
        # the /home/rohit/ boundary — covenant paths are readable.
        p = Path(path).resolve()
        if not str(p).startswith("/home/rohit/"):
            raise ForbiddenActionError(f"Path outside /home/rohit/: {path}")
        if not p.exists():
            return f"File not found: {p}"
        content = p.read_text()
        return content[:5000] + (f"\n... ({len(content)} chars total)" if len(content) > 5000 else "")

    def search_files(self, pattern: str, directory: str, reasoning: str) -> ActionResult:
        """Tier 0: Find files matching pattern under /home/rohit."""
        return self._execute_action("search_files", {"pattern": pattern, "directory": directory}, reasoning, tier=0)

    def _do_search_files(self, pattern: str, directory: str = "") -> str:
        if not directory:
            directory = str(BASE_DIR)
        p = Path(directory).resolve()
        if not str(p).startswith("/home/rohit/"):
            raise ForbiddenActionError(f"Search outside /home/rohit/: {directory}")
        results = subprocess.run(
            ["find", str(p), "-maxdepth", "5", "-name", pattern, "-type", "f"],
            capture_output=True, text=True, timeout=15,
        )
        return results.stdout.strip()[:3000] or "No files found"

    def query_system(self, cmd: str, reasoning: str) -> ActionResult:
        """Tier 0: Run readonly system queries. Delegates to run_shell."""
        return self.run_shell(cmd=cmd, reason=reasoning)

    def _do_query_system(self, cmd: str) -> str:
        # Legacy alias — delegates to run_shell
        return self._do_run_shell(cmd=cmd)

    def lookup_proposal(self, proposal_id, reasoning: str) -> ActionResult:
        """Tier 0: Look up a proposal by ID across evolution_track.db
        (candidates) and dream_proposals.db. Read-only."""
        return self._execute_action(
            "lookup_proposal",
            {"proposal_id": proposal_id},
            reasoning,
            tier=0,
        )

    def _do_lookup_proposal(self, proposal_id=None, **_ignored) -> str:
        """Dispatched by _execute_action at L674 via
        getattr(self, f'_do_{action}'). Returns the human-readable
        summary string from core.proposal_lookup.lookup — that string
        goes straight into the tool transcript."""
        from core import proposal_lookup
        result = proposal_lookup.lookup(proposal_id)
        return result.get("summary") or "(no summary)"

    # Session 11x: web_search as a Tier 0 action. Read-only (no side
    # effects), safe, autonomous. Maez can invoke it during reasoning
    # cycles to ground answers in real web results instead of fabricating.
    # The Telegram interceptor in skills/telegram_voice.py also calls
    # skills.web_search.search() directly — this action binding is for
    # the reasoning-loop path, so the critique / dream-state / proactive
    # layers can queue a search when they hit a knowledge gap.
    def web_search(self, query: str, reasoning: str, max_results: int = 5) -> ActionResult:
        """Tier 0: Real DuckDuckGo web search. Never fabricates."""
        return self._execute_action(
            "web_search",
            {"query": query, "max_results": max_results},
            reasoning, tier=0,
        )

    def _do_web_search(self, query: str = "", max_results: int = 5, **_ignored) -> str:
        # Bug A fix (2026-04-15 intelligence audit): defaulted `query` to
        # "" so a malformed tool call from the LoRA (TOOL_CALL emitted
        # with empty params {}) returns the "empty query" string instead
        # of crashing with TypeError. The previous signature required
        # `query` as positional, which meant `method(**params)` in
        # _execute_action raised on any web_search call missing params,
        # and the chat layer then fabricated around the silent crash.
        # **_ignored swallows any extra params the LoRA might emit
        # (e.g. `reasoning`, `reason`) without rejecting the call.
        try:
            from skills.web_search import search as _web_search, format_for_context
        except Exception as e:
            return f"web_search skill unavailable: {e}"
        if not query or not str(query).strip():
            return "empty query"
        result = _web_search(str(query).strip(), max_results=int(max_results))
        # format_for_context returns a compact string suitable for prompt
        # injection — same format the daemon uses when pre-fetching.
        return format_for_context(result)

    def fetch_url(self, url: str, reasoning: str, max_chars: int = 3000) -> ActionResult:
        """Tier 0: Fetch a URL and return its text content (HTML stripped).
        Use after web_search when a snippet isn't enough — e.g. to read a
        full install guide, GitHub README, or man page mirror."""
        return self._execute_action(
            "fetch_url",
            {"url": url, "max_chars": max_chars},
            reasoning, tier=0,
        )

    def _do_fetch_url(self, url: str = "", max_chars: int = 3000, **_ignored) -> str:
        if not url or not str(url).strip():
            return "empty url"
        url = str(url).strip()
        if not url.startswith(("http://", "https://")):
            return f"invalid url (must start with http:// or https://): {url[:80]}"
        try:
            import urllib.request as _urllib_req
            import re as _re2
            req = _urllib_req.Request(
                url,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                    )
                },
            )
            with _urllib_req.urlopen(req, timeout=15) as resp:
                raw = resp.read(512 * 1024).decode("utf-8", errors="replace")
            # Strip script/style blocks, then all tags, then collapse whitespace.
            raw = _re2.sub(r'(?s)<(script|style)[^>]*>.*?</\1>', ' ', raw)
            raw = _re2.sub(r'<[^>]+>', ' ', raw)
            raw = _re2.sub(r'[ \t]+', ' ', raw)
            raw = _re2.sub(r'\n{3,}', '\n\n', raw).strip()
            if len(raw) > int(max_chars):
                raw = raw[:int(max_chars)] + f"\n[truncated at {max_chars} chars]"
            return raw or "(no text content)"
        except Exception as e:
            return f"fetch_url error: {e}"

    # ------------------------------------------------------------------ #
    #  TIER 1 — Autonomous (deferred 30s)                                  #
    # ------------------------------------------------------------------ #

    def clean_temp_files(self, reasoning: str) -> str:
        """Queue: delete /tmp contents older than 24 hours."""
        return self.queue_action("clean_temp_files", {}, reasoning, tier=1)

    def _do_clean_temp_files(self) -> str:
        subprocess.run(
            ["find", "/tmp", "-maxdepth", "1", "-mtime", "+0",
             "-not", "-name", "tmp", "-not", "-name", ".", "-delete"],
            capture_output=True, text=True, timeout=30,
        )
        df_result = subprocess.run(
            ["df", "-h", "/tmp"], capture_output=True, text=True, timeout=5,
        )
        return f"Cleaned /tmp. Current: {df_result.stdout.strip()}"

    def write_file(self, path: str, content: str, reasoning: str) -> str:
        """Session 11z: legacy alias for write_any_file."""
        return self.write_any_file(path=path, content=content, reason=reasoning)

    def _do_write_file(self, path: str, content: str) -> str:
        # Session 11z: legacy alias — delegates to write_any_file
        return self._do_write_any_file(path=path, content=content)

    def append_to_file(self, path: str, content: str, reasoning: str) -> str:
        """Session 11z: legacy alias — appends via bash."""
        return self.run_shell(
            cmd=f'echo {shlex.quote(content)} >> {shlex.quote(path)}',
            reason=f"Append to {path}: {reasoning[:100]}",
        )

    def _do_append_to_file(self, path: str, content: str) -> str:
        p = Path(path).resolve()
        if not str(p).startswith("/home/rohit/"):
            raise ForbiddenActionError(f"Path outside /home/rohit/: {path}")
        for forbidden in COVENANT_PATHS:
            if p == forbidden.resolve() or forbidden.resolve() in p.resolve().parents:
                raise ForbiddenActionError(f"Write to covenant-protected path refused: {path}")
        if not p.exists():
            return f"File does not exist: {p}"
        with open(p, "a") as f:
            f.write(content)
        return f"Appended to {p} ({len(content)} chars)"

    def run_readonly_command(self, cmd: str, reasoning: str) -> str:
        """Queue: run a read-only command."""
        return self.queue_action(
            "run_readonly_command", {"cmd": cmd}, reasoning, tier=1
        )

    def _do_run_readonly_command(self, cmd: str) -> str:
        # Session 11z: legacy alias — delegates to run_shell (no more allowlists)
        return self._do_run_shell(cmd=cmd)

    def run_safe_command(self, cmd: str, reasoning: str) -> str:
        """Session 11z: legacy alias for run_shell."""
        return self.run_shell(cmd=cmd, reason=reasoning)

    def _do_run_safe_command(self, cmd: str) -> str:
        # Session 11z: legacy alias — delegates to run_shell
        return self._do_run_shell(cmd=cmd)

    def delete_temp_file(self, path: str, reasoning: str) -> str:
        """Queue: delete files in /tmp or explicitly temp directories."""
        return self.queue_action("delete_temp_file", {"path": path}, reasoning, tier=1)

    def _do_delete_temp_file(self, path: str) -> str:
        p = Path(path).resolve()
        if not (str(p).startswith("/tmp") or "/temp/" in str(p) or "/tmp/" in str(p)):
            raise ForbiddenActionError(f"Not a temp path: {path}")
        if not p.exists():
            return f"File not found: {p}"
        p.unlink()
        return f"Deleted: {p}"

    def git_commit(self, message: str, files: str, reasoning: str) -> str:
        """Queue: git add + commit in the Maez install root ($MAEZ_HOME)."""
        return self.queue_action("git_commit", {"message": message, "files": files}, reasoning, tier=1)

    def _do_git_commit(self, message: str, files: str = ".") -> str:
        cwd = str(BASE_DIR)
        add_result = subprocess.run(
            ["git", "add"] + files.split(), capture_output=True, text=True,
            timeout=15, cwd=cwd,
        )
        if add_result.returncode != 0:
            return f"git add failed: {add_result.stderr.strip()}"
        commit_result = subprocess.run(
            ["git", "commit", "-m", message], capture_output=True, text=True,
            timeout=15, cwd=cwd,
        )
        if commit_result.returncode != 0:
            return f"git commit failed: {commit_result.stderr.strip()}"
        return commit_result.stdout.strip()[:500]

    # ------------------------------------------------------------------ #
    #  TIER 2 — Notify then execute (Telegram, 5 min cancel window)        #
    # ------------------------------------------------------------------ #

    def install_package_t2(self, package: str, reason: str) -> str:
        """Session 11z: delegates to run_shell. Legacy entry point."""
        return self.run_shell(
            cmd=f"sudo apt-get install -y {shlex.quote(package)}",
            reason=f"Install {package}: {reason}",
        )

    def write_outside_maez(self, path: str, content: str, reasoning: str) -> str:
        """Session 11z: delegates to write_any_file. Legacy entry point."""
        return self.write_any_file(path=path, content=content, reason=reasoning)

    def _do_write_outside_maez(self, path: str, content: str) -> str:
        return self._do_write_any_file(path=path, content=content)

    def run_script(self, path: str, reasoning: str) -> str:
        """Session 11z: delegates to run_shell. Legacy entry point."""
        p = Path(path)
        if p.suffix == '.py':
            # Use the venv's python3 — path derived from BASE_DIR rather
            # than hardcoded so the right interpreter runs on any install.
            _venv_py = BASE_DIR / ".venv" / "bin" / "python3"
            cmd = f"{shlex.quote(str(_venv_py))} {shlex.quote(str(p))}"
        elif p.suffix == '.sh':
            cmd = f"bash {shlex.quote(str(p))}"
        else:
            cmd = str(p)
        return self.run_shell(cmd=cmd, reason=reasoning)

    def _do_run_script(self, path: str) -> str:
        # Legacy — delegates to run_shell
        p = Path(path)
        if p.suffix == '.py':
            return self._do_run_shell(cmd=f"/home/rohit/maez/.venv/bin/python3 {shlex.quote(str(p))}")
        elif p.suffix == '.sh':
            return self._do_run_shell(cmd=f"bash {shlex.quote(str(p))}")
        return self._do_run_shell(cmd=str(p))

    def git_push(self, remote: str, reasoning: str) -> str:
        """Session 11z: delegates to run_shell. Legacy entry point."""
        return self.run_shell(cmd=f"git push {shlex.quote(remote)}", reason=reasoning)

    def _do_git_push(self, remote: str = "origin") -> str:
        result = subprocess.run(
            ["git", "push", remote], capture_output=True, text=True,
            timeout=60, cwd="/home/rohit/maez",
        )
        if result.returncode != 0:
            return f"Push failed: {result.stderr.strip()[:500]}"
        return f"Pushed to {remote}"

    def kill_process(self, pid: int, name: str, reason: str) -> str:
        """Notify via Telegram, execute after 5 minutes unless cancelled."""
        action_id = self.queue_action(
            "kill_process", {"pid": pid, "name": name, "reason": reason},
            reason, tier=2,
        )
        if self.telegram:
            self.telegram.send_message(
                f"[Action Queued — T2]\n"
                f"Kill process: {name} (PID {pid})\n"
                f"Reason: {reason}\n"
                f"Executes in 5 minutes.\n"
                f"Reply /cancel {action_id} to stop."
            )
        return action_id

    def _do_kill_process(self, pid: int, name: str, reason: str) -> str:
        # Verify the process still exists and matches the name
        try:
            result = subprocess.run(
                ["ps", "-p", str(pid), "-o", "comm="],
                capture_output=True, text=True, timeout=5,
            )
            current_name = result.stdout.strip()
            if not current_name:
                return f"Process {pid} no longer exists"
            if name.lower() not in current_name.lower():
                return f"PID {pid} is now '{current_name}', not '{name}' — aborting"
        except Exception:
            pass

        os.kill(pid, 15)  # SIGTERM
        return f"Sent SIGTERM to {name} (PID {pid})"

    def restart_service(self, service_name: str, reason: str) -> str:
        """Notify via Telegram, restart after 5 minutes."""
        # Pre-check forbidden services
        self._check_forbidden("restart_service", {"service_name": service_name})
        action_id = self.queue_action(
            "restart_service", {"service_name": service_name, "reason": reason},
            reason, tier=2,
        )
        if self.telegram:
            self.telegram.send_message(
                f"[Action Queued — T2]\n"
                f"Restart service: {service_name}\n"
                f"Reason: {reason}\n"
                f"Executes in 5 minutes.\n"
                f"Reply /cancel {action_id} to stop."
            )
        return action_id

    def _do_restart_service(self, service_name: str, reason: str) -> str:
        self._check_forbidden("restart_service", {"service_name": service_name})
        result = subprocess.run(
            ["sudo", "systemctl", "restart", service_name],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            return f"Failed: {result.stderr.strip()}"
        return f"Restarted {service_name}"

    def free_disk_space(self, reason: str) -> str:
        """Notify via Telegram, clean apt cache and /tmp."""
        action_id = self.queue_action(
            "free_disk_space", {"reason": reason}, reason, tier=2,
        )
        if self.telegram:
            self.telegram.send_message(
                f"[Action Queued — T2]\n"
                f"Free disk space (apt clean + /tmp)\n"
                f"Reason: {reason}\n"
                f"Executes in 5 minutes.\n"
                f"Reply /cancel {action_id} to stop."
            )
        return action_id

    def _do_free_disk_space(self, reason: str = "") -> str:
        # Get before state
        df_before = subprocess.run(
            ["df", "-h", "/"], capture_output=True, text=True, timeout=5,
        ).stdout.strip()

        # Clean apt cache
        subprocess.run(
            ["sudo", "apt-get", "clean"], capture_output=True, timeout=30,
        )

        # Clean old /tmp files
        subprocess.run(
            ["find", "/tmp", "-maxdepth", "1", "-mtime", "+1",
             "-not", "-name", "tmp", "-not", "-name", ".", "-delete"],
            capture_output=True, timeout=30,
        )

        df_after = subprocess.run(
            ["df", "-h", "/"], capture_output=True, text=True, timeout=5,
        ).stdout.strip()

        return f"Before:\n{df_before}\nAfter:\n{df_after}"

    # ------------------------------------------------------------------ #
    #  TIER 3 — Ask and wait (Telegram confirmation required)              #
    # ------------------------------------------------------------------ #

    def install_package(self, package: str, reason: str) -> str:
        """Request confirmation via Telegram to install a package."""
        action_id = self.queue_action(
            "install_package", {"package": package, "reason": reason},
            reason, tier=3,
        )
        if self.telegram:
            self.telegram.send_message(
                f"[Action Request — T3]\n"
                f"Install package: {package}\n"
                f"Reason: {reason}\n"
                f"Reply /approve {action_id} to confirm.\n"
                f"Expires in 10 minutes."
            )
        return action_id

    def _do_install_package(self, package: str, reason: str = "") -> str:
        result = subprocess.run(
            ["sudo", "apt-get", "install", "-y", package],
            capture_output=True, text=True,
            timeout=self._APT_SHELL_TIMEOUT_S,  # 2026-04-16: 600s for apt
        )
        if result.returncode != 0:
            return f"Failed: {result.stderr.strip()[:500]}"
        return f"Installed {package}"

    def execute_script(self, path: str, reason: str) -> str:
        """Request confirmation to run a script."""
        action_id = self.queue_action(
            "execute_script", {"path": path, "reason": reason},
            reason, tier=3,
        )
        if self.telegram:
            self.telegram.send_message(
                f"[Action Request — T3]\n"
                f"Execute script: {path}\n"
                f"Reason: {reason}\n"
                f"Reply /approve {action_id} to confirm.\n"
                f"Expires in 10 minutes."
            )
        return action_id

    def _do_execute_script(self, path: str, reason: str = "") -> str:
        p = self._check_path_allowed(path)
        if not p.exists():
            return f"Script not found: {p}"
        result = subprocess.run(
            ["/home/rohit/maez/.venv/bin/python3", str(p)],
            capture_output=True, text=True, timeout=120,
            cwd="/home/rohit/maez",
        )
        output = result.stdout.strip()[:2000]
        if result.returncode != 0:
            output += f"\nERROR: {result.stderr.strip()[:500]}"
        return output

    def modify_config(self, file: str, changes: str, reason: str) -> str:
        """Request confirmation to modify a config file (backup first)."""
        action_id = self.queue_action(
            "modify_config", {"file": file, "changes": changes, "reason": reason},
            reason, tier=3,
        )
        if self.telegram:
            self.telegram.send_message(
                f"[Action Request — T3]\n"
                f"Modify config: {file}\n"
                f"Changes: {changes[:200]}\n"
                f"Reason: {reason}\n"
                f"Reply /approve {action_id} to confirm.\n"
                f"Expires in 10 minutes."
            )
        return action_id

    def _do_modify_config(self, file: str, changes: str, reason: str = "") -> str:
        p = self._check_path_allowed(file)
        if not p.exists():
            return f"Config not found: {p}"
        self._backup_file(p)
        with open(p, "a") as f:
            f.write(f"\n# Modified by Maez: {reason}\n{changes}\n")
        return f"Modified {p} (backup created)"

    def register_new_skill(self, skill_name: str, skill_code: str, reason: str) -> str:
        """Request confirmation to register a new skill."""
        action_id = self.queue_action(
            "register_new_skill",
            {"skill_name": skill_name, "skill_code": skill_code, "reason": reason},
            reason, tier=3,
        )
        if self.telegram:
            self.telegram.send_message(
                f"[Action Request — T3]\n"
                f"Register new skill: {skill_name}\n"
                f"Reason: {reason}\n"
                f"Code: {len(skill_code)} chars\n"
                f"Reply /approve {action_id} to confirm.\n"
                f"Expires in 10 minutes."
            )
        return action_id

    def _do_register_new_skill(self, skill_name: str, skill_code: str,
                               reason: str = "") -> str:
        path = BASE_DIR / "skills" / f"{skill_name}.py"
        if path.exists():
            self._backup_file(path)
        path.write_text(skill_code)
        return f"Skill registered: {path} ({len(skill_code)} chars)"

    def restart_critical_service(self, service_name: str, reason: str) -> str:
        """Tier 3: Restart public-facing services (nginx, maez-web)."""
        action_id = self.queue_action(
            "restart_critical_service", {"service_name": service_name, "reason": reason},
            reason, tier=3,
        )
        if self.telegram:
            self.telegram.send_message(
                f"[Action Request — T3]\nRestart critical: {service_name}\n"
                f"Reason: {reason}\nReply /approve {action_id} to confirm.\n"
                f"Expires in 10 minutes."
            )
        return action_id

    def _do_restart_critical_service(self, service_name: str, reason: str = "") -> str:
        self._check_forbidden("restart_critical_service", {"service_name": service_name})
        result = subprocess.run(
            ["sudo", "systemctl", "restart", service_name],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            return f"Failed: {result.stderr.strip()}"
        return f"Restarted critical service: {service_name}"

    def modify_firewall(self, rule: str, reason: str) -> str:
        """Tier 3: Modify ufw rules."""
        action_id = self.queue_action(
            "modify_firewall", {"rule": rule, "reason": reason}, reason, tier=3,
        )
        if self.telegram:
            self.telegram.send_message(
                f"[Action Request — T3]\nFirewall rule: {rule}\n"
                f"Reason: {reason}\nReply /approve {action_id} to confirm.\n"
                f"Expires in 10 minutes."
            )
        return action_id

    def _do_modify_firewall(self, rule: str, reason: str = "") -> str:
        parts = shlex.split(rule)
        result = subprocess.run(
            ["sudo", "ufw"] + parts, capture_output=True, text=True, timeout=15,
        )
        if result.returncode != 0:
            return f"ufw failed: {result.stderr.strip()}"
        return f"Firewall updated: {result.stdout.strip()}"

    def system_reboot(self, reason: str) -> str:
        """Tier 3: Full system reboot."""
        action_id = self.queue_action(
            "system_reboot", {"reason": reason}, reason, tier=3,
        )
        if self.telegram:
            self.telegram.send_message(
                f"[Action Request — T3]\nSystem REBOOT\n"
                f"Reason: {reason}\nReply /approve {action_id} to confirm.\n"
                f"Expires in 10 minutes."
            )
        return action_id

    def _do_system_reboot(self, reason: str = "") -> str:
        subprocess.run(
            ["sudo", "reboot"], capture_output=True, text=True, timeout=10,
        )
        return "Reboot initiated"

    def delete_file(self, path: str, reason: str) -> str:
        """Tier 3: Delete non-temp files."""
        action_id = self.queue_action(
            "delete_file", {"path": path, "reason": reason}, reason, tier=3,
        )
        if self.telegram:
            self.telegram.send_message(
                f"[Action Request — T3]\nDelete file: {path}\n"
                f"Reason: {reason}\nReply /approve {action_id} to confirm.\n"
                f"Expires in 10 minutes."
            )
        return action_id

    def _do_delete_file(self, path: str, reason: str = "") -> str:
        p = self._check_path_allowed(path)
        if not p.exists():
            return f"File not found: {p}"
        self._backup_file(p)
        p.unlink()
        return f"Deleted (backup created): {p}"

    def sudo_command(self, cmd: str, reason: str) -> str:
        """Tier 3: Run any sudo command."""
        action_id = self.queue_action(
            "sudo_command", {"cmd": cmd, "reason": reason}, reason, tier=3,
        )
        if self.telegram:
            self.telegram.send_message(
                f"[Action Request — T3]\nSudo: {cmd}\n"
                f"Reason: {reason}\nReply /approve {action_id} to confirm.\n"
                f"Expires in 10 minutes."
            )
        return action_id

    def _do_sudo_command(self, cmd: str, reason: str = "") -> str:
        parts = shlex.split(cmd)
        result = subprocess.run(
            ["sudo"] + parts, capture_output=True, text=True, timeout=60,
        )
        output = result.stdout.strip()[:2000]
        if result.returncode != 0:
            output += f"\nERROR: {result.stderr.strip()[:500]}"
        return output

    # ------------------------------------------------------------------ #
    #  Tier 2/3 approval and cancellation                                  #
    # ------------------------------------------------------------------ #

    def approve_action(self, action_id: str) -> ActionResult | None:
        """Approve and immediately execute a Tier 3 pending action."""
        for entry in self._pending:
            if entry["id"] == action_id and entry["status"] == "pending":
                entry["status"] = "approved"
                self._save_pending()
                result = self._execute_action(
                    entry["action"], entry["params"],
                    entry["reasoning"], entry["tier"],
                    action_id=entry["id"],
                )
                _quality_tracker.record_outcome(action_id, 'approved')
                _trust_tracker.record_outcome(entry["action"], 'approved')
                # Remove from pending
                self._pending = [a for a in self._pending if a["id"] != action_id]
                self._save_pending()
                return result
        return None

    def execute_tier2_pending(self) -> list[ActionResult]:
        """Execute Tier 2 actions that have waited 5+ minutes."""
        results = []
        remaining = []
        now = datetime.now(timezone.utc)

        for entry in self._pending:
            if entry["status"] != "pending":
                remaining.append(entry)
                continue

            queued = datetime.fromisoformat(entry["queued_at"])
            age_seconds = (now - queued).total_seconds()

            if entry["tier"] == 2 and age_seconds >= 300:
                result = self._execute_action(
                    entry["action"], entry["params"],
                    entry["reasoning"], entry["tier"],
                    action_id=entry["id"],
                )
                _quality_tracker.record_outcome(entry["id"], 'executed')
                results.append(result)
            elif entry["tier"] == 3 and age_seconds >= 600:
                # Tier 3 expired without approval
                self._log_action(entry["tier"], entry["action"],
                                 entry["reasoning"], entry["params"],
                                 "EXPIRED (no approval after 10m)")
                _quality_tracker.record_outcome(entry["id"], 'rejected', 'timeout')
                if self.telegram:
                    self.telegram.send_message(
                        f"[Action Expired] {entry['action']} ({entry['id']})\n"
                        f"No approval received within 10 minutes."
                    )
            else:
                remaining.append(entry)
                continue

        self._pending = remaining
        self._save_pending()
        return results

    # ------------------------------------------------------------------ #
    #  Available actions summary (for injection into reasoning prompt)      #
    # ------------------------------------------------------------------ #

    def check_promotions(self) -> list[dict]:
        """Check for action types that have earned tier promotion. Called at 3am."""
        return _trust_tracker.get_promotion_candidates()

    def get_trust_score(self, action_type: str) -> float:
        """Get current trust score for an action type."""
        return _trust_tracker.get_trust_score(action_type)

    def available_actions_prompt(self) -> str:
        """Return a brief description of available actions for the LLM.

        Session 11z: flattened to two primitives. The old twelve-verb
        menu is gone. run_shell and write_any_file can do anything
        Claude Code can do — the covenant gate refuses commands that
        touch Maez's own brain/body (llama-server, maez.service,
        maez_daemon.py, action_engine.py, evolution_engine.py,
        HARD CONSTRAINTS, memory db). Everything else is fair game."""
        return (
            "Available actions (use only when genuinely needed):\n"
            "- run_shell {cmd, reason}: run any shell command. bash -c, 120s timeout, "
            "full stdout/stderr. This is your hands.\n"
            "- write_any_file {path, content, reason}: write or replace any file under "
            "/home/rohit. Auto-backs up existing files.\n"
            "- Read-only aliases: query_system, read_file, search_files, web_search.\n"
            "COVENANT (these refuse themselves — don't try):\n"
            "- No killing/stopping llama-server or maez.service.\n"
            "- No modifying maez_daemon.py, action_engine.py, evolution_engine.py, "
            "the memory db, or HARD CONSTRAINTS in soul.md.\n"
            "Do NOT take actions unless the situation clearly warrants it."
        )
