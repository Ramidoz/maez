#!/usr/bin/env python3
"""Theme 2 S1 witness fixture builder. Deterministic where possible.

Usage: python3 theme2_s1_fixtures.py <airlock_dir>
Refuses to run unless <airlock_dir> is under /tmp or an explicitly
airlocked path (never the live tree). Builds:
  F-A  : (absence — no file created; the path is reserved)
  F-E  : 0-byte ledger.db
  F-P  : migrations 0001..0002 only
  F-D1 : F-G with the turns table dropped
  F-D2 : F-G with 16 bytes at offset 4096 overwritten with 0xFF
  F-G  : fully migrated (0001..0005), genesis intact, zero non-genesis rows
  F-L  : F-G + birth anchor via the production writer (flag on, airlock path)
  F-X  : F-L with meta.birth_event_turn_id UPDATEd to 'no-such-turn'
Latch variants are built by the harness from F-L (valid/torn/corrupt/
stale-ahead/foreign) per the protocol's literal recipes.
Prints sha256 of every produced file.
"""
import hashlib, os, shutil, sqlite3, subprocess, sys
from pathlib import Path

REPO = Path("/home/rohit/maez")

def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()

def main() -> None:
    root = Path(sys.argv[1]).resolve()
    assert str(root).startswith("/tmp"), "airlock only — never the live tree"
    root.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    out = {}

    # F-E
    fe = root / "F-E" / "ledger.db"; fe.parent.mkdir(exist_ok=True)
    fe.write_bytes(b""); out["F-E"] = sha(fe)

    # F-G: full migration via the repo's own migrate entry point
    fg = root / "F-G" / "ledger.db"; fg.parent.mkdir(exist_ok=True)
    e = dict(env, MAEZ_LEDGER_DB_PATH=str(fg))
    subprocess.run([sys.executable, "-c",
        "import sys; sys.path.insert(0,'%s'); "
        "from core.ledger.migrate import run; run('%s')" % (REPO, fg)],
        check=True, env=e, cwd=REPO)
    out["F-G"] = sha(fg)

    # F-P: partial — apply only 0001..0002 manually
    fp = root / "F-P" / "ledger.db"; fp.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(fp)
    for name in ("0001_init.sql", "0002_triggers.sql"):
        conn.executescript((REPO / "core/ledger/migrations" / name).read_text())
    conn.commit(); conn.close(); out["F-P"] = sha(fp)

    # F-D1 / F-D2 from copies of F-G
    fd1 = root / "F-D1" / "ledger.db"; fd1.parent.mkdir(exist_ok=True)
    shutil.copy2(fg, fd1)
    c = sqlite3.connect(fd1); c.executescript(
        "PRAGMA foreign_keys=OFF; DROP TABLE turns;"); c.close()
    out["F-D1"] = sha(fd1)
    fd2 = root / "F-D2" / "ledger.db"; fd2.parent.mkdir(exist_ok=True)
    shutil.copy2(fg, fd2)
    with open(fd2, "r+b") as f:
        f.seek(4096); f.write(b"\xff" * 16)
    out["F-D2"] = sha(fd2)

    # F-L: birth anchor through the PRODUCTION writer, airlock path, flag on
    fl = root / "F-L" / "ledger.db"; fl.parent.mkdir(exist_ok=True)
    shutil.copy2(fg, fl)
    e = dict(env, MAEZ_LEDGER_DB_PATH=str(fl), MAEZ_LEDGER_WRITES="1")
    subprocess.run([sys.executable, "-c",
        "import sys; sys.path.insert(0,'%s'); "
        "from core.ledger.writer import LedgerWriter; "
        "w=LedgerWriter('%s'); "
        "w.write_turn('system_event','birth (S1 witness fixture)',"
        "surface='system',birth_anchor=True,"
        "taint_labels=['self_generated'],privacy_access='sealed_adjacent'); w.close()" % (REPO, fl)],
        check=True, env=e, cwd=REPO)
    out["F-L"] = sha(fl)          # per-run digest: writer stamps real time

    # F-X: mutate the meta pointer on a copy of F-L
    fx = root / "F-X" / "ledger.db"; fx.parent.mkdir(exist_ok=True)
    shutil.copy2(fl, fx)
    c = sqlite3.connect(fx)
    c.execute("UPDATE meta SET value='no-such-turn' WHERE key='birth_event_turn_id'")
    c.commit(); c.close(); out["F-X"] = sha(fx)

    for k in sorted(out):
        print(k, out[k])

if __name__ == "__main__":
    main()
