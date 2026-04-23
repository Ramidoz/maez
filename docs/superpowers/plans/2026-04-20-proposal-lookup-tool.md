# Proposal Lookup Tool Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Tier-0 `lookup_proposal(proposal_id)` action so Maez's brain_loop can retrieve a proposal's content by ID directly from the SQLite stores, instead of falling back to `grep -r` over the filesystem.

**Architecture:** A new module `core/proposal_lookup.py` exposes one pure function `lookup(proposal_id: int) -> dict` that queries `memory/evolution_track.db::candidates` and `memory/dream_proposals.db::dream_proposals` by ID and returns a compact structured summary. The action surface lives on `core.action_engine.ActionEngine`: a new public `lookup_proposal` method + `_do_lookup_proposal` dispatcher, registered at tier 0 in `ACTION_TIERS`, and added to the brain_loop's `allowed` set so the planner can actually call it. Read-only by construction; no card, no confirmation. Observed trigger 2026-04-20 — Maez received a stale-proposal reminder for candidate #25, the user asked "what is proposal #25?" in Telegram, and the brain_loop could only `grep -r 'proposal 25' /home/rohit/maez/` (hit `vocab.json` noise).

**Tech Stack:** Python 3.12 stdlib (`sqlite3`), existing `ActionEngine` + `ActionResult` classes, unittest.

---

## Scope boundary

**In:** one new module (`core/proposal_lookup.py`), one new tier-0 action registered via the existing ACTION_TIERS + `_do_X` pattern, brain_loop `allowed` set inclusion, unit tests for each surface.

**Out:** proposal approval/rejection (separate flow, already exists via `/approve`-style CLI commands); mutation of proposal state from this tool; UX for listing recent proposals (only per-ID lookup in this plan — listing is a follow-up if needed).

## File structure

- **Create** `core/proposal_lookup.py` — pure-function module. `lookup(proposal_id: int) -> dict` returns `{"found": bool, "sources": [...], "summary": str}`. Reads both DBs; never writes. Fails open (returns `found=False`) on DB errors.
- **Modify** `core/action_engine.py`
  - Add `'lookup_proposal': 0` to `ACTION_TIERS` dict (currently at L216-245).
  - Add public `lookup_proposal(proposal_id, reasoning)` method that calls `_execute_action("lookup_proposal", {"proposal_id": proposal_id}, reasoning, tier=0)`. Place alongside `query_system` at ~L946.
  - Add `_do_lookup_proposal(proposal_id)` method that calls `core.proposal_lookup.lookup(...)` and formats the returned dict into a human-readable string (same shape as other `_do_*` methods, which return strings that go into the tool transcript).
- **Modify** `core/brain_loop.py` — add `'lookup_proposal'` to the `allowed` set at ~L532 so the planner can emit a `TOOL_CALL` for it. Without this the brain_loop will reject dispatches to it even though ACTION_TIERS has it at tier 0.
- **Create** `tests/test_proposal_lookup.py` — unit tests for the pure-function module (no ActionEngine coupling). Uses temp SQLite DBs to avoid touching prod.
- **Modify** `tests/test_action_engine.py` if it exists — add tests for the registration + tier assignment. **If the file doesn't exist, skip this modification and put a smaller registration-assertion test into `tests/test_proposal_lookup.py` instead.**

## Key facts for the implementer

1. **Evolution candidates schema** (from `memory/evolution_track.db::candidates`): id INTEGER PRIMARY KEY, state, weakness_description, target_file, diff_text, justification, cognition_evidence (JSON), rejection_reason, rollback_reason, rollback_layer, cooldown_key, pre_patch_hash, post_patch_hash, backup_path, pre_patch_score_avg, post_patch_score_avg, created_at, validated_at, applied_at, resolved_at.

2. **Dream proposals schema** (from `memory/dream_proposals.db::dream_proposals`): id INTEGER PRIMARY KEY, created_at, insight, status, applied_at, reject_reason, proposal_type, target_section, proposed_new_body, unified_diff.

3. **Both share the `id` space but are independent tables.** ID 25 can exist in either or both. The lookup returns whatever's present and labels the source.

4. **DBs may be missing** during tests or on a freshly-provisioned box. Fail open with `found=False`, never crash.

