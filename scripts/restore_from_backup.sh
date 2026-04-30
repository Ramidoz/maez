#!/usr/bin/env bash
# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# Hardware-failure restore wrapper (Decision 22 v1).
#
# Thin shell wrapper around `python -m scripts.backup.restore_cli`.
#
# IMPORTANT: this OVERWRITES live state. Stop the maez daemon before
# restoring (otherwise concurrent writes will corrupt the restored
# state). The script does NOT auto-stop the daemon.
#
# Usage:
#   scripts/restore_from_backup.sh \
#     --snapshot ~/maez-backups/2026-04-30T06-00-00 \
#     --reason hardware-failure
#
# Reason flag is REQUIRED. Choose:
#   --reason hardware-failure   writes a coma core memory
#   --reason deliberate-pause   no coma write, only an operational log
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${MAEZ_ROOT:-$(cd "$SCRIPT_DIR/.." && pwd)}"

cd "$REPO_ROOT"

if [[ -x "$REPO_ROOT/.venv/bin/python" ]]; then
    PYTHON="$REPO_ROOT/.venv/bin/python"
else
    PYTHON="${PYTHON:-python3}"
fi

# Pre-flight: warn if maez daemon is running.
if systemctl --user is-active maez.service >/dev/null 2>&1 || \
   systemctl is-active maez.service >/dev/null 2>&1; then
    echo "WARNING: maez.service is active. Concurrent writes during" >&2
    echo "         restore will corrupt the restored state. Stop the" >&2
    echo "         daemon first:" >&2
    echo "           systemctl --user stop maez.service" >&2
    echo "         then re-run this script. Aborting." >&2
    exit 3
fi

exec "$PYTHON" -m scripts.backup.restore_cli "$@"
