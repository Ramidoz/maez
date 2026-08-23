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
DISCRIMINATOR=0
ARCHIVE_PATH="$REPO/docs/superpowers/witness/theme2-s1-baseline.tar.zst"
MAX_ARCHIVE_BYTES=$((25 * 1024 * 1024))

while [ $# -gt 0 ]; do
    case "$1" in
        --work) W="$2"; shift 2 ;;
        --baseline-census) BASELINE_CENSUS="$2"; shift 2 ;;
        --forced-on) FORCED_ON="$2"; shift 2 ;;
        --discriminator) DISCRIMINATOR=1; ARCHIVE=0; shift ;;
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
if [ ! -d "$WPARENT" ] || [ "$(readlink -f "$WPARENT")" != "$WPARENT" ]; then
    echo "REFUSED: --work parent must be an existing, non-symlinked directory" >&2
    exit 3
fi
# The property that matters is that nobody else can rename or delete our
# directory out from under us. Ownership gives that; so does the sticky bit
# on a world-writable directory, which is exactly what /tmp is. Requiring
# ownership alone refused a plain /tmp workdir.
WP_MODE=$(stat -c %a "$WPARENT")
if [ "$(stat -c %u "$WPARENT")" != "$(id -u)" ] \
   && [ "${WP_MODE%???}" != "1" ]; then
    echo "REFUSED: --work parent is neither owned by this user nor sticky" >&2
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
GATE_SELFTEST="$REPO/docs/superpowers/witness/theme2_s1_t5_gate_selftest.py"
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
    # Six stop/start cycles across repeated attempts tripped systemd's
    # start-rate limiter, and the unit entered `failed (start-limit-hit)` --
    # so restoration failed for a reason that had nothing to do with Maez,
    # and left it down. Clear the counter before every start attempt.
    systemctl --user reset-failed "$UNIT" 2>/dev/null || true
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
# EXIT alone does not fire on a signal, and this script stops the owner's
# daemon. Trap the signals too, so an interrupted run still brings Maez back.
trap on_exit EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
trap 'exit 131' HUP

say "=== T5 baseline orchestrator ==="
say "repo HEAD: $(cd "$REPO" && git rev-parse HEAD)"
if [ -n "$(cd "$REPO" && git status --porcelain)" ]; then
    say "REFUSED: working tree is dirty; a baseline must be pinned to a commit"
    exit 4
fi
say "sqlite: $($PY -c 'import sqlite3;print(sqlite3.sqlite_version)')"

# The comparator is the instrument the verdict rests on. Verify it first.
say "--- gate self-test (the sole authority; case count = grep -c)"
"$PY" "$GATE_SELFTEST" 2>&1 | tee -a "$LOG"

# FORENSIC instrument: its self-test is recorded, not gating (round 19 Q3).
say "--- projection self-test (forensic instrument, recorded not gating)"
set +e
"$PY" "$SELFTEST" > "$W/projection-selftest.txt" 2>&1
say "projection self-test rc=$? (see projection-selftest.txt)"
set -e

# Protocol §6 requires the frozen selector suite green, and gate round 18
# found it required but absent from the orchestrator.
# §6 requires the frozen selector suite green, INSIDE the airlock -- round 19
# found it running directly on the host, which is exactly scar rule 1.
say "--- frozen pytest selector suite (§6), inside the airlock"
SELECTORS=$(grep -v "^#" "$REPO/docs/superpowers/witness/theme2-s1-selectors.txt" \
            | grep -v "^$" | tr "\n" " ")
say "selectors: $SELECTORS"
PYTEST_AIRLOCK="$W/airlock-pytest"
rm -rf "$PYTEST_AIRLOCK"
# shellcheck disable=SC2086
"$AIRLOCK" "$PYTEST_AIRLOCK" "$PY" -m pytest -q $SELECTORS 2>&1 \
    | tail -25 | tee -a "$LOG"

# Round 19 Q6.7: `is-active || true` turned an unavailable user bus into
# "not active" and proceeded. Probe the bus first and refuse if it cannot
# answer.
if ! systemctl --user show-environment >/dev/null 2>&1; then
    say "REFUSED: the user systemd bus is unavailable; daemon state cannot "
    say "         be established, and a baseline must not race a daemon "
    say "         whose state is unknown"
    exit 9
