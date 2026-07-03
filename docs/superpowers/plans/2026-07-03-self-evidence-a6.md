# Self-Evidence (A6) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.

**Goal:** A pure, read-only reader that aggregates Maez's integrity receipts (scars, fabrication catches, redo outcomes, veto-proven-wrong, card rejections) from four existing stores into one honest, deduplicated index — counts, timestamps, per-source coverage — with no LLM, no write path, no score, no first-person rendering, and no voice/prompt wiring.

**Architecture:** One pure module `core/learning/self_evidence.py` exposing `self_evidence_digest(window=None) -> dict`. It composes read-only `coverage()` descriptors that each source module reports about *itself* (so A6 hardcodes no source's retention policy), reuses `consequence_memory.stats()` for scar-class counts, and enumerates the scar sidecar via a new public `ScarSidecar.list_all()` to unify overlaps (a raw row a scar already cites is counted once). One owner inspection surface: `scripts/self_evidence.py`, gated behind `MAEZ_SELF_EVIDENCE`.

**Tech Stack:** Python 3.12; sqlite3 opened **read-only** (`file:...?mode=ro`, `uri=True`); host tests `/home/rohit/maez/.venv/bin/python -B -m unittest` (NOT pytest).

**Spec:** `docs/superpowers/specs/2026-07-03-self-evidence-a6-design.md` (@e2f8ac1).

**Task 0 (DONE 2026-07-03 — plan written on this ground):** `consequence_memory.stats()` returns `{total, by_class:{class:{count,heeded}}}` (reuse for scar-class counts; filter to `SCAR_CLASSES`). `ScarSidecar` has NO enumeration method → add public `list_all()`. Live sidecar rows cite `exhibit:<tier>/<row_id>` only → **no real raw overlap exists live**, so the dedup witness MUST seed one. Source-native ids confirmed: `fabrication_events.id`, `veto_events.id`, `consequence.id` are autoincrement PKs. Retention verified per-source: fabrication `_FAB_RETENTION_DAYS=90` best-effort; consequence/veto no deletion (veto `_resolve_expired` only relabels); sidecar append-preserving. Sources' DBs: `memory/{fabrication_log.db,veto_ledger.db,consequence_memory.db,scar_tissue.db}`.

## Hard Invariants (from spec + Codex plan-pins)
- **Reader, never author:** no LLM, no write to any source, no synthesized/first-person sentence. Flag-on writes zero rows anywhere.
- **Read-only, never create:** every source read opens `mode=ro` and NEVER calls `_ensure_db`/any initializer. A missing DB → `status: "no_data"` AND creates no file.
- **No score:** output contains no key `score`/`grade`/`rating` and no ratio-as-verdict. Structural test enforces this.
- **Per-source coverage:** each source labels its own retention truth (from its own module's `coverage()`); A6 never merges into one all-time number. Empty/zero renders explicit (`no_data`/`0`), never omitted.
- **`claim_receipt_redo` is combined** with `outcome_detail: "unstructured"`. A6 authors NO schema; held/corrected split is A1's lane.
- **Real-overlap dedup:** dedup witness uses an actual sidecar row citing a real raw native id — never two synthetic strings.
- **Live counts live in the witness artifact, never in unit tests** (they drift). Tests assert structure/invariants over seeded fixtures.
- **No first-person rendering:** the script/surface prints `fabrication_events: N`, never `I have fabricated N times`.

---

## Task 1: read-only `coverage()` on each source + `ScarSidecar.list_all()`

**Files:** Modify `core/learning/fabrication_memory.py`, `core/learning/consequence_memory.py`, `core/routing/veto_ledger.py`, `core/learning/scar_tissue.py`; Test `tests/test_self_evidence_coverage.py` (create)

Each `coverage()` opens the DB **read-only, existence-checked first** (never creates), returns a plain dict. Shape:
```python
# fabrication_memory.coverage()
{"status": "ok", "retained_rows": N, "earliest_row_ts": .., "latest_row_ts": ..,
 "retention": "90d_best_effort"}          # "90d" comes from _FAB_RETENTION_DAYS, NOT hardcoded elsewhere
# missing DB:
{"status": "no_data", "retention": "90d_best_effort"}
```
`consequence_memory.coverage()` → `{"status","earliest_row_ts","latest_row_ts","retention":"none"}` (counts come from the existing `stats()`). `veto_ledger` → module-level `coverage()` → `{"status","total_events":N,"likely_wrong":M,"earliest_row_ts":..,"retention":"none"}`. `ScarSidecar.list_all()` → `list[dict]` (dedup_key, active_episode_id, receipt_refs, occurrence_count, first_ts, last_ts) reusing its existing `_decode_list`; `ScarSidecar.coverage()` → `{"status","active_episodes":N,"total_occurrences":M,"retention":"append_preserving"}`.

Shared read-only helper (add to each module, or a tiny `core/infra/ro_sqlite.py`):
```python
def _ro_connect(path):
    from pathlib import Path
    import sqlite3
    if not Path(path).exists():
        return None                      # caller renders no_data; NO creation
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    return con
```

- [ ] **Step 1: Failing tests** (`tests/test_self_evidence_coverage.py`):
```python
import sqlite3, tempfile, unittest
from pathlib import Path


class CoverageReadOnlyTests(unittest.TestCase):
    def test_missing_db_returns_no_data_and_creates_no_file(self):
        from core.learning import fabrication_memory as fm
        with tempfile.TemporaryDirectory() as td:
            missing = Path(td) / "nope.db"
            cov = fm._coverage_at(missing)          # implementer: parametrized read for the test
            self.assertEqual(cov["status"], "no_data")
            self.assertFalse(missing.exists())       # READ-ONLY: reporting no_data created nothing

    def test_coverage_reports_retention_from_module_constant(self):
        from core.learning import fabrication_memory as fm
        self.assertIn("90d", fm.coverage()["retention"])  # policy from _FAB_RETENTION_DAYS, not A6

    def test_ro_connect_cannot_write(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "x.db"
            sqlite3.connect(p).executescript("CREATE TABLE t(a); INSERT INTO t VALUES(1);")
            from core.infra.ro_sqlite import _ro_connect   # or module-local equivalent
            con = _ro_connect(p)
            with self.assertRaises(sqlite3.OperationalError):
                con.execute("INSERT INTO t VALUES(2)")       # ro rejects writes


class SidecarListAllTests(unittest.TestCase):
    def test_list_all_enumerates_rows(self):
        from core.learning.scar_tissue import ScarSidecar
        with tempfile.TemporaryDirectory() as td:
            s = ScarSidecar(Path(td) / "s.db")
            s.register("k1", episode_id="ep-1", receipt_ref="fabrication:5", occurred_at="2026-07-03T00:00:00Z")
            s.register("k2", episode_id="ep-2", receipt_ref="veto:9", occurred_at="2026-07-03T00:00:00Z")
            rows = s.list_all()
            self.assertEqual({r["dedup_key"] for r in rows}, {"k1", "k2"})
            self.assertIn("fabrication:5", sum((r["receipt_refs"] for r in rows), []))
```
- [ ] **Step 2: RED.** — [ ] **Step 3: Implement** the shared `_ro_connect`, each `coverage()`, and `ScarSidecar.list_all()`. Retention strings derive from each module's own constant. — [ ] **Step 4: GREEN + existing suites for all four modules still pass** (`tests.test_fabrication_memory tests.test_consequence_memory tests.test_scar_tissue` + veto's suite). — [ ] **Step 5: Commit** `feat(self-evidence): read-only coverage() per source + ScarSidecar.list_all()`

---

## Task 2: `self_evidence_digest()` — sources composition

**Files:** Create `core/learning/self_evidence.py`; Test `tests/test_self_evidence.py` (create)

- [ ] **Step 1: Failing tests**
```python
import tempfile, unittest
from pathlib import Path
from unittest import mock


class DigestSourcesTests(unittest.TestCase):
    def _digest(self, **overrides):
        from core.learning import self_evidence
        return self_evidence.self_evidence_digest(**overrides)

    def test_missing_source_renders_no_data_not_omitted(self):
        # point every source at a missing dir; each source key present with status no_data
        d = self._digest()   # implementer injects tmp/missing paths via a seam
        for key in ("fabrication_events", "veto_proven_wrong", "consequence_scar_classes", "scar_sidecar"):
            self.assertIn(key, d["sources"])
            self.assertEqual(d["sources"][key]["status"], "no_data")

    def test_explicit_zero_for_veto_with_no_likely_wrong(self):
        # seed veto with 3 events, none likely_wrong -> count 0, NOT missing
        d = self._digest()   # with seeded veto fixture
        self.assertEqual(d["sources"]["veto_proven_wrong"]["count"], 0)

    def test_no_score_key_anywhere(self):
        import json
        blob = json.dumps(self._digest()).lower()
        for banned in ('"score"', '"grade"', '"rating"'):
            self.assertNotIn(banned, blob)

    def test_redo_is_combined_with_unstructured_detail(self):
        d = self._digest()   # with a seeded claim_receipt_redo consequence row
        self.assertEqual(
            d["sources"]["consequence_scar_classes"]["outcome_detail"]["claim_receipt_redo"],
            "unstructured",
        )

    def test_coverage_note_present_no_global_alltime(self):
        d = self._digest()
        self.assertIn("per-source", d["coverage_note"])
        self.assertEqual(d["kind"], "self_evidence_integrity_ledger")
```
Implementer adds a single injection seam (e.g. `self_evidence_digest(*, _sources=None)`) so tests point sources at tmp fixtures; production default reads the real modules' `coverage()`/`stats()`.
- [ ] **Step 2: RED.** — [ ] **Step 3: Implement** — compose `sources` from each `coverage()` + `consequence_memory.stats()` filtered to `consequence_memory.SCAR_CLASSES`; attach `outcome_detail={"claim_receipt_redo":"unstructured"}`; build the fixed `kind`/`generated_at`/`window`/`coverage_note`. Any source raising → `status:"unavailable"` (never omitted, never raises out). — [ ] **Step 4: GREEN.** — [ ] **Step 5: Commit** `feat(self-evidence): digest sources composition (no_data/zero explicit, no score, redo combined)`

---

## Task 3: `merged_events` — real-overlap dedup (the hard witness)

**Files:** Modify `core/learning/self_evidence.py`; Test additions to `tests/test_self_evidence.py`

Merged-event identity: a raw row (`fabrication:<id>`/`veto:<id>`/`consequence:<id>`) that a sidecar row's `receipt_refs` names is the SAME event as that scar → counted once. `distinct_integrity_events = (raw ids not claimed by any sidecar row) + (sidecar active episodes)`; `overlap_unified = count of raw ids claimed`.

- [ ] **Step 1: Failing test** (uses a REAL sidecar row citing a REAL raw id — Codex pin):
```python
class MergedDedupTests(unittest.TestCase):
    def test_scarred_fabrication_row_counts_once(self):
        from core.learning.scar_tissue import ScarSidecar
        from core.learning import self_evidence
        with tempfile.TemporaryDirectory() as td:
            # seed ONE real fabrication_events row id=5 and ONE real consequence row id=9
            fab_db = Path(td) / "fabrication_log.db"; _seed_fab_row(fab_db, row_id=5)
            cons_db = Path(td) / "consequence_memory.db"; _seed_consequence_scar(cons_db, row_id=9, kind="fabrication_catch")
            side = ScarSidecar(Path(td) / "scar_tissue.db")
            side.register("fabrication:token", episode_id="ep-1",
                          receipt_ref="fabrication:5", occurred_at="2026-07-03T00:00:00Z")
            side.merge_evidence("fabrication:token", receipt_refs=["consequence:9"],
                                occurred_at="2026-07-03T00:00:00Z", count_occurrence=False)
            d = self_evidence.self_evidence_digest(_sources=_tmp_sources(fab_db, cons_db, side))
            merged = d["merged_events"]
            # the fabrication row (5) AND consequence row (9) are BOTH claimed by the scar ->
            # this is ONE event, not three
            self.assertEqual(merged["overlap_unified"], 2)     # two raw ids unified into the scar
            self.assertEqual(merged["distinct_integrity_events"], 1)

    def test_unscarred_raw_row_is_counted(self):
        # a fabrication row with NO sidecar citation still counts (full-history proof)
        ...
```
`_seed_fab_row`/`_seed_consequence_scar` write ONE real row into a real sqlite file matching the production schema (the test owns the fixture; not synthetic identity strings).
- [ ] **Step 2: RED.** — [ ] **Step 3: Implement** `merged_events`: gather claimed refs from `sidecar.list_all()`, enumerate raw native ids from each source (read-only), compute unified/distinct. — [ ] **Step 4: GREEN.** — [ ] **Step 5: Commit** `feat(self-evidence): merged_events dedup via real sidecar receipt overlap`

---

## Task 4: inspection surface + `MAEZ_SELF_EVIDENCE` flag + no-first-person guard

**Files:** Create `scripts/self_evidence.py`; Test `tests/test_self_evidence_surface.py` (create)

- [ ] **Step 1: Failing tests**
```python
class SurfaceTests(unittest.TestCase):
    def test_flag_off_surface_is_inert(self):
        import os
        from scripts import self_evidence as cli
        with mock.patch.dict(os.environ, {"MAEZ_SELF_EVIDENCE": "0"}, clear=False):
            out = cli.render(argv=["show"])
            self.assertIn("disabled", out.lower())     # surface gated; digest not printed

    def test_flag_on_renders_digest_without_first_person(self):
        import os
        from scripts import self_evidence as cli
        with mock.patch.dict(os.environ, {"MAEZ_SELF_EVIDENCE": "1"}, clear=False):
            out = cli.render(argv=["show"]).lower()
            for fp in (" i ", "i have", "i've", "myself", "my record"):
                self.assertNotIn(fp, out)              # receipts only, never self-claim prose
            self.assertIn("fabrication_events", out)   # the receipt label is present
```
- [ ] **Step 2: RED.** — [ ] **Step 3: Implement** `scripts/self_evidence.py`: `render(argv)` uses the house strict flag parser on `MAEZ_SELF_EVIDENCE`; off → one-line "self-evidence surface disabled (set MAEZ_SELF_EVIDENCE=1)"; on → pretty-print `self_evidence_digest()` (JSON + a plain label:count table, third-person only). `main()` calls `render(sys.argv[1:])`. — [ ] **Step 4: GREEN.** — [ ] **Step 5: Commit** `feat(self-evidence): owner inspection script behind MAEZ_SELF_EVIDENCE, no first-person render`

---

## Task 5: regression + read-only filesystem proof + STOP

- [ ] **Step 1:**
```bash
/home/rohit/maez/.venv/bin/python -B -W ignore::ResourceWarning -m unittest \
  tests.test_self_evidence_coverage tests.test_self_evidence tests.test_self_evidence_surface \
  tests.test_fabrication_memory tests.test_consequence_memory tests.test_scar_tissue \
  tests.test_scar_hooks tests.test_metabolic_curation -v
```
- [ ] **Step 2: Read-only filesystem proof** — a test (or scripted check) that runs `self_evidence_digest()` against a tmp dir containing NONE of the four DBs and asserts the dir is still empty afterward (reporting `no_data` created no file); and that a full digest against seeded read-only copies leaves their mtime/size unchanged.
- [ ] **Step 3:** ruff on touched files; `git diff --check`; confirm no `_ensure_db`/write API is called on any read path (grep the new module for write-API names → none).
- [ ] **Step 4: STOP.** No merge, no flag flip. Codex cross-lane → Claude cross-verify → merge dormant → owner flips `MAEZ_SELF_EVIDENCE=1` → live witness: `scripts/self_evidence.py show` prints the real index (fabrication `90d_best_effort`/58d/11577, veto `0`, card_rejected `6`, sidecar `4`, the 4 scars counted once) into the **witness artifact** — those live numbers appear there, never in a unit test.

## Self-Review
**Spec coverage:** reader-only (no LLM/write/first-person) enforced by Tasks 2/4 + Step 3 grep; read-only-no-create (Task 1 + Task 5 filesystem proof); per-source `coverage()` with policy from each module's own constant (Task 1); reuse `stats()` for scar-class counts (Task 2); `list_all()` per the pin, not `get` (Task 1); redo combined + `outcome_detail:"unstructured"` (Task 2); real-overlap dedup with a seeded real sidecar row (Task 3); no-score structural test (Task 2); explicit no_data/zero (Task 2); live counts only in the witness artifact (Task 5). 
**Deliberate scoping flagged for review:** the spec named a `/self-evidence` command AND a cockpit panel; v0 ships ONE inspection surface — the runnable `scripts/self_evidence.py` — matching how A1 backfill / A3 curation were witnessed (lowest web/telegram-wiring risk in the covenant-critical first slice). The telegram command and cockpit panel become thin later consumers of `self_evidence_digest()` (the function makes them trivial). If Rohit/Codex want the cockpit panel in v0, it's an added task, not a redesign — the digest is already the single source. **This narrowing is called out here, not silent.**
**Placeholder scan:** `_seed_fab_row`/`_seed_consequence_scar`/`_tmp_sources`/`_coverage_at` are named test fixtures the implementer writes against the real schemas (build-time adaptation, like A1 Task 1's tmp-db pattern) — not TODOs.
**Type consistency:** `self_evidence_digest(window=None, *, _sources=None) -> dict`; `coverage() -> dict` (all four sources); `ScarSidecar.list_all() -> list[dict]`; `render(argv) -> str`. Consistent across tasks.
