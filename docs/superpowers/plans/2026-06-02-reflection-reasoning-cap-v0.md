# Reflection Reasoning Cap v0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Disable Qwen 3.6's chain-of-thought for the reflection synthesis call only, so the JSON emits reliably (`finish_reason=stop`) in ~9s instead of truncating at 8192 tokens — by adding one request-body field, with nothing else in the request (body *or* envelope) allowed to drift.

**Architecture:** Add `chat_template_kwargs={"enable_thinking": False}` to the JSON body built in `_default_llm_call` (the reflection-only caller). One failing test captures the outgoing `urllib.request.Request.data` and the `urlopen(..., timeout=...)` call to assert the new field is present and **no other body field or the envelope timeout drifted**. The Token Budget v0 terminal-state guards stay untouched (live defense-in-depth).

**Tech Stack:** Python, `unittest` (`.venv/bin/python -m unittest`, **NOT pytest**), `unittest.mock`, existing `urllib.request` llama-server call.

**Spec:** `docs/superpowers/specs/2026-06-02-reflection-reasoning-cap-v0-design.md`

**Lane:** Codex implements, Claude cross-verifies (special attention: only `chat_template_kwargs` added; model/tokens/temperature/prompt/timeout unchanged; terminal-state tests stay green).

---

## Task 1: Cap reasoning on the reflection call (TDD)

**Files:**
- Modify: `scripts/memory_reflection/nightly_lived_memory.py` (`_default_llm_call`)
- Test: `tests/test_nightly_lived_memory.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_nightly_lived_memory.py` (alongside the existing `ReflectionSynthesisTerminalMetadataTests`, same `import json` / `from unittest import mock` already used there):

```python
class ReflectionReasoningCapTests(unittest.TestCase):
    def test_default_llm_call_disables_thinking_without_other_payload_drift(self):
        from scripts.memory_reflection import nightly_lived_memory as nlm

        class _Resp:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self):
                return json.dumps(
                    {"choices": [{"finish_reason": "stop", "message": {"content": "[]"}}]}
                ).encode("utf-8")

        with mock.patch("urllib.request.urlopen", return_value=_Resp()) as urlopen:
            llm_call = nlm._default_llm_call("qwen36-27b", 240)
            llm_call("PROMPT-TEXT")

        # Envelope: the timeout is the urlopen kwarg, NOT a body field.
        self.assertEqual(urlopen.call_args.kwargs.get("timeout"), 240)

        # Body: capture the outgoing Request payload.
        request = urlopen.call_args.args[0]
        body = json.loads(request.data.decode("utf-8"))

        # The one functional change.
        self.assertEqual(body["chat_template_kwargs"], {"enable_thinking": False})

        # Exact body key-set — nothing added or removed beyond chat_template_kwargs.
        self.assertEqual(
            set(body.keys()),
            {"model", "messages", "max_tokens", "temperature", "chat_template_kwargs"},
        )

        # No other body field drifted.
        self.assertEqual(body["model"], "qwen36-27b")
        self.assertEqual(body["max_tokens"], 8192)
        self.assertEqual(body["temperature"], 0.4)
        self.assertEqual(body["messages"], [{"role": "user", "content": "PROMPT-TEXT"}])
```

- [ ] **Step 2: Run the test to verify it FAILS**

Run: `.venv/bin/python -m unittest tests.test_nightly_lived_memory.ReflectionReasoningCapTests -v`
Expected: **FAIL** — the current body has no `chat_template_kwargs` key, so `body["chat_template_kwargs"]` raises `KeyError` and the key-set assertion would also fail.

- [ ] **Step 3: Implement the one body-field addition**

In `scripts/memory_reflection/nightly_lived_memory.py`, inside `_default_llm_call`'s `_call`, add the `chat_template_kwargs` line to the request body dict. The body becomes exactly:

```python
        body = _json.dumps({
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": _REFLECTION_SYNTHESIS_MAX_TOKENS,
            "temperature": 0.4,
            # Reflection synthesis is structured extraction with citations, not
            # deliberation. Qwen 3.6's chain-of-thought can exceed max_tokens and
            # truncate before the JSON; disabling thinking for THIS call (the
            # template injects an empty <think></think>) makes it emit directly,
            # ~9s and well under the cap. Token Budget v0 guards stay as
            # defense-in-depth in case reasoning ever returns.
            "chat_template_kwargs": {"enable_thinking": False},
        }).encode("utf-8")
```

Do **not** change `max_tokens`, `temperature`, the `model`/`messages` shape, the `timeout_s` used in `urllib.request.urlopen(req, timeout=timeout_s)`, the terminal-reason stashing, or anything else.

- [ ] **Step 4: Run the test to verify it PASSES**

Run: `.venv/bin/python -m unittest tests.test_nightly_lived_memory.ReflectionReasoningCapTests -v`
Expected: **PASS** — `chat_template_kwargs` present and valued; key-set exact; model/tokens/temperature/prompt unchanged; `urlopen` called with `timeout=240`.

