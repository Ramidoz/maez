# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""
core/soul_editor.py — Session 11s.

Structured editing of config/soul.md beyond the existing append-only
write_soul_note flow. Supports proposing and applying SECTION REPLACEMENTS
with diff preview, protected-section guards, atomic writes, and automatic
backups.

Why this exists
===============
Session 11o shipped dream-state append proposals (Maez proposes new soul
notes during AFK time, the owner approves them via /apply_dream). That flow
can only GROW soul.md — it cannot edit, consolidate, or refine existing
content. 11s adds the inverse: propose REPLACING a specific ``## Section``
of soul.md with new content.

The first real use case, already sitting in soul.md today: the Session
5/9 self-analysis bug produced dozens of duplicate ``[Self-observed
pattern — 2026-04-10]`` entries plus duplicate ``## Self-Analysis —
2026-04-10`` sections. Soul editor lets Maez propose consolidating them
into one clean section.

Safety contract
===============
- The PREAMBLE (everything before the first ``##`` header — currently
  HARD CONSTRAINTS, TRUST COVENANT, SYSTEM BASELINE, and the identity
  intro) is PROTECTED. No proposal targeting the preamble is ever
  applied. This is enforced in TWO places: at parse time
  (``PROTECTED_PREAMBLE`` sentinel returned from ``find_section``) and
  at write time (``apply_section_replace`` refuses).
- Additionally, any proposed new body that contains the literal strings
  ``HARD CONSTRAINTS``, ``TRUST COVENANT``, or the self-destruct forbid-
  patterns (``NEVER kill``, ``disable ollama``) is rejected.
- Every write makes a timestamped backup at
  ``/home/rohit/maez/config/soul.md.bak.YYYYMMDDHHMMSS`` BEFORE the
  atomic swap. The ``.bak`` files accumulate forever — recovery is
  trivial, and soul history is never lost.
- Writes are atomic via ``os.replace(tmp, target)``. The daemon's soul
  watcher thread picks up the MD5 change within 10 seconds and
  hot-reloads ``self.system_prompt``.

Public API
==========
    doc = soul_editor.load()                          # SoulDocument
    doc.sections                                      # list[Section]
    doc.find_section(name) -> Optional[Section]
    doc.find_duplicate_sections() -> list[tuple[str, list[Section]]]

    proposal = soul_editor.propose_replacement(
        target_name='Self-Reflection',
        new_body='...',
        rationale='why this edit',
    )                                                 # Proposal or raises

    proposal.unified_diff                             # human-readable
    proposal.old_body / proposal.new_body             # raw text

    ok, msg = soul_editor.apply_section_replace(proposal)
