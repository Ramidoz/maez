# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""destructive_snapshot.py — pre-flight snapshot layer for destructive
shell commands.

Context 2026-04-20: owner approved an action card proposing
`git checkout -- core/cognition_quality.py` as a "preparation step"
for applying an evolution proposal. Checkout ran, unstaged local
edits were destroyed, no backup path existed. `write_any_file` has
auto-backup; destructive shell commands did not. This module closes
the gap.

Scope:
  - classify(cmd) → {is_destructive, shape, files}
  - snapshot(request_id, cmd, reason, files, *, root=...) → {manifest_path}
  - list_recent(days=7, *, root=...) → [manifest summaries]
  - restore(request_id, dry_run=True, *, root=...) → {mode, files}

Shape coverage (MVP): git_checkout, git_restore, git_reset_hard, rm,
truncate. Other destructive shapes (`mv -f`, `dd of=`, redirect `>`)
are out of scope and will be added when observed.

Safety policy:
  - Parse errors never raise — return is_destructive=False.
  - Snapshot failures never block the command — the action_engine
    caller logs the failure and proceeds.
  - Restore is human-driven via CLI, not exposed as a Maez action.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import shlex
import shutil
import sys
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger("maez.destructive_snapshot")

_DEFAULT_ROOT = "/home/rohit/maez/memory/backups/pre_destructive"

# Regexes for each destructive shape. Ordered — more specific first.
_GIT_PREFIX = r"git\s+(?:-C\s+\S+\s+)?"
_RE_GIT_CHECKOUT = re.compile(
    rf"{_GIT_PREFIX}checkout\s+--\s+(?P<paths>.+)$"
)
# restore with --staged is index-only (not destructive to working tree)
_RE_GIT_RESTORE = re.compile(
    rf"{_GIT_PREFIX}restore\s+(?!--staged)(?:--(?!staged)\S+\s+)*(?P<paths>.+)$"
)
_RE_GIT_RESET_HARD = re.compile(
    rf"{_GIT_PREFIX}reset\s+--hard\b"
)
# rm <flags> <paths> — non-flag tokens after rm are the paths
_RE_RM = re.compile(r"(?<!\w)rm\b(?P<rest>.*)$")
_RE_TRUNCATE = re.compile(r"(?<!\w)truncate\b(?P<rest>.*)$")


def _git_cwd(cmd: str) -> str | None:
    """Extract `-C <dir>` from a git command if present."""
    m = re.search(r"git\s+-C\s+(\S+)", cmd)
    return m.group(1) if m else None


def _resolve_paths(paths: list[str], base: str | None) -> list[str]:
    """Resolve path tokens against a `-C` base if given. Preserve
    absolute paths untouched."""
    out: list[str] = []
    for p in paths:
        p = p.strip().strip('"').strip("'")
        if not p:
            continue
        if p.startswith("/") or base is None:
            out.append(p)
        else:
            out.append(str(Path(base) / p))
    return out


