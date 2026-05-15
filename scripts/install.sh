#!/usr/bin/env bash
# Maez — from-source installer (Linux-only, alpha).
#
# Does the following, in order, stopping on the first failure:
#   1. Verify host prerequisites (Python 3.12+, git, systemd, ideally an NVIDIA GPU).
#   2. Create .venv and install core runtime deps via pip install -e .
#   3. Render systemd unit templates into ~/.config/systemd/user/
#      (or offer system-wide install under /etc/systemd/system).
#   4. Seed config/ from templates: .env from .env.example, identity.yaml
#      from identity.template.yaml, soul.local.md from soul.local.template.md.
#   5. Invoke the first-run wizard (scripts/first_run_wizard.py) which
#      interactively fills in owner display_name, git_handle, and the
#      optional telegram/API-key knobs.
#
# Re-running this script is safe: every step is idempotent and detects
# an existing install, skipping or updating rather than clobbering.
#
# Out of scope for alpha: macOS (needs launchd units), Windows (needs
# a full rewrite of the perception + shell-action layers).

set -euo pipefail

# ── config ────────────────────────────────────────────────────────────
MAEZ_HOME="$(cd "$(dirname "$(dirname "$(realpath "$0")")")" && pwd)"
MAEZ_USER="$(id -un)"
MAEZ_UID="$(id -u)"
VENV_DIR="$MAEZ_HOME/.venv"
PYTHON_MIN="3.12"

# ── helpers ───────────────────────────────────────────────────────────
color_red()    { printf '\033[31m%s\033[0m' "$1"; }
color_green()  { printf '\033[32m%s\033[0m' "$1"; }
color_yellow() { printf '\033[33m%s\033[0m' "$1"; }
color_bold()   { printf '\033[1m%s\033[0m' "$1"; }

section() {
    echo
    color_bold "── $1 ─────────────────────────────────────────"
    echo
}

ok()   { echo "  $(color_green "[ok]") $1"; }
warn() { echo "  $(color_yellow "[warn]") $1"; }
fail() { echo "  $(color_red "[fail]") $1"; exit 1; }
info() { echo "  [..] $1"; }


# ── 1. host prereqs ───────────────────────────────────────────────────
section "1. Host prerequisites"

# Python 3.12+
if ! command -v python3 >/dev/null 2>&1; then
    fail "python3 not on PATH. Install Python $PYTHON_MIN+ first."
fi
PY_VER="$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
if [ "$(printf '%s\n' "$PYTHON_MIN" "$PY_VER" | sort -V | head -n1)" != "$PYTHON_MIN" ]; then
    fail "Python $PY_VER found; need >= $PYTHON_MIN."
fi
ok "Python $PY_VER"

# git
if ! command -v git >/dev/null 2>&1; then
    fail "git not on PATH."
fi
ok "git $(git --version | awk '{print $3}')"

# systemd (optional but strongly recommended)
if command -v systemctl >/dev/null 2>&1; then
    ok "systemd present"
else
    warn "systemd not found — daemon autostart will require manual supervisor setup."
fi

# GPU (optional but strongly recommended)
if command -v nvidia-smi >/dev/null 2>&1; then
    GPU_NAME="$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -n1 || true)"
    ok "GPU: ${GPU_NAME:-detected}"
else
    warn "No NVIDIA GPU detected — local inference will fall back to CPU (slow)."
fi


# ── 2. venv + deps ────────────────────────────────────────────────────
section "2. Python environment"

if [ ! -d "$VENV_DIR" ]; then
    info "Creating venv at $VENV_DIR"
    python3 -m venv "$VENV_DIR"
    ok "venv created"
else
    ok "venv exists at $VENV_DIR"
fi

# shellcheck disable=SC1091
. "$VENV_DIR/bin/activate"

info "Upgrading pip"
pip install --quiet --upgrade pip

info "Installing core runtime dependencies (pip install -e .)"
pip install --quiet -e "$MAEZ_HOME"
ok "core deps installed ($(pip list --format=freeze | wc -l) packages)"

# Optional extras
echo
read -r -p "Install optional extras? [vision, telegram, google, dev, all, none] (default: none): " EXTRAS
case "${EXTRAS:-none}" in
    none|"")
        ok "skipping optional extras"
        ;;
    vision|telegram|google|dev|all)
        info "Installing $EXTRAS extras"
        pip install --quiet -e "$MAEZ_HOME[$EXTRAS]"
        ok "$EXTRAS extras installed"
        ;;
    *)
        warn "Unknown extras spec '$EXTRAS' — skipping. Install manually with: pip install -e .[name]"
        ;;
esac


# ── 3. config seed ────────────────────────────────────────────────────
section "3. Config seed"

seed_from_template() {
    local template="$1"
    local target="$2"
    if [ -f "$target" ]; then
        ok "$target already exists (kept as-is)"
    elif [ -f "$template" ]; then
        cp "$template" "$target"
        ok "seeded $target from $(basename "$template")"
    else
        warn "$template missing; skipped"
    fi
}

seed_from_template "$MAEZ_HOME/.env.example"                        "$MAEZ_HOME/config/.env"
seed_from_template "$MAEZ_HOME/config/identity.template.yaml"       "$MAEZ_HOME/config/identity.yaml"
seed_from_template "$MAEZ_HOME/config/soul.local.template.md"       "$MAEZ_HOME/config/soul.local.md"

# config/.env holds ordinary config only. Identity-bearing credentials belong
# in config/secrets.local.env or systemd credentials per Decision 26.
chmod 600 "$MAEZ_HOME/config/.env" 2>/dev/null || true


