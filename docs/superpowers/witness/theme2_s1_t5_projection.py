#!/usr/bin/env python3
"""Theme 2 S1 — T5 invariance projection (protocol §12.8, rev per gate round 12).

Raw byte equality between two runs is impossible: every store on the reply
path stamps uuid4() and a wall clock. This tool computes the projection the
protocol pre-registers.

    project  <tree> <out.json>
    volatile <a.json> <b.json> <out.json>     # from the two BASELINE runs
    compare  <a.json> <b.json> <volatile.json> [--ledger-sha SHA]

Gate round 12 closed four defects in the first version, and the fixes are
the substance of this file:

  D1  Volatile fields are ORDINALIZED, never dropped. Dropping a column
      makes every change inside it invisible -- S1 could zero every
      timestamp in the tree and the comparison would still report
      equality. Ranking preserves cardinality, ordering, uniqueness and
      monotonicity, so a collapse shows up as a rank-structure change.
  D2  Non-database files are compared by sha256 and a difference is a
      KILL, not a note. An HNSW graph rebuilt with a different topology
      is a real behavior change.
  D3  -wal/-shm sidecars are named explicitly: presence is compared,
      bytes are not. They are checkpoint-timing artifacts. Their
      existence is expected -- a read-only open of a WAL database
      creates them (envelope_builder.py:268, recent_turns.py:97).
  E1  The volatility classifier is an exact grammar with frozen units
      and ranges, and row alignment is a defined procedure rather than
      an unstated assumption.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import sys
from pathlib import Path

# ── frozen grammar (E1). Shape only — no field-name heuristics, because a
#    name-based rule is exactly the discretion gate round 12 objected to. ──

UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
BARE_HEX_RE = re.compile(r"^[0-9a-f]{12,64}$")
PREFIXED_HEX_RE = re.compile(r"^[a-z][a-z0-9_]*-[0-9a-f]{8,32}$")
ISO8601_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:?\d{2})?$")

# Unix seconds 2020-09-13 .. 2052-06-07, and the same window in
# milliseconds. Anything outside these two windows is NOT time-shaped,
# whatever it is called.
SEC_MIN, SEC_MAX = 1_600_000_000, 2_600_000_000
MS_MIN, MS_MAX = SEC_MIN * 1000, SEC_MAX * 1000

SQLITE_SUFFIXES = (".db", ".sqlite3", ".sqlite")
SIDECAR_RE = re.compile(r".*\.(db|sqlite3|sqlite)-(wal|shm)$")
MAX_ROWS_PER_TABLE = 200_000


def is_uuid_shaped(v) -> bool:
    return isinstance(v, str) and bool(
        UUID_RE.match(v) or BARE_HEX_RE.match(v) or PREFIXED_HEX_RE.match(v))


def is_time_shaped(v) -> bool:
    if isinstance(v, bool):
        return False
    if isinstance(v, (int, float)):
        f = float(v)
        return SEC_MIN <= f <= SEC_MAX or MS_MIN <= f <= MS_MAX
    return isinstance(v, str) and bool(ISO8601_RE.match(v))


def canonical_path(rel: str, uuid_map: dict) -> str:
    parts = []
    for p in Path(rel).parts:
        parts.append(uuid_map.setdefault(p, f"<uuid:{len(uuid_map)}>")
                     if UUID_RE.match(p) else p)
    return "/".join(parts)


# ── projection ────────────────────────────────────────────────────────────

def project_sqlite(path: Path) -> dict:
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro&immutable=1", uri=True)
    except sqlite3.Error as e:
        return {"error": f"{type(e).__name__}: {e}"}
    out: dict = {"schema": [], "pragmas": {}, "tables": {}}
    try:
        out["schema"] = [list(r) for r in conn.execute(
            "SELECT name, type, sql FROM sqlite_master ORDER BY name, type")]
        # D2: an unprojected pragma change is a real behavior change.
        for pr in ("user_version", "application_id", "page_size",
                   "journal_mode", "encoding"):
            try:
                out["pragmas"][pr] = conn.execute(f"PRAGMA {pr}").fetchone()[0]
            except sqlite3.Error:
                out["pragmas"][pr] = None
        names = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
        for t in names:
            cols = [r[1] for r in conn.execute(f'PRAGMA table_info("{t}")')]
            rows = [list(r) for r in conn.execute(f'SELECT * FROM "{t}"')]
            if len(rows) > MAX_ROWS_PER_TABLE:
                out["tables"][t] = {"error": f"row cap exceeded: {len(rows)}"}
                continue
            out["tables"][t] = {"columns": cols, "count": len(rows),
                                "rows": rows}
    finally:
        conn.close()
    return out


def project_tree(tree: Path, seeded: set[str]) -> dict:
    uuid_map: dict = {}
    sqlites, blobs, sidecars, seeded_seen = {}, {}, [], []
    for p in sorted(tree.rglob("*")):
        if not p.is_file():
            continue
        rel = str(p.relative_to(tree))
        cp = canonical_path(rel, uuid_map)
        if rel in seeded:
            # Seeded package sources: code, not store. Copied read-only from
            # the repo so the reply machinery can import at all.
            seeded_seen.append(rel)
            continue
        if SIDECAR_RE.match(rel):
            sidecars.append(cp)                      # D3: presence only
            continue
        if p.suffix in SQLITE_SUFFIXES:
            sqlites[cp] = project_sqlite(p)
        else:
            blobs[cp] = {"size": p.stat().st_size,
                         "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
    latch = sorted(canonical_path(str(p.relative_to(tree)), uuid_map)
                   for p in tree.rglob("*")
                   if "birth_observed" in p.parts
                   or p.name.startswith("segment-")
                   or p.name.endswith(".tmp"))
    return {"sqlite_files": sorted(sqlites), "blob_files": sorted(blobs),
            "sidecar_files": sorted(sidecars),
            "seeded_sources": sorted(seeded_seen),
            "sqlite": sqlites, "blobs": blobs,
            "latch_artifacts": latch, "uuid_map_size": len(uuid_map)}


# ── volatility derivation (E1) ────────────────────────────────────────────

def _col_multiset(tb: dict, i: int) -> list[str]:
    return sorted(repr(r[i]) for r in tb["rows"])


def derive_volatile(a: dict, b: dict) -> dict:
    volatile: dict = {}
    findings: list = []
    for db in sorted(set(a["sqlite"]) & set(b["sqlite"])):
        ta = a["sqlite"][db].get("tables", {})
        tb_ = b["sqlite"][db].get("tables", {})
        for t in sorted(set(ta) & set(tb_)):
            A, B = ta[t], tb_[t]
            if "rows" not in A or "rows" not in B:
                continue
            for i, c in enumerate(A["columns"]):
                if c not in B["columns"]:
                    continue
                j = B["columns"].index(c)
                if _col_multiset(A, i) == _col_multiset(B, j):
                    continue
                vals = ([r[i] for r in A["rows"]] + [r[j] for r in B["rows"]])
                diff = [v for v in vals if v is not None]
                if diff and all(is_uuid_shaped(v) for v in diff):
                    kind = "uuid"
                elif diff and all(is_time_shaped(v) for v in diff):
                    kind = "time"
                else:
                    findings.append({
                        "db": db, "table": t, "column": c,
                        "reason": "differs between baseline runs and is "
                                  "neither uuid-shaped nor time-shaped under "
                                  "the frozen grammar",
                        "sample": sorted({str(v) for v in diff})[:5]})
                    continue
                volatile.setdefault(db, {}).setdefault(t, {})[c] = kind
    return {"volatile": volatile, "findings": findings,
            "grammar": {"uuid": [UUID_RE.pattern, BARE_HEX_RE.pattern,
                                 PREFIXED_HEX_RE.pattern],
                        "iso8601": ISO8601_RE.pattern,
                        "unix_seconds_window": [SEC_MIN, SEC_MAX],
                        "unix_millis_window": [MS_MIN, MS_MAX]}}


# ── normalization (D1 + the row-alignment procedure) ──────────────────────

def normalize_table(tb: dict, kinds: dict, uuid_ord: dict) -> list:
    """Ordinalize, never drop.

    1. time columns  -> dense rank over the column's sorted distinct values.
       Preserves ordering, spacing-order and uniqueness; a collapse to a
       single value changes the rank structure and is caught.
    2. rows are sorted by their stable key: the non-volatile columns plus
       the time ranks. This is the row-alignment procedure -- it needs no
       row identity, and it is identical in both runs whenever the stable
       content is.
    3. uuid columns -> a per-DATABASE first-appearance ordinal assigned in
       that sorted order. Per-database, not per-column, so a foreign-key
       relationship that got scrambled shows up as an ordinal mismatch.
    """
    cols, rows = tb["columns"], tb["rows"]
    time_idx = [i for i, c in enumerate(cols) if kinds.get(c) == "time"]
    uuid_idx = [i for i, c in enumerate(cols) if kinds.get(c) == "uuid"]
    stable_idx = [i for i in range(len(cols))
                  if i not in time_idx and i not in uuid_idx]

    ranks = {}
    for i in time_idx:
        distinct = sorted({r[i] for r in rows}, key=lambda v: (v is None, str(v)))
        ranks[i] = {v: k for k, v in enumerate(distinct)}

    def stable_key(r):
        return (json.dumps([r[i] for i in stable_idx], default=repr, sort_keys=True),
                json.dumps([ranks[i].get(r[i]) for i in time_idx]))

    out = []
    for r in sorted(rows, key=stable_key):
        row = list(r)
        for i in time_idx:
            row[i] = f"<t:{ranks[i][r[i]]}>"
        for i in uuid_idx:
            v = r[i]
            if v is not None:
                row[i] = uuid_ord.setdefault(v, f"<id:{len(uuid_ord)}>")
        out.append(json.dumps(row, default=repr))
    return out


def compare(a: dict, b: dict, vol: dict, ledger_sha: str | None) -> dict:
    v = vol.get("volatile", {})
    res: dict = {"kills": [], "notes": []}

    for name, proj in (("a", a), ("b", b)):
        if proj["latch_artifacts"]:
            res["kills"].append({"clause": "B2", "tree": name,
                                 "detail": proj["latch_artifacts"]})

    for clause, key in (("B3.sqlite", "sqlite_files"),
                        ("B3.blob", "blob_files"),
                        ("B3.sidecar", "sidecar_files"),
                        ("B3.seeded", "seeded_sources")):
        if a[key] != b[key]:
            res["kills"].append({"clause": clause,
                                 "only_a": sorted(set(a[key]) - set(b[key])),
                                 "only_b": sorted(set(b[key]) - set(a[key]))})

    if ledger_sha:
        for name, proj in (("a", a), ("b", b)):
            blob = proj["blobs"].get("ledger.db")
            if blob is None:
                res["kills"].append({"clause": "B1", "tree": name,
                                     "detail": "ledger.db absent"})
            elif blob["sha256"] != ledger_sha:
                res["kills"].append({"clause": "B1", "tree": name,
                                     "expected": ledger_sha,
                                     "got": blob["sha256"]})

    # D2 -- every non-database file byte-compared; a difference KILLS.
    for k in sorted(set(a["blobs"]) & set(b["blobs"])):
        if k == "ledger.db":
            continue
        if a["blobs"][k]["sha256"] != b["blobs"][k]["sha256"]:
            res["kills"].append({"clause": "P2b", "file": k,
                                 "a": a["blobs"][k]["sha256"][:16],
                                 "b": b["blobs"][k]["sha256"][:16]})

    for db in sorted(set(a["sqlite"]) | set(b["sqlite"])):
        pa, pb = a["sqlite"].get(db), b["sqlite"].get(db)
        if pa is None or pb is None:
            res["kills"].append({"clause": "P1", "db": db,
                                 "detail": "present in only one tree"})
            continue
        if pa.get("schema") != pb.get("schema"):
            res["kills"].append({"clause": "P1.schema", "db": db})
        if pa.get("pragmas") != pb.get("pragmas"):
            res["kills"].append({"clause": "P1.pragma", "db": db,
                                 "a": pa.get("pragmas"), "b": pb.get("pragmas")})
        ta, tb_ = pa.get("tables", {}), pb.get("tables", {})
        if set(ta) != set(tb_):
            res["kills"].append({"clause": "P1.tables", "db": db,
                                 "only_a": sorted(set(ta) - set(tb_)),
                                 "only_b": sorted(set(tb_) - set(ta))})
            continue
        ua, ub = {}, {}
        for t in sorted(ta):
            A, B = ta[t], tb_[t]
            if "rows" not in A or "rows" not in B:
                res["kills"].append({"clause": "P1.unprojected", "db": db,
                                     "table": t})
                continue
            if A["columns"] != B["columns"]:
                res["kills"].append({"clause": "P1.columns", "db": db,
                                     "table": t})
                continue
            if A["count"] != B["count"]:
                res["kills"].append({"clause": "P1.count", "db": db,
                                     "table": t, "a": A["count"],
                                     "b": B["count"]})
                continue
            kinds = v.get(db, {}).get(t, {})
            na = normalize_table(A, kinds, ua)
            nb = normalize_table(B, kinds, ub)
            if na != nb:
                first = next((i for i, (x, y) in enumerate(zip(na, nb))
                              if x != y), None)
                res["kills"].append({"clause": "P1.rows", "db": db, "table": t,
                                     "first_divergent_index": first,
                                     "a": na[first] if first is not None else None,
                                     "b": nb[first] if first is not None else None})

    def phases(proj):
        out = {}
        for db, pj in proj["sqlite"].items():
            for t, tb_ in pj.get("tables", {}).items():
                if "memory_phase" in tb_.get("columns", []):
                    i = tb_["columns"].index("memory_phase")
                    counts: dict = {}
                    for r in tb_["rows"]:
                        counts[repr(r[i])] = counts.get(repr(r[i]), 0) + 1
                    out[f"{db}::{t}"] = dict(sorted(counts.items()))
        return out

    pa_, pb_ = phases(a), phases(b)
    res["phase_multisets"] = {"a": pa_, "b": pb_}
    if pa_ != pb_:
        res["kills"].append({"clause": "P3", "a": pa_, "b": pb_})

    res["verdict"] = ("IDENTICAL-UNDER-PROJECTION" if not res["kills"]
                      else "DIFFERS")
    return res


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    cmd = sys.argv[1]
    if cmd == "project":
        tree, out = Path(sys.argv[2]), Path(sys.argv[3])
        seeded = set()
        man = tree.parent / "logs" / "seeded-sources.txt"
        if man.exists():
            for line in man.read_text().splitlines():
                sp = line.split(None, 1)
                if len(sp) == 2:
                    seeded.add(sp[1].strip().split("/maez/", 1)[-1]
                               .removeprefix("memory/"))
        out.write_text(json.dumps(project_tree(tree, seeded), indent=1,
                                  default=repr) + "\n")
        print(f"projected {tree} -> {out}")
    elif cmd == "volatile":
        a = json.loads(Path(sys.argv[2]).read_text())
        b = json.loads(Path(sys.argv[3]).read_text())
        r = derive_volatile(a, b)
        Path(sys.argv[4]).write_text(json.dumps(r, indent=1) + "\n")
        n = sum(len(cs) for t in r["volatile"].values() for cs in t.values())
        print(f"volatile columns: {n}; findings: {len(r['findings'])}")
        for f in r["findings"]:
            print("  FINDING", f["db"], f["table"], f["column"], f["sample"])
        return 1 if r["findings"] else 0
    elif cmd == "compare":
        a = json.loads(Path(sys.argv[2]).read_text())
        b = json.loads(Path(sys.argv[3]).read_text())
        vol = json.loads(Path(sys.argv[4]).read_text())
        led = None
        if "--ledger-sha" in sys.argv:
            led = sys.argv[sys.argv.index("--ledger-sha") + 1]
        r = compare(a, b, vol, led)
        print(json.dumps(r, indent=1))
        return 0 if r["verdict"] == "IDENTICAL-UNDER-PROJECTION" else 1
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
