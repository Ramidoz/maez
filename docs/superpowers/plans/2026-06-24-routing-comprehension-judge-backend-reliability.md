# Routing Comprehension Judge Backend Reliability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the routing-comprehension judge parse reliably on the real daemon path by routing its direct call to the configured primary OpenAI-compatible endpoint and logging content-light parse diagnostics.

**Architecture:** The current judge logic stays the same: same 4-way comprehension contract, same no-keyword guard, same fail-open posture when unavailable. The fix is below the judgment layer: `chat_direct()` becomes the deterministic direct-classifier path to `MAEZ_PRIMARY_BASE_URL`, carries finish/backend/thinking metadata, and `routing_comprehension` includes that metadata in content-light receipts. `ENABLED` still waits for a clean live shadow witness.

**Tech Stack:** Python stdlib, `unittest`, existing `core.routing.llm_client`, existing OpenAI-compatible llama.cpp endpoint, existing `core.routing.routing_comprehension` receipts.

---

## Task 0: Backend Proof Gate

**Files:**
- Create: `docs/proofs/2026-06-24-routing-comprehension-backend-proof.md`

- [ ] **Step 1: Re-run the live daemon backend proof**

Run:

```bash
cd /home/rohit/maez
pid=$(systemctl --user show -p MainPID --value maez.service)
tr '\0' '\n' < "/proc/$pid/environ" \
  | grep -E '^(MAEZ_LLM_BACKEND|MAEZ_LLAMACPP_URL|MAEZ_PRIMARY_BASE_URL|MAEZ_PRIMARY_MODEL|MAEZ_PRIMARY_CHAT_KWARGS|MAEZ_ROUTING_COMPREHENSION)'
```

Expected on the current failure shape:

```text
MAEZ_PRIMARY_MODEL=qwen36-27b
MAEZ_PRIMARY_BASE_URL=http://127.0.0.1:8080
MAEZ_PRIMARY_CHAT_KWARGS={"enable_thinking": false}
MAEZ_ROUTING_COMPREHENSION_SHADOW=1
```

`MAEZ_LLM_BACKEND` is absent, so `core.routing.llm_client.active_backend()` defaults to `ollama`. That means the judge's current `chat_direct()` path does not use the proven `:8080` OpenAI-compatible endpoint even though `MAEZ_PRIMARY_BASE_URL` points there.

- [ ] **Step 2: Confirm the current code path**

Run:

```bash
cd /home/rohit/maez
sed -n '150,175p' core/routing/routing_comprehension.py
sed -n '473,684p' core/routing/llm_client.py
```

Expected facts:

```text
LlmEligibilityJudge.decide calls chat_direct(... think=False, chat_template_kwargs={"enable_thinking": False}).
chat_direct() chooses active_backend().
active_backend() defaults to "ollama" when MAEZ_LLM_BACKEND is unset.
_ollama_options() strips chat_template_kwargs before calling ollama.chat().
_chat_llamacpp() preserves chat_template_kwargs in extra_body.
```

- [ ] **Step 3: Write the proof note**

Create `docs/proofs/2026-06-24-routing-comprehension-backend-proof.md` with:

```markdown
# Routing Comprehension Backend Proof

Date: 2026-06-24

## Live daemon environment

The running daemon has:

- `MAEZ_PRIMARY_MODEL=qwen36-27b`
- `MAEZ_PRIMARY_BASE_URL=http://127.0.0.1:8080`
- `MAEZ_PRIMARY_CHAT_KWARGS={"enable_thinking": false}`
- `MAEZ_ROUTING_COMPREHENSION_SHADOW=1`
- no `MAEZ_LLM_BACKEND`

## Current failure path

`LlmEligibilityJudge` calls `llm_client.chat_direct()`. With no
`MAEZ_LLM_BACKEND`, `chat_direct()` defaults to the Ollama backend.
That path strips `chat_template_kwargs`, so the judge is not guaranteed
to get the same `enable_thinking=false` behavior that the raw `:8080`
OpenAI-compatible probe proved clean.

## Chosen fix