# ── 4. first-run wizard ───────────────────────────────────────────────
section "4. First-run wizard"

if [ -x "$MAEZ_HOME/scripts/first_run_wizard.py" ] || [ -f "$MAEZ_HOME/scripts/first_run_wizard.py" ]; then
    info "Launching identity wizard"
    "$VENV_DIR/bin/python3" "$MAEZ_HOME/scripts/first_run_wizard.py" || {
        warn "wizard exited non-zero — you can re-run it later with:"
        echo "       $VENV_DIR/bin/python3 $MAEZ_HOME/scripts/first_run_wizard.py"
    }
else
    warn "first_run_wizard.py missing; edit config/identity.yaml by hand."
fi


# ── 5. systemd units ──────────────────────────────────────────────────
section "5. Systemd units"

if ! command -v systemctl >/dev/null 2>&1; then
    warn "systemctl not found — skipping unit rendering."
else
    echo "  Where should systemd units land?"
    echo "    [1] Per-user units in ~/.config/systemd/user/ (recommended; no sudo needed)"
    echo "    [2] System-wide units in /etc/systemd/system/  (requires sudo)"
    echo "    [3] Skip (render templates into scripts/rendered/ for manual install)"
    read -r -p "Choice [1]: " SYSTEMD_CHOICE
    SYSTEMD_CHOICE="${SYSTEMD_CHOICE:-1}"

    RENDER_DIR=""
    case "$SYSTEMD_CHOICE" in
        1)
            RENDER_DIR="$HOME/.config/systemd/user"
            mkdir -p "$RENDER_DIR"
            ;;
        2)
            RENDER_DIR="/etc/systemd/system"
            ;;
        3)
            RENDER_DIR="$MAEZ_HOME/scripts/rendered"
            mkdir -p "$RENDER_DIR"
            ;;
        *)
            warn "Unknown choice '$SYSTEMD_CHOICE' — defaulting to user units."
            RENDER_DIR="$HOME/.config/systemd/user"
            mkdir -p "$RENDER_DIR"
            ;;
    esac

    render_unit() {
        local template="$1"
        local out_name
        out_name="$(basename "$template" .template.service).service"
        if [ "$template" = *.template.timer ]; then
            out_name="$(basename "$template" .template.timer).timer"
        fi
        local out_path="$RENDER_DIR/$out_name"

        # Substitute placeholders. Using | delimiter avoids the / in paths.
        local rendered
        rendered="$(sed \
            -e "s|__MAEZ_HOME__|$MAEZ_HOME|g" \
            -e "s|__MAEZ_USER__|$MAEZ_USER|g" \
            -e "s|__MAEZ_UID__|$MAEZ_UID|g" \
            "$template")"

        if [ "$SYSTEMD_CHOICE" = "2" ]; then
            echo "$rendered" | sudo tee "$out_path" >/dev/null
        else
            echo "$rendered" > "$out_path"
        fi
        ok "rendered $out_name"
    }

    for tpl in "$MAEZ_HOME"/scripts/*.template.service; do
        [ -f "$tpl" ] && render_unit "$tpl"
    done

    # Non-templated units (timer is already portable)
    [ -f "$MAEZ_HOME/scripts/maez-self-dev-scheduled.timer" ] && \
        cp "$MAEZ_HOME/scripts/maez-self-dev-scheduled.timer" "$RENDER_DIR/" 2>/dev/null || true
    # Lived-memory reflection — service + timer (not templated; paths
    # are absolute. Owners on a non-default MAEZ_HOME will need to
    # adjust by hand.)
    [ -f "$MAEZ_HOME/scripts/maez-lived-memory-reflection.service" ] && \
        cp "$MAEZ_HOME/scripts/maez-lived-memory-reflection.service" "$RENDER_DIR/" 2>/dev/null || true
    [ -f "$MAEZ_HOME/scripts/maez-lived-memory-reflection.timer" ] && \
        cp "$MAEZ_HOME/scripts/maez-lived-memory-reflection.timer" "$RENDER_DIR/" 2>/dev/null || true

    if [ "$SYSTEMD_CHOICE" = "1" ]; then
        systemctl --user daemon-reload
        echo
        echo "  To start the daemon now:"
        echo "    systemctl --user enable --now maez.service maez-subscription-proxy.service"
    elif [ "$SYSTEMD_CHOICE" = "2" ]; then
        sudo systemctl daemon-reload
        echo
        echo "  To start the daemon now:"
        echo "    sudo systemctl enable --now maez.service maez-subscription-proxy.service"
    else
        echo
        echo "  Rendered units are in: $RENDER_DIR"
        echo "  Review them and copy to your preferred systemd path."
    fi
fi


# ── 6. done ───────────────────────────────────────────────────────────
section "Done"
cat <<EOF
  Maez is installed at: $MAEZ_HOME
  Virtualenv: $VENV_DIR
  Config: $MAEZ_HOME/config/ (.env, identity.yaml, soul.local.md)

  Next steps:
    1. Edit $MAEZ_HOME/config/.env for ordinary config.
       Put API keys/tokens in $MAEZ_HOME/config/secrets.local.env (0600).
    2. Review $MAEZ_HOME/config/identity.yaml and adjust as needed.
    3. Start the daemon (see commands above).
    4. Tail logs: tail -f $MAEZ_HOME/logs/maez.log

  Docs: $MAEZ_HOME/docs/ARCHITECTURE.md
  Self-dev CLI: $VENV_DIR/bin/python -m core.self_dev --help

  Welcome. This Maez is yours alone; no two Maez instances
  should ever share one developmental history.
EOF
