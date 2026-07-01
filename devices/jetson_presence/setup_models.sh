#!/usr/bin/env bash
# devices/jetson_presence/setup_models.sh
# Manifest-pinned model setup. Runs ON THE JETSON. Artifacts stay device-local
# (gitignored). Models ship inside an InsightFace release zip pack; the manifest pins
# the pack sha256 AND each extracted member sha256, so `build` needs no trust-on-first-use.
# Usage:
#   setup_models.sh deps         # install onnxruntime/cuda-python<13/numpy<2; requires python3-pip
#   setup_models.sh build        # verify pack+member shas (refuse on any mismatch) then trtexec-compile
#   setup_models.sh lock-hashes  # re-lock: download pack, recompute all shas, rewrite manifest, EXIT (no build)
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
MODELS="$HERE/models"
PY="${PYTHON:-python3}"
# b1a/ helpers are importable from the deployed package root:
export PYTHONPATH="$HERE:${PYTHONPATH:-}"
export MODELS_DIR="$MODELS"
export TRTEXEC="${TRTEXEC:-/usr/src/tensorrt/bin/trtexec}"

cmd_deps() {
  echo "== check pip + install inference deps =="
  if ! "$PY" -m pip --version >/dev/null 2>&1; then
    echo "Missing pip for $PY." >&2
    echo "Install it on the Jetson first:" >&2
    echo "  sudo apt install python3-pip" >&2
    echo "Then verify:" >&2
    echo "  python3 -m pip --version" >&2
    exit 2
  fi
  "$PY" -m pip install --user --upgrade onnxruntime 'cuda-python<13' 'numpy<2'
}

# Re-lock helper (only needed when swapping the pack/models): download, recompute every
# sha256 (pack + members), rewrite manifest. NO build. Review the diff + commit after.
cmd_lock_hashes() {
  echo "== download pack + recompute sha256 (NO build) =="
  "$PY" - <<'PYEOF'
import hashlib
import json
import os
import urllib.request
import zipfile


def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


mdir = os.environ["MODELS_DIR"]
mpath = os.path.join(mdir, "manifest.json")
with open(mpath, encoding="utf-8") as f:
    manifest = json.load(f)

pack = manifest["source_pack"]
zip_path = os.path.join(mdir, pack["name"] + ".zip")
print(f"downloading {pack['name']} <- {pack['url']}")
urllib.request.urlretrieve(pack["url"], zip_path)
with open(zip_path, "rb") as fh:
    pack["sha256"] = sha256_bytes(fh.read())
print(f"  pack sha256={pack['sha256']}")

zf = zipfile.ZipFile(zip_path)
for entry in manifest["models"]:
    entry["sha256"] = sha256_bytes(zf.read(entry["member"]))
    print(f"  {entry['member']} sha256={entry['sha256']}")

with open(mpath, "w", encoding="utf-8") as f:
    json.dump(manifest, f, indent=2)
    f.write("\n")
print("manifest.json updated.")
PYEOF
  echo ">> Review the diff to models/manifest.json, then COMMIT the real hashes."
}

# Verify pack + member shas against the pinned manifest, extract, THEN trtexec-compile.
# No engine is built from an unverified byte.
cmd_build() {
  echo "== gate + verify pack/members + extract + compile =="
  "$PY" - <<'PYEOF'
import os
import subprocess
import sys
import urllib.request
import zipfile

from jetson_presence.b1a import manifest as man

mdir = os.environ["MODELS_DIR"]
trtexec = os.environ["TRTEXEC"]
manifest = man.load_manifest()

if not man.hashes_locked(manifest):
    sys.exit("REFUSING build: manifest has unlocked hashes. Run lock-hashes + commit first.")

pack = manifest["source_pack"]
zip_path = os.path.join(mdir, pack["name"] + ".zip")
if not os.path.exists(zip_path):
    print(f"downloading {pack['name']} <- {pack['url']}")
    urllib.request.urlretrieve(pack["url"], zip_path)
if not man.verify_sha256(zip_path, pack["sha256"]):
    sys.exit(f"REFUSING build: source pack sha256 mismatch ({pack['name']})")
print(f"verified pack {pack['name']}")

zf = zipfile.ZipFile(zip_path)
for entry in manifest["models"]:
    onnx = os.path.join(mdir, entry["member"])
    with open(onnx, "wb") as out:
        out.write(zf.read(entry["member"]))
    if not man.verify_sha256(onnx, entry["sha256"]):
        sys.exit(f"REFUSING build: sha256 mismatch for {entry['name']} ({entry['member']})")
    print(f"verified {entry['name']} <- {entry['member']}")

for entry in manifest["models"]:
    onnx = os.path.join(mdir, entry["member"])
    engine = os.path.join(mdir, os.path.basename(entry["engine_path"]))
    cmd = [
        trtexec,
        f"--onnx={onnx}",
        f"--saveEngine={engine}",
        f"--shapes={man.trtexec_shape_arg(entry)}",
    ]
    if entry["precision"] == "fp16":
        cmd.append("--fp16")  # explicit; an FP16 parity miss is a real result, not an override
    print("building:", " ".join(cmd))
    subprocess.run(cmd, check=True)
    print(f"  -> {engine}")

print("all engines built")
PYEOF
  echo "Done. Engines in $MODELS (gitignored). Run parity + spike to witness."
}

case "${1:-}" in
  deps) cmd_deps ;;
  build) cmd_build ;;
  lock-hashes) cmd_lock_hashes ;;
  *) echo "usage: setup_models.sh {deps|build|lock-hashes}" >&2; exit 2 ;;
esac