`chat_direct()` is only used by the routing-comprehension judge today.
Make it the deterministic direct-classifier path to the configured
primary OpenAI-compatible endpoint (`MAEZ_PRIMARY_BASE_URL` /
`PRIMARY_BASE_URL`), preserving `chat_template_kwargs`, `think=False`,
and non-streaming finish metadata. Normal owner replies continue to use
`chat()` and the gateway.

## Stop condition

If a future rerun shows `chat_direct()` has additional production
callers, or the daemon no longer has an OpenAI-compatible
`MAEZ_PRIMARY_BASE_URL`, stop and amend the plan before changing code.
```

- [ ] **Step 4: Commit the proof**

Run:

```bash
git add docs/proofs/2026-06-24-routing-comprehension-backend-proof.md
git commit -m "docs(routing): prove comprehension judge backend seam"
```

## Task 1: Direct Classifier Path Uses PRIMARY_BASE_URL and Carries Metadata

**Files:**
- Modify: `core/routing/llm_client.py`
- Modify: `tests/test_brain_gateway_routing.py`

- [ ] **Step 1: Write failing tests for the direct path**

Append these tests to `tests/test_brain_gateway_routing.py` inside `RoutingTest`:

```python
    def test_chat_direct_uses_primary_openai_endpoint_when_backend_unset(self):
        gateway = BrainGateway()
        response = types.SimpleNamespace(
            message=types.SimpleNamespace(content='{"ok": true}'),
            finish_reason="stop",
            backend="primary_openai",
            thinking_suppressed=True,
        )

        with (
            mock.patch.dict(os.environ, {}, clear=False),
            mock.patch("core.routing.brain_gateway.GATEWAY", gateway),
            mock.patch.object(
                llm_client,
                "_chat_primary_openai",
                return_value=response,
            ) as fake_chat,
        ):
            out = llm_client.chat_direct(
                model="qwen36-27b",
                messages=[{"role": "user", "content": "classify"}],
                think=False,
                options={
                    "temperature": 0.0,
                    "num_predict": 320,
                    "chat_template_kwargs": {"enable_thinking": False},
                },
                purpose="routing_comprehension",
            )

        self.assertIs(out, response)
        fake_chat.assert_called_once_with(
            model="qwen36-27b",
            messages=[{"role": "user", "content": "classify"}],
            stream=False,
            think=False,
            options={
                "temperature": 0.0,
                "num_predict": 320,
                "chat_template_kwargs": {"enable_thinking": False},
            },
        )
        self.assertEqual(list(gateway.events), [])

    def test_primary_openai_direct_records_finish_backend_and_thinking_state(self):
        choice = types.SimpleNamespace(
            message=types.SimpleNamespace(content='{"decision":"ambiguous"}'),
            finish_reason="stop",
        )
        completion = types.SimpleNamespace(choices=[choice])
        client = types.SimpleNamespace(
            chat=types.SimpleNamespace(
                completions=types.SimpleNamespace(
                    create=mock.Mock(return_value=completion)
                )
            )
        )

        with (
            mock.patch(
                "core.routing.llm_client._get_openai_client_for_base",
                return_value=client,
            ),
            mock.patch(
                "core.routing.llm_client.PRIMARY_BASE_URL",
                "http://127.0.0.1:8080",
            ),
            mock.patch(
                "core.routing.llm_client.PRIMARY_MODEL",
                "qwen36-27b",
            ),
        ):
            out = llm_client._chat_primary_openai(
                model="qwen36-27b",
                messages=[{"role": "user", "content": "classify"}],
                stream=False,
                think=False,
                options={
                    "temperature": 0.0,
                    "num_predict": 320,
                    "chat_template_kwargs": {"enable_thinking": False},
                },
            )

        self.assertEqual(out.message.content, '{"decision":"ambiguous"}')
        self.assertEqual(out.finish_reason, "stop")
        self.assertEqual(out.backend, "primary_openai")
        self.assertTrue(out.thinking_suppressed)
        kwargs = client.chat.completions.create.call_args.kwargs
        self.assertEqual(kwargs["model"], "qwen36-27b")
        self.assertEqual(kwargs["max_tokens"], 320)
        self.assertEqual(
            kwargs["extra_body"],
            {"chat_template_kwargs": {"enable_thinking": False}},
        )

    def test_primary_openai_direct_records_length_finish_reason(self):
        choice = types.SimpleNamespace(
            message=types.SimpleNamespace(content=""),
            finish_reason="length",
        )
        completion = types.SimpleNamespace(choices=[choice])
        client = types.SimpleNamespace(
            chat=types.SimpleNamespace(
                completions=types.SimpleNamespace(
                    create=mock.Mock(return_value=completion)
                )
            )
        )

        with mock.patch(
            "core.routing.llm_client._get_openai_client_for_base",
            return_value=client,
        ):
            out = llm_client._chat_primary_openai(
                model="qwen36-27b",
                messages=[],
                stream=False,
                think=False,
                options={"num_predict": 320},
            )

        self.assertEqual(out.finish_reason, "length")
        self.assertTrue(out.thinking_suppressed)
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
cd /home/rohit/maez
.venv/bin/python -m unittest tests.test_brain_gateway_routing.RoutingTest -v
```

Expected: failure because `_chat_primary_openai` / `_get_openai_client_for_base` do not exist, and `chat_direct()` still dispatches through `active_backend()`.

- [ ] **Step 3: Implement the primary OpenAI direct path**

In `core/routing/llm_client.py`, update the imports near the model import:

```python
from core.model_config import PRIMARY_BASE_URL as _PRIMARY_BASE_URL
from core.model_config import PRIMARY_MODEL as _PRIMARY_MODEL
PRIMARY_BASE_URL = _PRIMARY_BASE_URL
PRIMARY_MODEL = _PRIMARY_MODEL
```

Replace the singleton with per-base-url clients:

```python
_openai_client_singletons: dict[str, Any] = {}


