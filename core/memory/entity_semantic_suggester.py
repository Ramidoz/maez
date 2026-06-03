# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Semantic-mapping suggester + auditor (Step 5p).

Closes the two friction surfaces Step 5o exposed:

  1. Drafting NEW mappings: the operator should not have to
     ``sqlite3 memory/entity_index.db`` to find each entity's
     LLM-assigned ``kind`` before writing a mapping. The suggester
     emits draft YAML in the resolver's exact shape with the
     correct kind already filled in. The operator only needs to
     write the phrase.

  2. Validating EXISTING mappings: when the operator writes
     ``kind: hardware`` but the index records ``kind: concept``,
     the resolver silently warns and skips at recall time. Tonight's
     smoke proved this is a real silent-failure path. The auditor
     reads ``config/entity_semantics.local.yaml``, checks each
     target against the index, and surfaces kind mismatches +
     missing entities as ``AuditIssue`` records the operator can
     act on.

Hard contract:

  • No LLM, no network, no subprocess. Pure ix introspection.
  • No writes (suggester emits to stdout; auditor returns issues).
  • Cross-session filter on suggested entities: default
    ``min_sessions=2`` keeps the suggestion list focused on
    entities where MSEL would actually pay off (MSEL's value is
    cross-session evidence, not single-session bookmarks).
  • Output YAML round-trips through ``load_semantic_mappings``
    so the operator can sanity-check before editing — placeholder
    phrases are valid strings, not YAML structure markers.

Public API:

  suggest_semantic_drafts(*, ix, top_n=10, min_sessions=2)
                                       -> list[SemanticDraft]
  format_yaml(drafts)                  -> str
  audit_semantic_mappings(*, mappings, ix)
                                       -> list[AuditIssue]
  main(argv)                           -> int  # CLI