def classify(cmd: Any) -> dict:
    """Classify a shell command. Returns a dict with:
      - is_destructive: bool
      - shape: str ("git_checkout"|"git_restore"|"git_reset_hard"|
                    "rm"|"truncate"|"")
      - files: list[str] — absolute paths when determinable, or the
                raw tokens; "<git-modified-tracked>" sentinel for
                git reset --hard (resolved by caller at snapshot time).
    Never raises."""
    default = {"is_destructive": False, "shape": "", "files": []}
    if not cmd or not isinstance(cmd, str):
        return default
    s = cmd.strip()
    if not s:
        return default

    # git reset --hard
    if _RE_GIT_RESET_HARD.search(s):
        return {
            "is_destructive": True,
            "shape": "git_reset_hard",
            "files": ["<git-modified-tracked>"],
        }

    # git checkout -- <paths>
    m = _RE_GIT_CHECKOUT.search(s)
    if m:
        try:
            paths = shlex.split(m.group("paths"))
        except ValueError:
            return default
        return {
            "is_destructive": True,
            "shape": "git_checkout",
            "files": _resolve_paths(paths, _git_cwd(s)),
        }

    # git restore <paths> (excludes --staged)
    m = _RE_GIT_RESTORE.search(s)
    if m:
        try:
            toks = shlex.split(m.group("paths"))
        except ValueError:
            return default
        # drop any remaining --flag tokens
        toks = [t for t in toks if not t.startswith("-")]
        if not toks:
            return default
        return {
            "is_destructive": True,
            "shape": "git_restore",
            "files": _resolve_paths(toks, _git_cwd(s)),
        }

    # rm
    m = _RE_RM.search(s)
    if m:
        try:
            toks = shlex.split(m.group("rest"))
        except ValueError:
            return default
        paths = [t for t in toks if not t.startswith("-")]
        if not paths:
            return default
        return {
            "is_destructive": True,
            "shape": "rm",
            "files": paths,
        }

    # truncate
    m = _RE_TRUNCATE.search(s)
    if m:
        try:
            toks = shlex.split(m.group("rest"))
        except ValueError:
            return default
        # truncate flags may consume args (-s N) — last non-flag is path
        non_flags: list[str] = []
        skip_next = False
        for t in toks:
            if skip_next:
                skip_next = False
                continue
            if t == "-s":
                skip_next = True
                continue
            if t.startswith("-"):
                continue
            non_flags.append(t)
        if not non_flags:
            return default
        return {
            "is_destructive": True,
            "shape": "truncate",
            "files": non_flags,
        }

    return default


def _mirror_path(original: str) -> str:
    """Return the mirrored relative path for a snapshot. Preserves
    the absolute path structure under `files/` so restoration is
    unambiguous."""
    p = original
    if p.startswith("/"):
        p = p[1:]
    return f"files/{p}"


def _sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def snapshot(
    *,
    request_id: str,
    cmd: str,
    reason: str,
    files: list[str],
    root: str | None = None,
    shape: str = "",
) -> dict:
    """Copy `files` into backup/<request_id>/ + write manifest.
    Returns {manifest_path, n_files, errors}. Never raises —
    returns an error list if anything went wrong."""
    root_path = Path(root or _DEFAULT_ROOT)
    dir_path = root_path / request_id
    files_root = dir_path / "files"
    errors: list[str] = []
    entries: list[dict] = []
    try:
        files_root.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        return {
            "manifest_path": None, "n_files": 0,
            "errors": [f"mkdir failed: {e}"],
        }
    for orig in files:
        if orig == "<git-modified-tracked>":
            # Caller resolves this at snapshot time by running
            # git diff --name-only; if caller didn't resolve it,
            # record the sentinel so restore can skip it.
            entries.append({
                "original_path": orig,
                "snapshot_path": None,
                "sha256": None,
                "size_bytes": 0,
                "existed_pre_snapshot": False,
                "note": "sentinel-not-resolved",
            })
            continue
        src = Path(orig)
        snap_rel = _mirror_path(orig)
        snap = dir_path / snap_rel
        try:
            snap.parent.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            errors.append(f"mkdir for {orig}: {e}")
            continue
        if src.exists() and src.is_file():
            try:
                shutil.copy2(str(src), str(snap))
                entries.append({
                    "original_path": str(src),
                    "snapshot_path": snap_rel,
                    "sha256": _sha256_of(snap),
                    "size_bytes": snap.stat().st_size,
                    "existed_pre_snapshot": True,
                })
            except Exception as e:
                errors.append(f"copy {orig}: {e}")
                entries.append({
                    "original_path": str(src),
                    "snapshot_path": None,
                    "sha256": None,
                    "size_bytes": 0,
                    "existed_pre_snapshot": True,
                    "note": f"copy_failed: {e}",
                })
        else:
            # File didn't exist pre-command (e.g. `rm` of a missing path,
            # or a sentinel). Record intent for restore to handle.
            entries.append({
                "original_path": str(src),
                "snapshot_path": None,
                "sha256": None,
                "size_bytes": 0,
                "existed_pre_snapshot": False,
            })
    manifest = {
        "request_id": request_id,
        "ts": time.time(),
        "cmd": cmd,
        "reason": reason,
        "shape": shape,
        "files": entries,
    }
    manifest_path = dir_path / "manifest.json"
    try:
        manifest_path.write_text(json.dumps(manifest, indent=2))
    except Exception as e:
        errors.append(f"manifest write: {e}")
        return {"manifest_path": None, "n_files": len(entries),
                "errors": errors}
    return {
        "manifest_path": str(manifest_path),
        "n_files": len(entries),
        "errors": errors,
    }


