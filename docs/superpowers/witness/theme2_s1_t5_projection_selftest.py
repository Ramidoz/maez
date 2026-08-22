#!/usr/bin/env python3
"""Self-test for the T5 projection comparator.

The comparator is the instrument T5's verdict rests on, so it is verified
against synthetic fixtures before it is ever pointed at a real store tree.
Every case below is a defect a gate round actually found and reproduced;
the names in the `clause` column are the clauses that must fire.

    python3 theme2_s1_t5_projection_selftest.py

Exit 0 iff every case behaves as declared. Runs entirely in a scratch
directory; touches nothing else.
"""
from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

TOOL = Path(__file__).resolve().parent / "theme2_s1_t5_projection.py"
BASE = 1_700_000_000


def build(d: Path, *, texts, ts, phase="gestation", blob=b"\x00" * 64, uv=0,
          solo=None, collide=False, wal_extra=False, nulls=False,
          ledger=True, digest="a" * 64, extra_col=False,
          literal_token=False, pdigest="digest-" + "a" * 32):
    d.mkdir(parents=True, exist_ok=True)
    name = "ledger.db" if ledger else "thoughts.db"
    c = sqlite3.connect(d / name)
    c.execute(f"PRAGMA user_version={uv}")
    c.execute("CREATE TABLE t (id TEXT, ts REAL, body TEXT, memory_phase TEXT)")
    for txt, tv in zip(texts, ts):
        c.execute("INSERT INTO t VALUES (?,?,?,?)",
                  (str(uuid.uuid4()), tv, txt, phase))
    c.execute("CREATE TABLE solo (id TEXT, at REAL)")
    c.execute("INSERT INTO solo VALUES (?,?)",
              (str(uuid.uuid4()), BASE if solo is None else solo))
    # A semantic digest must never be absorbed as an identifier.
    c.execute("CREATE TABLE dg (id TEXT, content_sha256 TEXT, "
              "prefixed_digest TEXT)")
    c.execute("INSERT INTO dg VALUES (?,?,?)",
              (str(uuid.uuid4()), digest, pdigest))
    if extra_col:
        c.execute("CREATE TABLE oc (stable TEXT, added TEXT)")
        c.execute("INSERT INTO oc VALUES (?,?)", ("same", str(uuid.uuid4())))
    else:
        c.execute("CREATE TABLE oc (stable TEXT)")
        c.execute("INSERT INTO oc VALUES (?)", ("same",))
    c.execute("CREATE TABLE nn (id TEXT, maybe TEXT)")
    c.execute("INSERT INTO nn VALUES (?,?)",
              (str(uuid.uuid4()), str(uuid.uuid4()) if nulls else None))
    if collide:
        # Two rows whose only non-uuid content is identical: the stable key
        # collides, so uuid ordinal assignment is ambiguous.
        c.execute("CREATE TABLE rel (parent TEXT, child TEXT, tag TEXT)")
        for _ in range(2):
            c.execute("INSERT INTO rel VALUES (?,?,?)",
                      (str(uuid.uuid4()), str(uuid.uuid4()), "same"))
    c.commit()
    if wal_extra:
        c.execute("PRAGMA journal_mode=WAL")
        c.execute("INSERT INTO t VALUES (?,?,?,?)",
                  (str(uuid.uuid4()), BASE + 99, "WAL-ONLY ROW", phase))
        c.commit()
        c.close()
    else:
        c.close()
    seg = d / str(uuid.uuid4())
    seg.mkdir()
    (seg / "data_level0.bin").write_bytes(blob)
    if literal_token:
        # A directory literally named like the canonicalization placeholder.
        lit = d / "<uuid:0>"
        lit.mkdir()
        (lit / "data_level0.bin").write_bytes(blob)


def extract(path: Path, *, doc="marker 0", md_ts=BASE, vec="a" * 64):
    path.write_text(json.dumps({
        "collections": {"raw::raw_archive": {
            "count": 1, "vector_sha256": vec, "vector_bytes": 8,
            "records": [{"document": doc,
                         "metadata": {"memory_phase": "gestation",
                                      "timestamp": md_ts,
                                      "id": str(uuid.uuid4())}}]}}}) + "\n")


def run(*a):
    return subprocess.run([sys.executable, str(TOOL), *a],
                          capture_output=True, text=True)


