#!/usr/bin/env bash
# Theme 2 S1 — T5 baseline orchestrator (protocol §12, closes gate round 14 J).
#
# One committed authority owns the whole sequence, because a report can
# record what a human did but cannot make a failed exit code bite:
#
#   preflight -> stop daemon -> (fresh airlock -> self-test -> replay ->
#   extract -> project) x2 -> derive volatile -> compare -> archive ONLY on
#   total success -> restart daemon, always
#
# Every step's exit status is consumed. The archive is produced only after
# every prior step succeeded. The daemon is restarted from an EXIT trap, so
# it comes back even when an intermediate step fails or the run is
# interrupted.
#
# Usage:
#   theme2_s1_t5_run.sh --work <dir> [--stop-daemon] [--no-archive]
#
# --stop-daemon is opt-in and explicit. Without it the run refuses if
# maez.service is active, rather than quietly racing the live daemon.
set -euo pipefail

REPO=/home/rohit/maez
W=""
STOP_DAEMON=0
ARCHIVE=1
UNIT=maez.service
ARCHIVE_PATH="$REPO/docs/superpowers/witness/theme2-s1-baseline.tar.zst"
MAX_ARCHIVE_BYTES=$((25 * 1024 * 1024))

while [ $# -gt 0 ]; do
    case "$1" in
        --work) W="$2"; shift 2 ;;
        --stop-daemon) STOP_DAEMON=1; shift ;;
        --no-archive) ARCHIVE=0; shift ;;
        *) echo "unknown argument: $1" >&2; exit 2 ;;
    esac
done
[ -n "$W" ] || { echo "usage: $0 --work <dir> [--stop-daemon]" >&2; exit 2; }
case "$W" in /tmp/*) ;; *) echo "REFUSED: --work must be under /tmp" >&2; exit 3 ;; esac

AIRLOCK="$REPO/docs/superpowers/witness/theme2_s1_airlock.sh"
REPLAY="$REPO/docs/superpowers/witness/theme2_s1_t5_replay.py"
EXTRACT="$REPO/docs/superpowers/witness/theme2_s1_t5_extract.py"
PROJECT="$REPO/docs/superpowers/witness/theme2_s1_t5_projection.py"
SELFTEST="$REPO/docs/superpowers/witness/theme2_s1_t5_projection_selftest.py"
MANIFEST="$REPO/docs/superpowers/witness/theme2-s1-replay.json"
PY="$REPO/.venv/bin/python"

mkdir -p "$W"
LOG="$W/orchestrator.log"
say() { printf '%s | %s\n' "$(date -Is)" "$*" | tee -a "$LOG"; }

DAEMON_WAS_ACTIVE=0
restore_daemon() {
    rc=$?
    if [ "$DAEMON_WAS_ACTIVE" = "1" ]; then
        say "restarting $UNIT (exit rc=$rc)"
        systemctl --user start "$UNIT" || say "WARNING: restart failed"
        sleep 2
        say "post-restart is-active: $(systemctl --user is-active "$UNIT" || true)"
    fi
    say "orchestrator exiting rc=$rc"
    exit $rc
}
trap restore_daemon EXIT

say "=== T5 baseline orchestrator ==="
say "repo HEAD: $(cd "$REPO" && git rev-parse HEAD)"
if [ -n "$(cd "$REPO" && git status --porcelain)" ]; then
    say "REFUSED: working tree is dirty; a baseline must be pinned to a commit"
    exit 4
fi
say "sqlite: $($PY -c 'import sqlite3;print(sqlite3.sqlite_version)')"

# The comparator is the instrument the verdict rests on. Verify it first.
say "--- projection self-test"
"$PY" "$SELFTEST" 2>&1 | tee -a "$LOG"

PRE_ACTIVE=$(systemctl --user is-active "$UNIT" || true)
say "pre-run $UNIT is-active: $PRE_ACTIVE"
if [ "$PRE_ACTIVE" = "active" ]; then
    if [ "$STOP_DAEMON" = "1" ]; then
        DAEMON_WAS_ACTIVE=1
        say "stopping $UNIT (owner-authorized)"
        systemctl --user stop "$UNIT"
        sleep 3
        say "post-stop is-active: $(systemctl --user is-active "$UNIT" || true)"
    else
        say "REFUSED: $UNIT is active and --stop-daemon was not given"
        exit 5
    fi
fi

one_run() {
    local tag="$1" A="$W/airlock-$tag"
    say "--- run $tag: airlock $A"
    rm -rf "$A"
    "$AIRLOCK" "$A" --self-test 2>&1 | tee "$W/selftest-$tag.txt" | tee -a "$LOG"
    T5_REUSE_AIRLOCK=1 "$AIRLOCK" "$A" "$PY" "$REPLAY" \
        --manifest "$MANIFEST" --report "$REPO/logs/t5_run.json" 2>&1 | tee -a "$LOG"
    T5_REUSE_AIRLOCK=1 "$AIRLOCK" "$A" "$PY" "$EXTRACT" \
        "$REPO/logs/t5_extract.json" 2>&1 | tee -a "$LOG"
    cp "$A/maez/logs/t5_run.json"     "$W/run-$tag.json"
    cp "$A/maez/logs/t5_extract.json" "$W/extract-$tag.json"
    "$PY" "$PROJECT" project "$A/maez/memory" "$W/proj-$tag.json" \
        --extract "$W/extract-$tag.json" 2>&1 | tee -a "$LOG"
}

one_run a
one_run b

say "--- derive the volatile field list from the two baseline runs"
"$PY" "$PROJECT" volatile "$W/proj-a.json" "$W/proj-b.json" \
    "$W/volatile.json" 2>&1 | tee -a "$LOG"

LEDGER_SHA=$("$PY" -c "
import json,sys
d=json.load(open('$W/run-a.json'))
print(d['ledger_post_migration_sha256'])")
say "ledger post-migration sha256: $LEDGER_SHA"

say "--- compare run a against run b under the projection"
"$PY" "$PROJECT" compare "$W/proj-a.json" "$W/proj-b.json" \
    "$W/volatile.json" --ledger-sha "$LEDGER_SHA" 2>&1 | tee "$W/compare.json"

if [ "$ARCHIVE" = "1" ]; then
    say "--- archive run a's store tree"
    SEEDED=$("$PY" -c "
import json
print('\n'.join(e['path'] for e in
      json.load(open('$W/proj-a.json'))['seeded_sources']))")
    EXCL="$W/archive-exclude.txt"
    printf '%s\n' "$SEEDED" > "$EXCL"
    tar --sort=name --numeric-owner --owner=0 --group=0 --mtime=@0 \
        --exclude-from="$EXCL" \
        -C "$W/airlock-a/maez/memory" -cf "$W/baseline.tar" .
    zstd -19 -q -f -o "$W/baseline.tar.zst" "$W/baseline.tar"
    SZ=$(stat -c %s "$W/baseline.tar.zst")
    say "archive bytes: $SZ  sha256: $(sha256sum "$W/baseline.tar.zst" | cut -d' ' -f1)"
    if [ "$SZ" -gt "$MAX_ARCHIVE_BYTES" ]; then
        say "REFUSED: archive exceeds 25 MB; owner rules on placement first"
        exit 6
    fi
    cp "$W/baseline.tar.zst" "$ARCHIVE_PATH"
    say "archive written: $ARCHIVE_PATH"
    say "ARCHIVE SHA256: $(sha256sum "$ARCHIVE_PATH" | cut -d' ' -f1)"
fi

say "=== T5 baseline orchestration complete ==="
