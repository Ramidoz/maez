# devices/jetson_presence/setup_models.sh
#!/usr/bin/env bash
# Two-phase, manifest-pinned model setup. Runs ON THE JETSON. Artifacts stay
# device-local (gitignored). Usage:
#   setup_models.sh deps         # install onnx/onnxruntime/pycuda/numpy
#   setup_models.sh lock-hashes  # download ONNX, compute sha256, write manifest, EXIT (no build)
#   setup_models.sh build        # REFUSE unless locked; verify each sha; THEN trtexec-compile
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
MODELS="$HERE/models"
PY="${PYTHON:-python3}"
# b1a/ helpers are importable from the deployed package root:
export PYTHONPATH="$HERE:${PYTHONPATH:-}"
export MODELS_DIR="$MODELS"
export TRTEXEC="${TRTEXEC:-/usr/src/tensorrt/bin/trtexec}"

cmd_deps() {
  echo "== ensure pip + inference deps =="
  "$PY" -m ensurepip --upgrade 2>/dev/null || true
  "$PY" -m pip install --user --upgrade onnx onnxruntime pycuda numpy 2>&1 | tail -2
}

# Phase 1: download each manifest model, compute its sha256, write it back. NO build.
cmd_lock_hashes() {
  echo "== download ONNX + compute sha256 (NO build) =="
  "$PY" - <<'PYEOF'
import hashlib
import json
import os
import urllib.request

mdir = os.environ["MODELS_DIR"]
mpath = os.path.join(mdir, "manifest.json")
with open(mpath, encoding="utf-8") as f:
    manifest = json.load(f)

for entry in manifest["models"]:
    onnx = os.path.join(mdir, entry["name"] + ".onnx")
    print(f"downloading {entry['name']} <- {entry['source_url']}")
    urllib.request.urlretrieve(entry["source_url"], onnx)
    h = hashlib.sha256()
    with open(onnx, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    entry["sha256"] = h.hexdigest()
    print(f"  sha256={entry['sha256']}")

with open(mpath, "w", encoding="utf-8") as f:
    json.dump(manifest, f, indent=2)
    f.write("\n")
print("manifest.json updated.")
PYEOF
  echo ">> Review the diff to models/manifest.json, then COMMIT the real hashes before 'build'."
}

# Phase 2: refuse unless locked, verify every sha, THEN trtexec-compile. No unverified engine.
cmd_build() {
  echo "== gate + verify + compile =="
  "$PY" - <<'PYEOF'
import os
import subprocess
import sys

from jetson_presence.b1a import manifest as man

mdir = os.environ["MODELS_DIR"]
trtexec = os.environ["TRTEXEC"]
manifest = man.load_manifest()

if not man.hashes_locked(manifest):
    sys.exit("REFUSING build: manifest still has unlocked hashes. Run lock-hashes + commit first.")

for entry in manifest["models"]:
    onnx = os.path.join(mdir, entry["name"] + ".onnx")
    if not man.verify_sha256(onnx, entry["sha256"]):
        sys.exit(f"REFUSING build: sha256 mismatch for {entry['name']}")
    print(f"verified {entry['name']}")

for entry in manifest["models"]:
    onnx = os.path.join(mdir, entry["name"] + ".onnx")
    engine = os.path.join(mdir, os.path.basename(entry["engine_path"]))
    cmd = [trtexec, f"--onnx={onnx}", f"--saveEngine={engine}"]
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
  lock-hashes) cmd_lock_hashes ;;
  build) cmd_build ;;
  *) echo "usage: setup_models.sh {deps|lock-hashes|build}" >&2; exit 2 ;;
esac
