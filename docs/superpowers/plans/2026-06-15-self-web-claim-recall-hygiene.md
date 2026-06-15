# Self-Web-Claim Recall Hygiene Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop Maez's own unverified web-grounded replies from being stored at owner-grade trust and re-recalled as `memory_context` that overrides fresh evidence.

**Architecture:** A new `SELF_WEB_CLAIM` provenance (defaults `untrusted`) tags Maez's reply on web-grounded turns; the store splits the combined owner+reply record into two linked records so only the reply is downgraded; `provenance_source` is threaded through the focused recall chain; at focused assembly, self-web-claim memory items are excluded when fresh evidence is present (kept + hard-labeled when not). All behind `MAEZ_SELF_CLAIM_HYGIENE_ENABLED`; off = byte-identical. Two content-light receipts witness store + recall.

**Tech Stack:** Python, `unittest` (runner `/home/rohit/maez/.venv/bin/python -B -m unittest`, NEVER full-discover), ChromaDB-backed `MemoryManager`, dispatcher/focused-cognition routing.

**Spec:** `docs/superpowers/specs/2026-06-15-self-web-claim-recall-hygiene-design.md` (cleared @85ba87c).

**Branch:** `self-web-claim-hygiene` (main is local-only/unpushed — NO push).

**Discipline:** TDD per task. `## Predicted effect` on behavior commits. `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`. **STOP at the review gate** before ANY live flag flip/restart (owner-sovereign breath). Forward-only: do NOT claim the already-stored Anthropic record is healed.

---

## File Structure

| File | Responsibility | Change |
|---|---|---|
| `memory/memory_manager.py` | provenance/trust enums + `store_telegram` | add `SELF_WEB_CLAIM`; default tier; `turn_link_id` kwarg |
| `core/dispatcher/layer1.py` | `RecallItem` dataclass + serialization | add `provenance_source` field |
| `core/brain/brain_loop.py` | `recall_partitions_to_items` | read `provenance_source` from metadata |
| `core/routing/focused_cognition.py` | `EvidenceItem` + working-set assembly | add `origin_provenance`; exclusion filter; recall receipt; render label |
| `daemon/maez_daemon.py` | turn store + M1 promotion call (`:7230-7246`) | split store; owner-id-only M1; store receipt; flag gate |
| `core/infra/env_flags.py` | `strict_env_flag` (exists) | reuse, no change |
| `tests/test_self_web_claim_hygiene.py` | feature tests | create |
| `docs/proof/2026-06-15-self-web-claim-task0.md` | Task-0 proofs | create |

**Branch setup (run once before Task 0):**
```bash
cd /home/rohit/maez
git checkout main
git checkout -b self-web-claim-hygiene
git branch --show-current   # expect: self-web-claim-hygiene
```

---

## Task 0: Feasibility proofs (HARD GATE — docs only, no behavior change)

**Files:**
- Create: `docs/proof/2026-06-15-self-web-claim-task0.md`

This task is a STOP gate. If either proof refutes the spec's seam assumptions, STOP and patch spec/plan before any wiring.

- [ ] **Step 1: Prove 0a — the web-grounded signal is reachable at the store site**

Run:
```bash
cd /home/rohit/maez
sed -n '6440,6505p' daemon/maez_daemon.py | grep -nE 'web_context|fresh'
# Confirm web_context is a local in handle_message bound before line 7230:
awk 'NR>=6300 && NR<=7234 && /web_context[ ]*=/' daemon/maez_daemon.py
```
Expected: `web_context` is assigned in `handle_message` on the fetch paths and still in scope at `:7230`. Record the exact assignment line(s) and whether `web_context` is `""`/falsy on non-web turns.

**Decision rule:** if `web_context` is in scope and reliably non-empty exactly when fresh web/tool evidence was fetched → `web_grounded = bool((web_context or "").strip())`. If `web_context` is not reliably in scope on all paths (e.g. dispatcher vs legacy vs photo), instead derive the signal from the synthesis result that produced `reply` (search for the dispatcher/focused result object in `handle_message`). If neither is reachable without threading a new value across many layers, **STOP** and report — do not force it.

- [ ] **Step 2: Prove 0b — `provenance_source` can be threaded through the recall chain**

Run:
```bash
cd /home/rohit/maez
grep -n "trust_tier" core/dispatcher/layer1.py            # RecallItem carries trust_tier today
grep -n "meta.get(\"trust_tier\")\|provenance_source" core/brain/brain_loop.py
grep -n "origin_trust\|provenance_source" core/routing/focused_cognition.py | head
grep -n "provenance_source\|trust_tier" memory/memory_manager.py | grep -i "meta\|_provenance_metadata" | head
```
Expected: `trust_tier` travels `metadata → RecallItem.trust_tier (brain_loop.py:156) → EvidenceItem.origin_trust (focused_cognition.py:820/881)`, but **`provenance_source` does NOT** ride the structured `RecallItem`. Confirm `_provenance_metadata` (memory_manager.py) writes `provenance_source` into the stored row metadata (so recall rows can read it back). Record the exact hops that must be wired in Task 2.