- [ ] **Step 5: Confirm scope — only the body dict changed**

Run: `git diff scripts/memory_reflection/nightly_lived_memory.py`
Expected: the only functional change is the added `chat_template_kwargs` line (plus its comment) in `_default_llm_call`'s body. `_REFLECTION_SYNTHESIS_MAX_TOKENS` (8192), the timeout argument, the terminal-reason stash, `synthesize_reflections`, `_parse_reflections`, the prompt, and the CLI `--synthesis-timeout` default (240) are all unchanged. No edits to `daemon/maez_daemon.py`, the prompt in `core/memory/reflection.py`, or any flag.

- [ ] **Step 6: Commit**

```bash
git add scripts/memory_reflection/nightly_lived_memory.py tests/test_nightly_lived_memory.py
git commit -m "feat(reflection): cap reasoning on synthesis call (enable_thinking=false)

Qwen 3.6's chain-of-thought exceeded even 8192 max_tokens (~50% truncation);
budget-raising was the wrong lever. Disable thinking for the reflection
synthesis call only via chat_template_kwargs={enable_thinking: false} — the
template injects an empty think-block so the model emits the JSON directly.
Probe: 2/2 finish_reason=stop, ~9s, ~340 tokens, 3 grounded in-voice
candidates, zero reflection citations. Reflection-only caller; no model/
prompt/token/temperature/timeout change. Token Budget v0 invalid-witness
guards stay as defense-in-depth. Test asserts no other body field or the
envelope timeout drifts."
```

---

## Task 2: Regression + owner re-run witness

**Files:**
- Modify: `docs/slices/sleep-consolidation/acceptance.md`

- [ ] **Step 1: Run the reflection/nightly targeted suites**

Run:

```bash
.venv/bin/python -m unittest \
  tests.test_nightly_lived_memory \
  tests.test_reflection_synthesis \
  tests.test_reflection_input_hygiene \
  tests.test_reflection_dry_run_wiring \
  tests.test_consolidation_telemetry \
  -v
```

Expected: all PASS — the new cap test passes and every Token Budget v0 terminal-state test (stop/length/llm_timeout, derived properties, invalid-witness mapping, channel wall) stays green. The added field does not alter terminal-state handling.

- [ ] **Step 2: Floor both directions (NOT git stash)**

Run: `.venv/bin/python -m unittest discover -s tests 2>&1 | grep -E "^(Ran|FAILED|OK)"`
Expected: within ±2 of the `main` base (ambient order-pollution wobble); no new deterministic reflection failure; name any branch-only header rather than absorbing it.

- [ ] **Step 3: Append the witness gate**

Append to `docs/slices/sleep-consolidation/acceptance.md`:

```markdown
## Reflection Reasoning Cap v0 — re-run witness (owner-run)

Re-run the dry-run from `main`: `MAEZ_REFLECTION_SYNTHESIS_ENABLED=1`, write off.

- **2 stable runs, both `finish_reason="stop"` / `valid_witness=true`** — no `length`,
  `llm_timeout`, or `llm_error`. (Probe already showed 2/2; this re-confirms on the
  merged wired path.)
- **1-3 candidates**, each grounded; resolving `source_memory_ids` yields zero
  `source_kind="reflection"`.
- **In-voice** — Maez noticing its own formation, not a report.
- **Fast** — single-digit seconds; completion_tokens well under the 8192 cap (a
  regression here signals reasoning crept back).

Both axes stable across both runs -> the `MAEZ_REFLECTION_SYNTHESIS_WRITE=1` decision
reopens (honestly, not automatically).
```

- [ ] **Step 4: Commit**

```bash
git add docs/slices/sleep-consolidation/acceptance.md
git commit -m "docs(reflection): reasoning-cap re-run witness gate"
```

---

## Self-Review

- **Spec coverage:** §2 one body field → Task 1 Step 3; §4 positive assertion → Task 1 Step 1 (`chat_template_kwargs == {"enable_thinking": False}`); §4 negative-body → exact key-set + field values; §4 negative-envelope → `urlopen.call_args.kwargs["timeout"] == 240`; §3 guards stay → Task 2 Step 1 (terminal-state tests green) + Task 1 Step 5 (no edits to terminal-reason/guards); §5 acceptance → Task 2 Step 3.
- **Placeholder scan:** none — full test and the exact body dict are concrete.
- **Type consistency:** `_default_llm_call(model, timeout_s)` returns the `_call` callable; body uses `_REFLECTION_SYNTHESIS_MAX_TOKENS` (8192) and `temperature` 0.4 (verified against the merged `e904af1` code); `urlopen(req, timeout=timeout_s)` keeps `req` positional, `timeout` keyword — so `call_args.args[0]` is the Request and `call_args.kwargs["timeout"]` is 240.
- **One risk:** if a future edit passes `timeout` positionally instead of as a kwarg, the envelope assertion's `call_args.kwargs["timeout"]` would miss it — acceptable for v0 since the current code uses the kwarg form, and a positional move would itself be a payload-shape change the reviewer would catch.