5. **Action dispatch** in `core/action_engine.py` uses `getattr(self, f"_do_{action}", None)` at L674, so adding a `_do_lookup_proposal` method is sufficient wiring. No switch table to update.

6. **The brain_loop allowed set** ([core/brain_loop.py:532-542](../../core/brain_loop.py)) gates which action names the planner is permitted to dispatch. If an action is in ACTION_TIERS but NOT in `allowed`, the brain_loop will refuse to send it — the action runs fine from direct callers but the planner can't reach it.

7. **Test runner convention** (repeat from previous plan): stdlib unittest only, Python 3.12 in `.venv/bin/python`, full suite via `cd /home/rohit/maez && .venv/bin/python -m unittest discover -s tests -p 'test_*.py' 2>&1 | tail -5`. Pre-existing `test_fix6_followups` syntax error counts as 1 unrelated error — ignore.

## Proposal #25 as a live reference

While implementing, proposal #25 is real and lives in `memory/evolution_track.db::candidates`. Use it as a sanity check — after wiring, `.venv/bin/python -c "from core import proposal_lookup; print(proposal_lookup.lookup(25))"` should return a dict with `found=True`, `sources=["evolution_candidates"]`, and a summary mentioning `core/cognition_quality.py` and `POLICY_EXPLORATORY_THRESHOLD`.

---

## Task 1: `core/proposal_lookup.py` — pure lookup function

**Files:**
- Create: `core/proposal_lookup.py`
- Create: `tests/test_proposal_lookup.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_proposal_lookup.py` with this exact content:

