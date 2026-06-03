# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
"""Owner-curated entity alias seeding (Step 5g).

Reads a YAML file describing canonical entities and aliases and
upserts them into the Step-5e ``EntityIndex``. This is the cheap
first response to the Step-5f signal that the deterministic
extractor on its own is too sparse on real proper-noun entities.

Hard contract:

  • No LLM, no network, no subprocess. Pinned by tests that
    intercept ``subprocess.run`` / ``socket.socket``.
  • No mentions are created. Alias seeding adds the resolution
    layer (entities + aliases), not evidence (mentions). That
    keeps the pipeline honest — a mention is a pointer to a
    specific session/source, and seeding a name doesn't witness
    it appearing anywhere.
  • Ambiguity follows Step 5e: the same alias may map to multiple
    entities, and ``find_entities`` divides confidence
    accordingly. The seeder doesn't refuse cross-entity alias
    collision — it surfaces the ambiguity in the report.
  • Dry-run is the default. ``--write`` opt-in is required to
    commit. Same posture as the backfill (Step 5f).

YAML schema:

    entities:
      - canonical_name: "Maya Ananthan"
        kind: "person"
        aliases: ["Maya"]
        notes: "owner-curated alias"
      - canonical_name: "Track A"
        kind: "project"
        aliases: ["Track A readiness", "firstborn readiness"]

Top-level must be a mapping with an ``entities`` key whose value
is a list of mappings; ``canonical_name`` and ``kind`` are
required, ``aliases`` is an optional list of non-empty strings,
``notes`` is free-form. Duplicate ``(canonical_name, kind)``
pairs in the same file are an error.
"""

from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

if TYPE_CHECKING:
    from core.memory.entity_index import EntityIndex

logger = logging.getLogger(__name__)


# ── exceptions / dataclasses ──────────────────────────────────────


class SeedFileError(ValueError):
    """Raised when the seed file is malformed: invalid YAML, wrong
    top-level shape, missing required fields, non-string aliases,
    or duplicate (canonical_name, kind) pairs in the same file."""


@dataclass
class SeedEntity:
    """One parsed entity entry from the seed file."""
    canonical_name: str
    kind: str
    aliases: list[str] = field(default_factory=list)
    notes: str | None = None


@dataclass
class SeedReport:
    """Summary of one seed run. ``ambiguous_aliases_after_seed`` is
    the metric that matters most — counts distinct ``normalized_alias``
    values claimed by ≥2 entities post-seed. A high value means more
    of the index's resolution surface is ambiguous and ``expand_query``
    will return split-confidence matches in those cases."""
    entities_seen: int = 0
    entities_created: int = 0
    entities_existing: int = 0
    aliases_added: int = 0
    aliases_existing: int = 0
    ambiguous_aliases_after_seed: int = 0
    write_mode: bool = False
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def render_text(self) -> str:
        """CLI-friendly rendering. Disclaimer-led."""
        head = (
            "WRITE MODE — alias seed committed to entity_index.db."
            if self.write_mode
            else "DRY RUN — no writes occurred. Use --write to commit."
        )
        lines = [head, ""]
        lines.append(f"entities seen:                 {self.entities_seen}")
        lines.append(f"entities created:              {self.entities_created}")
        lines.append(f"entities existing:             {self.entities_existing}")
        lines.append(f"aliases added:                 {self.aliases_added}")
        lines.append(f"aliases already present:       {self.aliases_existing}")
        lines.append(
            f"ambiguous aliases after seed:  "
            f"{self.ambiguous_aliases_after_seed}"
        )
        if self.warnings:
            lines.append("")
            lines.append("warnings:")
            for w in self.warnings:
                lines.append(f"  - {w}")
        if self.errors:
            lines.append("")
            lines.append("errors:")
            for e in self.errors:
                lines.append(f"  - {e}")
        return "\n".join(lines)


# ── load + validate ───────────────────────────────────────────────


