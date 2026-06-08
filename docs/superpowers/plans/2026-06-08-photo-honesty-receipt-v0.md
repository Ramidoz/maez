# Photo Honesty Receipt v0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A photo-focused reply that doesn't validly cite its vision evidence (`cited_ids != ["E1"]`) never reaches the user or memory as a trusted "I saw it" answer — caught deterministically, with zero model latency on the good path.

**Architecture:** Extend `synthesize_photo_turn` with a deterministic citation rail (valid = `cited_ids == ["E1"]`; ungrounded first reply → one forced-citation retry → deterministic `[E1]`-bearing fallback). Add `FocusedResult.receipt_reason`. The daemon photo branch logs the receipt trace-linked to `turn_id`. No judge, no memory-schema change.

**Tech Stack:** Python, `unittest` (NOT pytest). Run via `/home/rohit/maez/.venv/bin/python -B -m unittest`.

**Worktree:** `/home/rohit/maez-wt-photo-honesty` (branch `photo-honesty-receipt-v0`). Run all commands from there.

---

## File Structure

- **Modify** `core/routing/focused_cognition.py`:
  - `FocusedResult` dataclass — add `receipt_reason: str | None = None`.
  - New constant `_PHOTO_VISION_RETRY_INSTRUCTION`.
  - `synthesize_photo_turn` — the rail (valid-citation gate, retry, deterministic-with-`[E1]`, set `receipt_reason`).
- **Modify** `daemon/maez_daemon.py` — photo branch (~5984): log `receipt=<reason> turn_id=<_user_msg_turn_id>`.
- **Modify** `tests/test_photo_focused_synthesis.py` — rail behavior tests (the core).
- **Modify** `tests/test_photo_focused_routing.py` — structural test for the daemon receipt log.

---

### Task 1: `FocusedResult.receipt_reason` field + retry instruction constant

**Files:**
- Modify: `core/routing/focused_cognition.py` (FocusedResult dataclass ~286; constants block ~133)
- Test: `tests/test_photo_focused_synthesis.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_photo_focused_synthesis.py`:

```python
def test_focused_result_has_receipt_reason_default_none(self):
    from core.routing.focused_cognition import FocusedResult
    r = FocusedResult(reply="x", cited_ids=["E1"], working_set_chars=1)
    self.assertIsNone(r.receipt_reason)
    r2 = FocusedResult(reply="x", cited_ids=["E1"], working_set_chars=1,
                       receipt_reason="cited_ok")
    self.assertEqual(r2.receipt_reason, "cited_ok")
```

(Add it inside the existing `SynthesizePhotoTurn` class, or a new `unittest.TestCase`.)

- [ ] **Step 2: Run test to verify it fails**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_photo_focused_synthesis -k receipt_reason_default`
Expected: FAIL — `TypeError: __init__() got an unexpected keyword argument 'receipt_reason'`.

- [ ] **Step 3: Add the field + the retry instruction constant**

In `core/routing/focused_cognition.py`, the `FocusedResult` dataclass currently is:

```python
@dataclass(frozen=True)
class FocusedResult:
    reply: str
    cited_ids: list[str]
    working_set_chars: int
    prompt_build_ms: int | None = None
    chat_total_ms: int | None = None
    reply_token_est: int | None = None
```

Add the field at the end:

```python
@dataclass(frozen=True)
class FocusedResult:
    reply: str
    cited_ids: list[str]
    working_set_chars: int
    prompt_build_ms: int | None = None
    chat_total_ms: int | None = None
    reply_token_est: int | None = None
    receipt_reason: str | None = None
```

Add the retry instruction constant immediately AFTER the existing
`_PHOTO_VISION_INSTRUCTION = ( ... )` block (around line 142):

```python
_PHOTO_VISION_RETRY_INSTRUCTION = (
    "Your previous answer did not cite the evidence. Every claim you make about "
    "the photo MUST cite [E1] — the only evidence — and no other label. If you "
    "cannot ground a statement in the analysis above, do not make it. Answer "
    "again, citing [E1]."
)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_photo_focused_synthesis -k receipt_reason_default`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd /home/rohit/maez-wt-photo-honesty
git add core/routing/focused_cognition.py tests/test_photo_focused_synthesis.py
git commit -m "feat(focused-cognition): FocusedResult.receipt_reason + retry instruction"
```

---

### Task 2: The deterministic citation rail in `synthesize_photo_turn`

**Files:**
- Modify: `core/routing/focused_cognition.py` (`synthesize_photo_turn`)
- Test: `tests/test_photo_focused_synthesis.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_photo_focused_synthesis.py`. Helper for a chat_fn that returns a
scripted sequence of contents (so retry can differ from the first call):