```python
# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""Unit tests for core.proposal_lookup — the SQLite-backed structured
lookup that replaces `grep -r proposal 25 /home/rohit/maez/` with a
direct query against the two proposal stores.

Observed trigger 2026-04-20: Maez received a stale-proposal reminder
for candidate #25, the user asked 'what is proposal #25?', and the
brain_loop grepped the filesystem (hit vocab.json noise). This tool
gives the planner a dedicated lookup path."""
from __future__ import annotations

import os
import sqlite3
import tempfile
import unittest
from unittest.mock import patch


def _make_evolution_db(path, rows):
    """rows: list of dicts keyed by the candidates-table columns."""
    conn = sqlite3.connect(path)
    conn.execute("""
        CREATE TABLE candidates (
            id INTEGER PRIMARY KEY,
            state TEXT,
            weakness_description TEXT,
            target_file TEXT,
            diff_text TEXT,
            justification TEXT,
            cognition_evidence TEXT,
            rejection_reason TEXT,
            rollback_reason TEXT,
            rollback_layer TEXT,
            cooldown_key TEXT,
            pre_patch_hash TEXT,
            post_patch_hash TEXT,
            backup_path TEXT,
            pre_patch_score_avg REAL,
            post_patch_score_avg REAL,
            created_at TEXT,
            validated_at TEXT,
            applied_at TEXT,
            resolved_at TEXT
        )
    """)
    for r in rows:
        cols = ", ".join(r.keys())
        placeholders = ", ".join("?" for _ in r)
        conn.execute(
            f"INSERT INTO candidates ({cols}) VALUES ({placeholders})",
            tuple(r.values()),
        )
    conn.commit()
    conn.close()


def _make_dream_db(path, rows):
    conn = sqlite3.connect(path)
    conn.execute("""
        CREATE TABLE dream_proposals (
            id INTEGER PRIMARY KEY,
            created_at TEXT,
            insight TEXT,
            status TEXT,
            applied_at TEXT,
            reject_reason TEXT,
            proposal_type TEXT,
            target_section TEXT,
            proposed_new_body TEXT,
            unified_diff TEXT
        )
    """)
    for r in rows:
        cols = ", ".join(r.keys())
        placeholders = ", ".join("?" for _ in r)
        conn.execute(
            f"INSERT INTO dream_proposals ({cols}) VALUES ({placeholders})",
            tuple(r.values()),
        )
    conn.commit()
    conn.close()


class LookupReturnsEvolutionCandidate(unittest.TestCase):
    def test_found_in_evolution_track(self):
        with tempfile.TemporaryDirectory() as tmp:
            evo_path = os.path.join(tmp, "evolution_track.db")
            dream_path = os.path.join(tmp, "dream_proposals.db")
            _make_evolution_db(evo_path, [{
                "id": 25,
                "state": "validated",
                "target_file": "core/cognition_quality.py",
                "weakness_description": "topic concentration on browser_usage",
                "diff_text": "--- a/core/cognition_quality.py\n+++ b/core/cognition_quality.py\n@@ -70,7 +70,7 @@\n-POLICY_EXPLORATORY_THRESHOLD = 0.7\n+POLICY_EXPLORATORY_THRESHOLD = 0.6",
                "created_at": "2026-04-19T19:14:30",
            }])
            _make_dream_db(dream_path, [])

            from core import proposal_lookup
            with patch.object(proposal_lookup, "_EVOLUTION_DB", evo_path), \
                 patch.object(proposal_lookup, "_DREAM_DB", dream_path):
                result = proposal_lookup.lookup(25)

            self.assertTrue(result["found"], f"expected found=True; got {result}")
            self.assertIn("evolution_candidates", result["sources"])
            summary = result["summary"]
            self.assertIn("25", summary)
            self.assertIn("validated", summary)
            self.assertIn("core/cognition_quality.py", summary)
            self.assertIn("POLICY_EXPLORATORY_THRESHOLD", summary)


class LookupReturnsDreamProposal(unittest.TestCase):
    def test_found_in_dream_proposals(self):
        with tempfile.TemporaryDirectory() as tmp:
            evo_path = os.path.join(tmp, "evolution_track.db")
            dream_path = os.path.join(tmp, "dream_proposals.db")
            _make_evolution_db(evo_path, [])
            _make_dream_db(dream_path, [{
                "id": 7,
                "created_at": "2026-04-18T09:00:00",
                "insight": "I've been quiet on weekends — consider gentler tone.",
                "status": "pending",
                "proposal_type": "soul_note",
                "target_section": "voice.weekend",
            }])

            from core import proposal_lookup
            with patch.object(proposal_lookup, "_EVOLUTION_DB", evo_path), \
                 patch.object(proposal_lookup, "_DREAM_DB", dream_path):
                result = proposal_lookup.lookup(7)

            self.assertTrue(result["found"])
            self.assertIn("dream_proposals", result["sources"])
            self.assertIn("7", result["summary"])
            self.assertIn("gentler", result["summary"])


class LookupHandlesMissingId(unittest.TestCase):
    def test_id_absent_from_both_dbs(self):
        with tempfile.TemporaryDirectory() as tmp:
            evo_path = os.path.join(tmp, "evolution_track.db")
            dream_path = os.path.join(tmp, "dream_proposals.db")
            _make_evolution_db(evo_path, [])
            _make_dream_db(dream_path, [])

            from core import proposal_lookup
            with patch.object(proposal_lookup, "_EVOLUTION_DB", evo_path), \
                 patch.object(proposal_lookup, "_DREAM_DB", dream_path):
                result = proposal_lookup.lookup(999)

            self.assertFalse(result["found"])
            self.assertEqual(result["sources"], [])
            self.assertIn("not found", result["summary"].lower())


class LookupFailsOpenOnMissingDb(unittest.TestCase):
    def test_missing_db_file_does_not_crash(self):
        with tempfile.TemporaryDirectory() as tmp:
            # Neither DB exists on disk.
            evo_path = os.path.join(tmp, "nope-evo.db")
            dream_path = os.path.join(tmp, "nope-dream.db")

            from core import proposal_lookup
            with patch.object(proposal_lookup, "_EVOLUTION_DB", evo_path), \
                 patch.object(proposal_lookup, "_DREAM_DB", dream_path):
                result = proposal_lookup.lookup(25)

            self.assertFalse(result["found"])
            self.assertIn("not found", result["summary"].lower())


class LookupFoundInBothDbs(unittest.TestCase):
    def test_id_present_in_both_sources_reports_both(self):
        with tempfile.TemporaryDirectory() as tmp:
            evo_path = os.path.join(tmp, "evolution_track.db")
            dream_path = os.path.join(tmp, "dream_proposals.db")
            _make_evolution_db(evo_path, [{
                "id": 3, "state": "validated",
                "target_file": "core/foo.py",
                "weakness_description": "x",
                "diff_text": "diff",
                "created_at": "2026-04-19T00:00:00",
            }])
            _make_dream_db(dream_path, [{
                "id": 3, "status": "pending",
                "insight": "something",
                "proposal_type": "soul_note",
                "target_section": "voice",
                "created_at": "2026-04-19T00:00:00",
            }])

            from core import proposal_lookup
            with patch.object(proposal_lookup, "_EVOLUTION_DB", evo_path), \
                 patch.object(proposal_lookup, "_DREAM_DB", dream_path):
                result = proposal_lookup.lookup(3)

            self.assertTrue(result["found"])
            self.assertIn("evolution_candidates", result["sources"])
            self.assertIn("dream_proposals", result["sources"])


class LookupValidatesInput(unittest.TestCase):
    def test_non_integer_id_returns_not_found(self):
        from core import proposal_lookup
        result = proposal_lookup.lookup("twenty-five")
        self.assertFalse(result["found"])
        self.assertIn("invalid", result["summary"].lower())


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd /home/rohit/maez && .venv/bin/python -m unittest tests.test_proposal_lookup -v
```