def _validate_entry(raw: object, idx: int) -> SeedEntity:
    """Turn one YAML mapping into a ``SeedEntity`` with strict
    validation. The error messages name the offending index so a
    bad seed file is debuggable in seconds."""
    if not isinstance(raw, dict):
        raise SeedFileError(
            f"entities[{idx}] must be a YAML mapping, got "
            f"{type(raw).__name__}"
        )
    canonical_name = raw.get("canonical_name")
    if not isinstance(canonical_name, str) or not canonical_name.strip():
        raise SeedFileError(
            f"entities[{idx}] missing required string "
            "'canonical_name'"
        )
    kind = raw.get("kind")
    if not isinstance(kind, str) or not kind.strip():
        raise SeedFileError(
            f"entities[{idx}] ({canonical_name!r}) missing required "
            "string 'kind'"
        )

    aliases_raw = raw.get("aliases", [])
    if aliases_raw is None:
        aliases_raw = []
    if not isinstance(aliases_raw, list):
        raise SeedFileError(
            f"entities[{idx}] ({canonical_name!r}) 'aliases' must be "
            f"a list, got {type(aliases_raw).__name__}"
        )
    aliases: list[str] = []
    for j, a in enumerate(aliases_raw):
        if not isinstance(a, str):
            raise SeedFileError(
                f"entities[{idx}] ({canonical_name!r}) aliases[{j}] "
                f"must be a string, got {type(a).__name__}"
            )
        if not a.strip():
            raise SeedFileError(
                f"entities[{idx}] ({canonical_name!r}) aliases[{j}] "
                "is empty"
            )
        aliases.append(a)

    notes = raw.get("notes")
    if notes is not None and not isinstance(notes, str):
        raise SeedFileError(
            f"entities[{idx}] ({canonical_name!r}) 'notes' must be "
            f"a string or absent, got {type(notes).__name__}"
        )

    return SeedEntity(
        canonical_name=canonical_name.strip(),
        kind=kind.strip(),
        aliases=aliases,
        notes=notes,
    )