def main() -> int:
    root = Path(tempfile.mkdtemp(prefix="t5_selftest_"))
    texts = [f"marker {i}" for i in range(5)]
    good = [BASE + i for i in range(5)]
    specs = {
        "A":   dict(texts=texts, ts=good),
        "B":   dict(texts=texts, ts=[t + 900 for t in good], solo=BASE + 900),
        "Zc":  dict(texts=texts, ts=[BASE + 1] * 5),
        "Z0":  dict(texts=texts, ts=good, solo=0.0),
        "Zms": dict(texts=texts, ts=[t * 1000 for t in good], solo=BASE * 1000),
        "Ct":  dict(texts=texts[:-1] + ["CHANGED"], ts=good),
        "Hb":  dict(texts=texts, ts=good, blob=b"\x01" * 64),
        "Up":  dict(texts=texts, ts=good, uv=7),
        "Wl":  dict(texts=texts, ts=good, wal_extra=True),
        "Nu":  dict(texts=texts, ts=good, nulls=True),
        "K1":  dict(texts=texts, ts=good, collide=True),
        "K2":  dict(texts=texts, ts=[t + 900 for t in good], collide=True),
        "Dg":  dict(texts=texts, ts=good, digest="b" * 64),
        "Lt":  dict(texts=texts, ts=good, literal_token=True),
        "Pd":  dict(texts=texts, ts=good, pdigest="digest-" + "b" * 32),
        "Oc":  dict(texts=texts, ts=[t + 900 for t in good], extra_col=True),
    }
    for name, kw in specs.items():
        build(root / name, **kw)
        extract(root / f"{name}.extract.json",
                md_ts=BASE + (900 if name in ("B", "K2") else 0))
        run("project", str(root / name), str(root / f"{name}.json"),
            "--extract", str(root / f"{name}.extract.json"))
    # a projection with no extract, to prove P2 is mandatory
    run("project", str(root / "A"), str(root / "A_noext.json"))

    r = run("volatile", str(root / "A.json"), str(root / "B.json"),
            str(root / "vol.json"))
    run("volatile", str(root / "K1.json"), str(root / "K2.json"),
        str(root / "volk.json"))
    ok = r.returncode == 0
    print(f"{'ok ' if ok else 'BAD'} volatile(A,B) derives cleanly        "
          f"{r.stdout.strip()}")

    rn = run("volatile", str(root / "A.json"), str(root / "Nu.json"),
             str(root / "voln.json"))
    ok_n = rn.returncode == 1 and "findings: 1" in rn.stdout
    print(f"{'ok ' if ok_n else 'BAD'} NULL-pattern change is a FINDING     "
          f"{rn.stdout.strip().splitlines()[0]}")
    ok &= ok_n

    ro = run("volatile", str(root / "A.json"), str(root / "Oc.json"),
             str(root / "volo.json"))
    ok_o = ro.returncode == 1 and "added" in ro.stdout
    print(f"{'ok ' if ok_o else 'BAD'} one-sided column is a FINDING        "
          f"{ro.stdout.strip().splitlines()[0] if ro.stdout.strip() else '(none)'}")
    ok &= ok_o

    rd = run("volatile", str(root / "A.json"), str(root / "Dg.json"),
             str(root / "vold.json"))
    ok_d = rd.returncode == 1 and "content_sha256" in rd.stdout
    print(f"{'ok ' if ok_d else 'BAD'} sha256 is NOT uuid-shaped            "
          f"{'reported as a finding' if ok_d else rd.stdout.strip()[:60]}")
    ok &= ok_d

    rp = run("volatile", str(root / "A.json"), str(root / "Pd.json"),
             str(root / "volp.json"))
    ok_p = rp.returncode == 1 and "prefixed_digest" in rp.stdout
    print(f"{'ok ' if ok_p else 'BAD'} prefixed digest is NOT uuid-shaped   "
          f"{'reported as a finding' if ok_p else rp.stdout.strip()[:60]}")
    ok &= ok_p

    led = json.loads((root / "A.json").read_text())["sqlite"]["ledger.db"]["file_sha256"]
    cases = [
        ("A",   "B",  "equivalent runs",            None),
        ("Zc",  "A",  "chronology collapse",        "P1.rows"),
        ("Z0",  "A",  "one-row time -> epoch zero", "P1.class"),
        ("Zms", "A",  "seconds -> milliseconds",    "P1.timewindow"),
        ("Ct",  "A",  "content change",             "P1.rows"),
        ("Hb",  "A",  "HNSW-shaped blob change",    "P2b"),
        ("Up",  "A",  "pragma change",              "P1.pragma"),
        ("Wl",  "A",  "committed only in the WAL",  "P1.count"),
        ("K1",  "K2", "stable-key collision",       "P1.collision"),
        ("Dg",  "A",  "semantic digest changed",    "P1.rows"),
        ("Lt",  "A",  "literal <uuid:N> component", "B3.dirs"),
    ]
    for x, y, label, want in cases:
        volfile = "volk.json" if x == "K1" else "vol.json"
        d = json.loads(run("compare", str(root / f"{x}.json"),
                           str(root / f"{y}.json"),
                           str(root / volfile)).stdout)
        clauses = sorted({k["clause"] for k in d["kills"]})
        good_ = (not clauses) if want is None else (want in clauses)
        ok &= good_
        print(f"{'ok ' if good_ else 'BAD'} {label:28s} {d['verdict']:28s} "
              f"{clauses}")

    d = json.loads(run("compare", str(root / "A_noext.json"),
                       str(root / "A_noext.json"), str(root / "vol.json")).stdout)
    ok_p2 = "P2.missing" in {k["clause"] for k in d["kills"]}
    print(f"{'ok ' if ok_p2 else 'BAD'} P2 is mandatory on both sides"
          f"{'':<3}{d['verdict']}")
    ok &= ok_p2

    d = json.loads(run("compare", str(root / "A.json"), str(root / "B.json"),
                       str(root / "vol.json"), "--ledger-sha", "0" * 64).stdout)
    b1 = [k for k in d["kills"] if k["clause"] == "B1" and "got" in k]
    ok &= bool(b1)
    print(f"{'ok ' if b1 else 'BAD'} B1 reads the sqlite file digest      "
          f"{'kills on a wrong digest' if b1 else 'NO KILL'}")

    print("\nALL PASS" if ok else "\nSOME CASES FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
