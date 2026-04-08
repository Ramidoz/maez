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
]

FORBIDDEN_PATHS = [
    Path("/home/rohit/maez/memory/db"),
    Path("/home/rohit/maez/daemon/maez_daemon.py"),
]

READONLY_COMMANDS = {
    "ls", "cat", "head", "tail", "df", "du", "ps", "top", "free",
    "uptime", "uname", "whoami", "hostname", "date", "wc", "file",
    "stat", "lsblk", "ip", "ss", "nvidia-smi", "sensors", "journalctl",
    "systemctl status", "dpkg", "apt list", "pip list", "git log",
    "git status", "git diff", "find", "which", "env", "printenv",
}


class ForbiddenActionError(Exception):
    """Raised when an action violates hardcoded safety constraints."""
    pass


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

    # ------------------------------------------------------------------ #
    #  TIER 2 — Notify then execute (Telegram, 5 min cancel window)        #
    # ------------------------------------------------------------------ #

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

    def available_actions_prompt(self) -> str:
        """Return a brief description of available actions for the LLM."""
        return (
            "Available actions (use only when genuinely needed):\n"
            "- Tier 0 (immediate): promote_to_core_memory, write_soul_note, update_baseline\n"
            "- Tier 1 (next cycle): clean_temp_files, write_file, append_to_file, run_readonly_command\n"
            "- Tier 2 (notify+5min): kill_process, restart_service, free_disk_space\n"
            "- Tier 3 (ask+wait): install_package, execute_script, modify_config, register_new_skill\n"
            "Do NOT take actions unless the situation clearly warrants it."
        )