def load_seed_file(path: Path | str) -> list[SeedEntity]:
    """Parse and validate a seed YAML file. Raises ``SeedFileError``
    on any malformed input; returns a deterministic list of
    ``SeedEntity`` records on success.

    Duplicate ``(canonical_name, kind)`` pairs in the same file are
    rejected — they're a config error, not an idempotency case;
    re-running the seeder hits the index's UNIQUE constraint and
    that's the right place for cross-run dedup."""
    p = Path(path)
    try:
        raw = yaml.safe_load(p.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        raise SeedFileError(
            f"could not parse {p} as YAML: {e}"
        ) from e
    except OSError as e:
        raise SeedFileError(f"could not read {p}: {e}") from e

    if not isinstance(raw, dict):
        raise SeedFileError(
            f"{p}: top-level must be a mapping, got "
            f"{type(raw).__name__}"
        )
    if "entities" not in raw:
        raise SeedFileError(f"{p}: missing required key 'entities'")
    entries_raw = raw["entities"]
    if not isinstance(entries_raw, list):
        raise SeedFileError(
            f"{p}: 'entities' must be a list, got "
            f"{type(entries_raw).__name__}"
        )

    entries: list[SeedEntity] = []
    seen_keys: set[tuple[str, str]] = set()
    for i, item in enumerate(entries_raw):
        entry = _validate_entry(item, i)
        # Use normalized name for the dup check so capitalization
        # variants in the same file are caught.
        from core.memory.entity_index import normalize_entity_name
        key = (normalize_entity_name(entry.canonical_name), entry.kind)
        if key in seen_keys:
            raise SeedFileError(
                f"{p}: duplicate entry for "
                f"({entry.canonical_name!r}, {entry.kind!r}) at "
                f"entities[{i}]"
            )
        seen_keys.add(key)
        entries.append(entry)
    return entries


# ── seed (dry-run / write) ────────────────────────────────────────


def _count_ambiguous_aliases(ix: "EntityIndex") -> int:
    """Distinct normalized_alias values claimed by ≥2 entities.
    The MSEL-precision pressure metric: high count means the index's
    resolution surface is ambiguous and expand_query will split
    confidence on those queries."""
    with ix._connect() as con:
        rows = con.execute(
            "SELECT normalized_alias, COUNT(DISTINCT entity_id) AS n "
            "FROM aliases GROUP BY normalized_alias HAVING n >= 2"
        ).fetchall()
    return len(rows)


def _alias_already_present(
    ix: "EntityIndex", entity_id: str, alias: str,
) -> bool:
    from core.memory.entity_index import normalize_entity_name

    normalized = normalize_entity_name(alias)
    if not normalized:
        return False
    with ix._connect() as con:
        row = con.execute(
            "SELECT id FROM aliases "
            "WHERE entity_id = ? AND normalized_alias = ?",
            (entity_id, normalized),
        ).fetchone()
    return row is not None


def seed_aliases(
    *,
    ix: "EntityIndex",
    entries: list[SeedEntity],
    write: bool = False,
) -> SeedReport:
    """Apply the seed entries to the entity index.

    Default ``write=False`` is the dry-run path: nothing is inserted,
    but the report still computes honest "would-create" / "would-add"
    counts by checking existence per (entity, alias) before writing."""
    from core.memory.entity_index import normalize_entity_name

    report = SeedReport(write_mode=write, entities_seen=len(entries))

    # Snapshot existing entity keyset and per-entity alias keyset
    # so dry-run accounting matches what a write would do.
    with ix._connect() as con:
        _entity_rows = con.execute(
            "SELECT id, normalized_name, kind FROM entities"
        ).fetchall()
        _alias_rows = con.execute(
            "SELECT entity_id, normalized_alias FROM aliases"
        ).fetchall()
    existing_entities: dict[tuple[str, str], str] = {}
    for row in _entity_rows:
        existing_entities[(row["normalized_name"], row["kind"])] = row["id"]
    existing_aliases: set[tuple[str, str]] = set()
    for row in _alias_rows:
        existing_aliases.add((row["entity_id"], row["normalized_alias"]))

    # Plan first; execute only when write=True.
    planned_alias_keys: set[tuple[str, str]] = set()
    for entry in entries:
        norm = normalize_entity_name(entry.canonical_name)
        if not norm:
            report.warnings.append(
                f"{entry.canonical_name!r} normalizes to empty; "
                "skipped"
            )
            continue
        key = (norm, entry.kind)
        ent_id = existing_entities.get(key)
        if ent_id is None:
            report.entities_created += 1
            ent_id = f"<planned:{norm}:{entry.kind}>"
        else:
            report.entities_existing += 1

        if write and ent_id.startswith("<planned:"):
            ent_id = ix.upsert_entity(
                entry.canonical_name, kind=entry.kind,
            )
            existing_entities[key] = ent_id

        for alias in entry.aliases:
            normalized_alias = normalize_entity_name(alias)
            if not normalized_alias:
                report.warnings.append(
                    f"{entry.canonical_name!r}: alias {alias!r} "
                    "normalizes to empty; skipped"
                )
                continue
            alias_key = (ent_id, normalized_alias)
            if alias_key in existing_aliases or alias_key in planned_alias_keys:
                report.aliases_existing += 1
                continue
            planned_alias_keys.add(alias_key)
            report.aliases_added += 1
            if write:
                ix.add_alias(ent_id, alias)

    report.ambiguous_aliases_after_seed = _count_ambiguous_aliases(ix)
    return report


# ── CLI ───────────────────────────────────────────────────────────


def _default_seed_path() -> Path:
    """Default path: ``config/entity_aliases.local.yaml`` (gitignored,
    owner-private). The example file at
    ``docs/entity_aliases.example.yaml`` is committed but contains
    only fixture data."""
    try:
        from core import paths as _paths
        return _paths.home() / "config" / "entity_aliases.local.yaml"
    except Exception:
        return Path("config/entity_aliases.local.yaml")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="python -m core.memory.entity_alias_seed",
        description=(
            "Seed owner-curated entity aliases from a YAML file into "
            "memory/entity_index.db. Adds entities and aliases only; "
            "no mentions are created. Dry-run by default."
        ),
    )
    p.add_argument(
        "--file", "-f", type=Path, default=None,
        help="Seed YAML file (default: "
             "config/entity_aliases.local.yaml).",
    )
    p.add_argument(
        "--index-db", type=Path, default=None,
        help="Override entity index DB path (default: "
             "memory/entity_index.db).",
    )
    p.add_argument(
        "--write", action="store_true",
        help="Commit to entity_index.db. Without this flag, the run "
             "is a dry run.",
    )
    p.add_argument(
        "--dry-run", action="store_true",
        help="Explicit dry-run (default). Provided for symmetry "
             "with --write.",
    )
    args = p.parse_args(argv)

    if args.write and args.dry_run:
        print(
            "error: --write and --dry-run are mutually exclusive",
            file=sys.stderr,
        )
        return 2

    seed_path = args.file or _default_seed_path()
    if not Path(seed_path).exists():
        print(
            f"error: seed file not found at {seed_path}\n"
            f"hint: copy docs/entity_aliases.example.yaml to "
            f"{seed_path} and edit, or pass --file to override.",
            file=sys.stderr,
        )
        return 2

    try:
        entries = load_seed_file(seed_path)
    except SeedFileError as e:
        print(f"seed file error: {e}", file=sys.stderr)
        return 2

    from core.memory.entity_index import EntityIndex

    ix = (
        EntityIndex(args.index_db) if args.index_db else EntityIndex()
    )
    report = seed_aliases(ix=ix, entries=entries, write=bool(args.write))
    print(report.render_text())
    if not args.write:
        print(
            "\nNOTE: dry-run only. Re-run with --write to commit. "
            "The seeder never creates mentions and never calls "
            "subprocess or network.",
            file=sys.stderr,
        )
    return 0


__all__ = [
    "SeedEntity",
    "SeedFileError",
    "SeedReport",
    "load_seed_file",
    "main",
    "seed_aliases",
]


if __name__ == "__main__":
    raise SystemExit(main())
