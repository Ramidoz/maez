#!/usr/bin/env bash
# Maez continuity backup — consistent, encrypted, off-disk, witnessed.
#
# Captures the validated 2026-06-03 procedure as a repeatable ritual:
#   pause the daemon (so memory DBs are consistent, not torn) → tar the
#   irreplaceable self (.git + code + all of memory/ + soul/identity/secrets),
#   excluding regeneratable bulk (models/.venv/logs/training/data/weights) →
#   zstd → gpg AES256 → an external disk → restart the daemon → WITNESS the
#   archive by decrypting, extracting, and proving Maez's self is readable.
#
# Hard rails:
#   - refuses to write to the SAME physical disk as the repo (that is not a
#     backup — it is false security against the disk-failure case);
#   - ALWAYS restarts the daemon, even on failure (trap);
#   - is not "done" until the restore/list witness passes;
#   - the encryption key lives OFF the backup media (so the SSD alone cannot
#     decrypt); save its contents in a durable secret store independently.
#
# Config (env overrides):
#   MAEZ_REPO         default /home/rohit/maez
#   MAEZ_BACKUP_KEY   default ~/.config/maez/maez_backup.key
#   MAEZ_BACKUP_DEST  default /run/media/rohit/Lexar/MAEZ/MAEZ_CONTINUITY_BACKUPS
#
# Usage:  scripts/maez_backup.sh

set -uo pipefail

REPO="${MAEZ_REPO:-/home/rohit/maez}"
KEYFILE="${MAEZ_BACKUP_KEY:-$HOME/.config/maez/maez_backup.key}"
DEST_ROOT="${MAEZ_BACKUP_DEST:-/run/media/rohit/Lexar/MAEZ/MAEZ_CONTINUITY_BACKUPS}"
SERVICE="${MAEZ_SERVICE:-maez.service}"

fail() { echo "ERROR: $*" >&2; exit 1; }
note() { echo "  $*"; }

# ── preflight ────────────────────────────────────────────────────────
[ -d "$REPO/.git" ] || fail "no git repo at $REPO (set MAEZ_REPO)"
command -v gpg  >/dev/null || fail "gpg not found"
command -v zstd >/dev/null || fail "zstd not found"
command -v sqlite3 >/dev/null || fail "sqlite3 not found (needed for the restore witness)"

# The destination must be present, durable, AND on a DIFFERENT PHYSICAL disk
# than the repo. A backup on the same disk does not survive a disk failure, and
# a backup on tmpfs/RAM does not survive a reboot — refuse both. (Comparing the
# mount source alone is NOT enough: tmpfs and other partitions on the same
# physical disk look "different" but aren't a real backup target.)
[ -d "$DEST_ROOT" ] || fail "destination $DEST_ROOT not present — attach the external drive."
src_src="$(df --output=source "$REPO"      2>/dev/null | tail -1)"
dst_src="$(df --output=source "$DEST_ROOT" 2>/dev/null | tail -1)"
dst_fstype="$(df --output=fstype "$DEST_ROOT" 2>/dev/null | tail -1)"
[ -n "$src_src" ] && [ -n "$dst_src" ] || fail "could not resolve source/destination filesystems"
case "$dst_fstype" in
  tmpfs|ramfs|overlay|"") fail "destination $DEST_ROOT is volatile/non-durable ($dst_fstype) — not a backup. Attach an external drive." ;;
esac
# resolve the underlying physical disk for each (PKNAME = parent block device)
src_disk="$(lsblk -no PKNAME "$src_src" 2>/dev/null | grep -v '^$' | head -1)"; src_disk="${src_disk:-$src_src}"
dst_disk="$(lsblk -no PKNAME "$dst_src" 2>/dev/null | grep -v '^$' | head -1)"; dst_disk="${dst_disk:-$dst_src}"
[ "$src_disk" != "$dst_disk" ] || fail "destination is on the SAME physical disk as the repo ($src_disk) — that is not a backup. Attach an external drive."

# The encryption key must NOT live on the backup media — otherwise the disk
# alone could decrypt the archive and "encrypted off-disk backup" is theater.
# Make the claim below true-by-construction: resolve the key's physical disk
# (via its nearest existing ancestor, since the key may not exist yet) and
# refuse if it is the backup disk. Checked BEFORE we would mint a key, so we
# never write one onto the media and then reject it.
key_probe="$KEYFILE"
while [ ! -e "$key_probe" ] && [ "$key_probe" != "/" ] && [ "$key_probe" != "." ]; do
  key_probe="$(dirname "$key_probe")"
done
key_src="$(df --output=source "$key_probe" 2>/dev/null | tail -1)"
key_disk="$(lsblk -no PKNAME "$key_src" 2>/dev/null | grep -v '^$' | head -1)"; key_disk="${key_disk:-$key_src}"
[ "$key_disk" != "$dst_disk" ] || fail "the backup key ($KEYFILE) is on the SAME disk as the backup destination ($dst_disk) — the media alone could then decrypt the archive. Put MAEZ_BACKUP_KEY on a different disk (default: ~/.config/maez/maez_backup.key)."