"""

from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.memory.entity_index import EntityIndex
    from core.memory.entity_semantic_resolver import SemanticMapping

logger = logging.getLogger(__name__)


# ── dataclasses ───────────────────────────────────────────────────


@dataclass
class SemanticDraft:
    """One draft mapping. ``phrase_placeholder`` is the operator-
    edits-this slot; the rest of the fields are pre-filled from
    the index so the operator never has to look up the kind."""
    canonical_name: str
    kind: str
    phrase_placeholder: str
    confidence: float = 1.0
    mention_count: int = 0
    distinct_sessions: int = 0
    notes: str = ""


@dataclass
class AuditIssue:
    """One auditor finding. ``code`` is one of:
       ``kind_mismatch`` — canonical exists but kind differs
       ``missing_entity`` — canonical absent from the index
       ``empty_target`` — schema-level shape failure (rare;
                          load_semantic_mappings would normally
                          catch this earlier)
    """
    code: str
    severity: str          # "warning" | "error"
    message: str
    canonical_name: str
    declared_kind: str
    suggested_kind: str | None = None  # populated for kind_mismatch
    phrase: str | None = None


# ── suggester ────────────────────────────────────────────────────


def suggest_semantic_drafts(
    *,
    ix: "EntityIndex",
    top_n: int = 10,
    min_sessions: int = 2,
) -> list[SemanticDraft]:
    """Return up to ``top_n`` draft mappings, ordered by mention
    count DESC. Filters out entities with fewer than
    ``min_sessions`` distinct mention sessions (default 2 — the
    cross-session-evidence floor MSEL is built around)."""
    with ix._connect() as con:
        rows = con.execute(
            "SELECT e.canonical_name AS canonical_name, "
            "       e.kind AS kind, "
            "       COUNT(m.id) AS mention_count, "
            "       COUNT(DISTINCT m.session_id) AS distinct_sessions "
            "FROM entities e LEFT JOIN entity_mentions m "
            "  ON m.entity_id = e.id "
            "GROUP BY e.id "
            "HAVING distinct_sessions >= ? "
            "ORDER BY mention_count DESC, e.canonical_name ASC "
            "LIMIT ?",
            (int(min_sessions), int(top_n)),
        ).fetchall()
    drafts: list[SemanticDraft] = []
    for r in rows:
        canonical = r["canonical_name"]
        notes_lines = [
            f"{r['mention_count']} mention(s) across "
            f"{r['distinct_sessions']} distinct session(s).",
            f"kind '{r['kind']}' filled from the index "
            "(extractor-assigned).",
            "Replace the placeholder phrase below with how you "
            "actually refer to this entity in conversation.",
        ]
        drafts.append(SemanticDraft(
            canonical_name=canonical,
            kind=r["kind"],
            phrase_placeholder=f"<your phrase for {canonical}>",
            confidence=1.0,
            mention_count=r["mention_count"],
            distinct_sessions=r["distinct_sessions"],
            notes="\n".join(notes_lines),
        ))
    return drafts


# ── YAML emission ────────────────────────────────────────────────


_LEAD_COMMENT = """\
# AUTO-GENERATED SEMANTIC-MAPPING DRAFTS — Step 5p.
#
# Each entry below is a HEURISTIC draft surfaced from
# memory/entity_index.db. The operator must:
#
#   1. Replace the placeholder ``phrase`` with how they actually
#      refer to the entity ("the firstborn", "the rig", "the
#      project"). The phrase MUST NOT appear verbatim in episode
#      text — that's the whole point of the semantic resolver.
#   2. Delete entries that don't represent useful semantic
#      bridges. Not every indexed entity needs an alternative
#      phrasing; only the ones the operator actually uses.
#   3. Save to config/entity_semantics.local.yaml.
#
# The ``kind`` field is pre-filled from the index — DO NOT change
# it unless you also re-classify the entity in the index. A
# mismatched kind causes the resolver to silently warn-and-skip
# at recall time. Run `python -m core.memory.entity_semantic_suggester
# --audit config/entity_semantics.local.yaml` to detect mismatches
# in an existing file.
"""


def _yaml_str(value: str) -> str:
    """Conservative double-quote with backslash-escapes."""
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def format_yaml(drafts: list[SemanticDraft]) -> str:
    """Emit drafts as a YAML document the resolver loader
    accepts. Placeholder phrases are valid YAML strings (so the
    operator can syntax-check the file before editing) but signal
    "edit me" via the surrounding-angle-bracket convention."""
    if not drafts:
        return _LEAD_COMMENT + "\nmappings: []\n"

    lines = [_LEAD_COMMENT, "mappings:"]
    for d in drafts:
        lines.append(f"  - phrase: {_yaml_str(d.phrase_placeholder)}")
        lines.append("    targets:")
        lines.append(
            f"      - canonical_name: {_yaml_str(d.canonical_name)}"
        )
        lines.append(f"        kind: {_yaml_str(d.kind)}")
        lines.append(f"    confidence: {d.confidence}")
        if d.notes:
            lines.append("    notes: |-")
            for note_line in d.notes.splitlines():
                lines.append(f"      {note_line}")
    return "\n".join(lines) + "\n"


# ── auditor ──────────────────────────────────────────────────────


def _lookup_canonical_only(ix, canonical_name: str) -> list[dict]:
    """Find entities with this normalized canonical_name across
    ALL kinds. Used by the auditor to detect kind mismatches —
    if there's no match anywhere, that's missing_entity; if
    there's a match at a different kind, that's kind_mismatch."""
    from core.memory.entity_index import normalize_entity_name

    normalized = normalize_entity_name(canonical_name)
    with ix._connect() as con:
        rows = con.execute(
            "SELECT id, canonical_name, kind FROM entities "
            "WHERE normalized_name = ?",
            (normalized,),
        ).fetchall()
    return [dict(r) for r in rows]


def audit_semantic_mappings(
    *,
    mappings: list["SemanticMapping"],
    ix: "EntityIndex",
) -> list[AuditIssue]:
    """Walk each mapping's targets and check each one against the
    index. Returns one ``AuditIssue`` per problematic target;
    clean mappings yield nothing."""
    issues: list[AuditIssue] = []
    for mapping in mappings:
        for target in mapping.targets:
            canonical = target.get("canonical_name", "")
            declared_kind = target.get("kind", "")
            if not canonical:
                issues.append(AuditIssue(
                    code="empty_target",
                    severity="error",
                    canonical_name="",
                    declared_kind=declared_kind,
                    phrase=mapping.phrase,
                    message=(
                        f"phrase {mapping.phrase!r}: target has no "
                        "canonical_name"
                    ),
                ))
                continue

            matches = _lookup_canonical_only(ix, canonical)
            if not matches:
                issues.append(AuditIssue(
                    code="missing_entity",
                    severity="error",
                    canonical_name=canonical,
                    declared_kind=declared_kind,
                    phrase=mapping.phrase,
                    message=(
                        f"phrase {mapping.phrase!r}: target "
                        f"({canonical!r}, {declared_kind!r}) is "
                        "not in the entity index. Run extraction "
                        "or seed the entity to make this resolvable."
                    ),
                ))
                continue

            kinds_present = [m["kind"] for m in matches]
            if declared_kind not in kinds_present:
                # Kind mismatch — index has the canonical at a
                # DIFFERENT kind. Suggest the most-mentions kind
                # if there's a tie.
                suggested = kinds_present[0]
                issues.append(AuditIssue(
                    code="kind_mismatch",
                    severity="warning",
                    canonical_name=canonical,
                    declared_kind=declared_kind,
                    suggested_kind=suggested,
                    phrase=mapping.phrase,
                    message=(
                        f"phrase {mapping.phrase!r}: target "
                        f"{canonical!r} declared kind "
                        f"{declared_kind!r}, but the index has it "
                        f"as {suggested!r}. The resolver will "
                        "silently warn and skip at recall time. "
                        f"Edit the mapping to kind: {suggested!r}."
                    ),
                ))
    return issues


# ── CLI ──────────────────────────────────────────────────────────


def _default_index_path() -> Path:
    try:
        from core import paths as _paths
        return _paths.memory_dir() / "entity_index.db"
    except Exception:
        return Path("memory/entity_index.db")


def _default_local_semantics_path() -> Path:
    try:
        from core import paths as _paths
        return _paths.home() / "config" / "entity_semantics.local.yaml"
    except Exception:
        return Path("config/entity_semantics.local.yaml")


_DISCLAIMER = (
    "HEURISTIC tool. Suggestions require operator review before "
    "merging into config/entity_semantics.local.yaml. The auditor "
    "checks an existing file for kind mismatches and missing "
    "entities; it does NOT mutate the file."
)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="python -m core.memory.entity_semantic_suggester",
        description=(
            "Suggest semantic-mapping drafts from the entity "
            "index, OR audit an existing semantics file for "
            "kind mismatches. No LLM, no network. Owner pastes / "
            "edits manually."
        ),
    )
    p.add_argument(
        "--audit", type=Path, default=None,
        help="Path to an existing semantics YAML file. When set, "
             "switches to audit mode (no suggestions printed).",
    )
    p.add_argument(
        "--index-db", type=Path, default=None,
        help="Override entity index DB (default: "
             "<memory>/entity_index.db).",
    )
    p.add_argument(
        "--top-n", type=int, default=10,
        help="Suggest the top-N entities by mention count "
             "(default: 10).",
    )
    p.add_argument(
        "--min-sessions", type=int, default=2,
        help="Filter suggestions to entities with at least N "
             "distinct mention sessions (default: 2 — cross-session "
             "evidence floor).",
    )
    args = p.parse_args(argv)

    print(f"NOTE: {_DISCLAIMER}", file=sys.stderr)

    ix_path = args.index_db or _default_index_path()
    if not Path(ix_path).exists():
        print(
            f"error: entity index not found at {ix_path}. "
            "Run extraction / backfill first.",
            file=sys.stderr,
        )
        return 2
    from core.memory.entity_index import EntityIndex

    ix = EntityIndex(ix_path)

    if args.audit is not None:
        if not Path(args.audit).exists():
            print(
                f"error: audit target {args.audit} not found",
                file=sys.stderr,
            )
            return 2
        from core.memory.entity_semantic_resolver import (
            SemanticConfigError, load_semantic_mappings,
        )
        try:
            mappings = load_semantic_mappings(args.audit)
        except SemanticConfigError as e:
            print(f"semantics file error: {e}", file=sys.stderr)
            return 2
        issues = audit_semantic_mappings(mappings=mappings, ix=ix)
        if not issues:
            print(
                f"clean: {len(mappings)} mapping(s) audited; "
                "no issues found.",
            )
            return 0
        print(f"found {len(issues)} issue(s):")
        for issue in issues:
            tag = f"[{issue.severity.upper()}] {issue.code}"
            print(f"  {tag} {issue.message}")
        return 2

    drafts = suggest_semantic_drafts(
        ix=ix,
        top_n=args.top_n,
        min_sessions=args.min_sessions,
    )
    if not drafts:
        print(
            "# no entities meet the suggestion criteria "
            f"(min_sessions={args.min_sessions}). Lower "
            "--min-sessions or run extraction first.",
            file=sys.stderr,
        )
        sys.stdout.write(_LEAD_COMMENT)
        sys.stdout.write("\nmappings: []\n")
        return 0

    sys.stdout.write(format_yaml(drafts))
    return 0


__all__ = [
    "AuditIssue",
    "SemanticDraft",
    "audit_semantic_mappings",
    "format_yaml",
    "main",
    "suggest_semantic_drafts",
]


if __name__ == "__main__":
    raise SystemExit(main())