def _normalize_openai_base_url(base_url: str) -> str:
    base = str(base_url or "").rstrip("/")
    if not base:
        base = "http://127.0.0.1:8080"
    if not base.endswith("/v1"):
        base = f"{base}/v1"
    return base


def _get_openai_client_for_base(base_url: str):
    normalized = _normalize_openai_base_url(base_url)
    client = _openai_client_singletons.get(normalized)
    if client is None:
        from openai import OpenAI

        client = OpenAI(
            base_url=normalized,
            api_key='llamacpp',
        )
        _openai_client_singletons[normalized] = client
    return client
```

Keep `_get_openai_client()` as a compatibility shim:

```python
def _get_openai_client():
    return _get_openai_client_for_base(LLAMACPP_BASE_URL)
```

Extend `_LlmResponse`:

```python
@dataclass
class _LlmResponse:
    """Minimal ollama.ChatResponse-shaped object so consumers can call
    resp.message.content without caring which backend produced it."""
    message: _LlmMessage
    server_prompt_ms: Optional[int] = None
    finish_reason: Optional[str] = None
    backend: Optional[str] = None
    thinking_suppressed: Optional[bool] = None
```

Add this helper below `_chat_template_kwargs()` or above `_chat_openai_compat()`:

```python
def _thinking_suppressed(
    *,
    think: Optional[bool],
    options: Optional[dict],
) -> bool:
    try:
        return _chat_template_kwargs(think=think, options=options).get("enable_thinking") is False
    except Exception:
        return think is False