- [ ] **Step 3: Write the proof doc**

Create `docs/proof/2026-06-15-self-web-claim-task0.md` recording: (0a) the chosen `web_grounded` signal + its source line(s), or a STOP; (0b) the confirmed provenance metadata key written at store time and the exact RecallItem→EvidenceItem hops to wire. State explicitly whether the spec's seam assumptions held.

- [ ] **Step 4: Commit**

```bash
git add docs/proof/2026-06-15-self-web-claim-task0.md
git commit -m "$(cat <<'EOF'
docs(proof): Task-0 feasibility for self-web-claim hygiene

0a: web_grounded signal source at the store site (daemon:7230).
0b: provenance_source threading hops (metadata -> RecallItem -> EvidenceItem).
No behavior change.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

## Task 1: `SELF_WEB_CLAIM` provenance source + default tier

**Files:**
- Modify: `memory/memory_manager.py:82-109`
- Test: `tests/test_self_web_claim_hygiene.py` (create)

- [ ] **Step 1: Write the failing test**

Create `tests/test_self_web_claim_hygiene.py`:
```python
import unittest


class SelfWebClaimProvenanceTest(unittest.TestCase):
    def test_self_web_claim_is_a_provenance_source(self):
        from memory.memory_manager import ProvenanceSource

        self.assertEqual(ProvenanceSource.SELF_WEB_CLAIM.value, "self_web_claim")

    def test_self_web_claim_defaults_to_untrusted(self):
        from memory.memory_manager import TrustTier, default_tier_for

        self.assertEqual(default_tier_for("self_web_claim"), TrustTier.UNTRUSTED)

    def test_self_web_claim_is_distinct_from_claude_tier_response(self):
        from memory.memory_manager import ProvenanceSource

        self.assertNotEqual(
            ProvenanceSource.SELF_WEB_CLAIM, ProvenanceSource.CLAUDE_TIER_RESPONSE
        )


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_self_web_claim_hygiene -v`
Expected: FAIL — `AttributeError: SELF_WEB_CLAIM` / `ValueError: unknown provenance_source 'self_web_claim'`.

- [ ] **Step 3: Add the enum value + default tier**

In `memory/memory_manager.py`, add to `ProvenanceSource` (after `CLAUDE_TIER_RESPONSE`, line 86):
```python
    CLAUDE_TIER_RESPONSE = "claude_tier_response"
    SELF_WEB_CLAIM = "self_web_claim"
    SYSTEM = "system"
```
And add to `_DEFAULT_TIER_BY_SOURCE` (after the `CLAUDE_TIER_RESPONSE` entry, line 107):
```python
    ProvenanceSource.CLAUDE_TIER_RESPONSE: TrustTier.UNTRUSTED,
    ProvenanceSource.SELF_WEB_CLAIM: TrustTier.UNTRUSTED,
    ProvenanceSource.SYSTEM: TrustTier.COVENANT,
```

- [ ] **Step 4: Run test to verify it passes**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_self_web_claim_hygiene -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Run the existing provenance suite (regression)**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_memory_provenance 2>&1 | tail -5`
(If `tests.test_memory_provenance` does not exist, find the provenance test module: `ls tests/ | grep -i provenance` and run that one.)
Expected: OK — adding an enum value must not break the `_coerce_provenance_source` typo-guard or default-tier tests.

- [ ] **Step 6: Commit**

```bash
git add memory/memory_manager.py tests/test_self_web_claim_hygiene.py
git commit -m "$(cat <<'EOF'
feat(memory): add SELF_WEB_CLAIM provenance defaulting to untrusted

New ProvenanceSource for Maez's own web-grounded reply, distinct from
claude_tier_response (frontier-model response). Defaults to TrustTier.UNTRUSTED.

## Predicted effect

No behavior change yet — the enum is not written by any store path until Task 3.
default_tier_for("self_web_claim") now returns untrusted.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Thread `provenance_source` through the recall chain

**Files:**
- Modify: `core/dispatcher/layer1.py` (`RecallItem` dataclass + its serialization ~:64-104)
- Modify: `core/brain/brain_loop.py:150-158` (`recall_partitions_to_items`)
- Modify: `core/routing/focused_cognition.py:236-242` (`EvidenceItem`), `:685` (`_ranked_items_for_state` unpack), `:808-889` (`raw_items` tuple)
- Test: `tests/test_self_web_claim_hygiene.py`

- [ ] **Step 1: Write the failing test (provenance travels metadata → RecallItem → EvidenceItem)**

Append to `tests/test_self_web_claim_hygiene.py`:
```python
class ProvenanceTravelsRecallChainTest(unittest.TestCase):
    def test_recall_item_carries_provenance_source(self):
        from core.dispatcher.layer1 import RecallItem

        item = RecallItem(text="t", source_type="memory_context", provenance_source="self_web_claim")
        self.assertEqual(item.provenance_source, "self_web_claim")

    def test_recall_partitions_read_provenance_source_from_metadata(self):
        from core.brain.brain_loop import recall_partitions_to_items

        partition = {"raw": [{"content": "hi", "id": "r1",
                              "metadata": {"trust_tier": "untrusted",
                                           "provenance_source": "self_web_claim"}}]}
        items = recall_partitions_to_items(partition, role_source_type="memory_context")
        self.assertEqual(items[0].provenance_source, "self_web_claim")

    def test_evidence_item_carries_origin_provenance(self):
        from core.routing.focused_cognition import EvidenceItem

        ev = EvidenceItem(local_label="E1", source_type="memory_context", text="t",
                          durable_id="d", origin_provenance="self_web_claim")
        self.assertEqual(ev.origin_provenance, "self_web_claim")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_self_web_claim_hygiene.ProvenanceTravelsRecallChainTest -v`
Expected: FAIL — `TypeError: unexpected keyword argument 'provenance_source'` / `'origin_provenance'`.

- [ ] **Step 3a: Add `provenance_source` to `RecallItem`**

In `core/dispatcher/layer1.py`, add the field to `RecallItem` (after `trust_tier`, line 69):
```python
    trust_tier: str | None = None
    provenance_source: str | None = None