def list_recent(*, days: int = 7, root: str | None = None) -> list[dict]:
    """Return manifest summaries newest first. `days` caps age."""
    root_path = Path(root or _DEFAULT_ROOT)
    if not root_path.exists():
        return []
    cutoff = time.time() - (days * 86400)
    out: list[dict] = []
    for child in root_path.iterdir():
        m = child / "manifest.json"
        if not m.exists():
            continue
        try:
            data = json.loads(m.read_text())
        except Exception:
            continue
        if data.get("ts", 0) < cutoff:
            continue
        out.append({
            "request_id": data.get("request_id"),
            "ts": data.get("ts"),
            "cmd": data.get("cmd"),
            "shape": data.get("shape"),
            "n_files": len(data.get("files", [])),
            "manifest_path": str(m),
        })
    out.sort(key=lambda x: x.get("ts") or 0, reverse=True)
    return out


def restore(
    *,
    request_id: str,
    dry_run: bool = True,
    root: str | None = None,
) -> dict:
    """Restore files from a snapshot. `dry_run=True` previews only."""
    root_path = Path(root or _DEFAULT_ROOT)
    m_path = root_path / request_id / "manifest.json"
    if not m_path.exists():
        return {"mode": "not_found", "files": []}
    try:
        data = json.loads(m_path.read_text())
    except Exception as e:
        return {"mode": "error", "error": str(e), "files": []}

    actions: list[dict] = []
    for entry in data.get("files", []):
        if not entry.get("existed_pre_snapshot"):
            continue
        snap_rel = entry.get("snapshot_path")
        if not snap_rel:
            continue
        snap = root_path / request_id / snap_rel
        target = Path(entry["original_path"])
        if not snap.exists():
            actions.append({"target": str(target), "status": "snap_missing"})
            continue
        actions.append({
            "target": str(target),
            "snapshot": str(snap),
            "status": "would_restore" if dry_run else "restored",
        })
        if not dry_run:
            try:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(str(snap), str(target))
            except Exception as e:
                actions[-1]["status"] = f"restore_failed: {e}"

    return {
        "mode": "dry_run" if dry_run else "applied",
        "files": actions,
    }


# ── CLI ────────────────────────────────────────────────────────────────

def _cli_list(days: int = 7) -> int:
    rows = list_recent(days=days)
    if not rows:
        print("(no pre-destructive snapshots in the last "
              f"{days} days)")
        return 0
    for r in rows:
        ts = time.strftime("%Y-%m-%d %H:%M:%S",
                           time.localtime(r.get("ts", 0)))
        print(f"{r.get('request_id', '?')}  {ts}  "
              f"shape={r.get('shape', '?')}  files={r.get('n_files', 0)}")
        print(f"    cmd: {r.get('cmd', '')[:100]}")
    return 0


def _cli_restore(request_id: str, dry_run: bool = True) -> int:
    r = restore(request_id=request_id, dry_run=dry_run)
    mode = r.get("mode")
    if mode == "not_found":
        print(f"no snapshot for request_id {request_id!r}")
        return 1
    print(f"mode: {mode}")
    for f in r.get("files", []):
        print(f"  {f.get('status', '?'):20s}  {f.get('target', '?')}")
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = list(argv or sys.argv[1:])
    if not argv or argv[0] in ("-h", "--help", "help"):
        print("usage:")
        print("  python -m core.destructive_snapshot list [days]")
        print("  python -m core.destructive_snapshot preview <request_id>")
        print("  python -m core.destructive_snapshot restore <request_id>")
        return 0
    cmd = argv[0]
    if cmd == "list":
        days = int(argv[1]) if len(argv) > 1 else 7
        return _cli_list(days=days)
    if cmd == "preview" and len(argv) >= 2:
        return _cli_restore(argv[1], dry_run=True)
    if cmd == "restore" and len(argv) >= 2:
        return _cli_restore(argv[1], dry_run=False)
    print(f"unknown command: {cmd}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
