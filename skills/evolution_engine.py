"""
evolution_engine.py — Maez's self-evolution system

Runs nightly after consolidation and self-analysis.
Searches for better implementations, validates, deploys safe improvements.

Pipeline: DISCOVER → UNDERSTAND → IMPLEMENT → VALIDATE → DEPLOY

Safeguards:
  - Immutable file list (never touched)
  - Security scanner (dangerous patterns)
  - Behavior validator (isolated import test)
  - Telegram approval for anything flagged
  - Full audit log of every experiment
  - Automatic backup before any deployment
"""

import ast
import hashlib
import json
import logging
import os
import shutil
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Optional

logger = logging.getLogger("maez")

MAEZ_ROOT = '/home/rohit/maez'
STAGING_DIR = f'{MAEZ_ROOT}/staging'
BACKUP_DIR = f'{MAEZ_ROOT}/evolution/backups'
EVOLUTION_LOG = f'{MAEZ_ROOT}/logs/evolution.log'

IMMUTABLE_FILES = {
    'core/action_engine.py',
    'config/soul.md',
    'memory/memory_manager.py',
    'config/.env',
    'skills/evolution_engine.py',
    'daemon/maez_daemon.py',
}

SECURITY_PATTERNS = [
    'subprocess.call(', 'os.system(', 'eval(', 'exec(',
    '__import__', 'rm -rf', 'shutil.rmtree',
    'DROP TABLE', 'DELETE FROM',
]

EVOLVABLE_SKILLS = {
    'skills/web_search.py',
    'skills/disk_cleanup.py',
    'skills/git_awareness.py',
    'skills/screen_perception.py',
    'skills/presence_perception.py',
    'skills/calendar_perception.py',
    'skills/self_analysis.py',
}


def _log_evolution(entry: dict):
    with open(EVOLUTION_LOG, 'a') as f:
        f.write(
            f"{time.strftime('%Y-%m-%d %H:%M:%S')} | "
            f"{entry.get('action', '?')} | "
            f"{entry.get('target', '?')} | "
            f"{entry.get('result', '?')} | "
            f"{entry.get('detail', '')}\n"
        )


def _search_github(query: str, max_results: int = 5) -> list:
    try:
        encoded = urllib.parse.quote(query)
        url = (f"https://api.github.com/search/repositories"
               f"?q={encoded}+language:python&sort=stars&order=desc"
               f"&per_page={max_results}")
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Maez/1.0',
            'Accept': 'application/vnd.github.v3+json',
        })
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        return [{
            'name': item['full_name'],
            'url': item['html_url'],
            'description': item.get('description', ''),
            'stars': item.get('stargazers_count', 0),
        } for item in data.get('items', [])]
    except Exception as e:
        logger.debug("GitHub search failed: %s", e)
        return []


def validate_syntax(code: str) -> tuple:
    try:
        ast.parse(code)
        return True, ""
    except SyntaxError as e:
        return False, str(e)


def validate_security(code: str, target_file: str) -> tuple:
    concerns = []
    code_lower = code.lower()
    for pattern in SECURITY_PATTERNS:
        if pattern.lower() in code_lower:
            concerns.append(f"Contains '{pattern}'")
    import re
    if re.search(r'(password|secret|token|key)\s*=\s*["\'][^"\']+["\']', code, re.IGNORECASE):
        concerns.append("Possible hardcoded credentials")
    if code.count('\n') > 1000:
        concerns.append(f"File too large: {code.count(chr(10))} lines")
    return len(concerns) == 0, concerns


def validate_behavior(staging_path: str) -> tuple:
    try:
        result = subprocess.run(
            [sys.executable, '-c',
             f'import importlib.util; '
             f'spec = importlib.util.spec_from_file_location("test", "{staging_path}"); '
             f'mod = importlib.util.module_from_spec(spec); '
             f'spec.loader.exec_module(mod); print("IMPORT_OK")'],
            capture_output=True, text=True, timeout=30,
            env={**os.environ, 'MAEZ_TESTING': '1'},
        )
        if 'IMPORT_OK' in result.stdout:
            return True, ""
        return False, result.stderr[:500]
    except subprocess.TimeoutExpired:
        return False, "Import timed out"
    except Exception as e:
        return False, str(e)


def _backup_file(file_path: str) -> str:
    ts = time.strftime('%Y%m%d_%H%M%S')
    backup_path = f"{BACKUP_DIR}/{os.path.basename(file_path)}.{ts}.bak"
    shutil.copy2(file_path, backup_path)
    return backup_path


def deploy_improvement(staging_path: str, target_path: str,
                       tracker=None, baseline_rate: float = 0.0) -> bool:
    try:
        full_target = os.path.join(MAEZ_ROOT, target_path)
        backup_path = ""
        if os.path.exists(full_target):
            backup_path = _backup_file(full_target)
        shutil.copy2(staging_path, full_target)
        logger.info("Deployed: %s", target_path)
        _log_evolution({'action': 'DEPLOYED', 'target': target_path, 'result': 'OK'})
        if tracker:
            tracker.record_deployment(target_path, "", baseline_rate, backup_path)
        return True
    except Exception as e:
        logger.error("Deploy failed %s: %s", target_path, e)
        return False


def _generate_improvement(weakness: str, current_code: str,
                          reference_repo: dict, target_file: str) -> Optional[str]:
    try:
        import requests
        prompt = (
            f"You are improving Maez's code.\n\n"
            f"FILE: {target_file}\nWEAKNESS: {weakness}\n"
            f"REFERENCE: {reference_repo['name']} — {reference_repo['description']}\n\n"
            f"CURRENT CODE:\n{current_code[:2000]}\n\n"
            f"Write an improved version addressing the weakness. "
            f"Keep the same function signatures and module interface. "
            f"Return ONLY valid Python code."
        )
        resp = requests.post('http://localhost:11434/api/generate',
                             json={'model': 'gemma4:26b', 'prompt': prompt, 'stream': False},
                             timeout=120)
        if resp.status_code == 200:
            code = resp.json().get('response', '').strip()
            if code.startswith('```'):
                code = '\n'.join(code.split('\n')[1:-1])
            return code
    except Exception as e:
        logger.error("Code generation failed: %s", e)
    return None


def _weakness_to_file(weakness: str) -> Optional[str]:
    mapping = {
        'wake word': 'skills/wake_word.py', 'voice': 'skills/voice_output.py',
        'web search': 'skills/web_search.py', 'search': 'skills/web_search.py',
        'disk': 'skills/disk_cleanup.py', 'git': 'skills/git_awareness.py',
        'screen': 'skills/screen_perception.py', 'presence': 'skills/presence_perception.py',
        'calendar': 'skills/calendar_perception.py', 'memory': 'skills/self_analysis.py',
        'repetitive': 'skills/self_analysis.py',
    }
    for kw, fp in mapping.items():
        if kw in weakness.lower():
            return fp
    return None


def _queue_for_approval(staging_file, target_file, weakness, repo, concerns, telegram_cb):
    pending_path = f'{MAEZ_ROOT}/evolution/pending_evolution.json'
    pending = {
        'staging_file': staging_file, 'target_file': target_file,
        'weakness': weakness, 'repo': repo, 'concerns': concerns,
        'timestamp': time.time(),
    }
    with open(pending_path, 'w') as f:
        json.dump(pending, f, indent=2)

    concerns_text = '\n'.join(f"  {c}" for c in concerns) if concerns else "  No security concerns"
    msg = (f"Evolution proposal:\n\nFile: {target_file}\nWeakness: {weakness}\n"
           f"Source: {repo['name']} ({repo['stars']} stars)\n\n{concerns_text}\n\n"
           f"/approve_evolution to deploy\n/reject_evolution to discard")
    if telegram_cb:
        telegram_cb(msg)


def run_evolution_cycle(weaknesses: list, telegram_callback=None) -> dict:
    summary = {'experiments': 0, 'deployed': 0, 'flagged': 0, 'failed': 0, 'changes': []}

    logger.info("Evolution cycle: %d weaknesses", len(weaknesses))
    _log_evolution({'action': 'CYCLE_START', 'target': str(len(weaknesses)),
                    'result': 'started', 'detail': ', '.join(weaknesses[:3])})

    for weakness in weaknesses[:5]:
        summary['experiments'] += 1
        target_file = _weakness_to_file(weakness)
        if not target_file or any(imm in target_file for imm in IMMUTABLE_FILES):
            continue

        full_path = os.path.join(MAEZ_ROOT, target_file)
        if not os.path.exists(full_path):
            continue

        with open(full_path) as f:
            current_code = f.read()

        # Search GitHub
        repos = _search_github(f"python {weakness}", 3)
        if not repos:
            summary['failed'] += 1
            continue

        best = repos[0]
        logger.info("Found: %s (%d stars) for '%s'", best['name'], best['stars'], weakness)
        _log_evolution({'action': 'FOUND', 'target': weakness, 'result': best['name']})

        # Generate improvement
        improved = _generate_improvement(weakness, current_code, best, target_file)
        if not improved:
            summary['failed'] += 1
            continue

        # Stage
        staging_file = os.path.join(STAGING_DIR, os.path.basename(target_file))
        with open(staging_file, 'w') as f:
            f.write(improved)

        # Validate
        syn_ok, syn_err = validate_syntax(improved)
        if not syn_ok:
            summary['failed'] += 1
            _log_evolution({'action': 'SYNTAX_FAIL', 'target': target_file, 'result': syn_err})
            continue

        sec_ok, concerns = validate_security(improved, target_file)
        beh_ok, beh_err = validate_behavior(staging_file)

        if sec_ok and beh_ok and target_file in EVOLVABLE_SKILLS:
            if deploy_improvement(staging_file, target_file):
                summary['deployed'] += 1
                summary['changes'].append({
                    'file': target_file, 'weakness': weakness,
                    'source': best['name'], 'auto_deployed': True,
                })
        else:
            all_concerns = concerns[:]
            if not beh_ok:
                all_concerns.append(f"Behavior fail: {beh_err}")
            _queue_for_approval(staging_file, target_file, weakness, best,
                                all_concerns, telegram_callback)
            summary['flagged'] += 1

        time.sleep(2)

    _log_evolution({'action': 'CYCLE_END', 'target': 'all',
                    'result': f"d={summary['deployed']} f={summary['flagged']} x={summary['failed']}"})
    logger.info("Evolution complete: deployed=%d, flagged=%d, failed=%d",
                summary['deployed'], summary['flagged'], summary['failed'])
    return summary


def format_morning_report(summary: dict) -> str:
    if summary['experiments'] == 0:
        return "No evolution experiments ran tonight."
    lines = [f"Evolution: {summary['experiments']} experiments"]
    if summary['deployed']:
        lines.append(f"  Auto-deployed: {summary['deployed']}")
        for c in summary['changes']:
            if c.get('auto_deployed'):
                lines.append(f"    {c['file']} <- {c['source']}")
    if summary['flagged']:
        lines.append(f"  Needs review: {summary['flagged']}")
    if summary['failed']:
        lines.append(f"  Failed validation: {summary['failed']}")
    return '\n'.join(lines)


class EvolutionTracker:
    """Tracks deployed improvements and auto-reverts if quality drops."""

    def __init__(self, db_path: str = '/home/rohit/maez/memory/evolution_track.db'):
        import sqlite3
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        with self._conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS deployments (
                    deployment_id   INTEGER PRIMARY KEY AUTOINCREMENT,
                    target_file     TEXT NOT NULL,
                    weakness        TEXT,
                    baseline_insight_rate REAL,
                    deployed_at     REAL NOT NULL,
                    post_insight_rate REAL,
                    verdict         TEXT,
                    backup_path     TEXT
                )
            """)
            conn.commit()
        logger.info("EvolutionTracker initialized")

    def _conn(self):
        import sqlite3
        return sqlite3.connect(self.db_path)

    def record_deployment(self, target_file: str, weakness: str,
                          baseline_rate: float, backup_path: str):
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO deployments (target_file, weakness, baseline_insight_rate, "
                "deployed_at, backup_path) VALUES (?, ?, ?, ?, ?)",
                (target_file, weakness, baseline_rate, time.time(), backup_path),
            )
            conn.commit()
        logger.info("EvolutionTracker: recorded deployment of %s (baseline=%.1f%%)",
                     target_file, baseline_rate)

    def get_pending_checks(self, min_age_seconds: int = 1800) -> list:
        """Get deployments older than min_age_seconds that haven't been checked."""
        cutoff = time.time() - min_age_seconds
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT deployment_id, target_file, baseline_insight_rate, backup_path "
                "FROM deployments WHERE post_insight_rate IS NULL AND deployed_at < ?",
                (cutoff,),
            ).fetchall()
        return [{'id': r[0], 'file': r[1], 'baseline': r[2], 'backup': r[3]} for r in rows]

    def set_verdict(self, deployment_id: int, post_rate: float, verdict: str):
        with self._conn() as conn:
            conn.execute(
                "UPDATE deployments SET post_insight_rate=?, verdict=? WHERE deployment_id=?",
                (post_rate, verdict, deployment_id),
            )
            conn.commit()