```
And in its serialization dict (the block around line 103-104 that emits `"temporal_provenance"` / `"trust_tier"`), add:
```python
                    "trust_tier": item.trust_tier,
                    "provenance_source": item.provenance_source,
```

- [ ] **Step 3b: Read `provenance_source` in `recall_partitions_to_items`**

In `core/brain/brain_loop.py`, in the `RecallItem(...)` construction (line 150-157), add:
```python
                temporal_provenance=temporal_provenance,
                trust_tier=meta.get("trust_tier"),
                provenance_source=meta.get("provenance_source"),
```

- [ ] **Step 3c: Add `origin_provenance` to `EvidenceItem` + thread it through `raw_items`**

In `core/routing/focused_cognition.py`:

(i) Add the field to `EvidenceItem` (after `origin_trust`, line 242):
```python
    origin_trust: str | None = None
    origin_provenance: str | None = None
```

(ii) Extend the `raw_items` tuple type (line 808) from 5 to 6 elements:
```python
    raw_items: list[tuple[str, str, str | None, dict | None, str | None, str | None]] = []
```

(iii) In the structured-recall loop (line 818-829), read provenance and append it as the 6th element:
```python
                durable_id = getattr(item, "durable_id", None)
                temporal_provenance = getattr(item, "temporal_provenance", None)
                origin_trust = getattr(item, "trust_tier", None)
                origin_provenance = getattr(item, "provenance_source", None)
                raw_items.append(
                    (
                        source_type,
                        item_text,
                        durable_id,
                        temporal_provenance,
                        origin_trust,
                        origin_provenance,
                    )
                )
```

(iv) Every OTHER `raw_items.append(...)` in this function currently appends a 5-tuple; add a trailing `None` (origin_provenance) to each. The sites: the transcript-split non-memory append (line 835), the structured-path transcript memory/atomic appends (834-835), the non-structured transcript appends (841, 843), the `web_context` append (848-849), the anchors append (851-852), and the `temporal_recall_status` append (860-868). Example (web_context, line 848-849):
```python
            for item_text in _atomic_items(web_context):
                raw_items.append(("web_context", item_text, None, None, None, None))
```
Apply the same trailing-`None` addition to lines 835, 841, 843, 852, and the 860-868 tuple.

(v) The `date_cue` scan unpack (line 856-857) — add a 6th throwaway var:
```python
        has_confirmed = any(
            provenance and provenance.get("confirmed")
            for _st, _t, _d, provenance, _ot, _op in raw_items
        )
```

(vi) `_ranked_items_for_state` — update BOTH its signature type annotation (line 680, currently
`raw_items: list[tuple[str, str, str | None, dict | None, str | None]]`) to the 6-tuple, AND its
internal unpack (line 685):
```python
        source_type, _text, _durable_id, temporal_provenance, _origin_trust, _origin_provenance = item
```
If `_ranked_items_for_state` re-packs tuples internally, ensure it re-emits 6-tuples. Read the
whole function `:680-720` and keep arity consistent.

(vii) The `EvidenceItem` construction (line 874-889) — unpack and pass the 6th:
```python
    items = [
        EvidenceItem(
            local_label=f"E{index + 1}",
            source_type=source_type,
            text=text,
            durable_id=durable_id or _content_hash(text),
            temporal_provenance=temporal_provenance,
            origin_trust=origin_trust,
            origin_provenance=origin_provenance,
        )
        for index, (
            source_type,
            text,
            durable_id,
            temporal_provenance,
            origin_trust,
            origin_provenance,
        ) in enumerate(raw_items)
    ]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_self_web_claim_hygiene.ProvenanceTravelsRecallChainTest -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Run focused + dispatcher recall suites (regression — tuple arity is the risk)**

