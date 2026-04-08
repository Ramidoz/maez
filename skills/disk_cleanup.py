"""
disk_cleanup.py — Scan disk and propose cleanup to Rohit

Scans for safe-to-clean files, calculates savings,
sends Telegram summary. Rohit approves before execution.
"""

import logging
import os
import re
import subprocess
import time
from pathlib import Path

logger = logging.getLogger("maez")


def _get_size(path: str) -> int:
    try:
        result = subprocess.run(['du', '-sb', path],
                                capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            return int(result.stdout.split()[0])
    except Exception:
        pass
    return 0


def _count_old_files(directory: str, hours: int = 24) -> tuple:
    count = 0
    total = 0
    try:
        cutoff = time.time() - (hours * 3600)
        for f in Path(directory).rglob('*'):
            if f.is_file():
                try:
                    if f.stat().st_mtime < cutoff:
                        count += 1
                        total += f.stat().st_size
                except Exception:
                    pass
    except Exception:
        pass
    return count, total


def scan() -> dict:
    report = {'items': [], 'total_bytes': 0,
              'scanned_at': time.strftime('%Y-%m-%d %H:%M:%S')}

    # /tmp old files
    try:
        count, size = _count_old_files('/tmp', hours=24)
        if size > 1024 * 1024:
            report['items'].append({
                'path': '/tmp', 'description': f'{count} files older than 24h',
                'bytes': size, 'command': 'find /tmp -type f -atime +1 -delete',
                'safe': True,
            })
            report['total_bytes'] += size
    except Exception:
        pass

    # apt cache
    apt_size = _get_size('/var/cache/apt/archives')
    if apt_size > 50 * 1024 * 1024:
        report['items'].append({
            'path': '/var/cache/apt/archives', 'description': 'apt package cache',
            'bytes': apt_size, 'command': 'sudo apt-get clean', 'safe': True,
        })
        report['total_bytes'] += apt_size

    # pip cache
    pip_cache = os.path.expanduser('~/.cache/pip')
    if os.path.exists(pip_cache):
        pip_size = _get_size(pip_cache)
        if pip_size > 100 * 1024 * 1024:
            report['items'].append({
                'path': pip_cache, 'description': 'pip package cache',
                'bytes': pip_size, 'command': f'rm -rf {pip_cache}', 'safe': True,
            })
            report['total_bytes'] += pip_size

    # thumbnail cache
    thumb_cache = os.path.expanduser('~/.cache/thumbnails')
    if os.path.exists(thumb_cache):
        thumb_size = _get_size(thumb_cache)
        if thumb_size > 50 * 1024 * 1024:
            report['items'].append({
                'path': thumb_cache, 'description': 'thumbnail cache',
                'bytes': thumb_size, 'command': f'rm -rf {thumb_cache}', 'safe': True,
            })
            report['total_bytes'] += thumb_size

    # journald logs
    try:
        result = subprocess.run(['journalctl', '--disk-usage'],
                                capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            match = re.search(r'take up ([\d.]+)([KMGT])', result.stdout)
            if match:
                size_val = float(match.group(1))
                unit = match.group(2)
                mult = {'K': 1024, 'M': 1024**2, 'G': 1024**3, 'T': 1024**4}
                journal_bytes = int(size_val * mult.get(unit, 1))
                if journal_bytes > 500 * 1024 * 1024:
                    report['items'].append({
                        'path': '/var/log/journal', 'description': 'systemd journal logs',
                        'bytes': journal_bytes, 'command': 'sudo journalctl --vacuum-time=7d',
                        'safe': True,
                    })
                    report['total_bytes'] += journal_bytes
    except Exception:
        pass

    return report


def format_telegram_message(report: dict) -> str:
    if not report['items']:
        return "Disk scan complete. Nothing significant to clean."
    total_mb = report['total_bytes'] / (1024 * 1024)
    size_str = f"{total_mb / 1024:.1f} GB" if total_mb >= 1024 else f"{total_mb:.0f} MB"
    lines = [f"Found {size_str} to clean:\n"]
    for item in report['items']:
        lines.append(f"  {item['description']}: {item['bytes'] / (1024*1024):.0f} MB")
    lines.append(f"\n/approve_cleanup to free {size_str}.\n/cancel to skip.")
    return '\n'.join(lines)


def execute_cleanup(report: dict) -> dict:
    results = []
    freed = 0
    for item in report['items']:
        if not item.get('safe'):
            continue
        try:
            cmd = item['command'].split()
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if r.returncode == 0:
                results.append(f"Cleaned {item['description']}")
                freed += item['bytes']
            else:
                results.append(f"Failed: {item['description']}")
        except Exception as e:
            logger.error("Cleanup error %s: %s", item['description'], e)
    return {'results': results, 'freed_bytes': freed, 'freed_mb': freed / (1024 * 1024)}


if __name__ == '__main__':
    r = scan()
    print(format_telegram_message(r))
