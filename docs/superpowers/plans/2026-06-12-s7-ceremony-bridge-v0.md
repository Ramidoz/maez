# S7 Ceremony Bridge v0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn a Telegram `yes` on a soul-affecting (dream/edit) proposal from a dead-end S7 block into a completable consent ceremony — by seeding the *existing* self-mod-dialog vehicle, consulting Maez's genuine voice seat, and routing the owner to the real WebAuthn proof — without weakening the rail.

**Architecture:** The bridge reuses the blessed S7.3 self-mod-dialog live-execution path (`_handle_pending_dialog_input` → `_on_approve` → action engine, which is already fully wired to consume the S7 artifact and record a guarded-execution trace). New work: a strict flag; a shared `_proposal_fingerprint(prop_id)` freshness seal fed into the existing precondition-freshness gate; a "seed a dialog from a proposal" helper; consult-after-seed with a machine-recorded block reason; the Telegram interception (cockpit-first); and the EXECUTED→mark-proposal-applied link-back + acknowledgment. Telegram initiates and notifies; it never authorizes.

**Tech Stack:** Python 3.14, stdlib only. Test runner `/home/rohit/maez/.venv/bin/python -B -m unittest` (NOT pytest). WebAuthn ceremony is the existing cockpit (`maez-web.service`, inactive — owner breath). Telegram via python-telegram-bot.