fi
PRE_ACTIVE=$(systemctl --user is-active "$UNIT" || true)
say "pre-run $UNIT is-active: $PRE_ACTIVE"
if [ "$PRE_ACTIVE" = "active" ]; then
    if [ "$STOP_DAEMON" = "1" ]; then
        DAEMON_WAS_ACTIVE=1
        say "stopping $UNIT (owner-authorized)"
        systemctl --user stop "$UNIT"
        sleep 3
        POST_STOP=$(systemctl --user is-active "$UNIT" || true)
        say "post-stop is-active: $POST_STOP"
        if [ "$POST_STOP" = "active" ]; then
            say "REFUSED: $UNIT is still active after stop"
            exit 9
        fi
    else
        say "REFUSED: $UNIT is active and --stop-daemon was not given"
        exit 5
    fi
fi

one_run() {
    # Separate statements on purpose: bash 5.3 expands every word of a
    # `local` before assigning any of them, so `A="$W/airlock-$tag"` in the
    # same statement dies under `set -u` with "tag: unbound variable".
    local tag="$1"
    local fixture="${2:-healthy}"
    local extra="${3:-}"
    local A="$W/airlock-$tag"
    say "--- run $tag: airlock $A"
    rm -rf "$A"
    "$AIRLOCK" "$A" --self-test 2>&1 | tee "$W/selftest-$tag.txt" | tee -a "$LOG"
    T5_REUSE_AIRLOCK=1 T5_RUN_ID="$T5_RUN_ID" "$AIRLOCK" "$A" "$PY" "$REPLAY" \
        --manifest "$MANIFEST" --fixture "$fixture" $extra \
        --report "$REPO/logs/t5_run.json" 2>&1 | tee -a "$LOG"
    cp "$A/maez/logs/t5_run.json" "$W/run-$tag.json"
    # Everything below is FORENSIC: the extract and the byte projection are
    # evidence, and round 19 found they could still terminate the run under
    # set -e. Their statuses are captured (round 19 Q3).
    set +e
    T5_REUSE_AIRLOCK=1 T5_RUN_ID="$T5_RUN_ID" "$AIRLOCK" "$A" "$PY" "$EXTRACT" \
        "$REPO/logs/t5_extract.json" > "$W/extract-$tag.log" 2>&1
    say "forensic extract ($tag) rc=$?"
    cp "$A/maez/logs/t5_extract.json" "$W/extract-$tag.json" 2>/dev/null
    if [ -f "$W/extract-$tag.json" ]; then
        "$PY" "$PROJECT" project "$A/maez/memory" "$W/proj-$tag.json" \
            --extract "$W/extract-$tag.json" > "$W/project-$tag.log" 2>&1
    else
        "$PY" "$PROJECT" project "$A/maez/memory" "$W/proj-$tag.json" \
            > "$W/project-$tag.log" 2>&1
    fi
    say "forensic projection ($tag) rc=$?"
    set -e
}

if [ "$DISCRIMINATOR" = "1" ]; then
    # Gate round 20 F-list, executed as one mode: flags-off runs against
    # both fixtures (compared to the committed pinned baseline), then the
    # forced-on partial run whose refusals are the dormancy proof. No
    # archive is produced -- the pre-S1 artifacts are frozen and this run
    # exists to be measured against them, not to replace them.
    BASELINE_CENSUS="$REPO/docs/superpowers/witness/theme2-s1-baseline-census.json"
    [ -f "$BASELINE_CENSUS" ] || { say "REFUSED: pinned baseline census missing"; exit 4; }
fi

one_run a healthy
# Run b is FORENSIC ONLY -- the gate consumes a and p. It is kept because
# run-to-run repeatability is useful context for the archive, but round 19
# was right that it must not be able to abort the run (Q3).
set +e
one_run b healthy
say "forensic second healthy run rc=$?"
set -e

