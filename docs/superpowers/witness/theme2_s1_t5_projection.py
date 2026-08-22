#!/usr/bin/env python3
"""Theme 2 S1 — T5 invariance projection (protocol §12.8).

Raw byte equality between two runs is impossible: every store on the reply
path stamps uuid4() and a wall clock. This tool computes the projection
§12.8 pre-registers, and does three jobs:

    project  <tree> <out.json>          -- one store tree -> one projection
    volatile <a.json> <b.json> <out>    -- derive the volatile column list
                                           from two BASELINE projections
    compare  <a.json> <b.json> <volatile.json>
                                        -- B1..B3 / P1..P3 verdict

The volatile list is derived from the two baseline runs and frozen in
protocol v7 before any S1 code exists. A column that differs between the
baseline runs and is NEITHER uuid-shaped NOR time-shaped is reported as a
FINDING, never absorbed into the volatile set.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import sys
from pathlib import Path

UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)
# ISO-8601 with or without offset, and bare unix seconds/millis.
ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}")
SQLITE_SUFFIXES = (".db", ".sqlite3", ".sqlite")
# WAL/SHM sidecars are real database state but are checkpoint-timing
# artifacts, not content. They are compared by presence, never by bytes.
SIDECAR_SUFFIXES = ("-wal", "-shm")


def canonical_path(rel: str, uuid_map: dict) -> str:
    parts = []
    for p in Path(rel).parts:
        if UUID_RE.match(p):
            parts.append(uuid_map.setdefault(p, f"<uuid:{len(uuid_map)}>"))
        else:
            parts.append(p)
    return "/".join(parts)


def is_time_shaped(v) -> bool:
    if isinstance(v, (int, float)) and 1_000_000_000 <= float(v) <= 4_000_000_000_000:
        return True
    if isinstance(v, str) and ISO_RE.match(v):
        return True
    return False


def is_uuid_shaped(v) -> bool:
    if not isinstance(v, str):
        return False
    if UUID_RE.match(v):
        return True
    # chroma and the ledger both mint bare hex ids of various widths.
    return bool(re.fullmatch(r"[0-9a-f]{12,64}", v)) or bool(
        re.fullmatch(r"[a-z]+-[0-9a-f]{8,32}", v)
    )


def project_sqlite(path: Path) -> dict:
    uri = f"file:{path}?mode=ro&immutable=1"
    out: dict = {"schema": [], "tables": {}}
    try:
        conn = sqlite3.connect(uri, uri=True)
    except sqlite3.Error as e:
        return {"error": f"{type(e).__name__}: {e}"}
    try:
        out["schema"] = [
            list(r)
            for r in conn.execute(
                "SELECT name, type, sql FROM sqlite_master ORDER BY name, type"
            )
        ]
        names = [
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            )
        ]
        for t in names:
            cols = [r[1] for r in conn.execute(f'PRAGMA table_info("{t}")')]
            rows = [
                list(r) for r in conn.execute(f'SELECT * FROM "{t}"')
            ]
            out["tables"][t] = {
                "columns": cols,
                "count": len(rows),
                # Per-column value multisets: this is what makes the
                # volatile derivation order-independent and well defined.
                "column_values": {
                    c: sorted(
                        (repr(row[i]) for row in rows), key=str
                    )
                    for i, c in enumerate(cols)
                },
                "rows": sorted((json.dumps(r, default=repr) for r in rows)),
            }
    finally:
        conn.close()
    return out


def project_tree(tree: Path) -> dict:
    uuid_map: dict = {}
    files, sqlites, blobs, sidecars = {}, {}, {}, []
    for p in sorted(tree.rglob("*")):
        if not p.is_file():
            continue
        rel = str(p.relative_to(tree))
        cp = canonical_path(rel, uuid_map)
        if rel.endswith(SIDECAR_SUFFIXES):
            sidecars.append(cp)
            files[cp] = {"kind": "sidecar"}
            continue
        if p.suffix in SQLITE_SUFFIXES:
            sqlites[cp] = project_sqlite(p)
            files[cp] = {"kind": "sqlite"}
        else:
            blobs[cp] = {
                "size": p.stat().st_size,
                "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
            }
            files[cp] = {"kind": "blob"}
    latch = sorted(
        canonical_path(str(p.relative_to(tree)), uuid_map)
        for p in tree.rglob("*")
        if "birth_observed" in p.parts
        or p.name.startswith("segment-")
        or p.name.endswith(".tmp")
    )
    return {
        "file_set": sorted(files),
        "file_kinds": files,
        "sqlite": sqlites,
        "blobs": blobs,
        "sidecars": sorted(sidecars),
        "latch_artifacts": latch,
        "uuid_map_size": len(uuid_map),
    }


def derive_volatile(a: dict, b: dict) -> dict:
    """A column is volatile iff its value multiset differs between the two
    baseline runs AND every differing value is uuid-shaped or time-shaped.
    Anything else is a FINDING."""
    volatile, findings = {}, []
    for db in sorted(set(a["sqlite"]) & set(b["sqlite"])):
        ta, tb = a["sqlite"][db].get("tables", {}), b["sqlite"][db].get("tables", {})
        for t in sorted(set(ta) & set(tb)):
            for c in ta[t]["columns"]:
                if c not in tb[t]["columns"]:
                    continue
                va, vb = ta[t]["column_values"][c], tb[t]["column_values"][c]
                if va == vb:
                    continue
                diff = set(va) ^ set(vb)
                parsed = []
                for s in diff:
                    try:
                        parsed.append(eval(s, {"__builtins__": {}}, {}))
                    except Exception:                       # noqa: BLE001
                        parsed.append(s)
                if all(is_uuid_shaped(v) or is_time_shaped(v) for v in parsed):
                    volatile.setdefault(db, {}).setdefault(t, []).append(c)
                else:
                    findings.append({
                        "db": db, "table": t, "column": c,
                        "reason": "differs between baseline runs but is "
                                  "neither uuid-shaped nor time-shaped",
                        "sample": sorted(map(str, parsed))[:5],
                    })
    return {"volatile": volatile, "findings": findings}


def compare(a: dict, b: dict, vol: dict, ledger_sha: str | None) -> dict:
    v = vol.get("volatile", {})
    res: dict = {"kills": [], "notes": []}

    # B2 -- no latch artifacts anywhere.
    for name, proj in (("a", a), ("b", b)):
        if proj["latch_artifacts"]:
            res["kills"].append(
                {"clause": "B2", "tree": name,
                 "detail": proj["latch_artifacts"]})

    # B3 -- canonicalized file set identical.
    if a["file_set"] != b["file_set"]:
        only_a = sorted(set(a["file_set"]) - set(b["file_set"]))
        only_b = sorted(set(b["file_set"]) - set(a["file_set"]))
        res["kills"].append(
            {"clause": "B3", "only_in_a": only_a, "only_in_b": only_b})

    # B1 -- the ledger must be untouched flags-off.
    if ledger_sha:
        for name, proj in (("a", a), ("b", b)):
            blob = proj["blobs"].get("ledger.db")
            if blob and blob["sha256"] != ledger_sha:
                res["kills"].append(
                    {"clause": "B1", "tree": name,
                     "expected": ledger_sha, "got": blob["sha256"]})

    # P1 -- schema, counts, and rows minus the volatile columns.
    for db in sorted(set(a["sqlite"]) | set(b["sqlite"])):
        pa, pb = a["sqlite"].get(db), b["sqlite"].get(db)
        if pa is None or pb is None:
            res["kills"].append({"clause": "P1", "db": db,
                                 "detail": "present in only one tree"})
            continue
        if pa.get("schema") != pb.get("schema"):
            res["kills"].append({"clause": "P1.schema", "db": db})
        ta, tb = pa.get("tables", {}), pb.get("tables", {})
        if set(ta) != set(tb):
            res["kills"].append({"clause": "P1.tables", "db": db,
                                 "only_a": sorted(set(ta) - set(tb)),
                                 "only_b": sorted(set(tb) - set(ta))})
            continue
        for t in sorted(ta):
            if ta[t]["count"] != tb[t]["count"]:
                res["kills"].append({"clause": "P1.count", "db": db,
                                     "table": t, "a": ta[t]["count"],
                                     "b": tb[t]["count"]})
                continue
            drop = set(v.get(db, {}).get(t, []))
            for c in ta[t]["columns"]:
                if c in drop:
                    continue
                if ta[t]["column_values"][c] != tb[t]["column_values"][c]:
                    res["kills"].append({"clause": "P1.column", "db": db,
                                         "table": t, "column": c})

    # P2b -- binary segment files. A difference is a finding to adjudicate
    # with the in-namespace vector extract, never silently tolerated.
    for k in sorted(set(a["blobs"]) & set(b["blobs"])):
        if a["blobs"][k]["sha256"] != b["blobs"][k]["sha256"]:
            res["notes"].append({"clause": "P2b", "file": k,
                                 "detail": "binary differs; adjudicate "
                                           "with the vector extract"})
    # P3 -- phase-exactness, reported explicitly so the run report can quote
    # the multisets rather than infer them from P1's silence. A difference
    # here is already a P1.column kill; this clause exists for legibility,
    # and it kills independently so a future volatile-list error cannot
    # quietly swallow a phase change.
    def phases(proj):
        out = {}
        for db, pj in proj["sqlite"].items():
            for t, tb in pj.get("tables", {}).items():
                if "memory_phase" in tb.get("columns", []):
                    vals = tb["column_values"]["memory_phase"]
                    counts = {}
                    for v in vals:
                        counts[v] = counts.get(v, 0) + 1
                    out[f"{db}::{t}"] = dict(sorted(counts.items()))
        return out

    pa, pb = phases(a), phases(b)
    res["phase_multisets"] = {"a": pa, "b": pb}
    if pa != pb:
        res["kills"].append({"clause": "P3", "a": pa, "b": pb})

    res["verdict"] = "IDENTICAL-UNDER-PROJECTION" if not res["kills"] else "DIFFERS"
    return res


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    cmd = sys.argv[1]
    if cmd == "project":
        tree, out = Path(sys.argv[2]), Path(sys.argv[3])
        out.write_text(json.dumps(project_tree(tree), indent=1) + "\n")
        print(f"projected {tree} -> {out}")
    elif cmd == "volatile":
        a = json.loads(Path(sys.argv[2]).read_text())
        b = json.loads(Path(sys.argv[3]).read_text())
        r = derive_volatile(a, b)
        Path(sys.argv[4]).write_text(json.dumps(r, indent=1) + "\n")
        n = sum(len(c) for t in r["volatile"].values() for c in t.values())
        print(f"volatile columns: {n}; findings: {len(r['findings'])}")
        for f in r["findings"]:
            print("  FINDING", f["db"], f["table"], f["column"], f["sample"])
    elif cmd == "compare":
        a = json.loads(Path(sys.argv[2]).read_text())
        b = json.loads(Path(sys.argv[3]).read_text())
        vol = json.loads(Path(sys.argv[4]).read_text())
        led = sys.argv[5] if len(sys.argv) > 5 else None
        r = compare(a, b, vol, led)
        print(json.dumps(r, indent=1))
        return 0 if r["verdict"] == "IDENTICAL-UNDER-PROJECTION" else 1
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
