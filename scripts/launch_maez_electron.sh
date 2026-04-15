#!/usr/bin/env bash
set -euo pipefail

export HOME=/home/rohit
export XDG_RUNTIME_DIR=/run/user/1000

pick_xauthority() {
  local candidate

  for candidate in "$XDG_RUNTIME_DIR"/.mutter-Xwaylandauth.* "$XDG_RUNTIME_DIR"/gdm/Xauthority; do
    if [[ -f "$candidate" ]]; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done

  return 1
}

if [[ -S "$XDG_RUNTIME_DIR/wayland-0" ]]; then
  export WAYLAND_DISPLAY=wayland-0
  export XDG_SESSION_TYPE=wayland
fi

if [[ -S /tmp/.X11-unix/X0 ]]; then
  export DISPLAY=:0
fi

if auth="$(pick_xauthority 2>/dev/null)"; then
  export XAUTHORITY="$auth"
fi

if [[ -z "${DISPLAY:-}" && -z "${WAYLAND_DISPLAY:-}" ]]; then
  echo "No graphical session detected; skipping Maez Electron startup."
  exit 0
fi

cd /home/rohit/maez/ui/electron
exec /home/rohit/maez/ui/electron/node_modules/.bin/electron \
  /home/rohit/maez/ui/electron/main.js \
  --no-sandbox \
  --disable-dev-shm-usage \
  --ozone-platform-hint=auto
