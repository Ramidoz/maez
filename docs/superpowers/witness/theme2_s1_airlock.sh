#!/usr/bin/env bash
# Theme 2 S1 — T5 containment wrapper (protocol §12.2).
#
# Containment, not redirection. memory_manager.BASE_DB is a module-global
# absolute path to the live Chroma store with no environment override, so
# env redirection cannot airlock a run that touches the reply path. This
# wrapper makes the live tree read-only and binds airlock directories over
# exactly the writable targets: the live absolute path still resolves, the
# bytes land in the airlock, and any path the bind set did not anticipate
# fails EROFS -- loudly -- instead of writing to the live tree.
#
# Usage:  theme2_s1_airlock.sh <airlock_dir> <command> [args...]
#         theme2_s1_airlock.sh <airlock_dir> --self-test
#
# The airlock dir must be under /tmp. The wrapper refuses otherwise.
set -euo pipefail

MAEZ_TREE=/home/rohit/maez
HOST_HOME=/home/rohit

# --clearenv plus an explicit set is what makes "all MAEZ_* flags unset,
# full env recorded" true by construction rather than by inspection. The
# TZ pin matters: the manifest asks "what day is it today", so an
# unpinned zone could change stored text between runs. Default is the
# owner timezone resolved by core.time.temporal_spine.owner_timezone().
T5_TZ=${T5_TZ:-America/Chicago}

if [ $# -lt 2 ]; then
    echo "usage: $0 <airlock_dir> <command> [args...]" >&2
    exit 2
fi

AIRLOCK=$(readlink -f "$1"); shift
case "$AIRLOCK" in
    /tmp/*) ;;
    *) echo "REFUSED: airlock must be under /tmp, got: $AIRLOCK" >&2; exit 3 ;;
esac

mkdir -p \
    "$AIRLOCK/maez/memory" \
    "$AIRLOCK/maez/logs" \
    "$AIRLOCK/maez/.cache" \
    "$AIRLOCK/home/.config/maez" \
    "$AIRLOCK/home/.cache/chroma"

# The ONNX embedding model cache (ONNXMiniLM_L6_V2, per
# memory/embedding_contract.json) is a read-only asset the hermetic run
# cannot re-download. Seed it once; it is excluded from the store tree
# and from the archive.
if [ ! -e "$AIRLOCK/home/.cache/chroma/onnx_models" ] \
   && [ -d "$HOST_HOME/.cache/chroma/onnx_models" ]; then
    cp -a "$HOST_HOME/.cache/chroma/onnx_models" "$AIRLOCK/home/.cache/chroma/"
fi

BWRAP_ARGV=(
    bwrap
    --ro-bind / /
    --ro-bind "$MAEZ_TREE" "$MAEZ_TREE"
    --bind "$AIRLOCK/maez/memory"        "$MAEZ_TREE/memory"
    --bind "$AIRLOCK/maez/logs"          "$MAEZ_TREE/logs"
    --bind "$AIRLOCK/maez/.cache"        "$MAEZ_TREE/.cache"
    --bind "$AIRLOCK/home/.config/maez"  "$HOST_HOME/.config/maez"
    --bind "$AIRLOCK/home/.cache/chroma" "$HOST_HOME/.cache/chroma"
    --tmpfs /tmp
    --proc /proc
    --dev /dev
    --unshare-net
    --unshare-pid
    --die-with-parent
    --clearenv
    --setenv HOME "$HOST_HOME"
    --setenv PATH "$MAEZ_TREE/.venv/bin:/usr/local/bin:/usr/bin:/bin"
    --setenv VIRTUAL_ENV "$MAEZ_TREE/.venv"
    --setenv PYTHONDONTWRITEBYTECODE 1
    --setenv PYTHONHASHSEED 0
    --setenv LANG C.UTF-8
    --setenv LC_ALL C.UTF-8
    --setenv TZ "$T5_TZ"
    --chdir "$MAEZ_TREE"
)

if [ "${1:-}" = "--argv" ]; then
    printf '%s\n' "${BWRAP_ARGV[@]}"
    exit 0
fi

if [ "${1:-}" = "--self-test" ]; then
    # Protocol §12.2's containment self-test. Three assertions, recorded
    # verbatim. Any deviation kills the run before the manifest is touched.
    "${BWRAP_ARGV[@]}" /bin/sh -c '
        set -u
        printf "1 repo-write-must-fail: "
        if echo x > '"$MAEZ_TREE"'/CONTAINMENT_PROBE 2>/dev/null; then
            echo "FAIL (write succeeded)"; exit 1
        else
            echo "PASS (EROFS)"
        fi
        printf "2 memory-write-must-succeed: "
        if echo x > '"$MAEZ_TREE"'/memory/CONTAINMENT_PROBE 2>/dev/null; then
            echo "PASS"
        else
            echo "FAIL (write refused)"; exit 1
        fi
        printf "3 network-must-be-absent: "
        if [ "$(cat /proc/net/tcp | wc -l)" -le 1 ]; then
            echo "PASS (no tcp sockets in namespace)"
        else
            echo "FAIL (tcp table non-empty)"; exit 1
        fi
    '
    rc=$?
    echo "4 probe-visible-in-airlock-only:"
    if [ -f "$AIRLOCK/maez/memory/CONTAINMENT_PROBE" ]; then
        echo "   PASS (present at $AIRLOCK/maez/memory/CONTAINMENT_PROBE)"
    else
        echo "   FAIL (absent from airlock)"; exit 1
    fi
    echo "5 live-tree-unmarked:"
    if [ -e "$MAEZ_TREE/CONTAINMENT_PROBE" ] \
       || [ -e "$MAEZ_TREE/memory/CONTAINMENT_PROBE" ]; then
        echo "   FAIL (probe leaked into the live tree)"; exit 1
    else
        echo "   PASS (neither probe exists in the live tree)"
    fi
    rm -f "$AIRLOCK/maez/memory/CONTAINMENT_PROBE"
    exit $rc
fi

exec "${BWRAP_ARGV[@]}" "$@"