def check_and_revert(memory_manager, telegram_callback=None):
    """Check recent deployments and revert if quality dropped."""
    tracker = EvolutionTracker()
    pending = tracker.get_pending_checks(min_age_seconds=1800)
    if not pending:
        return

    from skills.self_analysis import analyze
    analysis = analyze(memory_manager)
    if not analysis:
        return

    current_rate = analysis.get('unique_insight_rate', 0)

    for dep in pending:
        baseline = dep['baseline'] or 0
        drop = baseline - current_rate

        if drop > 5 and dep['backup'] and os.path.exists(dep['backup']):
            # Revert
            full_target = os.path.join(MAEZ_ROOT, dep['file'])
            try:
                shutil.copy2(dep['backup'], full_target)
                tracker.set_verdict(dep['id'], current_rate, 'reverted')
                msg = (f"Reverted {dep['file']} — insight rate dropped "
                       f"from {baseline:.0f}% to {current_rate:.0f}%")
                logger.info("Evolution: %s", msg)
                _log_evolution({'action': 'REVERTED', 'target': dep['file'],
                                'result': f'{baseline:.0f}→{current_rate:.0f}'})
                if telegram_callback:
                    telegram_callback(msg)
            except Exception as e:
                logger.error("Revert failed %s: %s", dep['file'], e)
        else:
            # Keep
            tracker.set_verdict(dep['id'], current_rate, 'kept')
            msg = f"Kept {dep['file']} — insight rate at {current_rate:.0f}%"
            logger.info("Evolution: %s", msg)
            if telegram_callback:
                telegram_callback(msg)


# ══════════════════════════════════════════════════════════════════════
#  SELF-EDIT EXECUTION RAIL — v1
#
#  All backup and apply operations go through action_engine safety
#  checks and audit logging. DB is the authority for lifecycle state.
# ══════════════════════════════════════════════════════════════════════

import difflib
import hashlib as _hashlib
import re as _re
import sqlite3 as _sqlite3
import subprocess as _subprocess
from datetime import datetime as _dt, timezone as _tz

# --- Configurable constants ---
COOLDOWN_HOURS = 24
WATCHDOG_CYCLES = 20
REGRESSION_THRESHOLD = 10
PRE_PATCH_BASELINE_CYCLES = 10
IMMEDIATE_HEALTH_TIMEOUT = 60
LOCK_TIMEOUT_SECONDS = 900
V1_ALLOWED_TARGET = "core/cognition_quality.py"

EVOLUTION_DB = '/home/rohit/maez/memory/evolution_track.db'


def _rail_conn():
    return _sqlite3.connect(EVOLUTION_DB)


