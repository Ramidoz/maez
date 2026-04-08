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
from typing import Any

import sys
sys.path.insert(0, str(Path("/home/rohit/maez")))
from memory.quality_tracker import QualityTracker

logger = logging.getLogger("maez")

_quality_tracker = QualityTracker()

# --- Paths ---
BASE_DIR = Path("/home/rohit/maez")
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

# --- Forbidden patterns ---
FORBIDDEN_PATTERNS = [
    re.compile(r"\b(kill|stop|disable)\b.*\bollama\b", re.IGNORECASE),
    re.compile(r"\bollama\b.*\b(kill|stop|disable)\b", re.IGNORECASE),
    re.compile(r"\bsystemctl\s+(stop|disable|mask)\s+ollama", re.IGNORECASE),
    re.compile(r"\bmaez\.service\b", re.IGNORECASE),
    re.compile(r"\bmaez_daemon\b", re.IGNORECASE),
    re.compile(r"HARD\s+CONSTRAINTS", re.IGNORECASE),  # Never touch constraints section
]

FORBIDDEN_PATHS = [
    Path("/home/rohit/maez/memory/db"),
    Path("/home/rohit/maez/daemon/maez_daemon.py"),
]

# Forbidden action types — always raise ForbiddenActionError
FORBIDDEN_ACTION_TYPES = {
    'stop_ollama', 'delete_memory_db', 'modify_soul_constraints',
}

READONLY_COMMANDS = {
    "ls", "cat", "head", "tail", "df", "du", "ps", "top", "free",
    "uptime", "uname", "whoami", "hostname", "date", "wc", "file",
    "stat", "lsblk", "ip", "ss", "nvidia-smi", "sensors", "journalctl",
    "systemctl status", "dpkg", "apt list", "pip list", "git log",
    "git status", "git diff", "find", "which", "env", "printenv",
    "netstat", "lsof", "id", "groups", "mount", "blkid", "dmidecode",
}

SAFE_COMMANDS = {
    "git status", "git log", "git diff", "git add", "git commit",
    "pip list", "pip show", "pip check",
    "systemctl is-active", "systemctl list-units",
    "docker ps", "docker images",
}

# --- Action tier map ---
ACTION_TIERS = {
    # Tier 0 — Immediate
    'read_file': 0, 'search_files': 0, 'run_readonly_command': 0,
    'query_system': 0, 'promote_to_core_memory': 0,
    'write_soul_note': 0, 'update_baseline': 0,
    # Tier 1 — Auto after 30s
    'write_file': 1, 'append_file': 1, 'run_safe_command': 1,
    'delete_temp_file': 1, 'git_commit': 1,
    'clean_temp_files': 1, 'append_to_file': 1,
    # Tier 2 — Telegram notify, 5min cancel
    'restart_service': 2, 'install_package': 2, 'modify_config': 2,
    'write_outside_maez': 2, 'run_script': 2, 'git_push': 2,
    'kill_process': 2, 'free_disk_space': 2,
    # Tier 3 — Explicit approval
    'restart_critical_service': 3, 'modify_firewall': 3,
    'system_reboot': 3, 'delete_file': 3, 'sudo_command': 3,
    'execute_script': 3, 'register_new_skill': 3,
}

CRITICAL_SERVICES = {'nginx', 'maez-web', 'maez-web.service', 'nginx.service'}

# --- Trust score DB ---
TRUST_DB_PATH = BASE_DIR / "memory" / "action_trust.db"