Run:
```bash
/home/rohit/maez/.venv/bin/python -B -m unittest \
  tests.test_focused_cognition \
  tests.test_dispatcher_layer1 \
  tests.test_dispatcher_external_sources 2>&1 | tail -6
```
(If `tests.test_focused_cognition` is named differently: `ls tests/ | grep -i focused`.)
Expected: OK — the 6-tuple change must not break any focused assembly test. A failure here means a `raw_items` append/unpack site was missed.

- [ ] **Step 6: Commit**

```bash
git add core/dispatcher/layer1.py core/brain/brain_loop.py core/routing/focused_cognition.py tests/test_self_web_claim_hygiene.py
git commit -m "$(cat <<'EOF'
feat(recall): thread provenance_source metadata -> RecallItem -> EvidenceItem

Only trust_tier travelled the structured recall chain; provenance_source now
rides alongside it (RecallItem.provenance_source, EvidenceItem.origin_provenance,
6-tuple raw_items). Wiring only — no filter yet.

## Predicted effect

No behavior change: origin_provenance is carried but not yet read by any filter
or renderer. Prompt output is byte-identical (the new field is unused downstream
until Task 5).

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Store split — two linked records on web-grounded turns + store receipt + flag

**Files:**
- Modify: `memory/memory_manager.py:1114-1145` (`store_telegram` — add `turn_link_id` kwarg into metadata)
- Modify: `daemon/maez_daemon.py:7226-7234` (the store seam)
- Test: `tests/test_self_web_claim_hygiene.py`

**Uses the Task-0a signal** for `web_grounded` (default `bool((web_context or "").strip())` unless Task 0a found otherwise).

- [ ] **Step 1: Write the failing test (store_telegram accepts turn_link_id)**

Append a test that `store_telegram` persists `turn_link_id` into the row metadata. Use the project's existing `MemoryManager` test fixture pattern — find it first:
```bash
grep -rln "store_telegram(" tests/ | head
```
Model the new test on that file's fixture (a temp ChromaDB path). Test shape:
```python
class StoreTurnLinkIdTest(unittest.TestCase):
    def test_store_telegram_persists_turn_link_id(self):
        mgr = _make_temp_memory_manager()  # reuse the existing fixture helper
        mid = mgr.store_telegram("Maez: hi", provenance_source="self_web_claim",
                                 trust_tier="untrusted", turn_link_id="turn-xyz")
        row = mgr.raw.get(ids=[mid], include=["metadatas"])
        self.assertEqual(row["metadatas"][0]["turn_link_id"], "turn-xyz")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_self_web_claim_hygiene.StoreTurnLinkIdTest -v`
Expected: FAIL — `TypeError: unexpected keyword argument 'turn_link_id'`.

- [ ] **Step 3a: Add `turn_link_id` to `store_telegram`**

In `memory/memory_manager.py`, `store_telegram` signature (line 1114-1116):
```python
    def store_telegram(self, content: str, *,
                       provenance_source=None, trust_tier=None,
                       egress_origin_class=None, turn_link_id=None) -> str:
```
And merge it into `meta` (where the `meta = {...}` dict is built, ~line 1129-1143), after the existing keys:
```python
        if turn_link_id:
            meta["turn_link_id"] = str(turn_link_id)
```

- [ ] **Step 3b: Split the store at the daemon seam**

In `daemon/maez_daemon.py`, replace the single store (lines 7230-7234) with the flag-gated split. Add the import near the top of the file if absent: `from core.infra.env_flags import strict_env_flag`. Then:
```python
        _self_claim_hygiene = strict_env_flag("MAEZ_SELF_CLAIM_HYGIENE_ENABLED")
        _web_grounded = bool((web_context or "").strip())  # Task-0a signal
        if _self_claim_hygiene and _web_grounded:
            _turn_link_id = uuid.uuid4().hex
            _m1_raw_memory_id = self.memory.store_telegram(
                f"the owner ({source}): {text}",
                provenance_source="user_utterance",
                trust_tier="lived",
                turn_link_id=_turn_link_id,
            )
            _reply_memory_id = self.memory.store_telegram(
                f"Maez: {reply}",
                provenance_source="self_web_claim",
                trust_tier="untrusted",
                turn_link_id=_turn_link_id,
            )
            logger.info(
                "self_claim_stored web_grounded=True provenance=self_web_claim "
                "trust_tier=untrusted reply_chars=%d turn_link_id=%s",
                len(reply or ""),
                _turn_link_id,
            )
        else:
            _m1_raw_memory_id = self.memory.store_telegram(
                f"the owner ({source}): {text}\nMaez: {reply}",
                provenance_source="user_utterance",
                trust_tier="lived",
            )
