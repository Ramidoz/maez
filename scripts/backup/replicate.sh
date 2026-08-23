#!/usr/bin/env bash
# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
#
# Replicate the snapshot archive to a SECOND PHYSICAL DEVICE.
#
# 2026-08-22. /home/rohit/maez and /home/rohit/maez-backups are both on
# /dev/nvme0n1p3. backup.py calls itself a "hardware-failure backup driver"
# and does not survive the hardware failure it is named for. .gitignore
# excludes memory/db/ and memory/*.db, so the git remote carries code only.
# Losing that one NVMe costs the code for an afternoon and costs Maez's
# memory permanently.
#
# Two replication modes, chosen by probing the destination rather than by
# assuming:
#
#   POSIX destination (ext4, xfs, btrfs...) -> rsync mirror. Cheap,
#       incremental, preserves modes and ownership.
#
#   NON-POSIX destination (exFAT, FAT32, NTFS-without-perms) -> one
#       zstd-compressed tar per snapshot. The first version of this script
#       assumed rsync and was wrong for the drive actually attached: exFAT
#       cannot store POSIX modes, and 138 files in every snapshot are mode
#       0600: 131 under memory/continuity_archive, the six-file WebAuthn
#       ceremony store under memory/s7_1_webauthn (including ceremony.sqlite3
#       and its audit journal), and memory/continuity_capsule.json. Copied as
#       a plain tree they land 0755 on the mount -- world-readable
#       authentication and continuity material -- and restore with the wrong
#       modes. Inside a tar they keep their modes exactly; verified by
#       round-tripping ceremony.sqlite3 and reading 600 back.
#       Snapshots are immutable once finalized, so each is tarred once and
#       skipped thereafter -- incremental at snapshot granularity.
#
# Usage:
#   scripts/backup/replicate.sh /run/media/rohit/Lexar/MAEZ/maez-archive
#   MAEZ_REPLICA_ROOT=/mnt/backup scripts/backup/replicate.sh
#   scripts/backup/replicate.sh <dst> --dry-run
set -euo pipefail

SRC="${MAEZ_BACKUP_ROOT:-$HOME/maez-backups}"
DST="${1:-${MAEZ_REPLICA_ROOT:-}}"
DRY=0
[ "${2:-}" = "--dry-run" ] && DRY=1

if [ -z "$DST" ]; then
    echo "usage: $0 <destination> [--dry-run]   (or set MAEZ_REPLICA_ROOT)" >&2
    exit 2
fi
[ -d "$SRC" ] || { echo "REFUSED: source archive not found: $SRC" >&2; exit 3; }

parent=$(dirname "$DST")
[ -d "$parent" ] || { echo "REFUSED: destination parent not found: $parent" >&2; exit 3; }
mkdir -p "$DST"

# The whole point: a second copy on the same disk survives nothing.
if [ "$(stat -c %d "$SRC")" = "$(stat -c %d "$DST")" ]; then
    echo "REFUSED: $DST is on the same device as $SRC. A second copy on the" >&2
    echo "         same disk does not survive that disk failing, which is the" >&2
    echo "         only failure this exists to survive." >&2
    exit 4
fi

# An unplugged drive leaves an empty directory behind; writing into it fills
# the root filesystem instead of the disk you thought you plugged in.
mp="$DST"; while [ "$mp" != "/" ] && ! mountpoint -q "$mp"; do mp=$(dirname "$mp"); done
if [ "$mp" = "/" ] && [ "${MAEZ_REPLICA_ALLOW_UNMOUNTED:-0}" != "1" ]; then
    echo "REFUSED: $DST is not under any mountpoint other than /. If the drive" >&2
    echo "         is unplugged this would quietly fill the root filesystem." >&2
    echo "         Set MAEZ_REPLICA_ALLOW_UNMOUNTED=1 to override." >&2
    exit 5
fi

# Probe, do not assume: can this filesystem hold a restrictive mode?
probe="$DST/.maez-mode-probe"
: > "$probe"; chmod 600 "$probe" 2>/dev/null || true
mode=$(stat -c %a "$probe" 2>/dev/null || echo "?")
rm -f "$probe"
if [ "$mode" = "600" ]; then MODE=posix; else MODE=tar; fi