```

Add a shared OpenAI-compatible non-stream implementation:

```python
def _chat_openai_compat(
    *,
    base_url: str,
    backend_label: str,
    model: str,
    messages: list[dict],
    stream: bool = False,
    think: Optional[bool] = None,
    options: Optional[dict] = None,
    timeout_s: Optional[float] = None,
) -> _LlmResponse:
    if stream:
        raise BackendError("direct OpenAI-compatible classifier calls must be non-streaming")

    client = _get_openai_client_for_base(base_url)
    messages = _sanitize_messages_for_llamacpp(messages)

    temperature = 0.7
    max_tokens = 512
    if options:
        temperature = float(options.get("temperature", temperature))
        max_tokens = int(options.get("num_predict", max_tokens))

    extra_body: dict = {}
    merged = _chat_template_kwargs(think=think, options=options)
    if merged:
        extra_body["chat_template_kwargs"] = merged

    try:
        completion = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            extra_body=extra_body if extra_body else None,
            timeout=timeout_s,
        )
    except Exception as e:
        raise BackendError(f"{backend_label} chat failed: {e!r}") from e

    try:
        first = completion.choices[0]
        content = first.message.content or ""
        finish_reason = str(getattr(first, "finish_reason", "") or "")
        content = _strip_special_tokens(content)
    except Exception as e:
        raise BackendError(f"{backend_label} response parse failed: {e!r}") from e

    return _LlmResponse(
        message=_LlmMessage(content=content, thinking=None),
        finish_reason=finish_reason,
        backend=backend_label,
        thinking_suppressed=_thinking_suppressed(think=think, options=options),
    )
```

Refactor `_chat_llamacpp()` non-stream branch to call `_chat_openai_compat()`:

```python
    if not stream:
        return _chat_openai_compat(
            base_url=LLAMACPP_BASE_URL,
            backend_label=BACKEND_LLAMACPP,
            model=LLAMACPP_MODEL,
            messages=messages,
            stream=False,
            think=think,
            options=options,
            timeout_s=timeout_s,
        )
```

Add `_chat_primary_openai()`:

```python
def _chat_primary_openai(
    model: str,
    messages: list[dict],
    stream: bool = False,
    think: Optional[bool] = None,
    options: Optional[dict] = None,
) -> _LlmResponse:
    if stream:
        raise BackendError("primary direct classifier calls must be non-streaming")
    return _chat_openai_compat(
        base_url=PRIMARY_BASE_URL,
        backend_label="primary_openai",
        model=model or PRIMARY_MODEL,
        messages=messages,
        stream=False,
        think=think,
        options=options,
    )
```

Replace `chat_direct()` with:

```python
def chat_direct(
    model: str,
    messages: list[dict],
    think: Optional[bool] = None,
    options: Optional[dict] = None,
    purpose: Any = None,
) -> Any:
    """Direct non-gateway chat for tiny deterministic classifier calls.

    This intentionally uses the configured primary OpenAI-compatible
    endpoint, not the legacy backend selector. The routing-comprehension
    judge needs the same chat-template kwargs behavior proven on
    MAEZ_PRIMARY_BASE_URL.
    """
    del purpose
    return _chat_primary_openai(
        model=model,
        messages=messages,
        stream=False,
        think=think,
        options=options,
    )
```

- [ ] **Step 4: Run tests and verify they pass**

Run:

```bash
cd /home/rohit/maez
.venv/bin/python -m unittest tests.test_brain_gateway_routing.RoutingTest -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```bash
git add core/routing/llm_client.py tests/test_brain_gateway_routing.py
git commit -m "fix(routing): send direct judge calls to primary endpoint"
```

Commit body:

```text
The routing-comprehension judge is the only production caller of chat_direct.
The live daemon had MAEZ_PRIMARY_BASE_URL=:8080 but no MAEZ_LLM_BACKEND, so
chat_direct defaulted to Ollama and lost the proven chat_template_kwargs path.

## Predicted effect
With MAEZ_ROUTING_COMPREHENSION_SHADOW=1, live routing_comprehension receipts
should report backend=primary_openai, thinking_suppressed=True, finish_reason=stop,
and no parse_error on the four witness probes.
```

## Task 2: Content-Light Judge Diagnostics

**Files:**
- Modify: `core/routing/routing_comprehension.py`
- Modify: `tests/test_routing_comprehension.py`

- [ ] **Step 1: Write failing tests for diagnostics**

In `tests/test_routing_comprehension.py`, add `import hashlib` near the imports.

Append these tests inside `RoutingComprehensionPureTests`:

