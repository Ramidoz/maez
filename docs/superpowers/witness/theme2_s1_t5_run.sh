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
BASELINE_CENSUS=""
FORCED_ON=""
ARCHIVE_PATH="$REPO/docs/superpowers/witness/theme2-s1-baseline.tar.zst"
MAX_ARCHIVE_BYTES=$((25 * 1024 * 1024))

while [ $# -gt 0 ]; do
    case "$1" in
        --work) W="$2"; shift 2 ;;
        --baseline-census) BASELINE_CENSUS="$2"; shift 2 ;;
        --forced-on) FORCED_ON="$2"; shift 2 ;;
        --stop-daemon) STOP_DAEMON=1; shift ;;
        --no-archive) ARCHIVE=0; shift ;;
        *) echo "unknown argument: $1" >&2; exit 2 ;;
    esac
done
[ -n "$W" ] || { echo "usage: $0 --work <dir> [--stop-daemon]" >&2; exit 2; }
case "$W" in /tmp/*) ;; *) echo "REFUSED: --work must be under /tmp" >&2; exit 3 ;; esac

# Gate round 15 item J: --work took only a lexical /tmp check and mkdir -p, so
# a pre-existing hardlink or symlink could alias proj-a.json to proj-b.json --
# run B would overwrite A's evidence, the comparison would read B twice, and
# the archive would still come from physical airlock A. Claim the workdir
# atomically, refuse anything that already exists, and hold a run-wide lock.
WPARENT=$(dirname "$W")
if [ ! -d "$WPARENT" ] || [ "$(readlink -f "$WPARENT")" != "$WPARENT" ] \
   || [ "$(stat -c %u "$WPARENT")" != "$(id -u)" ]; then
    echo "REFUSED: --work parent must be an owned, non-symlinked directory" >&2
    exit 3
fi
if ! mkdir "$W" 2>/dev/null; then
    echo "REFUSED: --work already exists; it must be created by this run" >&2
    exit 3
fi
exec 8>"$W/.t5-run-lock"
if ! flock -n 8; then echo "REFUSED: another run holds this workdir" >&2; exit 3; fi
# One run id, presented by every airlock invocation so reuse proves identity
# rather than merely finding a marker.
export T5_RUN_ID="t5-$$-$(date +%s)"

AIRLOCK="$REPO/docs/superpowers/witness/theme2_s1_airlock.sh"
REPLAY="$REPO/docs/superpowers/witness/theme2_s1_t5_replay.py"
EXTRACT="$REPO/docs/superpowers/witness/theme2_s1_t5_extract.py"
PROJECT="$REPO/docs/superpowers/witness/theme2_s1_t5_projection.py"
SELFTEST="$REPO/docs/superpowers/witness/theme2_s1_t5_projection_selftest.py"
GATE="$REPO/docs/superpowers/witness/theme2_s1_t5_gate.py"
MANIFEST="$REPO/docs/superpowers/witness/theme2-s1-replay.json"
PY="$REPO/.venv/bin/python"

LOG="$W/orchestrator.log"
say() { printf '%s | %s\n' "$(date -Is)" "$*" | tee -a "$LOG"; }

DAEMON_WAS_ACTIVE=0
DAEMON_RESTORED=0

# Returns 0 only when the unit is genuinely active again.
restore_daemon_now() {
    [ "$DAEMON_WAS_ACTIVE" = "1" ] || { DAEMON_RESTORED=1; return 0; }
    say "restarting $UNIT"
    systemctl --user start "$UNIT" || true
    for _ in 1 2 3 4 5 6 7 8 9 10; do
        if [ "$(systemctl --user is-active "$UNIT" || true)" = "active" ]; then
            DAEMON_RESTORED=1
            say "post-restart is-active: active"
            return 0
        fi
        sleep 1
    done
    say "ERROR: $UNIT did not return to active"
    return 1
}

on_exit() {
    rc=$?
    if [ "$DAEMON_RESTORED" != "1" ]; then
        # Reached on failure and on SIGINT. Restoration failing here is an
        # error, not a warning (gate round 15 item J).
        restore_daemon_now || rc=7
    fi
    say "orchestrator exiting rc=$rc"
    exit $rc
}
trap on_exit EXIT

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
    local tag="$1" fixture="${2:-healthy}" A="$W/airlock-$tag"
    say "--- run $tag: airlock $A"
    rm -rf "$A"
    "$AIRLOCK" "$A" --self-test 2>&1 | tee "$W/selftest-$tag.txt" | tee -a "$LOG"
    T5_REUSE_AIRLOCK=1 T5_RUN_ID="$T5_RUN_ID" "$AIRLOCK" "$A" "$PY" "$REPLAY" \
        --manifest "$MANIFEST" --fixture "$fixture" \
        --report "$REPO/logs/t5_run.json" 2>&1 | tee -a "$LOG"
    T5_REUSE_AIRLOCK=1 T5_RUN_ID="$T5_RUN_ID" "$AIRLOCK" "$A" "$PY" "$EXTRACT" \
        "$REPO/logs/t5_extract.json" 2>&1 | tee -a "$LOG"
    cp "$A/maez/logs/t5_run.json"     "$W/run-$tag.json"
    cp "$A/maez/logs/t5_extract.json" "$W/extract-$tag.json"
    "$PY" "$PROJECT" project "$A/maez/memory" "$W/proj-$tag.json" \
        --extract "$W/extract-$tag.json" 2>&1 | tee -a "$LOG"
}

one_run a healthy
one_run b healthy

# Gate round 16 finding L: the healthy fixture is where legacy and S1 AGREE,
# so a pair of healthy runs cannot prove the guard is dormant -- only that two
# runs match. The partial fixture is where they must DIVERGE. This third run
# pins the legacy stamps on it; after S1 lands, flags-off must reproduce them
# exactly, and a forced-on S1 must NOT.
one_run p partial

say "--- discriminator: legacy behavior on the partial fixture"
"$PY" - "$W/run-p.json" <<'PYEOF' 2>&1 | tee "$W/discriminator.txt" | tee -a "$LOG"
import json, sys
d = json.load(open(sys.argv[1]))
probe = d.get("phase_probe", {})
census = d.get("stamp_census", {})
print("fixture:", d.get("fixture"))
print("resolver current_phase:", probe.get("current_phase"))
print("resolver has resolve() API:", probe.get("has_resolve_api"))
print("resolve():", probe.get("resolve"))
print("stamp census:", json.dumps(census, sort_keys=True))
# Pre-S1: the legacy resolver answers `gestation` for a structurally
# incomplete ledger -- that is the defect S1 exists to fix, and it is the
# behavior flags-off must preserve. Once S1 exists, this same assertion is
# what proves the guard stayed dormant.
if probe.get("current_phase") != "gestation":
    print("REFUSED: partial fixture did not read gestation; the "
          "discriminator's baseline is not what the protocol assumes")
    sys.exit(1)
stamped = [v for k, v in census.items() if isinstance(v, dict) for v in [v]]
if not any("gestation" in v for v in stamped):
    print("REFUSED: no gestation stamp landed on the partial fixture; "
          "the discriminator would compare nothing")
    sys.exit(1)
print("discriminator baseline OK")
PYEOF

say "--- derive the volatile field list from the two baseline runs"
"$PY" "$PROJECT" volatile "$W/proj-a.json" "$W/proj-b.json" \
    "$W/volatile.json" 2>&1 | tee -a "$LOG"

LEDGER_SHA=$("$PY" -c "
import json,sys
d=json.load(open('$W/run-a.json'))
print(d['ledger_post_migration_sha256'])")
say "ledger post-migration sha256: $LEDGER_SHA"

# FORENSIC, not gating (gate round 17 item N): the byte projection is
# recorded because it is useful evidence, but a physical-layout difference
# must not block a baseline. Its verdict is captured; `|| true` is deliberate.
say "--- forensic: byte projection, run a vs run b (recorded, not gating)"
set +e
"$PY" "$PROJECT" compare "$W/proj-a.json" "$W/proj-b.json" \
    "$W/volatile.json" --ledger-sha "$LEDGER_SHA" > "$W/compare.json" 2>&1
PROJ_RC=$?
set -e
say "forensic projection verdict rc=$PROJ_RC (recorded in compare.json)"

# THE GATE. This is the only authority. G1-G7, fail-closed.
say "--- gate: G1..G7"
"$PY" "$GATE" \
    --run-a "$W/run-a.json" --run-b "$W/run-b.json" --run-p "$W/run-p.json" \
    --proj-a "$W/proj-a.json" --proj-b "$W/proj-b.json" \
    ${BASELINE_CENSUS:+--baseline-census "$BASELINE_CENSUS"} \
    ${FORCED_ON:+--forced-on "$FORCED_ON"} \
    --out "$W/gate-verdict.json" 2>&1 | tee -a "$LOG"

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
    # Gate round 16 item J: hashing inside a command substitution passed to
    # `say` hid its failure -- `say` succeeded, set -e saw nothing, and
    # publication went ahead with an empty digest. Hash as its own checked
    # command.
    ARCHIVE_SHA=$(sha256sum "$W/baseline.tar.zst" | cut -d\  -f1)
    [ -n "$ARCHIVE_SHA" ] || { say "REFUSED: archive hashing failed"; exit 8; }
    say "archive bytes: $SZ  sha256: $ARCHIVE_SHA"
    if [ "$SZ" -gt "$MAX_ARCHIVE_BYTES" ]; then
        say "REFUSED: archive exceeds 25 MB; owner rules on placement first"
        exit 6
    fi
    # Gate round 15 item J: publication used to precede restoration, and a
    # failed restart was only a warning -- so a baseline could be published
    # into the repo while Maez stayed down. Restore first, verify, and make
    # publication contingent on it.
    restore_daemon_now
    # Publish through a temporary destination and rename, so a SIGINT during
    # the copy cannot leave a partial archive at the committed path.
    cp "$W/baseline.tar.zst" "$ARCHIVE_PATH.tmp"
    PUBLISHED_SHA=$(sha256sum "$ARCHIVE_PATH.tmp" | cut -d\  -f1)
    if [ "$PUBLISHED_SHA" != "$ARCHIVE_SHA" ]; then
        rm -f "$ARCHIVE_PATH.tmp"
        say "REFUSED: published copy digest differs from the built archive"
        exit 8
    fi
    mv -f "$ARCHIVE_PATH.tmp" "$ARCHIVE_PATH"
    # The pinned stamp census is the durable comparison basis (gate round 17,
    # M(iv)): without it, a later flags-off run has nothing exact to match and
    # G3 degenerates to "some gestation stamp exists".
    CENSUS_PATH="$REPO/docs/superpowers/witness/theme2-s1-baseline-census.json"
    "$PY" -c "
import json,sys
v=json.load(open('$W/gate-verdict.json'))
json.dump(v['pinned_census'], open('$CENSUS_PATH.tmp','w'), indent=1, sort_keys=True)
" && mv -f "$CENSUS_PATH.tmp" "$CENSUS_PATH"
    say "pinned census published: $CENSUS_PATH"
    say "CENSUS SHA256: $(sha256sum "$CENSUS_PATH" | cut -d\  -f1)"
    say "archive published: $ARCHIVE_PATH"
    say "ARCHIVE SHA256: $ARCHIVE_SHA"
else
    restore_daemon_now
fi

say "=== T5 baseline orchestration complete ==="