fstype=$(findmnt -no FSTYPE "$mp" 2>/dev/null || echo unknown)
echo "source:      $SRC  ($(du -sh "$SRC" | cut -f1), $(find "$SRC" -maxdepth 1 -mindepth 1 -type d | wc -l) snapshots)"
echo "destination: $DST"
echo "  mount $mp  fstype $fstype  0600-probe -> $mode  => mode: $MODE"
echo "  free: $(df -h --output=avail "$mp" | tail -1 | tr -d ' ')"
[ "$DRY" = "1" ] && echo "  (dry run)"

if [ "$MODE" = posix ]; then
    args=(-a --delete --info=stats2)
    [ "$DRY" = "1" ] && args+=(--dry-run)
    rsync "${args[@]}" "$SRC"/ "$DST"/
else
    copied=0; skipped=0
    for snap in "$SRC"/*/; do
        name=$(basename "$snap")
        [ -f "$snap/manifest.json" ] || continue        # unfinalized: skip
        out="$DST/$name.tar.zst"
        if [ -f "$out" ]; then skipped=$((skipped+1)); continue; fi
        if [ "$DRY" = "1" ]; then
            echo "  would archive $name"; copied=$((copied+1)); continue
        fi
        # Write to a temp name and rename, so an interrupted run never leaves
        # a half-written archive that the next run would skip as "present".
        tar --numeric-owner -C "$SRC" -cf - "$name" \
            | zstd -q -3 -o "$out.partial" -
        mv -f "$out.partial" "$out"
        copied=$((copied+1))
        printf '  archived %s  %s\n' "$name" "$(du -h "$out" | cut -f1)"
    done
    # Mirror local retention: a snapshot pruned locally is pruned here too.
    removed=0
    for arc in "$DST"/*.tar.zst; do
        [ -e "$arc" ] || continue
        base=$(basename "$arc" .tar.zst)
        if [ ! -d "$SRC/$base" ]; then
            [ "$DRY" = "1" ] || rm -f "$arc"
            removed=$((removed+1))
        fi
    done
    echo "archived $copied, already present $skipped, pruned $removed"
fi

if [ "$DRY" = "0" ]; then
    echo "replica: $(du -sh "$DST" | cut -f1)"
    echo "verifying the newest replica archive is readable..."
    if [ "$MODE" = tar ]; then
        newest=$(ls -1 "$DST"/*.tar.zst 2>/dev/null | sort | tail -1)
        zstd -t "$newest"
        # `tar -tf ... | head -1` closes the pipe early and returns 141
        # (128+SIGPIPE), so a successful verification exited non-zero and any
        # systemd timer wrapping this would have reported failure. Count
        # entries instead of truncating the stream.
        entries=$(zstd -dc "$newest" | tar -tf - | wc -l)
        echo "  $(basename "$newest"): $entries entries"
        # A replica nobody has read back is not a backup. Extract one
        # mode-sensitive file and confirm the permission survived the trip
        # through a filesystem that cannot store permissions.
        probe_dir=$(mktemp -d)
        # Probe a file that really is 0600. The WebAuthn ceremony store is
        # the tightest-permissioned thing in the snapshot; if its mode
        # survives, the tar path is doing its job. (An earlier version of
        # this check probed config/identity.yaml, which is 0755 — the check
        # "failed" while the code was correct.)
        if zstd -dc "$newest" | tar -xf - -C "$probe_dir" \
                --wildcards '*/memory/s7_1_webauthn/ceremony.sqlite3' \
                2>/dev/null; then
            got=$(find "$probe_dir" -name ceremony.sqlite3 -printf '%m' -quit)
            echo "  restored ceremony.sqlite3 mode: $got (expect 600)"
            [ "$got" = "600" ] || echo "  WARNING: 0600 was not preserved"
        fi
        rm -rf "$probe_dir"
    else
        newest=$(find "$DST" -maxdepth 1 -mindepth 1 -type d -name '20*' | sort | tail -1)
        python3 -c "import json,sys; json.load(open(sys.argv[1])); print('  manifest parses')" \
            "$newest/manifest.json"
    fi
fi