```python
    def test_parse_error_carries_content_light_diagnostics(self) -> None:
        raw = "<think>lots</think>"
        diagnostics = rc.JudgeDiagnostics(
            output_chars=len(raw),
            finish_reason="length",
            backend="primary_openai",
            thinking_suppressed=False,
            raw_sha256=hashlib.sha256(raw.encode("utf-8")).hexdigest(),
        )

        out = rc.parse_judge_response(raw, diagnostics=diagnostics)

        self.assertEqual(out.reason_code, "parse_error")
        self.assertEqual(out.diagnostics.output_chars, len(raw))
        self.assertEqual(out.diagnostics.finish_reason, "length")
        self.assertEqual(out.diagnostics.backend, "primary_openai")
        self.assertFalse(out.diagnostics.thinking_suppressed)
        self.assertEqual(out.diagnostics.raw_sha256, hashlib.sha256(raw.encode("utf-8")).hexdigest())

    def test_shadow_receipt_includes_diagnostics_without_raw_output(self) -> None:
        raw = '{"decision":"personal_or_relational","confidence":0.95,"reason_code":"owner_sharing"}'
        decision = rc.JudgeDecision(
            decision=rc.Decision.PERSONAL_OR_RELATIONAL,
            confidence=0.95,
            reason_code="owner_sharing",
            diagnostics=rc.JudgeDiagnostics(
                output_chars=len(raw),
                finish_reason="stop",
                backend="primary_openai",
                thinking_suppressed=True,
                raw_sha256=hashlib.sha256(raw.encode("utf-8")).hexdigest(),
            ),
        )

        receipt = rc.shadow_receipt(
            surface="telegram_surface",
            chat_id="secret-chat",
            decision=decision,
            trigger=rc.SearchTrigger(source="WEB_SEARCH", reason="current_world_request"),
            enabled=False,
            veto_applied=False,
        )

        self.assertIn("output_chars=", receipt)
        self.assertIn("finish_reason=stop", receipt)
        self.assertIn("backend=primary_openai", receipt)
        self.assertIn("thinking_suppressed=True", receipt)
        self.assertIn("raw_sha256=", receipt)
        self.assertNotIn(raw, receipt)
        self.assertNotIn("secret-chat", receipt)
        self.assertNotIn("personal_or_relational\",\"confidence", receipt)

    def test_llm_judge_threads_response_metadata_into_decision(self) -> None:
        raw = (
            '{"decision":"external_info_requested","confidence":0.95,'
            '"reason_code":"owner_asks_lookup"}'
        )
        response = SimpleNamespace(
            message=SimpleNamespace(content=raw),
            finish_reason="stop",
            backend="primary_openai",
            thinking_suppressed=True,
        )

        with (
            mock.patch("core.llm_client.chat", side_effect=AssertionError("gateway path")),
            mock.patch("core.llm_client.chat_direct", return_value=response, create=True),
        ):
            decision = rc.LlmEligibilityJudge().decide(
                rc.JudgeContext(current_turn="please look this up")
            )

        self.assertEqual(decision.decision, rc.Decision.EXTERNAL_INFO_REQUESTED)
        self.assertEqual(decision.diagnostics.finish_reason, "stop")
        self.assertEqual(decision.diagnostics.backend, "primary_openai")
        self.assertTrue(decision.diagnostics.thinking_suppressed)
        self.assertEqual(decision.diagnostics.output_chars, len(raw))
        self.assertEqual(decision.diagnostics.raw_sha256, hashlib.sha256(raw.encode("utf-8")).hexdigest())
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
cd /home/rohit/maez
.venv/bin/python -m unittest tests.test_routing_comprehension.RoutingComprehensionPureTests -v
```

Expected: FAIL because `JudgeDiagnostics` and `JudgeDecision.diagnostics` do not exist and receipts do not include diagnostic fields.

- [ ] **Step 3: Implement diagnostics**

In `core/routing/routing_comprehension.py`, update imports:

```python
import hashlib
from dataclasses import dataclass, field
```

Add constants near the other caps:

```python
diagnostic_value_cap = 80
sha256_hex_len = 64
```

Add this dataclass above `JudgeDecision`:

```python
@dataclass(frozen=True)
class JudgeDiagnostics:
    output_chars: int = 0
    finish_reason: str = ""
    backend: str = "unknown"
    thinking_suppressed: bool = False
    raw_sha256: str = ""
```

Extend `JudgeDecision`:

```python
@dataclass(frozen=True)
class JudgeDecision:
    decision: Decision
    confidence: float
    reason_code: str
    diagnostics: JudgeDiagnostics = field(default_factory=JudgeDiagnostics)
```

Add helpers near `_compact_reason`:

```python
def _sha256_text(text: str) -> str:
    return hashlib.sha256(str(text or "").encode("utf-8")).hexdigest()


def _diagnostics_from_response(raw: str, response) -> JudgeDiagnostics:
    return JudgeDiagnostics(
        output_chars=len(str(raw or "")),
        finish_reason=_compact_reason(str(getattr(response, "finish_reason", "") or "")),
        backend=_compact_reason(str(getattr(response, "backend", "") or "unknown")),
        thinking_suppressed=bool(getattr(response, "thinking_suppressed", False)),
        raw_sha256=_sha256_text(raw),
    )
```

Change `parse_judge_response` signature and return sites:

```python
def parse_judge_response(
    raw: str,
    *,
    diagnostics: JudgeDiagnostics | None = None,
) -> JudgeDecision:
    diag = diagnostics or JudgeDiagnostics(
        output_chars=len(str(raw or "")),
        raw_sha256=_sha256_text(raw),
    )
    try:
        ...
        return JudgeDecision(
            decision=decision,
            confidence=confidence,
            reason_code=reason_code,
            diagnostics=diag,
        )
    except Exception:
        return JudgeDecision(
            decision=ambiguous_decision,
            confidence=0.0,
            reason_code="parse_error",
            diagnostics=diag,
        )
```

In `LlmEligibilityJudge.decide`, replace:

```python
            message = getattr(response, "message", None)
            return parse_judge_response(getattr(message, "content", "") or "")
```

with:

```python
            message = getattr(response, "message", None)
            raw = getattr(message, "content", "") or ""
            return parse_judge_response(
                raw,
                diagnostics=_diagnostics_from_response(raw, response),
            )
```

In the exception path, return diagnostics:

```python
            return JudgeDecision(
                decision=ambiguous_decision,
                confidence=0.0,
                reason_code="judge_unavailable",
                diagnostics=JudgeDiagnostics(
                    backend="unavailable",
                    finish_reason="backend_error",
                    thinking_suppressed=False,
                ),
            )
```

Extend `shadow_receipt`:

```python
    diag = decision.diagnostics
    return (
        "routing_comprehension "
        ...
        f"veto_applied={bool(veto_applied)} "
        f"output_chars={max(0, int(diag.output_chars))} "
        f"finish_reason={_compact_reason(diag.finish_reason)} "
        f"backend={_compact_reason(diag.backend)} "
        f"thinking_suppressed={bool(diag.thinking_suppressed)} "
        f"raw_sha256={_clip(diag.raw_sha256, sha256_hex_len)}"
    )
```

- [ ] **Step 4: Run tests and verify they pass**

Run:

```bash
cd /home/rohit/maez
.venv/bin/python -m unittest tests.test_routing_comprehension.RoutingComprehensionPureTests -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```bash
git add core/routing/routing_comprehension.py tests/test_routing_comprehension.py
git commit -m "feat(routing): add content-light judge diagnostics"
```

Commit body:

```text
Diagnostics record output length, finish reason, backend, thinking suppression,
and a SHA-256 of raw judge output. The raw judge text and turn text are never
logged.

## Predicted effect
Shadow receipts should make any future parse_error self-explaining without
leaking the owner turn or model output.
```

## Task 3: Brain Loop Receipt Regression and No-Keyword Guard

**Files:**
- Modify: `tests/test_brain_loop.py`
- Modify: `tests/test_routing_comprehension.py`

- [ ] **Step 1: Add receipt diagnostics to a seam test**

In `tests/test_brain_loop.py`, update `test_shadow_logs_decision_but_external_search_still_runs`'s fake decision to include diagnostics:

```python
                return rc.JudgeDecision(
                    decision=rc.Decision.PERSONAL_OR_RELATIONAL,
                    confidence=0.96,
                    reason_code="owner_sharing_personal_state",
                    diagnostics=rc.JudgeDiagnostics(
                        output_chars=107,
                        finish_reason="stop",
                        backend="primary_openai",
                        thinking_suppressed=True,
                        raw_sha256="a" * 64,
                    ),
                )