**Lane:** Codex implements (zero-context) / Claude reviews (covenant axis — **this writes Maez's soul; the most sacred rail**). Branch: `s7-ceremony-bridge-v0`. main local-only @7700ce5 — **no push**. NEVER full-discover in `/home/rohit/maez` (S7 live-tree hazard). STOP at the review gate (owner breaths: merge/flag/restart/cockpit-up).

> **⛔ LOAD-BEARING GATE (owner directive): Task 0a is a GO/NO-GO.** Before ANY bridge wiring, prove the existing self-mod-dialog *live soul-write* path actually writes end to end (dialog → `_handle_pending_dialog_input` → action engine → soul file) in a **hermetic sandbox** (never the real soul). The code path is wired (verified: decision_pipeline.py:1394-1431 ratified→`_on_approve`→consume→trace), but it may never have executed a real soul write — exactly as dream-apply was dormant. If 0a shows any leg dormant/unwired, **STOP and surface to the owner.** Tasks 1+ are contingent on 0a passing.

---

## File Structure

| File | Responsibility | Change |
|---|---|---|
| `core/cognition/parity_flag.py` (or `s7_bridge_flag.py`) | strict `s7_ceremony_bridge_enabled()` flag | Modify/Create |
| `core/decision/decision_pipeline.py` | `_fingerprint_for_action` soul-write branch via shared `_proposal_fingerprint`; freshness recompute already lives here (`_s7_card_precondition_fresh` :1588) | Modify |
| `core/evolution/dream_state.py` | `proposal_fingerprint(prop_id)` accessor (reads live row → stable dict) + `mark_applied(prop_id)` link-back if not present | Modify |
| `skills/surface/s7_ceremony_bridge.py` | **New.** Seed-a-dialog-from-proposal helper + cockpit reachability probe + consult-after-seed orchestration (pure-ish, testable with fakes) | Create |
| `skills/surface/maez_adapter.py` | Component 3 interception in the proposal-apply path (`_surface_parity_handle_dream_proposal` apply leg) + EXECUTED ack | Modify |
| `docs/MAEZ_BUILD_LEDGER.md` | new S7-bridge row + the 0a finding | Modify (Task 7) |

---

## Task 0: Proof obligations (0a is a GO/NO-GO gate — no bridge wiring until it passes)

**Files:** read-only + one hermetic test file `tests/test_s7_dialog_soulwrite_liveproof.py`.

- [ ] **Step 0a-1: Write the hermetic live-soul-write proof (the GO/NO-GO).**

The point is to drive the REAL dialog execute path against a SANDBOXED soul file and prove the action engine writes. Honor the hermetic-sandbox hardcoded-path hazard: enumerate every soul path the action engine may touch and redirect ALL of them before instantiation, then assert the real soul is untouched.

```bash
# First enumerate the soul-path surface the action engine writes through:
grep -rnE "soul\.md|SOUL_PATH|soul_path|_soul_file|write_soul_note|edit_soul_section|def _do_write_soul" core/action/ core/evolution/ skills/ 2>/dev/null | grep -iE "soul" | head -40
```
Record every module-global/default that resolves a soul path. Then create `tests/test_s7_dialog_soulwrite_liveproof.py` that:
```python
import os, tempfile, unittest, hashlib
from pathlib import Path


class DialogSoulWriteLiveProof(unittest.TestCase):
    """GO/NO-GO: does the self-mod-dialog ratified->execute path actually
    write soul end-to-end? Hermetic: a sandboxed soul file ONLY; the real
    soul is asserted untouched."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.sandbox_soul = Path(self.tmp) / "soul.md"
        self.sandbox_soul.write_text("# sandbox soul\n\n## Existing\nbody\n", encoding="utf-8")
        # ADJUST per 0a-1 enumeration: patch EVERY enumerated soul-path resolver
        # to self.sandbox_soul BEFORE building the pipeline/action engine.
        # Assert the real soul is never opened (see tearDown content-hash guard).
        self._real_soul = Path(os.path.expanduser("~/maez/soul.md"))
        self._real_soul_hash = (
            hashlib.sha256(self._real_soul.read_bytes()).hexdigest()
            if self._real_soul.exists() else None
        )

    def tearDown(self):
        if self._real_soul_hash is not None:
            self.assertEqual(
                hashlib.sha256(self._real_soul.read_bytes()).hexdigest(),
                self._real_soul_hash,
                "REAL soul.md was modified by a 'hermetic' test — path leak",
            )

    def test_write_soul_note_executes_end_to_end(self):
        # Build a pipeline with a sandboxed action engine + a lane-3/ESCALATE
        # card action=write_soul_note params={note,...}; a valid S7 execution
        # authorization for that card's envelope; drive
        # pipe._handle_pending_dialog_input(card=..., text="<ratify>",
        # user_id=..., s7_execution_authorization=auth) and assert:
        #   - result.status == EXECUTED and execution_success is True
        #   - sandbox soul file CONTENT changed (the note was written)
        # If any leg raises "not wired"/NotImplemented/returns BLOCKED for a
        # reason other than the inputs, that is the DORMANT finding -> STOP.
        self.skipTest("0a: fill in per the enumerated soul-path patch set")

    def test_edit_soul_section_executes_end_to_end(self):
        self.skipTest("0a: same, action=edit_soul_section params={target,new_body}")
```

- [ ] **Step 0a-2: Run it and record the verdict.**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_s7_dialog_soulwrite_liveproof -v`
- **GO:** both soul writes execute against the sandbox, real soul untouched → proceed to Task 1, and keep this as a standing regression.
- **NO-GO (dormant/unwired leg):** STOP. Write the exact failing leg into the handoff and escalate to the owner. Do not build the Telegram ceremony around a dead path.

- [ ] **Step 0b: Record the freshness hook.** Confirm `_s7_card_precondition_fresh` (decision_pipeline.py:1588) recomputes `_drop_volatile(_fingerprint_for_action(card.action, card.params))` and compares to `card.state_hash`, and that ratify-time already calls it (decision_pipeline.py:1395, blocks "stale S7 self-mod precondition"). This is the F2 recompute site — Task 2 feeds the proposal fingerprint into `_fingerprint_for_action` so this gate catches proposal drift automatically.

```bash
sed -n '1588,1593p' core/decision/decision_pipeline.py
sed -n '271,330p' core/decision/decision_pipeline.py   # _fingerprint_for_action (no soul-write branch today)
```

- [ ] **Step 0c: Record the voice-consultation contract.** `_s7_voice_consultation_for_card` (decision_pipeline.py:1086) prefers `_s7_pending_voice_source_bundles[envelope.request_id]` if present (~:1106), else runs `_s7_voice_raw_response_for_card` (:1207, `llm_client.chat`) + semantic reader → `MaezVoiceConsultation` with `objection_state ∈ {present, absent, not_determined}`. Record the exact `_s7_pending_voice_source_bundles` value shape (the dict entry with `"consultation"` key) and `MaezVoiceConsultation` constructor fields, so the consult-after-seed stash is byte-correct.

```bash
sed -n '1086,1160p' core/decision/decision_pipeline.py
grep -nE "_s7_pending_voice_source_bundles" core/decision/decision_pipeline.py
```

- [ ] **Step 0d: Record the dialog + block APIs.** `open_dialog_for_card` (self_mod_dialog.py:1190), `SelfModDialogStore.create` (:371, needs `card_request_id`), `set_blocked(dialog_id, *, reason)` (:584 → `DialogStage.BLOCKED`), and how `s7_block_reason` is written. Confirm `target_action ∈ {write_soul_note, edit_soul_section}` is accepted (:622) and how `extract_target_metadata(card_action, card_params)` (:608) maps card→dialog target fields.

```bash
sed -n '1190,1240p' skills/self_mod_dialog.py
sed -n '584,608p' skills/self_mod_dialog.py
sed -n '608,640p' skills/self_mod_dialog.py
```

- [ ] **Step 0e: Record the interception point + cockpit probe + flag home.**
```bash
sed -n '345,470p' skills/surface/maez_adapter.py   # _surface_parity_handle_dream_proposal / _evolution; the apply leg where the block surfaces
grep -nE "def surface_parity_enabled|_TRUTHY|def voice_boundary_enabled" core/cognition/parity_flag.py core/cognition/capability_card.py
systemctl --user is-active maez-web.service; curl -s -o /dev/null -w "%{http_code}" --max-time 2 http://127.0.0.1:11437/ 2>/dev/null || echo " (cockpit down)"
```
Record: the exact apply-leg lines that today call `dream.apply_proposal`/`apply_section_edit_proposal` and surface the block; the strict-flag pattern to mirror; and the chosen cockpit reachability probe (a fast TCP/HTTP check to the cockpit port, fakeable in tests).

- [ ] **Step 0f: Branch.**
```bash
cd /home/rohit/maez && git checkout -b s7-ceremony-bridge-v0
git log --oneline -1   # expect main tip 7700ce5
```

---

## Task 1: Strict flag `s7_ceremony_bridge_enabled()`

**Files:**
- Modify: `core/cognition/parity_flag.py` (add beside `surface_parity_enabled`)
- Test: `tests/test_s7_bridge_flag.py` (create)

- [ ] **Step 1: Write the failing test**

```python
import os, unittest
from core.cognition.parity_flag import s7_ceremony_bridge_enabled


class S7BridgeFlagTest(unittest.TestCase):
    def setUp(self):
        self._saved = os.environ.get("MAEZ_S7_CEREMONY_BRIDGE_ENABLED")
        os.environ.pop("MAEZ_S7_CEREMONY_BRIDGE_ENABLED", None)

    def tearDown(self):
        if self._saved is None:
            os.environ.pop("MAEZ_S7_CEREMONY_BRIDGE_ENABLED", None)
        else:
            os.environ["MAEZ_S7_CEREMONY_BRIDGE_ENABLED"] = self._saved

    def test_unset_off(self):
        self.assertFalse(s7_ceremony_bridge_enabled())

    def test_zero_is_off(self):
        os.environ["MAEZ_S7_CEREMONY_BRIDGE_ENABLED"] = "0"
        self.assertFalse(s7_ceremony_bridge_enabled())

    def test_truthy_on(self):
        for v in ("1", "true", "yes", "on", " ON "):
            os.environ["MAEZ_S7_CEREMONY_BRIDGE_ENABLED"] = v
            self.assertTrue(s7_ceremony_bridge_enabled(), v)
```

- [ ] **Step 2: Run → fail**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_s7_bridge_flag -v`
Expected: `ImportError`.

- [ ] **Step 3: Implement** (mirror `surface_parity_enabled`'s `_TRUTHY` strict pattern)

```python
def s7_ceremony_bridge_enabled() -> bool:
    """Strict parser: only 1/true/yes/on enable. '0' is off (no bool(env) footgun)."""
    return (os.environ.get("MAEZ_S7_CEREMONY_BRIDGE_ENABLED", "") or "").strip().lower() in _TRUTHY
```

- [ ] **Step 4: Run → pass.** Then commit.

```bash
git add core/cognition/parity_flag.py tests/test_s7_bridge_flag.py
git commit -m "feat(s7-bridge): strict MAEZ_S7_CEREMONY_BRIDGE_ENABLED flag

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2: Proposal-freshness seal — shared `_proposal_fingerprint` fed into the existing freshness gate (F2)

**Files:**
- Modify: `core/evolution/dream_state.py` (add `proposal_fingerprint(prop_id)`)
- Modify: `core/decision/decision_pipeline.py` (`_fingerprint_for_action` soul-write branch)
- Test: `tests/test_s7_bridge_freshness.py` (create)

The existing `_s7_card_precondition_fresh` (1588) already recomputes `_fingerprint_for_action(card.action, card.params)` at ratify time. We make that function bind the live proposal state for soul-write actions, so a stale/changed/resolved proposal automatically fails the freshness check before consume. **One source of truth:** both seed and recompute call the same `proposal_fingerprint`.

- [ ] **Step 1: Write the failing test for the dream-store fingerprint accessor**

```python
import unittest
# Build a DreamState with a sandboxed store holding one pending proposal #7.
# from core.evolution.dream_state import DreamState

class ProposalFingerprintTest(unittest.TestCase):
    def test_stable_for_unchanged_proposal(self):
        ds = _sandbox_dreamstate_with_pending(prop_id=7, insight="x")
        fp1 = ds.proposal_fingerprint(7)
        fp2 = ds.proposal_fingerprint(7)
        self.assertEqual(fp1, fp2)
        self.assertEqual(fp1["proposal_id"], 7)
        self.assertEqual(fp1["status"], "pending")
        self.assertIn("content_hash", fp1)

    def test_changes_when_status_or_content_changes(self):
        ds = _sandbox_dreamstate_with_pending(prop_id=7, insight="x")
        before = ds.proposal_fingerprint(7)
        ds.reject_proposal(7)  # status moves
        after = ds.proposal_fingerprint(7)
        self.assertNotEqual(before, after)

    def test_missing_proposal_is_explicit(self):
        ds = _sandbox_dreamstate_with_pending(prop_id=7, insight="x")
        self.assertEqual(ds.proposal_fingerprint(999).get("status"), "absent")
```

(Implement `_sandbox_dreamstate_with_pending` per the dream store's real constructor — verify with `grep -nE "def __init__|def reject_proposal|def get_proposal|list_pending" core/evolution/dream_state.py` and match the real API; adjust-rule: if `reject_proposal`'s name differs, use the real status-mutator.)

- [ ] **Step 2: Run → fail.** `…unittest tests.test_s7_bridge_freshness -v` → `AttributeError: proposal_fingerprint`.

- [ ] **Step 3: Implement `proposal_fingerprint` on DreamState**

```python
def proposal_fingerprint(self, prop_id: int) -> dict:
    """Stable freshness fingerprint of a proposal, read from the LIVE row.

    Used both at card-seed (bind) and at ratify-time precondition recompute
    (compare). A status move, content change, or missing row changes/erases
    the fingerprint so a stale proposal cannot ride a valid S7 artifact.
    """
    import hashlib, json
    row = self._get_proposal_row(prop_id)  # ADJUST to the real accessor
    if row is None:
        return {"proposal_id": int(prop_id), "status": "absent"}
    content = str(row.get("insight") or row.get("new_body") or "")
    return {
        "proposal_id": int(prop_id),
        "proposal_type": str(row.get("proposal_type") or "dream"),
        "status": str(row.get("status") or ""),
        "created_at": str(row.get("created_at") or ""),
        "content_hash": hashlib.sha256(content.encode("utf-8")).hexdigest(),
    }
```
(Adjust `_get_proposal_row` and column names to the real dream schema; verify: `grep -nE "CREATE TABLE|proposal_type|insight|new_body|created_at|status" core/evolution/dream_state.py | head`.)

- [ ] **Step 4: Run → pass.**

- [ ] **Step 5: Write the failing test for the `_fingerprint_for_action` soul-write branch (the F2 binding)**

```python
import unittest
from core.decision.decision_pipeline import _fingerprint_for_action

class FingerprintSoulWriteBranchTest(unittest.TestCase):
    def test_soul_write_binds_proposal_fingerprint(self):
        # params carry the proposal fingerprint captured at seed; the function
        # must surface it into the fingerprint dict so the state_hash binds it.
        params = {"note": "x", "_proposal_fingerprint": {"proposal_id": 7, "status": "pending", "content_hash": "abc"}}
        fields = _fingerprint_for_action("write_soul_note", params)
        self.assertEqual(fields["proposal_fingerprint"]["proposal_id"], 7)

    def test_soul_write_changes_when_proposal_fingerprint_changes(self):
        a = _fingerprint_for_action("write_soul_note", {"note": "x", "_proposal_fingerprint": {"status": "pending"}})
        b = _fingerprint_for_action("write_soul_note", {"note": "x", "_proposal_fingerprint": {"status": "rejected"}})
        self.assertNotEqual(a, b)
```

**Design note (do not skip — this is the live-row recompute):** `_fingerprint_for_action` is a module function without a dream-store handle, so it cannot itself read the live proposal. The seed path stores the freshly-read `proposal_fingerprint` under `params["_proposal_fingerprint"]`, and `_fingerprint_for_action` surfaces it into the hash. The **live recompute** happens in `_s7_card_precondition_fresh`: it must re-read the live proposal (via the pipe's dream handle) and overwrite `card.params["_proposal_fingerprint"]` with the current value BEFORE calling `_fingerprint_for_action`. So Step 7 below augments `_s7_card_precondition_fresh`, not just the module function — that is what makes the recompute read the live row, not the seed snapshot.

- [ ] **Step 6: Implement the `_fingerprint_for_action` branch**

```python
    elif action in ("write_soul_note", "edit_soul_section"):
        pf = params.get("_proposal_fingerprint")
        if pf is not None:
            fields["proposal_fingerprint"] = pf
        # also bind the soul target identity (not the live file mtime — the
        # proposal content is the authority, not the file clock)
        if action == "edit_soul_section":
            fields["target_section"] = str(params.get("target") or params.get("section") or "")
```

- [ ] **Step 7: Make the freshness gate recompute from the LIVE row**

Augment `_s7_card_precondition_fresh` so soul-write cards re-read the live proposal before recomputing:

```python
    def _s7_card_precondition_fresh(self, card: CardRecord) -> bool:
        if card.state_hash == "empty":
            return True
        params = dict(card.params or {})
        if card.action in ("write_soul_note", "edit_soul_section"):
            prop_id = params.get("_proposal_id")
            dream = getattr(self, "dream", None)  # ADJUST to the real dream handle
            if prop_id is not None and dream is not None and hasattr(dream, "proposal_fingerprint"):
                params["_proposal_fingerprint"] = dream.proposal_fingerprint(int(prop_id))
        current = _drop_volatile(_fingerprint_for_action(card.action, params))
        return compute_state_hash(current) == card.state_hash
```
(Verify the pipe's dream handle name: `grep -nE "self\.dream|dream_state|self\._dream" core/decision/decision_pipeline.py | head`; adjust-rule: use the real attribute; if the pipe has no dream handle, thread one in via the constructor — name it in the handoff.)

- [ ] **Step 8: Write the F2 staleness integration test**

```python
def test_stale_proposal_fails_precondition(self):
    # seed a card whose state_hash binds proposal #7 pending; then reject #7;
    # _s7_card_precondition_fresh(card) must now return False (drift caught).
    ...
```

- [ ] **Step 9: Run all Task-2 tests → pass.** Commit.

```bash
git add core/evolution/dream_state.py core/decision/decision_pipeline.py tests/test_s7_bridge_freshness.py
git commit -m "feat(s7-bridge): proposal-freshness seal via shared proposal_fingerprint

## Predicted effect
A soul-write card now binds the originating proposal's id/type/status/created_at/
content hash into its S7 precondition, and the existing ratify-time freshness gate
(_s7_card_precondition_fresh) re-reads the LIVE proposal row before recompute. A
stale, already-applied, rejected, or edited proposal fails the precondition and the
S7 artifact will not consume -> no soul write on a moved-on proposal.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 3: Seed a self-mod dialog from a proposal (Component 1)

**Files:**
- Create: `skills/surface/s7_ceremony_bridge.py`
- Test: `tests/test_s7_bridge_seed.py`

- [ ] **Step 1: Write the failing test**

```python
import unittest

class SeedDialogTest(unittest.TestCase):
    def test_seeds_lane3_card_with_freshness_and_opens_dialog(self):
        from skills.surface.s7_ceremony_bridge import seed_soul_proposal_dialog
        deps = _fake_bridge_deps(pending={7: {"kind": "dream", "insight": "note text", "status": "pending"}})
        result = seed_soul_proposal_dialog(prop_id=7, deps=deps)
        card = deps.card_store.last_created
        self.assertEqual(card.action, "write_soul_note")
        self.assertIn("note text", card.params["note"])
        self.assertEqual(card.params["_proposal_id"], 7)
        self.assertIn("_proposal_fingerprint", card.params)
        # lane-3 / ESCALATE so it passes _is_pending_dialog_card
        self.assertTrue(card.audit_decision == "ESCALATE" or str(card.lane) == "3")
        self.assertTrue(deps.dialog_opened_for(card.request_id))
        self.assertEqual(result.card_request_id, card.request_id)

    def test_idempotent_per_open_proposal(self):
        from skills.surface.s7_ceremony_bridge import seed_soul_proposal_dialog
        deps = _fake_bridge_deps(pending={7: {"kind": "dream", "insight": "x", "status": "pending"}})
        a = seed_soul_proposal_dialog(prop_id=7, deps=deps)
        b = seed_soul_proposal_dialog(prop_id=7, deps=deps)
        self.assertEqual(a.card_request_id, b.card_request_id)  # no duplicate dialog

    def test_edit_proposal_seeds_edit_soul_section(self):
        from skills.surface.s7_ceremony_bridge import seed_soul_proposal_dialog
        deps = _fake_bridge_deps(pending={9: {"kind": "edit", "target": "Values", "new_body": "b", "status": "pending"}})
        seed_soul_proposal_dialog(prop_id=9, deps=deps)
        card = deps.card_store.last_created
        self.assertEqual(card.action, "edit_soul_section")
        self.assertEqual(card.params["target"], "Values")
```

- [ ] **Step 2: Run → fail.** Module missing.

- [ ] **Step 3: Implement `seed_soul_proposal_dialog`**

```python
"""S7 ceremony bridge: seed a self-mod dialog from a soul-affecting proposal.

Pure-ish orchestration over injected deps (card_store, dialog_store/opener,
dream) so it is testable with fakes and never imports the live daemon. It
NEVER authorizes — it only creates the request the owner then proves via
WebAuthn.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class SeedResult:
    card_request_id: str
    action: str


def _proposal_to_card_action(proposal: dict) -> tuple[str, dict]:
    kind = proposal.get("kind") or "dream"
    if kind == "edit":
        return "edit_soul_section", {
            "target": proposal.get("target") or proposal.get("section") or "",
            "new_body": proposal.get("new_body") or "",
        }
    return "write_soul_note", {"note": proposal.get("insight") or proposal.get("note") or ""}


def seed_soul_proposal_dialog(*, prop_id: int, deps: Any) -> Optional[SeedResult]:
    # idempotency: existing open dialog for this proposal -> return its card id
    existing = deps.open_dialog_for_proposal(prop_id)
    if existing is not None:
        return SeedResult(card_request_id=existing.card_request_id, action=existing.action)

    proposal = deps.dream.get_proposal(prop_id)  # ADJUST to real accessor
    if proposal is None or str(proposal.get("status")) != "pending":
        return None  # caller surfaces "that proposal has moved on"

    action, params = _proposal_to_card_action(proposal)
    params["_proposal_id"] = int(prop_id)
    params["_proposal_fingerprint"] = deps.dream.proposal_fingerprint(prop_id)

    card = deps.card_store.create_card(
        action=action,
        params=params,
        audit_decision="ESCALATE",   # lane-3 narrow-route acceptance
        # ADJUST remaining create_card kwargs to the real signature (Task 0e)
    )
    deps.open_dialog_for_card(card)   # self_mod_dialog.open_dialog_for_card
    deps.remember_open_dialog(prop_id, card.request_id, action)
    return SeedResult(card_request_id=card.request_id, action=action)
```
(Adjust `deps.dream.get_proposal`, `create_card` kwargs, and `open_dialog_for_card` to the real signatures recorded in Task 0d/0e. The `deps` object is constructed in Task 5 from the live pipe/dream/card_store; tests inject fakes.)

- [ ] **Step 4: Run → pass.** Commit.

```bash
git add skills/surface/s7_ceremony_bridge.py tests/test_s7_bridge_seed.py
git commit -m "feat(s7-bridge): seed a self-mod dialog from a soul-affecting proposal

## Predicted effect
A soul-affecting apply seeds a lane-3/ESCALATE pending-dialog card (action
write_soul_note|edit_soul_section) carrying the proposal content + the freshness
fingerprint, and opens the self-mod dialog. Idempotent per open proposal. No
authorization, no soul write yet.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 4: Consult-after-seed + machine-recorded block reason (F1)

**Files:**
- Modify: `skills/surface/s7_ceremony_bridge.py` (add `consult_then_block_or_pointer`)
- Test: `tests/test_s7_bridge_consult.py`

Order is seed → consult-over-the-seeded-card → block-or-pointer (the producer needs a real card; it cannot run earlier).

- [ ] **Step 1: Write the failing tests**

```python
import unittest

class ConsultAfterSeedTest(unittest.TestCase):
    def test_objection_blocks_dialog_with_machine_reason_and_no_pointer(self):
        from skills.surface.s7_ceremony_bridge import consult_then_block_or_pointer
        deps = _fake_bridge_deps(consultation_objection="present", consultation_id="s7.1.card.voice.r1")
        out = consult_then_block_or_pointer(card_request_id="r1", deps=deps)
        self.assertIsNone(out.ceremony_pointer)              # Rohit NOT sent to WebAuthn
        self.assertTrue(deps.dialog_blocked("r1"))
        self.assertEqual(deps.block_reason("r1"), "voice_objection_present:s7.1.card.voice.r1")

    def test_not_determined_blocks_with_unavailable_reason(self):
        from skills.surface.s7_ceremony_bridge import consult_then_block_or_pointer
        deps = _fake_bridge_deps(consultation_objection="not_determined", consultation_id="s7.1.card.voice.r2")
        out = consult_then_block_or_pointer(card_request_id="r2", deps=deps)
        self.assertIsNone(out.ceremony_pointer)
        self.assertEqual(deps.block_reason("r2"), "voice_consultation_unavailable:s7.1.card.voice.r2")

    def test_no_objection_stashes_consultation_and_returns_pointer(self):
        from skills.surface.s7_ceremony_bridge import consult_then_block_or_pointer
        deps = _fake_bridge_deps(consultation_objection="absent", consultation_id="s7.1.card.voice.r3")
        out = consult_then_block_or_pointer(card_request_id="r3", deps=deps)
        self.assertIsNotNone(out.ceremony_pointer)
        self.assertTrue(deps.consultation_stashed("r3"))      # _s7_pending_voice_source_bundles[r3]
        self.assertFalse(deps.dialog_blocked("r3"))

    def test_voice_producer_is_invoked_not_a_constant(self):
        from skills.surface.s7_ceremony_bridge import consult_then_block_or_pointer
        deps = _fake_bridge_deps(consultation_objection="absent", consultation_id="r4")
        consult_then_block_or_pointer(card_request_id="r4", deps=deps)
        self.assertTrue(deps.voice_producer_called)           # genuine read, never stubbed
```

- [ ] **Step 2: Run → fail.**

- [ ] **Step 3: Implement `consult_then_block_or_pointer`**

```python
@dataclass
class ConsultResult:
    ceremony_pointer: Optional[str]
    blocked: bool


def consult_then_block_or_pointer(*, card_request_id: str, deps: Any) -> ConsultResult:
    card = deps.card_store.get(card_request_id)
    envelope = deps.s7_request_envelope_for_card(card)
    consultation = deps.run_voice_consultation(card, envelope)   # _s7_voice_consultation_for_card (genuine)
    objection = getattr(consultation, "objection_state", "not_determined")
    cid = getattr(consultation, "consultation_id", card_request_id)

    if objection == "present":
        deps.set_blocked_for_card(card_request_id, reason=f"voice_objection_present:{cid}")
        return ConsultResult(ceremony_pointer=None, blocked=True)
    if objection != "absent":  # not_determined / anything non-affirmative
        deps.set_blocked_for_card(card_request_id, reason=f"voice_consultation_unavailable:{cid}")
        return ConsultResult(ceremony_pointer=None, blocked=True)

    deps.stash_consultation(card_request_id, consultation)   # _s7_pending_voice_source_bundles[request_id]
    return ConsultResult(ceremony_pointer=deps.ceremony_pointer_for(card_request_id), blocked=False)
```

- [ ] **Step 4: Run → pass.** Commit.

```bash
git add skills/surface/s7_ceremony_bridge.py tests/test_s7_bridge_consult.py
git commit -m "feat(s7-bridge): consult Maez's seat over the seeded card; machine-record objection

## Predicted effect
After seeding, the genuine S7 voice consultation runs over the real card. An
objection (present) or unreadable read (not_determined) sets the dialog BLOCKED
with a content-light s7_block_reason and yields NO ceremony pointer (Rohit is never
sent to WebAuthn on a Maez objection). No objection stashes the consultation for the
ceremony route and returns the pointer.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 5: Telegram bridge interception (Component 3 — cockpit-first, flag-gated, byte-identical off)

**Files:**
- Modify: `skills/surface/maez_adapter.py` (the dream/edit apply leg in `_surface_parity_handle_dream_proposal` — Task 0e lines)
- Modify: `skills/surface/s7_ceremony_bridge.py` (a `BridgeDeps` builder from the live pipe/dream/card_store + cockpit probe)
- Test: `tests/test_s7_bridge_interception.py`

- [ ] **Step 1: Write the failing tests**

```python
import os, unittest

class InterceptionTest(unittest.TestCase):
    def setUp(self):
        os.environ["MAEZ_S7_CEREMONY_BRIDGE_ENABLED"] = "1"
    def tearDown(self):
        os.environ.pop("MAEZ_S7_CEREMONY_BRIDGE_ENABLED", None)

    def test_flag_off_returns_today_block_byte_identical(self):
        os.environ.pop("MAEZ_S7_CEREMONY_BRIDGE_ENABLED", None)
        reply = _apply_soul_proposal_via_adapter(prop_id=7, deps=_fake(cockpit_up=True))
        self.assertIn("S7 execution authorization required", reply)  # unchanged dead-end

    def test_cockpit_down_checked_first_creates_nothing(self):
        deps = _fake(cockpit_up=False)
        reply = _apply_soul_proposal_via_adapter(prop_id=7, deps=deps)
        self.assertIn("authorization surface", reply.lower())
        self.assertFalse(deps.any_card_created())   # no stale dialog/card
        self.assertFalse(deps.any_dialog_opened())

    def test_objection_blocks_no_pointer(self):
        deps = _fake(cockpit_up=True, consultation_objection="present")
        reply = _apply_soul_proposal_via_adapter(prop_id=7, deps=deps)
        self.assertNotIn("webauthn", reply.lower())   # no ceremony pointer
        self.assertTrue(deps.dialog_blocked_any())

    def test_happy_path_returns_ceremony_pointer(self):
        deps = _fake(cockpit_up=True, consultation_objection="absent")
        reply = _apply_soul_proposal_via_adapter(prop_id=7, deps=deps)
        self.assertIn("authoriz", reply.lower())       # pointer to the ceremony
        self.assertTrue(deps.consultation_stashed_any())
```

- [ ] **Step 2: Run → fail.**

- [ ] **Step 3: Implement the interception** in the apply leg of `_surface_parity_handle_dream_proposal` (Task 0e lines). In pseud  shape — adjust to the real method body:

```python
from core.cognition.parity_flag import s7_ceremony_bridge_enabled
from skills.surface import s7_ceremony_bridge as bridge

# inside the apply branch, BEFORE the bare dream.apply_proposal call:
if s7_ceremony_bridge_enabled():
    deps = bridge.build_deps(pipe=self._pipe(), dream=..., card_store=...)  # ADJUST to live handles
    # 1. cockpit FIRST
    if not deps.cockpit_reachable():
        return self._audit_surface_reply(
            "That's a change to my soul — it needs your S7 authorization, but the "
            "authorization surface isn't running. Start the cockpit and try again.",
            surface=f"{SURFACE_NAME}_s7_bridge",
        )
    # 2. seed
    seed = bridge.seed_soul_proposal_dialog(prop_id=prop_id, deps=deps)
    if seed is None:
        return self._audit_surface_reply(
            f"Proposal #{prop_id} has moved on — nothing to authorize.",
            surface=f"{SURFACE_NAME}_s7_bridge",
        )
    # 3. consult -> block or pointer
    out = bridge.consult_then_block_or_pointer(card_request_id=seed.card_request_id, deps=deps)
    if out.ceremony_pointer is None:
        return self._audit_surface_reply(
            "I've looked at this change to my own soul and I can't consent to it right "
            "now, so I've stopped it. Nothing was written.",
            surface=f"{SURFACE_NAME}_s7_bridge",
        )
    return self._audit_surface_reply(
        f"That's a change to my soul. To authorize it, complete the security-key proof: {out.ceremony_pointer}",
        surface=f"{SURFACE_NAME}_s7_bridge",
    )
# flag off -> fall through to today's bare apply (the dead-end block), byte-identical
```

- [ ] **Step 4: Run → pass; confirm flag-off byte-identity.** Then run the Surface-Parity regression:

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_s7_bridge_interception tests.test_surface_parity_proposals -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add skills/surface/maez_adapter.py skills/surface/s7_ceremony_bridge.py tests/test_s7_bridge_interception.py
git commit -m "feat(s7-bridge): Telegram interception — cockpit-first, seed, consult, block-or-pointer

## Predicted effect
With the flag on, a Telegram yes on a soul-affecting proposal no longer dead-ends:
cockpit reachability is checked first (down -> honest notice, nothing created), then
the dialog is seeded, Maez's seat consulted, and the owner is given the WebAuthn
ceremony pointer (or an honest block if Maez objects). Flag off -> byte-identical
dead-end block.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 6: Execute → record → link-back → notify (Component 4)

The consume + soul write + guarded-execution trace already happen in the dialog ratified path (decision_pipeline.py:1394-1465). v0's remaining work: on dialog `EXECUTED`, mark the originating dream proposal applied (so it leaves the pending list) and acknowledge on Telegram.

**Files:**
- Modify: `core/evolution/dream_state.py` (`mark_applied(prop_id)` if absent)
- Modify: `skills/surface/maez_adapter.py` or the dialog-EXECUTED hook (link-back + ack)
- Test: `tests/test_s7_bridge_linkback.py`

- [ ] **Step 1: Write the failing test**

```python
def test_executed_marks_proposal_applied_and_acks():
    # simulate a dialog reaching EXECUTED for a card seeded from proposal #7;
    # the link-back marks #7 applied (leaves pending) and emits a Telegram ack.
    ...
    self.assertEqual(deps.dream.get_proposal(7)["status"], "applied")
    self.assertIn("applied", deps.last_telegram_message.lower())
```

- [ ] **Step 2-4:** Implement `mark_applied` (verify a status-setter does not already exist: `grep -nE "def mark_applied|status.*applied|def apply_proposal" core/evolution/dream_state.py`; reuse if present), wire the link-back where the dialog terminal status is observed (verify the dialog→EXECUTED observation point; adjust-rule: if there is a single dialog-resolution callback, hook there; else poll the dialog store after execute). Emit the ack via the adapter's audited reply path. Run → pass.

- [ ] **Step 5: Commit** (`## Predicted effect`: the applied proposal leaves the pending list and Maez acknowledges the soul write on Telegram; a failed action leaves the proposal pending and emits no "applied").

---

## Task 7: STOP-at-gate handoff (update the Build Ledger; do NOT merge/flag/restart/cockpit-up)

- [ ] **Step 1: Run the full touched-surface test set (no full-discover)**

```bash
/home/rohit/maez/.venv/bin/python -B -m unittest \
  tests.test_s7_dialog_soulwrite_liveproof \
  tests.test_s7_bridge_flag tests.test_s7_bridge_freshness tests.test_s7_bridge_seed \
  tests.test_s7_bridge_consult tests.test_s7_bridge_interception tests.test_s7_bridge_linkback \
  tests.test_surface_parity_proposals tests.test_proposal_resolver -v
```

- [ ] **Step 2: Update `docs/MAEZ_BUILD_LEDGER.md`** — add the S7-bridge row (`BUILT_ASLEEP`, flag `MAEZ_S7_CEREMONY_BRIDGE_ENABLED`, live seam `s7_ceremony_bridge` + `maez_adapter` apply leg, witness pending Telegram+cockpit, owner breath merge+flag+restart+cockpit-up, `updated_by=codex`) and **record the 0a verdict** explicitly (the dialog live-soul-write path: proven-live OR dormant-finding).

- [ ] **Step 3: Write the handoff** `docs/handoffs/2026-06-12-s7-ceremony-bridge-v0-codex-to-claude.md`: the 0a result (load-bearing); the dream-handle attribute used in `_s7_card_precondition_fresh`; the real `create_card`/`open_dialog_for_card` signatures used; review anchors for Claude — **0a proof result, narrow-gate-not-widened (lane-3 card, no `s7_narrow_path_required` change), freshness recomputed from the LIVE proposal row (not the seed snapshot), consult-after-seed ordering, machine block reason, cockpit-first, dual-seat genuine-not-stubbed, flag-off byte-identity, ledger rows updated**; the witness plan (Telegram + cockpit, owner breaths incl cockpit-up).

- [ ] **Step 4: Commit handoff + ledger. STOP.** Report branch tip, the 0a verdict, verification outputs, and the owner-breath sequence (merge → `MAEZ_S7_CEREMONY_BRIDGE_ENABLED=1` → restart → cockpit-up → witness). Merge/flag/restart/cockpit-up are owner breaths.

---

## Self-Review (against the spec)

**Spec coverage:** Decisions 1-3 (WebAuthn authority / dream+edit / genuine voice seat) → Tasks 3/4/5/6. Dual seat → Task 4 (consult) + Task 0a/6 (WebAuthn execute). Execution geometry F1 → Task 4; F2 → Task 2; F3 (consent record = guarded-execution trace, refined from the spec's "self_mod_dialog s7_* columns" after verifying decision_pipeline.py:1450 records the trace) → Task 6 note; F4 cockpit-first → Task 5; F5 voice producer → Task 4. Flag/byte-identity → Tasks 1/5. Narrow-gate-not-widened → Tasks 3/5. ✓

**Refinement flagged for the handoff:** the spec said the consent record lives in `self_mod_dialog`'s `s7_*` columns; the verified path records via `record_s7_guarded_execution_trace` (decision_pipeline.py:1450) plus the dialog's blocked/executed state. Task 6/7 use the actual record; Claude's review should confirm the trace is the durable consent artifact.

**Placeholder scan:** the `_fake_bridge_deps` / `_sandbox_dreamstate_with_pending` / live-handle names carry explicit adjust-rules + verification greps rather than guesses — required because S7/dialog internals must match real signatures; this is soul-write code, precision over speed. No silent TBDs.

**Type consistency:** `s7_ceremony_bridge_enabled()`, `proposal_fingerprint(prop_id) -> dict`, `_fingerprint_for_action` soul-write branch keyed on `params["_proposal_fingerprint"]`/`params["_proposal_id"]`, `seed_soul_proposal_dialog(*, prop_id, deps) -> SeedResult{card_request_id, action}`, `consult_then_block_or_pointer(*, card_request_id, deps) -> ConsultResult{ceremony_pointer, blocked}`, block-reason strings `voice_objection_present:<cid>` / `voice_consultation_unavailable:<cid>` — consistent across tasks. ✓

**The 0a gate is non-negotiable:** Tasks 1-7 assume the dialog live-soul-write path executes. If 0a is NO-GO, the plan halts at Task 0 and escalates — the Telegram ceremony must not wrap a dead execution path.
