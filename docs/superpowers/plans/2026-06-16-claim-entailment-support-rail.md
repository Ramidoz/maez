# Claim-Level Entailment Support Rail Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** In shadow (observe-only), judge each cited sentence of Maez's final served reply for entailment against *only the evidence it cited*, via MiniCheck, with a witnessable per-claim receipt.

**Architecture:** Re-home the grounding-shadow observation to the focused path: capture a `{local_label→text}` evidence map from `_focused_working_set` at the `check_groundedness` seam, then enqueue the **post-audit served reply** + that map after `audit_assistant_text` returns. The reused `GroundingShadow` worker checks each post-audit sentence's cited `[E#]` against only that label's text (deterministic floor first, MiniCheck behind the swappable `SupportVerifier`), writing a claim-level receipt. Default-off flag; off = byte-identical.

**Tech Stack:** Python, `unittest` (runner `/home/rohit/maez/.venv/bin/python -B -m unittest <module>`, NEVER full-discover), the existing `core/cognition/grounding_shadow.py` + `support_verifier.py`, MiniCheck-DeBERTa via `scripts/minicheck_verifier_service.py` (`:8083/support`).

**Spec:** `docs/superpowers/specs/2026-06-16-claim-entailment-support-rail-design.md` (PASS, @eeb58c6).
**Branch:** `claim-entailment-support-rail` (main local-only/unpushed — NO push).
**Discipline:** TDD per task. `## Predicted effect` on behavior commits. `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`. **STOP at the review gate** before ANY flag flip / service install / restart (owner-sovereign). v0 is **shadow only — it MEASURES, does not protect a reply.**

## File Structure

| File | Responsibility | Change |
|---|---|---|
| `core/cognition/grounding_shadow.py` | shadow queue/worker/compute/telemetry | enqueue I/O-free fix; `compute_shadow` → cited-only mapping; `build_telemetry` → claim-level + `post_audit`; new `observe_focused_support` hook |
| `core/cognition/support_verifier.py` | verifier ABC + impls | add a `name` on verifiers (receipt needs `verifier`) |
| `daemon/maez_daemon.py` | focused reply path | capture map at ~6590; enqueue post-audit at ~6882; supersede audit-path hook |
| `core/safety/audited_output.py` | audit-path shadow hook | remove/neuter the superseded `_observe_grounding_shadow` (empty-claimable) |
| `scripts/grounding_bench/corpus.json` | audition corpus | add Anthropic/Mythos-class items |
| `tests/test_grounding_shadow.py` | shadow tests | extend (create if absent) |
| `docs/proof/2026-06-16-thread-a-task0.md` | Task-0 proofs | create |

**Branch setup (run once):**
```bash
cd /home/rohit/maez
git checkout main && git checkout -b claim-entailment-support-rail
git branch --show-current   # expect: claim-entailment-support-rail
```

---

## Task 0: Feasibility proofs (HARD GATE — docs only, no behavior change)

**Files:** Create `docs/proof/2026-06-16-thread-a-task0.md`. STOP gate — if either refutes the spec, STOP and patch spec/plan.

- [ ] **Step 1: Prove 0a — MiniCheck `/support` service health**

The service artifact exists (`scripts/minicheck_verifier_service.py`). Do NOT duplicate it. Prove it can answer (a probe is allowed; installing the unit is an owner breath — do not install):
```bash
cd /home/rohit/maez
ss -ltnp 2>/dev/null | grep ':8083' || echo "no :8083 listener (expected — not installed)"
# Probe the verifier contract WITHOUT standing up the unit: start the artifact transiently in a subshell,
# hit it once, kill it. (This proves the artifact answers {"verdict","score"}; it does not install anything.)
timeout 90 /home/rohit/maez/.venv/bin/python scripts/minicheck_verifier_service.py &
SVC=$!; sleep 25
curl -s -m 30 http://127.0.0.1:8083/support -H 'Content-Type: application/json' \
  -d '{"evidence":"Anthropic released Claude Opus 4.5.","claim":"Anthropic released Claude Opus 4.5."}' ; echo
kill $SVC 2>/dev/null
```
Expected: a JSON `{"verdict": "SUPPORTED"|"UNSUPPORTED", "score": <float>}`. Record the exact response. **If the model can't load (no weights / OOM), record that as the Task-0a outcome:** v0 still builds + tests the deterministic floor with `FakeSupportVerifier`, but the handoff must say "no verifier witness yet" (no fake witness).