```

Then add these assertions after the existing receipt assertions:

```python
        self.assertIn("output_chars=107", joined)
        self.assertIn("finish_reason=stop", joined)
        self.assertIn("backend=primary_openai", joined)
        self.assertIn("thinking_suppressed=True", joined)
        self.assertIn("raw_sha256=" + "a" * 64, joined)
```

- [ ] **Step 2: Add a no-keyword regression focused on the new code**

In `tests/test_routing_comprehension.py`, extend `test_structural_no_keyword_or_regex_intent_matching` with diagnostic words that must not sneak into logic as examples:

```python
        for diagnostic_only in ("output_chars", "finish_reason", "raw_sha256"):
            self.assertIn(diagnostic_only, src)
        for forbidden in ("gym", "stock", "price", "vulnerable"):
            self.assertNotIn(forbidden, src.lower())
```

- [ ] **Step 3: Run tests and verify failures before implementation if Task 2 was not yet applied**

If Task 2 has already landed, this may pass immediately because the new diagnostics exist. Run anyway:

```bash
cd /home/rohit/maez
.venv/bin/python -m unittest \
  tests.test_brain_loop.RoutingComprehensionShadow \
  tests.test_routing_comprehension.RoutingComprehensionPureTests \
  -v
```

Expected after Task 2: PASS.

- [ ] **Step 4: Commit**

Run:

```bash
git add tests/test_brain_loop.py tests/test_routing_comprehension.py
git commit -m "test(routing): pin comprehension diagnostics at brain seam"
```

## Task 4: Verification, Handoff, and STOP

**Files:**
- Create: `docs/handoffs/2026-06-24-routing-comprehension-backend-reliability-handoff.md`

- [ ] **Step 1: Run focused tests**

Run:

```bash
cd /home/rohit/maez
.venv/bin/python -m unittest \
  tests.test_brain_gateway_routing.RoutingTest \
  tests.test_routing_comprehension.RoutingComprehensionPureTests \
  tests.test_brain_loop.RoutingComprehensionShadow \
  -v
```

Expected: PASS.

- [ ] **Step 2: Run changed-surface lint**

Run:

```bash
cd /home/rohit/maez
.venv/bin/python -m ruff check \
  core/routing/llm_client.py \
  core/routing/routing_comprehension.py \
  tests/test_brain_gateway_routing.py \
  tests/test_routing_comprehension.py \
  tests/test_brain_loop.py
git diff --check
```

Expected:

```text
All checks passed!
```

and `git diff --check` prints nothing.

- [ ] **Step 3: Optional broad changed-surface run**

Run:

```bash
cd /home/rohit/maez
.venv/bin/python -m unittest \
  tests.test_brain_gateway_routing \
  tests.test_routing_comprehension \
  tests.test_brain_loop \
  -v
```

Expected: PASS or only known pre-existing unrelated failures. If any failure references the files changed in this slice, stop and fix before handoff.

- [ ] **Step 4: Write the handoff**

Create `docs/handoffs/2026-06-24-routing-comprehension-backend-reliability-handoff.md`:

```markdown
# Routing Comprehension Backend Reliability Handoff

Branch: routing-comprehension-backend-reliability
Status: STOPPED at review gate. Not enabled.

## What changed

- `chat_direct()` now routes deterministic classifier calls to the configured
  primary OpenAI-compatible endpoint (`PRIMARY_BASE_URL` / `MAEZ_PRIMARY_BASE_URL`)
  instead of defaulting to the legacy active backend.
- The OpenAI-compatible direct response carries `finish_reason`, `backend`, and
  `thinking_suppressed`.
- `routing_comprehension` receipts now include content-light diagnostics:
  `output_chars`, `finish_reason`, `backend`, `thinking_suppressed`, and
  `raw_sha256`.

## What did not change