# The key: generate once (first run), then reuse. Warn loudly on a new key —
# it must be copied to a durable store or the backup is unrecoverable.
if [ ! -s "$KEYFILE" ]; then
  command -v openssl >/dev/null || fail "openssl not found (needed to mint the backup key)"
  umask 177; mkdir -p "$(dirname "$KEYFILE")"
  openssl rand -base64 48 > "$KEYFILE"; chmod 600 "$KEYFILE"
  echo "!! Generated a NEW backup key at $KEYFILE"
  echo "!! SAVE its contents to your password manager NOW — it is the ONLY key,"
  echo "!! and it is deliberately NOT stored on the backup media."
fi

TS="$(date -u +%Y%m%dT%H%M%SZ)"
DEST="$DEST_ROOT/$TS"
ARCHIVE="$DEST/maez_continuity_$TS.tar.zst.gpg"
mkdir -p "$DEST" || fail "cannot create $DEST"

# ── consistent snapshot: pause daemon, ALWAYS bring it back ───────────
restart_daemon() { systemctl --user start "$SERVICE" >/dev/null 2>&1 || true; }
trap restart_daemon EXIT
echo "Pausing $SERVICE for a consistent snapshot…"
systemctl --user stop "$SERVICE" >/dev/null 2>&1 || true
# Witness the stop — never trust that "asked to stop" means "stopped". A
# consistent snapshot REQUIRES the daemon quiescent (no process mutating the
# SQLite state mid-tar), so poll for 'inactive' and FAIL before archiving if it
# is still running. The EXIT trap restarts it on the way out. (systemctl stop is
# synchronous, but a failed/timed-out stop is swallowed above, so the gate — not
# the stop's exit code — is what actually proves quiescence.)
stopped=""; tries=0
while [ "$tries" -lt 15 ]; do
  st="$(systemctl --user is-active "$SERVICE" 2>/dev/null | head -1)"
  [ "$st" = "inactive" ] && { stopped=1; break; }
  tries=$((tries + 1)); sleep 1
done
[ -n "$stopped" ] || fail "daemon is still '$(systemctl --user is-active "$SERVICE" 2>/dev/null | head -1)' after stop — refusing to archive live, mutating state (the trap will restart it)."
note "daemon: inactive (stop witnessed)"

echo "Building encrypted archive → $ARCHIVE"
tar --exclude='maez/models' --exclude='maez/.venv' --exclude='maez/logs' \
    --exclude='maez/backups' --exclude='maez/training' --exclude='maez/data' \
    --exclude='maez/staging' --exclude='*.gguf' --exclude='*/__pycache__' \
    --exclude='*/node_modules' --exclude='maez/.git/lfs' \
    -C "$(dirname "$REPO")" -cf - "$(basename "$REPO")" \
  | zstd -15 -T0 -q \
  | gpg --batch --yes --pinentry-mode loopback --passphrase-file "$KEYFILE" \
        -c --cipher-algo AES256 -o "$ARCHIVE"
ec=("${PIPESTATUS[@]}")
[ "${ec[0]}" = 0 ] && [ "${ec[1]}" = 0 ] && [ "${ec[2]}" = 0 ] \
  || fail "archive pipeline failed (tar=${ec[0]} zstd=${ec[1]} gpg=${ec[2]})"

( cd "$DEST" && sha256sum "$(basename "$ARCHIVE")" > SHA256SUMS )

# snapshot done — bring the daemon back before the (longer) witness step
restart_daemon
trap - EXIT

# ── witness: decrypt + restore + verify it is real, not a pretty file ─
W="$(mktemp -d)"
trap 'rm -rf "$W"' EXIT
echo "Witnessing (decrypt → restore → verify)…"
( cd "$DEST" && sha256sum -c SHA256SUMS >/dev/null 2>&1 ) || fail "checksum mismatch on $ARCHIVE"
gpg --batch --quiet --pinentry-mode loopback --passphrase-file "$KEYFILE" -d "$ARCHIVE" 2>/dev/null \
  | zstd -d -q | tar -xf - -C "$W" || fail "decrypt/extract failed (bad key or corrupt archive)"
B="$W/$(basename "$REPO")"
git -C "$B" log --oneline -1 >/dev/null 2>&1 || fail "restored .git is invalid"
sqlite3 "$B/memory/identity_ledger.db" '.tables' >/dev/null 2>&1 || fail "restored identity_ledger.db unreadable"
for f in config/soul.md config/identity.yaml config/secrets.local.env config/.env memory/lived_episodes.db; do
  [ -s "$B/$f" ] || fail "restored archive missing $f"
done
for x in models .venv logs training data; do
  [ -e "$B/$x" ] && fail "exclude leaked into archive: $x"
done

echo "OK — continuity backup witnessed."
note "archive : $ARCHIVE ($(du -h "$ARCHIVE" | cut -f1), restores to $(du -sh "$B" | cut -f1))"
note "head    : $(git -C "$B" rev-parse --short HEAD) · memory + soul + secrets present · bulk excluded"
note "key     : $KEYFILE  (keep an independent copy — the backup is only as real as the key's survival)"