Expected: `ImportError: No module named 'core.proposal_lookup'` on every test. Feature absent. If tests fail for OTHER reasons (syntax, fixture plumbing), fix those before implementing.

- [ ] **Step 3: Implement `core/proposal_lookup.py`**

Create `core/proposal_lookup.py` with this exact content:

```python
# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
"""proposal_lookup.py — structured lookup for Maez's proposal stores.

Built 2026-04-20 after a Telegram turn where the user asked "what is
proposal #25?" and the brain_loop fell back to `grep -r 'proposal 25'
/home/rohit/maez/` which hit vocab.json tokenizer noise. Proposals
live in SQLite, not markdown — the planner needed a dedicated surface.

Two stores are queried:
  - memory/evolution_track.db::candidates — self-edit proposals (the
    evolution system's candidate patches, e.g. candidate #25 that
    proposes lowering POLICY_EXPLORATORY_THRESHOLD from 0.7 to 0.6).
  - memory/dream_proposals.db::dream_proposals — soul / consolidation
    proposals emitted by the dream-state subsystem.

The ID space is independent across the two tables. A given ID may
exist in both, one, or neither. The return shape always includes a
`sources` list naming where the ID was found.

Read-only by construction. Fails open (found=False, no crash) when
either DB is missing or unreadable — a missing DB is a valid state
on a freshly-provisioned box.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

_MAEZ_HOME = Path("/home/rohit/maez")

# Module-level paths so tests can monkey-patch them without touching
# the real prod DBs.
_EVOLUTION_DB = str(_MAEZ_HOME / "memory" / "evolution_track.db")
_DREAM_DB = str(_MAEZ_HOME / "memory" / "dream_proposals.db")


def _fetch_evolution_candidate(proposal_id: int) -> dict | None:
    """Query candidates table. Returns None on any failure — the caller
    treats that as 'not found in this source', not a crash."""
    try:
        conn = sqlite3.connect(_EVOLUTION_DB, timeout=1.5)
    except sqlite3.Error:
        return None
    try:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT id, state, target_file, weakness_description, "
            "diff_text, justification, created_at, validated_at, "
            "applied_at, resolved_at "
            "FROM candidates WHERE id = ?",
            (proposal_id,),
        ).fetchone()
    except sqlite3.Error:
        conn.close()
        return None
    conn.close()
    if row is None:
        return None
    return dict(row)


def _fetch_dream_proposal(proposal_id: int) -> dict | None:
    try:
        conn = sqlite3.connect(_DREAM_DB, timeout=1.5)
    except sqlite3.Error:
        return None
    try:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT id, created_at, insight, status, proposal_type, "
            "target_section, applied_at, reject_reason, unified_diff "
            "FROM dream_proposals WHERE id = ?",
            (proposal_id,),
        ).fetchone()
    except sqlite3.Error:
        conn.close()
        return None
    conn.close()
    if row is None:
        return None
    return dict(row)


def _render_evolution_summary(r: dict) -> str:
    """Compact multi-line rendering of an evolution candidate row.
    Diff is truncated to keep the tool-transcript tight."""
    lines = [
        f"evolution candidate #{r.get('id')}: state={r.get('state')}",
        f"  target_file: {r.get('target_file')}",
        f"  weakness: {r.get('weakness_description')}",
        f"  created_at: {r.get('created_at')}",
    ]
    if r.get("validated_at"):
        lines.append(f"  validated_at: {r.get('validated_at')}")
    if r.get("applied_at"):
        lines.append(f"  applied_at: {r.get('applied_at')}")
    diff = r.get("diff_text") or ""
    if diff:
        if len(diff) > 500:
            diff = diff[:500] + "\n  ...[diff truncated]"
        lines.append("  diff:")
        for dl in diff.splitlines():
            lines.append(f"    {dl}")
    return "\n".join(lines)


def _render_dream_summary(r: dict) -> str:
    lines = [
        f"dream proposal #{r.get('id')}: status={r.get('status')}",
        f"  proposal_type: {r.get('proposal_type')}",
        f"  target_section: {r.get('target_section')}",
        f"  created_at: {r.get('created_at')}",
    ]
    insight = r.get("insight") or ""
    if insight:
        if len(insight) > 300:
            insight = insight[:300] + "…"
        lines.append(f"  insight: {insight}")
    return "\n".join(lines)


def lookup(proposal_id: Any) -> dict:
    """Look up a proposal by ID across both stores.

    Returns a dict:
      {
        "found": bool,
        "sources": list[str],   # subset of {"evolution_candidates",
                                #             "dream_proposals"}
        "summary": str,         # human-readable rendering
      }
    """
    try:
        pid = int(proposal_id)
    except (TypeError, ValueError):
        return {
            "found": False,
            "sources": [],
            "summary": f"invalid proposal_id {proposal_id!r} "
                       f"— must be an integer.",
        }

    sources: list[str] = []
    summary_parts: list[str] = []

    evo = _fetch_evolution_candidate(pid)
    if evo is not None:
        sources.append("evolution_candidates")
        summary_parts.append(_render_evolution_summary(evo))

    dream = _fetch_dream_proposal(pid)
    if dream is not None:
        sources.append("dream_proposals")
        summary_parts.append(_render_dream_summary(dream))

    if not sources:
        return {
            "found": False,
            "sources": [],
            "summary": f"proposal #{pid} not found in "
                       f"evolution_track.db or dream_proposals.db.",
        }

    return {
        "found": True,
        "sources": sources,
        "summary": "\n\n".join(summary_parts),
    }
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
cd /home/rohit/maez && .venv/bin/python -m unittest tests.test_proposal_lookup -v
```