```python
def _scripted_chat(contents):
    """Return a chat_fn that yields each content in order, then "" forever."""
    box = {"i": 0}

    def chat_fn(**_k):
        i = box["i"]
        box["i"] += 1
        text = contents[i] if i < len(contents) else ""
        return SimpleNamespace(message=SimpleNamespace(content=text))

    return chat_fn, box


class CitationRail(unittest.TestCase):
    A = ANALYSIS  # module-level analysis text from this test file

    def test_valid_citation_first_try_is_cited_ok(self):
        chat, box = _scripted_chat(["That's a Reddit thread [E1]."])
        r = synthesize_photo_turn(analysis_text=self.A, caption="check this",
                                  surface="telegram_surface", chat_fn=chat, model="m")
        self.assertEqual(r.receipt_reason, "cited_ok")
        self.assertEqual(r.cited_ids, ["E1"])
        self.assertEqual(box["i"], 1)  # no retry

    def test_ungrounded_then_retry_recovers(self):
        chat, box = _scripted_chat(["A Reddit thread.",            # cited=0
                                    "A Reddit thread [E1]."])      # retry cites E1
        r = synthesize_photo_turn(analysis_text=self.A, caption="check this",
                                  surface="telegram_surface", chat_fn=chat, model="m")
        self.assertEqual(r.receipt_reason, "retry_recovered")
        self.assertEqual(r.cited_ids, ["E1"])
        self.assertIn("[E1]", r.reply)
        self.assertEqual(box["i"], 2)  # exactly one retry

    def test_ungrounded_both_times_is_deterministic_fallback(self):
        chat, box = _scripted_chat(["WWDC2024 clip, no cite.",     # cited=0
                                    "Still no citation here."])    # retry cited=0
        r = synthesize_photo_turn(analysis_text=self.A, caption="check this",
                                  surface="telegram_surface", chat_fn=chat, model="m")
        self.assertEqual(r.receipt_reason, "deterministic_fallback")
        self.assertEqual(r.cited_ids, ["E1"])
        self.assertIn("[E1]", r.reply)
        self.assertIn("Reddit", r.reply)              # the sight-report (analysis)
        self.assertNotIn("WWDC2024", r.reply)         # NOT the wandering reply
        self.assertNotIn("Still no citation", r.reply)
        self.assertEqual(box["i"], 2)

    def test_fake_citation_e2_is_ungrounded(self):
        # [E2] is not in the one-item working set → fake grounding → retry/fallback,
        # never accepted as cited_ok.
        chat, box = _scripted_chat(["It shows [E2] a thread.",     # invalid label
                                    "Now grounded [E1]."])         # retry valid
        r = synthesize_photo_turn(analysis_text=self.A, caption="check this",
                                  surface="telegram_surface", chat_fn=chat, model="m")
        self.assertEqual(r.receipt_reason, "retry_recovered")
        self.assertEqual(r.cited_ids, ["E1"])

    def test_e1_plus_e2_is_ungrounded(self):
        chat, box = _scripted_chat(["A thread [E1][E2].",          # E1+fake E2 → invalid
                                    "no cite either"])             # retry cited=0
        r = synthesize_photo_turn(analysis_text=self.A, caption="check this",
                                  surface="telegram_surface", chat_fn=chat, model="m")
        self.assertEqual(r.receipt_reason, "deterministic_fallback")
        self.assertEqual(r.cited_ids, ["E1"])

    def test_empty_brain_first_call_no_retry(self):
        chat, box = _scripted_chat([""])  # brain returns nothing
        r = synthesize_photo_turn(analysis_text=self.A, caption="check this",
                                  surface="telegram_surface", chat_fn=chat, model="m")
        self.assertEqual(r.receipt_reason, "deterministic_fallback")
        self.assertEqual(box["i"], 1)     # NO wasted retry
        self.assertEqual(r.cited_ids, ["E1"])

    def test_retry_raises_falls_back(self):
        calls = {"i": 0}

        def chat_fn(**_k):
            calls["i"] += 1
            if calls["i"] == 1:
                return SimpleNamespace(message=SimpleNamespace(content="no cite"))
            raise RuntimeError("brain down on retry")

        r = synthesize_photo_turn(analysis_text=self.A, caption="check this",
                                  surface="telegram_surface", chat_fn=chat_fn, model="m")
        self.assertEqual(r.receipt_reason, "deterministic_fallback")
        self.assertEqual(r.cited_ids, ["E1"])
        self.assertEqual(calls["i"], 2)   # at most one retry, then fallback
```

