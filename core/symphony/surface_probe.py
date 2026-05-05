# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""surface_probe.py — R5 of the 2026-05-04 symphony audit.

Implements the harness designed in S3 of the audit. Captures a
per-surface fingerprint of how Maez constructs its system prompt
across the surfaces Maez can speak through (Telegram-owner,
Telegram-public, web /chat, CLI, daemon cycle, fast-reply). The
fingerprint is diffable across runs — a baseline committed today
is the canonical "this is one Maez" snapshot; any future change
that flips an axis (audit gate disappears, body-truth no longer
present, identity excerpt changes) shows up as a delta line in
re-runs.

The harness is **probe-mode only**:
- Never drives the live Telegram bot
- Never POSTs to the web cockpit
- Calls internal prompt-builders / soul loaders directly

Design intent (per S3):
- Cheap to run (no live LLM calls)
- Stable serialization (JSON, sorted keys)
- Re-runnable on demand: `python -m core.symphony.surface_probe`
- Replay-comparable: future runs diff against the baseline

Axes per surface:
- system_prompt_sha256: sha256 of the surface's full system prompt
  (or canonical identity rendering for surfaces that don't have a
  single-string prompt)
- system_prompt_chars: length of that string
- audit_gate_present: does the surface call self_claim_audit /
  audit_assistant_text on its replies before send?
- tool_manifest_present: does the surface inject _TOOL_MANIFEST or
  available_actions_prompt?
- circadian_present: does the surface inject the circadian context
  block?
- body_truth_present: does the surface consult body_capabilities
  (directly OR via capability_registry.prompt_snippet())?
- identity_excerpt: first 120 chars of the identity sentence (for
  human-readable diffs)

The probe set:
- 8 natural-text probes from S3 (the audit's load-bearing examples
  of "what does Maez say when asked about its own body")

Surfaces enumerated:
- telegram_owner — skills/telegram_voice.py
- telegram_public — skills/telegram_public.py
- fast_reply — core/infra/fast_prompt_builder.py
- daemon_cycle — daemon/maez_daemon.py
- web_owner — skills/web_interface.py (the /chat owner-bridge path)
- cli — cli/maez_chat.py

Surfaces that need full daemon machinery to instantiate are probed
via SOURCE-LEVEL inspection (regex / grep) rather than runtime
construction. The harness degrades gracefully — if a surface can't
be reached, it's omitted from the result with no error.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("maez.symphony.surface_probe")

REPO = Path(__file__).resolve().parents[2]


# ── Probe set ────────────────────────────────────────────────────────

# Natural-text probes from S3 of the symphony audit. These are the
# user-shaped questions that exposed the wmctrl-class self-knowledge
# gap (offering tools the body doesn't have) and the surface drift
# class (Maez sounding like a different being on different surfaces).
NATURAL_TEXT_PROBES: tuple[str, ...] = (
    "hey you good?",
    "what can you do with my screen?",
    "can you check my Firefox tabs?",
    "what did your body just do?",
    "what are you unable to do right now?",
    "i miss her",
    "what's in your body right now?",
    "do you remember our conversation yesterday?",
)


# ── Per-surface probe builders ───────────────────────────────────────

@dataclass
class SurfaceFingerprint:
    """Documented axes that distinguish "same Maez" from "drift."

    Each axis can be probed at ZERO LLM cost — either by reading
    file source (source-level audit) or by calling a prompt-build
    function in isolation."""

    system_prompt_sha256: str
    system_prompt_chars: int
    audit_gate_present: bool
    tool_manifest_present: bool
    circadian_present: bool
    body_truth_present: bool
    identity_excerpt: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "system_prompt_sha256": self.system_prompt_sha256,
            "system_prompt_chars": self.system_prompt_chars,
            "audit_gate_present": self.audit_gate_present,
            "tool_manifest_present": self.tool_manifest_present,
            "circadian_present": self.circadian_present,
            "body_truth_present": self.body_truth_present,
            "identity_excerpt": self.identity_excerpt[:120],
        }