- [ ] **Step 2: Prove 0b — capture-then-post-audit reachability (runtime)**

Confirm in source that BOTH moments are reachable in one `handle_message` scope, and that the post-audit reply retains `[E#]`:
```bash
sed -n '6588,6594p' daemon/maez_daemon.py    # _focused_result + _focused_working_set in scope
sed -n '6617,6621p' daemon/maez_daemon.py    # reply = _focused_reply; _focused_used = True
grep -n 'reply = audit_assistant_text' daemon/maez_daemon.py   # post-audit reply (~6882)
awk 'NR>=6619 && NR<=6882 && /reply *=|_CITE_RE/' daemon/maez_daemon.py   # confirm no citation-strip on reply in range
grep -n 'local_label' core/routing/focused_cognition.py | head   # EvidenceItem.local_label
```
Expected: `_focused_working_set` (with `.items`, each `EvidenceItem` carrying `local_label` + text) and the post-audit `reply` are both in `handle_message` scope; the only `reply` mutations between focused-assign and audit are `strip_tool_call_leaks` + a pursuit append (no `[E#]` strip). Record the line numbers.

**Runtime confirmation (instrument, no behavior change):** add a *temporary* `logger.info` at the post-audit point that logs `len(_label_text_map)` and `bool(_CITE_RE.search(reply))` and `_focused_used`, behind a throwaway env flag; run/observe ONE real focused web turn (owner may need to drive it — if no live turn is available this session, mark 0b as "source-proven, runtime-pending" and the handoff notes it). Then REMOVE the temporary log before committing Task 0 (docs/proof only).

- [ ] **Step 3: Write the proof doc + commit**

Record 0a (service response or load-failure) and 0b (the two reachable moments + `[E#]` retention + the label-map non-emptiness, source-proven and/or runtime). State **SEAM ASSUMPTIONS HELD: YES/NO**.
```bash
git add docs/proof/2026-06-16-thread-a-task0.md
git commit -m "$(cat <<'EOF'
docs(proof): Task-0 feasibility for claim-entailment support rail

0a: MiniCheck /support artifact answers {"verdict","score"} (or load-failure noted).
0b: focused-seam capture + post-audit reply both reachable in handle_message; reply
retains [E#]; label->text map non-empty on a web turn. No behavior change.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

## Task 1: Fix the enqueue queue-full I/O defect (+ regression)

**Files:** Modify `core/cognition/grounding_shadow.py:220-236`. Test: `tests/test_grounding_shadow.py`.

The defect: `enqueue()` calls `self._emit(...)` (a file write) inside `except queue.Full` — I/O on the enqueue path under overload.

- [ ] **Step 1: Write the failing regression test**

Append to `tests/test_grounding_shadow.py` (create if absent, with `import unittest`):
```python
class EnqueueQueueFullIsIOFreeTest(unittest.TestCase):
    def test_queue_full_does_not_emit(self):
        from core.cognition.grounding_shadow import GroundingShadow
        from core.cognition.support_verifier import FakeSupportVerifier
        shadow = GroundingShadow(FakeSupportVerifier([]), "/nonexistent/should_never_be_written.jsonl", maxsize=1)
        emitted = []
        shadow._emit = lambda rec: emitted.append(rec)   # spy: _emit must NOT be called on full
        shadow._q.put_nowait({"a": 1})                    # fill the queue (maxsize=1)
        result = shadow.enqueue({"shadow_id": "x", "ts": 0})  # this must hit queue.Full
        self.assertEqual(result, "shadow_enqueue_failed")
        self.assertEqual(emitted, [])                     # NO telemetry write on full
        self.assertEqual(shadow.dropped_count, 1)         # memory-only counter bumped instead