Ensure `from types import SimpleNamespace` and the module-level `ANALYSIS` (a
string containing "Reddit", no `[E#]` markers) exist in the file. The existing file
already defines `ANALYSIS = ("The image is a screenshot of a Reddit thread …")`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_photo_focused_synthesis.CitationRail`
Expected: FAIL — current `synthesize_photo_turn` has no retry and no `receipt_reason` (so `receipt_reason` is `None`, `box["i"]` is 1, etc.).

- [ ] **Step 3: Implement the rail**

Replace the tail of `synthesize_photo_turn` — from the `deterministic = ( ... )`
assignment through the `return FocusedResult( ... )` — with this. (Keep everything
ABOVE `deterministic` — the chat_fn/model defaults, working_set, EvidenceItem —
unchanged.)

```python
    # Deterministic fallback: the vision analysis verbatim, citing [E1] so the
    # reply, cited_ids, log, and downstream checks all agree. Grounded by
    # construction (it IS the evidence). receipt_reason marks it as forced.
    deterministic = ("Here's what I'm confident I saw [E1]: " + analysis_text).strip()

    base_system = (
        f"{_voice_card(surface)}\n\n"
        f"{_PHOTO_VISION_INSTRUCTION}\n\n"
        f"=== WHAT MAEZ SAW IN THE PHOTO (cite [E1]) ===\n"
        f"{analysis_text}"
    )

    def _run(system_text):
        try:
            response = chat_fn(
                model=model,
                messages=[
                    {"role": "system", "content": system_text},
                    {"role": "user", "content": caption},
                ],
                think=False,
                options={"temperature": 0.7, "num_predict": 1024},
            )
            return (
                getattr(getattr(response, "message", None), "content", None) or ""
            ).strip()
        except Exception:
            return ""

    def _valid_photo_citation(text: str) -> bool:
        # Valid only if it cites E1 and NO other label. The one-item photo working
        # set contains exactly E1; any other [E#] is fake grounding.
        return sorted({f"E{m.group(1)}" for m in _CITE_RE.finditer(text)}) == ["E1"]

    _t0 = _time.monotonic()
    _t1 = _time.monotonic()
    first_raw = _run(base_system)
    if first_raw and _valid_photo_citation(first_raw):
        reply, receipt_reason = first_raw, "cited_ok"
    elif first_raw:
        # Brain produced an ungrounded reply. One forced-citation retry.
        retry_raw = _run(base_system + "\n\n" + _PHOTO_VISION_RETRY_INSTRUCTION)
        if retry_raw and _valid_photo_citation(retry_raw):
            reply, receipt_reason = retry_raw, "retry_recovered"
        else:
            reply, receipt_reason = deterministic, "deterministic_fallback"
    else:
        # Brain returned nothing on the first call — no wasted retry.
        reply, receipt_reason = deterministic, "deterministic_fallback"
    _t2 = _time.monotonic()

    cited_ids = sorted({f"E{m.group(1)}" for m in _CITE_RE.finditer(reply)})
    return FocusedResult(
        reply=reply,
        cited_ids=cited_ids,
        working_set_chars=working_set_chars,
        prompt_build_ms=int((_t1 - _t0) * 1000),
        chat_total_ms=int((_t2 - _t1) * 1000),
        reply_token_est=len(reply) // 4,
        receipt_reason=receipt_reason,
    )
```

Note: the old inline `system = (...)`, `messages = [...]`, and the old single chat
block are REPLACED by `base_system` + the `_run` helper. Delete the old `system`,
`messages`, `raw_reply`, and the old `reply = raw_reply or deterministic` /
`cited_ids` lines (they're superseded above).

- [ ] **Step 4: Run tests to verify they pass**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_photo_focused_synthesis`
Expected: PASS (the original 7 tests + the new rail tests).

- [ ] **Step 5: Commit**

```bash
git add core/routing/focused_cognition.py tests/test_photo_focused_synthesis.py
git commit -m "feat(focused-cognition): deterministic citation rail for photo synthesis

valid photo citation = cited_ids==[E1]; ungrounded first reply → one forced-cite
retry → deterministic [E1]-bearing fallback; receipt_reason records which.

## Predicted effect

A photo reply that doesn't validly cite its vision evidence is retried once; if
still ungrounded it becomes the deterministic 'Here's what I'm confident I saw
[E1]: <analysis>'. The WWDC2024-class (cited=0) hallucination never returns. Good
(cited_ok) path is unchanged and adds no latency."
```

---

### Task 3: Trace-linked receipt log in the daemon photo branch

**Files:**
- Modify: `daemon/maez_daemon.py` (photo branch — the `photo_focused_synthesis` log, ~5987)
- Test: `tests/test_photo_focused_routing.py`

- [ ] **Step 1: Write the failing structural test**