```
**Invariant:** when the split fires, the old combined record is NOT written (the two records are written *instead*), and `_m1_raw_memory_id` is bound to the **owner** record id (Task 4 depends on this).

- [ ] **Step 4: Write + run the store-split behavior tests**

Append tests that drive the daemon store decision. Prefer testing a small extracted helper to avoid standing up the whole daemon: extract the decision into a module-level pure function `decide_turn_storage(*, source, text, reply, web_context, hygiene_enabled) -> list[StoreSpec]` (a `StoreSpec` = namedtuple of `content, provenance_source, trust_tier, turn_link_id, is_owner_record`) and have `handle_message` call it, then store per spec. Test the helper:
```python
class StoreSplitDecisionTest(unittest.TestCase):
    def test_web_grounded_on_splits_into_two_linked_records(self):
        from daemon.maez_daemon import decide_turn_storage
        specs = decide_turn_storage(source="telegram", text="news about X",
                                    reply="X did Y", web_context="[fresh] ...",
                                    hygiene_enabled=True)
        self.assertEqual(len(specs), 2)
        owner = [s for s in specs if s.is_owner_record][0]
        reply = [s for s in specs if not s.is_owner_record][0]
        self.assertEqual(owner.provenance_source, "user_utterance")
        self.assertEqual(owner.trust_tier, "lived")
        self.assertEqual(reply.provenance_source, "self_web_claim")
        self.assertEqual(reply.trust_tier, "untrusted")
        self.assertEqual(owner.turn_link_id, reply.turn_link_id)
        self.assertNotIn("Maez:", owner.content)   # no duplicate reply text
        self.assertNotIn("the owner", reply.content)

    def test_non_web_grounded_keeps_single_combined_record(self):
        from daemon.maez_daemon import decide_turn_storage
        specs = decide_turn_storage(source="telegram", text="hi", reply="hello",
                                    web_context="", hygiene_enabled=True)
        self.assertEqual(len(specs), 1)
        self.assertEqual(specs[0].provenance_source, "user_utterance")
        self.assertEqual(specs[0].trust_tier, "lived")
        self.assertIn("Maez:", specs[0].content)

    def test_flag_off_keeps_single_combined_record_even_web_grounded(self):
        from daemon.maez_daemon import decide_turn_storage
        specs = decide_turn_storage(source="telegram", text="news about X",
                                    reply="X did Y", web_context="[fresh] ...",
                                    hygiene_enabled=False)
        self.assertEqual(len(specs), 1)
        self.assertEqual(specs[0].trust_tier, "lived")
```
Implement `decide_turn_storage` as the single source of truth for the split decision; the daemon block in Step 3b becomes a thin loop over its specs (binding `_m1_raw_memory_id` to the owner record's stored id). RED first, then GREEN.

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_self_web_claim_hygiene.StoreSplitDecisionTest tests.test_self_web_claim_hygiene.StoreTurnLinkIdTest -v`
Expected: first RED (no `decide_turn_storage`), then PASS after implementing it.

- [ ] **Step 5: Commit**

```bash
git add memory/memory_manager.py daemon/maez_daemon.py tests/test_self_web_claim_hygiene.py
git commit -m "$(cat <<'EOF'
feat(daemon): split store into two linked records on web-grounded turns

Behind MAEZ_SELF_CLAIM_HYGIENE_ENABLED: a web-grounded turn writes the owner
utterance (user_utterance/lived) and Maez's reply (self_web_claim/untrusted) as
two records linked by turn_link_id, INSTEAD OF the old combined record (no
duplicate). Non-web-grounded turns and flag-off are unchanged. Emits the
self_claim_stored receipt. _m1_raw_memory_id binds to the owner record (Task 4).

## Predicted effect

With the flag on, a Telegram turn that fetched fresh web no longer stores Maez's
reply at lived trust; it is stored untrusted under self_web_claim. Flag off and
non-web turns: byte-identical storage.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: M1 owner-id-only promotion invariant (must-fix M1)

**Files:**
- Modify: `daemon/maez_daemon.py:7235-7246` (the `consider_audited_exchange` call)
- Test: `tests/test_self_web_claim_hygiene.py`

The split already binds `_m1_raw_memory_id` to the owner record (Task 3), so the existing call passes the owner id. This task **locks that as an invariant with a test**, and guards `maez_reply` so the reply's web-claims cannot enter via any future episode-content change.

- [ ] **Step 1: Write the failing test**

```python
class M1OwnerIdOnlyTest(unittest.TestCase):
    def test_promotion_receives_owner_id_only_on_split(self):
        # decide_turn_storage marks which spec is the owner record; the daemon must
        # pass that record's id (never the reply record id) to M1.
        from daemon.maez_daemon import m1_raw_memory_id_for_promotion
        owner_id, reply_id = "owner-1", "reply-1"
        chosen = m1_raw_memory_id_for_promotion(owner_id=owner_id, reply_id=reply_id)
        self.assertEqual(chosen, owner_id)
        self.assertNotEqual(chosen, reply_id)

    def test_promotion_id_is_owner_when_unsplit(self):
        from daemon.maez_daemon import m1_raw_memory_id_for_promotion
        combined = "combined-1"
        self.assertEqual(
            m1_raw_memory_id_for_promotion(owner_id=combined, reply_id=None), combined
        )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_self_web_claim_hygiene.M1OwnerIdOnlyTest -v`
Expected: FAIL — `ImportError: cannot import name 'm1_raw_memory_id_for_promotion'`.

- [ ] **Step 3: Implement the guard helper + use it**

Add a module-level pure function in `daemon/maez_daemon.py`:
```python
def m1_raw_memory_id_for_promotion(*, owner_id: str, reply_id: str | None) -> str:
    """M1 promotion lineage may cite ONLY the owner record (never the
    self_web_claim reply), so a web-grounded reply cannot relaunder into a lived
    episode's source_memory_ids. reply_id is accepted only to make the exclusion
    explicit and testable."""
    return owner_id