```

- [ ] **Step 2: Run → RED**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_grounding_shadow.EnqueueQueueFullIsIOFreeTest -v`
Expected: FAIL — `_emit` is called (emitted != []) / no `dropped_count` attribute.

- [ ] **Step 3: Implement the I/O-free queue-full path**

In `grounding_shadow.py`, add `self.dropped_count = 0` to `__init__` (after `self._stop`), and rewrite `enqueue`:
```python
    def enqueue(self, job: dict) -> str:
        try:
            self._q.put_nowait(job)
            return "enqueued"
        except queue.Full:
            self.dropped_count += 1   # memory-only; worker may flush this, never inline I/O
            return "shadow_enqueue_failed"
        except Exception:
            return "shadow_enqueue_failed"
```
(The worker `_run`/`_process` may optionally emit a periodic `dropped_count` summary, but the enqueue path writes nothing.)

- [ ] **Step 4: Run → GREEN + regression**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_grounding_shadow 2>&1 | tail -4`
Then: `ls tests/ | grep -i grounding` and run any existing grounding_shadow test module. Expected: OK.
ruff: `/home/rohit/maez/.venv/bin/ruff check core/cognition/grounding_shadow.py tests/test_grounding_shadow.py | tail -2`

- [ ] **Step 5: Commit**

```bash
git add core/cognition/grounding_shadow.py tests/test_grounding_shadow.py
git commit -m "$(cat <<'EOF'
fix(grounding-shadow): queue-full path is memory-only (no inline telemetry write)

GroundingShadow.enqueue() wrote telemetry via _emit() on queue.Full — I/O on the
enqueue path under overload. Now bumps an in-memory dropped_count and returns;
the worker owns any flush. Full-queue regression test asserts no _emit on full.

## Predicted effect

No behavior change in normal operation; under shadow-queue overload, enqueue no
longer performs a synchronous file write. Telemetry content unchanged.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Cited-only mapping — rewrite `compute_shadow` (the honest-mapping law)

**Files:** Modify `core/cognition/grounding_shadow.py` (`compute_shadow` + helpers; add `name` read for verifier). Test: `tests/test_grounding_shadow.py`.

`compute_shadow` changes signature from `(final_text, claimable_items, verifier, ...)` to `(final_text, evidence_map, verifier, ...)` where `evidence_map` is `{local_label: text}`. Per post-audit sentence: extract `[E#]`, resolve against the map, classify by mode, run MiniCheck on **only** cited texts.

- [ ] **Step 1: Write the failing tests**