Expected: 6 tests pass (found in evolution, found in dream, missing ID, missing DB file, found in both, invalid input).

- [ ] **Step 5: Live sanity check against proposal #25**

```bash
cd /home/rohit/maez && .venv/bin/python -c "from core import proposal_lookup; r = proposal_lookup.lookup(25); print(r['found'], r['sources']); print(r['summary'][:600])"
```

Expected output contains `True`, `['evolution_candidates']`, and text mentioning `core/cognition_quality.py`, `POLICY_EXPLORATORY_THRESHOLD`, and `validated`. This proves the module works against the real prod DB.

- [ ] **Step 6: Full suite regression**

```bash
cd /home/rohit/maez && .venv/bin/python -m unittest discover -s tests -p 'test_*.py' 2>&1 | tail -5
```

Expected: 174 tests OK (168 previous + 6 new) + 1 pre-existing `test_fix6_followups` error.

- [ ] **Step 7: Commit**

```bash
cd /home/rohit/maez && git add core/proposal_lookup.py tests/test_proposal_lookup.py && git commit -m "feat(proposal_lookup): SQLite-backed lookup for evolution + dream proposals

Observed trigger 2026-04-20: user asked 'what is proposal #25?' in
Telegram; brain_loop fell back to grep -r over the filesystem, hit
vocab.json noise, couldn't answer. Proposals live in
evolution_track.db (candidates) and dream_proposals.db — not in
markdown.

Pure lookup function: lookup(proposal_id) -> dict with found,
sources, summary. Reads both DBs, fails open on missing files or
DB errors. Returns compact multi-line text suitable for
tool-transcript injection."
```

