#!/usr/bin/env python3
# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""One-shot memory-curation pass — 2026-04-24.

Writes dated corrective core memories + tags high-impact stale/fabricated
raw entries with `integrity` metadata. Never deletes. Idempotent: a second
run on a post-curation state is a no-op (every corrective already present
by source; every targeted id already carries the intended tag).

Principles (treat this as runtime curation, not a code refactor):

  1. No deletion. Raw memory stays intact. Corrections accumulate as new
     dated core memories. Stale/fabricated entries are downweighted via
     `integrity` metadata, not removed.
  2. Only curate high-impact clusters. Four: vision-service fabrication,
     current brain/model identity, repetitive stale disk-pressure refrain,
     judge-retired status. Do NOT bulk-tag every `%` or every `gemma`
     mention.
  3. Every write reversible or additive.

Usage:
    .venv/bin/python scripts/memory_curation/curate_2026_04_24.py --dry-run
    .venv/bin/python scripts/memory_curation/curate_2026_04_24.py --commit

Dry-run is default. `--commit` executes writes + tags. Log lands in
logs/memory_curation_2026-04-24.txt regardless of mode (dry-run logs
planned actions; commit logs executed ones).
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

LOG_PATH = _REPO / "logs" / "memory_curation_2026-04-24.txt"


# ─── corrective core memories ────────────────────────────────────────────

def _live_disk_usage() -> str:
    """Capture current / usage at write-time so the correction carries
    today's real number, not yesterday's. Fails open with '(unknown)'."""
    try:
        r = subprocess.run(
            ["df", "-h", "/"], capture_output=True, text=True, timeout=3,
        )
        lines = [ln for ln in (r.stdout or "").splitlines() if "/" in ln]
        if lines:
            return lines[-1].strip()
    except Exception:
        pass
    return "(unknown)"


# Each entry: {source: unique source string, content: the correction body}.
# Content follows reference_corrective_core_memory_pattern.md:
#   dated header, explicit fabrication name, current truth,
#   "if asked" guidance, live verification command.
CORRECTIONS = [
    {
        "source": "infrastructure_correction_primary_brain_2026-04-24",
        "content": (
            "INFRASTRUCTURE GROUND-TRUTH (2026-04-24 correction, "
            "overrides earlier beliefs about which model runs Maez):\n\n"
            "Earlier raw-memory entries refer to `gemma-4-26B-A4B`, "
            "`gemma4:26b`, or `supergemma4-26b` as Maez's primary "
            "brain. That was true for a window ending 2026-04-23. The "
            "current primary is Qwen3.6-27B-UD-Q4_K_XL, served via "
            "llama.cpp on 127.0.0.1:8080 at about 19 GB of VRAM on "
            "the RTX 4090.\n\n"
            "If asked which model is currently loaded:\n"
            "  - Do not name gemma anything.\n"
            "  - Say the current primary is Qwen3.6-27B-UD-Q4_K_XL.\n"
            "  - Offer to verify live via "
            "`curl -s http://127.0.0.1:8080/v1/models` and defer to "
            "whatever that returns if it disagrees with this note.\n\n"
            "The authoritative source is /etc/maez/model.env "
            "(MAEZ_PRIMARY_MODEL) and the live /v1/models endpoint. "
            "This correction overrides older raw-memory mentions of "
            "gemma variants as the current brain."
        ),
    },
    {
        "source": "observational_refrain_disk_pressure_2026-04-24",
        "content": (
            "OBSERVATIONAL REFRAIN (2026-04-24): the repeated "
            "`/ partition is at 65.6% / 87.0% capacity` observations "
            "in raw memory spanning 2026-04-06 through 2026-04-20 "
            "are historical snapshots, NOT current state. They "
            "accumulated because the daemon cycled through nearly "
            "identical disk-pressure framings for two weeks with "
            "little change.\n\n"
            f"Live disk snapshot at correction time: {_live_disk_usage()}\n\n"
            "If asked about current disk pressure:\n"
            "  - Do not narrate from memory.\n"
            "  - Read the live value via `df -h /` and report THAT.\n"
            "  - If the live value is steady (hasn't moved materially "
            "in a day) say so plainly; do not restate the same "
            "percentage cycle after cycle.\n\n"
            "This is not a fabrication — the historical observations "
            "were accurate at the time. They are retained in raw "
            "memory per the never-delete rule. This note exists so "
            "the refrain does not get re-narrated as if current."
        ),
    },
    {
        "source": "infrastructure_correction_judge_retired_2026-04-24",
        "content": (
            "INFRASTRUCTURE GROUND-TRUTH (2026-04-24 correction, "
            "overrides earlier beliefs about the grounding judge):\n\n"
            "Earlier raw-memory entries describe an active grounding "
            "judge, an `llama-judge.service`, or a Qwen3.5-4B judge "
            "running on port 8081. That was true through most of "
            "April. As of 2026-04-23 the judge was RETIRED: service "
            "stopped, disabled, systemd dependency-symlink removed. "
            "The 4B weights are no longer loaded; port 8081 has no "
            "listener.\n\n"
            "If asked whether a judge is flagging / auditing a "
            "reply, or whether llama-judge is running:\n"
            "  - Say the judge was retired on 2026-04-23.\n"
            "  - The primary brain (Qwen3.6-27B) is now responsible "
            "for its own grounding discipline; Commit 1 of the "
            "2026-04-23 repair pass made audit-before-store the "
            "invariant (see core/safety/audited_output.py).\n"
            "  - Verify via `systemctl is-active llama-judge` "
            "(expected: 'inactive')."
        ),
    },
]