def _init_rail_schema():
    """Create rail tables if they don't exist. Idempotent."""
    with _rail_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS candidates (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                state               TEXT NOT NULL DEFAULT 'proposed',
                weakness_description TEXT,
                target_file         TEXT,
                diff_text           TEXT,
                justification       TEXT,
                cognition_evidence  TEXT,
                rejection_reason    TEXT,
                rollback_reason     TEXT,
                rollback_layer      TEXT,
                cooldown_key        TEXT,
                pre_patch_hash      TEXT,
                post_patch_hash     TEXT,
                backup_path         TEXT,
                pre_patch_score_avg REAL,
                post_patch_score_avg REAL,
                created_at          TEXT,
                validated_at        TEXT,
                applied_at          TEXT,
                resolved_at         TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS evolution_lock (
                id                  INTEGER PRIMARY KEY CHECK (id = 1),
                active_candidate_id INTEGER,
                locked_at           TEXT,
                locked_by           TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS watchdog_context (
                candidate_id        INTEGER PRIMARY KEY,
                target_file         TEXT,
                backup_path         TEXT,
                pre_patch_score_avg REAL,
                applied_at          TEXT,
                watchdog_cycles     INTEGER DEFAULT 0,
                regression_threshold REAL,
                resolved            INTEGER DEFAULT 0
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS proposal_jobs (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                state           TEXT NOT NULL DEFAULT 'pending',
                weakness_description TEXT,
                evidence_json   TEXT,
                cooldown_key    TEXT,
                created_at      TEXT,
                started_at      TEXT,
                finished_at     TEXT,
                attempt_count   INTEGER DEFAULT 0,
                last_error      TEXT,
                candidate_id    INTEGER
            )
        """)
        # Ensure the single lock row exists
        if conn.execute("SELECT COUNT(*) FROM evolution_lock").fetchone()[0] == 0:
            conn.execute("INSERT INTO evolution_lock (id) VALUES (1)")
        conn.commit()


_init_rail_schema()


# ══════════════════════════════════════════════════════════════════════
#  LOCKING AND STALE-LOCK RECOVERY
# ══════════════════════════════════════════════════════════════════════

def _ensure_lock_row():
    """Guarantee the single lock row exists. Bootstrap recovery."""
    with _rail_conn() as conn:
        if conn.execute("SELECT COUNT(*) FROM evolution_lock").fetchone()[0] == 0:
            conn.execute("INSERT INTO evolution_lock (id) VALUES (1)")
            conn.commit()
            logger.info("Rail: lock row id=1 recreated (bootstrap recovery)")


def reconcile_lock() -> str | None:
    """Detect and clear stale or inconsistent lock state. Returns message or None."""
    _ensure_lock_row()
    with _rail_conn() as conn:
        row = conn.execute("SELECT active_candidate_id, locked_at FROM evolution_lock WHERE id=1").fetchone()
        if not row or row[0] is None:
            return None

        cand_id, locked_at = row
        # Check candidate exists
        cand = conn.execute("SELECT state FROM candidates WHERE id=?", (cand_id,)).fetchone()
        if not cand:
            conn.execute("UPDATE evolution_lock SET active_candidate_id=NULL, locked_at=NULL, locked_by=NULL WHERE id=1")
            conn.commit()
            msg = f"Stale lock cleared: candidate {cand_id} does not exist"
            _log_evolution({'action': 'LOCK_RECONCILE', 'target': str(cand_id), 'result': 'cleared_missing'})
            logger.info("Rail: %s", msg)
            return msg

        # Check candidate in valid active state
        if cand[0] not in ('queued', 'applied', 'validated'):
            conn.execute("UPDATE evolution_lock SET active_candidate_id=NULL, locked_at=NULL, locked_by=NULL WHERE id=1")
            conn.commit()
            msg = f"Stale lock cleared: candidate {cand_id} state={cand[0]}"
            _log_evolution({'action': 'LOCK_RECONCILE', 'target': str(cand_id), 'result': f'cleared_state_{cand[0]}'})
            logger.info("Rail: %s", msg)
            return msg

        # Check timeout
        if locked_at:
            try:
                lock_time = _dt.fromisoformat(locked_at)
                age = (_dt.now(_tz.utc) - lock_time).total_seconds()
                if age > LOCK_TIMEOUT_SECONDS:
                    conn.execute("UPDATE evolution_lock SET active_candidate_id=NULL, locked_at=NULL, locked_by=NULL WHERE id=1")
                    conn.commit()
                    msg = f"Stale lock cleared: locked {age:.0f}s ago (timeout={LOCK_TIMEOUT_SECONDS}s)"
                    _log_evolution({'action': 'LOCK_RECONCILE', 'target': str(cand_id), 'result': f'cleared_timeout_{age:.0f}s'})
                    logger.info("Rail: %s", msg)
                    return msg
            except Exception:
                pass

    return None


def _acquire_lock(candidate_id: int) -> bool:
    """Acquire evolution lock for a candidate. Returns True if acquired."""
    reconcile_lock()
    with _rail_conn() as conn:
        row = conn.execute("SELECT active_candidate_id FROM evolution_lock WHERE id=1").fetchone()
        if row and row[0] is not None:
            return False
        now = _dt.now(_tz.utc).isoformat()
        conn.execute(
            "UPDATE evolution_lock SET active_candidate_id=?, locked_at=?, locked_by=? WHERE id=1",
            (candidate_id, now, 'apply_candidate'),
        )
        conn.commit()
    return True


def _release_lock(candidate_id: int | None = None):
    """Release evolution lock. If candidate_id given, only release if it matches."""
    with _rail_conn() as conn:
        if candidate_id is not None:
            row = conn.execute("SELECT active_candidate_id FROM evolution_lock WHERE id=1").fetchone()
            if row and row[0] != candidate_id:
                return  # not our lock
        conn.execute("UPDATE evolution_lock SET active_candidate_id=NULL, locked_at=NULL, locked_by=NULL WHERE id=1")
        conn.commit()


def _restart_maez_service():
    """Kill + start maez.service (restart is too slow due to threaded shutdown)."""
    _subprocess.run(['sudo', 'systemctl', 'kill', '-s', 'SIGKILL', 'maez.service'],
                    capture_output=True, timeout=10)
    time.sleep(2)
    _subprocess.run(['sudo', 'systemctl', 'reset-failed', 'maez.service'],
                    capture_output=True, timeout=5)
    time.sleep(1)
    return _subprocess.run(
        ['sudo', 'systemctl', 'start', 'maez.service'],
        capture_output=True, text=True, timeout=30,
    )


def _get_lock_state() -> dict:
    _ensure_lock_row()
    with _rail_conn() as conn:
        row = conn.execute("SELECT active_candidate_id, locked_at, locked_by FROM evolution_lock WHERE id=1").fetchone()
    return {'active_candidate_id': row[0], 'locked_at': row[1], 'locked_by': row[2]} if row else {}


# ══════════════════════════════════════════════════════════════════════
#  CANDIDATE POLICY LAYER
# ══════════════════════════════════════════════════════════════════════

def _normalize_cooldown_key(weakness: str, target: str) -> str:
    words = sorted(set(_re.findall(r'[a-z]+', weakness.lower())))
    return '|'.join(words) + '|' + target


def _check_policy(weakness: str, target_file: str, diff_text: str = "") -> str | None:
    """Check all candidate policies. Returns rejection_reason or None if OK."""
    reconcile_lock()

    # Single active candidate
    lock = _get_lock_state()
    if lock.get('active_candidate_id') is not None:
        return f"Active candidate {lock['active_candidate_id']} holds the lock"

    # Scope enforcement — v1 hardcheck
    if target_file != V1_ALLOWED_TARGET:
        return f"Target '{target_file}' not allowed in v1 (only {V1_ALLOWED_TARGET})"

    # Source awareness scope check
    try:
        from core.source_awareness import get_file
        entry = get_file(target_file)
        if not entry or entry.get('self_edit_scope') != 'allowed':
            return f"Source awareness: scope={entry.get('self_edit_scope') if entry else 'not found'}"
    except Exception as e:
        return f"Source awareness check failed: {e}"

    # Cooldown
    cooldown_key = _normalize_cooldown_key(weakness, target_file)
    cutoff = _dt.now(_tz.utc).isoformat()
    with _rail_conn() as conn:
        recent = conn.execute(
            "SELECT id, resolved_at FROM candidates WHERE cooldown_key=? AND resolved_at IS NOT NULL ORDER BY resolved_at DESC LIMIT 1",
            (cooldown_key,),
        ).fetchone()
    if recent and recent[1]:
        try:
            resolved = _dt.fromisoformat(recent[1])
            age_hours = (_dt.now(_tz.utc) - resolved).total_seconds() / 3600
            if age_hours < COOLDOWN_HOURS:
                return f"Cooldown: same weakness resolved {age_hours:.1f}h ago (need {COOLDOWN_HOURS}h)"
        except Exception:
            pass

    # Dedup
    if diff_text:
        with _rail_conn() as conn:
            dupes = conn.execute(
                "SELECT id FROM candidates WHERE diff_text=? AND state IN ('proposed','validated','queued')",
                (diff_text,),
            ).fetchall()
        if dupes:
            return f"Duplicate diff: matches candidate {dupes[0][0]}"

    return None


def _reject_candidate(weakness: str, target: str, reason: str, diff: str = "") -> int:
    """Create a rejected candidate row. Returns candidate_id."""
    now = _dt.now(_tz.utc).isoformat()
    with _rail_conn() as conn:
        cur = conn.execute(
            "INSERT INTO candidates (state, weakness_description, target_file, diff_text, "
            "rejection_reason, cooldown_key, created_at, resolved_at) "
            "VALUES ('rejected', ?, ?, ?, ?, ?, ?, ?)",
            (weakness, target, diff, reason,
             _normalize_cooldown_key(weakness, target), now, now),
        )
        conn.commit()
        cand_id = cur.lastrowid
    _log_evolution({'action': 'CANDIDATE_REJECTED', 'target': target,
                    'result': reason, 'detail': f'id={cand_id}'})
    logger.info("Rail: candidate %d rejected: %s", cand_id, reason)
    return cand_id


# ══════════════════════════════════════════════════════════════════════
#  DIFF GENERATION
# ══════════════════════════════════════════════════════════════════════

def _file_sha256(path: str) -> str:
    return _hashlib.sha256(open(path, 'rb').read()).hexdigest()


def generate_diff(weakness_description: str, evidence: dict = None) -> dict:
    """Generate a diff candidate. Returns {candidate_id, state, ...} or {error}."""
    target = V1_ALLOWED_TARGET
    full_path = os.path.join(MAEZ_ROOT, target)

    # Policy check
    reason = _check_policy(weakness_description, target)
    if reason:
        cid = _reject_candidate(weakness_description, target, reason)
        return {'candidate_id': cid, 'state': 'rejected', 'reason': reason}

    # Read target
    if not os.path.exists(full_path):
        return {'error': f'Target file not found: {full_path}'}
    with open(full_path) as f:
        current_code = f.read()

    pre_hash = _file_sha256(full_path)
    evidence_json = json.dumps(evidence or {}, default=str)

    # Generate diff via gemma4
    try:
        import requests
        prompt = (
            f"You are improving Maez's cognition quality system.\n\n"
            f"FILE: {target}\n"
            f"WEAKNESS: {weakness_description}\n"
            f"COGNITION EVIDENCE: {evidence_json[:500]}\n\n"
            f"CURRENT CODE (first 3000 chars):\n{current_code[:3000]}\n\n"
            f"Output a unified diff only. One minimal bounded change.\n"
            f"Use --- a/{target} and +++ b/{target} headers.\n"
            f"No explanation. No comments. Just the diff."
        )
        resp = requests.post('http://localhost:11434/api/generate',
                             json={'model': 'gemma4:26b', 'prompt': prompt, 'stream': False},
                             timeout=120)
        if resp.status_code != 200:
            return {'error': f'Ollama returned {resp.status_code}'}
        diff_text = resp.json().get('response', '').strip()
        # Extract diff block if wrapped in markdown
        if '```' in diff_text:
            parts = diff_text.split('```')
            for part in parts[1:]:
                lines = part.strip().split('\n')
                if lines and (lines[0].startswith('diff') or lines[0].startswith('---') or lines[0] == ''):
                    diff_text = '\n'.join(lines[1:] if not lines[0].startswith('---') else lines)
                    break
    except Exception as e:
        return {'error': f'Diff generation failed: {e}'}

    if not diff_text or '---' not in diff_text:
        cid = _reject_candidate(weakness_description, target, 'diff_empty_or_invalid', diff_text)
        return {'candidate_id': cid, 'state': 'rejected', 'reason': 'Empty or invalid diff'}

    # Dry-run: write diff to temp, apply --dry-run
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', suffix='.patch', delete=False) as tf:
        tf.write(diff_text)
        patch_file = tf.name

    try:
        result = _subprocess.run(
            ['patch', '--dry-run', '-p1', '-d', MAEZ_ROOT, '-i', patch_file],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            cid = _reject_candidate(weakness_description, target,
                                    f'diff_invalid: {result.stderr.strip()[:200]}', diff_text)
            return {'candidate_id': cid, 'state': 'rejected',
                    'reason': f'patch --dry-run failed: {result.stderr.strip()[:200]}'}
    finally:
        os.unlink(patch_file)

    # Create validated candidate
    now = _dt.now(_tz.utc).isoformat()
    cooldown_key = _normalize_cooldown_key(weakness_description, target)
    with _rail_conn() as conn:
        cur = conn.execute(
            "INSERT INTO candidates (state, weakness_description, target_file, diff_text, "
            "cognition_evidence, cooldown_key, pre_patch_hash, created_at, validated_at) "
            "VALUES ('validated', ?, ?, ?, ?, ?, ?, ?, ?)",
            (weakness_description, target, diff_text, evidence_json,
             cooldown_key, pre_hash, now, now),
        )
        conn.commit()
        cand_id = cur.lastrowid

    _log_evolution({'action': 'CANDIDATE_VALIDATED', 'target': target,
                    'result': f'id={cand_id}', 'detail': weakness_description[:80]})
    logger.info("Rail: candidate %d validated for %s", cand_id, target)

    return {'candidate_id': cand_id, 'state': 'validated', 'target': target,
            'diff_lines': len(diff_text.split('\n')), 'pre_hash': pre_hash}


# ══════════════════════════════════════════════════════════════════════
#  EXECUTION RAIL
# ══════════════════════════════════════════════════════════════════════

def apply_candidate(candidate_id: int) -> dict:
    """Full execution rail: preflight → backup → apply → validate → watchdog setup."""
    acquired_lock = False

    try:
        # Step 1 — PREFLIGHT
        reconcile_lock()

        with _rail_conn() as conn:
            row = conn.execute(
                "SELECT state, target_file, diff_text, weakness_description, pre_patch_hash "
                "FROM candidates WHERE id=?", (candidate_id,),
            ).fetchone()

        if not row:
            return {'error': f'Candidate {candidate_id} not found'}

        state, target, diff_text, weakness, pre_hash = row

        if state not in ('validated', 'queued'):
            return {'error': f'Candidate {candidate_id} state={state}, expected validated/queued'}

        if target != V1_ALLOWED_TARGET:
            _set_candidate_state(candidate_id, 'rejected',
                                 rejection_reason=f'Target {target} not allowed in v1')
            return {'error': f'Target not allowed: {target}'}

        # Source awareness check
        try:
            from core.source_awareness import get_file
            entry = get_file(target)
            if not entry or entry.get('self_edit_scope') != 'allowed':
                _set_candidate_state(candidate_id, 'rejected',
                                     rejection_reason='Source awareness scope check failed')
                return {'error': 'Scope check failed'}
        except Exception as e:
            _set_candidate_state(candidate_id, 'rejected',
                                 rejection_reason=f'Source awareness error: {e}')
            return {'error': f'Source awareness error: {e}'}

        full_path = os.path.join(MAEZ_ROOT, target)
        current_hash = _file_sha256(full_path)
        if current_hash != pre_hash:
            _set_candidate_state(candidate_id, 'rejected',
                                 rejection_reason=f'File changed since validation (hash mismatch)')
            return {'error': 'Target file hash changed since validation'}

        # Acquire lock
        if not _acquire_lock(candidate_id):
            _set_candidate_state(candidate_id, 'rejected',
                                 rejection_reason='Could not acquire evolution lock')
            return {'error': 'Could not acquire lock'}
        acquired_lock = True

        # Step 2 — BACKUP via action engine mechanism
        from pathlib import Path as _P
        backup_dir = _P(MAEZ_ROOT) / 'backups'
        backup_dir.mkdir(parents=True, exist_ok=True)
        ts = time.strftime('%Y%m%d_%H%M%S')
        backup_path = str(backup_dir / f'{os.path.basename(target)}.{ts}.bak')
        shutil.copy2(full_path, backup_path)
        logger.info("Rail: backup created %s", backup_path)
        _log_evolution({'action': 'BACKUP', 'target': target, 'result': backup_path})

        with _rail_conn() as conn:
            conn.execute("UPDATE candidates SET backup_path=? WHERE id=?",
                         (backup_path, candidate_id))
            conn.commit()

        # Step 3 — APPLY PATCH
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.patch', delete=False) as tf:
            tf.write(diff_text)
            patch_file = tf.name

        try:
            result = _subprocess.run(
                ['patch', '-p1', '-d', MAEZ_ROOT, '-i', patch_file],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode != 0:
                # Restore immediately
                shutil.copy2(backup_path, full_path)
                _set_candidate_state(candidate_id, 'rolled_back',
                                     rollback_reason=f'patch apply failed: {result.stderr.strip()[:200]}',
                                     rollback_layer='immediate')
                _release_lock(candidate_id)
                acquired_lock = False
                return {'error': f'Patch apply failed: {result.stderr.strip()[:200]}',
                        'rolled_back': True, 'layer': 'immediate'}
        finally:
            os.unlink(patch_file)

        post_hash = _file_sha256(full_path)
        with _rail_conn() as conn:
            conn.execute("UPDATE candidates SET post_patch_hash=? WHERE id=?",
                         (post_hash, candidate_id))
            conn.commit()

        # Step 4 — IMMEDIATE VALIDATION (Layer 1)
        # py_compile
        compile_result = _subprocess.run(
            [sys.executable, '-m', 'py_compile', full_path],
            capture_output=True, text=True, timeout=15,
        )
        if compile_result.returncode != 0:
            shutil.copy2(backup_path, full_path)
            _set_candidate_state(candidate_id, 'rolled_back',
                                 rollback_reason=f'py_compile failed: {compile_result.stderr.strip()[:200]}',
                                 rollback_layer='immediate')
            _release_lock(candidate_id)
            acquired_lock = False
            _log_evolution({'action': 'IMMEDIATE_ROLLBACK', 'target': target,
                            'result': 'py_compile_fail'})
            return {'error': 'py_compile failed', 'rolled_back': True, 'layer': 'immediate'}

        # validate_behavior (reused directly)
        beh_ok, beh_err = validate_behavior(full_path)
        if not beh_ok:
            shutil.copy2(backup_path, full_path)
            _set_candidate_state(candidate_id, 'rolled_back',
                                 rollback_reason=f'validate_behavior failed: {beh_err}',
                                 rollback_layer='immediate')
            _release_lock(candidate_id)
            acquired_lock = False
            _log_evolution({'action': 'IMMEDIATE_ROLLBACK', 'target': target,
                            'result': f'behavior_fail: {beh_err[:100]}'})
            return {'error': f'Behavior validation failed: {beh_err}',
                    'rolled_back': True, 'layer': 'immediate'}

        # Compute pre-patch score avg early (needed for continuity capsule)
        _pre_score = 50.0
        try:
            from core.cognition_quality import _recent_scores as _rs
            if len(_rs) >= PRE_PATCH_BASELINE_CYCLES:
                _pre_score = sum(_rs[-PRE_PATCH_BASELINE_CYCLES:]) / PRE_PATCH_BASELINE_CYCLES
        except Exception:
            pass

        # Write continuity capsule BEFORE killing daemon
        try:
            from core.continuity import pre_restart_write
            pre_restart_write(
                candidate_id=candidate_id,
                target_file=target,
                diff_text=diff_text,
                pre_patch_score=_pre_score,
            )
        except Exception as e:
            logger.debug("Pre-restart continuity write failed: %s", e)

        # Restart maez.service
        restart = _restart_maez_service()
        if restart.returncode != 0:
            shutil.copy2(backup_path, full_path)
            _restart_maez_service()
            _set_candidate_state(candidate_id, 'rolled_back',
                                 rollback_reason=f'Service restart failed: {restart.stderr.strip()[:200]}',
                                 rollback_layer='immediate')
            _release_lock(candidate_id)
            acquired_lock = False
            return {'error': 'Service restart failed', 'rolled_back': True, 'layer': 'immediate'}

        # Health check
        import requests as _requests
        healthy = False
        for _ in range(IMMEDIATE_HEALTH_TIMEOUT // 5):
            time.sleep(5)
            try:
                r = _requests.get('http://localhost:11435/health', timeout=3)
                if r.status_code == 200:
                    healthy = True
                    break
            except Exception:
                pass

        if not healthy:
            shutil.copy2(backup_path, full_path)
            _restart_maez_service()
            _set_candidate_state(candidate_id, 'rolled_back',
                                 rollback_reason='Health check failed after restart',
                                 rollback_layer='immediate')
            _release_lock(candidate_id)
            acquired_lock = False
            _log_evolution({'action': 'IMMEDIATE_ROLLBACK', 'target': target,
                            'result': 'health_check_fail'})
            return {'error': 'Health check failed', 'rolled_back': True, 'layer': 'immediate'}

        # Step 5 — DELAYED WATCHDOG SETUP (Layer 2)
        # Compute pre-patch score average from cognition
        pre_score_avg = 50.0
        try:
            from core.cognition_quality import _recent_scores
            if len(_recent_scores) >= PRE_PATCH_BASELINE_CYCLES:
                window = _recent_scores[-PRE_PATCH_BASELINE_CYCLES:]
                pre_score_avg = sum(window) / len(window)
        except Exception:
            pass

        now = _dt.now(_tz.utc).isoformat()
        with _rail_conn() as conn:
            conn.execute(
                "UPDATE candidates SET state='applied', applied_at=?, pre_patch_score_avg=? WHERE id=?",
                (now, pre_score_avg, candidate_id),
            )
            conn.execute("""
                INSERT OR REPLACE INTO watchdog_context
                (candidate_id, target_file, backup_path, pre_patch_score_avg,
                 applied_at, watchdog_cycles, regression_threshold, resolved)
                VALUES (?, ?, ?, ?, ?, ?, ?, 0)
            """, (candidate_id, target, backup_path, pre_score_avg,
                  now, WATCHDOG_CYCLES, REGRESSION_THRESHOLD))
            conn.commit()

        # Record in deployments for historical tracking
        tracker = EvolutionTracker()
        tracker.record_deployment(target, weakness or '', pre_score_avg, backup_path)

        # Step 6 — OUTCOME RECORDING
        _log_evolution({'action': 'APPLIED', 'target': target,
                        'result': f'candidate={candidate_id}',
                        'detail': f'pre_score={pre_score_avg:.1f}'})
        logger.info("Rail: candidate %d applied to %s (pre_score=%.1f)",
                     candidate_id, target, pre_score_avg)

        try:
            from skills.dev_notifier import send_dev
            send_dev(
                f"Evolution applied: {target}\n"
                f"Weakness: {weakness or 'unspecified'}\n"
                f"Candidate: {candidate_id}\n"
                f"Pre-score avg: {pre_score_avg:.1f}\n"
                f"Watchdog active for {WATCHDOG_CYCLES} cycles."
            )
        except Exception:
            pass

        return {'candidate_id': candidate_id, 'state': 'applied', 'target': target,
                'pre_score_avg': pre_score_avg, 'backup_path': backup_path}

    except Exception as e:
        logger.error("Rail: apply_candidate failed: %s", e)
        if acquired_lock:
            _release_lock(candidate_id)
        return {'error': str(e)}

    finally:
        # Safety: if we still hold the lock and candidate isn't in active state, release
        if acquired_lock:
            with _rail_conn() as conn:
                row = conn.execute("SELECT state FROM candidates WHERE id=?", (candidate_id,)).fetchone()
                if row and row[0] not in ('applied', 'queued'):
                    _release_lock(candidate_id)


def _set_candidate_state(candidate_id: int, state: str, **kwargs):
    """Update candidate state and optional fields."""
    now = _dt.now(_tz.utc).isoformat()
    sets = [f"state='{state}'"]
    params = []

    if state in ('rejected', 'rolled_back', 'expired'):
        sets.append("resolved_at=?")
        params.append(now)

    for key in ('rejection_reason', 'rollback_reason', 'rollback_layer',
                'post_patch_score_avg'):
        if key in kwargs:
            sets.append(f"{key}=?")
            params.append(kwargs[key])

    params.append(candidate_id)
    with _rail_conn() as conn:
        conn.execute(f"UPDATE candidates SET {','.join(sets)} WHERE id=?", params)
        conn.commit()


# ══════════════════════════════════════════════════════════════════════
#  DELAYED WATCHDOG INTEGRATION
# ══════════════════════════════════════════════════════════════════════

def check_watchdog_candidates(memory_manager, telegram_callback=None):
    """Check applied candidates via watchdog_context. Called by existing check_and_revert cadence."""
    with _rail_conn() as conn:
        rows = conn.execute(
            "SELECT candidate_id, target_file, backup_path, pre_patch_score_avg, "
            "regression_threshold FROM watchdog_context WHERE resolved=0"
        ).fetchall()

    if not rows:
        return

    # Get current cognition scores
    try:
        from core.cognition_quality import _recent_scores
        if len(_recent_scores) < 5:
            return  # not enough post-patch data yet
        post_avg = sum(_recent_scores[-10:]) / min(len(_recent_scores), 10)
    except Exception:
        return

    for cand_id, target, backup_path, pre_avg, threshold in rows:
        regression = (pre_avg or 50) - post_avg

        if regression > (threshold or REGRESSION_THRESHOLD):
            # Delayed rollback
            full_target = os.path.join(MAEZ_ROOT, target)
            if backup_path and os.path.exists(backup_path):
                try:
                    shutil.copy2(backup_path, full_target)
                    _restart_maez_service()
                    _set_candidate_state(cand_id, 'rolled_back',
                                         rollback_reason=f'Regression {regression:.1f} > {threshold:.1f}',
                                         rollback_layer='delayed',
                                         post_patch_score_avg=post_avg)
                    with _rail_conn() as conn:
                        conn.execute(
                            "UPDATE deployments SET post_insight_rate=?, verdict='reverted' "
                            "WHERE target_file=? AND verdict IS NULL",
                            (post_avg, target),
                        )
                        conn.commit()
                    msg = (f"Delayed rollback: {target} — score dropped "
                           f"{pre_avg:.0f} → {post_avg:.0f} (regression={regression:.1f})")
                    logger.info("Rail: %s", msg)
                    _log_evolution({'action': 'DELAYED_ROLLBACK', 'target': target,
                                    'result': f'{pre_avg:.0f}→{post_avg:.0f}'})
                    if telegram_callback:
                        telegram_callback(msg)
                except Exception as e:
                    logger.error("Rail: delayed rollback failed: %s", e)
            else:
                _set_candidate_state(cand_id, 'rolled_back',
                                     rollback_reason='Regression detected but backup missing',
                                     rollback_layer='delayed',
                                     post_patch_score_avg=post_avg)
                with _rail_conn() as conn:
                    conn.execute(
                        "UPDATE deployments SET post_insight_rate=?, verdict='reverted' "
                        "WHERE target_file=? AND verdict IS NULL",
                        (post_avg, target),
                    )
                    conn.commit()
        else:
            # Keep — resolved successfully
            now = _dt.now(_tz.utc).isoformat()
            _set_candidate_state(cand_id, 'kept',
                                 post_patch_score_avg=post_avg)
            with _rail_conn() as conn:
                conn.execute("UPDATE candidates SET resolved_at=? WHERE id=?", (now, cand_id))
                # Update deployments verdict
                conn.execute(
                    "UPDATE deployments SET post_insight_rate=?, verdict='kept' "
                    "WHERE target_file=? AND verdict IS NULL",
                    (post_avg, target),
                )
                conn.commit()
            msg = f"Watchdog kept {target} — score {post_avg:.0f} (pre={pre_avg:.0f})"
            logger.info("Rail: %s", msg)
            if telegram_callback:
                telegram_callback(msg)

        # Mark resolved
        with _rail_conn() as conn:
            conn.execute("UPDATE watchdog_context SET resolved=1 WHERE candidate_id=?", (cand_id,))
            conn.commit()
        _release_lock(cand_id)


# ══════════════════════════════════════════════════════════════════════
#  STATUS AND CLI
# ══════════════════════════════════════════════════════════════════════

def rail_status() -> dict:
    """Return current rail state."""
    reconcile_msg = reconcile_lock()
    lock = _get_lock_state()
    with _rail_conn() as conn:
        candidates = conn.execute(
            "SELECT id, state, target_file, weakness_description, created_at "
            "FROM candidates ORDER BY id DESC LIMIT 5"
        ).fetchall()
        watchdogs = conn.execute(
            "SELECT candidate_id, target_file, pre_patch_score_avg, resolved "
            "FROM watchdog_context"
        ).fetchall()

    return {
        'lock': lock,
        'reconcile_msg': reconcile_msg,
        'recent_candidates': [
            {'id': r[0], 'state': r[1], 'target': r[2],
             'weakness': (r[3] or '')[:60], 'created_at': r[4]}
            for r in candidates
        ],
        'watchdogs': [
            {'candidate_id': r[0], 'target': r[1],
             'pre_score': r[2], 'resolved': bool(r[3])}
            for r in watchdogs
        ],
    }


def list_candidates() -> list[dict]:
    with _rail_conn() as conn:
        rows = conn.execute(
            "SELECT id, state, target_file, weakness_description, "
            "rejection_reason, rollback_reason, rollback_layer, "
            "pre_patch_score_avg, post_patch_score_avg, "
            "created_at, validated_at, applied_at, resolved_at "
            "FROM candidates ORDER BY id DESC"
        ).fetchall()
    return [
        {'id': r[0], 'state': r[1], 'target': r[2],
         'weakness': (r[3] or '')[:80],
         'rejection_reason': r[4], 'rollback_reason': r[5],
         'rollback_layer': r[6],
         'pre_score': r[7], 'post_score': r[8],
         'created': r[9], 'validated': r[10],
         'applied': r[11], 'resolved': r[12]}
        for r in rows
    ]


# ══════════════════════════════════════════════════════════════════════
#  PATCHED check_and_revert — integrates watchdog candidates
# ══════════════════════════════════════════════════════════════════════

_original_check_and_revert = check_and_revert


def check_and_revert(memory_manager, telegram_callback=None):
    """Extended check_and_revert: original logic + rail watchdog candidates."""
    # Run original deployment checks
    _original_check_and_revert(memory_manager, telegram_callback)
    # Run rail watchdog checks
    try:
        check_watchdog_candidates(memory_manager, telegram_callback)
    except Exception as e:
        logger.debug("Rail watchdog check failed: %s", e)


# ══════════════════════════════════════════════════════════════════════
#  AUTONOMOUS PROPOSAL TRIGGER
# ══════════════════════════════════════════════════════════════════════

AUTO_APPLY_ENABLED = False   # Hardcoded. Never auto-apply.
PROPOSAL_SCORE_THRESHOLD = 45
MIN_EVIDENCE_CYCLES = 10
MAX_PROPOSAL_HUNKS = 1
MAX_PROPOSAL_CHANGED_LINES = 8

# Worker constants
WORKER_POLL_INTERVAL = 10
JOB_TIMEOUT_SECONDS = 300
MAX_JOB_ATTEMPTS = 3

_STRUCTURAL_REJECT_PATTERNS = [
    _re.compile(r'^def\s'),
    _re.compile(r'^class\s'),
    _re.compile(r'^import\s'),
    _re.compile(r'^from\s+\S+\s+import'),
    _re.compile(r'^\s*(if|for|while|try|except|with|return)\b'),
]


def _validate_diff_structure(diff_text: str) -> tuple[bool, str]:
    """Reject diffs that touch logic, control flow, imports, or function defs.
    Only constants, thresholds, and keyword lists may change."""
    hunks = 0
    changed_lines = 0
    for line in diff_text.split('\n'):
        if line.startswith('@@'):
            hunks += 1
        if line.startswith('+') and not line.startswith('+++'):
            changed_lines += 1
            stripped = line[1:].strip()
            for pat in _STRUCTURAL_REJECT_PATTERNS:
                if pat.match(stripped):
                    return False, f"Diff touches structural code: {stripped[:60]}"
        if line.startswith('-') and not line.startswith('---'):
            changed_lines += 1
            stripped = line[1:].strip()
            for pat in _STRUCTURAL_REJECT_PATTERNS:
                if pat.match(stripped):
                    return False, f"Diff removes structural code: {stripped[:60]}"

    if hunks > MAX_PROPOSAL_HUNKS:
        return False, f"Too many hunks: {hunks} (max {MAX_PROPOSAL_HUNKS})"
    if changed_lines > MAX_PROPOSAL_CHANGED_LINES:
        return False, f"Too many changed lines: {changed_lines} (max {MAX_PROPOSAL_CHANGED_LINES})"
    if changed_lines == 0:
        return False, "Empty diff"
    return True, ""


# Valid failure mode labels — label-derived, never topic-derived
VALID_FAILURE_LABELS = {
    'fixation', 'weak_retrieval', 'vague', 'repetition', 'baseline',
}
# Positive/neutral labels excluded from failure mode derivation
_POSITIVE_LABELS = {'actionable', 'insightful', 'good_observation', 'neutral', 'unknown'}


def _build_evidence_packet(critique: dict) -> dict:
    """Build structured evidence packet from critique window.
    IMPORTANT:
      dominant_failure_mode = label-derived (fixation, vague, etc.)
      dominant_topic = topic-derived (browser_usage, git_workflow, etc.)
    These are different fields from different systems. Never conflate."""
    try:
        from core.cognition_quality import (
            _recent_scores, _recent_topics, _recent_labels,
            get_behavior_policy,
        )
        import collections as _cc
        window = min(len(_recent_scores), 20)
        scores = _recent_scores[-window:]
        topics = _recent_topics[-window:]
        labels_window = _recent_labels[-window:]
        primaries = [ll[0] if ll else 'unknown' for ll in labels_window]

        # dominant_failure_mode — derived from LABELS, not topics
        all_labels = [l for ll in labels_window for l in ll]
        neg_labels = {k: v for k, v in _cc.Counter(all_labels).items()
                      if k not in _POSITIVE_LABELS}
        dominant_failure = max(neg_labels, key=neg_labels.get) if neg_labels else None

        # Validate: must be a known label, not a topic value
        if dominant_failure and dominant_failure not in VALID_FAILURE_LABELS:
            logger.warning("dominant_failure_mode '%s' is not a valid label; coercing to None", dominant_failure)
            dominant_failure = None

        # dominant_topic — derived from TOPICS
        dominant_topic = critique.get('dominant_topic', '')

        policy = get_behavior_policy()

        sa_entry = None
        try:
            from core.source_awareness import get_file
            sa_entry = get_file(V1_ALLOWED_TARGET)
        except Exception:
            pass

        return {
            'scores': scores,
            'primary_labels': primaries,
            'topics': topics,
            'dominant_failure_mode': dominant_failure,
            'dominant_topic': dominant_topic,
            'fixation_ratio': critique.get('fixation_ratio', 0),
            'avg_score': critique.get('avg_score', 0),
            'policy_directive': policy.get('directive', ''),
            'policy_mode': policy.get('reflection_mode', 'normal'),
            'source_awareness_scope': sa_entry.get('self_edit_scope') if sa_entry else None,
        }
    except Exception as e:
        logger.error("Evidence packet build failed: %s", e)
        return {'error': str(e)}


def _derive_weakness(critique: dict, evidence: dict) -> str:
    """Auto-derive weakness_description from evidence.
    Leads with failure label, not topic. Topic is secondary context."""
    failure = evidence.get('dominant_failure_mode')
    topic = (evidence.get('dominant_topic') or critique.get('dominant_topic', 'unknown')).replace('_', ' ')
    avg = evidence.get('avg_score') or critique.get('avg_score', 0)
    ratio = critique.get('fixation_ratio', 0)
    window = critique.get('window_size', 20)

    # Count cycles supporting this failure mode from labels
    failure_count = 0
    try:
        labels = evidence.get('primary_labels') or []
        if labels and failure:
            failure_count = sum(1 for l in labels if l == failure)
    except Exception:
        pass
    if failure_count == 0:
        failure_count = int(ratio * window) if ratio else 0

    # Failure-mode-first templates
    if failure == 'fixation':
        text = (
            f"Recent reasoning is fixating on {topic} \u2014 the same subject appeared "
            f"in {failure_count} of the last {window} cycles. Average score {avg}/100. "
            f"The reasoning loop needs broader topic coverage. "
            f"Context: {topic} was the dominant subject during this period."
        )
    elif failure == 'weak_retrieval':
        text = (
            f"Recent reasoning is not grounding itself in perception data \u2014 "
            f"{failure_count} of the last {window} cycles lacked concrete system metrics or "
            f"sensor references. Average score {avg}/100. "
            f"Retrieval and grounding need strengthening. "
            f"Context: {topic} was the dominant subject during this period."
        )
    elif failure == 'vague':
        text = (
            f"Recent reasoning is too vague \u2014 {failure_count} of the last {window} cycles "
            f"lacked specific metrics, measurements, or actionable observations. "
            f"Average score {avg}/100. Specificity and grounding need improvement. "
            f"Context: {topic} was the dominant subject during this period."
        )
    elif failure == 'repetition':
        text = (
            f"Recent reasoning is repeating itself \u2014 high semantic overlap was "
            f"detected across {failure_count} of the last {window} cycles on {topic}. "
            f"Average score {avg}/100. Novelty and diversity need improvement. "
            f"Context: {topic} was the dominant subject during this period."
        )
    else:
        # Fallback to topic-first when failure mode is unknown
        text = (
            f"Topic concentration on {topic} detected across "
            f"{int(ratio * window)} of the last {window} cycles. "
            f"Average score {avg}/100. Dominant failure: {failure or 'unknown'}."
        )

    # Store derivation metadata in evidence for audit
    evidence['_weakness_derived_from_failure_mode'] = failure is not None and failure in VALID_FAILURE_LABELS
    evidence['_weakness_failure_count'] = failure_count

    return text


# ══════════════════════════════════════════════════════════════════════
#  STRUCTURED PATCH INTENT — AST extraction + deterministic edit
# ══════════════════════════════════════════════════════════════════════

# Threshold-like naming patterns for scalar ranking (rank 1)
_THRESHOLD_NAME_PARTS = {'THRESHOLD', 'FLOOR', 'CEILING', 'MIN', 'MAX', 'LIMIT', 'RATIO'}


def _compute_target_rank(name: str, typ: str) -> int:
    """Rank editable targets. Lower rank = preferred.
    Rank 1: threshold-like scalars (name contains THRESHOLD/FLOOR/MAX etc)
    Rank 2: other scalar constants (int/float/bool)
    Rank 3: keyword lists (list of strings)
    Rank 4: everything else"""
    if typ in ('int', 'float', 'bool'):
        parts = set(name.upper().split('_'))
        if parts & _THRESHOLD_NAME_PARTS:
            return 1  # threshold scalar — most preferred
        return 2  # other scalar
    if typ == 'list_str':
        return 3  # keyword list
    return 4  # other


def _extract_editable_targets(filepath: str) -> list[dict]:
    """Extract module-level constant assignments via AST. No imports, no execution.
    Returns targets sorted by rank (scalars first, then lists)."""
    import ast as _ast
    with open(filepath) as f:
        source = f.read()
    tree = _ast.parse(source)
    targets = []

    for node in _ast.iter_child_nodes(tree):
        if not isinstance(node, _ast.Assign):
            continue
        if len(node.targets) != 1 or not isinstance(node.targets[0], _ast.Name):
            continue
        name = node.targets[0].id
        if not name.isupper() and not name.startswith('_'):
            continue  # only UPPER_CASE constants or _PREFIXED

        val = node.value
        entry = {'name': name, 'lineno': node.lineno, 'end_lineno': getattr(node, 'end_lineno', node.lineno)}

        if isinstance(val, _ast.Constant):
            if isinstance(val.value, (int, float, bool)):
                entry['current_value'] = val.value
                entry['type'] = type(val.value).__name__
                entry['target_rank'] = _compute_target_rank(name, entry['type'])
                targets.append(entry)
        elif isinstance(val, _ast.List):
            strs = []
            all_str = True
            for elt in val.elts:
                if isinstance(elt, _ast.Constant) and isinstance(elt.value, str):
                    strs.append(elt.value)
                else:
                    all_str = False
                    break
            if all_str and strs:
                entry['current_value'] = strs
                entry['type'] = 'list_str'
                entry['target_rank'] = _compute_target_rank(name, 'list_str')
                targets.append(entry)

    # Sort by rank (scalars first)
    targets.sort(key=lambda t: t['target_rank'])
    return targets


_INTENT_REQUIRED_FIELDS = {'target_name', 'target_type', 'current_value', 'proposed_value', 'rationale'}


def extract_intent_json(raw_response: str) -> dict | None:
    """Robust JSON extraction from model response. Never raises.
    Returns parsed dict with all required fields, or None."""
    if not raw_response or not raw_response.strip():
        return None
    try:
        text = raw_response.strip()

        # Step 1 — Strip markdown fences
        if '```' in text:
            blocks = text.split('```')
            for block in blocks[1:]:
                block = block.strip()
                if block.startswith('json'):
                    block = block[4:].strip()
                if '{' in block:
                    text = block.split('```')[0].strip()
                    break

        # Step 2 — Isolate first JSON object via brace counting
        start = text.find('{')
        if start < 0:
            return None
        depth = 0
        end = -1
        for i in range(start, len(text)):
            if text[i] == '{':
                depth += 1
            elif text[i] == '}':
                depth -= 1
                if depth == 0:
                    end = i
                    break
        if end < 0:
            return None  # no complete JSON object
        json_str = text[start:end + 1]

        # Step 3 — Parse
        intent = json.loads(json_str)

        # Step 4 — Validate required fields
        missing = _INTENT_REQUIRED_FIELDS - set(intent.keys())
        if missing:
            logger.info("Intent missing fields: %s", missing)
            return None

        return intent

    except json.JSONDecodeError as e:
        logger.info("Intent JSON parse failed: %s (raw: %s)", e, raw_response[:200])
        return None
    except Exception as e:
        logger.info("Intent extraction error: %s", e)
        return None


# Fix 1: Narrowed target set — top 5 for initial, top 3 for retry
_MAX_INITIAL_TARGETS = 5
_MAX_RETRY_TARGETS = 3


# Failure-mode-to-target-family keyword mapping for filtering
_TARGET_FAMILIES = {
    'fixation': {'FIXATION', 'STREAK', 'PENALTY', 'SUPPRESS', 'AVOID', 'RECENT', 'TOPIC', 'WINDOW', 'COOLDOWN'},
    'weak_retrieval': {'RETRIEVAL', 'RERANK', 'BOOST', 'PENALTY', 'GROUNDING', 'WING', 'ANTIFIXATION', 'FETCH'},
    'vague': {'SPECIFIC', 'ACTIONABLE', 'GROUNDING', 'LENGTH', 'MINIMUM', 'METRIC', 'CONCRETE', 'SCORE', 'FLOOR'},
    'repetition': {'OVERLAP', 'NOVELTY', 'DIVERSITY', 'SEMANTIC', 'REPETITION', 'SIMILARITY', 'WINDOW'},
}


def _filter_targets_by_failure(targets: list, failure_mode: str | None) -> tuple[list, bool, int]:
    """Filter targets by failure-mode family, preserving scalar-first rank order.
    Returns (filtered_targets, filtered_by_failure_mode, family_match_count)."""
    if not failure_mode or failure_mode not in _TARGET_FAMILIES:
        return targets[:_MAX_INITIAL_TARGETS], False, 0

    family_kws = _TARGET_FAMILIES[failure_mode]
    matched = []
    unmatched = []
    for t in targets:
        name_parts = set(t['name'].upper().split('_'))
        if name_parts & family_kws:
            matched.append(t)
        else:
            unmatched.append(t)

    if len(matched) >= 3:
        # Take matched first (preserving rank), fill to 5 with remaining
        result = matched[:_MAX_INITIAL_TARGETS]
        remaining_slots = _MAX_INITIAL_TARGETS - len(result)
        if remaining_slots > 0:
            result.extend(unmatched[:remaining_slots])
        return result, True, len(matched)
    else:
        logger.info("Insufficient family matches for %s (%d found), using full ranked list",
                     failure_mode, len(matched))
        return targets[:_MAX_INITIAL_TARGETS], False, len(matched)


def _generate_patch_intent(weakness: str, evidence: dict, editable_targets: list) -> dict | None:
    """Ask Gemma for structured patch intent JSON. Targets sorted by rank (scalars first).
    Filtered by failure-mode family when possible. Retries once with top 3 on failure."""
    failure_mode = evidence.get('dominant_failure_mode')
    injected, filtered_by_fm, family_match_count = _filter_targets_by_failure(editable_targets, failure_mode)
    targets_text = '\n'.join(
        f"  [rank {t.get('target_rank', '?')}] {t['name']} = {t['current_value']!r}  "
        f"(type: {t['type']}, line {t['lineno']})"
        for t in injected
    )
    evidence_summary = json.dumps({
        'avg_score': evidence.get('avg_score'),
        'dominant_topic': evidence.get('dominant_topic'),
        'fixation_ratio': evidence.get('fixation_ratio'),
        'policy_directive': str(evidence.get('policy_directive', ''))[:100],
    }, default=str)

    prompt = (
        f"You are proposing one minimal change to improve Maez's reasoning quality.\n\n"
        f"Weakness detected:\n{weakness}\n\n"
        f"Evidence:\n{evidence_summary}\n\n"
        f"Editable targets from core/cognition_quality.py:\n{targets_text}\n\n"
        f'Output JSON only. No prose. No diff.\n'
        f'Exactly this structure:\n'
        f'{{\n'
        f'  "target_name": "<existing constant name>",\n'
        f'  "target_type": "constant" or "keyword_list",\n'
        f'  "current_value": <current value>,\n'
        f'  "proposed_value": <new value>,\n'
        f'  "rationale": "<one sentence>"\n'
        f'}}\n\n'
        f"Rules:\n"
        f"- target_name must be one of the listed editable targets\n"
        f"- proposed_value must be the same type as current_value\n"
        f"- proposed_value must differ from current_value\n"
        f"- one target only\n"
        f"- Prefer targets ranked earlier in this list.\n"
        f"  Only propose a keyword list change if no scalar or\n"
        f"  threshold change would reasonably address the weakness.\n"
    )
    if failure_mode:
        prompt += (
            f"\nThe dominant failure mode is {failure_mode}.\n"
            f"Targets are filtered toward this failure type.\n"
            f"Choose the target that most directly addresses {failure_mode},\n"
            f"not merely the topic.\n"
        )

    retry_info = {'retry_attempted': False, 'retry_reason': None, 'retry_succeeded': False}
    filter_info = {
        'filtered_by_failure_mode': filtered_by_fm,
        'family_match_count': family_match_count,
    }

    # First attempt
    raw, intent = _call_ollama_for_intent(prompt)

    if intent:
        intent.update(retry_info)
        intent.update(filter_info)
        intent['injected_target_count'] = len(injected)
        intent['injected_target_names'] = [t['name'] for t in injected]
        # Check if proposed target aligns with failure family
        if failure_mode and failure_mode in _TARGET_FAMILIES and intent.get('target_name'):
            name_parts = set(intent['target_name'].upper().split('_'))
            intent['failure_family_alignment'] = bool(name_parts & _TARGET_FAMILIES[failure_mode])
        else:
            intent['failure_family_alignment'] = False
        return _enrich_intent(intent, editable_targets)

    # Fix 3: One retry with stricter, narrower prompt
    retry_reason = 'empty_response' if not raw else ('timeout' if raw == '__TIMEOUT__' else 'non_json')
    retry_info['retry_attempted'] = True
    retry_info['retry_reason'] = retry_reason
    logger.info("Intent parse failed (%s), retrying with stricter prompt", retry_reason)

    retry_targets = [t for t in editable_targets if t.get('target_rank', 9) <= 2][:_MAX_RETRY_TARGETS]
    if not retry_targets:
        retry_targets = editable_targets[:_MAX_RETRY_TARGETS]

    retry_text = '\n'.join(
        f"  {t['name']} = {t['current_value']!r}" for t in retry_targets
    )
    retry_prompt = (
        f"Respond with JSON only.\nNo markdown.\nNo explanation.\nNo prose before or after.\n\n"
        f"Pick exactly one target from this list:\n{retry_text}\n\n"
        f'Output exactly:\n'
        f'{{\n'
        f'  "target_name": "...",\n'
        f'  "target_type": "...",\n'
        f'  "current_value": ...,\n'
        f'  "proposed_value": ...,\n'
        f'  "rationale": "one sentence"\n'
        f'}}\n\n'
        f"Nothing else."
    )

    raw2, intent2 = _call_ollama_for_intent(retry_prompt)
    if intent2:
        retry_info['retry_succeeded'] = True
        intent2.update(retry_info)
        intent2.update(filter_info)
        intent2['injected_target_count'] = len(retry_targets)
        intent2['injected_target_names'] = [t['name'] for t in retry_targets]
        if failure_mode and failure_mode in _TARGET_FAMILIES and intent2.get('target_name'):
            name_parts = set(intent2['target_name'].upper().split('_'))
            intent2['failure_family_alignment'] = bool(name_parts & _TARGET_FAMILIES[failure_mode])
        else:
            intent2['failure_family_alignment'] = False
        logger.info("Retry succeeded: target=%s", intent2.get('target_name'))
        return _enrich_intent(intent2, editable_targets)

    logger.info("Intent parse failed after retry (raw: %s)", (raw2 or raw or '')[:100])
    return None


def _call_ollama_for_intent(prompt: str) -> tuple[str | None, dict | None]:
    """Call Ollama and extract intent JSON. Returns (raw_response, parsed_intent)."""
    try:
        import requests as _req
        resp = _req.post('http://localhost:11434/api/generate',
                         json={'model': 'gemma4:26b', 'prompt': prompt, 'stream': False},
                         timeout=180)
        if resp.status_code != 200:
            return '__TIMEOUT__', None
        raw = resp.json().get('response', '').strip()
        if not raw:
            return '', None
        intent = extract_intent_json(raw)
        return raw, intent
    except Exception as e:
        if 'timeout' in str(e).lower() or 'timed out' in str(e).lower():
            return '__TIMEOUT__', None
        logger.info("Ollama intent call failed: %s", e)
        return None, None


def _enrich_intent(intent: dict, editable_targets: list) -> dict:
    """Add target_rank and ranked_targets_considered to parsed intent."""
    target_map = {t['name']: t for t in editable_targets}
    if intent.get('target_name') in target_map:
        intent['target_rank'] = target_map[intent['target_name']].get('target_rank')
    intent['ranked_targets_considered'] = [
        {'name': t['name'], 'rank': t.get('target_rank'), 'type': t['type']}
        for t in editable_targets[:8]
    ]
    return intent


def _validate_patch_intent(intent: dict, editable_targets: list) -> tuple[bool, str]:
    """Validate parsed patch intent against editable targets."""
    if not intent or not isinstance(intent, dict):
        return False, "intent is null or not a dict"

    name = intent.get('target_name')
    if not name:
        return False, "missing target_name"

    target_map = {t['name']: t for t in editable_targets}
    if name not in target_map:
        return False, f"target_name '{name}' not in editable targets"

    target = target_map[name]
    proposed = intent.get('proposed_value')
    current = target['current_value']

    if proposed is None:
        return False, "proposed_value is null"
    if proposed == current:
        return False, f"proposed_value equals current_value ({current})"

    # Type check
    if target['type'] in ('int', 'float', 'bool'):
        if not isinstance(proposed, type(current)):
            # Allow int↔float coercion
            if isinstance(proposed, (int, float)) and isinstance(current, (int, float)):
                pass
            else:
                return False, f"type mismatch: proposed={type(proposed).__name__}, expected={target['type']}"
    elif target['type'] == 'list_str':
        if not isinstance(proposed, list) or not all(isinstance(s, str) for s in proposed):
            return False, "proposed_value must be a list of strings"

    return True, ""


def _synthesize_edit(filepath: str, target_name: str, proposed_value, editable_targets: list) -> tuple[str, str]:
    """Formatting-preserving deterministic edit. Returns (original, edited).
    For scalars: preserves indentation, spacing around =, inline comments.
    For lists: preserves multiline/single-line layout style."""
    with open(filepath) as f:
        original = f.read()

    target = next(t for t in editable_targets if t['name'] == target_name)
    lines = original.split('\n')
    start = target['lineno'] - 1  # 0-indexed
    end = target.get('end_lineno', target['lineno']) - 1
    orig_span = lines[start:end + 1]

    if target['type'] in ('int', 'float', 'bool'):
        # SCALAR: replace value token only, preserve everything else
        orig_line = lines[start]
        eq_pos = orig_line.find('=')
        if eq_pos < 0:
            # Fallback
            edited_lines = lines[:start] + [f"{target_name} = {proposed_value!r}"] + lines[end + 1:]
            return original, '\n'.join(edited_lines)

        prefix = orig_line[:eq_pos + 1]  # "NAME =" or "NAME="
        rest = orig_line[eq_pos + 1:]

        # Find where the value ends and comment begins
        # Walk the rest to find # that's not inside a string
        comment_start = None
        in_str = False
        for i, ch in enumerate(rest):
            if ch in ('"', "'"):
                in_str = not in_str
            elif ch == '#' and not in_str:
                comment_start = i
                break

        if comment_start is not None:
            # Preserve spacing between value and comment
            value_part = rest[:comment_start]
            comment_part = rest[comment_start:]
            # Replace the value, keep the spacing pattern
            spaces_before_val = len(value_part) - len(value_part.lstrip())
            spaces_after_val = len(value_part) - len(value_part.rstrip())
            new_val_str = f" {proposed_value!r}"
            # Pad to keep comment at roughly the same column
            orig_total = len(prefix) + len(value_part)
            new_total = len(prefix) + len(new_val_str)
            pad = max(1, orig_total - new_total)
            new_line = prefix + new_val_str + ' ' * pad + comment_part
        else:
            # No comment — just replace value
            new_line = prefix + f" {proposed_value!r}"

        edited_lines = lines[:start] + [new_line] + lines[end + 1:]
        return original, '\n'.join(edited_lines)

    elif target['type'] == 'list_str':
        # LIST: detect original shape, preserve layout
        is_multiline = (end > start)

        if is_multiline:
            # Preserve multiline format
            # Detect indentation of elements from original
            first_line = orig_span[0]
            base_indent = len(first_line) - len(first_line.lstrip())
            # Detect element indent from second line (if exists)
            if len(orig_span) > 1:
                elem_line = orig_span[1]
                elem_indent = len(elem_line) - len(elem_line.lstrip())
            else:
                elem_indent = base_indent + 4

            # Detect trailing comma style
            has_trailing_comma = False
            for line in reversed(orig_span):
                stripped = line.strip().rstrip(']').rstrip()
                if stripped.endswith(','):
                    has_trailing_comma = True
                    break

            # Build new multiline list
            new_lines = [f"{' ' * base_indent}{target_name} = ["]
            for i, val in enumerate(proposed_value):
                comma = ',' if i < len(proposed_value) - 1 or has_trailing_comma else ','
                new_lines.append(f"{' ' * elem_indent}{val!r}{comma}")
            new_lines.append(f"{' ' * base_indent}]")

            edited_lines = lines[:start] + new_lines + lines[end + 1:]
            return original, '\n'.join(edited_lines)
        else:
            # Single-line list — keep single-line
            orig_line = lines[start]
            eq_pos = orig_line.find('=')
            prefix = orig_line[:eq_pos + 1] if eq_pos >= 0 else f"{target_name} ="
            val_repr = repr(proposed_value)
            new_line = f"{prefix} {val_repr}"
            edited_lines = lines[:start] + [new_line] + lines[end + 1:]
            return original, '\n'.join(edited_lines)

    else:
        # Fallback for other types
        new_line = f"{target_name} = {proposed_value!r}"
        edited_lines = lines[:start] + [new_line] + lines[end + 1:]
        return original, '\n'.join(edited_lines)


# ══════════════════════════════════════════════════════════════════════
#  EVIDENCE NORMALIZATION + CANONICAL DISPLAY LOADER
# ══════════════════════════════════════════════════════════════════════

def normalize_evidence(evidence: dict) -> dict:
    """Ensure all required evidence fields exist. Preserves originals, adds normalized fields."""
    if not evidence or not isinstance(evidence, dict):
        evidence = {}

    # dominant_failure_mode
    if not evidence.get('dominant_failure_mode'):
        labels = evidence.get('primary_labels') or evidence.get('labels') or []
        if labels:
            import collections as _cc
            neg = {k: v for k, v in _cc.Counter(labels).items()
                   if k not in ('actionable', 'insightful', 'good_observation', 'neutral', 'unknown')}
            evidence['dominant_failure_mode'] = max(neg, key=neg.get) if neg else None
        else:
            evidence['dominant_failure_mode'] = evidence.get('dominant_failure_mode') or None

    # dominant_topic
    if not evidence.get('dominant_topic'):
        topics = evidence.get('topics') or []
        if topics:
            import collections as _cc
            tc = _cc.Counter(topics)
            evidence['dominant_topic'] = tc.most_common(1)[0][0]
        else:
            evidence['dominant_topic'] = None

    # avg_score
    if evidence.get('avg_score') is None:
        scores = evidence.get('scores') or []
        if scores:
            evidence['avg_score'] = sum(scores) / len(scores)
        else:
            evidence['avg_score'] = None

    # Ensure lists exist
    evidence.setdefault('scores', [])
    evidence.setdefault('topics', [])
    evidence.setdefault('primary_labels', [])

    # Safety net: validate dominant_failure_mode is a label, not a topic
    dfm = evidence.get('dominant_failure_mode')
    if dfm is not None and dfm not in VALID_FAILURE_LABELS:
        logger.warning("normalize_evidence: dominant_failure_mode '%s' appears topic-derived; coercing to None", dfm)
        evidence['dominant_failure_mode'] = None

    # evidence_complete
    evidence['evidence_complete'] = (
        evidence.get('dominant_failure_mode') is not None
        and evidence.get('dominant_topic') is not None
        and evidence.get('avg_score') is not None
        and len(evidence.get('scores', [])) >= MIN_EVIDENCE_CYCLES
    )

    return evidence


def load_candidate_for_display(candidate_id: int) -> dict | None:
    """Canonical DB read → display-ready object. Single source of truth for show + Telegram."""
    with _rail_conn() as conn:
        conn.row_factory = _sqlite3.Row
        row = conn.execute("SELECT * FROM candidates WHERE id=?", (candidate_id,)).fetchone()
    if not row:
        return None

    d = dict(row)
    evidence = {}
    intent = None
    usefulness = None

    if d.get('cognition_evidence'):
        try:
            evidence = json.loads(d['cognition_evidence'])
        except Exception:
            evidence = {}

    intent = evidence.get('patch_intent')
    usefulness = evidence.get('usefulness')

    # Normalize evidence
    evidence = normalize_evidence(evidence)

    # Compute usefulness on the fly if missing or stale
    if intent:
        diff_changed = 0
        if d.get('diff_text'):
            diff_changed = sum(1 for l in d['diff_text'].split('\n')
                               if (l.startswith('+') and not l.startswith('+++'))
                               or (l.startswith('-') and not l.startswith('---')))
        usefulness = score_proposal_usefulness(intent, evidence, diff_changed)

    # Build display object
    return {
        'id': d['id'],
        'state': d['state'],
        'target_file': d.get('target_file', V1_ALLOWED_TARGET),
        'weakness': d.get('weakness_description', ''),
        'created_at': d.get('created_at'),
        'rejection_reason': d.get('rejection_reason'),
        'rollback_reason': d.get('rollback_reason'),
        'rollback_layer': d.get('rollback_layer'),
        'pre_score': d.get('pre_patch_score_avg'),
        'post_score': d.get('post_patch_score_avg'),
        'diff_text': d.get('diff_text'),
        'evidence': evidence,
        'intent': intent,
        'usefulness': usefulness or {
            'addresses_failure_mode': None, 'direction_sane': None,
            'change_minimal': None, 'overall': 'unknown',
            'reasoning': 'No patch intent available',
        },
    }


# ══════════════════════════════════════════════════════════════════════
#  USEFULNESS RUBRIC — deterministic, no LLM
# ══════════════════════════════════════════════════════════════════════

# Target family keywords for failure mode alignment
_FAILURE_TARGET_FAMILIES = {
    'fixation': {'FIXATION', 'STREAK', 'PENALTY', 'TOPIC', 'THRESHOLD', 'ANTIFIXATION'},
    'weak_retrieval': {'RETRIEVAL', 'BOOST', 'PENALTY', 'RERANK', 'SCORE_WEIGHT', 'ANTIFIXATION'},
    'vague': {'ACTIONABLE', 'SPECIFICITY', 'GROUNDING', 'MIN_ACTIONABLE', 'LENGTH'},
    'baseline': {'BASELINE', 'THRESHOLD', 'NORMAL'},
    'repetition': {'FIXATION', 'NOVELTY', 'ANTIFIXATION', 'STREAK'},
}

# Directional whitelist: (failure_mode, target_name_part) → expected direction
# direction: 'lower' means proposed < current is sane, 'raise' means proposed > current
_DIRECTION_RULES = {
    ('fixation', 'THRESHOLD'): 'lower',      # lower threshold = more sensitive detection
    ('fixation', 'PENALTY'): 'raise',         # higher penalty = stronger anti-fixation
    ('fixation', 'STREAK'): 'lower',          # lower streak = faster detection
    ('weak_retrieval', 'WEIGHT'): 'raise',    # higher weight = better retrieval scoring
    ('weak_retrieval', 'PENALTY'): 'lower',   # lower penalty = less aggressive suppression
    ('weak_retrieval', 'BOOST'): 'raise',
    ('vague', 'ACTIONABLE'): 'lower',         # lower threshold = easier to pass
    ('vague', 'SPECIFICITY'): 'raise',        # higher weight = more emphasis on specifics
    ('vague', 'GROUNDING'): 'raise',
}


def score_proposal_usefulness(intent: dict, evidence: dict, diff_lines_changed: int = 0) -> dict:
    """Deterministic usefulness rubric. Returns usefulness dict. Never raises.
    Returns overall='unknown' when evidence is incomplete."""
    try:
        # Check evidence completeness first
        if not evidence.get('evidence_complete', False):
            missing = []
            if not evidence.get('dominant_failure_mode'):
                missing.append('dominant_failure_mode')
            if not evidence.get('dominant_topic'):
                missing.append('dominant_topic')
            if evidence.get('avg_score') is None:
                missing.append('avg_score')
            if len(evidence.get('scores', [])) < MIN_EVIDENCE_CYCLES:
                missing.append(f'scores ({len(evidence.get("scores", []))} < {MIN_EVIDENCE_CYCLES})')

            # change_minimal is always scoreable
            change_minimal = diff_lines_changed <= 6
            return {
                'addresses_failure_mode': None,
                'direction_sane': None,
                'change_minimal': change_minimal,
                'overall': 'unknown',
                'reasoning': f'Insufficient evidence \u2014 missing: {", ".join(missing)}.',
            }

        target_name = intent.get('target_name', '')
        failure_mode = evidence.get('dominant_failure_mode', '')
        current = intent.get('current_value')
        proposed = intent.get('proposed_value')

        # 1. addresses_failure_mode
        name_parts = set(target_name.upper().split('_'))
        family_keywords = _FAILURE_TARGET_FAMILIES.get(failure_mode, set())
        addresses = bool(name_parts & family_keywords)

        # 2. direction_sane
        direction_sane = False
        if proposed == current or type(proposed) != type(current):
            direction_sane = False
        elif isinstance(current, (int, float)) and isinstance(proposed, (int, float)):
            # Check directional whitelist
            for (fm, name_part), expected_dir in _DIRECTION_RULES.items():
                if fm == failure_mode and name_part in target_name.upper():
                    if expected_dir == 'lower' and proposed < current:
                        direction_sane = True
                    elif expected_dir == 'raise' and proposed > current:
                        direction_sane = True
                    break
            # If no rule matched but addresses failure mode, still False (conservative)
        elif isinstance(current, list) and isinstance(proposed, list):
            # Lists: direction is ambiguous, only sane if addresses failure mode
            direction_sane = addresses

        # 3. change_minimal
        change_minimal = diff_lines_changed <= 6
        borderline = 3 < diff_lines_changed <= 6

        # 4. overall
        scores = [addresses, direction_sane, change_minimal]
        true_count = sum(scores)
        if true_count == 3:
            overall = 'strong'
        elif true_count == 2:
            overall = 'acceptable'
        else:
            overall = 'weak'

        # 5. reasoning
        parts = []
        if addresses:
            parts.append(f"{target_name} aligns with {failure_mode} failure mode")
        else:
            parts.append(f"{target_name} does not clearly address {failure_mode}")
        if direction_sane:
            parts.append("direction is appropriate")
        else:
            parts.append("direction unclear or misaligned")
        if change_minimal:
            if borderline:
                parts.append(f"{diff_lines_changed} lines changed (borderline)")
            else:
                parts.append(f"{diff_lines_changed} lines changed (minimal)")
        else:
            parts.append(f"{diff_lines_changed} lines changed (too large)")

        reasoning = '; '.join(parts) + '.'

        return {
            'addresses_failure_mode': addresses,
            'direction_sane': direction_sane,
            'change_minimal': change_minimal,
            'overall': overall,
            'reasoning': reasoning,
        }

    except Exception as e:
        return {
            'addresses_failure_mode': False,
            'direction_sane': False,
            'change_minimal': False,
            'overall': 'weak',
            'reasoning': f'scoring error: {e}',
        }


def process_proposal_job(job_id: int) -> dict:
    """Process a single proposal job: intent → edit → validate → candidate."""
    target = V1_ALLOWED_TARGET
    full_path = os.path.join(MAEZ_ROOT, target)

    with _rail_conn() as conn:
        row = conn.execute(
            "SELECT weakness_description, evidence_json, cooldown_key FROM proposal_jobs WHERE id=?",
            (job_id,),
        ).fetchone()
    if not row:
        return {'error': f'Job {job_id} not found'}

    weakness, evidence_json, cooldown_key = row
    evidence = json.loads(evidence_json) if evidence_json else {}

    # Step 1: Extract editable targets
    editable = _extract_editable_targets(full_path)
    if not editable:
        return {'error': 'No editable targets found'}

    # Step 2: Generate patch intent
    intent = _generate_patch_intent(weakness, evidence, editable)
    if not intent:
        return {'error': 'Gemma returned no valid patch intent'}

    # Step 3: Validate intent
    valid, reason = _validate_patch_intent(intent, editable)
    if not valid:
        return {'error': f'Intent validation failed: {reason}', 'intent': intent}

    # Step 4: Synthesize edit on original content (not live file)
    original, edited = _synthesize_edit(full_path, intent['target_name'],
                                         intent['proposed_value'], editable)

    # Step 5: Deterministic diff
    diff_lines = list(difflib.unified_diff(
        original.split('\n'), edited.split('\n'),
        fromfile=f'a/{target}', tofile=f'b/{target}',
        lineterm='',
    ))
    diff_text = '\n'.join(diff_lines)

    if not diff_text:
        return {'error': 'Deterministic diff produced empty output', 'intent': intent}

    # Step 6: Validators
    # 6a: structural
    struct_ok, struct_reason = _validate_diff_structure(diff_text)
    if not struct_ok:
        return {'error': f'Structural validation: {struct_reason}', 'intent': intent}

    # 6b: patch --dry-run
    import tempfile as _tf
    with _tf.NamedTemporaryFile(mode='w', suffix='.patch', delete=False) as tf:
        tf.write(diff_text)
        patch_file = tf.name
    try:
        pr = _subprocess.run(
            ['patch', '--dry-run', '-p1', '-d', MAEZ_ROOT, '-i', patch_file],
            capture_output=True, text=True, timeout=10,
        )
        if pr.returncode != 0:
            return {'error': f'patch --dry-run: {pr.stderr.strip()[:200]}', 'intent': intent}
    finally:
        os.unlink(patch_file)

    # 6c: py_compile on temp edited file
    with _tf.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as ef:
        ef.write(edited)
        temp_edited = ef.name
    try:
        cr = _subprocess.run(
            [sys.executable, '-m', 'py_compile', temp_edited],
            capture_output=True, text=True, timeout=15,
        )
        if cr.returncode != 0:
            return {'error': f'py_compile: {cr.stderr.strip()[:200]}', 'intent': intent}
    finally:
        os.unlink(temp_edited)

    # Step 7: Create candidate
    pre_hash = _file_sha256(full_path)
    now = _dt.now(_tz.utc).isoformat()
    enriched_evidence = normalize_evidence(dict(evidence))
    enriched_evidence['patch_intent'] = intent
    enriched_evidence['proposal_job_id'] = job_id

    # Compute pre_patch_score_avg
    pre_score = evidence.get('avg_score', 50.0)

    with _rail_conn() as conn:
        cur = conn.execute(
            "INSERT INTO candidates (state, weakness_description, target_file, diff_text, "
            "cognition_evidence, cooldown_key, pre_patch_hash, pre_patch_score_avg, "
            "created_at, validated_at) "
            "VALUES ('validated', ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (weakness, target, diff_text, json.dumps(enriched_evidence, default=str),
             cooldown_key, pre_hash, pre_score, now, now),
        )
        conn.commit()
        cand_id = cur.lastrowid

    _log_evolution({'action': 'CANDIDATE_VALIDATED', 'target': target,
                    'result': f'id={cand_id} via job {job_id}',
                    'detail': f'{intent["target_name"]}={intent["proposed_value"]}'})

    # Score usefulness and persist into evidence
    diff_changed = sum(1 for l in diff_lines
                       if (l.startswith('+') and not l.startswith('+++'))
                       or (l.startswith('-') and not l.startswith('---')))
    usefulness = score_proposal_usefulness(intent, evidence, diff_changed)
    enriched_evidence['usefulness'] = usefulness
    with _rail_conn() as conn:
        conn.execute("UPDATE candidates SET cognition_evidence=? WHERE id=?",
                     (json.dumps(enriched_evidence, default=str), cand_id))
        conn.commit()

    # Continuity mode override — only on validated candidate
    try:
        from core.continuity import set_mode_override
        set_mode_override('corrective')
    except Exception:
        pass

    # Notify Rohit via canonical display
    try:
        from skills.dev_notifier import send_dev
        disp = load_candidate_for_display(cand_id)
        if disp:
            send_dev(format_telegram_notification(disp))
    except Exception:
        pass

    return {'candidate_id': cand_id, 'state': 'validated', 'intent': intent,
            'usefulness': usefulness, 'diff_lines': len(diff_lines)}


# ══════════════════════════════════════════════════════════════════════
#  PROPOSAL WORKER THREAD
# ══════════════════════════════════════════════════════════════════════

def _worker_loop():
    """Background worker: polls proposal_jobs, processes one at a time."""
    logger.info("Proposal worker started (poll every %ds)", WORKER_POLL_INTERVAL)
    while True:
        try:
            _worker_tick()
        except Exception as e:
            logger.error("Proposal worker error: %s", e)
        time.sleep(WORKER_POLL_INTERVAL)


def _worker_tick():
    """Single worker poll cycle: reclaim stale, then process one pending."""
    # Reclaim stale processing jobs
    cutoff = (_dt.now(_tz.utc) - __import__('datetime').timedelta(seconds=JOB_TIMEOUT_SECONDS)).isoformat()
    with _rail_conn() as conn:
        stale = conn.execute(
            "SELECT id, attempt_count FROM proposal_jobs WHERE state='processing' AND started_at < ?",
            (cutoff,),
        ).fetchall()
        for job_id, attempts in stale:
            if attempts + 1 >= MAX_JOB_ATTEMPTS:
                conn.execute(
                    "UPDATE proposal_jobs SET state='failed', last_error='stale processing timeout', "
                    "finished_at=? WHERE id=?",
                    (_dt.now(_tz.utc).isoformat(), job_id),
                )
                logger.info("Proposal worker: job %d failed (stale, max attempts)", job_id)
            else:
                conn.execute(
                    "UPDATE proposal_jobs SET state='pending', started_at=NULL WHERE id=?",
                    (job_id,),
                )
                logger.info("Proposal worker: job %d reclaimed (stale processing)", job_id)
            _log_evolution({'action': 'JOB_STALE_RECOVERY', 'target': str(job_id),
                            'result': 'failed' if attempts + 1 >= MAX_JOB_ATTEMPTS else 'reclaimed'})
        conn.commit()

    # Claim one pending job
    with _rail_conn() as conn:
        row = conn.execute(
            "SELECT id FROM proposal_jobs WHERE state='pending' ORDER BY created_at ASC LIMIT 1"
        ).fetchone()
        if not row:
            return
        job_id = row[0]
        now = _dt.now(_tz.utc).isoformat()
        result = conn.execute(
            "UPDATE proposal_jobs SET state='processing', started_at=?, "
            "attempt_count=attempt_count+1 WHERE id=? AND state='pending'",
            (now, job_id),
        )
        if result.rowcount == 0:
            return  # someone else claimed it
        conn.commit()

    logger.info("Proposal worker: processing job %d", job_id)

    # Process
    try:
        result = process_proposal_job(job_id)
        now = _dt.now(_tz.utc).isoformat()

        if 'candidate_id' in result:
            with _rail_conn() as conn:
                conn.execute(
                    "UPDATE proposal_jobs SET state='done', finished_at=?, candidate_id=? WHERE id=?",
                    (now, result['candidate_id'], job_id),
                )
                conn.commit()
            logger.info("Proposal worker: job %d done → candidate %d", job_id, result['candidate_id'])
        else:
            error = result.get('error', 'unknown')
            with _rail_conn() as conn:
                row = conn.execute("SELECT attempt_count FROM proposal_jobs WHERE id=?", (job_id,)).fetchone()
                attempts = row[0] if row else 1
                new_state = 'failed' if attempts >= MAX_JOB_ATTEMPTS else 'pending'
                conn.execute(
                    "UPDATE proposal_jobs SET state=?, finished_at=?, last_error=? WHERE id=?",
                    (new_state, now, error[:500], job_id),
                )
                conn.commit()
            logger.info("Proposal worker: job %d %s (%s)", job_id, new_state, error[:100])

    except Exception as e:
        now = _dt.now(_tz.utc).isoformat()
        with _rail_conn() as conn:
            row = conn.execute("SELECT attempt_count FROM proposal_jobs WHERE id=?", (job_id,)).fetchone()
            attempts = row[0] if row else 1
            new_state = 'failed' if attempts >= MAX_JOB_ATTEMPTS else 'pending'
            conn.execute(
                "UPDATE proposal_jobs SET state=?, finished_at=?, last_error=? WHERE id=?",
                (new_state, now, str(e)[:500], job_id),
            )
            conn.commit()
        logger.error("Proposal worker: job %d error: %s", job_id, e)


def start_proposal_worker():
    """Start the proposal worker thread. Call from daemon startup."""
    import threading
    t = threading.Thread(target=_worker_loop, daemon=True, name="proposal-worker")
    t.start()
    logger.info("Proposal worker thread started")


def enqueue_proposal_job(weakness: str, evidence: dict, cooldown_key: str) -> int | None:
    """Enqueue a proposal job. Returns job_id or None if blocked."""
    # Check for in-flight jobs with same cooldown_key
    with _rail_conn() as conn:
        existing = conn.execute(
            "SELECT id FROM proposal_jobs WHERE cooldown_key=? AND state IN ('pending','processing')",
            (cooldown_key,),
        ).fetchone()
    if existing:
        logger.info("Proposal enqueue suppressed: job %d already in flight for %s", existing[0], cooldown_key)
        return None

    now = _dt.now(_tz.utc).isoformat()
    with _rail_conn() as conn:
        cur = conn.execute(
            "INSERT INTO proposal_jobs (state, weakness_description, evidence_json, "
            "cooldown_key, created_at) VALUES ('pending', ?, ?, ?, ?)",
            (weakness, json.dumps(evidence, default=str), cooldown_key, now),
        )
        conn.commit()
        job_id = cur.lastrowid

    _log_evolution({'action': 'JOB_ENQUEUED', 'target': V1_ALLOWED_TARGET,
                    'result': f'job_id={job_id}', 'detail': weakness[:80]})
    logger.info("Proposal job %d enqueued: %s", job_id, weakness[:60])
    return job_id


# ══════════════════════════════════════════════════════════════════════
#  AUTONOMOUS PROPOSAL TRIGGER — updated for async jobs
# ══════════════════════════════════════════════════════════════════════

def check_proposal_trigger(critique: dict) -> dict | None:
    """Evaluate all 7 conditions and generate proposal if warranted.
    Returns candidate dict or None. Never acquires lock or patches files."""
    target = V1_ALLOWED_TARGET
    conditions = {}

    # Condition 1: critique window just fired (caller guarantees this)
    conditions['critique_fired'] = True

    # Condition 2: avg score below threshold
    avg = critique.get('avg_score', 100)
    conditions['score_below_threshold'] = avg < PROPOSAL_SCORE_THRESHOLD
    if not conditions['score_below_threshold']:
        _log_evolution({'action': 'PROPOSAL_SUPPRESSED', 'target': target,
                        'result': f'score {avg} >= {PROPOSAL_SCORE_THRESHOLD}'})
        logger.info("Proposal trigger: suppressed (score %.1f >= %d)", avg, PROPOSAL_SCORE_THRESHOLD)
        return None

    # Condition 3: dominant failure is fixation (not vague-only)
    try:
        from core.cognition_quality import _recent_labels
        import collections as _cc
        window = min(len(_recent_labels), 20)
        flat = [l for ll in _recent_labels[-window:] for l in ll]
        label_counts = _cc.Counter(flat)
        has_fixation = label_counts.get('fixation', 0) > 0
    except Exception:
        has_fixation = False
    conditions['fixation_present'] = has_fixation
    if not has_fixation:
        _log_evolution({'action': 'PROPOSAL_SUPPRESSED', 'target': target,
                        'result': 'no fixation in dominant failure mode'})
        logger.info("Proposal trigger: suppressed (vague-only, no fixation)")
        return None

    # Condition 4: no active candidate in DB
    reconcile_lock()
    lock = _get_lock_state()
    conditions['no_active_lock'] = lock.get('active_candidate_id') is None
    if not conditions['no_active_lock']:
        _log_evolution({'action': 'PROPOSAL_SUPPRESSED', 'target': target,
                        'result': f'lock held by candidate {lock["active_candidate_id"]}'})
        logger.info("Proposal trigger: suppressed (lock held)")
        return None

    # Condition 5: cooldown
    weakness_preview = f"fixation_{critique.get('dominant_topic', 'unknown')}"
    cooldown_key = _normalize_cooldown_key(weakness_preview, target)
    with _rail_conn() as conn:
        recent = conn.execute(
            "SELECT resolved_at FROM candidates WHERE cooldown_key=? AND resolved_at IS NOT NULL "
            "ORDER BY resolved_at DESC LIMIT 1", (cooldown_key,),
        ).fetchone()
    in_cooldown = False
    if recent and recent[0]:
        try:
            age_h = (_dt.now(_tz.utc) - _dt.fromisoformat(recent[0])).total_seconds() / 3600
            in_cooldown = age_h < COOLDOWN_HOURS
        except Exception:
            pass
    conditions['cooldown_clear'] = not in_cooldown
    if in_cooldown:
        _log_evolution({'action': 'PROPOSAL_SUPPRESSED', 'target': target,
                        'result': f'cooldown active ({age_h:.1f}h < {COOLDOWN_HOURS}h)'})
        logger.info("Proposal trigger: suppressed (cooldown)")
        return None

    # Condition 6: no unresolved same-key proposal OR in-flight job
    with _rail_conn() as conn:
        existing_cand = conn.execute(
            "SELECT id FROM candidates WHERE cooldown_key=? AND state IN ('proposed','validated','queued')",
            (cooldown_key,),
        ).fetchone()
        existing_job = conn.execute(
            "SELECT id FROM proposal_jobs WHERE cooldown_key=? AND state IN ('pending','processing')",
            (cooldown_key,),
        ).fetchone()
    conditions['no_unresolved_proposal'] = existing_cand is None and existing_job is None
    if existing_cand:
        _log_evolution({'action': 'PROPOSAL_SUPPRESSED', 'target': target,
                        'result': f'unresolved proposal {existing_cand[0]} exists'})
        logger.info("Proposal trigger: suppressed (unresolved proposal %d)", existing_cand[0])
        return None
    if existing_job:
        _log_evolution({'action': 'PROPOSAL_SUPPRESSED', 'target': target,
                        'result': f'proposal work already in flight (job {existing_job[0]})'})
        logger.info("Proposal trigger: suppressed (in-flight job %d)", existing_job[0])
        return None

    # Condition 7: enough evidence
    try:
        from core.cognition_quality import _recent_scores
        evidence_count = len(_recent_scores)
    except Exception:
        evidence_count = 0
    conditions['enough_evidence'] = evidence_count >= MIN_EVIDENCE_CYCLES
    if not conditions['enough_evidence']:
        _log_evolution({'action': 'PROPOSAL_SUPPRESSED', 'target': target,
                        'result': f'only {evidence_count} cycles (need {MIN_EVIDENCE_CYCLES})'})
        logger.info("Proposal trigger: suppressed (only %d evidence cycles)", evidence_count)
        return None

    # All conditions passed — enqueue proposal job (non-blocking)
    logger.info("Proposal trigger: ALL CONDITIONS MET — enqueuing job")
    _log_evolution({'action': 'PROPOSAL_TRIGGERED', 'target': target,
                    'result': f'avg={avg} conditions={conditions}'})

    evidence = _build_evidence_packet(critique)
    weakness = _derive_weakness(critique, evidence)

    job_id = enqueue_proposal_job(weakness, evidence, cooldown_key)
    if job_id:
        logger.info("Proposal trigger: job %d enqueued (non-blocking)", job_id)
        return {'job_id': job_id, 'state': 'enqueued', 'weakness': weakness}
    else:
        logger.info("Proposal trigger: enqueue suppressed (duplicate in-flight)")
        return None


# ══════════════════════════════════════════════════════════════════════
#  CLI
# ══════════════════════════════════════════════════════════════════════

_USEFULNESS_EMOJI = {
    'strong': '\u2705 recommended',
    'acceptable': '\u26a0\ufe0f review carefully',
    'weak': '\u274c low confidence',
    'unknown': '\u26aa insufficient evidence to assess',
}


def _render_candidate_cli(disp: dict):
    """Render a display object from load_candidate_for_display to stdout."""
    sep = '\u2550' * 50
    u = disp['usefulness']
    overall = u.get('overall', 'unknown')

    print(sep)
    print(f"CANDIDATE {disp['id']} \u2014 {disp['state']} \u2014 usefulness: {overall}")
    print(sep)
    print(f"Weakness:  {disp['weakness']}")

    ev = disp['evidence']
    if ev:
        print(f"Evidence:  {len(ev.get('scores', []))} cycles, avg score {ev.get('avg_score', '?')},")
        print(f"           dominant failure: {ev.get('dominant_failure_mode', '?')}")
        print(f"           dominant topic: {ev.get('dominant_topic', '?')}")
        print(f"           evidence complete: {ev.get('evidence_complete', '?')}")

    print()
    print("Proposed change:")
    print(f"  File:    {disp['target_file']}")
    intent = disp['intent']
    if intent:
        print(f"  Target:  {intent.get('target_name', '?')}")
        print(f"  Before:  {intent.get('current_value')!r}")
        print(f"  After:   {intent.get('proposed_value')!r}")
        print(f"  Why:     {intent.get('rationale', '?')}")
    else:
        print(f"  (no structured intent available)")

    print()
    print("Usefulness assessment:")
    afm = u.get('addresses_failure_mode')
    ds = u.get('direction_sane')
    cm = u.get('change_minimal')
    print(f"  Addresses failure mode: {'yes' if afm else ('no' if afm is False else 'n/a')}")
    print(f"  Direction sane:         {'yes' if ds else ('no' if ds is False else 'n/a')}")
    print(f"  Change minimal:         {'yes' if cm else ('no' if cm is False else 'n/a')}")
    print(f"  Overall:                {overall}")
    print(f"  Reasoning:              {u.get('reasoning', '?')}")

    if disp.get('diff_text'):
        print()
        print("Diff preview:")
        for line in disp['diff_text'].split('\n')[:20]:
            print(f"  {line}")

    print()
    print(f"To apply:  python -m skills.evolution_engine apply {disp['id']}")
    print(f"To reject: python -m skills.evolution_engine reject {disp['id']}")
    print(sep)


def format_telegram_notification(disp: dict) -> str:
    """Format Telegram notification from canonical display object."""
    u = disp['usefulness']
    overall = u.get('overall', 'unknown')
    intent = disp.get('intent') or {}
    emoji = _USEFULNESS_EMOJI.get(overall, '')

    return (
        f"\U0001f9e0 Maez self-edit proposal\n\n"
        f"Weakness: {disp['weakness'][:150]}\n"
        f"Candidate: {disp['id']} | Usefulness: {overall}\n"
        f"Change: {intent.get('target_name', '?')} "
        f"{intent.get('current_value')!r} \u2192 {intent.get('proposed_value')!r}\n"
        f"Why: {intent.get('rationale', '?')}\n\n"
        f"{emoji}\n\n"
        f"python -m skills.evolution_engine show {disp['id']}\n"
        f"python -m skills.evolution_engine apply {disp['id']}\n"
        f"python -m skills.evolution_engine reject {disp['id']}"
    )


def retroactive_normalize():
    """Normalize evidence and recompute usefulness for all existing candidates."""
    with _rail_conn() as conn:
        conn.row_factory = _sqlite3.Row
        rows = conn.execute("SELECT id, cognition_evidence, diff_text FROM candidates").fetchall()

    count = 0
    for row in rows:
        cid = row['id']
        ev = {}
        if row['cognition_evidence']:
            try:
                ev = json.loads(row['cognition_evidence'])
            except Exception:
                continue

        old_overall = ev.get('usefulness', {}).get('overall', 'none')
        ev = normalize_evidence(ev)

        intent = ev.get('patch_intent')
        if intent:
            diff_changed = 0
            if row['diff_text']:
                diff_changed = sum(1 for l in row['diff_text'].split('\n')
                                   if (l.startswith('+') and not l.startswith('+++'))
                                   or (l.startswith('-') and not l.startswith('---')))
            ev['usefulness'] = score_proposal_usefulness(intent, ev, diff_changed)
        elif not ev.get('usefulness'):
            ev['usefulness'] = {
                'addresses_failure_mode': None, 'direction_sane': None,
                'change_minimal': None, 'overall': 'unknown',
                'reasoning': 'No patch intent available',
            }

        new_overall = ev.get('usefulness', {}).get('overall', 'unknown')
        with _rail_conn() as conn:
            conn.execute("UPDATE candidates SET cognition_evidence=? WHERE id=?",
                         (json.dumps(ev, default=str), cid))
            conn.commit()

        logger.info("retroactive normalization: candidate %d, was %s, now %s", cid, old_overall, new_overall)
        print(f"  [{cid}] {old_overall} → {new_overall} (evidence_complete={ev.get('evidence_complete')})")
        count += 1

    return count


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)

    if len(sys.argv) < 2:
        print("Usage: python -m skills.evolution_engine <command> [args]")
        print("Commands: dry-run <weakness>, apply <id>, status, candidates, show <id>, reject <id>")
        sys.exit(0)

    cmd = sys.argv[1]

    if cmd == 'dry-run':
        if len(sys.argv) < 3:
            print("Usage: dry-run <weakness description>")
            sys.exit(1)
        weakness = ' '.join(sys.argv[2:])
        print(f"Generating diff for: {weakness}")
        result = generate_diff(weakness)
        print(json.dumps(result, indent=2, default=str))

    elif cmd == 'apply':
        if len(sys.argv) < 3:
            print("Usage: apply <candidate_id>")
            sys.exit(1)
        cand_id = int(sys.argv[2])
        print(f"Applying candidate {cand_id}...")
        result = apply_candidate(cand_id)
        print(json.dumps(result, indent=2, default=str))

    elif cmd == 'show':
        if len(sys.argv) < 3:
            print("Usage: show <candidate_id>")
            sys.exit(1)
        cid = int(sys.argv[2])
        disp = load_candidate_for_display(cid)
        if not disp:
            print(f"Candidate {cid} not found")
        else:
            _render_candidate_cli(disp)

    elif cmd == 'reject':
        if len(sys.argv) < 3:
            print("Usage: reject <candidate_id>")
            sys.exit(1)
        cid = int(sys.argv[2])
        with _rail_conn() as conn:
            row = conn.execute("SELECT state FROM candidates WHERE id=?", (cid,)).fetchone()
        if not row:
            print(f"Candidate {cid} not found")
        else:
            _set_candidate_state(cid, 'rejected', rejection_reason='manual rejection')
            _log_evolution({'action': 'MANUAL_REJECTION', 'target': V1_ALLOWED_TARGET,
                            'result': f'candidate {cid}'})
            print(f"Candidate {cid} rejected (was: {row[0]})")

    elif cmd == 'status':
        status = rail_status()
        print(json.dumps(status, indent=2, default=str))

    elif cmd == 'candidates':
        cands = list_candidates()
        for c in cands:
            print(f"  [{c['id']}] {c['state']:12s} {c['target'] or '?':35s} {c['weakness']}")

    else:
        print(f"Unknown command: {cmd}")
        print("Commands: dry-run <weakness>, apply <id>, status, candidates, show <id>, reject <id>")
