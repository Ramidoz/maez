#!/usr/bin/env bash
# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# Hardware-failure backup wrapper (Decision 22 v1).
#
# Thin shell wrapper around `python -m scripts.backup`. Invoked by
# the systemd timer at the configured cadence (6h default).
#
# Defaults:
#   MAEZ_ROOT          repo root (default: this script's parent dir)
#   MAEZ_BACKUP_ROOT   snapshot destination (default: ~/maez-backups)
#
# Owner can opt into secrets via --include-secrets, but only with an
# encrypted destination. See docs/operations/hardware_backup.md.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${MAEZ_ROOT:-$(cd "$SCRIPT_DIR/.." && pwd)}"

cd "$REPO_ROOT"

# Pick venv python if present; fall back to system python3.
if [[ -x "$REPO_ROOT/.venv/bin/python" ]]; then
    PYTHON="$REPO_ROOT/.venv/bin/python"
else
    PYTHON="${PYTHON:-python3}"
fi

exec "$PYTHON" -m scripts.backup "$@"