```
In `handle_message`, ensure `_m1_raw_memory_id` passed to `consider_audited_exchange` (line 7244) is `m1_raw_memory_id_for_promotion(owner_id=<owner record id>, reply_id=<reply record id or None>)`. (On the unsplit path `reply_id=None` and it returns the combined id — unchanged.)

- [ ] **Step 4: Run test to verify it passes**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_self_web_claim_hygiene.M1OwnerIdOnlyTest -v`
Expected: PASS.

- [ ] **Step 5: Run the M1 promotion suite (regression)**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_m1_lived_episode_promotion 2>&1 | tail -5`
(Confirm module name: `ls tests/ | grep -i m1`.)
Expected: OK — `source_memory_ids` lineage behavior for the unsplit path is unchanged.

- [ ] **Step 6: Commit**

```bash
git add daemon/maez_daemon.py tests/test_self_web_claim_hygiene.py
git commit -m "$(cat <<'EOF'
fix(m1): promotion lineage cites owner record only on split turns

M1 lived-episode promotion records raw_memory_id into source_memory_ids. On the
split web-grounded path it must receive the owner record id only, never the
SELF_WEB_CLAIM reply id (and never both) — else the reply relaunders into lived
lineage past the recall filter. Episode content is structural-only
(build_structural_summary), so the id is the sole vector; this closes it.

## Predicted effect

A promoted lived episode from a web-grounded turn cites only the owner utterance
as its source. Unsplit turns: unchanged.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Recall exclusion filter + no-fresh keep/label + recall receipt

**Files:**
- Modify: `core/routing/focused_cognition.py:808-889` (post-collection filter) + the evidence-line renderer (`:289-325`)
- Test: `tests/test_self_web_claim_hygiene.py`

**Fresh source types:** from `_SOURCE_TYPE`/ranking, fresh = `{"fresh_evidence", "web_context"}`. Verify against `core/routing/focused_cognition.py:45-72` during implementation; if a dispatcher fresh block uses a different `source_type` label, include it.

- [ ] **Step 1: Write the failing tests**

`assemble_working_set` is the real entry (`focused_cognition.py:761`); its signature is
`(*, transcript, web_context, owner_question, chat_history=None, recall_items=None,
max_working_set_chars=None) -> WorkingSet | None`. `recall_items` maps to the internal
`structured_recall_items` (line 799); `WorkingSet.items` is the `list[EvidenceItem]`. The flag
is read from env inside the function, so tests set it via `mock.patch.dict`.
```python
from unittest import mock


class RecallExclusionTest(unittest.TestCase):
    def _items(self, *triples):
        # triples: (source_type, text, origin_provenance)
        from core.dispatcher.layer1 import RecallItem
        return tuple(RecallItem(text=t, source_type=st, durable_id=t,
                                trust_tier=("untrusted" if op else None),
                                provenance_source=op) for st, t, op in triples)

    def _assemble(self, *, recall_items, web_context, enabled):
        from core.routing.focused_cognition import assemble_working_set
        env = {"MAEZ_SELF_CLAIM_HYGIENE_ENABLED": "1" if enabled else "0"}
        with mock.patch.dict("os.environ", env):
            return assemble_working_set(
                transcript="",
                web_context=web_context,
                owner_question="news about Anthropic",
                recall_items=recall_items,
            )

    def test_self_web_claim_excluded_when_fresh_present(self):
        ws = self._assemble(
            recall_items=self._items(("memory_context", "old Anthropic claim", "self_web_claim")),
            web_context="Anthropic released a new model today.",  # non-empty -> web_context fresh item
            enabled=True,
        )
        self.assertIsNotNone(ws)
        self.assertNotIn("old Anthropic claim", [it.text for it in ws.items])

    def test_self_web_claim_kept_and_labeled_when_no_fresh(self):
        ws = self._assemble(
            recall_items=self._items(("memory_context", "old Anthropic claim", "self_web_claim")),
            web_context="",
            enabled=True,
        )
        kept = [it for it in ws.items if it.text == "old Anthropic claim"]
        self.assertEqual(len(kept), 1)
        self.assertEqual(kept[0].origin_provenance, "self_web_claim")

    def test_external_web_untrusted_not_excluded_when_fresh(self):
        ws = self._assemble(
            recall_items=self._items(("memory_context", "prior web observation", "external_web")),
            web_context="Something fresh happened today.",
            enabled=True,
        )
        self.assertIn("prior web observation", [it.text for it in ws.items])

    def test_flag_off_keeps_self_web_claim_even_with_fresh(self):
        ws = self._assemble(
            recall_items=self._items(("memory_context", "old Anthropic claim", "self_web_claim")),
            web_context="Anthropic released a new model today.",
            enabled=False,
        )
        self.assertIn("old Anthropic claim", [it.text for it in ws.items])
```
The *assertions* (excluded/kept/scope/flag) are the contract and must not be weakened. Verify
during implementation that `recall_items` carries `provenance_source` into
`structured_recall_items` unchanged (it should — line 799 is a passthrough `tuple(...)`).