# ─── raw-entry tagging filters ──────────────────────────────────────────

# Patterns that identify a fabricated `llama-server-vision` narrative.
# Match if ANY of these substrings appear in the entry text. The vision
# service never existed as a systemd unit on this machine; the 2026-04-23
# chat-self-claim-hallucination regression traced to this class.
_VISION_FABRICATION_PATTERNS = (
    "llama-server-vision",
    "Llama vision server",
    "llama vision server",
    "vision server is returning 500",
    "missing mmproj",
)

_VISION_REASON = (
    "fake 'llama-server-vision' service narrative; no such systemd "
    "unit ever existed. See core memory "
    "infrastructure_correction_2026-04-23. Retained per never-delete "
    "rule."
)

# Disk-pressure refrain: a very tight filter. Must match ALL of:
#   - entry in raw (type=reasoning)
#   - timestamp between 2026-04-06 and 2026-04-20 (inclusive)
#   - contains "partition" AND a percentage, AND the refrain-structure
#     phrase "is at" or "remains at"
#
# Intentionally conservative; the goal is to tag the repetitive
# refrain only, not every disk-related observation. Entries from
# 2026-04-21 onward MAY carry fresh signal — do not tag.
_DISK_REFRAIN_START = "2026-04-06"
_DISK_REFRAIN_END = "2026-04-20"
_DISK_REFRAIN_STRUCT_PATTERNS = (
    "partition is at",
    "partition remains at",
)
_DISK_REFRAIN_PCT_RE = re.compile(r"\b\d{1,3}\.\d%|\b\d{1,3}%")

_DISK_REASON = (
    "repetitive disk-pressure snapshot from 2026-04-06..2026-04-20; "
    "historical observation retained per never-delete rule. Canonical "
    "framing in observational_refrain_disk_pressure_2026-04-24."
)


def _matches_vision_fabrication(doc: str) -> bool:
    if not doc:
        return False
    return any(p in doc for p in _VISION_FABRICATION_PATTERNS)


def _matches_disk_refrain(doc: str, ts: str) -> bool:
    if not doc or not ts:
        return False
    # Timestamp window: string comparison works on ISO-8601.
    if not (_DISK_REFRAIN_START <= ts[:10] <= _DISK_REFRAIN_END):
        return False
    if not any(p in doc for p in _DISK_REFRAIN_STRUCT_PATTERNS):
        return False
    if not _DISK_REFRAIN_PCT_RE.search(doc):
        return False
    # Guard: don't tag entries that META-analyze the refrain — those
    # are meta-observations worth keeping visible.
    if "refrain" in doc.lower() or "fixation" in doc.lower():
        return False
    return True


# ─── driver ─────────────────────────────────────────────────────────────

