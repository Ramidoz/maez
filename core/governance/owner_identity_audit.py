# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Append-only audit sink for web-native owner-identity claims (Task 0 §2)."""
import json, os, time
from core.infra import paths as _paths

DEFAULT_AUDIT_PATH = str(_paths.home() / "memory" / "owner_identity_audit.jsonl")

def record(action: str, *, account: str | None, euid: int, path: str = DEFAULT_AUDIT_PATH) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    line = json.dumps({"at": time.time(), "action": action, "account": account, "euid": euid})
    with open(path, "a") as f:
        f.write(line + "\n")