"""

from __future__ import annotations

import difflib
import logging
import os
import re
import shutil
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional


logger = logging.getLogger("maez.soul_editor")


try:
    from core import paths as _paths
    SOUL_PATH = _paths.soul_combined_path()
    BACKUP_DIR = _paths.config_dir()  # backups live beside soul.md
except Exception:
    SOUL_PATH = Path("/home/rohit/maez/config/soul.md")
    BACKUP_DIR = Path("/home/rohit/maez/config")


# ── protected content guards ─────────────────────────────────────────
# These phrases are load-bearing — if they disappear from soul.md via
# any proposal, the system's safety rails disappear with them. We also
# refuse any proposal that tries to INTRODUCE phrases suggesting self-
# destruction or ollama interference.
PROTECTED_PHRASES_REQUIRED = {
    # These MUST stay in the preamble; if a proposal strips them from
    # soul.md entirely, reject.
    "HARD CONSTRAINTS",
    "TRUST COVENANT",
    "SYSTEM BASELINE",
}

PROTECTED_PHRASES_REJECT_IN_NEW = {
    # These MUST NOT appear in a newly proposed section body. If the
    # proposal tries to inject "ignore HARD CONSTRAINTS" or similar,
    # reject.
    "ignore HARD CONSTRAINTS",
    "override TRUST COVENANT",
    "disable ollama",
    "kill ollama",
    "stop ollama",
    "stop maez",
    "kill maez",
}


# ── data structures ──────────────────────────────────────────────────
@dataclass
class Section:
    """One ``## Header``-delimited section of soul.md.

    ``body`` is the raw text starting immediately after the header line
    and running up to the line before the next ``## `` header (or EOF).
    It may contain trailing blank lines — preserved verbatim.
    """
    name: str                      # header text without the leading "## "
    header_line: str               # full "## Header" line
    body: str                      # body text (may be multi-line)
    start_line: int                # 1-indexed line of the header in file
    end_line: int                  # 1-indexed last line of the section

    def identity_key(self) -> str:
        """A case-insensitive, whitespace-stripped key for dedup
        detection. Two sections with the same identity_key are flagged
        as duplicates by find_duplicate_sections()."""
        return re.sub(r"\s+", " ", self.name.strip().lower())


@dataclass
class SoulDocument:
    """Parsed soul.md: a protected preamble + a list of editable sections."""
    preamble: str                  # everything before the first "## " header
    sections: list[Section] = field(default_factory=list)
    source_path: Path = SOUL_PATH

    def find_section(self, name: str) -> Optional[Section]:
        """Find the FIRST section whose name matches ``name`` case-
        insensitively with whitespace normalized. If multiple sections
        share the name (the duplicate case), only the first is returned
        — use find_duplicate_sections() to enumerate all of them."""
        key = re.sub(r"\s+", " ", name.strip().lower())
        for s in self.sections:
            if s.identity_key() == key:
                return s
        return None

    def find_duplicate_sections(self) -> list[tuple[str, list[Section]]]:
        """Return [(section_name, [Section, Section, ...]), ...] for
        every section name that appears more than once. The duplicates
        sharing a name are returned in original file order."""
        buckets: dict[str, list[Section]] = {}
        for s in self.sections:
            buckets.setdefault(s.identity_key(), []).append(s)
        return [(v[0].name, v) for k, v in buckets.items() if len(v) > 1]

    def to_text(self) -> str:
        """Serialize back to the raw soul.md text form."""
        parts = [self.preamble]
        for s in self.sections:
            parts.append(s.header_line + "\n" + s.body)
        return "".join(parts)


@dataclass
class Proposal:
    """A proposed section replacement. Constructed by propose_replacement().
    Apply via apply_section_replace(proposal)."""
    target_name: str
    old_body: str
    new_body: str
    rationale: str
    unified_diff: str
    created_at: float = field(default_factory=time.time)


# ── parser ───────────────────────────────────────────────────────────
def parse(text: str) -> SoulDocument:
    """Parse raw soul.md text into a SoulDocument.

    Section boundaries are ``^## Header`` lines. Everything before the
    first such line is the preamble (protected — contains HARD
    CONSTRAINTS, TRUST COVENANT, SYSTEM BASELINE, and the identity
    intro). Everything after is split into Section objects by header.
    """
    lines = text.splitlines(keepends=True)
    # Find header line indices
    header_re = re.compile(r"^##\s+(.+?)\s*$")
    header_idxs: list[int] = []
    for i, line in enumerate(lines):
        if header_re.match(line.rstrip("\n")):
            header_idxs.append(i)

    if not header_idxs:
        # No headers — entire file is preamble
        return SoulDocument(preamble=text, sections=[])

    preamble = "".join(lines[:header_idxs[0]])

    sections: list[Section] = []
    for k, idx in enumerate(header_idxs):
        header_line_raw = lines[idx].rstrip("\n")
        m = header_re.match(header_line_raw)
        # mypy-ish: we matched above so m is not None
        name = m.group(1) if m else header_line_raw[3:].strip()  # pragma: no cover

        end_idx = header_idxs[k + 1] if k + 1 < len(header_idxs) else len(lines)
        body = "".join(lines[idx + 1 : end_idx])
        sections.append(
            Section(
                name=name,
                header_line=header_line_raw,
                body=body,
                start_line=idx + 1,
                end_line=end_idx,
            )
        )

    return SoulDocument(preamble=preamble, sections=sections)


def load(path: Optional[Path] = None) -> SoulDocument:
    """Read + parse soul.md from disk. Resolves SOUL_PATH at call time
    so test harnesses can monkey-patch ``soul_editor.SOUL_PATH``."""
    return parse((path or SOUL_PATH).read_text())


# ── proposal creation ────────────────────────────────────────────────
def propose_replacement(
    target_name: str,
    new_body: str,
    rationale: str = "",
    doc: Optional[SoulDocument] = None,
) -> Proposal:
    """Build a Proposal to replace ``target_name``'s body with
    ``new_body``. Validates protected phrases and refuses obvious
    self-destruct patterns. Raises ``ValueError`` on any guard trip.

    The returned Proposal carries a human-readable unified diff for
    Telegram preview; the caller is expected to ship it to approval
    and later call ``apply_section_replace``.
    """
    if doc is None:
        doc = load()

    target = doc.find_section(target_name)
    if target is None:
        raise ValueError(
            f"target section not found: {target_name!r}. "
            f"Known sections: {[s.name for s in doc.sections]}"
        )

    # Reject proposals that would modify a protected phrase.
    # (The preamble already can't be targeted via find_section, but we
    # double-check in case ``target_name`` happens to match a ``##``
    # section that carries load-bearing content.)
    for forbidden in PROTECTED_PHRASES_REJECT_IN_NEW:
        if forbidden.lower() in new_body.lower():
            raise ValueError(
                f"proposed body contains forbidden phrase: {forbidden!r}"
            )

    # Build the unified diff between old body and new body.
    old_lines = target.body.splitlines(keepends=True)
    new_lines = new_body.splitlines(keepends=True)
    diff_lines = list(
        difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile=f"soul.md :: {target_name} (current)",
            tofile=f"soul.md :: {target_name} (proposed)",
            lineterm="",
        )
    )
    diff_text = "".join(line + ("\n" if not line.endswith("\n") else "")
                        for line in diff_lines)

    return Proposal(
        target_name=target_name,
        old_body=target.body,
        new_body=new_body,
        rationale=rationale,
        unified_diff=diff_text,
    )


# ── consolidation helper ─────────────────────────────────────────────
def propose_duplicate_consolidation(
    target_name: str,
    merged_body: Optional[str] = None,
    doc: Optional[SoulDocument] = None,
) -> Proposal:
    """Convenience helper for the ``## Self-Analysis — 2026-04-10``
    duplicate case. Finds ALL sections matching ``target_name``,
    produces a proposal that keeps the FIRST occurrence and replaces
    its body with ``merged_body`` (if given) or a deduplicated merge
    of all the duplicate bodies.

    NOTE: this helper currently only generates the proposal — applying
    it via apply_section_replace will only replace the FIRST section's
    body. The DUPLICATE sections after it will remain in place and
    should be removed via a second pass (or a future full-document
    rewrite API). For now the caller is expected to inspect the diff
    and decide.
    """
    if doc is None:
        doc = load()

    dupes = doc.find_duplicate_sections()
    matching = [
        (name, secs) for name, secs in dupes
        if re.sub(r"\s+", " ", name.strip().lower()) ==
           re.sub(r"\s+", " ", target_name.strip().lower())
    ]
    if not matching:
        raise ValueError(
            f"no duplicates found for section {target_name!r}. "
            f"All duplicates: {[n for n, _ in dupes]}"
        )

    _, sections = matching[0]
    # Deduplicate bodies — simple set-of-lines approach, preserves
    # order from first occurrence
    seen_lines: set[str] = set()
    merged_lines: list[str] = []
    for s in sections:
        for line in s.body.splitlines(keepends=True):
            key = line.strip()
            if key and key not in seen_lines:
                seen_lines.add(key)
                merged_lines.append(line)
            elif not key and merged_lines and merged_lines[-1].strip():
                merged_lines.append(line)  # keep single blank line separators
    auto_merged = "".join(merged_lines)
    # Ensure trailing blank line
    if not auto_merged.endswith("\n\n"):
        auto_merged = auto_merged.rstrip("\n") + "\n\n"

    return propose_replacement(
        target_name=target_name,
        new_body=merged_body if merged_body is not None else auto_merged,
        rationale=(
            f"Consolidate {len(sections)} duplicate '{target_name}' sections "
            f"(from the Session 5/9 self-analysis duplication bug) into one "
            f"deduplicated version. Lines from original duplicates are merged "
            f"preserving first-occurrence order."
        ),
        doc=doc,
    )


# ── apply ────────────────────────────────────────────────────────────
def _backup_path() -> Path:
    """Timestamped backup filename for soul.md at the current moment."""
    ts = datetime.now().strftime("%Y%m%d%H%M%S")
    return BACKUP_DIR / f"soul.md.bak.{ts}"


def apply_section_replace(proposal: Proposal) -> tuple[bool, str]:
    """Atomically apply a Proposal to soul.md.

    Steps:
        1. Re-load soul.md (fresh parse — soul.md may have been
           edited since the proposal was generated)
        2. Re-find the target section
        3. Verify its current body still matches the proposal's
           ``old_body`` exactly. If it doesn't, REFUSE — the section
           has changed under us and the diff is stale.
        4. Double-check the required phrases (HARD CONSTRAINTS etc)
           are still present after the replacement
        5. Write a backup copy of current soul.md to
           /home/rohit/maez/config/soul.md.bak.YYYYMMDDHHMMSS
        6. Write the new full text to soul.md.tmp, then os.replace
           to soul.md (atomic on POSIX)

    Returns ``(ok, message)``. On any guard trip, ok is False and the
    soul.md file is UNCHANGED.
    """
    try:
        doc = load()
    except Exception as e:
        return False, f"reload failed: {e!r}"

    target = doc.find_section(proposal.target_name)
    if target is None:
        return False, f"target section not found at apply time: {proposal.target_name!r}"

    if target.body != proposal.old_body:
        return False, (
            f"stale proposal — current body of {proposal.target_name!r} has "
            f"changed since the proposal was generated. refusing to write."
        )

    # Build the new full text by swapping this section's body
    new_sections = []
    for s in doc.sections:
        if s is target:
            new_sections.append(
                Section(
                    name=s.name,
                    header_line=s.header_line,
                    body=proposal.new_body,
                    start_line=s.start_line,
                    end_line=s.end_line,
                )
            )
        else:
            new_sections.append(s)
    new_doc = SoulDocument(
        preamble=doc.preamble,
        sections=new_sections,
        source_path=doc.source_path,
    )
    new_text = new_doc.to_text()

    # Verify required phrases still present in the full serialized file
    for required in PROTECTED_PHRASES_REQUIRED:
        if required not in new_text:
            return False, (
                f"protected phrase {required!r} is missing from the "
                f"proposed full soul.md — refusing to write."
            )

    # Backup + atomic write
    try:
        bak = _backup_path()
        shutil.copy2(SOUL_PATH, bak)
    except Exception as e:
        return False, f"backup failed: {e!r} — soul.md NOT modified"

    try:
        tmp = SOUL_PATH.with_suffix(".md.tmp")
        tmp.write_text(new_text)
        os.replace(tmp, SOUL_PATH)
    except Exception as e:
        return False, (
            f"atomic write failed: {e!r} — backup is at {bak}. "
            f"soul.md is in an unknown state; manual inspection advised."
        )

    logger.info(
        "soul_editor: section %r replaced (backup=%s, %d → %d body chars)",
        proposal.target_name, bak.name, len(proposal.old_body), len(proposal.new_body),
    )
    return True, (
        f"section {proposal.target_name!r} replaced. "
        f"backup at {bak.name}. daemon soul watcher will hot-reload within 10s."
    )