def run(*, commit: bool) -> int:
    log_lines: list[str] = []

    def log(msg: str) -> None:
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")
        prefix = "[COMMIT] " if commit else "[DRYRUN] "
        line = f"{stamp} {prefix}{msg}"
        log_lines.append(line)
        print(line)

    from memory.memory_manager import MemoryManager
    m = MemoryManager()

    log(f"raw count: {m.raw.count()}")
    log(f"core count (before): {m.core.count()}")

    # ── Phase B: corrective core memories ───────────────────────────
    core_res = m.core.get(include=["documents", "metadatas"])
    existing_sources = {
        (meta or {}).get("source", "") for meta in (core_res.get("metadatas") or [])
    }

    log("── Phase B: corrective core memories ──")
    corrections_written = 0
    for corr in CORRECTIONS:
        src = corr["source"]
        if src in existing_sources:
            log(f"  SKIP (already present): {src}")
            continue
        if commit:
            mid = m.store_core(corr["content"], source=src)
            log(f"  WROTE {src} -> {mid} ({len(corr['content'])} chars)")
            corrections_written += 1
        else:
            log(f"  WOULD WRITE: {src} ({len(corr['content'])} chars)")
            corrections_written += 1

    # ── Phase C: tag raw entries ────────────────────────────────────
    log("── Phase C: tag_integrity on raw clusters ──")

    raw_res = m.raw.get(include=["documents", "metadatas"])
    rids = raw_res.get("ids") or []
    rdocs = raw_res.get("documents") or []
    rmetas = raw_res.get("metadatas") or []

    vision_ids_to_tag: list[str] = []
    disk_ids_to_tag: list[str] = []

    for rid, doc, meta in zip(rids, rdocs, rmetas, strict=False):
        meta = meta or {}
        current_integrity = meta.get("integrity")
        ts = meta.get("timestamp", "") or ""

        # Vision cluster
        if _matches_vision_fabrication(doc):
            if current_integrity == "fabricated":
                continue  # already tagged, skip
            vision_ids_to_tag.append(rid)
            continue

        # Disk-pressure refrain
        if _matches_disk_refrain(doc, ts):
            if current_integrity == "historical_artifact":
                continue
            disk_ids_to_tag.append(rid)

    log(f"  vision_fabrication matches (to tag): {len(vision_ids_to_tag)}")
    log(f"  disk_refrain matches (to tag):       {len(disk_ids_to_tag)}")

    # Sample-review dump (always, both modes) — surfaces the filter
    # shape to a human reader. A bad filter becomes obvious here.
    def _sample_dump(label: str, ids_list: list[str], pool_ids: list[str],
                    pool_docs: list[str], pool_metas: list) -> None:
        if not ids_list:
            log(f"  [{label}] 0 matches — nothing to sample.")
            return
        # Find (id, doc, ts) triples for the first 3 ids
        by_id = {pool_ids[i]: (pool_docs[i], (pool_metas[i] or {}).get("timestamp", ""))
                 for i in range(len(pool_ids))}
        log(f"  [{label}] sample of 3 (of {len(ids_list)}):")
        for sid in ids_list[:3]:
            doc, ts = by_id.get(sid, ("(?)", "(?)"))
            head = (doc or "").replace("\n", " ")[:140]
            log(f"    id={sid} ts={ts}")
            log(f"      head={head!r}")

    _sample_dump("vision_fabrication", vision_ids_to_tag, rids, rdocs, rmetas)
    _sample_dump("disk_refrain", disk_ids_to_tag, rids, rdocs, rmetas)

    vision_tagged = 0
    disk_tagged = 0

    if commit:
        if vision_ids_to_tag:
            vision_tagged = m.tag_integrity(
                vision_ids_to_tag,
                integrity="fabricated",
                reason=_VISION_REASON,
            )
            log(f"  tagged {vision_tagged} vision entries as 'fabricated'")

        if disk_ids_to_tag:
            # Chunk the disk-refrain tagging — Chroma's update() is
            # fine with batch calls but huge single-call payloads
            # aren't ideal. 500-id chunks.
            # 2026-04-24: heartbeat between chunks so progress is
            # visible when the script runs for several minutes.
            CHUNK = 500
            total = len(disk_ids_to_tag)
            for i in range(0, total, CHUNK):
                sub = disk_ids_to_tag[i:i + CHUNK]
                batch_start = time.time()
                disk_tagged += m.tag_integrity(
                    sub,
                    integrity="historical_artifact",
                    reason=_DISK_REASON,
                )
                elapsed = time.time() - batch_start
                log(f"    chunk {i // CHUNK + 1}: "
                    f"{disk_tagged}/{total} tagged "
                    f"({elapsed:.1f}s this chunk)")
                sys.stdout.flush()
            log(f"  tagged {disk_tagged} disk-refrain entries as "
                f"'historical_artifact'")
    else:
        log(f"  WOULD TAG {len(vision_ids_to_tag)} vision as 'fabricated'")
        log(f"  WOULD TAG {len(disk_ids_to_tag)} disk-refrain as "
            "'historical_artifact'")

    # ── Summary ────────────────────────────────────────────────────
    log("── Summary ──")
    log(f"  corrective core writes: {corrections_written}")
    log(f"  vision entries tagged:  {vision_tagged if commit else len(vision_ids_to_tag)}")
    log(f"  disk-refrain tagged:    {disk_tagged if commit else len(disk_ids_to_tag)}")
    log(f"  core count (after):     {m.core.count()}")
    log(f"  mode:                   {'COMMIT' if commit else 'DRY RUN'}")

    # Write the log file.
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    existing = LOG_PATH.read_text() if LOG_PATH.exists() else ""
    header = "\n" + "=" * 70 + f"\nRun at {datetime.now(timezone.utc).isoformat()}\n" + "=" * 70 + "\n"
    LOG_PATH.write_text(existing + header + "\n".join(log_lines) + "\n")
    log(f"log appended to {LOG_PATH}")

    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--commit",
        action="store_true",
        help="Execute writes + tags. Default is a dry run.",
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="Explicit dry-run flag (the default; this flag is for "
        "clarity in scripts that want to be explicit).",
    )
    args = ap.parse_args()
    return run(commit=bool(args.commit))


if __name__ == "__main__":
    sys.exit(main())