Only the two files. Do not `git add .`.

---

## Task 2: Wire `lookup_proposal` into the action engine + brain_loop

**Files:**
- Modify: `core/action_engine.py` (ACTION_TIERS at L216-245, add methods near L946)
- Modify: `core/brain_loop.py` (allowed set at L532-542)
- Create test: append to `tests/test_proposal_lookup.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_proposal_lookup.py` (BEFORE the `if __name__ == "__main__":` line at the bottom):

```python
class ActionEngineRegistration(unittest.TestCase):
    """The lookup tool is useless to Maez until the action engine knows
    about it AND the brain_loop is allowed to dispatch it."""

    def test_action_tier_registered(self):
        from core.action_engine import ACTION_TIERS
        self.assertIn("lookup_proposal", ACTION_TIERS,
                      "lookup_proposal missing from ACTION_TIERS")
        self.assertEqual(ACTION_TIERS["lookup_proposal"], 0,
                         "lookup_proposal must be tier 0 (read-only)")

    def test_brain_loop_allows_action(self):
        # Rebuild the allowed set by calling into brain_loop's
        # module-level object. The set is defined inside run_brain_loop
        # at ~L532; we verify via a lightweight helper if one exists,
        # else by source inspection. Simplest: import the module, read
        # the source of run_brain_loop, and assert the action name
        # appears as a string literal inside the allowed set.
        import inspect
        from core import brain_loop
        src = inspect.getsource(brain_loop.run_brain_loop)
        self.assertIn("'lookup_proposal'", src,
                      "'lookup_proposal' not in brain_loop.run_brain_loop "
                      "allowed set — planner can't dispatch it")

    def test_do_method_exists_and_dispatches(self):
        from core.action_engine import ActionEngine
        self.assertTrue(
            hasattr(ActionEngine, "_do_lookup_proposal"),
            "ActionEngine._do_lookup_proposal is missing; "
            "the getattr(_do_<action>) dispatch will fail"
        )
        self.assertTrue(
            hasattr(ActionEngine, "lookup_proposal"),
            "ActionEngine.lookup_proposal public method is missing"
        )
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd /home/rohit/maez && .venv/bin/python -m unittest tests.test_proposal_lookup.ActionEngineRegistration -v
```

Expected: 3 failures — `lookup_proposal missing from ACTION_TIERS`, not in brain_loop allowed set, `_do_lookup_proposal` missing.

- [ ] **Step 3: Register in ACTION_TIERS**

In `core/action_engine.py`, find the `ACTION_TIERS` dict (starts at L216). Locate the "Pure read-only tools — Lane 0 always." block (L222-224) and add `'lookup_proposal': 0` in that block. Exact line to change:

FROM:
```python
    # Pure read-only tools — Lane 0 always.
    'web_search': 0, 'fetch_url': 0,
    'read_file': 0, 'search_files': 0, 'query_system': 0,
```

TO:
```python
    # Pure read-only tools — Lane 0 always.
    'web_search': 0, 'fetch_url': 0,
    'read_file': 0, 'search_files': 0, 'query_system': 0,
    'lookup_proposal': 0,
```

- [ ] **Step 4: Add the public method + `_do_` dispatcher**

In `core/action_engine.py`, after the `query_system` methods (which end at ~L952), add:

```python
    def lookup_proposal(self, proposal_id, reasoning: str) -> ActionResult:
        """Tier 0: Look up a proposal by ID across evolution_track.db
        (candidates) and dream_proposals.db. Read-only."""
        return self._execute_action(
            "lookup_proposal",
            {"proposal_id": proposal_id},
            reasoning,
            tier=0,
        )

    def _do_lookup_proposal(self, proposal_id=None, **_ignored) -> str:
        """Dispatched by _execute_action at L674 via
        getattr(self, f'_do_{action}'). Returns the human-readable
        summary string from core.proposal_lookup.lookup — that string
        goes straight into the tool transcript."""
        from core import proposal_lookup
        result = proposal_lookup.lookup(proposal_id)
        return result.get("summary") or "(no summary)"
```

