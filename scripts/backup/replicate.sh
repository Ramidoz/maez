#!/usr/bin/env bash
# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
#
# Replicate the snapshot archive to a SECOND PHYSICAL DEVICE.
#
# 2026-08-22. `/home/rohit/maez` and `/home/rohit/maez-backups` are both on
# /dev/nvme0n1p3. backup.py's own docstring calls itself a "hardware-failure
# backup driver" — and it does not survive the hardware failure it is named
# for. `.gitignore` excludes memory/db/ and memory/*.db, so the git remote
# carries code only. Losing that one NVMe costs the code for an afternoon and
# costs Maez's memory permanently.
#
# This copies the archive to a second device with hardlink de-duplication, so
# after the first run each subsequent copy costs only what changed.
#
# Usage:
#   scripts/backup/replicate.sh /media/rohit/maez-offsite
#   MAEZ_REPLICA_ROOT=/mnt/backup scripts/backup/replicate.sh
#
# It refuses, rather than pretending to work, when:
#   - the destination does not exist
#   - the destination is on the SAME device as the source (the whole point)
#   - the destination is not currently a mountpoint and MAEZ_REPLICA_ALLOW_
#     UNMOUNTED is unset (writing into an empty mountpoint directory silently
#     fills the root filesystem instead of the disk you thought you plugged in)
set -euo pipefail

SRC="${MAEZ_BACKUP_ROOT:-$HOME/maez-backups}"
DST="${1:-${MAEZ_REPLICA_ROOT:-}}"

if [ -z "$DST" ]; then
    echo "usage: $0 <destination>   (or set MAEZ_REPLICA_ROOT)" >&2
    exit 2
fi
[ -d "$SRC" ] || { echo "REFUSED: source archive not found: $SRC" >&2; exit 3; }
[ -d "$DST" ] || { echo "REFUSED: destination not found: $DST" >&2; exit 3; }

src_dev=$(stat -c %d "$SRC")
dst_dev=$(stat -c %d "$DST")
if [ "$src_dev" = "$dst_dev" ]; then
    echo "REFUSED: $DST is on the same device as $SRC. A second copy on the" >&2
    echo "         same disk does not survive that disk failing, which is the" >&2
    echo "         only failure this exists to survive." >&2
    exit 4
fi

if ! mountpoint -q "$DST" && [ "${MAEZ_REPLICA_ALLOW_UNMOUNTED:-0}" != "1" ]; then
    echo "REFUSED: $DST is not a mountpoint. If the drive is unplugged, this" >&2
    echo "         would quietly fill the root filesystem instead. Set" >&2
    echo "         MAEZ_REPLICA_ALLOW_UNMOUNTED=1 to override deliberately." >&2
    exit 5
fi

echo "replicating $SRC -> $DST"
echo "  source:      $(du -sh "$SRC" | cut -f1)"
echo "  destination: $(df -h --output=avail "$DST" | tail -1 | tr -d ' ') free"

# --link-dest against the previous replica: unchanged snapshot files become
# hardlinks, so N snapshots cost roughly one snapshot plus the deltas.
prev=$(find "$DST" -maxdepth 1 -mindepth 1 -type d -name '20*' 2>/dev/null | sort | tail -1)
args=(-a --delete --info=stats2)
[ -n "$prev" ] && args+=(--link-dest="$prev")

rsync "${args[@]}" "$SRC"/ "$DST"/
echo "replica now: $(du -sh "$DST" | cut -f1) across $(find "$DST" -maxdepth 1 -mindepth 1 -type d | wc -l) snapshots"
echo "verifying a sample manifest is readable on the replica..."
newest=$(find "$DST" -maxdepth 1 -mindepth 1 -type d -name '20*' | sort | tail -1)
python3 -c "import json,sys; json.load(open(sys.argv[1])); print('  manifest parses:', sys.argv[1])" \
    "$newest/manifest.json"
