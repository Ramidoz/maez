#!/usr/bin/env python3
"""Theme 2 S1 — T5 Chroma record/vector extract (protocol §12.8 P2).

Chroma stores documents and metadata in chroma.sqlite3 but keeps the
float vectors in the binary HNSW segment files, so P2's vector clause
cannot be computed from the sqlite projection alone. This runs INSIDE
the airlock namespace -- the only place memory_manager.BASE_DB resolves
to the airlock rather than the live store -- and emits the logical
record set with the framing §12.8 freezes:

    records ordered by (document, canonical-JSON metadata,
    canonical-JSON record); each vector serialized as IEEE-754
    little-endian doubles, concatenated, sha256.

The third sort key exists to break duplicate-document ties, which the
replay manifest deliberately contains ("hello maez, marker 00/05/10/15"
differ only by marker).

Usage (inside the namespace):
    python3 theme2_s1_t5_extract.py <out.json>
"""
from __future__ import annotations

import hashlib
import json
import struct
import sys
from pathlib import Path

MAEZ_TREE = Path("/home/rohit/maez")


def canon(o) -> str:
    return json.dumps(o, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, default=repr)


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    out_path = Path(sys.argv[1])

    if not MAEZ_TREE.exists():
        raise SystemExit("repo missing")
    probe = MAEZ_TREE / ".t5_extract_probe"
    try:
        probe.write_text("x")
    except OSError:
        pass
    else:
        probe.unlink(missing_ok=True)
        raise SystemExit(
            "REFUSED: /home/rohit/maez is writable — not inside the airlock")

    sys.path.insert(0, str(MAEZ_TREE))
    import memory.memory_manager as mm

    result: dict = {"base_db": str(mm.BASE_DB), "collections": {}}
    if not str(mm.BASE_DB).startswith(str(MAEZ_TREE / "memory")):
        raise SystemExit(f"REFUSED: BASE_DB outside the overlay: {mm.BASE_DB}")

    import chromadb
    from chromadb.config import Settings

    result["chromadb_version"] = chromadb.__version__

    for subdir in sorted(p.name for p in mm.BASE_DB.iterdir() if p.is_dir()):
        try:
            client = chromadb.PersistentClient(
                path=str(mm.BASE_DB / subdir),
                settings=Settings(anonymized_telemetry=False))
            cols = client.list_collections()
        except Exception as e:                          # noqa: BLE001
            result["collections"][subdir] = {"error": f"{type(e).__name__}: {e}"}
            continue
        for col in cols:
            c = client.get_collection(col if isinstance(col, str) else col.name)
            got = c.get(include=["documents", "metadatas", "embeddings"])
            recs = []
            for i, rid in enumerate(got.get("ids") or []):
                doc = (got.get("documents") or [None] * (i + 1))[i]
                md = (got.get("metadatas") or [None] * (i + 1))[i]
                emb = (got.get("embeddings") or [None] * (i + 1))[i]
                recs.append({"id": rid, "document": doc, "metadata": md,
                             "embedding": list(emb) if emb is not None else None})
            recs.sort(key=lambda r: (str(r["document"]), canon(r["metadata"]),
                                     canon(r)))
            blob = b"".join(
                struct.pack("<%dd" % len(r["embedding"]), *r["embedding"])
                for r in recs if r["embedding"] is not None)
            name = c.name if hasattr(c, "name") else str(col)
            result["collections"][f"{subdir}::{name}"] = {
                "count": len(recs),
                "vector_sha256": hashlib.sha256(blob).hexdigest(),
                "vector_bytes": len(blob),
                # ids are uuid-shaped and excluded from the logical set;
                # they are covered by the sqlite projection's ordinalization.
                "records": [{"document": r["document"], "metadata": r["metadata"]}
                            for r in recs],
            }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, indent=1, default=repr) + "\n")
    print(f"extracted {len(result['collections'])} collections -> {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