Add to `tests/test_photo_focused_routing.py`, in the
`PhotoSynthesisLivesInsideThePipeline` class:

```python
def test_photo_log_is_trace_linked_with_receipt(self):
    body = _handle_message_body()
    # the photo_focused_synthesis log must carry the receipt reason and turn id
    self.assertIn("receipt=", body)
    self.assertIn("turn_id=", body)
    self.assertIn("receipt_reason", body)           # reads it off the result
    self.assertIn("_user_msg_turn_id", body)        # the trace key
```

- [ ] **Step 2: Run to verify it fails**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_photo_focused_routing.PhotoSynthesisLivesInsideThePipeline.test_photo_log_is_trace_linked_with_receipt`
Expected: FAIL — current log has no `receipt=`/`turn_id=`.

- [ ] **Step 3: Update the log line**

In `daemon/maez_daemon.py`, the photo branch currently logs:

```python
                    logger.info(
                        "photo_focused_synthesis surface=%s working_set_chars=%s "
                        "cited=%s reply_chars=%d",
                        source,
                        getattr(_photo_result, "working_set_chars", "?"),
                        len(getattr(_photo_result, "cited_ids", []) or []),
                        len(reply),
                    )
```

Replace with:

```python
                    logger.info(
                        "photo_focused_synthesis surface=%s working_set_chars=%s "
                        "cited=%s reply_chars=%d receipt=%s turn_id=%s",
                        source,
                        getattr(_photo_result, "working_set_chars", "?"),
                        len(getattr(_photo_result, "cited_ids", []) or []),
                        len(reply),
                        getattr(_photo_result, "receipt_reason", None),
                        _user_msg_turn_id,
                    )
```

`_user_msg_turn_id` is already defined earlier in `handle_message` (it feeds the
evidence envelope) and is in scope here — confirm with:
`grep -n "_user_msg_turn_id" daemon/maez_daemon.py | head` (it must appear BEFORE the photo branch).

- [ ] **Step 4: Run to verify it passes**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_photo_focused_routing`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add daemon/maez_daemon.py tests/test_photo_focused_routing.py
git commit -m "feat(telegram): trace-link photo receipt to turn_id in the daemon log

## Predicted effect

Each photo turn logs receipt=<cited_ok|retry_recovered|deterministic_fallback>
and turn_id, so 'what happened to this photo reply?' is answerable by id. No
behavior change beyond the log line; no memory-schema change."
```

---

### Task 4: Regression sweep

**Files:** none (verification only)

- [ ] **Step 1: Run the touched + adjacent suites**

Run:
```bash
/home/rohit/maez/.venv/bin/python -B -m unittest \
  tests.test_photo_focused_synthesis tests.test_photo_focused_routing \
  tests.test_chat_photo_wiring tests.test_focused_cognition \
  tests.test_memory_integrity_invariant tests.test_envelope_builder
```
Expected: all OK (the pre-existing `test_model_reply_persistence` ledger order-flake is NOT in this set; if you add it, run it in isolation to confirm it still passes).

- [ ] **Step 2: Full discover (floor check, AFTER the last change)**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest discover -s tests -t .`
Expected: same failure set as `main 0f9de8f` (known live-judge + fast-lane + ledger-meta order-flakes). Diff branch-only failures vs the main baseline; each branch-only delta must pass in isolation. Zero real regressions.

- [ ] **Step 3: Hand to Codex for cross-lane review** (do not self-merge). Write a short handoff in `docs/handoffs/` noting: branch, commits, the rail behavior, the `cited_ids==["E1"]` valid-citation rule, the honest scope limit (catches ignored-evidence, not cited-but-contradicts → Lane 2), and the floor result.

---

## Self-Review

**Spec coverage:** valid-citation `==["E1"]` (Task 2 `_valid_photo_citation`), retry-once (Task 2), deterministic-`[E1]` fallback (Task 2), `receipt_reason` field (Task 1), trace-linked log (Task 3), telemetry-only / no-schema-change (no memory edits anywhere), the 10 spec tests (Tasks 1–3 cover: receipt field; cited_ok; retry_recovered; deterministic_fallback; fake-citation [E2] and [E1][E2]; empty-first; retry-raises; at-most-once; trace-linked log; no-schema-change is satisfied by construction — no memory file touched). All covered.

**Placeholder scan:** none — every step has complete code/commands.

**Type consistency:** `receipt_reason: str | None` consistent across Task 1 (field), Task 2 (set to `cited_ok|retry_recovered|deterministic_fallback`), Task 3 (`getattr(_photo_result, "receipt_reason", None)`). `_valid_photo_citation` and `_PHOTO_VISION_RETRY_INSTRUCTION` names consistent.
