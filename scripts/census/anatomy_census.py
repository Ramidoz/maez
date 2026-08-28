"""Anatomy census instrument — mechanical layer.

Derives what can be derived FROM RUNTIME, never from timestamps alone:
  Q1 owns      : store, modules, flags, tables
  Q2 alive     : flags read from /proc/<live pid>/environ, not model.env
  Q3 functioning: newest ROW clock (data, not file mtime) + log evidence
  Q5 freshness : age of newest row; whether anything refreshes it
  Q6 dependents: which modules READ it

Q4 (what notices) needs judgement and is filled in by hand.

STRICTLY READ-ONLY: every store opened mode=ro. Never writes, never
creates, never connects to a store in a mode that could create it.
"""
import ast, json, os, re, sqlite3, subprocess, sys, time
from pathlib import Path

REPO = Path("/home/rohit/maez")
# Any column whose NAME looks like a clock. Deliberately over-broad;
# values are validated as plausible epochs/ISO below, so false name
# matches cost nothing. A narrow hand-list already produced a false
# "11 stores have no clock" finding — proposed_at, ts_utc,
# last_recalled_at and first_ts were all missed.
TS_RE = re.compile(
    r"(^|_)(ts|tstamp|timestamp|time|at|date|epoch|when|seen|recalled|"
    r"issued|resolved|proposed|updated|created|started|ended|retired)(_|$)",
    re.I,
)

def live_pid():
    out = subprocess.run(["systemctl","--user","show","-p","MainPID","--value","maez.service"],
                         capture_output=True, text=True).stdout.strip()
    return int(out) if out.isdigit() and out != "0" else None

def live_env(pid):
    env = {}
    try:
        for chunk in Path(f"/proc/{pid}/environ").read_bytes().split(b"\0"):
            s = chunk.decode(errors="ignore")
            if "=" in s:
                k, v = s.split("=", 1); env[k] = v
    except Exception:
        pass
    return env

def prod_sources():
    out = []
    for r in ("core","daemon","skills","scripts","cli","tools"):
        for p in (REPO/r).rglob("*.py"):
            if "worktree" in str(p) or f"{os.sep}tests{os.sep}" in str(p):
                continue
            out.append(p)
    return out

def store_facts(db: Path):
    """Rows, tables, and the NEWEST ROW CLOCK — data freshness, not mtime."""
    facts = {"tables": {}, "newest_row_epoch": None, "newest_col": None}
    if db.stat().st_size == 0:
        return facts
    try:
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    except Exception as e:
        facts["error"] = str(e); return facts
    try:
        tabs = [r[0] for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
        newest = None; newest_col = None
        for t in tabs:
            try:
                n = con.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
            except Exception:
                n = None
            facts["tables"][t] = n
            try:
                cols = [r[1] for r in con.execute(f'PRAGMA table_info("{t}")')]
            except Exception:
                continue
            for c in cols:
                if TS_RE.search(c):
                    try:
                        v = con.execute(f'SELECT MAX("{c}") FROM "{t}"').fetchone()[0]
                    except Exception:
                        continue
                    if v is None: continue
                    ep = None
                    if isinstance(v,(int,float)):
                        ep = float(v)
                        if ep > 1e11: ep /= 1000.0      # ms
                    elif isinstance(v,str):
                        m = re.match(r"(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2}):(\d{2})", v)
                        if m:
                            try:
                                ep = time.mktime(time.strptime(v[:19], "%Y-%m-%d %H:%M:%S"
                                                 if " " in v[:19] else "%Y-%m-%dT%H:%M:%S"))
                            except Exception: ep = None
                    if ep and 1_000_000_000 < ep < 3_000_000_000:
                        if newest is None or ep > newest:
                            newest = ep; newest_col = f"{t}.{c}"
        facts["newest_row_epoch"] = newest
        facts["newest_col"] = newest_col
    finally:
        con.close()
    return facts

def main():
    pid = live_pid(); env = live_env(pid) if pid else {}
    srcs = prod_sources()
    blob = {}
    for p in srcs:
        try: blob[p] = p.read_text(errors="ignore")
        except Exception: pass

    def strip_comments(t):
        return "\n".join(l for l in t.split("\n") if not l.strip().startswith("#"))

    now = time.time()
    rows = []
    for db in sorted((REPO/"memory").glob("*.db")):
        name = db.name
        pat = re.compile(r"(?<![A-Za-z0-9_])"+re.escape(name))
        refs, writers, readers = [], [], []
        for p, t in blob.items():
            code = strip_comments(t)
            if not pat.search(code):
                continue
            rel = str(p.relative_to(REPO))
            refs.append(rel)
            if re.search(r"INSERT\s+INTO|UPDATE\s+\w+\s+SET|CREATE\s+TABLE", code, re.I):
                writers.append(rel)
            if re.search(r"SELECT\s", code, re.I):
                readers.append(rel)
        # flags mentioned in the referencing modules
        flags = set()
        for rel in refs:
            for f in re.findall(r"MAEZ_[A-Z0-9_]+", blob[REPO/rel]):
                flags.add(f)
        facts = store_facts(db)
        newest = facts["newest_row_epoch"]
        rows.append({
            "store": name,
            "bytes": db.stat().st_size,
            "file_mtime_days": round((now - db.stat().st_mtime)/86400, 1),
            "newest_row_days": (round((now-newest)/86400,1) if newest else None),
            "newest_col": facts["newest_col"],
            "tables": facts["tables"],
            "code_refs": len(refs),
            "writers": sorted(set(writers)),
            "readers": sorted(set(readers)),
            "flags_in_scope": sorted(flags),
            "flags_live": sorted([f for f in flags if env.get(f, "") not in ("", "0")]),
            "flags_off": sorted([f for f in flags if env.get(f, "") in ("", "0")]),
        })
    print(json.dumps({"live_pid": pid, "generated_epoch": now, "stores": rows}, indent=1))

main()
