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


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    print("=== GitHub Search Test ===")
    results = _search_github("python duckduckgo search RSS", 3)
    for r in results:
        print(f"  {r['name']} ({r['stars']} stars) — {r['description'][:60]}")
    print("\n=== Validation Test ===")
    ok, _ = validate_syntax("def hello(): return 'world'")
    print(f"Safe code syntax: {ok}")
    ok, concerns = validate_security("os.system('rm -rf /')", 'test.py')
    print(f"Dangerous code security: safe={ok}, concerns={concerns}")