The `**_ignored` on `_do_lookup_proposal` follows the pattern of `_do_web_search` at L969 — `_execute_action` passes through the full params dict, so tolerating extra kwargs is the safe shape.

- [ ] **Step 5: Add to the brain_loop `allowed` set**

In `core/brain_loop.py`, find the `allowed = { ... }` block starting at L532. It currently reads:

```python
    allowed = {
        # Session 11z primitives — the only two that really matter
        'run_shell', 'write_any_file',
        # Read-only — still supported as direct actions
        'query_system', 'read_file', 'search_files', 'web_search',
        # Legacy aliases — delegate to run_shell / write_any_file internally
        'run_readonly_command', 'run_safe_command',
        'write_file', 'append_to_file', 'git_commit',
        'install_package', 'restart_service', 'run_script',
        'write_outside_maez', 'git_push',
    }
```

Replace the "Read-only" line with:

```python
        # Read-only — still supported as direct actions
        'query_system', 'read_file', 'search_files', 'web_search',
        'lookup_proposal',
```

- [ ] **Step 6: Run the registration tests**

```bash
cd /home/rohit/maez && .venv/bin/python -m unittest tests.test_proposal_lookup.ActionEngineRegistration -v
```

Expected: 3 OK.

- [ ] **Step 7: Full suite regression**

```bash
cd /home/rohit/maez && .venv/bin/python -m unittest discover -s tests -p 'test_*.py' 2>&1 | tail -5
```

Expected: 177 OK (168 baseline + 6 from Task 1 + 3 from Task 2) + 1 pre-existing `test_fix6_followups` error.

- [ ] **Step 8: Live deploy + sanity check**

```bash
sudo systemctl restart maez.service && sleep 4 && systemctl is-active maez && journalctl -u maez --since '10 seconds ago' --no-pager | grep -E 'surface v2 live|Cycle 1' | head
```

Expected: `active`, surface v2 live, Cycle 1 running.

Also confirm the tool is loadable in the daemon's running interpreter by checking that a bare `systemctl status` doesn't surface any import errors for `core.proposal_lookup`. If the service failed to start, `journalctl -u maez --since '1 minute ago' --no-pager | grep -iE 'traceback|error|failed to import'` will show why.

- [ ] **Step 9: Commit**

```bash
cd /home/rohit/maez && git add core/action_engine.py core/brain_loop.py tests/test_proposal_lookup.py && git commit -m "feat(action_engine): register lookup_proposal as a tier-0 action

Wires core.proposal_lookup.lookup into the action surface so the
brain_loop can dispatch it directly instead of falling back to
grep -r over the filesystem. ACTION_TIERS entry + lookup_proposal
public method + _do_lookup_proposal dispatcher + brain_loop allowed
set inclusion.

Next time the user asks 'what is proposal #25?', the planner emits
TOOL_CALL lookup_proposal(proposal_id=25) and the tool transcript
contains the actual proposal content — no grep-r noise."
```

Only the three files. Do not `git add .`.

---

## Self-review

**Spec coverage:**
- Task 1 creates `core/proposal_lookup.py` with pure `lookup()` function, handles both DBs, missing-ID, missing-DB, dual-source, input validation. ✓
- Task 2 registers in ACTION_TIERS, adds public + `_do_` methods, adds to brain_loop allowed set. ✓
- Live sanity check against proposal #25 confirms end-to-end against real data. ✓

**Placeholder scan:** every code block is complete, no TBDs, no "similar to Task N" without code, no undefined identifiers. ✓

**Type consistency:**
- `lookup(proposal_id: Any) -> dict` with explicit keys `found: bool`, `sources: list[str]`, `summary: str`. Tests assert those exact keys. ✓
- `ACTION_TIERS["lookup_proposal"] = 0` matches test assertion. ✓
- `_do_lookup_proposal(proposal_id=None, **_ignored) -> str` matches the `_execute_action` → `getattr(self, f"_do_{action}")(**params)` dispatch contract verified at `core/action_engine.py:674`. ✓
- `allowed` set entry `'lookup_proposal'` matches the action name the planner emits and matches the ACTION_TIERS key. ✓

Plan is self-contained. Ready to execute via subagent-driven development.
