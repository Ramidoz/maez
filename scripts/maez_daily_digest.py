#!/usr/bin/env python3
"""Maez daily digest -- morning status summary.

Runs at 7 AM via Hermes cron. Collects:
- Git log since yesterday
- Test function count
- Latest handoff open queue (top 5 items)
- Service status (maez, maez-web, llama-server)
- Memory state (if accessible)

Outputs plain text to stdout. Hermes delivers it.

NOT the drift-detection harness. That is scripts/probe/maez_drift_report.py
(slice G.A) -- a signal-classifying PASS/WARN/CRITICAL instrument with its
own test suite. This file was originally named maez_drift_report.py too,
which collided with it; renamed 2026-08-17. This is a status digest and
makes no drift judgement.
"""

import subprocess
import re
from datetime import datetime, timedelta
from pathlib import Path

REPO = Path("/home/rohit/maez")
DATE_TODAY = datetime.now().strftime("%Y-%m-%d")
DATE_YESTERDAY = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")


def run(cmd, cwd=None):
    """Run a command, return stdout or empty string on failure."""
    try:
        r = subprocess.run(
            cmd, shell=True, capture_output=True, text=True,
            cwd=cwd or str(REPO), timeout=30
        )
        return r.stdout.strip()
    except Exception:
        return ""


def git_log_since_yesterday():
    """Commits since yesterday midnight."""
    log = run(f'git log --oneline --since="{DATE_YESTERDAY}" --format="%h %s (%ar)"')
    if not log:
        return "No commits since yesterday."
    lines = log.strip().split("\n")
    return f"{len(lines)} commits since {DATE_YESTERDAY}:\n" + "\n".join(f"  {l}" for l in lines)


def test_count():
    """Count test functions (doesn't run them)."""
    result = run("grep -r 'def test_' tests/ --include='*.py' | wc -l")
    try:
        return int(result)
    except ValueError:
        return "unknown (grep failed)"


def latest_handoff_queue():
    """Extract top open queue items from latest handoff."""
    handoffs = sorted(REPO.glob("docs/HANDOFF-*.md"), reverse=True)
    if not handoffs:
        return "No handoff docs found."
    
    content = handoffs[0].read_text()
    # Find the open queue section — stop at next ## (not ###)
    queue_match = re.search(r"## Open queue.*?(?=\n## [^#]|\Z)", content, re.DOTALL)
    if not queue_match:
        return f"Latest handoff ({handoffs[0].name}): no open queue section found."
    
    queue_text = queue_match.group(0)
    # Extract numbered items (limit to 5)
    items = re.findall(r"^\d+\.\s+\*\*(.+?)\*\*", queue_text, re.MULTILINE)
    if not items:
        return f"Latest handoff ({handoffs[0].name}): queue section exists but no numbered items found."
    
    header = f"Open queue from {handoffs[0].name} (top {min(5, len(items))}):\n"
    return header + "\n".join(f"  {i+1}. {item}" for i, item in enumerate(items[:5]))


def service_status():
    """Check Maez services status."""
    services = ["maez", "maez-web", "maez-watchdog", "maez-subscription-proxy", "llama-server"]
    lines = []
    for svc in services:
        # --user is REQUIRED: every Maez unit is user-scoped, and without it
        # this reports "inactive" for services that are running fine.
        status = run(f"systemctl --user is-active {svc}.service 2>/dev/null")
        if not status:
            status = "unknown"
        lines.append(f"  {svc}: {status}")
    return "Service status:\n" + "\n".join(lines)


def memory_state():
    """Quick memory stats if DBs are accessible."""
    stats = []
    
    # Count lived episodes
    episodes = run("sqlite3 memory/db/raw/chroma.sqlite3 'SELECT count(*) FROM embeddings;' 2>/dev/null")
    if episodes:
        stats.append(f"  Raw memory entries: {episodes}")
    
    # Entity index count
    entity_count = run("sqlite3 memory/recall_stats.db 'SELECT count(*) FROM entities;' 2>/dev/null")
    if entity_count:
        stats.append(f"  Entity index: {entity_count}")
    
    # Wonderings
    wonderings = run("sqlite3 memory/quality.db 'SELECT count(*) FROM wonderings WHERE status=\"active\";' 2>/dev/null")
    if wonderings:
        stats.append(f"  Active wonderings: {wonderings}")
    
    if not stats:
        return "Memory state: DBs not accessible (services may be down)."
    return "Memory state:\n" + "\n".join(stats)


def main():
    print(f"=== MAEZ DAILY DRIFT REPORT — {DATE_TODAY} ===")
    print()
    print(git_log_since_yesterday())
    print()
    print(f"Test functions: {test_count()}")
    print()
    print(service_status())
    print()
    print(memory_state())
    print()
    print(latest_handoff_queue())
    print()
    print("=== END ===")


if __name__ == "__main__":
    main()
