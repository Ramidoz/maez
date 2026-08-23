#!/usr/bin/env python3
"""Theme 2 S1 — T5 replay driver (protocol §12.6).

Drives the frozen 20-interaction manifest through the reply machinery,
flags off, inside the containment namespace built by
theme2_s1_airlock.sh. Refuses to run anywhere else.

Usage (inside the namespace only):
    python3 docs/superpowers/witness/theme2_s1_t5_replay.py \
        --manifest docs/superpowers/witness/theme2-s1-replay.json \
        --report   /home/rohit/maez/logs/t5_run.json

The report goes to logs/, which protocol §12.7 excludes from the store
tree and from the archive, so writing it cannot perturb what T5
compares.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import socket
import sys
import time
import traceback
from pathlib import Path

MAEZ_TREE = Path("/home/rohit/maez")
EXPECTED_MANIFEST_SHA = (
    "2b9faf616941bb6a0ab6294e1323e2dd73cb57389ab021cc2b868f59109cb420"
)

# Gate round 13 item B: --clearenv fixes the environment at namespace ENTRY,
# but importing the daemon runs the shipped secrets loader, which repopulates
# config/.env into os.environ exactly as it does in production
# (maez_daemon.py:34 -> secrets.load_ordinary_config_for_process). That is
# correct behavior to exercise, not a leak to suppress -- but it makes
# "nothing MAEZ-shaped" false, so what T5 asserts is the narrower, true
# thing: no PHASE/S1 flag is set. The list is frozen; S1's own flags join it
# when they exist.
FLAGS_THAT_MUST_BE_UNSET = (
    "MAEZ_LEDGER_WRITES",
    "MAEZ_BIRTH_PHASE",
    "MAEZ_BIRTH_LATCH",
    "MAEZ_S1_PHASE_TRUTH",
)
# Gate round 14 item B: these do not gate writes, they select WHICH store is
# read and written -- core.memory.birth_phase.default_ledger_path() honors
# MAEZ_LEDGER_DB_PATH and then core.infra.paths.memory_dir(), which honors
# MAEZ_DATA and MAEZ_HOME. The ordinary config loader can repopulate any
# non-secret name after --clearenv, so an unset check at entry is not enough.
# They are absent from this host's config/.env today; the run fails closed if
# they appear and do not point inside the overlay.
# Gate round 15 item B: checking raw env values against "somewhere under the
# repo" is not the same as checking where the stores actually land.
# MAEZ_DATA=/home/rohit/maez/logs passes a raw under-repo test while moving
# every store to logs/memory -- writable, but EXCLUDED from the projection
# and the archive, so the baseline would silently capture nothing. The guard
# therefore validates the EFFECTIVE resolved paths against the projected
# store tree, and it runs before anything can open a store.
STORE_TREE = MAEZ_TREE / "memory"
LOGS_TREE = MAEZ_TREE / "logs"
# Values safe to record verbatim. Everything else is recorded by NAME only:
# config/.env carries credentials, and a witness report is a committed file.
ENV_VALUES_SAFE_TO_RECORD = (
    "HOME", "LANG", "LC_ALL", "PATH", "PWD", "PYTHONDONTWRITEBYTECODE",
    "PYTHONHASHSEED", "TZ", "VIRTUAL_ENV", "MAEZ_S1_PHASE_TRUTH",
    "MAEZ_LLM_BACKEND",
    "MAEZ_LIVE_FAST_LANE_ENABLED", "MAEZ_WORKING_SELF",
)


def env_snapshot() -> dict:
    return {
        "names": sorted(os.environ),
        "count": len(os.environ),
        "values": {k: os.environ[k] for k in sorted(os.environ)
                   if k in ENV_VALUES_SAFE_TO_RECORD},
        "maez_names": sorted(k for k in os.environ if k.startswith("MAEZ_")),
    }


class ContainmentRefusal(RuntimeError):
    """The driver is not inside the airlock namespace. It will not run."""


def assert_contained() -> dict:
    """Prove containment from inside before importing a single Maez module.

    Three independent checks, all cheap, all recorded. Any failure aborts
    before the reply machinery can construct a store.
    """
    evidence: dict = {}

    # 1. The repo must be read-only. A module-global absolute path can only
    #    be caught by the filesystem, so this is the load-bearing check.
    probe = MAEZ_TREE / ".t5_containment_probe"
    try:
        probe.write_text("x")
    except OSError as e:
        evidence["repo_readonly"] = f"PASS ({e.__class__.__name__}: {e.strerror})"
    else:
        probe.unlink(missing_ok=True)
        raise ContainmentRefusal(
            f"{MAEZ_TREE} is WRITABLE — not inside the airlock namespace"
        )

    # 2. memory/ must be writable, and must not be the live store. The live
    #    store is ~579 MB; an airlock-bound one starts empty.
    mem = MAEZ_TREE / "memory"
    mp = mem / ".t5_containment_probe"
    try:
        mp.write_text("x")
        mp.unlink()
    except OSError as e:
        raise ContainmentRefusal(f"{mem} is not writable: {e}") from e
    live_marker = mem / "db" / "raw"
    if live_marker.exists() and any(live_marker.iterdir()):
        raise ContainmentRefusal(
            f"{live_marker} is populated — this looks like the LIVE store"
        )
    evidence["memory_writable_and_empty"] = "PASS"

    # 3. The network must be unshared (protocol §12.3, hermetic).
    try:
        s = socket.create_connection(("127.0.0.1", 8080), timeout=0.5)
    except OSError as e:
        evidence["network_unreachable"] = f"PASS ({e.__class__.__name__})"
    else:
        s.close()
        raise ContainmentRefusal("127.0.0.1:8080 is reachable — not hermetic")

    # 4. No MAEZ_* flag may be set.
    leaked = sorted(k for k in os.environ if k.startswith("MAEZ_"))
    if leaked:
        raise ContainmentRefusal(f"MAEZ_* set in the namespace: {leaked}")
    evidence["no_maez_env_at_entry"] = "PASS"
    evidence["env_at_entry"] = env_snapshot()
    return evidence


def load_manifest(path: Path) -> list[dict]:
    raw = path.read_bytes()
    got = hashlib.sha256(raw).hexdigest()
    if got != EXPECTED_MANIFEST_SHA:
        raise SystemExit(
            f"manifest digest mismatch: expected {EXPECTED_MANIFEST_SHA}, got {got}"
        )
    return json.loads(raw)["interactions"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--report", required=True)
    # Gate round 16 finding L: the healthy fixture is exactly where the legacy
    # resolver and S1 AGREE (both `gestation`), so a run against it cannot
    # tell a dormant S1 from an accidentally always-on one. The `partial`
    # fixture is where they must DIVERGE -- legacy says gestation for every
    # unreadable or half-built ledger (birth_phase.py:38-66, verified on this
    # host for absent / 0-byte / partial / corrupt), while S1 must say
    # unknown and every consumer must refuse. That divergence is the dormancy
    # proof; the healthy fixture alone is not one.
    ap.add_argument("--fixture", choices=("healthy", "partial"),
                    default="healthy")
    # Gate round 20 F-list item 1: the forced-on producer. G5's dormancy
    # proof needs a run in which S1 is ON against the partial fixture, and
    # the flag is set HERE, inside the contained process, after the
    # containment checks -- not smuggled through the environment where the
    # flags-off assertions would (rightly) refuse it. Expected outcomes
    # invert: refusals are success, stores must NOT grow.
    ap.add_argument("--forced-on", action="store_true",
                    help="enable MAEZ_S1_PHASE_TRUTH inside the namespace "
                         "and witness refusals instead of stores")
    args = ap.parse_args()

    report: dict = {
        "protocol": "theme2-s1 protocol §12.6",
        "started_at": time.time(),
        "python": sys.version,
        "interactions": [],
    }
    report["containment"] = assert_contained()

    interactions = load_manifest(Path(args.manifest))
    report["manifest_sha256"] = EXPECTED_MANIFEST_SHA
    report["interaction_count"] = len(interactions)

    sys.path.insert(0, str(MAEZ_TREE))
    import sqlite3

    report["sqlite_version"] = sqlite3.sqlite_version
    # Round 29 finding #30: nothing in the evidence bound it to the CODE
    # under test — `resolver_module` was an unverified path string, so a
    # record could name any resolver it liked and a PASS was compatible with
    # a different tree entirely. Digest the sources the claim is about.
    # Round 31 #36: the HEALTHY arm had only negative backing ("not the
    # partial ledger"), so one execution could supply both arms by editing
    # two hex strings. The applied-migration set is a fixture-CAUSED fact the
    # judge can check against the protocol's frozen expectation.
    try:
        _c = sqlite3.connect(f"file:{MAEZ_TREE / 'memory' / 'ledger.db'}?mode=ro", uri=True)
        report["applied_migrations"] = sorted(
            r[0] for r in _c.execute("SELECT name FROM schema_migrations"))
        _c.close()
    except sqlite3.Error as exc:
        report["applied_migrations"] = {"error": str(exc)}
    # Round 31 #38 (partial): nothing required a record to have come from
    # THIS producer inside THIS airlock. Digest both.
    report["instrument_digests"] = {
        rel: hashlib.sha256((Path(__file__).resolve().parent / rel).read_bytes()).hexdigest()
        for rel in ("theme2_s1_t5_replay.py", "theme2_s1_airlock.sh")}
    report["source_digests"] = {}
    for rel in ("core/memory/birth_phase.py", "memory/memory_manager.py",
                "core/infra/private_thoughts.py", "core/ledger/writer.py"):
        try:
            report["source_digests"][rel] = hashlib.sha256(
                (MAEZ_TREE / rel).read_bytes()).hexdigest()
        except OSError as exc:
            raise SystemExit(f"REFUSED: cannot digest {rel}: {exc}")

    # Gate round 15 item B: reproduce production's environment ordering
    # OURSELVES, before importing the daemon -- importing it runs this same
    # loader (maez_daemon.py:34) and then immediately opens stores
    # (action_engine.py:51/73), so a guard placed after the import would run
    # too late to prevent anything.
    from core.infra.secrets import load_ordinary_config_for_process
    loaded = load_ordinary_config_for_process()
    report["ordinary_config_loaded_names"] = sorted(loaded)
    report["env_after_config_load"] = env_snapshot()

    set_flags = [f for f in FLAGS_THAT_MUST_BE_UNSET if os.environ.get(f)]
    if set_flags:
        raise SystemExit(f"REFUSED: flags-off violated: {set_flags}")
    if args.forced_on:
        # Set AFTER the environment was proven clean, so the report shows
        # the flag came from this producer and nowhere else.
        os.environ["MAEZ_S1_PHASE_TRUTH"] = "1"
        report["forced_on"] = True

    from core.infra import paths as _paths
    from core.memory.birth_phase import default_ledger_path

    def effective_paths() -> dict:
        return {
            "home": _paths.home(),
            "data_dir": _paths.data_dir(),
            "config_dir": _paths.config_dir(),
            "cache_dir": _paths.cache_dir(),
            "memory_dir": _paths.memory_dir(),
            "memory_db_dir": _paths.memory_db_dir(),
            "audit_log_db": _paths.audit_log_db(),
            "logs_dir": _paths.logs_dir(),
            "ledger": default_ledger_path(),
        }

    # Every path is pinned by EXACT equality. Gate round 16: config_dir and
    # cache_dir were unchecked, and audit_log_db accepted any descendant of
    # memory/ -- which would admit an alias to an unrelated database.
    REQUIRED = {
        "home": MAEZ_TREE, "data_dir": MAEZ_TREE,
        "config_dir": MAEZ_TREE / "config", "cache_dir": MAEZ_TREE / ".cache",
        "memory_dir": STORE_TREE, "memory_db_dir": STORE_TREE / "db",
        "audit_log_db": STORE_TREE / "audit_log.db",
        "logs_dir": LOGS_TREE, "ledger": STORE_TREE / "ledger.db",
    }

    def assert_paths(when: str) -> dict:
        eff = effective_paths()
        wrong = {k: str(eff[k]) for k, want in REQUIRED.items()
                 if Path(eff[k]).resolve() != want}
        if wrong:
            raise SystemExit(
                f"REFUSED ({when}): effective store paths are not the "
                f"projected tree: {wrong}")
        return {k: str(v) for k, v in eff.items()}

    report["effective_store_paths_before_import"] = assert_paths("pre-import")

    # Gate round 12, item B: the ledger is migrated INSIDE the namespace.
    # Doing it before namespace entry left a Python startup -- imports,
    # site/.pth, bytecode, inherited descriptors -- outside the boundary
    # the protocol claims to be total. Nothing runs outside now.
    from core.ledger.migrate import run as migrate_run

    ledger = MAEZ_TREE / "memory" / "ledger.db"
    report["fixture"] = args.fixture
    if args.fixture == "healthy":
        migrate_run(str(ledger))
    else:
        # migrations 0001..0002 only: a structurally incomplete ledger.
        mig = MAEZ_TREE / "core" / "ledger" / "migrations"
        conn = sqlite3.connect(ledger)
        for name in ("0001_init.sql", "0002_triggers.sql"):
            conn.executescript((mig / name).read_text())
        conn.commit()
        conn.close()
    report["ledger_post_migration_sha256"] = hashlib.sha256(
        ledger.read_bytes()).hexdigest()
    report["ledger_post_migration_file_set"] = sorted(
        q.name for q in ledger.parent.iterdir() if q.name.startswith("ledger.db"))

    # Import and construct only after containment is proven. Constructing
    # MaezDaemon builds MemoryManager, which mkdirs and opens Chroma at
    # memory_manager.BASE_DB -- the un-redirectable literal. Inside the
    # namespace that resolves into the airlock.
    # Round 19 Q4: the airlock puts a writable tmpfs over ALL of /home/rohit,
    # so naming two subtrees under it left /home/rohit/.local/state/x.db free
    # to escape. Sweep the home root -- minus the read-only repo bind inside
    # it -- and take the inventory BEFORE anything can create a store.
    WRITABLE_ROOTS = (
        LOGS_TREE, MAEZ_TREE / ".cache", Path("/home/rohit"),
        Path("/tmp"), Path("/run"), Path("/var/tmp"),
    )

    from daemon.maez_daemon import MaezDaemon

    # Gate round 16 item B: the daemon import calls the ordinary config
    # loader a SECOND time (maez_daemon.py:34), and a first .env can set
    # MAEZ_CONFIG so the second call reads a different file. The environment
    # checked before the import is therefore not necessarily the final one.
    # Re-assert on the post-import state; this is the configuration that
    # actually runs.
    report["env_after_import"] = env_snapshot()
    set_flags_2 = [f for f in FLAGS_THAT_MUST_BE_UNSET
                   if os.environ.get(f)
                   and not (f == "MAEZ_S1_PHASE_TRUTH" and args.forced_on)]
    if set_flags_2:
        raise SystemExit(
            f"REFUSED: flags-off violated after import: {set_flags_2}")
    report["effective_store_paths_after_import"] = assert_paths("post-import")
    report["flags_off_after_import"] = "PASS"

    _MAGIC = b"SQLite format 3\x00"

    def _pre_sweep() -> set[str]:
        found: set[str] = set()
        for root in WRITABLE_ROOTS:
            if not root.exists():
                continue
            for q in root.rglob("*"):
                try:
                    if root == Path("/home/rohit") and MAEZ_TREE in q.parents:
                        continue
                    if not q.is_file():
                        continue
                    with q.open("rb") as fh:
                        if fh.read(16) == _MAGIC:
                            found.add(str(q))
                except OSError:
                    continue
        return found

    stray_inventory_before = _pre_sweep()
    report["stray_store_inventory_before_count"] = len(stray_inventory_before)

    t0 = time.time()
    daemon = MaezDaemon()
    report["daemon_construct_seconds"] = round(time.time() - t0, 3)

    # Gate round 13 finding I: two equally EMPTY store trees agree with each
    # other and prove nothing. Without a positive control, a run in which
    # every handle_message raised would still exit 0 and still produce a
    # "baseline". So: count the store tail's invocations and its observable
    # effect, and fail the run if the tail never executed.
    tail_calls = {"store_telegram": 0}
    consumer_refusals: list[dict] = []
    _orig_store = daemon.memory.store_telegram

    def _counting_store(*a, **kw):
        tail_calls["store_telegram"] += 1
        try:
            return _orig_store(*a, **kw)
        except Exception as exc:                     # noqa: BLE001
            # Forced-on, a PhaseUnknownRefusal here IS the witnessed
            # behaviour G5 requires — record it with its consumer and
            # reason, then re-raise so the caller's own handling (and the
            # flags-off failure path) stay untouched.
            consumer_refusals.append({
                "consumer": "memory_manager.store_telegram",
                "exception": type(exc).__name__,
                "message": str(exc)[:200],
            })
            raise

    # Observation only: the proxy calls through unchanged and is removed
    # before the store tree is projected.
    daemon.memory.store_telegram = _counting_store

    def collection_counts() -> dict:
        out = {}
        for name in ("raw", "daily", "core"):
            try:
                out[name] = getattr(daemon.memory, name).count()
            except Exception as e:                       # noqa: BLE001
                out[name] = f"error: {type(e).__name__}"
        return out

    # The stamp census: what memory_phase values actually landed, per store.
    # This is the quantity the discriminator compares -- flags off must
    # reproduce the legacy stamps on BOTH fixtures, and a forced-on S1 must
    # change them on the partial fixture.
    def stamp_census() -> dict:
        out: dict = {}
        for name in ("raw", "daily", "core"):
            try:
                col = getattr(daemon.memory, name)
                got = col.get(include=["metadatas"])
                counts: dict = {}
                for md in (got.get("metadatas") or []):
                    v = (md or {}).get("memory_phase")
                    counts[str(v)] = counts.get(str(v), 0) + 1
                out[f"chroma::{name}"] = dict(sorted(counts.items()))
            except Exception as e:                       # noqa: BLE001
                out[f"chroma::{name}"] = f"error: {type(e).__name__}"
        # Gate round 17 item B: censusing a reconstructed filename reads the
        # wrong file when a selector moved the store. Ask each module where
        # its store actually is.
        from core.infra.private_thoughts import _default_private_thoughts_path
        for label, dbp in (("private_thoughts",
                            _default_private_thoughts_path()),
                           ("audit_log", _paths.audit_log_db())):
            if not dbp.exists():
                out[label] = "absent"
                continue
            try:
                c = sqlite3.connect(f"file:{dbp}?mode=ro", uri=True)
                rows = c.execute(
                    f"SELECT memory_phase, COUNT(*) FROM {label} "
                    "GROUP BY memory_phase").fetchall()
                c.close()
                out[label] = {str(k): v for k, v in rows}
            except Exception as e:                       # noqa: BLE001
                out[label] = f"error: {type(e).__name__}"
        return out

    report["collection_counts_before"] = collection_counts()

    # The phase probe: what the resolver answers on THIS fixture, recorded
    # before the replay so the report states the behavior under test rather
    # than leaving it to be inferred from stamps.
    from core.memory import birth_phase as _bp
    report["phase_probe"] = {
        "resolver_module": _bp.__file__,
        "current_phase": _bp.current_phase(str(ledger)),
        "birth_event_turn_id": _bp.birth_event_turn_id(str(ledger)),
        "has_resolve_api": hasattr(_bp, "resolve"),
    }
    if hasattr(_bp, "resolve"):
        r = _bp.resolve()
        report["phase_probe"]["resolve"] = {
            "phase": getattr(r, "phase", None),
            "reason": getattr(r, "reason", None)}

    for item in interactions:
        rec = {"id": item["id"], "at": item["at"], "source": item["source"]}
        # Gate round 14 finding I: an aggregate "tail invoked at least once"
        # passes on 19 returned-before-tail interactions plus one stored one,
        # and production has returned-before-tail paths
        # (maez_daemon.py:7197). Bind EVERY interaction to its own observed
        # passage instead.
        before = tail_calls["store_telegram"]
        t = time.time()
        try:
            reply = daemon.handle_message(item["text"], source=item["source"])
            rec["reply"] = reply
            rec["outcome"] = "returned"
        except Exception as e:                      # noqa: BLE001
            rec["outcome"] = "raised"
            rec["exception"] = f"{type(e).__name__}: {e}"
            rec["traceback"] = traceback.format_exc()
        rec["seconds"] = round(time.time() - t, 3)
        rec["tail_passages"] = tail_calls["store_telegram"] - before
        report["interactions"].append(rec)

    daemon.memory.store_telegram = _orig_store
    report["collection_counts_after"] = collection_counts()
    report["store_tail_invocations"] = tail_calls["store_telegram"]

    returned = sum(1 for r in report["interactions"] if r["outcome"] == "returned")
    raised = [r["id"] for r in report["interactions"] if r["outcome"] == "raised"]
    no_tail = [r["id"] for r in report["interactions"]
               if r.get("tail_passages", 0) < 1]
    before, after = (report["collection_counts_before"],
                     report["collection_counts_after"])
    grew = any(isinstance(after.get(k), int) and isinstance(before.get(k), int)
               and after[k] > before[k] for k in ("raw", "daily", "core"))
    report["stamp_census"] = stamp_census()
    report["consumer_refusals"] = consumer_refusals
    SQLITE_MAGIC = b"SQLite format 3\x00"

    def looks_like_sqlite(q: Path) -> bool:
        try:
            with q.open("rb") as fh:
                return fh.read(16) == SQLITE_MAGIC
        except OSError:
            return False

    def sweep() -> set[str]:
        found: set[str] = set()
        for root in WRITABLE_ROOTS:
            if not root.exists():
                continue
            for q in root.rglob("*"):
                try:
                    # The repo is --ro-bind mounted inside the home tmpfs;
                    # nothing there can be written, and walking it costs
                    # seconds. logs/ and .cache/ are swept as their own roots.
                    if root == Path("/home/rohit") and \
                            MAEZ_TREE in q.parents:
                        continue
                    if not q.is_file():
                        continue
                    if q.resolve().is_relative_to(STORE_TREE):
                        continue          # inside the projected tree
                    if looks_like_sqlite(q):
                        found.add(str(q))
                except OSError:
                    continue
        return found

    def collect_containment_evidence():
        # Round 29 finding #29: this ran only on the flags-off path, so the
        # forced-on record carried no census paths at all and its stores were
        # unconstrained. Both paths record where their stores actually went.
        report["census_resolved_paths"] = {
            "private_thoughts": str(
                __import__("core.infra.private_thoughts", fromlist=["x"])
                ._default_private_thoughts_path()),
            "audit_log": str(_paths.audit_log_db()),
        }

        """Round 27 finding #14: the forced-on branch RETURNED before these
        sweeps ran, so the report proving "nothing was stored" carried no
        latch sweep, no escaped-store sweep, and no post-replay ledger
        digest — the two halves of the discriminator were held to different
        standards. Both paths call this now, before either writes."""
        # Gate round 19 Q1.1: K2 read `ledger_post_replay_file_set`, which the
        # driver fills only with `ledger.db*` names, so a real
        # memory/birth_observed/segment-000001.jsonl could exist while K2 passed.
        # Sweep the whole store tree and give K2 something that can be false.
        latch = []
        for q in STORE_TREE.rglob("*"):
            try:
                if "birth_observed" in q.parts or q.name.startswith("segment-") \
                        or q.name.endswith(".tmp"):
                    latch.append(str(q.relative_to(STORE_TREE)))
            except OSError:
                continue
        report["latch_artifacts_in_store_tree"] = sorted(latch)

        strays = sorted(sweep() - stray_inventory_before)
        report["stray_store_sweep_roots"] = [str(r) for r in WRITABLE_ROOTS]
        report["stray_store_inventory_before"] = len(stray_inventory_before)
        report["stray_stores_outside_projected_tree"] = strays
        if strays:
            raise SystemExit(
                f"REFUSED: the run created stores outside the projected tree: "
                f"{strays}")

        report["reply_shapes"] = {
            r["id"]: {"chars": len(r.get("reply") or ""),
                      "empty": not (r.get("reply") or "").strip()}
            for r in report["interactions"]}
        report["brain_reachable"] = False

        # Gate round 12, item C: flags off, the ledger is NOT "never opened" --
        # the evidence-envelope builder opens it read-only (envelope_builder.py:268,
        # recent_turns.py:97), and a read-only open of a WAL database creates the
        # -shm/-wal sidecars. The main-file digest is what B1 asserts; record the
        # sidecar reality rather than claim it away.
        report["ledger_post_replay_sha256"] = hashlib.sha256(
            (MAEZ_TREE / "memory" / "ledger.db").read_bytes()).hexdigest()
        report["ledger_post_replay_file_set"] = sorted(
            q.name for q in (MAEZ_TREE / "memory").iterdir()
            if q.name.startswith("ledger.db"))
        report["ledger_main_file_unchanged"] = (
            report["ledger_post_replay_sha256"]
            == report["ledger_post_migration_sha256"])

    if args.forced_on:
        # G5's contract (protocol §12.8 v7): resolve() reads unknown, every
        # reached consumer refuses with PhaseUnknownRefusal, no store grows,
        # zero gestation stamps land. The flags-off control below would call
        # that failure; here it is precisely success.
        refused_ok = bool(consumer_refusals) and all(
            r["exception"] == "PhaseUnknownRefusal"
            for r in consumer_refusals)
        grew_any = any(
            isinstance(report["collection_counts_after"].get(k), int)
            and isinstance(report["collection_counts_before"].get(k), int)
            and report["collection_counts_after"][k]
                > report["collection_counts_before"][k]
            for k in ("raw", "daily", "core"))
        gest = [s_ for s_, v in report["stamp_census"].items()
                if isinstance(v, dict) and v.get("gestation")]
        report["positive_control"] = {
            "mode": "forced_on",
            "refusals_observed": len(consumer_refusals),
            "all_refusals_typed": refused_ok,
            "collections_grew": grew_any,
            "stores_with_gestation_stamps": gest,
            "verdict": ("PASS" if refused_ok and not grew_any and not gest
                        else "FAIL"),
        }
        collect_containment_evidence()
        out = Path(args.report)
        out.parent.mkdir(parents=True, exist_ok=True)
        report["finished_at"] = time.time()
        out.write_text(json.dumps(report, indent=1, default=str) + "\n")
        pc = report["positive_control"]
        print(f"forced-on run: {pc['refusals_observed']} refusals, "
              f"grew={pc['collections_grew']}, verdict {pc['verdict']}")
        return 0 if pc["verdict"] == "PASS" else 1

    report["positive_control"] = {
        "interactions_returned": returned,
        "interactions_raised": raised,
        "interactions_without_tail_passage": no_tail,
        "store_tail_invocations": tail_calls["store_telegram"],
        "collections_grew": grew,
        "verdict": ("PASS" if (returned == len(interactions)
                               and not no_tail
                               and grew) else "FAIL"),
    }
    # T5 deliberately exercises the hermetic fallback, so a reply that is a
    # degraded string is expected -- but it must never be reported as healthy
    # synthesis. Label the shape; do not judge it here.

    # Gate round 17/18 item B: enumerating selectors one at a time will
    # always miss one, so this is the catch-all. Round 19 Q4 asked whether it
    # would wrongly refuse anything legitimate, and the first live run
    # answered yes: adding /home/rohit as a root made it walk the read-only
    # repo mounted inside it and flag 68 pre-existing databases in backups/,
    # .claude/worktrees/, local/quarantine/ and tmp/ -- none of which the run
    # could possibly have created.
    #
    # K4 is about stores the RUN CREATES outside the projected tree, so the
    # honest test is a before/after difference, not an absolute census. The
    # inventory is taken before the daemon is constructed; only paths that
    # appear afterwards are strays.
    collect_containment_evidence()
    report["finished_at"] = time.time()
    out = Path(args.report)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=1, default=str) + "\n")
    pc = report["positive_control"]
    print(f"t5 replay: {len(interactions)} interactions, "
          f"{pc['interactions_returned']} returned, "
          f"tail x{pc['store_tail_invocations']}, "
          f"positive control {pc['verdict']} -> {out}")
    # A run whose positive control failed is not a baseline. Exit non-zero so
    # the orchestration cannot archive it.
    return 0 if pc["verdict"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