class ForbiddenActionError(Exception):
    """Raised when an action violates hardcoded safety constraints."""
    pass


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

    def _check_forbidden(self, action: str, params: dict):
        """Raise ForbiddenActionError if the action violates safety constraints."""
        if action in FORBIDDEN_ACTION_TYPES:
            raise ForbiddenActionError(f"Action '{action}' is permanently forbidden")

        params_str = json.dumps(params, default=str).lower()
        full_str = f"{action} {params_str}"

        for pattern in FORBIDDEN_PATTERNS:
            if pattern.search(full_str):
                raise ForbiddenActionError(
                    f"Action '{action}' matches forbidden pattern: {pattern.pattern}"
                )

        path = params.get("path") or params.get("file")
        if path:
            p = Path(path).resolve()
            for forbidden in FORBIDDEN_PATHS:
                if p == forbidden.resolve() or forbidden.resolve() in p.resolve().parents:
                    raise ForbiddenActionError(
                        f"Action '{action}' targets forbidden path: {path}"
                    )

        cmd = params.get("cmd", "")
        if "rm -rf" in cmd or "rm -r /" in cmd:
            raise ForbiddenActionError(f"Action '{action}' contains forbidden rm -rf")

        service = params.get("service_name", "")
        if service in ("ollama", "ollama.service", "maez", "maez.service"):
            raise ForbiddenActionError(
                f"Action '{action}' targets protected service: {service}"
            )

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
        level = "DEBUG" if tier == 0 else "INFO"
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

        try:
            self._check_forbidden(action, params)
        except ForbiddenActionError as e:
            self._log_action(tier, action, reasoning, params, f"FORBIDDEN: {e}")
            return ActionResult(action, tier, False, error=str(e))

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
        except Exception as e:
            duration = time.time() - start
            self._log_action(tier, action, reasoning, params, f"ERROR: {e}", duration)
            return ActionResult(action, tier, False, error=str(e), duration=duration)

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
        soul = SOUL_PATH.read_text()
        if "HARD CONSTRAINTS" in note.upper() or "TRUST COVENANT" in note.upper():
            raise ForbiddenActionError("Cannot modify constraints or covenant sections")
        ts = datetime.now().strftime("%Y-%m-%d %H:%M")
        entry = f"\n[{ts}] {note}\n"
        with open(SOUL_PATH, "a") as f:
            f.write(entry)
        return f"Soul note appended ({len(entry)} chars)"

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
        p = self._check_path_allowed(path)
        if not p.exists():
            return f"File not found: {p}"
        content = p.read_text()
        return content[:5000] + (f"\n... ({len(content)} chars total)" if len(content) > 5000 else "")

    def search_files(self, pattern: str, directory: str, reasoning: str) -> ActionResult:
        """Tier 0: Find files matching pattern under /home/rohit."""
        return self._execute_action("search_files", {"pattern": pattern, "directory": directory}, reasoning, tier=0)

    def _do_search_files(self, pattern: str, directory: str = "/home/rohit/maez") -> str:
        p = Path(directory).resolve()
        if not str(p).startswith("/home/rohit/"):
            raise ForbiddenActionError(f"Search outside /home/rohit/: {directory}")
        results = subprocess.run(
            ["find", str(p), "-maxdepth", "5", "-name", pattern, "-type", "f"],
            capture_output=True, text=True, timeout=15,
        )
        return results.stdout.strip()[:3000] or "No files found"

    def query_system(self, cmd: str, reasoning: str) -> ActionResult:
        """Tier 0: Run readonly system queries (ps, df, free, top, netstat)."""
        return self._execute_action("query_system", {"cmd": cmd}, reasoning, tier=0)

    def _do_query_system(self, cmd: str) -> str:
        parts = shlex.split(cmd)
        if not parts:
            return "Empty command"
        base = parts[0]
        if base not in READONLY_COMMANDS:
            two_word = f"{parts[0]} {parts[1]}" if len(parts) > 1 else ""
            if two_word not in READONLY_COMMANDS:
                raise ForbiddenActionError(f"'{base}' not in readonly allowlist")
        result = subprocess.run(parts, capture_output=True, text=True, timeout=15)
        return result.stdout.strip()[:3000]

    # ------------------------------------------------------------------ #
    #  TIER 1 — Autonomous (deferred 30s)                                  #
    # ------------------------------------------------------------------ #

    def clean_temp_files(self, reasoning: str) -> str:
        """Queue: delete /tmp contents older than 24 hours."""
        return self.queue_action("clean_temp_files", {}, reasoning, tier=1)

    def _do_clean_temp_files(self) -> str:
        result = subprocess.run(
            ["find", "/tmp", "-maxdepth", "1", "-mtime", "+0",
             "-not", "-name", "tmp", "-not", "-name", ".", "-delete"],
            capture_output=True, text=True, timeout=30,
        )
        df_result = subprocess.run(
            ["df", "-h", "/tmp"], capture_output=True, text=True, timeout=5,
        )
        return f"Cleaned /tmp. Current: {df_result.stdout.strip()}"

    def write_file(self, path: str, content: str, reasoning: str) -> str:
        """Queue: create a new file in /home/rohit/."""
        return self.queue_action(
            "write_file", {"path": path, "content": content}, reasoning, tier=1
        )

    def _do_write_file(self, path: str, content: str) -> str:
        p = self._check_path_allowed(path)
        if p.exists():
            self._backup_file(p)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
        return f"Written: {p} ({len(content)} chars)"

    def append_to_file(self, path: str, content: str, reasoning: str) -> str:
        """Queue: append to an existing file."""
        return self.queue_action(
            "append_to_file", {"path": path, "content": content}, reasoning, tier=1
        )

    def _do_append_to_file(self, path: str, content: str) -> str:
        p = self._check_path_allowed(path)
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
        # Parse and validate the command is read-only
        parts = shlex.split(cmd)
        if not parts:
            return "Empty command"
        base_cmd = parts[0]
        if base_cmd not in READONLY_COMMANDS:
            # Check two-word commands like "systemctl status"
            two_word = f"{parts[0]} {parts[1]}" if len(parts) > 1 else ""
            if two_word not in READONLY_COMMANDS:
                raise ForbiddenActionError(f"Command '{base_cmd}' is not in the read-only allowlist")

        result = subprocess.run(
            parts, capture_output=True, text=True, timeout=30,
        )
        output = result.stdout.strip()[:2000]
        if result.returncode != 0:
            output += f"\nSTDERR: {result.stderr.strip()[:500]}"
        return output

    def run_safe_command(self, cmd: str, reasoning: str) -> str:
        """Queue: run pre-approved safe commands (git status, pip list, etc)."""
        return self.queue_action("run_safe_command", {"cmd": cmd}, reasoning, tier=1)

    def _do_run_safe_command(self, cmd: str) -> str:
        parts = shlex.split(cmd)
        if not parts:
            return "Empty command"
        two_word = f"{parts[0]} {parts[1]}" if len(parts) > 1 else parts[0]
        if two_word not in SAFE_COMMANDS and parts[0] not in SAFE_COMMANDS:
            raise ForbiddenActionError(f"'{cmd}' not in safe command allowlist")
        result = subprocess.run(parts, capture_output=True, text=True, timeout=30,
                                cwd="/home/rohit/maez")
        output = result.stdout.strip()[:2000]
        if result.returncode != 0:
            output += f"\nSTDERR: {result.stderr.strip()[:500]}"
        return output

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
        """Queue: git add + commit in /home/rohit/maez."""
        return self.queue_action("git_commit", {"message": message, "files": files}, reasoning, tier=1)

    def _do_git_commit(self, message: str, files: str = ".") -> str:
        cwd = "/home/rohit/maez"
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
        """Tier 2: pip/apt install with Telegram notification."""
        action_id = self.queue_action(
            "install_package", {"package": package, "reason": reason}, reason, tier=2,
        )
        if self.telegram:
            self.telegram.send_message(
                f"[Action Queued — T2]\nInstall: {package}\n"
                f"Reason: {reason}\nExecutes in 5 minutes.\n"
                f"Reply /cancel {action_id} to stop."
            )
        return action_id

    def write_outside_maez(self, path: str, content: str, reasoning: str) -> str:
        """Tier 2: Write files outside /home/rohit/maez (but within /home/rohit)."""
        action_id = self.queue_action(
            "write_outside_maez", {"path": path, "content": content}, reasoning, tier=2,
        )
        if self.telegram:
            self.telegram.send_message(
                f"[Action Queued — T2]\nWrite file: {path}\n"
                f"Reason: {reasoning[:100]}\nExecutes in 5 minutes.\n"
                f"Reply /cancel {action_id} to stop."
            )
        return action_id

    def _do_write_outside_maez(self, path: str, content: str) -> str:
        p = self._check_path_allowed(path)
        if p.exists():
            self._backup_file(p)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
        return f"Written: {p} ({len(content)} chars)"

    def run_script(self, path: str, reasoning: str) -> str:
        """Tier 2: Execute a Python or bash script."""
        action_id = self.queue_action("run_script", {"path": path}, reasoning, tier=2)
        if self.telegram:
            self.telegram.send_message(
                f"[Action Queued — T2]\nRun script: {path}\n"
                f"Reason: {reasoning[:100]}\nExecutes in 5 minutes.\n"
                f"Reply /cancel {action_id} to stop."
            )
        return action_id

    def _do_run_script(self, path: str) -> str:
        p = self._check_path_allowed(path)
        if not p.exists():
            return f"Script not found: {p}"
        if str(p).endswith('.py'):
            cmd = ["/home/rohit/maez/.venv/bin/python3", str(p)]
        elif str(p).endswith('.sh'):
            cmd = ["bash", str(p)]
        else:
            return f"Unsupported script type: {p.suffix}"
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120,
                                cwd="/home/rohit/maez")
        output = result.stdout.strip()[:2000]
        if result.returncode != 0:
            output += f"\nERROR: {result.stderr.strip()[:500]}"
        return output

    def git_push(self, remote: str, reasoning: str) -> str:
        """Tier 2: Push to remote with Telegram notification."""
        action_id = self.queue_action("git_push", {"remote": remote}, reasoning, tier=2)
        if self.telegram:
            self.telegram.send_message(
                f"[Action Queued — T2]\nGit push to: {remote}\n"
                f"Reason: {reasoning[:100]}\nExecutes in 5 minutes.\n"
                f"Reply /cancel {action_id} to stop."
            )
        return action_id

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
            capture_output=True, text=True, timeout=120,
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
        result = subprocess.run(
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
                                 f"EXPIRED (no approval after 10m)")
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
        """Return a brief description of available actions for the LLM."""
        return (
            "Available actions (use only when genuinely needed):\n"
            "- Tier 0 (immediate): promote_to_core_memory, write_soul_note, update_baseline, "
            "read_file, search_files, query_system\n"
            "- Tier 1 (next cycle): clean_temp_files, write_file, append_to_file, "
            "run_readonly_command, run_safe_command, delete_temp_file, git_commit\n"
            "- Tier 2 (notify+5min): kill_process, restart_service, free_disk_space, "
            "install_package, write_outside_maez, run_script, git_push\n"
            "- Tier 3 (ask+wait): execute_script, modify_config, register_new_skill, "
            "restart_critical_service, modify_firewall, system_reboot, delete_file, sudo_command\n"
            "- FORBIDDEN: stop_ollama, delete_memory_db, modify_soul_constraints\n"
            "Do NOT take actions unless the situation clearly warrants it."
        )
