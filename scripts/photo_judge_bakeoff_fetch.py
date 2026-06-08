# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""scripts/photo_judge_bakeoff_fetch.py — the ONLY network component of the
photo bakeoff. Pinned + sha256-recorded HuggingFace downloads into the NON-live
models/bakeoff/ cache, with an OPTIONAL one-shot smoke hook (default: skipped —
the runner's adapter-load is the integration smoke; pass smoke_fn to verify a load
+ predict here). NEVER starts a service, edits model.env, or writes to
models/llamacpp/. The runner never imports this module.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path


def _snapshot_download(repo_id, revision, local_dir, **kw):
    from huggingface_hub import snapshot_download
    return snapshot_download(repo_id=repo_id, revision=revision,
                             local_dir=local_dir, **kw)


def _dir_sha256(path: str) -> str:
    h = hashlib.sha256()
    for p in sorted(Path(path).rglob("*")):
        if p.is_file() and p.name != "bakeoff_manifest.json":  # exclude our own
            h.update(p.name.encode())
            h.update(p.read_bytes())
    return h.hexdigest()


def fetch_one(*, repo_id: str, revision: str, name: str, dest_root: str,
              smoke_fn=None) -> dict:
    if not revision:
        raise ValueError("revision must be PINNED (a specific commit/tag)")
    dest = os.path.join(dest_root, name)
    _snapshot_download(repo_id=repo_id, revision=revision, local_dir=dest)
    sha = _dir_sha256(dest)
    rec = {"name": name, "repo_id": repo_id, "revision": revision,
           "path": dest, "sha256": sha, "smoke": "skipped"}
    # Record the pinned revision + sha256 so the bakeoff report's fingerprint is
    # the ACTUAL downloaded artifact (the adapter reads this manifest at load).
    with open(os.path.join(dest, "bakeoff_manifest.json"), "w",
              encoding="utf-8") as fh:
        json.dump({"name": name, "repo_id": repo_id, "revision": revision,
                   "sha256": sha}, fh, indent=2)
    if smoke_fn is not None:
        try:
            smoke_fn(dest)            # caller-supplied one load + one predict
            rec["smoke"] = "ok"
        except Exception as e:        # honest failure, never a crash
            rec["smoke"] = f"failed: {type(e).__name__}: {e}"
    return rec


def main(argv=None) -> int:
    import argparse
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--repo-id", required=True)
    p.add_argument("--revision", required=True, help="PINNED commit SHA or tag")
    p.add_argument("--name", required=True,
                   help="dest subdir under models/bakeoff/")
    p.add_argument("--dest-root", default=os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "models", "bakeoff"))
    args = p.parse_args(argv)
    rec = fetch_one(repo_id=args.repo_id, revision=args.revision,
                    name=args.name, dest_root=args.dest_root)
    print(json.dumps(rec, indent=2))   # the runbook records this verbatim
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