```python
class CitedOnlyMappingTest(unittest.TestCase):
    def _compute(self, reply, evidence_map, verifier):
        from core.cognition.grounding_shadow import compute_shadow
        return compute_shadow(reply, evidence_map, verifier, per_sentence_timeout_s=0.25, per_job_budget_s=5.0)

    def test_no_citation_abstains_never_supported(self):
        from core.cognition.support_verifier import FakeSupportVerifier
        # verifier would say SUPPORTED, but an uncited sentence must NOT be blessed
        v = FakeSupportVerifier(["SUPPORTED"])
        out = self._compute("Anthropic launched Mythos 5.", {"E1": "Anthropic released Opus."}, v)
        s = out["sentences"][0]
        self.assertEqual(s["mode"], "no_citation")
        self.assertEqual(s["verdict"], "ABSTAIN")
        self.assertEqual(v.calls, 0)   # model NOT called on the floor case

    def test_cited_support_routes_only_cited_evidence(self):
        from core.cognition.support_verifier import FakeSupportVerifier
        v = FakeSupportVerifier(["UNSUPPORTED"])
        out = self._compute("Anthropic launched Mythos 5 [E1].",
                            {"E1": "Anthropic released Opus 4.5.", "E2": "Unrelated."}, v)
        s = out["sentences"][0]
        self.assertEqual(s["mode"], "cited_support")
        self.assertEqual(s["verdict"], "UNSUPPORTED")
        self.assertEqual(s["cited_evidence_ids"], ["E1"])
        self.assertEqual(v.last_evidence, "Anthropic released Opus 4.5.")  # ONLY E1, not E2

    def test_unmatched_citation_is_deterministic_unsupported(self):
        from core.cognition.support_verifier import FakeSupportVerifier
        v = FakeSupportVerifier(["SUPPORTED"])
        out = self._compute("Claim [E9].", {"E1": "x"}, v)   # E9 not in map
        s = out["sentences"][0]
        self.assertEqual(s["mode"], "unmatched_citation")
        self.assertEqual(s["verdict"], "UNSUPPORTED")
        self.assertEqual(v.calls, 0)

    def test_empty_evidence_abstains(self):
        from core.cognition.support_verifier import FakeSupportVerifier
        v = FakeSupportVerifier(["SUPPORTED"])
        out = self._compute("Claim [E1].", {"E1": "   "}, v)  # cited but empty text
        s = out["sentences"][0]
        self.assertEqual(s["mode"], "empty_evidence")
        self.assertEqual(s["verdict"], "ABSTAIN")
        self.assertEqual(v.calls, 0)
```
**`FakeSupportVerifier` needs `calls`, `last_evidence`, and a `name`.** If the existing fake lacks them, extend it in Task 2 Step 3 (it's a test double).

- [ ] **Step 2: Run → RED**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_grounding_shadow.CitedOnlyMappingTest -v`
Expected: FAIL — `compute_shadow` signature/behavior is the old all-evidence one; no `mode`.

- [ ] **Step 3: Implement cited-only `compute_shadow`**

Add the citation regex + a per-sentence classifier near the top of `grounding_shadow.py`:
```python
_CITE_RE = re.compile(r"\[E(\d+)\]")


def _cited_labels(sentence: str) -> list[str]:
    return [f"E{m.group(1)}" for m in _CITE_RE.finditer(sentence)]


def _verifier_name(verifier) -> str:
    return getattr(verifier, "name", None) or verifier.__class__.__name__


def classify_sentence(sentence, evidence_map, verifier, timeout_s) -> dict:
    labels = _cited_labels(sentence)
    base = {"sentence": sentence, "cited_evidence_ids": labels}
    if not labels:
        return {**base, "mode": "no_citation", "verdict": "ABSTAIN",
                "verifier": "deterministic", "score": None, "latency_s": 0.0}
    if any(lab not in evidence_map for lab in labels):
        return {**base, "mode": "unmatched_citation", "verdict": UNSUPPORTED,
                "verifier": "deterministic", "score": None, "latency_s": 0.0}
    texts = [(evidence_map[lab] or "").strip() for lab in labels]
    combined = "\n".join(t for t in texts if t)
    if not combined:
        return {**base, "mode": "empty_evidence", "verdict": "ABSTAIN",
                "verifier": "deterministic", "score": None, "latency_s": 0.0}
    try:
        label, score, latency = verifier.support(combined, sentence, timeout_s)
    except Exception:
        label, score, latency = UNAVAILABLE, None, 0.0
    if label == UNAVAILABLE:
        return {**base, "mode": "verifier_unavailable", "verdict": UNAVAILABLE,
                "verifier": _verifier_name(verifier), "score": score, "latency_s": latency}
    return {**base, "mode": "cited_support", "verdict": label,
            "verifier": _verifier_name(verifier), "score": score, "latency_s": latency}
```
**Coupling (keep the module coherent):** changing `compute_shadow`'s signature breaks its in-module
caller `_process` and any existing `test_grounding_shadow` tests using the old
`compute_shadow(final_text, claimable_items)` shape. In THIS task also: (a) update `_process` to read
`job.get("evidence_map") or {}` (tolerate both old/new jobs until Task 4 replaces the job source);
(b) update/replace existing tests that use the old signature. The Step-4 full-module regression run
**must stay green** — do not leave the module internally inconsistent between tasks.

Then rewrite `compute_shadow` to take `evidence_map` and call `classify_sentence` per sentence (keep the `per_job_budget_s` budget-stop and the `no_sentences` floor; replace the old `claimable_evidence`/all-evidence path):
```python
def compute_shadow(final_text, evidence_map, verifier, *,
                   per_sentence_timeout_s: float = 0.25, per_job_budget_s: float = 1.5) -> dict:
    if not evidence_map:
        return {"status": "no_evidence", "sentences": [], "shadowed_count": 0, "remaining_count": 0}
    sentences = split_sentences(final_text)
    if not sentences:
        return {"status": "no_sentences", "sentences": [], "shadowed_count": 0, "remaining_count": 0}
    started = time.monotonic()
    results, shadowed, status = [], 0, "ok"
    for idx, sentence in enumerate(sentences):
        if time.monotonic() - started >= per_job_budget_s:
            return {"status": "budget_exceeded", "sentences": results,
                    "shadowed_count": shadowed, "remaining_count": len(sentences) - idx}
        rec = classify_sentence(sentence, evidence_map, verifier, per_sentence_timeout_s)
        if rec["verdict"] == UNAVAILABLE:
            status = "verifier_unavailable"
        results.append(rec)
        shadowed += 1
    return {"status": status, "sentences": results, "shadowed_count": shadowed, "remaining_count": 0}
```
Extend `FakeSupportVerifier` (in `support_verifier.py`) with `calls`/`last_evidence`/`name` if missing:
```python
    name = "fake"
    def support(self, evidence, claim, timeout_s=None):
        self.calls = getattr(self, "calls", 0) + 1
        self.last_evidence = evidence
        # ... existing scripted-verdict logic ...
```

- [ ] **Step 4: Run → GREEN**

Run: `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_grounding_shadow.CitedOnlyMappingTest -v` → 4 PASS.

- [ ] **Step 5: Commit**

```bash
git add core/cognition/grounding_shadow.py core/cognition/support_verifier.py tests/test_grounding_shadow.py
git commit -m "$(cat <<'EOF'
feat(grounding-shadow): cited-only entailment mapping (honest-mapping law)

compute_shadow now takes a {local_label->text} evidence map; per sentence it
extracts [E#], and classifies by mode: no_citation->ABSTAIN (never blessed),
unmatched_citation->UNSUPPORTED (deterministic), empty_evidence->ABSTAIN,
cited_support-> MiniCheck on ONLY the cited evidence, verifier_unavailable->
UNAVAILABLE. An uncited sentence is never blessed by the whole pile.

## Predicted effect

Pure logic (no live wiring yet); the rail now checks each cited sentence against
only its cited evidence. No reply is changed.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Claim-level receipt + `post_audit` header

**Files:** Modify `core/cognition/grounding_shadow.py` (`build_telemetry`). Test: `tests/test_grounding_shadow.py`.

- [ ] **Step 1: Write the failing test**

```python
class ClaimLevelReceiptTest(unittest.TestCase):
    def test_receipt_has_required_claim_fields_and_post_audit(self):
        from core.cognition.grounding_shadow import build_telemetry, compute_shadow
        from core.cognition.support_verifier import FakeSupportVerifier
        compute = compute_shadow("Anthropic launched Mythos 5 [E1].",
                                 {"E1": "Anthropic released Opus 4.5."},
                                 FakeSupportVerifier(["UNSUPPORTED"]), per_job_budget_s=5.0)
        rec = build_telemetry("sid", 0, "telegram_surface", "boot", {"mode": "noop"},
                              compute, post_audit=True, debug=False)
        self.assertTrue(rec["post_audit"])
        s0 = rec["sentences"][0]
        for field in ("claim_hash", "cited_evidence_ids", "support_verdict", "mode", "verifier", "score", "latency_ms"):
            self.assertIn(field, s0)
        self.assertEqual(s0["mode"], "cited_support")
        self.assertEqual(s0["cited_evidence_ids"], ["E1"])
        self.assertNotIn("snippet", s0)   # content-light by default
```
Note `build_telemetry`'s signature changes: drop `claimable_items`/`boot_id` positional drift — pass `post_audit`. Adapt the test to the final signature you implement (keep the assertions).

- [ ] **Step 2: Run → RED.** `compute`-shaped records lack `claim_hash`/`mode`/`verifier`; no `post_audit`.

- [ ] **Step 3: Implement** — in `build_telemetry`, build per-sentence records from the new `classify_sentence` output and add `post_audit`:
```python
    for result in compute_result.get("sentences", []):
        sentence = result.get("sentence") or ""
        rec = {
            "claim_hash": _hash(sentence),
            "cited_evidence_ids": result.get("cited_evidence_ids", []),
            "support_verdict": result.get("verdict"),
            "mode": result.get("mode"),
            "verifier": result.get("verifier"),
            "score": result.get("score"),
            "latency_ms": round((result.get("latency_s") or 0.0) * 1000, 1),
        }
        if debug:
            rec["snippet"] = sentence[:120]
        sentences.append(rec)
```
And add `post_audit` to the returned header dict + the `build_telemetry(..., post_audit: bool = False, debug=False)` signature. Keep the existing header counts (`unsupported_count`/`supported_count` etc., now keyed off `support_verdict`).

- [ ] **Step 4: Run → GREEN + full module.** `/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_grounding_shadow 2>&1 | tail -4`. ruff clean.

- [ ] **Step 5: Commit** (`feat(grounding-shadow): claim-level receipt + post_audit header`; `## Predicted effect`: receipt now records claim/cited_evidence_ids/mode/verifier per the invariant; telemetry shape change only).

---

## Task 4: Re-home the hook — capture at focused seam, enqueue post-audit

**Files:** Modify `core/cognition/grounding_shadow.py` (new `observe_focused_support`), `daemon/maez_daemon.py` (capture + enqueue), `core/safety/audited_output.py` (supersede old hook). Test: `tests/test_grounding_shadow.py`.

- [ ] **Step 1: Write the failing test for the new hook**

```python
class ObserveFocusedSupportTest(unittest.TestCase):
    def test_enqueues_post_audit_reply_and_map(self):
        import core.cognition.grounding_shadow as gs
        from core.cognition.support_verifier import FakeSupportVerifier
        captured = {}
        class _Spy(gs.GroundingShadow):
            def enqueue(self, job):
                captured.update(job); return "enqueued"
        gs.set_shadow_singleton(_Spy(FakeSupportVerifier([]), "/tmp/x.jsonl"))
        with mock_env({"MAEZ_GROUNDING_SHADOW_ENABLED": "1"}):
            gs.observe_focused_support("Served reply [E1].", {"E1": "evidence"},
                                       surface="telegram_surface", boot_id="b", shadow_id="s", ts=0)
        gs.reset_shadow_singleton()
        self.assertEqual(captured["final_text"], "Served reply [E1].")
        self.assertEqual(captured["evidence_map"], {"E1": "evidence"})
        self.assertTrue(captured["post_audit"])
```
(Use `unittest.mock.patch.dict("os.environ", ...)` for `mock_env`.)

- [ ] **Step 2: Run → RED** (`observe_focused_support` undefined).

- [ ] **Step 3: Implement** `observe_focused_support` in `grounding_shadow.py` (parallel to `shadow_observe`, new payload), and update `_process`/`compute_shadow` call to read `job["evidence_map"]`:
```python
def observe_focused_support(reply, evidence_map, *, surface, boot_id, shadow_id, ts) -> str:
    """Non-blocking focused-path observation of the POST-AUDIT served reply."""
    try:
        shadow = _get_shadow()
        if shadow is None:
            return "disabled"
        return shadow.enqueue({
            "final_text": reply or "",
            "evidence_map": evidence_map or {},
            "surface": surface, "boot_id": boot_id,
            "shadow_id": shadow_id, "ts": ts, "post_audit": True,
        })
    except Exception:
        return "disabled"
```
In `_process`, pass `job["evidence_map"]` to `compute_shadow` and `job.get("post_audit", False)` to `build_telemetry`.

- [ ] **Step 4: Wire the daemon (the two-moment seam)**

In `daemon/maez_daemon.py`, at the focused seam (near the `check_groundedness` call ~6590), capture the map (read `_focused_working_set.items`, build `{local_label: text}`):
```python
        _label_text_map = {}
        try:
            for _it in getattr(_focused_working_set, "items", ()) or ():
                _lbl = getattr(_it, "local_label", None)
                _txt = getattr(_it, "text", None)
                if _lbl and _txt:
                    _label_text_map[_lbl] = _txt
        except Exception:
            _label_text_map = {}
```
Then, immediately after `reply = audit_assistant_text(...)` returns (~6882), enqueue the post-audit reply:
```python
        try:
            if _focused_used and _label_text_map:
                from core.cognition.grounding_shadow import observe_focused_support
                observe_focused_support(
                    reply, _label_text_map,
                    surface=source, boot_id=os.environ.get("MAEZ_BOOT_ID"),
                    shadow_id=uuid.uuid4().hex, ts=int(time.time()),
                )
        except Exception:
            pass
```
**Supersede the audit-path hook:** in `core/safety/audited_output.py`, remove the `_observe_grounding_shadow(result, evidence_envelope, ...)` call at `:253` (it only ever fed empty `claimable`). Leave a one-line comment pointing to the focused-path hook.

- [ ] **Step 5: Run + regression**

`/home/rohit/maez/.venv/bin/python -B -m unittest tests.test_grounding_shadow 2>&1 | tail -4` → OK.
Confirm the daemon imports cleanly: `/home/rohit/maez/.venv/bin/python -B -c "import daemon.maez_daemon"`.
Run the audited-output tests (the hook removal must not break them): `ls tests/ | grep -iE "audited_output|audit"` then run the named module(s). ruff on all touched files.

- [ ] **Step 6: Commit** (`feat(daemon): re-home grounding shadow to the focused seam (post-audit served reply)`; `## Predicted effect`: with the flag ON, a focused web turn enqueues the served reply + cited-evidence map to the shadow; flag OFF or non-focused turns enqueue nothing; reply never changed; the empty-claimable audit-path hook is removed).

---

## Task 5: Optional uncited diagnostic + flag-off byte-identical sweep

**Files:** `core/cognition/grounding_shadow.py`, `tests/test_grounding_shadow.py`.

- [ ] **Step 1: Tests** — (a) flag-off: `observe_focused_support` with `MAEZ_GROUNDING_SHADOW_ENABLED` unset enqueues nothing (returns "disabled", no telemetry); (b) optional `uncited_all_evidence_diagnostic`: when enabled (its own sub-flag `MAEZ_GROUNDING_SHADOW_DIAGNOSTIC`), an uncited sentence ALSO gets a diagnostic record with a would-be label, but the sentence's `support_verdict` stays `ABSTAIN`/`no_citation` (the diagnostic NEVER counts as grounded). Assert both.
- [ ] **Step 2: RED → implement** the sub-flag-gated diagnostic in `classify_sentence` (when no citation AND diagnostic enabled, additionally run the verifier vs all `evidence_map` values, recording `mode=uncited_all_evidence_diagnostic` as a SEPARATE record; the primary `no_citation` record is unchanged). Default off.
- [ ] **Step 3: GREEN + commit** (`feat(grounding-shadow): flag-off byte-identical + optional uncited diagnostic`; `## Predicted effect`: flag off = no enqueue/telemetry; diagnostic sub-flag adds a never-grounded learning record).

---

## Task 6: Corpus extension — Anthropic/Mythos class

**Files:** `scripts/grounding_bench/corpus.json`. (Optional re-run of `bench_grounding.py` is owner/infra — needs the model.)

- [ ] **Step 1:** Append items to `corpus.json`'s `items[]` covering the witnessed class (keep the existing `mode`/`evidence_kind`/`expected` schema):
```json
{ "id": "ffs-anthropic-1", "mode": "fabricated_false_specific", "source": "synthetic", "evidence_kind": "claimable_present",
  "evidence": "Anthropic released Claude Opus 4.5 in late 2025.",
  "claim": "Anthropic launched a Claude Corps initiative and a Mythos 5 model.",
  "expected": "UNSUPPORTED", "strict_rule": false,
  "rationale": "Neither Claude Corps nor Mythos 5 appears in the evidence; fabricated specifics about a real entity." },
{ "id": "cbu-anthropic-1", "mode": "cited_but_unsupported", "source": "synthetic", "evidence_kind": "claimable_present",
  "evidence": "Anthropic published a research note on interpretability.",
  "claim": "The US government suspended foreign access to Anthropic's Fable 5 and Mythos 5 models.",
  "expected": "UNSUPPORTED", "strict_rule": false,
  "rationale": "Export-control suspension and the named models are not in the cited evidence." }
```
- [ ] **Step 2:** Validate JSON: `/home/rohit/maez/.venv/bin/python -B -c "import json; json.load(open('scripts/grounding_bench/corpus.json'))"` → no error. (Re-running the scorecard needs the MiniCheck model — owner/infra; note in the handoff if deferred.)
- [ ] **Step 3: Commit** (`test(grounding-bench): add Anthropic/Mythos fabrication corpus items`; not a behavior commit — no `## Predicted effect` needed).

---

## Task 7: STOP-at-gate handoff

**Files:** Create `docs/handoffs/2026-06-16-claim-entailment-support-rail-gate.md`.

- [ ] **Step 1: Write the handoff** — branch + commits + green suites (paste output); Codex cross-lane ask (honesty/memory core) with anchors: cited-only law (no_citation never blessed; cited_support routes only cited evidence; unmatched→UNSUPPORTED), post_audit (judges served reply), queue-full I/O-free, off=byte-identical. **Owner breath:** install `scripts/maez-minicheck-verifier.template.service` as a `:8083` unit + start it; add `MAEZ_GROUNDING_SHADOW_ENABLED=1` to model.env; restart. **Forward-only witness:** on a real focused web turn, `grep grounding_shadow.jsonl` for a row with `post_audit:true` and ≥1 `mode:cited_support` / `support_verdict:UNSUPPORTED` on a fabricated cited sentence (the Mythos-5 class). **No service → no verifier witness** (deterministic floor still witnessable). **v0 is SHADOW — it measures, does not protect a reply.**
- [ ] **Step 2: Commit + STOP.** No service install, no flag flip, no restart, no model.env edit — owner-sovereign. Surface branch tip + green suites + the witness recipe and wait.

---

## Notes for the implementer

- **Runner:** `/home/rohit/maez/.venv/bin/python -B -m unittest <module>` — NEVER `discover`.
- **Read the real functions** (`compute_shadow`, `build_telemetry`, `GroundingShadow`, `shadow_observe`, `FakeSupportVerifier`) before editing — signatures here match the code at plan time but confirm.
- **The post-audit seam is load-bearing:** capture the map at ~6590, enqueue at ~6882 with the *served* `reply`. Do NOT enqueue the focused draft.
- **Module coherence across Tasks 2–4 (important):** `compute_shadow`, `build_telemetry`, `_process`,
  and the hook all live in `grounding_shadow.py` and share the job/record shape. When a task changes
  a signature, update its in-module caller (`_process`) and any existing tests **in that same task**
  so the full `tests.test_grounding_shadow` regression stays green. If TDD forces two of them
  together, land them together — never leave the module internally inconsistent between tasks.
- **No push. STOP at the gate.** v0 is shadow-only — never claim it protects a reply.