- The 4-way judge contract did not change.
- The structural no-keyword guard still passes.
- `MAEZ_ROUTING_COMPREHENSION_ENABLED` remains owner-gated and must stay off
  until the live daemon shadow witness has zero `parse_error`.
- Normal owner replies still use `chat()` and the brain gateway.

## Why this was needed

The live daemon had `MAEZ_PRIMARY_BASE_URL=http://127.0.0.1:8080` and
`MAEZ_PRIMARY_CHAT_KWARGS={"enable_thinking": false}`, but no `MAEZ_LLM_BACKEND`.
Before this slice, `chat_direct()` defaulted to Ollama and lost the proven
`:8080` thinking-suppression path.

## Review anchors

1. `core/routing/llm_client.py`: `chat_direct()` calls `_chat_primary_openai()`.
2. `core/routing/llm_client.py`: `_chat_openai_compat()` forwards
   `chat_template_kwargs={"enable_thinking": false}` in `extra_body`.
3. `core/routing/llm_client.py`: `_LlmResponse` carries finish/backend/thinking
   metadata.
4. `core/routing/routing_comprehension.py`: `JudgeDiagnostics` is content-light.
5. `core/routing/routing_comprehension.py`: `shadow_receipt()` logs diagnostics
   but never raw model output or turn text.
6. `tests/test_routing_comprehension.py`: structural no-keyword guard still passes.

## Verification

Commands run:

```bash
.venv/bin/python -m unittest \
  tests.test_brain_gateway_routing.RoutingTest \
  tests.test_routing_comprehension.RoutingComprehensionPureTests \
  tests.test_brain_loop.RoutingComprehensionShadow \
  -v

.venv/bin/python -m ruff check \
  core/routing/llm_client.py \
  core/routing/routing_comprehension.py \
  tests/test_brain_gateway_routing.py \
  tests/test_routing_comprehension.py \
  tests/test_brain_loop.py

git diff --check
```

## Owner breath after review PASS

1. Merge.
2. Restart with `MAEZ_ROUTING_COMPREHENSION_SHADOW=1` and
   `MAEZ_ROUTING_COMPREHENSION_ENABLED` still off.
3. Repeat these probes until every applicable receipt has a typed decision,
   `finish_reason=stop`, `backend=primary_openai`, `thinking_suppressed=True`,
   and zero `parse_error`:
   - `I did legs today, I'm insecure about my legs`
   - `What's the latest on OpenAI today?`
   - `What did you check online for that?`
   - `I feel anxious about Nvidia stock today; check the latest price`
4. Only after the clean witness, flip `MAEZ_ROUTING_COMPREHENSION_ENABLED=1`.

## Still out

The anxious-to-S4 clinical-boundary reflex is separate. That turn may still be
intercepted before the routing-comprehension judge sees it.
```

- [ ] **Step 5: Commit handoff**

Run:

```bash
git add docs/handoffs/2026-06-24-routing-comprehension-backend-reliability-handoff.md
git commit -m "docs(routing): hand off comprehension backend reliability fix"
```

- [ ] **Step 6: STOP at review gate**

Do not merge. Do not enable. Report:

```text
Routing comprehension backend reliability is built and STOPPED at review gate.
ENABLED is still off. Shadow witness remains the owner gate.
```

## Plan Self-Review

- Spec requirement: proof on real daemon path, not raw `:8080`.
  - Covered by Task 0 live env proof and handoff witness.
- Spec requirement: zero parse_error across repeated probes before enable.
  - Covered by Task 4 owner breath; enable explicitly remains out of build scope.
- Spec requirement: content-light diagnostics.
  - Covered by Task 2 tests and implementation.
- Spec requirement: no keyword reflex.
  - Covered by existing structural guard and Task 3 extension.
- Spec requirement: default-off byte-identical.
  - Existing tests keep judge uncalled when both flags are off; no task changes flag semantics.
- Placeholder scan:
  - No red-flag markers remain.
- Type consistency:
  - `JudgeDiagnostics`, `JudgeDecision.diagnostics`, `_LlmResponse.finish_reason`, `_LlmResponse.backend`, and `_LlmResponse.thinking_suppressed` are defined before use.
