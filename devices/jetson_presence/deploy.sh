#!/usr/bin/env bash
# Deploy the Jetson edge package SOURCE ONLY to the device. Never copies secrets.
set -euo pipefail

JETSON="${MAEZ_JETSON_SSH:-rohit@192.168.40.27}"
DEST="${MAEZ_JETSON_DEST:-/home/rohit/maez-jetson}"
HERE="$(cd "$(dirname "$0")" && pwd)"

case "$DEST" in
  /*/maez-jetson) ;;
  *) echo "Refusing deploy: MAEZ_JETSON_DEST must be an absolute path ending in /maez-jetson (got: $DEST)" >&2; exit 2 ;;
esac

# rsync ONLY package source files. The allowlist keeps local runtime/secret artifacts out.
rsync -av --delete \
  --exclude '__pycache__/' \
  --exclude '.env*' \
  --exclude 'secrets*' \
  --exclude 'runtime*' \
  --exclude 'state/' \
  --exclude 'logs/' \
  --exclude '*.token' --exclude 'token' \
  --exclude '*.key' --exclude '*.pem' --exclude '*.secret' \
  --include '*/' --include '*.py' \
  --exclude '*' \
  "$HERE/jetson_presence/" "$JETSON:$DEST/jetson_presence/"

# B1a: also deploy the model setup script + the TRACKED manifest (never the artifacts).
# The trailing `--exclude '*'` means ONLY the allowlisted paths cross; *.onnx/*.engine
# never match an --include, so they are structurally excluded.
rsync -av \
  --include 'setup_models.sh' \
  --include 'models/' \
  --include 'models/manifest.json' \
  --exclude '*' \
  "$HERE/" "$JETSON:$DEST/"
echo "Deployed setup_models.sh + models/manifest.json (artifacts excluded by allowlist)."

echo "Deployed source to $JETSON:$DEST/jetson_presence/"
echo "Token + flag are provisioned on the Jetson env, NOT copied from the repo."
echo "Run on device:  cd $DEST && MAEZ_JETSON_DEVICE_TOKEN=... python3 -m jetson_presence.run --once"
