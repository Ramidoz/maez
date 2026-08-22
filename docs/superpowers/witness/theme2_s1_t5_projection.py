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
import shutil
import sqlite3
import sys
import tempfile
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

def time_window(v) -> str | None:
    """Which frozen time domain a value inhabits. Comparing the multiset of
    these catches a seconds-to-milliseconds rewrite, which preserves rank
    and would otherwise normalize identically (gate round 13, item D)."""
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        f = float(v)
        if SEC_MIN <= f <= SEC_MAX:
            return "unix_s"
        if MS_MIN <= f <= MS_MAX:
            return "unix_ms"
        return None
    if isinstance(v, str) and ISO8601_RE.match(v):
        return "iso8601"
    return None


def project_sqlite(path: Path) -> dict:
    """Project a SQLite store WAL-aware.

    Gate round 13, item D: the first version opened with `immutable=1`,
    which tells SQLite to ignore the write-ahead log -- so a committed
    change living only in the WAL was invisible while sidecar presence
    compared equal. The database and its sidecars are copied to scratch
    and opened normally, so the WAL is applied before anything is read.
    """
    scratch = Path(tempfile.mkdtemp(prefix="t5proj_"))
    try:
        local = scratch / path.name
        shutil.copy2(path, local)
        for suffix in ("-wal", "-shm"):
            side = path.with_name(path.name + suffix)
            if side.exists():
                shutil.copy2(side, scratch / side.name)
        try:
            conn = sqlite3.connect(str(local))
        except sqlite3.Error as e:
            return {"error": f"{type(e).__name__}: {e}"}
        return _project_open(conn, path)
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def _project_open(conn, path: Path) -> dict:
    out: dict = {"schema": [], "pragmas": {}, "tables": {},
                 "file_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
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
            out["tables"][t] = {
                "columns": cols, "count": len(rows), "rows": rows,
                # E: NULLs are class-neutral, so classification skips them --
                # but a change in how many there are is a real change, and is
                # compared here rather than lost.
                "null_counts": {c: sum(1 for r in rows if r[i] is None)
                                for i, c in enumerate(cols)},
                "time_windows": {
                    c: sorted(w for w in (time_window(r[i]) for r in rows)
                              if w is not None)
                    for i, c in enumerate(cols)},
            }
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
            # Seeded package sources: code, not store. Copied from the repo so
            # the reply machinery can import at all. Compared by DIGEST, not
            # merely by name (gate round 13, item D).
            seeded_seen.append(
                {"path": rel,
                 "sha256": hashlib.sha256(p.read_bytes()).hexdigest()})
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
            "seeded_sources": sorted(seeded_seen,
                                     key=lambda d: d["path"]),
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
                # E: NULL is class-neutral -- it belongs to no shape and does
                # not disqualify a field. What it must not do is disappear
                # silently, so null_counts is compared in P1 and a NULL->UUID
                # change shows up there rather than being classified away.
                vals = ([r[i] for r in A["rows"]] + [r[j] for r in B["rows"]])
                diff = [v for v in vals if v is not None]
                if not diff:
                    findings.append({
                        "db": db, "table": t, "column": c,
                        "reason": "differs between baseline runs only in its "
                                  "NULL pattern; NULL is class-neutral and "
                                  "cannot be absorbed as volatile",
                        "sample": []})
                    continue
                if all(is_uuid_shaped(v) for v in diff):
                    kind = "uuid"
                elif all(is_time_shaped(v) for v in diff):
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

    if uuid_idx:
        seen: dict = {}
        for r in rows:
            seen[stable_key(r)] = seen.get(stable_key(r), 0) + 1
        collisions = {k: n for k, n in seen.items() if n > 1}
        if collisions:
            # Two rows sharing a stable key make uuid ordinal assignment
            # ambiguous: a genuine relationship scramble and a harmless
            # relabel look identical. Fail closed rather than guess
            # (gate round 13, item D).
            return [f"<COLLISION:{len(collisions)} stable keys are not unique "
                    f"in a table carrying uuid-classified columns>"]
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
        # B1 reads the sqlite projection's recorded file digest: ledger.db is
        # classified as a sqlite store, not a blob, so the first version
        # always reported it absent (gate round 13, item D).
        for name, proj in (("a", a), ("b", b)):
            entry = proj["sqlite"].get("ledger.db")
            got = entry.get("file_sha256") if entry else None
            if got is None:
                res["kills"].append({"clause": "B1", "tree": name,
                                     "detail": "ledger.db not projected"})
            elif got != ledger_sha:
                res["kills"].append({"clause": "B1", "tree": name,
                                     "expected": ledger_sha, "got": got})

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
        # A projection error is not data. Two matching error objects
        # previously compared equal and passed (gate round 13, item D).
        for nm, pj in (("a", pa), ("b", pb)):
            if "error" in pj:
                res["kills"].append({"clause": "P1.error", "db": db,
                                     "tree": nm, "detail": pj["error"]})
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
            if A.get("null_counts") != B.get("null_counts"):
                res["kills"].append({"clause": "P1.nulls", "db": db,
                                     "table": t, "a": A.get("null_counts"),
                                     "b": B.get("null_counts")})
            kinds = v.get(db, {}).get(t, {})
            # Revalidate every volatile value against its FROZEN class at
            # compare time. Without this, compare() blindly trusted the
            # baseline classification, so a one-row time column could be
            # rewritten to epoch zero -- outside the frozen window, therefore
            # not time-shaped -- and still normalize to <t:0>.
            for c, kind in kinds.items():
                if c not in A["columns"]:
                    continue
                i = A["columns"].index(c)
                check = is_uuid_shaped if kind == "uuid" else is_time_shaped
                for nm, T in (("a", A), ("b", B)):
                    bad = sorted({repr(r[i]) for r in T["rows"]
                                  if r[i] is not None and not check(r[i])})
                    if bad:
                        res["kills"].append({
                            "clause": "P1.class", "db": db, "table": t,
                            "column": c, "tree": nm, "expected_class": kind,
                            "offending": bad[:5]})
                if kind == "time" and (A.get("time_windows", {}).get(c)
                                       != B.get("time_windows", {}).get(c)):
                    # Catches a seconds-to-milliseconds rewrite, which
                    # preserves rank and would normalize identically.
                    res["kills"].append({
                        "clause": "P1.timewindow", "db": db, "table": t,
                        "column": c,
                        "a": A.get("time_windows", {}).get(c),
                        "b": B.get("time_windows", {}).get(c)})
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

    # P2 -- the Chroma record/vector extract, now part of the verdict rather
    # than an artifact nothing read (gate round 13, item D).
    xa, xb = a.get("extract"), b.get("extract")
    if (xa is None) != (xb is None):
        res["kills"].append({"clause": "P2", "detail": "extract present on "
                                                       "only one side"})
    elif xa is not None:
        if set(xa.get("collections", {})) != set(xb.get("collections", {})):
            res["kills"].append({
                "clause": "P2.collections",
                "only_a": sorted(set(xa["collections"]) - set(xb["collections"])),
                "only_b": sorted(set(xb["collections"]) - set(xa["collections"]))})
        for k in sorted(set(xa.get("collections", {}))
                        & set(xb.get("collections", {}))):
            ca, cb = xa["collections"][k], xb["collections"][k]
            if "error" in ca or "error" in cb:
                res["kills"].append({"clause": "P2.error", "collection": k,
                                     "a": ca.get("error"), "b": cb.get("error")})
                continue
            if ca.get("count") != cb.get("count"):
                res["kills"].append({"clause": "P2.count", "collection": k,
                                     "a": ca.get("count"), "b": cb.get("count")})
            if ca.get("records") != cb.get("records"):
                res["kills"].append({"clause": "P2.records", "collection": k})
            if ca.get("vector_sha256") != cb.get("vector_sha256"):
                res["kills"].append({"clause": "P2.vectors", "collection": k,
                                     "a": ca.get("vector_sha256"),
                                     "b": cb.get("vector_sha256")})

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
        proj = project_tree(tree, seeded)
        if "--extract" in sys.argv:
            xp = Path(sys.argv[sys.argv.index("--extract") + 1])
            proj["extract"] = json.loads(xp.read_text())
        out.write_text(json.dumps(proj, indent=1, default=repr) + "\n")
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
