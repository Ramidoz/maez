"""
git_awareness.py — Monitor git repos for Maez

Scans repos under /home/rohit/, injects [GIT] context block.
Shows uncommitted changes, unpushed commits, current branches.
"""

import logging
import os
import subprocess
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger("maez")

_cache = None
_cache_time = 0
CACHE_TTL = 300


def _run_git(repo_path: str, args: list) -> Optional[str]:
    try:
        result = subprocess.run(
            ['git', '-C', repo_path] + args,
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return None


def find_repos() -> list:
    repos = []
    try:
        result = subprocess.run(
            ['find', '/home/rohit', '-name', '.git',
             '-maxdepth', '4', '-type', 'd',
             '-not', '-path', '*/.venv/*',
             '-not', '-path', '*/node_modules/*'],
            capture_output=True, text=True, timeout=15
        )
        for line in result.stdout.strip().split('\n'):
            if line:
                repos.append(str(Path(line).parent))
    except Exception as e:
        logger.error("find repos failed: %s", e)
    return repos


def get_repo_status(repo_path: str) -> dict:
    name = os.path.basename(repo_path)
    branch = _run_git(repo_path, ['branch', '--show-current']) or 'unknown'

    status = _run_git(repo_path, ['status', '--porcelain']) or ''
    changed_files = [l.strip() for l in status.split('\n') if l.strip()]

    unpushed = _run_git(repo_path, ['log', '@{u}..', '--oneline', '--no-decorate']) or ''
    unpushed_commits = [l for l in unpushed.split('\n') if l.strip()]

    last_commit = _run_git(repo_path, ['log', '-1', '--format=%s|%cr', '--no-decorate']) or ''
    last_msg, last_time = '', ''
    if '|' in last_commit:
        parts = last_commit.split('|', 1)
        last_msg = parts[0].strip()[:60]
        last_time = parts[1].strip()

    return {
        'name': name, 'path': repo_path, 'branch': branch,
        'changed_files': changed_files,
        'unpushed_commits': unpushed_commits,
        'last_commit_msg': last_msg, 'last_commit_time': last_time,
        'is_dirty': len(changed_files) > 0,
        'has_unpushed': len(unpushed_commits) > 0,
    }


def scan_all() -> list:
    global _cache, _cache_time
    now = time.time()
    if _cache and now - _cache_time < CACHE_TTL:
        return _cache

    repos = find_repos()
    statuses = []
    for repo in repos:
        try:
            statuses.append(get_repo_status(repo))
        except Exception as e:
            logger.debug("repo scan failed %s: %s", repo, e)

    _cache = statuses
    _cache_time = now
    dirty = sum(1 for r in statuses if r['is_dirty'])
    logger.info("Git scan: %d repos, %d dirty", len(statuses), dirty)
    return statuses


def format_for_context() -> str:
    statuses = scan_all()
    if not statuses:
        return "[GIT] No git repos found."

    dirty = [r for r in statuses if r['is_dirty']]
    unpushed = [r for r in statuses if r['has_unpushed'] and not r['is_dirty']]
    clean = [r for r in statuses if not r['is_dirty'] and not r['has_unpushed']]

    if not dirty and not unpushed:
        latest = max(statuses, key=lambda r: r['last_commit_time'] or '', default=statuses[0])
        return (f"[GIT] All {len(statuses)} repos clean. "
                f"Last: {latest['last_commit_msg']} ({latest['last_commit_time']})")

    lines = ["[GIT]"]
    for repo in dirty:
        lines.append(f"  {repo['name']} ({repo['branch']}): "
                     f"{len(repo['changed_files'])} uncommitted")
        for f in repo['changed_files'][:3]:
            lines.append(f"    {f}")
        if len(repo['changed_files']) > 3:
            lines.append(f"    ... +{len(repo['changed_files'])-3} more")

    for repo in unpushed:
        lines.append(f"  {repo['name']}: {len(repo['unpushed_commits'])} unpushed")

    if clean:
        lines.append(f"  {len(clean)} other repos clean.")
    return '\n'.join(lines)


def get_summary_for_telegram() -> str:
    statuses = scan_all()
    dirty = [r for r in statuses if r['is_dirty']]
    unpushed = [r for r in statuses if r['has_unpushed']]

    if not dirty and not unpushed:
        return f"All {len(statuses)} repos clean. Nothing uncommitted."

    lines = []
    if dirty:
        lines.append(f"{len(dirty)} repo(s) with uncommitted work:")
        for repo in dirty:
            lines.append(f"  {repo['name']} ({repo['branch']}): {len(repo['changed_files'])} files")
            for f in repo['changed_files'][:3]:
                lines.append(f"    {f}")
    if unpushed:
        lines.append(f"{len(unpushed)} repo(s) with unpushed commits:")
        for repo in unpushed:
            lines.append(f"  {repo['name']}: {len(repo['unpushed_commits'])} commits")
    return '\n'.join(lines)


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    print(format_for_context())