def _sha256_of(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _source_contains(file_path: Path, *needles: str) -> bool:
    """True if any needle appears in the file's source. Defensive
    wrapper — missing files silently return False so the harness
    degrades gracefully when a surface file is absent."""
    if not file_path.exists():
        return False
    try:
        src = file_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    return any(n in src for n in needles)


def probe_telegram_owner() -> Optional[SurfaceFingerprint]:
    """Source-level probe of skills/telegram_voice.py — the owner-
    primary surface. Reads soul.md as the proxy system-prompt
    fingerprint (telegram_owner appends the soul block + a hard-
    coded CRITICAL block + _TOOL_MANIFEST + circadian)."""
    tv_file = REPO / "skills" / "telegram_voice.py"
    soul = REPO / "config" / "soul.md"
    if not tv_file.exists() or not soul.exists():
        return None
    try:
        soul_text = soul.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    src = tv_file.read_text(encoding="utf-8", errors="replace")
    return SurfaceFingerprint(
        system_prompt_sha256=_sha256_of(soul_text),
        system_prompt_chars=len(soul_text),
        audit_gate_present=(
            "_audit_telegram_reply" in src
            or "self_claim_audit" in src
            or "audit_assistant_text" in src
        ),
        tool_manifest_present=("_TOOL_MANIFEST" in src),
        circadian_present=(
            "_get_circadian_context" in src
            or "circadian" in src
        ),
        body_truth_present=(
            "capability_registry" in src
            or "body_capabilities" in src
            or "prompt_snippet" in src
        ),
        identity_excerpt=soul_text[:120],
    )


def probe_telegram_public() -> Optional[SurfaceFingerprint]:
    """Source-level probe of skills/telegram_public.py."""
    tp_file = REPO / "skills" / "telegram_public.py"
    if not tp_file.exists():
        return None
    src = tp_file.read_text(encoding="utf-8", errors="replace")
    # Telegram public's identity surface lives inside
    # _build_system_prompt (a multi-line f-string). We extract its
    # body for fingerprinting.
    m = re.search(
        r"def _build_system_prompt\([^)]*\)[^:]*:(.*?)(?=\n    (?:async )?def )",
        src, re.DOTALL,
    )
    body = m.group(1) if m else src[:2000]
    return SurfaceFingerprint(
        system_prompt_sha256=_sha256_of(body),
        system_prompt_chars=len(body),
        audit_gate_present=(
            "audit_assistant_text" in src
            or "self_claim_audit" in src
            or "_audit_telegram_reply" in src
        ),
        tool_manifest_present=("_TOOL_MANIFEST" in src),
        circadian_present=(
            "_get_circadian_context" in src
            or "circadian" in src.lower()
        ),
        body_truth_present=(
            "capability_registry" in src
            or "body_capabilities" in src
        ),
        identity_excerpt=(
            re.search(r"You are Maez[^\n]*", body).group(0)[:120]
            if re.search(r"You are Maez[^\n]*", body)
            else body[:120]
        ),
    )


def probe_fast_reply() -> Optional[SurfaceFingerprint]:
    """Runtime probe of the fast-lane prompt builder — its
    compact_identity() function returns the canonical fast-lane
    identity. Body-truth-aware post-R4."""
    try:
        from core.infra import fast_prompt_builder as fpb
    except Exception:
        return None
    try:
        identity = fpb.compact_identity()
    except Exception:
        identity = getattr(fpb, "COMPACT_IDENTITY", "") or ""
    fast_file = REPO / "core" / "infra" / "fast_prompt_builder.py"
    src = fast_file.read_text(encoding="utf-8", errors="replace") \
        if fast_file.exists() else ""
    return SurfaceFingerprint(
        system_prompt_sha256=_sha256_of(identity),
        system_prompt_chars=len(identity),
        # Fast-lane is documented as audit-bypassing today — the
        # design said excluded by intent. R4 added body_capabilities
        # for the identity claim; the audit gate itself is still
        # not present (would inflate the fast-lane budget).
        audit_gate_present=(
            "self_claim_audit" in src
            or "audit_assistant_text" in src
        ),
        # Fast-lane intentionally excludes _TOOL_MANIFEST per its
        # docstring ("EXCLUDED on purpose").
        tool_manifest_present=("_TOOL_MANIFEST" in src),
        circadian_present=("circadian" in src.lower()),
        body_truth_present=("body_capabilities" in src),
        identity_excerpt=identity[:120],
    )


def probe_daemon_cycle() -> Optional[SurfaceFingerprint]:
    """Source-level probe of daemon/maez_daemon.py — the brain-loop
    cycle. Reads soul.md as the proxy system-prompt fingerprint
    (cycle appends soul + circadian + perception + capability
    snippet + recent action context)."""
    daemon_file = REPO / "daemon" / "maez_daemon.py"
    soul = REPO / "config" / "soul.md"
    if not daemon_file.exists() or not soul.exists():
        return None
    soul_text = soul.read_text(encoding="utf-8", errors="replace")
    src = daemon_file.read_text(encoding="utf-8", errors="replace")
    return SurfaceFingerprint(
        system_prompt_sha256=_sha256_of(soul_text),
        system_prompt_chars=len(soul_text),
        audit_gate_present=("self_claim_audit" in src),
        tool_manifest_present=(
            "_TOOL_MANIFEST" in src
            or "available_actions_prompt" in src
        ),
        circadian_present=("_get_circadian_context" in src),
        body_truth_present=(
            "capability_registry" in src
            or "body_capabilities" in src
            or "recent_action_context" in src
        ),
        identity_excerpt=soul_text[:120],
    )


def probe_web_owner() -> Optional[SurfaceFingerprint]:
    """Source-level probe of skills/web_interface.py — the /chat
    handler. Has its own owner-bridge / linked / guest prompt
    branches; we fingerprint the owner_system block from the
    chat() function."""
    wi_file = REPO / "skills" / "web_interface.py"
    if not wi_file.exists():
        return None
    src = wi_file.read_text(encoding="utf-8", errors="replace")
    # Extract the owner_system assignment block.
    m = re.search(
        r"owner_system\s*=\s*\((.*?)\)\s*\n",
        src, re.DOTALL,
    )
    body = m.group(1) if m else ""
    return SurfaceFingerprint(
        system_prompt_sha256=_sha256_of(body),
        system_prompt_chars=len(body),
        audit_gate_present=("audit_assistant_text" in src),
        tool_manifest_present=("_TOOL_MANIFEST" in src),
        circadian_present=("circadian" in src.lower()),
        body_truth_present=(
            "body_capabilities" in src
            or "_render_identity_reply" in src
        ),
        identity_excerpt=(
            re.search(r"You are[^\n]*", body).group(0)[:120]
            if body and re.search(r"You are[^\n]*", body)
            else body[:120]
        ),
    )


def probe_cli() -> Optional[SurfaceFingerprint]:
    """Source-level probe of cli/maez_chat.py — the CLI surface."""
    cli_file = REPO / "cli" / "maez_chat.py"
    soul = REPO / "config" / "soul.md"
    if not cli_file.exists() or not soul.exists():
        return None
    soul_text = soul.read_text(encoding="utf-8", errors="replace")
    src = cli_file.read_text(encoding="utf-8", errors="replace")
    return SurfaceFingerprint(
        system_prompt_sha256=_sha256_of(soul_text),
        system_prompt_chars=len(soul_text),
        audit_gate_present=("self_claim_audit" in src),
        tool_manifest_present=("_TOOL_MANIFEST" in src),
        circadian_present=("circadian" in src.lower()),
        body_truth_present=(
            "capability_registry" in src
            or "body_capabilities" in src
            or "prompt_snippet" in src
        ),
        identity_excerpt=soul_text[:120],
    )


# ── Public API ───────────────────────────────────────────────────────

_PROBES = {
    "telegram_owner": probe_telegram_owner,
    "telegram_public": probe_telegram_public,
    "fast_reply": probe_fast_reply,
    "daemon_cycle": probe_daemon_cycle,
    "web_owner": probe_web_owner,
    "cli": probe_cli,
}


def run_probe(*, baseline_id: Optional[str] = None) -> dict[str, Any]:
    """Run every reachable surface probe and return the baseline.

    Surfaces that fail to probe (file missing, import error, etc.)
    are silently omitted — the harness degrades gracefully so a
    partial baseline is still useful. The set of present surfaces
    is itself part of the baseline (subsequent runs that reach
    fewer surfaces show up as missing keys in the diff).
    """
    if baseline_id is None:
        baseline_id = time.strftime("%Y-%m-%d", time.gmtime())
    surfaces: dict[str, Any] = {}
    for name, probe in _PROBES.items():
        try:
            fp = probe()
        except Exception as e:
            logger.warning(
                "surface_probe(%s) failed: %s — omitting from baseline",
                name, e,
            )
            continue
        if fp is None:
            continue
        surfaces[name] = fp.to_dict()
    return {
        "baseline_id": baseline_id,
        "probed_at": time.time(),
        "natural_text_probes": list(NATURAL_TEXT_PROBES),
        "surfaces": surfaces,
    }


def diff_baselines(
    old: dict[str, Any], new: dict[str, Any],
) -> list[str]:
    """Return human-readable delta lines between two baselines.

    Surfaces present in one but missing in the other surface as
    add/drop lines. Per-surface axes that flipped surface as
    `<surface>.<axis>: <old> → <new>` lines.

    Returns [] when the two baselines are identical along every
    fingerprint axis.
    """
    deltas: list[str] = []
    old_surfaces = old.get("surfaces") or {}
    new_surfaces = new.get("surfaces") or {}

    # Surface-level drops / additions
    dropped = set(old_surfaces.keys()) - set(new_surfaces.keys())
    added = set(new_surfaces.keys()) - set(old_surfaces.keys())
    for name in sorted(dropped):
        deltas.append(f"DROPPED surface: {name}")
    for name in sorted(added):
        deltas.append(f"ADDED surface: {name}")

    # Per-axis flips on surfaces present in both
    for name in sorted(set(old_surfaces.keys()) & set(new_surfaces.keys())):
        old_fp = old_surfaces[name]
        new_fp = new_surfaces[name]
        for axis in sorted(set(old_fp.keys()) | set(new_fp.keys())):
            ov = old_fp.get(axis)
            nv = new_fp.get(axis)
            if ov != nv:
                # Hashes / long strings: show only first 16 chars in
                # the diff line to keep readable.
                ov_s = str(ov)[:60]
                nv_s = str(nv)[:60]
                deltas.append(
                    f"{name}.{axis}: {ov_s!r} → {nv_s!r}",
                )
    return deltas


def write_baseline(
    baseline: dict[str, Any], path: Path,
) -> None:
    """Serialize the baseline to JSON. Sort keys for stable diffs."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(baseline, indent=2, sort_keys=True, default=str)
        + "\n",
        encoding="utf-8",
    )


def read_baseline(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


# ── CLI ──────────────────────────────────────────────────────────────


def _default_baseline_path(baseline_id: str) -> Path:
    return (
        REPO / "docs" / "audit_symphony_2026-05-04"
        / "baselines" / f"surface_probe_{baseline_id}.json"
    )


def main(argv: Optional[list[str]] = None) -> int:
    import argparse
    p = argparse.ArgumentParser(
        prog="python -m core.symphony.surface_probe",
        description=(
            "Capture or diff the per-surface fingerprint baseline."
        ),
    )
    p.add_argument(
        "--baseline", default=None,
        help="Baseline ID (used as filename suffix and stored in "
             "the JSON). Defaults to today's UTC date.",
    )
    p.add_argument(
        "--write", action="store_true",
        help="Write the baseline to "
             "docs/audit_symphony_2026-05-04/baselines/.",
    )
    p.add_argument(
        "--compare", default=None,
        help="Path to an existing baseline JSON to diff against.",
    )
    args = p.parse_args(argv)

    baseline_id = args.baseline or time.strftime("%Y-%m-%d", time.gmtime())
    current = run_probe(baseline_id=baseline_id)

    if args.compare:
        old = read_baseline(Path(args.compare))
        deltas = diff_baselines(old, current)
        if not deltas:
            print(
                f"surface_probe: no drift against {args.compare} "
                f"({len(current['surfaces'])} surfaces probed)",
                file=sys.stderr,
            )
            return 0
        print(
            f"surface_probe: {len(deltas)} delta line(s) vs "
            f"{args.compare}:", file=sys.stderr,
        )
        for d in deltas:
            print(f"  - {d}")
        return 1

    output = json.dumps(
        current, indent=2, sort_keys=True, default=str,
    )
    if args.write:
        path = _default_baseline_path(baseline_id)
        write_baseline(current, path)
        rel = os.path.relpath(path, REPO)
        print(
            f"surface_probe: wrote baseline to {rel} "
            f"({len(current['surfaces'])} surfaces)",
            file=sys.stderr,
        )
    else:
        print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
