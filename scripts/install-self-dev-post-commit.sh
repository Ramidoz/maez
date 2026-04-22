#!/bin/bash
# install-self-dev-post-commit.sh
# Install (or re-install) the Maez self-dev post-commit git hook.
#
# The hook is thin: it resolves HEAD's SHA and backgrounds a
# disowned `python -m core.self_dev_hooks run <sha>` invocation so
# the commit never blocks on a Claude call. The orchestrator decides
# whether to actually review based on policy (budget, diff size).
#
# Safe to re-run: overwrites the existing .git/hooks/post-commit.
# To DISABLE: just `rm /home/rohit/maez/.git/hooks/post-commit`.

set -euo pipefail

REPO_ROOT="/home/rohit/maez"
HOOK_PATH="${REPO_ROOT}/.git/hooks/post-commit"
PYTHON_BIN="${REPO_ROOT}/.venv/bin/python3"

if [ ! -d "${REPO_ROOT}/.git" ]; then
    echo "error: ${REPO_ROOT}/.git not found" >&2
    exit 1
fi
if [ ! -x "${PYTHON_BIN}" ]; then
    echo "error: venv python missing at ${PYTHON_BIN}" >&2
    exit 1
fi

# Generate the hook body via the module itself — single source of
# truth for the script contents.
"${PYTHON_BIN}" -m core.self_dev_hooks render-hook > "${HOOK_PATH}"
chmod +x "${HOOK_PATH}"

echo "installed: ${HOOK_PATH}"
echo ""
echo "to verify:"
echo "  cat ${HOOK_PATH}"
echo ""
echo "to disable temporarily:"
echo "  chmod -x ${HOOK_PATH}"
echo ""
echo "to uninstall:"
echo "  rm ${HOOK_PATH}"