# Gate round 16 finding L: the healthy fixture is where legacy and S1 AGREE,
# so a pair of healthy runs cannot prove the guard is dormant -- only that two
# runs match. The partial fixture is where they must DIVERGE. This third run
# pins the legacy stamps on it; after S1 lands, flags-off must reproduce them
# exactly, and a forced-on S1 must NOT.
one_run p partial

if [ "$DISCRIMINATOR" = "1" ]; then
    say "--- FORCED-ON run: partial fixture, MAEZ_S1_PHASE_TRUTH=1 inside"
    one_run f partial "--forced-on"
    FORCED_ON="$W/run-f.json"
    say "forced-on producer verdict: $("$PY" -c "
import json; print(json.load(open('$W/run-f.json'))['positive_control']['verdict'])")"
fi

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

# FORENSIC (gate round 18 finding P): the volatile derivation exits non-zero
# on a finding, and under set -e that still gated the run through a demoted
# instrument. Its status is captured, not propagated.
say "--- forensic: volatile field derivation (recorded, not gating)"
set +e
"$PY" "$PROJECT" volatile "$W/proj-a.json" "$W/proj-b.json" \
    "$W/volatile.json" > "$W/volatile-derivation.txt" 2>&1
VOL_RC=$?
set -e
say "forensic volatile derivation rc=$VOL_RC"
[ -f "$W/volatile.json" ] || echo '{"volatile":{},"findings":[]}' > "$W/volatile.json"

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
    --run-a "$W/run-a.json" --run-p "$W/run-p.json" \
    ${BASELINE_CENSUS:+--baseline-census "$BASELINE_CENSUS"} \
    ${FORCED_ON:+--forced-on "$FORCED_ON"} \
    --out "$W/gate-verdict.json" 2>&1 | tee -a "$LOG"

if [ "$ARCHIVE" = "1" ]; then
    say "--- archive run a's store tree"
    # Round 19 Q3: archive construction depended on proj-a.json, a forensic
    # artifact. It now reads the seed manifest the wrapper wrote.
    SEEDED=$("$PY" -c "
import sys
print('\n'.join(l.split(None,1)[1].strip().split('/maez/memory/',1)[-1]
      for l in open('$W/airlock-a/maez/logs/seeded-sources.txt')
      if l.strip()))")
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
    # Round 19 Q3: the archive was renamed first and the census only
    # afterward, so an interrupt left a new archive beside an old census.
    # Both temporaries are written and verified first; the census -- the
    # smaller, gate-derived file -- is renamed last, so a half-landed pair
    # is always "archive present, census absent", which the next run
    # detects rather than trusting.
    mv -f "$ARCHIVE_PATH.tmp" "$ARCHIVE_PATH"
    # The pinned stamp census is the durable comparison basis (gate round 17,
    # M(iv)): without it, a later flags-off run has nothing exact to match and
    # G3 degenerates to "some gestation stamp exists".
    # Gate round 18: census generation was the left side of `&&`, where bash
    # suppresses errexit -- a failed write left the new archive beside an old
    # or absent census and the run still claimed publication. It is now its
    # own checked statement, and it carries the archive digest so the pair
    # cannot drift apart.
    CENSUS_PATH="$REPO/docs/superpowers/witness/theme2-s1-baseline-census.json"
    "$PY" -c "
import json
v = json.load(open('$W/gate-verdict.json'))
out = dict(v['pinned_census'])
out['bound_archive_sha256'] = '$ARCHIVE_SHA'
json.dump(out, open('$CENSUS_PATH.tmp', 'w'), indent=1, sort_keys=True)
"
    CENSUS_SHA=$(sha256sum "$CENSUS_PATH.tmp" | cut -d\  -f1)
    [ -n "$CENSUS_SHA" ] || { say "REFUSED: census hashing failed"; exit 8; }
    mv -f "$CENSUS_PATH.tmp" "$CENSUS_PATH"
    say "pinned census published: $CENSUS_PATH"
    say "CENSUS SHA256: $CENSUS_SHA (bound to archive $ARCHIVE_SHA)"
    say "archive published: $ARCHIVE_PATH"
    say "ARCHIVE SHA256: $ARCHIVE_SHA"
else
    restore_daemon_now
fi

say "=== T5 baseline orchestration complete ==="