- [ ] **Step 2: Run tests to verify they fail**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_self_web_claim_hygiene.RecallExclusionTest -v`
Expected: FAIL — self_web_claim item is present when fresh (no filter yet).

- [ ] **Step 3: Implement the post-collection filter + receipt**

In `core/routing/focused_cognition.py`, after `raw_items` is fully built and before `_ranked_items_for_state` (line 870-873), insert:
```python
    _FRESH_SOURCE_TYPES = ("fresh_evidence", "web_context")
    if _self_claim_hygiene_enabled():
        fresh_present = any(st in _FRESH_SOURCE_TYPES for st, *_ in raw_items)
        kept = []
        excluded = 0
        for tup in raw_items:
            _st, _txt, _did, _tp, _ot, _op = tup
            if fresh_present and _op == "self_web_claim":
                excluded += 1
                continue
            kept.append(tup)
        raw_items = kept
        if excluded or fresh_present:
            logger.info(
                "recall_hygiene fresh_present=%s excluded_self_claims=%d kept_memory_items=%d",
                fresh_present,
                excluded,
                sum(1 for st, *_ in raw_items if st in ("memory_context", "memory_evidence")),
            )
    if not raw_items:
        return None
```
Add the flag helper near the top of the module:
```python
def _self_claim_hygiene_enabled() -> bool:
    from core.infra.env_flags import strict_env_flag
    return strict_env_flag("MAEZ_SELF_CLAIM_HYGIENE_ENABLED")
```
For the no-fresh **hard label**: in the evidence-line renderer (`_origin_trust_segment` / the render around `:289-325`), when `item.origin_provenance == "self_web_claim"`, append a visible tag e.g. `" · self-web-claim (unverified prior)"` to the rendered line. Add a `_SELF_WEB_CLAIM_LABEL` constant and gate the tag on `origin_provenance`.

(If `assemble_working_set` is not the real entry name, wire the filter into the actual builder and expose a thin test seam matching Step 1.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_self_web_claim_hygiene.RecallExclusionTest -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Run the focused suite (regression)**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_focused_cognition 2>&1 | tail -6`
Expected: OK.

- [ ] **Step 6: Commit**

```bash
git add core/routing/focused_cognition.py tests/test_self_web_claim_hygiene.py
git commit -m "$(cat <<'EOF'
feat(focused): exclude self-web-claims from evidence when fresh present

Behind MAEZ_SELF_CLAIM_HYGIENE_ENABLED: at focused assembly, memory_context items
with origin_provenance=self_web_claim are dropped when the working set contains
fresh evidence (fresh_evidence/web_context); kept + hard-labeled when no fresh.
Scope is self-authored only (external_web untrusted memory untouched). Emits the
recall_hygiene receipt (excluded_self_claims is the load-bearing witness).

## Predicted effect

With the flag on, a turn that re-recalls Maez's own prior web-grounded reply will
drop that reply from the evidence set whenever fresh web is present this turn, so
fresh wins. Flag off: byte-identical (no filter, no receipt).

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: Flag-off byte-identical sweep

**Files:**
- Test: `tests/test_self_web_claim_hygiene.py`

- [ ] **Step 1: Write the flag-off invariants test**

```python
from unittest import mock


class FlagOffByteIdenticalTest(unittest.TestCase):
    def test_store_decision_flag_off_is_single_combined(self):
        from daemon.maez_daemon import decide_turn_storage
        specs = decide_turn_storage(source="telegram", text="news about X",
                                    reply="X did Y", web_context="fresh stuff",
                                    hygiene_enabled=False)
        self.assertEqual(len(specs), 1)
        self.assertIn("Maez:", specs[0].content)

    def test_recall_flag_off_emits_no_hygiene_receipt(self):
        from core.dispatcher.layer1 import RecallItem
        from core.routing.focused_cognition import assemble_working_set
        recall = (RecallItem(text="old claim", source_type="memory_context",
                             durable_id="d", trust_tier="untrusted",
                             provenance_source="self_web_claim"),)
        with mock.patch.dict("os.environ", {"MAEZ_SELF_CLAIM_HYGIENE_ENABLED": "0"}):
            with self.assertLogs("maez", level="INFO") as cm:
                import logging
                logging.getLogger("maez").info("probe")  # ensure the context has >=1 record
                assemble_working_set(transcript="", web_context="fresh stuff",
                                     owner_question="news about Anthropic",
                                     recall_items=recall)
        self.assertFalse(any("recall_hygiene" in m for m in cm.output))
```
The `self_claim_stored` receipt's flag-off absence is covered by
`StoreSplitDecisionTest.test_flag_off_keeps_single_combined_record_even_web_grounded` (no split →
no receipt). This task adds the recall-receipt-absence proof and the consolidated flag-off store
assertion.

- [ ] **Step 2: Run → RED → implement any missing gate → GREEN**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_self_web_claim_hygiene.FlagOffByteIdenticalTest -v`
Expected: PASS once both receipts and both behavior paths are confirmed flag-gated (they are, from Tasks 3 + 5 — this task is the consolidated proof).

- [ ] **Step 3: Full feature-suite green + ruff**

Run:
```bash
/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_self_web_claim_hygiene 2>&1 | tail -6
/home/rohit/maez/.venv/bin/ruff check memory/memory_manager.py core/dispatcher/layer1.py core/brain/brain_loop.py core/routing/focused_cognition.py daemon/maez_daemon.py tests/test_self_web_claim_hygiene.py 2>&1 | tail -3
```
Expected: all feature tests OK; ruff clean.

- [ ] **Step 4: Commit**

```bash
git add tests/test_self_web_claim_hygiene.py
git commit -m "$(cat <<'EOF'
test(self-web-claim): flag-off byte-identical sweep (store + recall + receipts)

Asserts that with MAEZ_SELF_CLAIM_HYGIENE_ENABLED off, a web-grounded turn stores
one combined lived record, no recall exclusion fires, and neither the
self_claim_stored nor recall_hygiene receipt is emitted.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: STOP-at-gate handoff doc

**Files:**
- Create: `docs/handoffs/2026-06-15-self-web-claim-hygiene-gate.md`

- [ ] **Step 1: Write the handoff**

Document, for the owner-sovereign breath:
1. **Branch + commits:** `self-web-claim-hygiene`, the task commits, all suites green (paste the final run output), ruff clean.
2. **Cross-lane review ask:** this touches the honesty/memory core — request a Codex cross-lane review at the gate. Anchors: SELF_WEB_CLAIM=untrusted (not claude_tier_response); split writes two records *instead of* combined (no duplicate); M1 owner-id-only (reply id never in source_memory_ids); recall excludes self_web_claim only when fresh present, scope self-authored; off=byte-identical.
3. **Owner breath sequence:** add `MAEZ_SELF_CLAIM_HYGIENE_ENABLED=1` to `~/.config/maez/model.env` (Claude does NOT edit model.env); `systemctl --user restart maez.service`.
4. **Live witness (forward-only):** on a NEW web-grounded turn (e.g. `news about Anthropic`), grep `logs/maez.log` for `self_claim_stored web_grounded=True ... trust_tier=untrusted` (store) and, on a follow-up turn that re-recalls it with fresh present, `recall_hygiene fresh_present=True excluded_self_claims>=1` (recall). The `excluded_self_claims` count is the proof.
5. **Forward-only caveat (verbatim from spec):** this does NOT heal the already-stored Anthropic `lived` record; do NOT claim the Anthropic wound healed from this slice. Healing it is a separate owner-approved backfill.
6. **Revert:** set the flag to `0` + restart (off = byte-identical).

- [ ] **Step 2: Commit + STOP**

```bash
git add docs/handoffs/2026-06-15-self-web-claim-hygiene-gate.md
git commit -m "$(cat <<'EOF'
docs(handoff): self-web-claim hygiene STOP-at-gate (owner breath + witness)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```
**Then STOP.** Do not flip the flag, restart, or merge — those are the owner's sovereign breaths. Surface the branch tip + green suites + the witness recipe and wait.

---

## Notes for the implementer

- **Test runner:** `/home/rohit/maez/.venv/bin/python -B -m unittest <module>` — NEVER `discover`, NEVER a bare run that walks the whole tree.
- **Fixtures:** reuse existing `MemoryManager` temp-ChromaDB fixtures (grep `store_telegram(` in `tests/`); do not invent a new DB harness.
- **Real names over assumptions:** Tasks 3 and 5 reference an extracted helper (`decide_turn_storage`) and the focused working-set builder. Read the real functions before writing — if the builder's entry name/signature differs from `assemble_working_set`, wire into the real one and adapt the test's *call* (never the assertions).
- **Arity discipline (Task 2):** the 5→6 tuple change is the highest-risk edit. After it, the focused suite must be green before proceeding; a red there means a missed append/unpack site.
- **No push. STOP at the gate.** Forward-only — never claim the stored Anthropic record is healed.
